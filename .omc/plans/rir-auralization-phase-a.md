# RIR Auralization Phase A — Implementation Plan (ADR 0044)

> **Status**: APPROVED for execution (user autopilot, 2026-05-31). Planner-confirmed.
> **Source of truth (resume)**: this file + `.omc/plans/rir-estimation-roadmap.md` RESUME POINTER.
> **Scope**: web-tier only, 0 new packages, 2 new modules + 1 binaural extension. Core `roomestim/` untouched.
> **Version target**: MINOR bump 0.22.2 → 0.23.0 (new feature surface, additive).
> **Gate**: canonical `/home/seung/miniforge3/bin/python -m pytest`; default + web + ruff + mypy --strict + tense-lint all EXIT0; counts up only.

---

## RESUME POINTER (update every phase)

- **CURRENT STEP**: Step 0 not started — executor begins at Step 1 (rir.py).
- **Blocking gate**: RESOLVED (see §Blocking-Gate Resolutions). All 4 gate items closed by planner+spike.
- **Last GREEN**: v0.22.2 (default 300p/5s, web 68p/4s, ruff/mypy/tense EXIT0), commit `2eae5eb`.
- **Next action**: executor → Step 1.

---

## Blocking-Gate Resolutions (planner decisions + spike evidence)

### Gate 2 — §E spike (OQ-48): RESOLVED → **image-source direct assembly** (compute_rir REJECTED)

Throwaway spike run against installed pra **0.10.1** via canonical python (scripts removed after). Evidence:

1. **`compute_rir()` returns a single 1-D broadband array** per (mic, src) pair (`np.asarray(room.rir[0][0]).ndim == 1`, shape `(7365,)`). There is **no per-band RIR** field anywhere on the room or source object (only `damping` and `images`). → **band-separability is impossible** from `compute_rir()`.
2. **`measure_rt60()` returns one broadband scalar** (`shape (1,1)`, value `0.1253 s`) that is **inconsistent** with the analytic Sabine expectation (`~0.734 s` for the 500 Hz band, α=0.14) — a ~6× underestimate on the sparse specular RIR. This **empirically confirms the ADR 0040:67 flag** that `measure_rt60` on a sparse-ISM RIR is unreliable. RT60-consistency gate is therefore **RED for compute_rir**.
3. Both compute_rir GREEN conditions (RT60 consistency AND band-separability) **FAIL**.

**Decision (OQ-48 CLOSED)**: Use **image-source direct assembly** from `pra_source.images` (arrival times) + `pra_source.damping` (per-band attenuation). This is the ADR's stated 1st path. `compute_rir()` and `measure_rt60()` are **not used** in Phase A. RT60 truth comes exclusively from `predict_rt60_default_per_band` (§C), never from `measure_rt60`.

### Gate 2b — ADR AMBIGUITY FLAG: pra emits **8 bands, not 6**

Spike finding (deviation from ADR §A which implies 6-band damping): when binaural.py builds the room with a 6-band `pra.Material`, `pra_source.damping` has shape **(8, N_images)** with pra octave centers `[125, 250, 500, 1000, 2000, 4000, 8000, 16000]`. pra extends the octave grid from `fs=48000`, appending 8 kHz + 16 kHz beyond roomestim's `OCTAVE_BANDS_HZ = (125,250,500,1000,2000,4000)`. The first 6 rows align exactly with roomestim bands.

**Decision**: `rir.py` slices `damping[0:6]` to recover the 6 roomestim bands, with a runtime guard asserting `damping.shape[0] >= 6` and that the leading 6 pra octave centers equal `OCTAVE_BANDS_HZ` (fail loud, not silent). This is the live justification for the demo's existing `_resolve_damping_scalar` arbitrary-band branch (binaural.py:80-94) — we do NOT reuse that collapse; we slice and keep 6 bands. Document as note in D79.

### Gate 1 — §D binauralization: ACCEPTED for v1

Accept the v1 design as the **shipping synthesis path**:
- **early (pre-`t_mix`)**: per-DOA `nearest_hrir` convolution (reuse existing binaural.py DOA → HRIR logic).
- **late (post-`t_mix`)**: 2-HRIR decorrelation with interaural-coherence target curve `IC(f) = sinc(2*pi*f*d/c)` (d = interaural distance, c = speed of sound). This is a **named design parameter**, not a verified perceptual claim.

