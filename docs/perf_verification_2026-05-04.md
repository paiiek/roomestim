# roomestim v0.1 — Performance Verification Report

**Date**: 2026-05-04  
**Repo**: `/home/seung/mmhoa/roomestim/`  
**Python**: `/home/seung/miniforge3/bin/python3` (shapely 2.1.2, numpy, jsonschema installed)  
**Scope**: Quantitative evidence against design §1 precision targets and A1–A16 acceptance criteria.  
**Method**: All measurements executed via python_repl using miniforge Python; no production code modified.

---

## Pass/Fail Summary

| Item | Criterion | Target | Result | PASS |
|------|-----------|--------|--------|------|
| S1 | Coord roundtrip (10 804 pts) | az/el < 1e-6 rad, dist_rel < 1e-9 | az=0.0, el=2.2e-16, dist=1.8e-16 | ✓ |
| S2a | VBAP ring az error (n=4,6,8,12) | < 1° | 0.000000° (all n) | ✓ |
| S2a | VBAP ring radial error | < 1 cm | 0.000000 cm (all n) | ✓ |
| S2b | DBAP on mount surfaces | all on surface (tol 1 cm) | 6/6 | ✓ |
| S2b | DBAP coverage gain | min > −3 dB | −1.07 dB | ✓ |
| S2c | WFS spacing ≤ c/(2·f_max) | always satisfied | confirmed 3 f_max values | ✓ |
| S2c | WFS kErrWfsSpacingTooLarge | raised on violation | raised correctly | ✓ |
| S2c | wfs_f_alias_hz finite & positive | required | confirmed all cases | ✓ |
| S3 | Noise sweep 100 trials × 5 σ | non-divergent, max dev < 1° | 0.000° all σ | ✓ |
| S4 | RT60 vs Sabine (carpet scenario) | ±20% | 0.0000% error | ✓ |
| S4 | RT60 vs Sabine (concrete+wood) | ±20% | 0.0000% error | ✓ |
| S4 | Pre-baked constant accuracy | — | 0.0124% vs formula | ✓ |
| S5 | layout.yaml Draft202012 schema | 0 violations | 0 violations | ✓ |
| S5 | Required fields present | version, name, speakers | all present | ✓ |
| S5 | Per-speaker id≥1, channel≥1, monotone | required | confirmed | ✓ |
| S5 | All numeric values finite | A1 finiteness | confirmed | ✓ |
| S6 | Idempotency byte equality | 10/10 runs | 10/10 | ✓ |
| S7 | Lab cross-check (sanity) | equal-angle spacing | 90.0° × 4 confirmed | ✓ |

**Overall: 18/18 checks pass. All design §1 precision targets met.**

---

## 1. Coordinate Roundtrip Accuracy (A4 extended)

**Source**: `roomestim/coords.py` — `yaml_speaker_to_cartesian` → `cartesian_to_pipeline`.

**Setup**: Full grid sweep — az_deg ∈ [−180, 180] step 5°, el_deg ∈ [−90, 90] step 5°, dist ∈ {0.5, 1, 2, 5} m. Total 10 804 points.

| Metric | Value | Target | PASS |
|--------|-------|--------|------|
| max az error (rad) | 0.000e+00 | < 1e-6 | ✓ |
| max el error (rad) | 2.220e-16 | < 1e-6 | ✓ |
| max dist relative error | 1.776e-16 | < 1e-9 | ✓ |

[STAT:n] n = 10 804 points  
[STAT:effect_size] Errors are at IEEE-754 double precision floor (machine epsilon ≈ 2.2e-16); the roundtrip is numerically exact.

**Note**: `cartesian_to_pipeline` uses `atan2` and `sqrt` — both correctly invert `yaml_speaker_to_cartesian`'s `sin/cos` expansions. The pole singularity (el = ±90°, cos(el) = 0) produces az = atan2(0,0) = 0 which is consistent with the VBAP convention. `coords.py:38–48`.

---

## 2. Placement Accuracy on Synthetic GT Rooms (A5, A6, A7, A8)

### 2a. VBAP Ring — n ∈ {4, 6, 8, 12}, radius = 2 m, el = 0°

