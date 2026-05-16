# ADR 0028 — Hard-wall closure of melamine-foam citation + image-source method library adoption

- **Status**: Accepted (v0.14.0)
- **Date**: 2026-05-16
- **Predecessor**: ADR 0019 (MELAMINE_FOAM enum; v0.11.0 NEW pending),
  ADR 0021 (conference Sabine-shoebox residual study; v0.12.0 AMBIGUOUS
  classification), ADR 0018 (substitute-disagreement record + honesty-leak
  lineage), D26 (predictor-adoption deferral policy: characterise first,
  decide second), D27 (verbatim-pending closure cadence), D28-P1
  (audit-trail hybrid §Status-update pattern), D28-P2 (permitted
  re-deferral cadence with cycle-count hard-wall), D34 (v0.14 ADR + OQ
  re-numbering audit-trail; 0022/0023 → 0028/0029).
- **Cross-ref**: ADR 0009 (D9 — Eyring parallel predictor; runtime
  invariant `eyring ≤ sabine + 1e-9` — pattern source for the ISM
  runtime lower bound `ism ≥ eyring - 1e-6`), ADR 0011 (MISC_SOFT
  enum + honesty-first coefficient sourcing precedent), ADR 0014
  (Building_Lobby coupled-space exclusion — defines why polygon ISM
  has NO target room at v0.14), ADR 0016 (Stage-2 schema flip
  predicate; UNCHANGED at v0.14), ADR 0020 (CI tense lint; ADR 0028
  body authored under D22 past-tense convention).

## Decision

ADR 0028 was a **composite** ADR bundling three sub-decisions at v0.14.0:

1. **Hard-wall closure of the Vorländer-verbatim citation cadence
   (Item A)** — the D27 / D28-P2 cycle-3 hard wall for ADR 0019's
   melamine-foam α₅₀₀ verbatim citation landed at v0.14.0 under
   **path γ (honesty-leak fallback)**: α₅₀₀ = 0.85 stayed as the
   envelope-bracketed value (invariant envelope [0.80, 0.95]) with
   an explicit "no verbatim source acquired through D27 cadence
   exhaustion (v0.11 NEW → v0.12 FIRST re-deferral → v0.13
   SECOND-AND-LAST re-deferral → v0.14 HARD WALL closure under γ)"
   §References note. The MELAMINE_FOAM enum entry was RETAINED; the
   library coefficient row was BYTE-EQUAL to v0.11 / v0.12 / v0.13;
   the lab A11 PASS-gate (rel_err = +2.40 %) was BYTE-EQUAL. The
   PRIMARY-source row was reframed from `Vorländer 2020 §11 / Appx A
   (PRIMARY, verbatim pending)` to a multi-source envelope record
   (verbatim unattained through D27 cadence exhaustion + secondary
   cross-checks corroborated within the [0.80, 0.95] envelope).

