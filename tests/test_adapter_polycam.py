"""Tests for ``roomestim.adapters.polycam.PolycamAdapter`` — P5 acceptance."""

from __future__ import annotations

from pathlib import Path

import pytest
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.adapters import PolycamAdapter, RoomPlanAdapter
from roomestim.model import RoomModel

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
OBJ_PATH = FIXTURE_DIR / "lab_room.obj"
JSON_PATH = FIXTURE_DIR / "lab_room.json"
USDZ_PATH = FIXTURE_DIR / "lab_room.usdz"


def _floor_polygon_area(room: RoomModel) -> float:
    coords = [(p.x, p.z) for p in room.floor_polygon]
    return float(ShapelyPolygon(coords).area)


def _is_ccw(room: RoomModel) -> bool:
    coords = [(p.x, p.z) for p in room.floor_polygon]
    return bool(ShapelyPolygon(coords).exterior.is_ccw)


def test_a_polycam_obj_parses_to_roommodel() -> None:
    """OBJ shoebox parses to RoomModel with ceiling ~2.5 m, area ~16, >=4 walls."""
    room = PolycamAdapter().parse(OBJ_PATH)
    assert isinstance(room, RoomModel)
    assert room.ceiling_height_m == pytest.approx(2.5, abs=0.10)
    floor_area = _floor_polygon_area(room)
    assert floor_area == pytest.approx(16.0, rel=0.05), (
        f"floor area {floor_area} not within 5% of 16.0"
    )
    walls = [s for s in room.surfaces if s.kind == "wall"]
    assert len(walls) >= 4, f"expected >=4 walls, got {len(walls)}"
    assert _is_ccw(room), "floor polygon must be CCW"


def test_a_polycam_usdz_skip_or_raise() -> None:
    """USDZ path raises NotImplementedError (no usd extra in default CI)."""
    if USDZ_PATH.exists():
        # If a real fixture is present at some point, we still expect raise
        # in the default CI build (no `[usd]` extra installed).
        with pytest.raises(NotImplementedError):
            PolycamAdapter().parse(USDZ_PATH)
        return
    # No fixture: explicitly stub a name and confirm we still raise on the
    # extension. Use a non-existent path; the adapter dispatches on suffix
    # before any IO.
    with pytest.raises(NotImplementedError):
        PolycamAdapter().parse(FIXTURE_DIR / "missing_fixture.usdz")


def test_a_polycam_json_delegates_to_roomplan() -> None:
    """``.json`` path produces the same dimensions as RoomPlanAdapter."""
    polycam_room = PolycamAdapter().parse(JSON_PATH)
    roomplan_room = RoomPlanAdapter().parse(JSON_PATH)
    assert polycam_room.ceiling_height_m == pytest.approx(
        roomplan_room.ceiling_height_m, abs=1e-9
    )
    assert _floor_polygon_area(polycam_room) == pytest.approx(
        _floor_polygon_area(roomplan_room), rel=1e-9
    )
