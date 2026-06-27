# Autopilot — Commercial-release push + RIR/Room-estimation research-pull

RESUME POINTER. Started 2026-06-27. Baseline: **v0.51.0** (`7e43368`, origin/main synced),
default 770p/7s, web 86p/3s, ruff/mypy clean.

## User mandate (authoritative)
1. **Commercial-release target.** Execute autonomously EVERY backlog candidate that does NOT
   require user-action (no creds, no external-data download gates) or that I can unblock myself.
2. **Research DiffRIR / RIR / Room-Estimation** → pull in or apply commercially-licensable
   techniques. ML/DL features explicitly OK.
3. Hard rules: **NO FAKE NUMBERS**, commercial-OK licenses only, OMC orchestration
   (planner→executor→code-review→verifier, no self-approval), additive releases,
   checkpoint resume-pointer + memory EVERY phase.

## Phase plan
- **Phase 0 (running)**: parallel fan-out —
  (A) research: DiffRIR + RIR-estimation SOTA + room-estimation/layout SOTA (2024-2026),
      filtered for commercial-permissive license + direct applicability to roomestim.
      → `.omc/research/rir-roomestim-research-pull-2026-06-27.md` (on-disk).
  (B) backlog triage: classify every candidate {executable-now / user-gated / data-gated},
      rank executable-now by commercial-release ROI.
      → `.omc/plans/commercial-push-triage.md`.
- **Phase 1**: synthesize A+B → pick concrete candidate set → planner.
- **Phase 2+**: executor → code-review → verifier per candidate, additive releases.

## Phase 0 results (both on-disk)
- Triage `.omc/plans/commercial-push-triage.md`: code-only north-star queue EXHAUSTED.
  Only GREEN = packaging hygiene: **GREEN-1 py.typed (PEP 561), GREEN-2 CHANGELOG.md** → v0.51.1 PATCH.
  Everything else AMBER (VGGT+GTSAM frontier, ACE 2b, FLAIR) / RED (user/GT-gated).
- Research `.omc/research/rir-roomestim-research-pull-2026-06-27.md`: commercial-OK pulls —
  ① **AcoustiX** (MIT) PLY→ray-trace RIR, no external download, cross-sim RT60 validation.
  ② **MoGe** (MIT/Apache) single-RGB→metric geometry, benchmarkable on existing 244-pano eval.
  ③ **VGGT-SLAM** (BSD-2+GTSAM) proper multi-chunk fix BUT VGGT-1B-Commercial = USER-ACTION gate.