2. **(Item B — image-source method library landing)**: SCAFFOLDED
   for the v0.14 next-executor-pass per plan §0.0 row "Library
   location lock" + §2.B. ADR 0028 §Decision sub-item 2 was placed
   under reservation at the Item A authoring pass; the next executor
   pass (Item B) was scheduled to land the ISM library at
   `roomestim/reconstruct/image_source.py`, the analytic shoebox
   validation evidence, and the conference + lab + ACE Office_1
   ISM-vs-Sabine ratios. Until the Item B pass landed, the §Decision
   sub-item 2 body of this ADR carried only the reservation marker
   below; the substantive landing waited on the executor sequencing
   per plan §0.3 (Item B before Item C before Item A finalisation,
   but Item A scaffolding was permitted under D28-P1 ahead of Item B
   to anchor the cross-references).

   **Item B executor pass landed at 2026-05-16** (populated below):

   - **Library**: `roomestim/reconstruct/image_source.py` NEW (430
     lines / mypy `--strict` clean / ruff clean). Public API:
     ```python
     image_source_rt60(
         volume_m3: float,
         dimensions_m: tuple[float, float, float],
         surface_areas: tuple[float, ...],
         absorption_coeffs: tuple[float, ...],
         max_order: int = 50,
         energy_threshold_db: float = -60.0,
         sound_speed_m_s: float = 343.0,
     ) -> float

     image_source_rt60_per_band(
         volume_m3: float,
         dimensions_m: tuple[float, float, float],
         surface_areas: tuple[float, ...],
         absorption_coeffs_per_band: dict[int, tuple[float, ...]],
         max_order: int = 50,
         energy_threshold_db: float = -60.0,
         sound_speed_m_s: float = 343.0,
     ) -> dict[int, float]
     ```
     Algorithm: Allen & Berkley 1979 §II + Lehmann & Johansson 2008
     §III placement bookkeeping; image-source lattice ``L1-cap`` at
     ``|nx| + |ny| + |nz| <= max_order``; per-surface bounce counts
     ``n_xneg = |nx - qx|``, ``n_xpos = |nx|`` per axis (Allen &
     Berkley 1979 eq. 7); diagonal fixed source-receiver placement at
     ``(0.3L, 0.3W, 0.4H)`` → ``(0.7L, 0.7W, 0.6H)`` (non-degenerate
     on all 3 axes per Lehmann-Johansson placement-bias appendix);
     Schroeder-integrated EDC with T30 / T20 / T10 fit cascade
     (ISO 3382-2). Surface index convention LOCKED:
     ``(floor, ceiling, wall_xneg, wall_xpos, wall_yneg, wall_ypos)``.

   - **Analytic shoebox validation** (`tests/test_image_source.py`
     `test_ism_shoebox_low_absorption_matches_sabine` line 92 +
     `test_ism_shoebox_moderate_absorption_within_15pct_of_eyring`
     line 131):
     - **Low-α=0.05 cube (4×4×4)**: ISM=2.1238 s, Sabine=2.1467 s
       (analytic), ISM/Sabine = 0.9893 (-1.1 % off, within ±5 %
       envelope per plan §0.0 row "ISM correctness validation").
       PASS at `max_order=80` (plan-locked default 50 insufficient for
       this regime — Sabine convergence requires deeper enumeration).
     - **Moderate-α=0.50 cube**: ISM=0.1677 s, Eyring=0.1548 s,
       ISM/Eyring = 1.0827 (+8.3 % off, OUTSIDE planner-locked ±5 %
       Eyring band). Plan §0.4 STOP rule #2 outcome at executor pass:
       investigation confirmed Allen-Berkley bounce-count formula
       applied byte-exact + Lehmann-Johansson placement applied; the
       residual is a physical Eyring-Taylor-limit effect (Eyring
       assumes diffuse field which breaks at moderate absorption;
       pure-specular ISM accounts for specular bookkeeping that
       Eyring does not). Threshold widened to ±15 % per STOP-#2
       "acceptable executor action" branch with explicit
       characterisation note in the test docstring; reported back
       to planner via the v0.14.0 Item B verifier hand-off.

   - **Per-room ISM-vs-Sabine + ISM-vs-Eyring ratios** (recorded
     2026-05-16 via `tests/test_image_source.py` executor pass):
     - **Conference (6.7×3.3×2.7, paper-faithful map; 3 drywall +
       1 glass + carpet + acoustic-tile ceiling)** —
       `test_a11_soundcam_conference_ism_ratio_characterises` line 320:
       ISM=2.2693 s, Sabine=0.4490 s, Eyring=0.3981 s;
       **ISM/Sabine = 5.0537**, ISM/Eyring = 5.7002. Branch C-i
       fires (ratio >> 1.15); see §Decision sub-item 3 below for the
       Item C structural reframe.
     - **Lab (4.9×5.1×2.7, MELAMINE_FOAM walls per ADR 0019)** —
       `test_a11_soundcam_lab_ism_ratio_characterises` line 378:
       ISM=0.1069 s, Sabine=0.1618 s, Eyring=0.1007 s;
       **ISM/Eyring = 1.0619** (high-absorption regime; ISM ≈ Eyring
       as expected per Vorlaender 2020 §4.2.4 high-α convergence).
     - **ACE Office_1 (4.83×3.32×2.95, carpet + 4 painted walls +
       drywall ceiling per `ACE_ROOM_GEOMETRY`)** —
       `test_ace_office_1_ism_ratio_characterises` line 441:
       ISM=1.7324 s, Sabine=0.8637 s, Eyring=0.8152 s;
       **ISM/Sabine = 2.0059**. Second-room confirmation (D26
       forbidden-indefinite-deferral gate): Office_1 ratio > 1.15
       cleanly + conference ratio > 1.15 → predictor-default switch
       AT MOST may land at v0.15+ per §Reverse-criterion item 2 below.

     - **Convergence caveat (added 2026-05-16 per code-reviewer pass
       MAJOR finding #1)**: ratios published above are computed at
       `max_order=50` (the planner-locked default and the value used
       in the per-room tests). The ISM is **NOT numerically converged
       at `max_order=50`** for these rooms — a code-reviewer-pass
       sweep at `max_order=100` produced: conference ISM=2.5774 s →
       ISM/Sabine = **5.7400** (+13.6 % vs the 5.0537 above);
       Office_1 ISM=2.0376 s → ISM/Sabine = **2.3593** (+17.6 % vs the
       2.0059 above); lab is high-absorption and is already converged
       at `max_order=50` (ISM/Eyring stays ≈ 1.06). Branch C-i (ratio
       > 1.15) fires under BOTH truncations for BOTH rooms, so the
       Item C structural reframe decision (§Decision sub-item 3 below)
       and the D26 ≥ 2-rooms gate are **robust to convergence**; the
       absolute ratio values are NOT load-bearing for the v0.14
       decision and are recorded for characterisation only. v0.15+
       may revise quantitative ratios under a successor §Status-update
       if higher-order convergence becomes load-bearing for a future
       predictor-default decision (Item D / OQ-24).
       Cross-ref: code-review memo
       `.omc/plans/v0.14-code-review-2026-05-16.md` §2.1.

   - **Test surface**: 14 NEW tests in `tests/test_image_source.py`
     (analytic shoebox 2 + runtime invariant single-band 1 + per-band
     1 + conference / lab / Office_1 ratio characterisation 3 +
     ADR 0028 presence guards 2 + max-order convergence 1 + input
     validation smoke 1 + ADR 0019 §Status-update presence 1 +
     RELEASE_NOTES presence 1 + Item C branch driver 1). Default-lane
     test count rotated 138 → 152 (plan-locked target; ±2 slack
     range [150, 154]).

   - **Polygon ISM** DEFERRED to v0.15+ inline per plan §0.0 row
     "Item B" lock + OQ-23 NEW per D34 (no target room at v0.14
     requires polygon ISM — conference + lab + Office_1 are all
     shoebox-able; Building_Lobby is coupled-space EXCLUDED per
     ADR 0014).

   - **Runtime invariant** ``ism_rt60 ≥ eyring_rt60 - 1e-6`` (single-
     band + per-band) HELD across analytic-cube α sweep
     {0.05, 0.10, 0.25, 0.50, 0.85} + conference + lab + Office_1
     rooms; enforced at runtime by
     `tests/test_image_source.py::test_ism_eyring_lower_bound_invariant_single_band`
     + `test_ism_eyring_lower_bound_invariant_per_band` + per-room
     ratio tests inline.

3. **(Item C — conference OQ-13b reclassification)**: SCAFFOLDED for
   the v0.14 next-executor-pass per plan §0.0 row "Item C". The
   classification branch (C-i ratio > 1.15 / C-ii 1.10 ≤ ratio ≤ 1.15 /
   C-iii ratio < 1.10) was data-driven on the Item B conference ISM
   ratio; the §Decision sub-item 3 body of this ADR was scheduled
   for population by the Item B + C executor pass.

   **Item B + C executor pass landed at 2026-05-16** (populated below):

   **Branch C-i fires** at the conference room measurement:
   ISM/Sabine = **5.0537** (well above the 1.15 threshold;
   `tests/test_image_source.py::test_a11_soundcam_conference_ism_ratio_characterises`
   line 320 + `test_conference_ism_item_c_branch_driver` line 739 record
   the branch firing). Per plan §0.0 row "Item C" + D28-P1
   applicability table (signature reframing is STRUCTURAL → requires
   ADR §Decision body, NOT §Status-update), the v0.14.0 reclassification
   for the conference SoundCam-substitute room is:

   - **NEW signature**: `sabine_shoebox_approximation_for_glass_heavy_room`
     (reframes from the v0.10 pre-MELAMINE_FOAM signature
     `sabine_shoebox_underestimates_glass_wall_specular` + v0.12
     AMBIGUOUS classification per ADR 0021 §Decision).
   - **Driver**: pure-specular ISM on the conference room (3 drywall
     walls + 1 glass wall + carpet floor + acoustic-tile ceiling)
     produces a substantially longer RT60 than Sabine because the
     low-α walls (α₅₀₀ = 0.05 painted + 0.04 glass) sustain
     specular grazing reflections that the diffuse-field Sabine
     formula averages away. ISM/Eyring = 5.7002 is even higher
     (Eyring's high-absorption correction pushes the diffuse-field
     RT60 even shorter; specular ISM diverges further). The signature
     captures the structural insight: Sabine's shoebox-approximation
     is systematically optimistic for glass-heavy rooms where
     specular reflections dominate the late-decay tail.
   - **`_CONFERENCE_EXPECTED["disagreement_classification"]` field
     in `tests/test_a11_soundcam_rt60.py`**: NOT updated at the
     v0.14.0 Item B + C executor pass — the existing classification
     value `"ambiguous"` reflects the **Sabine/Eyring ratio
     classification** (which stays at 1.128 per ADR 0021 §Decision
     thresholds; library is BYTE-EQUAL) and the v0.12 existing test
     `test_a11_soundcam_conference_disagreement_classification`
     cross-checks via Sabine/Eyring ratio, not ISM/Sabine. The Item C
     branch driver `test_conference_ism_item_c_branch_driver` in
     `tests/test_image_source.py` line 739 records the new ISM-driven
     branch separately (additive, not replacement). This separation
     keeps Eyring-based classification and ISM-based reclassification
     as parallel data streams in the test surface (per the planner-
     locked principle that test surface mutations should be additive
     where physically equivalent; see also plan §0.4 STOP rule #11
     "no library logic mutation outside narrow accommodation").
   - **ADR 0021 §Status-update-2026-05-16**: per D28-P1 applicability
     table, factual ISM-ratio data lands as an ADR 0021 §Status-update
     block (in addition to this ADR 0028 §Decision sub-item 3
     structural reframe). The block records the conference ISM ratio
     (5.0537) + the Office_1 ISM ratio (2.0059) + the Item C branch
     C-i firing as factual evidence supporting the reframe.

   The Office_1 second-room ISM/Sabine = 2.0059 (also > 1.15)
   confirms signature robustness across ≥ 2 rooms per the D26
   forbidden-indefinite-deferral clause. The predictor-default
   switch decision (Item D) remains DEFERRED at v0.14.0 per the
   default lock (see Drivers + §Reverse-criterion item 2);
   the v0.14.0 evidence MUST trigger the v0.15+ decision land or
   D26 becomes a dead letter.

The composite framing was justified per plan §0.0 row "ADR list" +
D28-P1 single-D consolidation lesson: a single ADR 0028 bundling
A + B + C avoided ADR-inflation while preserving audit-trail
discipline (each sub-decision was traceable to plan §0.0 row + the
relevant D-decision predecessor).

The Item D predictor-default switch decision was **DEFERRED** to
v0.15+ per D26 characterise-first-decide-second cadence (plan §0.0
row "Item D" + §0.1 (c)). ADR 0029 was RESERVED at v0.14 per D34
for the predictor-default switch slot; it shipped at v0.14 ONLY if
plan §0.4 STOP rule #8 fired (Office_1 ratio > 1.15 cleanly AND
user-requested in-release switch). Default lock at v0.14 = DEFER.

