# C2 — polygon-ISM → RT60 cascade (Tier 3, data-unblock cycle)

**Planner:** planner (opus), DIRECT mode (no interview; autonomous autopilot).
**Date:** 2026-06-12. **Baseline:** working tree **v0.37.0**, gate **607p/7s default · 86p/3s web** (`-m web`), ruff+mypy clean.
**Canonical gate:** `/home/seung/miniforge3/bin/python -m pytest` (miniforge — NOT PATH pytest).
**Hard rule:** NO FAKE NUMBERS is absolute. North star = geometry robustness; acoustics is LOWEST priority.
**Truth source for this item:** `.omc/plans/data-unblock-validation-cycle.md` RESUME line 228 (Tier 3 C2).

---

## RECOMMENDATION (decisive — ONE call)

**Ship Option B: honest DEFER-with-evidence. NO predictor numeric change.**

Deliverable = a scientist research note that QUANTITATIVELY evaluates the candidate
diffuse-field cap/blend variants against U-Rochester (n=10 shoebox) + dEchorate (11 configs)
and demonstrates that **no geometry-blind cap clears the bar**, plus an ADR 0040 §Status-update
that reconfirms the RT60 cascade DEFER *now backed by the newly-acquired multi-room measured
corpus* (previously BUT-403-blocked). The predictor, ISM, Eyring, materials, and the
`RT60_DISCLOSURE` string stay **byte-equal**.

This is the correct C2 outcome, not a consolation prize. The three reasons it is decisive:

1. **The literal "polygon-ISM → RT60 cascade" (wiring `polygon_image_source.py` into
   `predict_rt60_default` for non-shoebox rooms) is still un-validatable.** Every measured-RT60
   corpus on disk — U-Rochester, dEchorate, BUT-ReverbDB — is a **shoebox/cuboid**. There is
   STILL no non-shoebox measured RT60 GT. Promoting polygon-ISM into the cascade would emit
   non-shoebox RT60 magnitudes that cannot be checked against anything → fake numbers. DEFER
   stands (ADR 0040 §Status-update 2026-06-08; OQ "non-shoebox measured GT" still open).

2. **The only testable lever — a diffuse-field cap/blend on the SHOEBOX ISM path (phaseC §7
   "Option H") — cannot fix the dominant measured error.** The U-Rochester over-prediction
   (+160~826%, median +326%, one-sided positive) is, per `.omc/research/urochester-rt60-validation.md`,
   **entirely the material gap** (treated/absorptive rooms fed roomestim's default-reverberant
   α=0.05 painted walls), NOT an ISM specular artifact. A geometry-blind diffuse cap runs Eyring
   on the *same wrong default α*; on under-absorbed large rooms Eyring is also high, so the cap
   barely moves the U-Rochester error. The cap only helps the genuine ISM specular-blowup case
   (dEchorate `011111`: ISM 2.49 s vs measured 0.525 s; BUT all-reflective ~2.0 s over) — **n=1–2
   rigid cuboids**. Tuning a shipped cap on n=1–2 single-geometry cuboids = overfit one geometry
   (phaseC §6/§7, ADR 0040 Reverse-criterion 2). The material confound makes any "accuracy" claim
   from a U-Rochester-tuned cap a soft fake number.

3. **The diffuse-field worst-case escape hatch ALREADY SHIPS and is already documented.**
   `predict_rt60_default(room, ..., prefer_ism=False)` already skips ISM and returns the Eyring
   diffuse-field estimate (`predictor.py:498, 587`), and its docstring (`predictor.py:478-485`)
   already carries the dEchorate finding: *"for STRONGLY-REFLECTIVE rectilinear rooms the ISM
   default can over-predict … the diffuse-field Eyring path (`prefer_ism=False`) is worst-case-
   safer there."* A new `diffuse_cap`/blend kwarg would be **redundant** with this for the
   pure-Eyring cap, or an **unvalidated novel blend** (a β-weighted ISM/Eyring) with no basis
   beyond n=1–2 cuboids. The disclosure (`_disclosure.py::RT60_DISCLOSURE`, after A3 `66babfb`)
   *already* states the U-Rochester one-sided +160~826% default-regime bias. There is nothing
   honest left to ship in code.

