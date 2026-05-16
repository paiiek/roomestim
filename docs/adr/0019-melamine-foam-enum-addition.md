# ADR 0019 — MELAMINE_FOAM MaterialLabel extension + lab fixture material flip

- **Status**: Accepted (v0.11.0)
- **Date**: 2026-05-11
- **Cross-ref**: D3, D14, D22 (audit-trail-discipline pattern), D23, D24,
  D25, ADR 0011 (MISC_SOFT precedent), ADR 0016 (Stage-2 schema flip
  predicate; reverse-criterion firing), ADR 0018 (substitute-disagreement
  record at v0.10), ADR 0020 (CI tense lint), OQ-13a (resolved at v0.11),
  OQ-13f (resolved at v0.11), OQ-14 (NEW v0.11; FIBERGLASS_CEILING +
  TILE_FLOOR deferred to v0.12+), `roomestim/model.py`
  (`MaterialLabel`, `MaterialAbsorption`, `MaterialAbsorptionBands`),
  `tests/test_a11_soundcam_rt60.py`,
  `tests/test_misc_soft_furniture_budget.py`,
  `tests/test_room_acoustics_octave.py`,
  `tests/fixtures/soundcam_synthesized/lab/dims.yaml`.

## Decision

Extend the closed `MaterialLabel` enum (D3, ADR 0011) with one new entry
**`MELAMINE_FOAM`** (`"melamine_foam"`), and add the corresponding rows
to the absorption tables:

- `MaterialAbsorption[MaterialLabel.MELAMINE_FOAM] = 0.85` at 500 Hz mid-band.
- `MaterialAbsorptionBands[MaterialLabel.MELAMINE_FOAM] = (0.35, 0.65, 0.85, 0.92, 0.93, 0.92)`
  for (125, 250, 500, 1000, 2000, 4000) Hz.

Both rows are sourced from the **Vorländer 2020 *Auralization* §11 /
Appendix A** "melamine foam panel" / "acoustic foam absorber" entry,
class "porous absorber, 2-4 inch panel". The α₅₀₀ value 0.85 is taken
from the **planner-locked envelope** (0.80 ≤ α₅₀₀ ≤ 0.95) per the
OQ-13a amendment recorded in `.omc/plans/open-questions.md` and the
v0.11-design plan §0.1; the verbatim page + row + panel-thickness
column citation is recorded as **pending verbatim Vorländer lookup**
under §References below — honesty-first policy applies (D22) and the
coefficient invariant test `test_melamine_foam_a500_in_expected_range`
brackets the value to the envelope so any silent drift outside the
0.80-0.95 range trips the test.

The band-index-2 ↔ legacy-scalar invariant
(`MaterialAbsorptionBands[m][2] == MaterialAbsorption[m]`) is preserved
by construction and continues to be enforced by
`tests/test_room_acoustics_octave.py::test_band_a500_matches_legacy_scalar`
plus the new `test_melamine_foam_band_a500_matches_legacy_scalar` /
`test_melamine_foam_bands_monotonic_in_500hz_region` guards.

The lab SoundCam substitute fixture (`tests/fixtures/soundcam_synthesized/lab/dims.yaml`)
`material_rationale` block + `tests/test_a11_soundcam_rt60.py::_predict_lab()`
flip the lab wall material `MISC_SOFT` → **`MELAMINE_FOAM`**, matching
the paper-described NRC 1.26 melamine-foam treatment.

## Drivers

1. **ADR 0018 §Reverse-criterion** named MELAMINE_FOAM addition as the path back to A11 PASS-gate for treated rooms; v0.11 closes that path.
2. **OQ-13a amendment (v0.10.1)** locked Vorländer 2020 §11 / Appx A as PRIMARY source; v0.11 uses the planner-locked envelope mid-value (verbatim page citation pending follow-up — flagged in §References).
3. **Conference disagreement-record stays** byte-equal because the conference paper-faithful map has no foam; the conference residual is a Sabine-shoebox-approximation effect (OQ-13b), orthogonal to this enum.
4. **§2.4 executor outcome**: lab Sabine 500 Hz under MELAMINE_FOAM walls = 0.162 s vs measured 0.158 s; rel_err = +2.40 %; sub-branch A (PASS-gate recovered). Lab umbrella renamed `test_a11_soundcam_lab_band_record`; new companion `test_a11_soundcam_lab_pass_gate_recovered`.

