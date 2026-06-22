# roomestim — Prioritized Backlog (durable, all-future-work)

Created: 2026-06-08 · Baseline: **v0.31.0**, default 433p/3s, origin/main synced.
Owner intent: "권장순 백로그 저장하고 나중에 모두 수행" — this file is the single source of
truth for what to do next, in priority order. Update the RESUME POINTER at the bottom each phase.

Guiding compass:
- **North star** = roomestim's own SPATIAL-INFERENCE robustness (geometry) is the frontier.
  RIR/acoustics are a *means*, low priority. (`project_roomestim_north_star`)
- **Commercialization SWOT 3 blockers**: ① real-capture geometry never validated,
  ② real `.usdz` (RoomPlan parametric) ingest, ③ acoustics is demo-grade.
- **Hard rule: NO FAKE NUMBERS.** If GT is absent or ambiguous, report honest caveats,
  do not fabricate agreement. (Pattern of last commits ec285a7 / 8b0b074.)
- All non-trivial work goes through OMC: planner → executor → code-review → verifier;
  no self-approval. Validation work is doc-only unless results genuinely warrant a code
  change (then route the change through review separately).

Status reached as of this file: immediate code-only candidates exhausted (4-candidate
A/B/C/D cycle closed). Every remaining item is one of:
(가) external-data gated, (나) large refactor, (다) un-verifiable now (fake-number trap).

---

## 🟢 Tier 1 — DO NOW (data in hand, bounded, honest result guaranteed)

### ① footprint/wall geometry validation — room-local laser crop (ARKitScenes)  ← IN PROGRESS
- **What**: Use the already-downloaded ARKit Faro laser GT (~47GB local at
  `/home/seung/mmhoa/spike-vggt-multiview/data/arkit`) cropped *per room* (manual / semi-
  automatic crop) to BYPASS the failed automatic localization (FPFH+RANSAC fitness 0.18–0.22)
  and measure footprint/wall error for the FIRST time. Also extends the ceiling corpus to N scenes.
- **Why #1**: tightest fit to north star (geometry robustness = frontier) + directly hits
  SWOT blocker ① (0 real-capture geometry validations). Ceiling already validated (clean
  3-scene ~1–4cm); footprint/wall still 0.
- **Data/tooling**: `phase0b/{footprint_validate,footprint_register,footprint_register2d,
  gt_extract}.py`, `laser_scanner_point_clouds/<visit>/*.ply`, `mesh/<video>/*_3dod_mesh.ply`,
  `laser_scanner_point_clouds_mapping.csv`. roomestim side: `MeshAdapter().parse(<ply>)`.
- **Risk**: automatic localization already FAILED → room-local crop is the workaround. Crop
  is data-prep (bounded), not an algorithm. If error > 15cm, honestly downgrade the claim.
- **Output**: `.omc/research/arkit-footprint-wall-laser-validation.md` (gitignored).
  Do NOT change production/version unless a real regression/feature is justified (then via review).

### ② RT60 accuracy validation — BUT ReverbDB (CC-BY ~8.7GB, 9 rooms measured RIR + box dims)  ← IN PROGRESS
- **What**: Use measured RT60 GT to produce predictor's FIRST honest error bar. Current RT60
  has ±1.4s and NO accuracy gate (tests assert ordering, not magnitude).
- **Why high**: hits SWOT blocker ③ (acoustics demo-grade). Converts "no accuracy claim" →
  "honest error bar". Cleanest task with the surest result (data commercial-OK, identified).
  Its GT also unblocks ③/Tier-2 (polygon-ISM RT60).
- **North-star note**: acoustics is low priority → ranked behind ①, but its *certainty* is higher.
- **Data**: BUT ReverbDB (NOT yet on disk — agent downloads it). CC-BY 4.0. 9 rooms, measured
  RIRs + room box dimensions. Extract measured RT60 (Schroeder/EDT), feed dims to predictor, compare.
- **Output**: `.omc/research/but-reverbdb-rt60-validation.md` (gitignored).

---

## 🟡 Tier 2 — after Tier 1 lays the GT (features)

### ③ polygon-ISM RT60 cascade (ADR 0040)
Extend v0.31.0 candidate C (geometry-only `polygon_image_source.py`) into a real acoustic
predictor. **Blocker = non-shoebox measured RT60 GT (= ②) + pra RT60-fit reliability unverified.**
②-complete is the prerequisite.

