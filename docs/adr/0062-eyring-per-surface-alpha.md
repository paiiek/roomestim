# ADR 0062 — Eyring RT60 honors per-surface α (custom-α core fix)

- Status: Accepted
- Version: v0.62.0 (MINOR — behavior change on the Eyring path; label rooms byte-equal)
- Date: 2026-07-01
- Supersedes / relates: ADR 0028 (predictor cascade), ADR 0030 (ISM > Eyring default),
  ADR 0031 (closed material enum), P5.9 material editing.

## Context

RT60 prediction (`roomestim/reconstruct/predictor.py`) has two branches:

- **ISM (rectilinear shoebox)** — already computes absorption as an area-weighted
  mean of **per-surface `surface.absorption_500hz`** (`_area_weighted_alpha`,
  `_shoebox_per_band_alphas`). Custom / edited α is HONORED here.
- **Eyring (non-shoebox = most captured/measured rooms, and the ISM lower-bound
  target)** — consumed a `dict[MaterialLabel, float]` of per-material area sums and
  looked up `MaterialAbsorption[label]` (the TABLE) in
  `materials.eyring_rt60` / `eyring_rt60_per_band`. **Per-surface custom α was
  DISCARDED.**

Consequence: any surface whose stored α diverges from its label's table value —
edited materials plus several adapters (`moge`, `image` unknown-α, `room_yaml_reader`
`a500_from_block`, `ace_challenge` `alpha_500`, `reconstruct/walls`) — had NO effect on
RT60 for non-shoebox rooms, which are nearly every real captured room.

## Decision

Route the Eyring branch through **per-surface α**, matching what the ISM branch
already does. New additive helpers in `materials.py`:

- `eyring_rt60_from_pairs(volume_m3, pairs: Sequence[tuple[area, α_500]]) -> float`
- `eyring_rt60_per_band_from_pairs(volume_m3, pairs: Sequence[tuple[area, bands_or_None, α_500]]) -> dict[int, float]`

Same math and guards as the label-dict functions (empty/zero/`alpha_bar ≥ 1`). The
label-dict `eyring_rt60` / `eyring_rt60_per_band` are UNCHANGED, still exported, still
used by the web report and unit tests.

`predictor.py` builds the per-surface pair list from
`room.surfaces + _objects_to_surfaces(room.objects)` — the SAME surface set the
label-dict folded (NO door/window α overrides, which the Eyring path never applied —
this preserves parity). All five Eyring call sites now route through the new helpers:
`predict_rt60_default` (ISM lower-bound target, object-fallback, non-shoebox return) and
`predict_rt60_default_per_band` (target, object-fallback, non-shoebox return).

The public signatures `predict_rt60_default(room, surface_areas_by_material, ...)` /
`_per_band` are UNCHANGED. `surface_areas_by_material` is still accepted (external
callers pass it) but no longer drives the Eyring value — the α now derives from `room`.
Documented in the docstrings.

## Byte-equality (grouping rationale)

The pre-v0.62.0 Eyring summed `Σ_material (Σarea_m) * table[m]` — ONE multiply per
material on the pre-summed area. To reproduce this EXACT floating-point result for
"label" rooms while honoring custom α, the predictor **groups surfaces by `(material, α)`**
(single-band) / `(material, resolved_bands)` (per-band) and multiplies each group's
pre-summed area by that group's α:

- **Label room** (every surface's α equals `MaterialAbsorption[material]`): each material
  collapses to ONE group → `group_area * α == Σarea_m * table[m]` bit-for-bit (same
  accumulation order: `room.surfaces` then object faces). ✅ byte-equal — verified
  empirically against `eyring_rt60` / `eyring_rt60_per_band` on an L-shaped label room.
- **Per-band `absorption_bands is None`**: the predictor resolves it to
  `MaterialAbsorptionBands[material]` (the table) before grouping — exactly the coefficient
  the old `eyring_rt60_per_band` used — so a label room is byte-equal regardless of whether
  its surfaces stored per-band data. Every `MaterialLabel` has a bands entry, so the
  helper's `α_500` broadcast fallback stays inert for known materials.
- **Custom-α surface**: a divergent α forms its own group → its α enters the Eyring mean.
  ✅ intended.

## Intentional (non-byte-equal, CORRECT) changes

Rooms whose adapters already store a per-surface α diverging from
`MaterialAbsorption[label]` change RT60 on the Eyring path (Eyring finally honors their
stored α): `moge`, `image` (unknown_a500 / unknown_bands), `room_yaml_reader`
(a500_from_block), `ace_challenge.py:480` (alpha_500 / alpha_bands),
`reconstruct/walls.py`. ISM (shoebox) goldens are UNCHANGED — that path was already
per-surface.

**Goldens re-baselined at v0.62.0** (Eyring path, divergent per-surface α):
_none — the full default suite (886) remained byte-equal after routing; no golden required
re-baselining._ (Should any future adapter-α golden move, mark it inline
`# v0.62.0: Eyring now honors per-surface α (custom-α core fix)`.)

## Consequences

- Edited materials (P5.9) and adapter-divergent α now affect RT60 on non-shoebox rooms.
- The ISM lower-bound target uses the same per-surface α, so the invariant
  `ISM ≥ Eyring − tol` stays coherent.
- No new dependencies; stdlib only; core stays torch-free.
