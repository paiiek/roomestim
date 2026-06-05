# image-backend honesty follow-ups (rec #1 provenance-in-layout + rec #2 real-model golden) — BUILD

Resume truth source for the two user-selected follow-ups after the v0.25.0 image→geometry ship.
Parent build: `.omc/plans/image-backend-single-pano-build.md` (BUILD COMPLETE @ `6c9780f`).

## SCOPE (user decision 2026-06-05: "일단 1,2 해보자")
- **T1 provenance propagation → layout.yaml** — carry the rough-tier honesty marker into the
  *placement artifact boundary* (currently only volatile stderr via `_maybe_print_estimated_notice`).
  room.yaml already persists `provenance` (room_yaml.py:138); layout.yaml does NOT. Gap = layout.yaml.
- **T2 real-model golden test** — one `vision`-marked regression test that runs the REAL torch path
  (`_infer_corners` → HorizonNet) on a vendored synthetic pano; in-gate tests are torch-free only.
- rec #3 (web exposure ban until OQ-57) = policy, NOT in scope here.

## ORCHESTRATION (mandatory per memory)
planner(done inline)→executor→code-reviewer→independent verifier; no self-approval; autonomous
execute→verify(full gate)→repeat; update this RESUME POINTER each phase.

## DE-RISK FACTS (captured 2026-06-05, before build)
- canonical miniforge: torch 2.5.1 present but **torchvision BROKEN** (`operator torchvision::nms does not exist`,
  RuntimeError NOT ImportError) → real path cannot run in default gate; golden MUST skip there.
- WORKING vision venv: `/home/seung/mmhoa/spike-image-geometry/venv/bin/python` (torchvision 0.20.1) + has
  roomestim core deps (shapely/yaml/jsonschema/numpy/scipy/sklearn/cv2).
- local st3d ckpt (offline, no network): `/home/seung/mmhoa/spike-image-geometry/ckpt/resnet50_rnn__st3d.pth`
  → set `ROOMESTIM_HORIZONNET_CKPT` to it; `PYTHONPATH=/home/seung/mmhoa/roomestim`.
- synthetic pano source: `/home/seung/mmhoa/spike-image-geometry/synth/roomA.png` (1024×512, 14KB, OUR render
  via render_synth_pano.py; GT W=4.0 D=3.0 H=2.7 cam_h=1.6). MIT-clean (our own procedural render).
- **GOLDEN (ImageAdapter.parse, ScaleAnchor known_distance=1.6, DETERMINISTIC across 2 runs to 1e-4):**
  width_x=4.7327, depth_z=3.9647, ceiling=3.1528, provenance=reconstructed, materials={UNKNOWN},
  objects=[], n_surfaces=6 (floor+ceiling+4 walls). vs GT 4.0/3.0/2.7 → err +73/+96/+45cm = ROUGH (documents tier).

## T1 DESIGN (minimal, byte-equal for existing layouts)
1. `model.py` PlacementResult: add `geometry_provenance: Provenance = "assumed"` (Provenance already in model.py).
2. `export/layout_yaml.py` placement_to_dict: emit top-level `x_geometry_provenance` ONLY when value
   `!= "assumed"` (covers reconstructed=rough marker + measured=positive claim; assumed stays implicit →
   ALL existing layouts byte-equal since every existing PlacementResult defaults assumed). geometry_schema
   root additionalProperties:true → validates. If any measured-room CLI golden breaks → narrow to
   reconstructed-only (fallback). [verify in gate]
3. `io/placement_yaml_reader.py`: read `data.get("x_geometry_provenance","assumed")`, validate via reused
   `_parse_provenance` (from room_yaml_reader), set on PlacementResult → edit round-trips it.
4. `cli.py`: thread `room.provenance` onto result. Single point: in `_run_placement` wrapper set
   `result.geometry_provenance = room.provenance` (covers _cmd_run + _cmd_place). `_cmd_export` reads both
   room+placement → set `placement.geometry_provenance = room.provenance` (room authoritative) before write.
   `_cmd_edit` (no room) → relies on reader round-trip (already preserved). 
5. tests (extend test_provenance_roundtrip.py or new test_layout_provenance.py): reconstructed→key present;
   assumed→key absent (byte-equal); measured→present; edit round-trips; reader missing-key→assumed.

## T2 DESIGN
1. vendor `tests/fixtures/image/roomA_synth_pano.png` = copy of spike synth/roomA.png + provenance note in a
   sibling `README.md`/`.meta` (render params + GT + MIT-clean origin).
2. pyproject markers: add `"vision: requires the [vision] extra (torch+torchvision+HorizonNet weights); excluded from default CI"`.
3. new `tests/test_image_backend_golden.py`:
   - module-level `_vision_stack_available()` try/except BROAD Exception (handles broken torchvision RuntimeError)→bool.
   - `@pytest.mark.vision` + skipif(not available). Body: ImageAdapter().parse(fixture, ScaleAnchor('known_distance',1.6))
     under warnings suppression; on OSError/ConnectionError/ImportError (no ckpt/offline)→pytest.skip.
   - assert provenance==reconstructed, all materials UNKNOWN, objects==[], n_surfaces==6, 4 walls,
     width_x≈4.7327 / depth_z≈3.9647 / ceiling≈3.1528 each abs=0.2 (regression lock); comment documents GT+rough err.
   - MUST run green in vision venv (capture exact); MUST skip in canonical default gate (broken torchvision).

## VERSION / DOCS
- PATCH bump 0.25.0→0.25.1 (additive honesty marker, backward-compat). ADR 0046 (provenance) +status-update
  for layout-boundary propagation; new D-number; RELEASE_NOTES or CHANGELOG line. Keep lean.

