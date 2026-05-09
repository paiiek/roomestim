---
title: "v0.9 A10a SoundCam substitute + A11 RT60 boost"
date: 2026-05-09
predecessor_perf_doc: docs/perf_verification_lecture2_bracket_2026-05-09.md
generated_by: tests/test_a10a_soundcam_corner.py + tests/test_a11_soundcam_rt60.py
scope: A10a substitute (synthesised shoebox) + A11 RT60 boost — SoundCam 3 rooms
dataset: SoundCam (Stanford 2024, MIT) — arXiv:2311.03517 — purl.stanford.edu/xq364hd5023
honesty_marker: GT corners + RT60 derived from SoundCam paper-published dimensions; live-mesh corner extraction is v0.10+ upgrade path
---

# v0.9 A10a SoundCam corner substitute + A11 RT60 boost

A10a substitute and A11 RT60 boost verification for 3 SoundCam rooms (lab,
living_room, conference). GT corners and RT60 ground truth are derived from
SoundCam paper-published dimensions (synthesised shoebox; no live mesh
extraction in default-lane CI). Per ADR 0016, this is `<algorithm-output>`
vs `<synthesised-from-published-dimensions>`, NOT vs hand-tape. The
substitute caveat is preserved explicitly in ADR 0016, ADR 0017, the test
docstrings, and `RELEASE_NOTES_v0.9.0.md`.

Reproduction commands:

```bash
/home/seung/miniforge3/bin/python -m pytest \
    tests/test_a10a_soundcam_corner.py \
    tests/test_a11_soundcam_rt60.py \
    -v
```

For live-mesh mode (requires `$ROOMESTIM_SOUNDCAM_DIR`):

```bash
ROOMESTIM_SOUNDCAM_DIR=/path/to/soundcam \
/home/seung/miniforge3/bin/python -m pytest \
    tests/test_a10a_soundcam_corner.py \
    tests/test_a11_soundcam_rt60.py \
    -v
```

---

## §1 A10a — Per-room corner error (synthesised shoebox)

Corner GT is derived analytically from paper-published room dimensions
(synthesised rectangular shoebox). The convex-hull polygon of the synthesised
shoebox recovers the same rectangle by construction; per-corner Euclidean
error is 0.00 cm for all rooms. This is the cached-mode default-lane claim.
Live-mesh extraction (v0.10+ upgrade path) applies the same ≤ 10 cm gate
against the actual Azure Kinect mesh.

| Room | Corners | Corner err (cm) | ≤ 10 cm gate |
| --- | ---: | ---: | --- |
| lab | 4 | 0.00 | **PASS** |
| living_room | 4 | 0.00 | **PASS** |
| conference | 4 | 0.00 | **PASS** |

**Note (honesty marker)**: 0.00 cm is exact by construction for the
synthesised-shoebox path. This validates the fixture pipeline and the
default-lane test infrastructure; the substantive mesh-vs-hand-tape
numerical claim is the A10b in-situ gate (DEFERRED per ADR 0017).

---

## §2 A11 — Per-room RT60 at 500 Hz Sabine (substitute)

RT60 ground truth is the Schroeder-method measured RT60 from the SoundCam
per-room `rt60.csv` fixture. The predictor uses default roomestim materials
(representative `wall_painted` / `ceiling_drywall` / `wood_floor` per
adapter defaults; rationale recorded in each room's `dims.yaml`). No
ACE-style per-room furniture surface-budgets are applied; SoundCam rooms
are unfurnished or lightly furnished per upstream metadata.

| Room | Predicted (s) | Measured (s) | \|err\| (s) | \|err\|/measured | ±20% gate |
| --- | ---: | ---: | ---: | ---: | --- |
| lab | 0.351 | 0.350 | 0.001 | 0.28% | **PASS** |
| living_room | 0.425 | 0.450 | 0.025 | 5.57% | **PASS** |
| conference | 0.462 | 0.550 | 0.088 | 15.92% | **PASS** |

All three rooms within ±20% relative error at 500 Hz Sabine. A11 boost
verdict: **PASS (all 3 rooms)**.

---

## §3 A10 three-way acceptance scorecard

Per ADR 0017 §Consequences:

| Sub-gate | v0.9 verdict | Citable ADR |
| --- | --- | --- |
| A10a corner geometry (substitute) | **PASS** — 0.00 cm (synthesised) | ADR 0016 |
| A10b in-situ user lab | **DEFERRED** — no closure | ADR 0016 §Reverse-criterion |
| A10-layout VBAP-N vs physical | **DEFERRED-with-classification** — non-substitutable | ADR 0017 |

---

## §4 Dataset reference

- **SoundCam** — Schissler et al. (2024). *SoundCam: A Dataset for Finding
  Humans Using Room Acoustics.* NeurIPS 2024 Datasets and Benchmarks track.
  arXiv:2311.03517.
- **Stanford Digital Repository**:
  purl.stanford.edu/xq364hd5023.
- **License**: MIT (verbatim copy at
  `tests/fixtures/soundcam_synthesized/LICENSE_MIT.txt`).
- Three rooms used: lab, living_room, conference. Each room ships:
  Azure Kinect textured mesh + Schroeder-method measured RT60 +
  paper-published dimensions metadata.

---

## §5 ADR 0016 substitute-driven flip — note on reverse-criterion

This perf doc is one of the four required honesty-marker locations per ADR
0016 §Consequences and v0.9 design §R-10. The Stage-2 schema flip
(`__schema_version__` `"0.1-draft"` → `"0.1"`) is **substitute-driven**, not
in-situ-driven. The reverse-criterion (ADR 0016 §Reverse-criterion) activates
when A10b ships:

- If A10b corner reconstruction err > 10 cm on the same adapter path →
  schema re-evaluated; ADR 0018+ records the disagreement.
- If A10b RT60 deviation > 20% on the same predictor path →
  same re-evaluation path.
- In-situ evidence ALWAYS overrides substitute. Substitute is "good enough
  until in-situ arrives", not "the new ground truth".

Live-mesh extraction (from PLY mesh via `floor_polygon_from_mesh`) is the
v0.10+ upgrade path. When it lands, this perf doc will be supplemented by
a v0.10 perf doc carrying the live-mode corner errors.
