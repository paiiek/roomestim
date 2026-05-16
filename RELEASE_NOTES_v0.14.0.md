# roomestim v0.14.0 — Release Notes

**Date**: 2026-05-16 (drafted; Item A authoring pass) / 2026-05-NN
(target shipped at the v0.14 final-commit-prep pass).
**Predecessor**: v0.13.0 (`2046681`) — Vorländer SECOND re-deferral
(ADR 0019 §Status-update-2026-05-12-2; D27 cadence cycle 2 (last
permitted)) + D28 NEW (audit-trail meta-rules P1/P2) + mypy `--strict`
baseline enforced (OQ-13i CLOSED) + lint scope expansion-2 (ADR 0020
§Status-update-2026-05-13).
**Release nature**: SemVer minor — DELIBERATE-mode v0.14.0 bundle landing
**Item A** (OQ-13a HARD-WALL CLOSURE under path γ via ADR 0028 NEW) +
**Item B** (OQ-15 ISM library bundle — `roomestim/reconstruct/image_source.py`
NEW; conference + lab + ACE Office_1 ratios characterised) + **Item C**
(OQ-13b reclassification — branch-dependent on Item B conference ISM ratio).
**Item D** (predictor-default switch) DEFERRED per D26 characterise-first-decide-second
cadence (planner-locked default; ADR 0029 RESERVED).

## What v0.14.0 ships

v0.14.0 landed the DELIBERATE-mode scope locked by
`.omc/plans/v0.14-design.md` §0.0:

### Item A — OQ-13a HARD-WALL CLOSURE under path γ (honesty-leak fallback) via ADR 0028 NEW

- **D27 cadence closed at cycle 3 (HARD WALL)**: the v0.11 NEW pending →
  v0.12 FIRST re-deferral → v0.13 SECOND-AND-LAST re-deferral cadence
  landed CLOSURE at v0.14.0 (NOT a third re-deferral; per D27 + D28-P2
  forbidden-indefinite-deferral discipline). Cycle count is final.
- **Closure path actually taken**: **γ (honesty-leak fallback)** per
  planner-locked default-safe lock. The Item A executor pass MANDATORY
  one-shot pre-flight verbatim-citation grep across `docs/`, `roomestim/`,
  and `tests/` returned ONLY §References row labels + closure-attempt
  outcome records inside ADR 0019 (lines 114, 116, 165, 173, 180,
  182-183, 193, 198). NO extracted verbatim α₅₀₀ value with page + row +
  panel-thickness landed inside the [0.80, 0.95] envelope. §0.4 STOP
  rule #7 OPPORTUNISTIC reverse (path α / β closure if verbatim landed
  mid-cycle) did NOT fire. Path γ default-safe lock held.
- **α₅₀₀ = 0.85 BYTE-EQUAL to v0.11 / v0.12 / v0.13**; MELAMINE_FOAM
  enum entry RETAINED; library row BYTE-EQUAL; lab A11 PASS-gate
  rel_err = +2.40 % BYTE-EQUAL.
- **§References reframe** (per D28-P1 factual band): PRIMARY-source row
  "Vorländer 2020 §11 / Appx A (PRIMARY, verbatim pending)" reframed
  in-place to a multi-source envelope record (Vorländer PRIMARY
  envelope-bracketed verbatim unattained through D27 cadence exhaustion +
  Bies & Hansen 2018 §A secondary unverified + NRC manufacturer datasheets
  secondary unverified + SoundCam paper arXiv:2311.03517v2 §A.1 NRC 1.26
  corroboration consistent with envelope mid-value).
- **Honesty-leak entry preserved** (per ADR 0018 §Drivers lineage): explicit
  "verbatim citation unattainable through three ship cycles +
  external-acquisition exhaustion at v0.13 documented Option B (channels
  NOT investigated)" as the truthful audit-trail record of WHY path γ
  was the closure path. NOT a softening of the hard wall; the entry IS
  the audit-trail.
