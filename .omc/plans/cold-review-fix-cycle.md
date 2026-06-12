# roomestim — Cold-Review Fix Cycle (autopilot, 2026-06-11)

Inputs (evidence, all on disk):
- `.omc/research/cold-review-2026-06-11-verification.md` (runtime PASS; packaging DEGRADED)
- `.omc/research/cold-review-2026-06-11-capability-audit.md` (VERDICT REVISE; M1 stale README, M2 VBAP/WFS geometry-decoupling undisclosed, M3 RT60 spec line dishonest inline)
- `.omc/research/cold-review-2026-06-11-competitive-landscape.md` (white-space = scan→RT60→standards-layout; table-stakes = Atmos/RP22-compliant layout output)
- `.omc/research/urochester-rt60-validation.md` (RT60 default-material +160~826%, median +326%)
- `.omc/plans/data-unblock-validation-cycle.md` (C1 Tier 2, user decided gate=(b) synthetic fixture)

Hard rules: NO FAKE NUMBERS · planner→executor→code-review→verifier (no self-approval) ·
behavior-affecting changes get independent review · full gate each phase · atomic per-item commits ·
RESUME POINTER updated each phase.

**BASELINE PIN — RESOLVED & MEASURED (2026-06-12, Critic C-1 closed as REFUTED-with-clarification):**
- default lane: `/home/seung/miniforge3/bin/python -m pytest -q` → **562 passed / 7 skipped**
  (3 fresh raw observations this session). Critic's 464p/4s used a NON-canonical marker filter
  (`-m "not lab and not web and not e2e"`, 101 deselected; 464+4+101=569 — consistent, different lane).
- collection note: `--co -q` lists 567 ids; run executes 569 outcomes (2 runtime-conditional items) —
  README counts must always state the COMMAND alongside the number.
- web lane: `pytest -q -m web` → **86 passed / 3 skipped** (480 deselected; 86+3+480=569 ✓).
  README:438 "86p/4s" is the stale figure — A1 corrects it.
- ruff `All checks passed!` · mypy `Success: no issues found in 49 source files`.

## Work items (execute in order)

