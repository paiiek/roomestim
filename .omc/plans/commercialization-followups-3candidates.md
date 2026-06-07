# Commercialization Follow-ups — 3 Candidates Implementation Plan

**Created:** 2026-06-07 (planner)
**Baseline at planning time:** v0.28.0 — canonical default gate
`/home/seung/miniforge3/bin/python -m pytest -m "not web and not vision and not lab and not e2e"`
→ **408 passed, 3 skipped**; web `-m web` → 86p/3s; `ruff check` + `mypy --strict` EXIT 0.
**Resume truth source:** `.omc/plans/commercialization-analysis.md` (RESUME POINTER + lines 198-234).
**Governing discipline:** 가짜 숫자 금지 — every accuracy claim empirically backed; anything
unverifiable is honestly DEFERRED or scoped to its buildable+verifiable core, never faked.

> RESUME POINTER: none of (4)/(5)/(6) started. Recommended order **(6) → (4) → (5)**.
> Each candidate below is self-contained; do them as separate commits. After each: re-run the
> full canonical gate (default + web + ruff + mypy), not just the new tests.

---

## ★ EXECUTION RESULTS (2026-06-07 autopilot) — all three resolved

| # | Outcome | Gate impact |
|---|---|---|
| **(6) cam_h** | **SHIPPED** — verifiable scale-honesty core (sensitivity helper + extended ASSUMED warning + `IMAGE_CAM_H_SCALE_NOTE`). Plan item (3) floor-plane cross-estimate **DEFERRED with mathematical proof** (floor polygon is scale-INVARIANT → cam_h not over-determined → any cross-estimate would be a fake number). ADR 0045 §honesty documents scale-ambiguity + cuboid-GT gap. | default 408→**414p/3s** (+6 torch-free tests), web 86p/3s, ruff/mypy EXIT0. Independent code-review **APPROVE**. |
| **(4) parametric .usdz** | **DEFERRED** — research (document-specialist, cited) found RoomPlan parametric semantics are **NOT in the USD** (routed out-of-band via CapturedRoom JSON + iOS-17 String→UUID mapping); `.usdz` exposes only geometry (already ingested by MeshAdapter), semantics already covered by JSON sidecar. Candidate as framed is moot/unbuildable-honestly. Recorded `.omc/research/oq4-roomplan-parametric-usd-defer.md`; improved `roomplan.py:225` NotImplementedError to an honest, informative message. Re-open needs a real exported `.usdz`+mapping JSON. | No accuracy code shipped (correct). Message-only edit (test catches NotImplementedError → safe). |
| **(5) OQ-55 visual material** | **DEFERRED (no-commit spike)** — feasibility report `.omc/research/oq55-visual-material-feasibility.md`. Blocker: no in-repo material/absorption GT → accuracy unverifiable → forbidden under 가짜 숫자 금지. Honesty trap (material→absorption→RT60 numeric pipeline) detailed. IF ever built: opt-in, ESTIMATE-labelled, RT60-neutral-unless-accepted, image-path-only — specified as a SEPARATE future task. | Zero production files; baseline unchanged. |

**Net:** 1 shipped within verifiable bounds, 2 honestly deferred with durable research + re-open
conditions. No unbacked accuracy number introduced anywhere.

---

## Cross-cutting honesty rule (applies to all three)

`provenance` and the `ceiling_confidence`/`ceiling_coverage` fields exist precisely to keep
unverified output from masquerading as measured. Every new code path MUST set the least-claim
label and MUST NOT introduce any number presented as an accuracy figure unless it is produced
by an empirical fixture in-gate. New disclosure strings go in
`roomestim/reconstruct/_disclosure.py` (single source of truth — same pattern as
`CEILING_CONFIDENCE_HEURISTIC_NOTE` / `RT60_DISCLOSURE`), never inline-retyped.

---

## Candidate (6) — image cam_h auto-estimation  ★ DO FIRST

### Why first
Most clearly buildable+verifiable, no new heavy deps, and removes the **dominant error lever**:
cold-eval (memory `project_image_backend_cold_eval`) found `cam_h` is the single largest error
dimension — `r = cam_h / tan(-v_floor)` is linear in `cam_h`, so +10 cm cam_h → +25-40 cm room
error, and a wrong default (1.6 m vs a real 1.2-1.4 m tripod) scales the whole room 15-30%.

### Current state (file:line)
- `roomestim/adapters/image.py:306-315` — `ImageAdapter.__init__(default_cam_height_m=1.6)`.
- `image.py:343-361` — scale source: measured `scale_anchor` (known_distance) ELSE assumed
  default `cam_h`, with an honest `UserWarning` ("scale is ASSUMED ... not measured").
