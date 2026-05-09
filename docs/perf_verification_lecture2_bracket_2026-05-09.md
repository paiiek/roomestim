---
title: "v0.8 Lecture_2 ceiling/seat bracketing — sensitivity-only"
date: 2026-05-09
predecessor_perf_doc: docs/perf_verification_e2e_2026-05-08.md
generated_by: tests/test_lecture_2_ceiling_seat_bracket.py::test_bracket_emits_perf_doc_appendix
scope: sensitivity-only — v0.6/v0.7 numerical baseline preserved
excluded_rooms: [Building_Lobby]   # ADR 0014
v4_bounding_case: disabled   # gated by ROOMESTIM_BRACKET_V4=1
---

# v0.8 Lecture_2 ceiling/seat bracketing — sensitivity-only

Sensitivity bracketing of Lecture_2 ceiling material + lecture_seat α (unoccupied profile) per ADR 0015. v0.6/v0.7 numerical baseline is preserved; this document is a sensitivity report only.

Variant set: **V0** baseline / **V1** ceiling=CEILING_DRYWALL / **V2** lecture_seat α₅₀₀=0.20 unoccupied / **V3** V1+V2 / **V4** ceiling=WALL_CONCRETE bounding case (env-gated).

Building_Lobby is excluded per ADR 0014. Rows below cover the 6 furniture-tracked rooms × 6 octave bands × 2 predictors.

## §1 Per-variant Lecture_2 500 Hz residual

| Variant | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| V0 | 0.435 | 0.374 | 1.343 | -0.908 | -0.969 |
| V1 | 0.743 | 0.682 | 1.343 | -0.600 | -0.661 |
| V2 | 0.322 | 0.272 | 1.343 | -1.021 | -1.071 |
| V3 | 0.464 | 0.414 | 1.343 | -0.879 | -0.929 |

## §2 V3 acceptance verdict

- Lecture_2 V3 |err| @500 Hz: 0.879 s (threshold 0.500 s)
- Non-Lecture_2 rooms regressing > +0.100 s @500 Hz vs V0 (Sabine):
  - Meeting_1: +0.108 s
  - Meeting_2: +0.142 s

**Verdict: NULL** — V3 does not satisfy the acceptance envelope. Single-coefficient ceiling/seat bracketing is insufficient to close the Lecture_2 residual without external regression. v0.9 considers the broader F4a per-band sensitivity sweep + coupled-space modelling per ADR 0015 §Reverse-trigger.

## §3 Per-band bracketing tables

### V0

#### 125 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.601 | 0.547 | 0.678 | -0.077 | -0.131 |
| Lecture_2 | 0.632 | 0.572 | 0.880 | -0.248 | -0.308 |
| Meeting_1 | 0.721 | 0.668 | 0.554 | +0.167 | +0.114 |
| Meeting_2 | 0.780 | 0.718 | 0.581 | +0.199 | +0.137 |
| Office_1 | 0.676 | 0.631 | 0.535 | +0.141 | +0.096 |
| Office_2 | 0.641 | 0.597 | 0.508 | +0.133 | +0.089 |

#### 250 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.759 | 0.705 | 0.851 | -0.092 | -0.146 |
| Lecture_2 | 0.513 | 0.452 | 1.062 | -0.549 | -0.610 |
| Meeting_1 | 0.560 | 0.506 | 0.481 | +0.079 | +0.025 |
| Meeting_2 | 0.563 | 0.501 | 0.455 | +0.108 | +0.046 |
| Office_1 | 0.943 | 0.898 | 0.406 | +0.537 | +0.492 |
| Office_2 | 0.846 | 0.802 | 0.450 | +0.396 | +0.352 |

#### 500 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.686 | 0.631 | 0.561 | +0.125 | +0.070 |
| Lecture_2 | 0.435 | 0.374 | 1.343 | -0.908 | -0.969 |
| Meeting_1 | 0.410 | 0.355 | 0.427 | -0.017 | -0.072 |
| Meeting_2 | 0.395 | 0.331 | 0.407 | -0.012 | -0.076 |
| Office_1 | 0.704 | 0.658 | 0.377 | +0.327 | +0.281 |
| Office_2 | 0.631 | 0.587 | 0.452 | +0.179 | +0.135 |

