# roomestim — Data-Unblock Validation Cycle (ralplan consensus, 2026-06-09)

DRAFT PLAN v1 (Planner). Baseline: working tree **v0.35.0** (NOTE: backlog said v0.31.0 — stale).
Inputs: cold capability audit (analyst, opus) + GT dataset hunt continuation (general-purpose, opus).
Hard rule: **NO FAKE NUMBERS**. North star = roomestim's own geometry-inference robustness; acoustics low-prio.
OMC: planner → executor → code-review → verifier; validation work is doc-only unless a real regression/feature
warrants code, then route that change through a SEPARATE review pass. RESUME POINTER at bottom.

## Situation (what changed today)
1. **Two blocked data levers are now UNBLOCKED** (reachable + commercial-OK):
   - (A) **3DSES** CC-BY-SA (confirm version 3.0 vs 4.0 on Zenodo at V1 execution — load-bearing for copyleft
     attribution; do NOT assert 4.0 unverified), Zenodo 13323342 — TLS cloud + CAD model in the SAME frame = the known scan↔GT
     extrinsic ARKitScenes lacked → first per-room **wall-position** GT (clean-TLS input caveat).
   - (B) **U. of Rochester RIR** CC-BY 4.0, figshare 48711175 (92.8MB) — 14 rooms, box dims + measured RT60
     → first **multi-room** RT60 error bar across geometric variety.
   - BUT ReverbDB re-verified DEAD (403). U-Rochester supersedes.
2. **Two honesty gaps surfaced in README** (analyst): (a) concave/occupancy footprint modes (v0.34.0) are
   ADVERTISED but recover NO re-entrant corner at any default (ICL-NUIM n=1: convex +10.1%, concave +8.8%,
   occupancy +8.6%; only hand-tuned knife-edge threshold hits +0.5%) — undisclosed capability gap;
   (b) ceiling "±10cm 실증" over-states (n=2-3 clean; one retained scene 31.8cm). Also footprint clean-convex
   Boardroom −2% positive is UNDER-claimed.

## Principles (Planner)
1. Honest validation first: convert the two new datasets into real error bars; never fabricate agreement.
2. Geometry before acoustics (north star). Wall/footprint GT (3DSES) ranks above RT60 (U-Rochester) on
   north-star fit, but RT60 has higher certainty — run both, they're independent.
3. Doc-only by default; code changes only when validation reveals a real, measurable, reviewable gain.
4. Self-consistency of claims: README must match the research (no over- OR under-claim).
5. Bounded, resumable, autonomous (execute→verify full gate→repeat).

## Decision Drivers (top 3)
- **D1 unblock value** — first-ever independent wall-position + multi-room RT60 validation (kills SWOT blockers ①/③ partially).
- **D2 honesty exposure** — the silent concave-mode gap is the sharpest fake-number-adjacent risk for B2B audience; cheap to fix.
- **D3 north-star leverage** — floater-robust default footprint is the one code change where GT now exists, the default is the dominant error source (+17%), and it's pure geometry robustness.

## Viable Options (the cycle shape)
- **Option A (CHOSEN): Honesty-now (H1) → validate → reconcile → improve.** (0) Ship the data-INDEPENDENT
  honesty fix H1 doc-only NOW. (1) Download + validate 3DSES & U-Rochester (doc-only research notes). (2) Update
  README honestly using the new results (H2 ceiling-softening + H3 clean-convex-positive + 3DSES bleed/non-rect
  findings). (3) Ship the floater-robust AUTO-SELECT footprint (C1) — gated on its OWN in-hand criteria (clean
  byte-equal + Boardroom −2% + Redwood +22%→+5% reproduced), NOT on V1 (see Critic Finding 2: 3DSES clean-TLS
  has no floaters → cannot supply floater evidence). V1's contribution to C1 is only validating auto-select on
  through-opening-bleed / non-rect rooms — the failure mode 3DSES CAN show. (4) Drain code-only candidates
  (polygon-ISM→RT60 cascade now testable, ambisonics).
  Pros: claims trail evidence; the one data-independent fix ships immediately; code change gated on in-hand GT,
  not mis-attributed to clean-TLS. Cons: longest path (acceptable).
