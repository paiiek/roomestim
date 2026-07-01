"""Tests for the immersive format catalog + obstacle-aware Mode A (P7.2).

Covers:
  * ``roomestim.place.formats`` — channel counts match the format id, bed/
    surround azimuths match ITU-R BS.775, height elevation reuses
    ``standards.HEIGHT_EL_IDEAL_DEG``, and ``get_format`` fails loud on unknowns;
  * ``place_format_avoid`` — on an obstacle-free room every channel is CLEARED at
    deviation 0 with angles equal to the catalog (parity vs ``coords``); on the
    bundled ``lab_room_with_column`` example a colliding channel is nudged
    (deviation > 0, CLEARED, still clear) or flagged UNRESOLVED; the note records
    ideal-vs-actual; and identical inputs give identical output (determinism);
  * dispatch wiring (``run_placement(room, "format_avoid", n, format_id=…)``),
    including the ``format_id=None`` fail-loud and existing-algorithm byte-equality.
"""

from __future__ import annotations

import math
from pathlib import Path

from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.coords import yaml_speaker_to_cartesian
from roomestim.geom.obstacle import freestanding_footprints, position_is_clear
from roomestim.model import PlacementResult, Point3, RoomModel
from roomestim.place.dispatch import run_placement
from roomestim.place.formats import (
    FORMAT_CATALOG,
    get_format,
    list_format_ids,
)
from roomestim.place.obstacle_aware import place_format_avoid
from roomestim.place.standards import HEIGHT_EL_IDEAL_DEG
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
# Format catalog — counts, angles, provenance, fail-loud
# --------------------------------------------------------------------------- #

_EXPECTED_COUNTS = {
    "5.1": 6,
    "7.1": 8,
    "5.1.2": 8,
    "5.1.4": 10,
    "7.1.4": 12,
    "9.1.6": 16,
}


def test_format_channel_counts_match_id() -> None:
    assert list_format_ids() == list(_EXPECTED_COUNTS.keys())
    for fid, expected in _EXPECTED_COUNTS.items():
        assert len(get_format(fid).channels) == expected


def test_format_bed_surround_azimuths_match_itu_bs775() -> None:
    by_name = {ch.name: ch for ch in get_format("5.1").channels}
    assert by_name["L"].az_deg == -30.0
    assert by_name["R"].az_deg == 30.0
    assert by_name["C"].az_deg == 0.0
    assert by_name["Ls"].az_deg == -110.0
    assert by_name["Rs"].az_deg == 110.0
    # 7.1 side +/-90, back +/-150 (public BS.775 7.1 layout)
    by71 = {ch.name: ch for ch in get_format("7.1").channels}
    assert by71["Lss"].az_deg == -90.0
    assert by71["Rss"].az_deg == 90.0
    assert by71["Lsr"].az_deg == -150.0
    assert by71["Rsr"].az_deg == 150.0


def test_format_height_elevation_reuses_standards_constant() -> None:
    for ch in get_format("9.1.6").channels:
        if ch.role == "height":
            assert ch.el_deg == HEIGHT_EL_IDEAL_DEG
    # bed/surround are at listener level
    for ch in get_format("9.1.6").channels:
        if ch.role in ("bed", "surround"):
            assert ch.el_deg == 0.0


def test_format_notes_disclose_public_provenance() -> None:
    note = FORMAT_CATALOG["5.1.4"].note
    assert "BS.775" in note
    assert "Dolby" in note
    assert "RP22" in note  # explicitly disclaims the paywalled standard


def test_get_format_unknown_raises_listing_ids() -> None:
    try:
        get_format("not-a-format")
    except ValueError as exc:
        assert "not-a-format" in str(exc)
        for fid in list_format_ids():
            assert fid in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for unknown format_id")


# --------------------------------------------------------------------------- #
# Mode A — obstacle-free room: every channel CLEARED at deviation 0
# --------------------------------------------------------------------------- #


