# roomestim — Decisions Log (Open Questions Resolved)

- **Date**: 2026-05-03
- **Owner**: paiiek
- **Source**: `.omc/plans/roomestim-v0-design.md` (§§1–14) + auto-mode operating defaults
- **Status**: ACCEPTED for v0.1 implementation start. Each decision is reversible at v0.2 review.

The 7 questions in `open-questions.md` (§13 of the design doc) are resolved as follows so that P0 can begin without blocking on cross-team input. Reversal criteria are listed; if any trigger fires during v0.1, re-open the corresponding question.

---

## D1 — Distribution model: separate git repo for v0.1, defer submodule/PyPI to v0.2

**Question**: Submodule under `spatial_engine/third_party/` vs PyPI?

**Decision**: roomestim ships as a standalone git repo at `/home/seung/mmhoa/roomestim/` for v0.1 (matches design §11.3 / Q7). Both submodule and PyPI options remain on the table; ADR for the choice is authored in **roomestim v0.2** after the schema has been exercised.

**Why**: Independent versioning before the schema has been exercised by ≥10 real `room.yaml` files; mirrors `vid2spatial` / `claude_text2traj` precedent. Locks zero cross-repo coordination tax during v0.1.

**Reverse if**: spatial_engine team requests immediate vendoring; CI maintenance cost of standalone repo exceeds 1 day/month.

---

## D2 — `room.yaml` shape acceptance by engine team: NOT a v0.1 blocker

**Question**: Does the engine team accept the proposed `room.yaml` shape (2.5D polygon + scalar ceiling)?

**Decision**: roomestim v0.1 ships `room.yaml` with `version: "0.1-draft"` (Stage 1, permissive `additionalProperties: true`) per §6.0 two-stage lock. Engine-team review is **not required** for v0.1; the cross-repo PR proposing `spatial_engine/proto/room_schema.json` lands in **roomestim v0.2** after the lab fixture has produced a real `room.yaml`. Stage 2 strict lock (`version: "0.1"`, `additionalProperties: false`) flips inside v0.1 only after A10 lab fixture passes.

**Why**: Schema is unexercised; cross-repo PRs before exercise produce churn on both sides (R3). Two-stage lock is the explicit insurance.

**Reverse if**: ≥3 of the next 10 real-world `room.yaml` files require schema patches after Stage 2 lock — falsifier per §6.0.

---

## D3 — `material` enum: closed 8-entry enum is sufficient for v0.1

**Question**: Closed `material` enum sufficient, or do we need a free-form `custom_label`?

**Decision**: Ship the closed 8-entry enum from §3 A11 / §6 schema:
`{wall_painted, wall_concrete, wood_floor, carpet, glass, ceiling_acoustic_tile, ceiling_drywall, unknown}`. The `unknown` entry is the v0.1 fallback for any unmappable surface. **No** `custom_label` field in v0.1.

**Why**: Closed enum prevents schema rot and forces the absorption-coefficient table (Vorländer 2020 Appendix A, per R4) to stay authoritative. `unknown` covers the unmappable case without opening the schema to free-form labels.

**Reverse if**: ≥30% of surfaces across the first 10 captures land in `unknown` — that signals enum coverage is too narrow; v0.2 either extends the enum or introduces `custom_label` with a separate `absorption_500hz_user` field.

---

## D4 — Lab speakers in `lab_setup.md`: assume NOT pre-mounted; v0.1 places them as part of A10

**Question**: Are the lab speakers already mounted, or are we placing them as part of v0.1 acceptance?

**Decision**: Assume **not pre-mounted**. The A10 acceptance flow is:
1. RoomPlan/Polycam scan of the empty lab → `room.yaml`.
2. `roomestim place --algorithm vbap --n-speakers 8 --layout-radius 2.0` → recommended `layout.yaml`.
3. Tape-measured installation of speakers per the recommendation.
4. Tape-measured ground truth comparison: A10 passes if installed positions are within ±5° azimuth / ±10 cm radial of the recommendation, AND the room corner errors are <10 cm.

If the user later confirms the speakers were already mounted before scan day, we instead validate against pre-existing positions (±5° / ±10 cm of measured-as-mounted), and the placement step in A10 becomes a one-shot regression test.

**Why**: The "place-then-mount" interpretation is the more demanding and more useful one (it actually exercises the placement engine on a real room). The "already-mounted" interpretation degrades A10 to a pure regression test.

