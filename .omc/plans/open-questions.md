# roomestim — Open Questions

> **Status update 2026-05-03**: All 7 questions for v0.1 are RESOLVED in `.omc/plans/decisions.md` (D1–D7). This file is kept as a historical record. Each item below shows the resolution pointer and reversal criterion.

## roomestim-v0-design - 2026-05-03

- [x] **(D1)** Will roomestim be attached as a git submodule under `spatial_engine/third_party/`, or distributed via PyPI? — **Decision: standalone git repo for v0.1; submodule/PyPI choice deferred to v0.2 ADR.** Reverse if engine team requests immediate vendoring or maintenance cost > 1 day/month.
- [x] **(D2)** Does the engine team accept the proposed `room.yaml` shape (2.5D polygon + scalar ceiling)? — **Decision: not a v0.1 blocker; ship `version: "0.1-draft"` (Stage 1 permissive) and propose to engine in roomestim v0.2 after lab fixture exercise.** Reverse if ≥3/10 real-world files need schema patches after Stage 2 lock.
- [x] **(D3)** Is the closed `material` enum (8 entries) sufficient, or do we need a free-form fallback with a `custom_label` field? — **Decision: closed 8-entry enum with `unknown` as fallback; no `custom_label` in v0.1.** Reverse if ≥30% of surfaces across first 10 captures land in `unknown`.
- [x] **(D4)** Are the lab speakers in `lab_setup.md` already mounted, or are we placing them as part of the v0.1 acceptance test? — **Decision: assume NOT pre-mounted; A10 = scan → place → mount → tape-measure.** Reverse to regression-only mode if user confirms speakers were already mounted.
- [x] **(D5)** Should `aim_direction` be exported in `layout.yaml` (extension field) or only kept in roomestim's `PlacementResult`? — **Decision: export as `x_aim_az_deg` / `x_aim_el_deg` per-speaker extension keys (engine-ignored).** Reverse if engine team promotes `aim` to a first-class field.
- [x] **(D6)** Capture device availability for v0.1 acceptance gate: does the team have an iPhone Pro / iPad Pro for RoomPlan capture, or do we need to ship Polycam as the v0.1 first-class adapter instead? — **Decision: RoomPlan first-class, Polycam supported secondary; both adapters in v0.1; A10 flexes to whichever device captures on the day.** Reverse if P5 ships before P4 (Polycam becomes de facto first-class).
- [x] **(D7)** Should `room.yaml` include octave-band absorption coefficients for v0.1, or is single mid-band 500 Hz sufficient given ±20% RT60 acceptance tolerance? — **Decision: single mid-band 500 Hz only; octave-band defers to v0.3.** Reverse if engine reverb integration requires octave-band data.

All v0.1 implementation decisions are now locked. New questions raised during P0–P7 should be appended to a new section dated when raised.

---

## v0.5-design — 2026-05-06

> **Status update 2026-05-07**: All 5 questions RESOLVED via locked scope (partial-A + B). Resolutions recorded inline below; full rationale in `.omc/plans/v0.5-design.md` §0a. New decision (D15) will be appended to `decisions.md` at v0.5.0 commit.

- [x] **(OQ-1)** Eaton 2016 TASLP Table I — does the parallel `cwm:websearchwithme` research at `.omc/research/ace-table-i-acquisition.md` surface a viable acquisition path? — **Resolution: PARTIAL — dimensions (L×W×H) acquired from arXiv:1606.03365 Table 1 (TASLP supporting material, open access); materials remain TASLP-locked (paywalled). Scope locked to partial-A (dims-only) + B.** Reverse if TASLP material assignments later become available and disagree with current `ACE_ROOM_GEOMETRY` material strings.
- [x] **(OQ-2)** F4b enum coefficients — is `MaterialAbsorption[MISC_SOFT] = 0.40` and the `(0.20, 0.30, 0.40, 0.50, 0.60, 0.65)` band profile acceptable as representative-not-verbatim under the v0.3 honesty-marker policy? — **Resolution: APPROVED — representative-not-verbatim with honesty marker matches v0.3 `MaterialAbsorptionBands` precedent; `MISC_SOFT` row required to preserve `band-2 == legacy scalar` invariant.** Reverse if ≥1 adapter starts emitting `MISC_SOFT` and downstream consumer reports magnitude wrong.
- [x] **(OQ-3)** D14 reverse-trigger semantics — under Scenario A 5b, do we co-ship coefficient revision (a) or split (b)? — **Resolution: N/A under partial-A — D14 5b cannot evaluate "assignments correct" without F1 materials, so trigger does not fire. F4a stays DEFERRED.** Reverse if F1 materials acquired in v0.6+ window and 5b conditions then evaluate true.
- [x] **(OQ-4)** Stage-2 schema flip (D8) — keep Stage-1 at v0.5? — **Resolution: KEEP STAGE-1 — D8 binds Stage-2 to A10 lab-capture which has not happened; non-negotiable, not just a default.** Reverse if A10 ships in v0.5 (it is not in scope).
- [x] **(OQ-5)** ADR 0010+ numbering — confirm ordering. — **Resolution: ADR 0010 = ACE-geometry-verified (dims-only); ADR 0011 = MISC_SOFT-enum. Inverted from initial draft to put F1-partial headline first.** Reverse only if ADRs reordered before commit.

---

## v0.6-design — 2026-05-07

> **Status update 2026-05-08**: All 5 OQs RESOLVED via planner-locked defaults; executor confirmed at v0.6.0 ship time (no deviations). Full rationale in `.omc/plans/v0.6-design.md` §3 and `.omc/plans/v0.6-audit-findings.md`. New decision (D17) appended to `decisions.md` at v0.6.0 commit.

- [x] **(OQ-6)** Per-piece α table source — Vorländer 2020 *Auralization* §11 / Appx A vs Beranek 2004 *Concert Halls and Opera Houses* Ch.3 Table 3.1. — **Resolution: Vorländer 2020 §11 / Appx A primary; Beranek 2004 Ch.3 Table 3.1 cross-check for `lecture_seat` row only. Values shipped: office_chair α₅₀₀=0.50, stacking_chair α₅₀₀=0.15, lecture_seat α₅₀₀=0.45, table α₅₀₀=0.10, bookcase α₅₀₀=0.30 (m² Sabines per piece). Executor confirmed locked defaults at v0.6.0; cited rows recorded in `roomestim/adapters/ace_challenge.py` per-piece dict comments + ADR 0013 §References.** Reverse if a textbook re-read surfaces a value that differs by > 30% on any band.
- [x] **(OQ-7)** Per-room furniture mapping — `office_chair` vs `lecture_seat` for Meeting_1 / Meeting_2. — **Resolution: Meeting_1 / Meeting_2 → `office_chair` (movable padded chairs, not fixed theatre seats). Executor confirmed locked default at v0.6.0; mapping recorded in `_FURNITURE_BY_ROOM`.** Reverse if a Vorländer §11 "meeting chair" row is later identified.
- [x] **(OQ-8)** Plumbing — direct in `_room_case_for` factory vs separate helper `_misc_soft_surface_from_furniture(...)`. — **Resolution: separate helper (private; unit-testable in isolation). Executor confirmed locked default at v0.6.0; helper at `roomestim/adapters/ace_challenge.py::_misc_soft_surface_from_furniture` with 14 unit tests in `tests/test_misc_soft_furniture_budget.py`.** Reverse if helper has only one call site by ship date and adds no test surface (it does — default holds).
- [x] **(OQ-9)** Building_Lobby treatment in v0.6 — (a) exclude (cleanest), (b) per-area MISC_SOFT density, or (c) defer to separate ADR. — **Resolution: (a) EXCLUDE. v0.6.0 ships with `Building_Lobby` absent from `_FURNITURE_BY_ROOM`; surface synthesis helper returns `None` for Building_Lobby. Executor confirmed locked default at v0.6.0; v0.6 perf doc shows Building_Lobby Sabine 500 Hz unchanged from v0.5 (+1.425 s err Sabine, expected). Future ADR (v0.7+) re-evaluates Building_Lobby coupled-space modelling on its own terms.** Reverse only if a coupled-space ADR ships first.
- [x] **(OQ-10)** New `MaterialLabel.FLOOR_HARD` enum entry for hard-floored rooms with unspecified subtype (Lecture_1 / Lecture_2 / Building_Lobby). — **Resolution: NO new enum entry in v0.6. Executor confirmed locked default at v0.6.0; `MaterialLabel` enum has 9 entries unchanged from v0.5.0/v0.5.1. Existing v0.5.1 honesty caveat block in `ace_challenge.py` carries the indeterminacy.** Reverse if hard-floor subtype is later confirmed for any room (lab visit / author email) AND the confirmed subtype is not already in the enum.

---

## v0.8-design — 2026-05-09

> **Status update 2026-05-09**: 1 OQ raised by v0.8.0 ship (OQ-11 — v0.9+ ratification prerequisites). v0.8 verdict was null per ADR 0015 §Consequences — V3 combined ceiling/seat bracketing did not satisfy the |Lecture_2 err| ≤ 0.5 s envelope without regressing Meeting_1 / Meeting_2 by > +0.10 s @500 Hz Sabine vs V0. Full rationale in `.omc/plans/v0.8-design.md` and ADR 0015. New decision (D19) appended to `decisions.md` at v0.8.0 commit.

- [ ] **(OQ-11)** v0.9+ ratification prerequisites — under what conditions may v0.9 (or later) ratify a Lecture_2 bracketing variant as a new default in `ACE_ROOM_GEOMETRY` / `_PIECE_EQUIVALENT_ABSORPTION_*`? — **Resolution candidate (planner-locked default for executor confirmation at v0.9 ship time)**: ratification requires **all three** of (i) the variant closes Lecture_2 |err| ≤ 0.5 s @500 Hz Sabine; (ii) the variant does not regress {Lecture_1, Meeting_1, Meeting_2, Office_1, Office_2} by more than +0.10 s @500 Hz Sabine vs V0; (iii) **independent evidence** (lab visit, author email, textbook citation beyond Beranek 2004 / Vorländer 2020 §11) confirms the variant coefficient or material assignment. v0.8 ship verdict was null on (i)+(ii) for V3, so no v0.8 ratification candidate exists; v0.9 inherits the locked criteria. Reverse if a v0.9 critic verdict reframes any of (i)/(ii)/(iii) as too strict / too loose.

  **Reading on V4 bounding case** (`ROOMESTIM_BRACKET_V4=1`, ceiling=`wall_concrete`): bounding case is intentionally *not* a candidate for ratification (it is "what would close the gap entirely?", not "what is physically defensible?"). v0.9 perf-doc reading of V4 will continue to be characterising-only.

---

## v0.9-design — 2026-05-09

> **Status update 2026-05-09**: 1 OQ block raised by v0.9 design (OQ-12 covers a/b/c sub-questions on A10b in-situ timeline + AnyRIR watchlist trigger + ARKitScenes v0.10+ scoping). OQ-11 status reaffirmed (v0.9 does NOT ratify Lecture_2 variants — gates remain locked). D14..D19 invariants reaffirmed. Full rationale in `.omc/plans/v0.9-design.md` §0..§5 and ADR 0016 + ADR 0017. New decision (D20) will be appended to `decisions.md` at v0.9.0 commit.

