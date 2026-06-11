"""Geometric layout-angle check (Atmos-style) — B5.

Given a finished placement (a :class:`~roomestim.model.PlacementResult` or a bare
list of :class:`~roomestim.model.PlacedSpeaker`) and a listener point, this module
computes the per-speaker azimuth and elevation *as seen from the listener* and
compares the elevation against the PUBLIC Dolby Atmos height-speaker guidance.

Public source for the elevation thresholds:
    Dolby Atmos Home Theater Installation Guidelines (Dolby Laboratories, public
    PDF) — height speakers 30-55 deg elevation, 45 deg ideal.

This is a GEOMETRY check only. It makes NO acoustic-performance claim, and a
"pass" does NOT mean the layout is room-aware: a fixed-geometry VBAP/WFS ring can
pass the angle window while remaining independent of the room (see the VBAP/WFS
disclosure in :mod:`roomestim.place.dispatch`). The CTA/CEDIA RP22 standard is
NOT EVALUATED here — its full text is paywalled, so no criterion is verified
against it. The single source of truth for that framing is
:data:`LAYOUT_ANGLE_CHECK_NOTE`; do not retype it.

The geometric bands (``listener-level`` / ``height`` / ``overhead``) are a
roomestim geometric convention defined by the elevation cut-offs below, NOT a
Dolby channel classification. ``height_band_pass`` and ``ideal_45_delta_deg`` are
populated ONLY for speakers that land in the geometric ``height`` band; for
``listener-level`` and ``overhead`` speakers they are ``None`` (N/A — the Dolby
height-speaker window does not apply, which is NOT the same as a failed check).

Deterministic: no randomness, no I/O. Azimuth/elevation use the single sign-flip
authority :func:`roomestim.coords.cartesian_to_pipeline` (pipeline convention,
RIGHT = +az, UP = +el).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from roomestim.coords import cartesian_to_pipeline
from roomestim.model import PlacedSpeaker, PlacementResult, Point3

__all__ = [
    "AngleBand",
    "HEIGHT_EL_IDEAL_DEG",
    "HEIGHT_EL_MAX_DEG",
    "HEIGHT_EL_MIN_DEG",
    "LAYOUT_ANGLE_CHECK_NOTE",
    "LISTENER_LEVEL_MAX_EL_DEG",
    "LayoutAngleReport",
    "OVERHEAD_MIN_EL_DEG",
    "SpeakerAngle",
    "check_layout_angles",
    "format_report_lines",
    "report_to_dict",
]

# --------------------------------------------------------------------------- #
# Public Dolby thresholds (height-speaker window) + geometric band cut-offs
# --------------------------------------------------------------------------- #

#: Dolby Atmos Home Theater Installation Guidelines (public): height speakers
#: sit at 30-55 deg elevation, with 45 deg the documented ideal.
HEIGHT_EL_MIN_DEG: float = 30.0
HEIGHT_EL_MAX_DEG: float = 55.0
HEIGHT_EL_IDEAL_DEG: float = 45.0

#: roomestim geometric band convention (NOT a Dolby classification). A speaker is
#: ``listener-level`` below :data:`LISTENER_LEVEL_MAX_EL_DEG`, ``overhead`` above
#: :data:`OVERHEAD_MIN_EL_DEG`, and ``height`` in between. The Dolby 30-55 window
#: lives strictly inside the ``height`` band, so a height-band speaker can still
#: fail the window (too low or too high within the band).
LISTENER_LEVEL_MAX_EL_DEG: float = 20.0
OVERHEAD_MIN_EL_DEG: float = 60.0

#: Floating-point tolerance (deg) on the inclusive Dolby window bounds. NOT a
#: widening of the guidance: it only absorbs the ~1e-14 spherical<->cartesian
#: round-trip noise so a speaker AUTHORED at exactly 30.0 / 55.0 deg is not
#: spuriously rejected. Far smaller than any meaningful placement difference.
_WINDOW_TOL_DEG: float = 1e-6

AngleBand = Literal["listener-level", "height", "overhead"]

# Single source of truth — reference, do not retype (style of
# POLYGON_ISM_GEOMETRY_NOTE in roomestim.reconstruct._disclosure).
LAYOUT_ANGLE_CHECK_NOTE: str = (
    "Geometric angle check only — NO acoustic performance claim. Per speaker it "
    "computes azimuth and elevation from the listener point and compares the "
    "elevation against PUBLIC Dolby guidance (Dolby Atmos Home Theater "
    "Installation Guidelines: height speakers 30-55 deg elevation, 45 deg ideal). "
    "A pass means the geometric mounting angle falls in the published window; it "
    "does NOT claim good timbre/imaging and does NOT imply room-awareness — a "
    "fixed-geometry VBAP/WFS ring can pass while staying independent of the room "
    "(see the VBAP/WFS disclosure). CTA/CEDIA RP22 is NOT EVALUATED (paywalled "
    "full text; no criterion verified against it). The bands (listener-level < 20 "
    "deg, height 20-60 deg, overhead > 60 deg) are a roomestim geometric "
    "convention, not a Dolby classification."
)


# --------------------------------------------------------------------------- #
# Report dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SpeakerAngle:
    """Per-speaker geometric angle record.

    ``height_band_pass`` and ``ideal_45_delta_deg`` are ``None`` for
    ``listener-level`` and ``overhead`` speakers — the Dolby height-speaker
    window is N/A for them (NOT a failed check).
    """

    channel: int
    azimuth_deg: float
    elevation_deg: float
    band: AngleBand
    height_band_pass: bool | None
    ideal_45_delta_deg: float | None


@dataclass(frozen=True)
class LayoutAngleReport:
    """Whole-layout geometric angle report + honesty :data:`note`."""

    speakers: tuple[SpeakerAngle, ...]
    n_listener_level: int
    n_height: int
    n_overhead: int
    n_height_pass: int
    n_height_fail: int
    note: str


# --------------------------------------------------------------------------- #
# Core geometry
# --------------------------------------------------------------------------- #


def _speaker_angle(channel: int, position: Point3, listener: Point3) -> SpeakerAngle:
    """Compute the :class:`SpeakerAngle` of ``position`` seen from ``listener``."""
    dx = position.x - listener.x
    dy = position.y - listener.y
    dz = position.z - listener.z
    az_rad, el_rad, _dist = cartesian_to_pipeline(dx, dy, dz)
    az_deg = math.degrees(az_rad)
    el_deg = math.degrees(el_rad)

    if el_deg < LISTENER_LEVEL_MAX_EL_DEG:
        band: AngleBand = "listener-level"
    elif el_deg > OVERHEAD_MIN_EL_DEG:
        band = "overhead"
    else:
        band = "height"

    if band == "height":
        height_band_pass: bool | None = (
            HEIGHT_EL_MIN_DEG - _WINDOW_TOL_DEG
            <= el_deg
            <= HEIGHT_EL_MAX_DEG + _WINDOW_TOL_DEG
        )
        ideal_45_delta_deg: float | None = el_deg - HEIGHT_EL_IDEAL_DEG
    else:
        height_band_pass = None
        ideal_45_delta_deg = None

    return SpeakerAngle(
        channel=channel,
        azimuth_deg=az_deg,
        elevation_deg=el_deg,
        band=band,
        height_band_pass=height_band_pass,
        ideal_45_delta_deg=ideal_45_delta_deg,
    )


def check_layout_angles(
    layout: PlacementResult | Iterable[PlacedSpeaker],
    listener: Point3 | None = None,
) -> LayoutAngleReport:
    """Run the geometric angle check on ANY layout, regardless of algorithm.

    ``layout`` is a :class:`~roomestim.model.PlacementResult` or any iterable of
    :class:`~roomestim.model.PlacedSpeaker`. ``listener`` defaults to the
    listener-frame origin ``Point3(0, 0, 0)`` (the convention VBAP/WFS rings are
    built around); callers with a room should pass the listener-area centroid.

    See :data:`LAYOUT_ANGLE_CHECK_NOTE` — geometric angle check only, no acoustic
    performance claim.
    """
    if listener is None:
        listener = Point3(0.0, 0.0, 0.0)

    speakers_in = (
        layout.speakers if isinstance(layout, PlacementResult) else list(layout)
    )
    angles = tuple(
        _speaker_angle(sp.channel, sp.position, listener) for sp in speakers_in
    )

    n_listener_level = sum(1 for a in angles if a.band == "listener-level")
    n_height = sum(1 for a in angles if a.band == "height")
    n_overhead = sum(1 for a in angles if a.band == "overhead")
    n_height_pass = sum(1 for a in angles if a.height_band_pass is True)
    n_height_fail = sum(1 for a in angles if a.height_band_pass is False)

    return LayoutAngleReport(
        speakers=angles,
        n_listener_level=n_listener_level,
        n_height=n_height,
        n_overhead=n_overhead,
        n_height_pass=n_height_pass,
        n_height_fail=n_height_fail,
        note=LAYOUT_ANGLE_CHECK_NOTE,
    )


# --------------------------------------------------------------------------- #
# Serialization helpers (JSON sidecar + human-readable lines)
# --------------------------------------------------------------------------- #


def report_to_dict(report: LayoutAngleReport) -> dict[str, object]:
    """Return a plain JSON-serialisable dict for the layout.angles.json sidecar."""
    return {
        "check": "geometric_layout_angle",
        "note": report.note,
        "summary": {
            "n_listener_level": report.n_listener_level,
            "n_height": report.n_height,
            "n_overhead": report.n_overhead,
            "n_height_pass": report.n_height_pass,
            "n_height_fail": report.n_height_fail,
        },
        "speakers": [
            {
                "channel": a.channel,
                "azimuth_deg": a.azimuth_deg,
                "elevation_deg": a.elevation_deg,
                "band": a.band,
                "height_band_pass": a.height_band_pass,
                "ideal_45_delta_deg": a.ideal_45_delta_deg,
            }
            for a in report.speakers
        ],
    }


def format_report_lines(report: LayoutAngleReport) -> list[str]:
    """Return human-readable lines for CLI output (one header + one per speaker)."""
    lines: list[str] = []
    lines.append(
        "geometric layout-angle check (Atmos-style; geometry only, no acoustic claim):"
    )
    for a in report.speakers:
        if a.band == "height":
            assert a.height_band_pass is not None
            assert a.ideal_45_delta_deg is not None
            verdict = "PASS" if a.height_band_pass else "FAIL"
            tail = (
                f"height-window {verdict} "
                f"(delta-from-45deg {a.ideal_45_delta_deg:+.1f})"
            )
        else:
            tail = "height-window N/A"
        lines.append(
            f"  ch{a.channel}: az={a.azimuth_deg:+.1f} deg "
            f"el={a.elevation_deg:+.1f} deg "
            f"band={a.band} {tail}"
        )
    lines.append(
        f"  summary: listener-level={report.n_listener_level} "
        f"height={report.n_height} (pass={report.n_height_pass} "
        f"fail={report.n_height_fail}) overhead={report.n_overhead}"
    )
    lines.append(f"  NOTE: {report.note}")
    return lines
