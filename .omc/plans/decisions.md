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

---

## D17 — v0.6.0 ships TASLP-derived MISC_SOFT surface budget per room (B-L excluded) + 2 LOW retro fixes

**Date**: 2026-05-08

**Question**: D16 §"v0.6 v0.6+ work item set updated" listed three
v0.6+ items: (a) per-room MISC_SOFT surface area derived from TASLP
§II-C furniture counts, (b) Building_Lobby coupled-space modelling
ADR, (c) hard-floor subtype confirmation. Plus two LOW retros from
v0.5.1 (code-reviewer LOW-RETRO-1 — "are NOT in any open or paywalled
source" framing; security-reviewer LOW-RETRO-2 — "via SNU IEEE Xplore"
institutional naming). Which of these ship at v0.6.0?

**Decision**:
- **(a) TASLP-MISC ships** — six of the seven ACE rooms gain one
  synthesised `Surface(material=MaterialLabel.MISC_SOFT, kind="floor")`
  whose Newell-area is integrand-preserving:
  `area_misc_soft = Σ_pieces count_i * A_500_i / a_misc_soft_500` with
  `a_misc_soft_500 = 0.40` (v0.5.0 row). Per-piece α₅₀₀ values cited
  from Vorländer 2020 *Auralization* §11 / Appendix A (primary) with
  Beranek 2004 *Concert Halls and Opera Houses* Ch.3 Table 3.1 cross-
  check for the lecture-seat row (planner-locked OQ-6 default).
  Building_Lobby is **excluded by default** (planner-locked OQ-9
  default = (a) exclude); the helper returns `None` for B-L.
  Surface count goes 6 → 7 for the 6 furniture-tracked rooms.
- **(b) Building_Lobby coupled-space ADR DEFERRED** — separate ADR on
  its own terms (geometry kind annotation, multi-room volume) at v0.7+.
  v0.6 default = exclude per OQ-9.
- **(c) Hard-floor subtype DEFERRED** — needs non-canonical evidence
  (lab visit / author email / Imperial SAP report). Unchanged from
  v0.5.1.
- **LOW-RETRO-1 ships** — module docstring "are NOT in any open or
  paywalled source" → "are not in the canonical published paper"
  (consistent with ADR 0012 reverse-if path).
- **LOW-RETRO-2 ships** — "via SNU IEEE Xplore" → "(institutional
  access)" or "via institutional IEEE Xplore subscription" in module
  docstring + in-module honesty caveat + ADR 0012 References. Audit-
  findings narrative blocks (`.omc/plans/v0.4-audit-findings.md`,
  `v0.5-audit-findings.md`) intentionally preserved as historical
  record (D16 precedent — append-only).
- **No new `MaterialLabel.FLOOR_HARD` enum entry** (planner-locked
  OQ-10 default = no). Existing v0.5.1 honesty caveat block in
  `ace_challenge.py` is sufficient.
- **No `__schema_version__` flip** (OQ-4 unchanged; D8 binds Stage-2
  to A10 lab capture, which has not shipped).
- **No `MaterialAbsorptionBands` coefficient revision** (D14 5b
  pre-condition unchanged).

**v0.6.0 deliverables**:
- ACE adapter `_PIECE_EQUIVALENT_ABSORPTION_*` per-piece α tables (5
  rows × scalar + 5 rows × 6-band tuples); `_FURNITURE_BY_ROOM` per-room
  counts (6 rooms; Building_Lobby intentionally absent).
- ACE adapter helpers `_furniture_to_misc_soft_area` and
  `_misc_soft_surface_from_furniture` (private; unit-testable).
- `_build_room_model` wires the helper iff it returns non-None.
  `load_room` `notes` string declares MISC_SOFT presence/absence per
  room.
- `tests/test_misc_soft_furniture_budget.py` (+14 default-lane tests).
- ADR 0013 — TASLP-derived MISC_SOFT surface budget per room.
- ADR 0012 References — v0.6 cross-ref appended; LOW-RETRO-2 softening
  in DOI line. ADR 0012 body byte-identical to v0.5.1.
- `.omc/plans/v0.6-audit-findings.md`.
- OQ-6..OQ-10 marked `[x]` in `.omc/plans/open-questions.md`.
- `pyproject.toml` and `roomestim/__init__.py`: 0.5.1 → 0.6.0;
  `__schema_version__` stays `"0.1-draft"`.
- `RELEASE_NOTES_v0.6.0.md`.
- `docs/perf_verification_e2e_2026-05-08.md` (regenerated from gated
  E2E run with TASLP-MISC plumbing). v0.4 (`2026-05-06.md`) and v0.5
  (`2026-05-07.md`) perf docs preserved byte-identical.

**Empirical effect (v0.5 → v0.6 perf doc, 500 Hz Sabine errors)**:
- Lecture_1: +1.201 → +0.125 s (drop −1.076 s; v0.4 F4 hypothesis
  empirically supported).
- Office_1: +0.486 → +0.327 s (drop −0.160 s).
- Office_2: +0.410 → +0.179 s (drop −0.231 s).
- Meeting_1: +0.072 → −0.017 s (drop −0.089 s).
- Meeting_2: +0.061 → −0.012 s (drop −0.073 s).
- Lecture_2: −0.670 → −0.908 s (under-prediction deepens by 0.238 s;
  consistent with F3 ceiling-material hypothesis — separate v0.7+
  work; F3 stays DEFERRED).
- Building_Lobby: unchanged (excluded).
- Eyring monotonicity (`eyring ≤ sabine + 1e-9`) holds per-room
  per-band — runtime-asserted in the gated E2E.

**Why this scope and not the alternatives**:
- "Public API for `furniture_to_misc_soft_area`" rejected — no
  external consumer asks today; reverse-trigger to public when one
  does.
- "Per-furnishing Surface objects" rejected — explodes surface count
  without changing the Sabine integrand.
- "Add `floor_hard` MaterialLabel" rejected (OQ-10) — schema-impacting,
  no per-band data justifies splitting WOOD_FLOOR.
- "Building_Lobby per-area MISC_SOFT density" rejected (OQ-9) —
  compounds coupled-space modelling error.
- "Co-ship coefficient revision (F4a)" rejected — D14 5b cannot
  evaluate without F1 walls/ceiling materials (still INDETERMINATE
  per ADR 0012).
- "Wait for canonical-source materials" rejected — no canonical source
  exists for walls/ceiling per ADR 0012; v0.6 ships the part that has
  canonical evidence (TASLP §II-C furniture counts) and leaves the
  walls/ceiling half DEFERRED with the same explicit rationale as
  v0.5.1.

**Reverse if**:
- A textbook re-read or author lookup surfaces a per-piece α value
  that differs by > 30% on any band → patch the per-piece dicts and
  re-run gated E2E.
- An adapter consumer reports the synthesised MISC_SOFT surface area
  is wrong for their use case → revisit the helper formula and the
  per-piece α table.
- A lab visit produces a measured furnishings-class absorption per-
  room delta that disagrees with the synthesised area by > 30% →
  revisit.
- A Building_Lobby coupled-space ADR (v0.7+) ships first → re-evaluate
  whether B-L should be included with a coupled-space-aware budget.
- Hard-floor subtype confirmation (lab visit / author email) for any
  of Lecture_1 / Lecture_2 / Building_Lobby AND the confirmed subtype
  is not already in the MaterialLabel enum → revisit OQ-10 default.

**Cross-ref**: D14, D15, D16, ADR 0008, ADR 0009, ADR 0010, ADR 0011,
ADR 0012, ADR 0013, `.omc/plans/v0.6-design.md`,
`.omc/plans/v0.6-audit-findings.md`, `RELEASE_NOTES_v0.6.0.md`,
`docs/perf_verification_e2e_2026-05-08.md`,
`roomestim/adapters/ace_challenge.py` (TASLP-MISC plumbing + LOW-RETRO
softening).

---

## D18 — v0.7.0 ships WFS CLI ergonomics (Scope A) + Building_Lobby coupled-space exclusion ADR (Scope C)

**Date**: 2026-05-09

**Question**: D17 §"v0.6+ work item set updated" listed
"Building_Lobby coupled-space ADR — separate ADR on its own terms (v0.7+)"
as an explicit DEFERRED item. Independently, the v0.6 CLI surfaces a
raw `ValueError(kErrWfsSpacingTooLarge: ...)` at the default invocation
`roomestim run --algorithm wfs --n-speakers 8 --layout-radius 2.0`
because `f_max_hz` is hard-coded to 8000.0 in `roomestim/cli.py`. Which
of these ship at v0.7.0?

**Decision**:
- **Scope A — WFS CLI ergonomics ships**. `roomestim/cli.py` `place`
  and `run` parsers gain two new optional flags:
    - `--wfs-f-max-hz FLOAT` (default 8000.0) — exposes the
      previously-hardcoded constant.
    - `--wfs-spacing-m FLOAT` (default None — derived from
      `--layout-radius` and `--n-speakers`) — escape hatch for
      explicit spacing.
  The library-level `place_wfs(...)` `ValueError` API contract is
  UNCHANGED (kErrWfsSpacingTooLarge still raises with the same
  message). The constructive remediation message is built only at
  the CLI layer in `_run_placement(...)` via try/except, citing
  both remediation paths concretely:
    - "max safe `--wfs-f-max-hz` for current spacing is X = c/(2*spacing_m) = ... Hz"
    - "minimum safe `--n-speakers` for current f_max_hz is Y = ceil(baseline_len/(c/(2*f_max))) + 1 = ..."
- **Scope C — Building_Lobby coupled-space ADR ships** as ADR 0014.
  No code change (the v0.6 implicit exclusion in `_FURNITURE_BY_ROOM`
  is the same set of facts; ADR 0014 is the explicit citable
  decision-handle). ADR 0012 and ADR 0013 References gain one
  cross-link line each pointing forward to ADR 0014.
- **No `__schema_version__` flip** (D8 unchanged; A10 lab capture has
  not shipped).
- **No new MaterialLabel enum entries.** No new TASLP-MISC
  per-piece α revisions. No `MaterialAbsorptionBands` coefficient
  revision. No predictor changes. No perf doc regeneration (Scope A
  is CLI-UX-only; Scope C is bookkeeping-only).
- **v0.7.0 is structurally additive vs v0.6.0**: 100 → 104 default-lane
  tests (+4 in `tests/test_cli_wfs_ergonomics.py`); existing 100 tests
  remain byte-equal.

**v0.7.0 deliverables**:
- `roomestim/cli.py`: 2 new flags on `place` and `run` parsers
  (4 `add_argument` calls total, byte-symmetric); `_run_placement`
  signature gains `wfs_f_max_hz: float = 8000.0` and
  `wfs_spacing_m: float | None = None` kwargs; constructive `ValueError`
  re-raise wrapper around `place_wfs(...)`.
- `tests/test_cli_wfs_ergonomics.py` (NEW; +4 default-lane tests):
  constructive-error assertion; `--wfs-f-max-hz 300` success path;
  `--wfs-spacing-m 0.02` + `--wfs-f-max-hz 8000` success path;
  `--wfs-spacing-m` overrides derived spacing (verified via
  `x_wfs_f_alias_hz` round-trip in `layout.yaml`).
- `docs/adr/0014-building-lobby-coupled-space-exclusion.md` (NEW):
  full Status / Date / Predecessor / Decision / Drivers /
  Alternatives considered / Why chosen / Consequences / Reverse if /
  References sections.
- `docs/adr/0012-eaton-taslp-materials-not-in-paper.md` and
  `docs/adr/0013-taslp-misc-soft-surface-budget.md`: References gain
  one cross-link line each pointing to ADR 0014.
- `.omc/plans/v0.7-design.md` (NEW): scope-A + scope-C design doc.
- `.omc/plans/v0.7-audit-findings.md` (NEW): post-implementation
  audit findings.
- D18 (this entry; D14, D15, D16, D17 bodies untouched).
- `pyproject.toml` and `roomestim/__init__.py`: 0.6.0 → 0.7.0;
  `__schema_version__` stays `"0.1-draft"`.
- `RELEASE_NOTES_v0.7.0.md`.

**Why this scope and not the alternatives**:
- "Co-ship Building_Lobby coupled-space predictor" rejected — out
  of scope (per ADR 0014 §Alternatives considered (b)).
- "Co-ship `lecture_seat` α₅₀₀ revision (RELEASE_NOTES_v0.6.0.md
  flagged this as a v0.7+ candidate)" rejected — that revision
  re-anchors on F3 ceiling material entanglement and is a separate
  data-table ADR; v0.7 is locked to the two zero-risk items so the
  v0.6 numerical baseline is preserved.
- "Promote `kErrWfsSpacingTooLarge` constructive message to library-
  level `place_wfs(...)`" rejected — the library-level error is
  algorithmic (it does not know `n_speakers` or `layout_radius`,
  which are CLI-derived); building remediation strings inside the
  library would couple it to CLI semantics. Keeping the wrap at the
  CLI layer matches the existing layering.

**Reverse if**:
- An external consumer reports the `--wfs-spacing-m` override produces
  unexpected `x_wfs_f_alias_hz` (i.e. the explicit spacing is silently
  ignored) → patch and re-test.
- The constructive message's `min_safe_n` formula misfires on a
  `baseline_len == 0` edge case (currently guarded; reverse if a
  real consumer triggers it) → revisit the math in `_run_placement`.
- ADR 0014's reverse-trigger conditions fire (coupled-space predictor
  + per-sub-volume geometry; non-canonical effective-volume evidence;
  external-contributor predictor with > 50% B-L improvement) → see
  ADR 0014 §Reverse if.

**Cross-ref**: D14, D15, D16, D17, ADR 0008, ADR 0009, ADR 0010,
ADR 0011, ADR 0012, ADR 0013, ADR 0014,
`.omc/plans/v0.7-design.md`, `.omc/plans/v0.7-audit-findings.md`,
`RELEASE_NOTES_v0.7.0.md`, `roomestim/cli.py`,
`tests/test_cli_wfs_ergonomics.py`.

---

## D19 — v0.8.0 ships Lecture_2 ceiling/seat sensitivity bracketing (Scope A) + per-band ex-BL MAE snapshot (Scope B); F4a + ratification DEFERRED to v0.9+

**Date**: 2026-05-09

**Question**: D18 §"What stays deferred" carved out (1) Lecture_2
ceiling material hypothesis (F3) — canonical evidence path closed at
v0.7; (2) `MaterialAbsorptionBands` coefficient revision (F4a) — D14 5b
pre-condition unchanged; (3) `lecture_seat` α₅₀₀ revision — re-anchors
on F3 entanglement. The v0.7 critic verdict labelled v0.7 as borderline
ADR-theatre and demanded that v0.8 ship a residual-shrinking experiment
rather than another bookkeeping-only release. Which of these ship at
v0.8.0, and as commitment vs measurement?

**Decision**:
- **Scope A — Lecture_2 ceiling/seat sensitivity bracketing ships as
  measurement, NOT commitment.** Four committed variants and one
  optional bounding case (V0 baseline / V1 ceiling=`ceiling_drywall`
  / V2 lecture_seat α split unoccupied profile / V3 V1+V2 / **V4**
  ceiling=`wall_concrete` env-gated bounding case via
  `ROOMESTIM_BRACKET_V4=1`) are evaluated against the in-tree
  measured-T60 fixture
  (`tests/fixtures/ace_eaton_2016_table_i_measured_rt60.csv`). The
  bracketing test suite passes regardless of the numerical verdict
  (positive or null); the verdict is recorded in
  `docs/perf_verification_lecture2_bracket_2026-05-09.md` (auto-emitted,
  deterministic) + ADR 0015 §Consequences + `RELEASE_NOTES_v0.8.0.md`.
- **Scope B — per-band ex-BL MAE snapshot ships.** A frozen golden at
  `tests/fixtures/golden/per_band_mae_ex_bl_2026-05-09.json` records the
  v0.6 perf doc per-band-per-predictor MAE figures (mean of |err| over
  the 6 ex-BL rooms). The default-lane test
  `tests/test_per_band_mae_ex_bl_snapshot.py` recomputes MAE in-process
  every run; future predictor / adapter / per-band-table changes that
  shift any MAE force a one-line golden update + PR justification.
- **Library defaults UNCHANGED.** `_build_room_model(...)` gains an
  additive `overrides=` keyword (default `None` ⇒ byte-equal to v0.7).
  `MaterialLabel`, `MaterialAbsorption{,Bands}`, `_FURNITURE_BY_ROOM`,
  `_PIECE_EQUIVALENT_ABSORPTION_*`, `roomestim/place/wfs.py`,
  `roomestim/cli.py`, `roomestim/model.py` byte-equal to v0.7.
- **F4a + ratification DEFERRED to v0.9+** per ADR 0015 §Reverse-trigger.
  v0.8 verdict is **null** — V3 closes Lecture_2 |err| from −0.908 s to
  −0.879 s (bracketing only; not below the +/−0.5 s acceptance envelope)
  and regresses Meeting_1 / Meeting_2 by +0.108 s / +0.142 s @500 Hz
  Sabine vs V0. Single-coefficient swap is insufficient; v0.9 considers
  the broader F4a per-band sensitivity sweep + coupled-space modelling.

**v0.8.0 deliverables**:
- `roomestim/adapters/ace_challenge.py`: + `_RoomBuildOverrides` frozen
  dataclass; `_build_room_model` gains `overrides=` kwarg (additive);
  sibling helper `_misc_soft_surface_from_furniture_with_alpha(...)`
  for per-call seat α (the original
  `_misc_soft_surface_from_furniture` is byte-equal to v0.7).
- `tests/test_lecture_2_ceiling_seat_bracket.py` (NEW; +5 tests).
- `tests/test_per_band_mae_ex_bl_snapshot.py` (NEW; +2 tests).
- `tests/fixtures/ace_eaton_2016_table_i_measured_rt60.csv` (NEW;
  factual reproduction of v0.6 perf-doc measured-T60 column).
- `tests/fixtures/golden/per_band_mae_ex_bl_2026-05-09.json` (NEW).
- `docs/perf_verification_lecture2_bracket_2026-05-09.md` (NEW;
  deterministic; auto-emitted by Scope-A test #5).
- `docs/adr/0015-lecture-2-ceiling-seat-bracketing.md` (NEW; full
  Status / Date / Predecessor / Decision / Drivers / Alternatives
  considered (≥4) / Why chosen / Consequences / Reverse-trigger /
  References sections).
- `docs/adr/0014-building-lobby-coupled-space-exclusion.md`: References
  gain one cross-link line forward to ADR 0015.
- `.omc/plans/v0.8-design.md` (existed pre-executor; READ-ONLY).
- `.omc/plans/v0.8-audit-findings.md` (NEW; post-implementation; not
  authored at plan time).
- D19 (this entry; D14..D18 bodies untouched).
- OQ-11 appended to `.omc/plans/open-questions.md` under new "v0.8-design
  — 2026-05-09" section.
- `pyproject.toml` and `roomestim/__init__.py`: 0.7.0 → 0.8.0;
  `__schema_version__` stays `"0.1-draft"`.
- `RELEASE_NOTES_v0.8.0.md` (NEW; mirrors v0.7 release-notes shape;
  explicitly addresses the v0.7 critic SemVer-loose finding by framing
  v0.8 as substantive numerical-experiment release).
- Default-lane test count: 104 → 111 (+5 bracketing + +2 snapshot).

**Empirical Lecture_2 500 Hz Sabine bracketing results**:
- V0: 0.435 s (err −0.908 s vs measured 1.343 s).
- V1 ceiling=`ceiling_drywall`: 0.743 s (err −0.600 s; |err| reduced
  by 0.308 s).
- V2 unoccupied seat α: 0.322 s (err −1.021 s; |err| INCREASED by
  0.113 s — lower seat α reduces total absorption further).
- V3 combined: 0.464 s (err −0.879 s; |err| reduced by 0.029 s; below
  acceptance envelope; Meeting_1 +0.108 s + Meeting_2 +0.142 s
  regression at 500 Hz Sabine vs V0).

**Why this scope and not the alternatives**:
- "Ship F4a constrained sensitivity sweep at 2k/4k as v0.8 headline"
  rejected — broader sweep without sharpened prior; spawned per-room-
  per-band combinatorial space without a falsifying question. Deferred
  to v0.9 *gated on v0.8 outcome* (now v0.9 enters the broader sweep
  with the v0.8 null result as sharpened prior — single-coefficient
  ceiling/seat swap insufficient).
- "Ratify a winning variant as the v0.8 default" rejected — re-anchors
  on F3 ceiling-material entanglement; v0.8 verdict is null on (1)
  acceptance-envelope grounds anyway. Independent evidence still
  required per ADR 0015 §Reverse-trigger.
- "Ship Scope A only without per-band MAE snapshot" rejected — the
  snapshot is the infrastructure that makes future bracketing PRs
  auto-evaluated against residuals (critic M2 finding).
- "Write a coupled-space predictor (Cremer / Müller) as v0.8 headline"
  rejected — ADR 0014 §Alternatives considered (b) carved this out
  (needs per-sub-volume geometry the ACE adapter does not have).
- "Wait for non-canonical evidence" rejected — the v0.7 critic
  explicitly flagged this as confusing unknown ground truth with
  unfalsifiable hypothesis. The corpus IS the truth-table.

**Reverse if**:
- A v0.9+ release ratifies a variant as new default (requires all of
  ADR 0015 §Reverse-trigger conditions 1–3) → patch
  `ACE_ROOM_GEOMETRY` and/or `_PIECE_EQUIVALENT_ABSORPTION_*` and
  re-run gated E2E.
- The v0.8 perf doc appendix's md5 drifts on the same inputs (i.e.,
  Scope-A test #5 is no longer deterministic) → revisit emit-order
  invariants in the test.
- The per-band MAE snapshot fires on a routine PR (e.g., minor
  floating-point drift across dev environments) → tighten
  determinism (sort orders, accumulation order) or loosen the
  ±0.001 s tolerance with a recorded justification.
- A textbook re-read or author lookup surfaces a per-piece α value
  that differs from the V2 unoccupied profile by > 30% on any band
  (tightens the V2 representative-not-verbatim caveat).

**Cross-ref**: D14, D15, D16, D17, D18, ADR 0008, ADR 0009, ADR 0010,
ADR 0011, ADR 0012, ADR 0013, ADR 0014, ADR 0015,
`.omc/plans/v0.8-design.md`, `RELEASE_NOTES_v0.8.0.md`,
`roomestim/adapters/ace_challenge.py`,
`tests/test_lecture_2_ceiling_seat_bracket.py`,
`tests/test_per_band_mae_ex_bl_snapshot.py`,
`docs/perf_verification_lecture2_bracket_2026-05-09.md`.


---

## D20 — v0.9.0 ships A10a SoundCam substitute (synthesised) + A11 RT60 boost + Stage-2 schema flip + ADR 0016/0017; cross-repo PR proposal-stage; A10b in-situ DEFERRED (no closure)

**Date**: 2026-05-09

**Question**: D19 §"What stays deferred" carved out (a) Stage-2 schema
flip / A10 lab capture (D8); (b) F4a constrained sensitivity sweep;
(c) ratification of any Lecture_2 bracketing variant. The v0.8
strategic-position report `.omc/plans/v0.8-strategic-position-2026-05-09.md`
identified 8-release "wait for in-situ A10" deadlock as the 0%-progress
pattern blocking spatial_engine integration + cross-repo PR. The user
locked the v0.9 scope to "use clean public-dataset substitute" via
SoundCam. Which items ship at v0.9.0, and what is the substitute-vs-
in-situ honesty posture?

**Decision**:
- **A10a SoundCam corner substitute SHIPS (synthesised path)**. 3
  rooms (lab / living_room / conference) × synthesised rectangular-
  shoebox GT corners derived from SoundCam paper-published
  dimensions; per-corner Euclidean distance ≤ 10 cm. The synthesised
  path stops short of live-mesh download + extraction (deferred to
  v0.10+); the v0.9 honesty marker — "GT corners + RT60 derived from
  SoundCam paper-published dimensions; live-mesh corner extraction
  is v0.10+ upgrade path" — appears in 4 places (release notes + ADR
  0016 + ADR 0017 + each test docstring).
- **A11 SoundCam RT60 boost SHIPS**. Same 3 rooms × Sabine RT60 at
  500 Hz; |predicted - measured| / measured ≤ 0.20 enforced as a HARD
  test (not sensitivity-only bracket). Per-room defensible material
  maps recorded in `tests/fixtures/soundcam_synthesized/<room>/dims.yaml`
  rationale blocks. Empirical results: lab 0.28 % (predicted 0.351 s
  vs measured 0.350 s); living_room 5.57 % (0.425 s vs 0.450 s);
  conference 15.92 % (0.462 s vs 0.550 s). All 3 within ±20 %.
- **Stage-2 schema flip SHIPS**. `__schema_version__` flips
  `"0.1-draft"` → `"0.1"`; `RoomModel.schema_version` default flips
  `"0.1-draft"` → `"0.1"`. `proto/room_schema.json` (Stage 2 strict;
  `additionalProperties: false`; `version: const "0.1"`; authored
  byte-stable at v0.1.1 P3) becomes canonical. `proto/room_schema.draft.json`
  preserved for backward-compat reads. Reader `_load_schema` switch
  at `roomestim/io/room_yaml_reader.py:32` handles both variants;
  regression test in `tests/test_schema_stage2_validates.py`.
- **ADR 0016 SHIPS** — Stage-2 schema flip via SoundCam substitute
  with explicit reverse-criterion (in-situ ALWAYS overrides
  substitute; A10b mismatch → schema may revert to `"0.1-draft"`,
  cross-repo PR pauses).
- **ADR 0017 SHIPS** — A10-layout DEFERRED-with-classification
  (non-substitutable by any public dataset). A10 three-way
  decomposition: A10a PASS (substitute) / A10b DEFERRED (no closure)
  / A10-layout DEFERRED-with-classification.
- **Cross-repo PR remains PROPOSAL STAGE**. Proposal text shipped at
  `.omc/research/cross-repo-pr-v0.9-proposal.md`; merge decision is
  spatial_engine team responsibility, not v0.9.
- **Library defaults UNCHANGED.** MaterialLabel (9 entries),
  `MaterialAbsorption{,Bands}`, `_FURNITURE_BY_ROOM` (sum=276),
  `_PIECE_EQUIVALENT_ABSORPTION_*` (`lecture_seat` α₅₀₀ = 0.45,
  MISC_SOFT α = 0.40), `roomestim/place/wfs.py`, `roomestim/cli.py`,
  `roomestim/adapters/ace_challenge.py`, `roomestim/adapters/polycam.py`,
  `roomestim/reconstruct/floor_polygon.py` byte-equal to v0.8.0.
  ADRs 0001..0015 byte-equal.
- **A10b in-situ DEFERRED — no closure.** v0.9 does NOT claim A10
  fully closed; A10b remains user-volunteer-only (OQ-12a unchanged).
- **F4a / coupled-space / Lecture_2 ratification DEFERRED unchanged.**
  OQ-11 status reaffirmed; ADR 0015 §Reverse-trigger gates remain
  locked.

**v0.9.0 deliverables**:
- `roomestim/__init__.py`: 0.8.0 → 0.9.0; `__schema_version__`
  `"0.1-draft"` → `"0.1"` (2 line-flips).
- `roomestim/model.py`: `RoomModel.schema_version` default
  `"0.1-draft"` → `"0.1"` (1 line-flip at line 188).
- `pyproject.toml`: 0.8.0 → 0.9.0 (1 line-flip).
- `tests/fixtures/soundcam_synthesized/` (NEW; 11 files):
  `LICENSE_MIT.txt` + `README.md` + 3 × `dims.yaml` + 3 ×
  `GT_corners.json` + 3 × `rt60.csv`.