- `image.py:90-91` — `_corners_to_room` requires `cam_h > 0`.
- `cli.py:404-417` — `_scale_anchor_for` builds `ScaleAnchor("known_distance", cam_height)` from
  `--cam-height`; returns `None` when omitted → adapter falls back to default + warns.

### The honesty trap (critical — read before building)
**A single equirectangular panorama is scale-ambiguous.** HorizonNet recovers layout shape up
to a global scale; `cam_h` IS that scale. There is NO pixel-only signal that recovers absolute
camera height without an external metric prior. Any "auto cam_h" that silently emits a number
is a fake-number generator. Two non-faking strategies exist:

1. **Known-size reference detection** (e.g. a detected door ≈ standard height) — needs a second
   classifier + a strong real-world prior; itself only a prior, not a measurement; HIGH effort,
   unverifiable on the current GT (see below). → **DEFER.**
2. **Prior-based estimate, explicitly labelled non-measured** — replace/augment the hard-coded
   1.6 m default with a documented prior (still ASSUMED), and/or surface a *consistency check*
   that flags when the chosen cam_h yields an implausible room. This does NOT claim accuracy.

### Buildable + verifiable core (honest)
Do **NOT** claim to recover true camera height. Build the verifiable scale-honesty machinery:

1. **cam_h sensitivity surfacing (deterministic, fully verifiable).** Add a torch-free helper
   in `image.py` (e.g. `_cam_h_sensitivity(cor_id) -> dict`) that, given the recovered corners,
   reports how room dimensions scale with cam_h (the linear `r ∝ cam_h` relationship) and the
   plausibility window of cam_h values that keep all corners within `_MAX_PLAUSIBLE_RADIUS_M`
   (image.py:65). This is pure geometry — exactly invertible, so it is unit-testable against a
   synthetic `cor_id` with NO torch and NO real-data accuracy claim.