- **Option B (rejected, but its logic ADOPTED for H1): Honesty-fix everything first.** Rejected for H2/H3
  (those genuinely need the new numbers → would re-edit README twice / risk contradiction). ADOPTED for H1,
  which is data-independent (ICL-NUIM already disproves re-entrant recovery; no 3DSES result can change it) →
  H1 is hoisted to Tier 0a. This is the Architect-endorsed hybrid.
- **Option C (rejected as the WHOLE-cycle opener): Code-improve footprint first.** The footprint code change
  (C1) is real and its floater GT (Redwood/ICL noisy-recon) IS in hand — but opening the cycle with code
  before shipping the live H1 honesty fix and before the V1/V2 honesty-reconciliation inverts the honesty-first
  principle. C1 still runs (Tier 2) on its own in-hand gate; it is NOT delayed FOR 3DSES (Critic Finding 2),
  only sequenced after H1 + the doc-reconciliation. (After amd.6 C1 is convex-preserving auto-select, NOT a new
  default, so the old "n=1-2 default-flip" rejection rationale no longer applies — refreshed per Critic.)

## Prioritized Backlog (the deliverable — execute in this order)
### [Architect amendments 1-8 applied 2026-06-09: H1 promoted to Tier 0a; V1 method/scope fixed; C1 rescoped]

### Tier 0a — Honesty fix that needs NO data — SHIP FIRST, doc-only (Architect amd. 1)
- **H1 · concave/occupancy re-entrant over-claim correction (LIVE exposure, data-independent).** Correct
  README CHANGELOG line 145 ("L자형·notch re-entrant 코너 보존") and `roomestim/adapters/mesh.py:199`
  docstring ("recovers non-shoebox footprint") to state PLAINLY that concave (`ratio=0.4`) and occupancy
  (`min_count=3`) do **NOT** recover re-entrant corners at any SHIPPED default (cite ICL-NUIM: convex +10.1%,
  concave +8.8%, occupancy +8.6%; only hand-tuned knife-edge threshold hits +0.5%). No 3DSES result can change
  this (3DSES = clean-TLS wall/floater axis, not re-entrant carving). Route the docstring touch through the
  doc-review pass. This removes the sharpest fake-number-adjacent B2B exposure immediately.

### Tier 0b — Data validation (doc-only research, the user's core ask) — parallel, after H1 kicks off
- **V1 · 3DSES footprint/WALL validation.** Download Zenodo 13323342 (CAD 320MB + test 220MB first).
  **METHOD (Architect amd. 2 — `MeshAdapter` REJECTS point clouds at `mesh.py:636`; 3DSES is TLS point cloud):**
  choose explicitly and label — (a) mesh the TLS cloud (Poisson/alpha) then `parse`, disclosing the meshing
  param as a confound, OR (b) replicate `_convex_floor_polygon`/occupancy extraction outside the adapter (as
  Redwood did) and label the result "extraction formula on clean TLS — **adapter bypassed**." State which & why.
  **Through-opening bleed (amd. 3):** TLS sees through doorways/windows → bbox crop alone over-reads; clip the
  cropped cloud to CAD wall planes (or occupancy/largest-CC) before footprint, and report convex-hull vs
  occupancy footprint SEPARATELY so see-through bleed is visible, not hidden. Track the `_normalize_to_y_up`
  axis permutation back to CAD axes for per-wall offsets.
  **PER-WALL METRIC — DEFINE EXPLICITLY (Critic Finding 1; undefined ⇒ non-reproducible = soft fake):** per-wall
  offset = median perpendicular distance from the polygon edge segment ASSIGNED to CAD wall *k* to CAD plane *k*
  (correspondence by edge-normal orientation + proximity). **Restrict per-wall offsets to axis-aligned/
  rectangular 3DSES rooms only.** For NON-rectangular rooms the convex hull bridges the notch (fewer edges than
  CAD walls, `gt-dataset-hunt.md:232`) → do NOT fabricate a per-wall figure; report **footprint-area % error +
  a "walls unmeasurable by convex hull: N of M" coverage line** instead.
  **Emit TWO paired rows (amd. 4):** "extraction-on-
  clean-TLS per-wall offset vs CAD (adapter-bypass disclosed)" AND the already-known "real-RGB-D recon near-
  worst-case" reference (Redwood +22%/+0.7-1.8m), so no README line can state a wall number without its real-
  capture counterpart. **First verify the 220MB test subset has ≥3 croppable rooms (amd. 5)** — if not, the
  7.3GB full pull is MANDATORY not optional; state the contingency. Output `.omc/research/3dses-footprint-wall-validation.md`.