## Alternatives considered

- **(a) Add MELAMINE_FOAM + FIBERGLASS_CEILING + TILE_FLOOR.** Rejected: minimum-leverage scope discipline — lab needs wall treatment, not ceiling/floor. Other two enums re-deferred under OQ-14.
- **(b) Add MELAMINE_FOAM but keep lab fixture on MISC_SOFT walls.** Rejected: new enum is dead weight without a fixture exercising it; the flip is paper-faithful.
- **(c) Block on verbatim Vorländer α₅₀₀.** Rejected for v0.11: envelope (0.80-0.95) is tight; coefficient-invariant test brackets the value; honesty-first marker (D22) flags as planner-envelope, not fabricated.
- **(d) Re-tune MISC_SOFT α₅₀₀ from 0.40 → 0.85.** Rejected: MISC_SOFT is the furnishings slot (ADR 0011); re-purposing silently breaks ADR 0011's honesty contract and per-room budget tests.
- **(e) Defer the addition to v0.12+.** Rejected: v0.10.1 named v0.11 as the closure point; further deferral violates deferral cadence.

## Why chosen

- **Minimum-leverage**: 1 enum entry + 2 dict rows + 1 fixture flip + 1 test material switch; no predictor/adapter/CLI surfaces touched.
- **Honesty-first coefficient sourcing**: planner-locked envelope + citation-pending marker + invariant test bracket (same policy as ADR 0011 / ADR 0008).
- **Symmetric with ADR 0018 §Reverse-criterion**: closes the treated-room half (lab); leaves conference disagreement-record for the orthogonal OQ-13b path.

## Consequences

- **(+) Lab A11 PASS-gate recovered** (rel_err +2.40 %; signature `default_enum_underrepresents_treated_room_absorption` → `RECOVERED_under_melamine_foam_enum`).
- **(+) Default-lane test count +5** (+1 coefficient invariant, +2 band-row tests, +1 lint smoke, +1 PASS-gate-recovered companion).
- **(+) `MaterialLabel` 9 → 10**; Stage-1 schema absorbs gracefully; `__schema_version__` stays `"0.1-draft"` (Stage-2 flip still bound to A10b + ≥ 3 captures per ADR 0016 + D2).
- **(+) Conference disagreement-record band byte-equal** (only redundant `assert rel_err < -0.10` added per OQ-13f).
- **(−) α₅₀₀ = 0.85 is planner-envelope, not verbatim** (citation-pending; coefficient-invariant test brackets [0.80, 0.95]; successor patch updates if verbatim Vorländer lookup shifts the value).
- **(−) Schema marker does NOT re-flip at v0.11** (D2 ≥3-captures requirement unmet; only 2 substitute rooms).

## Reverse-criterion

- Verbatim Vorländer α₅₀₀ outside [0.80, 0.95] → v0.11.x patch updating row + invariant test + §References.
- FIBERGLASS_CEILING + TILE_FLOOR added at v0.12+ AND lab returns to PASS without MELAMINE_FOAM → re-evaluate under OQ-14.
- §2.4 PASS reframed as fixture-flip-tautology by successor critic → ADR 0021 re-frames as fixture-flip-dependent + ratchets citation to verbatim.
- Conference disagreement-record closes (OQ-13b residual study) → successor ADR may flip conference band back to PASS-gate.

## §2.4 executor decision-point record (v0.11.0)

| Metric | Value |
| --- | --- |
| Lab `predicted` (Sabine 500 Hz, MELAMINE_FOAM walls) | **0.161795 s** |
| Lab `measured` (paper Table 7 broadband) | 0.158000 s |
| Lab `rel_err = (predicted - measured) / measured` | **+2.40 %** |
| Sub-branch selected | **A (PASS-gate recovered)** |
| `_LAB_EXPECTED.predicted_s_min` | 0.150 (new) |
| `_LAB_EXPECTED.predicted_s_max` | 0.175 (new) |
| `_LAB_EXPECTED.rel_err_min` | -0.20 (new) |
| `_LAB_EXPECTED.rel_err_max` | +0.20 (new) |
| `_LAB_EXPECTED.disagreement_signature` | `RECOVERED_under_melamine_foam_enum` |
| Umbrella test renamed | `test_a11_soundcam_lab_disagreement_record` → `test_a11_soundcam_lab_band_record` |
| NEW companion test | `test_a11_soundcam_lab_pass_gate_recovered` |