#### 1000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.656 | 0.601 | 0.535 | +0.121 | +0.066 |
| Lecture_2 | 0.360 | 0.298 | 1.506 | -1.146 | -1.208 |
| Meeting_1 | 0.321 | 0.265 | 0.401 | -0.080 | -0.136 |
| Meeting_2 | 0.308 | 0.243 | 0.331 | -0.023 | -0.088 |
| Office_1 | 0.612 | 0.566 | 0.317 | +0.295 | +0.249 |
| Office_2 | 0.544 | 0.500 | 0.439 | +0.105 | +0.061 |

#### 2000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.550 | 0.495 | 0.639 | -0.089 | -0.144 |
| Lecture_2 | 0.324 | 0.261 | 1.378 | -1.054 | -1.117 |
| Meeting_1 | 0.279 | 0.223 | 0.417 | -0.138 | -0.194 |
| Meeting_2 | 0.269 | 0.202 | 0.328 | -0.059 | -0.126 |
| Office_1 | 0.491 | 0.445 | 0.298 | +0.193 | +0.147 |
| Office_2 | 0.438 | 0.394 | 0.420 | +0.018 | -0.026 |

#### 4000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.487 | 0.432 | 0.678 | -0.191 | -0.246 |
| Lecture_2 | 0.298 | 0.234 | 1.161 | -0.863 | -0.927 |
| Meeting_1 | 0.247 | 0.191 | 0.432 | -0.185 | -0.241 |
| Meeting_2 | 0.239 | 0.172 | 0.350 | -0.111 | -0.178 |
| Office_1 | 0.409 | 0.362 | 0.327 | +0.082 | +0.035 |
| Office_2 | 0.368 | 0.323 | 0.402 | -0.034 | -0.079 |

### V1

#### 125 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.601 | 0.547 | 0.678 | -0.077 | -0.131 |
| Lecture_2 | 0.641 | 0.580 | 0.880 | -0.239 | -0.300 |
| Meeting_1 | 0.733 | 0.679 | 0.554 | +0.179 | +0.125 |
| Meeting_2 | 0.795 | 0.733 | 0.581 | +0.214 | +0.152 |
| Office_1 | 0.676 | 0.631 | 0.535 | +0.141 | +0.096 |
| Office_2 | 0.641 | 0.597 | 0.508 | +0.133 | +0.089 |

#### 250 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.759 | 0.705 | 0.851 | -0.092 | -0.146 |
| Lecture_2 | 0.827 | 0.767 | 1.062 | -0.235 | -0.295 |
| Meeting_1 | 0.952 | 0.899 | 0.481 | +0.471 | +0.418 |
| Meeting_2 | 1.054 | 0.993 | 0.455 | +0.599 | +0.538 |
| Office_1 | 0.943 | 0.898 | 0.406 | +0.537 | +0.492 |
| Office_2 | 0.846 | 0.802 | 0.450 | +0.396 | +0.352 |

#### 500 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.686 | 0.631 | 0.561 | +0.125 | +0.070 |
| Lecture_2 | 0.743 | 0.682 | 1.343 | -0.600 | -0.661 |
| Meeting_1 | 0.669 | 0.616 | 0.427 | +0.242 | +0.189 |
| Meeting_2 | 0.681 | 0.619 | 0.407 | +0.274 | +0.212 |
| Office_1 | 0.704 | 0.658 | 0.377 | +0.327 | +0.281 |
| Office_2 | 0.631 | 0.587 | 0.452 | +0.179 | +0.135 |

#### 1000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.656 | 0.601 | 0.535 | +0.121 | +0.066 |
| Lecture_2 | 0.724 | 0.663 | 1.506 | -0.782 | -0.843 |
| Meeting_1 | 0.578 | 0.524 | 0.401 | +0.177 | +0.123 |
| Meeting_2 | 0.593 | 0.530 | 0.331 | +0.262 | +0.199 |
| Office_1 | 0.612 | 0.566 | 0.317 | +0.295 | +0.249 |
| Office_2 | 0.544 | 0.500 | 0.439 | +0.105 | +0.061 |

