# ADR 0026 — HRTF dataset selection (HUTUBS PRIMARY + MIT KEMAR FALLBACK)

- **Status**: Accepted (v0.12-web.0)
- **Date**: 2026-05-15
- **Cross-ref**: ADR 0024 (web demo separate package; bundling policy),
  ADR 0025 (binaural demo stack; 48 kHz target sample rate), D31 (HRTF
  licensing and bundling policy), OQ-17 (HUTUBS subject-id stability),
  `.omc/plans/v0.12-web-design.md` §13.

## Context

The `roomestim_web/` binaural demo (ADR 0025) requires a set of
Head-Related Impulse Responses (HRIRs) covering the full sphere at adequate
angular resolution. The HRTF dataset must satisfy:

1. **Licence**: freely bundleable in a public GitHub repo and HF Space.
2. **Format**: SOFA (AES69-2022) for interoperability with
   `pysofaconventions`.
3. **Angular resolution**: ≤ 5° step adequate for the ±2–5° speaker DOA
   precision of roomestim's placement outputs.
4. **Sample rate**: 44.1 kHz or 48 kHz native (resampling permitted at load).
5. **File size**: combined bundle well under the 10 MB §0.4 STOP threshold
   (ADR 0024 §Reverse-criterion).

## Decision

### PRIMARY — HUTUBS subject pp1 (CC BY 4.0)

- **Source**: TU Berlin HUTUBS dataset (Brinkmann et al. 2017/2019). Subject
  identifier `pp1`.
- **Licence**: Creative Commons Attribution 4.0 International (CC BY 4.0).
  Attribution required at three locations per D31: `HRTF_ATTRIBUTION.md`,
  `README.md` `## License` section, web UI footer.
- **Measurements**: 440 directions at ≤ 5° azimuth step; 11 500 total
  measurements in the full dataset (pp1 = individual subject 1).
- **Native sample rate**: 44.1 kHz. Resampled to 48 kHz at load time via
  `scipy.signal.resample_poly` (integer ratio 160/147 = 48000/44100).
- **Bundled path**: `roomestim_web/data/hrtf/hutubs_pp1.sofa`.
- **SHA-256 pin**: captured in `HRTF_ATTRIBUTION.md` at data-bundle commit
  time; verified by `tests/web/conftest.py` fixture-integrity check.

### FALLBACK — MIT KEMAR (Public Domain)

- **Source**: MIT Media Lab KEMAR dummy-head HRTF dataset (Gardner & Martin
  1994/1995). Compact set.
- **Licence**: Public Domain (no attribution required; included in
  `HRTF_ATTRIBUTION.md` for completeness per D31).
- **Measurements**: 710 directions.
- **Native sample rate**: 44.1 kHz. Resampled to 48 kHz at load time
  (same `scipy.signal.resample_poly` path as PRIMARY).
- **Bundled path**: `roomestim_web/data/hrtf/kemar.sofa`.
- **SHA-256 pin**: captured in `HRTF_ATTRIBUTION.md` at data-bundle commit
  time.

### Fallback activation rule

The `roomestim_web/views/binaural.py` loader tries HUTUBS pp1 first. If
`hutubs_pp1.sofa` is absent or fails SHA-256 verification, it falls back to
`kemar.sofa`. If both are absent, the binaural view raises a
`HRTFDataMissingError` with a link to `scripts/fetch_web_data.py`.

### Resampling

Both SOFA files are natively at 44.1 kHz. The binaural stack operates at
48 kHz (ADR 0025 `fs=48000`). Resampling is performed ONCE at module load
time via `scipy.signal.resample_poly(hrir, up=160, down=147)` and cached
in memory. The integer ratio 160/147 is exact (48000 = 44100 × 160/147);
no floating-point approximation.

### Not bundled in this commit

Both SOFA files and the LibriVox source WAV are NOT committed in this
initial v0.12-web.0 commit due to file-size and licence-clarity review.
`scripts/fetch_web_data.py` provides the download + SHA-256 verification
protocol. The binaural byte-exact golden test is marked `skip` until the
data files land (OQ-17, OQ-19).

## Drivers

1. **HUTUBS angular resolution** (440 directions at ≤ 5° step) matches
   the ±2–5° placement DOA precision of `place_vbap_ring` /
   `place_dbap_grid`. Coarser datasets (e.g., CIPIC at ~1125 total) would
   introduce audible nearest-neighbour artefacts at fine placement angles.
2. **CC BY 4.0 licence** (HUTUBS) is bundleable in a public repo with
   attribution only — no share-alike, no non-commercial restriction.
3. **Public Domain** (MIT KEMAR) is the zero-friction fallback; no
   attribution required, no licence-compatibility check needed.
