# E2E RT60 verification — ACE Challenge (Imperial College, 2015)

- Generated: 2026-05-06 by `tests/test_e2e_ace_challenge_rt60.py`
- Predictor: roomestim v0.3 Sabine RT60 (mid-band 500 Hz) + sabine_rt60_per_band (octave bands)
- Reference: ACE Challenge corpus tabulated T60 (per dataset_dir CSV)
- Framing: characterisation, NOT a pass/fail gate. Per-room error in seconds.

## Per-room 500 Hz error

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Building_Lobby | 2.022 | 0.597 | +1.425 |
| Lecture_1 | 1.762 | 0.561 | +1.201 |
| Lecture_2 | 0.673 | 1.343 | -0.670 |
| Meeting_1 | 0.499 | 0.427 | +0.072 |
| Meeting_2 | 0.468 | 0.407 | +0.061 |
| Office_1 | 0.864 | 0.377 | +0.486 |
| Office_2 | 0.887 | 0.452 | +0.435 |

- mean error: +0.430 s
- max abs error: +1.425 s

## Per-band errors

### 125 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Building_Lobby | 1.097 | 0.450 | +0.648 |
| Lecture_1 | 0.821 | 0.678 | +0.143 |
| Lecture_2 | 0.851 | 0.880 | -0.030 |
| Meeting_1 | 0.856 | 0.554 | +0.302 |
| Meeting_2 | 0.922 | 0.581 | +0.341 |
| Office_1 | 0.742 | 0.535 | +0.208 |
| Office_2 | 0.768 | 0.508 | +0.260 |

- mean error: +0.267 s
- max abs error: +0.648 s

### 250 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Building_Lobby | 2.164 | 0.608 | +1.555 |
| Lecture_1 | 1.539 | 0.851 | +0.689 |
| Lecture_2 | 0.746 | 1.062 | -0.317 |
| Meeting_1 | 0.685 | 0.481 | +0.204 |
| Meeting_2 | 0.676 | 0.455 | +0.221 |
| Office_1 | 1.159 | 0.406 | +0.753 |
| Office_2 | 1.200 | 0.450 | +0.750 |

- mean error: +0.551 s
- max abs error: +1.555 s

### 500 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Building_Lobby | 2.022 | 0.597 | +1.425 |
| Lecture_1 | 1.762 | 0.561 | +1.201 |
| Lecture_2 | 0.673 | 1.343 | -0.670 |
| Meeting_1 | 0.499 | 0.427 | +0.072 |
| Meeting_2 | 0.468 | 0.407 | +0.061 |
| Office_1 | 0.864 | 0.377 | +0.486 |
| Office_2 | 0.887 | 0.452 | +0.435 |

- mean error: +0.430 s
- max abs error: +1.425 s

### 1000 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Building_Lobby | 3.136 | 0.685 | +2.451 |
| Lecture_1 | 2.428 | 0.535 | +1.893 |
| Lecture_2 | 0.568 | 1.506 | -0.939 |
| Meeting_1 | 0.388 | 0.401 | -0.012 |
| Meeting_2 | 0.363 | 0.331 | +0.032 |
| Office_1 | 0.766 | 0.317 | +0.449 |
| Office_2 | 0.787 | 0.439 | +0.348 |

- mean error: +0.603 s
- max abs error: +2.451 s

### 2000 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Building_Lobby | 2.794 | 0.712 | +2.082 |
| Lecture_1 | 2.066 | 0.639 | +1.427 |
| Lecture_2 | 0.535 | 1.378 | -0.843 |
| Meeting_1 | 0.341 | 0.417 | -0.076 |
| Meeting_2 | 0.319 | 0.328 | -0.009 |
| Office_1 | 0.609 | 0.298 | +0.311 |
| Office_2 | 0.625 | 0.420 | +0.205 |

- mean error: +0.442 s
- max abs error: +2.082 s

### 4000 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Building_Lobby | 2.134 | 0.685 | +1.450 |
| Lecture_1 | 1.646 | 0.678 | +0.969 |
| Lecture_2 | 0.490 | 1.161 | -0.671 |
| Meeting_1 | 0.300 | 0.432 | -0.133 |
| Meeting_2 | 0.283 | 0.350 | -0.067 |
| Office_1 | 0.495 | 0.327 | +0.168 |
| Office_2 | 0.508 | 0.402 | +0.107 |

- mean error: +0.260 s
- max abs error: +1.450 s

## Caveats

This report is a CHARACTERISATION, not a pass/fail acceptance gate. Sabine assumes a diffuse field; real rooms violate this at low frequencies and in heavily-absorbed spaces (Vorländer 2020 §4). Material labels are inferred from ACE corpus informal descriptions (carpet/hard floor); mapping to roomestim's closed MaterialLabel enum involves judgment calls.