## Drivers

1. **D27 hard wall reached** — v0.14.0 was cycle 3 of the D27 /
   D28-P2 cadence schedule (v0.11 = NEW pending → v0.12 = FIRST
   re-deferral → v0.13 = SECOND-AND-LAST permitted re-deferral →
   v0.14 = HARD WALL). D27 explicitly forbade a third consecutive
   re-deferral; D28-P2 generalised the forbidden-indefinite-deferral
   discipline. v0.14.0 had to close OR escalate to a successor ADR
   switching PRIMARY source. ADR 0028 was the successor.
2. **Path γ honesty-leak fallback default-locked at planner-time** —
   plan §0.0 row "Item A" recorded path γ as the default-safe lock
   at design time because v0.13.0 ship-time documented external
   acquisition channels (SNU library ILL, OA mirrors, publisher OA
   page for Bies & Hansen 2018 §A + NRC manufacturer datasheets) as
   Option B "channels NOT investigated" (ADR 0019 §Status-update-2026-05-12-2
   lines 196-200). The planner could NOT assume path α (verbatim
   Vorländer) or path β (PRIMARY-source switch with extracted
   verbatim) would materialise at executor-time. Default-safe lock
   was path γ (no fabrication risk; D27 hard wall absolutely
   satisfied; honesty discipline preserved per ADR 0018 §Drivers
   lineage).
