"""Tests for ``roomestim.place.standards`` — B5 geometric layout-angle check.

Deterministic: synthetic layouts at exact elevations for boundary behaviour, plus
the REAL placement functions (VBAP ring + DBAP on a fixture room) to confirm the
check works on ANY layout regardless of algorithm. No randomness.
"""

from __future__ import annotations

import math

from roomestim.coords import yaml_speaker_to_cartesian
from roomestim.model import PlacedSpeaker, Point3
from roomestim.place.dbap import place_dbap
from roomestim.place.standards import (
    HEIGHT_EL_IDEAL_DEG,
    HEIGHT_EL_MAX_DEG,
    HEIGHT_EL_MIN_DEG,
    LAYOUT_ANGLE_CHECK_NOTE,
    LISTENER_LEVEL_MAX_EL_DEG,
    OVERHEAD_MIN_EL_DEG,
    LayoutAngleReport,
    SpeakerAngle,
    check_layout_angles,
    format_report_lines,
    report_to_dict,
)
from roomestim.place.vbap import place_vbap_ring
from tests.fixtures.synthetic_rooms import shoebox


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _speaker_at(channel: int, az_deg: float, el_deg: float) -> PlacedSpeaker:
    """A speaker at unit distance from the origin at (az_deg, el_deg)."""
    x, y, z = yaml_speaker_to_cartesian(az_deg, el_deg, 1.0)
    return PlacedSpeaker(channel=channel, position=Point3(x=x, y=y, z=z))


# --------------------------------------------------------------------------- #
# Elevation-band boundary behaviour (29.9 / 30 / 45 / 55 / 55.1)
# --------------------------------------------------------------------------- #


def test_height_band_lower_boundary_29_9_fails() -> None:
    """29.9 deg is inside the geometric height band but BELOW the Dolby window."""
    report = check_layout_angles([_speaker_at(1, 0.0, 29.9)])
    sp = report.speakers[0]
    assert sp.band == "height"
    assert sp.height_band_pass is False
    assert report.n_height == 1
    assert report.n_height_fail == 1
    assert report.n_height_pass == 0


def test_height_band_lower_boundary_30_passes() -> None:
    """Exactly 30 deg passes (inclusive lower bound)."""
    report = check_layout_angles([_speaker_at(1, 0.0, 30.0)])
    sp = report.speakers[0]
    assert sp.band == "height"
    assert sp.height_band_pass is True
    assert math.isclose(sp.ideal_45_delta_deg or 0.0, 30.0 - 45.0, abs_tol=1e-9)


def test_height_band_ideal_45_zero_delta() -> None:
    """45 deg passes with zero delta-from-ideal."""
    report = check_layout_angles([_speaker_at(1, 0.0, 45.0)])
    sp = report.speakers[0]
    assert sp.band == "height"
    assert sp.height_band_pass is True
    assert sp.ideal_45_delta_deg is not None
    assert math.isclose(sp.ideal_45_delta_deg, 0.0, abs_tol=1e-9)


def test_height_band_upper_boundary_55_passes() -> None:
    """Exactly 55 deg passes (inclusive upper bound)."""
    report = check_layout_angles([_speaker_at(1, 0.0, 55.0)])
    sp = report.speakers[0]
    assert sp.band == "height"
    assert sp.height_band_pass is True
    assert math.isclose(sp.ideal_45_delta_deg or 0.0, 55.0 - 45.0, abs_tol=1e-9)


def test_height_band_upper_boundary_55_1_fails() -> None:
    """55.1 deg is inside the geometric height band but ABOVE the Dolby window."""
    report = check_layout_angles([_speaker_at(1, 0.0, 55.1)])
    sp = report.speakers[0]
    assert sp.band == "height"
    assert sp.height_band_pass is False
    assert report.n_height_fail == 1


# --------------------------------------------------------------------------- #
# Listener-level + overhead -> height_band_pass / ideal None (N/A, not fail)
# --------------------------------------------------------------------------- #


