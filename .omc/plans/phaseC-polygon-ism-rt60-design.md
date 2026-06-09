# Phase C design — polygon-ISM toward an RT60-relevant acoustic step (READ-ONLY architect design)

- **Date**: 2026-06-09
- **Author**: architect (read-only analysis; no production/test/version file edited)
- **Cycle**: roomestim autopilot Phase C (acoustics — LOWEST priority per north star)
- **Scope decision**: extend geometry-only `polygon_image_source.py` toward an RT60-relevant
  step, honestly bounded by what measured dEchorate GT can validate.
- **Canonical Python**: `/home/seung/miniforge3/bin/python -m pytest` (miniforge, per project memory).
- **Baseline**: v0.34.0, default gate 433p/3s @v0.31.0 (per commercialization-analysis.md:274).

---

## RECOMMENDATION (decisive)

**G-only (MINIMAL): add a receiver-relative first-order PATH-LENGTH / TOA geometry helper to
`polygon_image_source.py`, validated by an in-gate analytic cross-check and backed out-of-gate
by the existing dEchorate measurement. Predictor untouched → every shipped RT60 number is
byte-equal. Option H (any predictor numeric change) is DEFER and may only proceed as a SEPARATE
review pass with the regression guard in §7.**

If the team judges the helper too thin to warrant a version bump (it is a small function), the
honest fallback is **DEFER with documentation** (§8) — also an acceptable Phase C outcome. Both
options ship ZERO acoustic magnitude and ZERO RT60 change. The recommendation is G-only-minimal
because there is exactly one increment that is simultaneously (a) not-yet-shipped, (b) genuinely
RT60-relevant, and (c) validatable against real measured data — and it is the path-length/TOA
helper. Everything beyond it is either already shipped, or unvalidatable (fake-number risk).

---

## 1. Decisive code finding — the hypothesised "non-shoebox Eyring" value is ALREADY SHIPPED

The task hypothesised a "genuinely safe, valuable non-shoebox geometry computation (e.g. polygon
volume/surface-area → Eyring for non-shoebox rooms, which the shoebox-only predictor currently
can't do)". **The code shows this already exists.** The shoebox-only constraint lives ONLY on the
*ISM lattice* path, NOT on the volume / surface-area / Eyring path:

- `eyring_rt60(volume_m3, surface_areas)` — `materials.py:146-192` — is **geometry-agnostic**: it
  consumes only a scalar volume and a `dict[MaterialLabel, float]` of per-material area sums.
  Nothing in it assumes a shoebox.
- `room_volume(room)` — `geom/polygon.py:88-108` — computes `shoelace_2d(floor_coords) *
  ceiling_height_m`. `shoelace_2d` (`geom/polygon.py:44-61`) handles **any simple polygon**
  (L-shape, pentagon, concave), not just rectangles.
- `_surface_areas_by_material(room)` — `roomestim_web/report.py:37-59` — sums
  `polygon_area_3d(surf.polygon)` over all `room.surfaces`; works for arbitrary wall geometry.
- `predict_rt60_default` / `_per_band` **already route non-shoebox rooms to Eyring**
  (`predictor.py:587-593` and `:711-717`, rationale `"non-shoebox or prefer_ism=False: Eyring
  fallback"`). `is_rectilinear_shoebox` (`predictor.py:128-145`) is the gate; anything that fails
  it (rotated rectangle, L-shape, n>4) already gets the geometry-correct Eyring estimate.

**Conclusion**: "polygon volume/surface-area → Eyring for non-shoebox" is not a gap — it is the
existing default behaviour. Building it would duplicate shipped code and add zero value. This
removes the most obvious G-only candidate from consideration.

## 2. What dEchorate CAN and CANNOT validate (the honesty boundary)

dEchorate (CC-BY 4.0) is **ONE physically measured CUBOID** (5.705×5.965×2.355 m) × 11
deliberately-extreme absorption configs (`.omc/research/dechorate-polygon-ism-validation.md`,
`but-reverbdb-rt60-validation.md`).

**Validatable (geometry, config-independent):**
- First-order image-source **POSITIONS** — already shipped + validated to ~1e-9 analytically and
  to **median 5.60 cm (3.88 cm excl. the offset "south" panel)** against real measured echo TOAs
  (dechorate note headline table). The validated quantity in that note was *image-source →
  microphone distance* (a receiver-relative path length).
- First-order **PATH LENGTH / TOA** to a receiver — the *exact* quantity the dEchorate script
  computed (`‖image_position − mic‖` and `dist/c` vs measured `T_reflct`). This is real measured
  backing for a path-length helper, at the dataset's ~2.8 cm calibration noise floor.

