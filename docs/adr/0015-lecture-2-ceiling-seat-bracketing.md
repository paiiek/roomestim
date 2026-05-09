# ADR 0015 — Lecture_2 ceiling/seat sensitivity bracketing methodology

- **Status**: Accepted (v0.8.0)
- **Date**: 2026-05-09
- **Predecessor**: v0.7.0 (`b56ea7c` — WFS CLI ergonomics + ADR 0014); ADRs
  0008 (octave-band), 0009 (Eyring parallel predictor), 0010 (ACE geometry
  arXiv-verified), 0011 (MISC_SOFT enum), 0012 (TASLP materials closure),
  0013 (TASLP-MISC surface budget), 0014 (Building_Lobby coupled-space
  exclusion); D14, D15, D16, D17, D18.

## Decision

v0.8 ships a **sensitivity bracketing harness** for the Lecture_2 residual.
Four committed variants and one optional bounding case are evaluated:

- **V0** baseline — library default; byte-equal to v0.7 numerical baseline.
- **V1** ceiling swap — Lecture_2 ceiling material → `ceiling_drywall`
  (replacing default `ceiling_acoustic_tile`).
- **V2** lecture_seat α split — unoccupied-seat profile
  (`α₅₀₀ = 0.20`; per-band tuple `(0.10, 0.16, 0.20, 0.24, 0.26, 0.26)`)
  applied at the test layer via the new `overrides=` kwarg on
  `_build_room_model(...)`. The library `MaterialAbsorption` /
  `MaterialAbsorptionBands` and `_PIECE_EQUIVALENT_ABSORPTION_*` dicts are
  **NOT** mutated.
- **V3** combined — V1 + V2.
- **V4** bounding — ceiling = `wall_concrete` (very low absorption);
  characterising "what would close the gap entirely?". **Env-gated**
  (`ROOMESTIM_BRACKET_V4=1`); not in the default appendix doc.

The harness is **measurement, not commitment**. v0.6/v0.7 numerical baseline
is preserved (overrides default `None` ⇒ byte-equal output). No library-level
coefficient or assignment is changed. The result — positive or null — is
recorded in:

- `docs/perf_verification_lecture2_bracket_2026-05-09.md` (deterministic
  appendix; auto-emitted by
  `tests/test_lecture_2_ceiling_seat_bracket.py::test_bracket_emits_perf_doc_appendix`).
- `RELEASE_NOTES_v0.8.0.md` §What ships.
- This ADR §Consequences (v0.8 verdict line at ship time).

## Drivers

- **v0.6 / v0.7 perf doc shows Lecture_2 dominates 58–72 % of ex-BL corpus
  residual error per band**: under-predicts every band (−0.908 s @500 Hz,
  −1.146 s @1 kHz, −1.054 s @2 kHz, −0.863 s @4 kHz vs measured). The
  cross-room MAE is not a useful summary while one room dominates the sum.
- **v0.7 critic verdict**: 3 releases of "wait for non-canonical evidence"
  confuses unknown ground truth with unfalsifiable hypothesis; the corpus
  IS the truth-table. Bracketing yields a falsifiable answer.
- **Bracketing has two valid outcomes**:
  - *Positive*: a single-coefficient swap closes the gap → publishable
    finding + v0.9 ratification reverse-trigger candidate.
  - *Null*: no single-coefficient swap closes the gap → publishable
    null, ruling out F3 + lecture_seat single-coefficient explanations
    and pointing v0.9 at coupled-space modelling / non-Sabine predictors.
- **Critic-flagged ADR cadence**: each ADR must record a real new
  commitment. v0.8 has exactly one (the bracketing methodology); no
  ADR 0016 is spawned by the bracketing experiment alone.

## Alternatives considered

- **(a) Bracketing as a library module under `roomestim/sensitivity/`.**
  Rejected. Sensitivity work is a *measurement of the library*, not a
  library *behaviour*. The repo precedent (ADR 0014 §Alternatives
  considered (b)) is "audit goes in `tests/` + `docs/`; library is for
  committed behaviour." Putting bracketing in the library tempts future
  authors to call it from production code paths — at which point the
  override hook becomes a coefficient channel and the library is no
  longer byte-equal to its committed defaults.
