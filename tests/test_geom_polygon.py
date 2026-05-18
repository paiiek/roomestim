"""tests/test_geom_polygon.py — roomestim.geom.polygon shared util (v0.15.1).

Covers:
  - polygon_area_3d: unit square in 3-D.
  - room_volume: lab_room L=5 W=4 H=2.85.
  - shoelace_2d: unit square.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from roomestim.geom.polygon import polygon_area_3d, room_volume, shoelace_2d


@pytest.fixture
def lab_room() -> object:
    from roomestim.adapters.roomplan import RoomPlanAdapter

    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    return RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)


def test_polygon_area_3d_unit_square() -> None:
    """Unit square in the XZ plane at y=0 has area 1.0."""

    class _Pt:
        def __init__(self, x: float, y: float, z: float) -> None:
            self.x = x
            self.y = y
            self.z = z

    polygon = [_Pt(0, 0, 0), _Pt(1, 0, 0), _Pt(1, 0, 1), _Pt(0, 0, 1)]
    assert abs(polygon_area_3d(polygon) - 1.0) < 1e-9


def test_room_volume_lab_room(lab_room: object) -> None:
    """lab_room L=5 W=4 H=2.85 → volume = 57.0 m³."""
    vol = room_volume(lab_room)  # type: ignore[arg-type]
    assert abs(vol - 57.0) < 1e-9, f"Expected 57.0 m³, got {vol}"


def test_shoelace_2d_unit_square() -> None:
    """Unit square coords → area 1.0."""
    coords = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    assert abs(shoelace_2d(coords) - 1.0) < 1e-9