**Setup**: `place_vbap_ring` output compared analytically to GT positions `az_i = i·360°/n`, `dist = radius_m`. Source: `roomestim/place/vbap.py:55–68`.

| n | max az error (°) | mean az error (°) | max radial error (cm) | PASS az | PASS rad |
|---|-----------------|-------------------|-----------------------|---------|----------|
| 4 | 0.000000 | 0.000000 | 0.000000 | ✓ | ✓ |
| 6 | 0.000000 | 0.000000 | 0.000000 | ✓ | ✓ |
| 8 | 0.000000 | 0.000000 | 0.000000 | ✓ | ✓ |
| 12 | 0.000000 | 0.000000 | 0.000000 | ✓ | ✓ |

Targets: angle error < 1°, radial error < 1 cm. Both met at machine-epsilon level.

**Listener-area centroid offset** (+0.3 m, 0, +0.5 m): max az = 0.000°, max radial = 0.000 cm. By v0.1 design, `listener_pos` is informational only; ring positions remain in listener-frame at origin. `vbap.py:101`.

### 2b. DBAP — Positions on Mount Surfaces + Coverage

**Setup**: Shoebox room (5×4×2.8 m, `synthetic_rooms.py:35`), 4 wall surfaces as mount surfaces, `place_dbap(n_speakers=6)`. Position-on-surface check uses surface plane projection + Shapely containment at 1 cm tolerance. `roomestim/place/dbap.py:51–104`.

| Check | Result | Target | PASS |
|-------|--------|--------|------|
| Positions on mount surface | 6/6 | 6/6 | ✓ |
| Coverage min/max gain | −1.07 dB | > −3 dB | ✓ |

[STAT:effect_size] Coverage headroom = 1.93 dB above the −3 dB floor.

### 2c. WFS Spacing Constraint (A8)

**Setup**: 2 m baseline, three f_max values; spacing set to 0.99 × bound. `roomestim/place/wfs.py:108–112`.

| f_max (Hz) | λ/2 bound (cm) | actual max spacing (cm) | f_alias (Hz) | PASS spacing | PASS f_alias |
|-----------|---------------|------------------------|-------------|-------------|-------------|
| 4 000 | 4.29 | 4.24 | 4 040 | ✓ | ✓ |
| 8 000 | 2.14 | 2.12 | 8 081 | ✓ | ✓ |
| 16 000 | 1.07 | 1.06 | 16 162 | ✓ | ✓ |

`kErrWfsSpacingTooLarge` raised correctly when `spacing_m=0.5 > bound=0.043` at `f_max=4000 Hz`. `wfs.py:109–113`.

---

## 3. Placement Under Noise (A16 extended)

**Setup**: 100 trials × σ ∈ {0, 1, 2, 5, 10} cm uniform vertex perturbation + ±1° yaw rotation on shoebox floor polygon. VBAP-8 ring run after each perturbation. `test_placement_under_noise.py:30–60`.

| σ (cm) | mean dev (°) | std dev (°) | max dev (°) | non-divergent (≤1°) |
|--------|-------------|-------------|-------------|---------------------|
| 0 | 0.0000 | 0.0000 | 0.0000 | ✓ |
| 1 | 0.0000 | 0.0000 | 0.0000 | ✓ |
| 2 | 0.0000 | 0.0000 | 0.0000 | ✓ |
| 5 | 0.0000 | 0.0000 | 0.0000 | ✓ |
| 10 | 0.0000 | 0.0000 | 0.0000 | ✓ |

[STAT:n] n = 100 trials per σ level (500 total)  
[STAT:effect_size] Zero variance across all noise levels.

**Design note**: VBAP ring placement is intentionally geometry-independent — it depends only on `n`, `radius_m`, `el_deg`. The noise sweep confirms the contract: floor_polygon perturbation has zero propagation to speaker positions. This is the correct behaviour for a ring algorithm. `vbap.py:76–108`. The A16 acceptance test passes by construction and is not tautological: it explicitly locks that this independence holds and cannot regress.

---

## 4. RT60 vs Sabine Reference (A11)

