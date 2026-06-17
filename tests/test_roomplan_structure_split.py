"""Unit tests for the CapturedStructure -> N-RoomModel splitter (ADR 0050, S1).

Structural / sanity ONLY — the fixtures have no independent ground truth, so
there are NO accuracy assertions (the per-room split is a documented HEURISTIC
reconstruction, see ``ROOMPLAN_STRUCTURE_SPLIT_NOTE``).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon

from roomestim.adapters.roomplan_structure import _mat4_from_flat, parse_structure

_FIXTURES = Path(__file__).parent / "fixtures" / "roomplan_real"
_MULTI = _FIXTURES / "capturedstructure_multiroom.json"
_SINGLE = _FIXTURES / "capturedstructure_single.json"

def _wall_count(room: object) -> int:
    return sum(1 for s in room.surfaces if s.kind == "wall")  # type: ignore[attr-defined]


def test_multiroom_yields_four_rooms_including_unidentified() -> None:
    rooms = parse_structure(_MULTI)
    assert len(rooms) == 4
    names = [r.name for r in rooms]
    # Two same-label bedrooms kept distinct (deterministic -2 suffix); the
    # unidentified section is preserved as its own room, never merged.
    assert names == ["bedroom", "bedroom-2", "bathroom", "unidentified"]


def test_partition_invariant_every_wall_assigned_once() -> None:
    rooms = parse_structure(_MULTI)
    total = sum(_wall_count(r) for r in rooms)
    # The fixture has 20 walls; the heuristic partition is total (no drop / dup).
    assert total == 20
    # Observed real partition on this fixture: 5 / 6 / 3 / 6 (no degenerate).
    assert [_wall_count(r) for r in rooms] == [5, 6, 3, 6]


def test_each_footprint_finite_and_positive() -> None:
    rooms = parse_structure(_MULTI)
    for room in rooms:
        coords = [(p.x, p.z) for p in room.floor_polygon]
        poly = Polygon(coords)
        assert poly.is_valid
        assert np.isfinite(poly.area)
        assert poly.area > 0.0
        # Coordinates are finite (reject NaN/inf blowups). NO building-bbox bound
        # is asserted: wall positions are in the world frame while the export's
        # single floors[] polygon is in the FLOOR's local transform frame, so the
        # two are not directly comparable — claiming a shared bbox would be a
        # fabricated bound.
        for x, z in coords:
            assert np.isfinite(x) and np.isfinite(z)


def test_ceiling_height_in_plausible_band() -> None:
    rooms = parse_structure(_MULTI)
    for room in rooms:
        assert 2.0 <= room.ceiling_height_m <= 3.5
        # Synthesized from wall heights — not a measured ceiling.
        assert room.ceiling_coverage is None
        assert room.ceiling_confidence == "unknown"


def test_provenance_measured() -> None:
    rooms = parse_structure(_MULTI)
    for room in rooms:
        assert room.provenance == "measured"  # LiDAR geometry


def test_objects_assigned_per_existing_kind_policy() -> None:
    """S2: 13 raw objects -> 10 kept furniture (sofa/table/bed/storage); the 3
    chair/sink/toilet are dropped per the existing single-room RoomPlan policy."""
    rooms = parse_structure(_MULTI)
    furniture = Counter(
        o.kind
        for r in rooms
        for o in r.objects
        if o.kind not in ("door", "window")
    )
    # bed x2, sofa x1, table x4, storage x3 = 10 kept (chair/sink/toilet dropped).
    assert sum(furniture.values()) == 10
    assert set(furniture) <= {"sofa", "table", "bed", "storage"}
    assert "chair" not in furniture
    assert furniture["table"] == 4
    assert furniture["storage"] == 3
    assert furniture["bed"] == 2
    assert furniture["sofa"] == 1


def test_doors_windows_assigned_and_wall_index_in_range() -> None:
    """S2: every door/window is routed to a room and its re-based wall_index is
    in-range for THAT room's walls-only frame (ADR 0037 guard never trips)."""
    rooms = parse_structure(_MULTI)
    doors = sum(1 for r in rooms for o in r.objects if o.kind == "door")
    windows = sum(1 for r in rooms for o in r.objects if o.kind == "window")
    assert doors == 4
    assert windows == 4
    for room in rooms:
        n_walls = _wall_count(room)
        for obj in room.objects:
            if obj.kind in ("door", "window") and obj.wall_index is not None:
                assert 0 <= obj.wall_index < n_walls


def test_single_section_yields_one_room() -> None:
    rooms = parse_structure(_SINGLE)
    assert len(rooms) == 1
    assert rooms[0].name == "livingRoom"
    assert _wall_count(rooms[0]) == 4


