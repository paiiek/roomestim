# ADR 0009 — Eyring as a parallel RT60 predictor (v0.4)

- **Status**: Accepted (v0.4.0)
- **Date**: 2026-05-06
- **Cross-ref**: D7, D12, D13, D14, ADR 0008, `.omc/plans/v0.4-audit-findings.md`,
  `docs/perf_verification_e2e_2026-05-06.md`.

## Context

v0.3 shipped per-band Sabine RT60 (`sabine_rt60_per_band`) and an opt-in octave-band
schema. The v0.3 E2E run against the 7-room ACE Challenge corpus (D13) showed
Sabine errors > 50% on 5 of 7 rooms at 500 Hz. D13 scheduled a v0.4 work item to
"consider Eyring or Millington-Sette correction for high-absorption rooms (Vorländer
2020 §4.2)".

Eyring's correction replaces Sabine's `α_total = Σ S_i α_i` denominator with
`−S_total · ln(1 − ᾱ)`, where `ᾱ = α_total / S_total`. In the low-α limit the
two are identical (Taylor: `−ln(1−x) → x`); in the high-α limit Eyring is strictly
smaller, undoing Sabine's known overestimate in heavily-absorbed rooms.

Why now (and not v0.5):
- D13 explicitly scheduled this for v0.4.
- Cost is small: two new pure functions in `roomestim/reconstruct/materials.py`,
  six unit tests, a 6-tuple extension of the existing E2E report; no production code
  outside `materials.py` is touched, no schema change, no CLI flag.

## Decision

Add `eyring_rt60(volume_m3, surface_areas) -> float` and
`eyring_rt60_per_band(volume_m3, surface_areas) -> dict[int, float]` to
`roomestim/reconstruct/materials.py` as **parallel predictors**.

- Sabine remains the **default**. Existing call sites are not changed.
- Eyring is exposed at the **callable level only** at v0.4. No CLI flag is wired;
  consumers wanting per-predictor output call the function directly. Schema-level
  exposure is deferred until ≥1 consumer asks for it.
- Both per-band predictors must satisfy `eyring(band) ≤ sabine(band) + 1e-9` per band
  per room. The gated E2E test enforces this invariant per room and per band.

## Drivers

1. D13 scheduled this for v0.4 explicitly.
2. Predictor choice is empirically not the dominant ACE-corpus error source
   (Δ ≤ 0.08 s at 500 Hz across 7 rooms — see audit-findings Finding 2). Shipping
   Eyring is honest delivery on the v0.4 schedule, not a claim that it fixes the gap.
3. Vorländer 2020 §4.2 monotonicity invariant gives a runtime check that catches
   coefficient/coding errors immediately (the E2E test fails loudly if the invariant
   ever flips).
4. Backwards-compatible: A12 byte-equality of every existing default-lane test holds.

## Alternatives considered

- **Replace Sabine with Eyring as the default RT60 predictor.** Rejected. Would
  break the d-inv-3 byte-equality of `sabine_rt60` and `sabine_rt60_per_band`,
  invalidating the v0.1.1 frozen golden in `tests/fixtures/golden/sabine_legacy_rt60_500hz.txt`
  and any downstream consumer that already pinned numerical expectations against
  Sabine output (A12).
- **Ship Millington-Sette per-surface decay instead of Eyring.** Rejected for v0.4.
  Millington-Sette `T = 0.161 V / Σ −S_i ln(1 − α_i)` is per-surface, which is more
  faithful in heavily-mixed-material rooms but raises `ValueError` on any single
  surface with α≥1 (more brittle than Eyring's averaged ᾱ). Worth a future ADR but
  not the v0.4 scope.
- **Wait until v0.5.** Rejected. D13 explicitly scheduled this for v0.4. Deferring
  again would erode the decisions log's predictive value.

## Why chosen

Minimal additive surface, exact spec match for D13, runtime-verified invariant against
Sabine. No schema/CLI churn. Honest framing: v0.4 ships the predictor; the audit
document records empirically that the predictor choice is not the dominant ACE-corpus
error source.

## Consequences

- (+) v0.4 callers can compute Eyring scalar and per-band RT60.
- (+) E2E perf doc carries both predictors side-by-side per room and per band.
- (+) Runtime monotonicity assertion catches mis-coded coefficient or formula
  regressions on the next E2E run.
- (−) Two predictors in the public API → consumers must pick. Mitigated by Sabine
  remaining the default in CLI/adapter codepaths and by ADR 0009 + audit-findings
  spelling out when each is appropriate.
- (−) Eyring still inherits Sabine's diffuse-field assumption; in non-diffuse rooms
  (Building_Lobby coupled spaces; Lecture_1 large lightly-damped) both predictors
  miss the same physics. Audit-findings Finding 4 records this.

## Reverse if

- A v0.5 audit (after Eaton 2016 Table I confirms `ACE_ROOM_GEOMETRY`) shows Eyring
  is materially worse than Sabine on the corrected geometry → revisit; possibly
  demote to a `MILLINGTON_SETTE`-style alternative.
- A consumer reports the Eyring API breaks their workflow → v0.4.x patch.
- The `eyring ≤ sabine + 1e-9` invariant ever fails in CI → halt-and-investigate; the
  invariant is load-bearing (it codifies Vorländer 2020 §4.2).

## References

- Eyring, C. F. (1930). "Reverberation time in dead rooms." JASA 1(2), 217–241.
- Vorländer, M. (2020). *Auralization*, §4.2. Springer.
- ADR 0008 — octave-band absorption schema extension (v0.3).
- D13 — D12 reverse-trigger fired empirically; v0.4 work scheduled.
- D14 — Eyring shipped; ACE byte-audit deferred.