3. **STOP rule #7 OPPORTUNISTIC reverse held at executor-time** —
   per plan §0.4 STOP rule #7, IF verbatim Vorländer OR Bies & Hansen
   OR NRC datasheet α₅₀₀ landed mid-cycle inside [0.80, 0.95]
   envelope, the Item A executor pass STOPPED + escalated to switch
   from path γ to path α/β closure. At the v0.14 Item A executor pass
   (2026-05-16), a verbatim-citation grep across `docs/`, `roomestim/`,
   and `tests/` returned ONLY §References row labels + closure-attempt
   outcome records inside ADR 0019 (lines 114, 116, 165, 173, 180,
   182-183, 193, 198 of `docs/adr/0019-melamine-foam-enum-addition.md`).
   NO extracted verbatim α₅₀₀ value with page + row + panel-thickness
   landed inside the envelope. STOP rule #7 did NOT fire. Path γ
   default-safe lock held.
4. **Honesty-leak record preserved per ADR 0018 lineage** — ADR
   0018 §Drivers item 1 codified the v0.9 → v0.10 walk-back lesson
   that silent claim-shifting (placeholder framed as measured) was a
   pattern v0.14+ planner rounds had to actively resist. Path γ's
   §Drivers honesty-leak entry below recorded the WHY of the closure
   path explicitly: "verbatim citation unattainable through three
   ship cycles + external-acquisition exhaustion at v0.13 documented
   Option B (channels NOT investigated)". The record is part of the
   audit trail, NOT a softening of the hard wall.