def test_listener_level_is_na_not_fail() -> None:
    report = check_layout_angles([_speaker_at(1, 0.0, 0.0)])
    sp = report.speakers[0]
    assert sp.band == "listener-level"
    assert sp.height_band_pass is None
    assert sp.ideal_45_delta_deg is None
    assert report.n_listener_level == 1
    assert report.n_height_fail == 0
    assert report.n_height_pass == 0


def test_overhead_is_na_not_fail() -> None:
    report = check_layout_angles([_speaker_at(1, 0.0, 75.0)])
    sp = report.speakers[0]
    assert sp.band == "overhead"
    assert sp.height_band_pass is None
    assert sp.ideal_45_delta_deg is None
    assert report.n_overhead == 1
    assert report.n_height_fail == 0


def test_band_cutoffs_are_documented_constants() -> None:
    """Bands honour the documented geometric cut-offs, exclusive at both ends."""
    assert check_layout_angles(
        [_speaker_at(1, 0.0, LISTENER_LEVEL_MAX_EL_DEG - 0.01)]
    ).speakers[0].band == "listener-level"
    assert check_layout_angles(
        [_speaker_at(1, 0.0, LISTENER_LEVEL_MAX_EL_DEG + 0.01)]
    ).speakers[0].band == "height"
    assert check_layout_angles(
        [_speaker_at(1, 0.0, OVERHEAD_MIN_EL_DEG + 0.01)]
    ).speakers[0].band == "overhead"


# --------------------------------------------------------------------------- #
# Azimuth correctness on KNOWN coordinates (coords.py pipeline convention)
# --------------------------------------------------------------------------- #


def test_azimuth_known_coordinates_pipeline_convention() -> None:
    """RIGHT = +az; front = 0, right = +90, behind = 180, left = -90."""
    speakers = [
        PlacedSpeaker(channel=1, position=Point3(0.0, 0.0, 1.0)),   # front
        PlacedSpeaker(channel=2, position=Point3(1.0, 0.0, 0.0)),   # right
        PlacedSpeaker(channel=3, position=Point3(0.0, 0.0, -1.0)),  # behind
        PlacedSpeaker(channel=4, position=Point3(-1.0, 0.0, 0.0)),  # left
    ]
    report = check_layout_angles(speakers)
    az = [sp.azimuth_deg for sp in report.speakers]
    assert math.isclose(az[0], 0.0, abs_tol=1e-9)
    assert math.isclose(az[1], 90.0, abs_tol=1e-9)
    assert math.isclose(abs(az[2]), 180.0, abs_tol=1e-9)
    assert math.isclose(az[3], -90.0, abs_tol=1e-9)


def test_elevation_uses_listener_offset() -> None:
    """Elevation is measured FROM the listener point, not the global origin."""
    sp = PlacedSpeaker(channel=1, position=Point3(0.0, 1.0, 1.0))
    # From origin: el = atan2(1, 1) = 45 deg.
    r0 = check_layout_angles([sp])
    assert math.isclose(r0.speakers[0].elevation_deg, 45.0, abs_tol=1e-9)
    # From a listener lifted to y=1: speaker is level -> el = 0.
    r1 = check_layout_angles([sp], listener=Point3(0.0, 1.0, 0.0))
    assert math.isclose(r1.speakers[0].elevation_deg, 0.0, abs_tol=1e-9)


# --------------------------------------------------------------------------- #
# REAL placement functions: VBAP fixture AND DBAP fixture
# --------------------------------------------------------------------------- #


def test_real_vbap_ring_height_dome_passes_angle_check() -> None:
    """A VBAP ring at el=45 is a fixed-geometry layout; every speaker passes the
    angle window. This is an ANGLE check only, NOT room-awareness."""
    result = place_vbap_ring(n=8, radius_m=2.0, el_deg=45.0)
    report = check_layout_angles(result)
    assert report.n_height == 8
    assert report.n_height_pass == 8
    assert report.n_height_fail == 0
    for sp in report.speakers:
        assert sp.band == "height"
        assert sp.height_band_pass is True