**Reverse if**: User confirms the lab speakers were already mounted; switch A10 to regression-test mode (no installation step) without changing the numerical thresholds.

---

## D5 — `aim_direction` export: ship as `x_aim_az_deg` / `x_aim_el_deg` extension keys in `layout.yaml`

**Question**: Should `aim_direction` be exported in `layout.yaml`, or kept only in roomestim's `PlacementResult`?

**Decision**: Export per §6.1: per-speaker extension keys `x_aim_az_deg` (∈ [-180, 180]) and `x_aim_el_deg` (∈ [-90, 90]). Both follow the VBAP layout-frame. Default = vector from speaker → listener-area centroid; user-overridable. Engine ignores these (`additionalProperties: true` at the per-speaker block); they exist for documentation / listening-test reports / future engine reverb.

**Why**: Aim is information that costs nothing to emit (already computed for placement) and would otherwise require parallel YAML files. Extension-key prefix `x_` makes it explicit that the engine MAY ignore.

**Reverse if**: spatial_engine team requests a non-`x_` first-class `aim` field — at that point promote into `geometry_schema.json` v-next via cross-repo PR.

---

## D6 — Capture device availability for v0.1 acceptance: RoomPlan-first, Polycam supported

**Question**: Does the team have an iPhone Pro / iPad Pro for RoomPlan capture, or do we need to ship Polycam as the v0.1 first-class adapter instead?

**Decision**: Per design Q1 — **RoomPlan is first-class, Polycam is supported secondary, COLMAP is experimental**. Both RoomPlan and Polycam adapters ship in v0.1 (P4 and P5 phases respectively). A10 acceptance gate uses whichever device the user can capture with on the day; the test-fixture name flexes (`tests/fixtures/lab_real.usdz` is the canonical name regardless of source app — both RoomPlan and Polycam emit USDZ).

**Why**: Removes the device-availability dependency from the v0.1 ship gate. If only Polycam is available on capture day, the Polycam adapter (P5) is on the same critical path and the acceptance test runs through that adapter.

**Reverse if**: P5 (Polycam adapter) ships before P4 (RoomPlan adapter) due to capture-device unavailability — at that point Polycam becomes first-class de facto, and ADR 0001 is reversed.

---

## D7 — Octave-band absorption: defer to v0.3; v0.1 ships single mid-band (500 Hz)

**Question**: Single mid-band 500 Hz vs full octave-band absorption coefficients?

**Decision**: Per design §10 deferral table — v0.1 ships **single mid-band 500 Hz** absorption only (`absorption_500hz` field). Octave-band coefficients defer to v0.3.

**Why**: Sabine RT60 estimate at single mid-band reaches ±20% accuracy (the A11 tolerance) without octave-band data. Octave-band would require either (a) full Vorländer 2020 Appendix A imported as a 6-column-per-material table, or (b) measurements we do not have. RT60 is advisory metadata at v0.1, not a renderer input.

**Reverse if**: spatial_engine reverb integration (post v0.2) requires octave-band coefficients to feed image-source / wave-based reverb — at that point introduce `absorption_octave_125_8000hz: [a125, a250, a500, a1000, a2000, a4000, a8000]` as an optional sibling field in v0.3, with `absorption_500hz` deprecated but kept for compatibility.

---

## Implementation impact

- **P0 starts now** with all D1–D7 decisions baked in.
- ADRs 0001..0005 (placed in `roomestim/docs/adr/`) reference back to D1, D2, D3, D6, D7 by section number when authored in P7.
- `open-questions.md` has been superseded by this file for v0.1; the questions remain logged there as historical record but are marked RESOLVED.

---

## D8 — Autopilot exit boundary: Stage-2 schema flip and A10 lab capture are post-autopilot human-gated work within v0.1