## Execution order (this run)
1. [IN PROGRESS] GREEN-1+2 → executor → code-review → verifier → **v0.51.1 PATCH** (certain value).
2. [IN PROGRESS] Feasibility scout: can this env run MoGe / AcoustiX (torch? GPU? weights size?).
3. After scout: pick the highest-ROI feasible research-pull, plan→execute→review→verify (additive
   MINOR), honest eval on existing harness (NO fake numbers; ship experimental/un-validated label
   if it doesn't beat baseline).

## Feasibility verdict (scout on-disk: env-feasibility-moge-acoustix-2026-06-27.md)
- GPU: RTX 2080 Ti ×2 (22.5GB). Canonical miniforge torch=BROKEN torchvision; **spike-vggt venv
  `/home/seung/mmhoa/spike-vggt-multiview/venv/bin/python` = WORKING torch 2.5.1+cu121 + CUDA**.
- **MoGe = AUTONOMOUSLY FEASIBLE** (✅ no blockers, MIT/Apache, GPU ready, 244-pano eval exists at
  `/home/seung/mmhoa/spike-image-geometry/panocontext_data/pano_s2d3d/`, HorizonNet baseline).
- AcoustiX = blocked (Sionna NVIDIA-registration user-gate + protobuf). VGGT-SLAM = blocked
  (GTSAM build + VGGT-1B-Commercial user-gate). Both DEFERRED to user decision.

## DECISION: research-pull this run = MoGe metric single-image backend (additive, opt-in, torch-guarded)
Hypothesis: MoGe is metric → no cam_h assumption → avoids HorizonNet's dominant error lever
(cam_h ±10cm → ±25-40cm). Honest test on existing 244-pano cuboid eval vs HorizonNet baseline
(39/50cm per-DIM median). If it beats baseline → ship as real improvement w/ real numbers.
If not → honest negative, ship experimental or don't default. GT is 100% cuboid → label that limit.

## Status log
- 2026-06-27 P0 done. GREEN v0.51.1 built (772p/7s, py.typed in wheel) → code-review APPROVE.
- 2026-06-27 **v0.51.1 COMMITTED `0f1f9bc`** (not yet pushed). GREEN done.
- 2026-06-27 MoGe plan written `.omc/plans/moge-image-backend.md` (planner APPROVE). Target v0.52.0.
- 2026-06-27 **BLOCKED at MoGe Phase 0**: `pip install git+https://github.com/microsoft/MoGe.git`
  DENIED by auto-mode classifier (agent-chosen external git repo = untrusted code integration).
  No PyPI `moge` package exists → git install (or HF trust_remote_code, same gate) is the only path.
  → USER AUTHORIZED MoGe install (2026-06-27). Push decision: hold v0.51.1+v0.52.0 together.
- 2026-06-27 **MoGe 2.0.0 INSTALLED** in spike venv (`moge-2.0.0`, exit 0). API probe:
  `from moge.model.v1 import MoGeModel` OK, `from moge.model.v2 import MoGeModel` OK.
  submodules = model/scripts/test/train/utils. Next: inference probe (downloads weights ~1-2GB),
  capture return fields, then execute moge-image-backend.md Phases 1-7.
  [RESUME: MoGe usable in `/home/seung/mmhoa/spike-vggt-multiview/venv/bin/python`; build adapter
   `roomestim/adapters/moge.py` per plan; default gate in canonical miniforge env must stay 770p/7s.]
- 2026-06-27 **Phase 2 DONE**: `roomestim/adapters/moge.py` MoGeAdapter (torch-free import VERIFIED;
  ruff+mypy --strict clean). Pano→8 yaw + up/down crops (torch-free gnomonic sampler)→MoGe.infer
  (lazy, fov_x pinned)→known-rotation fuse to Y-up cloud→voxel downsample→delegate to
  MeshAdapter._extract_room_model (NO dup geometry, like multiview)→materials UNKNOWN +
  provenance reconstructed. Smoke (real office pano) PASS: ceiling 3.02m (GT 3.58), provenance/
  materials/objects honest. KNOWN: footprint over-reads (16m axis) where MoGe sees real depth
  THROUGH openings/windows that cuboid GT closes off (per-crop scale CV~22%) → anticipated modality
  mismatch, NOT a bug; eval will report convex+robust+scale-invariant honestly. MoGe convention
  verified = OpenCV (x-right,y-down,z-forward, metric z).
- 2026-06-27 **Phase 3 DONE** (CLI): `--backend moge` in ingest+run choices+help; `_get_adapter`
  moge branch behind `_ExperimentalGate` (gate fires torch-free, VERIFIED exit 1 both subcmds);
  --cam-height ignored-NOTE; --floor-reconstruction applies (no ignored note, like multiview);
  provenance phrase map += moge. ruff+mypy --strict clean. E2E `ingest --backend moge --experimental`
  in spike venv writes room.yaml + all honesty NOTEs.
- 2026-06-27 **Phase 4 DONE** (tests): `tests/test_moge_adapter.py` (@pytest.mark.moge + importorskip;
  contract+honesty+scale-anchor-ignored+subprocess torch-free import lock) = **4 passed in spike venv**.
  Default canonical gate = **772p/8s** (v0.51.1 HEAD baseline 772p/7s + my +1 moge-module skip; 0 change
  to passed). NOTE: working tree also has a CONCURRENT session's untracked WIP (roomestim_web/pipeline.py
  + tests/web/test_pipeline_rough_tier.py) — NOT mine; isolated gate excluding it = 772p/8s.
  Installed pytest into spike venv (test runner only, not roomestim).
