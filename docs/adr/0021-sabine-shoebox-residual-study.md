# ADR 0021 — Conference glass-heavy Sabine-shoebox residual characterising study

- **Status**: Accepted (v0.12.0)
- **Date**: 2026-05-12
- **Cross-ref**: D9 (Eyring parallel predictor), D22 (audit-trail-discipline
  hybrid pattern), D26 NEW (predictor-adoption deferral policy: characterise
  first, decide second), D27 NEW (verbatim-pending closure cadence),
  ADR 0009 (Eyring parallel predictor; runtime invariant
  `eyring ≤ sabine + 1e-9`), ADR 0016 (Stage-2 schema flip; §Reverse-criterion
  binds schema flip to A10b in-situ), ADR 0018 (substitute-disagreement
  record; conference signature `sabine_shoebox_underestimates_glass_wall_specular`),
  ADR 0019 (MELAMINE_FOAM enum; v0.11 precedent for honesty-first coefficient
  sourcing), ADR 0020 (CI tense lint; v0.12 §Status-update for scope
  expansion lands in parallel), OQ-13b (status-update at v0.12; AMBIGUOUS
  classification per §Decision below), OQ-15 NEW (predictor-adoption
  decision deferred to v0.13+ per D26 policy),
  `tests/test_a11_soundcam_rt60.py`, `roomestim/reconstruct/materials.py`.

## Decision

The v0.10/v0.11 conference disagreement-record (paper-faithful Sabine
prediction 0.449 s vs measured 0.581 s; rel_err -22.7 %; signature
`sabine_shoebox_underestimates_glass_wall_specular`) is **characterised
at v0.12** using the in-repo Eyring parallel predictor (D9 / ADR 0009)
as the disagreement-study comparator. The §2.4 executor decision-point
landed:

| Metric | Value |
| --- | --- |
| Conference V (L=6.7 × W=3.3 × H=2.7 m) | **59.697 m³** |
| Conference S_total (4 walls + floor + ceiling) | **98.220 m²** |
| Mean absorption ᾱ (paper-faithful map; 500 Hz) | **0.2179** |
| Sabine 500 Hz predicted | **0.449030 s** |
| Eyring 500 Hz predicted (in-repo D9 predictor) | **0.398101 s** |
| `sabine_eyring_ratio = sabine_predicted / eyring_predicted` | **1.128** |
| Classification per §Decision thresholds (1.15 / 1.10) | **AMBIGUOUS** (1.10 ≤ ratio ≤ 1.15) |
| Sub-branch selected | **Ambiguous — characterising-only; signature UNCHANGED at v0.12** |

Per the planner-locked classification thresholds:

- `ratio > 1.15` → Sabine-approximation effect for glass-heavy room.
- `ratio < 1.10` → coefficient-sourcing issue (glass per-band α likely
  understates).
- `1.10 ≤ ratio ≤ 1.15` → **AMBIGUOUS**; ratio is too close to the
  low-absorption Taylor-limit `-ln(1-x) ≈ x` to discriminate between
  Sabine-approximation and coefficient-sourcing; mirror-image-source or
  ray-tracing comparator required at v0.13+ under OQ-15.

**Threshold derivation (planner-chosen heuristic, NOT physics-derived
at v0.12)**: the 1.10 / 1.15 endpoints are **planner-locked heuristic
bands**, committed to `.omc/plans/v0.12-design.md` §2.4 **before** the
executor §2.4 measurement was run (audit-trail: planner draft predates
ratio computation; the AMBIGUOUS verdict is therefore not
sandbagged-to-fit). The bands were chosen by inspection of the
low-absorption Taylor expansion `-ln(1-x) = x + x²/2 + O(x³)`, which
implies `sabine/eyring ≈ 1 + ᾱ/2` at first order — for the conference
ᾱ = 0.218 this predicts ratio ≈ 1.109, very close to the lower
endpoint. A higher-order or variance-weighted derivation (accounting
for per-surface α heterogeneity, not just mean) is outside the v0.12
envelope; **v0.13+ may revise the endpoints under a successor ADR**
after either (a) Eyring-Taylor residual analysis on the conference
ᾱ-distribution + S-distribution, or (b) mirror-image-source comparator
calibration on ≥ 2 rooms (per OQ-15 path). Until such revision, the
v0.12 thresholds are **heuristic-with-honesty-flag**, not
physics-derived. Reverse-criterion in §Reverse-criterion below
explicitly permits threshold revision under a successor ADR (NOT
silently inside ADR 0021).