- **V2 · U-Rochester RT60 validation.** Download figshare 48711175 (92.8MB). RoomSummary.pdf was ALREADY
  fetched + per-room dims extracted to `/tmp/ur_roomsummary.pdf` (hunt note) — REUSE it, don't re-derive dims;
  only the band-resolution remains open: **confirm whether it exposes octave-band T30 (per-band) or broadband
  T30 only (amd. 7).** Extract measured RT60 (Schroeder/
  ISO 3382) for the ~8-9 rectangular rooms, feed dims to `predict_rt60_default(_per_band)`, produce the first
  **error bar across geometric variety UNDER THE DEFAULT-MATERIAL ASSUMPTION** (NOT predictor accuracy — materials
  confound dominates, dEchorate finding); flag non-shoebox rooms separately. Output `.omc/research/urochester-rt60-validation.md`.
  (V1 ⟂ V2 — run concurrently. Codex unavailable in env → use opus agents for hard parts.)

### Tier 1 — Honesty reconciliation H2/H3 (doc-only, INFORMED by Tier 0b) — after V1/V2
- **H2 · README ceiling softening** — "±10cm 실증" → "few-cm on n=2-3 clean scenes; one 6m-venue scene at 32cm".
- **H3 · README footprint positive** — add Redwood Boardroom −2% clean-convex + the new 3DSES wall numbers,
  BOUND to the real-RGB-D counterpart (amd. 4) so it reads "extraction-on-clean-laser," never "wall accuracy."
  (Bundle H2-H3 into ONE reviewed doc pass; H1 already shipped in Tier 0a.)

### Tier 2 — Floater-robust footprint code improvement (gated on its OWN in-hand GT, NOT on V1) — full review
- **C1 · floater-robust footprint via AUTO-SELECT, convex-preserving (Architect amd. 6 + Critic Finding 2).**
  NOT a new default, NOT a re-entrant-recovery claim. Target the +17% floater-ENGULFING problem (occupancy fixed
  +22%→+5% on noisy recon): auto-select occupancy/density extraction ONLY when a floater/density signal fires;
  otherwise STAY convex → clean-input golden fixtures remain byte-equal by construction. Explicitly state
  occupancy default `min_count=3` FAILS the notch and threshold auto-calibration is a separate, currently-
  nonexistent capability (do NOT assume it).
  **GATE = its OWN in-hand criteria (Critic Finding 2 — 3DSES clean-TLS has NO floaters → cannot supply floater
  evidence; do NOT gate C1 on V1):** clean-input fixtures BYTE-EQUAL + Boardroom −2% not regressed + Redwood
  +22%→+5% floater reduction REPRODUCED (Redwood/ICL noisy-recon GT already on disk). V1's role for C1 is ONLY
  to validate auto-select on through-opening-bleed / non-rect rooms (what 3DSES CAN show), not as the floater gate.
  **C1's code-review MUST confirm it does not silently re-introduce the re-entrant over-claim H1 removed from
  `mesh.py:199` (Critic Minor 2).** Real code change → planner→executor→code-review→verifier; validation script
  must NOT be the gate (independent review).