- **(b) Ship F4a constrained sensitivity sweep at 2 kHz / 4 kHz
  (`MaterialAbsorptionBands[wall_painted]` and `[ceiling_drywall]`) as
  the v0.8 headline.** Rejected — broader sweep without sharpened prior;
  spawned per-room-per-band combinatorial space without a falsifying
  question. Deferred to v0.9 *gated on Scope A outcome*: if the V0..V3
  bracketing gives a positive verdict, F4a may be unnecessary; if null,
  v0.9 enters the broader sweep with a sharpened prior over which rows
  matter (e.g., the null result rules out single-coefficient F3 and
  redirects v0.9 toward per-band sweep + coupled-space modelling).
- **(c) Ratify the winning variant as the v0.8 default.** Rejected.
  Ratification re-anchors on F3 ceiling-material entanglement: changing
  `ACE_ROOM_GEOMETRY["Lecture_2"]["ceiling"]` (or
  `_PIECE_EQUIVALENT_ABSORPTION_*["lecture_seat"]`) on the basis of a
  bracketing result alone is the same kind of "guess swapped for guess"
  D14 5b warned against. The ratification reverse-trigger (below) is
  deliberately stricter than "won the bracket".
- **(d) Ship Scope A only without the per-band MAE snapshot
  (`tests/test_per_band_mae_ex_bl_snapshot.py`).** Rejected. The
  snapshot is the infrastructure that makes future bracketing PRs
  auto-evaluated against residuals (critic M2 finding: "test count
  growth ≠ residual coverage"). Without it, future PRs editing the
  predictor or per-band tables can shift MAE silently.
- **(e) Write a coupled-space predictor (Cremer / Müller two-room
  formula; Vorländer 2020 §4.4) as the v0.8 headline.** Rejected. ADR
  0014 §Alternatives considered (b) carved this out: needs per-sub-volume
  geometry the ACE adapter does not have. Out of v0.8 scope.

## Why chosen

- Minimum-leverage answer to the critic verdict ("v0.7 was borderline ADR
  theatre; v0.8 must ship a residual-shrinking experiment"). Bracketing is
  a falsifiable measurement; the test suite goes green either way; v0.8
  ships a publishable result.
- Preserves the v0.6/v0.7 numerical baseline. Library defaults are
  byte-equal under `overrides=None`; the gated E2E numbers do not move.
- Couples cleanly with the per-band MAE snapshot (`Scope B`) which
  freezes the v0.6/v0.7 residual signature so future PRs editing
  predictor / adapter / per-band tables that shift MAE force a one-line
  golden update + PR justification.

## Consequences

- `_build_room_model(...)` gains an additive `overrides=` keyword:
  `_RoomBuildOverrides(ceiling_label, seat_alpha_500, seat_alpha_bands)`.
  Default-equivalent path (`overrides=None`) is byte-equal to v0.7.
- `_misc_soft_surface_from_furniture(...)` is **byte-equal** to v0.7. A
  new sibling `_misc_soft_surface_from_furniture_with_alpha(...)` provides
  the per-call seat-α channel used only when an override is in flight.
- New default-lane perf doc:
  `docs/perf_verification_lecture2_bracket_2026-05-09.md`. Deterministic
  byte-content (idempotent emit; verified by stable md5sum across reruns).
- New default-lane test files:
  - `tests/test_lecture_2_ceiling_seat_bracket.py` (+5 tests).
  - `tests/test_per_band_mae_ex_bl_snapshot.py` (+2 tests).
- New in-tree fixture
  `tests/fixtures/ace_eaton_2016_table_i_measured_rt60.csv` (factual
  reproduction of the v0.6 perf-doc measured-T60 column; not predictor
  output; ADR 0014 applies).
- New golden
  `tests/fixtures/golden/per_band_mae_ex_bl_2026-05-09.json` (frozen MAE
  derived once from the v0.6 perf doc + recomputation match).
- Default-lane test count: 104 → 111 (+5 bracketing + +2 snapshot).
  Existing 104 tests remain byte-equal.
- v0.8 numerical verdict (recorded at ship time; see
  `docs/perf_verification_lecture2_bracket_2026-05-09.md` §2 for the
  exact figures): **NULL** — V3 (combined ceiling-drywall + unoccupied
  seat α) does not satisfy the |Lecture_2 err| ≤ 0.5 s envelope at
  500 Hz without regressing Meeting_1 / Meeting_2 by > +0.10 s.
  Single-coefficient bracketing is insufficient to close the Lecture_2
  residual; v0.9 considers the broader F4a per-band sensitivity sweep
  + coupled-space modelling.
- ADR 0014 References gains one cross-link line forward to ADR 0015
  (parallel to the v0.7 cross-link pattern on ADR 0012 / 0013).
- Schema unchanged: `__schema_version__` stays `"0.1-draft"`.
- `MaterialLabel` enum unchanged (9 entries).
- `MaterialAbsorption{,Bands}` byte-equal to v0.7.
- `_FURNITURE_BY_ROOM` and `_PIECE_EQUIVALENT_ABSORPTION_*` byte-equal to
  v0.7.

## Reverse-trigger / ratification reverse-if

A v0.9+ release **may ratify** a variant as a new default iff **all** the
following hold:

1. The variant closes Lecture_2 |err| ≤ 0.5 s at 500 Hz (Sabine).
2. The variant does not regress {Lecture_1, Meeting_1, Meeting_2,
   Office_1, Office_2} by more than +0.10 s at 500 Hz (Sabine) compared
   to the V0 baseline.
3. **Independent evidence** (lab visit, author email, textbook citation
   beyond Beranek 2004 / Vorländer 2020 §11) confirms the variant
   coefficient or material assignment.

If any of (1)..(3) is missing, the variant remains a sensitivity
data-point and v0.9 picks an alternative path (e.g., F4a per-band sweep
or coupled-space predictor). The v0.8 verdict — null per §Consequences —
already blocks ratification on (1) and (2) without needing (3).

## References

- Eaton, J., Gaubitch, N. D., Moore, A. H., & Naylor, P. A. (2016).
  *Estimation of room acoustic parameters: The ACE Challenge.* IEEE/ACM
  TASLP 24(10), 1681–1693. DOI: 10.1109/TASLP.2016.2577502 (institutional
  access).
  - **§II-C "Rooms" (p.1683)**: per-room furniture counts +
    Building_Lobby coupled-space caveat (cited via ADR 0013 + ADR 0014).
- Vorländer, M. (2020). *Auralization: Fundamentals of Acoustics,
  Modelling, Simulation, Algorithms and Acoustic Virtual Reality* (2nd
  ed.). Springer.
  - **§4.2 "Reverberation time"**: Sabine / Eyring assumptions.
  - **§4.4 "Coupled rooms"**: physics ruled out for v0.8 (ADR 0014 (b)).
  - **§11 / Appendix A**: per-piece equivalent absorption rows used by
    `_PIECE_EQUIVALENT_ABSORPTION_*` (cited via ADR 0013).
- Beranek, L. L. (2004). *Concert Halls and Opera Houses: Music,
  Acoustics, and Architecture* (2nd ed.). Springer.
  - **Ch.3 Table 3.1**: unoccupied vs occupied lecture-seat α profiles
    (V2 unoccupied profile = `α₅₀₀ = 0.20` representative; bracket
    midpoint of the Beranek "unoccupied lecture seats" 0.18..0.22 row
    range).
- ADR 0008, 0009, 0010, 0011, 0012, 0013, 0014.
- D14, D15, D16, D17, D18.
- v0.6 perf doc — `docs/perf_verification_e2e_2026-05-08.md` (preserved
  byte-identical at v0.8.0; the empirical evidence row for the −0.908 s
  Lecture_2 500 Hz residual that v0.8 brackets).
- v0.8 perf doc — `docs/perf_verification_lecture2_bracket_2026-05-09.md`
  (NEW; auto-emitted; deterministic).
- Project memory `project_taslp_2016_content.md` (TASLP §II-C content map;
  furniture counts + Building_Lobby coupled-space caveat).
