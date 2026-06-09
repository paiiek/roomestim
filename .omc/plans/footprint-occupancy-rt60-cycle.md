# Autopilot cycle — occupancy footprint ⑥ ship + footprint GT n>1 + concave clean GT + polygon-ISM RT60

Created: 2026-06-09. Baseline: **v0.33.0**, default gate (running; master plan claimed 458p/6skip), origin/main synced.
User directive: "이거 모두 수행하고 싶은데 뭐부터 할까 오토파일럿으로" — do ALL FOUR backlog levers, autopilot decides order.
Mode: full autonomous OMC (planner/architect → executor → code-review → verifier), gates GREEN each phase,
**NO FAKE NUMBERS**, doc-only/검증갭 정직고지, persist resume each phase. Canonical env: `/home/seung/miniforge3/bin/python`.

Predecessor: `.omc/plans/autopilot-predictor-geometry-ambisonics.md` (4-phase, COMPLETE). Its "NEXT" = these 4 levers.

Gate suite (every code phase must stay GREEN — see [[reference_canonical_test_env]]):
- default: `/home/seung/miniforge3/bin/python -m pytest`
- web: marker-scoped web tests
- ruff check + mypy (strict)
- smoke (CLI)

## ORDERING RATIONALE (autopilot decision)
Project discipline = "lay GT before feature; north-star (geometry) before acoustics (a means)".
- occupancy footprint ⑥ already has n=1 validation (Redwood Boardroom recon: convex +22% → occupancy +5%;
  clean laser convex −2% → occupancy −4.5%). So the GT hunt ENRICHES, does not BLOCK, the ship.
- GT-first avoids re-doing ⑥'s validation section; acoustics (④) is lowest per north star → last.

## PHASE SEQUENCE

### Phase A — footprint GT corpus widening (levers 2+3, combined)  ← doc-only research
**(2) n>1 GT**: re-crop Redwood Lobby/Apartment (multi-room → per-room crop) + seek any permissive
modern-LiDAR/RoomPlan single-room laser/CAD GT pair. **(3) concave clean GT**: find a clean (laser-grade)
NON-rectangular room GT to validate concave/occupancy footprint on re-entrant corners (currently 0).
Candidates: ICL-NUIM (CC-BY synthetic, known frame, may have L/non-convex room), Redwood Lobby (open),
re-examine the rejected list for any concave single-room permissive pair.
Output: extend/append `.omc/research/geometry-footprint-gt-dataset-hunt.md` (gitignored). HONEST if empty.
STATUS: ✅ DONE (doc-only, gitignored). n grew **1→2**: added **ICL-NUIM Living Room (CC-BY 3.0)** = FIRST concave
clean GT (synthetic-exact, L-shape +5.5% concavity). **KEY HONEST FINDING**: at ALL defaults the footprint pipeline
FAILS to carve even a mild +5.5% re-entrant corner — released convex +10.1%, released concave +8.8%, WIP occupancy
(min_count=3) +8.6%; only hand-tuned non-default `min_count=5` reaches +0.5% (knife-edge, min_count=8 → −7.7%).
⇒ **occupancy's validated value = FLOATER-REJECTION (Redwood recon +22%→+5%), NOT notch-recovery.** Phase B docs/CLI
NOTE must frame it exactly so (no concave-recovery overclaim). Redwood Apartment/Lobby quota-blocked (transient,
retry ≤24h, IDs cached). critic review pending.

### Phase B — ⑥ ship occupancy/density-aware footprint (north-star CORE)  ← code
Port the VALIDATED occupancy extractor (`/tmp/redwood_hunt/occ.py`: 5cm density grid → count≥k mask →
largest 8-connected component (scipy.ndimage.label) → min-area-rect/polygon) into roomestim as a THIRD
`floor_reconstruction="occupancy"` mode (opt-in; convex stays default). Rationale: convex-hull engulfs
floaters (= dominant end-to-end error source, ~+17% of +22% on Redwood recon); occupancy recovers room
(+22%→+5% recon; clean −2%→−4.5%). Honest framing: robustness lever, validated n=1 (+ whatever Phase A adds),
NOT default. Touch: `FloorReconstruction` Literal, `floor_polygon.py` new extractor (scipy.ndimage), `mesh.py`
_resolve + parse wiring + convex fallback on degeneracy, CLI `--floor-reconstruction` choices, tests, version MINOR.
Full OMC: architect design → executor → code-review → verifier. Gate GREEN. Commit.
STATUS: ✅ DONE — committed **`67f98b5` v0.34.0**. `floor_reconstruction="occupancy"` opt-in 3rd mode
(density 5cm grid → count≥min_count → largest 8-conn comp scipy.ndimage → delegate cell-centers to concave
extractor; convex default byte-equal). Honest framing = FLOATER-REJECTION not notch-recovery (Phase A evidence).
code-review APPROVE (0 CRIT/HIGH/MED; LOW-1 finite-guard + LOW-2 8×2 axis-lock test applied; LOW-3 backlog).
Gate GREEN: default 558p/7s (544+14, 0 regress), web 86p/3s, ruff/mypy clean, smoke 0.34.0, golden byte-equal.

### Phase C — ④ polygon-ISM RT60 cascade (acoustics, LOWEST priority)  ← code
Extend geometry-only `polygon_image_source.py` (v0.31.0 candidate C) into an RT60-relevant acoustic step,
validated against dEchorate measured GT. Empirical guardrail from ②: ISM OVER-predicts rigid rooms
(~2.0s specular blow-up) → need diffuse-field cap/blend; `MELAMINE_FOAM` α likely too high. Honest: if a real
predictor change isn't justifiable without overfitting dEchorate's 1 geometry, ship geometry-only extension +
honest caveat, route any numeric change through separate review. Full OMC cycle. Gate GREEN. Commit.
STATUS: 🔵 DESIGN DONE (`.omc/plans/phaseC-polygon-ism-rt60-design.md`). Decision = **G-only-minimal**: add
config-independent first-order **path-length/TOA helper** to `polygon_image_source.py` (cannot overfit; analytic
in-gate + measured dEchorate out-of-gate backing); predictor UNTOUCHED → all RT60 byte-equal. Found "non-shoebox
Eyring" is ALREADY shipped (predictor routes non-shoebox→Eyring). Option H (predictor numeric change)=DEFER w/
regression guard (SoundCam α=0.85 ratio band + ACE ±1.4s envelope + shoebox byte-equal). Version 0.34→0.35.
STATUS: ✅ DONE (commit pending). `polygon_image_source.py` += `ImagePath` frozen dataclass +
`first_order_path_lengths(images, receiver, *, sound_speed_m_s=None)` = geometry-only first-order path-length/TOA
(image-source identity ‖image−receiver‖); predictor/ISM/Eyring/_disclosure UNTOUCHED → RT60 byte-equal. In-gate
analytic test (independent specular-point P, receiver≠source, ~1e-9) + measured dEchorate backing out-of-gate.
code-review APPROVE (0 HIGH+; reviewer independently cross-checked path-lengths via orthogonal reflection matrix,
max dev 0.0; 3 LOW non-blocking). Gate GREEN: default 562p/7s (558+4, 0 regress), web 86p/3s, ruff/mypy clean, smoke 0.35.0.

## RESUME POINTER
- 2026-06-09: cycle created. Baseline v0.33.0. Order = A (GT) → B (occupancy ⑥ code) → C (RT60 code).
  NEXT ACTION: confirm baseline gate green, then run Phase A data hunt (scientist) → critic → doc-only.
