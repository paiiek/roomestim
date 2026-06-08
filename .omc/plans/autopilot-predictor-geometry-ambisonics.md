# Autopilot run — predictor fix → alpha-shape → geometry data hunt → ambisonics

Created: 2026-06-08. Baseline: v0.31.0, default 433p/3s, origin/main synced (doc commit cc79da9).
User directive: "1,2,3 차례로 실시하고 4도 마지막에. 전체 오토파일럿으로 순차 수행 너가 알아서."
Mode: full autonomous OMC (planner/architect → executor → code-review → verifier), gates GREEN each phase,
NO FAKE NUMBERS, persist resume each phase. Canonical env: `/home/seung/miniforge3/bin/python`.

Gate suite (every phase must stay GREEN — see [[reference_canonical_test_env]]):
- default: `/home/seung/miniforge3/bin/python -m pytest` (baseline 433p/3s)
- web: marker-scoped web tests (~86p/3s)
- ruff check + mypy (strict)
- smoke (CLI)

## PHASE SEQUENCE

### Phase 1 — predictor honesty fix (③ slice; acoustics, now dEchorate-validatable)  ← ACTIVE
Finding from ② (`.omc/research/but-reverbdb-rt60-validation.md`): ISM over-predicts strongly-reflective
rectilinear rooms (011111: 2.49s pred vs 0.525s measured); Eyring diffuse worst-case-safer (max 0.355s);
`MELAMINE_FOAM` α likely too high vs partial-coverage foam.
RISK: dEchorate = 1 geometry, deliberately EXTREME configs. ±1.4s disclaimer was ACE-calibrated (typical
mixed-material rooms). Tuning to dEchorate could overfit and HARM typical rooms.
DESIGN DONE (architect, `/tmp/phase1_predictor_design.md`): **Option E** — reword `RT60_DISCLOSURE`
(`_disclosure.py:21-29`, append BIDIRECTIONAL + ~2.3s extreme-room clause, KEEP "1.4"/"model"/"not a
validated acoustic measurement"/"guidance" substrings) + add Eyring `prefer_ism=False` guidance docstring
in `predictor.py` + 1 loose structural test `test_reflective_shoebox_ism_over_predicts_vs_eyring` (ISM>1.3×Eyring
on near-rigid shoebox) + optional disclosure honesty assert. **NO numeric/default/α change** (B overfits+blast
radius via web consumers & ratio invariants; D breaks SoundCam α=0.85 calibration test_a11). PATCH bump v0.31.1.
STATUS: ✅ DONE — committed `1b7fbca` v0.31.1. Option E shipped (disclosure reword + Eyring guidance docstring
+ loose structural test ISM>1.10×Eyring [measured ratio ~1.18]). Gate GREEN: default 445→446p/6skip, web 86p/3skip,
ruff/mypy clean, CLI 0.31.1; pre-change HEAD 445 confirmed via stash (no regression). code-review APPROVE (0
CRIT/HIGH/MED; LOW-2 "measured"→"computed" applied). NO numeric/default/α change. (Note: real baseline is 445,
memory's "433" was stale.)

### Phase 2 — ⑥ alpha-shape non-convex footprint (ADR 0042; north-star)  ← ACTIVE
convex-hull over-estimate reconfirmed by ①. Implement alpha-shape footprint extraction. Caveat: footprint GT
absent → structural improvement only, NOT a validated accuracy claim. Keep convex-hull as fallback/default-safe.
DESIGN DONE (architect, `.omc/plans/phase2-alphashape-design.md` ← copy from /tmp): ⑥ CORE ALREADY SHIPPED
v0.24.0/D82 (concave `shapely.concave_hull(ratio=0.4)` extractor + opt-in ctor/env + guards + convex fallback +
L-shape test). Only honest residual: (1) CLI flag `--floor-reconstruction {convex,concave}` (reachability PR3),
(2) scan-jitter robustness test (ADR 0042 PR2 noise gate). REJECTED: default-flip (golden drift+no GT), auto-α/
floor_band_m (fake precision, no footprint GT). Ship (1)+(2) as MINOR 0.32.0, framed reachability+robustness NOT
accuracy. footprint accuracy validation stays Phase 3 (data hunt).
STATUS: ✅ DONE — committed `9a7d6c4` v0.32.0. CLI flag `--floor-reconstruction {convex,concave}` (env-precedence
preserved) + jitter robustness test + CLI tests. Gate GREEN: default 446→452p/6skip, web 86p/3skip, ruff/mypy clean,
CLI 0.32.0. code-review APPROVE-WITH-FIXES → HIGH(env silent-override regression, default=None sentinel) + MEDIUM
(test >=6) + LOW(cast hoist) all applied + verified. Core extraction untouched (no golden drift). NOT an accuracy claim.

### Phase 3 — geometry data hunt (unblock ①/⑥ validation)  ← ACTIVE
Find a commercial-OK dataset with KNOWN scan↔GT extrinsic OR single-room laser (no adjacent rooms) to validate
footprint/walls. Risk: may come up empty (like BUT). If empty → document honestly, do not fabricate.
STATUS: ✅ DONE — research note `.omc/research/geometry-footprint-gt-dataset-hunt.md` (gitignored), doc-only.
**QUALIFIED YES (first positive footprint evidence).** Found Redwood Indoor Lidar-RGBD (PUBLIC DOMAIN →
commercial-OK): single-room FARO laser GT + RGB-D recon, trimesh-ingestable. Boardroom (n=1 clean+CONVEX scene):
roomestim convex footprint on clean laser = −2.0% area vs documented 60.90㎡ (externally anchored), wall dims
−2.2/−2.5cm (method-vs-method) → **≤15cm SUPPORTED on clean laser-grade CONVEX room** (easy case for convex hull).
End-to-end on noisy 2017 RGB-D recon = +22% area/+0.7–1.8m walls → ≤15cm NOT met; honest split = ~+5% recon-mesh
drift + ~+17% roomestim's own convex-hull engulfing floaters (→ density/occupancy footprint ⑥ is the validated
mitigation lever, recovers to −4.5%). Rejected (non-commercial/no-GT/paywalled): ScanNet++/Matterport/HM3D/ZInD/
S3DIS/Replica/Hypersim/Structured3D; ICL-NUIM = CC-BY backup (synthetic). SWOT blocker ① PARTIALLY lifted
(clean-convex input has positive evidence; noisy-recon end-to-end fails, cause identified). LIMITS: n=1, convex-only,
no permissive modern-LiDAR/RoomPlan single-room GT pair found, concave-room clean GT still absent.
critic APPROVE-WITH-FIXES (all numbers reproduced exactly·license verified·n=1 data-driven not cherry-picked;
MAJOR-1 causal-inversion + MAJOR-2 trivial-case over-generalization + 3 MINOR → all applied).

### Phase 4 — ⑦ ambisonics layout (ADR 0041; last)
Resolve dead enum + OQ-38 round-trip. Code-only.
DESIGN DONE (architect, `.omc/plans/phase4-ambisonics-design.md`): ship **only PR1** = OQ-38 round-trip via
`x_target_algorithm` extension key (writer emits for non-VBAP; reader restore-first/infer-fallback) so AMBISONICS/
DBAP labels stop silently collapsing to VBAP. Schema needs no change (`additionalProperties:true`). DEFER PR2-4
(actual ambisonics placement producer) — engine-gated (§D-3a, require.md unmet), product-peripheral, fake-completeness
risk. Keep enum member (ADR 0003 forward-compat). Invert the 2 collapse tests + add WFS/backward-compat/fixed-point
tests. Bump MINOR 0.32.0→0.33.0. Golden zero-churn (sole golden is VBAP).
STATUS: ✅ DONE — committed `15e4b8a` v0.33.0. PR1 shipped (x_target_algorithm round-trip; AMBISONICS/DBAP no longer
collapse to VBAP). PR2-4 producer DEFERRED (engine gate §D-3a). Gate GREEN: round-trip 18→19p, default 452→458p/6skip,
web 86p unchanged, ruff/mypy clean, VBAP golden byte-unchanged, v0.33.0. code-review APPROVE (0 CRIT/HIGH/MED; LOW-2
real backward-compat test + LOW-4 DBAP fixed-point applied). OQ-38 CLOSED, D102, ADR 0041 Partially-Accepted.
(Committed before Phase 3 note since fully verified+reviewed and Phase 3 is a long doc-only hunt — persist-progress.)

## RESUME POINTER
- 2026-06-08: master plan created; doc-only backlog committed (cc79da9).
- **ALL 4 PHASES COMPLETE.** Each ran full OMC (architect design → executor → code-review/critic → revision → gate).
  - Phase 1 ✅ `1b7fbca` v0.31.1 — RT60 disclosure honesty (no numeric/default change; overfit-avoided).
  - Phase 2 ✅ `9a7d6c4` v0.32.0 — concave footprint CLI flag + jitter test (core was already shipped D82).
  - Phase 4 ✅ `15e4b8a` v0.33.0 — OQ-38 label round-trip (ambisonics producer DEFERRED, engine-gated).
  - Phase 3 ✅ doc-only — Redwood footprint GT hunt = QUALIFIED YES (first positive footprint evidence, clean-convex
    ≤15cm; noisy-recon end-to-end fails, cause = roomestim convex hull → ⑥). SWOT blocker ① partially lifted.
- Final gate state: default 458p/6skip, web 86p/3skip, ruff/mypy clean, v0.33.0.
- NEXT (post-autopilot, for the backlog): (a) ship the density/occupancy-aware footprint (⑥ extension) — now has a
  VALIDATED lever (Redwood: convex +22% → occupancy +5%, clean-room −4.5%); (b) widen footprint GT to n>1 (re-crop
  Redwood Lobby/Apartment; seek permissive modern-LiDAR/RoomPlan single-room GT pair); (c) clean concave-room laser GT
  for non-shoebox footprint validation; (d) ③ polygon-ISM RT60 now has dEchorate GT (diffuse cap caveat).
- Push cycle to origin/main + run /oh-my-claudecode:cancel to close autopilot.