def test_format_avoid_no_obstacle_all_cleared_and_matches_catalog() -> None:
    room = shoebox()
    assert not freestanding_footprints(room), "shoebox must be obstacle-free"
    radius = 1.8
    result = place_format_avoid(room, format_id="7.1.4", layout_radius_m=radius)

    fmt = get_format("7.1.4")
    assert isinstance(result, PlacementResult)
    assert result.target_algorithm == "FORMAT_AVOID"
    assert result.regularity_hint == "IRREGULAR"
    assert result.layout_name == "format_avoid"
    assert len(result.speakers) == len(fmt.channels)
    assert [s.channel for s in result.speakers] == list(range(1, len(fmt.channels) + 1))

    la = room.listener_area
    ear = Point3(la.centroid.x, la.height_m, la.centroid.z)
    for sp, ch in zip(result.speakers, fmt.channels, strict=True):
        assert "[CLEARED]" in sp.notes
        assert "dev=0.0deg" in sp.notes
        # position parity vs coords.yaml_speaker_to_cartesian at the catalog angle
        dx, dy, dz = yaml_speaker_to_cartesian(ch.az_deg, ch.el_deg, radius)
        assert math.isclose(sp.position.x, ear.x + dx, abs_tol=1e-9)
        assert math.isclose(sp.position.y, ear.y + dy, abs_tol=1e-9)
        assert math.isclose(sp.position.z, ear.z + dz, abs_tol=1e-9)


# --------------------------------------------------------------------------- #
# Mode A — real obstacle: nudge or UNRESOLVED, note honesty, clearance
# --------------------------------------------------------------------------- #


def test_format_avoid_lab_room_nudges_colliding_channel() -> None:
    room = _lab_room()
    footprints = freestanding_footprints(room)
    clearance_m = 0.30
    result = place_format_avoid(
        room, format_id="9.1.6", clearance_m=clearance_m
    )
    fmt = get_format("9.1.6")
    assert len(result.speakers) == len(fmt.channels)

    perturbed = [
        sp for sp in result.speakers if "dev=0.0deg [CLEARED]" not in sp.notes
    ]
    # The column between the listener and the right-of-front channels forces at
    # least one channel off its ideal angle.
    assert perturbed, "expected at least one channel nudged or UNRESOLVED"

    for sp in result.speakers:
        assert "ideal az=" in sp.notes and "-> actual az=" in sp.notes
        assert "[CLEARED]" in sp.notes or "[UNRESOLVED]" in sp.notes
        # Every CLEARED channel must actually satisfy the plan-view clearance.
        if "[CLEARED]" in sp.notes:
            assert position_is_clear(
                sp.position.x, sp.position.z, footprints, clearance_m=clearance_m
            )


def test_format_avoid_is_deterministic() -> None:
    room = _lab_room()
    a = place_format_avoid(room, format_id="9.1.6")
    b = place_format_avoid(room, format_id="9.1.6")
    assert [(s.channel, s.position, s.notes) for s in a.speakers] == [
        (s.channel, s.position, s.notes) for s in b.speakers
    ]


# --------------------------------------------------------------------------- #
# Dispatch wiring
# --------------------------------------------------------------------------- #


def test_dispatch_format_avoid_works() -> None:
    room = _lab_room()
    # n_speakers is derived from the format; the passed value is ignored.
    result = run_placement(room, "format_avoid", 99, 1.8, 0.0, format_id="5.1.4")
    assert result.target_algorithm == "FORMAT_AVOID"
    assert len(result.speakers) == len(get_format("5.1.4").channels)


def test_dispatch_format_avoid_requires_format_id() -> None:
    room = _lab_room()
    try:
        run_placement(room, "format_avoid", 6, 1.8, 0.0)
    except ValueError as exc:
        assert "format_avoid requires format_id" in str(exc)
        for fid in list_format_ids():
            assert fid in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError when format_id is None")


def test_dispatch_format_avoid_round_trips_target_algorithm() -> None:
    from roomestim.export.layout_yaml import placement_to_dict

    room = _lab_room()
    result = place_format_avoid(room, format_id="5.1")
    d = placement_to_dict(result)
    assert d["x_target_algorithm"] == "FORMAT_AVOID"


def test_dispatch_existing_algorithms_byte_equal_through_new_signature() -> None:
    """The added ``format_id`` kwarg must not perturb existing branches."""
    room = _lab_room()
    assert run_placement(room, "dbap", 8, 1.8, 0.0) == run_placement(
        room, "dbap", 8, 1.8, 0.0, format_id=None
    )
    assert run_placement(room, "vbap", 6, 1.8, 0.0) == run_placement(
        room, "vbap", 6, 1.8, 0.0, format_id="5.1"
    )