- [ ] **(OQ-12a)** A10b in-situ user-lab timeline — under what circumstances does A10b (the original v0.1 acceptance gate; user's own venue scan + tape-measured corner GT + physical VBAP-N speaker placement) eventually ship? — **Resolution candidate (planner-locked default; user-volunteer-only)**: A10b ships only when the user has physical access + ~1 day calendar + a willingness to capture; it is NOT scheduled by v0.9. ADR 0016 §Reverse-criterion records that A10b retains override authority over A10a substitute findings (in-situ ALWAYS overrides substitute). Reverse if user provides a calendar slot for capture, OR if a v0.10+ critic verdict argues A10b should be re-scoped (e.g., scaled down to corner-only without speaker placement) to lower the activation barrier. **Status-update-2026-05-10b (v0.10.1)**: v0.11 will ship in-situ protocol DOC only (no capture commitment); A10b actual capture remains user-volunteer-only. **Status-update-2026-05-11 (v0.11.0)**: protocol DOC landed at `docs/protocol_a10b_insitu_capture.md` (minimal stub, 90 lines, per D25 doc-ahead-of-impl pattern); capture commitment UNCHANGED — still user-volunteer-only. ADR 0016 §Reverse-criterion unchanged. Schema marker stays `"0.1-draft"` (Stage-2 re-flip remains bound to ≥ 3 captures per D2 + ADR 0016; v0.11 has only 2 substitute rooms).

- [ ] **(OQ-12b)** AnyRIR (ICASSP 2026 / arXiv 2025-10) watchlist promotion criterion — when does AnyRIR move from WATCHLIST to candidate-for-integration? — **Resolution candidate**: AnyRIR is currently WATCHLIST-ONLY because it provides no geometry input/output and no RT60 output (direct value to roomestim is 0). Promotion criterion: AnyRIR releases a follow-up paper/dataset that ships *either* (i) per-RIR scan-mesh GT or (ii) Schroeder-derived RT60 against a simulated/measured benchmark. Until either of these lands, AnyRIR remains a passive item. Reverse if v0.10+ identifies a different angle of value (e.g., AnyRIR's blind-room-style invariance test could become an A11 robustness check).

- [ ] **(OQ-12c)** ARKitScenes (Apple, 2021) v0.10+ scoping — under what conditions does v0.10+ add ARKitScenes as a second public-dataset integration? — **Resolution candidate**: ARKitScenes is DEFERRED-not-rejected. Promotion criteria for v0.10+: (i) v0.9 SoundCam A10a substitute lands cleanly with sharpened priors on what mesh-format details matter (PLY normal handling, vertex-count thresholds, etc); (ii) the project sufficiently distinguishes commercial vs research roomestim use to make Apple's non-commercial license a non-blocker (or, alternatively, the project commits to a research-only branch); (iii) someone (user or executor) has the disk + bandwidth budget for the ~hundreds-of-GB scope. Reverse if a smaller subset of ARKitScenes (e.g., 50 representative scenes) is curated by upstream and shipped under a friendlier license, OR if v0.10 critic argues SoundCam-only is insufficient breadth for Stage-2 schema durability.

- **OQ-11 reaffirmation**: v0.9 ship does NOT ratify any Lecture_2 bracketing variant; ADR 0015 §Reverse-trigger criteria (i)/(ii)/(iii) remain unchanged. v0.9 deferred F4a / coupled-space / ratification work continues to OQ-11's gating; OQ-11 status is **OPEN, unchanged**. Future v0.10+ work that addresses Lecture_2 must satisfy OQ-11's full three-condition criterion before any default-state mutation in `ACE_ROOM_GEOMETRY` / `_PIECE_EQUIVALENT_ABSORPTION_*`.

---

## v0.10-design — 2026-05-10

> **Status update 2026-05-10**: 1 OQ block (OQ-13a..e) raised at v0.10 honesty-correction ship time. OQ-12a status ELEVATED priority under ADR 0016 §Reverse-criterion firing (in-situ A10b is now the ONLY non-tautological corner-extraction gate). OQ-12b/c statuses unchanged. OQ-11 reaffirmed unchanged. D14..D20 invariants reaffirmed; D21 NEW (v0.10 honesty correction). Full rationale in `.omc/plans/v0.10-design.md` §0..§5 and ADR 0018. ADR 0016 amended in place (§Status-update-2026-05-10 appended); ADR 0017 byte-equal.

- [x] **(OQ-13a)** v0.11+ MaterialLabel enum candidates for treated rooms — under what conditions does v0.11+ add `MELAMINE_FOAM` (NRC 1.26) + `FIBERGLASS_CEILING` (NRC 1.0) + `TILE_FLOOR` to the 9-entry MaterialLabel enum? — **Resolution candidate**: addition requires (i) paper-faithful α₅₀₀ + per-band coefficients sourced from Vorländer 2020 §11 / Beranek 2004 / Bies & Hansen 2018 / NRC manufacturer data sheets (per ADR 0011 / OQ-2 honesty-marker policy); (ii) the addition does not regress ACE corpus A11 (gated E2E) or default-lane MISC_SOFT tests; (iii) ≥ 2 SoundCam rooms (lab + conference) return to A11 ±20 % under paper-faithful material maps. Reverse if v0.11+ critic argues the enum addition introduces ≥ 1 silent honesty leak elsewhere (e.g., glass-heavy room residual still misses ±20 % even with new enums). **Amendment (v0.10.1, 2026-05-10b)**: PRIMARY source = Vorländer 2020 §11 / Appx A (matches ADR 0011 / OQ-2 / OQ-6 precedent); secondary cross-check = Bies & Hansen 2018 + NRC manufacturer data sheets. **Resolution-2026-05-11 (v0.11.0)**: MELAMINE_FOAM landed under ADR 0019 (α₅₀₀ = 0.85, planner-locked envelope per Vorländer 2020 §11 / Appx A, verbatim citation pending follow-up lookup). Lab fixture flip walls MISC_SOFT → MELAMINE_FOAM; §2.4 executor decision-point recorded `predicted = 0.162 s`, `rel_err = +2.40 %`, sub-branch A (PASS-gate recovered). FIBERGLASS_CEILING + TILE_FLOOR re-deferred to v0.12+ under NEW OQ-14.

- [ ] **(OQ-13b)** v0.11+ Sabine-shoebox residual study — does the conference -22.7 % residual (paper-faithful materials, default Sabine) reflect a Sabine-approximation effect for glass-heavy rooms, or a coefficient-source error? — **Resolution candidate**: a v0.11+ characterising study computing the ratio of mirror-image source method or ray tracing prediction vs Sabine on the same room would distinguish; if ratio > 1.15, it's a Sabine-approximation effect (predict to mitigate via Eyring or Millington-Sette); if ratio < 1.10, it's likely coefficient-sourcing. Reverse if v0.11+ retrieves a per-band paper-published RT60 (Figure 10 numerical extraction) that shifts the prediction-vs-measurement comparison materially.

- [ ] **(OQ-13c)** Cross-repo PR re-submission criteria — when does the spatial_engine `proto/room_schema.json` proposal restart? — **Resolution candidate**: per `.omc/research/cross-repo-pr-v0.10-deferred.md` 5-condition list. Reverse if spatial_engine team explicitly requests an interim Stage-1-permissive proposal (which would obviate Stage-2 re-flip dependency).

- [x] **(OQ-13d)** v0.10 critic verdict — what verdict does Critic give v0.10's disagreement-record framing + reverse-criterion firing? — **Resolution candidate (planner-locked default)**: Critic verdict ≥ 7/10 expected on (i) explicit walk-back of v0.9 over-claims; (ii) honest disagreement-record pattern; (iii) ratchet-safe schema revert; (iv) audit-trail preservation. Reverse if Critic flags any new honesty leak (e.g., the conference disagreement-record is itself a soft FAIL gate that protects the ±20 % invariant from drift, but the framing might be read as gate-weakening — Critic to weigh). Verdict received 2026-05-10 (Critic Opus, 7.6/10 composite); resolution-candidate stands; v0.10.1 patches OQ-13d-flagged residual issues.

- [ ] **(OQ-13e)** Live-mesh extraction (real A10a-substitute) — under what circumstances does v0.11+ add live-mesh corner extraction (alpha-shape / RANSAC / Hough on actual SoundCam PLY meshes) to replace the synthesised-shoebox revealed-tautology? — **Resolution candidate**: live extraction ships only when (i) the executor has SoundCam mesh download access; (ii) `floor_polygon_from_mesh` is augmented with non-convex polygon support per D6 deferred; (iii) corner err on at least 1 SoundCam room ≤ 10 cm against an authoritative GT (e.g., paper-published room dims acting as corner GT for axis-aligned rooms). Reverse if the v0.11+ executor confirms SoundCam meshes are not in fact convex-floored (which the v0.9 design risk register R-2 already flagged).

- **OQ-12a reaffirmation (PRIORITY ELEVATED)**: A10b in-situ user-lab timeline status ELEVATED priority under ADR 0016 §Reverse-criterion firing (per ADR 0018 §Decision item 4); in-situ remains the ONLY non-tautological corner-extraction gate at v0.10. OQ-12a body unchanged.

- **OQ-12b reaffirmation**: AnyRIR status unchanged from v0.9-design (WATCHLIST-ONLY).

- **OQ-12c reaffirmation**: ARKitScenes v0.10+ scoping status unchanged from v0.9-design (DEFERRED-not-rejected).

- **OQ-11 reaffirmation (v0.10)**: v0.10 does NOT ratify any Lecture_2 bracketing variant; ADR 0015 §Reverse-trigger criteria (i)/(ii)/(iii) remain unchanged. OQ-11 status **OPEN, unchanged**. v0.10 honesty correction is orthogonal to F4a / Lecture_2 ratification work.

---

## v0.10.1-patch — 2026-05-10b

> **Status update 2026-05-10b**: 4 NEW OQs (OQ-13f, g, h, i) raised at v0.10.1 ship time, derived from v0.10 critic verdict (7.6/10 composite) + v0.10 architect verdict (§Categorisation table). OQ-13d marked `[x]` resolved (verdict received). OQ-13a resolution candidate amended to specify Vorländer 2020 §11 / Appx A as PRIMARY for MELAMINE_FOAM α₅₀₀. OQ-12a status-update marker added (v0.11 will ship in-situ protocol DOC only; no capture commitment). OQ-11 / OQ-12b / OQ-12c / OQ-13b / OQ-13c / OQ-13e reaffirmed unchanged. New decision (D22) appended to `decisions.md` at v0.10.1 commit.

- [x] **(OQ-13f)** Disagreement-band asymmetry — lab `predicted_s_min/max=[0.235, 0.270]` window permits silent-pass on a hypothetical CARPET 0.30→0.20 perturbation (predicted=0.2693 ∈ band); the rel_err band [+45 %, +70 %] catches it (rel_err=+70.4 % barely fails) but with razor-thin margin. Should bands be tightened to ≤ ±5 % around the recorded signature, AND should structural-sign assertions (`assert rel_err > 0.40` lab; `< -0.10` conference) be added as a separate, redundant guard? — **Resolution candidate**: yes; v0.11 hybrid scope will tighten lab `predicted_s_max` to ≤ 0.265 (or remove entirely if lab returns to PASS-gate under MELAMINE_FOAM enum) AND add structural-sign assertion to conference test. Reverse if v0.11 critic argues the structural-sign assertion is itself a soft FAIL gate. **Resolution-2026-05-11 (v0.11.0)**: §2.4 executor decision-point landed sub-branch A (PASS-gate recovered; rel_err = +2.40 %). `_LAB_EXPECTED` replaced with PASS-gate values; lab umbrella renamed `test_a11_soundcam_lab_band_record`; NEW companion `test_a11_soundcam_lab_pass_gate_recovered`. Lab structural-sign assertion `assert rel_err < 0.20`; conference structural-sign assertion `assert rel_err < -0.10` added (band byte-equal). See ADR 0019.

- [ ] **(OQ-13g)** Audit-trail discipline for same-week-old ADRs — when an ADR (e.g., 0018) created at v0.X needs a same-week correction at v0.X.1, what is the canonical pattern? v0.10.1 sets precedent: hybrid (inline-edit + appended §Status-update-2026-MM-DDb block recording WHY). — **Resolution candidate**: codify in `.omc/plans/decisions.md` D22 (v0.10.1) that future same-week ADR corrections follow the hybrid pattern; pure-append-only with `<del>`/`<ins>` HTML markup is rejected as unreadable. Reverse if a future ADR has a structural error (not factual) — structural errors require ADR supersedure (new ADR + §Status: superseded), not in-place correction.

- [x] **(OQ-13h)** README-body-still-in-old-tense audit — v0.10's §Honesty-correction prepend pattern was correct, but `tests/fixtures/soundcam_synthesized/README.md` body lines 26-44 still described v0.9 placeholder regime in present tense. Should v0.11 codify a `git grep "we ship\|ship in v0.[0-9]"` audit pass as a CI lint or pre-commit hook? — **Resolution candidate**: yes; v0.11 hybrid scope adds a lightweight CI check that flags present-tense version-specific framing in fixture README + ADR + RELEASE_NOTES files. Reverse if the false-positive rate proves intolerable. **Resolution-2026-05-11 (v0.11.0)**: CI lint shipped via standalone `scripts/lint_tense.py` + `.github/workflows/ci.yml` step `Lint (tense)`. Scope: `tests/fixtures/**/README.md`, `docs/adr/*.md`, `RELEASE_NOTES_v*.md` (excluding current-version `RELEASE_NOTES_v0.11.0.md`). Block exclusion for `## §Status-update-` / `## §Honesty-correction-` (per D22). Per-line `# noqa: lint-tense` escape. Live-repo run at v0.11 ship flagged 0 files (well below STOP rule #7 threshold of > 3). See ADR 0020 + D24.

- [x] **(OQ-13i)** Mypy strict project commitment — `roomestim/adapters/ace_challenge.py:554-556` has 3 pre-existing strict mypy errors (`float(object)` casts); the project does not currently advertise mypy-strict cleanliness. Should it commit to strict cleanliness, or explicitly disclaim it? — **Resolution candidate**: deferred to v0.12+; v0.11 hybrid scope explicitly does NOT include mypy fixes (silent fix risks scope creep). Reverse if the project gains a downstream consumer (spatial_engine?) that depends on type-strict roomestim.

- **OQ-13d resolution annotation**: Verdict received 2026-05-10 (Critic Opus, 7.6/10 composite); resolution-candidate stands; v0.10.1 patches OQ-13d-flagged residual issues.

- **OQ-13a amendment (v0.10.1, 2026-05-10b)**: PRIMARY source = Vorländer 2020 §11 / Appx A (matches ADR 0011 / OQ-2 / OQ-6 precedent); secondary cross-check = Bies & Hansen 2018 + NRC manufacturer data sheets. Original OQ-13a body unchanged; this is an amendment to the resolution candidate only.

- **OQ-12a status-update-2026-05-10b (v0.10.1)**: v0.11 will ship in-situ protocol DOC only (no capture commitment); A10b actual capture remains user-volunteer-only.

- **OQ-11 / OQ-12b / OQ-12c / OQ-13b / OQ-13c / OQ-13e reaffirmation (v0.10.1)**: All other open questions UNCHANGED. v0.10.1 is factual-integrity-only and does not relitigate prior resolutions.

---

## v0.11-design — 2026-05-11

> **Status update 2026-05-11**: 4 OQs resolved at v0.11.0 ship time (OQ-13a, OQ-13f, OQ-13h, OQ-12a status-update). 1 NEW OQ raised (OQ-14 — FIBERGLASS_CEILING + TILE_FLOOR deferred to v0.12+). OQ-11 / OQ-12b / OQ-12c / OQ-13b / OQ-13c / OQ-13e / OQ-13g / OQ-13i reaffirmed unchanged. New decisions D23 + D24 + D25 appended to `decisions.md` at v0.11.0 commit. Full rationale in `.omc/plans/v0.11-design.md` §0..§13 and ADR 0019 + ADR 0020.

- **OQ-13a resolution annotation**: MELAMINE_FOAM addition landed under ADR 0019. FIBERGLASS_CEILING + TILE_FLOOR re-deferred under NEW OQ-14 below. §2.4 executor decision-point recorded `predicted = 0.162 s`, `rel_err = +2.40 %`, sub-branch A (PASS-gate recovered). MELAMINE_FOAM α₅₀₀ = 0.85 (planner-locked envelope per ADR 0019 §References, verbatim Vorländer 2020 §11 / Appx A citation pending follow-up lookup).

- **OQ-13f resolution annotation**: Lab umbrella renamed `test_a11_soundcam_lab_disagreement_record` → `test_a11_soundcam_lab_band_record`. NEW companion `test_a11_soundcam_lab_pass_gate_recovered`. Conference band byte-equal; redundant structural-sign assertion `assert rel_err < -0.10` added.

- **OQ-13h resolution annotation**: CI lint shipped via `scripts/lint_tense.py` + `.github/workflows/ci.yml` step `Lint (tense)`. Live-repo run at v0.11 ship flagged 0 files. ADR 0020 NEW.

- **OQ-12a status-update-2026-05-11**: Protocol DOC `docs/protocol_a10b_insitu_capture.md` landed at v0.11 (minimal stub; 90 lines; D25 doc-ahead-of-impl pattern). Capture commitment UNCHANGED — still user-volunteer-only.

- [ ] **(OQ-14)** FIBERGLASS_CEILING + TILE_FLOOR enum additions — under what conditions does v0.12+ add these to the now-10-entry MaterialLabel enum? — **Resolution candidate**: addition requires (i) paper-faithful α₅₀₀ + per-band coefficients sourced from Vorländer 2020 §11 / Appx A (or equivalent textbook per OQ-2 / OQ-6 precedent); (ii) a new substitute room (or A10b in-situ room) whose paper-faithful material map REQUIRES the new enum to close the A11 ±20 % gate; (iii) v0.12+ critic argues the addition does not introduce a silent honesty leak elsewhere. Reverse if A10b in-situ captures land and use only the existing 10-entry enum + MELAMINE_FOAM (FIBERGLASS_CEILING + TILE_FLOOR remain deferred indefinitely if no captured room paper-faithfully requires them).

- **OQ-11 / OQ-12b / OQ-12c / OQ-13b / OQ-13c / OQ-13e / OQ-13g / OQ-13i reaffirmation (v0.11.0)**: All other open questions UNCHANGED. v0.11 ships the 4-item hybrid scope (MELAMINE_FOAM + band tightening + CI lint + protocol DOC) and does not relitigate prior resolutions. OQ-13g remains codified in D22 (no new action). OQ-13i (mypy strict) UNCHANGED — deferred to v0.12+.

---

## v0.12-design — 2026-05-12

> **Status update 2026-05-12**: 4 OQs receive v0.12 status-update annotations (OQ-13a verbatim citation closure-attempt; OQ-13b conference characterising-study annotation; OQ-13f re-examination; OQ-13h reverse-criterion firing). 1 NEW OQ raised (OQ-15 — predictor-adoption decision deferred to v0.13+ per D26 policy). 0 OQs flipped from `[ ]` to `[x]` (OQ-13b stays OPEN under AMBIGUOUS classification). OQ-11 / OQ-12a/b/c / OQ-13c / OQ-13d / OQ-13e / OQ-13g / OQ-13i / OQ-14 reaffirmed unchanged. New decisions D26 + D27 appended to `decisions.md` at v0.12.0 commit. Full rationale in `.omc/plans/v0.12-design.md` §2.2-§2.6 and ADR 0021 + ADR 0019 §Status-update-2026-05-12 + ADR 0020 §Status-update-2026-05-12.

- **OQ-13a status-update-2026-05-12 (v0.12.0)**: Verbatim Vorländer 2020 §11 / Appx A citation closure attempted at v0.12 per D27 cadence. **Outcome**: Vorländer page + row + panel-thickness column verbatim citation **STILL PENDING** — v0.12 executor did not have direct textbook access. Closure-attempt outcome recorded in ADR 0019 §Status-update-2026-05-12 (D22 hybrid pattern; factual change → in-place + appended §Status-update). **Secondary-source corroboration landed**: SoundCam paper arXiv:2311.03517v2 §A.1 NRC 1.26 figure consistent with envelope mid-value α₅₀₀ = 0.85. α₅₀₀ value at v0.12 = **0.85 BYTE-EQUAL to v0.11**; lab A11 PASS-gate unchanged (rel_err = +2.40 %); STOP rules #5 + #7 did not fire. **Re-deferred to v0.13+** under D27 reverse-criterion (d) (verbatim source access-limited; v0.12 = FIRST of at-most-two consecutive re-deferral cycles permitted per D27; v0.13 = LAST permitted re-deferral; v0.14 = hard wall).

- **OQ-13b status-update-2026-05-12 (v0.12.0)**: Conference glass-heavy Sabine-shoebox residual characterising study landed at v0.12 (ADR 0021 NEW). **Empirical result**: `sabine_eyring_ratio = 0.449030 / 0.398101 = 1.128` (V = 59.697 m³; S_total = 98.220 m²; ᾱ = 0.218). Per planner-locked classification thresholds: ratio > 1.15 = Sabine-approximation effect; ratio < 1.10 = coefficient-sourcing issue; 1.10 ≤ ratio ≤ 1.15 = AMBIGUOUS. **Classification at v0.12**: **AMBIGUOUS** (ratio 1.128 in [1.10, 1.15] zone). Conference disagreement-record signature `sabine_shoebox_underestimates_glass_wall_specular` UNCHANGED at v0.12 (no structural ADR 0018 amendment under ambiguous classification; STOP rule #11 holds). **OQ-13b remains `[ ]` OPEN** — closure deferred to v0.13+ comparator upgrade per OQ-15 NEW below. Resolution-candidate revised to "v0.13+ mirror-image-source comparator (or ray tracing) required for further discrimination between Sabine-approximation regime and coefficient-sourcing issue".

- **OQ-13f re-examination-2026-05-12 (v0.12.0)**: Per `.omc/plans/v0.12-design.md` §0.1 Item L row + §2.5, the v0.11 OQ-13f resolution-candidate reverse-criterion "structural-sign assertion may become soft FAIL gate" was re-examined at v0.12 after lab returned to PASS-gate. **Outcome**: NO firing. Lab `assert rel_err < 0.20` and conference `assert rel_err < -0.10` structural-sign assertions are NOT soft FAIL gates because: (i) they were planned at v0.11 §2.4 sub-branch A as PASS-gate boundaries, NOT artefacts of a disagreement-record regime; (ii) at v0.11 ship time the lab rel_err = +2.40 % is 3.7σ inside the +20 % boundary (margin ≈ 0.18); (iii) the structural-sign assertion is the redundant guard, not the primary gate (`_LAB_EXPECTED.rel_err_min/max` is the primary band check). Lab + conference test bodies UNCHANGED at v0.12. If a v0.13+ critic argues margin is too loose (e.g., suggests tightening lab to `assert rel_err < 0.10`), tighten under a successor ADR — NOT at v0.12.

- **OQ-13h reverse-criterion-firing-2026-05-12 (v0.12.0)**: Lint scope expanded preemptively per v0.11 OQ-13h §Reverse-criterion. Three new file families added to `scripts/lint_tense.py::_scoped_files()`: `docs/perf_verification_*.md`, `docs/architecture.md`, `README.md`. **v0.12 first-run flag count**: **0 files flagged** on the expanded 5-family scope (well under v0.12 §0.4 STOP rule #6 threshold of > 5; 0 noqa markers required). Pattern + block-exclusion + per-line escape semantics UNCHANGED. ADR 0020 §Status-update-2026-05-12 records the expansion. NEW test `test_lint_tense_scope_includes_expanded_files` asserts the 3 new families remain in scope (preemptive guard against silent scope contraction).

- [ ] **(OQ-15)** Predictor-adoption decision deferred to v0.13+ per D26 policy — should v0.13+ ship Eyring or Millington-Sette as default predictor for glass-heavy rooms, OR ship per-band glass α revision (Vorländer 2020 §11 verbatim) WITHOUT predictor change, OR ship mirror-image-source comparator (new library code in `roomestim/predict/image_source.py`) before re-running the residual study? — **Resolution candidate (planner-locked default; depending on v0.13+ comparator upgrade)**: at v0.12 the conference Eyring/Sabine ratio = 1.128 landed in the AMBIGUOUS [1.10, 1.15] zone per ADR 0021 §Decision; the §2.4 decision-point therefore deferred the predictor-adoption decision pending a more discriminating comparator. v0.13+ resolution path: (a) **mirror-image-source comparator** (new library code `roomestim/predict/image_source.py`; ~300-500 lines; non-rectangular polygon reflection bookkeeping + image-source pruning + energy-decay integration) — if the mirror-image ratio shifts the classification to Sabine-approximation effect (ratio > 1.15), v0.14+ ADR 0022 ships Eyring as parallel-but-preferred predictor; (b) **per-band glass α revision** (Vorländer 2020 §11 verbatim cross-check on the GLASS row — currently `(0.18, 0.06, 0.04, 0.03, 0.02, 0.02)`) — if revision shifts classification to coefficient-sourcing issue, v0.13+ ships the GLASS row update WITHOUT predictor change; (c) **multi-room expansion** (≥ 1 second glass-heavy room from ACE corpus, e.g., Office_1 ~ 5 m² window) — provides confirming/disconfirming second data point. **Reverse**: per D26 reverse-criterion, if spatial_engine integration request lands at v0.12+ ship time, accelerate the predictor-decision to v0.13.0 (NOT v0.13+); per D27 reverse-criterion, if Vorländer 2020 access remains blocked through v0.13, switch PRIMARY source under successor ADR.

- **OQ-11 / OQ-12a/b/c / OQ-13c / OQ-13d / OQ-13e / OQ-13g / OQ-13i / OQ-14 reaffirmation (v0.12.0)**: All other open questions UNCHANGED. v0.12 ships the 4-item DELIBERATE-mode hybrid scope (OQ-13a closure-attempt + OQ-13b characterising + lint scope expansion + OQ-13f re-examination) and does not relitigate prior resolutions. OQ-12a capture commitment UNCHANGED (still user-volunteer-only; v0.11 protocol DOC preserved byte-equal). OQ-13c cross-repo PR stays WITHDRAWN per ADR 0018 §Reverse-criterion (≥ 3 captures requirement unmet; conference still in disagreement-record under ambiguous v0.12 classification). OQ-13e live-mesh extraction unchanged. OQ-13g D22 codification preserved. OQ-13i mypy strict still deferred. OQ-14 FIBERGLASS_CEILING + TILE_FLOOR re-deferred (no captured room requires them at v0.12).

---

## v0.13-design — 2026-05-13 (planner-pass; not yet shipped)

> **Status update 2026-05-13 (planner)**: 1 NEW OQ surfaced by v0.13 design pass (OQ-16 — Vorländer α₅₀₀ PRIMARY source path-α-vs-β lock at v0.14 hard wall). 1 OQ slated for resolution at v0.13 ship (OQ-13i — mypy strict baseline). 2 OQs slated for annotation at v0.13 ship (OQ-13a SECOND re-deferral; OQ-13h reverse-firing-2). OQ-15 explicitly DEFERRED to v0.14 DELIBERATE per main-agent tiebreaker (Critic-lean) — OQ-15 status UNCHANGED at v0.13 ship; v0.14 closes via ISM library. Full rationale in `.omc/plans/v0.13-design.md` §1 + §3 + §8.

- [ ] **(OQ-16)** Vorländer 2020 §11 / Appendix A vs Bies & Hansen 2018 *Engineering Noise Control* §A vs NRC manufacturer datasheets — which PRIMARY source closes the melamine foam α₅₀₀ verbatim-citation at the v0.14 D27 hard wall? — **Resolution candidate (planner-locked default at v0.13-design pass)**: path α (verbatim Vorländer 2020 acquisition pending; v0.13 = SECOND-AND-LAST permitted re-deferral; v0.14 = hard wall — closure MUST land OR successor ADR switches PRIMARY source). β (PRIMARY-source switch NOW at v0.13) REJECTED at v0.13 design time because no in-repo verbatim α₅₀₀ for melamine foam from Bies & Hansen 2018 §A or NRC datasheet exists at v0.12 ship time — `grep -rn "Bies\|Hansen" docs/ roomestim/` returns ONLY the ADR 0019 §References row naming Bies & Hansen as secondary cross-check (no extracted value). Switching PRIMARY source without an extracted verbatim value would be a fabricated-quote v0.9-style honesty leak (per ADR 0018 §Drivers / D22 audit-trail discipline). Reverse: if at v0.13 executor day OR v0.14 design pass, a verbatim α₅₀₀ becomes available from ANY of {Vorländer 2020, Bies & Hansen 2018, NRC manufacturer datasheet, SoundCam NRC 1.26 decomposition} AND lands inside [0.80, 0.95] invariant envelope, close OQ-13a immediately (path α-closure OR β PRIMARY-source switch under successor ADR 0022 per D27 reverse-criterion options (i)/(ii)/(iii)).

- **OQ-13a planner-pre-shipping note (v0.13-design)**: SECOND-AND-LAST permitted re-deferral cycle per D27. v0.14 = HARD WALL. ADR 0019 §Status-update-2026-05-12-2 will record the re-deferral at v0.13 ship; OQ-13a annotation appended at ship time.

- **OQ-13h planner-pre-shipping note (v0.13-design)**: reverse-criterion firing-2 scheduled for v0.13 ship — lint scope expansion-2 to cover the remaining `docs/*.md` files (i.e., the non-`adr/`, non-`perf_verification_*`, non-`architecture.md` subset) + `.omc/research/*.md`. ADR 0020 §Status-update-2026-05-13 will record the expansion at v0.13 ship under D22-P1 hybrid pattern (codified at v0.13 in D28 NEW).

- **OQ-13i planner-pre-shipping note (v0.13-design)**: scheduled CLOSURE at v0.13 ship via Item C (mypy full-repo `--strict` baseline enforced). 3 known errors at `roomestim/adapters/ace_challenge.py:554-556` + cascading reveals to be resolved up to §0.4 STOP threshold (50 errors net). `pyproject.toml [tool.mypy]` block ALREADY contains `strict = true` + `files = ["roomestim"]`; v0.13 enforces it (CI step rename `Type-check (mypy)` → `Type check (mypy --strict)`). NO duplicate `mypy.ini` at repo root.

- **OQ-15 reaffirmation (v0.13-design)**: explicitly DEFERRED to v0.14 DELIBERATE alongside D27 hard-wall closure. v0.13 = SHORT-mode 4-item admin bundle (Vorländer SECOND re-deferral + D28 NEW + mypy strict + lint-2 expansion-2); OQ-15 ISM library bundle is structurally its own DELIBERATE bundle per main-agent tiebreaker (Critic-lean). v0.13 does NOT touch `roomestim/predict/*` or open a new comparator path. OQ-15 status UNCHANGED.

- **OQ-11 / OQ-12a/b/c / OQ-13b / OQ-13c / OQ-13d / OQ-13e / OQ-13f / OQ-13g / OQ-14 reaffirmation (v0.13-design)**: all UNCHANGED. v0.13 admin bundle does not relitigate substantive prior resolutions. OQ-13b remains AMBIGUOUS pending v0.14 ISM ratio. OQ-13f re-examination already landed at v0.12 (NO firing). OQ-13g D22 codification preserved (and now GENERALISED into D28-P1 at v0.13). OQ-14 enum additions still unmotivated.

---

## v0.13-design — 2026-05-12 (ship-time annotations)

> **Status update 2026-05-12 (v0.13.0)**: 1 OQ RESOLVED at v0.13 ship (OQ-13i — mypy strict baseline enforced). 2 OQs receive ship-time annotations (OQ-13a SECOND re-deferral; OQ-13h reverse-criterion firing-2). All other OQs reaffirmed UNCHANGED. New decision D28 appended to `decisions.md` at v0.13. Full rationale in `.omc/plans/v0.13-design.md` + ADR 0019 §Status-update-2026-05-12-2 (v0.13.0) + ADR 0020 §Status-update-2026-05-13.

- **OQ-13a status-update-2026-05-12 (v0.13.0)**: Verbatim Vorländer 2020 §11 / Appx A citation closure attempted at v0.13 per D27 cadence. **Outcome**: Vorländer page + row + panel-thickness column verbatim citation **STILL PENDING** — v0.13 executor did not have direct textbook access; no library, ILL, or NRC datasheet path materialised. Closure-attempt outcome recorded in ADR 0019 §Status-update-2026-05-12 (v0.13.0) (D22 hybrid pattern + D28-P1). α₅₀₀ = **0.85 BYTE-EQUAL to v0.11 / v0.12**; lab A11 PASS-gate UNCHANGED (rel_err = +2.40 %). **Re-deferred under D27 SECOND-AND-LAST permitted re-deferral. v0.14 = HARD WALL.** Cross-ref: ADR 0019 §Status-update-2026-05-12 (v0.13.0), D27, D28-P1, OQ-16 NEW.

- **OQ-13h reverse-criterion-firing-2 annotation (v0.13.0)**: lint scope expansion-2 landed at v0.13 ship — `scripts/lint_tense.py::_scoped_files()` expanded to cover remaining `docs/*.md` files + `.omc/research/*.md`. ADR 0020 §Status-update-2026-05-13 records the expansion under D22-P1 hybrid pattern (codified at v0.13 in D28 NEW). **v0.13 first-run flag count**: 1 file flagged (`docs/weekly_progress_report_2026-05-11.md:204`); 1 `# noqa: lint-tense` annotation applied. Pattern + block-exclusion semantics UNCHANGED.

- **OQ-13i RESOLVED `[x]` at v0.13.0**: mypy `--strict roomestim/` returns "Success: no issues found in 29 source files" at v0.13 ship. Resolution path: `roomestim/adapters/ace_challenge.py:554-556` narrowing applied via `_geom_float` helper; CI step renamed `Type-check (mypy)` → `Type check (mypy --strict)`; default-lane regression guard test `tests/test_mypy_strict_baseline.py::test_mypy_strict_clean` shipped. `pyproject.toml [tool.mypy]` `strict = true` was already set; v0.13 enforces it end-to-end.

- **OQ-15 reaffirmation (v0.13.0)**: DEFERRED to v0.14 DELIBERATE UNCHANGED per main-agent tiebreaker (Critic-lean). v0.13 = SHORT-mode admin bundle; OQ-15 ISM library bundle is structurally its own v0.14 DELIBERATE.

- **OQ-11 / OQ-12a/b/c / OQ-13b / OQ-13c / OQ-13d / OQ-13e / OQ-13f / OQ-13g / OQ-14 / OQ-16 reaffirmation (v0.13.0)**: all UNCHANGED at v0.13 ship. OQ-16 (path-α-vs-β lock) remains OPEN pending v0.14 hard-wall closure. Context: planner pre-shipping notes above (Status update 2026-05-13 (planner)) apply unchanged.

---

## v0.12-web-design — 2026-05-15

## OQ-17 — HUTUBS subject-id stability across HRTF library updates (v0.12-web.0)

When TU Berlin re-issues the HUTUBS dataset (correction patches, additional subjects),
does `pp1` remain the canonical first subject AND remain anthropometrically equivalent
to the v0.12-web.0 bundled file?

Resolution candidate: SHA-256 pin + manual diff at every HUTUBS release. If `pp1` changes
byte-non-equal, re-record binaural golden hash and bump `0.12-web.0 → 0.12-web.1`.

Cross-refs: ADR 0026; D31.


## OQ-18 — HF Spaces cold-start budget for the bundled web demo (v0.12-web.0)

What is the measured cold-start wall time (Spaces build + first request) for the v0.12-web.0
deploy?

Resolution candidate: measure once at executor-time after first deploy. If > 90 s, switch to
a Docker-based Space or trim deps.

Cross-refs: §4 S3 (pre-mortem); ADR 0024.


## OQ-19 — Binaural WAV byte-exact reproducibility across pyroomacoustics versions (v0.12-web.0)

Does pinning `pyroomacoustics==0.7.X` (or 0.9.X) guarantee byte-exact output across host
CPU architectures (Intel x86_64 vs ARM64)?

Resolution candidate: record golden hash on x86_64 Linux Python 3.11; CI gate on the same
architecture; mark the byte-exact test as `@pytest.mark.xfail(condition=platform.machine() != "x86_64")`
if cross-arch reproducibility proves infeasible.

Cross-refs: ADR 0025; `tests/web/test_binaural_renderer.py::test_binaural_render_byte_exact_golden`.

---

## v0.12-web.1-design — 2026-05-15b

## OQ-20 — glTF binary (`.glb`) byte-equal reproducibility across trimesh versions (v0.12-web.1)

Does `trimesh.load("lab_room.glb", force="mesh").vertices` return bit-identical ndarrays
when trimesh upgrades from 4.0 → 4.x → 5.x?

Resolution candidate: likely non-issue — glTF binary buffer is little-endian IEEE-754 by
spec and trimesh round-trips through `np.frombuffer`. Pin `trimesh>=4.0,<5` in
`pyproject.toml` IF the v0.12-web.1 CI flags any byte drift. Otherwise leave the lower
bound permissive and re-record fixtures at the v0.13-web.0 or v0.14 boundary if trimesh
majors. Also covers the glTF axis-convention caveat: for files exported with a Z-up root
transform, `MeshAdapter` returns geometrically valid but axis-swapped floor/ceiling
projections (documented in ADR 0027 § "Consequences" and `RELEASE_NOTES_v0.12-web.1.md`
§ "Known gaps").

Cross-refs: §3-P2; ADR 0027.


## OQ-21 — `.ply` files with vertex colour but no faces (points-only degenerate case) (v0.12-web.1) — CLOSED v0.20.0

**CLOSED (v0.20.0, 2026-05-28)** — no-faces guard landed (D66; ADR 0027
§Status-update-v0.20.0). `MeshAdapter._room_model_from_mesh` now rejects a
points-only PLY with a clear `ValueError("MeshAdapter: mesh has 0 faces
(points-only PLY); a surface mesh with triangular faces is required.")` right
after the `(N, 3)` vertex-shape check, before the undefined convex-hull path.
New fixture `tests/fixtures/points_only.ply` (vertices only, 0 faces) +
`tests/test_adapter_mesh.py::test_mesh_adapter_points_only_ply_raises` lock it.

What does `MeshAdapter` do with a PLY upload that contains vertices but no triangular faces
(a degenerate point-cloud export)?

Resolution candidate: at v0.12-web.1 ship, `trimesh.load(path, force="mesh")` returned a
`Trimesh` with 0 faces; the existing `vertices.shape[1] != 3` guard did NOT catch this.
Resolution candidate: add a `if hasattr(loaded, "faces") and len(loaded.faces) == 0: raise
ValueError("PLY contains points-only, no triangular faces")` guard at v0.12-web.2 if a user
reported it. Documented as a known degenerate case in `RELEASE_NOTES_v0.12-web.1.md`
§ "Known gaps". Reverse: if v0.12-web.1 verifier flagged a CI segfault on a real
points-only `.ply` upload, hotpatch in v0.12-web.1 itself.

Cross-refs: §3-P1; ADR 0027; D66.


## OQ-22 — `_TEMP_REAPER` 4 h `atexit` window tightening (v0.12-web.1)

Should `_temp_reaper`'s 4 h `atexit` window become a per-submit TTL instead — e.g. delete
a tempdir 30 min after `_on_submit` returned regardless of process state?

Resolution candidate: at v0.12-web.1 ship, 4 h `atexit` was sufficient for HF Spaces
(containers cycle ≤ 24 h; the 8-entry deque covered the typical session). Resolution
candidate: if OQ-18 measurement (cold-start budget) revealed containers cycle < 1 h, tighten
to 30 min at v0.12-web.2 or v0.13-web.0.

Cross-refs: §3-P4; D32.


## OQ-26 — HUTUBS URL long-term stability + GitHub mirror backup (v0.12-web.4)

Is the TU Berlin DepositOnce bitstream URL for HUTUBS zip stable long-term?
Is there a GitHub mirror of the pp1 SOFA that could serve as a fallback?

**Context**: ADR 0029 §A documents that HUTUBS is NOT auto-downloaded (1.36 GB).
The manual extraction path via `--extract-hutubs` depends on the TU Berlin URL.

Resolution candidate: if TU Berlin URL rotates (v0.12-web.x), update URL constant in
`scripts/fetch_web_data.py:HUTUBS_ZIP_URL` + append §Status-update to ADR 0029.
A GitHub mirror of only pp1 SOFA (~10 MB) would allow auto-download at v0.13-web.0.

**Reverse**: if HUTUBS URL is confirmed stable over ≥2 years, close OQ-26 with
"URL stable; no mirror needed". If pp1 SOFA appears on sofaconventions.org or a
public GitHub, add auto-download at v0.12-web.5.

**Cross-refs**: ADR 0029 §A, ADR 0026 §OQ-17, D36.


## OQ-27 — Auto-fetch SHA-256 pin missing for KEMAR + LibriVox (v0.12-web.4) [CLOSED v0.12-web.5]

**Status**: CLOSED at v0.12-web.5 — real digests pinned (KEMAR + LibriVox),
`fetch_kemar`/`fetch_librivox` forward `expected_sha256=`, ADR 0029 §A
Status-update-v0.12-web.5 records closure. Test `test_fetch_kemar_passes_sha256_pin`
asserts the pin is forwarded. See `scripts/fetch_web_data.py:KEMAR_SOFA_SHA256` /
`LIBRIVOX_MP3_SHA256` for the actual digests.

---


`scripts/fetch_web_data.py` ships `_download_file(expected_sha256=...)` infrastructure
but `fetch_kemar` / `fetch_librivox` pass `expected_sha256=None`, triggering only a
WARNING log (`fetch_web_data.py:86-89`). Production downloads are therefore not
integrity-verified — a compromised upstream or MITM-capable network could deliver
modified SOFA/MP3 bytes that the demo would silently accept.

**Context**: ADR 0029 §A originally implied "SHA-256 검증" but v0.12-web.4 ships
without pinned digests. Code-review 2026-05-17 (MAJOR-2) flagged the ADR↔code gap.
ADR 0029 §A was patched 2026-05-17 to note "pin deferred to v0.12-web.5 per OQ-27"
to restore honesty (per ADR 0018 honesty discipline + D35).

Resolution candidate at v0.12-web.5:
1. Run `curl -L $KEMAR_SOFA_URL | sha256sum` and `curl -L $LIBRIVOX_MP3_URL | sha256sum`
   from a trusted environment, paste digests into `KEMAR_SOFA_SHA256` /
   `LIBRIVOX_MP3_SHA256` constants.
2. Wire `expected_sha256=` into `fetch_kemar` + `fetch_librivox`.
3. Remove the WARNING-only branch in `_download_file:86-89`.
4. Update ADR 0029 §A §Status-update-v0.12-web.5 to "pin landed".

**Reverse**: if upstream digests rotate frequently (e.g. LibriVox transcoding) the pin
becomes brittle — revisit OQ-27 with a per-release manifest file instead.

**Cross-refs**: ADR 0029 §A, ADR 0018 (honesty discipline), D35, code-review 2026-05-17 MAJOR-2.


## OQ-28 — Upstream URL stability monitoring (KEMAR + LibriVox + HUTUBS) (v0.12-web.6)

KEMAR (github.com/spatialaudio), LibriVox (archive.org), HUTUBS (api-depositonce.tu-berlin.de)
URLs는 SHA-256 pin이 있더라도 URL 자체가 rotate / 404 되면 auto-fetch 영구 실패.
현재 v0.12-web.6에서 모니터링 메커니즘 없음.

**Context**: v0.12-web.5에서 SHA pin landed (OQ-27 closed)이지만 URL availability는
별도 위험. v0.12-web.5 평가의 P3 (제품 완성도) 항목.

Resolution candidate at v0.12-web.7 또는 그 이후:
1. `.github/workflows/url-monitor.yml` NEW — 주 1회 cron으로 3 URL에 HEAD 요청 + SHA 재계산
2. mismatch / 404 시 GitHub Issue 자동 생성 또는 Slack 노티
3. CI 실패 → ADR 0029 §Status-update + URL rotation patch 사이클 트리거

**Reverse**: URL rotation 빈도가 < 1회/년이면 모니터링 ROI 낮음 → cron 주기 분기별로
완화하거나 OQ-28 close. > 1회/분기면 위 actionizer 우선순위 P1로 격상.

**Cross-refs**: ADR 0029 §A, OQ-26 (HUTUBS URL specific), OQ-27 (SHA pin closed).


## OQ-29 — HUTUBS pp1 SOFA GitHub mirror (v0.12-web.6 follow-up to OQ-26)

OQ-26 의 일부 — pp1 SOFA만 (10 MB)을 GitHub releases / Hugging Face Datasets 등에
미러로 호스팅하면 1.36 GB HUTUBS zip 다운로드 우회 + cold-boot에 사용 가능.

**Context**: ADR 0029 §A가 HUTUBS를 manual-only로 분류한 주된 이유가 1.36 GB 크기.
pp1 SOFA만 별도 미러하면 KEMAR과 같은 auto-fetch 경로에 추가 가능.

Resolution candidate:
1. Brinkmann et al. (TU Berlin)에 mirror 요청 (CC BY 4.0 라이선스 명시) — author 컨택 필요.
2. 자체 mirror — license 검토 후 GitHub Release / HF Datasets / SoundCam GitHub 등에 호스팅.
3. v0.12-web.x 패치에 mirror URL + SHA pin landed.

**Cross-refs**: ADR 0029 §A, OQ-26, OQ-28.


## OQ-30 — Per-wall α decomposition for ISM mixed-material walls (v0.15.0)

`predict_rt60_default()` at v0.15.0 collapses all `kind == "wall"` surfaces into
one area-weighted-average α before feeding the 6-tuple `absorption_coeffs` to
`image_source_rt60`. Mixed-material walls (e.g., one glass wall + three painted
walls) lose specular vs diffuse information at the ISM boundary.

**Context**: ADR 0030 §Trade-off acknowledges this simplification. The ISM library
itself supports per-surface α at the API level (6-tuple per shoebox), but the
default-wrapper layer averages — extending requires a wall-direction mapping
(which surface goes to wall_x_neg vs wall_x_pos etc).

Resolution candidate at v0.15.x or v0.16.0:
1. Extend `_shoebox_surface_areas_and_alphas()` to map each `kind == "wall"` to
   the nearest cardinal direction by surface-normal vector (Newell's method).
2. If unique mapping is ambiguous (e.g., 5 walls in a 4-wall shoebox), fall back
   to area-weighted average + emit WARNING.
3. Re-run lab A11 + ACE Office_1 + conference characterisation; ratios must
   stay within ±15% of v0.15.0 baseline (otherwise ADR 0028 §Decision sub-item 2
   `ism ≥ eyring - 1e-6` invariant must be re-validated).

**Reverse**: if measured-room characterisation shows < 5% improvement vs
area-weighted average across ≥ 3 mixed-wall rooms, close OQ-30 as "ROI
insufficient".

**Cross-refs**: ADR 0030 §Trade-off, ADR 0028 §Decision sub-item 2,
`roomestim/reconstruct/predictor.py:_shoebox_surface_areas_and_alphas`, D38.

## OQ-31 — Multi-engine schema target support (v0.18+, 2026-05-18)

**Question**: Current `--validate-engine PATH` validates against a single
`spatial_engine/proto/geometry_schema.json`. If users need to target different
audio engines (SPARTA, IEM Plugin Suite, custom engine), how should multiple
schema targets be supported?

**Current state**: `write_layout_yaml` accepts `schema_path_override: str | None`
pointing to a single engine repo directory. No multi-target support.

**Deferral reason**: No user request yet. Single engine (spatial_engine) covers
all current known use-cases. Multi-target adds complexity (plugin loader, target
name registry) with unclear ROI.

**Trigger conditions** (D26 forbidden-indefinite-deferral applied):
- ≥ 1 user reports need for a non-spatial_engine schema target, OR
- spatial_engine schema has a breaking change requiring side-by-side validation.

**Evaluation cadence**: v0.17 cycle end — must decide by v0.18 (hard wall per D26).

**Resolution candidates**:
1. `--validate-engine PATH:target_name` syntax with a target registry in
   `roomestim/export/engine_registry.py`.
2. Plugin loader: `--validate-engine-plugin my_engine_plugin.py`.
3. Close as WONTFIX if only spatial_engine is ever targeted.

**Cross-refs**: ADR 0033 §E, D42.

---

## v0.17.0 신규 OQ (2026-05-19)

**OQ-33 — Mesh / Polycam / ACEChallenge adapter object 자동 인식 (v0.18+)**
현재 `MeshAdapter` (Polycam 등)와 `ACEChallengeAdapter`는 `objects=[]` placeholder.
mesh segmentation 정보 없이 column/door/window 자동 추출 미지원.

**Deferral reason**: BoundingBox 클러스터링 알고리즘 미안정. 사용자 보고 없음.
RoomPlan adapter는 ARKit `RoomAnchor` segment label로 자동 인식 가능 (별도 작업).

**Trigger conditions** (D26 forbidden-indefinite-deferral 적용):
- 사용자가 RoomPlan 외 phone-scan 출처에서 객체 자동 추출 요청 ≥ 1건, OR
- mesh-only fixture에 object ground-truth 도입.

**Evaluation cadence**: v0.18 cycle 종료 시 재검토; v0.19까지 결정 강제 (D26).

**Resolution candidates**:
1. mesh segmentation API (Polycam Pro) object label 직접 소비.
2. BoundingBox 클러스터링 + geometric heuristic (height/aspect ratio 기반 kind 추론).
3. 사용자 수동 annotation UI (ADR 0034 evolve helper 활용).

**Cross-refs**: ADR 0034 §D (Scope OUT), ADR 0030 §Status-update-v0.17 Item Q 정직성 노트.

---

**OQ-34 — 곡선/원형 객체 (cylinder column) 지원 (v0.19+)**
v0.17.0 `ObjectKind` Literal은 `"column"` (rectilinear box only)만 지원.
cylinder / arch / circular pillar는 polygonal 근사 (n=16 등) 없이 표현 불가.

**Deferral reason**: 현재 shoebox ISM 모델은 rectilinear surface가 기본 단위.
곡선 근사는 n개 삼각형 surface → ISM order 50에서 계산 비용 n배 증가.
사용자 보고 없음.

**Trigger conditions** (D26 forbidden-indefinite-deferral 적용):
- 사용자가 cylinder/arch column 지원 요청 ≥ 1건, OR
- acoustic 모델이 non-rectilinear surface를 지원하는 버전으로 교체.

**Evaluation cadence**: v0.19 cycle 시작 시 재검토.

**Resolution candidates**:
1. polygonal 근사 (n=8~16 sided polygon) + 기존 `Object` kind="column" 확장
   (`shape: Literal["box", "cylinder"]` 신규 필드).
2. `ObjectKind` Literal 확장 (`"column_cylinder"`) + ADR 0034 §Status-update.
3. 전용 `CurvedObject` dataclass (ADR 0036).

**Cross-refs**: ADR 0034 §D (Scope OUT — "곡선/원형 객체").

---

**OQ-35 — USDZ/gLTF acoustic metadata 표준 (v0.19+)**
v0.17.0 `--with-acoustics-sidecar` 플래그는 `<basename>.acoustics.json` sidecar를
생성하지만, schema는 `"v0.1-internal"` (비표준).

**Deferral reason**: USD `<material binding>` acoustic extension 표준 없음.
Apple RoomPlan API acoustic metadata 포맷 미공개. Vision Pro spatial audio SDK
acoustic import 경로 미확인.

**Trigger conditions** (D26 forbidden-indefinite-deferral 적용):
- Vision Pro / Apple RoomPlan API acoustic metadata 표준 공개, OR
- 사용자가 외부 도구 (Unreal MetaSounds, SPARTA) acoustic import 요청 ≥ 1건.

**Evaluation cadence**: v0.19 cycle 시작 시 재검토.

**Resolution candidates**:
1. USD `UsdShade.Material` acoustic custom attribute 정의 (roomestim 자체 extension).
2. gLTF `KHR_materials_acoustic` 확장 제안 (Khronos Working Group 참여).
3. sidecar schema `"v0.2"` 안정화 (외부 표준 없이 roomestim 자체 spec).

**Cross-refs**: ADR 0035 §E (sidecar format), ADR 0035 §G (reverse-criterion).

---

**OQ-36 — `room.yaml` schema 다운그레이드 export flag (`--schema 0.1`) (v0.18+)**
이미 forward-ref 됨 (ADR 0030 §Status-update-v0.17 + ADR 0034 §B + decisions.md D44).
v0.18 에서 정식 allocate 후 deferral. 외부 consumer 가 0.2-draft `room.yaml` 의
`objects` unknown field 로 fail 보고 시 `roomestim export --schema 0.1` (objects
생략 + schema_version 0.1-draft write) 도입.

**Trigger conditions** (D26): 외부 consumer fail 보고 ≥ 1건 (현재 0건 —
`spatial_engine` 은 `layout.yaml` 만 소비). **Evaluation cadence**: v0.19 cycle 시작.
**Resolution candidates**: (1) `--schema 0.1` flag + `room_yaml.py` 분기. (2) `objects`
를 구 schema 에서 `x_objects` extension key 로. (3) 영구 deferral (보고 0건이면 YAGNI).
**Cross-refs**: ADR 0034 §B, ADR 0030 §Status-update-v0.17.

---

**OQ-37 — `PlacedSpeaker.notes` round-trip (engine schema `x_notes` extension) (v0.19+)**
현재 `notes` 는 `write_layout_yaml` 이 직렬화 안 함 + reader 가 `""` 로 채움. nudge
편집 시 notes 보존 불가. engine `geometry_schema.json` per-speaker
`additionalProperties: true` 이므로 `x_notes` extension key 추가 가능하나 engine 측
협의 (소비/무시 정책) 필요.

**Trigger conditions** (D26): 스피커별 메모 보존 요청 ≥ 1건 또는 nudge 워크플로
notes 손실 보고. **Evaluation cadence**: v0.19 cycle 시작. **Resolution candidates**:
(1) `x_notes` per-speaker extension key. (2) sidecar `.notes.json`. (3) 영구 비-목표
(notes = in-memory annotation 전용). **Cross-refs**: ADR 0036 §C / §G(iv).

---

**OQ-38 — `target_algorithm` 전체 round-trip (`x_target_algorithm` engine extension) (v0.19+)**
현재 `read_placement_yaml` 은 `regularity_hint` + `x_wfs_f_alias_hz` 키 존재로
WFS-vs-VBAP 만 추론 → `target_algorithm ∈ {DBAP, AMBISONICS}` 인 layout 은 read 시
"VBAP" 로 붕괴 (D50 Level 1 계약에서 명시적 제외). nudge round-trip 후 알고리즘
라벨이 바뀐다.

**Trigger conditions** (D26): DBAP/AMBISONICS layout 을 nudge round-trip 후 알고리즘
라벨 손실 보고 ≥ 1건, OR engine 이 algorithm-aware 검증 도입. **Evaluation cadence**:
v0.19 cycle 시작. **Resolution candidates**: (1) top-level `x_target_algorithm`
extension key (writer emit + reader 복원; WFS 추론보다 우선). (2) reader 추론 확장
(regularity → algorithm — 단 DBAP/AMBISONICS 는 불충분). (3) 영구 deferral (placement
알고리즘은 `place` 재실행으로 결정; 편집은 좌표만). **Cross-refs**: ADR 0036 §C, D50.

---

## v0.18.2 OQ status-updates (2026-05-24)

### OQ-33 status-update (v0.18.2 — residual narrowed, re-deferred to v0.20)

**Previous status**: deferred from v0.17 with evaluation cadence v0.19 (D26 hard
wall).

**v0.18.2 resolution (D54)**: OQ-33 의 manual-annotation 부분은 **이미 충족됨**
(v0.17 에서 shipped):
- Core: `evolve_room_add_object` / `evolve_room_remove_object` (`roomestim/edit.py`)
- Web: `roomestim_web/object_add.py` Object Add Mode (kind-specific input forms +
  input validation + direct `evolve_room_add_object` calls)
- Acoustic fold: `predictor._objects_to_surfaces()` + `_objects_to_wall_alpha_overrides()`
  (column → +5 surfaces, door/window → wall α override per D46)

**Residual (still open)**: "non-RoomPlan adapter (Mesh/ACE) 의 무인 자동 객체
추출" — `MeshAdapter` 와 `ACEChallengeAdapter` 는 여전히 `objects=[]` placeholder.
RoomPlan adapter 의 `_extract_objects()` (ARKit category substring matching) 는
mesh/ACE 에 범용화 불가 (소스 데이터 부재).

**Re-deferred to v0.20 (hard wall)**: 두 자동-추출 후보 —
- 후보 1 (Polycam Pro segmentation API): 비공개 API, Linux-CI 불가, fixture 없음
- 후보 2 (bbox clustering + geometric heuristic): greenfield "미안정", GT fixture
  부재로 검증 불가

두 D26 trigger 모두 미충족 (0 user reports; 0 mesh-only GT fixtures). D54 결정.
v0.20 hard wall — 재-재연기 금지. trigger 미충족 시 WONTFIX 정식 종결.

**OQ-33 is NOT closed** (residual = adapter auto-detection remains real).

**Reverse-criterion (D54)**: (a) non-RoomPlan 출처 자동 추출 요청 ≥ 1건, OR
(b) mesh-only object-GT fixture repo 도입, OR (c) Polycam Linux-buildable
segmentation export 공개.

**Cross-refs**: D54, ADR 0034 §Status-update-v0.18.2, ADR 0030 §Status-update-v0.18.2
Item X.

---

**OQ-39 — ADR 0030 §Status-update split (v0.21+)**

ADR 0030 (`docs/adr/0030-predictor-default-switch.md`) 는 v0.18.2 기준 7개
§Status-update 블록을 포함하는 ~438 라인 파일. 파일 크기가 커짐에 따라 내비게이션
불편 가능성 존재.

**Deferral reason**: doc-only re-defer 사이클에서 438-line ADR 을 분할하면 no
functional gain 에 audit-trail discipline (D22 — append-only, no retroactive edits)
위반 위험. D26 YAGNI — 현재 reader pain 보고 0건.

**Trigger conditions** (D26 forbidden-indefinite-deferral 적용):
- 파일 > ~600 lines (현재 ~438), OR
- documented navigation-pain / readability report ≥ 1건.

**Evaluation cadence**: v0.21 cycle 시작 시 재검토.

**Resolution candidates**:
1. ADR 0030 본문(§A–§E) 을 `docs/adr/0030-predictor-default-switch-core.md` 로
   분리 + status-update 블록만 원본 파일에 잔류.
2. `docs/adr/0030-status-updates/` 디렉토리 분할 (버전별 파일).
3. 영구 deferral (파일 크기 ~600 lines 이하 유지 가능 시 YAGNI).

**Cross-refs**: ADR 0030, D22 audit-trail-discipline.

### OQ-39 §Status-update-v0.22.1 (2026-05-28 — CLOSED, D73)

D26 forced-decision satisfied. Trigger condition (b) fired: the v0.22.0
multi-perspective security audit produced documented navigation-pain reading
ADR 0030 §A–§E under 10 §Status-update blocks (477 lines). v0.21-cycle
re-evaluation cadence was 1 cycle overdue (v0.22.0 absorbed security focus,
not eligible).

**Resolution**: split-by-section (Option 1 from this OQ's Resolution
candidates). §A–§E + §Consequences + §Reverse-criterion + §References stay in
`docs/adr/0030-predictor-default-switch.md` (~145 lines post-split); 10
§Status-update blocks (in original file order: v0.15.1, v0.15.2, v0.16,
v0.16.1, v0.17, v0.18, v0.18.1, v0.18.4, v0.18.3, v0.18.2) relocate
byte-equal to NEW companion
`docs/adr/0030-predictor-default-switch-status-updates.md`. ADR 0039 NEW
codifies the split mechanism as reusable. D22 preserved (relocation, not
retroactive edit).

**[x] CLOSED**. Decision: D73. ADR refs: ADR 0030 (split landing), ADR 0039
(meta-ADR).

**Reverse-criterion (재개 조건)**: companion file > 800 lines, OR
documented navigation-pain in the companion file → escalate to per-version
subdirectory split per ADR 0039 §Reverse-criterion item 1.

---

## v0.18.4 OQ status-updates (2026-05-25)

### OQ-36 status-update (v0.18.4 — CLOSED / WONTFIX, D57)

D26 hard-wall forced decision (v0.19-cycle cadence commitment). Trigger = "외부
consumer fail 보고 ≥ 1건" — **verified 0건** (git log / docs / artifacts 전수
grep, 0 hits). Sole real consumer (`spatial_engine`) consumes only `layout.yaml`
and never reads `room.yaml` (`docs/adr/0034-object-schema.md:142`). Library
write-path (`room_model_to_dict(schema_version="0.1")` + `write_room_yaml(
schema_version=...)`) already exists; CLI `--schema` flag = YAGNI (0 consumer).
D26 hard-wall is satisfied by a real decision (WONTFIX), not another re-defer.

**[x] CLOSED (WONTFIX)**. Decision: D57. ADR ref: ADR 0034 §Status-update-v0.18.4.

**Reverse-criterion (재개 조건):** (a) `room.yaml` 직접 소비 외부 consumer 가
0.2-draft `objects` unknown field 로 fail 보고 ≥ 1건, OR (b) spatial_engine 이
`room.yaml` 소비 도입하면서 0.1-draft 만 지원 → v0.20+ ADR 0034 §Status-update
기록 + CLI 플래그 신설.

---

### OQ-37 status-update (v0.18.4 — re-deferred to v0.20, D60)

Trigger 미충족: per-speaker note 보존 요청 0건; nudge notes-loss 보고 0건.
`notes` = in-memory annotation only (ADR 0036 §C Level-1 명시 제외; reader 미복원).
Engine `geometry_schema.json` `additionalProperties: true` → `x_notes` 기술적
가능, engine 소비/무시 정책 협의 필요.

**신규 cadence: v0.20 cycle 시작 시 재검토** (OQ-38 과 동일 사이클 — 한 번의
engine-schema 협의로 묶음 평가). Decision: D60. ADR ref: ADR 0036 §Status-update-v0.18.4.

**Reverse if (조기 escalate):** per-speaker note 보존 요청 ≥ 1건 OR nudge
notes-loss 보고 ≥ 1건 → `x_notes` extension key + engine 협의.

---

### OQ-38 status-update (v0.18.4 — re-deferred to v0.20, D61)

Trigger 미충족: DBAP/AMBISONICS nudge round-trip 라벨-손실 보고 0건; engine
algorithm-aware 검증 미도입. `placement_yaml_reader.py:67-76` WFS-vs-VBAP 추론만;
DBAP/AMBISONICS → "VBAP" 붕괴 (D50 Level-1 명시 제외, 의도적 설계).

**신규 cadence: v0.20 cycle 시작 시 재검토** (OQ-37 과 동일 사이클). Decision: D61.
ADR ref: ADR 0036 §Status-update-v0.18.4.

**Reverse if (조기 escalate):** DBAP/AMBISONICS 라벨 손실 보고 ≥ 1건 OR engine
algorithm-aware 검증 도입 → `x_target_algorithm` extension key.

---

### OQ-34 status-update (v0.18.4 — re-deferred to v0.21, D58)

Trigger 미충족: 사용자 cylinder/arch column 요청 0건; acoustic 모델 = rectilinear
shoebox ISM (non-rectilinear 교체 없음). 곡선 근사 = ISM surface 수 n배 → 계산비용
n배 (실측 needs 없는 성능회귀).

**신규 cadence: v0.21 cycle 시작 시 재검토** (v0.20 OQ-33 hard wall 과 충돌 회피;
OQ-34 한 사이클 뒤). Decision: D58. ADR ref: ADR 0034 §Status-update-v0.18.4.

**Reverse if (조기 escalate):** cylinder/arch column 요청 ≥ 1건 OR acoustic 모델
non-rectilinear 교체 → `shape: Literal["box","cylinder"]` 필드 검토.

---

### OQ-35 status-update (v0.18.4 — re-deferred to v0.21, D59)

Trigger 미충족: Apple/Khronos acoustic-metadata 표준 **미공개**; Unreal/SPARTA
등 외부 도구 import 요청 0건. sidecar `"v0.1-internal"` 동작 중; 외부 표준 없는
상태에서 spec 동결 = premature (표준 등장 시 재작업 비용).

**신규 cadence: v0.21 cycle 시작 시 재검토** (외부 표준 의존 — OQ-34 와 동일
사이클 묶음). Decision: D59. ADR ref: ADR 0035 §Status-update-v0.18.4.

**Reverse if (조기 escalate):** Vision Pro/Apple RoomPlan acoustic metadata 표준
공개 OR 외부 도구 acoustic import 요청 ≥ 1건 → ADR 0035 §E 확장 (§G
reverse-criterion (iv)).


---

**OQ-40** — gradio `col_count` Dataframe-kwarg deprecation noise (web lane).
`roomestim_web/material_override.py:196` and `roomestim_web/object_add.py:218`
pass `col_count=(N, "fixed")` to a gradio `Dataframe`, which emits a
Deprecation/UserWarning under newer gradio. SEPARATE from D62 (which is adapter
test-migration only). **Deferred** — a fix is a gradio-6 runtime-source migration
(`roomestim_web/**`), out of scope for the v0.18.5 test-hygiene PATCH; requires a
gradio version-compat assessment first. **Reverse-trigger**: address when a
gradio upgrade is undertaken, or if ≥1 user reports the web-lane warning noise.
Allocated v0.18.5 (D62 cycle).


---

**OQ-42 (CLOSED, opened v0.19.0, closed v0.20.0, 2026-05-28)** — hardcoded
engine-schema absolute path fallback. `roomestim/export/layout_yaml.py:57–59`
`_DEFAULT_ENGINE_SCHEMA_PATH = /home/seung/mmhoa/spatial_engine/proto/geometry_schema.json`
is used when neither `SPATIAL_ENGINE_REPO_DIR` env nor `--validate-engine` flag
is set. Not a correctness bug — a portability/UX wart, orthogonal to the
v0.19.0 ①/②/③ scope (④, deferred). Blast radius is real:
`tests/test_export_layout_yaml.py:29–42` and `tests/test_engine_toggle.py:160–288`
depend on this fallback + ENV/CLI precedence (D42 / ADR 0033); cli help
(`cli.py:141/260`) promises the fallback. Replacing it with a hard error would
require coordinated test + help-text + ADR 0033 amendments. **Cadence: v0.20.**
**Reverse-trigger**: address when the engine-schema location is parameterized or
when a non-author environment hits the missing-path failure.

**CLOSED (v0.20.0, 2026-05-28)** — resolved by option (a) descriptive error
(D65; ADR 0033 §Status-update-v0.20.0). The documented `CLI > ENV > default`
chain (ADR 0033 §B) is RETAINED — `_DEFAULT_ENGINE_SCHEMA_PATH` stays as the
documented fallback (the path is not yet permanently unavailable, so §E's
breaking-removal trigger is NOT yet fired). The fix replaces the silent deep
`FileNotFoundError` with one descriptive error
(`kErrEngineSchemaNotFound`) raised from a single source
(`_assert_schema_file_exists`, inherited by all three open sites) that names
`SPATIAL_ENGINE_REPO_DIR`, `--validate-engine`, and `--no-engine-validation`.
Behavior + byte output are unchanged on any host where the schema resolves;
only hosts where it is genuinely absent see the new (actionable) error. CLI help
(`cli.py`) updated to drop the "hardcoded" wording. New test
`tests/test_export_layout_yaml.py::test_engine_schema_missing_raises_descriptive`;
`tests/test_engine_toggle.py` docstrings updated to the error-on-missing
semantics.

---

**OQ-43** — `edit.py` dual "surface index" frame (the wall_index bug's TWIN). — CLOSED v0.21.0

**CLOSED (v0.21.0, 2026-05-28)** — shared resolver landed (D68; ADR 0037
§Status-update-v0.21.0). `roomestim/model.py` gained `wall_surfaces(room)` (the
single walls-only authority) + `surface_index_for_wall(room, wall_ordinal)`
(bridges a walls-only ordinal to its full-`room.surfaces` index; `IndexError` out
of range). The four predictor walls-only filters + the web viewer filter now route
through `wall_surfaces`. `evolve_room_material` / `_bulk` full-list-index semantics
are byte-identical (additive only; no shipping caller passes a walls-relative index
there yet). Characterization test `tests/test_surface_index_frame.py` pins
`wall_surfaces(room)[k] is room.surfaces[surface_index_for_wall(room, k)]` across
two adapter orderings (RoomPlan `[floor, ceiling, wall×4]` → ordinal 2 = full index
4; inline synthetic trailing-floor order — TODO 1 resolved: inline synthetic
`RoomModel` chosen as cheapest, no mesh fixture / trimesh dependency). Revert-sanity
confirmed the test fails under the naive identity resolver (load-bearing).

---

Surfaced by the v0.20.0 multi-perspective audit (critic). `evolve_room_material`
(`roomestim/edit.py:218`) and `evolve_room_materials_bulk` (`:254-261`) index into
the **full** `room.surfaces` list, while `Object.wall_index` resolves on the
**walls-only** filtered list (predictor `reconstruct/predictor.py:293`, viewer
`roomestim_web/viewer.py:252` — unified walls-only in v0.19.0/ADR 0037). Two
different integer "surface index" frames coexist in the model with no shared
resolver. Adapter surface order is NOT uniform (`roomplan.py:294`
`[floor,*ceilings,*walls]`; `mesh.py` `[floor,ceiling,*walls]`;
`ace_challenge.py` has a trailing floor), so a future "edit wall N material"
feature wiring a walls-relative index into `evolve_room_material` would patch the
WRONG surface. NOT a current regression (no shipping caller passes a walls-relative
index there), but the exact latent condition that produced the v0.19.0 defect.
**Recommended next correctness cycle.** Fix: a shared
`surface_index_for_wall(room, wall_ordinal)` resolver + a characterization test
pinning `evolve_room_material` and `wall_index` to the same `Surface` on a nonzero
index across all adapters' orderings (the analogue of `test_wall_index_frame.py`).
**Reverse-trigger**: any feature exposing a wall-relative material edit. Allocated
v0.20.0 (audit).

**OQ-44** — silent state/predictor changes on out-of-range or edited input. — CLOSED v0.21.0

**CLOSED (v0.21.0, 2026-05-28)** — all three behaviors fixed (D69 + D70; ADR 0037
§Status-update-v0.21.0; ADR 0031 §Status-update-v0.21.0). (a) The predictor
ISM→Eyring fallback rationale now carries the offending exception
(`... ISM fallback to Eyring ({type(exc).__name__}: {exc})`, ×2 sites) —
rationale-string-only, `rt60_s` byte-equal for the fallback path; valid-input
negative control byte-equal `1.9190766987173207`. New test
`tests/test_objects_acoustic_invariant.py::test_out_of_range_wall_index_rationale_carries_index`
pins `"999"` in both scalar + per-band rationale. (b) `wall_index` upper-bound
`0 <= wall_index < len(wall_surfaces(room))` enforced at THREE independent entry
points — `read_room_yaml` (raise), `object_add._on_add_object` (user-facing error,
room unchanged), `RoomPlanAdapter._room_model_from_sidecar` (raise). TODO 3
resolved: `RoomPlanAdapter` DOES emit objects (`_extract_objects` maps
door/window/column with `wall_index`), so the adapter guard is LIVE, not dead.
Revert-sanity confirmed the reader-bound test fails when the guard is removed
(load-bearing). (c) `evolve_surface` band-promotion is now gated on
`surf.absorption_bands is not None` (scalar `absorption_500hz` stays
unconditional); `test_evolve_surface_material_only` split into
single-band-stays-None + per-band-still-promotes (commit-coupled to the gate per
D70). The graceful Eyring fallback is PRESERVED — (a) only makes the downgrade
diagnosable, never fatal.

---

Surfaced by the v0.20.0 audit (critic, reproduced). (a) An out-of-range
`wall_index` on a door/window makes `_objects_to_wall_alpha_overrides` raise, which
`predict_rt60_default` catches (`predictor.py:479-491`) and silently downgrades the
**whole room** ISM→Eyring (materially changing RT60), with the offending index
discarded from the rationale; `object_add.py:201-202` accepts any `wall_index>=0`
with no upper bound, and the reader (`room_yaml_reader.py`, `roomplan.py:169`)
applies no bound either. (b) `evolve_surface` (`edit.py:91-93`) unconditionally
promotes a single-band surface (`absorption_bands=None`, the `octave_band=False`
ingest default) to per-band on a material change, silently shifting the per-band
predictor branch for edited rooms. **Deferred.** Fix: bound `wall_index <
len(walls)` at object-add/reader time (user-facing error) + surface the bad index
in the predictor rationale; gate the band promotion on the source surface already
having bands. **Reverse-trigger**: any user report of an unexpected RT60 jump after
an object add / material edit. Allocated v0.20.0 (audit).

**OQ-45** — web public-deployment hardening (HF Spaces). — CLOSED v0.22.0
(2026-05-28, D71, ADR 0038). Surfaced by the v0.20.0
security audit. The tool is publicly deployable (`app.py`, `sdk: gradio`) and the
audit found (no CRITICAL/RCE; YAML safe_load uniform, no eval/exec/pickle/shell):
(a) **unbounded untrusted-mesh parsing** — `trimesh.load(force="mesh")`
(`mesh.py:69`) reached from web upload (`app.py`/`pipeline.py`) with NO file-size /
vertex-count cap → trivial DoS on a shared Space; (b) **stale dependency
environment with known CVEs** (starlette/aiohttp/pillow/requests/urllib3/werkzeug
per `pip-audit`) and a README `sdk_version: "4.0.0"` vs installed gradio 6.14.0
mismatch; (c) **info-leak** — `_DEFAULT_ENGINE_SCHEMA_PATH` (`layout_yaml.py:58`,
the `/home/seung/...` dev path) and other raw exception text are echoed into
web-user-facing error strings (`app.py` `_on_export`/`_on_apply_overrides`),
disclosing the dev username/layout (residual of OQ-42 — error message improved but
the hardcoded constant + verbose web echo remain); (d) **tempdir reaper**
(`app.py:59-68`) globs the shared system temp root (cross-session deletion risk on
a shared host); (e) **latent crash** — `material_override.py:105`
`on_apply_overrides` raises `AttributeError` on a list-shaped JSON payload (only
dict accepted; no type guard). **Deferred** — out of scope for the local/CLI core;
gate on an actual public-deployment decision. Fix when deploying publicly: cap
upload size + vertex count (`gradio max_file_size` + a `MeshAdapter` bound), pin a
lockfile + `pip-audit` in CI, scrub absolute paths/raw exceptions from web-facing
errors, namespace the tempdir reaper per-PID, type-guard `on_apply_overrides`.
**Reverse-trigger**: decision to expose the Gradio demo publicly. Allocated v0.20.0
(audit). **CLOSED v0.22.0 (2026-05-28, D71+D72, ADR 0038)** — reverse-trigger treated
as fired (the audit + the v0.21 fix program authorized the hardening pass). Landed:
(a) `MeshAdapter` env-overridable byte + vertex caps (ADR 0038) — the byte-cap is
the pre-`trimesh.load` parse-memory bound, the vertex-cap a post-parse
hull-projection guard — plus a Gradio `max_file_size` cap **bound on the
`build_demo()` Blocks object** (`demo.max_file_size`) so gradio's server honors it
regardless of launch path (gradio 6.14.0 `Blocks` ctor rejects the kwarg; only
`launch()` accepts it, and HF's root `app.py` never runs `roomestim_web`'s
`__main__` guard — so the original launch-only cap was inert in production; the
root entrypoint now also carries it); (b) **all** web-facing error-string echo
sites scrubbed — not just the original three. The v0.22.0 first pass scrubbed only
`app.py` `_on_submit`/`_on_apply_overrides_wrapper`/`_on_export`; a security
re-review (D72) found the **Speaker Nudge** path
(`speaker_nudge.py:_on_nudge_speaker`) still echoed `validate_placement()`'s
schema-path-bearing error list verbatim. The exhaustive scrub now covers
`speaker_nudge.py` (validate echo + nudge `ValueError`/`IndexError`),
`object_add.py` (`_on_add_object`/`_on_remove_object` `{exc}` branches), and
`material_override.py` (`on_apply_overrides` `JSONDecodeError`/per-entry `{exc}`) —
full detail logged server-side; `validate_placement` itself is intact (CLI wants
the path) and `_DEFAULT_ENGINE_SCHEMA_PATH` is kept (ADR 0033 §Status-update-v0.22.0);
a new load-bearing web test drives the real `validate_placement` with a missing
schema and asserts no `/home/`/`geometry_schema` reaches the user; (c) per-PID
tempdir reaper (`roomestim_{pid}_*` glob + creation prefixes); (d)
`on_apply_overrides` list-input type guard. The dependency-CVE work is
declaration-only this cycle (`pyproject` `gradio>=4.44`, README
`sdk_version: "6.14.0"`; installed env unaffected, RT60 byte-equal); the CI
`pip-audit` + lockfile follow-up is split out to **OQ-46**.

---

**OQ-46** — CI `pip-audit` + dependency lockfile for the web extras (HF Spaces).
Split from OQ-45 (D71, v0.22.0, 2026-05-28). The v0.22.0 dep work was
declaration-only (`pyproject` floor bumps + README `sdk_version` reconcile) so the
canonical env and all gates stay byte-identical. The residual **process/infra**
piece — not a code change — is: (a) add a lockfile (`pip-compile`/`uv lock` or
equivalent) pinning the resolved web-extras tree, and (b) wire `pip-audit` into CI
so a freshly-resolved install is checked against the advisory DB on every push.
This catches a transitive CVE re-introduced by a floor that resolves to a newer
(or, on an old host, older) line than the canonical 6.14.0 env. **Deferred** —
requires a CI runner + a lockfile-maintenance cadence decision; out of scope for
a code-only cycle. **Reverse-trigger**: a public deployment lands AND a CI
pipeline exists to host the audit step. Allocated v0.22.0 (D71).

---

## v0.21.0-edit-predict-correctness — executor open items - 2026-05-28

Planner-pass implementation-choice items, resolved during the v0.21.0 executor
pass (no reverse-trigger; not OQ-numbered project questions):

- TODO 3 — RESOLVED: `RoomPlanAdapter` DOES emit `Object`s on its parse path
  (`_extract_objects` maps door/window/column categories with `wall_index`), so
  the adapter-side wall_index bound is LIVE, not a dead guard. Added in
  `_room_model_from_sidecar` post-assembly.
- TODO 1 — RESOLVED: inline synthetic trailing-floor `RoomModel` chosen as the
  cheapest second-adapter ordering for `tests/test_surface_index_frame.py` (no
  mesh fixture / trimesh dependency), proving `surface_index_for_wall`
  ordering-independence alongside the RoomPlan `[floor, ceiling, wall×4]` case.

---

## Feature-expansion 설계 사이클 (2026-05-29 — 설계 문서, 미구현)

> 멀티-페이즈 자율 작업 (`.omc/plans/feature-expansion-roadmap.md`). 산출물은 **설계 ADR draft**
> (Status=PROPOSED); 코드/테스트는 아직 없다. 각 ADR 은 architect 설계 + critic 리뷰를 거쳤다.

- **(OQ-23 재기재 / B4 Polygon ISM)** — polygon/non-rectilinear ISM RT60 예측. OQ-23 은 v0.14.0
  NEW 였으나 curated open-questions 에서 누락되어 있었다 → 여기 재기재. **설계 = [ADR 0040](../../docs/adr/0040-polygon-ism-design.md)**
  (REVISED, critic 1 CRITICAL + 3 MAJOR 반영). 권장: pyroomacoustics 재사용(선택지 b) + core
  lazy-import fallback(§C2) + 3-티어 predictor cascade(shoebox ISM / polygon ISM / Eyring).
  ADR 0030 §Reverse-criterion item 3 충족 경로. 구현 deferred (PR1-4 제안; PR1 degenerate-shoebox
  스파이크 게이트 통과 전 cascade 연결 금지). **Status: 설계 완료, 구현 OPEN.**
  - 파생 신규 OQ 제안: coupled-space marker 필드(RoomModel), non-shoebox 측정 GT 코퍼스,
    pra `measure_rt60` sparse-RIR fit 신뢰성, lazy-import 재현성 비대칭 — 모두 ADR 0040 §OQ 참조.

- **(B5 Ambisonics 배치 / OQ-38 연결)** — AMBISONICS enum stub 정식화.
  **설계 = [ADR 0041](../../docs/adr/0041-ambisonics-placement-design.md)** (REVISED,
  critic ACCEPT-WITH-RESERVATIONS: 0 CRITICAL + 3 MAJOR 반영; citation 정확도 100%).
  권장: (a)안 = Ambisonics를 "디코더용 규칙적 스피커 리그 배치" 기하 알고리즘으로 정의,
  실제 SH 디코딩은 engine 책임(`ipc_schema.md:21-22` `/sys/ambi_order` 확인). 리그 =
  t-design 우선·platonic 폴백(VBAP dome 재사용 부적합). **OQ-38 종결 제안**: `x_target_algorithm`
  extension key writer/reader (cadence 초과 + D26 forced-decision 근거). 구현 deferred —
  **PR2 착수 전 gate: engine이 IRREGULAR ambisonics 리그를 디코더로 라우팅하는 메커니즘
  합의 필요(§D-3a)**; require.md는 아직 ambisonics를 mandatory로 안 함(ADR 0003 precondition 미충족).
  - 파생 신규 OQ 제안: ambisonics order↔n_speakers 추론/라운딩 규칙, t-design 좌표 출처/라이선스,
    engine 식별·라우팅 합의 — 모두 ADR 0041 §OQ 참조.

- **(B6 Live-mesh corner 추출 / OQ-13e 부분 resolution)** — synthesized-shoebox tautology를
  실제 메시 코너 추출로 대체. **설계 = [ADR 0042](../../docs/adr/0042-live-mesh-corner-extraction.md)**
  (REVISED, critic ACCEPT-WITH-RESERVATIONS: 2 CRITICAL + 3 MAJOR 반영). 권장: floor polygon
  추출 = **alpha-shape(concave hull)**, convex(현 `mesh.py:135`)는 `alpha=None` literal
  short-circuit 으로 default 보존(회귀 0), alpha-shape 는 opt-in. 벽 = extrusion 재사용(RANSAC
  미채택). 신규 의존 0(scipy/shapely/trimesh 기존). **핵심 정정**: convex-hull deferral 출처는
  D6 아닌 **ADR 0027 + OQ-13e(ii)** (D6=capture-device; repo 전반 mislabel — D74 로 cleanup 기록 제안).
  비볼록 simple polygon 은 downstream(geom/listener/roomplan)에서 이미 지원, self-intersecting 만
  미지원. 검증 = 합성 L-shape 메시(SoundCam access 불요; 단 비-tautological 위해 interior/벽/천장
  vertex 포함 + jitter 게이트 필요 — PR2 deliverable). OQ-13e (i)SoundCam access는 **확인 불가** →
  A10a 비-tautological 승격(PR4)만 그 조건에 잔류.
  - 파생 신규 OQ 제안: point-cloud 직접 입력 허용(0-faces 가드 완화), D74(alpha-shape 채택 + D6 mislabel cleanup).

- **(B7 흡음 가구 ObjectKind 확장 / OQ-33 연결)** — ObjectKind(column/door/window)→흡음 가구 확장.
  **설계 = [ADR 0043](../../docs/adr/0043-absorptive-furniture-objectkind.md)** (REVISED, critic
  REVISE: 1 CRITICAL + 2 MAJOR 반영). 권장: B7-A(enum 확장)/B7-B(자동인식) 분리. 가구 흡음 모델 =
  ACE equivalent-absorption-area 패턴(ADR 0013), 단 **ISM shoebox 경로는 sabin 직접 누적(B-2)
  필수** — 합성 surface(B-1)는 area-weighted-α 를 희석할 뿐 sabin 미주입(critic CRITICAL,
  predictor.py:155/180 확인). 자동인식: RoomPlan sidecar category 확장만 저비용, mesh BoundingBox
  클러스터링은 **OQ-33 deferred 유지**(D26 trigger 미충족). **D26-YAGNI 긴장(사용자 보고 0건)**:
  검증(가구 흡음 RT60 영향 측정)을 enum 확장보다 **선행**해 ±20% 잠식 입증 시에만 enum 개방.
  - 파생: sofa/curtain A_500 provenance(honesty-marked source 필요), ADR 0034 §D "≥3 kind" 정책
    정합(planner 판단), 비-shoebox door/window α-override 제외 동작(report.py:42) 별도 추적.

> **Feature-expansion 설계 사이클 종합 (2026-05-29)**: B4~B7 4개 ADR(0040~0043) 설계 완료, 모두
> critic 리뷰 반영 REVISED, tense-lint clean. 전부 Status=PROPOSED(구현 미착수). 구현 우선순위
> 권고는 `.omc/plans/feature-expansion-roadmap.md` Phase 6 참조.

---

## RIR Auralization 설계 사이클 (2026-05-30 — 설계 문서, 미구현)

> Hybrid 물리-기반 RIR estimation 을 auralization(청취) 용도로 추가하는 연구+설계 사이클.
> 추적 = `.omc/plans/rir-estimation-roadmap.md`; 리서치 전문 = `.omc/research/rir-estimation-2026-05-30.md`.
> **설계 = [ADR 0044](../../docs/adr/0044-rir-auralization-design.md)** (Status=PROPOSED, REVISED;
> critic ACCEPT-WITH-RESERVATIONS, 0 CRITICAL+0 MAJOR 반영). Phase A = RAZR 식 ISM early +
> filtered-noise late + BRIR, web-tier, 신규 패키지 0, 측정/학습데이터 0.

**OQ-47** — diffuse late-tail 바이노럴화(ADR 0044 §D: 2-HRIR decorrelation + IC target curve
`sinc(2πf·d/c)`)의 **지각충실** 검증. IC 목표곡선은 설계변수로 지정 가능하나 그 결과의 perceptual
fidelity 는 미검증 — Phase A 최대 불확실성. **Reverse-trigger**: filtered-noise tail 이 perceptual/JND
검증 통과 시 neural 보정 불요(ADR 0044 Reverse-criterion #3). Allocated 2026-05-30.
> **STATUS-UPDATE (D79, v0.23.0, 2026-05-31)** — 합성 경로 **SHIPPED**(`synthesize_brir`: early per-DOA HRIR + late 2-HRIR decorrelation IC 목표 `sinc(2πf·d/c)`). 그러나 *지각충실*은 여전히 **OPEN**(verification-deferred) — diffuse tail 은 *plausible* 로만 기술(honesty scope). OQ-49 metric 선정이 검증 선행조건.

**OQ-48** — `compute_rir()` 선결 spike: (i) sparse-ISM-RIR `measure_rt60` 가
`predict_rt60_default_per_band` 와 RT60 일관(T20/T30 ±5%)한가(ADR 0040:67 연계),
(ii) broadband 반환에서 per-band RIR 추출(band-separability) 가능한가. 둘 다 GREEN 아니면
image-source 직접 조립(`pra_source.damping` per-band, `binaural.py:309`) 폴백. ADR 0044 §E / blocking gate #2.
> **RESOLVED by planner spike (2026-05-31, pra 0.10.1, canonical python; throwaway scripts removed)** — **둘 다 RED**:
> (i) `compute_rir()` 는 (mic,src) 당 **broadband 1-D 단일 RIR** 반환(`ndim==1`, 예 shape (7365,)); per-band RIR 필드 부재 → band-separability **불가**.
> (ii) `measure_rt60()` 는 broadband 스칼라 1개(0.125 s)로, 500 Hz 밴드 Sabine 기대값(~0.734 s)과 **~6× 불일치** → RT60 일관성 **실패**(ADR 0040:67 플래그 실증 확인).
> → **결정: image-source 직접 조립 채택, `compute_rir`/`measure_rt60` 미사용.** 추가 발견: pra 가 `fs` 에서 octave 그리드를 **8밴드**(125…4k + 8k/16k)로 확장 → `damping` shape (8, N); 선행 6밴드는 `OCTAVE_BANDS_HZ` 와 정확히 일치 → `rir.py` 가 `damping[0:6]` 슬라이스 + band-grid guard. **정식 CLOSE 는 구현 GREEN 후 D79 에서** (계획 `.omc/plans/rir-auralization-phase-a.md`).
> **CLOSED (D79, v0.23.0, 2026-05-31)** — Phase A 구현 GREEN(default 300p/web 82p/ruff·mypy·tense EXIT0). image-source 직접 조립이 `roomestim_web/rir.py::assemble_early_rir_per_band` 로 shipped; `compute_rir`/`measure_rt60` 미사용 확정. `damping[0:6]` 슬라이스 + band-grid guard 구현.

**OQ-49** — Phase A auralization 평가 metric 선정: 어느 objective(EDT/C50/C80/DRR/EDC fit/log-spectral)
가 지각품질과 best 상관 + 잔향 JND 임계. 리서치 Q2 미해결(method-centric corpus) → **추가 문헌조사
필요**. 미선정 시 Phase A acceptance 가 회귀 게이트 외에는 falsifiable 하지 않음(critic stakeholder 지적).
> **STATUS-NOTE (D79, v0.23.0, 2026-05-31)** — 여전히 **OPEN**. Phase A 구현은 회귀 게이트(RT60-consistency per-band, splice-continuity, 결정성, 6-band 유지) 로 falsifiable 하나, perceptual metric 선정(OQ-47 검증 선행조건)은 미해결. 추가 문헌조사 필요.

**OQ-50** — 대상 방당 ~12 측정 RIR 확보 현실성(DiffRIR few-shot 예산). Phase C(differentiable fitting)
gate. **Reverse-trigger**: 확보 불가 시 Phase C 미실시, blind Phase A 만 유효(ADR 0044 Reverse-criterion #1).

**OQ-51** — mixing-time analytic `√V` 근사가 비-shoebox/coupled-space(예: Building_Lobby)에서 충분한가,
echo-density profile 필요한가. ADR 0044 §A.
> **STATUS-NOTE (D79, v0.23.0, 2026-05-31)** — `√V` mixing time 이 v1 로 **SHIPPED**(`rir.py::mixing_time_s = 1e-3·√(room_volume)`). 비-shoebox/coupled-space 적정성은 여전히 **OPEN**(echo-density estimator 부재로 v1 은 analytic 근사만; Building_Lobby 등 결합공간 검증 미실시).

> **RIR 사이클 종합 (2026-05-30)**: 리서치(20 confirmed/5 refuted; EDC-neural perceptual 등가 주장
> 반박됨) → 실현가능성 스파이크(GO-WITH-CAVEATS) → ADR 0044 draft(REVISED). Status=PROPOSED, 구현
> 미착수. 구현 착수 전 blocking gate(§D 합의 + §E spike + §A splice-continuity + 회귀 0) 충족 필요.