### ④ real RoomPlan `.usdz` parametric ingest (SWOT blocker ② remainder)
Mesh `.usdz` ingest already works. RoomPlan semantics aren't in USD (CapturedRoom JSON + iOS17
UUID mapping is out-of-band) → judged moot in D-candidate. **Reopen when a real-device export
sample is obtained.**

### ⑤ furniture absorption validation — Motus / MeshRIR (CC-BY)
Validate v0.27.0 free-standing absorption wiring against measured RT60. By-product of ②, acoustics → low.

---

## 🔵 Tier 3 — code-only features but weak verification gate

### ⑥ live-mesh non-convex corner extraction (ADR 0042, alpha-shape)
footprint currently = convex-hull (structural over-estimate) → alpha-shape improvement.
North-star aligned, 0 external data, but footprint GT absent (① lays it) → tie to ① to be meaningful. Design done.

### ⑦ ambisonics layout (ADR 0041)
Resolves dead enum + OQ-38 round-trip. Code-only but product-peripheral.

---

## ⚪ Tier 4 — large / low-priority / conditional

- **⑧ true multi-room RoomCollection (ADR 0047)** — multi-PR core refactor, no real multi-room
  fixture → DEFER (product is single-room).
- **⑨ RIR auralization Phase B/C (ADR 0044)** — explicitly low priority per north star (Phase A shipped v0.23.0).
- **⑩ PyPI publish (ADR 0007)** — already PyPI-ready (v0.30.0). Reverse-criteria (downstream
  demand) not triggered → publish the moment a consumer appears.

---

## ⛔ Blocked now (data absent → fake-number trap)

- **cam_h known-size prior** (ADR 0045 §D) — detector + verifiable prior absent.
- **material inference** (OQ-55) — material/absorption GT = 0 → accuracy unverifiable.
- **per-corner uncertainty** (OQ-57) — calibration data absent.

---

## RESUME POINTER