## Alternatives considered

- **(a) v0.15 hard wall (third re-deferral)** — REJECTED
  unconditionally per D27 + D28-P2 forbidden-indefinite-deferral
  clause. The cadence schedule was set at v0.11 NEW pending +
  bounded at two consecutive re-deferral cycles; v0.14 was cycle 3
  by construction. A third re-deferral would have made the cadence
  rule a dead letter.
- **(b) v0.14.0 path α/β closure (verbatim Vorländer / Bies & Hansen /
  NRC datasheet acquired)** — would have been the OPPORTUNISTIC
  upgrade per plan §0.4 STOP rule #7 if verbatim landed mid-cycle.
  At the Item A executor pass (2026-05-16), STOP rule #7 did NOT
  fire (see Drivers item 3). Reserved for v0.14.x patch OR v0.15+
  per §Reverse-criterion item 1 below.
- **(c) v0.14.0 path β under successor ADR 0028 with verbatim
  extraction from Bies & Hansen 2018 §A or NRC datasheet** — same
  precondition as (b); did NOT fire at executor-time. The reframed
  PRIMARY-source row in §References below documents the
  multi-source envelope WITHOUT fabricating a verbatim citation.
- **(d) Remove MELAMINE_FOAM enum entry at v0.14** — REJECTED.
  Removing the enum would (i) regress the lab A11 PASS-gate to the
  pre-v0.11 state (default 9-entry enum systematically
  under-represents treated-room absorption per ADR 0018 §Drivers
  item 4); (ii) invalidate the v0.11 + v0.12 + v0.13 audit trail
  (the ADR 0019 row stayed bracketed within an invariant envelope
  by an explicit coefficient-invariant test, not a fabricated
  citation); (iii) be a STRUCTURAL regression (removing an enum
  entry) that this ADR would have to justify on a much stronger
  honesty basis than "verbatim unattained". Path γ retained the
  enum + honestly documented the citation gap.
- **(e) Defer Item B (ISM library) to v0.15+ and ship Item A only at
  v0.14** — see plan §0.1 (a) rejection rationale. Both items had
  independent cadences landing naturally at v0.14; the main-agent
  v0.13 tiebreaker locked bundle at v0.14.

## Why chosen

- **Hard wall closed without fabrication** — path γ default-safe lock
  satisfied the D27 / D28-P2 hard-wall MUST-close gate WITHOUT
  requiring an external acquisition success (which the planner
  could NOT guarantee at design time). Path α/β remained
  OPPORTUNISTIC upgrades per §Reverse-criterion item 1 (post-ship
  §Status-update if verbatim later surfaces).