## References

- **Vorländer, M. (2020). *Auralization*, §11 / Appendix A.** Springer.
  PRIMARY source for MELAMINE_FOAM α₅₀₀ + per-band coefficients (per OQ-13a
  amendment + ADR 0011 / OQ-2 / OQ-6 precedent). **Citation status (v0.11)**:
  verbatim page + row + panel-thickness column **PENDING** — v0.11 shipped
  the planner-locked envelope mid-value (α₅₀₀ = 0.85) honesty-flagged per
  D22 (not fabricated; bracketed by the coefficient-invariant test).
  **Citation status (v0.12)**: see §Status-update-2026-05-12 block below
  for the v0.12 closure-attempt outcome (secondary-source corroboration
  landed; Vorländer verbatim page/row/panel-thickness still PENDING and
  re-deferred to v0.13+ per the D27 cadence reverse-criterion).
  **Citation status (v0.13)**: see §Status-update-2026-05-12-2 block below
  for the SECOND-AND-LAST permitted re-deferral under D27 / D28-P2 cadence
  (verbatim page/row/panel-thickness still PENDING; v0.14 = HARD WALL
  previewed). **Citation status (v0.14)**: HARD-WALL CLOSURE under **path γ
  (honesty-leak fallback)** via successor **ADR 0028 NEW** (see
  `docs/adr/0028-hardwall-closure-and-ism-adoption.md` §Decision sub-item 1
  + §References "multi-source envelope" row); PRIMARY-source row reframed
  from "Vorländer 2020 §11 / Appx A (PRIMARY, verbatim pending)" to a
  **multi-source envelope record** (Vorländer 2020 §11/Appx A PRIMARY
  envelope-bracketed verbatim unattained through D27 cadence exhaustion +
  Bies & Hansen 2018 §A secondary unverified + NRC manufacturer datasheets
  secondary unverified + SoundCam paper arXiv:2311.03517v2 §A.1 NRC 1.26
  corroboration consistent with envelope mid-value). α₅₀₀ = 0.85 BYTE-EQUAL
  to v0.11/v0.12/v0.13; lab A11 PASS-gate rel_err = +2.40 % BYTE-EQUAL; enum
  MELAMINE_FOAM RETAINED. See §Status-update-2026-05-16 block below for the
  v0.14 HARD-WALL CLOSURE record.
- Bies & Hansen (2018), *Engineering Noise Control*, §A — secondary cross-check.
- NRC manufacturer data sheets — secondary cross-check.
- arXiv:2311.03517v2 (NeurIPS 2024 D&B, SoundCam) — Table 7 broadband RT60 = 0.158 s (lab).
- ADR 0011, 0016, 0018, 0020 — cross-refs above.
- D22, D23, D25 — `.omc/plans/decisions.md`.
- `.omc/plans/v0.11-design.md`, `.omc/plans/open-questions.md`, `RELEASE_NOTES_v0.11.0.md`.

## §Status-update-2026-05-12 (v0.12.0) — verbatim Vorländer citation closure attempt

**Closure attempt outcome (D22 hybrid pattern, factual: citation status)**:
v0.12 executor attempted the Vorländer 2020 *Auralization* (2nd ed.,
Springer) §11 / Appendix A verbatim page + row + panel-thickness column
lookup for the "melamine foam panel" / "acoustic foam absorber" row.

- **Vorländer 2020 verbatim page / row / panel-thickness**: **STILL
  PENDING at v0.12**. Executor did not have direct textbook access; per
  D27 reverse-criterion (d), v0.12 records the closure-attempt outcome
  honestly rather than fabricating a citation. Re-deferred to v0.13+
  (verbatim source access-limited; this is the **FIRST of at most two
  consecutive re-deferral cycles** permitted by D27 — v0.13 is the LAST
  permitted re-deferral; v0.14 is the hard wall where closure MUST land
  OR successor ADR switches PRIMARY source).
