"""v0.18 — layout.yaml round-trip fidelity contract (D50; ADR 0036 §C).

Level 1 ({VBAP, WFS}): position (≤1e-9) + channel + regularity + WFS meta + aim
direction (reader-restored) are structurally preserved. target_algorithm is
preserved only for {VBAP, WFS}; DBAP/AMBISONICS collapse to "VBAP" on read
(OQ-38). notes / per-speaker id are excluded (no engine schema slot).

Byte-equal idempotency (Gate 20/21/23) uses axis-aligned fixtures (az ∈
{0,90,180,270}°, el=0, integer radius) which are genuine single write→read→write
fixed points. Non-axis-aligned azimuths (e.g. 120°) drift by ~1 ULP in dist_m
through the cartesian↔spherical cycle and need several iterations to converge —
documented in the v0.18 design risk table and the verifier notes.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pytest
import yaml

from roomestim.export.layout_yaml import validate_placement, write_layout_yaml
from roomestim.io.placement_yaml_reader import read_placement_yaml
from roomestim.model import PlacedSpeaker, PlacementResult, Point3


def _axis_aligned_result(
    *,
    algorithm: str = "VBAP",
    regularity: str = "CIRCULAR",
    radius_m: float = 2.0,
    wfs_f_alias_hz: float | None = None,
    explicit_aim: bool = False,
) -> PlacementResult:
    """4 speakers at az {0,90,180,270}°, el=0 — a single-iteration fixed point."""
    speakers: list[PlacedSpeaker] = []
    for i, az_deg in enumerate((0.0, 90.0, 180.0, 270.0)):
        az = math.radians(az_deg)
        pos = Point3(x=radius_m * math.sin(az), y=0.0, z=radius_m * math.cos(az))
        aim = Point3(x=-pos.x, y=-pos.y, z=-pos.z) if explicit_aim else None
        speakers.append(PlacedSpeaker(channel=i + 1, position=pos, aim_direction=aim))
    return PlacementResult(
        target_algorithm=algorithm,
        regularity_hint=regularity,
        speakers=speakers,
        layout_name="axis",
        wfs_f_alias_hz=wfs_f_alias_hz,
    )


def _write(result: PlacementResult, path: Path) -> None:
    write_layout_yaml(result, path, validate=False)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_position_round_trip_within_1e9(tmp_path: Path) -> None:
    r = _axis_aligned_result()
    p = tmp_path / "layout.yaml"
    _write(r, p)
    r2 = read_placement_yaml(p)
    for a, b in zip(r.speakers, r2.speakers):
        assert b.position.x == pytest.approx(a.position.x, abs=1e-9)
        assert b.position.y == pytest.approx(a.position.y, abs=1e-9)
        assert b.position.z == pytest.approx(a.position.z, abs=1e-9)


def test_aim_restored_on_read(tmp_path: Path) -> None:
    r = _axis_aligned_result(explicit_aim=True)
    p = tmp_path / "layout.yaml"
    _write(r, p)
    r2 = read_placement_yaml(p)
    for a, b in zip(r.speakers, r2.speakers):
        assert b.aim_direction is not None
        # compare unit-normalized directions (aim carries direction only)
        am = math.sqrt(a.aim_direction.x ** 2 + a.aim_direction.y ** 2 + a.aim_direction.z ** 2)
        bm = math.sqrt(b.aim_direction.x ** 2 + b.aim_direction.y ** 2 + b.aim_direction.z ** 2)
        assert b.aim_direction.x / bm == pytest.approx(a.aim_direction.x / am, abs=1e-9)
        assert b.aim_direction.z / bm == pytest.approx(a.aim_direction.z / am, abs=1e-9)


def test_aim_absent_stays_none_when_keys_missing(tmp_path: Path) -> None:
    # writer always emits x_aim_*; this fixture is a hand-edited file with the
    # aim keys deleted to simulate a pre-v0.18 / hand-written layout.
    r = _axis_aligned_result()
    p = tmp_path / "layout.yaml"
    _write(r, p)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    for sp in data["speakers"]:
        sp.pop("x_aim_az_deg", None)
        sp.pop("x_aim_el_deg", None)
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    r2 = read_placement_yaml(p)
    assert all(s.aim_direction is None for s in r2.speakers)


def test_partial_aim_key_treated_as_missing(tmp_path: Path) -> None:
    r = _axis_aligned_result()
    p = tmp_path / "layout.yaml"
    _write(r, p)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    # leave x_aim_az_deg, drop x_aim_el_deg → exactly one present
    for sp in data["speakers"]:
        sp.pop("x_aim_el_deg", None)
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    r2 = read_placement_yaml(p)
    assert all(s.aim_direction is None for s in r2.speakers)


def test_idempotent_explicit_aim_rewrite_byte_equal(tmp_path: Path) -> None:
    r = _axis_aligned_result(explicit_aim=True)
    p1 = tmp_path / "a.yaml"
    p2 = tmp_path / "b.yaml"
    _write(r, p1)
    r2 = read_placement_yaml(p1)
    _write(r2, p2)
    assert _sha(p1) == _sha(p2)


def test_idempotent_default_aim_rewrite_byte_equal(tmp_path: Path) -> None:
    # never-authored aim (writer emits toward-origin); reader restores that
    # direction → second write hits the explicit branch and is byte-equal.
    r = _axis_aligned_result(explicit_aim=False)
    p1 = tmp_path / "a.yaml"
    p2 = tmp_path / "b.yaml"
    _write(r, p1)
    r2 = read_placement_yaml(p1)
    _write(r2, p2)
    assert _sha(p1) == _sha(p2)


def test_channel_regularity_wfs_preserved(tmp_path: Path) -> None:
    r = _axis_aligned_result(
        algorithm="WFS", regularity="LINEAR", wfs_f_alias_hz=1500.0
    )
    p = tmp_path / "layout.yaml"
    _write(r, p)
    r2 = read_placement_yaml(p)
    assert [s.channel for s in r2.speakers] == [s.channel for s in r.speakers]
    assert r2.regularity_hint == "LINEAR"
    assert r2.target_algorithm == "WFS"
    assert r2.wfs_f_alias_hz == pytest.approx(1500.0, abs=1e-9)


def test_dbap_target_algorithm_collapses_to_vbap(tmp_path: Path) -> None:
    # D50 honesty / OQ-38: DBAP has no round-trip label slot → reads as "VBAP".
    r = _axis_aligned_result(algorithm="DBAP", regularity="CIRCULAR")
    p = tmp_path / "layout.yaml"
    _write(r, p)
    r2 = read_placement_yaml(p)
    assert r2.target_algorithm == "VBAP"  # collapse (label not preserved)
    # position still preserved ≤1e-9
    for a, b in zip(r.speakers, r2.speakers):
        assert b.position.x == pytest.approx(a.position.x, abs=1e-9)
        assert b.position.z == pytest.approx(a.position.z, abs=1e-9)


def test_ambisonics_target_algorithm_collapses_to_vbap(tmp_path: Path) -> None:
    r = _axis_aligned_result(algorithm="AMBISONICS", regularity="CIRCULAR")
    p = tmp_path / "layout.yaml"
    _write(r, p)
    r2 = read_placement_yaml(p)
    assert r2.target_algorithm == "VBAP"


def test_edit_then_validate(tmp_path: Path) -> None:
    from roomestim.edit import nudge_speaker

    r = _axis_aligned_result()
    p = tmp_path / "layout.yaml"
    _write(r, p)
    loaded = read_placement_yaml(p)
    edited = nudge_speaker(loaded, 0, daz_deg=5.0)
    assert validate_placement(edited) == []


# --------------------------------------------------------------------------- #
# D56 fix-lock regression gates (v0.18.3; G10 / G11 / G12)
# --------------------------------------------------------------------------- #


def _n8_ring_result() -> PlacementResult:
    """8-speaker VBAP ring — the non-axis-aligned case that produced dirty floats."""
    from roomestim.place.vbap import place_vbap_ring

    return place_vbap_ring(n=8, radius_m=2.0, el_deg=0.0)


def test_noop_edit_empty_diff_non_axis_aligned(tmp_path: Path) -> None:
    """G10 — a zero-magnitude edit on a non-axis-aligned ring is byte-identical.

    This is the dogfood-reproduced defect turned into a permanent guard.
    Before D56, ``edit --speaker 0 --daz 0`` on the n8 ring produced a
    non-empty diff touching an unrelated speaker (x_aim_az_deg churn).
    """
    from roomestim.edit import nudge_speaker

    r = _n8_ring_result()
    in_path = tmp_path / "in.yaml"
    out_path = tmp_path / "out.yaml"
    _write(r, in_path)

    # Read → zero-magnitude nudge on speaker 0 → write.
    loaded = read_placement_yaml(in_path)
    edited = nudge_speaker(loaded, 0, daz_deg=0.0)
    _write(edited, out_path)

    assert in_path.read_bytes() == out_path.read_bytes(), (
        "no-op edit (--daz 0) on n8 ring produced non-empty diff — "
        "D56 writer normalization regression"
    )


def test_place_output_has_no_dirty_floats(tmp_path: Path) -> None:
    """G11 — every emitted numeric leaf equals its own round(v, 9).

    Asserts that the writer already normalized all degree/distance fields so
    no trailing-ULP noise (e.g. ``-135.00000000000003``) survives into the
    YAML text. The assertion is non-vacuous: it parses the written YAML and
    checks every float leaf.
    """
    import yaml as _yaml

    r = _n8_ring_result()
    p = tmp_path / "layout.yaml"
    _write(r, p)

    data = _yaml.safe_load(p.read_text(encoding="utf-8"))
    dirty: list[str] = []
    for sp in data["speakers"]:
        for key in ("az_deg", "el_deg", "dist_m", "x_aim_az_deg", "x_aim_el_deg"):
            v = sp[key]
            if v != round(v, 9):
                dirty.append(f"speaker {sp['id']} {key}={v!r}")

    assert dirty == [], (
        "D56 regression — emitted floats not normalized to 9 decimals: " + str(dirty)
    )


def test_idempotent_non_axis_aligned_rewrite_byte_equal(tmp_path: Path) -> None:
    """G12 — write→read→write is a byte-equal fixed point on a non-axis-aligned layout.

    Before D56 this was NOT byte-equal (the second write produced different dirty
    floats than the first). Confirms single-iteration convergence post-fix.
    """
    r = _n8_ring_result()
    p1 = tmp_path / "a.yaml"
    p2 = tmp_path / "b.yaml"
    _write(r, p1)
    r2 = read_placement_yaml(p1)
    _write(r2, p2)
    assert _sha(p1) == _sha(p2), (
        "non-axis-aligned write→read→write not byte-equal — "
        "D56 idempotency regression"
    )