**Conditional clause (kept so the executor follows evidence, not this prediction):** ship an
opt-in cap ONLY if the §"Decision rule" below is fully met. It is predicted NOT to be met. If by
some measurement it IS met, the cap ships strictly default-OFF + framed as a *worst-case bound*,
never as accuracy. See §"Conditional fallback".

---

## Context / verified facts (do not re-derive)

- **phaseC §3 G-only helper ALREADY SHIPPED** (v0.35.0 `4554e9a`): `first_order_path_lengths` /
  `ImagePath` exist in `roomestim/reconstruct/polygon_image_source.py`. C2 is NOT that. C2 is
  phaseC §7 "Option H" (predictor numeric change), previously DEFER pending a real measured
  multi-room corpus.
- **NEW since phaseC design:** U-Rochester RIR (CC-BY 4.0, figshare 48711175) downloaded +
  validated → `.omc/research/urochester-rt60-validation.md`. Default-material predictor
  systematically over-predicts treated rooms; Tier-A rect n=7 median **+1.35 s (+326%)**,
  one-sided positive, **BROADBAND T30 only**, NO per-material α GT (material confound is real).
  All 14 rooms are BOXES → no non-shoebox GT.
- **dEchorate** (CC-BY 4.0): ONE measured cuboid × 11 absorption configs. ISM over-predicts the
  all-reflective `011111` config by ~2.0 s (2.49 s vs 0.525 s measured); Eyring on the same inputs
  gives 0.33–0.39 s. `.omc/research/dechorate-polygon-ism-validation.md` (geometry, 5.6 cm) +
  `.omc/research/but-reverbdb-rt60-validation.md` (RT60). BUT-ReverbDB itself = HTTP-403 dead.
- **Predictor already enforces a LOWER bound** `ism_rt60 >= eyring_rt60 - 1e-6` (FIX-1/D74 ladder,
  `predictor.py:529-555`, `:651-669`). It never caps ISM *above* Eyring. A diffuse cap is the
  opposite (an UPPER bound) and would invert this near-rigid behaviour.
- **Mandatory regression guards for ANY predictor numeric change (phaseC §7):**
  1. **Byte-equal on shoebox** rooms unless explicitly the target —
     `tests/test_predict_rt60_default.py`, `tests/test_image_source.py`.
  2. **SoundCam α=0.85 ISM/Eyring band [0.85, 1.25]** at `tests/test_image_source.py:185-189`
     + lab MELAMINE_FOAM characterisation `tests/test_image_source.py:387-391`.
  3. **ACE ±1.4 s disclosure envelope** must not regress (`_disclosure.py`).
  - PLUS: `tests/test_predict_rt60_default.py:248-264` LOCKS *"ISM over-predicts above Eyring in a
    near-rigid shoebox"* as the phenomenon the widened disclosure warns about — a **default-ON cap
    toward Eyring breaks this test directly**. (Opt-in/default-OFF leaves it green.)
  - PLUS: `tests/test_rt60_disclosure.py` pins 5 substrings of `RT60_DISCLOSURE`: `"model"`,
    `"not a validated acoustic measurement"`, `"1.4"`, `"guidance"`, `"bidirectional"` (lines
    55-62). Keep `RT60_DISCLOSURE` byte-equal → all 5 pass untouched.

### Data on disk (NOT in-gate fixtures — gitignored scratch)
- U-Rochester: `/home/seung/mmhoa/data-gt/urochester/` (92.8 MB). Room dims PDF cached at
  `/tmp/ur_roomsummary.pdf` (REUSE; do not re-derive dims).
- dEchorate processed RIRs: `/home/seung/mmhoa/data/dechorate_rirs/dechorate_rir_processed.hdf5`
  (357 MB, intact v1.0). Geometry recipe + calibrated `.mat`: `/tmp/dEchorate/recipes/...`
  (**`/tmp` is ephemeral** — if absent, re-clone the dEchorate repo / re-download per the
  reproduce blocks in the two dEchorate research notes; the room dims `[5.705,5.965,2.355]` and
  `c=345.844` are recorded there so a re-pull is for the RIRs only).
- Prior throwaway scripts (`/tmp/dechorate_*_validate.py`) may be gone — `/tmp` is ephemeral;
  re-author from the research-note method sections.

---

## Principles
1. Evidence before code: convert the cap/blend question into a measured error decomposition; never
   ship an acoustic number that can't be checked.
