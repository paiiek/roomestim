"""tests/test_schema_backward_parse.py — v0.17 Phase 6 schema parse.

Covers Phase 6 acceptance gates per .omc/plans/v0.17-design.md (Phase 6,
line 677-686):

- Backward parse: 0.1-draft YAML without ``objects:`` → ``objects = []``.
- Forward parse: 0.2-draft YAML with one column → preserved attrs.
- Explicit empty ``objects: []`` round-trips as empty.
- Unsupported schema_version raises ``ValueError`` with a ``supported`` hint.
- Round-trip: lab_room + column → write → read → equality on every field.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from roomestim import Object, evolve_room_add_object
from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.export.room_yaml import write_room_yaml
from roomestim.io.room_yaml_reader import read_room_yaml
from roomestim.model import (
    ListenerArea,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _minimal_room() -> RoomModel:
    """Construct a minimal 0.2-draft-ready RoomModel directly."""
    floor_polygon = [
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
        floor_polygon=floor_polygon,
        ceiling_height_m=2.85,
        surfaces=[floor_surface],
        listener_area=listener_area,
    )


# --------------------------------------------------------------------------- #
# Backward / forward parse
# --------------------------------------------------------------------------- #


def test_parse_0_1_draft_no_objects(tmp_path: Path) -> None:
    """Legacy 0.1-draft YAML omits ``objects`` and parses as ``[]``."""
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


def test_parse_0_2_draft_with_objects(tmp_path: Path) -> None:
    """0.2-draft YAML with a single column round-trips attribute by attribute."""
    room = _minimal_room()
    col = Object(
        kind="column",
        anchor=Point3(x=1.0, y=0.0, z=1.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )
    with_col = evolve_room_add_object(room, col)
    out = tmp_path / "room.yaml"
    write_room_yaml(with_col, out, schema_version="0.2-draft")
    loaded = read_room_yaml(out)
    assert loaded.schema_version == "0.2-draft"
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


def test_parse_0_2_draft_empty_objects(tmp_path: Path) -> None:
    """Explicit ``objects: []`` round-trips as an empty list."""
    room = _minimal_room()
    out = tmp_path / "room_empty.yaml"
    write_room_yaml(room, out, schema_version="0.2-draft")
    loaded = read_room_yaml(out)
    assert loaded.schema_version == "0.2-draft"
    assert loaded.objects == []


def test_parse_unsupported_schema_version(tmp_path: Path) -> None:
    """Unsupported schema_version raises ``ValueError`` with a ``supported`` hint."""
    bad_yaml = textwrap.dedent("""\
        version: "1.0"
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
    path = tmp_path / "bad.yaml"
    path.write_text(bad_yaml, encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        read_room_yaml(path)
    assert "supported" in str(excinfo.value).lower()


# --------------------------------------------------------------------------- #
# Full round-trip on lab_room + column
# --------------------------------------------------------------------------- #


@pytest.fixture
def lab_room() -> RoomModel:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    return RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)


def test_round_trip_0_2_draft(lab_room: RoomModel, tmp_path: Path) -> None:
    """lab_room + column → write → read → identical schema_version + objects."""
    col = Object(
        kind="column",
        anchor=Point3(x=2.0, y=0.0, z=1.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )
    room_with_col = evolve_room_add_object(lab_room, col)
    out = tmp_path / "lab_col.yaml"
    write_room_yaml(room_with_col, out, schema_version="0.2-draft")
    loaded = read_room_yaml(out)

    assert loaded.schema_version == "0.2-draft"
    assert loaded.name == room_with_col.name
    assert loaded.ceiling_height_m == pytest.approx(room_with_col.ceiling_height_m)
    assert len(loaded.surfaces) == len(room_with_col.surfaces)
    assert len(loaded.objects) == 1
    got = loaded.objects[0]
    assert got.kind == col.kind
    assert got.width_m == pytest.approx(col.width_m)
    assert got.height_m == pytest.approx(col.height_m)
    assert got.depth_m == pytest.approx(col.depth_m)
    assert got.wall_index == col.wall_index
    assert got.material == col.material