#### 2000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.550 | 0.495 | 0.639 | -0.089 | -0.144 |
| Lecture_2 | 0.607 | 0.546 | 1.378 | -0.771 | -0.832 |
| Meeting_1 | 0.464 | 0.410 | 0.417 | +0.047 | -0.007 |
| Meeting_2 | 0.472 | 0.409 | 0.328 | +0.144 | +0.081 |
| Office_1 | 0.491 | 0.445 | 0.298 | +0.193 | +0.147 |
| Office_2 | 0.438 | 0.394 | 0.420 | +0.018 | -0.026 |

#### 4000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.487 | 0.432 | 0.678 | -0.191 | -0.246 |
| Lecture_2 | 0.538 | 0.477 | 1.161 | -0.623 | -0.684 |
| Meeting_1 | 0.392 | 0.338 | 0.432 | -0.040 | -0.094 |
| Meeting_2 | 0.400 | 0.336 | 0.350 | +0.050 | -0.014 |
| Office_1 | 0.409 | 0.362 | 0.327 | +0.082 | +0.035 |
| Office_2 | 0.368 | 0.323 | 0.402 | -0.034 | -0.079 |

### V2

#### 125 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.474 | 0.430 | 0.678 | -0.204 | -0.248 |
| Lecture_2 | 0.503 | 0.454 | 0.880 | -0.377 | -0.426 |
| Meeting_1 | 0.623 | 0.575 | 0.554 | +0.069 | +0.021 |
| Meeting_2 | 0.676 | 0.621 | 0.581 | +0.095 | +0.040 |
| Office_1 | 0.621 | 0.578 | 0.535 | +0.086 | +0.043 |
| Office_2 | 0.564 | 0.524 | 0.508 | +0.056 | +0.016 |

#### 250 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.504 | 0.459 | 0.851 | -0.347 | -0.392 |
| Lecture_2 | 0.391 | 0.341 | 1.062 | -0.671 | -0.721 |
| Meeting_1 | 0.473 | 0.425 | 0.481 | -0.008 | -0.056 |
| Meeting_2 | 0.483 | 0.427 | 0.455 | +0.028 | -0.028 |
| Office_1 | 0.796 | 0.753 | 0.406 | +0.390 | +0.347 |
| Office_2 | 0.667 | 0.626 | 0.450 | +0.217 | +0.176 |

#### 500 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.426 | 0.381 | 0.561 | -0.135 | -0.180 |
| Lecture_2 | 0.322 | 0.272 | 1.343 | -1.021 | -1.071 |
| Meeting_1 | 0.347 | 0.298 | 0.427 | -0.080 | -0.129 |
| Meeting_2 | 0.342 | 0.285 | 0.407 | -0.065 | -0.122 |
| Office_1 | 0.594 | 0.551 | 0.377 | +0.217 | +0.174 |
| Office_2 | 0.498 | 0.457 | 0.452 | +0.046 | +0.005 |

#### 1000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.379 | 0.334 | 0.535 | -0.156 | -0.201 |
| Lecture_2 | 0.264 | 0.213 | 1.506 | -1.242 | -1.293 |
| Meeting_1 | 0.273 | 0.223 | 0.401 | -0.128 | -0.178 |
| Meeting_2 | 0.268 | 0.209 | 0.331 | -0.063 | -0.122 |
| Office_1 | 0.510 | 0.466 | 0.317 | +0.193 | +0.149 |
| Office_2 | 0.422 | 0.381 | 0.439 | -0.017 | -0.058 |

#### 2000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.317 | 0.272 | 0.639 | -0.322 | -0.367 |
| Lecture_2 | 0.232 | 0.181 | 1.378 | -1.146 | -1.197 |
| Meeting_1 | 0.236 | 0.185 | 0.417 | -0.181 | -0.232 |
| Meeting_2 | 0.232 | 0.172 | 0.328 | -0.096 | -0.156 |
| Office_1 | 0.412 | 0.368 | 0.298 | +0.114 | +0.070 |
| Office_2 | 0.343 | 0.301 | 0.420 | -0.077 | -0.119 |

#### 4000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.286 | 0.240 | 0.678 | -0.392 | -0.438 |
| Lecture_2 | 0.214 | 0.162 | 1.161 | -0.947 | -0.999 |
| Meeting_1 | 0.210 | 0.159 | 0.432 | -0.222 | -0.273 |
| Meeting_2 | 0.207 | 0.147 | 0.350 | -0.143 | -0.203 |
| Office_1 | 0.348 | 0.304 | 0.327 | +0.021 | -0.023 |
| Office_2 | 0.294 | 0.252 | 0.402 | -0.108 | -0.150 |

