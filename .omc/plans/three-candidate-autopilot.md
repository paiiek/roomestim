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
  session breaks). Prior commit `5aa3150` (3DSES Gold footprint) pushed.
  NOTE: actual v0.38.0 full `pytest -q` baseline = **614p/7s** (memory's 611 was v0.37.1; the
  v0.38.0 `--algorithm` commit added +3). web 86p/3s · ruff · mypy clean.
- **CAND-1: ✅ DONE 2026-06-17.** scientist(opus) → independent critic(opus) ACCEPT-WITH-FIXES (repro
  PASS exact, CAD-in-frame non-circular, architecture verified, NO fabricated numbers). 5 fixes applied:
  MED-1 (state real clean-wall criterion: documented gate=7 walls median 8.6cm vs post-hoc ~3 walls 0-3cm),
  MED-2 (z-bullet provenance — script reproduces residuals/over-reads/coverage only), MED-3 (README:163
  "CAD registration 없고"→"label-derived GT 기준이고… CAD 정합 확인했으나 미적용"), LOW-1 (V1 agreement =
  magnitude-only n=3, not sign-level), LOW-2 (45° hardcoded). KEY RESULT: CAD registers to Gold at sub-cm
  (0.4–0.7cm) → defensible wall GT exists, but single-station occlusion + convex bleed → only ~3/24 walls
  cleanly measurable → wall position VALIDATED NARROWLY / UNVALIDATED IN AGGREGATE; NO product README change.
  Gate GREEN 614p/7s · web 86p/3s · ruff · mypy clean (doc-only, 0 regression).
  Tracked diff = README.md (MED-3) + this plan. Research note + nr_wall_repro.py gitignored on-disk.
  Commit: (this commit). → push → CAND-2.
- **CAND-2: ✅ DONE (autonomous portion) 2026-06-17.** executor(sonnet) + independent main-agent re-verify.
  Results (report `.omc/research/pypi-publish-dryrun.md`, gitignored): `python -m build` PASS (wheel 255KB +
  sdist 420KB; only non-fatal SPDX-license deprecation warnings, deadline 2027-02-18). `twine check` PASS
  both artifacts. **proto-bundling fix (v0.37.1) CONFIRMED in artifact**: all 3 schemas
  (`roomestim/proto/room_schema{,.draft,.v0_2.draft}.json`) present in BOTH wheel + sdist; fresh throwaway
  venv (`/tmp`, repo unimportable) install-from-wheel → `import roomestim`=0.38.0, `roomestim --version`=0.38.0,
  `_proto_dir()` resolves to `site-packages/roomestim/proto` (NOT repo) with all 3 schemas loadable. Main
  agent independently re-ran the wheel-content list + fresh-venv smoke → identical PASS.
  **TestPyPI: SKIPPED** — no `~/.pypirc`, no `TWINE_*`/`PYPI_*` env (no credentials).
  **VERDICT: roomestim is INSTALL-GRADE and publish-ready.** Repo change = 0 (artifacts + report gitignored);
  no commit beyond this RESUME update. No code/version touched → CAND-1 gate (614p/7s) still valid.
  **★ USER-GATED REMAINDER:** the actual `pypi.org` publish is irreversible + namespace-claiming +
  outward-facing → REQUIRES user go-ahead + PyPI credentials. NOT done autonomously by design. Non-blocking
  future nit: switch `pyproject.toml` `project.license` to SPDX string before 2027-02-18.
- **CURRENT STEP: CAND-3 (ambisonics layout, ADR 0041) — NOT yet started.** Next action = planner(opus)
  → executor(opus) → code-review → verifier; real code feature (resolve dead enum + OQ-38 round-trip);
  full gate GREEN + golden round-trip + version bump.
