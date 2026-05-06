# E2E RT60 verification — ACE Challenge (Imperial College, 2015)

- Generated: 2026-05-06 by `tests/test_e2e_ace_challenge_rt60.py`
- Predictor: roomestim v0.4 Sabine + Eyring RT60 (mid-band 500 Hz + octave bands)
- Reference: ACE Challenge corpus tabulated T60 (per dataset_dir CSV)
- Framing: characterisation, NOT a pass/fail gate. Per-room error in seconds.

## Per-room 500 Hz error

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

## Per-band errors

### 125 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 1.097 | 1.041 | 0.450 | +0.648 | +0.592 |
| Lecture_1 | 0.821 | 0.750 | 0.678 | +0.143 | +0.072 |
| Lecture_2 | 0.851 | 0.771 | 0.880 | -0.030 | -0.109 |
| Meeting_1 | 0.856 | 0.796 | 0.554 | +0.302 | +0.242 |
| Meeting_2 | 0.922 | 0.852 | 0.581 | +0.341 | +0.271 |
| Office_1 | 0.742 | 0.694 | 0.535 | +0.208 | +0.159 |
| Office_2 | 0.768 | 0.717 | 0.508 | +0.260 | +0.209 |

- mean error Sabine: +0.267 s
- max abs error Sabine: +0.648 s
- mean error Eyring: +0.205 s
- max abs error Eyring: +0.592 s

### 250 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 2.164 | 2.108 | 0.608 | +1.555 | +1.500 |
| Lecture_1 | 1.539 | 1.469 | 0.851 | +0.689 | +0.618 |
| Lecture_2 | 0.746 | 0.666 | 1.062 | -0.317 | -0.397 |
| Meeting_1 | 0.685 | 0.625 | 0.481 | +0.204 | +0.144 |
| Meeting_2 | 0.676 | 0.605 | 0.455 | +0.221 | +0.150 |
| Office_1 | 1.159 | 1.110 | 0.406 | +0.753 | +0.704 |
| Office_2 | 1.200 | 1.150 | 0.450 | +0.750 | +0.700 |

- mean error Sabine: +0.551 s
- max abs error Sabine: +1.555 s
- mean error Eyring: +0.488 s
- max abs error Eyring: +1.500 s

### 500 Hz

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

### 1000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 3.136 | 3.081 | 0.685 | +2.451 | +2.396 |
| Lecture_1 | 2.428 | 2.358 | 0.535 | +1.893 | +1.823 |
| Lecture_2 | 0.568 | 0.486 | 1.506 | -0.939 | -1.020 |
| Meeting_1 | 0.388 | 0.326 | 0.401 | -0.012 | -0.074 |
| Meeting_2 | 0.363 | 0.289 | 0.331 | +0.032 | -0.042 |
| Office_1 | 0.766 | 0.718 | 0.317 | +0.449 | +0.401 |
| Office_2 | 0.787 | 0.737 | 0.439 | +0.348 | +0.297 |

- mean error Sabine: +0.603 s
- max abs error Sabine: +2.451 s
- mean error Eyring: +0.540 s
- max abs error Eyring: +2.396 s

### 2000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 2.794 | 2.739 | 0.712 | +2.082 | +2.027 |
| Lecture_1 | 2.066 | 1.996 | 0.639 | +1.427 | +1.357 |
| Lecture_2 | 0.535 | 0.454 | 1.378 | -0.843 | -0.924 |
| Meeting_1 | 0.341 | 0.278 | 0.417 | -0.076 | -0.139 |
| Meeting_2 | 0.319 | 0.244 | 0.328 | -0.009 | -0.084 |
| Office_1 | 0.609 | 0.560 | 0.298 | +0.311 | +0.262 |
| Office_2 | 0.625 | 0.575 | 0.420 | +0.205 | +0.155 |

- mean error Sabine: +0.442 s
- max abs error Sabine: +2.082 s
- mean error Eyring: +0.379 s
- max abs error Eyring: +2.027 s

### 4000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 2.134 | 2.079 | 0.685 | +1.450 | +1.394 |
| Lecture_1 | 1.646 | 1.576 | 0.678 | +0.969 | +0.898 |
| Lecture_2 | 0.490 | 0.408 | 1.161 | -0.671 | -0.753 |
| Meeting_1 | 0.300 | 0.236 | 0.432 | -0.133 | -0.196 |
| Meeting_2 | 0.283 | 0.207 | 0.350 | -0.067 | -0.143 |
| Office_1 | 0.495 | 0.446 | 0.327 | +0.168 | +0.119 |
| Office_2 | 0.508 | 0.457 | 0.402 | +0.107 | +0.055 |

- mean error Sabine: +0.260 s
- max abs error Sabine: +1.450 s
- mean error Eyring: +0.196 s
- max abs error Eyring: +1.394 s

## Caveats

This report is a CHARACTERISATION, not a pass/fail acceptance gate. Sabine assumes a diffuse field; real rooms violate this at low frequencies and in heavily-absorbed spaces (Vorländer 2020 §4). Material labels are inferred from ACE corpus informal descriptions (carpet/hard floor); mapping to roomestim's closed MaterialLabel enum involves judgment calls. Per-room and per-band `eyring ≤ sabine + 1e-9` is asserted at runtime (Vorländer 2020 §4.2).
