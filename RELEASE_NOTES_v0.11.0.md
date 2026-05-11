# roomestim v0.11.0 — Release Notes

**Date**: 2026-05-11 (drafted) / 2026-05-11 (shipped)
**Predecessor**: v0.10.1 (`957c531`) — factual-integrity patch; ADR 0018 fabricated-quote redaction; D22 hybrid pattern; OQ-13f/g/h/i recorded; OQ-12a status-update marker; OQ-13a amendment.
**Release nature**: SemVer minor — new library feature (MELAMINE_FOAM enum), new CI lint, new tests, new ADRs (0019 + 0020), new protocol DOC. Library-additive only — no predictor / CLI / adapter logic changes. Schema marker UNCHANGED (`__schema_version__` stays `"0.1-draft"`).

## What v0.11.0 ships

v0.11.0 closes the 4-item hybrid scope that v0.10.1 explicitly DEFERRED into v0.11 (per `RELEASE_NOTES_v0.10.1.md` §What-stays-deferred):

1. **MELAMINE_FOAM enum addition** (resolves OQ-13a; ADR 0019 NEW).
   - `MaterialLabel.MELAMINE_FOAM = "melamine_foam"` (enum now 10 entries, was 9).
   - `MaterialAbsorption[MELAMINE_FOAM] = 0.85` (α₅₀₀; planner-locked envelope per Vorländer 2020 §11 / Appx A "melamine foam panel" / "acoustic foam absorber"; verbatim citation pending follow-up Vorländer lookup — flagged honestly in ADR 0019 §References).
   - `MaterialAbsorptionBands[MELAMINE_FOAM] = (0.35, 0.65, 0.85, 0.92, 0.93, 0.92)` for (125, 250, 500, 1000, 2000, 4000) Hz.
   - Lab fixture (`tests/fixtures/soundcam_synthesized/lab/dims.yaml`) wall material flips `misc_soft` → `melamine_foam`. `tests/test_a11_soundcam_rt60.py::_predict_lab()` switches accordingly.

2. **Lab + conference band tightening** (resolves OQ-13f).
   - **§2.4 executor decision-point outcome**: lab Sabine 500 Hz under MELAMINE_FOAM walls = **0.161795 s** vs measured 0.158 s; `rel_err = +2.40 %`. Sub-branch A (PASS-gate recovered) lands. The full record is in ADR 0019 §"§2.4 executor decision-point record (v0.11.0)".
   - `_LAB_EXPECTED` band replaced with PASS-gate values (`rel_err_min = -0.20`, `rel_err_max = +0.20`, `disagreement_signature = "RECOVERED_under_melamine_foam_enum"`).
   - Lab umbrella test renamed `test_a11_soundcam_lab_disagreement_record` → `test_a11_soundcam_lab_band_record`; new companion `test_a11_soundcam_lab_pass_gate_recovered` added.
   - Conference: band byte-equal; redundant structural-sign assertion `assert rel_err < -0.10` added (belt-and-braces guard).
   - Lab structural-sign assertion `assert rel_err < 0.20` added.