**OQ-47 stays OPEN** as verification-deferred: the *perceptual fidelity* of the diffuse-tail binauralization is NOT a blocker for shipping the synthesis path. It is a future evaluation item (tied to OQ-49 metric selection). Phase A ships a *plausible* diffuse tail; perceptual equivalence is explicitly NOT claimed (honesty scope, ADR 0020).

### Gate 3 — §A splice per-band energy-continuity rule (specified)

At the splice point `t_mix`, the late tail's per-band initial envelope amplitude is normalized so that **per-band energy is continuous** across the boundary:

- Compute, for each of the 6 bands `b`, the early RIR's local energy in a short window ending at `t_mix`: `E_early[b] = sum(early_band[b][t_mix - W : t_mix] ** 2)` where `W` is a fixed window (spec: `W = round(0.005 * fs)` = 5 ms, a fixed constant for determinism).
- Set the late tail's band-`b` envelope start amplitude `a0[b]` so the late energy in the first `W` samples equals `E_early[b]`: `a0[b] = sqrt(E_early[b] / E_late_unit[b])` where `E_late_unit[b]` is the energy of the unit-amplitude shaped-noise window for that band.
- Splice is **truncate-and-paste, no crossfade** (DAFx 2025 policy). early RIR truncated at `t_mix`; late tail pasted starting at `t_mix`.
- **Regression test**: per-band boundary discontinuity (10*log10 ratio of mean-square energy in the 5 ms windows immediately before vs after `t_mix`) must be `<= 3 dB` for every band on a representative shoebox.

### Gate 4 — scope confirmation: CONFIRMED

- web-tier only; core `roomestim/` untouched.
- 0 new packages (scipy + numpy only; both already core/web deps).
- 2 new modules: `roomestim_web/rir.py` + `roomestim_web/late_reverb.py`, plus a BRIR function added to `roomestim_web/binaural.py` (additive — existing `render_binaural_demo` and `_resolve_damping_scalar` demo path UNTOUCHED).

---

## Verified Code Anchors (re-confirmed 2026-05-31, post v0.22.2)

ADR line numbers had drifted; actual current locations:

| Symbol | ADR said | ACTUAL |
|---|---|---|
| `image_source_model()` call | binaural.py:292 | **binaural.py:306** |
| `pra_source.images` | :308 | **:322** |
| `pra_source.damping` | :309 | **:323** |
| DOA az/el block | :339-342 | **:358-369** (v0.22.2 D75 rewrote axis logic) |
| `_resolve_damping_scalar` | :80-94 | **:80-94** (unchanged) |
| 2 s tail | :375 | **:402** |
| `predict_rt60_default_per_band` | :525 | **:559** (returns `RT60Prediction.rt60_per_band_s`) |
| `OCTAVE_BANDS_HZ` | model.py:75 | **model.py:75** (unchanged) |
| `room_volume` | polygon.py:66 | **polygon.py:88** |
| `nearest_hrir` | hrtf_io.py:217 | **hrtf_io.py:217** (returns `(hrir_l, hrir_r)`) |

`RT60Prediction.rt60_per_band_s: dict[int, float]` (predictor.py:97) keyed by the 6 `OCTAVE_BANDS_HZ`. `HrtfTable` exposes `hrirs_left`/`hrirs_right` (M×N), `directions` (M×2 az/el), 48 kHz (hrtf_io.py:47-49).

---

## Module-by-Module Spec

### Step 1 — `roomestim_web/rir.py` (early mono-RIR assembly + mixing-time + splice)

Builds a **per-band early mono-RIR** from pra image-source data, computes analytic mixing time, and splices the late tail.

Recommended public API:

