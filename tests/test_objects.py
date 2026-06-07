"""tests/test_objects.py — v0.17 Phase 1 ``Object`` dataclass + RoomModel.objects.

Covers Phase 1 acceptance gates per .omc/plans/v0.17-design.md §3 Phase 1:

- ``Object`` frozen dataclass: construction + ``dataclasses.replace`` only.
- ``RoomModel.objects`` default-empty contract.
- ``evolve_room_add_object`` / ``evolve_room_remove_object`` helpers.
- YAML round-trip with and without obstacles (0.2-draft).
- Backward parse for legacy ``0.1-draft`` YAML (objects → empty list).
- Unknown schema_version → ValueError.
- ``DEFAULT_OBJECT_MATERIAL`` per-kind table (D44 + ADR 0034 §C).
"""

from __future__ import annotations

import dataclasses
import textwrap
from pathlib import Path

import pytest

from roomestim import (
    DEFAULT_OBJECT_MATERIAL,
    Object,
    evolve_room_add_object,
    evolve_room_remove_object,
)
from roomestim.export.room_yaml import write_room_yaml
from roomestim.io.room_yaml_reader import read_room_yaml
from roomestim.model import (
    MaterialLabel,
    Point3,
    RoomModel,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def lab_room() -> RoomModel:
    """Synthetic shoebox via the RoomPlanAdapter (lab_room.json fixture)."""
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    from roomestim.adapters.roomplan import RoomPlanAdapter

    room = RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)
    assert isinstance(room, RoomModel)
    return room


# --------------------------------------------------------------------------- #
# Object dataclass
# --------------------------------------------------------------------------- #


