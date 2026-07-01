"""Tests for obstacle-aware Mode B placement (P7.1) + DBAP byte-equal parity.

Covers:
  * ``place_dbap(candidate_filter=None)`` is byte-equal to the pre-P7.1 output;
  * ``place_coverage_avoid`` keeps every selected speaker clear of the real
    free-standing column in the bundled ``lab_room_with_column`` example;
  * dispatch wiring (``run_placement(room, "coverage_avoid", n)``), including the
    unchanged unknown-algorithm raise;
  * the disclosure NOTE is reachable and the result round-trips its target
    algorithm through the ``x_target_algorithm`` layout.yaml extension key.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.geom.obstacle import (
    clearance_3d_m,
    freestanding_boxes,
    freestanding_footprints,
    plan_clearance_m,
)
from roomestim.model import Object, PlacementResult, Point3, RoomModel
from roomestim.place.dbap import place_dbap
from roomestim.place.dispatch import run_placement
from roomestim.place.obstacle_aware import (
    OBSTACLE_AWARE_PLACEMENT_NOTE,
    place_coverage_avoid,
)
from tests.fixtures.synthetic_rooms import shoebox


def _furnished_room(table_height_m: float = 0.7) -> RoomModel:
    """A shoebox whose whole floor plan is covered by ONE short table.

    Every wall/ceiling candidate's plan-view ``(x, z)`` overlaps (or is within
    clearance of) the footprint — the plan-view-only P7.1 filter emptied this
    pool and 400'd. The table is short, so a ceiling mount above it is clear in
    3D. Line-of-sight is disabled here to isolate the CLEARANCE dimension (the
    documented defect); LOS is a separate plan-view sightline heuristic and,
    with a full-plan table under the ear, would independently block everything.
    """
    room = shoebox(5.0, 4.0, 2.8)
    table = Object(
        kind="table",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=4.8,
        height_m=table_height_m,
        depth_m=3.8,
    )
    return replace(room, objects=[table])

_EXAMPLE = (
    Path(__file__).resolve().parents[1]
    / "roomestim_server"
    / "examples"
    / "lab_room_with_column.json"
)


def _lab_room() -> RoomModel:
    room = RoomPlanAdapter().parse(_EXAMPLE)
    assert freestanding_footprints(room), "example must have a free-standing column"
    return room


# --------------------------------------------------------------------------- #
# DBAP byte-equal parity — candidate_filter=None changes nothing
# --------------------------------------------------------------------------- #


def test_place_dbap_filter_none_is_byte_equal() -> None:
    room = shoebox()
    walls = [s for s in room.surfaces if s.kind == "wall"]
    baseline = place_dbap(
        mount_surfaces=walls, n_speakers=12, listener_area=room.listener_area
    )
    with_none = place_dbap(
        mount_surfaces=walls,
        n_speakers=12,
        listener_area=room.listener_area,
        candidate_filter=None,
    )
    assert with_none == baseline
    # positions identical element-for-element (defensive: dataclass eq already covers it)
    assert [(s.channel, s.position) for s in with_none.speakers] == [
        (s.channel, s.position) for s in baseline.speakers
    ]


# --------------------------------------------------------------------------- #
# Mode B — obstacle clearance on the real example column
# --------------------------------------------------------------------------- #


def test_coverage_avoid_returns_valid_placement_result() -> None:
    room = _lab_room()
    result = place_coverage_avoid(room, 6)
    assert isinstance(result, PlacementResult)
    assert result.target_algorithm == "COVERAGE_AVOID"
    assert result.regularity_hint == "IRREGULAR"
    assert result.layout_name == "coverage_avoid"
    assert len(result.speakers) == 6
    assert [s.channel for s in result.speakers] == list(range(1, 7))


def test_coverage_avoid_speakers_clear_of_column() -> None:
    room = _lab_room()
    footprints = freestanding_footprints(room)
    clearance_m = 0.30
    result = place_coverage_avoid(room, 8, clearance_m=clearance_m)
    for sp in result.speakers:
        d = plan_clearance_m(sp.position.x, sp.position.z, footprints)
        assert d >= clearance_m, (
            f"speaker {sp.channel} at (x={sp.position.x:.3f}, z={sp.position.z:.3f}) "
            f"is only {d:.3f} m from the column (< {clearance_m} m clearance)"
        )


def test_coverage_avoid_note_is_reachable_and_honest() -> None:
    assert "GEOMETRIC HEURISTIC" in OBSTACLE_AWARE_PLACEMENT_NOTE
    assert "NO" in OBSTACLE_AWARE_PLACEMENT_NOTE
    assert "SPL" in OBSTACLE_AWARE_PLACEMENT_NOTE
    # P7.5: the disclosure now documents 3D clearance + graceful degradation.
    assert "3D" in OBSTACLE_AWARE_PLACEMENT_NOTE
    assert "ZERO" in OBSTACLE_AWARE_PLACEMENT_NOTE


# --------------------------------------------------------------------------- #
# P7.5 — furnished room: 3D clearance fixes the plan-view false-empty 400
# --------------------------------------------------------------------------- #


def test_coverage_avoid_furnished_room_returns_valid_not_400() -> None:
    """A short table covering the whole plan emptied the plan-view pool (400).

    With 3D clearance the ceiling mounts above it survive: a valid result, not a
    ValueError.
    """
    room = _furnished_room(table_height_m=0.7)
    boxes = freestanding_boxes(room)
    result = place_coverage_avoid(room, 6, clearance_m=0.30, check_line_of_sight=False)
    assert isinstance(result, PlacementResult)
    assert len(result.speakers) == 6
    # Every placed speaker clears every object box in 3D.
    for sp in result.speakers:
        d = clearance_3d_m(sp.position.x, sp.position.y, sp.position.z, boxes)
        assert d >= 0.30, (
            f"speaker {sp.channel} only {d:.3f} m from a box in 3D (< 0.30 m)"
        )
    # The pool is non-empty BECAUSE of the 3D fix: a ceiling-height candidate
    # above the 0.7 m table is allowed (max speaker y reaches the 2.8 m ceiling).
    assert max(sp.position.y for sp in result.speakers) > 2.0


def test_coverage_avoid_graceful_degradation_places_k_lt_n() -> None:
    """More speakers requested than clear the filter -> place k<n + honest note."""
    room = _furnished_room(table_height_m=0.7)
    boxes = freestanding_boxes(room)
    n = 10_000
    result = place_coverage_avoid(room, n, clearance_m=0.30, check_line_of_sight=False)
    assert isinstance(result, PlacementResult)
    assert 1 <= len(result.speakers) < n
    # The honest shortfall note is recorded on every placed speaker.
    for sp in result.speakers:
        assert "obstacle-constrained: placed" in sp.notes
        assert f"/{n}" in sp.notes
        assert "in 3D" in sp.notes
    # No fabricated acoustics — still a pure 3D-clearance disclosure.
    for sp in result.speakers:
        d = clearance_3d_m(sp.position.x, sp.position.y, sp.position.z, boxes)
        assert d >= 0.30


def test_coverage_avoid_full_placement_has_no_shortfall_note() -> None:
    """When the pool covers n, the placed speakers carry no shortfall note."""
    room = _furnished_room(table_height_m=0.7)
    result = place_coverage_avoid(room, 6, clearance_m=0.30, check_line_of_sight=False)
    assert all("obstacle-constrained" not in sp.notes for sp in result.speakers)


def test_coverage_avoid_zero_clear_still_raises() -> None:
    """A full-height block covering the whole plan -> ZERO clear -> ValueError."""
    room = shoebox(5.0, 4.0, 2.8)
    block = Object(
        kind="storage",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=4.8,
        height_m=2.8,  # spans floor to ceiling -> no 3D escape above it
        depth_m=3.8,
    )
    room = replace(room, objects=[block])
    with pytest.raises(ValueError, match="candidate pool is empty"):
        place_coverage_avoid(room, 6, clearance_m=0.30, check_line_of_sight=False)


def test_coverage_avoid_production_path_los_on_short_table_not_400() -> None:
    """The PRODUCTION path runs with line-of-sight ON (dispatch default).

    Height-aware LOS is the companion of the 3D clearance fix: a ceiling mount
    ABOVE a short table (top 0.7 m, below both the mount and the 1.2 m ear) must
    NOT be treated as occluded by that table, so the pool does not empty. Without
    the height-aware LOS wiring the plan-view segment crosses the full-plan table
    and every candidate is rejected -> the original 400 would re-appear even
    after the clearance fix. This is the exact regression the reviewer flagged.
    """
    room = _furnished_room(table_height_m=0.7)
    boxes = freestanding_boxes(room)
    # LOS left at its default (True) — the production dispatch path.
    result = place_coverage_avoid(room, 6, clearance_m=0.30)
    assert isinstance(result, PlacementResult)
    assert len(result.speakers) == 6
    # Survivors are the ceiling-height mounts above the short table.
    assert max(sp.position.y for sp in result.speakers) > 2.0
    for sp in result.speakers:
        d = clearance_3d_m(sp.position.x, sp.position.y, sp.position.z, boxes)
        assert d >= 0.30


def test_coverage_avoid_los_on_tall_obstacle_still_blocks() -> None:
    """Height-aware LOS must NOT over-skip: a full-height block still occludes.

    A floor-to-ceiling block covering the whole plan has its top ABOVE the ear,
    so height-aware LOS does not skip it; combined with 3D clearance the pool
    empties and it fails loud (no silent placement through a solid wall-height
    obstacle).
    """
    room = shoebox(5.0, 4.0, 2.8)
    block = Object(
        kind="storage",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=4.8,
        height_m=2.8,
        depth_m=3.8,
    )
    room = replace(room, objects=[block])
    with pytest.raises(ValueError, match="candidate pool is empty"):
        place_coverage_avoid(room, 6, clearance_m=0.30)  # LOS default ON


def test_freestanding_footprints_and_boxes_are_index_aligned() -> None:
    """object_box delegates its exclusion gate to object_footprint, so the two
    room-level lists exclude the SAME objects and stay index-for-index aligned
    (a NaN/degenerate box can never desync the height-aware LOS tops)."""
    room = _furnished_room(table_height_m=0.7)
    room = replace(
        room,
        objects=[
            *room.objects,
            Object(  # NaN width: object_footprint rejects -> object_box must too
                kind="table",
                anchor=Point3(x=1.0, y=0.0, z=1.0),
                width_m=float("nan"),
                height_m=0.7,
                depth_m=0.8,
            ),
        ],
    )
    assert len(freestanding_footprints(room)) == len(freestanding_boxes(room))


# --------------------------------------------------------------------------- #
# Dispatch wiring
# --------------------------------------------------------------------------- #


def test_dispatch_coverage_avoid_works() -> None:
    room = _lab_room()
    result = run_placement(room, "coverage_avoid", 6, 1.8, 0.0)
    assert result.target_algorithm == "COVERAGE_AVOID"
    assert len(result.speakers) == 6


def test_dispatch_coverage_avoid_clearance_passthrough() -> None:
    room = _lab_room()
    footprints = freestanding_footprints(room)
    result = run_placement(room, "coverage_avoid", 6, 1.8, 0.0, clearance_m=0.50)
    for sp in result.speakers:
        assert plan_clearance_m(sp.position.x, sp.position.z, footprints) >= 0.50


def test_dispatch_unknown_algorithm_still_raises() -> None:
    room = _lab_room()
    try:
        run_placement(room, "definitely_not_an_algorithm", 6, 1.8, 0.0)
    except ValueError as exc:
        assert "unknown algorithm" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for unknown algorithm")


# --------------------------------------------------------------------------- #
# Existing algorithms stay byte-equal through the new dispatch signature
# --------------------------------------------------------------------------- #


def test_dispatch_dbap_byte_equal_through_new_signature() -> None:
    """The added ``clearance_m`` kwarg must not perturb the existing dbap branch."""
    room = _lab_room()
    a = run_placement(room, "dbap", 8, 1.8, 0.0)
    b = run_placement(room, "dbap", 8, 1.8, 0.0, clearance_m=0.30)
    assert a == b


def test_coverage_avoid_round_trips_target_algorithm() -> None:
    from roomestim.export.layout_yaml import placement_to_dict

    room = _lab_room()
    result = place_coverage_avoid(room, 6)
    # Exercise the same ``x_target_algorithm`` extension-key export used by the
    # COVERAGE_GRID precedent (non-VBAP labels are persisted, not collapsed).
    d = placement_to_dict(result)
    assert d["x_target_algorithm"] == "COVERAGE_AVOID"