### A1 · README refresh (doc-only) — fixes audit M1
- Changelog: add **v0.25.x AND v0.28.0~v0.35.0** rows (Critic Minor-3: table jumps v0.26.0→v0.24.0).
  Source rows from `git log --stat` REAL commit hashes/messages only (Critic Minor-2: no memory
  embellishment; don't copy the `(uncommitted)` placeholder style).
- Test counts (README:437/452): write the **freshly RE-MEASURED** counts + the exact gate command
  (see BASELINE PIN block — do NOT write any unmeasured number).
- Mark web-tier vs core outputs (setup PDF/binaural/BRIR = web-tier; README:198-203).
- Fix README:348 `+329%` → research-note value `+326%` (Critic M-2; trace to urochester note; if 329
  was a different subset, state n per figure instead).
- Acceptance: a reader cannot find a stale version/count; every number traces; no new accuracy claims;
  gate unchanged + `scripts/lint_tense.py` clean (Critic Minor-1).

### A2 · VBAP/WFS room-independence disclosure (doc + docstring; DBAP promotion = design decision)
- README algorithm table (README:211-217): state plainly VBAP & WFS place a fixed ring/line
  **independent of room geometry by construction** (`vbap.py:6`, `dispatch.py:51-52`); DBAP is the
  only geometry-aware algorithm (uses surfaces + listener_area).
- Docstrings: ensure `vbap.py`/`wfs` dispatch docstrings carry the same disclosure (they largely do —
  verify, align wording).
- DBAP-as-default decision: evaluate ONLY as a recommendation note in README ("기하-인지 배치가 목적이면
  `--algorithm dbap`"); do NOT flip the default in this cycle (behavior change, deserves own review +
  user sign-off). Record as deferred decision in this plan.
- Acceptance: README table row per algorithm has a geometry-aware column/note; no default flip.

### A3 · RT60 disclosure code-side regime note (RESCOPED per Critic M-1/M-3) — fixes audit M3 residue
- README doc half **ALREADY SHIPPED in `1391c80`** (L343 inline qualifier + L345-351 footnote with
  +160~826% + dataset/license). Executor: VERIFY-only + wording-align; do NOT re-edit correct text.
- Code (the real new work): extend `_disclosure.py` `RT60_DISCLOSURE` as a **NARROWING of the existing
  bidirectional statement** (Critic M-3): "bidirectional across material regimes; under the default
  UNKNOWN-material regime the product runs, the bias is one-sided positive (+160~826%, U-Rochester)" —
  MUST preserve the five pinned substrings (`tests/test_rt60_disclosure.py:59-64`: "model",
  "not a validated acoustic measurement", "1.4", "guidance", "bidirectional").
- MANDATORY pre-check (not conditional): grep golden fixtures (.gltf/.json/.usd/.yaml) for the literal
  disclosure string before claiming byte-equal; if pinned, update fixtures within the same reviewed commit.
- Acceptance: disclosure carries the default-regime one-sided note; all 5 substring pins still pass;
  numeric outputs byte-equal; gate green.

### A4 · PyPI packaging metadata (small) — amended per Critic M-4
- pyproject: add `license` (MIT — vendored HorizonNet CODE is MIT, `vision/horizonnet/LICENSE` (c) 2019
  Cheng Sun), `readme = "README.md"`, `classifiers`, `[project.urls]`. Add top-level `LICENSE` (MIT,
  holder = repo owner) **with a note that `roomestim/vision/horizonnet/` is governed by its own MIT
  LICENSE (not relicensed) and its NOTICE**.
- **WEIGHTS DISCLOSURE (Critic M-4, commercialization-honesty):** the `[vision]` pretrained weights
  (ZInD/Structured3D) are academic/NON-COMMERCIAL per `vision/horizonnet/NOTICE:15-26` — surface this
  in README + a classifier-adjacent note; pyproject must not imply weights are MIT.
- Smoke (Critic gap): `pip install -e .` regen + import + `python -m build --no-isolation` dry check.
- Acceptance: metadata complete; weights non-commercial terms disclosed; gate unchanged.

### B5 · Geometric layout-angle check (Atmos-style) (NEW feature, medium) — renamed per Critic ambiguity-B
- **NAMING (Critic):** call it "geometric layout-angle check (Atmos-style)", NOT "RP22 compliance" —
  CTA/CEDIA RP22 full text is paywalled; claiming compliance against an uncited standard text is itself
  an over-claim. Each implemented criterion MUST cite its PUBLIC source (Dolby public guidance: height
  30–55°, ideal 45°; public RP22 summaries only if criterion is verifiable from the cited public doc).
- Scope (NO FAKE NUMBERS): pure GEOMETRY — given RoomModel + layout, per-speaker azimuth/elevation from
  the listener point vs cited published ranges. Output = per-speaker pass/fail + "NOT EVALUATED"
  mandatory marking for non-geometric criteria. NOT an acoustic quality claim.
- **Must not imply VBAP/WFS are room-aware (Critic Minor-5):** a pass on a VBAP ring is an angle check
  only — doc note + test against a DBAP fixture too.
- New module `roomestim/place/standards.py` + CLI surface + sidecar note.
- Independent code-review + verifier required (behavior-adding).
- Acceptance: synthetic fixtures assert 30°/55°/45° boundaries; DBAP + VBAP fixtures; docs state
  "geometric angle check only, no acoustic performance claim"; every threshold cites a public source; gate green.

### B6 · Layout quality geometric metrics (small) — exact formulas per Critic ambiguity-A
- Each metric = an EXACT formula, no normative threshold/score (Critic: undefined "uniformity" =
  latent quality claim). Candidates: max adjacent azimuthal gap (deg); std of listener→speaker
  distances (m). REUSE DBAP's existing coverage-ratio prior art (`roomestim/place/dbap.py`) — do not
  invent a parallel.
- Acceptance: deterministic tests assert formula values on synthetic layouts; labeled GEOMETRIC metric,
  no perceptual/quality claim; no "higher = better" language anywhere.

### C1 · OWNERSHIP NOTE (Critic M-5)
- C1 is **owned by `.omc/plans/data-unblock-validation-cycle.md` Tier 2** (USER DECISION + HOOK SITES
  recorded there). This cycle only SEQUENCES it after B6 — execute from that plan, update its RESUME
  POINTER there; do not re-scope here.

### C1 · Floater-robust auto-select footprint (carried from data-unblock cycle Tier 2)
- As per `.omc/plans/data-unblock-validation-cycle.md` C1 block: convex-preserving auto-select,
  gate=(b) synthetic disconnected-floater fixture, clean fixtures byte-equal, NO bleed/re-entrant claim,
  cite Redwood +22%→+5% as design justification only. Own planner→executor→review→verifier.

## Phase gates (every item)
default 562p/7s baseline (+only additive growth) · web 86p/3s · ruff · mypy · smoke ·
`scripts/lint_tense.py` (honesty linter, mandatory for doc edits — Critic Minor-1); code-review
APPROVE; verifier VERIFIED for behavior-affecting items (A3 label, B5, B6, C1).

## RESUME POINTER
- [x] Reports saved to .omc/research/cold-review-2026-06-11-*.md
- [x] Plan written (this file)
- [x] Critic validation — ITERATE(1C/5M/5m) → all findings applied 2026-06-12: C-1 re-measured &
      REFUTED-with-clarification (562p/7s confirmed ×3, critic used non-canonical filter; collection
      567 vs 569 outcomes noted), M-1 A3 rescoped (doc half shipped in 1391c80), M-2 +329→+326 folded
      into A1, M-3 narrowing-not-replacement + 5 substring pins, M-4 weights non-commercial disclosure,
      M-5 C1 ownership → data-unblock plan, minors 1-5 applied → effective APPROVE conditions met
- [x] A1 README refresh — DONE `b6e3b1b` (22 실해시 독립검증, +326/+329 n-주석 research-note 추적,
      code-review APPROVE 2 LOW pre-existing, lint_tense 0, doc-only)
- [x] A2 VBAP/WFS disclosure — DONE `35739d1` (code-review APPROVE, radius=user-input 콜체인 확증,
      docstring/README-only byte-equal, 1 LOW nit 반영)
- [x] A3 RT60 disclosure regime-narrowing — DONE `66babfb` v0.35.1 (5 substring pins 보존, literal
      fixture 핀 0건 확인, full gate 562p/7s·mypy·ruff 클린, code-review APPROVE)
- [x] A4 PyPI metadata + LICENSE — DONE `2ed7f52` v0.35.2 (review 1 HIGH+1 MED 발견·수정: README
      default=st3d 사실 정정 + checkpoints.py '상용은 st3d' 과대권고 제거 + LICENSE per-weight 약관
      분리; 재리뷰 APPROVE; wheel에 vendored LICENSE/NOTICE 동봉 확인)
- [x] B5 geometric layout-angle check — DONE `b965653` v0.36.0 (standards.py 277L + 18 tests,
      code-review APPROVE, verifier PASS: flag-absent byte-identical·NOTE 발화·45°/10° 경계 확증,
      580p/7s·86p/3s·ruff·mypy·lint 클린)
- [x] B6 layout geometric metrics — DONE `9337c05` v0.36.1 (2 metrics 정확공식·무점수, +16 tests,
      code-review APPROVE·verifier PASS, 596p/7s 새 베이스라인)
- [x] C1 floater-robust auto-select footprint — DONE `2c822b3` v0.37.0 (planner→executor→code-review
      APPROVE(H1-regression·byte-equal path·no-raise 3종 확인)→verifier VERIFIED; φ 신호 coarse-grid
      0.25m/θ=1.10, 합성 픽스처 +39.9%→−5.0%, +11 tests, 607p/7s)

## CYCLE COMPLETE 2026-06-12 — 7/7 items shipped (b6e3b1b→2c822b3, v0.35.0→v0.37.0, 562→607 tests)
