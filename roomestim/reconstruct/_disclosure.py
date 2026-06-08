"""Single source of truth for the RT60 / acoustics honesty disclosure.

The acoustics layer is a geometric-acoustics MODEL (Sabine / Eyring / ISM),
not a validated acoustic measurement. RT60 depends on surface materials, and
roomestim does not infer materials — they are UNKNOWN, assumed, or hardcoded.
Observed model error is up to ~+/-1.4 s versus measured ACE-corpus RT60
(``docs/perf_verification_e2e_2026-05-08.md``): mean +0.16 s, with the worst
outliers on coupled / non-shoebox spaces (Building_Lobby +1.4 s, an excluded
coupled space; Lecture_2 -0.9 s). This module centralises the disclosure string
so every user-facing surface (predictor docstring, export sidecar, CLI, README)
cites the same honest framing.

Layering: core module, no web / torch dependency.
"""
from __future__ import annotations

# The geometric-acoustics model family backing every RT60 estimate.
RT60_MODEL_NAME: str = "geometric-acoustics (Sabine / Eyring / ISM)"

# Concise, honest disclosure. Single source of truth — reference, do not retype.
RT60_DISCLOSURE: str = (
    "RT60 is a geometric-acoustics MODEL estimate (Sabine / Eyring / ISM) that "
    "depends on surface materials. roomestim does not infer materials; when "
    "materials are UNKNOWN or assumed the estimate is indicative only. This is "
    "NOT a validated acoustic measurement and can deviate substantially from "
    "in-situ RT60. The ~+/-1.4 s figure is the typical mixed-material-room "
    "observation (ACE corpus); the error is BIDIRECTIONAL (the ISM default "
    "over-predicts strongly-reflective rectilinear rooms and under-predicts "
    "foam / absorber-dominated rooms), and for small, hard-surfaced or "
    "unknown-material rooms the deviation can reach the same order as the RT60 "
    "itself (observed up to ~2.3 s versus measured), and is larger for coupled "
    "/ non-shoebox spaces. Treat as relative GUIDANCE, not a guaranteed value."
)

# Image-backend cam_h scale-ambiguity. A single equirectangular panorama recovers
# room SHAPE but NOT absolute scale; the camera height IS that scale, and every
# recovered dimension is exactly linear in it. Single source of truth — reference,
# do not retype.
IMAGE_CAM_H_SCALE_NOTE: str = (
    "A single equirectangular panorama is SCALE-AMBIGUOUS: HorizonNet recovers room "
    "SHAPE, and the camera height (cam_h) IS the global metric scale. Because "
    "r = cam_h / tan(-v_floor), every recovered dimension is EXACTLY linear in cam_h "
    "(floor area scales with its square), so a fractional cam_h error maps 1:1 to a "
    "fractional room-scale error. There is NO pixel-only signal that recovers absolute "
    "cam_h from one pano; an unanchored cam_h is an ASSUMED prior, not a measurement. "
    "Supply a measured camera height (ScaleAnchor 'known_distance') for metric scale."
)

# RoomPlan multi-floor-entry disclosure. The accepted RoomPlan sidecar schema is
# single-room by construction (one ``dimensions``, flat ``walls[]/floors[]/
# ceilings[]``), and ``RoomModel`` is single-room by design (one
# ``floor_polygon``). When a sidecar carries more than one floor entry (e.g. a
# split-level or disjoint floor patch within one room), only the primary entry
# is represented; the rest were previously dropped SILENTLY. This note makes that
# loss explicit. Single source of truth — reference, do not retype.
ROOMPLAN_MULTI_FLOOR_NOTE: str = (
    "RoomPlan sidecar has more than one floor entry, but RoomModel is single-room "
    "by design (one floor_polygon). Only the primary (first) floor entry is "
    "represented; the additional floor entries are NOT merged or exported and the "
    "capture is treated as single-room. roomestim does NOT support multi-room / "
    "multi-floor captures (no RoomCollection); if the extra floor entries are part "
    "of a distinct room or level, that geometry is not modelled."
)

# Ceiling-confidence under-report guard. ``ceiling_coverage`` is a genuine
# geometric measurement; ``ceiling_confidence`` is a HEURISTIC label, NOT a
# calibrated probability. Single source of truth — reference, do not retype.
CEILING_CONFIDENCE_HEURISTIC_NOTE: str = (
    "ceiling_confidence is a HEURISTIC label (NOT a calibrated probability) derived "
    "from ceiling_coverage = the fraction of 25 cm floor-footprint grid cells that "
    "contain a scan vertex within +/-10 cm of the detected ceiling plane. "
    "coverage >= 0.50 -> 'high'; coverage < 0.50 -> 'low' (the densest upper plane "
    "spans a minority of the footprint, so a tabletop, mezzanine slab, or severely "
    "under-sampled ceiling may have been mis-picked and the height UNDER-reported). "
    "The 0.50 threshold is a conservative geometric rule of thumb validated only on "
    "synthetic fixtures; it is NOT calibrated against measured data. 'unknown' means "
    "coverage was not measured (e.g. image-reconstructed or hand-authored geometry)."
)

# Polygon image-source GEOMETRY-only disclosure. The polygon image-source
# enumerator returns mirror-image POSITIONS + a per-image visibility flag for an
# extruded simple polygon; it emits NO RT60 and is NOT wired into the predictor.
# Polygon-ISM RT60 is DEFERRED (no non-shoebox measured GT; pyroomacoustics
# RT60-fit reliability unverified; pyroomacoustics is a web-extra). Single source
# of truth — reference, do not retype.
POLYGON_ISM_GEOMETRY_NOTE: str = (
    "The polygon image-source enumerator is GEOMETRY ONLY: it returns first-order "
    "image-source POSITIONS (mirror of the source across each wall / floor / ceiling "
    "plane) plus a per-image visibility flag, for an extruded simple polygon. It is "
    "NOT an acoustic predictor: it emits NO RT60 and is NOT wired into "
    "predict_rt60_default. Polygon-ISM RT60 is DEFERRED pending a non-shoebox "
    "MEASURED ground-truth corpus (magnitude otherwise unverifiable), an unverified "
    "pyroomacoustics RT60-fit reliability on sparse ISM RIR, and the pyroomacoustics "
    "web-extra reproducibility asymmetry (see ADR 0040)."
)

__all__ = [
    "RT60_DISCLOSURE",
    "RT60_MODEL_NAME",
    "CEILING_CONFIDENCE_HEURISTIC_NOTE",
    "IMAGE_CAM_H_SCALE_NOTE",
    "POLYGON_ISM_GEOMETRY_NOTE",
    "ROOMPLAN_MULTI_FLOOR_NOTE",
]