- **Secondary-source corroboration landed at v0.12**: SoundCam paper
  arXiv:2311.03517v2 §A.1 (Stanford 2024 NeurIPS D&B) describes the lab
  as having **"NRC 1.26 melamine foam walls"** (Noise Reduction
  Coefficient 1.26 averaged across 250/500/1000/2000 Hz). The NRC 1.26
  figure is consistent with the planner-locked envelope mid-value
  α₅₀₀ = 0.85 used at v0.11 (foam absorption rises steeply through
  250-500 Hz and plateaus above 1 kHz; 500 Hz scalar at ~0.85 is
  physically plausible for the implied band-average). NOT a Vorländer
  2020 verbatim citation.
- **α₅₀₀ value at v0.12**: **0.85 BYTE-EQUAL to v0.11**. No shift inside
  the [0.80, 0.95] invariant envelope; lab A11 PASS-gate UNCHANGED
  (rel_err = +2.40 %); STOP rules #5 + #7 did not fire. NEW test
  `test_melamine_foam_a500_v0_12_status_update_block_present` asserts envelope
  + §Status-update block presence.
- **Audit-trail integrity**: per D22 hybrid pattern, v0.11 §References
  PENDING annotation is in-line annotated ("see §Status-update-2026-05-12
  below"); this block is the canonical record of WHY closure is
  re-deferred.

**No library code changes** at v0.12: α₅₀₀ row + band row + lab A11
PASS-gate predictions all byte-equal to v0.11.

**Cross-references**: D22 (hybrid pattern), D27 NEW (verbatim-pending
closure cadence; access-limited reverse-criterion invoked), OQ-13a
(v0.11 `[x]`; v0.12 §Status-update annotation), `.omc/plans/v0.12-design.md`
§2.2, `tests/test_room_acoustics_octave.py::test_melamine_foam_a500_v0_12_status_update_block_present`.

## §Status-update-2026-05-12-2 (v0.13.0) — Vorländer verbatim citation SECOND re-deferral

**Closure attempt outcome (D22 hybrid pattern, factual: citation status)**:
v0.13 executor attempted the Vorländer 2020 *Auralization* (2nd ed.,
Springer) §11 / Appendix A verbatim page + row + panel-thickness column
lookup for the "melamine foam panel" / "acoustic foam absorber" row.

- **Vorländer 2020 verbatim page / row / panel-thickness**: **STILL
  PENDING at v0.13**. No library, ILL, or NRC datasheet path materialised
  during the v0.13 cycle. Per D27 reverse-criterion (d), v0.13 records
  the closure-attempt outcome honestly. This is the **SECOND-AND-LAST
  permitted re-deferral** under D27 cadence. **v0.14 = HARD WALL** —
  closure MUST land OR successor ADR 0022 switches PRIMARY source.
- **Path α/β evidence lock (planner-locked at v0.13-design)**: path α
  (verbatim Vorländer 2020 acquisition) remains the default path.
  Path β (PRIMARY-source switch to Bies & Hansen 2018 §A) was REJECTED
  at v0.13 design time because no in-repo verbatim α₅₀₀ for melamine foam
  from Bies & Hansen 2018 §A exists — `grep -rn "Bies\|Hansen" docs/
  roomestim/` returns ONLY the ADR 0019 §References row naming Bies &
  Hansen as secondary cross-check (no extracted value). Switching PRIMARY
  source without an extracted verbatim value would be a fabricated-quote
  honesty leak (ADR 0018 §Drivers / D22).
- **α₅₀₀ value at v0.13**: **0.85 BYTE-EQUAL to v0.11 / v0.12**. No
  shift inside the [0.80, 0.95] invariant envelope; lab A11 PASS-gate
  UNCHANGED (rel_err = +2.40 %). STOP rules #5 + #7 did not fire.
- **D27 cadence accounting**: v0.13 = SECOND-AND-LAST permitted
  re-deferral. v0.14 = HARD WALL. Three v0.14 closure paths explicitly
  previewed: (i) verbatim Vorländer 2020 §11 / Appx A acquired and
  recorded; (ii) successor ADR 0022 switches PRIMARY to Bies & Hansen
  2018 §A with verbatim extracted α₅₀₀; (iii) successor ADR 0022
  switches PRIMARY to NRC manufacturer datasheet with verbatim value.
- **External-acquisition-channel exhaustion record (Option B —
  HONEST-FALLBACK)**: At v0.13 executor-time, external acquisition
  channels (SNU library ILL, OA mirrors, publisher OA page) for Bies &
  Hansen 2018 §A were NOT investigated. v0.14 hard-wall closure MUST
  exhaust these channels before invoking path-β under successor ADR 0022.

**No library code changes** at v0.13: α₅₀₀ row + band row + lab A11
PASS-gate predictions all byte-equal to v0.12 / v0.11.

**Cross-references**: D22 (hybrid pattern), D27 (cadence; SECOND-AND-LAST
re-deferral invoked), D28-P1 NEW (audit-trail process meta-rules),
OQ-13a (v0.13 annotation), OQ-16 NEW (path-α-vs-β lock at v0.14 hard
wall), `.omc/plans/v0.13-design.md` §2.A.

## §Status-update-2026-05-16 (v0.14.0) — Vorländer verbatim citation HARD-WALL CLOSURE under path γ via ADR 0028

**Closure outcome (D22 hybrid pattern + D28-P1 factual band; factual:
citation closure-path)**: v0.14.0 was cycle 3 of the D27 / D28-P2
verbatim-pending-closure cadence (v0.11 NEW pending → v0.12 FIRST
re-deferral → v0.13 SECOND-AND-LAST re-deferral → **v0.14 HARD WALL**).
Per D27 reverse-criterion + D28-P2, a third consecutive re-deferral
was forbidden; v0.14 had to close OR escalate to a successor ADR
switching PRIMARY source. The v0.14 Item A executor pass landed
**HARD-WALL CLOSURE under path γ (honesty-leak fallback)** via the
successor **ADR 0028 NEW**
(`docs/adr/0028-hardwall-closure-and-ism-adoption.md`).

- **Closure path actually taken**: **γ (honesty-leak fallback)** per
  planner-locked default-safe lock (v0.14-design.md §0.0 row "Item A"
  + §0.4 STOP rule #7 OPPORTUNISTIC reverse not fired at executor-time).
  At the v0.14 Item A executor pass (2026-05-16), a verbatim-citation
  grep across `docs/`, `roomestim/`, and `tests/` returned ONLY
  §References row labels + closure-attempt outcome records inside this
  ADR 0019 (lines 114, 116, 165, 173, 180, 182-183, 193, 198). NO
  extracted verbatim α₅₀₀ value with page + row + panel-thickness
  landed inside the [0.80, 0.95] envelope. STOP rule #7 did NOT fire;
  path α (verbatim Vorländer) and path β (PRIMARY-source switch to
  Bies & Hansen 2018 §A or NRC manufacturer datasheet with verbatim
  extracted value) remained OPPORTUNISTIC upgrades for v0.14.x patch
  or v0.15+ per ADR 0028 §Reverse-criterion item 1.
- **D27 cadence accounting**: **v0.14 = cycle 3 = HARD WALL CLOSED**
  (NOT a third re-deferral). The cadence schedule that v0.11 design
  pass + v0.12 §Status-update + v0.13 §Status-update-2026-05-12-2
  collectively previewed landed under path γ at v0.14.0 ship time.
  Cycle count is final; no further D27 re-deferral cycles permitted
  for this ADR.
- **α₅₀₀ value at v0.14**: **0.85 BYTE-EQUAL to v0.11 / v0.12 / v0.13**.
  Under path γ, the MELAMINE_FOAM library row stayed bracketed within
  the [0.80, 0.95] invariant envelope; no library-coefficient change.
  `MaterialAbsorption[MaterialLabel.MELAMINE_FOAM] = 0.85` BYTE-EQUAL;
  `MaterialAbsorptionBands[MaterialLabel.MELAMINE_FOAM] = (0.35, 0.65, 0.85, 0.92, 0.93, 0.92)`
  BYTE-EQUAL. Under the OPPORTUNISTIC α/β branch (NOT fired), the
  envelope-bracketed value would have been re-checked against the
  extracted verbatim; out-of-envelope shift would have tripped a
  v0.14.x patch per ADR 0028 §Reverse-criterion item 1.
- **Lab A11 PASS-gate at v0.14**: **rel_err = +2.40 % BYTE-EQUAL** to
  v0.11 / v0.12 / v0.13. Under path γ no library state changed;
  `_LAB_EXPECTED` predictions BYTE-EQUAL; sub-branch A (PASS-gate
  recovered) annotation BYTE-EQUAL.
- **§References PRIMARY-source row reframe (v0.14)**: the v0.11
  "Vorländer 2020 §11 / Appx A (PRIMARY, verbatim pending)" framing
  was reframed at v0.14 to a **multi-source envelope record** —
  Vorländer 2020 §11/Appx A PRIMARY envelope-bracketed verbatim
  unattained through D27 cadence exhaustion + Bies & Hansen 2018 §A
  secondary unverified + NRC manufacturer datasheets secondary
  unverified + SoundCam paper arXiv:2311.03517v2 §A.1 NRC 1.26
  corroboration consistent with envelope mid-value. The reframe was
  recorded in-place at the Vorländer §References row above ("Citation
  status (v0.14)" entry) per D28-P1 factual band + D28-P1 supersedure
  clause (factual citation-status growth → in-place §References
  edit + appended §Status-update block; STRUCTURAL PRIMARY-source
  switch under path β would have required ADR 0028 §Decision
  sub-item 1 to record the switch — which it does as the path γ
  closure record + the path β OPPORTUNISTIC reverse).
- **Honesty-leak entry preserved (per ADR 0018 §Drivers lineage)**:
  the explicit record that "verbatim citation unattainable through
  three ship cycles + external-acquisition exhaustion at v0.13
  documented Option B (channels NOT investigated)" was preserved as
  the truthful audit-trail record of WHY path γ was the closure
  path. Per ADR 0018 §Drivers item 1, silent claim-shifting
  (placeholder framed as measured) was the v0.9 → v0.10 walk-back
  failure mode that v0.14+ planner rounds actively resisted; this
  §Status-update block is the audit-trail entry, NOT a softening of
  the hard wall. v0.15+ may §Status-update ADR 0028 upgrading
  γ → α/β if verbatim later surfaces per ADR 0028 §Reverse-criterion
  item 1.
- **STOP rules**: STOP rule #5 (`__schema_version__` UNCHANGED at
  `"0.1-draft"`) held; STOP rule #6 (`MaterialLabel` enum UNCHANGED
  at 10 entries) held; STOP rule #7 (verbatim landed mid-cycle
  inside envelope) did NOT fire at the Item A executor pass.