## GATES (baseline to beat — capturing @ HEAD 076a645)
canonical `/home/seung/miniforge3/bin/python -m pytest`. default `-m "not web and not lab and not e2e"`,
web `-m web`, ruff, mypy(roomestim only), tense EXIT0. (baseline numbers filled after bg run completes.)

## PHASES
- [x] P1 T1 implement (executor) → code-review → full gate  — commit-pending
- [x] P2 T2 implement + run golden in vision venv (executor) → code-review → full gate  — commit-pending
- [x] P3 version+docs wrap → independent verifier → commit  — wrap done (v0.25.1); commit-pending

## ROUND 2 (2026-06-05 PM) — cold eval → 2 follow-ups (user: "둘다진행")
Cold multi-scenario eval (scientist, 244 real panos + synthetic sweeps) findings:
- adapter == spike pipeline numerically (no divergence; faithful). per-DIM median 39cm(res)/50cm(office)
  matches README; but per-ROOM(both dims) median 83-95cm, both-≤15cm only 3-8% → README per-dim framing optimistic.
- dominant lever = cam_h (user-supplied): +10cm → +25-40cm dim err (linear). assumed-default 1.6 → 15-30% over-scale.
- **WORST FAILURE (new): near-horizon radius blowup** `r=cam_h/tan(-v_floor)` diverges; 2% of res emit absurd
  >15m rooms (24.9m, 41m) with NO flag. `_MIN_FLOOR_TAN=1e-6` guard too loose (catches AT-horizon, not NEAR).
- force-cuboid silent-degrade path UNVALIDATABLE here (this PanoContext mirror is 100% cuboid GT).
- 0/240 crash failures (robust to crash, not to wrong answer).

### F1 (CODE) near-horizon plausibility guard — adapters/image.py `_corners_to_room` — DONE
- root cause: per-corner r blowup. Honest fix = REJECT physically-implausible reconstruction loudly (raise
  ValueError w/ depression-angle diagnostic) instead of silently emitting a giant room. NOT a skip (would break
  the force-cuboid quad → existing "<3 corners" raise).
- bound: per-corner `_MAX_PLAUSIBLE_RADIUS_M = 20.0` m — set FROM DATA: legit-room max corner-radius
  p95 = 14.5 m, p99 = 27.9 m on 240 panos. Measured post-guard reject rate ≈ **2.9%** (absurd near-horizon tail
  + thin slice of genuine p95–p99 very-large rooms single-pano st3d cannot reconstruct reliably anyway);
  **0 false-reject on 240 panos**. Raises (not skips); the old `_MIN_FLOOR_TAN` AT-horizon skip path is preserved.
- tests (test_adapter_image.py, all green): `test_near_horizon_corner_rejected`, `test_normal_room_not_falsely_rejected`,
  `test_plausibility_bound_is_a_boundary`, + review-fix adds `test_all_corners_far_still_rejected`
  (all-far → raises on first far corner) and `test_at_horizon_corner_still_skipped` (at-horizon corner silently
  skipped, room builds from remaining 3 → proves new raise did not shadow the old skip).
- behavior change → PATCH 0.25.1→0.25.2 + ADR 0045 §Status-update-2026-06-05c (D89) + RELEASE_NOTES_v0.25.2.md. DONE.

### F2 (DOCS) README per-room honesty correction — DONE
- distinguished per-DIM vs per-ROOM in the accuracy blockquote: per-room median 벽 오차 ≈ **83–95 cm**,
  both-≤15cm 주거 **8%** · 사무 **3%** (per-dim 35–57cm/11–17% is ~2.5× optimistic vs per-room). Noted near-horizon
  auto-reject (≈2.9% of residential samples; >~40 m rooms unsupported in rough tier). Kept "rough pre-scan, not
  install" verdict, noting data is if anything harsher (heavy catastrophic tail). doc-only (+ RELEASE_NOTES line). DONE.
- ORCH: executor(F1 code+tests+measure)→code-review→executor(F2+wrap)→independent verifier→commit.

## RESUME POINTER (2026-06-05)
ROUND 2 (F1 guard + F2 honesty) implemented, reviewed APPROVE-WITH-FIXES, wrapped v0.25.2,
gates GREEN, pending verifier+commit; OQ-60 relative-bound follow-up logged.

Detail: F1 near-horizon plausibility guard (`_MAX_PLAUSIBLE_RADIUS_M=20.0`, data-grounded
p95=14.5/p99=27.9, ≈2.9% reject, 0 false-reject on 240 panos, raises not skips) + F2 README
per-room honesty (per-room median 83–95cm, both-≤15cm 주거 8%/사무 3%) DONE. 3 review LOW fixes
applied: image.py constant comment reworded to honest 2.9% reject framing; +2 tests
(`test_all_corners_far_still_rejected`, `test_at_horizon_corner_still_skipped`). Wrapped at
**v0.25.2** (PATCH, behavior change): `__init__.py` + `pyproject.toml` = 0.25.2,
`__schema_version__` unchanged. Docs: ADR 0045 §Status-update-2026-06-05c (D89 near-horizon guard
+ per-room honesty; NEW OQ-60 relative-outlier-bound follow-up, deferred low-pri), new
`RELEASE_NOTES_v0.25.2.md`, README accuracy blockquote per-dim→per-room correction.
Gates GREEN (default 356p/6s, web 86p/4s, ruff/mypy/tense EXIT0).
PENDING: independent verifier pass + git commit (NOT yet committed).

### prior (v0.25.1, T1/T2) — for history
T1 (provenance→layout.yaml) + T2 (real-model golden test) IMPLEMENTED, code-review APPROVE,
wrapped v0.25.1 (ADR 0046 §Status-update-2026-06-05, D87/D88, RELEASE_NOTES_v0.25.1.md).