- `tests/test_a10a_soundcam_corner.py` (NEW; +3 default-lane tests).
- `tests/test_a11_soundcam_rt60.py` (NEW; +3 default-lane tests).
- `tests/test_schema_stage2_validates.py` (NEW; +1 default-lane
  test).
- `docs/adr/0016-stage2-schema-flip-via-substitute.md` (NEW).
- `docs/adr/0017-a10-layout-deferred-non-substitutable.md` (NEW).
- `.omc/research/cross-repo-pr-v0.9-proposal.md` (NEW).
- `.omc/plans/decisions.md`: D20 appended (D14..D19 bodies untouched).
- `.omc/plans/open-questions.md`: OQ-12a/b/c already appended at
  plan time; no further OQs raised.
- `RELEASE_NOTES_v0.9.0.md` (NEW).

**Empirical findings**:
- A10a corner errors: 0.00 cm / 0.00 cm / 0.00 cm (lab / living_room
  / conference); synthesised shoebox is exact by construction.
- A11 RT60 errors at 500 Hz Sabine: 0.28 % / 5.57 % / 15.92 % (all
  within ±20 % gate).
- Default-lane: 111 → 118 (+3 A10a + +3 A11 + +1 Stage-2 = +7).
  ruff clean.

**Why this scope and not the alternatives**:
- "Wait for A10b in-situ indefinitely" rejected — 8-release deadlock
  pattern (v0.8 strategic-position report).
- "Live SoundCam mesh download + extraction" deferred to v0.10+ — out
  of v0.9 scope; default-lane CI cannot depend on multi-GB downloads.
- "ARKitScenes substitute instead" rejected — Apple non-commercial
  license; ~hundreds-of-GB scope; minimum-leverage move is 3
  SoundCam rooms first (OQ-12c).
- "Stage-2 flip with no substitute (declare schema good enough on
  author judgement)" rejected — would break OQ-4 / D2 / D8 conditions
  (Stage-2 lock requires real-world fixture exercise; ≥3 captures
  per D2).
- "Co-ship F4a / Lecture_2 ratification at v0.9" rejected — ADR 0015
  reverse-trigger still gated by independent evidence; v0.9 is the
  Stage-2-flip + A10a/A11-substitute release, not another residual-
  shrinking experiment.

**Reverse-trigger / ratchet-safe behaviour**:
- ADR 0016 §Reverse-criterion: if A10b in-situ ever ships and
  disagrees with substitute (corner > 10 cm OR RT60 > 20 % on same
  predictor / adapter path), Stage-2 flip RE-EVALUATED; schema may
  revert to `"0.1-draft"` (reader switch already supports both);
  cross-repo PR pauses or follow-up PR adjusts.
- **In-situ ALWAYS overrides substitute.**
- ADR 0017 §Reverse-trigger: if a future public dataset ships VBAP-N
  layout GT, ADR 0017 is reverted and an A10a-layout substitute is
  added in v0.10+.

**Cross-ref**: D2, D8, D11, D14, D15, D16, D17, D18, D19,
ADR 0001..0015 (untouched), ADR 0016, ADR 0017,
`.omc/plans/v0.8-strategic-position-2026-05-09.md`,
`.omc/plans/v0.9-design.md`,
`.omc/research/cross-repo-pr-v0.9-proposal.md`,
`RELEASE_NOTES_v0.9.0.md`,
`tests/fixtures/soundcam_synthesized/`,
`tests/test_a10a_soundcam_corner.py`,
`tests/test_a11_soundcam_rt60.py`,
`tests/test_schema_stage2_validates.py`,
SoundCam (arXiv:2311.03517; purl.stanford.edu/xq364hd5023; MIT).

---

## D21 — v0.10.0 honesty correction; ADR 0016 §Reverse-criterion FIRED; ADR 0018 records substitute-disagreement; living_room REMOVED; Stage-2 schema marker REVERTED

**Date**: 2026-05-10 (v0.10.0 commit time).

**Decision**: v0.10.0 is a **honesty-correction release**. v0.9.0 critic
verdict (4.4/10) flagged a structural honesty leak: every SoundCam
fixture file carried `citation_pending: true`, but RELEASE_NOTES_v0.9.0.md
+ `docs/perf_verification_a10a_soundcam_2026-05-09.md` + ADR 0016
§Consequences advertised the values as "measured" without the
placeholder qualifier. Paper retrieval agents (cross-checked, 2026-05-10)
confirmed paper-retrieved RT60 (arXiv:2311.03517v2 Table 7 Schroeder
broadband mean): lab=0.158 s; conference=0.581 s; living_room=NO
authoritative dims per §A.2. Default 9-entry MaterialLabel enum +
paper-faithful material maps + Sabine 500 Hz prediction yields lab=0.254 s
(rel-err +60 %) and conference=0.449 s (rel-err -22.7 %); both outside
±20 %. ADR 0016 §Reverse-criterion items (1)/(2)/(3) ALL FIRE:

1. ADR 0018 records the substitute-disagreement.
2. Schema marker REVERTED `"0.1"` → `"0.1-draft"` in
   `roomestim/__init__.py` + `roomestim/model.py`.
3. Cross-repo PR proposal annotated WITHDRAWN at
   `.omc/research/cross-repo-pr-v0.9-proposal.md`; new
   `.omc/research/cross-repo-pr-v0.10-deferred.md` records restart
   criteria.

**Files touched (all additive / amend-in-place; v0.8/v0.9 invariants
byte-equal)**:
- `tests/fixtures/soundcam_synthesized/lab/{dims.yaml,rt60.csv,GT_corners.json}` — paper-retrieved values.
- `tests/fixtures/soundcam_synthesized/conference/{dims.yaml,rt60.csv,GT_corners.json}` — paper-retrieved values.
- `tests/fixtures/soundcam_synthesized/living_room/` — DELETED (paper §A.2: no authoritative dims).
- `tests/fixtures/soundcam_synthesized/README.md` — §Honesty-correction-2026-05-10 prepend + room-list update.
- `tests/test_a10a_soundcam_corner.py` — 3 → 2 tests; revealed-tautology disclosure framing per ADR 0018; renamed `_under_10cm` → `_smoke`.
- `tests/test_a11_soundcam_rt60.py` — 3 PASS-gate → 2 disagreement-record tests; expects ±20 % FAIL by recorded margins.
- `tests/test_schema_stage2_validates.py` — assertion inverted to `__schema_version__ == "0.1-draft"`.
- `roomestim/__init__.py` — version 0.9.0 → 0.10.0; `__schema_version__` `"0.1"` → `"0.1-draft"`.
- `roomestim/model.py` — `RoomModel.schema_version` default `"0.1"` → `"0.1-draft"`.
- `pyproject.toml` — version 0.9.0 → 0.10.0.
- `docs/adr/0018-soundcam-substitute-disagreement-record.md` (NEW).
- `docs/adr/0016-stage2-schema-flip-via-substitute.md` — §Status-update-2026-05-10 + ADR 0018 cross-link appended (body above byte-equal).
- `RELEASE_NOTES_v0.10.0.md` (NEW).
- `RELEASE_NOTES_v0.9.0.md` — §Honesty-correction-2026-05-10 prepend (body byte-equal beneath).
- `docs/perf_verification_a10_soundcam_2026-05-10.md` (NEW).
- `docs/perf_verification_a10a_soundcam_2026-05-09.md` — 1-line SUPERSEDED prepend (body byte-equal).
- `.omc/research/cross-repo-pr-v0.9-proposal.md` — WITHDRAWN prepend (body byte-equal).
- `.omc/research/cross-repo-pr-v0.10-deferred.md` (NEW).
- `.omc/plans/v0.10-design.md` (planner artefact, ships with this commit).
- `.omc/plans/decisions.md` — D21 (this entry).
- `.omc/plans/open-questions.md` — OQ-13 (a..e) appended; OQ-12a/b/c/OQ-11 reaffirmed.

**Empirical findings (paper-retrieved + default-enum Sabine)**:
- A10a corner errors: 0.00 cm / 0.00 cm (lab / conference); revealed tautology — synthesised-vs-synthesised. Living_room REMOVED.
- A11 RT60 disagreement-record: lab predicted 0.254 s vs measured 0.158 s = +60 % (signature: `default_enum_underrepresents_treated_room_absorption`); conference predicted 0.449 s vs measured 0.581 s = -22.7 % (signature: `sabine_shoebox_underestimates_glass_wall_specular`). Both OUT of ±20 % gate, recorded.
- Default-lane: 118 → 116 (-2 from living_room removals; A10a smoke + A11 disagreement-record per-room counts preserved for lab + conference; schema test invariant count preserved). ruff clean.

**Why this scope and not the alternatives**:
- "v0.9.1 patch" rejected — paper RT60 cannot be matched within ±20 % by any default 9-enum combination on lab; would force mass-fail or silent gate-weakening (new honesty leak Critic will flag).
- "v0.10 hybrid (add MELAMINE_FOAM + FIBERGLASS_CEILING + TILE_FLOOR enums)" rejected for v0.10 — library-coefficient revision chains into MaterialAbsorption + MaterialAbsorptionBands + many test files; scope explosion. Deferred to v0.11+ (OQ-13a).
- "Keep schema flip; just replace fixtures" rejected — ADR 0016 §Reverse-criterion explicitly designs a revert path on substitute-vs-paper disagreement; skipping the revert silently breaks the ratchet-safe contract.
- "Keep living_room with Figure 2 plot-axes-derived dims" rejected — plot-axes-derived is itself fabrication; open-layout + vaulted-ceiling + kitchen+stairway exposure breaks shoebox approximation regardless. Removal is honest.

**Reverse-trigger / ratchet-safe behaviour**:
- ADR 0018 §Reverse-criterion: if v0.11+ adds `MELAMINE_FOAM` +
  `FIBERGLASS_CEILING` + `TILE_FLOOR` enums with paper-faithful coefficient
  sourcing AND A11 substitute returns to ±20 % on lab + conference, the
  schema marker MAY re-flip `"0.1-draft"` → `"0.1"` per ADR 0019+ (TBD).
- If a future paper retrieval surfaces authoritative living_room dims,
  living_room MAY be re-introduced under a successor ADR.
- If v0.11+ critic flags conference disagreement-record framing as soft-
  FAIL gate weakening, conference test MAY be removed leaving only lab.

**Cross-ref**: D2, D8, D11, D14..D20 (byte-equal), ADR 0001..0017
(byte-equal except ADR 0016 §Status-update-2026-05-10 amendment), ADR 0018
(NEW), `.omc/plans/v0.10-design.md`, `RELEASE_NOTES_v0.9.0.md` (amended in
place), `RELEASE_NOTES_v0.10.0.md` (NEW),
`docs/perf_verification_a10a_soundcam_2026-05-09.md` (amended in place),
`docs/perf_verification_a10_soundcam_2026-05-10.md` (NEW),
`.omc/research/cross-repo-pr-v0.9-proposal.md` (amended in place),
`.omc/research/cross-repo-pr-v0.10-deferred.md` (NEW),
`tests/fixtures/soundcam_synthesized/`,
`tests/test_a10a_soundcam_corner.py`,
`tests/test_a11_soundcam_rt60.py`,
`tests/test_schema_stage2_validates.py`,
SoundCam (arXiv:2311.03517v2; purl.stanford.edu/xq364hd5023; MIT).

---

## D22 — v0.10.1 patch ships fabricated-quote redaction; codifies hybrid audit-trail-discipline pattern for same-week-old ADR corrections; new OQ-13f/g/h/i recorded

- **Date**: 2026-05-10b
- **Author**: oh-my-claudecode:planner (consulted by user after v0.10.0 critic verdict 7.6/10 composite + architect §Categorisation table flagged 3 v0.10.1 patch-scope items)
- **Predecessor**: D21 (v0.10.0 honesty correction; ADR 0018; living_room removed)
- **Decision**: v0.10.1 ships the following audit-trail-discipline pattern as the canonical pattern for same-week-old ADR corrections:
  - **For factual errors** (uncited quotes, drafting residue, fabricated extrapolations): HYBRID PATTERN — in-line redaction at the offending line + appended `§Status-update-YYYY-MM-DDb` block at the bottom of the ADR (after §References) recording the WHY (issue surfaced, action taken, cross-references).
  - **For structural errors** (wrong decision-rationale, contradicted alternatives, broken reverse-criterion): ADR SUPERSEDURE — new ADR with §Status: superseded marker on the original.
- **Drivers**: v0.10's ADR 0018 §Drivers item 2 line 46 quoted `living_room measured 1.121 s` without citation, contradicting v0.10's own §A.2 "no authoritative dims" claim. v0.10 critic flagged as MED honesty-leak. The error is FACTUAL not structural — the ADR's decision (fire reverse-criterion + remove living_room + revert schema) remains correct; only the §Drivers prose contained a fabricated quote.
- **Why this pattern, not the alternatives**:
  - "Pure append-only with `<del>`/`<ins>` HTML markup" rejected — unreadable in markdown ADR; markdown ADRs are read by humans, not version-control diff tools.
  - "ADR supersedure (new ADR 0019 + ADR 0018 marked superseded)" rejected — overkill for a single-line factual correction; supersedure is reserved for structural errors per OQ-13g resolution-candidate.
  - "Silent in-place correction (no §Status-update record)" rejected — violates audit-trail discipline; the `decisions.md` D22 entry would have no anchor in the ADR itself.
- **Reverse-trigger / ratchet-safe behaviour**:
  - If a future ADR has a STRUCTURAL error (decision-rationale wrong; alternatives contradicted), D22 does NOT apply — supersedure is required. (Recorded in OQ-13g resolution-candidate.)
  - If the §Status-update block grows beyond ~20 lines, escalate to ADR supersedure (the issue is no longer a single-line correction).
  - If the same ADR requires ≥ 2 §Status-updates within the same week, escalate to ADR supersedure (audit trail is becoming unreadable).
- **Cross-references**: D2, D8, D11, D14..D20 (byte-equal under v0.10.1), D21 (byte-equal under v0.10.1), ADR 0001..0017 (byte-equal under v0.10.1), ADR 0018 (in-line redaction at line 46 + appended §Status-update-2026-05-10b block), `.omc/plans/v0.10.1-patch.md` (this v0.10.1 plan), `.omc/plans/open-questions.md` (OQ-13f/g/h/i NEW; OQ-13a amended; OQ-12a status-update; OQ-13d resolved).

## D23 — v0.11.0 hybrid scope ships MELAMINE_FOAM + lab/conference band tightening + tense CI lint + in-situ protocol DOC stub

- **Date**: 2026-05-11
- **Author**: oh-my-claudecode:planner (consulted by user after v0.10.1 ship time DEFERRED 4 items into v0.11 hybrid scope; v0.10.1 `RELEASE_NOTES_v0.10.1.md` §What-stays-deferred names the closure point as v0.11).
- **Predecessor**: D22 (v0.10.1 audit-trail discipline; deferred 4 items into v0.11 hybrid scope).
- **Decision**: v0.11.0 ships **four** items that v0.10.1 explicitly DEFERRED:
  1. **MELAMINE_FOAM enum addition** (`MaterialLabel.MELAMINE_FOAM = "melamine_foam"`; `MaterialAbsorption[MELAMINE_FOAM] = 0.85`; `MaterialAbsorptionBands[MELAMINE_FOAM] = (0.35, 0.65, 0.85, 0.92, 0.93, 0.92)`). Source: Vorländer 2020 §11 / Appx A "melamine foam panel" / "acoustic foam absorber" (planner-locked envelope mid-value at v0.11; verbatim citation pending follow-up Vorländer lookup — flagged in ADR 0019 §References). Resolution of OQ-13a; ADR 0019 NEW.
  2. **Lab + conference band tightening** (OQ-13f). Conference band byte-equal + redundant structural-sign assertion `assert rel_err < -0.10`. Lab: §2.4 executor decision-point recorded `predicted = 0.162 s`, `rel_err = +2.40 %`, sub-branch A (PASS-gate recovered) landed. `_LAB_EXPECTED` replaced with PASS-gate values; lab umbrella test renamed `test_a11_soundcam_lab_disagreement_record` → `test_a11_soundcam_lab_band_record`; NEW companion `test_a11_soundcam_lab_pass_gate_recovered`.
  3. **README-tense CI lint** (OQ-13h) via standalone `scripts/lint_tense.py` + GitHub Actions step `Lint (tense)` in `.github/workflows/ci.yml`. ADR 0020 NEW.
  4. **In-situ A10b protocol DOC stub** (OQ-12a status-update) at `docs/protocol_a10b_insitu_capture.md` (90 lines). Capture commitment UNCHANGED — still user-volunteer-only.
- **Drivers**: 4 items were deferred into v0.11 at v0.10.1 ship time; v0.11 closes them. Closing 4 deferrals in one minor release is bounded scope (envelope target 500-650 added lines per v0.11 design plan §0.2.A).
- **Why this scope, not alternatives**: (a) "Ship MELAMINE_FOAM alone at v0.11.0; defer CI lint + protocol DOC + band tightening to v0.12" — rejected because the 4 items have low coupling and shipping together amortises one release cycle. (b) "Ship all 4 + FIBERGLASS_CEILING + TILE_FLOOR" — rejected per v0.11 design plan §0.1 enum-scope lock (minimum-leverage; FIBERGLASS_CEILING + TILE_FLOOR re-deferred under NEW OQ-14). (c) "Split into v0.10.2 lint-only patch + v0.11.0 enum-only minor" — rejected as artificial split.
- **Reverse-criterion**: if at executor §2.4 decision point lab rel_err had landed below -0.20 (negative overshoot), STOP and re-consult planner (most likely response: ratchet MELAMINE_FOAM α₅₀₀ DOWN within the 0.80 envelope OR re-cast the lab fixture map). At v0.11 ship time the empirical result was rel_err = +2.40 %, well within sub-branch A (PASS-gate); reverse-criterion did not fire. If CI lint first run had flagged > 3 files, STOP per v0.11 §0.4 STOP rule #7; at v0.11 ship time the live-repo run flagged 0 files.
- **Cross-references**: D2 (≥3 captures requirement for Stage-2 lock; unchanged under v0.11), D8, D11, D14..D21 (byte-equal under v0.11), D22 (audit-trail-discipline pattern; protected by ADR 0020 block-exclusion), ADR 0001..0018 (byte-equal under v0.11), ADR 0019 NEW (MELAMINE_FOAM), ADR 0020 NEW (CI tense lint), `.omc/plans/v0.11-design.md` (v0.11 plan), `.omc/plans/open-questions.md` (OQ-13a/f/h `[x]`, OQ-12a status-update, OQ-14 NEW).

## D24 — CI tense lint policy

- **Date**: 2026-05-11
- **Author**: oh-my-claudecode:planner (consulted in the v0.11 design pass).
- **Predecessor**: D22 (audit-trail discipline; v0.10.1 §Status-update / §Honesty-correction block pattern).
- **Decision**: CI lint mechanism = **standalone Python script `scripts/lint_tense.py`** invoked from a **GitHub Actions step `Lint (tense)`** in `.github/workflows/ci.yml` (NOT pre-commit hook; NOT pytest-collection-time check). Scope: `tests/fixtures/**/README.md`, `docs/adr/*.md`, `RELEASE_NOTES_v*.md` (excluding current-version `RELEASE_NOTES_v0.11.0.md`). Pattern: word-bounded `\bwe ship\b | \bship in v0\.[0-9]+\b`. Block exclusion: lines inside `## §Status-update-` or `## §Honesty-correction-` markdown sections (per D22 audit-trail-discipline). Per-line escape: end-of-line `# noqa: lint-tense` marker (case-insensitive; rationale comment recommended). False-positive policy: **ZERO blocking false-positives at v0.11 ship time** — at first run the live-repo lint flagged 0 files.
- **Drivers**: OQ-13h surfaced at v0.10.1 (`tests/fixtures/soundcam_synthesized/README.md` body lines 27/31/41-43 carried v0.9-tense framing beneath v0.10 §Honesty-correction prepend). v0.10.1 fixed the lines in place but did not prevent recurrence. v0.11 adds the CI lint to prevent the class of issue.
- **Why this mechanism, not alternatives**: see v0.11 design plan §0.1 row "CI lint mechanism (OQ-13h)" and §1 C13-C16. Pre-commit hook rejected (requires user installation; PR contributors can skip with `--no-verify`). Pytest-collection-time check rejected (lint is not a test). `git grep` one-liner inside GH Actions rejected (block-exclusion per D22 is not expressible as a single grep pattern). Allow-list-based file suppression rejected for v0.11 (zero false-positives at ship time does not justify the extra mechanism).
- **Reverse-trigger / ratchet-safe behaviour**: if the GH Actions step proves flaky at v0.12+ (false-positives blocking releases for week+ periods), switch mechanism to **pre-commit advisory** (warn only, no block). If false-positive rate exceeds **1 per 10 files** at v0.12+, switch to **allow-list-based suppression** (per-file `.lint-tense-allow` file). If a new present-tense leak lands in `docs/perf_verification_*.md` or `docs/architecture.md` (outside current scope), **expand scope** at v0.12+ under a successor ADR — NOT silently at v0.11.
- **Cross-references**: D22 (block-exclusion pattern precedent), D23 (v0.11.0 scope), ADR 0019 (same v0.11 release), ADR 0020 NEW (CI lint), OQ-13h (resolved at v0.11), `scripts/lint_tense.py`, `tests/test_lint_tense.py`, `.github/workflows/ci.yml`.

## D25 — Doc-ahead-of-implementation pattern (v0.11 in-situ protocol DOC precedent)

- **Date**: 2026-05-11
- **Author**: oh-my-claudecode:planner (consulted in the v0.11 design pass).
- **Predecessor**: OQ-12a status-update at v0.10.1 stated "v0.11 will ship in-situ protocol DOC only (no capture commitment)"; D25 codifies the pattern.
- **Decision**: When a future capability (here, A10b in-situ capture) is user-volunteer-only and has no committed timeline, but the implementation protocol benefits from being recorded BEFORE the capability lands, the protocol DOC is shipped at a planning-stable version (here, v0.11) under a `docs/protocol_*.md` path WITHOUT an accompanying ADR. The architectural decision (in-situ overrides substitute) already exists in a prior ADR (here, ADR 0016 §Reverse-criterion); the protocol DOC is OPERATIONAL, not architectural. When the capability lands (here, v0.12+ if user-volunteer captures arrive), a successor ADR codifies the capture-process invariants.
- **Drivers**: v0.11 implements OQ-12a's deferred protocol DOC commitment. D25 codifies the pattern for future "doc-ahead" cases — e.g., a live-mesh extraction protocol DOC could ship at v0.12 ahead of OQ-13e closure under the same precedent.
- **Why this pattern, not alternatives**: (a) "Wait until A10b capture lands, then write the protocol DOC retroactively" — rejected because protocol-after-implementation is the v0.9 honesty-leak failure mode (placeholder-as-measured). Writing the protocol BEFORE empirical data sets expectations; the protocol is therefore not back-fitted to make the implementation "pass". (b) "Ship the protocol DOC as an ADR" — rejected because the operational protocol is not an architectural decision; ADR 0016 already records the in-situ-overrides-substitute architecture. ADR inflation is avoided.
- **Reverse-trigger / ratchet-safe behaviour**: if v0.12+ user-volunteer captures fail because the protocol is too thin (missing edge cases — multi-room captures, non-shoebox rooms, partial-occluding furniture), expand the DOC inline at v0.12 under a successor ADR (e.g., ADR 0021) or D26 amendment. If the protocol DOC is found to contradict an established invariant (e.g., specifying ≥ 4 corners while a target room is L-shaped with 6 corners), patch under a successor D-decision.
- **Cross-references**: D22 (audit-trail discipline; doc-and-implementation parallel), D23 (v0.11.0 hybrid scope), ADR 0016 (architectural decision; in-situ overrides substitute), OQ-12a (status-update at v0.11; resolution-candidate unchanged on capture commitment), `docs/protocol_a10b_insitu_capture.md`.

## D26 — Predictor-adoption deferral policy (characterise first, decide second)

- **Date**: 2026-05-12
- **Author**: oh-my-claudecode:planner (consulted in the v0.12 design pass).
- **Predecessor**: ADR 0009 (D9 — Eyring parallel predictor; not default; runtime invariant `eyring ≤ sabine + 1e-9`). The v0.9-v0.10 honesty cycle taught that predictor changes without independent verification are silent claim-shifting (same failure mode as v0.9 "placeholder pretending to be measured").
- **Decision**: When a residual study (e.g., OQ-13b conference Sabine-shoebox residual) classifies a disagreement as predictor-approximation-effect (or potentially-so under an ambiguous classification), the v0.12+ release that ships the study does **NOT** also switch the default predictor. The decision to switch defaults is deferred to a successor release after the characterising data has been confirmed by ≥ 1 independent comparator (e.g., mirror-image-source method, or ray tracing) AND the disagreement signature is robust across ≥ 2 rooms. Concretely for v0.12 / OQ-13b: ADR 0021 records the classification (here: AMBIGUOUS at ratio 1.128), but `roomestim/reconstruct/materials.py::sabine_rt60` remains the default predictor; OQ-15 NEW records the deferred decision; v0.13+ comparator upgrade (mirror-image-source) is the next-step path.
- **Drivers**: v0.9-v0.10 honesty cycle (D21 + ADR 0018 §Drivers) explicitly walked back "PASS" framing that depended on a single predictor + placeholder data; D26 codifies the procedural complement to that walk-back. ADR 0009 (D9) recorded Eyring as parallel predictor (not default) specifically because a parallel predictor that diverges from Sabine in heavily-absorbed rooms is information, not yet a default-switch decision. v0.12 extends the pattern: characterise the divergence in ADR 0021; defer the default-switch decision to ADR 0022 at v0.13+ if applicable.
- **Why this policy, not alternatives**: (a) "Switch defaults at the same release as the characterising study" — rejected; the v0.9-v0.10 honesty leak proved that single-release decision-shifts under one-comparator data are silent claim-shifting. (b) "Defer the characterising study itself until ≥ 2 comparators are available" — rejected; the characterising data is itself useful (e.g., for OQ-15 framing) and waiting compounds the v0.11-still-OPEN disagreement signature accumulation. (c) "Treat the characterising study as deciding by default" — rejected; same as (a).
- **Reverse-trigger / ratchet-safe behaviour**: if a downstream consumer (e.g., spatial_engine reverb integration request) explicitly depends on Sabine being default at v0.13+ ship time AND the conference signature is closed under a mirror-image-source upgrade, the predictor-default switch may land in v0.13+ under ADR 0022. Without spatial_engine integration pressure, the natural cadence is: v0.12 characterise; v0.13+ comparator upgrade; v0.14+ default-switch decision. **D26 explicitly forbids INDEFINITE deferral** — if v0.13+ ships a Millington-Sette or ray-tracing predictor library that conclusively disambiguates the conference signature AND a second glass-heavy room confirms the signature, the predictor-default switch MUST land in v0.13+ under ADR 0022 (no further deferral permitted).
- **Cross-references**: D9 (Eyring as parallel predictor), D21 (v0.10 honesty correction; ADR 0018 walk-back precedent), D22 (audit-trail discipline), D23 (v0.11 hybrid scope), D27 NEW (verbatim-pending closure cadence — parallel cadence policy for citation closure), ADR 0009 (Eyring), ADR 0021 NEW (v0.12 conference characterising study; ambiguous classification recorded), OQ-13b (status-update at v0.12; remains `[ ]` pending v0.13+ comparator upgrade), OQ-15 NEW (predictor-adoption decision deferred to v0.13+), `.omc/plans/v0.12-design.md` §2.6.1 + §0.1 row "Item D predictor adoption action".

## D27 — Verbatim-pending closure cadence