2. Material confound is load-bearing: U-Rochester has NO α GT → any cap tuned on it is fitting the
   material gap, not geometry; it MUST NOT be sold as material-independent accuracy.
3. North star = geometry; acoustics LOWEST. A doc-only honest DEFER is a first-class outcome.
4. Don't duplicate shipped capability: `prefer_ism=False` is already the diffuse worst-case hatch.
5. Bounded, resumable, autonomous (execute → full-gate verify → repeat). RESUME POINTER updated.

## Decision drivers (top 3)
- **D1 — un-validatability:** no non-shoebox measured RT60 GT; cascade promotion emits uncheckable
  magnitudes. Dominant driver toward DEFER.
- **D2 — material confound:** the measured over-prediction is a material-gap artifact a
  geometry-blind cap cannot fix; a U-Rochester-tuned cap is a soft fake number.
- **D3 — redundancy/north-star:** the diffuse hatch already ships; acoustics is lowest priority →
  zero justification for new predictor API surface.

## Viable options (judged)
- **Option A — opt-in diffuse-field cap/blend on ISM, default OFF, validated on U-Rochester +
  dEchorate.** REJECTED as the shipping outcome (kept only as the evidence-gated conditional
  below). Invalidation: (i) the metric it would improve (U-Rochester) is dominated by the material
  gap a cap can't fix; (ii) the case it genuinely fixes (rigid specular blowup) is n=1–2 cuboids =
  overfit one geometry; (iii) it is redundant with `prefer_ism=False`; (iv) cannot clear guard
  `test_predict_rt60_default.py:248-264` if ever made default-ON.
- **Option B — evidence-only DEFER-with-evidence (CHOSEN).** Run the cap-variant evaluation as
  research, ship NO predictor change, update ADR 0040 §Status-update + RESUME + OQs. Honest, gate-
  trivial (byte-equal), NO-FAKE-NUMBERS-correct. Pros: claims trail evidence; converts an assumed
  DEFER into a measured DEFER; zero regression surface. Cons: ships no code (acceptable — it is the
  lowest-priority lane and the honest answer is "don't").
- **Option C — non-shoebox cascade promotion** (`polygon_image_source` → `predict_rt60_default`).
  REJECTED / DEFER: no non-shoebox measured GT; magnitude unverifiable; would emit fake numbers.
  Explicitly reconfirmed in the ADR status-update.

Only Option B survives → invalidation rationale for A and C recorded above (RALPLAN-DR: 1 viable
option, alternatives explicitly invalidated).

---

## Work objectives
1. **Measure**, don't assume, that no geometry-blind diffuse cap/blend clears the bar — produce the
   error decomposition that makes the DEFER evidence-backed.
2. **Reconfirm** the RT60 cascade DEFER in ADR 0040 with the now-available multi-room corpus, and
   record that `prefer_ism=False` already covers the rigid-room worst-case mitigation.
3. **Keep every shipped RT60 number byte-equal** and the full gate green.

## Guardrails
**Must have**
- Predictor / ISM / Eyring / materials behaviour byte-equal; `RT60_DISCLOSURE` byte-equal (5 pins).
- The research note addresses the material confound HEAD-ON: a numeric decomposition of the
  U-Rochester over-prediction into (material-gap component) vs (cap-addressable component), showing
  the cap leaves U-Rochester error essentially unchanged.
- Every committed artifact citing U-Rochester / dEchorate numbers names the dataset + license
  (U-Rochester figshare 48711175 CC-BY 4.0; dEchorate Zenodo 5562386/4626589 CC-BY 4.0). Only
  derived factual measurements committed; raw WAV/HDF5 stays gitignored under `data-gt/` / `data/`.

**Must NOT have**
- NO non-shoebox RT60 magnitude shipped as a number.
- NO cap tuned on U-Rochester sold as accuracy / material-independent.
- NO new predictor kwarg unless the §Decision rule is fully met (predicted: not met).
- NO version bump for the doc-only path.
- NO in-gate dependency on the 92.8 MB / 357 MB datasets (gitignored scratch only).

---

## Task flow (executor — autonomous, full-gate each step)

