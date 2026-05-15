# ADR 0025 — Binaural demo stack (pyroomacoustics ISM + HUTUBS HRTF)

- **Status**: Accepted (v0.12-web.0)
- **Date**: 2026-05-15
- **Cross-ref**: ADR 0024 (web demo separate package), ADR 0026 (HRTF dataset
  selection), OQ-19 (binaural WAV byte-exact reproducibility across
  pyroomacoustics versions), `.omc/plans/v0.12-web-design.md` §13.

## Context

The `roomestim_web/` binaural demo view produces a 30-second stereo WAV
file that lets the user hear their own room's acoustics through headphones.
This requires two components:

1. **Room impulse response (RIR) synthesis** — given the `RoomModel`
   geometry + `MaterialAbsorption` table produced by the core acoustics
   package, synthesise per-source-direction RIRs.
2. **Binaural rendering** — convolve each mono source signal with the
   direction-matched HRTF (Head-Related Transfer Function) for left/right
   ears, sum to stereo, write WAV.

The choice of RIR synthesiser and HRTF library fixes the acoustic quality,
runtime budget (HF Spaces CPU; OQ-18 cold-start envelope), and
reproducibility contract (OQ-19 byte-exact golden test).

## Decision

### RIR synthesis — pyroomacoustics ISM

Use `pyroomacoustics` Image Source Method (ISM) with fixed parameters:

| Parameter | Value | Rationale |
|---|---|---|
| `max_order` | 10 | Adequate for RT60 ≤ 1.0 s rooms; higher order yields diminishing returns at CPU cost. |
| `ray_tracing` | `False` | CPU-only HF Spaces; ray tracing adds 10-100× cost for small room gain. |
| `fs` | 48 000 Hz | CD-quality; matches HUTUBS HRTF native sample rate; avoids resampling on the RIR side. |

One RIR per image-source direction (per `PlacementResult` speaker DOA).
The per-direction RIR length is determined by `max_order` and room geometry;
typical length ≈ 0.5–2.0 s at 48 kHz.

### Binaural rendering — HUTUBS HRTF + scipy fftconvolve

1. **HRTF lookup**: for each speaker DOA (azimuth, elevation), query the
   HUTUBS subject pp1 SOFA file (PRIMARY; ADR 0026) for the nearest-neighbour
   measurement direction. Fall back to MIT KEMAR (ADR 0026 FALLBACK) if the
   SOFA file is absent.
2. **Convolution**: `scipy.signal.fftconvolve(rir, hrtf_ir, mode="full")`
   for each of left/right ear HRIRs. FFT convolution chosen over
   `numpy.convolve` for speed at long RIR lengths.
3. **Mix**: sum convolved signals across all speaker directions; normalise to
   peak ±1.0; write 30-second stereo WAV at 48 kHz via `soundfile`.

Source audio: a 30-second mono speech excerpt from the LibriVox public-domain
corpus (Public Domain; see `scripts/fetch_web_data.py` for download
protocol). NOT bundled in this commit (file-size gate; same policy as SOFA
files — see ADR 0024 §Consequences).

### Reverse: downgrade path if S1 fires (HF Spaces CPU envelope exceeded)

If OQ-18 measures cold-start > 90 s OR per-request wall time > 30 s on the
HF Spaces free-tier CPU:

- Drop `max_order` from 10 → 6 (reduces RIR computation by ~40 %).
- Drop `fs` from 48 kHz → 24 kHz (halves convolution cost; HRTF
  resampled at load time per ADR 0026 §References).

Both downgrade steps preserve the binaural output format (stereo WAV) and
HUTUBS HRTF path; only quality degrades.

## Drivers

1. **pyroomacoustics** is the established Python RIR synthesiser with active
   maintenance, MIT licence, and a documented ISM implementation compatible
   with the `RoomModel` geometry format. No alternative Python library
   provides ISM + shoebox + polygon geometry in a single install.
2. **scipy.signal.fftconvolve** is already a transitive dependency of
   pyroomacoustics; zero additional install cost.
3. **HUTUBS subject pp1** provides 440 HRIR measurements at 2° angular
   resolution — adequate for the ±2–5° speaker DOA precision of the
   `place_vbap_ring` / `place_dbap_grid` outputs.
4. **48 kHz native** avoids a resampling step on the RIR side (pyroomacoustics
   natively synthesises at the requested `fs`); HUTUBS native rate is
   44.1 kHz, resampled to 48 kHz at load time (ADR 0026).
