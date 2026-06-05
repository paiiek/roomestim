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

## RESUME POINTER (2026-06-05)
T1 (provenance→layout.yaml) + T2 (real-model golden test) IMPLEMENTED and independent
code-review = APPROVE. Review-driven polish applied (placement reader import promoted to
module top, `place` subcommand now emits ESTIMATED notice, golden tolerance comment clarified
as cross-machine jitter bound). Wrapped at **v0.25.1** (PATCH): `__init__.py` + `pyproject.toml`
= 0.25.1, `__schema_version__` unchanged. Docs: ADR 0046 §Status-update-2026-06-05 (D87 layout-
boundary propagation, D88 real-model golden), new `RELEASE_NOTES_v0.25.1.md`, README image-backend
paragraph note. Gates GREEN (default 351p/6s, web 86p/4s, ruff/mypy/tense EXIT0).
PENDING: independent verifier pass + git commit (NOT yet committed).