### Step 1 — Cap/blend evaluation (scientist, out-of-gate research) → the core deliverable
Write `.omc/research/c2-polygon-ism-rt60-cascade-evaluation.md` (gitignored-durable note).
On U-Rochester (n=10 box-feedable rooms; REUSE `/tmp/ur_roomsummary.pdf` dims, REUSE the validated
measured RT60 from `urochester-rt60-validation.md` — do not re-derive) and dEchorate (11 configs;
measured T30 per `but-reverbdb-rt60-validation.md` method), compute, with geometry fed EXACT and
roomestim DEFAULT materials:
- baseline ISM (`predict_rt60_default`), Eyring (`prefer_ism=False`), and candidate caps:
  (a) hard cap `min(ISM, Eyring)`; (b) β-blend `β·ISM + (1−β)·Eyring` for β ∈ {0.25, 0.5, 0.75}.
- For each variant: signed/abs error vs measured, per room + aggregate, U-Rochester vs dEchorate
  separately.
- **Material-confound decomposition (the head-on treatment):** show that on U-Rochester the cap
  variants barely move the error (both ISM and Eyring sit high on under-absorbed default-α rooms),
  i.e. the +326% is a material gap, not a cap-addressable specular artifact; and that the cap's
  only material-confound-FREE benefit is the dEchorate rigid `011111` specular case (n=1).
- **Acceptance:** the note states the DECISION (DEFER) with the numbers behind it; every dataset
  number cited with name+license; explicit "cap is NOT validatable as general accuracy; only
  bounds the n=1–2 rigid-cuboid specular worst-case, which `prefer_ism=False` already exposes."
- Scripts in `/tmp` only; import roomestim read-only; touch NO production/test/version file.

### Step 2 — Apply the §Decision rule
If the rule is **NOT met** (predicted) → proceed to Step 3 (Option B, doc-only).
If the rule **IS met** → go to §"Conditional fallback" instead of Step 3.

### Step 3 — ADR 0040 §Status-update + disclosure cross-ref (doc-only)
- **EDIT** `docs/adr/0040-polygon-ism-design.md`: append a `## Status-update (2026-06-12, C2)`
  block: RT60 cascade reconfirmed DEFER now WITH the multi-room U-Rochester measured corpus
  (previously BUT-403-blocked); record the material-confound decomposition conclusion; record that
  `prefer_ism=False` already provides the rigid-room diffuse worst-case mitigation so no new cap
  API is warranted; cite the new research note + both datasets/licenses. Cross-ref ADR 0030
  Reverse-criterion item 3 (geometry foundation satisfied; acoustic magnitude stays DEFERRED).
- **EDIT (optional, minimal)** `roomestim/reconstruct/_disclosure.py::POLYGON_ISM_GEOMETRY_NOTE`:
  if and only if it sharpens honesty, append ONE clause that a multi-room measured RT60 corpus
  (U-Rochester) now exists and the cascade is STILL DEFERRED (material confound + no non-shoebox
  GT). This is a behavior-inert constant string with NO test pinning its content (only
  `RT60_DISCLOSURE` is pinned). **Do NOT touch `RT60_DISCLOSURE`.** Skip this edit if it adds no
  honesty value — the ADR already records it.
- **EDIT** `.omc/plans/data-unblock-validation-cycle.md` RESUME line 228: mark C2 DONE
  (evidence-only DEFER, commit hash, gate counts).
- **EDIT** `.omc/plans/open-questions.md`: update the non-shoebox-measured-GT OQ + pra-RT60-fit OQ
  with the C2 finding (cascade remains GT-blocked; cap is material-confounded). Append any open
  questions surfaced by the research note.

### Step 4 — Verify + commit
- Full gate: `/home/seung/miniforge3/bin/python -m pytest` (default) + `-m web` + `ruff check` +
  `mypy`. Expect **byte-equal 607p/7s · 86p/3s**, clean. If `POLYGON_ISM_GEOMETRY_NOTE` was edited,
  confirm `tests/test_rt60_disclosure.py` still green (it pins `RT60_DISCLOSURE`, not this note).
- Route through OMC: executor → code-review (doc-review pass; confirm no RT60 number changed, no
  over-claim, licenses cited) → verifier. NO self-approval.
- Commit doc-only (NO version bump — matches H1 `64f2435` doc-only precedent). Message records:
  C2 = evidence-backed DEFER; cap material-confounded; cascade GT-blocked; gate byte-equal.

---

