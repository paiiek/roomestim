# ADR 0014 — Building_Lobby coupled-space: explicit exclusion from aggregate metrics

- **Status**: Accepted (v0.7.0)
- **Date**: 2026-05-09
- **Predecessor**: v0.6.0 (`7df016a`); ADRs 0008 (octave-band), 0011
  (MISC_SOFT enum), 0012 (TASLP materials closure), 0013 (TASLP-MISC
  surface budget); D14, D15, D16, D17.

## Decision

Building_Lobby is **excluded by default** from any aggregate roomestim
metric — present and future. This includes:

- The TASLP-MISC per-room surface budget (`_FURNITURE_BY_ROOM`; ADR 0013).
- The perf doc per-band MAE / median aggregate statistics in
  `docs/perf_verification_e2e_*.md`.
- Any future octave-band aggregate (cross-room band-MAE, residual-error
  envelope, etc.).

Building_Lobby remains in the per-room rows of those documents for
transparency, but is annotated as `(excluded — coupled space; see ADR
0014)` and is not consumed by any aggregate calculation.

This formalises and ratifies the v0.6 implicit exclusion (D17 / OQ-9 /
ADR 0013 §Alternatives considered (d)) as the explicit, citable v0.7
final word, until the evidence-changes named under §Reverse if surface.

## Drivers

- **TASLP §II-C "Rooms" (p.1683) describes Building_Lobby as "a large
  irregular-shaped hard-floored room with coupled spaces including a
  café, stairwell and staircase."** The recording was made in a corner
  area; the table-I shoebox `(L, W, H, V)` corresponds to that corner,
  not the lobby as a whole. The full coupled space is many times larger
  than the recording corner.
- **`ACE_ROOM_GEOMETRY["Building_Lobby"]` is a 72.9 m³ shoebox** that
  describes only the recording corner. roomestim's geometry adapter has
  no per-sub-volume representation; the predictor receives a single
  bounded volume that does not match the physical setup.
- **Sabine and Eyring assume a diffuse field in a simple bounded
  geometry**, both of which fail on coupled spaces: sound energy
  migrates between sub-volumes with different decay constants, producing
  multi-slope decay curves that no single-slope T60 estimator can
  represent. See Vorländer 2020 *Auralization* §4.4 "Coupled rooms" for
  the physics, and §4.2 (Sabine / Eyring assumptions) for why both
  models break here.
- **Empirical confirmation in v0.6 perf doc**:
  `docs/perf_verification_e2e_2026-05-08.md` shows Building_Lobby Sabine
  500 Hz error of `+1.425 s` (predicted 2.022 s vs. measured 0.597 s) —
  a 3.4× over-prediction. This magnitude is consistent with the
  predictor seeing only the smaller-V coupled corner volume but the
  measurement integrating over a larger acoustic field (energy leaking
  in from the café / stairwell sub-spaces decays slower, lowering the
  measured T60). The 3.4× ratio is far outside the ±20% / ±50% bands
  used as warning thresholds elsewhere in the audit ledger; including
  Building_Lobby in any cross-room MAE silently inflates the aggregate
  by a known-broken model assumption.

## Alternatives considered

- **(a) Include Building_Lobby in aggregate metrics with an asterisk.**
  Rejected. The 3.4× over-prediction corrupts MAE / median / envelope
  statistics; an asterisk does not undo the arithmetic. Aggregates
  exist to give a single defensible number — admitting a known-broken
  row inverts that purpose.
- **(b) Build a coupled-space predictor (Cremer / Müller two-room
  formula; Vorländer 2020 §4.4).** Rejected for v0.7. Out of scope:
  (i) requires a new predictor module mirroring Sabine/Eyring API
  shape; (ii) requires per-sub-volume geometry that the ACE adapter
  does not have and cannot recover from `ACE_ROOM_GEOMETRY` alone;
  (iii) would itself be representative-not-verbatim without a measured
  per-sub-volume coupling coefficient. Not foreclosed; see §Reverse if.
- **(c) Treat Building_Lobby as INDETERMINATE per ADR 0012 + exclude
  silently (the v0.6 status quo).** Accepted as the v0.7 explicit form.
  Promoting the v0.6 implicit exclusion to ADR 0014 closes the open
  status flagged in `RELEASE_NOTES_v0.6.0.md` "What stays deferred —
  Building_Lobby coupled-space ADR: separate v0.7+ work item."

## Why chosen

ADR 0014 promotes the v0.6 implicit exclusion to an explicit, citable
decision. Future work items (perf-doc tooling, octave-band aggregates,
external consumers) can reference ADR 0014 directly rather than
re-litigating the exclusion. The reverse-trigger conditions are
recorded once in this ADR; downstream code paths only need to honour
"is `room_id` in the exclusion list?" without carrying the rationale.

This is the smallest correct architectural move that:

- Vindicates the v0.6 `_FURNITURE_BY_ROOM` Building_Lobby exclusion
  (ADR 0013 §Alternatives considered (d)) by giving it a primary
  citation (ADR 0014) rather than a parenthetical pointer.