**Date**: 2026-05-03 (RALPLAN-DR consensus iter 1, resolving Architect's `ARCHITECT-REVISE` G5 + Critic's `ITERATE` fix #1)

**Question**: When autopilot of P1–P6 finishes, can it legally flip the schema to Stage-2 (`version: "0.1"`, `additionalProperties: false`) and pass A10? §6.0:437 and decisions.md D2 say the flip needs the lab fixture to have produced ≥1 real `room.yaml` — but autopilot cannot capture a physical iPad/iPhone Pro scan.

**Decision**: Autopilot exits with:
- Stage-1 schema shipped (`version: "0.1-draft"`, `additionalProperties: true`).
- Default-CI lane (`pytest -m "not lab"`) green; A10 (`@pytest.mark.lab`) explicitly SKIP.
- A `RELEASE_NOTES_v0.1.md` line stating "Stage-1 schema shipped; Stage-2 flip and A10 lab capture pending human-driven follow-up session."
- A11 falls back to a **synthetic-shoebox reference RT60** (Critic fix #3 — see plan §3 A11 update) so RT60 testability does not depend on A10.

Stage-2 flip and A10 capture remain inside the v0.1 release — they are NOT promoted to v0.2 — but they are sequenced AFTER autopilot completes. Both are human-gated:
- Lab capture (iPad Pro RoomPlan / Polycam) → produces `tests/fixtures/lab_real.usdz`.
- Tape-measure ground truth → produces `tests/fixtures/lab_real_groundtruth.yaml`.
- A10 acceptance test runs (`pytest -m lab`).
- Reviewer sign-off → schema flips Stage-1 → Stage-2.
- Cross-repo PR proposing schema upstream → roomestim v0.2 work.

**Why this and not "promote A10 to v0.2 gate"**: Critic raised the alternative of moving A10 entirely to v0.2. Rejected because (a) A10 is the project's identity gate (cm-grade physical lab) and v0.1 staked its definition on it, and (b) `@pytest.mark.lab` already implies "advisory in default CI" — moving the gate to v0.2 would gut the v0.1 ship criteria more than necessary. D8 keeps the gate inside v0.1 but acknowledges the human handoff between autopilot and ship.

**Reverse if**: human-driven A10 capture session never materializes within 4 weeks of autopilot completion → consider promoting A10 to v0.2 gate instead.

---

## D9 — Lab-room sidecar fixture is the CI default; real USDZ is the post-autopilot acceptance fixture

**Date**: 2026-05-03 (RALPLAN-DR consensus iter 1, resolving Architect G1-refine + Critic fix #4)

**Question**: For A9 (RoomPlan adapter parses sample USDZ, ±10 cm ceiling, ±5% area, ≥4 walls), which of the three §4 P4 options ships in default CI?

**Decision**: Ship the **JSON-sidecar mock** in default CI as `tests/fixtures/lab_room.json` (RoomPlan-format JSON sidecar) plus `tests/fixtures/lab_room.meta.yaml` (ground-truth metadata: `ceiling_height_m`, `floor_area_m2`, expected wall count). The sidecar is the only Linux-CI-buildable option; hand-authored real USDZ requires Mac/Apple tooling (R1, R6).

A9 acceptance criterion is split (Critic fix #2):
- **A9a (default CI)**: sidecar mock parses through `roomplan_adapter.parse(...)` and the resulting `RoomModel` matches `lab_room.meta.yaml` ground truth within tolerance. Runs unconditionally.
- **A9b (gated)**: real USDZ at `tests/fixtures/lab_room.usdz` parses through the same code path. Test SKIPs if file absent (mirrors A2/A15 env-var pattern).

The sidecar fixture and metadata file are committed before P4 starts as a P4-task-1 deliverable.

**Why**: Critic correctly noted A9-as-written would silently regress from real-USDZ to mock-only. The split keeps full A9 coverage available when the fixture exists, while the default lane stays Linux-CI-buildable.

**Reverse if**: hand-authored USDZ becomes feasible on Linux (e.g., a portable USDZ writer in Python lands) — at that point promote A9b to default lane.

---

## D10 — A2/A15 C++ harness binaries: deferred to spatial_engine v0.2

**Date**: 2026-05-05 (v0.1.1 closeout, RALPLAN-DR iter-2 plan §4 Step 1)

**Question**: At v0.1.1, the engine's `core/build/` ships `spatial_engine_core` + `libspe_core.a` + `libspe_util.a` but neither `layout_loader_smoke` nor `coords_parity_harness`. The two A2/A15 acceptance tests therefore SKIP unconditionally. What ships at v0.1.1?

**Decision**: **Defer** A2/A15 C++ harness wire-up to spatial_engine v0.2. The named binaries are not part of the engine's v0.1 build; producing them belongs in the engine repo's own test suite, not in roomestim. v0.1.1 keeps the SKIP behaviour and improves the skip-reason text to name this decision (so future readers don't repeat the discovery).

**Why this and not "author the harness binaries inside roomestim/cpp/parity_harness/"**:
- (a) Smuggles C++ build complexity (CMake config, ABI tracking, libspe_* version pinning) into a Python-first repo.
- (b) Any drift between the engine's actual loader logic and our reimplementation would silently invalidate the parity claim — a consumer-side parity proof is no proof at all.
- (c) Cross-repo precedent (D1) defers cross-repo build coupling until v0.2.

**Compensating coverage in v0.1.1**:
- A2 fallback: schema validation S5 (already passing) is the unconditional A2 fallback per the original v0.1 design.
- A15 fallback: the 10 804-point Python coords roundtrip sweep at machine epsilon (`tests/test_coords_roundtrip.py`) exercises every code path the C++ harness would.

**Reverse if**: spatial_engine v0.2 builds either harness binary AND publishes its CLI contract — at that point re-enable the consumer-side A2/A15 tests in roomestim v0.2 (no code change required beyond removing the SKIP).

---

## D11 — Distribution-model decision: DEFERRED at v0.2 with re-evaluation criteria

**Question**: Which option does ADR 0007 choose — (a) standalone git repo, (b) git submodule under `spatial_engine/third_party/roomestim/`, or (c) PyPI publish?

**Decision**: DEFER. v0.2 ships as standalone (option (a)), unchanged from v0.1. ADR 0007 (`docs/adr/0007-distribution-model.md`) records the deferral with explicit re-evaluation criteria.

**Why**: The decision space is evidence-limited at v0.2. Key signals:
- Time since v0.1.1: ~1 day. No reverse-criterion signal possible.
- Cross-repo PR rounds since v0.1.1: 0 (schema PR drafted but not opened).
- Real-world room.yaml count produced: 0 (A10 lab capture is post-autopilot).
- CI maintenance hours since v0.1.1: ~0 (no incidents).
- Sibling-repo precedent: vid2spatial, claude_text2traj are both standalone.

Forcing a choice without evidence would fabricate rationale or lock a structure that usage may invalidate within 30 days. Mirrors v0.1.1 Critic M1 honesty principle.

**Reverse if**:
- Engine team explicitly requests vendoring → flip to (b).
- CI maintenance cost > 1 day/month over a 30-day window → flip to (b).
- ≥1 external consumer requests `pip install roomestim` → consider (c), only after (b) is evaluated and rejected.

**Re-evaluate at**: v0.3 ship or after first cross-repo PR exchange, whichever comes first.

**Cross-ref**: ADR 0007 (`docs/adr/0007-distribution-model.md`), D1, spec.md §2 (workstream c).

---

## D12 — Octave-band absorption schema extension at v0.3

**Question**: Should v0.3 add per-octave-band absorption coefficients to the schema and material table, and if so, how many bands?

**Decision**: YES — add 6 bands (125, 250, 500, 1000, 2000, 4000 Hz) as an OPTIONAL `absorption` block per surface. `absorption_500hz` remains REQUIRED. Emit block only when `Surface.absorption_bands is not None` (opt-in via `--octave-band` CLI flag). Default behaviour unchanged (A12 byte-equality preserved).

**Why**:
- E2E RT60 validation against ACE Challenge requires per-band predictions → per-band Sabine RT60.
- Schema extension cost is near-zero (optional block, backwards-compatible, both schema files updated).
- Alternative (wait for engine request, then breaking v0.4 schema change) is more costly.
- 8 kHz excluded: Vorländer 2020 Appx A typical room-acoustics tables stop at 4 kHz; no measured per-octave ACE data at 8 kHz in the pre-tabulated corpus files.

**Honesty note**: `MaterialAbsorptionBands` values are representative Vorländer-class coefficients, NOT verbatim Appx A rows. Each row carries an inline honesty marker in `roomestim/model.py`. UNKNOWN row is flat at 0.10 (synthetic broadband fallback). Enforced by `test_band_a500_matches_legacy_scalar`: `MaterialAbsorptionBands[m][2] == MaterialAbsorption[m]` for all m.

**Reverse if**:
- Engine team requests a different band set (e.g., 7 bands to 8 kHz) → v0.4 ADR authors extension.
- Per-band Sabine predictions consistently > 50% error across multiple rooms in E2E validation → revisit material coefficient table before v0.4.

**Cross-ref**: ADR 0008 (`docs/adr/0008-octave-band-absorption.md`), D7, spec.md §3 (workstream d).

---

## D13 — D12 reverse-trigger fired empirically; v0.4 material-table revisit scheduled (no immediate rollback)

**Date**: 2026-05-06

**Question**: The 7-room ACE Challenge characterisation run (`docs/perf_verification_e2e_2026-05-06.md`, generated against `/tmp/ace_corpus`) shows 500 Hz absolute errors above 50% of measured for 5 of 7 rooms. D12 lists this as a "reverse if" trigger. Do we roll back the v0.3 octave-band table now?

**Decision**: NO — keep v0.3 shipped material table. Schedule a v0.4 material-table revisit and a per-room material-assignment audit. The characterisation test stays a characterisation (no magnitude assert), as designed.

**Empirical findings (500 Hz)**:
- Building_Lobby: +239% (predicted 2.022 s vs measured 0.597 s)
- Lecture_1: +214% (predicted 1.762 s vs measured 0.561 s)
- Office_1: +129% (predicted 0.864 s vs measured 0.377 s)
- Office_2: +96% (predicted 0.887 s vs measured 0.452 s)
- Lecture_2: −50% (predicted 0.673 s vs measured 1.343 s)
- Meeting_1: +17%, Meeting_2: +15% — within typical Sabine bounds.

**Why no rollback**:
1. Two of the five large errors (Lecture_2 under-prediction; Building_Lobby/Lecture_1 over-prediction in lightly-damped large rooms) point at material-assignment guesses in `ACE_ROOM_GEOMETRY`, not at the material-coefficient table. The audit must come first; rolling back the table without it would be churn.
2. Sabine's diffuse-field assumption is known to fail in (a) lightly-damped rooms (Office_1/2 with mostly hard wall_painted surfaces give very small total absorption A, blowing up RT60 = 0.161 V/A) and (b) very large volumes (Lecture_2). This is a physics limitation, not a coefficient error.
3. The honesty-marker policy (D12, M1) was explicitly designed to admit these values are representative not verbatim. The doc records the actual error envelope; downstream consumers can decide.
4. v0.3 shipped opt-in via `--octave-band`; A12 byte-equality is preserved by default. No production code path is degraded.

**v0.4 work scheduled**:
- Audit `ACE_ROOM_GEOMETRY` material assignments per ACE corpus instructions PDF (`/tmp/ace_corpus/ACE_Corpus_instructions_v01.pdf`); flag wrong-material rows.
- Consider Eyring or Millington-Sette correction for high-absorption rooms (Vorländer 2020 §4.2).
- If audit shows assignments are correct yet errors persist → revisit `MaterialAbsorptionBands` coefficients for `wall_painted`, `wood_floor`, `ceiling_drywall` first.
- Re-run E2E; the report file will regenerate deterministically.

**Reverse if**:
- v0.4 audit shows the assignments ARE correct AND a coefficient revision still leaves >2 rooms with >50% error → reconsider whether Sabine is the right predictor at all (move to ray-tracing / image-source for v0.5).
- An external consumer of the v0.3 schema reports that the optional `absorption` block, as shipped, leads them astray → emergency v0.3.x patch.

**Cross-ref**: D7, D12, ADR 0008, `docs/perf_verification_e2e_2026-05-06.md`.

---

## D14 — Eyring shipped as parallel predictor; ACE_ROOM_GEOMETRY byte-audit deferred

**Date**: 2026-05-06

**Question**: D13 scheduled three v0.4 audit/work items: (a) audit `ACE_ROOM_GEOMETRY`
material assignments per the ACE corpus instructions PDF, (b) consider Eyring or
Millington-Sette correction for high-absorption rooms, (c) revisit the
`MaterialAbsorptionBands` coefficients if (a) showed assignments are correct yet errors
persist. Which of these ship at v0.4.0?

**Decision**:
- **(b) ships** — `eyring_rt60` and `eyring_rt60_per_band` are added to
  `roomestim/reconstruct/materials.py` as parallel predictors. Sabine remains the default.
  Per-band Sabine and per-band Eyring are now both reported by the gated E2E test, with
  the `eyring ≤ sabine + 1e-9` invariant enforced at runtime per Vorländer 2020 §4.2.
- **(a) DEFERRED** — the local ACE corpus distribution at `/tmp/ace_corpus/` has no
  machine-readable room metadata. The canonical room-by-room geometry + material
  assignment table is **Eaton 2016 TASLP Table I** (Eaton, J., Gaubitch, N. D., Moore,
  A. H., & Naylor, P. A., "Estimation of room acoustic parameters: The ACE Challenge",
  IEEE/ACM TASLP 24(10), 1681–1693). That paper is not in the local corpus; the local
  distribution only carries codename → friendly-name mapping in
  `software/Software/private/getACECorpusData.m`. Byte-cross-check is therefore deferred
  until the paper or its Table I extract is available.
- **(c) DEFERRED** — without (a) confirmed, revisiting `MaterialAbsorptionBands` would
  swap one source of uncertainty for another. Deferred to v0.5.

**Empirical findings from v0.4 E2E run** (Sabine and Eyring at 500 Hz, abs error in s):
- Eyring shifts every room toward Sabine at low ᾱ (Taylor limit holds; ratios ≈ 1) and
  meaningfully reduces error only on heavily-absorbed rooms.
- For the 7 ACE rooms, the largest Sabine→Eyring 500 Hz delta is ≤ 0.08 s. The dominant
  error source is therefore **NOT** the predictor choice; it is some combination of
  material assignment (D13 hypothesis) and the bare-walls model missing
  soft-furnishings/occupants absorption budget. Specific empirical numbers are recorded
  in the auto-regenerated `docs/perf_verification_e2e_2026-05-06.md` and analysed in
  `.omc/plans/v0.4-audit-findings.md`.

**Hypothesis (NOT confirmed)**: Lecture_2 under-prediction is consistent with
`ceiling_acoustic_tile` being the wrong assignment — flat painted ceiling
(`ceiling_drywall`, lower absorption) would push Sabine/Eyring upward toward the
measured 1.343 s. Cannot be confirmed without Eaton 2016 Table I; see audit-findings
Finding 3.

**Hypothesis (NOT confirmed)**: Building_Lobby/Lecture_1/Office_1/Office_2 over-prediction
is consistent with the bare-walls model missing absorption from soft furnishings, chairs,
desks, books, and (during measurement) any seated occupants. Two follow-ups are deferred
to a v0.5 ADR: (i) coefficient revision for `wall_painted` / `wood_floor` /
`ceiling_drywall`, (ii) optional `MISC_SOFT` MaterialLabel enum extension for
furnishings. See audit-findings Finding 4.

**Why no rollback of v0.3 material table**: v0.4 ships an additive predictor without
disturbing existing coefficients or schema. v0.3.1 byte-equality (74 default-lane tests)
holds. Rolling back coefficients now would (1) churn the schema clients reading
`absorption_bands` and (2) substitute a guess for a guess until (a) is confirmed.

**Reverse if**:
- Eaton 2016 Table I becomes available and disagrees with `ACE_ROOM_GEOMETRY` —
  patch table in v0.4.x and re-run E2E.
- An external roomestim consumer reports Eyring breaking their workflow — v0.4.x patch.
- After (a) confirms assignments are correct, errors >50% persist on >2 rooms with
  Eyring — that would falsify both the predictor hypothesis and the assignment
  hypothesis; revisit `MaterialAbsorptionBands` at v0.5 with explicit ADR.

**Cross-ref**: D7, D12, D13, ADR 0008, ADR 0009, `.omc/plans/v0.4-audit-findings.md`,
`docs/perf_verification_e2e_2026-05-06.md`, `roomestim/reconstruct/materials.py`.

---

## D15 — v0.5.0 ships partial-A (ACE geometry dims verified vs arXiv:1606.03365) + B (MISC_SOFT enum); materials, F3, F4a DEFERRED

**Date**: 2026-05-07

**Question**: D14 deferred four findings to v0.5: (1) `ACE_ROOM_GEOMETRY` byte-audit
vs Eaton 2016 Table I, (3) Lecture_2 ceiling-material reassignment hypothesis,
(4a) `MaterialAbsorptionBands` coefficient revision, (4b) `MISC_SOFT` enum extension.
Which of these ship at v0.5.0?

**Decision**:
- **Finding 1 dims half — SHIP**. arXiv:1606.03365 Table 1 (TASLP supporting material;
  open access; transcribed 2026-05-06) is adopted as the canonical dimensional source.
  All 7 rooms in `ACE_ROOM_GEOMETRY` are verified within ±0.01 m by the new gated
  audit at `tests/test_ace_geometry_audit.py` against the committed fixture
  `tests/fixtures/ace_eaton_2016_table_i_arxiv.csv`. `Office_2` is patched
  (W 3.50 → 3.22, H 3.00 → 2.94 — the only numerical correction). roomestim's
  "longer dimension as L" convention is kept; the L/W swap on `Office_1`,
  `Office_2`, and `Building_Lobby` between roomestim and arXiv is product-equivalent
  and only `Office_2`'s dimensional drift was a real numerical bug. ADR 0010
  records the decision and the L/W convention.
- **Finding 1 materials half — DEFERRED**. Materials are not in any open-access
  source; only in TASLP final paper (paywalled). Pushed to v0.6+ pending TASLP
  access.
- **Finding 3 — DEFERRED**. The Lecture_2 ceiling-material reassignment hypothesis
  cannot be confirmed without Finding 1 materials half.
- **Finding 4a — DEFERRED**. D14's 5b reverse-trigger requires "assignments correct
  AND errors persist on >2 rooms with Eyring"; the first pre-condition is
  indeterminable without Finding 1 materials half. F4a stays DEFERRED with this
  explicit rationale (NOT a coefficient guess swapped for another guess).
- **Finding 4b — SHIP**. `MaterialLabel.MISC_SOFT = "misc_soft"` is added to the
  closed enum (D3) with `MaterialAbsorption[MISC_SOFT] = 0.40` and
  `MaterialAbsorptionBands[MISC_SOFT] = (0.20, 0.30, 0.40, 0.50, 0.60, 0.65)`
  as a representative-not-verbatim row mirroring the v0.3 `MaterialAbsorptionBands`
  honesty-marker policy. Schema slot reserved for adapter-emitted furnishings /
  occupants absorption budget; adapter wiring follows consumer demand (D5
  precedent). ADR 0011 records the decision.

**v0.5.0 deliverables**:
- ACE adapter dimensional patch (Office_2) + honesty-caveat rewrite.
- Committed arXiv Table 1 fixture + gated audit test (`@pytest.mark.e2e`).
- Auto-regenerated `docs/ace_geometry_audit_2026-05-07.md`.
- `MISC_SOFT` enum extension + 4 new unit tests.
- ADR 0010 (ACE geometry verified vs arXiv, dims only).
- ADR 0011 (MISC_SOFT enum extension).
- `.omc/plans/v0.5-audit-findings.md` (Finding 1 split DONE/DEFERRED, F3 DEFERRED,
  F4a DEFERRED, F4b DONE).
- Regenerated `docs/perf_verification_e2e_2026-05-07.md` from the gated E2E
  (Office_2 V_m³ shrinks 53.55 → 48.28; Sabine RT60 at 500 Hz drops ~10%);
  v0.4 perf doc at `docs/perf_verification_e2e_2026-05-06.md` preserved for diff.
- Default-lane test count: 80 → 84 (+4 MISC_SOFT). ruff clean. `__schema_version__`
  stays `"0.1-draft"` (Stage-1; D8 binds Stage-2 to A10 lab capture).

**Why this scope and not the alternatives**:
- "Wait for TASLP" was rejected — the Office_2 dimensional drift is a real numerical
  bug; sitting on a known bug while waiting on a paywalled paper for the unrelated
  materials half is worse than shipping the dimensional fix today. Materials and
  the dependent findings (3, 4a) stay DEFERRED with explicit rationale.
- "Ship Scenario C (Millington-Sette)" was rejected — arXiv:1606.03365 supplied a
  real bug fix; that is the higher-value v0.5 headline. Millington-Sette stays a
  v0.6+ candidate (ADR 0009 alternative-considered).
- "Defer F4b to v0.6" was rejected — F4b is structurally independent of F1 and
  ships cleanly under SHORT-mode regardless of TASLP access.

**Reverse if**:
- Eaton 2016 TASLP final paper becomes available and its Table I numbers differ
  from arXiv:1606.03365 Table 1 → patch `ACE_ROOM_GEOMETRY` and re-run audit.
- The materials cross-check (when TASLP access lands) disagrees with the current
  `floor` / `walls` / `ceiling` strings → patch and re-run gated E2E.
- ≥1 adapter starts emitting `MISC_SOFT` AND a downstream consumer reports the
  `0.40` / band-tuple magnitude is wrong for their use case → revisit coefficients.

**Cross-ref**: D13, D14, ADR 0010, ADR 0011, `.omc/plans/v0.5-design.md` §0a,
`.omc/plans/v0.5-audit-findings.md`, `.omc/research/ace-table-i-acquisition.md`,
`docs/perf_verification_e2e_2026-05-07.md`, `docs/ace_geometry_audit_2026-05-07.md`.

---

## D16 — v0.5.1 audit framing correction: Eaton 2016 TASLP final reviewed; per-surface materials NOT in paper

**Date**: 2026-05-07 (post-v0.5.0)

**Question**: D14 / D15 framing assumed the Eaton 2016 TASLP final paper
(DOI 10.1109/TASLP.2016.2577502) contained the canonical per-surface material
assignment table for the 7 ACE Challenge rooms. After v0.5.0 shipped, the
paper became accessible via SNU IEEE Xplore and was reviewed cover-to-cover.
Does the framing hold?

**Answer**: No. The TASLP final does **not** contain a per-surface material
assignment table.

**Decision**:
- Treat all D14 / D15 references to "TASLP-blocked materials" as
  INDETERMINATE-NOT-BLOCKED. The canonical published source for walls and
  ceiling assignments does not exist; future audit cycles must not propose
  "wait for TASLP" as the resolution path for walls / ceiling.
- Floors are partially confirmed: TASLP §II-C "Rooms" describes 4/7 rooms as
  "carpeted" (Office_1, Office_2, Meeting_1, Meeting_2 → BYTE-CONFIRMED
  `carpet`) and 3/7 as "hard-floored" (Lecture_1, Lecture_2, Building_Lobby →
  HARD-FLOOR-COMPATIBLE; specific subtype not in paper).
- Building_Lobby gains a structural caveat: TASLP §II-C describes it as
  "large irregular-shaped hard-floored room with coupled spaces" with
  measurements taken in the corner area only. `ACE_ROOM_GEOMETRY` shoebox is
  the recording corner, not the room. v0.4's +1.425 s err Sabine on
  Building_Lobby is consistent with a modelling-assumption violation, not
  (only) coefficient/material gap.
- v0.5.0's Office_2 dimensional patch (W 3.50 → 3.22, H 3.00 → 2.94) and
  ADR 0010's "verified vs arXiv:1606.03365 Table 1" framing are
  **vindicated**: TASLP Table I = arXiv 1606.03365 Table 1 byte-identical.
  No code change needed.
- v0.5.0's MISC_SOFT enum slot (ADR 0011) is **retroactively strengthened**
  by TASLP §II-C explicit furniture counts (Office_2 "6 chairs + bookcase";
  Lecture_2 "~100 chairs + ~35 tables"; etc.). Per-room MISC_SOFT surface
  area is now derivable from canonical counts via Beranek 2004 / Vorländer
  2020 per-piece equivalent absorption — out-of-scope for v0.5.x;
  available for v0.6+.

**Drivers**:
- Avoid future audit cycles that wait on a non-existent canonical source.
- Strengthen the audit ledger so the v0.4 → v0.5 → v0.5.1 chain reflects
  what was actually established at each step.
- Keep the adapter's honesty caveat truthful: shipping with "TASLP-blocked"
  comments after the paper is in hand and confirmed silent on materials
  would be a known-false marker.

**Reverse-if**:
- Author-provided supplementary material (e.g., Imperial College SAP
  internal report; lab visit photos; author email response) surfaces a
  real material assignment table → revisit in v0.6+ ADR.
- A re-read of TASLP finds material assignments hidden somewhere (re-check
  appendices / figures / online supplementary) → revert D16.
- ACE Challenge consortium publishes a follow-up paper with materials.

**Cross-ref**: D13, D14, D15, ADR 0010, ADR 0011, ADR 0012,
`.omc/plans/v0.4-audit-findings.md` "Status update 2026-05-07",
`.omc/plans/v0.5-audit-findings.md` "Status update 2026-05-07 (v0.5.1)",
`roomestim/adapters/ace_challenge.py` honesty caveats (v0.5.1).