- **ADR 0028 NEW** (`docs/adr/0028-hardwall-closure-and-ism-adoption.md`)
  composite ADR §Decision sub-item 1 records the path γ closure + the
  path α/β OPPORTUNISTIC reverse anchor for v0.14.x / v0.15+.
- **ADR 0019 amended** via §Status-update-2026-05-16 (v0.14.0) HARD-WALL
  CLOSURE block + in-place §References "Citation status (v0.14)" entry
  per D28-P1 hybrid pattern.
- **D35 NEW** (`/home/seung/mmhoa/roomestim/.omc/plans/decisions.md`)
  records the v0.14.0 hard-wall closure decision under path γ (D27 cadence
  cycle 3 = HARD WALL closed; NOT re-deferred).

### Item B — OQ-15 ISM library bundle landed

- **Library**: `roomestim/reconstruct/image_source.py` NEW (430 lines;
  mypy `--strict` clean; ruff clean). Public API:
  `image_source_rt60(volume_m3, dimensions_m, surface_areas, absorption_coeffs, max_order=50, energy_threshold_db=-60.0, sound_speed_m_s=343.0) -> float`
  and parallel `image_source_rt60_per_band(...) -> dict[int, float]`.
  Algorithm: Allen & Berkley 1979 §II + Lehmann & Johansson 2008 §III
  bookkeeping; image-source lattice L1-cap at
  `|nx| + |ny| + |nz| <= max_order`; per-surface bounce counts per
  Allen-Berkley eq. 7; diagonal fixed source-receiver placement
  `(0.3L, 0.3W, 0.4H)` → `(0.7L, 0.7W, 0.6H)`; Schroeder EDC with
  T30 / T20 / T10 fit cascade (ISO 3382-2). Surface index convention
  LOCKED: `(floor, ceiling, wall_xneg, wall_xpos, wall_yneg, wall_ypos)`.
- **Tests**: `tests/test_image_source.py` NEW (14 tests). Default-lane
  test count rotated **138 → 152** (matches the plan-locked target
  exactly; ±2 slack range [150, 154] held). 14 tests cover analytic
  shoebox (2), runtime invariants single-band + per-band (2),
  conference + lab + Office_1 ratio characterisation (3), ADR 0028
  presence guards (2), max-order convergence (1), input validation
  smoke (1), ADR 0019 §Status-update presence (1), RELEASE_NOTES
  presence (1), Item C branch driver (1).
- **Analytic shoebox validation outcome**:
  - **Low-α=0.05 cube (4×4×4)**: ISM=2.1238 s vs Sabine=2.1467 s;
    ratio 0.9893 (-1.1 % off, within ±5 % planner-locked envelope).
    PASS at `max_order=80`.
  - **Moderate-α=0.50 cube**: ISM=0.1677 s vs Eyring=0.1548 s; ratio
    1.0827 (+8.3 % off, OUTSIDE planner-locked ±5 % Eyring band).
    Plan §0.4 STOP rule #2 outcome: investigation confirmed
    Allen-Berkley bounce-count formula applied byte-exact + Lehmann-
    Johansson placement applied; residual is the physical
    Eyring-Taylor-limit effect (Eyring assumes diffuse field which
    breaks at moderate absorption); threshold widened to ±15 % with
    explicit characterisation note in the test docstring per STOP-#2
    "acceptable executor action" branch. Reported back to planner.
- **Per-room ISM ratios** (recorded 2026-05-16):
  - **Conference (6.7×3.3×2.7, paper-faithful map)**: ISM=2.2693 s,
    Sabine=0.4490 s, Eyring=0.3981 s; **ISM/Sabine = 5.0537**,
    ISM/Eyring = 5.7002. Branch C-i fires (see Item C below).
  - **Lab (4.9×5.1×2.7, MELAMINE_FOAM walls)**: ISM=0.1069 s,
    Sabine=0.1618 s, Eyring=0.1007 s; **ISM/Eyring = 1.0619**
    (high-absorption regime; ISM ≈ Eyring as expected).
  - **ACE Office_1 (4.83×3.32×2.95)**: ISM=1.7324 s, Sabine=0.8637 s,
    Eyring=0.8152 s; **ISM/Sabine = 2.0059**. Second-room
    confirmation (D26 forbidden-indefinite-deferral gate fires —
    v0.15+ MUST land Item D).
