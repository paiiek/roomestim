"""tests/test_furniture_acoustic.py — Phase 2: furniture acoustic wiring.

Furniture (sofa/table/bed/storage) joins the column as a FREESTANDING object:
its bounding box is decomposed into 5 absorptive faces folded into the RT60
budget, and the RoomPlan adapter maps the matching CapturedRoomObject
categories. These tests pin:

- the furniture kinds are registered (FREESTANDING set + default materials);
- a furniture box emits 5 surfaces with its material (same shape as a column);
- adding an absorptive sofa LOWERS RT60 (a furnished room is deader);
- RoomPlan ``_extract_objects`` maps sofa/bed/table/storage (chair ignored),
  preserving depth for the free-standing box;
- a furniture object round-trips through the room.yaml reader.
- additive: no-furniture rooms are unaffected (column path intact).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from roomestim import evolve_room_add_object
from roomestim.adapters.roomplan import RoomPlanAdapter, _extract_objects
from roomestim.io.room_yaml_reader import _parse_object
from roomestim.model import (
    DEFAULT_OBJECT_MATERIAL,
    FREESTANDING_OBJECT_KINDS,
    WALL_ATTACHED_OBJECT_KINDS,
    MaterialLabel,
    Object as ObjectModel,
    Point3,
    RoomModel,
)
from roomestim.geom.polygon import polygon_area_3d
from roomestim.reconstruct.predictor import (
    _objects_to_surfaces,
    predict_rt60_default,
)

_FURNITURE_KINDS = ("sofa", "table", "bed", "storage")


def _area_dict(room: RoomModel) -> dict[MaterialLabel, float]:
    """Per-material area sums incl. object box surfaces — mirrors the production
    ``roomestim_web.report._surface_areas_by_material`` (folds object surfaces so
    ISM and the Eyring fallback both see furniture absorption)."""
    from collections import defaultdict

    areas: dict[MaterialLabel, float] = defaultdict(float)
    for s in room.surfaces:
        areas[s.material] += polygon_area_3d(s.polygon)
    for s in _objects_to_surfaces(list(room.objects)):
        areas[s.material] += polygon_area_3d(s.polygon)
    return dict(areas)


@pytest.fixture
def lab_room() -> RoomModel:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    return RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #


def test_furniture_kinds_freestanding_with_materials() -> None:
    for kind in _FURNITURE_KINDS:
        assert kind in FREESTANDING_OBJECT_KINDS
        assert kind not in WALL_ATTACHED_OBJECT_KINDS
        assert kind in DEFAULT_OBJECT_MATERIAL
    # Soft furnishings are absorptive; hard wooden pieces near the 0.10 floor.
    assert DEFAULT_OBJECT_MATERIAL["sofa"] is MaterialLabel.MISC_SOFT
    assert DEFAULT_OBJECT_MATERIAL["bed"] is MaterialLabel.MISC_SOFT
    assert DEFAULT_OBJECT_MATERIAL["table"] is MaterialLabel.WOOD_FLOOR
    assert DEFAULT_OBJECT_MATERIAL["storage"] is MaterialLabel.WOOD_FLOOR
    # Column remains free-standing; door/window remain wall-attached.
    assert "column" in FREESTANDING_OBJECT_KINDS
    assert WALL_ATTACHED_OBJECT_KINDS == frozenset({"door", "window"})


# --------------------------------------------------------------------------- #
# Box decomposition
# --------------------------------------------------------------------------- #


def test_furniture_box_emits_five_surfaces() -> None:
    sofa = ObjectModel(
        kind="sofa",
        anchor=Point3(1.0, 0.0, 1.0),
        width_m=2.0,
        height_m=0.9,
        depth_m=0.9,
        material=MaterialLabel.MISC_SOFT,
    )
    surfaces = _objects_to_surfaces([sofa])
    assert len(surfaces) == 5  # 4 sides + top, identical shape to a column
    assert sum(1 for s in surfaces if s.kind == "wall") == 4
    assert sum(1 for s in surfaces if s.kind == "ceiling") == 1
    assert all(s.material is MaterialLabel.MISC_SOFT for s in surfaces)


def test_door_window_emit_no_box_surfaces() -> None:
    """Wall-attached objects still produce no box surfaces (α-override path)."""
    door = ObjectModel(
        kind="door", anchor=Point3(0.0, 0.0, 0.0),
        width_m=0.9, height_m=2.0, depth_m=0.0, wall_index=0,
        material=MaterialLabel.WALL_PAINTED,
    )
    assert _objects_to_surfaces([door]) == []


# --------------------------------------------------------------------------- #
# Acoustic effect
# --------------------------------------------------------------------------- #


def test_absorptive_furniture_lowers_rt60(lab_room: RoomModel) -> None:
    base = predict_rt60_default(lab_room, _area_dict(lab_room)).rt60_s
    sofa = ObjectModel(
        kind="sofa",
        anchor=Point3(1.0, 0.0, 1.0),
        width_m=2.0,
        height_m=0.9,
        depth_m=0.9,
        material=MaterialLabel.MISC_SOFT,
    )
    room2 = evolve_room_add_object(lab_room, sofa)
    with_sofa = predict_rt60_default(room2, _area_dict(room2)).rt60_s
    # Adding absorptive surface area can only deaden the room.
    assert with_sofa < base
    # Sanity: a real, positive drop that does not collapse the room to silence.
    assert 0.0 < (base - with_sofa) < base
    assert with_sofa > 0.0


# --------------------------------------------------------------------------- #
# RoomPlan category mapping
# --------------------------------------------------------------------------- #


def _obj_entry(category: str, *, w: float = 1.0, h: float = 1.0, d: float = 0.5) -> dict:
    return {
        "category": category,
        "transform": [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [2.0, 0.0, 3.0, 1.0],  # USD row-vector: translation in last row
        ],
        "dimensions": [w, h, d],
    }


def test_roomplan_extract_furniture_categories() -> None:
    scan = {
        "objects": [
            _obj_entry("Sofa"),
            _obj_entry("couch"),
            _obj_entry("Bed"),
            _obj_entry("dining table"),
            _obj_entry("desk"),
            _obj_entry("storage"),
            _obj_entry("kitchen cabinet"),
            _obj_entry("refrigerator"),
            _obj_entry("chair"),  # ignored
            _obj_entry("toilet"),  # ignored
        ]
    }
    objs = _extract_objects(scan)
    kinds = [o.kind for o in objs]
    assert kinds == [
        "sofa", "sofa", "bed", "table", "table",
        "storage", "storage", "storage",
    ]
    # Free-standing furniture keeps its depth (box, not wall patch).
    assert all(o.depth_m == 0.5 for o in objs)
    # Default representative materials flow through when no hint is given.
    by_kind = {o.kind: o.material for o in objs}
    assert by_kind["sofa"] is MaterialLabel.MISC_SOFT
    assert by_kind["bed"] is MaterialLabel.MISC_SOFT
    assert by_kind["table"] is MaterialLabel.WOOD_FLOOR
    assert by_kind["storage"] is MaterialLabel.WOOD_FLOOR


# --------------------------------------------------------------------------- #
# room.yaml round-trip
# --------------------------------------------------------------------------- #


def test_furniture_object_parses_from_yaml_dict() -> None:
    parsed = _parse_object(
        {
            "kind": "sofa",
            "anchor": {"x": 1.0, "y": 0.0, "z": 1.0},
            "width_m": 2.0,
            "height_m": 0.9,
            "depth_m": 0.9,
        }
    )
    assert parsed.kind == "sofa"
    assert parsed.depth_m == pytest.approx(0.9)
    # Missing material falls back to the per-kind default.
    assert parsed.material is MaterialLabel.MISC_SOFT


def test_furniture_room_yaml_schema_round_trip(lab_room: RoomModel, tmp_path) -> None:
    """A furniture object survives a schema-VALIDATED write -> read round-trip.

    Pins the proto/room_schema.v0_2.draft.json furniture enum + oneOf branch:
    write_room_yaml and read_room_yaml both validate against that schema, so a
    missing furniture kind would raise here.
    """
    from roomestim.export.room_yaml import write_room_yaml
    from roomestim.io.room_yaml_reader import read_room_yaml

    sofa = ObjectModel(
        kind="sofa",
        anchor=Point3(1.0, 0.0, 1.0),
        width_m=2.0,
        height_m=0.9,
        depth_m=0.9,
        material=MaterialLabel.MISC_SOFT,
    )
    room = evolve_room_add_object(lab_room, sofa)
    out = tmp_path / "room.yaml"
    write_room_yaml(room, out)  # schema-validated on write
    back = read_room_yaml(out)  # schema-validated on read
    furn = [o for o in back.objects if o.kind == "sofa"]
    assert len(furn) == 1
    assert furn[0].depth_m == pytest.approx(0.9)
    assert furn[0].wall_index is None
    assert furn[0].material is MaterialLabel.MISC_SOFT


def test_invalid_object_kind_still_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid object kind"):
        _parse_object({"kind": "spaceship", "anchor": {"x": 0, "y": 0, "z": 0},
                       "width_m": 1.0, "height_m": 1.0})