### Tier 3 — code-only candidates (no data dep, drain as capacity allows)
- **C2 · polygon-ISM → RT60 cascade (ADR 0040)** — now testable (U-Rochester + dEchorate GT). Note empirical
  ISM over-prediction on rigid rooms → use diffuse-field cap/blend. Non-shoebox visibility pruning still
  unexercised (cuboid-only) — 3DSES non-rect rooms could exercise it.
- **C3 · ambisonics layout (⑦)** — peripheral, anytime.

### Deferred (still genuinely blocked — do NOT fake)
- Real RoomPlan parametric ingest (blocker ②) — needs ONE real device export; no path found.
- Material inference (OQ-55) — material/absorption GT = 0 → unverifiable.
- Multi-room RoomCollection (ADR 0047) — large refactor, no fixture; hard product ceiling but not data-gated.
- RGB-D end-to-end footprint (3DSES is clean TLS) — still no permissive RGB-D+laser+extrinsic single-room set.

## Acceptance criteria (testable, Architect-hardened)
- H1 (Tier 0a): README line 145 + `mesh.py:199` docstring no longer claim re-entrant recovery; state the no-
  default-recovers-notch fact with ICL-NUIM numbers; doc-review APPROVE; full gate unchanged (doc/comment only).
- V1: `.omc/research/3dses-*.md` reporting, for ≥3 CAD-cropped rooms, footprint-area % error AND per-wall
  **extraction-on-clean-TLS offset vs CAD** (adapter-bypass-or-meshing disclosed), convex-hull vs occupancy
  footprint shown SEPARATELY (through-opening bleed visible), each number PAIRED with the real-RGB-D worst-case
  reference. Wording = "extraction-on-clean-TLS," never "wall accuracy." No fabricated localization. If 220MB
  subset <3 rooms, full-pull contingency noted.
- V2: `.omc/research/urochester-*.md` with measured-vs-predicted RT60 for ≥8 rect rooms, framed as ERROR BAR
  UNDER DEFAULT-MATERIAL ASSUMPTION (not predictor accuracy), materials confound flagged; per-band only if
  RoomSummary.pdf exposes octave-band T30, else broadband T30.
- H2-H3: README diff a B2B reader cannot fault for over/under-claim; every number traces to a research note;
  clean-laser numbers bound to their real-capture counterpart.
- **ATTRIBUTION/COPYLEFT (Critic Finding 3):** any committed artifact (H3/V2 README lines, C2 ADR) that uses
  3DSES- or U-Rochester-derived numbers MUST cite the dataset by name+license — 3DSES (Zenodo 13323342,
  **CC-BY-SA 4.0**), U-Rochester RIR (figshare 48711175, **CC-BY 4.0**) — and include a one-sentence
  determination that committed artifacts contain ONLY derived factual measurements (not licensable adaptations)
  and that all RAW 3DSES/U-Rochester material stays gitignored (`.omc/research/` only). No raw data committed.
- **BASELINE PIN (Critic Minor 1):** before C1 starts, verifier RECORDS the current v0.35.0 gate counts
  (default / web / ruff / mypy / smoke) in the plan; "no regression vs v0.35.0" is checkable only against the
  pinned number (memory shows drift 433p/3s@v0.31.0 — re-measure, do not assume).
- C1 (if triggered): full gate GREEN (default + web + ruff + mypy + smoke), no regression vs v0.35.0 baseline,
  clean-input fixtures BYTE-EQUAL (auto-select convex-preserving), Boardroom −2% not regressed, NO re-entrant-
  recovery claim, code-review APPROVE, verifier VERIFIED, behavior change documented in README + ADR.
- Throughout: full gate suite re-run each phase; RESUME POINTER updated each phase.

## Risks / pre-mortem
- 3DSES per-room cropping is manual/semi-auto; mis-crop → wrong wall error. Mitigation: crop in the CAD frame
  (registration solved), clip to CAD wall planes for through-opening bleed, sanity-check vs CAD bounds, n≥3.