2. **Honest default provenance.** Keep `provenance="reconstructed"` (image.py:191). If a
   prior-based default cam_h is used (no anchor), the existing ASSUMED warning
   (image.py:354-361) already discloses it — extend it to cite the sensitivity (e.g. "a ±10 cm
   cam_h error ≈ ±X% room scale") using a single-source disclosure string in `_disclosure.py`.
3. **Optional: floor-plane cam_h cross-estimate, clearly labelled.** IF (and only if) the floor
   corners over-determine a consistent cam_h (cuboid: all four floor depression angles + a
   right-angle constraint), expose it as a *diagnostic* `estimated_cam_h_m` that is NEVER used
   to silently override the user/anchor value and is labelled as a layout-derived ESTIMATE, not
   a measurement. This is verifiable on synthetic cuboids (analytic inverse already exists in
   `tests/test_adapter_image.py:_synthetic_cor_id`). Gate it behind explicit opt-in.

### Honestly deferred (with reason)
- **True absolute cam_h recovery from one pano.** Scale-ambiguous; impossible without external
  metric prior. DEFER (document in ADR 0045 §image-backend honesty + `_disclosure.py`).
- **Empirical accuracy claim for any auto-cam_h on real panos.** The available GT (244-pano
  PanoContext/S2D3D mirror) is **100% cuboid-labelled** (memory cold-eval line 18), so the
  silent-degrade path for non-Manhattan / >4-corner rooms is **unverifiable on current data**.
  Any "auto cam_h improves accuracy by N cm" claim is therefore UN-BACKED → forbidden. State
  this limitation explicitly.

### Verification strategy
- **In-gate (default lane, torch-free):** new unit tests in `tests/test_adapter_image.py` using
  the existing `_synthetic_cor_id` inverse: assert the sensitivity helper reports the exact
  linear scaling (analytic), assert the plausibility window math matches `_MAX_PLAUSIBLE_RADIUS_M`,
  and (if (3) is built) assert the diagnostic cam_h equals the synthetic ground-truth cam_h on
  a cuboid to ~1e-6. These are deterministic — empirically honest because the fixture's cam_h
  is known exactly.
- **What canNOT be claimed in-gate:** any real-pano accuracy delta (needs `[vision]` extra,
  excluded from default gate; and GT is cuboid-only). If a real-pano sweep is run, it must live
  out-of-gate and be reported as cuboid-only, NOT as a general accuracy claim.
- **Gate markers:** default lane (torch-free core), unchanged baseline + new passing tests.
  No `vision`-marked test should be required for GREEN.

### Files to touch
`roomestim/adapters/image.py` (helper + extended ASSUMED warning), `roomestim/reconstruct/_disclosure.py`
(new `IMAGE_CAM_H_SCALE_NOTE`), `tests/test_adapter_image.py` (new in-gate tests),
`docs/adr/0045-image-to-geometry-capture-backend.md` (§honesty: scale-ambiguity + cuboid-GT gap),
optional `roomestim/cli.py` (surface diagnostic only if (3) built).

### Acceptance criteria
- [ ] New torch-free sensitivity helper + tests pass on default lane; baseline rises (408 → 408+N).
- [ ] No code path silently overrides a user/anchor cam_h with an inferred value.
- [ ] `provenance` stays `"reconstructed"`; disclosure string added to `_disclosure.py` only.
- [ ] ADR 0045 documents the scale-ambiguity + cuboid-GT verification gap explicitly.
- [ ] web 86p/3s, ruff + mypy --strict EXIT 0.

---

## Candidate (4) — Real .usdz RoomPlan parametric (CapturedRoom) ingest  ★ DO SECOND

### Current state (file:line)
- `roomestim/adapters/roomplan.py:225-230` — `.usdz` suffix → `NotImplementedError` (parametric
  path reserved; JSON sidecar is the CI path). The JSON sidecar (`roomplan.py:240-348`) already
  parses the **full** parametric content: walls (transform+dims+material_hint), floors/ceilings
  (polygons), and objects (`_extract_objects`, roomplan.py:131-203, incl. furniture).
- `roomestim/adapters/mesh.py:664-816` — `.usdz` **geometry-mesh** path: reads `UsdGeom.Mesh`
  prims only; explicitly bails on parametric CapturedRoom (`mesh.py:679-683`,
  "Parametric RoomPlan USD ... is not yet supported"). usd-core import helper at `mesh.py:641-662`.
- `scripts/gen_usdz_fixtures.py` — already authors synthetic `.usdz` mesh fixtures via `pxr`
  (`UsdGeom.Mesh` + `CreateNewUsdzPackage`); committed as `tests/fixtures/shoebox_{yup,zup}.usdz`,
  exercised by `tests/test_adapter_mesh.py:759-832`. **This is the proven fixture-synthesis path.**
- `[usd]` / `[mesh-export]` extras = `usd-core>=24.0` (pyproject.toml:45-46). usd-marked? No —
  USDZ tests `pytest.skip` when the fixture/usd-core is absent (test_adapter_mesh.py:71); they
  run in the default lane when usd-core is installed (it is, in miniforge).

### Key insight (de-risks scope)
Parametric `.usdz` ingest adds **NO new geometric capability** over the existing JSON sidecar —
the sidecar already carries every wall/floor/ceiling/object the parametric USD would. The value
is **file-format coverage** (a user who exported only the `.usdz`, not the sidecar). Frame the
deliverable as format convenience, NOT an accuracy improvement. This keeps it out of fake-number
territory by construction: geometry numbers come straight from the parametric entities, same as
the sidecar.

### The honesty trap (critical)
**No real Apple RoomPlan parametric `.usdz` fixture exists**, and Apple's exact USD schema for
`CapturedRoom` (how walls/openings/objects + their dimensions/transforms/categories are encoded:
`UsdGeom.Cube` with `size`+xform? custom attrs? `customData`?) is **not pinned in this repo**.
A synthesized fixture tests only OUR interpretation of the schema — passing tests would prove
self-consistency, NOT real-RoomPlan compatibility. Claiming "RoomPlan parametric ingest works"
on the strength of a self-authored fixture is the fake-number trap for this task.

### Buildable + verifiable core (honest)
1. **Schema research FIRST (gating step).** Determine Apple's actual CapturedRoom USD encoding
   from authoritative sources (Apple RoomPlan docs / `USDExport` / a real exported sample if one
   can be obtained). Record findings in a new ADR (extend ADR 0027 mesh-format-generalisation or
   add ADR 0048). **Decision gate:** if the real schema cannot be pinned with confidence, ingest
   stays DEFERRED and the work stops here (honest — do not ship a guess).
2. **If schema is pinned:** add a parametric branch to `MeshAdapter._room_model_from_usdz`
   (mesh.py:664) OR a dedicated `RoomPlanAdapter` `.usdz` branch (roomplan.py:225) that reads the
   parametric prims (walls/openings/objects + transforms/dims/categories) and routes them through
   the SAME `_extract_objects` / wall-polygon / material-hint logic the sidecar already uses
   (reuse roomplan.py helpers — single-source the parametric→RoomModel mapping). Detect parametric
   vs plain-mesh USDZ by prim type/schema so the existing geometry-mesh path (mesh.py) is unaffected.
3. **Provenance:** `provenance="measured"` (RoomPlan = LiDAR depth, consistent with sidecar
   roomplan.py:347 and mesh.py:959). Carry `ceiling_confidence`/`ceiling_coverage` only if a true
   geometric coverage measure is computed; otherwise leave least-claim defaults (`"unknown"`/None).

### Verification strategy
- **Synthetic parametric fixture** authored with `pxr` (extend `scripts/gen_usdz_fixtures.py` with
  a `make_captured_room()` that writes parametric wall/opening/object prims per the pinned schema),
  committed under `tests/fixtures/`, parsed in `tests/test_adapter_roomplan.py` (or
  `test_adapter_mesh.py`) — round-trip against known dims (mirror the existing
  `test_a9a_sidecar_parses` tolerances: ceiling ±10 cm, area ±5%, walls ≥4).
- **Honesty boundary (must be stated in code + ADR + README):** the synthetic fixture validates
  the PARSER against OUR schema model, NOT against real Apple output. Label the parametric path
  **PROVISIONAL / unverified-against-real-RoomPlan** until a real exported `.usdz` is parsed. Do
  not advertise "RoomPlan parametric supported" without that caveat.
- **Gate markers:** prefer default lane (usd-core present in miniforge); guard with `pytest.skip`
  when usd-core absent (same pattern as test_adapter_mesh.py:71). No accuracy number is claimed —
  only structural round-trip on a known synthetic box.

### Honestly deferred (with reason)
- **Real-RoomPlan compatibility guarantee.** Unverifiable without a real exported parametric
  `.usdz` (none available; no macOS capture in scope). DEFER; keep PROVISIONAL label until a real
  sample arrives. If schema can't be pinned in step 1, defer the WHOLE candidate.

### Files to touch
`scripts/gen_usdz_fixtures.py` (parametric fixture author), `roomestim/adapters/roomplan.py`
and/or `roomestim/adapters/mesh.py` (parametric branch reusing sidecar helpers),
`tests/test_adapter_roomplan.py` (round-trip test + skip guard), new ADR (schema record +
PROVISIONAL status), `README.md` (RoomPlan input matrix — note parametric `.usdz` PROVISIONAL).

### Acceptance criteria
- [ ] ADR records Apple CapturedRoom USD schema with sources, or candidate is DEFERRED with reason.
- [ ] If built: synthetic parametric fixture round-trips (ceiling ±10 cm, area ±5%, walls ≥4),
      reusing the sidecar parametric→RoomModel mapping (no duplicated geometry logic).
- [ ] Existing geometry-mesh `.usdz` path (shoebox fixtures) byte-equal / unaffected.
- [ ] Parametric path labelled PROVISIONAL (code docstring + ADR + README) — no real-RoomPlan
      compatibility claimed.
- [ ] `provenance="measured"`; full canonical gate GREEN (default 408+, web 86, ruff/mypy EXIT 0).

---

## Candidate (5) — OQ-55 visual material proposal  ★ DO LAST — NO-COMMIT SPIKE

### Mandate (from resume truth + user)
Explicitly flagged "저신뢰, auto-commit 금지". Prior session judged real material *inference*
"정직하게 빌드 불가": measured mesh has NO appearance/material data (mesh.py emits hardcoded
`WOOD_FLOOR`/`CEILING_DRYWALL`/`WALL_PAINTED`, mesh.py:921-943); the image path explicitly does
NO visual material inference (image.py:152-153, every surface `MaterialLabel.UNKNOWN`). A real
classifier is a separate vision capability with no in-repo verification path.

### Deliverable = RESEARCH SPIKE / feasibility report (NOT committed accuracy-claiming code)
Produce a written feasibility deliverable + (optionally) a throwaway spike OUTSIDE the shipping
adapters. The spike must NOT land any code that surfaces a material as if it were inferred with
accuracy. Scope it as: what CAN be honestly built vs what stays deferred.

- **CAN honestly build (if anything ships at all):** an OPT-IN, clearly-labelled COARSE material
  *proposal* surfaced strictly as `ESTIMATE` / low-confidence, gated behind an explicit flag,
  carrying NO accuracy number, and NEVER overriding `MaterialLabel.UNKNOWN` silently in the
  default path. Provenance/labelling must make clear it is a proposal, not a measurement. Any
  such mechanism is a SEPARATE follow-up only if the spike concludes it is honest — the spike
  itself commits nothing.
- **Must stay DEFERRED:** any material *accuracy* claim. No labelled dataset of
  roomestim-relevant surface materials with measured absorption is available in-repo → accuracy
  is unverifiable → forbidden to claim.

### The honesty trap (critical)
Material → absorption coefficient → RT60 is a direct numeric pipeline. A wrong-but-confident
material label silently changes the RT60 estimate, fabricating an acoustic number. The trap is
shipping a classifier whose label feeds `MaterialAbsorption` without an empirical accuracy bound.
Avoid by: (a) NOT committing any classifier into the shipping path; (b) if a proposal mechanism
is ever shipped, it must be opt-in, ESTIMATE-labelled, and must NOT change RT60 unless the user
explicitly accepts the proposed material (same honesty bar as the RT60 disclosure).

### Verification strategy
- The spike itself ships NO gate-affecting code → baseline unchanged (408/3).
- The deliverable is a feasibility report: data availability (is there ANY verifiable
  material/absorption GT?), candidate approaches (image classifier vs mesh — mesh has no
  appearance data, so mesh is a hard NO), the honest UX (opt-in ESTIMATE proposal), and a
  go/defer recommendation. Cite the no-GT gap as the blocker for any accuracy claim.
- If any artifact is written, it goes in `.omc/research/` or as a no-commit ADR draft — NOT into
  `roomestim/` production modules.

### Files to touch
`.omc/research/oq55-visual-material-feasibility.md` (report), optionally a throwaway spike under
a scratch dir (NOT `roomestim/`), optionally an ADR draft. **No production module edits.**
**No commit of accuracy-claiming code.**

### Acceptance criteria
- [ ] Feasibility report delivered: data/GT availability, approaches, honest UX, go/defer call.
- [ ] Zero changes to shipping adapters / predictor / RT60 path; baseline 408/3 unchanged.
- [ ] If a proposal mechanism is recommended, it is specified as opt-in + ESTIMATE-labelled +
      RT60-neutral-unless-accepted — and explicitly scoped as a SEPARATE future task, not this one.

---

## Recommended order & dependencies

1. **(6) cam_h** — independent, torch-free, fully in-gate verifiable; highest value (kills the
   dominant error lever's silent-ness). No dependency on others.
2. **(4) parametric ingest** — bounded IFF schema can be pinned (gating research step); reuses
   existing sidecar mapping + proven fixture-synthesis path. Independent of (6). Defer whole
   candidate if schema unpinnable.
3. **(5) OQ-55 spike** — no-commit feasibility only; last because it ships nothing and its honest
   conclusion likely DEFERS. Independent of (4)/(6).

No hard inter-dependencies; order reflects value × verifiability × honesty-risk (low→high).

---

## Side fix (DONE during planning)
Auto-memory `reference_canonical_test_env.md` updated to state the MEASUREMENT METHOD explicitly:
the canonical baseline is the **marker-scoped** command
`-m "not web and not vision and not lab and not e2e"` → **408p/3s @v0.28.0** (NOT a bare
`pytest -q`, which over-collects). History chain 275/6→388/3→396/3→408/3 recorded.

---

## ADR (decision record for this planning cycle)
- **Decision:** Pursue (6) then (4) then (5); (6) and (4) ship code only within empirically
  verifiable bounds, (5) ships nothing (no-commit spike).
- **Drivers:** 가짜 숫자 금지 discipline; verifiability of each claim in-gate; value of removing
  the dominant image error lever; file-format coverage value of (4); absence of material GT for (5).
- **Alternatives considered:** ship a real auto-cam_h regressor (rejected — scale-ambiguous,
  cuboid-only GT, unverifiable); ship parametric ingest validated only by self-authored fixture
  as "supported" (rejected — circular, mislabels real compatibility); ship a visual material
  classifier into the RT60 path (rejected — fabricates acoustic numbers without accuracy bound).
- **Why chosen:** each retained scope has a deterministic in-gate verification or an explicit
  PROVISIONAL/DEFER label; none introduces an unbacked accuracy number.
- **Consequences:** (6) improves honesty/UX, not headline accuracy; (4) adds format coverage with
  a PROVISIONAL caveat until a real RoomPlan sample exists; (5) likely concludes DEFER.
- **Follow-ups:** real RoomPlan `.usdz` sample acquisition (unblocks (4) verification); a
  material/absorption GT dataset (unblocks (5) accuracy); known-size-reference cam_h prior (a
  future (6) extension if a verifiable prior is found).