4. **SOFA format** (AES69-2022) is the de-facto standard for HRTF data;
   `pysofaconventions` provides a well-tested Python loader that handles
   coordinate system conversion and nearest-neighbour lookup internally.
5. **Combined bundle ~1 MB** (HUTUBS pp1 SOFA + KEMAR SOFA) is well under
   the 10 MB §0.4 STOP threshold; the D31 reverse-criterion
   (download-on-first-use if > 10 MB) does not fire.

## Alternatives considered

- **(a) CIPIC HRTF database (CC BY 4.0).** Rejected: 45 subjects at only
  25 azimuth × 50 elevation = 1250 directions total across all subjects;
  per-subject resolution coarser than HUTUBS pp1 at fine azimuth steps.
  HUTUBS wins on angular coverage.
- **(b) LISTEN database (IRCAM, CC BY 4.0).** Rejected: non-uniform
  elevation spacing; 187 directions per subject; angular resolution
  inadequate for 5° speaker placement steps.
- **(c) Download HRTF at runtime (no bundling).** Rejected: HF Spaces
  cold-start must not block on network; HUTUBS URLs have rotated in the
  past (TU Berlin server migrations). In-repo bundling is the cold-start
  guarantee (D31 reverse-criterion reverses if > 10 MB).
- **(d) Use only MIT KEMAR (no HUTUBS PRIMARY).** Rejected: KEMAR is a
  dummy head, not a human subject; pinnae geometry diverges from typical
  human ears more than HUTUBS pp1 (a real human subject). HUTUBS pp1 as
  PRIMARY delivers a more perceptually plausible demo.

## Consequences

- **(+) Cold-start HRTF availability**: SOFA files are in-repo; no network
  call at request time.
- **(+) SHA-256 integrity verification** at `tests/web/conftest.py` load:
  catches silent SOFA file corruption or accidental overwrite.
- **(+) Single resample at load** (not per-request): negligible per-request
  overhead after module initialisation.
- **(−) SOFA files NOT in this commit** (data-bundle gate; see ADR 0024
  §Consequences). Binaural golden test skipped until data lands.
- **(−) OQ-17 OPEN**: HUTUBS dataset versioning — if TU Berlin re-issues pp1
  (correction patch), the SHA-256 pin breaks and requires manual re-verification
  + golden hash update (OQ-17 resolution candidate: SHA-256 pin + manual diff
  at every HUTUBS release).

## Reverse-criterion

- **Combined SOFA bundle exceeds 10 MB** → switch to download-on-first-use
  via `scripts/fetch_web_data.py` (D31 reverse-criterion; ADR 0026 §Status-update
  at the relevant web release).
- **HUTUBS URL source rotates and pp1 subject-id changes** (OQ-17 fires) →
  re-pin SHA-256 + re-record binaural golden hash; bump `v0.12-web.0 →
  v0.12-web.1`.
- **HUTUBS licence changes** (CC BY 4.0 withdrawn or restricted) → switch
  PRIMARY to MIT KEMAR ONLY (Public Domain; zero licence risk). Successor
  ADR 0026-bis records the source switch (STRUCTURAL change; D28-P1 does not
  apply).

## References

- D31 — `.omc/plans/decisions.md` (HRTF licensing and bundling policy; SHA-256
  pins in `HRTF_ATTRIBUTION.md`; three-location attribution requirement).
- ADR 0024 — web demo separate package; `roomestim_web/data/hrtf/` path;
  10 MB §0.4 STOP threshold.
- ADR 0025 — binaural demo stack; 48 kHz target `fs`; `scipy.signal.fftconvolve`
  convolution; `pysofaconventions` SOFA loader.
- OQ-17 — `.omc/plans/open-questions.md` (HUTUBS pp1 subject-id stability
  across dataset updates).
- OQ-19 — `.omc/plans/open-questions.md` (binaural WAV byte-exact
  reproducibility across pyroomacoustics versions).
- Brinkmann et al. (2017/2019) — HUTUBS HRTF database. TU Berlin.
  https://depositonce.tu-berlin.de/handle/11303/be.6186.1
- Gardner & Martin (1994) — MIT KEMAR HRTF measurements. MIT Media Lab.
  Public Domain.
- AES69-2022 — SOFA (Spatially Oriented Format for Acoustics) standard.
- `HRTF_ATTRIBUTION.md` — per-repo attribution file (created at data-bundle
  commit time; not yet present at v0.12-web.0 initial commit).
- `scripts/fetch_web_data.py` — download + SHA-256 verification protocol.
- `.omc/plans/v0.12-web-design.md` §13 (ADR 0026 stub).
- `RELEASE_NOTES_v0.12-web.0.md` — parallel-track release notes.