- 2026-06-08: backlog created; **① and ② both EXECUTED + reviewed + revised via OMC** (the two
  recommended directions). Full cycle each: scientist (opus) → critic (opus) APPROVE-WITH-FIXES
  → author revision → verified reproducible. Doc-only: NO production/test/version change
  (git: only `.omc/` artifacts; version still 0.31.0, default gate untouched at 433p/3s).

  **① ARKit footprint/wall — `.omc/research/arkit-footprint-wall-laser-validation.md` — HONEST NEGATIVE.**
  - 0/5 scenes give a trustworthy ≤15cm footprint/wall validation; 1/5 (42445021) co-registerable
    but only SUGGESTIVE (full-2D centroid offset ~1.7m, ICP t≈0.14m/r≈9°/RMSE 4.4cm; footprint area
    "right ballpark" ~+2/−18% but dims ≥~20cm > ±15cm; co-reg residual itself >15cm). 4/5 excluded
    honestly (multi-floor / building-scale frame offset 1.4–4m / non-identifiable local 2D-ICP —
    e.g. 42444946 false 135° fit at 84% inlier).
  - Verdict: **≤15cm footprint/wall claim UNVALIDATED (not refuted)** — GT horizontal-localization
    uncertainty exceeds the tolerance. **SWOT blocker ① persists.** Confirmed convex-hull footprint
    over-estimate (bulges past re-entrant corners) → motivates ⑥ alpha-shape.
  - Critic MAJOR-1 caught a mislabeled centroid number ("0.30m" was X-axis-only, not 2D norm) → fixed
    to reproducible 1.66m; conclusion unchanged (larger residual only strengthens the negative).
  - To actually validate footprint/walls: need a dataset with KNOWN scan↔GT extrinsic OR a
    single-room laser scan (no adjacent rooms). ARKitScenes Faro visits are whole-floor → can't.
    Non-obvious unchecked lever: full upstream ARKitScenes video-trajectory↔visit alignment (Open Q).

  **② RT60 — `.omc/research/but-reverbdb-rt60-validation.md` — first honest RT60 error bar.**
  - BUT ReverbDB download is HTTP-403 blocked server-side (no CC-BY mirror) → honest pivot to
    **dEchorate (CC-BY 4.0)**: ONE measured cuboid (5.705×5.965×2.355m) × 11 absorption configs.
    Tests acoustic/material fidelity with geometry EXACT — NOT geometric robustness (BUT's goal). v1
    processed HDF5 used (advertised v2 is upstream-corrupt; published MD5 matches the broken file).
  - Error bar (geometry exact, only materials vary): ISM materials-KNOWN median 0.062s / max 1.965s;
    ISM DEFAULT materials (realistic no-info case) median 1.71s / max 2.30s. ISM error is
    BIDIRECTIONAL (over-predicts reflective rooms ~2.0s specular blow-up; under-predicts foam-dominated).
    Eyring diffuse is worst-case-safer (max 0.355s) but biased low.
  - Verdict: **±1.4s disclaimer is directionally honest (materials dominate; unknown materials ⇒
    indicative) but magnitude TOO TIGHT for small hard-surface / unknown-material rooms** (real errors
    reach ~2.3s). Dominant error source = MATERIALS, not geometry.

- **NEXT after ①/②:**
  - ③ polygon-ISM RT60 (ADR 0040): ② provides a real measured-RT60 GT (dEchorate) → now testable,
    BUT note the empirical finding that ISM over-predicts rigid rooms (use a diffuse-field cap/blend).
    A real predictor finding surfaced: ISM reflective over-prediction + `MELAMINE_FOAM` α likely too
    high vs partial-coverage foam — route any code change through a separate review pass (not done here).
  - ⑥ alpha-shape non-convex footprint (ADR 0042): ① re-confirms the convex-hull over-estimate, but ①
    also shows footprint GT is still missing (localization unsolved) → improvement would be
    un-validatable until a known-extrinsic / single-room laser dataset is found. Tie to that data lever.
  - Still-open external-data levers: known-extrinsic footprint dataset (unblocks ① + ⑥ validation),
    a reachable multi-room measured-RT60 set (BUT mirror or alternative), real RoomPlan parametric
    export (④). Tier-3/4 code-only items (⑦ ambisonics) remain available anytime.

- **2026-06-22 RECONCILIATION (autopilot candidate-triage, baseline v0.43.0):** this backlog was
  authored at v0.31.0; since then the queue has been worked down to exhaustion. Re-checked every lever
  against current `main` (`6e86863`, default 686p/7s GREEN · ruff clean · mypy 57 files clean):
  - ⑥ alpha-shape/concave footprint = **SHIPPED** (`reconstruct/floor_polygon.py`: `shapely.concave_hull`
    + occupancy extractor + `auto` convex-inflation auto-select; ADR 0042 done).
  - ⑦ ambisonics layout = **SHIPPED** v0.39.0 (`place/ambisonics.py`; ADR 0041).
  - ⑧ multi-room RoomCollection = **SHIPPED** v0.40.0→v0.43.0 (composition container + per-room offset
    + combined glTF/USD + real CapturedStructure splitter; ADR 0049/0050 — sidestepped the ADR0047 refactor).
  - ② RT60 error bar = **DONE** (dEchorate honest error bar, doc).
  - ③ polygon-ISM RT60 cascade = **DEFERRED, data-blocked**: MP-RIR (only new non-shoebox measured GT)
    has NO ceiling-height / material GT → RT60 magnitude is a material-confound fake-number trap
    (`diffrir-nonshoebox-validation.md` P2/P4). Geometry/TOA portion already validated + just committed
    (`6e86863`, ADR 0040 §Status-update edge2 method-backed negative).
  - ④ RoomPlan parametric ingest = **moot/deferred** (needs real-device export sample; geometry-only
    `.usdz` already ingested).
  - ⑤ furniture absorption, cam_h prior, material inference, per-corner uncertainty = **fake-number
    traps** (absorption/material/calibration GT = 0).
  - ⑩ PyPI publish = **install-grade DONE**; actual publish is **user-gated** (creds + approval).
  - North-star frontier = **multi-view VGGT fusion A1** (`project_multiview_fusion_a1`): convex_band
    12.7cm median / 7-of-10 ≤15cm (first sub-install-grade) but n=10 + convex-room artifact + flyer/scale
    caveats, real general solution = TSDF multi-session (large). **At user decision gate** (a vs b).
  - **CONCLUSION: no fresh-shippable, data-independent, non-user-gated candidate exists.** Every value-
    additive lever now needs external GT we don't have, user credentials, or a user direction decision.
    Manufacturing low-value off-north-star work (e.g. RIR auralization Phase B/C, explicitly low-priority
    means) would violate the compass + NO-FAKE rule. Autopilot stops here per its explicit stop-condition.
    **Next action is a user decision**, not more autonomous code: (a) green-light multi-view A1 toward
    TSDF/general fusion, (b) approve PyPI publish (provide creds), or (c) supply an external GT lever
    (known-extrinsic footprint dataset / non-shoebox material+ceiling RT60 set / real RoomPlan export).
