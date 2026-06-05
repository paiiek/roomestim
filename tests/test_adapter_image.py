"""ImageAdapter — in-gate, TORCH-FREE tests (ADR 0045 §image backend).

The geometry-assembly core (:func:`roomestim.adapters.image._corners_to_room`)
is exercised with a synthetic ``cor_id`` analytically inverted from a known
rectangular room, so no torch / real inference runs in-gate. A subprocess
boundary test asserts importing the module never pulls torch into
``sys.modules`` (gate #4), mirroring ``tests/test_vision_boundary.py``.
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pytest

from roomestim.adapters.base import CaptureAdapter, ScaleAnchor
from roomestim.adapters.image import (
    _MAX_PLAUSIBLE_RADIUS_M,
    _MIN_FLOOR_TAN,
    ImageAdapter,
    _corners_to_room,
)
from roomestim.export import write_room_yaml
from roomestim.io.room_yaml_reader import read_room_yaml
from roomestim.model import MaterialLabel

REPO_ROOT = Path(__file__).resolve().parent.parent

_PANO_W = 1024
_PANO_H = 512


def _synthetic_cor_id(
    floor_corners_xz: list[tuple[float, float]],
    *,
    cam_h: float,
    ceiling_height_m: float,
) -> list[tuple[float, float]]:
    """Analytically invert ``_corners_to_room``'s trig to a normalized cor_id.

    For a floor corner ``(x, z)`` at camera-relative radius ``r``:
      ``u = atan2(x, -z)`` (forward = -z), ``r = hypot(x, z)``,
      ``v_floor = -atan2(cam_h, r)`` (below horizon),
      ``v_ceil  =  atan2(ceiling_height_m - cam_h, r)`` (above horizon).
    Then map angles → pixel row/col → normalized ``[0, 1]`` and interleave
    ceiling-then-floor (HorizonNet order).
    """
    ceil_above = ceiling_height_m - cam_h
    rows: list[tuple[float, float]] = []
    for x, z in floor_corners_xz:
        u = math.atan2(x, -z)
        r = math.hypot(x, z)
        v_floor = -math.atan2(cam_h, r)
        v_ceil = math.atan2(ceil_above, r)

        col = (u / (2.0 * math.pi) + 0.5) * _PANO_W - 0.5
        u_norm = col / _PANO_W

        row_floor = (-v_floor / math.pi + 0.5) * _PANO_H - 0.5
        row_ceil = (-v_ceil / math.pi + 0.5) * _PANO_H - 0.5
        v_floor_norm = row_floor / _PANO_H
        v_ceil_norm = row_ceil / _PANO_H

        # ceiling row first, then floor row (even=ceiling, odd=floor).
        rows.append((u_norm, v_ceil_norm))
        rows.append((u_norm, v_floor_norm))
    return rows


# A 4.0 (x) by 3.0 (z) room, camera centred, cam_h=1.6, ceiling 2.7 m.
_CAM_H = 1.6
_CEIL = 2.7
_FLOOR_CORNERS = [
    (2.0, 1.5),
    (2.0, -1.5),
    (-2.0, -1.5),
    (-2.0, 1.5),
]


def _canned_cor_id() -> list[tuple[float, float]]:
    return _synthetic_cor_id(
        _FLOOR_CORNERS, cam_h=_CAM_H, ceiling_height_m=_CEIL
    )


def test_corners_to_room_geometry() -> None:
    room = _corners_to_room(_canned_cor_id(), _CAM_H, name="synthetic")

    assert room.provenance == "reconstructed"
    for surf in room.surfaces:
        assert surf.material == MaterialLabel.UNKNOWN

    xs = [p.x for p in room.floor_polygon]
    zs = [p.z for p in room.floor_polygon]
    assert (max(xs) - min(xs)) == pytest.approx(4.0, abs=0.05)
    assert (max(zs) - min(zs)) == pytest.approx(3.0, abs=0.05)

    assert room.ceiling_height_m == pytest.approx(_CEIL, abs=0.05)

    # Absolute corner recovery (not just bbox): each input corner appears in
    # the reconstructed floor ring. Guards against translation/scale drift the
    # bbox check would miss. (Trig sign/convention correctness is independently
    # validated against spike_metric.metric_layout in review.)
    recovered = [(p.x, p.z) for p in room.floor_polygon]
    for ex, ez in _FLOOR_CORNERS:
        assert any(
            rx == pytest.approx(ex, abs=0.05) and rz == pytest.approx(ez, abs=0.05)
            for rx, rz in recovered
        ), f"corner ({ex}, {ez}) not in recovered ring {recovered}"

    n_floor_edges = len(room.floor_polygon)
    n_walls = sum(1 for s in room.surfaces if s.kind == "wall")
    assert n_walls == n_floor_edges
    # floor + ceiling + one wall per edge.
    assert len(room.surfaces) == 2 + n_floor_edges


def test_near_horizon_corner_rejected() -> None:
    """A floor corner beyond the plausibility bound raises (F1 near-horizon guard).

    Replace one corner with a far (r >= 30 m) one so r > 20 m at cam_h=1.6. The
    far corner's floor-ray tangent is well above ``_MIN_FLOOR_TAN`` (so the NEW
    plausibility guard fires, not the old at-horizon skip).
    """
    far_x, far_z = 30.0, 0.0
    far_corners = [
        (far_x, far_z),  # r ~= 30 m -> exceeds the 20 m bound
        (2.0, -1.5),
        (-2.0, -1.5),
        (-2.0, 1.5),
    ]
    cor_id = _synthetic_cor_id(far_corners, cam_h=_CAM_H, ceiling_height_m=_CEIL)

    # Sanity: the far corner's depression-angle tangent is far above the old
    # at-horizon skip threshold, so this is the new guard, not the old skip.
    r_far = math.hypot(far_x, far_z)
    tan_floor_far = _CAM_H / r_far
    assert tan_floor_far > _MIN_FLOOR_TAN
    assert r_far > _MAX_PLAUSIBLE_RADIUS_M

    with pytest.raises(ValueError, match="(?i)plausibility|implausible|near-horizon"):
        _corners_to_room(cor_id, _CAM_H, name="far-corner")


def test_normal_room_not_falsely_rejected() -> None:
    """A normal 4x3 room (all corners well within 20 m) must NOT raise."""
    room = _corners_to_room(_canned_cor_id(), _CAM_H, name="normal")
    assert room.provenance == "reconstructed"
    assert len(room.floor_polygon) == 4


def test_plausibility_bound_is_a_boundary() -> None:
    """A corner just under 20 m passes; just over raises (boundary check)."""
    just_under = [
        (_MAX_PLAUSIBLE_RADIUS_M - 0.5, 0.0),
        (2.0, -1.5),
        (-2.0, -1.5),
        (-2.0, 1.5),
    ]
    cor_under = _synthetic_cor_id(just_under, cam_h=_CAM_H, ceiling_height_m=_CEIL)
    room = _corners_to_room(cor_under, _CAM_H, name="just-under")
    assert len(room.floor_polygon) == 4

    just_over = [
        (_MAX_PLAUSIBLE_RADIUS_M + 0.5, 0.0),
        (2.0, -1.5),
        (-2.0, -1.5),
        (-2.0, 1.5),
    ]
    cor_over = _synthetic_cor_id(just_over, cam_h=_CAM_H, ceiling_height_m=_CEIL)
    with pytest.raises(ValueError, match="(?i)plausibility|implausible|near-horizon"):
        _corners_to_room(cor_over, _CAM_H, name="just-over")


def test_all_corners_far_still_rejected() -> None:
    """ALL FOUR floor corners far (r ~= 30 m each) → raises on the first far corner.

    Documents that the all-far case raises (not just the mixed one-far case); the
    guard fires on the first out-of-bound corner it projects.
    """
    far = 30.0
    all_far_corners = [
        (far, 0.0),
        (0.0, -far),
        (-far, 0.0),
        (0.0, far),
    ]
    cor_id = _synthetic_cor_id(all_far_corners, cam_h=_CAM_H, ceiling_height_m=_CEIL)

    # Each corner is well beyond the 20 m bound and above the at-horizon skip.
    for x, z in all_far_corners:
        r = math.hypot(x, z)
        assert r > _MAX_PLAUSIBLE_RADIUS_M
        assert _CAM_H / r > _MIN_FLOOR_TAN

    with pytest.raises(ValueError, match="(?i)plausibility|implausible|near-horizon"):
        _corners_to_room(cor_id, _CAM_H, name="all-far")


def test_at_horizon_corner_still_skipped() -> None:
    """One at-horizon corner (v_floor ~= 0) is SILENTLY SKIPPED, not raised.

    Proves the new radius-raise did not shadow the old ``_MIN_FLOOR_TAN`` skip
    path: with one floor row at the horizon (tan(-v_floor) <= _MIN_FLOOR_TAN) the
    room still builds from the remaining 3 valid corners with no exception.

    The at-horizon floor row is constructed directly (v_floor ~= 0 -> normalized
    floor row 0.5), since ``_synthetic_cor_id`` cannot emit an exactly-horizon row.
    """
    # Three normal corners (ceiling-then-floor rows) from the helper.
    normal = _synthetic_cor_id(
        [(2.0, 1.5), (2.0, -1.5), (-2.0, -1.5)],
        cam_h=_CAM_H,
        ceiling_height_m=_CEIL,
    )

    # A 4th column whose FLOOR row sits at the horizon (v_floor ~= 0 -> tan ~= 0,
    # i.e. <= _MIN_FLOOR_TAN), so it is skipped. Its ceiling row is left valid;
    # the floor row's exact column is irrelevant since the column is skipped.
    u = math.atan2(-2.0, -1.5)
    col = (u / (2.0 * math.pi) + 0.5) * _PANO_W - 0.5
    u_norm = col / _PANO_W
    v_ceil = math.atan2(_CEIL - _CAM_H, math.hypot(-2.0, 1.5))
    row_ceil = (-v_ceil / math.pi + 0.5) * _PANO_H - 0.5
    v_ceil_norm = row_ceil / _PANO_H
    # Floor row at the horizon: invert the code's de-normalization so v_floor==0.
    # The core computes v_floor = -((row_f + 0.5)/_PANO_H - 0.5)*pi with
    # row_f = horizon_floor_norm * _PANO_H, so v_floor==0 needs
    # row_f == _PANO_H/2 - 0.5.
    horizon_floor_norm = (_PANO_H / 2.0 - 0.5) / _PANO_H

    cor_id = [*normal, (u_norm, v_ceil_norm), (u_norm, horizon_floor_norm)]

    # Confirm the constructed floor row really is at/above the horizon skip
    # threshold (tan(-v_floor) <= _MIN_FLOOR_TAN), exercising the OLD skip path.
    row_f = horizon_floor_norm * _PANO_H
    v_floor = -((row_f + 0.5) / _PANO_H - 0.5) * math.pi
    assert math.tan(-v_floor) <= _MIN_FLOOR_TAN

    # No raise: the at-horizon corner is silently skipped; the room builds from
    # the remaining 3 valid corners.
    room = _corners_to_room(cor_id, _CAM_H, name="at-horizon-skip")
    assert room.provenance == "reconstructed"
    assert len(room.floor_polygon) == 3


def test_corners_to_room_yaml_round_trip(tmp_path: Path) -> None:
    room = _corners_to_room(_canned_cor_id(), _CAM_H, name="synthetic")
    out = tmp_path / "room.yaml"
    write_room_yaml(room, out, schema_version="0.2-draft")
    back = read_room_yaml(out)
    assert back.provenance == "reconstructed"


def test_image_adapter_is_capture_adapter() -> None:
    assert isinstance(ImageAdapter(), CaptureAdapter)


def test_image_module_import_is_torch_free() -> None:
    """Importing the adapter module must not drag torch into sys.modules."""
    code = (
        "import roomestim.adapters.image; import sys; "
        "assert 'torch' not in sys.modules, "
        "'torch leaked into sys.modules via roomestim.adapters.image'; "
        "print('OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"torch-free import check failed.\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "OK" in result.stdout


def test_parse_without_scale_anchor_warns_assumed_height(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """parse() without a scale_anchor warns the scale is ASSUMED (OQ-58)."""
    import roomestim.adapters.image as image_mod

    canned = _canned_cor_id()
    monkeypatch.setattr(
        image_mod,
        "_infer_corners",
        lambda *a, **k: canned,
    )
    adapter = ImageAdapter()
    with pytest.warns(UserWarning, match="(?i)assumed.*camera height"):
        room = adapter.parse(Path("/tmp/does-not-matter.png"))
    assert room.provenance == "reconstructed"


def test_parse_with_scale_anchor_uses_measured_height(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import roomestim.adapters.image as image_mod

    canned = _canned_cor_id()
    monkeypatch.setattr(
        image_mod,
        "_infer_corners",
        lambda *a, **k: canned,
    )
    adapter = ImageAdapter()
    room = adapter.parse(
        Path("/tmp/p.png"),
        scale_anchor=ScaleAnchor("known_distance", _CAM_H),
    )
    xs = [p.x for p in room.floor_polygon]
    assert (max(xs) - min(xs)) == pytest.approx(4.0, abs=0.05)
