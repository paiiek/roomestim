# Phase 1 — Honest fix for the RT60 predictor finding (dEchorate validation ②)

**Repo:** /home/seung/mmhoa/roomestim @ v0.31.0
**Scope:** READ-ONLY design. No edits made. Decision-ready for the executor lane.

---

## Recommendation: Option E = C (reword disclosure) + narrow A (Eyring guidance)

**No numeric change. No default change. No α retune. PATCH version bump.**

The dEchorate finding exposes a genuine **honesty gap in the disclosure magnitude**
(ISM over-predicts rigid rooms by ~2.0 s, exceeding the shipped `±1.4 s` claim, and the
error is *bidirectional*), but it does **not** justify any numeric change to the shipped
default. It is ONE geometry with deliberately extreme absorption configs, while the existing
defaults are independently calibrated against real typical rooms (ACE) and a real measured
room (SoundCam lab). The honest fix is therefore narrow: correct the *uncertainty statement*,
not the model.

---

## Why this option (rationale + overfitting argument)

### The overfitting risk, stated plainly
dEchorate is ONE cuboid (5.705 × 5.965 × 2.355 m) with 11 *deliberately extreme* absorption
configs (all-foam … all-reflective). The shipped `±1.4 s` disclaimer was ACE-calibrated on
typical, mixed-material, furnished rooms (mean +0.16 s). **Tuning the predictor to fit
dEchorate's extremes would overfit and risk DEGRADING accuracy on the typical rooms roomestim
actually targets.** Widening an *uncertainty* statement (Option C) cannot fabricate accuracy —
it only stops the predictor from *understating* its error, so it carries no overfit risk.
Changing coefficients or capping outputs (D / B) DOES carry overfit risk and is rejected below.

### Why D (retune MELAMINE_FOAM) is rejected — conflicting real-room evidence
- dEchorate says α=0.85 is too high (under-predicts foam-dominated `010000`: 0.106 vs 0.461 s).
- BUT `MELAMINE_FOAM` α=0.85 was *deliberately calibrated* against a real measured room:
  SoundCam lab, where it recovers RT60 within ±20% (predicted band [0.150, 0.175] s vs
  measured 0.158 s) — see `tests/test_a11_soundcam_rt60.py:41-48,80-95,147-182`, ADR 0019.
- Lowering α raises predicted RT60 above the 0.175 s gate and **breaks**
  `test_a11_soundcam_lab_band_record` + `test_a11_soundcam_lab_pass_gate_recovered`.
- Two real rooms disagree on the same coefficient → the honest move is to NOT pick one. The
  disclosure already says materials are the dominant uncertainty.

### Why B (ISM cap / diffuse blend) is rejected — overfit + blast radius
- dEchorate shows Eyring is worst-case-safer (max abs err 0.355 s vs ISM 1.965 s) but
  **biased low on the median** (0.111 vs ISM 0.062 s). Capping ISM toward Eyring trades the
  median accuracy ISM was chosen for (ADR 0030) to bound a worst case seen on ONE extreme
  geometry.
- It would perturb the ISM/Eyring ratio invariants in
  `tests/test_image_source.py:185` (ratio ∈ [0.85, 1.25]) and `:359` (0.5 ≤ ism/sabine ≤ 8.0).
- It would silently change every shipped shoebox number consumed downstream by
  `roomestim_web/binaural.py:565` and `roomestim_web/late_reverb.py`.

### Why C is genuinely warranted (not overfit)
The shipped `±1.4 s` is ACE-derived (`_disclosure.py:6-9`, typical mixed-material rooms) and
is empirically exceeded (≈2.0–2.3 s) for small hard-surfaced / unknown-material rooms. The
disclosure's *thesis* (materials dominate) is confirmed; only its *number* and its
*one-sidedness* need correcting. Widening uncertainty is the honest, zero-risk fix.

### Why the A slice is narrow
Eyring is **already reachable** via `prefer_ism=False` (`predictor.py:475,577`) and that escape
hatch is already tested (`tests/test_predict_rt60_default.py:66`). What is missing is honest
*guidance*: that Eyring is worst-case-safer for strongly-reflective rectilinear rooms but
median-low-biased for typical rooms. We add that note in the docstring only — **no CLI flag,
no third `PredictorName`** (the Literal is test-locked at
`tests/test_predict_rt60_default.py:159-164`; adding a value would be scope creep and break it).

---

## Root cause
The model is not buggy — ISM specular blow-up between near-rigid parallel surfaces is a known
diffuse-vs-specular limitation, already partly disclosed. The actual defect is that the
**honesty disclosure understates and mis-shapes the error**: it implies a one-sided `±1.4 s`
bound, whereas measured ground truth shows the error is (a) bidirectional and (b) can reach the
same order as the RT60 itself in extreme / unknown-material rooms.

---

## EXACT file / function touch-list (smallest correct diffs)