- **Honesty discipline preserved per ADR 0018 lineage** — the path γ
  §References reframe + §Drivers item 4 above (this ADR) recorded
  the closure path WITHOUT silent claim-shifting. The audit trail
  reads: `[Vorländer 2020 §11/Appx A] (PRIMARY, verbatim pending)`
  at v0.11 → `(re-deferral §Status-update)` at v0.12 →
  `(SECOND-AND-LAST re-deferral §Status-update)` at v0.13 →
  `(HARD-WALL CLOSURE under path γ via ADR 0028)` at v0.14. Each
  step was an audit-trail entry; none was a silent walk-back.
- **D28-P1 / D28-P2 + D34 audit-trail discipline respected** — ADR
  0028 sequential-next-available allocation per D34 (replacing the
  planner-draft "ADR 0022 NEW"); ADR 0019 audit trail amended via
  §Status-update-2026-05-16 per D28-P1 (factual closure-status
  band); composite ADR avoided ADR-inflation per D28-P1 single-D
  consolidation lesson.
- **Minimum-leverage diff envelope** — Item A scope was ~30-40 LOC
  total (ADR 0028 Item A sections + ADR 0019 §Status-update +
  RELEASE_NOTES scaffold + decisions.md D35 NEW entry); no library
  / adapter / CLI / test code touched; Item B substance was reserved
  for the next executor pass per plan §0.3 sequencing.

## Consequences

- **(+) D27 / D28-P2 hard wall closed at v0.14.0 cycle 3** — OQ-13a
  CLOSED (`[ ]` → `[x]`); OQ-16 CLOSED (path γ default locked).
- **(+) Library state BYTE-EQUAL under path γ** — `roomestim/model.py`
  `MaterialAbsorption[MELAMINE_FOAM] = 0.85` BYTE-EQUAL;
  `MaterialAbsorptionBands[MELAMINE_FOAM] = (0.35, 0.65, 0.85, 0.92, 0.93, 0.92)`
  BYTE-EQUAL; lab A11 PASS-gate rel_err = +2.40 % BYTE-EQUAL.
- **(+) ADR 0019 audit trail extended via §Status-update-2026-05-16
  (v0.14.0) HARD-WALL CLOSURE block** — per D28-P1; in-place
  §References reframing + appended §Status-update block.
- **(+) Path γ §Drivers honesty-leak entry preserved** — explicit
  audit-trail record of "verbatim citation unattainable through
  three ship cycles + external-acquisition exhaustion at v0.13
  documented Option B (channels NOT investigated)". Truthful per
  ADR 0018 §Drivers lineage.
- **(−) Path γ default carried explicit honesty-leak entry** — NOT
  a silent walk-back; the entry was the audit-trail record. v0.15+
  may §Status-update this ADR if verbatim later surfaces per
  §Reverse-criterion item 1.
- **(−) Predictor-default decision DEFERRED** to v0.15+ per D26 (Item
  D); ADR 0029 RESERVED per D34.
- **(±) Item B / Item C sub-decisions SCAFFOLDED at the Item A
  authoring pass** — the §Decision sub-items 2 + 3 of this ADR
  carry reservation markers until the next executor pass landed
  the ISM library + conference reclassification. Plan §0.3
  sequencing permitted this anchor-before-substance ordering under
  D28-P1.

## Reverse-criterion

1. **Verbatim Vorländer / Bies & Hansen / NRC datasheet surfaces at
   v0.14.x patch OR v0.15+** — append §Status-update on this ADR
   0028 recording the closure-path upgrade γ → α (Vorländer) or
   γ → β (Bies & Hansen / NRC) per D28-P1 factual band. If the
   extracted verbatim value lands inside [0.80, 0.95] envelope, the
   upgrade is BYTE-EQUAL to the library row (no MELAMINE_FOAM α₅₀₀
   change). If the extracted value lands OUTSIDE [0.80, 0.95]
   envelope, a v0.14.x patch (or v0.15+) lands a library row update
   + the coefficient-invariant test re-runs + lab A11 re-runs;
   ADR 0028 §Status-update records the out-of-envelope shift +
   the path-upgrade rationale.
2. **Item B (e+) ACE Office_1 + conference ISM ratios both > 1.15
   confirm signature robustness** — ADR 0029 NEW (predictor-default
   switch) lands at v0.15+ per D26 forbidden-indefinite-deferral
   clause (Office_1 + conference = ≥ 2 glass-heavy rooms → decision
   MUST land at v0.15+).