**No library code changes** at v0.14 under path γ: α₅₀₀ row + band
row + lab A11 PASS-gate predictions all BYTE-EQUAL to v0.13 / v0.12 /
v0.11. The Item A executor pass scope was documentation-only (ADR
0028 NEW + this §Status-update block + decisions.md D35 NEW +
RELEASE_NOTES_v0.14.0.md scaffold).

**Cross-references**: D22 (hybrid pattern), D27 (cadence; cycle 3
HARD WALL closed), D28-P1 (factual-band §Status-update + supersedure
clause), D28-P2 (permitted re-deferral cadence with cycle-count
hard-wall), D34 (v0.14 ADR + OQ re-numbering audit-trail), D35
(v0.14.0 hard-wall closure under path γ recording decision),
OQ-13a (CLOSED at v0.14 via HARD-WALL CLOSURE under path γ),
OQ-16 (CLOSED at v0.14 — path γ default locked; α/β OPPORTUNISTIC
reverse not fired), ADR 0018 (§Drivers honesty-leak lineage), **ADR
0028 NEW** (`docs/adr/0028-hardwall-closure-and-ism-adoption.md`
§Decision sub-item 1 + §References "multi-source envelope" row),
`.omc/plans/v0.14-design.md` §0.0 row "Item A" + §2.A + §0.4 STOP
rule #7, `.omc/plans/v0.14-architect-revalidation-2026-05-16.md`
§2.1-§2.4 (hard-wall verification + path γ default-safe lock
re-confirmation), `RELEASE_NOTES_v0.14.0.md`.
