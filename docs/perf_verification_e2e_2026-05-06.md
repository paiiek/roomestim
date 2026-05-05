# E2E RT60 verification — ACE Challenge (Imperial College, 2015)

- Generated: 2026-05-06 by `tests/test_e2e_ace_challenge_rt60.py`
- Predictor: roomestim v0.3 Sabine RT60 (mid-band 500 Hz) + sabine_rt60_per_band (octave bands)
- Reference: ACE Challenge corpus tabulated T60 (per dataset_dir CSV)
- Framing: characterisation, NOT a pass/fail gate. Per-room error in seconds.

## Per-room 500 Hz error

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Meeting_1 | 0.499 | 0.610 | -0.111 |
| Office_1 | 0.864 | 0.420 | +0.444 |

- mean error: +0.166 s
- max abs error: +0.444 s

## Per-band errors

### 125 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Meeting_1 | 0.856 | 0.680 | +0.176 |
| Office_1 | 0.742 | 0.450 | +0.292 |

- mean error: +0.234 s
- max abs error: +0.292 s

### 250 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Meeting_1 | 0.685 | 0.650 | +0.035 |
| Office_1 | 1.159 | 0.440 | +0.719 |

- mean error: +0.377 s
- max abs error: +0.719 s

### 500 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Meeting_1 | 0.499 | 0.610 | -0.111 |
| Office_1 | 0.864 | 0.420 | +0.444 |

- mean error: +0.166 s
- max abs error: +0.444 s

### 1000 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Meeting_1 | 0.388 | 0.570 | -0.182 |
| Office_1 | 0.766 | 0.400 | +0.366 |

- mean error: +0.092 s
- max abs error: +0.366 s

### 2000 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Meeting_1 | 0.341 | 0.510 | -0.169 |
| Office_1 | 0.609 | 0.370 | +0.239 |

- mean error: +0.035 s
- max abs error: +0.239 s

### 4000 Hz

| Room | Predicted (s) | Measured (s) | Error (s) |
| --- | ---: | ---: | ---: |
| Meeting_1 | 0.300 | 0.430 | -0.130 |
| Office_1 | 0.495 | 0.320 | +0.175 |

- mean error: +0.022 s
- max abs error: +0.175 s

## Caveats

This report is a CHARACTERISATION, not a pass/fail acceptance gate. Sabine assumes a diffuse field; real rooms violate this at low frequencies and in heavily-absorbed spaces (Vorländer 2020 §4). Material labels are inferred from ACE corpus informal descriptions (carpet/hard floor); mapping to roomestim's closed MaterialLabel enum involves judgment calls.