v0.12 ships the characterising study WITHOUT switching the default
predictor (D26 policy: characterise first, decide second). The
conference disagreement-record signature
`sabine_shoebox_underestimates_glass_wall_specular` (ADR 0018) is
**preserved UNCHANGED at v0.12** — no structural amendment to ADR 0018
fires under the ambiguous classification (STOP rule #11 holds).
`_CONFERENCE_EXPECTED["disagreement_classification"] = "ambiguous"`.

## Drivers

1. **OQ-13b open at v0.11**: conference -22.7 % residual under
   paper-faithful materials never received a comparator-based
   characterisation. v0.11 ADR 0019 closed the lab branch (MELAMINE_FOAM
   PASS-gate); the conference branch needed its own characterising study.
2. **Minimum-leverage comparator**: Eyring (D9 / ADR 0009) is already
   in-repo with the runtime invariant `eyring ≤ sabine + 1e-9` enforced;
   ratio computation is one function call + one division. Mirror-image
   source or ray tracing would require new library code (~300-500 lines)
   outside the v0.12 envelope.
3. **D26 codification**: the v0.9-v0.10 honesty cycle taught that
   predictor changes without independent verification are silent
   claim-shifting (the same failure mode as the v0.9 "placeholder
   pretending to be measured" pattern). v0.12 records the
   characterising data; v0.13+ decides any predictor-default change
   under ADR 0022 if applicable.

## Alternatives considered

- **(a) Mirror-image-source / ray-tracing comparator.** Rejected for
  v0.12 — several-day library effort; breaks the v0.12 envelope.
  Deferred to v0.13+ under OQ-15.
- **(b) Multi-room residual study.** Rejected for v0.12 —
  minimum-leverage = conference only; ACE rooms carry confounders
  (TASLP-not-publishing-materials; coupled-space exclusion). Deferred
  to v0.13+ under OQ-15.
- **(c) Force binary classification despite ratio ∈ [1.10, 1.15].**
  Rejected — honesty-first: ambiguous ratio characterises as
  ambiguous (avoids v0.9 "placeholder pretending to be measured"
  failure mode).
- **(d) Conference fixture map revision.** Rejected for v0.12 — only
  fires if classification = coefficient_sourcing_issue; v0.12 result
  is AMBIGUOUS, so no fixture/coefficient changes ship.

## Why chosen

- **Honest characterisation over forced decision** — record empirical
  result + acknowledge Eyring-comparator limitation; v0.13+ comparator
  upgrade per OQ-15.
- **Minimum library cost** — Eyring already in-repo (D9 / ADR 0009);
  only new code is test-time arithmetic.
- **Audit-trail discipline** — both `sabine_predicted` and
  `eyring_predicted` recorded explicitly (mitigates §5.2 pre-mortem).

## Consequences

- **(+) OQ-13b receives an empirical characterisation** at v0.12 (was
  OPEN at v0.11; now annotated as AMBIGUOUS-with-data; remains `[ ]`
  status — closure deferred to v0.13+ comparator upgrade per OQ-15).
- **(+) Default-lane test count +2** (2 NEW companion tests for
  Eyring monotonicity guard + classification record).
- **(+) Conference signature `sabine_shoebox_underestimates_glass_wall_specular`
  preserved byte-equal** in ADR 0018 + `_CONFERENCE_EXPECTED`
  (no structural ADR 0018 amendment under ambiguous classification;
  STOP rule #11 holds).
- **(+) D26 NEW + D27 NEW** codify the characterise-first-decide-second
  pattern + verbatim-pending closure cadence for future cycles.
- **(−) Eyring as comparator is monotonicity-only** — the test asserts
  `ratio > 1.0` strict; the ambiguous-zone boundary 1.10/1.15 is too
  close to the Taylor-limit `-ln(1-x) ≈ x` for Eyring alone to be
  decisive. Mirror-image-source or ray-tracing is the v0.13+ upgrade
  path.
- **(−) Default predictor UNCHANGED at v0.12** — D26 explicitly forbids
  the predictor-default switch from landing in the same release as the
  characterising study. v0.13+ ADR 0022 carries that decision IF
  applicable (i.e., IF a future comparator upgrade resolves the
  ambiguity to `sabine_approximation_effect`).

## Reverse-criterion

- If Eyring ratio shifts by **> 0.05** at v0.13+ (e.g., a v0.13
  predictor refactor moves the conference ratio from 1.128 to 1.18 or
  1.08), re-run the §Decision computation and record the shift in a
  §Status-update on this ADR.
- If mirror-image-source comparator becomes feasible at v0.13+,
  **supersede ADR 0021 with ADR 0022** (the new comparator carries
  different classification thresholds; mirror-image is more
  discriminating than Eyring).
- If the conference fixture map is revised (e.g., glass per-band α
  retune at v0.13+ under OQ-15 coefficient-sourcing branch), re-run the
  §Decision computation under the new map; record results in a
  v0.13+ release.
- If a v0.13+ critic argues the 1.10/1.15 thresholds are too loose or
  too tight, revise thresholds under a successor ADR — NOT silently in
  this ADR.

## References

- ADR 0009 (D9), ADR 0016, ADR 0018 (byte-equal under v0.12 per STOP rule #11),
  ADR 0019, ADR 0020 — cross-refs above.
- D9, D22, D26 NEW, D27 NEW — `.omc/plans/decisions.md`.
- OQ-13b (status-update at v0.12; AMBIGUOUS classification; remains `[ ]`),
  OQ-15 NEW (predictor-adoption deferred to v0.13+) — `.omc/plans/open-questions.md`.
- arXiv:2311.03517v2 (NeurIPS 2024 D&B, SoundCam) — Table 7 broadband
  RT60 = 0.581 s (conference); §A.3 material treatment + Table I dims.
- `tests/test_a11_soundcam_rt60.py::test_a11_soundcam_conference_eyring_ratio_characterises`,
  `::test_a11_soundcam_conference_disagreement_classification` — NEW at v0.12.
- `roomestim/reconstruct/materials.py::eyring_rt60` — D9 / ADR 0009.
- `.omc/plans/v0.12-design.md` §2.3 / §2.4 — thresholds + §2.3.5 reverse-criterion.
