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

import math
from dataclasses import replace

from roomestim.coords import yaml_speaker_to_cartesian
from roomestim.geom.obstacle import (
    freestanding_boxes,
    freestanding_footprints,
    line_of_sight_blocked,
    position_is_clear_3d,
)
from roomestim.model import PlacedSpeaker, PlacementResult, Point3, RoomModel, Surface
from roomestim.place.algorithm import TargetAlgorithm
from roomestim.place.dbap import _candidates_on_surface, place_dbap
from roomestim.place.formats import get_format

#: Single source of truth for the obstacle-aware placement honesty framing.
#: Referenced (never retyped) by the dispatch docstring and the server response.
OBSTACLE_AWARE_PLACEMENT_NOTE: str = (
    "Obstacle-aware placement is a DETERMINISTIC GEOMETRIC HEURISTIC — NOT a "
    "proven-optimal, acoustically-validated, or perceptually-verified layout. "
    "Clearance is 3D (height-aware) Euclidean distance to axis-aligned object "
    "bounding boxes that span floor to object height (object rotation is NOT "
    "modelled; furniture is treated as a solid box), so a ceiling/high-wall mount "
    "cleanly ABOVE a short piece of furniture is correctly allowed instead of being "
    "rejected for a top-down footprint overlap. Line-of-sight is likewise "
    "height-aware: a plan-view segment/box intersection in which an object whose "
    "TOP is below both the speaker and the listener is skipped (a mount and ear "
    "both above a short object are not treated as occluded by it); it still ignores "
    "diffraction and treats each object as an opaque box at its nominal height. "
    "Mode A (format_avoid) preserves a standard "
    "format's canonical listener-relative angles and nudges each channel by the "
    "SMALLEST angular offset (stepped search, not a global optimum) that clears "
    "obstacles in 3D; per-channel ideal-vs-actual deviation is reported. A channel "
    "that cannot be cleared within the search window is left at its ideal angle and "
    "flagged UNRESOLVED — it is NOT silently moved. Mode B (coverage_avoid) maximizes "
    "listener-area min/max DBAP gain on wall/ceiling mounts with obstacle-colliding "
    "and occluded candidates removed in 3D; it makes NO SPL claim. When fewer "
    "wall/ceiling candidates clear the obstacle filter than the requested speaker "
    "count, Mode B places as many as clear (greedy max-min over the reduced pool) "
    "and discloses the shortfall in each speaker's note; it raises only when ZERO "
    "candidates clear. Canonical angles are reconstructed from PUBLIC guidance "
    "(ITU-R BS.775 bed/surround azimuths; Dolby Atmos Home Theater Installation "
    "Guidelines height angles, 45 deg ideal), NOT a paywalled standard, and are NOT "
    "inferred from the room."
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
    ceiling surfaces, with ONE inserted candidate filter: any candidate whose 3D
    (height-aware) clearance to every free-standing object box is below
    ``clearance_m`` — or, when ``check_line_of_sight`` is set, whose plan-view
    segment to the listener ear is blocked by a footprint — is dropped before the
    greedy max-min selection. The clearance is 3D so a ceiling/high-wall mount
    cleanly ABOVE a short piece of furniture survives (the plan-view-only P7.1
    filter wrongly emptied the pool in furnished rooms). Room-absolute (Frame A);
    makes NO SPL claim. See :data:`OBSTACLE_AWARE_PLACEMENT_NOTE`.

    The listener ear point is ``(centroid.x, listener_area.height_m,
    centroid.z)`` — identical to the server install block, so headless and
    server results do not drift.

    Graceful degradation: when the 3D-filtered candidate pool has FEWER than
    ``n_speakers`` positions, this places as many as clear (greedy max-min over
    the reduced pool) and records an honest shortfall note on every placed
    speaker; it does NOT raise. It raises ``ValueError`` (→ generic 400 at the
    server) only when the room has no wall/ceiling mount surface or when ZERO
    candidates clear the obstacle filter (fully obstructed).
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
    boxes = freestanding_boxes(room)
    # object_box == object_footprint exclusion gate, so boxes[i] aligns with
    # footprints[i]; box[5] is the object's top y for height-aware line-of-sight.
    object_tops_m = [b[5] for b in boxes]
    listener = room.listener_area
    ear = Point3(
        x=listener.centroid.x,
        y=listener.height_m,
        z=listener.centroid.z,
    )

    def _candidate_filter(cand: Point3) -> bool:
        if not position_is_clear_3d(
            cand.x, cand.y, cand.z, boxes, clearance_m=clearance_m
        ):
            return False
        if check_line_of_sight and line_of_sight_blocked(
            cand, ear, footprints, height_aware=True, object_tops_m=object_tops_m
        ):
            return False
        return True

    # Count the candidates that survive the 3D obstacle + LOS filter so we can
    # degrade gracefully (place k<n) instead of failing loud when the room is
    # furnished. Sampling is deterministic, so this pool is byte-identical to the
    # one ``place_dbap`` rebuilds internally below with the same filter.
    n_valid = sum(
        1
        for surface in mount_surfaces
        for cand in _candidates_on_surface(
            surface, inset_m=inset_m, samples_per_dim=samples_per_dim
        )
        if _candidate_filter(cand)
    )
    if n_valid == 0:
        raise ValueError(
            "coverage_avoid candidate pool is empty after the 3D obstacle "
            f"filter (clearance {clearance_m:.2f} m): every wall/ceiling mount "
            "position collides with or is occluded by a free-standing object."
        )
    n_effective = min(n_speakers, n_valid)

    result = place_dbap(
        mount_surfaces=mount_surfaces,
        n_speakers=n_effective,
        listener_area=room.listener_area,
        layout_name=layout_name,
        samples_per_dim=samples_per_dim,
        inset_m=inset_m,
        candidate_filter=_candidate_filter,
    )

    speakers = result.speakers
    if n_effective < n_speakers:
        shortfall = (
            f"obstacle-constrained: placed {n_effective}/{n_speakers} "
            f"({n_speakers - n_effective} requested speaker(s) could not clear "
            f"{clearance_m:.2f} m of a free-standing object in 3D; only "
            f"{n_valid} wall/ceiling candidate(s) cleared)"
        )
        speakers = [replace(sp, notes=shortfall) for sp in speakers]

    return PlacementResult(
        target_algorithm=TargetAlgorithm.COVERAGE_AVOID.value,
        regularity_hint="IRREGULAR",
        speakers=speakers,
        layout_name=layout_name,
    )


def _signed_offsets(max_deg: float, step_deg: float) -> list[float]:
    """``[0, +step, -step, +2step, -2step, …]`` up to ``±max_deg`` (inclusive).

    Insertion order is the deterministic tie-break for the stable sort in
    :func:`place_format_avoid` (equal-magnitude offsets keep this order).
    """
    if step_deg <= 0.0:
        raise ValueError(f"search_step_deg must be > 0; got {step_deg}")
    n = int(round(max_deg / step_deg)) if max_deg > 0.0 else 0
    offsets: list[float] = [0.0]
    for k in range(1, n + 1):
        offsets.append(k * step_deg)
        offsets.append(-k * step_deg)
    return offsets


def place_format_avoid(
    room: RoomModel,
    *,
    format_id: str,
    layout_radius_m: float = 1.8,
    clearance_m: float = 0.30,
    az_search_max_deg: float = 45.0,
    el_search_max_deg: float = 15.0,
    search_step_deg: float = 1.0,
    check_line_of_sight: bool = True,
    layout_name: str = "format_avoid",
) -> PlacementResult:
    """Format-anchored, obstacle-avoiding placement (Mode A).

    Each channel of ``format_id`` (a key of
    :data:`roomestim.place.formats.FORMAT_CATALOG`) starts at its canonical
    listener-relative angle: the ideal world point is
    ``ear + yaml_speaker_to_cartesian(az_deg, el_deg, layout_radius_m)`` where
    ``ear = (centroid.x, listener_area.height_m, centroid.z)`` — the same ear
    point as the server install block, so headless and server results do not
    drift. Angles pass through :func:`roomestim.coords.yaml_speaker_to_cartesian`
    (never hand-rolled trig).

    A channel is accepted at deviation 0 when its ideal point is clear of every
    free-standing object box by ``clearance_m`` in 3D (height-aware, so an
    elevated height/top channel above short furniture is not rejected for a
    plan-view footprint overlap) AND — unless ``check_line_of_sight`` is disabled
    — its plan-view line to the ear is not blocked. Otherwise a DETERMINISTIC increasing-deviation stepped scan tries
    angular offsets ``Δaz ∈ {±step..±az_search_max}`` × ``Δel ∈ {0,±step..
    ±el_search_max}`` sorted ascending by ``hypot(Δaz, Δel)`` (stable sort) and
    accepts the FIRST offset that clears — the smallest angular nudge. A channel
    that cannot be cleared within the search window is LEFT at its ideal angle
    and flagged ``UNRESOLVED`` in its note; it is NEVER silently moved or dropped
    (the format stays complete). Per-channel ideal-vs-actual az/el + deviation +
    ``[CLEARED|UNRESOLVED]`` is recorded in :attr:`~roomestim.model.PlacedSpeaker.notes`.

    Room-absolute (Frame A); makes NO acoustic/SPL claim. ``n_speakers`` is
    DERIVED from the format. Raises ``ValueError`` (→ generic 400 at the server)
    for an unknown ``format_id``. See :data:`OBSTACLE_AWARE_PLACEMENT_NOTE`.
    """
    fmt = get_format(format_id)
    footprints = freestanding_footprints(room)
    boxes = freestanding_boxes(room)
    # boxes[i] aligns with footprints[i] (identical exclusion gate); box[5] is the
    # object top y for height-aware line-of-sight.
    object_tops_m = [b[5] for b in boxes]
    listener = room.listener_area
    ear = Point3(
        x=listener.centroid.x,
        y=listener.height_m,
        z=listener.centroid.z,
    )

    # Deterministic offset grid, sorted ascending by combined angular deviation.
    az_offsets = _signed_offsets(az_search_max_deg, search_step_deg)
    el_offsets = _signed_offsets(el_search_max_deg, search_step_deg)
    offsets: list[tuple[float, float]] = [
        (d_az, d_el) for d_az in az_offsets for d_el in el_offsets
    ]
    offsets.sort(key=lambda o: math.hypot(o[0], o[1]))  # stable -> deterministic

    def _point_at(az_deg: float, el_deg: float) -> Point3:
        dx, dy, dz = yaml_speaker_to_cartesian(az_deg, el_deg, layout_radius_m)
        return Point3(x=ear.x + dx, y=ear.y + dy, z=ear.z + dz)

    def _clears(pt: Point3) -> bool:
        if not position_is_clear_3d(
            pt.x, pt.y, pt.z, boxes, clearance_m=clearance_m
        ):
            return False
        if check_line_of_sight and line_of_sight_blocked(
            pt, ear, footprints, height_aware=True, object_tops_m=object_tops_m
        ):
            return False
        return True

    speakers: list[PlacedSpeaker] = []
    for idx, ch in enumerate(fmt.channels, start=1):
        accepted: Point3 | None = None
        d_az_acc = 0.0
        d_el_acc = 0.0
        for d_az, d_el in offsets:
            pt = _point_at(ch.az_deg + d_az, ch.el_deg + d_el)
            if _clears(pt):
                accepted = pt
                d_az_acc = d_az
                d_el_acc = d_el
                break

        if accepted is None:
            # Nothing in the window clears -> keep the ideal point, flag it.
            actual = _point_at(ch.az_deg, ch.el_deg)
            act_az, act_el = ch.az_deg, ch.el_deg
            dev = 0.0
            status = "UNRESOLVED"
        else:
            actual = accepted
            act_az = ch.az_deg + d_az_acc
            act_el = ch.el_deg + d_el_acc
            dev = math.hypot(d_az_acc, d_el_acc)
            status = "CLEARED"

        note = (
            f"{format_id}/{ch.name}: ideal az={ch.az_deg:+.1f} el={ch.el_deg:+.1f} "
            f"-> actual az={act_az:+.1f} el={act_el:+.1f} dev={dev:.1f}deg [{status}]"
        )
        speakers.append(
            PlacedSpeaker(channel=idx, position=actual, notes=note)
        )

    return PlacementResult(
        target_algorithm=TargetAlgorithm.FORMAT_AVOID.value,
        regularity_hint="IRREGULAR",
        speakers=speakers,
        layout_name=layout_name,
    )


__all__ = [
    "OBSTACLE_AWARE_PLACEMENT_NOTE",
    "place_coverage_avoid",
    "place_format_avoid",
]
