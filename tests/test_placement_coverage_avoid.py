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

from pathlib import Path

from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.geom.obstacle import freestanding_footprints, plan_clearance_m
from roomestim.model import PlacementResult, RoomModel
from roomestim.place.dbap import place_dbap
from roomestim.place.dispatch import run_placement
from roomestim.place.obstacle_aware import (
    OBSTACLE_AWARE_PLACEMENT_NOTE,
    place_coverage_avoid,
)
from tests.fixtures.synthetic_rooms import shoebox

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
