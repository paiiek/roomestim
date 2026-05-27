"""Regression: ``Object.wall_index`` is resolved on the WALLS-ONLY frame.

Predictor side of the ① wall_index reference-frame fix (ADR 0037). A door at a
NONZERO ``wall_index`` makes the floor/ceiling-vs-wall divergence observable:
``lab_room.json`` has surface order ``[floor, ceiling, wall, wall, wall, wall]``,
so the full-surfaces frame at index 2 = the FIRST wall, while the walls-only
frame at index 2 = the THIRD wall. These are different surfaces.

The predictor (``_objects_to_wall_alpha_overrides``) already indexes the
walls-only list; this test locks that contract and supplies the shared
invariant the viewer test (``tests/web/test_wall_index_viewer.py``) mirrors.
"""

from __future__ import annotations

from pathlib import Path

from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.model import MaterialLabel, Object, Point3
from roomestim.reconstruct.predictor import _objects_to_wall_alpha_overrides

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "lab_room.json"

WALL_INDEX = 2  # nonzero → distinguishes walls-only frame from full-surfaces


def _door_at(wall_index: int) -> Object:
    return Object(
        kind="door",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=0.9,
        height_m=2.0,
        depth_m=0.0,
        wall_index=wall_index,
        material=MaterialLabel.WOOD_FLOOR,
    )


def test_predictor_resolves_wall_index_on_walls_only_frame() -> None:
    """The α override keys map into the walls-only list, never full surfaces."""
    room = RoomPlanAdapter().parse(FIXTURE)
    walls = [s for s in room.surfaces if s.kind == "wall"]
    assert len(walls) > WALL_INDEX, "fixture must have >wall_index walls"

    objects = [_door_at(WALL_INDEX)]
    overrides = _objects_to_wall_alpha_overrides(objects, walls)

    # The override is keyed by wall_index and that key indexes walls[WALL_INDEX].
    assert WALL_INDEX in overrides
    picked = walls[WALL_INDEX]
    assert picked.kind == "wall"

    # Load-bearing: the walls-only-frame surface is NOT the same object as the
    # full-surfaces-frame surface at the same index (the old viewer bug).
    assert room.surfaces[WALL_INDEX] is not picked
    assert room.surfaces[WALL_INDEX].kind in ("wall", "floor", "ceiling")
    # In lab_room, surfaces[2] is the FIRST wall; walls[2] is the THIRD wall.
    assert room.surfaces.index(picked) != WALL_INDEX


def test_predictor_picked_wall_matches_walls_only_index() -> None:
    """Shared invariant: predictor-picked surface == walls[wall_index] exactly."""
    room = RoomPlanAdapter().parse(FIXTURE)
    walls = [s for s in room.surfaces if s.kind == "wall"]
    overrides = _objects_to_wall_alpha_overrides([_door_at(WALL_INDEX)], walls)
    (idx,) = overrides.keys()
    assert walls[idx] is walls[WALL_INDEX]