### 1. Reword `RT60_DISCLOSURE` — `roomestim/reconstruct/_disclosure.py:21-29`

This is the single source of truth; the predictor docstring, `RT60Prediction.disclosure`, and
both export sidecars (`gltf.py:242`, `usd.py:317`) reference it by name, so the reword
propagates automatically with no golden-file edits.

**CURRENT (lines 20-29):**
```python
# Concise, honest disclosure. Single source of truth — reference, do not retype.
RT60_DISCLOSURE: str = (
    "RT60 is a geometric-acoustics MODEL estimate (Sabine / Eyring / ISM) that "
    "depends on surface materials. roomestim does not infer materials; when "
    "materials are UNKNOWN or assumed the estimate is indicative only. This is "
    "NOT a validated acoustic measurement and can deviate substantially from "
    "in-situ RT60 (model error observed up to ~+/-1.4 s versus measured, larger "
    "for coupled / non-shoebox spaces). Treat as relative GUIDANCE, not a "
    "guaranteed value."
)
```

**NEW (proposed — preserves every test-checked substring; ADDS the two honest clauses):**
```python
# Concise, honest disclosure. Single source of truth — reference, do not retype.
RT60_DISCLOSURE: str = (
    "RT60 is a geometric-acoustics MODEL estimate (Sabine / Eyring / ISM) that "
    "depends on surface materials. roomestim does not infer materials; when "
    "materials are UNKNOWN or assumed the estimate is indicative only. This is "
    "NOT a validated acoustic measurement and can deviate substantially from "
    "in-situ RT60. The ~+/-1.4 s figure is the typical mixed-material-room "
    "observation (ACE corpus); the error is BIDIRECTIONAL (the ISM default "
    "over-predicts strongly-reflective rectilinear rooms and under-predicts "
    "foam / absorber-dominated rooms), and for small, hard-surfaced or "
    "unknown-material rooms the deviation can reach the same order as the RT60 "
    "itself (observed up to ~2.3 s versus measured), and is larger for coupled "
    "/ non-shoebox spaces. Treat as relative GUIDANCE, not a guaranteed value."
)
```

Substrings that MUST remain for `tests/test_rt60_disclosure.py:54-63` to pass:
`1.4`, `model` (case-insensitive → "MODEL"/"model"), `not a validated acoustic measurement`
(case-insensitive), `guidance` (case-insensitive → "GUIDANCE"). All four are preserved above.

### 2. Add Eyring `prefer_ism=False` guidance — `roomestim/reconstruct/predictor.py`

No code logic change; docstring only. Add a short paragraph to the `predict_rt60_default`
docstring (insert after the existing `prefer_ism` parameter description near line 475) and/or
the module docstring (near line 33). Proposed text:

```
    Predictor-choice guidance (validated against measured RIRs, dEchorate
    CC-BY 4.0, 2026-06-08): for STRONGLY-REFLECTIVE rectilinear rooms the ISM
    default can over-predict (specular long-tail between near-rigid parallel
    surfaces); the diffuse-field Eyring path (``prefer_ism=False``) is
    worst-case-safer there. Eyring is, however, biased LOW on the median for
    typical mixed-material rooms, so it is an informed escape hatch, NOT a
    better default. ISM remains the default per ADR 0030. This guidance is
    based on ONE measured geometry with extreme absorption configs and does
    not generalise to a coefficient or default change.
```

### 3. NEW loose structural test (honest; no external data)

Add to `tests/test_predict_rt60_default.py` (reuses the existing `_low_absorption_shoebox`
helper at line 172). It gates the *phenomenon* the new disclosure warns about — ISM
over-prediction vs Eyring on a near-rigid shoebox — with a LOOSE ordering assert, NOT a
brittle dEchorate exact-match (the 357 MB dEchorate file is gitignored and not reproducible
in CI, so no magnitude golden is committed).

```python
def test_reflective_shoebox_ism_over_predicts_vs_eyring() -> None:
    """dEchorate finding (②): in a near-rigid shoebox the ISM default's specular
    long-tail over-predicts RT60 well above the diffuse-field Eyring estimate.
    This locks the PHENOMENON the widened RT60_DISCLOSURE now warns about, with a
    loose divergence assert (NOT a brittle dEchorate magnitude match)."""
    room, areas = _low_absorption_shoebox()  # all surfaces α≈0.05 (near-rigid)
    pred_ism = predict_rt60_default(room, areas, prefer_ism=True)
    pred_eyr = predict_rt60_default(room, areas, prefer_ism=False)
    assert pred_ism.predictor_name == "image_source"
    assert pred_eyr.predictor_name == "eyring"
    # ISM diverges substantially ABOVE Eyring in the reflective regime.
    assert pred_ism.rt60_s > 1.3 * pred_eyr.rt60_s, (
        f"expected ISM to over-predict vs Eyring in a near-rigid shoebox; "
        f"ISM={pred_ism.rt60_s:.3f}s Eyring={pred_eyr.rt60_s:.3f}s"
    )
```

