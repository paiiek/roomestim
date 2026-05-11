# roomestim v0.13.0 — Release Notes

**Date**: 2026-05-12 (drafted) / 2026-05-12 (shipped)
**Predecessor**: v0.12.0 (`d3c6cc2`) — conference Sabine-shoebox residual characterised (ADR 0021; ambiguous ratio 1.128) + Vorländer citation re-deferred (ADR 0019 §Status-update-2026-05-12) + lint scope expansion (ADR 0020 §Status-update-2026-05-12) + D26/D27.
**Release nature**: SemVer minor — SHORT-mode 4-item admin bundle (Vorländer SECOND re-deferral + D28 NEW + mypy strict baseline enforced + lint scope expansion-2). Library byte-equal — no predictor / CLI / adapter logic changes. Schema marker UNCHANGED (`__schema_version__` stays `"0.1-draft"`).

## What v0.13.0 shipped

v0.13.0 closes the 4-item SHORT-mode admin scope locked by `.omc/plans/v0.13-design.md` §0.1:

1. **Vorländer α₅₀₀ verbatim citation SECOND re-deferral** (ADR 0019 §Status-update-2026-05-12-2 (v0.13.0); Item A).
   - **Closure-attempt outcome**: Vorländer 2020 *Auralization* (2nd ed., Springer) §11 / Appx A verbatim page + row + panel-thickness column **STILL PENDING** at v0.13 — no library, ILL, or NRC datasheet path materialised during the v0.13 cycle.
   - **Path α locked (planner-locked)**: path α (verbatim Vorländer 2020 acquisition) remains default. Path β (PRIMARY-source switch to Bies & Hansen 2018 §A) REJECTED at v0.13 design time — no in-repo verbatim α₅₀₀ from Bies & Hansen 2018 §A exists.
   - **External-acquisition-channel exhaustion record (HONEST-FALLBACK)**: SNU library ILL, OA mirrors, publisher OA page for Bies & Hansen 2018 §A were NOT investigated at v0.13 executor-time. v0.14 hard-wall closure MUST exhaust these channels before invoking path-β.
   - **α₅₀₀ = 0.85 BYTE-EQUAL to v0.11 / v0.12**; lab A11 PASS-gate UNCHANGED (rel_err = +2.40 %).
   - **D27 cadence**: v0.13 = SECOND-AND-LAST permitted re-deferral. **v0.14 = HARD WALL** — three closure paths previewed: (i) verbatim Vorländer 2020 acquired; (ii) successor ADR 0022 switches PRIMARY to Bies & Hansen 2018 §A verbatim; (iii) successor ADR 0022 switches PRIMARY to NRC manufacturer datasheet.

2. **D28 NEW — audit-trail process meta-rules P1 + P2** (Item B).
   - D28-P1: the D22 hybrid pattern (in-place §Decision edit + appended §Status-update block) is the GENERAL pattern for factual changes to all accepted ADRs — not a special-case for ADR 0019. All future executor §Status-update blocks follow D28-P1.
   - D28-P2: STOP-rule-10 (no fabricated quotes) is operationalised as an executor pre-flight check: before writing any numeric value or quoted text in an ADR or §Status-update block, grep the repo for the source string; if absent, flag as pending (D22 honesty-first) and do NOT write a value.

3. **mypy `--strict` baseline enforced (OQ-13i CLOSED)** (Item C).
   - `roomestim/adapters/ace_challenge.py:554-556` narrowing applied via `_geom_float` helper function, resolving 3 pre-existing `float(object)` cast errors.
   - `mypy --strict roomestim/` returns "Success: no issues found in 29 source files".
   - CI step renamed `Type-check (mypy)` → `Type check (mypy --strict)` (`.github/workflows/ci.yml`).
   - Default-lane regression guard test `tests/test_mypy_strict_baseline.py::test_mypy_strict_clean` shipped.