3. **README-tense CI lint** (resolves OQ-13h; ADR 0020 NEW; D24 NEW).
   - `scripts/lint_tense.py` NEW (standalone Python; ~110 lines including docstring).
   - `.github/workflows/ci.yml` gains step `Lint (tense)` between `Type-check (mypy)` and `Test (pytest, skip lab fixtures)`.
   - Scope: `tests/fixtures/**/README.md`, `docs/adr/*.md`, `RELEASE_NOTES_v*.md` (excluding current-version `RELEASE_NOTES_v0.11.0.md` — current-version release notes are inherently in present tense; documented asymmetry).
   - Pattern: word-bounded `\bwe ship\b | \bship in v0\.[0-9]+\b`.
   - Block exclusion: lines inside `## §Status-update-` / `## §Honesty-correction-` (D22 audit-trail-discipline pattern).
   - Per-line escape: `# noqa: lint-tense`.
   - Live-repo first run flagged **0 files** (well under v0.11 §0.4 STOP rule #7 threshold of > 3).
   - `tests/test_lint_tense.py` NEW (1 default-lane test with 5 internal branches: live-repo + 4 seeded-fixture cases mitigating v0.11 §5.3 pre-mortem).

4. **In-situ A10b protocol DOC** (status-update on OQ-12a; D25 NEW codifies doc-ahead-of-impl pattern).
   - `docs/protocol_a10b_insitu_capture.md` NEW (minimal stub; 90 lines).
   - Sections: §1 Scope, §2 Corner GT acceptance criteria, §3 Scan device list, §4 Minimum scan completeness, §5 ABORT criteria, §6 Cross-references.
   - **protocol-only; no capture commitment at v0.11**. A10b actual capture remains user-volunteer-only.

## What stays the same

- `__schema_version__` stays `"0.1-draft"` (Stage-2 re-flip is bound to A10b in-situ capture + ≥ 3 captures per ADR 0016 §Reverse-criterion + D2; v0.11 has only 2 substitute rooms).
- `MISC_SOFT` enum + `MaterialAbsorption[MISC_SOFT] = 0.40` + `MaterialAbsorptionBands[MISC_SOFT] = (0.20, 0.30, 0.40, 0.50, 0.60, 0.65)` byte-equal (ADR 0011 honesty contract preserved).
- All other 8 existing `MaterialLabel` entries + their `MaterialAbsorption{,Bands}` rows byte-equal.
- `_FURNITURE_BY_ROOM` sum = 276; `_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2['lecture_seat']` = 0.45; `roomestim/place/*`, `roomestim/cli.py`, `roomestim/adapters/*` (except no MELAMINE_FOAM use yet) byte-equal.
- ADR 0001..0018 byte-equal (ADR 0018 §Status-update-2026-05-10b block from v0.10.1 preserved as-is; v0.11 does NOT re-edit ADR 0018).
- Conference disagreement-record band byte-equal (only the redundant structural-sign assertion line added).
- ACE corpus A11 (gated E2E) byte-equal — v0.11 MELAMINE_FOAM addition does NOT regress ACE evidence.
- Cross-repo PR stays WITHDRAWN (D11 + ADR 0018 §References tightening; ≥ 3 captures requirement unmet at v0.11).
- `proto/*` byte-equal; perf docs byte-equal; cross-repo PR research notes byte-equal; predecessor RELEASE_NOTES byte-equal; existing plan files byte-equal.

## Default-lane test count

**Baseline (v0.10.1)**: 119 default-lane tests (pytest -m "not lab").
**v0.11.0**: **124** default-lane tests (+5 net additions).

Per-section delta:
- `tests/test_a11_soundcam_rt60.py`: 2 → 3 (renamed umbrella + new `test_a11_soundcam_lab_pass_gate_recovered`).
- `tests/test_misc_soft_furniture_budget.py`: 16 → 17 (+1 `test_melamine_foam_a500_in_expected_range`).
- `tests/test_room_acoustics_octave.py`: 16 → 18 (+2 `test_melamine_foam_band_a500_matches_legacy_scalar` + `test_melamine_foam_bands_monotonic_in_500hz_region`).
- `tests/test_lint_tense.py`: 0 → 1 (NEW file; `test_no_present_tense_version_specific_framing`).

(The v0.11 design plan §0.2.B cited 116→121 based on a stale pre-flight baseline; actual baseline at HEAD `957c531` is 119, so v0.11 target lands at 124. The "+5 net additions" contract is honoured.)

## Lab regime

Lab moved from v0.10 disagreement-record (rel_err ≈ +60 %, signature `default_enum_underrepresents_treated_room_absorption`) to v0.11 PASS-gate-recovered (rel_err = +2.40 %, signature `RECOVERED_under_melamine_foam_enum`). The §2.4 executor decision-point procedure and its recorded outcome (`predicted = 0.161795 s`, `rel_err = +2.40 %`, sub-branch A) are documented in ADR 0019.

## ADR list

- **ADR 0019 NEW** — MELAMINE_FOAM enum extension + lab fixture flip + §2.4 executor decision-point record + Vorländer 2020 §11 / Appx A coefficient sourcing (citation-pending honest marker).
- **ADR 0020 NEW** — CI tense lint policy (standalone script + GH Actions step + block-exclusion per D22 + per-line `# noqa: lint-tense` escape + current-version-RN asymmetry).
- ADR 0001..0018 byte-equal (no v0.11 §Status-update on ADR 0018; closure recorded in ADR 0019 §References).

## D-decisions

- **D23 NEW** — v0.11.0 hybrid scope ships the 4-item closure set.
- **D24 NEW** — CI tense lint policy codification.
- **D25 NEW** — Doc-ahead-of-implementation pattern (v0.11 in-situ protocol DOC precedent).
- D1..D22 byte-equal.

## What stays deferred

- **v0.12+** — FIBERGLASS_CEILING + TILE_FLOOR enum additions (NEW **OQ-14**; rationale: lab returned to PASS-gate under MELAMINE_FOAM alone, no critical-path need for the other two enums at v0.11).
- **v0.12+** — Mypy strict project commitment (OQ-13i UNCHANGED).
- **v0.12+** — Glass-heavy room residual study (OQ-13b UNCHANGED).
- **v0.12+** — Cross-repo PR re-submission (OQ-13c UNCHANGED).
- **v0.12+** — Live-mesh extraction (OQ-13e UNCHANGED).
- **user-volunteer-only** — A10b in-situ ACTUAL capture (OQ-12a unchanged on capture commitment; protocol DOC only at v0.11 per D25).
- **v0.11.x or v0.12** — verbatim Vorländer 2020 §11 / Appx A page + row + panel-thickness column citation for MELAMINE_FOAM α₅₀₀ (currently planner-envelope-flagged per ADR 0019 §References).

## Tag policy

Local tag `v0.11.0` per D11 (tag-local-only). NOT pushed to remote.

## References

- v0.11.0 design plan: `.omc/plans/v0.11-design.md` (1123 lines; scope-locked at 2026-05-11).
- v0.10.1 commit: `957c531`.
- v0.10.1 release notes: `RELEASE_NOTES_v0.10.1.md` (byte-equal under v0.11).
- ADR 0016 — Stage-2 schema flip predicate (byte-equal; binding for the schema marker `"0.1-draft"`).
- ADR 0018 — substitute-disagreement record at v0.10 (byte-equal; v0.11 closes the MELAMINE_FOAM half of §Reverse-criterion).
- ADR 0019 NEW — MELAMINE_FOAM enum addition + §2.4 executor decision-point record.
- ADR 0020 NEW — CI tense lint policy.
- D2 (≥ 3 captures requirement for Stage-2 lock; unchanged).
- D11 (cross-repo PR tag-local-only).
- D22 (audit-trail-discipline pattern from v0.10.1).
- D23 NEW (v0.11.0 hybrid scope).
- D24 NEW (CI lint policy).
- D25 NEW (doc-ahead-of-impl pattern).
- OQ-13a (resolved at v0.11; MELAMINE_FOAM landed).
- OQ-13f (resolved at v0.11; sub-branch A PASS-gate).
- OQ-13h (resolved at v0.11; CI lint shipped).
- OQ-12a (status-update at v0.11; protocol DOC landed; capture commitment unchanged).
- OQ-14 NEW (FIBERGLASS_CEILING + TILE_FLOOR deferred to v0.12+).
- Vorländer, M. (2020). *Auralization*, §11 / Appendix A. Springer — primary coefficient source for MELAMINE_FOAM (citation status: planner-locked envelope per ADR 0019 §References pending verbatim follow-up).
- arXiv:2311.03517v2 (NeurIPS 2024 D&B, SoundCam) — Appendix A.1 + Table I + Table 7 — paper-retrieved RT60 (lab 0.158 s, byte-equal under v0.11).
