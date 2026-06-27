"""tests/test_multiview_scale_anchor.py — floor-length metric scale anchor.

MultiviewAdapter honors a ``ScaleAnchor("known_floor_length", L)``: a raw
VGGT/multiview cloud is NOT metric-native (per-room 1–5x off), so re-scaling
the cloud until the convex footprint's longest dimension equals the user's known
floor length anchors it to metric. See PLACEMENT_SENSITIVITY_VERDICT.md.
"""
from __future__ import annotations

import numpy as np
import pytest

import roomestim.geom.polygon as gp
from roomestim.adapters.base import ScaleAnchor
from roomestim.adapters.multiview import MultiviewAdapter, _footprint_diameter


def _rough_cloud(seed: int = 0, n: int = 4000) -> np.ndarray:
    """Y-up 4 x 3 m room (diagonal 5.0 m), floor + walls to 1.5 m only."""
    rng = np.random.default_rng(seed)
    pts = []
    for _ in range(n):
        pts.append([rng.uniform(0, 4), 0.0, rng.uniform(0, 3)])
    for _ in range(n):
        y = rng.uniform(0, 1.5)
        e = int(rng.integers(0, 4))
        pts.append(
            [
                [rng.uniform(0, 4), y, 0.0],
                [rng.uniform(0, 4), y, 3.0],
                [0.0, y, rng.uniform(0, 3)],
                [4.0, y, rng.uniform(0, 3)],
            ][e]
        )
    return np.asarray(pts, dtype=float)


def _save(tmp_path, cloud, name="c.npz"):
    p = tmp_path / name
    np.savez(p, P_m=cloud.astype(np.float32))
    return p


def _area(room) -> float:
    return gp.shoelace_2d([(p.x, p.z) for p in room.floor_polygon])


def test_anchor_sets_footprint_diameter_to_known_length(tmp_path):
    """A 2.5x mis-scaled cloud → anchored footprint diameter == known length."""
    p = _save(tmp_path, _rough_cloud() * 2.5)
    room = MultiviewAdapter(up_axis="y").parse(
        p, scale_anchor=ScaleAnchor("known_floor_length", 5.0)
    )
    assert _footprint_diameter(room) == pytest.approx(5.0, abs=1e-6)


def test_anchor_is_scale_invariant(tmp_path):
    """Different input cloud scales anchor to the SAME metric footprint area."""
    anchor = ScaleAnchor("known_floor_length", 5.0)
    r_big = MultiviewAdapter(up_axis="y").parse(
        _save(tmp_path, _rough_cloud() * 2.5, "big.npz"), scale_anchor=anchor
    )
    r_small = MultiviewAdapter(up_axis="y").parse(
        _save(tmp_path, _rough_cloud() * 0.37, "small.npz"), scale_anchor=anchor
    )
    assert _area(r_big) == pytest.approx(_area(r_small), abs=1e-3)
    # 4x3 room → diagonal 5.0 anchors area back to ~12 m².
    assert _area(r_big) == pytest.approx(12.0, rel=0.05)


def test_no_anchor_preserves_input_scale(tmp_path):
    """Without an anchor the cloud is assumed metric-native (unscaled)."""
    p = _save(tmp_path, _rough_cloud() * 2.5)
    room = MultiviewAdapter(up_axis="y").parse(p)
    # 2.5x cloud → ~2.5x the diagonal (12.5 m), i.e. left as-is.
    assert _footprint_diameter(room) == pytest.approx(12.5, rel=0.05)


def test_anchor_rejects_wrong_type(tmp_path):
    p = _save(tmp_path, _rough_cloud())
    with pytest.raises(ValueError, match="known_floor_length"):
        MultiviewAdapter(up_axis="y").parse(
            p, scale_anchor=ScaleAnchor("known_distance", 1.5)
        )


@pytest.mark.parametrize("bad", [0.0, -2.0, float("nan"), 200.0])
def test_anchor_rejects_implausible_length(tmp_path, bad):
    p = _save(tmp_path, _rough_cloud())
    with pytest.raises(ValueError):
        MultiviewAdapter(up_axis="y").parse(
            p, scale_anchor=ScaleAnchor("known_floor_length", bad)
        )


def test_anchor_composes_with_ceiling_override(tmp_path):
    """Anchor (footprint scale) and ceiling override (absolute m) are independent."""
    p = _save(tmp_path, _rough_cloud() * 2.5)
    room = MultiviewAdapter(up_axis="y", ceiling_height_m=2.7).parse(
        p, scale_anchor=ScaleAnchor("known_floor_length", 5.0)
    )
    assert _footprint_diameter(room) == pytest.approx(5.0, abs=1e-6)
    assert room.ceiling_height_m == pytest.approx(2.7)