4. **lint-2 scope expansion-2** (reverse-criterion firing on OQ-13h; ADR 0020 §Status-update-2026-05-13; Item D).
   - Two new file families added to `scripts/lint_tense.py::_scoped_files()`: remaining `docs/*.md` files (non-`adr/`, non-`perf_verification_*`, non-`architecture.md`) + `.omc/research/*.md`.
   - **v0.13 first-run flag count**: 1 file flagged (`docs/weekly_progress_report_2026-05-11.md:204`); 1 `# noqa: lint-tense` annotation applied (block-count threshold NOT exceeded; well under §0.4 STOP rule #6).
   - Pattern + block-exclusion (D22) + per-line escape semantics UNCHANGED. `CURRENT_VERSION_RELEASE_NOTES` constant rotated from `RELEASE_NOTES_v0.12.0.md` → `RELEASE_NOTES_v0.13.0.md`.
   - NEW tests `test_lint_tense_scope_includes_expansion2_files` + `test_lint_tense_noqa_marker_weekly_progress_report` shipped.

## What stays the same

- `__schema_version__` stays `"0.1-draft"` (Stage-2 re-flip bound to A10b in-situ capture + ≥ 3 captures per ADR 0016 + D2; STOP rule #5 held).
- `MaterialLabel` enum stays at 10 entries (no FIBERGLASS_CEILING / TILE_FLOOR addition; OQ-14 unchanged; STOP rule #4 held).
- `MELAMINE_FOAM` row byte-equal (α₅₀₀ = 0.85; band tuple `(0.35, 0.65, 0.85, 0.92, 0.93, 0.92)`; STOP rules #5 + #7 held).
- All other 9 existing `MaterialLabel` entries + their `MaterialAbsorption{,Bands}` rows byte-equal.
- `roomestim/place/*`, `roomestim/cli.py`, `roomestim/adapters/*` (library logic), `roomestim/reconstruct/*` byte-equal. Only `ace_challenge.py:554-556` received narrowing (type annotation, not logic).
- Lab A11 PASS-gate byte-equal (rel_err = +2.40 %; sub-branch A; signature `RECOVERED_under_melamine_foam_enum`).
- Conference disagreement-record byte-equal; ADR 0018 byte-equal; ADR 0021 byte-equal.
- Cross-repo PR stays WITHDRAWN (D11; ≥ 3 captures requirement unmet).
- `proto/*` byte-equal; predecessor RELEASE_NOTES byte-equal (v0.1.1 through v0.12.0).

## Default-lane test count [128 → 131]

| Stage | Default-lane (`pytest -m "not lab"`) | Full collection | Delta |
| --- | --- | --- | --- |
| v0.12.0 baseline (`d3c6cc2`) | 128 | 129 | (anchor) |
| v0.13.0 target | **131** | 132 | **+3** |

Net +3 additions (LOCKED per Delta 5):

1. `tests/test_mypy_strict_baseline.py::test_mypy_strict_clean` — mypy `--strict` regression guard (Item C).
2. `tests/test_lint_tense.py::test_lint_tense_scope_includes_v0_13_expansion` — lint scope expansion-2 guard for the v0.13-added `docs/*.md` remainder + `.omc/research/*.md` families (Item D).
3. `tests/test_lint_tense.py::test_lint_tense_v0_13_release_notes_exclusion_rotated` — `CURRENT_VERSION_RELEASE_NOTES` rotation guard ensuring the v0.12.0 → v0.13.0 asymmetry-rotation per ADR 0020 §Reverse-criterion item 4 (Item D).

## ADR list

| ADR | Status | NEW/AMENDED | Purpose |
| --- | --- | --- | --- |
| 0019 | Amended via §Status-update-2026-05-12-2 (v0.13.0) | AMENDED (D22 hybrid + D28-P1; factual: citation closure-attempt outcome) | Verbatim Vorländer SECOND re-deferral; path α locked; v0.14 hard wall previewed. |
| 0020 | Amended via §Status-update-2026-05-13 | AMENDED (D22 hybrid + D28-P1; operational refinement: scope expansion-2) | Lint scope expanded to remaining docs + research; 1 noqa applied. |
| 0021 | byte-equal | unchanged | Conference glass-heavy residual study (AMBIGUOUS classification). |
| 0001..0018 | byte-equal | unchanged | STOP rule #11 held. |

No new ADR at v0.13 (§0.4 STOP rule #9 held).

## What stays deferred

- **OQ-15 ISM bundle** → v0.14 DELIBERATE (explicitly deferred per main-agent tiebreaker Critic-lean; v0.13 admin bundle does not touch `roomestim/predict/*`).
- **OQ-13a Vorländer α₅₀₀ verbatim citation** → v0.14 D27 HARD WALL (SECOND-AND-LAST re-deferral consumed at v0.13).
- **OQ-13b conference disagreement-record** → v0.14 ISM comparator upgrade (classification remains AMBIGUOUS).
- **OQ-16 path-α-vs-β lock** → v0.14 hard-wall closure (NEW at v0.13-design).
- **OQ-12a A10b in-situ capture** — user-volunteer-only; not planner-schedulable.
- **OQ-14 FIBERGLASS_CEILING + TILE_FLOOR** — no captured room requires them at v0.13.

## Tag-local-only

Local tag `v0.13.0` per D11 (tag-local-only policy unchanged). NOT pushed to remote.

## References

- Predecessor commit: `d3c6cc2` (v0.12.0 ship).
- Design plan: `.omc/plans/v0.13-design.md` (820 lines; SHORT-mode 4-item admin bundle).
- ADR 0019 §Status-update-2026-05-12-2 (v0.13.0): `docs/adr/0019-melamine-foam-enum-addition.md` (SECOND re-deferral; path α/β evidence; D27 cadence accounting).
- ADR 0020 §Status-update-2026-05-13: `docs/adr/0020-ci-lint-tense-policy.md` (scope expansion-2 record).
- D28 NEW: `.omc/plans/decisions.md`.
- OQ-13a / OQ-13h / OQ-13i / OQ-16 annotations: `.omc/plans/open-questions.md` v0.13-design ship-time section.
- v0.12.0 release notes: `RELEASE_NOTES_v0.12.0.md` (byte-equal under v0.13).