```python
def assemble_early_rir_per_band(
    room_pra: Any,            # pra Room AFTER image_source_model()
    listener_pos: np.ndarray, # (3,) pra-frame mic position
    *,
    sample_rate_hz: int = 48000,
    n_bands: int = 6,
) -> np.ndarray:
    """Return (6, L_early) per-band early mono-RIR (amplitude impulse train).
    Iterates pra_source.images (arrival time = dist/c) and pra_source.damping
    (per-band attenuation, sliced [0:6] with a band-grid guard). Gain per image
    = damping[b, i] / max(dist, 0.1) placed at integer sample round(dist/c*fs).
    No HRIR here (mono). Deterministic: pure geometry, no RNG."""

def mixing_time_s(room: "RoomModel") -> float:
    """Analytic Lindau (2012) mixing time: t_mix[s] = 1e-3 * sqrt(V[m^3]).
    V from roomestim.geom.polygon.room_volume(room) (existing core helper)."""

def total_rir_length_samples(rt60_per_band_s: dict[int, float], fs: int) -> int:
    """Total convolvable RIR length = -60 dB reach of the SLOWEST band:
    max(rt60_per_band_s.values()) seconds * fs. Does NOT inherit the demo's
    2 s constant (binaural.py:402)."""

def assemble_mono_rir_per_band(
    room_pra, listener_pos, room, rt60_per_band_s, *,
    sample_rate_hz=48000, seed=0,
) -> np.ndarray:
    """Full per-band mono RIR (6, L_total): early (this module) truncated at
    t_mix, late tail (late_reverb.py) pasted with per-band energy-continuity
    normalization (Gate 3 rule). Returns the 6-band array; recombination to
    broadband is the caller's / BRIR step's job via the power-complementary
    filterbank in late_reverb.py."""
```

**Hook points**: `rir.py` consumes a pra `Room` that has already had `image_source_model()` called — it does NOT rebuild the room. A thin helper may reuse `binaural._build_shoebox_room` / `_build_extrusion_room` + `_to_pra` (import from binaural, do not duplicate), or the BRIR entry point (Step 3) builds the room and passes it in. `room_volume` imported from `roomestim.geom.polygon` (read-only core use, no core change).

**Determinism**: early assembly is pure geometry (no RNG). `seed` is threaded through only to `late_reverb` (Step 2).

Acceptance for Step 1:
- A1. `assemble_early_rir_per_band` returns shape `(6, L)`; first arrival (direct path) sample index equals `round(direct_dist/343*fs)` within ±1.
- A2. Band-grid guard raises `ValueError` if `damping.shape[0] < 6` or leading 6 pra octave centers != `OCTAVE_BANDS_HZ`.
- A3. `mixing_time_s` equals `1e-3*sqrt(room_volume(room))` exactly (analytic, no tolerance).
- A4. `total_rir_length_samples` >= `max(rt60_per_band_s.values()) * fs` (the −60 dB reach of the slowest band).

### Step 2 — `roomestim_web/late_reverb.py` (per-band filtered-noise tail)

Per-band exponentially-decaying shaped Gaussian noise, recombined via a power-complementary octave filterbank.

Recommended public API:

```python
OCTAVE_BANDS_HZ_LOCAL = (125, 250, 500, 1000, 2000, 4000)  # import from roomestim.model

def per_band_decay_envelope(rt60_s: float, n_samples: int, fs: int) -> np.ndarray:
    """Exponential envelope decay(t) = 10 ** (-3 * t / rt60_s) (60 dB def),
    t = arange(n_samples)/fs. Pure deterministic."""

def synthesize_late_tail_per_band(
    rt60_per_band_s: dict[int, float],
    n_samples: int,
    *,
    sample_rate_hz: int = 48000,
    seed: int = 0,
) -> np.ndarray:
    """Return (6, n_samples) per-band late tail. For each band: seeded Gaussian
    noise (np.random.default_rng(seed + band_index) for byte-equal determinism)
    * per_band_decay_envelope(rt60_band). Band-limit each stream with the
    power-complementary octave filterbank so sum-of-bands has flat power across
    band edges (no naive summation). Returns per-band (caller normalizes for
    splice continuity, then recombines)."""

def recombine_bands(per_band: np.ndarray) -> np.ndarray:
    """Power-complementary recombination of (6, N) → (N,) broadband, used after
    splice-continuity normalization."""
```

**Determinism strategy (project-mandated byte-equal)**: use `np.random.default_rng(seed + band_index)` per band (NOT the legacy global `np.random.seed` the demo uses, which is process-global and order-fragile). A fixed `seed=0` default makes two runs byte-identical. The filterbank coefficients are deterministic (computed from fixed band edges). No wall-clock, no unseeded RNG anywhere in the late path.