- TLS through-opening bleed (distinct from mis-crop): scan sees into neighboring rooms via doors/windows →
  convex hull over-reads. Mitigation: plane-clip + report convex vs occupancy footprint separately (V1).
- U-Rochester treatment is qualitative (no α-curves) → materials confound recurs; report as geometric-variety
  error bar under default-material assumption, NOT material/predictor accuracy. Don't over-interpret.
- C1 auto-select could regress clean-input cases; gate on clean byte-equal + Boardroom −2% not degrading + suite.
- **PRE-MORTEM scenario A (Critic): V1 emits a method-dependent, non-reproducible per-wall number** that gets
  folded into README → soft fake. Mitigation: the explicit perpendicular-edge-to-plane metric + rect-only
  restriction + "unmeasurable N/M" reporting for non-rect rooms (V1 method block).
- **PRE-MORTEM scenario B (Critic): C1 ships a floater fix on clean-TLS evidence that cannot show floaters** →
  mis-attributed claim, or a dead gate that never opens. Mitigation: C1 decoupled from V1, gated on in-hand
  Redwood/ICL floater GT; V1 only validates the bleed/non-rect mode.

## CONSENSUS (ralplan) — REACHED 2026-06-09
Planner draft → Architect (8 amendments, all applied) → Critic R1 ITERATE (3 MAJOR + 3 MINOR, all applied) →
Critic R2 ITERATE (1 residual stale label line 179 + license-version note, both applied) → conditional APPROVE
satisfied. Codex unavailable in env (no CLI on PATH) → opus agents used for Architect/Critic per ralplan fallback.

### ADR — Data-Unblock Validation Cycle
- **Decision:** Run honesty-first → validate-on-new-data → reconcile-claims → gated-code-improve → code-only-drain.
- **Drivers:** two GT levers newly unblocked (3DSES wall GT, U-Rochester multi-room RT60); one live data-
  independent honesty exposure (concave re-entrant over-claim); north-star = geometry robustness.
- **Alternatives considered:** B honesty-everything-first (adopted ONLY for data-independent H1); C code-first
  (rejected as cycle opener — inverts honesty-first; C1 still runs in Tier 2 on its own in-hand gate).
- **Why chosen:** claims strictly trail evidence; the one fix that needs no data ships now; the one code change
  is gated on in-hand GT (Redwood/ICL), never mis-attributed to clean-TLS 3DSES.
- **Consequences:** longest path; V1 is clean-TLS extraction (NOT RGB-D end-to-end) — wall numbers must be
  paired with the real-capture worst-case; RT60 is an error-bar-under-default-material, not predictor accuracy.
- **Follow-ups:** RGB-D+laser+extrinsic single-room set still unfound; RoomPlan parametric (blocker ②) + material
  inference (OQ-55) + multi-room RoomCollection (ADR 0047) remain deferred (genuinely blocked / large refactor).

## RESUME POINTER
- [x] ralplan: Architect review DONE (8 amendments applied)
- [x] ralplan: Critic R1+R2 → conditional APPROVE satisfied → CONSENSUS REACHED
- [x] Tier 0a H1 concave over-claim fix — DONE, code-review APPROVE, committed `64f2435` (doc-only, gate 562p/7s)
- [x] Tier 0b V2 U-Rochester RT60 — DONE, `.omc/research/urochester-rt60-validation.md`. FINDING: default-material
      predictor SYSTEMATICALLY over-predicts; Tier-A rect n=7 median +1.35s (+326%), worst +4.6s (combined +8.9s).
      Dataset = treated/absorptive rooms (high-mismatch tail; complements ACE mixed). Band=BROADBAND T30 only.
      → README ±1.4s directionally honest but magnitude 3-6× understated; "RT60 ±20%" spec row contradicted by
      an order of magnitude (observed +160~826%); error is one-sided positive under default materials. FEEDS H3.