(Optional, additive) extend `tests/test_rt60_disclosure.py::test_disclosure_constant_is_honest_and_nontrivial`
with `assert "bidirectional" in RT60_DISCLOSURE.lower()` to lock the new honesty clause.

> NOTE on the 1.3× factor: this is a loose lower bound, not a calibrated value. If the executor
> finds the near-rigid α=0.05 shoebox ratio is even larger, keep the assert loose (e.g. >1.3×)
> so it documents the direction without becoming brittle. Verify the actual ratio at
> implementation time and set the threshold comfortably below it.

---

## Gate impact

- **No numeric outputs change** — Option E edits only strings (one constant + docstrings) and
  adds one test. Every numeric/golden assertion stays green:
  - `tests/test_per_band_mae_ex_bl_snapshot.py` — unaffected (uses Sabine/Eyring on ACE directly,
    not the ISM default; ±0.001 s golden untouched).
  - `tests/test_a11_soundcam_rt60.py` — unaffected (no α change).
  - `tests/test_image_source.py` ratio invariants (`:185`, `:359`) — unaffected.
  - `tests/test_predict_rt60_default.py` existing tests — unaffected.
- **Disclosure tests track the reword automatically:**
  - `tests/test_rt60_disclosure.py:54-63` passes as long as `1.4` / `model` /
    `not a validated acoustic measurement` / `guidance` remain (all preserved).
  - `test_gltf_sidecar_carries_disclaimer` / `test_usd_sidecar_matches_gltf_disclaimer` compare
    against `RT60_DISCLOSURE` BY REFERENCE → auto-track the new text, **no golden file edits**.
- **No golden / byte-equal file changes.** No `.acoustics.json` value drift (disclaimer is a
  string field compared by reference).
- **Version bump: PATCH** (e.g. v0.31.0 → v0.31.1). No behaviour / numeric / schema change.
- **NEW test added:** `test_reflective_shoebox_ism_over_predicts_vs_eyring` (default lane,
  deterministic, no external data). Optional one-line extension to the disclosure honesty test.

---

## What must NOT change
- ISM stays the shoebox default (ADR 0030). Do NOT implement B's cap/blend on one extreme dataset.
- Do NOT retune `MELAMINE_FOAM` or any α (D) — conflicts with the SoundCam-lab calibration;
  dEchorate's partial-coverage foam does not generalise.
- Do NOT delete/replace the `1.4` figure — *append* to it; it stays the honest ACE typical-room number.
- Do NOT claim dEchorate validates typical rooms — it is ONE cuboid with extreme configs; the
  reword must say the figure is typical-room and the extreme number is regime-specific.
- Do NOT change `PredictorName` or add a CLI predictor selector.
- Do NOT fabricate accuracy — Option E is an honesty (uncertainty) fix, not an accuracy claim.

---

## STOP note
The honest answer is that **this is predominantly a disclosure/doc change, not a numeric-model
change.** The ISM model behaves as physically expected; the only thing wrong is that the shipped
error bar understates and one-sides the real error. ONE extreme-config geometry is insufficient
evidence to retune coefficients or cap the shipped default — doing so would overfit and risks
degrading the typical rooms roomestim targets. Ship Option E (reword disclosure + Eyring
guidance + one loose structural test), PATCH bump, and **STOP there.** Defer any numeric model
change until a multi-geometry, mixed-material measured-RT60 corpus exists (the same gate already
blocking polygon-ISM RT60 under ADR 0040).

---

## References
- `roomestim/reconstruct/_disclosure.py:21-29` — `RT60_DISCLOSURE` (reword target).
- `roomestim/reconstruct/predictor.py:458,586` — `predict_rt60_default[_per_band]` ISM→Eyring cascade.
- `roomestim/reconstruct/predictor.py:475,577` — `prefer_ism=False` Eyring escape hatch.
- `roomestim/reconstruct/predictor.py:63` — `PredictorName` Literal (test-locked; do not extend).
- `tests/test_rt60_disclosure.py:54-63` — substrings the reword must preserve.
- `tests/test_a11_soundcam_rt60.py:41-48,80-95,147-182` — MELAMINE_FOAM α=0.85 real-room calibration (kills D).
- `tests/test_image_source.py:185,359` — ISM/Eyring ratio invariants (perturbed by B).
- `tests/test_predict_rt60_default.py:66,159-164,172-243` — escape-hatch test, Literal lock, `_low_absorption_shoebox` helper.
- `roomestim_web/report.py:175`, `roomestim_web/binaural.py:565`, `roomestim_web/late_reverb.py` — downstream shoebox-RT60 consumers (B's blast radius; untouched by E).
- `.omc/research/but-reverbdb-rt60-validation.md:131-167` — bidirectional error table + ISM-vs-Eyring worst-case/median tradeoff.
