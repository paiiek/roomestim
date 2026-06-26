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
    "observation (ACE corpus); ACROSS material regimes the error is "
    "BIDIRECTIONAL (the ISM default over-predicts strongly-reflective "
    "rectilinear rooms and under-predicts foam / absorber-dominated rooms), and "
    "for small, hard-surfaced or unknown-material rooms the deviation can reach "
    "the same order as the RT60 itself (observed up to ~2.3 s versus measured), "
    "and is larger for coupled / non-shoebox spaces. WITHIN the DEFAULT "
    "UNKNOWN-material regime the product actually runs (no user-assigned "
    "materials), the independently validated bias is ONE-SIDED POSITIVE: "
    "against measured U-Rochester RIR (figshare 48711175, CC-BY 4.0) for "
    "acoustically treated rooms the model over-predicts RT60 by +160~826% "
    "(median +326%, rectilinear n=7), so this default-regime figure is NOT "
    "suitable for sizing acoustic treatment. A second, independent measured "
    "validation against the dEchorate calibrated shoebox corpus (Zenodo "
    "5562386, CC-BY 4.0; 10 absorption configs x 4 octave bands 500-4000 Hz, "
    "measured RT60 0.14-0.81 s) corroborates this and adds a quantified trend "
    "result: the diffuse-field Sabine / Eyring predictors track the measured "
    "RT60 ORDERING across configurations (Spearman rho ~= 0.90), but ABSOLUTE "
    "accuracy is NOT established -- with literature absorption analogs the ISM "
    "over-predicts the reflective configs (MAPE ~103%, dynamic range ~11x too "
    "wide) while Sabine under-predicts (MAPE ~28%). Because dEchorate -- like "
    "every measured corpus on hand -- publishes material NAMES but no "
    "per-surface absorption coefficients, the absolute error is dominated by "
    "absorption-INPUT uncertainty, so a tight absolute-accuracy band remains "
    "DEFERRED while the ordering/relative-trend validity is measurement-backed. "
    "Treat as relative GUIDANCE, not a guaranteed value."
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
    "web-extra reproducibility asymmetry (see ADR 0040). A multi-room MEASURED RT60 "
    "corpus (U-Rochester, CC-BY 4.0) is now on hand, but every measured corpus is a "
    "shoebox / cuboid, so the cascade and the shoebox diffuse-field cap/blend remain "
    "DEFERRED (no non-shoebox GT; the cap reduces error only via a material confound "
    "and is redundant with the existing prefer_ism=False diffuse path; see ADR 0040 "
    "Status-update 2026-06-12 / C2)."
)

# RoomPlan CapturedStructure per-room split disclosure (ADR 0050). A real
# multi-room ``CapturedStructure`` export gives NO element->room foreign key:
# ``sections`` (= rooms) carry only ``{label, story, center}`` and walls/objects
# are flat arrays. The splitter therefore assigns each wall to a section by a
# HEURISTIC (floor-plane nearest-section-center, story-matched), so the per-room
# split is a RECONSTRUCTION, not Apple-authoritative membership. Geometry
# provenance stays "measured" (LiDAR); this note carries the membership-heuristic
# honesty. Single source of truth — reference, do not retype.
ROOMPLAN_STRUCTURE_SPLIT_NOTE: str = (
    "The per-room split of a RoomPlan CapturedStructure is a HEURISTIC "
    "RECONSTRUCTION, not Apple-authoritative data: the export gives NO "
    "element->room membership (sections carry only label/story/center, and "
    "walls/doors/windows/objects are flat arrays). roomestim assigns each wall "
    "to the story-matched section whose center is nearest in the floor plane "
    "(x, z); this can mis-partition nested, adjacent, or same-label rooms and "
    "there is NO ground truth to measure the error. Each per-room footprint is "
    "the floor-projected CONVEX HULL of that room's assigned walls (an "
    "OVER-ESTIMATE that does not recover re-entrant corners), NOT a measured "
    "floor polygon — the export's single floors[] entry is building-wide. "
    "Ceiling height is SYNTHESIZED as the median assigned wall height (RoomPlan "
    "captures no ceiling). There is intentionally NO aggregate footprint, "
    "combined volume, or combined RT60. Do NOT treat the split as accurate "
    "multi-room recovery."
)

# Measured (blind) RT60 disclosure ([audio] extra, B-track A3). Unlike the
# geometric RT60 MODEL (Sabine / Eyring / ISM), a blind RT60 estimate is a
# MEASUREMENT derived from a recorded signal — but the blind estimator (Ratnam
# et al. maximum-likelihood decay model, via the `blind-rt60` package) carries
# its OWN error: a controlled-sim benchmark now bounds the decay-fit accuracy
# (~9% MAPE under clean impulsive excitation, see note body), but roomestim has
# NOT yet validated it end-to-end against a measured corpus (ACE benchmark
# deferred). It is a single BROADBAND value, not per-octave-band. Single source
# of truth — reference, do not retype.
MEASURED_RT60_NOTE: str = (
    "Measured (blind) RT60 is estimated from a recorded audio signal by the "
    "`blind-rt60` package (Ratnam et al. maximum-likelihood reverberation-decay "
    "model) — it is a MEASUREMENT, not the geometric Sabine/Eyring/ISM model, so "
    "it reflects the actual room + furnishings rather than assumed materials. "
    "HOWEVER the blind estimator carries its OWN error. A CONTROLLED-SIMULATION "
    "benchmark now BOUNDS the estimator's decay-fit accuracy (vs Schroeder RT60 "
    "of pyroomacoustics shoebox RIRs under clean impulsive excitation: ~9% MAPE, "
    "max ~18%, n=5), but this is a SIM bound, NOT measured-room end-to-end error; "
    "the END-TO-END measured-corpus (ACE) accuracy benchmark stays deferred. So "
    "treat the value as an indicative measurement, not a calibrated reference. It "
    "is a single "
    "BROADBAND RT60 (seconds), NOT per-octave-band, and its accuracy depends on "
    "the recording (a clean impulsive excitation — a clap or balloon pop — in a "
    "quiet room is best; steady background noise degrades it). Requires the "
    "optional `roomestim[audio]` extra (blind-rt60 + soundfile)."
)

__all__ = [
    "RT60_DISCLOSURE",
    "RT60_MODEL_NAME",
    "MEASURED_RT60_NOTE",
    "CEILING_CONFIDENCE_HEURISTIC_NOTE",
    "IMAGE_CAM_H_SCALE_NOTE",
    "POLYGON_ISM_GEOMETRY_NOTE",
    "ROOMPLAN_MULTI_FLOOR_NOTE",
    "ROOMPLAN_STRUCTURE_SPLIT_NOTE",
]
