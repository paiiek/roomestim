"""Characterization: the walls-only ⇄ full-surfaces index bridge (OQ-43 / D68).

``Object.wall_index`` lives in a WALLS-ONLY frame (predictor α overrides + the
web 3D viewer), while ``evolve_room_material`` indexes the FULL ``room.surfaces``
list. ``surface_index_for_wall`` is the single resolver that bridges the two:
``wall_surfaces(room)[k] is room.surfaces[surface_index_for_wall(room, k)]`` for
every wall ordinal ``k``.

This is the ``edit.py``-side analogue of ``tests/test_wall_index_frame.py``. It
pins the bridge across two distinct adapter orderings to prove the resolver is
ordering-independent (the latent condition that produced the v0.19.0 wall_index
defect): RoomPlan ``[floor, ceiling, wall×4]`` (lab_room.json) + an inline
synthetic ``[wall, wall, ceiling, floor]`` trailing-floor order (à la the ACE
adapter). See ADR 0037 + D68.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.model import (
    ListenerArea,
    MaterialAbsorption,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
    surface_index_for_wall,
    wall_surfaces,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "lab_room.json"


def _wall(x_offset: float) -> Surface:
    return Surface(
        kind="wall",
        polygon=[
            Point3(x=x_offset, y=0.0, z=0.0),
            Point3(x=x_offset + 1.0, y=0.0, z=0.0),
            Point3(x=x_offset + 1.0, y=2.5, z=0.0),
            Point3(x=x_offset, y=2.5, z=0.0),
        ],
        material=MaterialLabel.WALL_PAINTED,
        absorption_500hz=MaterialAbsorption[MaterialLabel.WALL_PAINTED],
    )


def _flat(kind: str, material: MaterialLabel) -> Surface:
    return Surface(
        kind=kind,  # type: ignore[arg-type]
        polygon=[
            Point3(x=0.0, y=0.0, z=0.0),
            Point3(x=1.0, y=0.0, z=0.0),
            Point3(x=1.0, y=0.0, z=1.0),
            Point3(x=0.0, y=0.0, z=1.0),
        ],
        material=material,
        absorption_500hz=MaterialAbsorption[material],
    )


def _trailing_floor_room() -> RoomModel:
    """Synthetic room with order [wall, wall, ceiling, floor] (ACE-style)."""
    surfaces = [
        _wall(0.0),
        _wall(2.0),
        _flat("ceiling", MaterialLabel.CEILING_DRYWALL),
        _flat("floor", MaterialLabel.WOOD_FLOOR),
    ]
    floor_polygon = [
        Point2(x=0.0, z=0.0),
        Point2(x=1.0, z=0.0),
        Point2(x=1.0, z=1.0),
        Point2(x=0.0, z=1.0),
    ]
    return RoomModel(
        name="synthetic_trailing_floor",
        floor_polygon=floor_polygon,
        ceiling_height_m=2.5,
        surfaces=surfaces,
        listener_area=ListenerArea(
            polygon=list(floor_polygon), centroid=Point2(x=0.5, z=0.5)
        ),
    )


def _assert_bridge(room: RoomModel) -> None:
    """For every wall ordinal k, the resolver maps to the same Surface object."""
    walls = wall_surfaces(room)
    assert walls, "room must have walls"
    for k in range(len(walls)):
        full_index = surface_index_for_wall(room, k)
        assert room.surfaces[full_index] is walls[k]
    # Out-of-range ordinal raises IndexError.
    with pytest.raises(IndexError):
        surface_index_for_wall(room, len(walls))


def test_bridge_roomplan_ordering() -> None:
    """RoomPlan [floor, ceiling, wall×4]: ordinal 2 maps to full index 4."""
    if not FIXTURE.exists():
        pytest.skip("lab_room.json fixture not found")
    room = RoomPlanAdapter().parse(FIXTURE)
    # lab_room surface order is [floor, ceiling, wall, wall, wall, wall].
    assert room.surfaces[0].kind == "floor"
    assert room.surfaces[1].kind == "ceiling"
    _assert_bridge(room)

    # Load-bearing: a NONZERO wall ordinal maps to a DIFFERENT full index than
    # itself (the exact divergence the v0.19.0 defect exploited). The 3rd wall
    # (ordinal 2) sits at full index 4 because [floor, ceiling] precede walls.
    assert surface_index_for_wall(room, 2) == 4


def test_bridge_trailing_floor_ordering() -> None:
    """Synthetic [wall, wall, ceiling, floor]: bridge holds for both walls."""
    room = _trailing_floor_room()
    assert room.surfaces[-1].kind == "floor"  # trailing floor (ACE-style)
    _assert_bridge(room)
    # Here ordinal 0 maps to full index 0 and ordinal 1 to full index 1
    # (walls lead), proving the resolver tracks the actual ordering, not a
    # fixed offset.
    assert surface_index_for_wall(room, 0) == 0
    assert surface_index_for_wall(room, 1) == 1
