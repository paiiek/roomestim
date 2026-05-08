# E2E RT60 verification — ACE Challenge (Imperial College, 2015)

- Generated: 2026-05-08 by `tests/test_e2e_ace_challenge_rt60.py`
- Predictor: roomestim v0.6 Sabine + Eyring RT60 (mid-band 500 Hz + octave bands)
- Reference: ACE Challenge corpus tabulated T60 (per dataset_dir CSV)
- Framing: characterisation, NOT a pass/fail gate. Per-room error in seconds.

## Per-room 500 Hz error

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 2.022 | 1.966 | 0.597 | +1.425 | +1.369 |
| Lecture_1 | 0.686 | 0.631 | 0.561 | +0.125 | +0.071 |
| Lecture_2 | 0.435 | 0.374 | 1.343 | -0.908 | -0.969 |
| Meeting_1 | 0.410 | 0.355 | 0.427 | -0.017 | -0.072 |
| Meeting_2 | 0.395 | 0.331 | 0.407 | -0.012 | -0.076 |
| Office_1 | 0.704 | 0.658 | 0.377 | +0.327 | +0.281 |
| Office_2 | 0.631 | 0.587 | 0.452 | +0.179 | +0.135 |

- mean error Sabine: +0.160 s
- max abs error Sabine: +1.425 s
- mean error Eyring: +0.106 s
- max abs error Eyring: +1.369 s

## Per-band errors

### 125 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 1.097 | 1.041 | 0.450 | +0.648 | +0.592 |
| Lecture_1 | 0.601 | 0.547 | 0.678 | -0.077 | -0.131 |
| Lecture_2 | 0.632 | 0.572 | 0.880 | -0.248 | -0.308 |
| Meeting_1 | 0.721 | 0.668 | 0.554 | +0.167 | +0.114 |
| Meeting_2 | 0.780 | 0.718 | 0.581 | +0.199 | +0.137 |
| Office_1 | 0.676 | 0.631 | 0.535 | +0.142 | +0.096 |
| Office_2 | 0.641 | 0.597 | 0.508 | +0.133 | +0.089 |

- mean error Sabine: +0.138 s
- max abs error Sabine: +0.648 s
- mean error Eyring: +0.084 s
- max abs error Eyring: +0.592 s

### 250 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 2.164 | 2.108 | 0.608 | +1.555 | +1.500 |
| Lecture_1 | 0.759 | 0.705 | 0.851 | -0.092 | -0.146 |
| Lecture_2 | 0.513 | 0.452 | 1.062 | -0.549 | -0.611 |
| Meeting_1 | 0.560 | 0.506 | 0.481 | +0.079 | +0.025 |
| Meeting_2 | 0.563 | 0.501 | 0.455 | +0.108 | +0.045 |
| Office_1 | 0.943 | 0.898 | 0.406 | +0.537 | +0.492 |
| Office_2 | 0.846 | 0.802 | 0.450 | +0.396 | +0.352 |

- mean error Sabine: +0.291 s
- max abs error Sabine: +1.555 s
- mean error Eyring: +0.237 s
- max abs error Eyring: +1.500 s

### 500 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 2.022 | 1.966 | 0.597 | +1.425 | +1.369 |
| Lecture_1 | 0.686 | 0.631 | 0.561 | +0.125 | +0.071 |
| Lecture_2 | 0.435 | 0.374 | 1.343 | -0.908 | -0.969 |
| Meeting_1 | 0.410 | 0.355 | 0.427 | -0.017 | -0.072 |
| Meeting_2 | 0.395 | 0.331 | 0.407 | -0.012 | -0.076 |
| Office_1 | 0.704 | 0.658 | 0.377 | +0.327 | +0.281 |
| Office_2 | 0.631 | 0.587 | 0.452 | +0.179 | +0.135 |

- mean error Sabine: +0.160 s
- max abs error Sabine: +1.425 s
- mean error Eyring: +0.106 s
- max abs error Eyring: +1.369 s

### 1000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 3.136 | 3.081 | 0.685 | +2.451 | +2.396 |
| Lecture_1 | 0.656 | 0.601 | 0.535 | +0.121 | +0.066 |
| Lecture_2 | 0.360 | 0.298 | 1.506 | -1.146 | -1.209 |
| Meeting_1 | 0.321 | 0.265 | 0.401 | -0.080 | -0.136 |
| Meeting_2 | 0.308 | 0.243 | 0.331 | -0.023 | -0.089 |
| Office_1 | 0.612 | 0.566 | 0.317 | +0.295 | +0.250 |
| Office_2 | 0.544 | 0.500 | 0.439 | +0.105 | +0.060 |

- mean error Sabine: +0.246 s
- max abs error Sabine: +2.451 s
- mean error Eyring: +0.191 s
- max abs error Eyring: +2.396 s

### 2000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 2.794 | 2.739 | 0.712 | +2.082 | +2.027 |
| Lecture_1 | 0.550 | 0.495 | 0.639 | -0.089 | -0.144 |
| Lecture_2 | 0.324 | 0.261 | 1.378 | -1.054 | -1.117 |
| Meeting_1 | 0.279 | 0.223 | 0.417 | -0.139 | -0.195 |
| Meeting_2 | 0.269 | 0.202 | 0.328 | -0.060 | -0.126 |
| Office_1 | 0.491 | 0.445 | 0.298 | +0.193 | +0.147 |
| Office_2 | 0.438 | 0.394 | 0.420 | +0.018 | -0.026 |

- mean error Sabine: +0.136 s
- max abs error Sabine: +2.082 s
- mean error Eyring: +0.081 s
- max abs error Eyring: +2.027 s

### 4000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Building_Lobby | 2.134 | 2.079 | 0.685 | +1.450 | +1.394 |
| Lecture_1 | 0.487 | 0.432 | 0.678 | -0.191 | -0.246 |
| Lecture_2 | 0.298 | 0.234 | 1.161 | -0.863 | -0.927 |
| Meeting_1 | 0.247 | 0.191 | 0.432 | -0.185 | -0.242 |
| Meeting_2 | 0.239 | 0.172 | 0.350 | -0.110 | -0.178 |
| Office_1 | 0.409 | 0.362 | 0.327 | +0.082 | +0.035 |
| Office_2 | 0.368 | 0.323 | 0.402 | -0.033 | -0.078 |

- mean error Sabine: +0.021 s
- max abs error Sabine: +1.450 s
- mean error Eyring: -0.034 s
- max abs error Eyring: +1.394 s

## Caveats

This report is a CHARACTERISATION, not a pass/fail acceptance gate. Sabine assumes a diffuse field; real rooms violate this at low frequencies and in heavily-absorbed spaces (Vorländer 2020 §4). Material labels are inferred from ACE corpus informal descriptions (carpet/hard floor); mapping to roomestim's closed MaterialLabel enum involves judgment calls. Per-room and per-band `eyring ≤ sabine + 1e-9` is asserted at runtime (Vorländer 2020 §4.2).