**NOT validatable with available GT (fake-number risk if shipped as a number):**
- Any **acoustic magnitude on a NON-shoebox room** — RT60, energy decay, absorption. dEchorate is
  a cuboid, so it cannot test non-shoebox acoustics; the existing shoebox ISM already covers
  cuboids. BUT-ReverbDB (the only multi-room measured-RT60 corpus sought) is **HTTP-403 blocked**
  (but-reverbdb note §Blocker) — there is still NO non-shoebox measured RT60 GT.
- **Non-convex visibility pruning** — dEchorate is convex; every `valid` flag is `True`, so the
  off-segment / occlusion path is never exercised (dechorate note "NOT validated").
- **Second-or-higher-order** image positions/TOAs — dEchorate annotations are first-order only
  (dechorate note "NOT validated"). A 2nd-order extension would be analytic-only, unvalidated by
  any measurement.
- **Absorption / material → RT60** on the extreme configs — `but-reverbdb` shows ISM
  over-predicts the all-reflective `011111` config by ~2.0 s (2.49 s vs measured 0.525 s) and
  `MELAMINE_FOAM` α=0.85 over-absorbs partial-coverage foam. Tuning to fix these would overfit
  one geometry (§7).

## 3. The chosen increment (G-only-minimal) — exact build

Add a deterministic, receiver-relative **first-order path-length / TOA** geometry function to
`roomestim/reconstruct/polygon_image_source.py`. For a planar first-order image the broken
source→surface→receiver path length equals the straight-line distance from the **mirrored image
position** to the receiver (image-source identity): `path_len = ‖image.position − receiver‖`;
optional `toa_s = path_len / sound_speed_m_s`. This is geometry only — no absorption, no energy,
no RT60.

**Why this is the right (and only) honest increment:**
- It is the single most RT60-relevant geometric quantity (TOA is the time axis of any
  image-source RIR / energy-decay) yet contains **no acoustic model parameter**, so it is the
  honest "skeleton" the module docstring already says it is building toward
  (`polygon_image_source.py:22-24`).
- It is **config-independent geometry** → structurally **cannot overfit** dEchorate's absorption
  configs (path length is identical for all 11 configs and for any room shape).
- It converts the existing throwaway dEchorate validation script into a permanent,
  regression-locked, tested API capability.
- It closes a real API asymmetry: the module returns a `reflection_point` computed for a receiver
  *co-located with the source* (`polygon_image_source.py:50-51, 275-289`), but offers **no way to
  get the acoustic path length to an arbitrary receiver** — which is precisely the measured
  quantity.

## 4. EXACT file / function touch-list (line-anchored)

**EDIT — `roomestim/reconstruct/polygon_image_source.py` (additive only):**
- After `ImageSource` dataclass (`:95-127`) add a frozen `ImagePath` dataclass: fields
  `image: ImageSource`, `receiver: Point3`, `path_length_m: float`, `toa_s: float | None`.
- After `first_order_image_sources` (ends `:326`) add:
  `first_order_path_lengths(images: Sequence[ImageSource], receiver: Point3, *,
  sound_speed_m_s: float | None = None) -> list[ImagePath]`.
  - Validate `receiver.{x,y,z}` finite (mirror the `:224-233` source-finite guard).
  - If `sound_speed_m_s is not None`: require finite `> 0` (fail loud, same style as
    `:219-223` ceiling-height guard); else `toa_s = None`.
  - `path_length_m = float(np.linalg.norm([image.position.{x,y,z} − receiver.{x,y,z}]))`.
  - Deterministic; preserves input order; emits NO RT60/energy/absorption.
- Extend `__all__` (`:85-89`) with `"ImagePath"`, `"first_order_path_lengths"`.
- Extend the module docstring's "GEOMETRY ONLY" framing (`:1-72`) with one sentence: path
  length / TOA are geometry (metres / seconds), still NO RT60, NO absorption.

**DO NOT TOUCH (byte-equal guarantee):**
- `roomestim/reconstruct/predictor.py` — no cascade change; `PredictorName` unchanged; both
  `predict_rt60_default*` unchanged. Shipped RT60 byte-equal.
- `roomestim/reconstruct/image_source.py` — shoebox ISM lattice unchanged.
- `roomestim/reconstruct/materials.py` — Eyring/Sabine unchanged.
- `roomestim/reconstruct/_disclosure.py` — `POLYGON_ISM_GEOMETRY_NOTE` (`:86-95`) stays accurate
  ("emits NO RT60 and is NOT wired into predict_rt60_default" remains true; path-length/TOA is
  geometry, not RT60). No edit required; the module docstring carries the one added sentence.

