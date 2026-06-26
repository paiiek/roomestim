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
- 2026-06-27 P0 done. GREEN v0.51.1 built (772p/7s, py.typed in wheel) → code-review next.
- 2026-06-27 P1: GREEN code-review + MoGe planner launched (parallel). [resume here]