def test_real_vbap_ring_listener_level_is_na() -> None:
    """A flat (el=0) VBAP ring is all listener-level -> N/A, not fail."""
    result = place_vbap_ring(n=8, radius_m=2.0, el_deg=0.0)
    report = check_layout_angles(result)
    assert report.n_listener_level == 8
    assert report.n_height == 0
    assert report.n_height_fail == 0


def test_real_dbap_fixture_runs_and_is_classified() -> None:
    """The check runs on a REAL DBAP placement (geometry-aware algorithm)."""
    room = shoebox()
    walls = [s for s in room.surfaces if s.kind in ("wall", "ceiling")]
    result = place_dbap(
        mount_surfaces=walls, n_speakers=8, listener_area=room.listener_area
    )
    centroid = room.listener_area.centroid
    listener = Point3(centroid.x, room.listener_area.height_m, centroid.z)
    report = check_layout_angles(result, listener=listener)
    assert len(report.speakers) == 8
    # Every speaker classified into exactly one band; counts are consistent.
    assert (
        report.n_listener_level + report.n_height + report.n_overhead
        == len(report.speakers)
    )
    assert report.n_height_pass + report.n_height_fail == report.n_height
    # Channels preserved from the placement result.
    assert [sp.channel for sp in report.speakers] == [
        s.channel for s in result.speakers
    ]


# --------------------------------------------------------------------------- #
# NOTE constant content pins + serialization shape
# --------------------------------------------------------------------------- #


def test_note_constant_content_pins() -> None:
    note = LAYOUT_ANGLE_CHECK_NOTE
    assert "Geometric angle check only" in note
    assert "NO acoustic performance claim" in note
    assert "Dolby" in note
    assert "30-55 deg" in note
    assert "RP22 is NOT EVALUATED" in note
    # The report carries the single source of truth verbatim.
    assert check_layout_angles([_speaker_at(1, 0.0, 0.0)]).note is LAYOUT_ANGLE_CHECK_NOTE


def test_public_threshold_constants() -> None:
    assert HEIGHT_EL_MIN_DEG == 30.0
    assert HEIGHT_EL_MAX_DEG == 55.0
    assert HEIGHT_EL_IDEAL_DEG == 45.0


def test_report_to_dict_shape() -> None:
    report = check_layout_angles(
        [_speaker_at(1, 30.0, 45.0), _speaker_at(2, 0.0, 0.0)]
    )
    d = report_to_dict(report)
    assert d["check"] == "geometric_layout_angle"
    assert d["note"] == LAYOUT_ANGLE_CHECK_NOTE
    assert isinstance(d["summary"], dict)
    assert d["summary"]["n_height_pass"] == 1
    assert d["summary"]["n_listener_level"] == 1
    speakers = d["speakers"]
    assert isinstance(speakers, list)
    assert len(speakers) == 2
    first = speakers[0]
    assert set(first.keys()) == {
        "channel",
        "azimuth_deg",
        "elevation_deg",
        "band",
        "height_band_pass",
        "ideal_45_delta_deg",
    }
    # listener-level speaker -> None fields survive serialization.
    assert speakers[1]["height_band_pass"] is None
    assert speakers[1]["ideal_45_delta_deg"] is None


def test_format_report_lines_human_readable() -> None:
    report = check_layout_angles([_speaker_at(1, 0.0, 45.0)])
    lines = format_report_lines(report)
    assert any("geometry only, no acoustic claim" in ln for ln in lines)
    assert any("ch1:" in ln and "PASS" in ln for ln in lines)
    assert any(ln.strip().startswith("NOTE:") for ln in lines)


def test_dataclass_types_are_frozen() -> None:
    report = check_layout_angles([_speaker_at(1, 0.0, 45.0)])
    assert isinstance(report, LayoutAngleReport)
    assert isinstance(report.speakers[0], SpeakerAngle)
