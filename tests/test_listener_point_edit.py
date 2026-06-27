"""tests/test_listener_point_edit.py — evolve_room_listener_point (D lever).

Recenters the coverage listener area on a user-specified seat (room-frame
metres), preserving the area's shape and ear height. The cheap, high-impact "D"
lever from PLACEMENT_SENSITIVITY_VERDICT.md.
"""
from __future__ import annotations

import numpy as np
import pytest

from roomestim.adapters.multiview import MultiviewAdapter
from roomestim.edit import evolve_room_listener_point


def _rough_cloud(seed: int = 0, n: int = 4000) -> np.ndarray:
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


@pytest.fixture
def room(tmp_path):
    p = tmp_path / "c.npz"
    np.savez(p, P_m=_rough_cloud().astype(np.float32))
    return MultiviewAdapter(up_axis="y").parse(p)


def test_listener_point_recenters_area(room):
    r = evolve_room_listener_point(room, 1.0, 1.0)
    assert r.listener_area.centroid.x == pytest.approx(1.0)
    assert r.listener_area.centroid.z == pytest.approx(1.0)


def test_listener_point_preserves_shape_and_height(room):
    la0 = room.listener_area
    r = evolve_room_listener_point(room, 1.0, 1.0)
    la1 = r.listener_area
    # same ear height
    assert la1.height_m == pytest.approx(la0.height_m)
    # same number of corners and same edge lengths (pure translation)
    assert len(la1.polygon) == len(la0.polygon)
    w0 = abs(la0.polygon[0].x - la0.polygon[1].x)
    w1 = abs(la1.polygon[0].x - la1.polygon[1].x)
    assert w1 == pytest.approx(w0)


def test_listener_point_does_not_mutate_input(room):
    cx0 = room.listener_area.centroid.x
    evolve_room_listener_point(room, 1.0, 1.0)
    assert room.listener_area.centroid.x == pytest.approx(cx0)  # frozen / replaced


def test_listener_point_outside_footprint_raises(room):
    with pytest.raises(ValueError, match="outside the room footprint"):
        evolve_room_listener_point(room, 99.0, 99.0)


@pytest.mark.parametrize("x,z", [(float("nan"), 1.0), (1.0, float("inf"))])
def test_listener_point_non_finite_raises(room, x, z):
    with pytest.raises(ValueError):
        evolve_room_listener_point(room, x, z)
