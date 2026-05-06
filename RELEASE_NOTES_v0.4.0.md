# RELEASE NOTES — roomestim v0.4.0

v0.4.0 ships Eyring as a parallel RT60 predictor (Sabine remains default). The gated
ACE Challenge E2E test now reports Sabine and Eyring side-by-side per room and per
octave band, with `eyring ≤ sabine + 1e-9` enforced at runtime per Vorländer 2020 §4.2.
The ACE corpus byte-audit against Eaton 2016 TASLP Table I is DEFERRED to v0.5
because the canonical Table I is not in the local corpus distribution.

A12 byte-equality of every v0.3.1 default-lane test is preserved (74 → 80; +6 Eyring
unit tests; nothing existing is modified).

---

## New API

- `roomestim.reconstruct.materials.eyring_rt60(volume_m3, surface_areas) -> float` —
  Eyring 1930 / Vorländer 2020 §4.2 reverberation time at 500 Hz. Raises `ValueError`
  on empty surfaces, zero absorption, or `ᾱ ≥ 1`.
- `roomestim.reconstruct.materials.eyring_rt60_per_band(volume_m3, surface_areas) -> dict[int, float]`
  — per-octave-band Eyring (keys = `OCTAVE_BANDS_HZ`).

Sabine remains the default predictor; CLI and adapter codepaths are unchanged at v0.4.
Eyring is callable-level only at v0.4.0; CLI / adapter exposure deferred to v0.5+ on
consumer request.

## ACE characterisation update

The gated E2E test now reports both predictors. Empirical numbers from the regenerated
`docs/perf_verification_e2e_2026-05-06.md` (500 Hz):

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 2.022 | 1.966 | 0.597 | +1.425 | +1.369 |
| Lecture_1 | 1.762 | 1.692 | 0.561 | +1.201 | +1.131 |
| Lecture_2 | 0.673 | 0.593 | 1.343 | -0.670 | -0.750 |
| Meeting_1 | 0.499 | 0.437 | 0.427 | +0.072 | +0.011 |
| Meeting_2 | 0.468 | 0.396 | 0.407 | +0.061 | -0.011 |
| Office_1 | 0.864 | 0.815 | 0.377 | +0.486 | +0.438 |
| Office_2 | 0.887 | 0.837 | 0.452 | +0.435 | +0.385 |

- mean error Sabine: +0.430 s
- max abs error Sabine: +1.425 s
- mean error Eyring: +0.367 s
- max abs error Eyring: +1.369 s

Observation: at the 7-room ACE corpus, the Sabine→Eyring 500 Hz delta is small
(≤ 0.080 s for every room). Predictor choice is **not** the dominant error source.

## Audit findings summary

`.omc/plans/v0.4-audit-findings.md` records four findings:
- **Finding 1 (DEFERRED)**: local corpus lacks a machine-readable room metadata
  table; canonical Eaton 2016 TASLP Table I not present locally → byte-audit deferred.
- **Finding 2 (DONE)**: Eyring shipped; documented to not be the dominant error source.
- **Finding 3 (DEFERRED, hypothesis)**: Lecture_2 may map to `ceiling_drywall` rather
  than `ceiling_acoustic_tile`; cannot confirm without paper.
- **Finding 4 (DEFERRED)**: bare-walls model misses soft-furnishings absorption budget.
  Two follow-ups (coefficient revision; `MISC_SOFT` enum extension) deferred to a
  v0.5 ADR.

D14 in `.omc/plans/decisions.md` records the rationale.

## Tests

| File | Count | Markers |
| --- | ---: | --- |
| `tests/test_room_acoustics_octave.py` | +6 (12 total) | (none — default lane) |
| `tests/test_e2e_ace_challenge_rt60.py` | unchanged count; 6-tuple report extension | `e2e`, `network` (gated); none (unit) |

Default-lane collected: **80** tests (74 v0.3.1 + 6 v0.4 Eyring). `ruff check` clean.

## Backwards compatibility

- `sabine_rt60` and `sabine_rt60_per_band` byte-identical to v0.3.1.
- `MaterialAbsorptionBands` table unchanged.
- Schema unchanged (no `0.1-draft` flip).
- All 74 v0.3.1 default-lane tests pass byte-for-byte.
- No CLI flag added; no adapter signature changed.

## What stays deferred

- ACE_ROOM_GEOMETRY byte-audit against Eaton 2016 Table I (D14, Finding 1).
- Lecture_2 ceiling material reassignment (Finding 3).
- `MaterialAbsorptionBands` coefficient revision (Finding 4a).
- `MISC_SOFT` enum extension (Finding 4b).
- Millington-Sette per-surface predictor (ADR 0009 alternatives).
- Stage-2 schema flip / A10 lab capture (D8).
- 8 kHz octave band (ADR 0008 reverse criterion).
- PyPI / submodule (D11).