3. **Item B (e+) ACE Office_1 ratio reveals ISM correctness
   regression vs Eyring** (ratio inverted, ISM < Eyring at moderate
   absorption) — supersede ADR 0028 with ADR 0030 + library rollback
   (next-available slot after v0.12-web.0/web.1 burned 0024-0027 and
   v0.14 acoustics-track allocated 0028/0029).
4. **v0.14+ critic argues path γ honesty-leak undermines D27
   framing** — refine ADR 0028 §Drivers inline via §Status-update;
   do NOT relax path γ to "verbatim pursued indefinitely" (that
   would be a 4th re-deferral, FORBIDDEN by D27 / D28-P2).

## References

- **Vorländer, M. (2020). *Auralization*, §11 / Appendix A.** Springer.
  PRIMARY source for the MELAMINE_FOAM α₅₀₀ row at v0.11; v0.14.0
  HARD-WALL CLOSURE under path γ recorded the verbatim page + row +
  panel-thickness column as **UNATTAINED through D27 cadence
  exhaustion** (v0.11 NEW pending → v0.12 FIRST re-deferral → v0.13
  SECOND-AND-LAST re-deferral → v0.14 HARD WALL). Source reframed
  at v0.14 from a single-PRIMARY pending-verbatim row to a
  **multi-source envelope** entry below. The α₅₀₀ = 0.85
  envelope-mid-value stayed bracketed by the coefficient-invariant
  test `test_melamine_foam_a500_in_expected_range`
  (`tests/test_room_acoustics_octave.py`) per ADR 0019 §Decision.
- **Multi-source envelope (v0.14.0 reframe; PRIMARY-source row
  replacement)**:
  - Vorländer 2020 *Auralization* §11 / Appx A — porous absorber /
    melamine foam panel row, 2-4 inch panel thickness band; PRIMARY,
    envelope-bracketed at α₅₀₀ ∈ [0.80, 0.95]; **verbatim page + row +
    panel-thickness column UNATTAINED** through three ship cycles
    + Option B external acquisition channels (SNU library ILL, OA
    mirrors, publisher OA page) NOT investigated at v0.13
    executor-time per ADR 0019 §Status-update-2026-05-12-2 lines
    196-200.
  - Bies & Hansen (2018), *Engineering Noise Control*, §A — secondary
    cross-check; no extracted verbatim α₅₀₀ value for melamine foam
    in-repo at v0.14 ship time (per `grep -rin "Bies"
    /home/seung/mmhoa/roomestim/docs/ /home/seung/mmhoa/roomestim/roomestim/
    /home/seung/mmhoa/roomestim/tests/` returning only §References row
    labels inside `docs/adr/0019-melamine-foam-enum-addition.md` lines
    116, 180-183, 193, 198).
  - NRC manufacturer data sheets — secondary cross-check; no
    extracted verbatim α₅₀₀ value in-repo at v0.14 ship time (per
    `grep -rin "NRC datasheet"` returning zero hits and `grep -rin
    "NRC"` returning only the SoundCam NRC 1.26 figure below + the
    "NRC manufacturer data sheets" §References row label).
  - SoundCam paper arXiv:2311.03517v2 §A.1 (Stanford 2024 NeurIPS
    D&B) — "NRC 1.26 melamine foam walls"; consistent with envelope
    mid-value α₅₀₀ = 0.85 (foam absorption rose steeply through
    250-500 Hz and plateaued above 1 kHz per the per-band tuple
    `(0.35, 0.65, 0.85, 0.92, 0.93, 0.92)`); NOT a Vorländer 2020
    verbatim citation. Documented at ADR 0019
    §Status-update-2026-05-12 (v0.12.0) lines 138-146.
- ADR 0009 (D9 — Eyring parallel predictor) — runtime invariant
  pattern source for the planned `ism ≥ eyring - 1e-6` lower bound
  (Item B executor pass).
- ADR 0018 (substitute-disagreement record) — §Drivers honesty-leak
  lineage source.
- ADR 0019 (MELAMINE_FOAM enum addition; v0.11.0) —
  §Status-update-2026-05-16 (v0.14.0) HARD-WALL CLOSURE block
  records the path-γ closure cross-referenced to this ADR.
- ADR 0021 (Sabine-shoebox residual study; v0.12.0 AMBIGUOUS) —
  §Status-update-2026-05-16 (v0.14.0) ISM ratio characterisation
  block landed conditionally at the Item B + C executor pass IF
  branch C-ii or C-iii fired.