5. **fftconvolve over time-domain convolve**: RIR length × HRIR length
   products at 48 kHz easily exceed 10⁶ samples; FFT path is O(N log N)
   vs O(N²).

## Alternatives considered

- **(a) Use a ray-tracing RIR synthesiser (e.g., pyroomacoustics
  `ray_tracing=True`).** Rejected: 10–100× CPU cost; incompatible with HF
  Spaces free-tier CPU envelope (OQ-18 pre-mortem).
- **(b) Use pre-computed RIRs (offline synthesis, bundled as NPZ).** Rejected:
  user-room-specific RIRs cannot be pre-computed; the whole point of the demo
  is that the RIR reflects the user's uploaded room geometry.
- **(c) Use a different HRTF library (CIPIC, LISTEN).** Rejected: CIPIC is
  CC BY 4.0 but has only 45 subjects at coarser angular resolution (1125
  measurements total vs HUTUBS 11 500); LISTEN is CC BY 4.0 but IRs measured
  at 44.1 kHz with non-uniform elevation spacing. HUTUBS subject pp1 wins on
  angular resolution and SOFA-native format.
- **(d) Use `numpy.convolve` instead of `scipy.signal.fftconvolve`.** Rejected:
  O(N²) for long RIRs; at 48 kHz with `max_order=10`, RIR length can reach
  10⁵ samples — numpy time-domain convolution adds multiple seconds per
  speaker direction.

## Consequences

- **(+) 30-second stereo WAV** delivered per request; quality adequate for
  headphone demo of room acoustics.
- **(+) Reverse-criterion downgrade path** (max_order 10 → 6; fs 48 kHz →
  24 kHz) preserves the binaural view at reduced quality if CPU envelope
  fires.
- **(+) Byte-exact golden test** (`tests/web/test_binaural_renderer.py::
  test_binaural_render_byte_exact_golden`) verifiable once SOFA + WAV data
  files land (OQ-19 resolution gate).
- **(−) Binaural golden test SKIPPED** until HUTUBS SOFA + LibriVox WAV
  files are bundled (data-size gate; see ADR 0024 §Consequences + ADR 0026
  §Consequences).
- **(−) Cross-architecture byte-exactness unverified (OQ-19 OPEN)**: pinning
  `pyroomacoustics` version guarantees reproducibility on x86_64 Linux; ARM64
  reproducibility requires separate golden hash (OQ-19 resolution candidate).

## Reverse-criterion

- **S1 fires (OQ-18 cold-start > 90 s or per-request > 30 s)**: drop
  `max_order` 10 → 6 AND/OR `fs` 48 kHz → 24 kHz (both are single-param
  changes in `roomestim_web/views/binaural.py`; no ADR amendment needed
  unless the downgrade persists into the next web release).
- **OQ-19 ARM64 non-reproducibility confirmed**: mark
  `test_binaural_render_byte_exact_golden` as
  `@pytest.mark.xfail(condition=platform.machine() != "x86_64")` under a
  new `tests/web/conftest.py` platform guard.
- **pyroomacoustics ISM replaced by a different synthesiser** (e.g., a
  GPU-accelerated RIR library becomes available on HF Spaces free tier) →
  successor ADR 0025-bis (STRUCTURAL change; D28-P1 does not apply).

## References

- ADR 0024 — web demo separate package; `roomestim_web/` sibling layout;
  `[web]` extras dependency isolation.
- ADR 0026 — HRTF dataset selection; HUTUBS pp1 PRIMARY + MIT KEMAR FALLBACK;
  44.1 → 48 kHz resampling at load.
- OQ-18 — `.omc/plans/open-questions.md` (HF Spaces cold-start budget; S1
  reverse-criterion trigger point).
- OQ-19 — `.omc/plans/open-questions.md` (binaural WAV byte-exact
  reproducibility across pyroomacoustics versions and CPU architectures).
- pyroomacoustics documentation — ISM `max_order`, `ray_tracing`, `fs`
  parameters.
- pysofaconventions — SOFA file loading for HRTF measurement data.
- scipy.signal.fftconvolve — FFT convolution reference.
- `.omc/plans/v0.12-web-design.md` §13 (ADR 0025 stub + stack spec).
- `RELEASE_NOTES_v0.12-web.0.md` — parallel-track release notes.