**Setup**: Shoebox 4×3×2.5 m (V = 30 m³, as specified). Two material scenarios tested using `sabine_rt60` from `roomestim/reconstruct/materials.py:38–79` vs hand-computed Sabine formula. Absorption table from `roomestim/model.py:53–62` (Vorländer 2020 Appendix A).

| Scenario | roomestim RT60 (s) | hand Sabine (s) | error % | within ±20% |
|----------|-------------------|-----------------|---------|-------------|
| carpet floor (α=0.30) + wall_painted (α=0.05) + ceiling_drywall (α=0.10) | 0.7374 | 0.7374 | 0.0000% | ✓ |
| wall_concrete (α=0.02) + wood_floor (α=0.10) + ceiling_drywall (α=0.10) | 1.5581 | 1.5581 | 0.0000% | ✓ |

Pre-baked constant `SABINE_REFERENCE_SHOEBOX_RT60_S = 0.581` (5×4×2.8 m shoebox) vs formula output 0.5809 s: 0.0124% difference. `materials.py:35`.

[STAT:effect_size] Formula match is exact (same formula, same table); the 0.0124% discrepancy is from the constant being rounded to 3 decimal places.

**Range context**: carpet scenario RT60 = 0.74 s (well-damped), concrete+wood RT60 = 1.56 s (reverberant). Both physically plausible for a 30 m³ room.

---

## 5. Engine Roundtrip Schema Validation (A2/A5)

**Setup**: VBAP-8 ring → `write_layout_yaml` → tempfile → `jsonschema.Draft202012Validator` against `/home/seung/mmhoa/spatial_engine/proto/geometry_schema.json`. Source: `roomestim/export/layout_yaml.py`, schema at `spatial_engine/proto/geometry_schema.json`.

| Check | Result | PASS |
|-------|--------|------|
| Schema violations | 0 | ✓ |
| `version` present | "1.0" | ✓ |
| `name` present | "vbap_ring" | ✓ |
| `speakers` array present | 8 entries | ✓ |
| All `id >= 1` | True | ✓ |
| All `channel >= 1` | True | ✓ |
| Monotone channels 1..8 | True | ✓ |
| All numeric leaves finite | True | ✓ |
| No spherical/Cartesian conflict | True (az_deg only) | ✓ |

Extension key `x_aim_az_deg` / `x_aim_el_deg` present per design §6.1 (D5). Engine ignores them (`additionalProperties: true`). No extra-field violations.

**C++ loader** (A2): SKIP — `SPATIAL_ENGINE_BUILD_DIR` not set. Schema validation is the unconditional fallback gate per A2 design.

---

## 6. Idempotency Byte Equality (A12)

**Setup**: `test_cli_idempotent.py` confirmed to use `f.read_bytes()` comparison (`test_cli_idempotent.py:57`). CLI invoked 10 independent times in separate temp directories.

| Runs | byte-identical room.yaml | byte-identical layout.yaml | PASS |
|------|--------------------------|---------------------------|------|
| 10/10 | ✓ | ✓ | ✓ |

[STAT:n] 10 independent subprocess pairs (20 total CLI invocations)  
No flakiness observed. YAML serialisation uses deterministic dict ordering (Python 3.10+ insertion order + `sort_keys` in `export/layout_yaml.py`).

---

## 7. Cross-Check Against spatial_engine Lab Fixture (Sanity)

**Source**: `/home/seung/mmhoa/spatial_engine/configs/lab_8ch_aligned.yaml`

Lab fixture is a **dome** layout: 4 lower speakers at el=0° (az = −135°, −45°, +45°, +135°) and 4 upper speakers at el=30° (same azimuths). Radius = 1.0 m for all speakers.

| Property | Lab value | roomestim n=4 ring | Notes |
|----------|-----------|-------------------|-------|
| Consecutive az spacing (lower) | 90.0° × 4 | 90.0° × 4 | Equal-angle confirmed |
| Phase offset from 0° | 225° (i.e. −135°) | 0° | Lab intentionally offset; not an error |
| Radius | 1.0 m | configurable (default 2.0 m) | Matches with `radius_m=1.0` |
| Elevation lower ring | 0° | configurable | Exact match |
| Elevation upper ring | 30° | configurable | Exact match (`place_vbap_dome`) |