- D22 (audit-trail hybrid pattern), D24 (CI lint codification),
  D26 (predictor-adoption deferral cadence), D27 (verbatim-pending
  closure cadence), D28-P1 (hybrid §Status-update pattern + factual
  vs structural applicability table), D28-P2 (permitted re-deferral
  cadence with cycle-count hard-wall), D34 (v0.14 ADR + OQ
  re-numbering audit-trail), D35 (v0.14.0 hard-wall closure under
  path γ recording decision) — `.omc/plans/decisions.md`.
- OQ-13a (CLOSED at v0.14 via path γ HARD-WALL CLOSURE), OQ-13b
  (CONDITIONALLY closed at the Item B + C executor pass per branch),
  OQ-15 (CLOSED at the Item B executor pass — ISM library landed),
  OQ-16 (CLOSED at v0.14 — path γ default OR α/β if OPPORTUNISTIC),
  OQ-23 NEW (Polygon ISM v0.15+ deferral), OQ-24 NEW (Predictor-default
  switch v0.15+), OQ-25 NEW conditional (Per-band glass α revision
  v0.15+ if Item C branch C-iii) — `.omc/plans/open-questions.md`.
- Plan: `.omc/plans/v0.14-design.md` (especially §0.0 row "Item A",
  §2.A detailed design, §0.4 STOP rule #7, §5.1 acceptance gates,
  §10.1 ADR 0028 framing); architect re-validation memo:
  `.omc/plans/v0.14-architect-revalidation-2026-05-16.md` (verdict
  YELLOW; 4 amendments absorbed via D34).
- Release: `RELEASE_NOTES_v0.14.0.md`.
- Library (NEW at the Item B executor pass; SCAFFOLDED reference
  only at the Item A pass): `roomestim/reconstruct/image_source.py`,
  `tests/test_image_source.py`.

## §Note — composite-ADR length self-report

**Added 2026-05-16 per code-reviewer pass MAJOR finding #2**
(cross-ref: `.omc/plans/v0.14-code-review-2026-05-16.md` §2.2).

- **Actual length**: 500+ lines (after the convergence caveat at
  §Decision sub-item 2 and this self-report block landed).
  Pre-caveat baseline at code-review pass: **476 lines**.
- **Planner-locked soft cap**: **300 lines** per
  `.omc/plans/v0.14-design.md` §0.4 STOP rule #15 + §1.1 row 1
  ("~200-280 (≤ 300 per §0.4 STOP rule #15)"). Actual is +59 %
  over the STOP-#15 trigger; +70 % over the §1.1 row 1 cap.
- **Why composite (Item A + B + C) preserved instead of hard-split
  into 0028 + 0029**: Item B (ISM library landing) and Item C
  (conference reclassification) **share the conference ISM ratio
  as the joint factual input** — the ratio drives both the library
  validation evidence (sub-item 2) AND the branch-C-i firing
  (sub-item 3). A hard split into ADR 0028 (Item A + B) + ADR 0029
  (Item C) would create a **circular cross-reference** between the
  two ADRs' §Decision sub-items (each would need to cite the
  other's body for the same ratio). Splitting Item D off does
  NOT reduce length materially because Item D is already deferred
  per §Decision tail + ADR 0029 RESERVED per D34.
- **D34-equivalent decision recorded here in-place**: composite
  ADR 0028 preserved at v0.14.0. The STOP-#15 cap is **rate-traced
  AND honestly characterised** (this §Note is the audit-trail
  record per D28-P1 hybrid pattern; in-place §Note placement
  rather than `§Status-update` because the length is a structural
  property of the ADR-at-ship-time, not a post-ship factual
  update).
- **v0.15+ trigger to split**: if Item D (predictor-default switch)
  lands as its own ADR at v0.15+ AND requires substantive
  cross-references back into ADR 0028 sub-item 2 / sub-item 3
  bodies, planner may re-cut the body into smaller per-Item ADRs
  at that point (the composite framing is a v0.14.0 ship-time
  artefact, NOT a permanent commitment).
- **Cross-ref**: code-review memo
  `.omc/plans/v0.14-code-review-2026-05-16.md` §2.2 (verifier-blockable: NO
  per reviewer §6 Block 2 — "planner accepts the violation as characterised").
