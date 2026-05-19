"""tests/test_objects_dataclass.py — v0.17 Phase 6 Object dataclass coverage.

Covers Phase 6 acceptance gates per .omc/plans/v0.17-design.md (Phase 6,
line 658-675):

- ``Object`` is a frozen dataclass; mutation → ``FrozenInstanceError``.
- ``DEFAULT_OBJECT_MATERIAL`` per-kind table (column/door/window).
- Door / window may be constructed with ``wall_index=None`` at the
  dataclass level (reader-level enforcement is a separate concern).
- ``RoomModel.objects`` defaults to an empty list.
- ``RoomModel.schema_version`` defaults to ``"0.2-draft"``.
- ``evolve_room_add_object`` / ``evolve_room_remove_object`` are pure /
  out-of-range removal raises ``IndexError`` with a ``valid range`` hint.
"""

from __future__ import annotations

import dataclasses

import pytest

from roomestim import (
    DEFAULT_OBJECT_MATERIAL,
    Object,
    evolve_room_add_object,
    evolve_room_remove_object,
)
from roomestim.model import (
    ListenerArea,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _minimal_room() -> RoomModel:
    """Construct a minimal RoomModel without touching adapters."""
    floor = [
        Point2(x=-2.5, z=-2.0),
        Point2(x=2.5, z=-2.0),
        Point2(x=2.5, z=2.0),
        Point2(x=-2.5, z=2.0),
    ]
    listener_area = ListenerArea(
        polygon=[
            Point2(x=-0.5, z=-0.5),
            Point2(x=0.5, z=-0.5),
            Point2(x=0.5, z=0.5),
            Point2(x=-0.5, z=0.5),
        ],
        centroid=Point2(x=0.0, z=0.0),
        height_m=1.2,
    )
    floor_surface = Surface(
        kind="floor",
        polygon=[
            Point3(x=-2.5, y=0.0, z=-2.0),
            Point3(x=2.5, y=0.0, z=-2.0),
            Point3(x=2.5, y=0.0, z=2.0),
            Point3(x=-2.5, y=0.0, z=2.0),
        ],
        material=MaterialLabel.WOOD_FLOOR,
        absorption_500hz=0.10,
    )
    return RoomModel(
        name="minimal",
        floor_polygon=floor,
        ceiling_height_m=2.85,
        surfaces=[floor_surface],
        listener_area=listener_area,
    )


def _make_column(anchor_x: float = 2.0) -> Object:
    return Object(
        kind="column",
        anchor=Point3(x=anchor_x, y=0.0, z=1.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )


# --------------------------------------------------------------------------- #
# Object frozen + dataclass identity
# --------------------------------------------------------------------------- #


def test_object_frozen() -> None:
    """``Object`` is a frozen dataclass; direct mutation must fail."""
    assert dataclasses.is_dataclass(Object)
    obj = _make_column()
    with pytest.raises(dataclasses.FrozenInstanceError):
        obj.width_m = 0.5  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# DEFAULT_OBJECT_MATERIAL per kind
# --------------------------------------------------------------------------- #


def test_object_default_material_per_kind() -> None:
    """Per-kind defaults: column→concrete, door→painted, window→glass."""
    assert DEFAULT_OBJECT_MATERIAL["column"] == MaterialLabel.WALL_CONCRETE
    assert DEFAULT_OBJECT_MATERIAL["door"] == MaterialLabel.WALL_PAINTED
    assert DEFAULT_OBJECT_MATERIAL["window"] == MaterialLabel.GLASS


# --------------------------------------------------------------------------- #
# wall_index field is unconstrained at the dataclass level
# --------------------------------------------------------------------------- #


def test_object_wall_index_constraint_column() -> None:
    """The dataclass permits any combination of ``kind`` × ``wall_index``.

    Schema-level enforcement (column → wall_index null, door/window →
    wall_index integer) lives in the reader; the dataclass itself is
    intentionally permissive.
    """
    # Column with wall_index=None is the normal case.
    col = Object(
        kind="column",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        wall_index=None,
    )
    assert col.wall_index is None

    # Door / window with wall_index=None: permitted at dataclass level.
    door = Object(
        kind="door",
        anchor=Point3(x=1.0, y=0.0, z=0.0),
        width_m=0.9,
        height_m=2.1,
        depth_m=0.0,
        wall_index=None,
    )
    assert door.wall_index is None
    window = Object(
        kind="window",
        anchor=Point3(x=1.0, y=1.0, z=0.0),
        width_m=1.2,
        height_m=1.2,
        depth_m=0.0,
        wall_index=None,
    )
    assert window.wall_index is None


# --------------------------------------------------------------------------- #
# RoomModel.objects + schema_version defaults
# --------------------------------------------------------------------------- #


def test_room_model_objects_default_empty() -> None:
    """A freshly-constructed RoomModel exposes ``objects == []``."""
    room = _minimal_room()
    assert room.objects == []
    assert isinstance(room.objects, list)


def test_room_model_schema_version_default() -> None:
    """RoomModel.schema_version defaults to ``"0.2-draft"`` (v0.17)."""
    room = _minimal_room()
    assert room.schema_version == "0.2-draft"


# --------------------------------------------------------------------------- #
# evolve_room_add_object / evolve_room_remove_object
# --------------------------------------------------------------------------- #


def test_evolve_room_add_object() -> None:
    """Adding an object yields a new room; original list is untouched."""
    room = _minimal_room()
    assert room.objects == []
    col = _make_column()
    new_room = evolve_room_add_object(room, col)
    assert len(new_room.objects) == 1
    assert new_room.objects[0] == col
    # Input list is not mutated.
    assert room.objects == []


def test_evolve_room_remove_object() -> None:
    """Removing index 0 of a two-object room keeps only the second."""
    room = _minimal_room()
    col_a = _make_column(anchor_x=1.0)
    col_b = _make_column(anchor_x=2.0)
    intermediate = evolve_room_add_object(room, col_a)
    two = evolve_room_add_object(intermediate, col_b)
    assert len(two.objects) == 2

    one = evolve_room_remove_object(two, 0)
    assert len(one.objects) == 1
    # Remaining object is the second (col_b).
    assert one.objects[0] == col_b


def test_evolve_room_remove_object_out_of_range() -> None:
    """Out-of-range index raises ``IndexError`` mentioning ``valid range``."""
    room = _minimal_room()
    col = _make_column()
    with_one = evolve_room_add_object(room, col)
    with pytest.raises(IndexError, match="valid range"):
        evolve_room_remove_object(with_one, 99)