def test_mat4_from_flat_origin_and_width_axis() -> None:
    # Real wall[0] transform (multiroom). reshape(4,4).T -> col3 = origin,
    # col0 = unit width-dir, matching roomplan._wall_polygon_from_transform.
    flat = [
        0.029369948, 0, 0.9995687, 0,
        0, 1, 0, 0,
        -0.9995686, 0, 0.02936996, 0,
        4.0551653, -0.26515633, -4.3787866, 1,
    ]
    m = _mat4_from_flat(flat)
    assert m.shape == (4, 4)
    np.testing.assert_allclose(m[:3, 3], [4.0551653, -0.26515633, -4.3787866])
    np.testing.assert_allclose(m[:3, 0], [0.029369948, 0, 0.9995687])
    assert abs(float(np.linalg.norm(m[:3, 0])) - 1.0) < 1e-3


def test_degenerate_section_does_not_crash(tmp_path: Path) -> None:
    """A section that receives 0 walls must not crash (S1 hardening floor).

    Full UserWarning hardening is S3; S1 only guarantees a constructible,
    finite, positive-area minimal footprint instead of an exception.
    """
    data = json.loads(_MULTI.read_text(encoding="utf-8"))
    # Append a section whose center is far from every wall on the same story, so
    # the nearest-center heuristic assigns it 0 walls.
    data["sections"].append(
        {"center": [100.0, -0.25, 100.0], "label": "faraway", "story": 0}
    )
    p = tmp_path / "degenerate.json"
    p.write_text(json.dumps(data), encoding="utf-8")

    rooms = parse_structure(p)
    assert len(rooms) == 5
    far = rooms[-1]
    assert far.name == "faraway"
    assert _wall_count(far) == 0
    poly = Polygon([(pt.x, pt.z) for pt in far.floor_polygon])
    assert poly.area > 0.0  # minimal box, not an exception
    # The 20 real walls are still partitioned exactly once across the rooms.
    assert sum(_wall_count(r) for r in rooms) == 20


def test_degenerate_section_emits_userwarning(tmp_path: Path) -> None:
    """S3: a section with < 3 assigned walls warns (not crashes)."""
    data = json.loads(_MULTI.read_text(encoding="utf-8"))
    data["sections"].append(
        {"center": [100.0, -0.25, 100.0], "label": "faraway", "story": 0}
    )
    p = tmp_path / "degenerate.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.warns(UserWarning, match="LOW-CONFIDENCE"):
        rooms = parse_structure(p)
    assert rooms[-1].name == "faraway"


def test_unidentified_section_kept_as_room() -> None:
    """S3: the `unidentified` section is preserved as its own room, never merged."""
    rooms = parse_structure(_MULTI)
    names = [r.name for r in rooms]
    assert "unidentified" in names
    uid = next(r for r in rooms if r.name == "unidentified")
    assert _wall_count(uid) > 0  # received walls via nearest-center, not dropped


def test_equidistant_tie_break_lowest_section_index(tmp_path: Path) -> None:
    """S3: a wall equidistant between two sections is deterministically assigned
    to the LOWEST section index."""
    # Two sections symmetric about x=0; one wall at the origin is equidistant.
    flat = [
        1.0, 0, 0, 0,
        0, 1, 0, 0,
        0, 0, 1, 0,
        0.0, 0.0, 0.0, 1,
    ]
    data = {
        "version": 2,
        "story": 0,
        "sections": [
            {"center": [-1.0, -0.25, 0.0], "label": "left", "story": 0},
            {"center": [1.0, -0.25, 0.0], "label": "right", "story": 0},
        ],
        "walls": [
            {"category": {"wall": {}}, "dimensions": [2.0, 2.44, 0.0],
             "transform": flat, "identifier": "W0", "story": 0}
        ],
        "doors": [], "windows": [], "openings": [], "objects": [], "floors": [],
    }
    p = tmp_path / "tie.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.warns(UserWarning):  # both sections are degenerate (< 3 walls)
        rooms = parse_structure(p)
    # The equidistant wall lands in section 0 ("left"), not section 1.
    assert _wall_count(rooms[0]) == 1
    assert _wall_count(rooms[1]) == 0


def test_openings_ingested_on_wall_path(tmp_path: Path) -> None:
    """S3: an `openings[]` entry is ingested as a wall-like surface (counts as a
    wall in its assigned room)."""
    data = json.loads(_MULTI.read_text(encoding="utf-8"))
    base_walls = sum(
        1 for w in data["walls"] if next(iter(w["category"])) == "wall"
    )
    # Copy a real wall's geometry into the openings[] array (same schema).
    one_wall = dict(data["walls"][0])
    one_wall["identifier"] = "OPENING-TEST-0"
    data["openings"] = [one_wall]
    p = tmp_path / "with_opening.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    rooms = parse_structure(p)
    total_walls = sum(_wall_count(r) for r in rooms)
    # The opening adds exactly one wall-like surface to the partition.
    assert total_walls == base_walls + 1 == 21