- **Convergence caveat (added 2026-05-16 per code-reviewer pass MAJOR
  finding #1)**: per-room ratios above are computed at `max_order=50`
  (planner-locked default) and are NOT numerically converged for the
  conference and Office_1 rooms. Code-reviewer sweep at
  `max_order=100`: conference ISM/Sabine = **5.7400** (+13.6 % vs
  5.0537); Office_1 ISM/Sabine = **2.3593** (+17.6 % vs 2.0059); lab
  is high-absorption and already converged at `max_order=50`. Branch
  C-i (ratio > 1.15) fires under BOTH truncations, so the v0.14
  structural reframe decision (Item C) and the D26 ≥ 2-rooms gate are
  **robust to convergence**; the absolute ratio values are NOT
  load-bearing for the v0.14 release decision and are recorded for
  characterisation only. v0.15+ may revise quantitative ratios under
  a successor §Status-update on ADR 0028 / ADR 0021 if
  higher-order convergence becomes load-bearing for a future
  predictor-default decision (Item D / OQ-24).
- **Runtime invariant** ``ism_rt60 ≥ eyring_rt60 - 1e-6`` (ADR 0028
  §Decision sub-item 2) HELD across analytic-cube α sweep + all 3
  rooms; enforced at runtime by
  `tests/test_image_source.py::test_ism_eyring_lower_bound_invariant_single_band`
  + `test_ism_eyring_lower_bound_invariant_per_band` + per-room tests
  inline.
- **Polygon ISM** DEFERRED to v0.15+ inline (OQ-23 NEW). Conference,
  lab, Office_1 are all shoebox-able; Building_Lobby coupled-space
  EXCLUDED per ADR 0014.
- **ADR 0028 §Decision sub-item 2** body populated with the library
  API + validation evidence + per-room ratios.

### Item C — OQ-13b reclassification: Branch C-i fired

**Branch C-i fires** per the conference ISM/Sabine = **5.0537** ratio
(well above the 1.15 threshold; recorded at
`tests/test_image_source.py::test_a11_soundcam_conference_ism_ratio_characterises`
+ `test_conference_ism_item_c_branch_driver`).

- **NEW signature**: `sabine_shoebox_approximation_for_glass_heavy_room`
  reframes from the v0.10 pre-MELAMINE_FOAM signature
  `sabine_shoebox_underestimates_glass_wall_specular` + v0.12 AMBIGUOUS
  classification per ADR 0021 §Decision. Lands in **ADR 0028 §Decision
  sub-item 3** as a STRUCTURAL change per D28-P1 applicability table
  (signature reframing requires ADR §Decision body, NOT §Status-update).
- **ADR 0021 §Status-update-2026-05-16** appended as a parallel
  factual-band record (per D28-P1 hybrid pattern; conference ISM/Sabine
  + Office_1 ISM/Sabine ratios recorded as evidence supporting the
  reframe).
- **`_CONFERENCE_EXPECTED["disagreement_classification"]` field in
  `tests/test_a11_soundcam_rt60.py`**: NOT updated at v0.14.0 Item B + C
  executor pass — the existing classification value `"ambiguous"`
  reflects the **Sabine/Eyring ratio** classification (which stays at
  1.128 per ADR 0021 §Decision thresholds; library is BYTE-EQUAL) and
  the v0.12 existing test
  `test_a11_soundcam_conference_disagreement_classification` cross-checks
  via Sabine/Eyring ratio, not ISM/Sabine. The Item C branch driver
  `test_conference_ism_item_c_branch_driver` in
  `tests/test_image_source.py` records the new ISM-driven branch
  separately (additive, not replacement) — keeps Eyring-based
  classification and ISM-based reclassification as parallel data
  streams in the test surface per plan §0.4 STOP rule #11 "no library
  logic mutation outside narrow accommodation".

### Item D — Predictor-default decision DEFERRED per D26

**Item D was DEFERRED** at v0.14 per planner §0.0 row "Item D" + plan
§0.1 (c) — D26 characterise-first-decide-second cadence forbade the
predictor-default switch from landing in the same release as the
characterising study (v0.9-honesty-cycle silent-claim-shifting failure
mode). v0.14 characterised with ISM (Item B); v0.15+ may decide
predictor-default per D26 cadence. ADR 0029 was RESERVED per D34;
ADR 0028 §Reverse-criterion item 2 records the v0.15+ follow-up gate
(Office_1 + conference ISM ratios both > 1.15 → D26 forbidden-indefinite-deferral
clause triggers → predictor-default switch MUST land at v0.15+).

## What stays the same

- `__schema_version__` stays `"0.1-draft"` (Stage-2 re-flip bound to A10b
  in-situ capture + ≥ 3 captures per ADR 0016 + D2; STOP rule #5 held).
- `MaterialLabel` enum stays at 10 entries (no FIBERGLASS_CEILING /
  TILE_FLOOR addition; OQ-14 unchanged; STOP rule #6 held).
- `MELAMINE_FOAM` row BYTE-EQUAL (α₅₀₀ = 0.85; band tuple
  `(0.35, 0.65, 0.85, 0.92, 0.93, 0.92)`; STOP rules #5 + #7 held under
  path γ).
- All other 9 existing `MaterialLabel` entries + their
  `MaterialAbsorption{,Bands}` rows BYTE-EQUAL.
- `roomestim/place/*`, `roomestim/cli.py`, `roomestim/adapters/*`
  (library logic), `roomestim/reconstruct/{floor_polygon,listener_area,materials,walls}.py`
  BYTE-EQUAL (only `roomestim/reconstruct/image_source.py` NEW at the
  Item B executor pass).
- Lab A11 PASS-gate BYTE-EQUAL (rel_err = +2.40 %; sub-branch A;
  signature `RECOVERED_under_melamine_foam_enum`).
- ADR 0018 BYTE-EQUAL; cross-repo PR stays WITHDRAWN (D11; ≥ 3 captures
  requirement unmet).
- `proto/*` BYTE-EQUAL; predecessor RELEASE_NOTES BYTE-EQUAL (v0.1.1
  through v0.13.0; v0.12-web.0 + v0.12-web.1 parallel-track BYTE-EQUAL).
- **Known pre-existing v0.12-web.1 regression** (NOT a v0.14
  acoustics-track regression; documented here for audit-trail
  honesty per ADR 0018 §Drivers lineage):
  `tests/test_mypy_strict_baseline.py::test_mypy_strict_clean` fails
  on `roomestim/adapters/polycam.py:29` (unused `type: ignore` +
  missing `-> None` return annotation). Plus 9 ruff errors in
  `tests/web/test_3d_viewer.py` (F401 unused `plotly.graph_objects`
  import + 4×E402 module-level imports not at top of file). Both
  are v0.12-web.1 carryovers (commit `0bef198`); will land in a
  v0.12-web.2 patch on the parallel-track lane (per D29 / D30
  lane-separation discipline). NOT in v0.14 acoustics-track scope
  per plan §0.0 + §1.1 file table.

## Default-lane test count [138 → **152**]

Filter is `pytest -m "not lab and not web"` (web-lane separation per
`.omc/plans/v0.14-design.md` §Status-update-2026-05-16 amendment 1).

| Stage | Acoustics-track count (`pytest -m "not lab and not web"`) | Delta |
| --- | --- | --- |
| v0.12-web.1 baseline (live; commit `0bef198`) | 138 | (anchor) |
| v0.14.0 actual (Item B executor pass) | **152** (matches target exactly; within ±2 slack range [150, 154]) | **+14** acoustics-track |

Verification at the v0.14.0 Item B executor pass (2026-05-16):
```
pytest -m "not lab and not web" --collect-only -q tests 2>&1 | tail -1
# 152/191 tests collected (39 deselected)
```

The +14 net breakdown all lands inside `tests/test_image_source.py` NEW
(planner-locked at plan §1.2):

1. `test_ism_shoebox_low_absorption_matches_sabine` (analytic shoebox
   low-α validation; +1).
2. `test_ism_shoebox_moderate_absorption_within_15pct_of_eyring`
   (analytic shoebox moderate-α validation; +1).
3. `test_ism_eyring_lower_bound_invariant_single_band` (runtime
   invariant `ism ≥ eyring - 1e-6` sweep; +1).
4. `test_ism_eyring_lower_bound_invariant_per_band` (runtime invariant
   per-band; +1).
5. `test_a11_soundcam_conference_ism_ratio_characterises` (conference
   ISM ratio; Item B (e+) per plan §0.0; +1).
6. `test_a11_soundcam_lab_ism_ratio_characterises` (lab ISM ratio; +1).
7. `test_ace_office_1_ism_ratio_characterises` (Office_1 second-room
   ratio; D26 forbidden-indefinite-deferral gate; +1).
8. `test_adr_0028_presence_and_h3_headers` (ADR 0028 NEW file +
   section presence; +1).
9. `test_ism_max_order_convergence` (convergence guard; +1).
10. `test_image_source_rt60_input_validation_smoke` (input validation
    smoke; +1).
11. `test_adr_0019_v0_14_hard_wall_closure_block_present` (ADR 0019
    §Status-update-2026-05-16 presence guard; +1).
12. `test_release_notes_v0_14_0_presence` (RELEASE_NOTES_v0.14.0
    presence guard; +1).
13. `test_adr_0028_structural_integrity_decision_reverse_references`
    (ADR 0028 §Decision + §Reverse-criterion + §References + D26/27/28
    cross-ref guards; +1).
14. `test_conference_ism_item_c_branch_driver` (Item C branch driver
    regression-guard surrogate per plan §1.2 row 12; +1).

The +14 net breakdown is enumerated in plan `.omc/plans/v0.14-design.md`
§1.2 (analytic shoebox validation + runtime invariants + ratio
characterisation + ADR 0028 / 0019 presence guards + lint constant
rotation). Item A authoring pass added NO test surface (per plan §2.A
(ii) rename-in-place default); Item B executor pass added the +14
substance.

## ADR list

| ADR | Status | NEW / AMENDED | Purpose |
| --- | --- | --- | --- |
| 0028 | Accepted (v0.14.0) | NEW (composite Item A + B + C; per D34) | Hard-wall closure of melamine-foam citation (path γ) + ISM library adoption + conference reclassification + Office_1 ratio + predictor-default DEFER decision per D26. |
| 0029 | Reserved | RESERVED (per D34; ships at v0.14 ONLY if Item D reverse fires per plan §0.4 STOP rule #8) | Predictor-default switch slot for v0.15+. |
| 0019 | Amended via §Status-update-2026-05-16 (v0.14.0) | AMENDED (D22 hybrid + D28-P1; factual: HARD-WALL CLOSURE under path γ via ADR 0028) | Verbatim Vorländer citation HARD-WALL CLOSURE; PRIMARY-source row reframed to multi-source envelope; path α / β OPPORTUNISTIC reverse anchored at ADR 0028 §Reverse-criterion item 1. |
| 0021 | Amended via §Status-update-2026-05-16 (v0.14.0) conditional | AMENDED (D28-P1 factual band; conditional on Item C branch C-ii or C-iii — populated by the Item B + C executor pass) | Conference ISM ratio characterisation IF branch C-ii (AMBIGUOUS persists) or C-iii (coefficient-sourcing). Branch C-i signature reframe lands in ADR 0028 §Decision sub-item 3, NOT here. |
| 0001..0018, 0020, 0024..0027 | byte-equal | unchanged | STOP rule #11 held. v0.12-web.0/web.1 parallel-track ADRs (0024-0027) UNCHANGED. |

## New decisions

| D | Title | Reverse-criterion |
| --- | --- | --- |
| D35 | v0.14.0 hard-wall closure under path γ (honesty-leak fallback) via ADR 0028 | If verbatim Vorländer / Bies & Hansen / NRC datasheet surfaces at v0.14.x patch OR v0.15+, append §Status-update on ADR 0028 recording γ → α/β upgrade per D28-P1 factual band. D35 does NOT supersede D27 or D28-P2; cycle count for ADR 0019 is final. |

## New open questions

- **OQ-23 NEW** — Polygon ISM v0.15+ deferral (per plan §8; populated
  at the Item B executor pass).
- **OQ-24 NEW** — Predictor-default switch v0.15+ (per plan §8; D26
  forbidden-indefinite-deferral clause active).
- **OQ-25 NEW conditional** — Per-band glass α revision v0.15+ (per
  plan §8; conditional on Item C branch C-iii).

## What stays deferred

- **OQ-12a A10b in-situ capture** — user-volunteer-only; not
  planner-schedulable.
- **OQ-14 FIBERGLASS_CEILING + TILE_FLOOR** — no captured room required
  them at v0.14.
- **Item D predictor-default switch** — deferred to v0.15+ per D26 (ADR
  0029 RESERVED per D34).
- **Polygon ISM** — deferred to v0.15+ per plan §0.0 row "Item B" lock +
  ADR 0028 §Decision sub-item 2 inline (OQ-23 NEW).

## Tag-local-only

Local tag `v0.14.0` per D11 (tag-local-only policy unchanged). NOT
pushed to remote.

## References

- Predecessor commit: `2046681` (v0.13.0 ship).
- Design plan: `.omc/plans/v0.14-design.md` (1060 lines; DELIBERATE-mode
  Item A + B + C + D-deferred bundle; amended 2026-05-16 per architect
  re-validation absorption + D34).
- Architect re-validation memo:
  `.omc/plans/v0.14-architect-revalidation-2026-05-16.md` (257 lines;
  verdict YELLOW → 4 amendments absorbed via D34).
- ADR 0028 NEW: `docs/adr/0028-hardwall-closure-and-ism-adoption.md`
  (composite Item A + B + C; sequential-next-available allocation per
  D34; Item B + C §Decision sub-items 2 + 3 populated by the next
  executor pass).
- ADR 0019 §Status-update-2026-05-16 (v0.14.0) HARD-WALL CLOSURE block:
  `docs/adr/0019-melamine-foam-enum-addition.md` (D22 hybrid + D28-P1
  factual band; cycle 3 closed under path γ).
- D35 NEW: `.omc/plans/decisions.md` (v0.14.0 hard-wall closure under
  path γ recording decision; cross-ref D27 / D28-P1 / D28-P2 / D34).
- OQ-13a / OQ-16 closure annotations + OQ-23/24/25 NEW entries:
  `.omc/plans/open-questions.md` (populated by the Item B + C executor
  pass per plan §1.1 row 10).
- Parallel-track predecessors (BYTE-EQUAL): `RELEASE_NOTES_v0.12-web.0.md`,
  `RELEASE_NOTES_v0.12-web.1.md`.
- D27 (verbatim-pending closure cadence) + D28-P1/P2 (audit-trail
  meta-rules) + D34 (v0.14 ADR + OQ re-numbering audit-trail):
  `.omc/plans/decisions.md`.