- Separates "Building_Lobby is excluded" (ADR 0014) from "TASLP-MISC
  furniture-budget specifics" (ADR 0013) so the exclusion does not
  re-anchor on TASLP-MISC scope drift.
- Imposes zero code change on the v0.6 numerical baseline (the
  exclusion is already in effect; this ADR documents *why*, not
  *what changes*).

## Consequences

- **Aggregate-stat reporting (perf docs, ADR 0013 §Consequences > Perf
  doc, future tooling)**: continues to exclude Building_Lobby by
  default. Each future perf doc must say so explicitly in its
  cross-room aggregate section, citing ADR 0014.
- **`_FURNITURE_BY_ROOM` Building_Lobby exclusion (ADR 0013)**: now
  explicitly motivated by ADR 0014, not just "see ADR 0012 caveat".
  The adapter docstring and `load_room` `notes` string remain unchanged
  in v0.7 (the exclusion is the same; only its primary citation
  shifts).
- **v0.6 perf doc Building_Lobby row** (`docs/perf_verification_e2e_2026-05-08.md`):
  stays in the per-room table as transparent record, but is excluded
  from any cross-room aggregate the document quotes. v0.7 does not
  re-run the gated E2E (Scope A is the only code-affecting work item);
  v0.6 perf doc remains the current v0.6+ characterisation reference.
- **ADR 0012 and ADR 0013 References**: gain a single line each
  pointing forward to ADR 0014 (parallel to existing inter-ADR
  cross-refs).
- **Decisions log**: D18 appended (D14, D15, D16, D17 bodies untouched).
- **No code change**: the exclusion is already implemented in
  `_FURNITURE_BY_ROOM` (v0.6); ADR 0014 is bookkeeping that gives the
  exclusion a stable citation handle.
- **Schema unchanged**: `__schema_version__` stays `"0.1-draft"` (D8
  unchanged).

## Reverse if

- **A future ADR provides a coupled-space predictor** (e.g.,
  Cremer / Müller two-room formula; Vorländer 2020 §4.4) **AND
  per-sub-volume geometry for Building_Lobby** (lobby + café +
  stairwell volumes individually). Both pre-conditions are required;
  shipping the predictor without sub-volume data still cannot model
  the actual recording.
- **OR a non-canonical evidence channel** (lab visit photos /
  measurement records; author email response) **yields a single
  bounded effective volume** that makes the shoebox model defensible
  for the recording corner (e.g., the "lobby corner" is in fact
  acoustically isolated from the café and the stairwell within the
  Sabine timescale). At that point Building_Lobby graduates to the
  same INDETERMINATE-but-includable status as the other 6 rooms.
- **OR an external user contributes a coupled-space predictor** and
  demonstrates **>50% improvement on Building_Lobby Sabine 500 Hz
  error without regressing the other 6 rooms**. The 50% threshold
  mirrors the v0.4 audit-finding heuristic for material-coefficient
  reverse-triggers (D13).

If any of the three conditions above fires, ADR 0014 is reverted /
superseded by a follow-on ADR that re-evaluates the exclusion list.

## References

- Eaton, J., Gaubitch, N. D., Moore, A. H., & Naylor, P. A. (2016).
  *Estimation of room acoustic parameters: The ACE Challenge.* IEEE/ACM
  TASLP 24(10), 1681–1693. DOI: 10.1109/TASLP.2016.2577502
  (institutional access).
  - **§II-C "Rooms" (p.1683)**: Building_Lobby described as "large
    irregular-shaped hard-floored room with coupled spaces including a
    café, stairwell and staircase. Measurements in Table I correspond
    to the corner area where the recordings were made whereas the total
    volume of the lobby is many times larger."
- Vorländer, M. (2020). *Auralization: Fundamentals of Acoustics,
  Modelling, Simulation, Algorithms and Acoustic Virtual Reality* (2nd
  ed.). Springer.
  - **§4.4 "Coupled rooms"**: physics of multi-volume sound-energy
    migration; multi-slope decay curves; why single-T60 estimators fail.
  - **§4.2 "Reverberation time"**: Sabine / Eyring diffuse-field +
    bounded-geometry assumptions.
- ADR 0012 — Eaton 2016 TASLP final reviewed; per-surface materials NOT
  in paper. §Decision documents the Building_Lobby structural caveat.
- ADR 0013 — TASLP-derived MISC_SOFT surface budget per room.
  §Alternatives considered (d) is the v0.6 form of the exclusion that
  ADR 0014 formalises.
- D17 — v0.6 OQ-9 lock (Building_Lobby = exclude).
- `docs/perf_verification_e2e_2026-05-08.md` — empirical evidence row
  for the +1.425 s Building_Lobby 500 Hz error; preserved as the v0.6
  characterisation reference (no v0.7 regeneration).
- `RELEASE_NOTES_v0.6.0.md` — "What stays deferred — Building_Lobby
  coupled-space ADR: separate v0.7+ work item" (the open status this
  ADR closes).
- ADR 0015 — Lecture_2 ceiling/seat sensitivity bracketing methodology
  (v0.8.0); Building_Lobby remains excluded under §Decision; cross-ref
  for the v0.8+ residual-shrinking experiment trail.
