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
    "in-situ RT60 (model error observed up to ~+/-1.4 s versus measured, larger "
    "for coupled / non-shoebox spaces). Treat as relative GUIDANCE, not a "
    "guaranteed value."
)

__all__ = ["RT60_DISCLOSURE", "RT60_MODEL_NAME"]
