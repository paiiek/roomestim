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