- **Date**: 2026-05-12
- **Author**: oh-my-claudecode:planner (consulted in the v0.12 design pass).
- **Predecessor**: D22 (v0.10.1 audit-trail discipline; same-week-old ADR correction precedent via hybrid §Status-update pattern). v0.11 ADR 0019 §References shipped MELAMINE_FOAM α₅₀₀ = 0.85 with explicit "verbatim citation pending" annotation per D22 honesty-first; v0.12 closes (or re-defers) that pending flag.
- **Decision**: When v0.X ships a library coefficient with explicit "verbatim citation pending" flag in the ADR §References block (per v0.11 ADR 0019 precedent + D22 honesty-first), the next minor release v0.X+1 MUST close the pending flag via §Status-update on the original ADR (D22 hybrid pattern; factual change → in-place update + appended §Status-update block). The closure either (a) confirms the planner-envelope mid-value at verbatim; or (b) revises the value within the invariant envelope (with library row + test update + lab/conference re-run); or (c) escalates with a successor ADR if the verbatim value lands outside the invariant envelope (per §0.4 STOP rule precedent); or (d) re-defers to v0.X+2 with explicit re-deferral §Status-update IF the verbatim source is access-limited AND the planner-envelope was tight (≤ ±10 % range). Concretely for v0.12 / ADR 0019: §Status-update-2026-05-12 lands with closure-attempt outcome = SECONDARY-SOURCE corroboration (SoundCam paper arXiv:2311.03517v2 §A.1 NRC 1.26 consistent with envelope mid-value 0.85) + Vorländer verbatim PENDING re-deferred to v0.13+ under D27 reverse-criterion (d).
- **Drivers**: pending flags accumulate honesty debt — a "PENDING" annotation in an ADR §References block at v0.X is a promissory note that must be either paid (closed) or explicitly re-negotiated (re-deferred with rationale) at v0.X+1. Silent persistence is the v0.9-style placeholder-pretending-to-be-measured failure mode. v0.11 OQ-13a resolution at ship time explicitly designated v0.12 as the closure point; D27 codifies the pattern so future enum / coefficient additions follow the same cadence without per-release planner consultation.
- **Why this cadence, not alternatives**: (a) "Defer until verbatim source is acquired regardless of release count" — rejected; pending flags accumulate. (b) "Re-implement coefficient as planner-envelope-mid-value indefinitely until verbatim arrives" — rejected; the envelope-mid-value is intentionally provisional + D22 honesty-flagged. (c) "Pull the coefficient at v0.X+1 if verbatim is not available" — rejected; pulling working library code because a documentation flag is unclosed inverts the priority order (working code > documentation cadence). The next-minor §Status-update cadence balances honesty (the flag is addressed at the very next release) with engineering reality (the coefficient stays in place if envelope-bracketed + honestly flagged).
- **Reverse-trigger / ratchet-safe behaviour**: D27 permits **at most two consecutive re-deferral cycles** for access-limited verbatim sources. Schedule: v0.X NEW pending → v0.X+1 = FIRST re-deferral (allowed) → v0.X+2 = SECOND and LAST permitted re-deferral (allowed) → v0.X+3 = hard wall (closure MUST land OR PRIMARY-source switch under successor ADR). At the hard wall the closure MUST either land (verbatim acquired) OR escalate to a successor ADR that switches PRIMARY source (e.g., "Vorländer 2020 unavailable; switch to Bies & Hansen 2018 §A as PRIMARY"). For ADR 0019: v0.11 = NEW pending; **v0.12 = FIRST re-deferral (this release; reverse-criterion (d) invoked for the first time)**; v0.13 = SECOND and LAST permitted re-deferral; v0.14 = hard wall. **D27 explicitly forbids ≥ 3 consecutive re-deferral cycles** — that is the indefinite-promissory-note failure mode. (Wording-precision note: an earlier draft framed this as "at most ONE re-deferral cycle" while the operational schedule allowed two — the cycle count is FIRST + LAST = two, matching the hard-wall placement at v0.X+3.)
- **Cross-references**: D22 (hybrid pattern; in-place + §Status-update for factual changes; D27 applies the same pattern to next-release citation closure), D23 (v0.11 hybrid scope; ADR 0019 NEW shipped the pending flag), D26 NEW (parallel cadence policy for predictor adoption deferral), ADR 0019 (v0.11 NEW; v0.12 §Status-update-2026-05-12 records the closure-attempt outcome), OQ-13a (resolved at v0.11; v0.12 §Status-update annotation appended; verbatim re-deferred to v0.13+ under D27 reverse-criterion (d)), `.omc/plans/v0.12-design.md` §2.6.2 + §0.1 row "Item C verbatim source mechanism".

## D28 — Audit-trail process meta-rules (P1 hybrid pattern + P2 re-deferral cadence)
- **Date**: 2026-05-13
- **Author**: oh-my-claudecode:planner (consulted in the v0.13 design pass; recorded at v0.13.0 ship time per `.omc/plans/v0.13-design.md` §2.B).
- **Predecessor**: D22 (v0.10.1 hybrid §Status-update for same-week ADR corrections); D27 (v0.12 verbatim-pending closure cadence). D28 generalises D22 + D27 implementation experience into two named, reusable meta-rules so future planner rounds can cite the pattern by name (e.g., "applied D28-P1") without re-deriving rationale inline.
- **Decision**:
  - **D28-P1 (hybrid-§Status-update-for-factual-corrections)** — When an existing ADR requires a FACTUAL correction or refinement (citation completion, citation re-deferral with rationale, factual-list-of-covered-files growth, factual outcome of a prior characterising study, narrow value-shift inside a pre-existing invariant envelope), the canonical audit-trail mechanism is **in-place edit at the offending row + appended `## §Status-update-YYYY-MM-DD[-N]` block** at the bottom of the ADR (after §References). This pattern (i) preserves the original ADR's framing byte-equal except for the in-line redaction; (ii) records the WHY of the correction in a structurally-discoverable block; (iii) keeps audit history readable as the project ages (in contrast to pure-append `<del>` / `<ins>` HTML markup or silent in-place edits). The block-anchor `## §Status-update-` is also the canonical block-exclusion marker used by `scripts/lint_tense.py` (per ADR 0020 + D24), so the pattern is mechanically self-consistent across audit-trail tooling.
  - **D28-P2 (permitted-re-deferral-cadence-with-cycle-count-hard-wall)** — When an ADR carries a PENDING flag for a structurally-blockable closure (verbatim source access-limited, comparator-upgrade access-limited, capture-volunteer access-limited), the resolution cadence is bounded: at most **TWO consecutive re-deferral cycles** are permitted before a HARD WALL is reached. Schedule: v0.X = NEW pending → v0.X+1 = FIRST re-deferral (allowed; §Status-update on original ADR records WHY) → v0.X+2 = SECOND-AND-LAST permitted re-deferral (allowed; same mechanism) → v0.X+3 = HARD WALL (closure MUST land OR successor ADR switches the source / mechanism). Indefinite re-deferral is FORBIDDEN; the hard-wall release MUST either acquire the pending value or escalate to a successor ADR that switches PRIMARY source. P2 is D27's specific schedule generalised into a reusable cadence rule applicable to any structurally-blockable closure (not just citation pendency).
- **Applicability table** (the discriminator: which ADR-band edits go via P1 hybrid §Status-update vs. via a STRUCTURAL change requiring a NEW ADR or supersedure):
  - **P1 hybrid §Status-update** (in-place edit + appended `## §Status-update-` block):
    - §Drivers edits (factual additions / corrections to the WHY of an existing decision).
    - §Decision edits (factual value updates inside a pre-existing invariant envelope — e.g., α₅₀₀ shift inside [0.80, 0.95]; predictor coefficient row update inside D9 monotonicity invariant; lint scope-list-of-covered-files growth).
    - §References edits (citation closure, citation re-deferral with rationale, secondary-source corroboration record).
    - §Consequences edits when factual (outcome update: "PASS-gate recovered at rel_err = +2.40 %"; "v0.X first-run flagged N files").
  - **STRUCTURAL — NEW ADR or ADR supersedure** (not P1; P1 does NOT apply):
    - §Reverse-criterion edits (the conditions under which the decision is undone — changing these IS the decision).
    - §Alternatives considered edits (re-litigating the choice space — changing these reframes WHY chosen).
    - §Why chosen edits (re-framing the decision rationale).
    - §Consequences edits when reframed (e.g., reframing the conference disagreement-record signature from `sabine_shoebox_underestimates_glass_wall_specular` to `sabine_shoebox_approximation_for_glass_heavy_room` is a STRUCTURAL change → ADR 0021 NEW at v0.12, NOT a §Status-update on ADR 0018).
    - Mechanism / pattern edits (switching from grep-based lint to AST-based lint; adding a pre-commit hook; introducing a new allow-list-suppression mechanism; changing block-exclusion semantics).