The lab layout is a valid equal-angle ring (`place_vbap_ring(n=4, radius_m=1.0)`) rotated by a −45° phase offset. roomestim does not currently expose a `phase_offset_deg` parameter; a user would need to rotate the output post-placement. The **spacing** (90° equal-angle) is identical; the offset is a deliberate installation choice for front-facing alignment.

[LIMITATION] Phase offset is not configurable in v0.1 `place_vbap_ring`. If the lab layout is regenerated from roomestim, the output would need an additional rotation. This is a missing v0.1 feature, not a numerical error.

---

## Limitations (post-v0.1.1 closeout categorisation, 2026-05-05)

The list below preserves the v0.1 measurement state. After v0.1.1 closeout, each
limitation now carries a status — CLOSED, CHARACTERISED, DEFERRED, AUDITED,
or OPEN. See `.omc/plans/v0.1.1-closeout.md` for the plan and the new test
files / decision document each status references.

### CLOSED in v0.1.1

[CLOSED] **Phase offset gap**: `place_vbap_ring` now accepts `phase_offset_deg`
and `place_vbap_dome` accepts `phase_offsets_deg=[lower, upper]`. Defaults
reproduce v0.1 byte-for-byte (frozen pre-edit golden:
`tests/fixtures/golden/place_vbap_ring_n8_default.yaml`). Lab fixture
position-subset match is asserted by
`tests/test_placement_vbap_phase.py::test_lab_8ch_aligned_position_subset_match`.

### CHARACTERISED in v0.1.1

[CHARACTERISED] **S3 noise sweep — DBAP geometry-dependence**: `_greedy_max_min_select`
(`roomestim/place/dbap.py:215–247`) is structurally non-smooth (argmax tie-break
flips the selected candidate set under sub-cm vertex perturbation). v0.1.1 ships
`tests/test_placement_dbap_under_noise.py` asserting **invariants only**
(non-divergence, on-surface ≤1 cm, count preservation) at σ ∈ {0, 1, 2, 5} cm.
Drift histogram is printed (not asserted) and committed in the test docstring
as the 2026-05-05 characterisation snapshot. No fabricated drift threshold.

### DEFERRED in v0.1.1

[DEFERRED] **A2 (C++ loader smoke-test) and A15 (C++ coords parity)**: The named
binaries (`layout_loader_smoke`, `coords_parity_harness`) do not exist in
`/home/seung/mmhoa/spatial_engine/core/build/` (verified 2026-05-04). Authoring
them inside roomestim was rejected (smuggles C++ build complexity into a
Python-first repo; consumer-side reimplementation invalidates parity). Deferred
to spatial_engine v0.2 — see `.omc/plans/decisions.md` D10. Compensating coverage:
schema validation S5 (A2 fallback) + 10 804-point Python coords roundtrip at
machine epsilon (A15 fallback). Skip-reason text in both test modules now names
D10 explicitly.

### AUDITED in v0.1.1

[AUDITED] **A10 (lab scan gate)**: Fixture path audited; `tests/fixtures/lab_real_groundtruth.yaml.template`
provided as single source of truth for the GT YAML schema (matching
`tests/test_acceptance_lab_room.py`'s consumed field set). The acceptance test's
inline schema docstring was trimmed to a one-line pointer at the template per
v0.1.1-closeout Step 5. The physical capture session itself remains post-autopilot
human-gated per D8.

### OPEN

[OPEN — substantive] **RT60 accuracy vs real rooms**: Sabine formula is ±20% at
best in real rooms (non-diffuse fields, low-frequency resonances); the 0.00%
formula-vs-formula match merely confirms the implementation is arithmetically
correct. Octave-band absorption + reference-room comparison would close this
limitation but is deferred to v0.3 per D7. Noted in `RELEASE_NOTES_v0.1.1.md`
under "Known limitations" (NOT closed).

---

*Report generated: 2026-05-04. Limitations section recategorised 2026-05-05 as
part of v0.1.1 closeout. No production code modified by this report; v0.1.1
closeout edits live in their own commits — see plan §4 Steps 0–6.*
