"""Obstacle-aware speaker placement (P7).

Two room-absolute (Frame A) placers that add a plan-view obstacle/line-of-sight
filter on top of the existing machinery, both explicit geometric heuristics:

- ``place_coverage_avoid`` (Mode B, this file) — extends DBAP
  (:func:`roomestim.place.dbap.place_dbap`) via its ``candidate_filter`` hook,
  dropping obstacle-colliding / occluded wall/ceiling candidates. Makes NO SPL
  claim.
- ``place_format_avoid`` (Mode A) — added in P7.2.

The single-source honesty disclaimer is :data:`OBSTACLE_AWARE_PLACEMENT_NOTE`,
mirroring ``COVERAGE_GRID_NOTE`` / ``AMBISONICS_RIG_DISCLOSURE`` /
``LAYOUT_ANGLE_CHECK_NOTE``. It is defined here now (P7.1) and reused verbatim by
Mode A in P7.2.
"""

from __future__ import annotations

from roomestim.geom.obstacle import (
    freestanding_footprints,
    line_of_sight_blocked,
    position_is_clear,
)
from roomestim.model import PlacementResult, Point3, RoomModel, Surface
from roomestim.place.algorithm import TargetAlgorithm
from roomestim.place.dbap import place_dbap

#: Single source of truth for the obstacle-aware placement honesty framing.
#: Referenced (never retyped) by the dispatch docstring and the server response.
OBSTACLE_AWARE_PLACEMENT_NOTE: str = (
    "Obstacle-aware placement is a DETERMINISTIC GEOMETRIC HEURISTIC — NOT a "
    "proven-optimal, acoustically-validated, or perceptually-verified layout. "
    "Clearance is plan-view (top-down) Euclidean distance to axis-aligned object "
    "bounding boxes (object rotation is NOT modelled; furniture is treated as a "
    "solid box). Line-of-sight is a plan-view segment/box intersection that ignores "
    "diffraction and (unless height-aware is enabled) speaker/obstacle height. Mode A "
    "(format_avoid) preserves a standard format's canonical listener-relative angles "
    "and nudges each channel by the SMALLEST angular offset (stepped search, not a "
    "global optimum) that clears obstacles; per-channel ideal-vs-actual deviation is "
    "reported. A channel that cannot be cleared within the search window is left at "
    "its ideal angle and flagged UNRESOLVED — it is NOT silently moved. Mode B "
    "(coverage_avoid) maximizes listener-area min/max DBAP gain on wall/ceiling "
    "mounts with obstacle-colliding and occluded candidates removed; it makes NO "
    "SPL claim. Canonical angles are reconstructed from PUBLIC guidance (ITU-R BS.775 "
    "bed/surround azimuths; Dolby Atmos Home Theater Installation Guidelines height "
    "angles, 45 deg ideal), NOT a paywalled standard, and are NOT inferred from the room."
)


def place_coverage_avoid(
    room: RoomModel,
    n_speakers: int,
    *,
    clearance_m: float = 0.30,
    check_line_of_sight: bool = True,
    samples_per_dim: int = 5,
    inset_m: float = 0.10,
    layout_name: str = "coverage_avoid",
) -> PlacementResult:
    """DBAP coverage placement that avoids free-standing obstacles (Mode B).

    Identical to :func:`roomestim.place.dbap.place_dbap` on the room's wall +
    ceiling surfaces, with ONE inserted candidate filter: any candidate that is
    not clear of every object footprint by ``clearance_m`` (plan-view) — or,
    when ``check_line_of_sight`` is set, whose plan-view segment to the listener
    ear is blocked by a footprint — is dropped before the greedy max-min
    selection. Room-absolute (Frame A); makes NO SPL claim. See
    :data:`OBSTACLE_AWARE_PLACEMENT_NOTE`.

    The listener ear point is ``(centroid.x, listener_area.height_m,
    centroid.z)`` — identical to the server install block, so headless and
    server results do not drift.

    Raises ``ValueError`` (→ generic 400 at the server) when the room has no
    wall/ceiling mount surface or when the candidate pool empties after the
    obstacle filter (same fail-loud contract as ``place_dbap``).
    """
    mount_surfaces: list[Surface] = [
        s for s in room.surfaces if s.kind in ("wall", "ceiling")
    ]
    if not mount_surfaces:
        raise ValueError(
            "coverage_avoid placement requires at least one wall or ceiling "
            "surface; none found in the room."
        )

    footprints = freestanding_footprints(room)
    listener = room.listener_area
    ear = Point3(
        x=listener.centroid.x,
        y=listener.height_m,
        z=listener.centroid.z,
    )

    def _candidate_filter(cand: Point3) -> bool:
        if not position_is_clear(
            cand.x, cand.z, footprints, clearance_m=clearance_m
        ):
            return False
        if check_line_of_sight and line_of_sight_blocked(cand, ear, footprints):
            return False
        return True

    result = place_dbap(
        mount_surfaces=mount_surfaces,
        n_speakers=n_speakers,
        listener_area=room.listener_area,
        layout_name=layout_name,
        samples_per_dim=samples_per_dim,
        inset_m=inset_m,
        candidate_filter=_candidate_filter,
    )
    return PlacementResult(
        target_algorithm=TargetAlgorithm.COVERAGE_AVOID.value,
        regularity_hint="IRREGULAR",
        speakers=result.speakers,
        layout_name=layout_name,
    )


__all__ = ["OBSTACLE_AWARE_PLACEMENT_NOTE", "place_coverage_avoid"]
