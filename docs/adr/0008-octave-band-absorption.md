# ADR 0008 — Octave-band absorption schema extension (v0.3)

- **Status**: Accepted (v0.3)
- **Date**: 2026-05-06
- **Cross-ref**: design plan §3.2, decisions D7, D12; spec.md §3 (workstream d).

## Context

v0.1.1 shipped with a single mid-band 500 Hz absorption coefficient per surface
(`absorption_500hz`, required). The `sabine_rt60()` API operates at 500 Hz only.
D7 reverse criterion states: "engine reverb integration requires octave-band data."
The engine has not yet explicitly requested this, but v0.3 ships the capability
proactively because:

1. The schema cost is small (one optional block, backwards-compatible).
2. The alternative — waiting until the engine asks, then landing a breaking change
   in a v0.4 schema flip — is more costly than an opt-in extension now.
3. Per-octave-band Sabine RT60 is required for E2E validation against the ACE
   Challenge corpus, which provides pre-tabulated T60 at ISO-266 octave bands.

## Decision

Add an OPTIONAL `absorption` block per surface with 6 octave-band coefficients:
`a125`, `a250`, `a500`, `a1000`, `a2000`, `a4000` (125 Hz – 4 kHz).

- `absorption_500hz` REMAINS REQUIRED and is the canonical fallback when `absorption` is absent.
- Reader fallback: prefer `absorption.a500` over `absorption_500hz` on mismatch (warn-not-raise).
- Writer: emit `absorption` block ONLY when `Surface.absorption_bands is not None` (opt-in via `--octave-band` CLI flag).
- Default CI path: absorption_bands=None → byte-identical to v0.1.1 (A12 preserved).

## Drivers

1. E2E RT60 validation against ACE Challenge requires per-band predictions → per-band Sabine.
2. Schema extension cost at v0.3 is near-zero (optional block, both schema files updated).
3. `MaterialAbsorptionBands` table (Vorländer-class representative values) enables the per-band path without new dependencies.
4. 8 kHz band is out of scope for v0.3 — Vorländer 2020 Appx A typical room-acoustics tables stop at 4 kHz; 8 kHz extension deferred to v0.4 if engine reverb integration demands it.

## Alternatives considered

- **Wait for engine request (defer to v0.4)**: rejected because ACE E2E adapter needs per-band
  predictions now, and the schema cost of deferral is a future breaking change.
- **7 bands (add 8 kHz)**: rejected per OD-8 — Vorländer Appx A stops at 4 kHz; no measured
  data at 8 kHz in ACE corpus pre-tabulated T60; extension adds no validated benefit.
- **Full material absorption coefficient table in schema**: rejected — too prescriptive; material
  coefficients live in `roomestim.model.MaterialAbsorptionBands`, not the schema.

## Why chosen

Minimal opt-in extension. Backwards-compatible (required field unchanged, new field optional).
Proactive delivery before engine request avoids a future breaking schema version bump.

## Consequences

- (+) E2E RT60 characterisation against ACE corpus now possible with per-band Sabine.
- (+) Schema forwards-compatible with engine reverb integration when/if requested.
- (+) New opt-in `--octave-band` CLI flag for `roomestim ingest` / `roomestim run`.
- (−) Two code paths in writer/reader (with/without absorption block) — mitigated by unit tests.
- (−) `MaterialAbsorptionBands` values are representative (not verbatim Vorländer Appx A rows)
  — honesty markers in docstrings per v0.1.1 Critic M1 precedent.

## Reverse criteria

- If engine team requests a different band set (e.g., 7 bands to 8 kHz), a v0.4 schema extension
  ADR is authored and the `absorption` block is extended or replaced.
- If per-band Sabine predictions are consistently poor (>50% error across multiple rooms in E2E
  validation), revisit the material coefficient table before v0.4.

## Follow-ups

- Per-row Vorländer Appx A citation: `roomestim/model.py` carries "representative typical
  room-acoustics row from Vorländer-class textbook tables; not a verbatim Appx A row" inline.
- E2E ACE adapter: `roomestim/adapters/ace_challenge.py`. Gated test: `tests/test_e2e_ace_challenge_rt60.py`.
- D12 entry in decisions.md records this decision.
