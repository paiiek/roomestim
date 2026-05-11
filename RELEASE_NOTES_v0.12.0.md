# roomestim v0.12.0 — Release Notes

**Date**: 2026-05-12 (drafted) / 2026-05-12 (shipped)
**Predecessor**: v0.11.0 (`eee3014`) — MELAMINE_FOAM enum (ADR 0019) + lab A11 PASS-gate recovered (rel_err +2.40 %) + CI tense-lint (ADR 0020) + in-situ A10b protocol DOC stub + D23/D24/D25.
**Release nature**: SemVer minor — new ADR 0021 (conference Sabine-shoebox residual characterising study) + new test surface (Eyring ratio classification on conference fixture) + lint-scope expansion (ADR 0020 §Status-update-2026-05-12) + 2 new D-decisions (D26 + D27) + 1 new OQ (OQ-15). Library-additive only — no predictor / CLI / adapter logic changes. Schema marker UNCHANGED (`__schema_version__` stays `"0.1-draft"`).

## What v0.12.0 ships

v0.12.0 closes the 4-item DELIBERATE-mode hybrid scope locked by `.omc/plans/v0.12-design.md` §0.1:

1. **Conference Sabine-shoebox residual characterising study** (status-update on OQ-13b; ADR 0021 NEW).
   - **Empirical result**: `sabine_eyring_ratio = sabine_predicted / eyring_predicted = 0.449030 / 0.398101 = 1.128` on the paper-faithful conference fixture (V = 59.697 m³; S_total = 98.220 m²; ᾱ = 0.218; 500 Hz mid-band).
   - **Classification**: **AMBIGUOUS** (ratio 1.128 falls inside the planner-locked [1.10, 1.15] ambiguous zone per ADR 0021 §Decision thresholds; ratio > 1.15 would have been Sabine-approximation effect; ratio < 1.10 would have been coefficient-sourcing issue).
   - **Comparator**: in-repo Eyring predictor (`roomestim/reconstruct/materials.py::eyring_rt60`; D9 / ADR 0009; runtime invariant `eyring ≤ sabine + 1e-9` enforced). Mirror-image-source method deferred to v0.13+ under OQ-15 NEW (envelope cost ~300-500 lines library code; outside v0.12 envelope).
   - **Conference signature UNCHANGED at v0.12**: `_CONFERENCE_EXPECTED["disagreement_signature"]` stays `sabine_shoebox_underestimates_glass_wall_specular` (ADR 0018 byte-equal under ambiguous classification per STOP rule #11). `_CONFERENCE_EXPECTED["disagreement_classification"]` NEW field stores `"ambiguous"` for v0.12 audit trail.
   - **Library defaults UNCHANGED**: `roomestim/reconstruct/materials.py::sabine_rt60` remains the default predictor; D26 NEW codifies the characterise-first-decide-second policy (predictor-default switch deferred to v0.13+ under ADR 0022 IF applicable).

2. **Vorländer α₅₀₀ verbatim citation closure attempt** (status-update on OQ-13a; ADR 0019 §Status-update-2026-05-12 NEW).
   - **Closure-attempt outcome**: Vorländer 2020 *Auralization* (2nd ed., Springer) §11 / Appx A verbatim page + row + panel-thickness column for the "melamine foam panel" entry **STILL PENDING** at v0.12 — executor did not have direct textbook access during the v0.12 cycle. Per D27 reverse-criterion (d), v0.12 records the closure-attempt outcome HONESTLY rather than fabricating a Vorländer citation; the pending flag is **re-deferred to v0.13+** under D27's one-permitted-re-deferral rule.
   - **Secondary-source corroboration landed**: SoundCam paper arXiv:2311.03517v2 §A.1 describes the lab as having "NRC 1.26 melamine foam walls" (Noise Reduction Coefficient 1.26 averaged across 250/500/1000/2000 Hz). The NRC 1.26 figure is consistent with the planner-locked envelope mid-value α₅₀₀ = 0.85 (a steep rise from ~0.35 at 125 Hz to ~0.92 plateau above 1 kHz, with the 500 Hz scalar at the inflection ≈ 0.85, is physically plausible for the implied band-average).
   - **α₅₀₀ value at v0.12**: **0.85 BYTE-EQUAL to v0.11** — `MaterialAbsorption[MaterialLabel.MELAMINE_FOAM] = 0.85`, `MaterialAbsorptionBands[MaterialLabel.MELAMINE_FOAM][2] = 0.85`. Lab A11 PASS-gate UNCHANGED (rel_err = +2.40 %; sub-branch A signature `RECOVERED_under_melamine_foam_enum`). STOP rules #5 + #7 did not fire. Envelope invariant [0.80, 0.95] preserved.
   - **NEW test** `test_melamine_foam_a500_v0_12_status_update_block_present` asserts the §Status-update-2026-05-12 block has landed in ADR 0019 + the envelope invariant remains intact.

3. **CI lint scope expansion** (reverse-criterion firing on OQ-13h; ADR 0020 §Status-update-2026-05-12 NEW).
   - Three new file families added to `scripts/lint_tense.py::_scoped_files()`: `docs/perf_verification_*.md` (7 files), `docs/architecture.md` (1 file), `README.md` (1 file).
   - **v0.12 first-run flag count**: **0 files flagged** on the expanded 5-family scope (well under v0.12 §0.4 STOP rule #6 threshold of > 5; 0 noqa markers required at v0.12 ship time).
   - Pattern + block-exclusion (D22) + per-line escape (`# noqa: lint-tense`) semantics UNCHANGED. Current-version `RELEASE_NOTES_v*.md` exclusion constant rotates from `RELEASE_NOTES_v0.11.0.md` → `RELEASE_NOTES_v0.12.0.md` (asymmetry documented at v0.11; rotation per v0.11 §Reverse-criterion item 4).
   - **NEW test** `test_lint_tense_scope_includes_expanded_files` asserts the 3 new families remain in scope (preemptive guard against silent scope contraction in future refactors).

4. **OQ-13f reverse-criterion re-examination** (bookkeeping; no test/library changes).
   - v0.12 re-examined the v0.11 OQ-13f resolution-candidate reverse-criterion "structural-sign assertion may become soft FAIL gate" after lab returned to PASS-gate.
   - **Outcome**: **NO firing**. Lab `assert rel_err < 0.20` (margin ≈ 0.18 inside +20 % boundary) and conference `assert rel_err < -0.10` (margin ≈ 0.13 inside -10 % boundary) are NOT soft FAIL gates because they were planned at v0.11 §2.4 sub-branch A as PASS-gate boundaries (not artefacts of disagreement-record regime), and the structural-sign assertion is the redundant guard, not the primary gate (`_LAB_EXPECTED.rel_err_min/max` is the primary band check).
   - Lab + conference test bodies UNCHANGED at v0.12. Re-examination outcome documented in `.omc/plans/open-questions.md` OQ-13f re-examination annotation.

## What stays the same

- `__schema_version__` stays `"0.1-draft"` (Stage-2 re-flip is bound to A10b in-situ capture + ≥ 3 captures per ADR 0016 §Reverse-criterion + D2; v0.12 has only 2 substitute rooms; OQ-12a capture commitment UNCHANGED).
- `MaterialLabel` enum stays at 10 entries (no FIBERGLASS_CEILING / TILE_FLOOR addition per OQ-14 unchanged; STOP rule #4 held).
- `MISC_SOFT` row byte-equal (α₅₀₀ = 0.40; band tuple `(0.20, 0.30, 0.40, 0.50, 0.60, 0.65)`).
- `MELAMINE_FOAM` row byte-equal (α₅₀₀ = 0.85; band tuple `(0.35, 0.65, 0.85, 0.92, 0.93, 0.92)`; STOP rules #5 + #7 held).
- All other 8 existing `MaterialLabel` entries + their `MaterialAbsorption{,Bands}` rows byte-equal.
- `_FURNITURE_BY_ROOM` sum = 276; `_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2['lecture_seat']` = 0.45; `roomestim/place/*`, `roomestim/cli.py`, `roomestim/adapters/*`, `roomestim/reconstruct/*` byte-equal. (Note: `roomestim/predict/` does NOT exist as a sub-package at v0.12 — the Eyring parallel predictor lives in `roomestim/reconstruct/materials.py::eyring_rt60` per D9 / ADR 0009. The OQ-15 v0.13+ resolution path (a) proposes adding `roomestim/predict/image_source.py` for a mirror-image-source comparator; that is v0.13+ scope.)
- **ADR 0018 byte-equal under v0.12** — the v0.10.1 §Status-update-2026-05-10b block is preserved byte-equal (STOP rule #11 held); conference signature reframe lands in NEW ADR 0021 (under ambiguous classification, signature is NOT reframed — but the STRUCTURAL principle that ADR 0018 would be amended ONLY via supersedure-or-NEW-ADR is preserved). `grep -c "Status-update-2026-05-10b" docs/adr/0018-...md` returns 2 (v0.10.1 preservation).
- ADR 0001..0017 byte-equal; ADR 0018 byte-equal; ADR 0019 gains §Status-update-2026-05-12 block (D22 hybrid; factual); ADR 0020 gains §Status-update-2026-05-12 block (D22 hybrid; operational refinement); ADR 0021 NEW.
- Conference disagreement-record band byte-equal (only the NEW field `disagreement_classification` added to `_CONFERENCE_EXPECTED`; existing 6 fields unchanged).
- ACE corpus A11 (gated E2E) byte-equal — v0.12 conference characterising study does NOT regress ACE evidence.
- Cross-repo PR stays WITHDRAWN (D11 + ADR 0018 §References tightening; ≥ 3 captures requirement unmet at v0.12).
- `proto/*` byte-equal; predecessor RELEASE_NOTES byte-equal (v0.1.1 through v0.11.0); existing plan files byte-equal (v0.1-design through v0.11-design + ralplan-iter1-resolutions + roomestim-v0-design).

## Default-lane test count [124 → 128]

| Stage | Default-lane (`pytest -m "not lab"`) | Full collection | Delta |
| --- | --- | --- | --- |
| v0.11.0 baseline (`eee3014`) | 124 | 125 | (anchor) |
| v0.12.0 target | **128** | 129 | **+4** |

Net +4 additions:

1. `tests/test_a11_soundcam_rt60.py::test_a11_soundcam_conference_eyring_ratio_characterises` — Eyring monotonicity guard + ratio recording (Item D / ADR 0021).
2. `tests/test_a11_soundcam_rt60.py::test_a11_soundcam_conference_disagreement_classification` — classification record per §2.4 thresholds (Item D / ADR 0021).
3. `tests/test_room_acoustics_octave.py::test_melamine_foam_a500_v0_12_status_update_block_present` — ADR 0019 §Status-update-2026-05-12 presence guard + envelope invariant check (Item C).
4. `tests/test_lint_tense.py::test_lint_tense_scope_includes_expanded_files` — lint scope expansion guard (Item K / ADR 0020 §Status-update).

**Item L** (OQ-13f re-examination) is bookkeeping; NO new test (per plan §2.5).

## ADR list

| ADR | Status | NEW/AMENDED | Purpose |
| --- | --- | --- | --- |
| 0021 | Accepted (v0.12.0) | **NEW** | Conference glass-heavy Sabine-shoebox residual characterising study. Classification AMBIGUOUS at v0.12 (Eyring/Sabine ratio 1.128 inside [1.10, 1.15] zone). |
| 0019 | Amended via §Status-update-2026-05-12 | AMENDED (D22 hybrid; factual: citation closure-attempt outcome) | Verbatim Vorländer pending re-deferred to v0.13+ under D27 reverse-criterion (d); secondary-source SoundCam NRC 1.26 corroboration recorded. |
| 0020 | Amended via §Status-update-2026-05-12 | AMENDED (D22 hybrid; operational refinement: scope expansion) | Lint scope expanded to perf docs + architecture + README; first-run 0 files flagged. |
| 0016/0017/0018 | byte-equal | unchanged | STOP rule #11 held; ADR 0018 §Status-update-2026-05-10b preserved byte-equal. |
| 0001..0015 | byte-equal | unchanged | — |

## What stays deferred

- **A10b actual in-situ capture** (OQ-12a) — user-volunteer-only; not planner-schedulable.
- **FIBERGLASS_CEILING + TILE_FLOOR enum additions** (OQ-14) — no captured room currently requires them at v0.12.
- **Cross-repo PR re-submission** (OQ-13c) — conference still in disagreement-record (ambiguous classification); WITHDRAWN.
- **Live-mesh extraction** (OQ-13e) — too large for v0.12 envelope (3-5 days; SoundCam PLY download access required).
- **Mypy strict project commitment** (OQ-13i) — deferred to v0.13+ unchanged.
- **AnyRIR watchlist** (OQ-12b) — passive; promotion criteria unmet.
- **ARKitScenes scoping** (OQ-12c) — disk + license still open.
- **Lecture_2 ratification** (OQ-11) — independent evidence still required.
- **Vorländer 2020 verbatim page/row/panel-thickness for MELAMINE_FOAM α₅₀₀** (OQ-13a) — re-deferred to v0.13+ under D27 reverse-criterion (d); this is the **FIRST** of at-most-two consecutive re-deferral cycles permitted by D27 (v0.13 = LAST permitted re-deferral; v0.14 = hard wall).
- **Predictor-adoption decision** (OQ-15 NEW) — per D26 policy: characterise first, decide second. v0.13+ comparator upgrade (mirror-image-source) is next-step path.

## Tag-local-only

Local tag `v0.12.0` per D11 (tag-local-only policy unchanged). NOT pushed to remote.

## References

- Predecessor commit: `eee3014` (v0.11.0 ship) + `4562b3e` (weekly progress report) + `8ab5d54` (README sync). v0.12 branches from `8ab5d54`.
- Design plan: `.omc/plans/v0.12-design.md` (1007 lines; DELIBERATE-mode 4-item bundle).
- ADR 0021 NEW: `docs/adr/0021-sabine-shoebox-residual-study.md`.
- ADR 0019 §Status-update-2026-05-12: `docs/adr/0019-melamine-foam-enum-addition.md` (closure-attempt outcome).
- ADR 0020 §Status-update-2026-05-12: `docs/adr/0020-ci-lint-tense-policy.md` (scope expansion record).
- D26 NEW + D27 NEW: `.omc/plans/decisions.md`.
- OQ-13a/b/f/h status-updates + OQ-15 NEW: `.omc/plans/open-questions.md` v0.12-design section.
- arXiv:2311.03517v2 (NeurIPS 2024 D&B, SoundCam) — §A.1 NRC 1.26 secondary-source corroboration for ADR 0019 §Status-update.
- Eyring predictor (D9 / ADR 0009): `roomestim/reconstruct/materials.py::eyring_rt60`.
- v0.11.0 weekly progress report: `docs/weekly_progress_report_2026-05-11.md` (byte-equal under v0.12).
- v0.11.0 release notes: `RELEASE_NOTES_v0.11.0.md` (byte-equal under v0.12).