## 5. dEchorate-validatable claim vs un-validatable claim (clearly separated)

**Validatable / SHIPPABLE as in-gate truth:**
- (in-gate, analytic) For a shoebox expressed as a 4-corner polygon, `first_order_path_lengths`
  to an arbitrary receiver R equals the analytic broken-path length `‖S−P‖ + ‖P−R‖` for the true
  specular point P (independent of the existing position test at
  `tests/test_polygon_image_source.py:51`), to ~1e-9.
- (out-of-gate, measured) The same path-length math reproduces real dEchorate first-order echo
  TOAs to **median 5.60 cm / 3.88 cm excl. south** (cite the research note; data is 357 MB,
  gitignored — NOT an in-gate fixture).

**Un-validatable / MUST NOT be shipped as a number:**
- Non-shoebox RT60 / energy / absorption (no non-shoebox measured GT; BUT-ReverbDB 403-blocked).
- Non-convex visibility correctness (dEchorate convex-only).
- 2nd+ order image TOAs (dEchorate first-order annotations only).

## 6. How overfitting is avoided

- The shipped quantity (path length / TOA) contains **no absorption coefficient and no acoustic
  model** → it is mathematically invariant across all 11 dEchorate configs and every room shape.
  There is literally no parameter to fit, so overfitting to "one geometry with extreme configs"
  is impossible by construction. This is exactly the property Option H lacks.
- The in-gate gate is an **analytic** identity (image-source mirror = broken-path length), not a
  dEchorate fixture, so the gate does not bind the codebase to one dataset.

## 7. Option H (predictor numeric change) — DEFER, separate review only, with regression guard