## Conditional fallback (only if §Decision rule met — predicted NOT met)
Ship an **opt-in, default-OFF** worst-case bound, framed as a bound NOT accuracy:
- `predict_rt60_default(..., diffuse_cap: bool = False)` and `_per_band` twin. Default `False` →
  byte-equal. When `True` and `is_rectilinear_shoebox`, return `min(ISM, Eyring)` (or the validated
  β-blend) with `predictor_name` unchanged + rationale noting the cap fired.
- Guards that MUST stay green (default path untouched, so they do): all of phaseC §7 (1)(2)(3) +
  `test_predict_rt60_default.py:248-264` + the 5 disclosure pins. New tests cover ONLY the opt-in
  branch (cap fires / doesn't, default byte-equal, invariant `cap_result <= ISM`).
- Honesty: rationale + docstring + ADR say "worst-case diffuse bound for rigid rectilinear rooms;
  NOT a material-independent accuracy improvement; validated only as a bound on the n=1–2 measured
  rigid cuboids." Disclosure unchanged.
- Version: 0.37.0 → **0.38.0** (minor, additive, default byte-equal). Full review pass.

### Decision rule (all four required to ship the cap; predicted: fails iv, and likely iii)
i.   Default path stays byte-equal (opt-in only). **Achievable.**
ii.  All three phaseC §7 guards + `:248-264` + 5 disclosure pins pass. **Achievable (default-OFF).**
iii. The cap improves a **material-confound-FREE** metric (the dEchorate rigid specular case), not
     merely the U-Rochester material gap. **Marginal — only n=1.**
iv.  The improvement **generalizes beyond n=1–2 cuboids** (needs ≥3 independent measured rigid
     geometries OR any non-shoebox measured RT60 GT). **NOT achievable — no such GT exists.** ← gate.

---

## Test plan (in-gate deterministic only)
- **Primary (Option B):** the test is that NOTHING changed — full default + web gate stays
  **byte-equal green** (607p/7s · 86p/3s); ruff + mypy clean. No new in-gate test required; the
  existing guards (`test_predict_rt60_default.py`, `test_image_source.py:185-189/387-391`,
  `test_rt60_disclosure.py` 5 pins) passing UNCHANGED is the evidence the predictor is untouched.
- **If `POLYGON_ISM_GEOMETRY_NOTE` edited:** confirm no test asserts its substring content (only
  `RT60_DISCLOSURE` is pinned) → gate stays green; optionally add a 1-line presence assertion that
  the note still contains "DEFERRED".
- **Conditional fallback only:** add opt-in-branch tests (default byte-equal; cap fires for rigid
  shoebox; `cap_result <= baseline ISM`; per-band twin). numpy-only, default lane, no web/torch.
- **Out-of-gate:** the cap-variant evaluation runs against the 92.8 MB / 357 MB datasets — NEVER
  added to the gate; throwaway `/tmp` scripts; research note is the durable artifact.

## Version bump policy
- Option B (doc-only / behavior-inert constant): **NO bump** (stay 0.37.0).
- Conditional fallback (opt-in code): 0.37.0 → **0.38.0** minor.

## Gate impact
- Option B: **zero** — byte-equal 607p/7s default, 86p/3s web, ruff+mypy clean.
- Conditional: +~3–5 default-lane tests (opt-in branch), RT60 byte-equal on default path.

## Honesty guardrails (explicit)
- NO non-shoebox RT60 number shipped. NO cap sold as accuracy. Material confound stated numerically.
- `prefer_ism=False` named as the already-shipped diffuse worst-case hatch (no duplicate API).
- `RT60_DISCLOSURE` byte-equal (5 pinned substrings intact). Datasets cited by name + license; raw
  data stays gitignored.
- Route planner → executor → code-review → verifier; no self-approval (project memory mandate).

## Risks / pre-mortem (3)
1. **Executor ships a U-Rochester-tuned cap and reports an "improvement."** → soft fake (material
   gap, not geometry). Mitigation: §Decision rule iii/iv + the mandatory material-confound
   decomposition in Step 1; code-review must reject any cap whose justification is U-Rochester
   error reduction.
2. **`/tmp/dEchorate` is gone (ephemeral) and the executor fabricates dEchorate numbers from
   memory.** → fake. Mitigation: re-pull per the reproduce blocks in the two dEchorate notes; if
   un-re-pullable, the note cites the PRIOR recorded dEchorate figures explicitly AS prior-recorded
   (not re-measured) and proceeds on U-Rochester (on disk) — the DEFER conclusion does not depend
   on a fresh dEchorate run.
3. **A doc-only edit accidentally perturbs `RT60_DISCLOSURE` or an RT60 number** → guard/pin
   failure. Mitigation: full gate each step; byte-equal is the pass condition; verifier confirms.

## Rollback
- Option B: `git revert` the doc-only commit — zero behavioral surface, trivially reversible.
- Conditional: default-OFF means the cap is inert until explicitly enabled; revert removes the
  kwarg; no shipped number ever changed.

---

## ADR (for the executor to fold into ADR 0040 §Status-update)
- **Decision:** C2 = evidence-backed DEFER of the polygon-ISM→RT60 cascade AND of the shoebox
  diffuse-field cap/blend (Option H). No predictor change. Doc-only.
- **Drivers:** D1 no non-shoebox measured RT60 GT (cascade uncheckable); D2 U-Rochester
  over-prediction is a material-gap confound a geometry-blind cap can't fix; D3 `prefer_ism=False`
  already exposes the diffuse worst-case, acoustics is north-star LOWEST.
- **Alternatives considered:** (A) opt-in cap/blend — invalidated: improves only the material-
  confounded metric or the n=1 rigid cuboid; redundant with `prefer_ism=False`; can't generalize
  w/o non-shoebox GT. (C) non-shoebox cascade promotion — invalidated: emits unverifiable
  magnitudes (fake numbers).
- **Why chosen:** claims strictly trail evidence; converts an assumed DEFER into a measured DEFER;
  zero regression surface; respects NO FAKE NUMBERS + north star.
- **Consequences:** RT60 cascade + Option H remain DEFERRED; the only diffuse mitigation stays the
  existing `prefer_ism=False`; a future cap requires ≥3 independent measured rigid geometries OR
  any non-shoebox measured RT60 corpus.
- **Follow-ups (OQ):** non-shoebox measured RT60 GT corpus (still unfound); pra/EDC RT60-fit
  reliability on sparse ISM RIR; per-material α GT (would let U-Rochester test predictor accuracy
  instead of an error-bar-under-default-materials).

---

## RESUME POINTER (C2)
- [x] Step 1 — `.omc/research/c2-polygon-ism-rt60-cascade-evaluation.md`: cap-variant eval on
      U-Rochester (n=10) + dEchorate (11 cfg) + material-confound decomposition; DECISION recorded;
      datasets cited w/ license; `/tmp` scripts only (`/tmp/c2_cap_eval.py`); production/test/version
      untouched. KEY FINDINGS: hard cap min(ISM,Eyring) ≡ shipped prefer_ism=False EXACTLY (ISM≥Eyring
      enforced, max|diff|=0); U-Rochester cap "win" (med abs 2.904→0.090) is a MATERIAL confound that
      sign-FLIPS on dEchorate-known-materials (Eyring 0.131 > ISM 0.100); confound-free benefit = n=1
      rigid 011111 only; no dataset-independent β. (NB: corrects plan's "cap barely moves U-Rochester"
      prediction — reported as measured; DEFER unchanged & strengthened.)
- [x] Step 2 — §Decision rule applied: NOT jointly met (iv FAILS — no non-shoebox / ≥3 rigid measured
      GT; iii marginal n=1; i/ii moot) → Option B doc-only DEFER. Conditional fallback NOT taken.
- [x] Step 3 — ADR 0040 §Status-update (2026-06-12, C2) appended; `POLYGON_ISM_GEOMETRY_NOTE` sharpened
      (one clause; `RT60_DISCLOSURE` byte-equal); data-unblock-validation-cycle.md C2 sub-item marked
      DONE (evidence-only DEFER, hash TBD by parent); open-questions.md OQ-23/B4 + (C) item updated.
- [ ] Step 4 — full gate byte-equal GREEN (607p/7s · 86p/3s · ruff · mypy); code-review (doc) +
      verifier APPROVE; doc-only commit, NO version bump. (executor sanity subset PASS; parent runs
      full gate + review + commit.)
- [ ] (Conditional only, if §Decision rule met) opt-in `diffuse_cap` default-OFF, +tests,
      0.38.0 bump, full review — predicted NOT taken.

**One-line status for parent cycle:** C2 → Option B (evidence-backed DEFER); cascade GT-blocked +
cap material-confounded; doc-only; gate byte-equal.