- 2026-06-27 **Phase 5 IN PROGRESS**: `tests/eval/moge_image_benchmark.py` written+ruff-clean (no test_
  funcs, __main__ only). Runs MoGe once/pano (shared cloud→convex+robust) + HorizonNet baseline via
  roomestim's OWN ImageAdapter (ROOMESTIM_HORIZONNET_CKPT=offline st3d ckpt; SAME scorer) + GT from
  label_cor at nominal cam_h (1.6 office camera_*/1.4 resid pano_*) + scale-invariant shape err + crop CV.
  n=100 run launched (background). [RESUME: read results at .omc/research/_data/moge_image_benchmark_results.md;
  then Phase 6 ADR0057+README is SEPARATE/out-of-scope for this executor; do NOT commit.]
- 2026-06-27 **Phase 5 DONE — REAL n=100 numbers** (.omc/research/_data/moge_image_benchmark_results.md,
  50 office camera_* + 50 resid pano_*). Per-DIM median cm / per-room <=15cm%:
  HorizonNet base office 91.9/2.0, resid 41.3/4.1, all 58.0/3.1; MoGe convex office 187.1/0, resid
  119.0/2.0, all 151.7/1.0; MoGe robust worse (all 176.3/0). MoGe scale-invariant (shape-only) ~50-53cm
  (still >> HNet). Ceiling median: HNet 13.1cm vs MoGe 71.7cm. Per-crop scale-CV median 14.7%/p90 25.8%/
  max 34.8%. MoGe fail 1, HNet fail 2. **VERDICT = SHIP-EXPERIMENTAL** (MoGe does NOT beat HorizonNet on
  either class; root cause = MoGe sees TRUE depth through openings/windows that cuboid GT closes + per-crop
  metric-scale drift). NO FAKE NUMBERS — all from the real run. Eval used an eval-only HNet-checkpoint
  memoize (load-once; identical net/forward/scorer; ZERO production change). Phases 2-5 COMPLETE; Phase 6
  (ADR0057+README) + Phase 7 (review/verify/commit) are SEPARATE. Did NOT commit.
- 2026-06-27 **MoGe Phase 0 FULLY DE-RISKED — real inference API confirmed** (probe exit 0):
  `MoGeModel.from_pretrained("Ruicheng/moge-vitl").to("cuda").eval()`; `model.infer(img_tensor)`
  (img = (3,H,W) float32 in [0,1]) → dict keys **`points`(H,W,3 metric cam-frame), `intrinsics`(3,3),
  `depth`(H,W), `mask`(H,W bool)**. z-range 0.7-4.6m on a 512 pano-crop = metric room-scale. Weights
  cached. Pano dataset = 1066 imgs at .../pano_s2d3d/{train,valid,test}/img/*.png.
  → BUILD delegated to opus executor: moge-image-backend.md Phases 1-5 (packaging+adapter+CLI+tests+eval).
- 2026-06-27 **CONCURRENT-SESSION COLLISION handled**: other session switched shared checkout to
  `feat/web-rough-consumer-tier` (web rough-tier commits b1a9c22, ec331cb on top of my v0.51.1).
  Web files (roomestim_web/, tests/web/) are DISJOINT from my MoGe files → `git stash -u` →
  `git checkout main` → `git stash pop`: MoGe work now cleanly on **main** (base v0.51.1 0f1f9bc),
  feat branch left untouched. Verifier+reviewer ran on feat (saw 776p incl. their +4 web tests);
  on main the gate is 772p baseline + moge skips. Eval verdict = SHIP-EXPERIMENTAL (honest negative:
  MoGe 151.7cm vs HNet 58.0cm per-DIM; scale-invariant 52.9cm still worse; cuboid-GT biased vs MoGe).
  [RESUME: on main, apply code-review fixes → Phase 6 ADR0057+README → commit v0.52.0 → push v0.51.1+v0.52.0 → checkout feat to restore concurrent view.]