- [x] Tier 0b V1 3DSES footprint/wall — DONE, `.omc/research/3dses-footprint-wall-validation.md`. CC-BY-SA 4.0
      confirmed; 3 axis-rect rooms (test subset, no 7.3GB needed); registration residual 1.3-1.9cm; route (b)
      adapter-bypassed. RESULT: clean-TLS+perfect-seg extraction = **3.4cm median wall (convex) / 2.5cm (occ),
      area +1.6-3.8% convex / −2.2+1.8% occ** — PAIRED with real-RGB-D worst-case (Redwood +22% / 0.7-1.8m).
      LOAD-BEARING: occupancy rejects DISCONNECTED floaters but NOT connected through-opening bleed → C1 must
      NOT be advertised as a bleed fix. Non-rect deferred (subset all rect). Cite tight-crop row (loose-crop
      margin-dependent). FEEDS H3 + refines C1 scope.
- [x] Tier 1 H2/H3 README reconciliation — DONE, executor(opus)→code-review APPROVE-WITH-FIXES(2 LOW, LOW-1
      scene-id 구분 반영), committed `1391c80`. gate 562p/7s·ruff·mypy 클린(doc-only). 3DSES 첫 독립 벽수치 +
      U-Rochester RT60 ±20%-spec 수정 + 천장 완화, 양 데이터셋 라이선스 귀속.
- [x] Tier 2 C1 floater-robust auto-select footprint — DONE `2c822b3` v0.37.0 (2026-06-12, cold-review-fix-cycle
      에서 실행: gate=(b) 합성 픽스처 사용자 기결정대로, coarse-grid φ 신호·byte-equal by construction·
      ADR 0048, code-review APPROVE·verifier VERIFIED, 607p/7s)
      ★USER DECISION 2026-06-10: gate = **(b) SYNTHETIC floater fixture** (deterministic·in-repo) + cite
        established Redwood +22%→+5% for design justification. NOT (a) Redwood re-acquire.
      ★BASELINE PIN (recorded pre-C1, miniforge pytest): default **562 passed / 7 skipped**, web **86 passed /
        3 skipped**, ruff+mypy clean. "no regression vs v0.35.0" checks against these.
      ★HOOK SITES: dispatch mesh.py:919-937; FloorReconstruction Literal mesh.py:54; _resolve_floor_reconstruction
        mesh.py:242; extractors floor_polygon.py (floor_polygon_from_mesh / floor_polygon_from_mesh_occupancy).
      ★GATE-DATA NOTE: C1's design gate "Redwood +22%→+5% floater reduction reproduced" — the Redwood noisy-recon
      raw data is NOT currently in /home/seung/mmhoa/data-gt (only 3dses+urochester今日DL). Prior Redwood analysis
      figures survive in .omc/scientist/figures/ (redwood_bedroom_recon_convexhull_floaters.png etc.) and the
      +22%→+5% finding IS established in the research notes. So C1 EITHER (a) re-acquires Redwood data (Drive
      quota — hunt noted retry ≤24h), OR (b) uses a SYNTHETIC floater fixture as the live regression gate +
      cites the established Redwood finding for design justification. Decide (a)/(b) at C1 planning. Scope refined
      by V1: occupancy fixes DISCONNECTED floaters but NOT connected through-opening bleed → C1 = disconnected-
      floater-engulfing fix ONLY; convex-preserving auto-select; clean fixtures byte-equal; NO bleed/re-entrant claim.
- [ ] Tier 3 C2/C3 code-only drain (no data dep): C2 polygon-ISM→RT60 cascade (now testable w/ U-Rochester +
      dEchorate GT; note ISM over-predicts treated rooms → diffuse-field cap/blend), C3 ambisonics layout.
- [ ] Tier 0a H1 concave over-claim correction (doc-only, ship FIRST)
- [ ] Tier 0b V1 (3DSES) + V2 (U-Rochester) download & validate (parallel)
- [ ] Tier 1 H2/H3 README reconciliation (informed by V1/V2)
- [ ] Tier 2 C1 floater-robust auto-select footprint (gated on OWN in-hand Redwood/ICL floater GT, NOT V1)
- [ ] Tier 3 C2/C3 code-only drain