### V3

#### 125 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.474 | 0.430 | 0.678 | -0.204 | -0.248 |
| Lecture_2 | 0.509 | 0.460 | 0.880 | -0.371 | -0.420 |
| Meeting_1 | 0.632 | 0.584 | 0.554 | +0.078 | +0.030 |
| Meeting_2 | 0.687 | 0.632 | 0.581 | +0.106 | +0.051 |
| Office_1 | 0.621 | 0.578 | 0.535 | +0.086 | +0.043 |
| Office_2 | 0.564 | 0.524 | 0.508 | +0.056 | +0.016 |

#### 250 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.504 | 0.459 | 0.851 | -0.347 | -0.392 |
| Lecture_2 | 0.550 | 0.501 | 1.062 | -0.512 | -0.561 |
| Meeting_1 | 0.726 | 0.678 | 0.481 | +0.245 | +0.197 |
| Meeting_2 | 0.804 | 0.749 | 0.455 | +0.349 | +0.294 |
| Office_1 | 0.796 | 0.753 | 0.406 | +0.390 | +0.347 |
| Office_2 | 0.667 | 0.626 | 0.450 | +0.217 | +0.176 |

#### 500 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.426 | 0.381 | 0.561 | -0.135 | -0.180 |
| Lecture_2 | 0.464 | 0.414 | 1.343 | -0.879 | -0.929 |
| Meeting_1 | 0.518 | 0.470 | 0.427 | +0.091 | +0.043 |
| Meeting_2 | 0.537 | 0.481 | 0.407 | +0.130 | +0.074 |
| Office_1 | 0.594 | 0.551 | 0.377 | +0.217 | +0.174 |
| Office_2 | 0.498 | 0.457 | 0.452 | +0.046 | +0.005 |

#### 1000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.379 | 0.334 | 0.535 | -0.156 | -0.201 |
| Lecture_2 | 0.418 | 0.368 | 1.506 | -1.088 | -1.138 |
| Meeting_1 | 0.439 | 0.391 | 0.401 | +0.038 | -0.010 |
| Meeting_2 | 0.459 | 0.402 | 0.331 | +0.128 | +0.071 |
| Office_1 | 0.510 | 0.466 | 0.317 | +0.193 | +0.149 |
| Office_2 | 0.422 | 0.381 | 0.439 | -0.017 | -0.058 |

#### 2000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.317 | 0.272 | 0.639 | -0.322 | -0.367 |
| Lecture_2 | 0.349 | 0.299 | 1.378 | -1.029 | -1.079 |
| Meeting_1 | 0.356 | 0.307 | 0.417 | -0.061 | -0.110 |
| Meeting_2 | 0.369 | 0.312 | 0.328 | +0.041 | -0.016 |
| Office_1 | 0.412 | 0.368 | 0.298 | +0.114 | +0.070 |
| Office_2 | 0.343 | 0.301 | 0.420 | -0.077 | -0.119 |

#### 4000 Hz

| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lecture_1 | 0.286 | 0.240 | 0.678 | -0.392 | -0.438 |
| Lecture_2 | 0.315 | 0.265 | 1.161 | -0.846 | -0.896 |
| Meeting_1 | 0.307 | 0.257 | 0.432 | -0.125 | -0.175 |
| Meeting_2 | 0.318 | 0.261 | 0.350 | -0.032 | -0.089 |
| Office_1 | 0.348 | 0.304 | 0.327 | +0.021 | -0.023 |
| Office_2 | 0.294 | 0.252 | 0.402 | -0.108 | -0.150 |

## §4 Caveats

Sensitivity-only report. Sabine and Eyring assume a diffuse field; real rooms violate this at low frequencies and in heavily-absorbed spaces (Vorländer 2020 §4). Material labels for V1..V4 are representative-not-verbatim per ADR 0012 / 0013 / 0015. Measured T60 values are factual reproductions of the v0.6/v0.7 perf doc (see ``tests/fixtures/ace_eaton_2016_table_i_measured_rt60.csv``).