Acceptance for Step 2:
- A5. `per_band_decay_envelope` at `t = rt60_s` equals `10**-3` (−60 dB) exactly.
- A6. Two calls to `synthesize_late_tail_per_band` with the same args are **byte-equal** (`np.array_equal`).
- A7. Power-complementary recombination: summed-band power spectrum has no >3 dB notch/peak at the 6 band-edge crossover frequencies (filterbank correctness).
- A8. All 6 bands present and distinct (no 500 Hz scalar collapse) — `per_band.shape[0] == 6` and bands are not all-equal.

### Step 3 — BRIR binauralization in `roomestim_web/binaural.py` (additive)

Add a NEW function (do NOT touch `render_binaural_demo` or `_resolve_damping_scalar`):

```python
def synthesize_brir(
    room: "RoomModel",
    listener_pos_world: "Point2 | tuple",   # or reuse listener_area centroid
    *,
    hrtf: "HrtfTable | None" = None,
    rt60_per_band_s: dict[int, float] | None = None,  # if None, compute via predict_rt60_default_per_band
    max_order: int = 10,
    sample_rate_hz: int = 48000,
    interaural_distance_m: float = 0.18,
    seed: int = 0,
) -> np.ndarray:
    """Return a 2-channel convolvable BRIR, shape (2, L_total).
    - Build room (reuse _build_shoebox_room / _build_extrusion_room + _to_pra).
    - image_source_model() → assemble_mono_rir_per_band (rir.py).
    - EARLY (pre t_mix): per-image DOA → nearest_hrir → per-band-weighted
      convolution into L/R (reuse the existing DOA az/el block logic at
      binaural.py:358-369; factor the math into a small shared helper rather
      than copy-paste, but DO NOT alter the demo call site).
    - LATE (post t_mix): recombine bands → mono diffuse tail; binauralize via
      2-HRIR decorrelation targeting IC(f)=sinc(2*pi*f*d/c) (Gate 1). No DOA.
    - Splice L and R channels at t_mix with the per-band energy-continuity
      normalization (Gate 3)."""
```

**Why §D lives in binaural.py**: it needs `nearest_hrir`, `HrtfTable`, and the DOA geometry that already live there. Keeping it in binaural.py avoids a circular import (`rir.py` would otherwise need HRTF). `rir.py`/`late_reverb.py` stay HRTF-free (mono); `binaural.synthesize_brir` is the only place HRIR meets the RIR.

Acceptance for Step 3:
- A9. `synthesize_brir` returns shape `(2, L)` and is convolvable: `scipy.signal.fftconvolve(mono_signal, brir[0])` runs without error and returns finite output.
- A10. Determinism: two `synthesize_brir` calls with identical args are byte-equal.
- A11. RT60-consistency invariant: the broadband decay of the late tail, fit over the post-`t_mix` region, matches `max(rt60_per_band_s)` within ±10% (tail decay traceable to the single RT60 truth source, §C). (Use a simple EDC/linear-fit on log-energy; tolerance loose because it is a sanity invariant, not a perceptual claim.)
- A12. Splice per-band continuity <= 3 dB at `t_mix` (Gate 3 regression test).

### Step 4 — Tests (`roomestim_web/tests/` or repo test dir, web-marked)

Concrete, load-bearing acceptance tests (must FAIL without the implementation). Place under the existing web test marker so they run in the `web` gate, not core. Consolidate A1–A12 above into a test module `test_rir_auralization.py`. Each test must use a fixed small shoebox fixture + the default HRTF (or a tiny synthetic HrtfTable) for speed.

Mandatory invariants (restated as the load-bearing list):
1. **RT60-consistency** (A11): tail decay matches `rt60_per_band_s` within tolerance.
2. **Splice per-band continuity** (A12, Gate 3): <= 3 dB at `t_mix` for all 6 bands.
3. **Total length** (A4): >= `max(RT60_band)` −60 dB time; demo 2 s NOT inherited.
4. **BRIR convolvable** (A9): 2-channel, fftconvolve-able, finite.
5. **Determinism** (A6, A10): two runs byte-equal.
6. **6 bands preserved** (A8): no 500 Hz scalar collapse; shape[0]==6, distinct.
7. **Band-grid guard** (A2): raises on <6 bands / mismatched centers.
8. **Filterbank power-complementary** (A7): no >3 dB crossover artifact.
9. **Core-tier gate untouched**: a meta-check that `roomestim/` imports unchanged (no new core dep) — verified by the full default gate staying GREEN.