def test_object_dataclass_frozen() -> None:
    """``Object`` is frozen — direct mutation raises ``FrozenInstanceError``."""
    obj = Object(
        kind="column",
        anchor=Point3(x=1.0, y=0.0, z=1.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
    )
    # Direct attribute mutation must fail.
    with pytest.raises(dataclasses.FrozenInstanceError):
        obj.width_m = 0.5  # type: ignore[misc]
    # dataclasses.replace produces a new instance with the field updated.
    obj2 = dataclasses.replace(obj, width_m=0.5)
    assert obj2.width_m == 0.5
    assert obj.width_m == 0.3  # original unchanged
    # Defaults: wall_index None for column, material UNKNOWN by default.
    assert obj.wall_index is None
    assert obj.material == MaterialLabel.UNKNOWN


# --------------------------------------------------------------------------- #
# RoomModel.objects default
# --------------------------------------------------------------------------- #


def test_room_model_objects_default_empty(lab_room: RoomModel) -> None:
    """A freshly-parsed RoomModel has ``objects == []`` by default."""
    # The lab_room fixture is produced by RoomPlanAdapter which targets
    # legacy 0.1-draft and therefore yields objects=[] via backward parse.
    assert lab_room.objects == []
    # And the field is the same value on a no-arg RoomModel (covered
    # separately by test_stage2_schema_flip via the shoebox factory; here
    # we just assert isinstance + iterability).
    assert isinstance(lab_room.objects, list)


# --------------------------------------------------------------------------- #
# evolve_room_add_object / evolve_room_remove_object
# --------------------------------------------------------------------------- #


def _make_column() -> Object:
    return Object(
        kind="column",
        anchor=Point3(x=1.0, y=0.0, z=1.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )


def test_evolve_room_add_object(lab_room: RoomModel) -> None:
    """Adding a column grows ``objects`` by one and preserves surfaces."""
    col = _make_column()
    new_room = evolve_room_add_object(lab_room, col)

    assert len(new_room.objects) == len(lab_room.objects) + 1
    assert new_room.objects[-1] == col
    # Surfaces and listener area are preserved (count and references).
    assert len(new_room.surfaces) == len(lab_room.surfaces)
    assert new_room.listener_area is lab_room.listener_area
    # Input list is not mutated.
    assert lab_room.objects == []


def test_evolve_room_remove_object(lab_room: RoomModel) -> None:
    """Adding then removing the same object restores ``objects = []``."""
    col = _make_column()
    room_with_col = evolve_room_add_object(lab_room, col)
    assert len(room_with_col.objects) == 1

    room_back = evolve_room_remove_object(room_with_col, 0)
    assert room_back.objects == []
    # Surfaces remain intact.
    assert len(room_back.surfaces) == len(lab_room.surfaces)


def test_evolve_room_remove_object_out_of_range(lab_room: RoomModel) -> None:
    """object_index outside valid range → IndexError with 'valid range' in msg."""
    with pytest.raises(IndexError, match="valid range"):
        evolve_room_remove_object(lab_room, 0)  # empty list, any index invalid
    col = _make_column()
    room_with_col = evolve_room_add_object(lab_room, col)
    with pytest.raises(IndexError, match="valid range"):
        evolve_room_remove_object(room_with_col, 5)
    with pytest.raises(IndexError, match="valid range"):
        evolve_room_remove_object(room_with_col, -1)


# --------------------------------------------------------------------------- #
# YAML round-trip
# --------------------------------------------------------------------------- #


def test_yaml_round_trip_no_objects(lab_room: RoomModel, tmp_path: Path) -> None:
    """Empty-objects round-trip via 0.2-draft: dump → load → identical objects."""
    out = tmp_path / "room.yaml"
    write_room_yaml(lab_room, out, schema_version="0.2-draft")
    loaded = read_room_yaml(out)

    assert loaded.objects == []
    assert loaded.schema_version == "0.2-draft"
    assert len(loaded.surfaces) == len(lab_room.surfaces)


def test_yaml_round_trip_with_column(lab_room: RoomModel, tmp_path: Path) -> None:
    """Adding a column → dump → load preserves the object list 1:1."""
    col = _make_column()
    room_with_col = evolve_room_add_object(lab_room, col)
    out = tmp_path / "room_col.yaml"
    write_room_yaml(room_with_col, out, schema_version="0.2-draft")
    loaded = read_room_yaml(out)

    assert len(loaded.objects) == 1
    got = loaded.objects[0]
    assert got.kind == "column"
    assert got.anchor.x == pytest.approx(1.0)
    assert got.anchor.y == pytest.approx(0.0)
    assert got.anchor.z == pytest.approx(1.0)
    assert got.width_m == pytest.approx(0.3)
    assert got.height_m == pytest.approx(2.85)
    assert got.depth_m == pytest.approx(0.3)
    assert got.wall_index is None
    assert got.material == MaterialLabel.WALL_CONCRETE


# --------------------------------------------------------------------------- #
# OQ-44(b): wall_index upper-bound enforced at load (reader)
# --------------------------------------------------------------------------- #


def test_read_room_yaml_rejects_out_of_range_wall_index(
    lab_room: RoomModel, tmp_path: Path
) -> None:
    """A door whose wall_index exceeds the wall count is rejected at load.

    The ``Object`` dataclass is context-free and cannot self-bound, so the read
    path is an independent entry point that must enforce the walls-only-frame
    bound (OQ-44(b) / D69). Without this guard the out-of-range index silently
    downgrades the whole-room RT60 to Eyring at predict time."""
    n_walls = sum(1 for s in lab_room.surfaces if s.kind == "wall")
    bad_door = Object(
        kind="door",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=0.9,
        height_m=2.0,
        depth_m=0.0,
        wall_index=n_walls + 5,  # out of range
        material=MaterialLabel.WALL_PAINTED,
    )
    room_with_bad = evolve_room_add_object(lab_room, bad_door)
    out = tmp_path / "room_bad_wall_index.yaml"
    write_room_yaml(room_with_bad, out, schema_version="0.2-draft")
    with pytest.raises(ValueError, match="out of range"):
        read_room_yaml(out)


def test_read_room_yaml_accepts_in_range_wall_index(
    lab_room: RoomModel, tmp_path: Path
) -> None:
    """An in-range wall_index round-trips cleanly (the guard is not over-eager)."""
    door = Object(
        kind="door",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=0.9,
        height_m=2.0,
        depth_m=0.0,
        wall_index=0,
        material=MaterialLabel.WALL_PAINTED,
    )
    room_with_door = evolve_room_add_object(lab_room, door)
    out = tmp_path / "room_ok_wall_index.yaml"
    write_room_yaml(room_with_door, out, schema_version="0.2-draft")
    loaded = read_room_yaml(out)
    assert len(loaded.objects) == 1
    assert loaded.objects[0].wall_index == 0


# --------------------------------------------------------------------------- #
# Backward / forward compatibility
# --------------------------------------------------------------------------- #


def test_yaml_backward_parse_0_1_draft(tmp_path: Path) -> None:
    """A legacy ``version: "0.1-draft"`` YAML parses with empty objects."""
    legacy_yaml = textwrap.dedent("""\
        version: "0.1-draft"
        name: legacy_room
        ceiling_height_m: 2.8
        floor_polygon:
          - {x: -2.5, z: -2.0}
          - {x: 2.5, z: -2.0}
          - {x: 2.5, z: 2.0}
          - {x: -2.5, z: 2.0}
        listener_area:
          centroid: {x: 0.0, z: 0.0}
          polygon:
            - {x: -0.75, z: -0.75}
            - {x: 0.75, z: -0.75}
            - {x: 0.75, z: 0.75}
            - {x: -0.75, z: 0.75}
          height_m: 1.2
        surfaces:
          - kind: floor
            material: wood_floor
            absorption_500hz: 0.10
            polygon:
              - {x: -2.5, y: 0.0, z: -2.0}
              - {x: 2.5, y: 0.0, z: -2.0}
              - {x: 2.5, y: 0.0, z: 2.0}
              - {x: -2.5, y: 0.0, z: 2.0}
    """)
    path = tmp_path / "legacy.yaml"
    path.write_text(legacy_yaml, encoding="utf-8")
    room = read_room_yaml(path)
    assert room.schema_version == "0.1-draft"
    assert room.objects == []


def test_yaml_invalid_schema_version(tmp_path: Path) -> None:
    """An unknown ``version`` raises ``ValueError('Unsupported...')``."""
    bad_yaml = textwrap.dedent("""\
        version: "0.9-future"
        name: future_room
        ceiling_height_m: 2.8
        floor_polygon:
          - {x: -1.0, z: -1.0}
          - {x: 1.0, z: -1.0}
          - {x: 1.0, z: 1.0}
          - {x: -1.0, z: 1.0}
        listener_area:
          centroid: {x: 0.0, z: 0.0}
          polygon:
            - {x: -0.5, z: -0.5}
            - {x: 0.5, z: -0.5}
            - {x: 0.5, z: 0.5}
            - {x: -0.5, z: 0.5}
          height_m: 1.2
        surfaces: []
    """)
    path = tmp_path / "future.yaml"
    path.write_text(bad_yaml, encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        read_room_yaml(path)


# --------------------------------------------------------------------------- #
# DEFAULT_OBJECT_MATERIAL
# --------------------------------------------------------------------------- #


def test_default_object_material_per_kind() -> None:
    """Per-kind defaults: obstacles (column/door/window) + furniture."""
    assert DEFAULT_OBJECT_MATERIAL["column"] == MaterialLabel.WALL_CONCRETE
    assert DEFAULT_OBJECT_MATERIAL["door"] == MaterialLabel.WALL_PAINTED
    assert DEFAULT_OBJECT_MATERIAL["window"] == MaterialLabel.GLASS
    # Furniture (Phase 2): soft → MISC_SOFT, hard wood → WOOD_FLOOR.
    assert DEFAULT_OBJECT_MATERIAL["sofa"] == MaterialLabel.MISC_SOFT
    assert DEFAULT_OBJECT_MATERIAL["bed"] == MaterialLabel.MISC_SOFT
    assert DEFAULT_OBJECT_MATERIAL["table"] == MaterialLabel.WOOD_FLOOR
    assert DEFAULT_OBJECT_MATERIAL["storage"] == MaterialLabel.WOOD_FLOOR
    # The documented kinds (obstacles + acoustically-wired furniture).
    assert set(DEFAULT_OBJECT_MATERIAL.keys()) == {
        "column", "door", "window", "sofa", "bed", "table", "storage",
    }
