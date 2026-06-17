# three-candidate autopilot — 3DSES walls → PyPI publish → ambisonics layout

Created: 2026-06-17 · Baseline: **v0.38.0**, default 611p/7s, web 86p/7s (per [[reference_canonical_test_env]]).
Owner intent (2026-06-17): "1,2,3 모두 차례로 수행 — 저장→커밋→푸시→오토파일럿으로 쭉, 세션 끝나도 계속."
Mode: **autopilot / autonomous execute→verify(full gate)→repeat**. Every non-trivial step routes through
OMC (planner→executor→code-review→verifier or scientist→critic). NO self-approval. **NO FAKE NUMBERS.**

Canonical gate (MANDATORY every code step): `/home/seung/miniforge3/bin/python -m pytest`
- default marker-scoped baseline = 611p/7s · web = 86p/7s · ruff clean · mypy clean.
- doc-only steps: gate must show 0 regression (still 611p/7s).

---

## SEQUENCE (do in order; each = its own OMC cycle + its own commit + push)

### CAND-1 — 3DSES walls/footprint deepening (geometry / north-star)  ← START HERE
- **Goal**: extend the just-shipped 3DSES Gold non-rect footprint validation (`5aa3150`) to
  (a) WALL inner-face position error using label-derived wall points (Gold 7 rooms), and
  (b) footprint breadth across Silver/Bronze tiers if labels permit.
- **Data**: full 7.3GB `3DSES.zip` on disk at `/home/seung/mmhoa/data-gt/3dses/` (gitignored).
  Gold = 7 scans S163/164/165/168/169/178/179, (N,9) float64, two label cols (real + CAD-pseudo).
  Label→class map MUST come from AUTHORITATIVE source (arXiv 2501.17534 / Zenodo readme), not guessed.
- **Honesty constraints (carry from 5aa3150)**: GT is label-derived, NO CAD registration, boundary
  25–47% non-wall-backed (occlusion/doorway) → **number-free or heavily-caveated**; quote a wall
  error number ONLY if a defensible inner-face GT + uncertainty floor can be established, else
  qualitative direction only. If un-verifiable → honest NEGATIVE/UNVALIDATED, no fabrication.
- **Route**: scientist(opus) → independent critic(opus) → apply fixes → verifier. Doc-only unless a
  real reviewable code gain surfaces (then SEPARATE review pass).
- **Output**: append "WALLS (full-pull)" section to `.omc/research/3dses-footprint-wall-validation.md`
  (gitignored) + README honesty touch if warranted + update this plan RESUME.
- **Commit**: `roomestim docs — 3DSES Gold wall inner-face 검증 (...)` doc-only, then push.

### CAND-2 — PyPI publish (ADR 0007)
- **Goal**: take the already-PyPI-ready package (v0.30.0 decouple + v0.37.1 proto-bundling fix) to
  an actually-installable published artifact.
- **Autonomous-safe scope**: clean build (`python -m build`) → `twine check` → **TestPyPI upload**
  (if credentials present) → install-from-TestPyPI smoke (`--backend` + schema resolve) in a fresh venv.
- **GATE (do NOT cross autonomously)**: real `pypi.org` publish is irreversible + namespace-claiming +
  outward-facing → STOP and surface for explicit user go + credentials. Do everything up to that button.
- **Route**: executor for build/verify; verifier confirms install smoke. No README number claims.
- **Output**: build artifacts verified, TestPyPI link (if done), `.omc/research/pypi-publish-dryrun.md`.
- **Commit**: only if repo files change (e.g. packaging metadata/docs); else no-op commit. Push.

### CAND-3 — ambisonics layout (ADR 0041)
- **Goal**: resolve the dead ambisonics enum + OQ-38 round-trip — a real code-only feature.
  Was DEFER'd (gate-unmet/peripheral) but user reopened. Build the layout path + round-trip.
- **Route**: planner(opus) → executor(opus) → code-review → verifier. Full gate GREEN, golden
  round-trip (byte-equal where the schema demands it), version bump per repo convention.
- **Output**: code + tests + ADR 0041 Status-update + README changelog row + new gate baseline.
- **Commit**: `roomestim vX.Y.0 — ambisonics layout (...)` then push.

---

## RESUME POINTER  (update EVERY phase — session may end anytime)

- 2026-06-17 INIT: plan created from AskUserQuestion answer (do 1,2,3 in order, autopilot, survive
  session breaks). Prior commit `5aa3150` (3DSES Gold footprint) pushed. Baseline v0.38.0 611p/7s.
- **CURRENT STEP: CAND-1 not yet started.** Next action = launch scientist(opus) for 3DSES wall
  inner-face validation per CAND-1 above.
- CAND-2: PENDING.
- CAND-3: PENDING.