If a future cycle pursues a diffuse-field cap/blend on ISM for rigid rooms (the `but-reverbdb`
note's "actionable predictor finding"), it is **out of scope here** and must be a SEPARATE review
pass, because it changes shipped RT60 numbers and is an overfit risk on ONE geometry. Mandatory
regression guard before any such change lands:
- **Byte-equal on shoebox**: every `is_rectilinear_shoebox==True` room's `predict_rt60_default*`
  output unchanged unless the change is explicitly the target (lock via existing
  `tests/test_predict_rt60_default.py` + `tests/test_image_source.py`).
- **SoundCam α=0.85 calibration**: the ISM/Eyring ratio band `[0.85, 1.25]` at
  `tests/test_image_source.py:185-189` (and the lab MELAMINE_FOAM characterisation at
  `:387-391`) must still hold. A cap tuned to drop dEchorate `011111` 2.49 s→0.525 s would very
  likely push this ratio out of band → REGRESSION.
- **ACE envelope**: the ±1.4 s ACE-calibrated disclosure (`_disclosure.py:21-33`) and the e2e
  perf doc must not regress for typical mixed-material rooms (Eyring is biased LOW on the
  `but-reverbdb` median, so a global switch is NOT a free win).
Because a single-geometry tuning cannot clear all three guards without evidence from a real
non-shoebox measured corpus, **Option H stays DEFER** (consistent with ADR 0040 §G + Reverse-
criterion 2 and the prior cycle's RT60-cascade DEFER).

## 8. DEFER fallback (if helper judged too thin)

A documented DEFER is honest and acceptable. Rationale to record: (a) the non-shoebox Eyring path
already exists (§1); (b) no non-shoebox measured RT60 GT exists (§2); (c) the only validatable
new geometry (path length/TOA) is a near-trivial helper; (d) acoustics is north-star LOWEST. In
that case ship nothing in code; append a one-paragraph ADR 0040 §Status-update noting Phase C
re-confirmed RT60 cascade DEFER and recorded the path-length helper as the queued minimal
increment pending demand.

## 9. Test set (in-gate, default lane, numpy-only — no web/torch)

Add to `tests/test_polygon_image_source.py`:
1. `test_shoebox_path_length_matches_analytic_broken_path` — shoebox, arbitrary receiver R ≠
   source; assert each first-order `path_length_m == ‖S−P‖+‖P−R‖` (true specular P, derived
   independently of the stored self-receiver `reflection_point`) to ~1e-9.
2. `test_path_length_toa_units_and_speed_guard` — `toa_s == path_length_m / c`; `c<=0` /
   non-finite raises `ValueError`; `sound_speed_m_s=None` → `toa_s is None`.
3. `test_path_length_non_finite_receiver_raises` — non-finite receiver raises.
4. `test_path_length_deterministic_and_order_preserving` — stable order, repeatable.
(Out-of-gate: keep the existing throwaway dEchorate script as documented empirical backing; do
NOT add the 357 MB dataset to the gate.)

## 10. Version bump + gate impact

- **Version**: 0.34.0 → **0.35.0** (minor; additive public API, zero behaviour change to shipped
  numbers). If DEFER fallback chosen: no bump, doc-only ADR status-update.
- **Gate**: default lane **433 → ~437-439p** (+4-6 tests), **3s unchanged**; numpy/shapely-only →
  runs in default lane, no web-extra. RT60 byte-equal → no acoustic regression. `ruff` + `mypy`
  clean (frozen dataclass + typed helper). web 86p/3s unchanged. Re-run full gate per project
  memory (default + web + ruff + mypy + smoke); new-feature pass alone is NOT GREEN.

## 11. Honesty guardrails (explicit)

- NO RT60, NO absorption, NO energy emitted — path length (m) + optional TOA (s) only.
- First-order only; non-convex visibility still NOT validated; 2nd+ order DEFERRED.
- dEchorate = 1 cuboid → validates geometry/path-length, NOT non-shoebox acoustic magnitude.
- Predictor / ISM / Eyring untouched → shipped RT60 byte-equal; `POLYGON_ISM_GEOMETRY_NOTE`
  stays literally true.
- In-gate gate is analytic (~1e-9); measured dEchorate agreement (5.6 cm) is cited out-of-gate,
  not fixture-locked.
- Route through planner → executor → code-reviewer → verifier (no self-approval), per memory.

---

## Consensus addendum

- **Antithesis (steelman for DEFER over the helper)**: the path-length helper is essentially
  `np.linalg.norm` and does not move the product's frontier (north-star = roomestim spatial-
  inference robustness, acoustics LOWEST). One could argue it manufactures activity in the lowest-
  priority lane and that the honest move is to spend Phase C elsewhere (multi-room RoomCollection
  ADR 0047, or spatial-inference robustness). This is a legitimate call; the helper clears the
  value bar only *barely* (it productises the one measured-validated quantity and closes a real
  API asymmetry).
- **Tradeoff tension**: ADR 0030 Reverse-criterion item 3 wants polygon-ISM *promoted into the
  predictor cascade* — i.e. it pulls toward Option H. North-star + no-fake-numbers + overfit risk
  pull hard toward DEFER. These cannot both be satisfied now; the honest resolution is to satisfy
  the criterion's *geometry foundation* (path length/TOA) while explicitly keeping the *acoustic
  magnitude* (RT60) DEFERRED until a non-shoebox measured corpus exists.
- **Synthesis**: G-only-minimal preserves the strength of both — it advances the polygon-ISM
  skeleton (ADR 0040 §A geometry) with measured backing, while preserving the predictor's
  ACE/SoundCam calibration byte-equal (no Option-H regression). H remains queued behind an
  explicit, evidence-gated regression guard.
- **Principle-violation flags**: none introduced. A path-length helper does NOT violate "no fake
  numbers" (it is measured-validated geometry). Shipping any non-shoebox RT60 number now WOULD
  violate it — hence excluded.

## References
- `roomestim/reconstruct/polygon_image_source.py:1-72, 85-127, 163-326` — geometry-only enumerator;
  insertion points for the new helper.
- `roomestim/reconstruct/materials.py:146-192, 195-236` — Eyring is geometry-agnostic (V + area dict).
- `roomestim/geom/polygon.py:44-61, 88-108` — shoelace/room_volume already non-shoebox capable.
- `roomestim/reconstruct/predictor.py:128-145, 587-593, 711-717` — shoebox gate; non-shoebox
  already routes to Eyring.
- `roomestim/reconstruct/_disclosure.py:21-33, 86-95` — RT60 + polygon-ISM disclosures (stay true).
- `tests/test_polygon_image_source.py:51-99` — existing position test (new path-length test is
  independent).
- `tests/test_image_source.py:185-189, 387-391` — SoundCam α=0.85 ISM/Eyring ratio guard for Option H.
- `.omc/research/dechorate-polygon-ism-validation.md` — measured path-length backing (5.60 cm).
- `.omc/research/but-reverbdb-rt60-validation.md` — ISM over-predicts rigid rooms; BUT 403-blocked.
- `docs/adr/0040-polygon-ism-design.md:189-221` — geometry LANDED, RT60 cascade DEFERRED.