### Step 5 — Docs + version bump (additive, after GREEN)

- **ADR 0044 Status update**: append a `§Status-update-v0.23.0` section moving Proposed → **Accepted/Implemented**. Record: OQ-48 CLOSED (image-source direct assembly, compute_rir rejected with spike evidence: broadband-only + measure_rt60 6× error); the 8-band-vs-6-band finding + `[0:6]` slice decision; Gate 1/3/4 resolutions. Do NOT rewrite the Proposed body — append, per ADR 0030 §Status-update split convention (D73).
- **decisions.md**: add **D79** — "RIR auralization Phase A 구현 (rir.py + late_reverb.py + synthesize_brir; image-source 직접조립, compute_rir 기각[§E spike]; per-band energy-continuity splice; 6-band 유지[damping[0:6] slice, pra 8-band 그리드]; v0.23.0 MINOR)". Include the spike evidence and the 8-band ambiguity flag.
- **open-questions.md**: 
  - **OQ-48** → CLOSED (D79) with spike evidence.
  - **OQ-47** → status-update: synthesis path SHIPPED; perceptual fidelity verification-deferred (tie to OQ-49). Still OPEN.
  - **OQ-49** → status-note: still open (metric selection prerequisite for OQ-47 verification).
  - **OQ-51** → status-note: `√V` mixing time used as v1; non-shoebox/coupled-space adequacy still open.
- **README**: add the auralization/BRIR capability under the web feature list; version line 0.23.0.
- **pyproject.toml**: `version = "0.23.0"`.
- **roadmap RESUME POINTER**: mark Phase 3 (구현) DONE, Phase A shipped.

---

## Task Flow (ordered)

1. Step 1 — `rir.py` (early assembly + mixing time + splice scaffold). Run web gate.
2. Step 2 — `late_reverb.py` (filtered-noise tail + filterbank + determinism). Run web gate.
3. Step 3 — `binaural.synthesize_brir` (BRIR, §D binauralization). Run web gate.
4. Step 4 — tests (A1–A12). Full gate (default + web + ruff + mypy --strict + tense-lint), EXIT0, counts up only.
5. Step 5 — docs (ADR §Status, D79, OQ updates, README) + version bump. tense-lint EXIT0.
6. code-reviewer → verifier (full gate) → GREEN. Commit per user request (autopilot).

After each step: re-run the FULL gate (memory: new-feature pass alone is NOT GREEN), update RESUME POINTER.

## Guardrails

**Must have**: 6 bands preserved end-to-end; single RT60 truth source (`predict_rt60_default_per_band`); byte-equal determinism (`default_rng(seed+band)`); web-tier isolation; per-band energy-continuity splice; total length from `max(RT60_band)`; 2-channel convolvable BRIR; full gate GREEN with counts up.

**Must NOT have**: any core `roomestim/` change; any new package; `compute_rir()`/`measure_rt60()` use; modification of `render_binaural_demo` or `_resolve_damping_scalar`; the demo 2 s tail constant inherited; 500 Hz scalar collapse in the new path; any "perceptually faithful" claim (honesty scope — say "plausible"); unseeded RNG; FDN (deferred to Phase B); neural late (Phase B/C, out of scope).

## Deviations from ADR (flagged)

- **D1 (8-band vs 6-band)**: ADR §A assumes `pra_source.damping` is per-band aligned to the 6-band material. Spike proves pra emits **8 bands** (adds 8k/16k from fs). Plan slices `damping[0:6]` with a hard band-grid guard. Justification: empirical; the leading 6 align exactly with `OCTAVE_BANDS_HZ`.
- **D2 (compute_rir definitively rejected, not "conditional")**: ADR §E left compute_rir as conditionally-acceptable if the spike were GREEN. Spike is RED on BOTH conditions, so the plan removes the conditional and commits to image-source direct assembly. Justification: broadband-only output + 6× measure_rt60 error.
- **D3 (RNG API)**: ADR/demo use global `np.random.seed`. Plan uses `np.random.default_rng(seed+band)` for the new path. Justification: process-global seed is order-fragile for byte-equal tests; per-band generator is robust and isolated. Demo path keeps its `np.random.seed(seed)` (untouched).
