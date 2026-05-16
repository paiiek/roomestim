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

## §Status-update-2026-05-16 (v0.14.0) — Conference ISM ratio recorded

**Closure-status update (D22 hybrid pattern + D28-P1 factual band)**:
v0.14.0 Item B executor pass landed the OQ-15 ISM library
(`roomestim/reconstruct/image_source.py` NEW per ADR 0028 §Decision
sub-item 2) and computed the conference SoundCam-substitute
(6.7×3.3×2.7; 3 drywall + 1 glass + carpet + acoustic-tile ceiling)
ISM-vs-Sabine ratio. This block records the factual ratio as evidence
supporting the Item C reclassification (which lands STRUCTURALLY in
ADR 0028 §Decision sub-item 3, NOT in this ADR 0021 — signature
reframing is STRUCTURAL per D28-P1 applicability table; this
§Status-update records ratio data only per D28-P1 factual band).

- **Conference ISM RT60**: 2.2693 s (`tests/test_image_source.py::test_a11_soundcam_conference_ism_ratio_characterises`
  line 320; Allen & Berkley 1979 ISM + Lehmann-Johansson 2008 §III
  placement bookkeeping; `max_order=50`).
- **Conference Sabine RT60**: 0.4490 s (unchanged from v0.12 + ADR 0021
  §2.4 executor decision-point output; library BYTE-EQUAL).
- **Conference Eyring RT60**: 0.3981 s (unchanged from v0.12).
- **Conference ISM/Sabine ratio**: **5.0537** (= 2.2693 / 0.4490; well
  above the 1.15 threshold).
- **Conference ISM/Eyring ratio**: **5.7002** (= 2.2693 / 0.3981).
- **Conference Sabine/Eyring ratio**: **1.1279** (BYTE-EQUAL to v0.12
  AMBIGUOUS-zone value; library unchanged).
- **ACE Office_1 ISM/Sabine ratio** (second-room confirmation per the
  D26 forbidden-indefinite-deferral clause): **2.0059** (= 1.7324 /
  0.8637; `tests/test_image_source.py::test_ace_office_1_ism_ratio_characterises`
  line 441). Office_1 is NOT a glass-heavy room (carpet + 4 painted
  walls + drywall ceiling per `ACE_ROOM_GEOMETRY`); the > 1.15 ratio
  indicates the ISM-vs-Sabine departure is NOT specific to glass — it
  is a general pure-specular-vs-diffuse-field characterisation effect
  (Lehmann & Johansson 2008 §IV finding).
- **Convergence caveat (added 2026-05-16 per code-reviewer pass
  MAJOR finding #1)**: the conference + Office_1 ISM ratios above are
  computed at `max_order=50` (planner-locked default + per-room test
  parameter). They are **NOT numerically converged at `max_order=50`**.
  Code-reviewer sweep at `max_order=100`: conference ISM=2.5774 s →
  ISM/Sabine = **5.7400** (+13.6 % vs the 5.0537 above); Office_1
  ISM=2.0376 s → ISM/Sabine = **2.3593** (+17.6 % vs the 2.0059
  above). Branch C-i (ratio > 1.15) fires under BOTH truncations for
  BOTH rooms, so the Item C structural reframe (lands in ADR 0028
  §Decision sub-item 3) and the D26 ≥ 2-rooms gate are **robust to
  convergence**; the absolute ratio values are NOT load-bearing for
  the v0.14 decision and are recorded for characterisation only.
  v0.15+ may revise quantitative ratios under a successor
  §Status-update if higher-order convergence becomes load-bearing
  for a future predictor-default decision. Cross-ref: ADR 0028
  §Decision sub-item 2 "Convergence caveat" + code-review memo
  `.omc/plans/v0.14-code-review-2026-05-16.md` §2.1.

**Item C branch fired**: **C-i** (ratio > 1.15) per plan §0.0 row
"Item C". Signature reframe to
`sabine_shoebox_approximation_for_glass_heavy_room` lands in ADR 0028
§Decision sub-item 3 (STRUCTURAL change per D28-P1 applicability
table). This ADR 0021 §Status-update is the parallel factual record;
ADR 0028 §Decision is the structural reframe authority.

**`_CONFERENCE_EXPECTED["disagreement_classification"]` field in
`tests/test_a11_soundcam_rt60.py`**: NOT updated at v0.14.0 Item B + C
executor pass. The existing classification value `"ambiguous"` reflects
the **Sabine/Eyring ratio** classification (still 1.128 → AMBIGUOUS zone
per the planner-locked thresholds in §Decision above; library is
BYTE-EQUAL). The v0.12 existing test
`test_a11_soundcam_conference_disagreement_classification` cross-checks
via Sabine/Eyring ratio, not ISM/Sabine; that test stays BYTE-EQUAL.
The Item C ISM-driven branch driver lands as a new test
`test_conference_ism_item_c_branch_driver` in
`tests/test_image_source.py` line 739 — additive, not replacement.
This separation keeps Eyring-based classification and ISM-based
reclassification as parallel data streams per plan §0.4 STOP rule #11.

**No library code change** at v0.14.0 in
`roomestim/reconstruct/materials.py` or any predictor call site —
Sabine + Eyring rows BYTE-EQUAL to v0.12 / v0.13. The ISM library is a
NEW PARALLEL PREDICTOR per ADR 0028 §Decision sub-item 2; Item D
predictor-default switch DEFERRED to v0.15+ per D26 + ADR 0028
§Reverse-criterion item 2.

**Cross-references**: D22 (hybrid pattern), D26 (predictor-adoption
deferral cadence — Item B (e+) Office_1 ratio + conference ratio both
> 1.15 → v0.15+ MUST land Item D), D27 (cycle 3 hard wall closed at
v0.14.0 under path γ via ADR 0028), D28-P1 (factual-band
§Status-update + STRUCTURAL-reframe-via-§Decision applicability table),
D34 (v0.14 ADR + OQ re-numbering audit-trail), D35 (v0.14.0 hard-wall
closure under path γ recording decision), OQ-13b (CONDITIONALLY closed
at v0.14 — branch C-i fired; signature reframe lands in ADR 0028
§Decision sub-item 3), OQ-15 (CLOSED at v0.14 — ISM library landed),
**ADR 0028 NEW** (`docs/adr/0028-hardwall-closure-and-ism-adoption.md`
§Decision sub-item 3 + §References — composite Item A + B + C ADR),
`tests/test_image_source.py::test_a11_soundcam_conference_ism_ratio_characterises`
+ `::test_ace_office_1_ism_ratio_characterises` +
`::test_conference_ism_item_c_branch_driver`,
`.omc/plans/v0.14-design.md` §0.0 row "Item C" + §2.B + §1.2 row 12,
`RELEASE_NOTES_v0.14.0.md`.