- **Concrete examples (≥ 3 per pattern)**:
  - **P1 examples (D28-P1 applies)**:
    1. ADR 0019 §Status-update-2026-05-12 (v0.12.0) — Vorländer verbatim citation closure-attempt re-deferral (factual: citation status; secondary-source NRC 1.26 corroboration recorded; α₅₀₀ = 0.85 BYTE-EQUAL).
    2. ADR 0019 §Status-update-2026-05-12-2 (v0.13.0) — Vorländer verbatim SECOND re-deferral per D27 / D28-P2 cadence (factual: citation status; D27 schedule cycle 2; v0.14 hard wall preview).
    3. ADR 0020 §Status-update-2026-05-12 (v0.12.0) — lint scope expansion-1: adds `docs/perf_verification_*.md` + `docs/architecture.md` + `README.md` (factual: scope-list-of-covered-files grows; pattern + block-exclusion + per-line escape semantics UNCHANGED).
    4. ADR 0020 §Status-update-2026-05-13 (v0.13.0) — lint scope expansion-2: adds the remaining `docs/*.md` (non-adr / non-perf / non-architecture) + `.omc/research/*.md` (factual: scope-list grows further; mechanism UNCHANGED; the supersedure-relaxation clause below applies).
  - **STRUCTURAL examples (D28-P1 does NOT apply; NEW ADR is the correct mechanism)**:
    1. ADR 0018 NEW at v0.10 (substitute-disagreement-record) — could NOT be a §Status-update on a prior ADR because it introduced a new disagreement-record framing (structural reframing of the v0.9 PASS-style claim).
    2. ADR 0021 NEW at v0.12 (conference Sabine-shoebox residual characterising study) — could NOT be a §Status-update on ADR 0018 because the v0.12 study introduced a new `disagreement_classification` field to the test fixture AND reframed the conference signature as classification-dependent (Sabine-approximation regime vs coefficient-sourcing vs ambiguous). Structural change. (Note: at v0.12 ship time the classification landed AMBIGUOUS so the signature stayed byte-equal under STOP rule #11 — but the STRUCTURAL principle that signature reframing requires NEW ADR is the invariant.)
    3. Hypothetical v0.14+ ADR 0022 (PRIMARY-source switch from Vorländer 2020 to Bies & Hansen 2018 §A or NRC manufacturer datasheet) would be a STRUCTURAL change requiring NEW ADR — switching PRIMARY source is a mechanism / source change, not a factual correction inside an existing source's framing.
- **D28-P1 supersedure clause (Critic Round-2 Delta 1, factual-scope-list-growth relaxation)**:
  D28-P1 SUPERSEDES the "successor ADR" wording in **D24 reverse-trigger item 3** AND in **ADR 0020 §Reverse-criterion item 3** for the **factual-scope-list-growth case** — i.e., when D24's reverse-criterion condition fires solely because a new file glob must be added to `scripts/lint_tense.py`'s allow-list (the factual list of covered files grows but pattern / block-exclusion / per-line-escape / current-version-exclusion mechanism stays BYTE-EQUAL), the appropriate audit-trail mechanism is an **in-place §Status-update on ADR 0020** (D28-P1), NOT a successor ADR. The v0.12 ADR 0020 §Status-update-2026-05-12 (first scope expansion: perf + architecture + README) and the v0.13 ADR 0020 §Status-update-2026-05-13 (second scope expansion: remaining `docs/*.md` + `.omc/research/*.md`, landing under Item D of `.omc/plans/v0.13-design.md`) are BOTH governed by this relaxation precedent.
  **NOT covered by P1 relaxation (still successor-ADR territory)**: any mechanism / pattern change — e.g., switching from grep-based lint to AST-based lint, adding a pre-commit hook for lint enforcement, introducing a new allow-list-suppression mechanism (other than the existing `# noqa: lint-tense` per-line escape), or any change to the block-exclusion semantics (`## §Status-update-` / `## §Honesty-correction-`).
  Without this clause, D28-P1 would be a policy-fix-by-coincidence (D24 reverse-criterion item 3 would still nominally require a successor ADR for each scope expansion, contradicting v0.12 + v0.13 in-place precedent). With this clause, D28-P1 is policy-fix-by-design.
- **Drivers**:
  - D22 implementation experience at v0.10.1 → v0.12 → v0.13 showed the hybrid §Status-update pattern is the right mechanism for factual corrections / re-deferrals / scope-list growth on existing ADRs, but D22's text was scoped to "same-week-old ADR corrections" — repeated reuse across release cycles needed a generalised reusable rule.
  - D27 implementation at v0.12 → v0.13 → v0.14 introduced a concrete two-cycle-then-hard-wall cadence for citation pendency; the same structure applies to any access-limited closure (comparator-upgrade access, capture-volunteer access) and benefits from being generalised.
  - The v0.12 Critic verdict and the v0.13 design-pass Critic preview both flagged the audit-trail ambiguity around "factual §Status-update vs STRUCTURAL NEW ADR" — D28-P1's applicability table resolves the ambiguity by listing per-ADR-band rules.
  - D24 reverse-trigger item 3 (and the mirroring ADR 0020 §Reverse-criterion item 3) said "expand scope under successor ADR, not silently" — v0.12 implementation relaxed "successor ADR" to "§Status-update" by precedent; v0.13 follows. D28-P1's supersedure clause makes this relaxation explicit policy rather than precedent-by-action.
- **Why this codification, not alternatives**:
  - **(a) Leave the patterns implicit** — rejected. Every future planner round would re-derive the hybrid pattern rationale inline (the v0.10 enum-scope-lock anti-pattern: rationale duplicated across artefacts). Codifying the pattern under a named D-decision means future plans cite "applied D28-P1" without re-deriving.
  - **(b) Split into D28 (P1) + D29 (P2)** — rejected for single-D consolidation; the two patterns are tightly coupled (P2 USES P1's §Status-update mechanism for re-deferral recording). Critic Round-2 acknowledged the consolidation choice; reverse is to accept the split if a v0.14+ critic argues the two patterns drift into independent evolution.
  - **(c) Absorb into D22 / D27 inline edits** — rejected because D22 and D27 are dated, single-occurrence decisions; retro-editing them to add meta-rules is itself a STRUCTURAL change to those D-entries (violates D22's own audit-trail discipline). D28 NEW is the cleaner record.
  - **(d) Defer codification to v0.14+** — rejected. v0.13's Item D ADR 0020 §Status-update-2026-05-13 NEEDS D28-P1 + the supersedure clause as the authority that justifies §Status-update-not-successor-ADR. Deferring D28 would force the v0.13 ADR 0020 §Status-update body to re-derive the rationale inline (the same anti-pattern (a) above).
- **Reverse-trigger / ratchet-safe behaviour**:
  - If a v0.14+ critic argues the applicability table is incomplete (e.g., that some §Reverse-criterion edits could be P1 hybrid in narrow factual cases — a counter-example surfaces that the planner did not anticipate), refine D28 inline at the next release via §Status-update on this D28 entry (recursive self-application of P1 to a D-decision; sound because decisions.md uses the same §Status-update conventions as ADRs).
  - If P2's two-cycle cadence proves too lax (a single re-deferral cycle is the right discipline for a specific class of pendency), introduce D29 narrowing the P2 cadence for that class WITHOUT amending D28-P2 inline (mechanism / scope change for a P-rule is itself a STRUCTURAL change requiring its own D-decision per D28-P1 applicability table).
  - If a v0.14+ ADR demonstrates that the supersedure clause is itself unsound (e.g., a scope-list growth case where in-place §Status-update silently grows beyond what readers can audit), supersede ADR 0020 with ADR 0022+ and amend D28-P1's supersedure-clause text under a successor D-decision.
- **Cross-references**: **D22** (hybrid pattern source — v0.10.1 same-week ADR corrections; P1 generalises D22 from "same-week" to "any factual band"); **D24** (CI lint codification; D24 reverse-trigger item 3 + ADR 0020 §Reverse-criterion item 3 SUPERSEDED by D28-P1 for the factual-scope-list-growth case); **D26** (predictor-adoption deferral; parallel cadence policy structurally identical to P2's permitted-re-deferral cycle; D26's "characterise-first-decide-second" is P2-shaped); **D27** (verbatim-pending closure cadence; cycle-count discipline source — P2 is its generalisation); implementing artefacts: ADR 0019 (D27 instance; v0.12 §Status-update + v0.13 §Status-update-2 are both P1 cases), ADR 0020 (v0.12 §Status-update + v0.13 §Status-update-2 are both P1 cases governed by the supersedure clause), ADR 0021 (NEW at v0.12 — example of P1 NOT applying: structural reframing required NEW ADR); plan refs: `.omc/plans/v0.13-design.md` §0.1 (a)-(d) + §2.B + §0.0 rows for Items A / B / D.


## D29 — Output filename routing for parallel-track design plans (v0.12-web.0, 2026-05-15)

When a planner pass on a parallel track (web demo) would otherwise overwrite an
acoustics-track design plan at `.omc/plans/v0.X-design.md`, write to
`.omc/plans/v0.X-{track-suffix}-design.md` instead (here: `v0.12-web-design.md`).

Drivers: overwriting the shipped acoustics-track v0.12 plan would silently break six
ADR/OQ cross-references (honesty leak per D22 audit-trail discipline).

Reverse: if the acoustics track absorbs the parallel track (web demo merged into core),
the renamed file collapses into a single `v0.X-design.md` under a successor planner pass.

Cross-refs: D22; `.omc/plans/v0.12-web-design.md` §0.0 Item Z.


## D30 — Web-demo-as-parallel-track release versioning (v0.12-web.0, 2026-05-15)

The web demo ships under a parallel version string `v{core_version_at_branch}-web.N`
(here: `v0.12-web.0`). Core `pyproject.toml [project] version` stays at the acoustics-track
number (`0.13.0`); `roomestim_web/__init__.py::__version__` carries the parallel string.

Drivers: web demo and core acoustics track evolve at different cadences; coupling them under
a single SemVer would force lock-step releases.

Reverse: collapse to a single combined version if the web demo becomes mandatory for the core install.

Cross-refs: D29; ADR 0024.


## D31 — HRTF licensing and bundling policy (v0.12-web.0, 2026-05-15)

Bundle both PRIMARY (HUTUBS subject pp1; CC BY 4.0; TU Berlin) and FALLBACK (MIT KEMAR;
Public Domain) SOFA files in-repo under `roomestim_web/data/hrtf/`. SHA-256 pins captured in
`HRTF_ATTRIBUTION.md` at data-bundle commit time and verified by `tests/web/conftest.py`.
Attribution required at three locations: file-level `HRTF_ATTRIBUTION.md`, repo `README.md`
`## License` section, and the web UI footer.

Drivers: HF Spaces cold-start must not block on network; HUTUBS URLs rotate; combined bundle
is ~1 MB (well under the 10 MB §0.4 STOP threshold).

Reverse: switch to download-on-first-use if combined bundle exceeds 10 MB.

Cross-refs: D29; ADR 0024; ADR 0026.


## D32 — Tempdir lifecycle: bounded deque + atexit reaper, NOT per-call cleanup

**Date**: 2026-05-15b (v0.12-web.1).

**Context**: `_on_submit` in v0.12-web.0 used `tempfile.mkdtemp(prefix="roomestim_")` and never cleaned up. HF Spaces deployed the demo on an ephemeral container with bounded disk; abandoned tempdirs accumulated and eventually OOM-the-disk the container. But Gradio's `gr.File` output required the file to remain on disk after `_on_submit` returned (the user downloaded it lazily on tab navigation).

**Decision**: Held the last 8 `TemporaryDirectory` instances in a module-level `deque(maxlen=8)`. Deque eviction triggered `__exit__` on the oldest entry, which `shutil.rmtree`d its directory. An `atexit`-registered reaper walked `tempfile.gettempdir()` at process shutdown for any `roomestim_*` directories older than 4 h (`mtime` heuristic) and removed them. The 8-entry cap covered the typical HF Spaces user session; the 4 h `atexit` window caught abandoned containers without breaking active downloads.

**Alternatives considered**:
- **(a) `tempfile.TemporaryDirectory()` with `gr.State`-tracked cleanup**: Gradio's `gr.State` did not survive page reload, and the cleanup hook fired on user navigation, which could happen before the download completed. Rejected — race condition.
- **(b) `atexit`-only reaper without the deque cap**: process never exited in HF Spaces (long-running gunicorn worker), so atexit never fired until container cycle. Without the deque cap, every submit leaked until cycle. Rejected — leak window too large.
- **(c) Document as known and ignore**: rejected per code-reviewer MED-2 — HF Spaces disk OOM was a real failure mode, not a theoretical one.

**Reverse-criterion**: If OQ-18 (HF Spaces cold-start) measurement reveals containers cycle in < 1 h, tighten to 30-min `mtime` window at v0.12-web.2 per OQ-22 resolution path. If the 8-entry deque cap proves too low for power users (i.e. anyone who submits > 8 times in one session), raise to 16 or switch to a 2 h TTL eviction.

**Cross-ref**: §3-P4; OQ-22; `roomestim_web/app.py:_TEMP_REAPER` + `_reap_stale_tempdirs()`.


## D33 — MeshAdapter rename (NOT shim): single canonical class; PolycamAdapter retained as deprecated subclass alias

**Date**: 2026-05-15b (v0.12-web.1).

**Context**: v0.12-web.1 generalised the OBJ-only path to four mesh formats (`.obj`, `.gltf`, `.glb`, `.ply`). Two surfacing options were available: (i) rename `PolycamAdapter` → `MeshAdapter` and re-export the old name as a deprecated alias; (ii) keep `PolycamAdapter` as-is and add a new sibling `MeshAdapter` class that delegated.

**Decision**: Option (i) — rename. `MeshAdapter` lived in `roomestim/adapters/mesh.py` and carried the full mesh-parsing logic. `PolycamAdapter` became a 5-line subclass shim in `roomestim/adapters/polycam.py` that emitted one `DeprecationWarning` on first `.parse()` call per location. The rename was the cleaner option because: (a) the v0.1+ class name no longer matched its actual scope (it parsed much more than Polycam exports); (b) the convex-hull-of-projection geometry was mesh-format-agnostic, so a subclass added no behavioural value; (c) external callers (incl. `pipeline.py`, `test_adapter_polycam.py`, `test_binaural_renderer.py`, `test_3d_viewer.py`, `test_pipeline_integration.py`) could migrate to `MeshAdapter` at their own pace via the alias; (d) the alias-as-subclass pattern made `isinstance(PolycamAdapter(), MeshAdapter)` → True, so any duck-typing call sites continued to work byte-equal.

**Alternatives considered**:
- **(ii) New sibling `MeshAdapter` delegating to `PolycamAdapter`**: rejected because it froze the misleading `PolycamAdapter` name as the canonical implementation, perpetuating the v0.1-era misnomer; also doubled the maintenance surface (every behaviour change required touching two classes).
- **(iii) Add a `format=` kwarg to `PolycamAdapter.parse()` without rename**: rejected because the suffix dispatch already existed at the top of `parse()`; a kwarg would be redundant noise.

**Reverse-criterion**: If a v0.13+ user reports the `DeprecationWarning` is too noisy in HF Spaces logs, downgrade to `PendingDeprecationWarning` at v0.13-web.0. If a v0.14 release decides to drop `PolycamAdapter` entirely (full removal of the alias), that lands under a successor D-decision and a `RELEASE_NOTES_v0.14-web.0.md` "Breaking changes" callout.

**Cross-ref**: §2.2 (`roomestim/adapters/polycam.py` shim); §3-P1; ADR 0027; v0.12-web.0 ADR 0024 (parallel-track package boundary preserved); D6 (convex-hull-of-projection caveat unchanged).


## D34 — v0.14 ADR + OQ re-numbering audit-trail (ADR 0022/0023 → 0028/0029; OQ-17/18/19 → OQ-23/24/25)

**Date**: 2026-05-16 (v0.14 planner architect-revalidation absorption round).

**Context**: The v0.14-design.md planner draft (drafted 2026-05-13; `.omc/plans/v0.14-design.md`) planner-locked "ADR 0022 NEW" / "ADR 0023 RESERVED" + "OQ-17 NEW (Polygon ISM v0.15+)" / "OQ-18 NEW (Predictor-default switch v0.15+)" / "OQ-19 NEW (Per-band glass α revision v0.15+)". Between 2026-05-13 and 2026-05-16 the parallel web-track shipped two interim releases:

- **v0.12-web.0** (`cfea9cb`, 2026-05-15): allocated ADR 0024 (web-demo-separate-package) + ADR 0025 (binaural-demo-stack) + ADR 0026 (hrtf-dataset-selection) AND OQ-17 (HUTUBS subject-id stability; `.omc/plans/open-questions.md:185`) + OQ-18 (HF Spaces cold-start budget; `:197`) + OQ-19 (binaural WAV byte-exact reproducibility; `:208`) + D29 (HRTF licensing) + D30 (web-track versioning) + D31 (HRTF licensing details).
- **v0.12-web.1** (`0bef198`, 2026-05-16): allocated ADR 0027 (mesh-format-generalisation) AND OQ-20 (glTF `.glb` byte-equal; `:223`) + OQ-21 (PLY no-faces; `:240`) + OQ-22 (`_TEMP_REAPER` tightening; `:256`) + D32 (tempdir lifecycle; `decisions.md:1225`) + D33 (MeshAdapter rename; `decisions.md:1243`).

The original v0.14 ADR / OQ numbers therefore collided with already-shipped allocations. Shipping v0.14 with "ADR 0022" / "OQ-17 NEW" would silently overwrite existing audit-trail entries — a D22 / D28-P1 audit-trail honesty-leak.

**Trigger**: `.omc/plans/v0.14-architect-revalidation-2026-05-16.md` (architect READ-ONLY re-validation pass; verdict YELLOW — 4 amendments needed before executor takeoff). Architect memo §3 AMENDMENT 2 (lines 159-176) flagged the ADR-numbering collision as MAJOR; AMENDMENT 4(b) (lines 200-206) flagged the OQ-numbering collision as borderline MAJOR (bundled under MINOR sub-items for absorption efficiency).

**Decision**: v0.14 acoustics-track allocates the next-available slots per D22 / D28-P1 sequential-numbering audit-trail discipline:

- **ADR 0028 NEW** (replaces "ADR 0022 NEW"): combined hard-wall closure under path γ + ISM library landing (`roomestim/reconstruct/image_source.py`) + conference signature reframe/AMBIGUOUS-persist + ACE Office_1 ratio recorded + predictor-default DEFER decision per D26 with v0.15+ reverse-trigger. Combined as a single ADR to avoid ADR-inflation per D28-P1 single-D consolidation lesson.
- **ADR 0029 RESERVED** (replaces "ADR 0023 RESERVED"): predictor-default switch slot; ships at v0.14 ONLY if Item D reverse fires per v0.14-design.md §0.4 STOP rule #8; otherwise reserved for v0.15+.
- **OQ-23 NEW** (replaces "OQ-17 NEW"): Polygon ISM v0.15+ deferral. Resolution candidate per v0.14-design.md §3.1.
- **OQ-24 NEW** (replaces "OQ-18 NEW"): Predictor-default switch v0.15+. Resolution candidate per v0.14-design.md §3.1 + D26 reverse.
- **OQ-25 NEW conditional** (replaces "OQ-19 NEW conditional"): Per-band glass α revision v0.15+ if Item C branch C-iii fires.

Additionally, v0.14-design.md §10.1 ADR-supersession reverse-criterion's "ADR 0024" reference is bumped to **ADR 0030** (next-available after v0.12-web.0/web.1 + v0.14 acoustics-track allocations 0028/0029).

**Alternatives considered**:
- **(a) Keep ADR 0022/0023 + OQ-17/18/19 and force-overwrite v0.12-web.0/web.1 entries**: rejected per D22 + D28-P1 audit-trail honesty discipline (silent overwrite of existing audit-trail entries is forbidden). Would also require renumbering v0.12-web.0/web.1's already-shipped ADRs/OQs, which is post-hoc audit-trail mutation (also D22-forbidden).
- **(b) Allocate ADR 0022 + ADR 0023 to v0.14 acoustics-track AND argue the v0.12-web.0 planner deliberately jumped to 0024 to reserve 0022/0023 for v0.14**: the architect memo §3 AMENDMENT 2 (line 174) acknowledges this is a "viable reverse-reading" but flags that no explicit D-decision or planner artefact records the 0022/0023 reservation intent. Rejected on the precautionary principle: ship with the explicit safe allocation (sequential next-available) rather than rely on inferred reservation intent that could be re-litigated by a v0.15+ critic.
- **(c) Re-number all four v0.12-web.x ADRs (0024-0027) to 0022-0025 and ship v0.14 acoustics-track ADRs as 0026/0027**: rejected — post-hoc renumbering of already-shipped artefacts is D22-forbidden audit-trail mutation; would also invalidate cross-references in shipped RELEASE_NOTES_v0.12-web.0.md + RELEASE_NOTES_v0.12-web.1.md.

**Why chosen**: Sequential-next-available allocation is the unique audit-discipline-compliant choice given the v0.12-web.0/web.1 baseline. ADR 0028/0029 + OQ-23/24/25 + ADR 0030 supersession-target preserve audit-trail honesty without requiring any v0.12-web.x mutation. The collision was a consequence of parallel-track interim releases shipping between v0.14 planner-draft (2026-05-13) and v0.14 planner architect-revalidation absorption (2026-05-16) — a procedural finding, not a substantive plan-correctness issue.

**Consequences**:
- (+) v0.14-design.md re-numbered in place (~120 token-level rewrites: 73 ADR 0022→0028 + 10 ADR 0023→0029 + 5 file-path renames + 5 bare-number narrative updates + 1 supersession-target update + 10 OQ-17→23 + 7 OQ-18→24 + 6 OQ-19→25). New §Status-update-2026-05-16 absorption block at end of v0.14-design.md captures the audit trail.
- (+) v0.14-design.md §0 prologue NOTE added explaining the re-numbering reason for future v0.14 critic readers + v0.15+ planner readers.
- (+) D34 (this decision) captures the re-numbering audit-trail in the canonical D-decision log.
- (−) v0.14 substantive plan content unchanged (no Items A/B/C/D framing change; no path γ default-safe lock change; no [0.80, 0.95] envelope change; no MELAMINE_FOAM α₅₀₀ change; no lab A11 PASS-gate change; no ISM library API change); only mechanical / cross-reference adjustments. Plan-currency unaffected.
- (−) Future planner rounds (v0.15+) MUST consult both `.omc/plans/decisions.md` (for D-decision next-available slot) AND `docs/adr/` directory (for ADR next-available slot) AND `.omc/plans/open-questions.md` (for OQ next-available slot) at planner-draft time to avoid similar collisions when parallel-track releases ship between draft and executor takeoff.

**Reverse-criterion**:
- If a v0.15+ critic / archivist surfaces explicit documentation (planner artefact, code-comment, or commit message body) showing that v0.12-web.0 ADR allocator (commit `cfea9cb`) DID reserve 0022/0023 for v0.14 acoustics-track deliberately, append §Status-update on this D34 recording the reservation evidence. Does NOT revert the v0.14 ADR 0028/0029 allocation (already shipped); records the audit-trail finding for v0.16+ planner discipline.
- If v0.14 acoustics-track ships ADR 0028 and an unrelated v0.13.x or v0.12-web.x patch later needs to ship between v0.12-web.1 and v0.14 (allocating 0028+), bump v0.14's ADR allocation to the new next-available slot at v0.14 executor-time (re-absorb via second §Status-update on v0.14-design.md). Same applies to OQ-23/24/25.

**Cross-ref**:
- Architect memo: `/home/seung/mmhoa/roomestim/.omc/plans/v0.14-architect-revalidation-2026-05-16.md` (§3 AMENDMENT 2 + §3 AMENDMENT 4(b); 257 lines).
- Planner artefact (re-numbered in place): `/home/seung/mmhoa/roomestim/.omc/plans/v0.14-design.md` (§0 prologue NOTE; §Status-update-2026-05-16 absorption block at end).
- Interim release plans (collision source): `/home/seung/mmhoa/roomestim/.omc/plans/v0.12-web.1-design.md` (D32/D33 + OQ-20/21/22 source); `.omc/plans/open-questions.md:185,197,208,223,240,256` (OQ-17/18/19/20/21/22 entries).
- ADR allocation map at 2026-05-16: 0001..0021 (acoustics-track sequential) + 0024/0025/0026 (v0.12-web.0) + 0027 (v0.12-web.1); v0.14 acoustics-track allocates 0028/0029 + (0030 reserved for supersession-target).
- D-decisions: D22 (audit-trail-honesty), D28-P1 (hybrid pattern), D29 (web-track filename routing, v0.12-web.0), D30 (web-track versioning, v0.12-web.0), D31 (HRTF licensing, v0.12-web.0), D32 (tempdir lifecycle, v0.12-web.1), D33 (MeshAdapter rename, v0.12-web.1).


## D35 NEW — v0.14.0 hard-wall closure under path γ (honesty-leak fallback) via ADR 0028

**Date**: 2026-05-16 (v0.14.0 Item A executor pass; first sub-pass of the v0.14 release cycle).

**Context**: D27 (verbatim-pending closure cadence) + D28-P2 (permitted-re-deferral-cadence-with-cycle-count-hard-wall) bound the ADR 0019 melamine-foam α₅₀₀ verbatim-citation closure schedule at v0.11 NEW pending → v0.12 FIRST re-deferral → v0.13 SECOND-AND-LAST re-deferral → **v0.14 = HARD WALL**. A third consecutive re-deferral was forbidden; v0.14.0 had to close OR escalate to a successor ADR switching PRIMARY source. The v0.14 planner-locked DEFAULT closure path was **γ (honesty-leak fallback)** per `.omc/plans/v0.14-design.md` §0.0 row "Item A" (default-safe lock — does not require external acquisition success); path α (verbatim Vorländer 2020 §11 / Appx A acquired) and path β (PRIMARY-source switch to Bies & Hansen 2018 §A or NRC manufacturer datasheet with extracted verbatim value) were OPPORTUNISTIC upgrades per §0.4 STOP rule #7.

**Trigger**: v0.14 Item A executor pass (2026-05-16). The MANDATORY one-shot pre-flight verbatim-citation grep across `docs/`, `roomestim/`, and `tests/` (per §0.4 STOP rule #7 + §9 Critic preview item 6) returned ONLY §References row labels + closure-attempt outcome records inside `docs/adr/0019-melamine-foam-enum-addition.md` (lines 114, 116, 165, 173, 180, 182-183, 193, 198). NO extracted verbatim α₅₀₀ value with page + row + panel-thickness landed inside the [0.80, 0.95] envelope. STOP rule #7 did NOT fire; path γ default-safe lock held.

**Decision**: v0.14.0 closed the D27 / D28-P2 hard-wall cadence at cycle 3 under **path γ (honesty-leak fallback)** via successor **ADR 0028 NEW** (`docs/adr/0028-hardwall-closure-and-ism-adoption.md` §Decision sub-item 1). Concretely:

- **α₅₀₀ value at v0.14**: **0.85 BYTE-EQUAL** to v0.11 / v0.12 / v0.13 (envelope-bracketed [0.80, 0.95]; coefficient-invariant test `test_melamine_foam_a500_in_expected_range` preserved). MELAMINE_FOAM enum entry RETAINED. Library row BYTE-EQUAL.
- **Lab A11 PASS-gate at v0.14**: **rel_err = +2.40 % BYTE-EQUAL** to v0.11 / v0.12 / v0.13 (no library state change under γ).
- **§References reframe** (per D28-P1 factual band): PRIMARY-source row "Vorländer 2020 §11 / Appx A (PRIMARY, verbatim pending)" reframed in-place to a multi-source envelope record (Vorländer PRIMARY envelope-bracketed verbatim unattained through D27 cadence exhaustion + Bies & Hansen 2018 §A secondary unverified + NRC manufacturer datasheets secondary unverified + SoundCam paper arXiv:2311.03517v2 §A.1 NRC 1.26 corroboration consistent with envelope mid-value). Recorded at ADR 0019 §References + appended §Status-update-2026-05-16 (v0.14.0) HARD-WALL CLOSURE block per D28-P1 hybrid pattern.
- **Honesty-leak entry preserved** (per ADR 0018 §Drivers lineage): explicit "verbatim citation unattainable through three ship cycles + external-acquisition exhaustion at v0.13 documented Option B (channels NOT investigated)" as the truthful audit-trail record of WHY path γ was the closure path. NOT a softening of the hard wall; the entry IS the audit-trail.
- **Cycle count is final**: NO further D27 re-deferral cycles permitted for this ADR. v0.15+ may §Status-update ADR 0028 upgrading γ → α/β if verbatim later surfaces per ADR 0028 §Reverse-criterion item 1, but the cadence-bound closure landed at v0.14.0.

**Drivers**:
- **D27 hard wall reached at v0.14.0 cycle 3** — the cadence schedule that v0.11 design pass + v0.12 §Status-update + v0.13 §Status-update-2026-05-12-2 collectively previewed. D27 + D28-P2 forbade a third consecutive re-deferral; v0.14.0 had to close. Re-deferral would have been an indefinite-promissory-note honesty leak per D27 + D28-P2 forbidden-indefinite-deferral discipline.
- **Path γ default-safe lock at planner-time** — v0.13.0 ship-time documented external acquisition channels (SNU library ILL, OA mirrors, publisher OA page) as Option B "channels NOT investigated" per ADR 0019 §Status-update-2026-05-12-2 lines 196-200. The planner could NOT assume path α or β would materialise at executor-time; default-safe lock was γ (no fabrication risk; D27 hard wall absolutely satisfied; honesty discipline preserved per ADR 0018 lineage).
- **STOP rule #7 OPPORTUNISTIC reverse not fired at executor-time** — the MANDATORY one-shot pre-flight verbatim-citation grep returned no extracted verbatim α₅₀₀ value with page + row + panel-thickness inside the [0.80, 0.95] envelope at the v0.14 Item A executor pass.
- **D28-P1 hybrid-§Status-update pattern applicable** — citation closure-path is a §References factual band per D28-P1 applicability table; in-place §References edit + appended §Status-update block on ADR 0019 is the canonical mechanism. PRIMARY-source SWITCH under path β would have been STRUCTURAL (mechanism / source change → NEW ADR per D28-P1 applicability table) — which ADR 0028 NEW is, as the closure-path record + the path β OPPORTUNISTIC reverse anchor.

**Why this decision, not alternatives**:
- **(a) v0.15 hard wall (third re-deferral)** — rejected per D27 + D28-P2 forbidden-indefinite-deferral clause. A third re-deferral would make the cadence rule a dead letter.
- **(b) Path α / β closure at v0.14 (verbatim acquired mid-cycle)** — would have been the OPPORTUNISTIC upgrade per §0.4 STOP rule #7 if verbatim landed mid-cycle. Did NOT fire at the Item A executor pass; reserved for v0.14.x patch OR v0.15+ per ADR 0028 §Reverse-criterion item 1.
- **(c) Remove MELAMINE_FOAM enum entry at v0.14** — rejected. Removing the enum would have (i) regressed the lab A11 PASS-gate to the pre-v0.11 state (default 9-entry enum systematically under-represents treated-room absorption per ADR 0018 §Drivers item 4); (ii) invalidated the v0.11 + v0.12 + v0.13 audit trail; (iii) been a STRUCTURAL regression needing a much stronger honesty basis than "verbatim unattained". Path γ retained the enum + honestly documented the citation gap.
- **(d) Treat path γ as a 4th re-deferral framed as closure** — rejected as the v0.9-style silent claim-shifting failure mode. Path γ explicitly recorded the honesty-leak entry (verbatim unattained + external-acquisition exhaustion); cycle count is final; v0.15+ §Status-update can upgrade γ → α/β if verbatim surfaces but cannot re-open the cadence cycle (per ADR 0028 §Reverse-criterion item 4 — "do NOT relax path γ to 'verbatim pursued indefinitely' (would be 4th re-deferral, FORBIDDEN by D27 / D28-P2)").

**Reverse-criterion / ratchet-safe behaviour**:
- If verbatim Vorländer / Bies & Hansen / NRC datasheet surfaces at v0.14.x patch OR v0.15+, append §Status-update on ADR 0028 recording the closure-path upgrade γ → α/β per D28-P1 factual band (no new D-decision needed; D35 is the v0.14.0 closure record, not a perpetual policy). If extracted value lands inside [0.80, 0.95] envelope, library row BYTE-EQUAL; if OUTSIDE envelope, v0.14.x patch lands library row update + coefficient-invariant test re-run + lab A11 re-run per ADR 0028 §Reverse-criterion item 1.
- If a v0.15+ critic argues path γ honesty-leak undermines D27 framing, refine ADR 0028 §Drivers inline via §Status-update; do NOT relax path γ to "verbatim pursued indefinitely" (FORBIDDEN per above).
- D35 does NOT supersede D27 or D28-P2; D27 + D28-P2 remain the cadence-policy decisions; D35 is the SPECIFIC instance closure record for ADR 0019's verbatim-citation cadence at v0.14.0. Future cadence instances (other ADRs with PENDING citations) continue to be governed by D27 + D28-P2.

**Cross-references**:
- ADRs: **ADR 0028 NEW** (`docs/adr/0028-hardwall-closure-and-ism-adoption.md` §Decision sub-item 1 records the path γ closure + the path α/β OPPORTUNISTIC reverse anchor); **ADR 0019 §Status-update-2026-05-16 (v0.14.0) HARD-WALL CLOSURE block** records the cycle-3 closure under path γ (cross-ref to ADR 0028); ADR 0018 (substitute-disagreement record; §Drivers honesty-leak lineage source).
- D-decisions: D22 (audit-trail hybrid pattern), D27 (verbatim-pending closure cadence; this D35 is its v0.14.0 cycle-3 closure record), D28-P1 (hybrid §Status-update pattern + applicability table; in-place §References edit + appended §Status-update block on ADR 0019), D28-P2 (permitted re-deferral cadence with cycle-count hard-wall; this D35 closes cycle 3), D34 (v0.14 ADR + OQ re-numbering audit-trail; ADR 0028 next-available slot allocation).
- OQs: OQ-13a (CLOSED at v0.14 via path γ HARD-WALL CLOSURE — flip `[ ]` → `[x]` landed at Item A + B executor pass), OQ-16 (CLOSED at v0.14 — path γ default locked).
- Plan: `.omc/plans/v0.14-design.md` (§0.0 row "Item A", §2.A detailed design, §0.4 STOP rule #7, §5.5 lab A11 PASS-gate preservation gate, §5.7 ADR presence checks, §10.1 ADR 0028 framing); architect re-validation memo: `.omc/plans/v0.14-architect-revalidation-2026-05-16.md` (verdict YELLOW; §2.2 STOP rule #7 NOT FIRED verification at architect pass; re-confirmed at Item A executor pass).
- Release: `RELEASE_NOTES_v0.14.0.md` (Item A "What v0.14 ships" §HARD-WALL CLOSURE entry).


## D36 NEW — Web data bundle prohibited; fetch-script + opt-out background (v0.12-web.4)

**Date**: 2026-05-17 (v0.12-web.4 executor pass)

**Context**: ADR 0026 §Reverse-criterion deferred SOFA bundle to "download-on-first-use via
`scripts/fetch_web_data.py`" once the combined bundle exceeded 10 MB. HUTUBS (1.36 GB zip)
exceeds HF Spaces cold-boot budget; KEMAR (2.5 MB) and LibriVox trimmed WAV do not.

**Decision**: HUTUBS is never auto-downloaded. KEMAR SOFA + LibriVox WAV are auto-fetched
via a daemon background thread (`_ensure_web_data()` in `roomestim_web/app.py`) at
`build_demo()` call time. Env `ROOMESTIM_WEB_AUTO_FETCH=0` disables all auto-fetch for
CI / air-gapped environments.

**Reverse**: If HF Spaces cold-boot timeout (<60 s) is exceeded due to KEMAR download → switch
to pre-bundled stub HRTF or accept no binaural demo on first boot (v0.12-web.5).

**Cross-refs**: ADR 0029 NEW, ADR 0026 §Status-update-2026-05-17, D31, D32, OQ-26.


## D37 NEW — HF Spaces system deps via `packages.txt` + boot-time UX (v0.12-web.6)

**Decision**: HF Spaces system packages (notably `ffmpeg` required by
`scripts.fetch_web_data.fetch_librivox`) are declared in `packages.txt` at repo root
(HF Spaces auto-detects). Boot-time binaural-status Markdown shows "데이터 다운로드 중"
or "데이터 미준비" anchored to `_ensure_web_data()` return value, eliminating the
"empty tab before first click" UX hole observed in v0.12-web.4/5 review.

**Why**: HF Spaces does not provide `ffmpeg` in the default Python image; without
`packages.txt`, `fetch_librivox()` fails with `ffmpeg not found in PATH` and the
binaural demo silently never populates. UX gap: the binaural-status Markdown was
only updated on first `_on_submit` click — before that, the tab was blank with no
indication of why.

**How to apply**: any new system-level deps go into `packages.txt`; any new
boot-time prep status goes through `_ensure_web_data()` return + `build_demo()`
initial-value branch (do NOT introduce a parallel status mechanism).

**Reverse**: if HF Spaces switches to a base image with ffmpeg pre-installed,
`packages.txt` can be removed (no harm if kept). If `_ensure_web_data()` becomes
async-only (e.g. lazy on-demand fetch), the boot-time branch in `build_demo()`
becomes vestigial — remove with v0.12-web.x.

**Cross-refs**: ADR 0029 §B (background fetch), packages.txt NEW, OQ-28 NEW
(URL monitoring), code-review 2026-05-17 위험 list item 1 + 3.


## D38 NEW — Predictor-default cascade ISM > Eyring (v0.15.0)

**Decision**: The default RT60 predictor cascade at v0.15.0 is
`predict_rt60_default(room, area_dict)`:
1. If `is_rectilinear_shoebox(room)` AND `prefer_ism=True` (default) →
   `image_source_rt60(...)` (ISM).
2. Else → `eyring_rt60(...)` (Eyring fallback).
3. Sabine is **not** the default; it remains side-by-side for comparison.

**Why**: ADR 0028 §Reverse-criterion item 2 + D26 forbidden-indefinite-deferral.
Office_1 (ratio 2.0059) + conference (ratio 5.0537) both > 1.15 confirmed
signature → switch MUST land at v0.15+. Failing to land would have made D26
a dead letter.

**How to apply**: any new acoustic surface that reports a single "headline"
RT60 should query `default_rt60_500hz_s` / `default_predictor_name`, NOT
`sabine_rt60_500hz_s`. Sabine remains valid as a comparison metric.

**Reverse**: if ISM produces clearly-wrong RT60 (Sabine/Eyring ≤ ISM invariant
violated, or > 3-room user feedback complaining "ISM too high") → expose
`prefer_ism` UI toggle and/or supersede ADR 0030 with ADR 0031 (would require
fresh measured-room evidence).

**Cross-refs**: ADR 0030 NEW, ADR 0028 §Reverse-criterion item 2, ADR 0028
§Status-update-v0.15.0, ADR 0009 (Eyring runtime invariant), D26, D27, OQ-30.

## v0.16.0 D-decision allocation (2026-05-18)

**D39** — `roomestim/edit.py` placement (RoomModel evolve helper API).
`evolve_room` / `evolve_surface` / `evolve_room_material` / `evolve_room_materials_bulk`
live in `roomestim/edit.py` (not model.py — shape-only; not reconstruct — RT60
prediction). D39 rationale: edit = shape-transition lane, natural home for v0.17
`add_obstacle()` / `remove_speaker()` additions.

**D40** — Manual Apply button (acoustic recompute trigger, not auto-debounce).
ISM cascade ~1.9 s × 5 rapid changes = ~9.5 s queue; manual button = single commit
point. Implementation: `_on_apply_overrides` in `roomestim_web/material_override.py`.

**D41** — Blueprint y-down screen ⇔ z-up world coordinate convention.
Blueprint x = RoomModel x (right), blueprint y = RoomModel z (forward, north-up).
Architectural drawing standard. `ax.set_ylabel("z (forward, m, north-up)")`.

**D42** — Engine validation precedence: CLI flag > ENV var > default ON.
`--validate-engine PATH` > `SPATIAL_ENGINE_REPO_DIR` > hardcoded default.
`--no-engine-validation` is mutually exclusive with `--validate-engine`. Default
backward-compat (validation ON).

**D43** — ADR 0009 invariant on evolved rooms. Material change → absorption
change → ISM + Eyring both change. Invariant `ism_rt60 ≥ eyring_rt60 - 1e-6`
must hold on ALL evolved rooms. Regression lock: 50 random seeds × 10 materials.

**New ADRs this cycle**: ADR 0031 (material override policy), ADR 0032 (blueprint
2D export), ADR 0033 (engine validation toggle). ADR 0030 §Status-update-v0.16
added (Items I/J/K). OQ-31 NEW (multi-engine schema target deferral, v0.18+).

## v0.17.0 D-decision allocation (2026-05-19)

**D44** — Object schema + backward parse 0.1-draft → 0.2-draft.
`RoomModel.objects: list[Object] = []` 신규 필드. `room_yaml_reader.py` schema_version
분기: `"0.1-draft"` → `objects=[]` 자동; `"0.2-draft"` → `objects` 키 파싱.
`room_yaml.py` 항상 `"0.2-draft"` write + `objects:` 무조건 emit.
**Scope**: core. **Reverse if**: 외부 consumer가 0.2-draft YAML unknown field로 fail
보고 → `roomestim export --schema 0.1` flag 도입 또는 OQ-36.
**ADR ref**: ADR 0034 §B.

**D45** — USDZ backend = `usd-core` PyPI wheel (`pyusd` deprecated → rejected).
`[project.optional-dependencies] usd = ["usd-core>=24.0; python_version >= '3.10'"]`.
gLTF backend = `trimesh` (기존 core dep — extras 추가 없음).
**Scope**: export. **Reverse if**: `usd-core` wheel 미제공 / numpy 충돌 발견 →
USDZ scope drop + v0.17.1 patch 또는 USDZ self-writer (~300 LoC).
**ADR ref**: ADR 0035 §A.

**D46** — Column → ISM 5 추가 surface; door/window → wall α override.
column: `predictor._objects_to_surfaces(objects)` → 4 측면 + 1 top surface (CCW
polygon, ADR 0002 convention); `_shoebox_surface_areas_and_alphas`에 머지.
door/window: `predictor._objects_to_wall_alpha_overrides(objects)` →
`{wall_index: [(area_m2, override_material), ...]}` dict; effective α =
`α_wall × (1 − Σfrac) + Σ(α_obj × frac)`.
**Scope**: acoustic. **Reverse if**: ADR 0009 invariant 위반 (`ism_rt60 < eyring_rt60
− 1e-6`) → ISM 분기 비활성 fallback.
**ADR ref**: ADR 0034 §C, ADR 0030 §Status-update-v0.17 Item Q.

**D47** — door/window α override + ADR 0009 invariant + ADR 0030 cascade 회귀 lock
(50 random seeds × 3 object kind = 150 instance).
`tests/test_objects_acoustic_invariant.py` NEW 6 케이스: invariant `ism_rt60 ≥
eyring_rt60 − 1e-6` + `default_predictor_name ∈ {"image_source", "eyring"}` (D38
cascade) 검증.
**Scope**: acoustic test. **Reverse if**: NaN rt60 or invariant failure →
`_objects_to_wall_alpha_overrides` override fraction clamp 추가 (frac ≤ 1.0).
**ADR ref**: ADR 0034 §D, ADR 0030 §Status-update-v0.17 Item Q.

**New ADRs this cycle**: ADR 0034 (Object schema), ADR 0035 (Mesh export policy).
ADR 0030 §Status-update-v0.17 추가 (Items Q/R/S).

## v0.18.0 D-decision allocation (2026-05-22)

**D48** — Round-trip은 신규 모듈(`load_layout.py`) 없이 기존 reader+writer+신규
evolve helper로 달성 (스켈레톤 `load_layout.py` 오류 정정). `read_placement_yaml`
(parse) + `write_layout_yaml` (serialize) 가 이미 존재 → round-trip = reader 보강
(aim 복원) + `roomestim/edit.py` 의 `evolve_placement`/`nudge_speaker` 조합.
**Scope**: core (`roomestim/io/` + `roomestim/edit.py`). **Reverse if**: 편집 로직이
reader/writer/edit 3곳에 분산되어 응집도 저하 시 `roomestim/layout/` package 통합
리팩터 (v0.19+). **ADR ref**: ADR 0036 §A.

**D49** — nudge 입력 단위: spherical Δ (az/el/dist 도·미터) XOR Cartesian Δ (미터);
동시 지정 거부 (ValueError); 내부 정규화는 `coords.py` 단일 권위. web step 1°/0.05m.
**Scope**: core (`roomestim/edit.py::nudge_speaker`). **Reverse if**: 단일 Apply 에서
두 frame 합성 nudge 요청 ≥ 2건 → 명시적 순서 계약 (Cartesian-first) 후 허용.
**ADR ref**: ADR 0036 §B.

**D50** — round-trip 충실도 Level 1 (position+aim 구조 동치) 정식 계약 ({VBAP, WFS}
한정); aim 은 v0.18 에서 reader 복원으로 비손실화 (export 버그 동시 수리).
`target_algorithm` 은 {VBAP, WFS} 에서만 보존; DBAP/AMBISONICS 는 read 시 "VBAP"
붕괴 (OQ-38). notes/id 제외 (notes = OQ-37; id = channel 재생성). 부분 aim 키 →
treat-as-missing. 수치 노트: position `dist_m` 은 비축-정렬 azimuth 에서 cartesian↔
spherical cycle 당 ~1 ULP drift → byte-equal idempotency 게이트는 축-정렬 fixture
(단일 write→read→write 고정점) 로 lock. **Scope**: core (reader 보강 + 회귀 lock).
**Reverse if**: aim 복원이 기존 origin-aim 케이스와 충돌 → 복원 우선순위 명시
(explicit > origin-default) 후 회귀 케이스 추가. **ADR ref**: ADR 0036 §C.

**D51** — byte-equal round-trip (comment/key-order/float-format 완전 보존)은 v0.18
비-목표; core 는 `yaml.safe_dump` 단일 직렬화 권위 유지. **Scope**: 정책 (no code).
**Reverse if**: layout.yaml hand-written comment 보존 요청 ≥ 2건 또는 git-diff 노이즈
보고 → v0.19+ ruamel 도입 ADR. **ADR ref**: ADR 0036 §F.

**D52** — `__schema_version__` 불변 ("0.2-draft"); layout.yaml 편집은 RoomModel
schema 와 직교. v0.18 은 RoomModel 필드를 추가/변경하지 않음. **Scope**: 버전 정책.
**Reverse if**: nudge 가 RoomModel 에 placement-cache 필드 추가 요구 → schema bump
재검토. **ADR ref**: ADR 0036 §E.

**New ADR this cycle**: ADR 0036 (Layout round-trip + speaker nudge policy).
ADR 0030 §Status-update-v0.18 추가 (Items T/U/V). 신규 OQ 3건: OQ-36 (room.yaml
다운그레이드 flag — forward-ref 정식 allocate), OQ-37 (notes round-trip v0.19+),
OQ-38 (target_algorithm 전체 round-trip / DBAP·AMBISONICS 라벨 v0.19+).

---

## v0.18.1 D-decision allocation (2026-05-22)

**D53** — `nudge_speaker` spherical 분기 el ∉ [-90, 90] → `ValueError` (reject).
clamp/warn-clamp/silent-accept 세 대안 거부. 근거: (1) 기존 `dist <= 0` reject 와
대칭 (같은 함수, 같은 frame, 동급 비물리 입력); (2) 사용자 의도 보존 (경계 초과는
truncate 대상 아닌 개념적 오류); (3) 멱등성 유지 (clamp 는 반복 apply 시 90°
saturate); (4) web `gr.Number(minimum=-90, maximum=90)` 입력 제약과 정합 ("UI 막음
+ core 강제" vs "UI 막음 + core 조용히 수정" 의미 충돌 회피). Cartesian 분기
unguarded 유지: atan2 산출 el 은 정의상 [-90, 90] 안에 들어 dead guard 회피.
**Scope**: `roomestim/edit.py::nudge_speaker` + `roomestim/cli.py` `--del-deg`
help note. **Reverse if**: "el 경계 넘어도 clamp 적용" ≥ 2 요청 →
`nudge_speaker(..., clamp_el: bool = False)` opt-in + ADR 0036 §Status-update.
**ADR ref**: ADR 0036 §B/§C (보강) + §Status-update-v0.18.1.

**New ADR this cycle**: none. ADR 0036 §Status-update-v0.18.1 (el-bound
enforcement) + ADR 0030 §Status-update-v0.18.1 (Item W) append. 신규 OQ: none
(Fix 7b 는 v0.18 에서 OQ 미신설; v0.18.1 closure 이므로 신규 deferral 불필요).

---

## v0.18.2 D-decision allocation (2026-05-24)

**D54** — OQ-33 ("adapter object 자동 인식")의 **manual-annotation 부분은
v0.17 에서 이미 충족됨** (core `evolve_room_add_object` / `evolve_room_remove_object`
+ web `roomestim_web/object_add.py` Object Add Mode + predictor `_objects_to_surfaces`
fold). 따라서 OQ-33 의 미해결 잔여를 **"non-RoomPlan adapter (Mesh/ACE) 의 무인
자동 객체 추출"** 로 **범위 축소**하고, 그 잔여(후보 1 Polycam Pro API / 후보 2
bbox clustering)는 **doc-only 로 v0.20 까지 재연기(re-defer)** 한다. 두 D26
trigger (RoomPlan 외 phone-scan 출처 자동 추출 요청 ≥ 1건; mesh-only object-GT
fixture 도입)는 **모두 미충족**이며, 두 자동-추출 후보 모두 0 user report 상태에서
가장 높은 리스크(미안정 클러스터링 / 비공개 API + non-CI)를 동반하므로 D26 의
YAGNI 규율에 정합한다. v0.20 은 **hard wall** 이다 (재-재연기 금지 — 그때까지도
trigger 미충족이면 WONTFIX 로 정식 종결).

**Rejected alternatives:**
- **후보 1 (Polycam Pro API)** — 비공개 API 의존, Linux-CI 빌드 불가, fixture 없음.
  0 user report 에 외부 의존을 들이는 것은 premature.
- **후보 2 (bbox clustering)** — greenfield + self-described "미안정"; validation
  ground-truth fixture 부재로 검증 불가한 heuristic 을 ship 하게 됨. D26 의
  "보고 없는 추측 구현 금지" 위반.
- **후보 3 을 "신규 작업"으로 취급** — 이미 ship 됨. 재구현은 중복.
- **무기한 재연기 (wall 없음)** — D26 직접 위반.

**Reverse-criterion (재연기 해제 조건):** 다음 중 하나라도 충족되면 v0.20 에서
ADR 0037 (auto-recognition policy) 를 신규 작성하고 후보 1/2 중 검증 가능한 쪽을
구현한다 —
(a) RoomPlan 외 출처(raw mesh/Polycam/ACE)에서 무인 객체 추출 요청 ≥ 1건, OR
(b) object ground-truth 라벨이 붙은 mesh-only fixture 가 repo 에 도입(후보 2 의
    회귀 검증 기반 확보), OR
(c) Polycam 이 안정적 Linux-buildable segmentation export 를 공개(후보 1 의 CI
    제약 해소).
**Scope**: policy (no acoustic/schema code). **ADR ref**: ADR 0034
§Status-update-v0.18.2 + ADR 0030 §Status-update-v0.18.2 Item X.

**D55 (OPTIONAL — deferred, user-gated)** — manual-annotation 의 CLI 패리티
격차를 닫기 위해 `roomestim add-object` 서브커맨드를 신설한다는 제안. 본체는
신규 로직 없이 이미 shipped 인 `evolve_room_add_object` + `room_yaml` reader/writer
를 호출만 한다. **이 항목은 OQ-33 해소에 필수가 아니다** (web 으로 이미 가능).
v0.18.2 사용자 확인 결과: **OUT / deferred** — 사용자가 명시 요청하지 않음.
**Reverse if**: 사용자가 CLI 객체 추가 패리티를 명시 요청할 때. 채택 시 web/CLI
객체 추가 시맨틱 분기 → 단일 helper 로 재수렴 주의.
**ADR ref**: 없음 (이 항목은 shipped core 사용이므로 신규 ADR 불필요).

**New ADR this cycle**: none (re-defer는 §Status-update append 만으로 충분 — 신규
ADR 은 v0.20 에서 auto-detection 이 실제 구현될 때 ADR 0037 로 신설).
ADR 0034 §Status-update-v0.18.2 + ADR 0030 §Status-update-v0.18.2 Item X append.
신규 OQ: OQ-39 (ADR 0030 §Status-update split — deferred).

---

**D56** — `write_layout_yaml`'s dict builder normalizes every emitted numeric
degree/distance field by `round(x, 9)` applied as the LAST step on every write
(approach A — normalize at the source). Fields normalized: `az_deg`, `el_deg`,
`dist_m`, `x_aim_az_deg`, `x_aim_el_deg` (per-speaker, `_placed_speaker_to_dict`)
and `x_wfs_f_alias_hz` (top-level, `placement_to_dict`). Implemented via a
`_round9(x: float) -> float` helper in `roomestim/export/layout_yaml.py`.

Because place-write and edit-write traverse the SAME `placement_to_dict` path,
identical structural input → byte-identical output → write→read→write is an
idempotent fixed point → a zero-magnitude `edit` (`--daz 0`) emits an **empty**
diff. Precision N=9: position error ≤ 1.7e-11 m at dist ≤ 2 m — ≪ D50 Level-1
≤1e-9 structural contract. `round(-0.0, 9) == -0.0` preserved.

Rejected alternatives: (2) place-only fix doesn't cover reader-restored aim on
edit-write; (3) numpy/Decimal = needless dep/weight; (4) regex post-process =
fragile; (5) yaml representer = global in-process side-effect, not auditable.

**Trigger**: dogfood-reproduced defect — no-op `edit --speaker 0 --daz 0` on n8
VBAP ring produced non-empty diff touching unrelated speaker. Confirmed at HEAD
`aae5514` (v0.18.2).

**Reverse-criterion**: if a real consumer needs > 9-decimal-degree precision in
`layout.yaml` (≥ 1 report), raise N or make it a parameter and record in ADR 0036
§Status-update. Default stays N=9.

**ADR ref**: ADR 0036 §Status-update-v0.18.3 + ADR 0030 §Status-update-v0.18.3
Item Y. New ADR: none. New OQ: none.

---

## v0.18.4 D-decision allocation (2026-05-25)

**D57** — OQ-36 (`room.yaml --schema 0.1` 다운그레이드 export flag) 의 D26
**hard-wall forced decision**: **영구 deferral / WONTFIX**. 근거:
(1) 유일한 실제 consumer 인 `spatial_engine` 은 `layout.yaml` **만** 소비하고
`room.yaml` 은 읽지 않는다 (`docs/adr/0034-object-schema.md:142` 명시). 따라서
"0.2-draft `objects` unknown field 로 외부 consumer fail" 이라는 trigger 의
전제가 성립하는 consumer 가 **존재하지 않는다**. (2) trigger ("외부 consumer
fail 보고 ≥ 1건") = **0건** (git log / docs / artifacts 전수 grep, 0 hits).
(3) **다운그레이드 기능 자체는 이미 라이브러리 레벨에 존재**한다 —
`room_model_to_dict(room, schema_version="0.1"|"0.1-draft")` + `write_room_yaml(
schema_version=...)` 가 legacy schema (objects 생략) 를 이미 write 한다
(`roomestim/export/room_yaml.py:105/167`). 미존재 항목은 **CLI 노출 (`--schema`
플래그)** 뿐이며, 프로그래매틱 caller 가 다운그레이드가 필요하면 오늘도 가능하다.
따라서 CLI 플래그를 추가하는 것은 0-consumer 기능에 대한 surface-area 증가 =
YAGNI. **이것은 무기한 deferral 이 아니라 D26 hard-wall 에서의 정식 close
(WONTFIX) 이다** — cadence 가 다시 미정으로 돌아가지 않는다.

**Rejected alternatives:**
- **옵션 1 (CLI `--schema 0.1` 플래그)** — 0 consumer / 0 fail report 에
  사용자-노출 표면을 추가. 라이브러리 write-path 가 이미 존재하므로 긴급
  프로그래매틱 needs 는 충족 가능. premature.
- **옵션 2 (`x_objects` extension key in 0.1)** — locked 0.1 schema 를 존재하지
  않는 consumer 를 위해 오염. ADR 0004 schema lock-in 위반 방향.
- **무기한 재연기 (cadence 만 갱신)** — D26 hard-wall 직접 위반 (이번 사이클이
  바로 그 wall).

**Reverse-criterion (WONTFIX 해제 조건):** 다음 중 하나라도 충족되면 v0.20+ 에서
`roomestim export --schema 0.1` CLI 플래그를 신설하고 (라이브러리 write-path 를
CLI 로 노출만; 신규 ADR 불필요, ADR 0034 §Status-update 로 기록) 회귀 테스트를
추가한다 — (a) `room.yaml` 을 직접 소비하는 외부 consumer 가 0.2-draft `objects`
unknown field 로 fail 보고 ≥ 1건, OR (b) spatial_engine (또는 신규 consumer) 이
`room.yaml` 소비를 도입하면서 0.1-draft 만 지원. 이 두 경우 전까지 OQ-36 은
**CLOSED (WONTFIX)** 이다.
**Scope**: policy (no code; library write-path 불변). **ADR ref**: ADR 0034
§Status-update-v0.18.4 + ADR 0030 §Status-update-v0.18.4 Item Z.

---

**D58** — OQ-34 (곡선/원형 column 지원) 재연기. 두 trigger 모두 미충족 (사용자
cylinder/arch 요청 0건; acoustic 모델은 여전히 rectilinear shoebox ISM). 곡선
근사는 ISM order 50 에서 surface 수 n배 → 계산비용 n배 (실측 needs 없는
성능회귀). **신규 cadence: v0.21 cycle 시작 시 재검토** (v0.20 은 OQ-33 잔여
auto-detection 의 hard wall 에 예약되어 있어 object-schema 변경과 충돌 회피;
OQ-34 는 그 한 사이클 뒤). **Reverse if (조기 escalate):** 사용자 cylinder/arch
column 요청 ≥ 1건 OR acoustic 모델이 non-rectilinear surface 버전으로 교체 →
그 시점에 ADR 0034 §Status-update + `shape: Literal["box","cylinder"]` 필드
(resolution candidate 1) 검토. **Scope**: policy (no code). **ADR ref**: ADR
0034 §Status-update-v0.18.4.

---

**D59** — OQ-35 (USDZ/gLTF acoustic metadata 표준) 재연기. 두 trigger 모두
미충족 (Apple/Khronos acoustic-metadata 표준 **미공개**; Unreal/SPARTA 등 외부
도구 import 요청 0건). sidecar 는 `"v0.1-internal"` 로 동작 중이며 외부 표준이
없는 상태에서 roomestim 자체 spec 을 동결하는 것은 premature (표준 등장 시
재작업 비용). **신규 cadence: v0.21 cycle 시작 시 재검토** (외부 표준 의존이므로
OQ-34 와 동일 사이클로 묶어 재검토 효율화). **Reverse if (조기 escalate):**
Vision Pro/Apple RoomPlan acoustic metadata 표준 공개 OR 외부 도구 acoustic
import 요청 ≥ 1건 → ADR 0035 §E 확장 (§G reverse-criterion (iv) = OQ-35
closure 경로). **Scope**: policy (no code). **ADR ref**: ADR 0035
§Status-update-v0.18.4 (신규 §Status-update 블록 — ADR 0035 최초 status-update).

---

**D60** — OQ-37 (`notes` round-trip via engine `x_notes` extension) 재연기.
trigger 미충족 (per-speaker 메모 보존 요청 0건; nudge notes-loss 보고 0건).
`notes` 는 현재 in-memory annotation 전용 (`model.py:247` `notes: str = ""`;
reader 가 복원 안 함; ADR 0036 §C 가 Level-1 계약에서 명시 제외). engine
`geometry_schema.json` 이 per-speaker `additionalProperties: true` 이므로
`x_notes` 추가는 기술적으로 가능하나 engine 측 소비/무시 정책 협의 필요.
**신규 cadence: v0.20 cycle 시작 시 재검토** (notes 와 algorithm round-trip 은
둘 다 `layout.yaml` round-trip extension 이므로 OQ-38 과 같은 사이클로 묶음 —
한 번의 engine-schema 협의로 둘 다 평가). **Reverse if (조기 escalate):**
per-speaker note 보존 요청 ≥ 1건 OR nudge 워크플로 notes 손실 보고 ≥ 1건 →
`x_notes` per-speaker extension key (resolution candidate 1) + engine 협의.
**Scope**: policy (no code). **ADR ref**: ADR 0036 §Status-update-v0.18.4
(§C/§G(iv) 보강).

---

**D61** — OQ-38 (`target_algorithm` 전체 round-trip via `x_target_algorithm`)
재연기. trigger 미충족 (DBAP/AMBISONICS nudge round-trip 라벨-손실 보고 0건;
engine algorithm-aware 검증 미도입). 현재 `roomestim/io/placement_yaml_reader.py:67-76` 은
`regularity_hint` + `x_wfs_f_alias_hz` 존재로 WFS-vs-VBAP 만 추론 → DBAP/AMBISONICS
layout 은 read 시 "VBAP" 로 붕괴 (D50 Level-1 계약에서 명시 제외). 편집은 좌표만
다루고 알고리즘은 `place` 재실행으로 결정한다는 D50 설계가 의도적. **신규 cadence:
v0.20 cycle 시작 시 재검토** (OQ-37 과 동일 — 둘 다 layout extension key,
한 번의 engine 협의로 묶음 평가). **Reverse if (조기 escalate):** DBAP/AMBISONICS
layout nudge round-trip 후 알고리즘 라벨 손실 보고 ≥ 1건 OR engine 이
algorithm-aware 검증 도입 → top-level `x_target_algorithm` extension key
(writer emit + reader 복원, WFS 추론보다 우선; resolution candidate 1).
**Scope**: policy (no code). **ADR ref**: ADR 0036 §Status-update-v0.18.4
(§C 보강).

---

**New ADR this cycle**: none (re-examination = §Status-update appends).
ADR 0030/0034/0035/0036 §Status-update-v0.18.4 append. 신규 OQ: none.

---

**D62** — The four `tests/web/*.py` files that used the **deprecated**
`PolycamAdapter` alias purely as a *generic mesh parser* migrate to the canonical
`roomestim.adapters.MeshAdapter` (D33's intended end-state). Changed call sites
(verified at HEAD `35e691d`): `tests/web/test_setup_pdf.py` (import :12, parse
:19), `tests/web/test_acoustic_report.py` (import :9, parse :15),
`tests/web/test_binaural_renderer.py` (import :24, parse :79),
`tests/web/test_3d_viewer.py` (import :11, construct :19 + parse :20). Each parse
target is `tests/fixtures/lab_room.obj` (a `.obj` mesh, NOT a `.json`), so the
swap is **behavior-preserving** — `PolycamAdapter(MeshAdapter)` is a subclass that
only adds a `DeprecationWarning` + `.json`-delegation branch, neither of which
applies to a `.obj` mesh parse. Effect: the four files emit ZERO `PolycamAdapter`
DeprecationWarnings; the alias's intentional warning now fires ONLY from the
contract test (the desired single canonical trigger).

**Explicitly OUT OF SCOPE**: (a) the alias is NOT removed — `roomestim/adapters/__init__.py`
keeps the `PolycamAdapter` export and the shim `roomestim/adapters/polycam.py` stays
as-is; full removal remains deferred under the **D33 reverse-criterion** (BREAKING →
needs successor D + "Breaking changes" callout). (b) the contract test
`tests/test_adapter_polycam.py` is NOT touched. (c) `roomestim/cli.py:303-306`
`_get_adapter("polycam")` is NOT touched — `MeshAdapter.parse` REJECTS `.json`
(raises `ValueError`; `.json` ∉ `_SUPPORTED_SUFFIXES`), so swapping cli.py would
REGRESS `roomestim … --backend polycam <file>.json`. (d) the shim docstring's
"removal at v0.14 or later" is noted as stale but not edited (removal deferred by D33).

**Reverse-criterion (D62)**: if a future cycle wants to remove the `PolycamAdapter`
alias entirely, it must (i) migrate remaining alias callers — `cli.py`
`_get_adapter("polycam")` (requires preserving `.json` delegation) and the contract
test — then (ii) land the removal under a successor D-decision with a "Breaking
changes" RELEASE_NOTES callout (D33). D62 does NOT authorize removal.

**Scope**: tests only (`tests/web/*.py`). **ADR ref**: ADR 0027
§Status-update-v0.18.5. **New ADR this cycle**: none. **New OQ**: OQ-40 (gradio
`col_count` deprecation noise — separate, deferred). PATCH bump `0.18.4 → 0.18.5`.


## D63 — `Object.wall_index` canonicalized on the walls-only frame (v0.19.0, 2026-05-28)

`wall_index` is zero-based into the WALLS-ONLY surface list
(`[s for s in surfaces if s.kind == "wall"]`), NOT the full `surfaces` array
(`[floor, *ceilings, *walls]`). The predictor
(`_objects_to_wall_alpha_overrides`, `predictor.py:461`) already used this frame;
the viewer (`roomestim_web/viewer.py:_wall_attached_traces`) was the single
divergent consumer (`room.surfaces[obj.wall_index]`) and was fixed to mirror the
predictor. For any nonzero `wall_index` the two had resolved to different
surfaces (e.g. `wall_index=0` = first wall for the predictor, the FLOOR for the
viewer), so wall-attached door/window quads rendered against the wrong surface.

**Drivers**: field name implies wall; predictor-already-walls-only → ZERO
acoustic edits, no RT60 re-baseline; single-consumer fix. **Rejected**:
full-surfaces frame (would force a predictor change + RT60 re-baseline + naming
re-litigation). Schema `wall_index` property gained a `description` documenting
the frame. Locked by `tests/test_wall_index_frame.py` (predictor) +
`tests/web/test_wall_index_viewer.py` (viewer), door at `wall_index=2`. Out-of-range
still returns `[]`. **Cross-refs**: ADR 0037; ADR 0034; D64.


## D64 — `MeshAdapter` `schema_version` unified to `0.2-draft` (v0.19.0, 2026-05-28)

`adapters/mesh.py` emitted `schema_version="0.1-draft"` while `RoomPlanAdapter`
(`roomplan.py:308`) and the `RoomModel` default emit `"0.2-draft"`. The mesh
adapter's value was a stale label: mesh output is never jsonschema-validated
(no jsonschema import in `mesh.py`; the 0.1 schema is referenced only by the
reader/exporter), so the change is a pure label fix with no validation
consequence. Bumped to `"0.2-draft"`; one test updated
(`tests/test_adapter_mesh.py`). The 0.1-draft backward-parse path
(reader/exporter) is UNTOUCHED. This output-contract change of a public adapter
is the specific SemVer driver for the v0.19.0 MINOR bump. **Cross-refs**:
ADR 0027; ADR 0035; D33; D63.


## D65 — engine-schema resolution raises a descriptive error (OQ-42 close, v0.20.0, 2026-05-28)

`export/layout_yaml.py` previously returned `_DEFAULT_ENGINE_SCHEMA_PATH`
(a hardcoded absolute path) whenever neither `SPATIAL_ENGINE_REPO_DIR` nor
`--validate-engine` resolved a file; a genuinely-missing schema then surfaced
only as a bare deep `FileNotFoundError` from `schema_file.open()` — unactionable
and non-portable off the author machine. **Decision**: option (a) — keep the
documented `CLI > ENV > default` chain and the `_DEFAULT_ENGINE_SCHEMA_PATH`
constant (ADR 0033 §B), but route all three open sites (`_load_engine_schema`,
`write_layout_yaml`, `validate_placement`) through a single guard
`_assert_schema_file_exists` that raises one descriptive `FileNotFoundError`
tagged `kErrEngineSchemaNotFound` naming `SPATIAL_ENGINE_REPO_DIR`,
`--validate-engine`, and `--no-engine-validation`.

**Drivers**: §E intent (no silent missing-schema failure) honored WITHOUT firing
§E's breaking-removal trigger (the default path is not yet permanently
unavailable); single-source guard = no third-copy drift; behavior + byte output
unchanged on any host where the schema resolves (suite green, RT60 byte-equal —
no acoustic edits). **Rejected**: (b) warn-and-skip (collides with ADR 0033 §C/§D
`--no-engine-validation` audit opt-out — re-introduces dishonesty §C prevents);
(c) vendor a pinned schema copy (ADR 0027/0033 keep the engine schema un-vendored
to avoid drift; D64 reaffirms mesh output is never validated against a vendored
schema). New sentinel `kErrEngineSchemaNotFound` mirrors the `kErr*` convention
in `model.py`. CLI help text de-"hardcoded". New test
`test_engine_schema_missing_raises_descriptive`; `test_engine_toggle.py`
docstrings re-worded. **Cross-refs**: ADR 0033 §Status-update-v0.20.0; ADR 0027;
D42; OQ-42 (CLOSED).


## D66 — `MeshAdapter` PLY no-faces guard (OQ-21 close, v0.20.0, 2026-05-28)

A points-only PLY (vertices, zero triangular faces) loads via
`trimesh.load(force="mesh")` as a `Trimesh` with `len(faces)==0`; the existing
`(N, 3)` vertex-shape check does NOT catch it, so the input reached the
convex-hull-of-projection path (undefined for a point cloud). **Decision**: add a
guard right after the vertex-shape check —
`faces = np.asarray(getattr(loaded, "faces", []))` → `if len(faces) == 0: raise
ValueError("MeshAdapter: mesh has 0 faces (points-only PLY); a surface mesh with
triangular faces is required.")`. New fixture `tests/fixtures/points_only.ply` +
`tests/test_adapter_mesh.py::test_mesh_adapter_points_only_ply_raises`.
**Drivers**: closes a v0.12-web.1 known degenerate case; small, self-contained,
no vendoring; adds a defined error path for a previously-undefined input (a SemVer
driver for the MINOR bump). **Rejected**: silently coercing to a point cloud /
attempting alpha-shape reconstruction (out of scope, D6 defers alpha-shape). The
4-format parse test and the vertex-color PLY test (faces present) are unaffected.
**Cross-refs**: ADR 0027 §Status-update-v0.20.0; D6; OQ-21 (CLOSED).


## D67 — `place_ambisonics` stub export removed (v0.20.0, 2026-05-28)

`roomestim/place/ambisonics.py` was a pure `NotImplementedError` stub
("deferred to v0.3 per ADR 0003") whose ONLY consumer was the
`roomestim/place/__init__.py` re-export — it is NOT in `dispatch.py`, NOT a CLI
`--algorithm {vbap,dbap,wfs}` choice, and NOT imported by any test (the one
ambisonics test, `test_layout_round_trip.py`, exercises `TargetAlgorithm`
collapse, not this function). **Decision**: delete `ambisonics.py` and remove the
`from ...ambisonics import place_ambisonics` import + the `"place_ambisonics"`
`__all__` entry from `place/__init__.py` (module docstring de-"Ambisonics"-ed).
Leaves zero misleading public surface. **Drivers**: the stub advertised a public
API that always raised; removing it is honest and zero-risk (grep confirmed no
internal consumer beyond the re-export). **Rejected**: keeping the stub (advertises
non-functional API). A future v0.x reviving ambisonics gets a real impl + ADR.
Not a breaking change in the D33 sense (never functional, never in CLI/dispatch).
**Cross-refs**: ADR 0003 (ambisonics deferral); D33 (breaking-change discipline —
N/A here).


## D68 — shared `wall_surfaces` / `surface_index_for_wall` resolver (OQ-43 close, v0.21.0, 2026-05-28)

Two "surface index" frames coexisted in the model with no shared authority:
`evolve_room_material` / `evolve_room_materials_bulk` (`edit.py`) index the FULL
`room.surfaces` list (correct for their only shipping caller — web
`on_apply_overrides`, which feeds full-list indices from
`_dataframe_to_changes_json`), while `Object.wall_index` resolves on the
WALLS-ONLY filtered list (predictor α overrides + web 3D viewer; ADR 0037).
Adapter surface order is NOT uniform (`roomplan.py` `[floor, *ceilings, *walls]`;
`mesh.py` `[floor, ceiling, *walls]`; `ace_challenge.py` trailing floor), so a
future "edit wall N" feature wiring a walls-relative index into
`evolve_room_material` would patch the WRONG surface — the exact latent condition
that produced the v0.19.0 defect. **Decision**: add two module-level read
accessors to `roomestim/model.py` — `wall_surfaces(room) -> list[Surface]` (the
ONE walls-only authority) and `surface_index_for_wall(room, wall_ordinal) -> int`
(bridges the walls-only ordinal to its full-`room.surfaces` index; raises
`IndexError` out of range). Route the existing walls-only filters
(`predictor.py` ×4, `roomestim_web/viewer.py`) through `wall_surfaces` (identical
result, single authority). **Additive + defensive only**:
`evolve_room_material` / `_bulk` signatures + full-list-index semantics are
byte-identical; no shipping caller passes a walls-relative index there yet. New
characterization test `tests/test_surface_index_frame.py` pins
`wall_surfaces(room)[k] is room.surfaces[surface_index_for_wall(room, k)]` across
two adapter orderings (RoomPlan `[floor, ceiling, wall×4]` → ordinal 2 maps to
full index 4; inline synthetic trailing-floor order). **Drivers**: removes the
latent wrong-surface condition; the analogue of `test_wall_index_frame.py` for the
edit lane. **Rejected**: placing the resolver in `roomestim/geom/` (depends only
on polygon math, no model knowledge → would invert the layering). **Cross-refs**:
ADR 0037 §Status-update-v0.21.0; D63 (wall-index canonicalization); OQ-43 (CLOSED).


## D69 — predictor fallback rationale surfaces the offending wall_index + wall_index upper-bound at reader / web / adapter (OQ-44(a)+(b) close, v0.21.0, 2026-05-28)

(a) An out-of-range `wall_index` on a door/window makes
`_objects_to_wall_alpha_overrides` raise, which `predict_rt60_default` /
`predict_rt60_default_per_band` catch and silently downgrade the WHOLE room
ISM→Eyring — with the offending index (carried in the exception text) discarded
from the rationale. **Decision (a)**: append the caught exception to the fallback
rationale tail (`... ISM fallback to Eyring ({type(exc).__name__}: {exc})`).
**Rationale-string-only** change: `rt60_s` is computed by `eyring_rt60` on the
same inputs → byte-equal for the fallback path; the valid-input ISM numeric path
is untouched (negative control `1.9190766987173207` byte-equal). (b)
`Object.wall_index` had no upper bound at any entry point. **Decision (b)**: bound
`0 <= wall_index < len(wall_surfaces(room))` for door/window objects at the three
independent entry points — `read_room_yaml` (raise `ValueError` post object-parse;
the reader is context-free per-object so the bound lives in `read_room_yaml`),
`roomestim_web.object_add._on_add_object` (user-facing error string, room returned
unchanged, no crash), and `RoomPlanAdapter._room_model_from_sidecar` (raise — the
adapter DOES emit objects via `_extract_objects`, so the guard is LIVE, not dead).
The graceful Eyring fallback is PRESERVED — (a) only makes the downgrade
diagnosable, never fatal. **Drivers**: a bad index is now rejected at load /
surfaced as a clean web error instead of silently changing RT60; the predictor
fallback is now diagnosable. New observable error path → SemVer MINOR driver.
**Rejected**: bounding inside the `Object` dataclass (context-free, cannot
self-bound). **Cross-refs**: ADR 0037 §Status-update-v0.21.0; ADR 0031
§Status-update-v0.21.0; D68 (`wall_surfaces` authority); OQ-44 (CLOSED).


## D70 — `evolve_surface` band-promotion gated on the source already having bands (OQ-44(c) close, v0.21.0, 2026-05-28)

`evolve_surface` (`edit.py`) unconditionally set
`absorption_bands = MaterialAbsorptionBands[material]` on a material change,
promoting a single-band surface (`absorption_bands=None`, the `octave_band=False`
ingest default) to per-band — silently shifting an edited room onto the per-band
predictor branch. **Decision**: gate the per-band lookup on
`surf.absorption_bands is not None`; keep the scalar `absorption_500hz` update
UNCONDITIONAL (single-band rooms still get correct 500 Hz acoustics). Single-band
surfaces stay single-band after a material edit; per-band surfaces still carry
per-band. **Commit-coupling (load-bearing)**: this gate necessarily changes the
public contract of `test_evolve_surface_material_only`, which was split into
`test_evolve_surface_material_only_single_band_stays_none` (None stays None) +
`test_evolve_surface_material_only_per_band_promotes` (bands still refresh). If
this gate is reverted, BOTH tests must revert with it — documented in the test
docstrings + `RELEASE_NOTES_v0.21.0.md` so a future bisect does not decouple them.
**Drivers**: a material edit no longer silently changes the predictor branch of a
single-band room; observable contract change of a public `edit.py` helper → SemVer
MINOR driver. **Rejected**: dropping band promotion entirely (per-band edited
rooms would lose their refreshed bands). **Cross-refs**: ADR 0031
§Status-update-v0.21.0; OQ-44 (CLOSED).

## D71 — web public-deployment hardening bundle (OQ-45 close, v0.22.0, 2026-05-28)

Cycle B of the post-audit fix program lands the five code-level / declarative
hardening items the v0.20.0 audit collected under OQ-45 (no CRITICAL/RCE was
found; these are defense-in-depth on a publicly-deployable Gradio Space).
**Decision** — land them as one bundle:

- **(a) Input resource bounds (ADR 0038).** `MeshAdapter` gains env-overridable
  `_MAX_MESH_FILE_BYTES` (~200 MB, `ROOMESTIM_MAX_MESH_BYTES`) +
  `_MAX_MESH_VERTICES` (5M, `ROOMESTIM_MAX_MESH_VERTICES`): file-size `stat()`
  check in `parse()` before `trimesh.load`, vertex-count check in
  `_room_model_from_mesh` (ordering shape → vertex-count → faces). Both raise a
  clear `ValueError` and protect the CLI/library path too. A matching Gradio
  `max_file_size` cap is applied at the web `launch()` boundary. This is the
  SemVer-MINOR driver (new observable `parse()` error path).
- **(b) Web error-string scrub.** The three `app.py` echo sites
  (`_on_submit` ValueError branch, `_on_apply_overrides_wrapper`, `_on_export`)
  no longer put `str(exc)`/`{exc}` in the USER-VISIBLE string — full detail stays
  in `_LOG.exception`/`warning` server-side, the user gets a generic
  "서버 로그를 확인하세요" message. Closes the residual OQ-42 echo-leak vector
  (the dev `_DEFAULT_ENGINE_SCHEMA_PATH` could surface via a validation message).
- **(c) Tempdir reaper per-PID.** `_reap_stale_tempdirs` globs
  `roomestim_{pid}_*` (was `roomestim_*`) and the two creation prefixes embed the
  PID, so the reaper can never delete another process's dirs on a shared host.
- **(d) List-input guard.** `material_override.on_apply_overrides` guards a
  non-dict JSON payload (`'["glass"]'`) after `json.loads` and before `.items()`:
  user-facing error + treat as empty (was `AttributeError`).
- **(e) Dep-CVE declaration-only.** `pyproject.toml` web extra `gradio` floor
  `>=4.0` → `>=4.44` (≤ installed 6.14.0 — widens the contract forward without
  forcing a downgrade; transitive starlette/aiohttp/pillow/requests/urllib3
  floors are pulled forward by gradio's pins). README front-matter `sdk_version`
  `"4.0.0"` → `"6.14.0"` reconciled to the installed reality. requests/urllib3/
  pillow are transitive (no direct import; `fetch_web_data` uses stdlib
  `urllib.request`) → NOT over-declared. The installed canonical env is
  UNAFFECTED (RT60 byte-equal `1.9190766987173207` proves it). CI `pip-audit` +
  lockfile deferred to OQ-46.

**Drivers**: publicly-deployable Gradio app; DoS / info-leak / cross-session
deletion / latent crash surfaced by the audit; defense-in-depth at the single
adapter chokepoint reachable from every entry path. **Rejected**: force-upgrade
the canonical miniforge env (risks all gates, not reproducible — declaration-only
floor bumps instead); remove `_DEFAULT_ENGINE_SCHEMA_PATH` (ADR 0033 §B / OQ-42
deliberately keeps it as the documented default — the fix is to stop echoing it).
**Versions**: `roomestim` 0.21.0 → 0.22.0 (MINOR); `roomestim_web` 0.17-web.0 →
0.18-web.0; schema unchanged `0.2-draft`. **Cross-refs**: ADR 0038 (NEW);
ADR 0024 §Status-update-v0.22.0; ADR 0033 §Status-update-v0.22.0; OQ-45 (CLOSED);
OQ-46 (NEW).

## D72 — security-re-review completion of the OQ-45 leak-scrub + boundary-cap (v0.22.0, 2026-05-28)

An independent security re-review of the (uncommitted) v0.22.0 changeset found
that D71 did **not** fully close OQ-45 — two real gaps the first pass missed.
This is an in-place completion of the same uncommitted v0.22.0 release (NOT a new
version): versions stay `roomestim` 0.22.0 / `roomestim_web` 0.18-web.0.

- **Gap 1 (HIGH) — schema-path info-leak still open via the Speaker Nudge tab.**
  D71 scrubbed only the three `app.py` echo sites. But `validate_placement()`
  (`roomestim/export/layout_yaml.py`) RETURNS error strings that embed the dev
  `_DEFAULT_ENGINE_SCHEMA_PATH` (a `/home/...` path) when the engine schema is
  missing, and `speaker_nudge.py:_on_nudge_speaker` echoed that list verbatim to
  the web user. **Decision** — scrub at the WEB BOUNDARY (leave
  `validate_placement` itself intact; CLI use wants the detailed path, D29 lane
  separation preserved): log the full `errs` server-side and return a generic
  message. An exhaustive re-grep of `roomestim_web/` for any web-facing
  return/`gr.update` interpolating `validate_placement(...)`, `{exc}`,
  `str(exc)`, or any exception/path found and fixed, beyond Gap 1:
  `speaker_nudge.py` nudge `ValueError`/`IndexError` branch; `object_add.py`
  `_on_add_object` (`ValueError` + catch-all) and `_on_remove_object`
  (`IndexError` + catch-all); `material_override.py` `on_apply_overrides`
  `JSONDecodeError` + per-entry `ValueError`/`KeyError`. A new load-bearing web
  test (`tests/web/test_speaker_nudge_ui.py`) drives the real `validate_placement`
  with a forced-missing schema and asserts the user-facing string carries no
  `/home/`/`geometry_schema` while the generic message is present and the full
  detail is logged (fails if the scrub is reverted).
- **Gap 2 (MEDIUM) — `max_file_size` cap inert in production.** D71 set the cap
  inside `roomestim_web/app.py`'s `if __name__ == "__main__"` block, but HF
  Spaces serves the root `app.py` (`demo = build_demo(); demo.launch()`) which
  never runs that block — so the cap never bound. **Decision** — bind it on the
  Blocks object in `build_demo()` (`demo.max_file_size = _MAX_UPLOAD_BYTES`);
  gradio 6.14.0's `gr.Blocks` ctor does NOT accept `max_file_size` (verified —
  only `launch()` does), and gradio's upload route reads
  `app.get_blocks().max_file_size` at request time, so binding the attribute
  makes the cap effective regardless of launch path. The root `app.py`
  entrypoint now also passes `launch(max_file_size=...)`, and the `__main__` cap
  in `roomestim_web/app.py` is kept (harmless). The `MeshAdapter` byte-cap stays
  the load-bearing pre-parse DoS guard. New tests assert the cap is set on both
  the `build_demo()` Blocks object and the root `app.py` `demo`.
- **Gap 3 (accuracy) — ADR 0038 + RELEASE_NOTES overclaim corrected.** The
  vertex-count cap runs AFTER `trimesh.load` and bounds the O(N) hull projection,
  NOT parse memory; the byte-cap (pre-`stat()`, before load) is the parse-memory
  bound. The "rejected at the Gradio layer before bytes hit disk" claim is wrong
  for gradio 6.14.0 (it streams the upload to a temp file before handlers run) —
  reworded to gradio's own server-side size rejection at the request boundary.

**Drivers**: an "OQ-45 CLOSED" claim must be honest; the named leak (Speaker
Nudge) was a live HIGH info-leak and the boundary cap was a live MEDIUM inert
control. **Rejected**: changing `validate_placement` core behavior (CLI wants the
path); removing `_DEFAULT_ENGINE_SCHEMA_PATH` (ADR 0033 §B keeps it). **Versions**:
unchanged (`roomestim` 0.22.0 / `roomestim_web` 0.18-web.0 — same uncommitted
release). **Cross-refs**: OQ-45 (CLOSED, completion); ADR 0038 §Decision/§Drivers
(reworded); D71 (this completes it).

## D73 — ADR 0030 §Status-update split mechanism + README schema-marker reconcile (OQ-39 closure, v0.22.1, 2026-05-28)

OQ-39 (v0.18.2 deferral; v0.21-cycle re-evaluation cadence) had two trigger
conditions: (a) ADR 0030 file > ~600 lines, OR (b) documented
navigation-pain ≥ 1件. At HEAD `66d0f4b` the file is 477 lines (8% below the
line threshold) but condition (b) is now satisfied — the v0.22.0
multi-perspective security audit had to scroll past 10 §Status-update blocks
to verify ADR 0030 §A–§E predictor cascade byte-equality. **Decision** —
split via the **split-by-section** mechanism: §A–§E core decision (+
§Consequences + §Reverse-criterion + §References) stays in
`docs/adr/0030-predictor-default-switch.md`; all 10 §Status-update blocks
(in original file order: v0.15.1, v0.15.2, v0.16, v0.16.1, v0.17, v0.18,
v0.18.1, v0.18.4, v0.18.3, v0.18.2) relocate byte-equal to a NEW companion
file
`docs/adr/0030-predictor-default-switch-status-updates.md`. The forward-
pointer block in the original file routes future readers. ADR 0039 NEW
codifies the split mechanism as a reusable pattern (line > 400 AND blocks ≥ 6
AND documented navigation-pain → split-by-section).

**Also reconciled in the same patch**: README.md:399 stale
`__schema_version__ = "0.1-draft"` → `"0.2-draft"` (ground truth in
`roomestim/__init__.py:4`; stale since ADR 0034 §B / v0.17.0 schema bump). This
extends D72's web-honesty-re-review spirit (D72 fixed README sdk_version in the
same file; the schema-marker partial-reconcile was the missed sibling).

**Drivers**: ADR 0030 readability for ongoing reviews (security audit cadence
made it load-bearing); D22 audit-trail-discipline preserved (split = file
relocation, NOT retroactive content edit); D72 honesty-re-review pattern
extension (full file reconcile, not partial); OQ-39 explicit v0.21-cycle
evaluation commitment now 1 cycle overdue. **Rejected**: (a) split-by-version
(per-version files in a subdirectory) — proliferates files for marginal
locality benefit, breaks single-grep-for-block-history; (b) permanent
deferral — D26 forbidden-indefinite-deferral applies, the trigger fired;
(c) collapsing/summarising §Status-update blocks — violates D22 audit-trail-
discipline. **Versions**: `roomestim` 0.22.0 → 0.22.1 (PATCH — doc-only +
1-line README fix); `roomestim_web` 0.18-web.0 unchanged (web byte-equal);
`__schema_version__` 0.2-draft unchanged. **Cross-refs**: OQ-39 (CLOSED);
ADR 0030 §A–§E (byte-equal); ADR 0039 NEW (split mechanism meta-ADR); D22
(operational extension); D72 (honesty-re-review precedent).

## D74 — ISM default predictor adaptive max_order (Eyring lower-bound invariant, v0.22.2, 2026-05-31)

감사 발견 MAJOR-1 (`.omc/research/codebase-audit-2026-05-30.md`): α=0.05
shoebox 5×4×2.8 에서 Eyring=1.944 인데 ISM@max_order=50=1.675 → 런타임 불변식
(`image_source_rt60 ≥ eyring_rt60 - 1e-6`, ADR 0028 §Decision sub-item 2)
위반. 저흡음 방에서 ISM 에너지 적분이 late tail 을 과소계수해 발생. **결정** —
저수준 `image_source_rt60(max_order=N)` 는 deterministic 으로 **불변**
(`test_image_source.py` 가 order 고정으로 검증; circular-dependency 회피). 고수준
`predict_rt60_default` / `predict_rt60_default_per_band` 만 적응적: max_order 를
`_ISM_MAX_ORDER_LADDER = (50, 100, 200)` 로 단계 상향하며 ISM 재계산, 불변식
(ISM ≥ Eyring − 1e-6) 충족하는 첫 order 채택. per-band 는 band 별 escalate +
band 별 Eyring 하한 비교 (band 마다 독립). cap(200)에서도 미충족이면 **Eyring 으로
fallback** (single-band) / 해당 band 만 Eyring 값으로 치환 (per-band) + rationale
에 "ISM non-converged at max_order=200 → Eyring fallback" 정직 명시. rationale
의 `max_order=` 는 실제 사용 order 반영. 실측: α=0.05 에서 order 100 으로 escalate
해 ISM=2.299 ≥ Eyring=1.944 충족 (회귀 테스트 GREEN).

**Drivers**: 불변식 위반 = ADR 0028/0009 물리 정합 위반, 저흡음 방에서 RT60 과소추정.
**Rejected**: (a) 저수준 함수 default order 단순 상향 (50→200) — 고흡음 방까지
200³ lattice 비용 강제, deterministic 테스트 contract 파손; (b) 불변식을 저수준
함수 안에 enforce — materials.eyring_rt60 와 circular dependency. **성능**: 200³
lattice 는 저흡음 방에서만 트리거 (고흡음은 50 에서 수렴 → 비용 불변).
**Versions**: `roomestim` 0.22.1 → 0.22.2 (PATCH). **Cross-refs**: ADR 0028
§Decision sub-item 2 (불변식 출처); ADR 0009 (Eyring parallel predictor);
ADR 0030 §Status-update-v0.22.2 (이 변경 기록); 신규 회귀 테스트
`tests/test_predict_rt60_default.py::test_low_absorption_ism_meets_eyring_lower_bound_*`.

## D75 — 비-shoebox binaural DOA az/el 축 스왑 수정 (+ extrusion 렌더러 경로 활성화, v0.22.2, 2026-05-31)

감사 발견 MAJOR-2: `roomestim_web/binaural.py` `_to_pra` 는 경로별로 다른 pra
frame 을 생성한다 — shoebox `[x, height, depth]`, extrusion `[x, depth, height]`.
그러나 DOA 계산은 shoebox 규약(`az=atan2(rel[0],rel[2])`, `el=atan2(rel[1],…)`)을
무조건 가정 → extrusion 경로에서 height/depth 축이 뒤바뀌어 머리 위 소스가 el≈0
으로 렌더된다. **결정** — DOA 를 경로별 올바른 축으로: 양 경로 모두 `side=rel[0]`;
shoebox `up=rel[1], front=rel[2]`; extrusion `up=rel[2], front=rel[1]`;
`az=atan2(side, front)`, `el=atan2(up, sqrt(side²+front²))`.

**Cross-fix (필수 선행조건)**: extrusion 렌더러 경로가 설치 환경(pyroomacoustics
0.10.1)에서 **아예 실행 불가** 상태였다 — (1) `room.extrude(materials=[floor,ceil])`
리스트 형식이 0.10.x 에서 `TypeError` (dict `{'floor','ceiling'}` 요구); (2)
`from_corners` 가 world 좌표를 쓰는데 `_to_pra`/image-containment 는 `(min_x,min_z)`
오프셋 frame 을 가정 → 모든 소스가 polygon 밖으로 떨어져 `add_source` 가 raise.
두 잠재결함을 최소수정 (extrude→dict, from_corners→offset frame) 으로 정합화해야
"실제 렌더러 경로 통과" 테스트(공식 재구현 금지 요건)가 성립. 이는 FIX-2 의 DOA
축 스왑이 그동안 무방비였던 직접 원인이기도 하다.

**Drivers**: 비-shoebox 방 바이노럴 데모의 공간 정위 오류 (위/측면 혼동).
**Rejected**: 공식 재구현 단위테스트만 강화 (가짜신뢰 — 기존
`test_binaural_doa_axis_mapping` 가 정확히 그 함정). **Versions**: `roomestim`
0.22.1 → 0.22.2; `roomestim_web` byte 변경 (web lane). **Cross-refs**: ADR 0025
(binaural demo stack); 신규 테스트
`tests/web/test_binaural_renderer.py::test_binaural_doa_elevation_nonshoebox_real_path`
(실제 렌더러 경로 + `nearest_hrir` spy).

## D76 — CLI ValidationError/YAMLError 미포착 수정 (reader 가 ValueError 로 wrap, v0.22.2, 2026-05-31)

감사 발견 MAJOR-3: `cli.main` 의 catch tuple 은 `(ValueError, OSError,
RuntimeError, IndexError)` 인데, `room_yaml_reader` 의 `yaml.safe_load`→
`yaml.YAMLError` 와 `Draft202012Validator.validate`→`jsonschema.ValidationError`
는 둘 다 `ValueError` 비서브클래스 → 스키마위반/malformed room.yaml 입력 시 raw
traceback 이 escape. 또한 reader 독스트링의 "Raises ValueError" 가 거짓.
**결정** — reader 경계에서 wrap (CLI tuple 확장보다 깔끔; 독스트링도 참이 됨):
`read_room_yaml` 이 `yaml.YAMLError`/`ValidationError` 를 잡아
`raise ValueError(...) from exc`. layout reader(`read_placement_yaml`)도 동일
점검 — `yaml.YAMLError` + 필수키 `KeyError` 를 ValueError 로 wrap (독스트링 정합).
결과: 스키마위반 room.yaml → `place` exit 1 + `error: <msg>` (traceback 없음).

**Drivers**: CLI robustness (사용자 입력 오류에 traceback 노출 = UX 결함);
독스트링 정직성. **Rejected**: `cli.main` catch tuple 에 두 예외 직접 추가 —
동작은 같지만 독스트링 거짓 유지 + 예외 타입 누수가 CLI 계층까지 도달.
**Versions**: `roomestim` 0.22.1 → 0.22.2 (PATCH). **Cross-refs**: 신규 테스트
`tests/test_cli_input_validation.py` (schema-violation / malformed-yaml → exit 1,
no traceback; reader ValueError contract).

**D76 addendum (code-reviewer MINOR, 2026-05-31)**: empty file (`safe_load` →
`None`) 과 top-level list (`safe_load` → `list`) 는 `YAMLError`/`ValidationError`
를 발생시키지 않아 wrap 범위를 빠져나갔다 — `None.get(...)` → `AttributeError`,
`list['name']` → `TypeError` 로 traceback escape. `safe_load` 직후 양 reader 에
`if not isinstance(data, dict): raise ValueError(... "expected a YAML mapping")` 추가.
신규 회귀 테스트 4개 (empty + list × room/place): `test_place_on_empty_room_yaml_exits_one_no_traceback`,
`test_place_on_list_room_yaml_exits_one_no_traceback`,
`test_read_room_yaml_empty_file_is_value_error`,
`test_read_room_yaml_list_is_value_error`. 실증: 가드 없이 `None.get` → `AttributeError`
/ `list['name']` → `TypeError` 확인됨 (load-bearing). Default gate 296→300.

## D77 — `run` 서브커맨드 engine-validation 토글 추가 (export/edit 동등, v0.22.2, 2026-05-31)

감사 발견 MINOR-1: `export` / `edit` 는 `--validate-engine` /
`--no-engine-validation` 상호배타 그룹(D42 / ADR 0033)을 갖지만 `run` 은 없어,
composite `run` 으로 layout.yaml 을 쓸 때 엔진검증을 끌 방법이 없었다. **결정** —
`_add_run_parser` 에 동일 mutually-exclusive 그룹 추가 + `_cmd_run` 이
`write_layout_yaml(validate=not no_validation, schema_path_override=cli_engine_path)`
로 thread (D42 precedence: CLI flag > ENV > default ON — `_cmd_export` 와 동일).
**Drivers**: 서브커맨드 간 토글 일관성. **Rejected**: 없음 (순수 누락 보완).
**Versions**: `roomestim` 0.22.1 → 0.22.2 (PATCH). **Cross-refs**: ADR 0033
(engine-validation toggle); D42; 신규 테스트
`tests/test_cli_input_validation.py::test_run_accepts_no_engine_validation`
+ `test_run_validate_engine_and_no_validation_mutually_exclusive`.

## D78 — 자기교차 polygon floor 거부 (read 경계 shapely validity, v0.22.2, 2026-05-31)

감사 발견 MINOR-3: `geom/polygon.py` 의 shoelace `abs()` 는 bow-tie (자기교차)
polygon 에 nonzero garbage area 를 반환 → volume·RT60 전부 오염, 그러나 shapely
는 정확히 area 0.0 로 판정. **결정** — `read_room_yaml` 경계에서 shapely validity
체크로 self-intersecting floor 거부 (`ValueError`). 신규 헬퍼
`roomestim.geom.polygon.is_simple_polygon(coords)` (shapely `Polygon(coords).is_valid`;
shapely 는 이미 hard dependency). `shoelace_2d` / `room_volume` 는 불변 (저수준
deterministic 유지; 검증은 read 경계에서). **Drivers**: malformed floor 가 조용히
모든 하류 면적/부피/RT60 계산을 오염시키는 것 차단. **Rejected**: `room_volume`
안에서 shapely 로 교체 — 저수준 함수에 shapely import + 동작 변경, read 경계 검증이
더 명확. **Versions**: `roomestim` 0.22.1 → 0.22.2 (PATCH). **Cross-refs**:
`room_volume` Notes (bow-tie 미지원 명시, 기존); 신규 테스트
`tests/test_cli_input_validation.py::test_bowtie_floor_polygon_rejected`
+ `test_simple_floor_polygon_accepted` (negative control).

## 비수정 (의도적, v0.22.2 사이클)

감사 발견 MINOR-2 (ISM per-wall α 면적-가중 평균) = OQ-30 기지 한계. 코드 변경
아님 — 현 per-band α 는 wall row 별 area-weighted 평균이며, 이는 ADR 0030 §A–§E
predictor 설계의 알려진 단순화다. trigger 미충족 (0 user reports). OQ-30 status
불변.

## D79 — RIR auralization Phase A 구현 (rir.py + late_reverb.py + synthesize_brir; OQ-48 CLOSE, v0.23.0, 2026-05-31)

ADR 0044 Phase A 를 web-tier 한정·신규 패키지 0(scipy+numpy)으로 구현했다. core
`roomestim/` 무변경(기본 게이트 300p/5s 불변 = 회귀 0). 신규 2 모듈 + binaural 1
함수(additive):

- `roomestim_web/rir.py` — pra image-source 직접 조립 early per-band mono-RIR
  (`pra_source.images` 도달시간 + `pra_source.damping` per-band 감쇠), analytic
  Lindau `t_mix[s]=1e-3·√V`(`room_volume` 재사용), per-band energy-continuity
  splice(5 ms 윈도우, ≤3 dB 불연속), 총길이 = `max(RT60_band)` −60 dB 도달(데모
  2 s 상수 미상속).
- `roomestim_web/late_reverb.py` — per-band 지수감쇠 filtered-noise tail
  (`decay=10^(−3t/RT60_band)`), power-complementary octave 필터뱅크(Butterworth
  −3 dB 기하 크로스오버, single-pass `sosfilt` → 크로스오버 합산 ≤0.02 dB),
  seeded `np.random.default_rng(seed+band)` byte-equal 결정성. 노이즈 대역제한 후
  envelope 적용(역순은 필터 임펄스응답이 감쇠를 오염시켜 per-band RT60 깨짐).
- `roomestim_web/binaural.synthesize_brir` — 2-채널 convolvable BRIR. early(pre-`t_mix`)
  per-image DOA→`nearest_hrir`(공유 헬퍼 `_doa_az_el_deg`, 데모 콜사이트 불변),
  late(post-`t_mix`) recombine→2-HRIR decorrelation IC 목표 `sinc(2πf·d/c)`.
  pra per-band damping 확보 위해 신규 경로는 surface 를 6-band 재질로 승격(additive,
  데모 빌더 불변).

**OQ-48 CLOSED**: §E spike 가 `compute_rir`(broadband 1-D 단일 RIR, band-separability
불가) + `measure_rt60`(~6× 오차) 둘 다 RED 로 확인 → image-source 직접 조립 채택,
`compute_rir`/`measure_rt60` 미사용. RT60 단일 진실원천 = `predict_rt60_default_per_band`
(predictor.py:559), 6 밴드 유지(500 Hz 스칼라 축소 배제).

**8-band 모호성 플래그(deviation D1)**: pra 는 fs=48000 에서 octave 그리드를
8밴드(125…4k + 8k/16k)로 확장 → `damping` shape (8, N). `rir.py` 는 `damping[0:6]`
슬라이스 + band-grid guard(선행 6밴드가 `OCTAVE_BANDS_HZ` 와 불일치 시 `ValueError`,
fail-loud). 데모의 `_resolve_damping_scalar`(binaural.py:80-94) 축소는 신규 경로에서
미사용·불변.

**Drivers**: room geometry+재질만으로 측정/학습 0 의 convolvable BRIR 합성(auralization).
**Rejected**: `compute_rir` 단독(broadband-only, per-band handoff 불가); FDN-first late
(신규 L + coloration 리스크, Phase B 로 deferred). **Honesty(ADR 0020)**: diffuse-tail
바이노럴화는 *plausible* 로만 기술(지각충실 미검증 = OQ-47). **Versions**: `roomestim`
0.22.2 → 0.23.0 (MINOR, additive feature surface). **Cross-refs**: ADR 0044
§Status-update-v0.23.0; OQ-47/49/51 status-update; 계획 `.omc/plans/rir-auralization-phase-a.md`;
16 acceptance 테스트 `tests/web/test_rir_auralization.py` (A1–A12 + real-HRTF splice
continuity + silent-band tail 보존, web-marked; web 게이트 82→84p).

### Deviation D2 (compute_rir 확정 기각) / D3 (RNG API)

ADR §E 는 compute_rir 을 조건부-허용으로 두었으나 spike 가 두 조건 모두 RED →
계획이 조건 제거하고 image-source 직접 조립으로 확정(D2). 신규 late 경로는
process-global `np.random.seed`(데모, order-fragile) 대신 `np.random.default_rng(seed+band)`
사용(D3, byte-equal 견고성); 데모 경로의 `np.random.seed(seed)` 는 불변.

### A11 invariant 정정 (구현 발견)

계획 A11 은 "broadband decay = max(RT60_band) ±10%" 였으나, 측정 대상인 −15..−45 dB
EDC 적합 구간에서는 비균일 RT60 룸(painted shoebox 는 밴드별 ~1.1–1.9 s)에 대해
성립하지 않는다: recombined broadband EDC 는 에너지-가중 혼합이라 이 구간 기울기를
광대역 high band 가 지배한다. deep-tail asymptote 자체는 max(RT60)에 점근하지만 ±10%
적합 구간에서 그 점근값을 회복할 수 없으므로, 원래 불변식은 이 적합-구간 한정으로
불가성립이다. 따라서 A11 을 **per-band tail 감쇠 = 해당 밴드 RT60 ±10%**(6 밴드 각각,
§C handoff 의 정확한 계약)로 정정 — 더 강하고 load-bearing(밴드 인덱스 오류·scalar
축소·slope 오류가 즉시 탈락). BRIR spliced tail 은 energy-continuity 재가중(A12)으로
밴드 균형이 의도적으로 변하므로 broadband RT60 미주장; 대신 A11b 가 tail 이 실제
감쇠함을 확인.

## D80 — 바이노럴 렌더러 HRTF 좌/우 채널 스왑 수정 (coords.pipeline_to_ambix 단일권위 경유, v0.23.1, 2026-06-01)

확정결함(고신뢰, 증거기반). 바이노럴 렌더러는 *pipeline* 관례 azimuth(RIGHT=+az,
`az = atan2(side, front)`, `side = rel[0] = world x`)를 산출하지만 `nearest_hrir`
는 *SOFA/AmbiX* 관례 azimuth(LEFT=+az)로 HRIR 을 선택한다. 로드된 KEMAR 데이터에서
실증: SOFA az=90° → LEFT 귀 39.5× 우세, az=270° → RIGHT 우세. 따라서 listener
오른쪽(+x) 소스가 pipeline +90° 그대로 lookup 되어 LEFT-우세 HRIR 을 골랐다 —
모든 측방 정위 성분이 L↔R 거울반전.

레포 자신의 단일권위 `roomestim/coords.py:pipeline_to_ambix(az)= −az`(라인 28-30)
가 바로 이 변환(pipeline→SOFA 는 az 부호반전)을 문서화하지만 `roomestim_web/binaural.py`
가 적용하지 않은 것이 원인. **수정**: DOA azimuth 를 `nearest_hrir` 에 넘기기 직전
`coords.pipeline_to_ambix` 경유 → SOFA lookup 이 SOFA 관례 az 를 받음. coords.py 를
실제 frame-변환 단일 진실원천으로 만든다(그 모듈의 본래 목적). el 은 관례 불변(영향
없음). 두 렌더 경로 동일 적용:

- `_doa_az_el_deg`(synthesize_brir 의 early/직접부가 사용) — SOFA 관례 az 반환으로 변경.
- `render_binaural_demo` 인라인 DOA 블록(`_doa_az_el_deg` 미호출) — 동일 헬퍼 호출로
  교체(geometry 재유도 제거 → 양 경로가 헬퍼 공유 = 변환 단일소스화).

**Blast radius**: 두 경로 동일 결함. synthesize_brir 의 **diffuse late tail**(대칭
decorrelation, DOA 없음)은 무영향 — 의도적으로 미변경(D79/ADR 0044 §D). **Regression
proof**: 신규 dataset-grounded ILD 테스트 2종(`test_binaural_ild_right_source_sofa`,
`..._render_path`) — 실제 HRIR 데이터/실제 render 경로에 대해 +x 소스의 RIGHT 채널
에너지 > LEFT(−x 는 거울) 단언. pre-fix 실패 확인(render-path: +x → L=1889 vs R=46.7,
LEFT 우세 = 버그), post-fix 통과(+x → R=1.834 vs L=0.044). 기존 self-referential
`test_binaural_doa_axis_mapping`(렌더러 자체 공식 재구현 → 결함 포착 불가)은 실제
`_doa_az_el_deg` 출력(SOFA 관례, +x → az≈270°)에 대한 단언으로 강화.

**Versions**: `roomestim` 0.23.0 → 0.23.1 (PATCH, web-tier correctness fix). core
`roomestim/` 무변경(기본 게이트 300p/5s 불변 = 회귀 0). **Gates(2026-06-01)**: default
300p/5s, web 84→86p/4s(+2 ILD), ruff clean, mypy --strict roomestim 38파일 clean
(binaural.py clean), tense-lint clean. **Cross-refs**: `roomestim/coords.py`
(pipeline_to_ambix 권위); D75(동일 DOA 헬퍼 축 로직); ADR 0044 §D(diffuse tail 무관).

## D81 — image/video → room geometry 실현가능성 스파이크 + ADR 0045 PROPOSED (`[vision]` capture backend, doc-only, 2026-06-01)

설계+리서치 사이클(미구현). roomestim frontier = 설치공간 사진/영상 → `RoomModel` geometry 복원
을 위한 `[vision]` capture backend 를 **정직성-우선 tiered** 아키텍처로 제안 — 신규 방향이 아니라
**ADR 0001 이 v0.3 로 보류한 image/COLMAP 브랜치의 만기 연속**(ADR 0001 §Follow-ups line 45:
"COLMAP scale-anchor work = v0.3 scope"; `base.py` 의 `CaptureAdapter` Protocol + `ScaleAnchor`
이미 pre-wired; `pyproject.toml:47` `colmap` extra 선언됨).

**Phase-0 스파이크 (수행됨; 아티팩트 `/home/seung/mmhoa/spike-image-geometry/` —
`final_spike_summary.json`, `metric_s2d3d_results.json`)**: HorizonNet(single-pano room-layout
net, HF-미러 `resnet50_rnn__st3d`, Structured3D 학습)을 166 실측 GT 방(PanoContext 53 residential
+ Stanford2D3D 113 office/conf/hall — **둘 다 해당 체크포인트에 out-of-domain**)에 forward.
- Standard: S2D3D 5.09% Corner-Err / 62.6% 3D-IoU; PanoContext 8.46% CE / 61.5% IoU
  (vs in-domain README ~0.76% CE / ~83% IoU).
- Metric cm(카메라높이 ScaleAnchor 후): nominal cam_h → median wall 35–57 cm; **PERFECT
  ScaleAnchor → median 18 cm, 단 43–45% 방만 ≤15 cm**; ±10 cm cam_h 불확실성 → 32–38 cm.
  오차 분해 = ~34–40 cm SCALE 성분(ScaleAnchor-resolvable) + ~18 cm SHAPE 성분(축소불가 corner).
- 기준선 RoomPlan LiDAR ~8.5 cm avg; 결정 게이트 ≲10–15 cm. 엔지니어링 경로 de-risk(GPU
  ~0.25 s/img, net 출력 1:1 `RoomModel` 매핑, 스케일=카메라높이 스칼라 1개 = 기존 ScaleAnchor
  `known_distance`). 계약 caveat: HorizonNet 은 Manhattan + 단일 평면 천장 가정.

**VERDICT = FALLBACK (conditional)**: single-pano(st3d, out-of-domain)는 ≤15 cm 게이트를 신뢰성
있게 통과하지 못함. gap 은 (a) out-of-domain 체크포인트 (b) cam_h scale 민감도 (c) floor-boundary
elevation 오차 귀속 — **원리적 기각 아님**(접근 불가한 in-domain 체크포인트라면 borderline 개연).

**Decision (ADR 0045 PROPOSED, Status-update 시제 = 제안/예정)**: single-pano = **rough-estimate /
assisted-measure / pre-scan tier**(per-corner 불확실성 + Manhattan-assumption flag + scale-source
disclosure + 엔지니어 확인 후 layout/RIR 투입); multi-view(MASt3R/VGGT) = *better-than-rough* 1급
정확도 경로(spike 선행); 출력 geometry `provenance=reconstructed(image)` 태그(measured/assumed 와
구분, install-grade 측정으로 미제시); 모델 의존은 `[vision]`/`[colmap]` extra 뒤(core 의존 0 불변,
`[web]` 선례); ADR 0001 `--experimental` 게이트 상속; 재질 manual/UNKNOWN 유지(시각→흡음 install-grade
아님, 저신뢰 제안만); provenance 스키마 추가는 **설계 작업으로 플래그만, 미구현**.

**doc-only**: 코드/테스트/version bump 0. `docs/adr/0045-image-to-geometry-capture-backend.md`
(PROPOSED, draft), 신규 OQ-52~58(open-questions.md), 본 D81, ADR-index 행 추가(docs/architecture.md).
ADR 0001 의 image 브랜치 closure 진행.
**Cross-refs**: ADR 0001(capture priority — 보류 브랜치), ADR 0002(room repr), ADR 0027/0042
(mesh adapter seam), ADR 0044(image-derived geometry 하류 소비자), D26(forbidden-indefinite-deferral);
리서치 `.omc/research/image-to-geometry-feasibility-2026-06-01.md`. **Gates(doc-only)**: tense-lint
EXIT 0; source/test 무변경(`git status` = docs/adr/ + docs/architecture.md + .omc/plans/ 만).

## D82 — 비-shoebox floor 재구성: opt-in concave-hull footprint (ADR 0042 PR1, v0.24.0, 2026-06-02)

ADR 0042 가 제안한 비볼록 floor polygon 재구성을 **opt-in** `MeshAdapter` 모드로 구현했다.
`roomestim/reconstruct/floor_polygon.py` 의 죽은 `floor_polygon_from_mesh` stub(프로덕션 호출처 0)
을 실구현으로 채우고, `MeshAdapter` default 경로는 이전(v0.23.1) convex-hull 동작과 **byte-equal**
로 보존했다 — CLI·library·web 어느 경로도 명시적 opt-in 없이는 출력이 바뀌지 않는다.

**알고리즘 선택 — `shapely.concave_hull`(신규 의존 0)**: ADR 0042 §B 는 `scipy.spatial.Delaunay`
+ `shapely.ops.polygonize` 레시피를 스케치했으나, 랜딩 코드는 더 단순한 `shapely.concave_hull`
경로를 택했다 — 동일한 zero-dep 제약(`shapely>=2.0` 이미 core, `pyproject.toml:15`)이면서 수동
α/circumradius 휴리스틱 없이 단일 `ratio` knob 만 노출(표면 축소). `(N,3)`→`(x,z)` 투영 →
`concave_hull(ratio=0.4)` → `.simplify(0.05, preserve_topology=True)` → `canonicalize_ccw`.

**튜닝 상수 근거**:
- `ratio=0.4` — concave-hull tightness `(0,1]`. `1.0`=convex hull, `→0.0`=outlier 마다 달라붙는
  톱니 경계. `0.4` 는 L자형 notch 를 복원하면서 dense·약노이즈 LiDAR/photogrammetry grid 에
  강건한 경험적 중간점.
- `simplify(0.05)` — 5 cm Douglas-Peucker tolerance 로 dense scan 의 near-collinear 경계 좌표를
  깨끗한 직선으로 병합(+sub-5 cm jitter 제거)하되, 수십 cm 이상 떨어진 실제 구조 코너는 보존.

**opt-in 와이어링 결정**: `MeshAdapter(*, floor_reconstruction="convex"|"concave")` 생성자 인자 +
`ROOMESTIM_MESH_FLOOR_RECON` env override(`ROOMESTIM_MAX_MESH_*` env 스타일과 일관). precedence =
생성자 인자 > env > `"convex"`. `"convex"` 는 기존 인라인 `MultiPoint(...).convex_hull` 을
`_convex_floor_polygon` 헬퍼로 추출만 한 byte-equal 레거시 코드(회귀테스트로 핀). `"concave"`
모드의 degeneracy(`ratio` 범위 위반/NaN, <3 distinct pt, MultiPolygon, holes, non-Polygon,
self-intersecting ring)는 `floor_polygon_from_mesh` 가 `ValueError` 로 올리고, 어댑터가 이를 잡아
**convex fallback + UserWarning** 으로 강등 — concave 가 convex 가 처리할 수 있던 parse 를 hard-fail
시키지 않는다.

**정직성 — dense-cloud 가정**: concave-hull 은 투영 cloud 가 dense(점간격 ≲0.25 m; 수천 vertex)
일 때만 정확하다. **sparse low-poly 메시**(예: 코너당 vertex 1개인 6점 extruded L prism)는 경계
샘플이 너무 거칠어 notch 를 못 잡고 면적이 **~10–20% 미달**한다(`floor_polygon_from_mesh` docstring
명시). 이 caveat 이 모드를 default 가 아닌 **opt-in** 으로 둔 이유다. CLI/web user-facing default 불변.

**downstream tolerance**: core 변경이지만 하류는 무수정 — `geom/polygon.py`(shoelace/volume),
`listener_area.py`(concave-centroid `representative_point` fallback), RoomModel/placement/Sabine 가
이미 simple non-convex footprint 를 수용(ADR 0042 §Context (4)). non-shoebox RT60 은 종전대로 Eyring
라우팅(ADR 0040 트랙, 무변경). self-intersecting 만 미지원이며 신규 `is_simple_polygon` 가드가 추출
경계에서 거부.

**미구현(잔존)**: (i) RANSAC wall-plane fit = **미채택**(ADR 0042 §C — extrusion 벽 재사용); (ii)
실측-메시 corner-error ≤10 cm **비-tautological 검증**은 SoundCam mesh access 미확보로 OPEN(OQ-13e (i)).
따라서 dense-cloud ≤10 cm 주장은 실제 스캔에서 아직 실증되지 않았다. ADR 0042 header 는 PROPOSED
framing 유지(부분 미구현 → Accepted 로 미전환); §Status-update-v0.24.0 로 PR1 랜딩 기록.

**Versions**: `roomestim` 0.23.1 → 0.24.0 (MINOR, additive core feature — `floor_reconstruction`
모드는 default 불변의 신규 observable behavior → MINOR not PATCH). `roomestim_web` 0.18-web.0 불변
(core 변경, web source 무변경, D30). `__schema_version__` 0.2-draft 불변(RoomModel 필드 미추가).
**Gates(2026-06-02)**: default(marker-scoped) 312p/5s(v0.23.1 300/5 → +12 core 회귀), web 86p/4s(불변),
full `pytest -q` 399p/8s, ruff clean, mypy --strict roomestim 38파일 clean, tense-lint EXIT 0.
code-review APPROVE-WITH-NITS(반영), independent verifier PASS.
**Cross-refs**: ADR 0042(설계; §Status-update-v0.24.0), ADR 0027(convex-hull-of-projection 출처),
ADR 0040(non-shoebox RT60 짝트랙), ADR 0038(mesh 입력 상한 — concave 도 동일 cap 하류), OQ-13e(부분진척).

## D83 — VGGT multi-view 스파이크: scale PASS / ≤15 cm FALLBACK → rough-tier now + front-end 후속 스파이크 (ADR 0045 blocking gate #2, doc-only, 2026-06-02)

ADR 0045 blocking gate #2(multi-view metric-scale 실현가능성, OQ-53)를 검증하는 feasibility VERDICT
스파이크를 수행하고 그 결과 + build-direction 결정을 기록한다. **doc-only** — 코드/테스트/version bump 0,
repo 는 byte-for-byte 무변경. 스파이크는 repo 밖 throwaway 아티팩트로 수행됐다
(`/home/seung/mmhoa/spike-vggt-multiview/` — `VERDICT.md`, `vggt_spike_verdict.json`).

**스파이크 (수행됨; 사실 기술 — 과거 시제)**: VGGT-1B(`facebook/VGGT-1B`, 비상업 research 체크포인트 —
feasibility VERDICT 용; 별도의 gated VGGT-1B-Commercial 폼이 존재하나 본 verdict 에 불필요)를 feed-forward
로 돌려 dense pointmap + camera extrinsics(similarity scale)를 얻고, camera-baseline anchor 로 metric scale 을
복원한 뒤 floor-band → concave-hull footprint 를 추출해 GT 와 비교했다. 데이터 = ARKitScenes `raw` Validation
split(Apple ML research 라이선스 — research VERDICT 용도)의 **10 개 별개 물리 방, 48 view** — 실제 handheld
parallax 가 있는 posed RGB + ARKit metric trajectory + 등록된 3DOD room mesh(=floor GT)를 갖춘 **genuine
multi-view + metric GT**(semi-synthetic 아님).

**VERDICT = FALLBACK** — 두 하위질문의 결과가 갈린다:
- **scale 하위질문(gate #2 핵심 risk) = PASS**: multi-view 가 single-pano 의 단일 cam_h 스칼라가 전체 metric
  scale 을 좌우하던 single-point-of-failure 를 제거(prior 스파이크: ±10 cm cam_h → median corner 18 cm →
  32–38 cm). parallax 로부터 scale 직접 복원 — **median scale error 1.6%, 10 방 중 6 방 best-fit 대비 ≤5%**,
  순수 camera-baseline anchor 만으로. OQ-53 scale 하위질문 RESOLVED(YES).
- **≤15 cm install-grade floor-geometry gate = out-of-the-box FAIL**: median corner error **22.4 cm**(nv48)
  / 24.7 cm(nv32); **2/10 방만 ≤15 cm**, 8/10 ≤30 cm; median floor-area **43% undershoot**(RoomPlan LiDAR
  ~8.5 cm 대비 ~2.6×). 2/10 방(long-thin / low-parallax sweep)은 VGGT pose/baseline degeneracy(1 방 96.5 cm outlier).

**Root cause = scale 아니라 periphery under-coverage**: sparse handheld sweep 이 far wall/corner 를
under-reconstruct 하는 coverage 문제(+ 스파이크의 naive concave-hull front-end 기여) — 둘 다 tractable front-end
문제이며 **VGGT 의 scale·geometry 능력의 원리적 기각이 아니다**(예: scene 41142278 scale error 0.4% / pose
RMSE 4 cm 인데 4.9×6.9 m floor 중 3.1×5.8 m 만 cover).

**Decision (build-direction)**:
1. **rough-tier now** — image/video → geometry 를 **HONEST metric scale + 가시적 per-corner uncertainty 를
   동반한 rough-estimate tier** 로 둔다. single-pano 보다 엄격히 우월(scale honest, cam_h 추측 불요). ≤15 cm
   주장은 LiDAR/RoomPlan 에 유보 — ADR 0045 provenance/honesty framing(measured/reconstructed/assumed) + OQ-54 정합.
2. **VGGT 를 as-is drop-in install-grade 경로로 ship 하지 않는다**, 동시에 "VGGT 불가능" 결론도 내리지 않는다
   (실패는 coverage/front-end, 모델 능력 아님).
3. **front-end 후속 스파이크 선행(OQ-59 신규)** — install-grade ≤15 cm 주장 또는 multi-view first-class 승격 전,
   집중된 floor-extraction front-end 스파이크: raw concave hull 대신 RANSAC wall-plane corner 추출 /
   coverage-aware capture guidance / multi-view TSDF fusion / VGGT-Omega 체크포인트. 최고가치 다음 실험.

**ADR 0045 header = PROPOSED 유지**: gate #2 의 정확도 절반(≤15 cm)이 미충족이고 blocking gate #1(OQ-52
in-domain 검증)·#3(OQ-54 provenance 스키마)이 미해소 → Accepted 미전환. ADR 0045 에 §Status-update-2026-06-02
추가 + §C 스파이크-결과 노트 + OQ-53 부분 RESOLVED / OQ-59 신규(open-questions.md) 기록.

**doc-only 변경 파일**: `docs/adr/0045-image-to-geometry-capture-backend.md`(§Status-update-2026-06-02 +
§C 노트, header PROPOSED 불변), `.omc/plans/open-questions.md`(OQ-53 부분 RESOLVED, OQ-59 신규),
본 D83. source/test/version 무변경.
**Gates(doc-only, 2026-06-02)**: tense-lint EXIT 0; source/test 무변경(`pytest -q` 399p/8s 불변 — 코드 무변경).
**Cross-refs**: ADR 0045(설계; §Status-update-2026-06-02 / §C / blocking gate #2), D81(image→geometry 사이클
+ ADR 0045 PROPOSED), OQ-53(부분 RESOLVED), OQ-59(신규), OQ-52/OQ-54(미해소 blocking gate); 스파이크 아티팩트
`/home/seung/mmhoa/spike-vggt-multiview/`(`VERDICT.md`, `vggt_spike_verdict.json`).

## D84 — OQ-59 floor-extraction front-end 스파이크: VERDICT FALLBACK(hardened) → RANSAC primary lever 기각, rough-tier 고정 (ADR 0045 blocking gate #2 정확도 절반, doc-only, 2026-06-04)

OQ-53/D83 이 남긴 갭(multi-view VGGT 는 scale PASS 이나 ≤15 cm floor-geometry 는 FALLBACK)을 좁히기 위해,
D83 이 최고가치 다음 레버로 지목한 **floor-extraction front-end** 를 집중 검증하는 feasibility VERDICT 스파이크를
수행하고 그 결과 + product 결정을 기록한다. **doc-only** — 코드/테스트/version bump 0, repo 는 byte-for-byte
무변경(`f494732`). 스파이크는 repo 밖 throwaway 아티팩트로 수행됐다(`/home/seung/mmhoa/spike-vggt-multiview/` —
`OQ59_VERDICT.md`, `out/oq59_verdict.json`, `logs/eval_rerun.log`, `scripts/frontends.py`).

**스파이크 (수행됨; 사실 기술 — 과거 시제)**: OQ-53 과 **동일한** 캐시된 nv48 VGGT 포인트클라우드(ARKitScenes
raw Validation 10 방, 48 view, Umeyama-metric, z-up) 위에서 **front-end 만** 바꿔 동일 `best_fit_2d` metric 으로
재평가했다. Step-1 reproduction gate(캐시가 OQ-53 nv48 baseline 을 재현하는가) = **PASS, 10 방 전부 delta 0.00 cm**
(캐시가 byte-faithful — 스파이크 간 silent drift 없음). 4 개 front-end 를 비교했다: `baseline_concave`(현 roomestim
concave hull, control), `convex_band`(floor band 의 convex hull, fixed-param·배포가능), `ransac_walls`(**PRIMARY** —
height-band wall points → sequential 2D-line RANSAC → polar-angle 정렬 → 인접선 교점 → corner ring, fixed-param·배포가능),
`sweep_best`(**ORACLE, 배포 불가** — per-room 으로 (conf_pct, band_m, ratio) grid 를 GT 대조 선택). OQ-53 에서 10/10
OOM-크래시했던 RANSAC 은 repo 밖 `frontends.py` 에서 수정됐다: inlier SVD refit 의 `full_matrices=False`(거대한 `(K,K)` U
미생성) + line-fit 전 ≤100 k pts 로 seeded uniform subsample(seed=0, 결정성) — 10 방 전부 ~1–2 s 에 실제 polygon 산출,
OOM 없음. **아래 RANSAC 수치는 진짜 데이터이지 크래시가 아니다.**

**Evidence (10 방, nv48 cloud — median corner cm / area err% / ≤15 cm)**:

| variant | median (all 10) | median (no-degen 8) | area err % | ≤15 cm | deployable? |
|---|---|---|---|---|---|
| baseline_concave (control) | 22.41 | 22.41 | 43.4 | 2/10 | — |
| **convex_band** | **17.13** | 17.13 | 30.0 | **4/10** | best deployable |
| ransac_walls (PRIMARY) | 19.30 | 18.72 | 26.4 | 2/10 | yes 그러나 convex 보다 나쁨 |
| sweep_best (ORACLE) | 11.60 | 11.60 | 35.7 | 7/10 | no — GT-tuned, 배포 불가 |

Degeneracy 방: 41159503(scale 63% off, front-end 으로 불가복), 41125756(scale 14% off).

**VERDICT = FALLBACK (hardened)** — front-end 레버 질문은 **NO** 로 답해진다:
- **배포가능 front-end 그 어느 것도 ≤15 cm 를 통과하지 못한다.** 최고 배포가능 = `convex_band` 17.13 cm / 4-of-10 —
  현 concave baseline(22.41 cm / 2-of-10) 대비 실질·무비용 개선이나 여전히 install-grade FAIL.
- **PRIMARY 가설(RANSAC wall-plane corner) = 기각.** 단일 고정 파라미터에서 trivial convex hull 보다 **나쁘다**(median
  19.30 cm vs 17.13 cm, 2/10 vs 4/10 ≤15 cm) 그리고 **high-variance**(41069048 3.4 cm win / 41159519 105 cm blow-up).
  per-room 결과가 bimodal — 벽이 잘 재구성된 곳은 sharp corner 를 복원하나, 벽이 partial/parallel 한 곳은 near-parallel
  교점이 방 밖으로 튄다. 단일 (thresh, n_planes, height-band) 로 두 regime 을 straddle 할 수 없어 median 이 parameter-free
  convex hull 뒤로 처진다. 핵심 음성 결과다.
- **Oracle = headroom 증명, 배포 불가.** `sweep_best` 가 11.60 cm / 7-of-10 에 도달해 concave-hull family 자체에 ≤15 cm
  여지가 있음을 보이나, inference 시점에 없는 per-room GT-tuned 파라미터를 쓰므로 ship 불가(method 아닌 ceiling).
- **Root cause = corner-fitting 아니라 periphery under-coverage**(OQ-53 에서 이미 isolated). hull family 는 존재하는 점의
  경계만 다시 그릴 뿐 missing periphery 를 만들어내지 못한다. 남은 레버(coverage-aware capture / TSDF / VGGT-Omega)는 모두
  *coverage* 를 공략하며 고정 cloud 위 front-end-only 변경이 아니다 — OQ-59 scope 밖, 각각 별도 capture/compute 스파이크.

**Decision (build-direction; D83 FALLBACK 을 hardens)**:
1. **rough-tier 고정** — image/video → geometry 를 **HONEST metric scale + 가시적 per-corner uncertainty 를 동반한
   rough-estimate tier** 로 못박는다. ≤15 cm install-grade 주장은 LiDAR/RoomPlan 에 유보. multi-view 를 first-class ≤15 cm
   경로로 **승격하지 않는다**.
2. **convex_band 는 rough-tier 내 무비용 in-tier upgrade(게이트 승급 아님)** — 이 경로가 ship 된다면 floor footprint 에
   concave baseline 대신 `convex_band` 를 선호(−5 cm median, +2 방 ≤15 cm, 0 비용). 단 **median win 이지 per-room dominance
   아님** — 3/10 방(41069021 13.3→19.6, 41125756 5.9→8.4, 41159519 18.6→25.4, best-baseline 2 방 포함)에서 regress 하므로
   rough-estimate 라벨 유지.
3. **다음 레버 = coverage, corner 아님** — binding constraint 는 VGGT periphery under-reconstruction. 최고가치 잔여 실험은
   coverage-aware capture / TSDF·VGGT-Omega denser fusion 으로, 각각 별도 스파이크다. install-grade floor 주장이 재우선화되지
   않는 한 defer(north-star: frontier = roomestim 공간추론 강건성, RIR/청취충실도는 수단).

**ADR 0045 header = PROPOSED 유지**: gate #2 의 정확도 절반(≤15 cm)이 여전히 미충족이고 blocking gate #1(OQ-52 in-domain
검증)·#3(OQ-54 provenance 스키마)이 미해소 → Accepted 미전환. ADR 0045 에 §Status-update-2026-06-04 추가 + §C
스파이크-결과 노트 갱신 + OQ-59 RESOLVED(open-questions.md) 기록.

**doc-only 변경 파일**: `docs/adr/0045-image-to-geometry-capture-backend.md`(§Status-update-2026-06-04 + §C 노트 갱신,
header PROPOSED 불변), `.omc/plans/open-questions.md`(OQ-59 RESOLVED + top-level 요약), `.omc/plans/v0.24.x-non-shoebox-and-multiview.md`
(트래커 close), `.omc/plans/oq59-floor-frontend-spike.md`(RESUME POINTER 갱신), 본 D84. source/test/version 무변경.
**Gates(doc-only, 2026-06-04)**: tense-lint EXIT 0; source/test/version 무변경(코드 무변경 — 게이트 무영향).
**Cross-refs**: ADR 0045(설계; §C / §Status-update-2026-06-04 / blocking gate #2), D83(VGGT multi-view 스파이크 → FALLBACK,
OQ-59 신설), OQ-53(scale PASS / ≤15 cm OPEN), OQ-59(RESOLVED — front-end 레버 NO), OQ-52/OQ-54(미해소 blocking gate);
스파이크 아티팩트 `/home/seung/mmhoa/spike-vggt-multiview/`(`OQ59_VERDICT.md`, `out/oq59_verdict.json`,
`logs/eval_rerun.log`, `scripts/frontends.py`).

## D85 — Room-level capture provenance 스키마 (`measured | reconstructed | assumed`) 구현 (ADR 0046 NEW; OQ-54 부분해소; image-backend 빌드 P1, 2026-06-04)

image→geometry 백엔드 빌드(플랜 `.omc/plans/image-backend-single-pano-build.md`)의 **Phase 1**. ADR 0045 §F provenance 스키마를
구현하여 Reverse-criterion #4(provenance 합의 전 image 출력 노출 금지)·blocking gate #3 의 honesty 전제를 닫았다.

**구현 (수행됨; 과거 시제)**: `RoomModel` 에 room-level `provenance: Literal["measured","reconstructed","assumed"] = "assumed"`
추가(`model.py`). 정직한 least-claim 기본값 `"assumed"` — 태그 안 된 모델은 measured 를 주장하지 않는다. 실측 어댑터
roomplan(LiDAR)/mesh(스캔)/ace(GT)만 명시적으로 `"measured"` 단언; polycam 은 위임 상속. YAML 은 `0.2-draft` 에서만 방출
(`objects[]` 선례, legacy 0.1 byte-equal 유지); reader 는 키 부재 시 `"assumed"` 기본화. 스키마는 additive(optional property,
`required` 미포함, root `additionalProperties:true` 보존; 0.1 스키마 무변경).

**masquerade 경로 = 0** (독립 code-review §B CLOSED): image-derived/untagged 가 measured 로 읽히는 경로 없음 — 3층(dataclass
default / writer 부재 / reader `.get(...,"assumed")`) 모두 least-claim, measured 는 실측 어댑터 명시 단언 시에만.

**per-Surface 는 deferred**: OQ-54 원문은 Surface 도 지목하나 3개 `additionalProperties:false` sub-object 편집 요구 → 단일-출처
어댑터에 불필요(YAGNI), room-level 선행·per-Surface follow-up.

**범위 규율**: image adapter / `[vision]` extra / CLI / per-Surface 미포함(후속 phase). 순수 additive.
**Version bump deferred**: 불활성 필드(소비자 0) → 단독 user-facing 가치 없음, image backend 기능 완성(플랜 P5) 시 일괄 bump.
**오케스트레이션**: executor 구현 → 독립 code-reviewer APPROVE(§F honesty 리뷰 겸; 0 blocker, masquerade CLOSED) → reviewer
minor(keyless-0.2 read-back 테스트) 적용. 자기승인 0.
**변경 파일**: `roomestim/model.py`, `proto/room_schema.v0_2.draft.json`, `roomestim/export/room_yaml.py`,
`roomestim/io/room_yaml_reader.py`, `roomestim/adapters/{roomplan,mesh,ace_challenge}.py`(measured 단언),
`tests/test_provenance_roundtrip.py`(신규 9 테스트), `docs/adr/0046-room-provenance-schema.md`(신규), `.omc/plans/open-questions.md`(OQ-54 부분해소), 본 D85.
**Gates(2026-06-04)**: canonical `/home/seung/miniforge3/bin/python -m pytest` — default 320p/5s, web 86p/4s, ruff/mypy(roomestim)/tense EXIT0.
**Cross-refs**: ADR 0046(provenance 스키마; 본 D85 가 구현 기록), ADR 0045(§F / Reverse-criterion #4 / blocking gate #3 — 본 변경이 해제),
OQ-54(room-level RESOLVED / per-Surface OPEN), D83·D84(image→geometry rough-tier 확정 → 본 빌드 동기), 빌드 플랜 P1.

## D86 — 단일-파노 image→geometry 캡처 백엔드(rough tier, experimental) 구현·출하 v0.25.0 (ADR 0045 §Status-update-2026-06-04b; ADR 0046; image-backend 빌드 P0–P5, 2026-06-04)

D83·D84 가 image→geometry 를 rough-estimate tier 로 확정한 뒤, 사용자 결정("실제 진척 + north-star-first")으로
roomestim 의 **첫 image→geometry 캡처 백엔드**(단일 equirectangular 파노라마 → RoomModel)를 구현·출하했다.
north-star killer use-case("깨끗한 스캔 없을 때 사진→geometry→레이아웃")의 첫 in-repo 실현. install-grade 아님 — rough tier.

**빌드 (수행됨; 과거 시제) — 5 phase, 각 executor→독립 code-reviewer APPROVE, 자기승인 0:**
- **P0** ckpt 리서치: HorizonNet 코드 MIT(상업OK). 진짜 residential ckpt(ZInD)는 비상업 라이선스(RED). permissive
  residential ckpt 부재 → 기본 st3d(Structured3D, HF mirror), zind opt-in(`--accept-zind-tou`). weights 미번들.
- **P1** provenance 스키마(D85/ADR 0046) — gate #3 해제.
- **P2** `[vision]` extra + vendored HorizonNet(MIT, py3.12 fix) + torch-free `checkpoints.py`(download-on-first-use).
  경계 게이트 #4 PASS(core torch-free, 깨진 canonical torchvision 로 입증). `b4a998a`.
- **P3** `adapters/image.py::ImageAdapter` — torch-free 지오메트리 코어(metric_layout 삼각법, cam-height ScaleAnchor)
  + torch path(lazy). provenance=reconstructed, 재질 UNKNOWN(§E), mesh seam 재사용. trig 를 spike 오라클과 수치 대조
  검증(mirror/sign 버그 0). `40a69c5`.
- **P4** CLI 노출(`--backend image`, `--experimental` 하드 게이트 torch-free, `--cam-height`/`--weights`/`--accept-zind-tou`)
  + ESTIMATED 라벨(reconstructed-only). `65f244b`.
- **P5** v0.25.0 MINOR 범프 + RELEASE_NOTES + README + 본 D86 + ADR 0045 §Status-update-2026-06-04b + 독립 verifier.

**정직성(핵심)**: provenance=reconstructed, 재질 UNKNOWN(시각재질 추론 안 함), scale=가정된 cam-height(OQ-58),
정확도 rough(st3d out-of-domain ~43–45% ≤15cm), CLI ESTIMATED 고지, ≤15cm 주장은 LiDAR/RoomPlan 한정. 두 feasibility
스파이크(OQ-53/OQ-59)가 확정한 rough tier 를 정확히 그 라벨로 출하.

**end-to-end 검증(out-of-gate, 실제 HorizonNet, spike venv)**: `run --backend image --experimental --cam-height 1.6
--input roomA.png --algorithm vbap --n-speakers 6` → room.yaml(provenance reconstructed)+layout.yaml+ESTIMATED, exit0.
ingest→place→export 가 이미지-파생 지오메트리에서 동작.

**Version**: 0.24.0→0.25.0 MINOR(additive image backend + provenance; default 동작 무변경). web 무변경.
**Deferred(정직)**: web 이미지 업로드, 실제 per-corner uncertainty(OQ-57 미해결), per-Surface provenance(OQ-54 잔여),
coverage 레버(OQ-59 b/c/d), OQ-52 in-domain ckpt. ADR 0045 header PROPOSED 유지(install-grade FALLBACK·gate #1·#2 미충족).
**Gates(canonical miniforge, 2026-06-04)**: default 345p/5s, web 86p/4s, ruff/mypy(47)/tense EXIT0. 독립 verifier PASS.
**변경 파일(P5)**: `pyproject.toml`·`roomestim/__init__.py`(0.25.0), `RELEASE_NOTES_v0.25.0.md`(신규), `README.md`,
`docs/adr/0045-...md`(§Status-update-2026-06-04b + footer 정정), 본 D86, 빌드 플랜(P0–P5 done).
**Cross-refs**: ADR 0045(§B rough tier 구현·출하 / §C install-grade FALLBACK / gate #3·#4 MET·#1·#2 미충족),
ADR 0046·D85(provenance), D83·D84(rough-tier 확정), OQ-54·OQ-57·OQ-58·OQ-52(잔여/deferred), 빌드 플랜 P0–P5.

## D87 — provenance 를 layout.yaml 아티팩트 경계로 전파 (image-backend honesty 후속 T1; ADR 0046 §Status-update-2026-06-05; v0.25.1, 2026-06-05)

room.yaml 은 이미 `provenance` 를 영속화(D85)하나 **layout.yaml(placement 아티팩트)에는 rough-tier 마커가 없어** 정직성 고지가
휘발성 stderr(`_maybe_print_estimated_notice`)뿐이었다. 사용자 권고 #1("provenance 전파") 수용 → 마커를 placement 산출물에 실어
아티팩트 경계에서 정직성 유지.

**구현**: `PlacementResult.geometry_provenance: Provenance = "assumed"` 필드 추가 → CLI `_run_placement`(=_cmd_run·_cmd_place 공통)
및 `_cmd_export`(room 권위)에서 `room.provenance` 전파 → `export/layout_yaml.py:placement_to_dict` 가 상위 확장키
`x_geometry_provenance` 를 **`!= "assumed"` 일 때만** 방출(reconstructed=rough 마커·measured=positive claim; assumed 묵시 →
**기존 layout 전부 byte-equal**, 모든 기존 PlacementResult 가 assumed 기본값이므로). `io/placement_yaml_reader.py` 가 round-trip +
누락 시 least-claim "assumed" 기본화, out-of-enum 은 공유 `_parse_provenance` 로 거부. `_cmd_place` 도 ESTIMATED 고지 출력(run/ingest 일관).
geometry_schema 루트 additionalProperties:true → 검증 통과. write→read→write idempotent.

**검증**: default 351p/6s, web 86p/4s, ruff/mypy/tense EXIT0. 독립 code-review APPROVE + 독립 verifier VERIFIED-GREEN(byte-equality·
E2E reconstructed 체인 실측). `test_layout_provenance.py`(신규 6 테스트).
**Cross-refs**: ADR 0046(§Status-update-2026-06-05), D85(room-level provenance 선행), ADR 0045 §F honesty / Reverse-criterion #4, D88(동시 출하 golden), D86(image backend).

## D88 — 실모델 golden 회귀 테스트(`vision` 마커, 실 HorizonNet 경로) (image-backend honesty 후속 T2; v0.25.1, 2026-06-05)

in-gate 이미지 테스트는 전부 torch-free(합성 cor_id)였고 **실 torch 경로(`_infer_corners`→vendored HorizonNet)는 무방비**였다.
사용자 권고 #2 수용 → 실모델 1-파노 회귀 락.

**구현**: `tests/test_image_backend_golden.py`(`@pytest.mark.vision`) — vendored 합성 파노(`tests/fixtures/image/roomA_synth_pano.png`,
MIT-clean 우리 렌더)에서 실 HorizonNet 추론 후 출력 고정(width 4.7327·depth 3.9647·ceiling 3.1528, abs=0.2 cross-machine bound) +
정직성 불변식(provenance reconstructed·materials UNKNOWN·objects=[]·6 surfaces) exact assert. **서브프로세스 가용성 probe** 로
torch 의 `sys.modules` 오염 차단(경계 게이트 #4 보존; 깨진 torchvision RuntimeError 도 비-제로 exit→skip). 오프라인/무-ckpt →
OSError/ConnectionError/ImportError → pytest.skip. pyproject `vision` 마커 신규.

**검증**: canonical default 게이트에서 깨끗이 SKIP(broken torchvision), `[vision]` venv(torchvision 0.20.1 + 로컬 st3d ckpt)에서 **1 passed**
(골든 정확 일치). 독립 verifier 가 venv 에서 직접 1-passed 재현.
**Cross-refs**: D87(동시 출하 T1), ADR 0045(§image backend / gate #4 torch 경계), D86(image backend), 빌드 플랜 P3(실경로).

## D89 — near-horizon 타당성 가드 + per-room 정직성 보정 (cold eval 후속 F1·F2; ADR 0045 §Status-update-2026-06-05c; OQ-60 NEW; v0.25.2, 2026-06-05)

출하 후 **콜드 다중-시나리오 평가**(244 실파노 + 합성 sweep): 어댑터는 스파이크 파이프라인과 수치적으로 동일(divergence 0).
per-DIM median 39cm(주거)/50cm(사무)는 README 와 일치하나 **per-ROOM(양변) median 83–95cm·양변 ≤15cm 주거 8%/사무 3%** →
README per-dim 프레이밍이 ~2.5× 낙관적. 지배 오차원 = 사용자 cam_h(+10cm→+25–40cm, 선형). **최악 실패: near-horizon radius
blowup** — `r=cam_h/tan(-v_floor)` 발산으로 주거 ~2% 가 비현실적 >15m 방(24.9m·41m)을 **플래그 없이** 방출; 기존 `_MIN_FLOOR_TAN=1e-6`
가드는 AT-horizon 만 차단, NEAR-horizon 누락.

**F1(코드)**: `adapters/image.py:_corners_to_room` 에 `_MAX_PLAUSIBLE_RADIUS_M = 20.0` — 데이터 기반(legit 코너반경 p95=14.5m·p99=27.9m;
@20m reject 2.9%). 코너 반경 초과 시 **조용한 거대-방 방출 대신 명확한 ValueError(하강각 진단 + remediation)로 거부**(force-cuboid 4-코너
불변식상 skip 불가 → raise). AT-horizon `_MIN_FLOOR_TAN` skip 경로 보존. 240 실파노 end-to-end: 7 거부(반경 21–42m, 41m·24.9m 환각 포함)/
233 정상/0 false-reject. CLI ValueError→exit1 전파.

**F2(문서)**: README 정확도 블록에 per-DIM vs per-ROOM 구분 + per-room 83–95cm·양변≤15cm 8%/3% 명시, near-horizon 자동거부(>~40m 방
rough tier 미지원) 고지; "rough pre-scan, 설치측정 아님" 판정 유지(데이터는 더 가혹).

**미해결(NEW) OQ-60**: 절대 반경 bound 는 "큰 방"과 "오검출"을 혼동 → 상대 outlier 검정(코너반경 ≫ k×median(나머지))으로 대체/보강 +
threshold 파라미터화. deferred, low-pri.

**검증**: default 356p/6s, web 86p/4s, ruff/mypy/tense EXIT0. 독립 code-review APPROVE-WITH-FIXES(LOW 3건 반영: 코멘트 수치 2.9%,
all-far 거부 테스트, at-horizon skip 보존 테스트). `test_adapter_image.py` +5 테스트. **Version** 0.25.1→0.25.2 PATCH(behavior change:
비현실 재구성 거부 + 정직성 문서 보정; 정확도 개선 아님).
**Cross-refs**: ADR 0045(§Status-update-2026-06-05c / §C install-grade FALLBACK), D86·D87·D88(image backend·honesty), OQ-57(per-corner
uncertainty)·OQ-58(scale source)·OQ-60(relative bound), cold eval(scientist, 244 panos).

## D90 — OQ-60 RESOLVED: near-horizon 가드 상대 outlier 테스트 기각, 절대 상한 20 m 유지 (코드 변경 0; ADR 0045 §Status-update-2026-06-06, 2026-06-06)

D89/OQ-60(절대 반경 상한을 상대 outlier 테스트로 교체?)을 240 실파노(seed=7; 주거 120 cam_h=1.4 + 사무 120 cam_h=1.6;
HorizonNet st3d, 0 추론오류)로 실측. **결론: 상대 기각, 절대 20 m 유지 — 코드/임계값 무변경이 정답.**

- **상대 테스트 구조적 무력**: 예측 코너반경 ratio(max/median) 최대 **1.84**(GT 최대 1.59), 전 분포 [1.01,1.84]. 후보
  k∈{4,6,8,10,15} 전부 0/240 거부. HorizonNet `force_cuboid` 가 네 코너를 비례 이동 → "한 코너만 ≫" 신호 미발생.
- **경쟁 가설(off-center→고 ratio)도 미발현**: 직사각형 방 대각 코너 동반 스케일로 GT ratio 상한 ~2.2.
- **절대 상한도 완벽 분리 불가하나 현 선택이 최선**: artifact #1(pred 28.1·GT 3.6 m)과 legit #2(pred 27.9·GT 47.4 m)가
  0.2 m 차로 겹침. 20 m 거부 4건 전부 정당(2=진짜 환각 GT 3.6/7.4 m, 2=>~40 m 초대형으로 rough tier 범위 밖, 재구성 불가).
- **scientist 의 "40 m 상향" 권고 기각**(내부모순: 40 m 는 28.1 m artifact #1 통과 → 3.6 m 방을 28 m 로 방출, 가드 무력화).

**검증**: read-only 실측(코드·게이트 무변경). doc-only(version bump 없음). decisions/open-questions/ADR 0045 동기화.
**변경 파일**: `docs/adr/0045-...md`(§Status-update-2026-06-06), `.omc/plans/open-questions.md`(OQ-60 RESOLVED), 본 D90.
**Cross-refs**: D89/OQ-60(본 D90 가 해소), ADR 0045(§Status-update-2026-06-05c·06-06), scientist 분석(240 panos·ratio 분포·2×2 분리표·per-k false-reject), [[project_image_backend_cold_eval]].

## D91 — MeshAdapter up-axis(gravity) 자동 정규화: measured 경로 P0 정확성 수정 (v0.25.3; ADR 0027 §Status-update-2026-06-07; commercialization Phase 0a, 2026-06-07)

상용화 분석(사용자 결정: B2B AV-인스톨러 프레이밍 + 공개 데이터셋 검증; `.omc/plans/commercialization-analysis.md`)이
measured 경로의 **실-캡처 미검증**(픽스처 전부 합성 Y-up; real-scan 게이트 영구 SKIP)을 지목. 로컬 실 **ARKitScenes**
10 scene(iPad LiDAR=RoomPlan 센서 정합)으로 MeshAdapter 첫 실행 → **천장 6.5–9.6 m**(실제 ~2.5 m) = P0 버그.

**근본원인**: `roomestim/adapters/mesh.py` 가 **Y-up 하드코딩**(`ceiling_height_m = y_max - y_min`)·gravity/up-축 정규화
전무. ARKit/RoomPlan·다수 mesh export 는 **Z-up(gravity-aligned)**. 합성 Y-up shoebox 픽스처만 있어 여태 안 보임.

**수정(F1/Phase 0a)**: ingest 시 up-축을 **planar-density 판별자**(축별 1-D 히스토그램 floor/ceiling 집중도, bin 0.04 m,
edge 0.15 m; 종횡비 무관)로 검출 후 모델 Y-up 으로 정규화 → 기존 floor/wall/ceiling 추출 불변. density 동률→floor-area
tiebreaker(clear-floor 1.50× 마진, narrow room 서 area 신뢰불가하므로 마진 미달 시 거부). density·area 둘 다 모호(완전
cube / sparse+narrow)면 `ValueError`(density·slab_area 진단 + `up_axis=` 권고)로 **fail-loud**(조용한 오답 금지 —
near-horizon 가드 D89 와 동일 철학). `up_axis` override(기본 auto). 합성 Y-up identity 정규화 → **byte-equal**.

**검증**: 실 ARKit 10 scene up-축 Z·천장 2.49–3.69 m(다중층 41159529=5.76 m 별도 bound)·`@pytest.mark.lab` 회귀 고정.
default 368p/6s, web 86p/4s 무영향, ruff/mypy(strict)/tense EXIT0. **독립 code-review 2라운드**(R1 HIGH=narrow-room silent
misdetect→density 판별자로 해소; R2 MEDIUM=sparse-narrow degenerate→area tiebreaker fail-loud(1.10→1.50)로 해소; docstring
정직성·det=−1 안전 주석) + **독립 verifier VERIFIED-GREEN**(실 ARKit 천장·3 fail-loud 경로·backward-compat 실측).
**Version** 0.25.2→0.25.3 PATCH(정확성 수정, 정확도 개선 아님). RELEASE_NOTES_v0.25.3.

**한계(정직)**: gravity-aligned-to-principal-axis 가정(기울어진 mesh→`up_axis=`); **센서 vs 실측 ±10 cm 절대정확도는
독립 GT(Faro/ScanNet++) 필요 — Phase 0b 후속, 미입증.** 스파이크 `eval_scene.py` GT 는 roomestim 로직 파생이라 재사용 금지.
**변경 파일**: `roomestim/adapters/mesh.py`, `tests/test_adapter_mesh.py`, `roomestim/__init__.py`·`pyproject.toml`(0.25.3),
`RELEASE_NOTES_v0.25.3.md`, `docs/adr/0027-...md`(§Status-update-2026-06-07), `.omc/plans/commercialization-analysis.md`, 본 D91.
**Cross-refs**: ADR 0027(mesh 어댑터)·ADR 0001(measured 경로)·ADR 0042(live-mesh, PROPOSED), D89(fail-loud 철학 선례),
commercialization Phase 0(0a 완료·0b=독립 GT·0c=acoustics 정직성 대기).

---

## D102 — OQ-38 CLOSED: `x_target_algorithm` round-trip 라벨 보존 (ADR 0041 PR1; v0.33.0; Phase 4, 2026-06-08)

**문제**: layout.yaml writer 가 `target_algorithm` 을 영속하지 않고 reader 가 재추론(`regularity_hint` +
`x_wfs_f_alias_hz` 존재 → WFS-vs-VBAP 만 구별) → `target_algorithm ∈ {DBAP, AMBISONICS}` 인 layout 이 read 시
**"VBAP" 로 silent 붕괴**(OQ-38). nudge round-trip 후 알고리즘 라벨 손실. ADR 0041 PR1 로 종결.

**수정(additive ~25 LOC)**: (1) writer `export/layout_yaml.py:placement_to_dict` — non-VBAP(DBAP/WFS/AMBISONICS)
에만 `out["x_target_algorithm"]` 방출(VBAP=reader 자연 기본값 → **golden byte-equal**, `x_wfs_f_alias_hz`/
`x_geometry_provenance` 와 동일한 "emit only when non-default" 선례). (2) reader `io/placement_yaml_reader.py` —
**restore-first/infer-fallback**: 키 있으면 복원하되 enum `{VBAP,DBAP,WFS,AMBISONICS}` 검증(out-of-enum →
`ValueError`, `_parse_provenance` 가드 미러, 기존 try/except 안에 두어 documented ValueError 계약 유지), 없으면
기존 추론 그대로(pre-v0.32 key-less layout backward-compat). schema 무변경(`additionalProperties:true`).

**정직성 가드**: 이는 round-trip **라벨** 결함만 종결 — roomestim 은 ambisonics rig 을 **생산하지 않음**(producer
부재). AMBISONICS enum 멤버는 ADR 0003 forward-compat 로 유지(삭제 안 함). ADR 0041 PR2-4(`place/ambisonics.py`
producer + dispatch branch + CLI `--order`)는 **DEFERRED**, trigger=§D-3a engine 식별·라우팅 gate(require.md
ambisonics mandatory 승격 또는 engine 팀 합의) — fake-completeness trap(decoder 없는데 rig 방출) 회피.

**검증**: round-trip 테스트 2건 invert(collapse→preservation) + 5건 신규(WFS 키-복원, VBAP 키-미방출, key-less
backward-compat, out-of-enum ValueError, AMBISONICS write→read→write byte-equal fixed-point) → 18p.
**Version** 0.32.0→0.33.0 MINOR(순수 additive·backward-compat). default 452→457p/6s, web 86p/3s 무변,
golden `place_vbap_ring_n8_default.yaml` byte-equal, ruff/mypy(strict) EXIT0.
**변경 파일**: `roomestim/export/layout_yaml.py`, `roomestim/io/placement_yaml_reader.py`,
`tests/test_layout_round_trip.py`, `roomestim/__init__.py`·`pyproject.toml`(0.33.0),
`docs/adr/0041-ambisonics-placement-design.md`(§OQ status), `.omc/plans/open-questions.md`(OQ-38 CLOSED), 본 D102.
**Cross-refs**: ADR 0041(ambisonics placement)·ADR 0036 §C(layout round-trip)·ADR 0003(forward-compat enum),
D50(round-trip fidelity), D61(OQ-38 v0.20 재유예), OQ-38(CLOSED).

## D103 — CLI `--algorithm` 기본값 추가: `place`/`run` 에서 생략 시 `vbap` (v0.38.0; 사용자 승인 2026-06-16)

**질문**: `roomestim place`/`run` 의 `--algorithm` 은 그동안 `required=True`(기본값 없음)이라 생략하면
argparse 오류로 종료됐다. 기본값을 추가할 것인가? 추가한다면 어떤 알고리즘을 기본으로?

**결정**: `--algorithm` 두 정의(`_add_place_parser` cli.py:124-128, `_add_run_parser` cli.py:246-250)를
`required=False, default="vbap"` 로 변경했다(`choices=["vbap","dbap","wfs"]` 불변). 사용자가 2026-06-16
승인했다. 생략 시 `vbap` 으로 기본 동작한다.

**근거**: (1) `vbap` 은 고정 반경 링이라 벽·천장 surface 없이 **항상 동작**한다. (2) `dbap` 은
`place/dispatch.py:45` 가 "DBAP placement requires at least one wall or ceiling surface" 를 raise 하므로,
기본값으로 두면 기하 없는(surface-less) 입력에서 crash → 기본값 부적합. (3) **정직성 제약**: `vbap` 은
구조상 geometry-blind(README '방 기하 인지에 대한 정직 고지' 참조) → 새 기본값은 기하-인지 배치가 아니며,
README note 는 이를 흐리지 않고 명시한다("기하-인지 배치가 목적이면 `--algorithm dbap` 을 지정"). downstream
은 모두 `args.algorithm` 을 동일하게 읽으므로(명시 설정 가정 코드 없음) 순수 backward-compatible.

**검증**: `tests/test_cli_input_validation.py` 에 (a) parser 기본값(`--algorithm` 생략 시
`args.algorithm == "vbap"`), (b) end-to-end `place` 무-flag 실행이 vbap layout 산출, 두 테스트 추가.
기존의 명시적 `--algorithm vbap|dbap|wfs` 호출은 동작 불변. MINOR 범프(0.37.1→0.38.0; 신규 능력, additive).
**변경 파일**: `roomestim/cli.py`(2 edit), `README.md`(honesty note + changelog row),
`roomestim/__init__.py`·`pyproject.toml`(0.38.0), `tests/test_cli_input_validation.py`(+2), 본 D103.
**Cross-refs**: README '방 기하 인지에 대한 정직 고지' note, ADR 0003(placement algorithm priority),
`place/dispatch.py:45`(DBAP surface 요구), D102.
