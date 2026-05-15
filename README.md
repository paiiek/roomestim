---
title: roomestim — spatial audio configurator
emoji: 🏠
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: "4.0.0"
app_file: app.py
pinned: false
---

# roomestim

Capture-to-config tool. Phone room-scan (Apple RoomPlan / Polycam / COLMAP fallback) or public corpus
(ACE Challenge, SoundCam) → simplified `RoomModel` + algorithm-aware speaker placement → engine-ready
`layout.yaml` (validated against `spatial_engine/proto/geometry_schema.json`) plus a `room.yaml`
that carries 10-entry `MaterialLabel` enum + octave-band absorption coefficients.

- **Status**: **v0.11.0** (2026-05-11) — MELAMINE_FOAM enum (ADR 0019) + lab A11 PASS-gate recovered
  (rel_err +2.4%) + CI tense-lint (ADR 0020) + in-situ A10b protocol DOC (no capture commitment yet).
  See `RELEASE_NOTES_v0.11.0.md` and `docs/weekly_progress_report_2026-05-11.md` for the cumulative
  v0.5.0 → v0.11.0 weekly story.
  v0.12-web.0 parallel-track web demo ships in `roomestim_web/` (sibling package; D30 release versioning; ADR 0024-0026).
- **Precision target**: cm-grade — walls ±10 cm, speaker angles ±2–5°, RT60 ±20%. NOT BIM precision.
- **Coordinate frame**: VBAP layout-frame (`spatial_engine/docs/coordinate_convention.md`) — listener
  at origin, x=right, y=up, z=front, metres. RIGHT = +az_deg, UP = +el_deg.
- **Sibling repos (read-only here)**: `/home/seung/mmhoa/spatial_engine/`,
  `/home/seung/mmhoa/vid2spatial_v2/`.
- **Schema marker**: `__schema_version__ = "0.1-draft"` (Stage-1 permissive). Stage-2 strict flip is
  bound to A10b in-situ capture per ADR 0016 §Reverse-criterion + ADR 0018.

## Web demo

A Gradio web app at `roomestim_web/` lets users upload a phone room scan (.usdz / .obj / .gltf / .glb / .ply),
configure speaker placement, and receive: a 3D interactive viewer, an octave-band RT60 report,
a printable per-speaker setup PDF, a binaural demo WAV (HUTUBS HRTF + pyroomacoustics ISM
inside their own room), and a ZIP archive of all artefacts. Install via the `[web]` optional
extra:

```bash
pip install -e ".[web]"
python -m roomestim_web   # or: gradio app.py for hot-reload
```

Deploy as a Hugging Face Space: the repo root `app.py` + `requirements.txt` + the front-matter
YAML block at the top of this file constitute the canonical Spaces layout.

See `RELEASE_NOTES_v0.12-web.0.md`, `docs/adr/0024-web-demo-separate-package.md`,
`docs/adr/0025-binaural-demo-stack.md`, `docs/adr/0026-hrtf-dataset-selection.md`.

## Capture backends

| Backend | Status | Notes |
|---|---|---|
| Apple RoomPlan | first-class | LiDAR metric scale; USDZ + JSON sidecar. See [ADR 0001](docs/adr/0001-capture-backend-priority.md). |
| Polycam | supported | Mesh-only; cross-platform (Android, non-Pro iPhone). |
| COLMAP | experimental | Scale-ambiguous; requires `[colmap]` extra + `--experimental` flag. |
| ACE Challenge (Eaton 2016 TASLP) | E2E adapter | 7-room corpus; dimensions from arXiv:1606.03365 Table 1; materials are NOT in paper → Vorländer 2020 §11 / Appx A proxy. See [ADR 0010](docs/adr/0010-ace-geometry-verified-arxiv.md) + [ADR 0012](docs/adr/0012-eaton-taslp-materials-not-in-paper.md). |
| SoundCam (Stanford NeurIPS D&B) | substitute (v0.9+) | 3-room MIT-licensed corpus; v0.11 lab returned to A11 PASS-gate under MELAMINE_FOAM. See [ADR 0016](docs/adr/0016-stage2-schema-flip-via-substitute.md) + [ADR 0018](docs/adr/0018-soundcam-substitute-disagreement-record.md) + [ADR 0019](docs/adr/0019-melamine-foam-enum-addition.md). |

## RT60 estimators

| Estimator | Decision | Status |
|---|---|---|
| Sabine (single mid-band 500 Hz) | [D7](.omc/plans/decisions.md) | v0.1+ |
| Sabine (octave-band 125-4000 Hz) | [D8](.omc/plans/decisions.md) | v0.3+ |
| Eyring (parallel predictor) | [D9](.omc/plans/decisions.md), [ADR 0009](docs/adr/0009-eyring-parallel-predictor.md) | v0.4+ |

## Quickstart

```bash
pip install -e .[dev]

python -m roomestim run \
    --backend roomplan \
    --input tests/fixtures/lab_room.usdz \
    --algorithm vbap --n-speakers 8 --layout-radius 2.0 \
    --out-dir /tmp/roomestim_out

# default-lane test suite (excludes lab + e2e fixtures)
pytest -m "not lab and not e2e" -v
# 121 passed, 3 skipped, 3 deselected (124 collected) at v0.11.0

# CI lint (tense audit for honesty leaks)
python scripts/lint_tense.py
```

## Install (dev)

```bash
# Debian/Ubuntu (PEP-668 system Python): use --user --break-system-packages OR venv
pip install --user --break-system-packages -e ".[dev,web]"
# OR
python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev,web]"
```

## Repo layout

```
roomestim/                  # package source — model, adapters, place, reconstruct
proto/                      # JSON Schema for room.yaml (Stage 1 draft + Stage 2 locked)
tests/                      # pytest, fixtures, hypothesis property tests (124 default-lane @ v0.11)
tests/fixtures/             # lab_room.usdz, ace_*/, soundcam_synthesized/
scripts/lint_tense.py       # honesty-leak lint (ADR 0020)
docs/                       # architecture, room_yaml_spec, ADRs 0001-0020, weekly progress report
docs/adr/                   # 20 architecture decision records
docs/perf_verification_*.md # per-version perf snapshots (Sabine RT60 MAE per ACE room)
docs/protocol_a10b_*.md     # in-situ capture protocol DOC (v0.11; no capture commitment)
.omc/plans/                 # design plans v0-design through v0.11-design, decisions.md (D1-D25), open-questions.md (OQ-1 through OQ-14)
RELEASE_NOTES_v*.md         # per-release notes (v0.1.1 → v0.11.0)
```

## Placement API

```python
from roomestim.place.vbap import place_vbap_ring, place_vbap_dome
from roomestim.place.wfs import place_wfs_line
from roomestim.place.dbap import place_dbap_grid

# Equal-angle ring with phase offset (deg). Default 0.0 = v0.1 byte-equal.
place_vbap_ring(n=8, radius_m=2.0, el_deg=0.0, phase_offset_deg=-135.0)

# Stacked dome, two independent ring offsets [lower, upper].
place_vbap_dome(
    n_lower=4, n_upper=4,
    radius_m=1.0,
    phase_offsets_deg=[-135.0, -135.0],
    layout_name="lab_8ch_aligned",
)

# WFS linear array (v0.7+).
place_wfs_line(n=16, length_m=3.0, listener_distance_m=2.0)
```

## MaterialLabel enum (v0.11.0 — 10 entries)

| Label | α₅₀₀ | Source |
|---|---|---|
| `CARPET` | 0.30 | Vorländer 2020 §11 / Appx A |
| `DRYWALL` | 0.05 | " |
| `GLASS` | 0.03 | " |
| `CEILING_ACOUSTIC_TILE` | 0.55 | " |
| `FLOOR_HARD_GENERIC` | 0.02 | " |
| `MISC_HARD` | 0.05 | " |
| `MISC_SOFT` | 0.40 | representative-not-verbatim per [D14](. omc/plans/decisions.md), [ADR 0011](docs/adr/0011-misc-soft-enum.md) |
| `WALL_CONCRETE` | 0.02 | Vorländer 2020 §11 / Appx A |
| `WALL_BRICK_PAINTED` | 0.02 | " |
| `MELAMINE_FOAM` (NEW v0.11) | 0.85 | planner-locked envelope; verbatim citation PENDING per [ADR 0019](docs/adr/0019-melamine-foam-enum-addition.md) §References |

## Phase status

| Phase | Description | Status | Release |
|---|---|---|---|
| P0 | Repo bootstrap, coords port, ADR stubs | done | v0.1 |
| P1 | RoomModel + CaptureAdapter protocol + room.yaml export | done | v0.1 |
| P2 | layout.yaml export + engine round-trip | done | v0.1 |
| P3 | VBAP + DBAP placement | done | v0.1 |
| P4 | RoomPlan adapter + reconstruction | done | v0.1 |
| P5 | WFS placement + Polycam adapter | done | v0.1 |
| P6 | CLI, viz, lab acceptance gate | done | v0.1 |
| P7 | Docs and ADR finalization | done | v0.1.1 |
| P8 | Octave-band absorption + Eyring + ACE Challenge E2E adapter | done | v0.3.0 / v0.4.0 |
| P9 | partial-A (ACE dims verified) + B (MISC_SOFT enum) + TASLP-MISC surface budget | done | v0.5.0 / v0.5.1 / v0.6.0 |
| P10 | WFS CLI + Building_Lobby coupled-space exclusion + Lecture_2 bracketing (null) | done | v0.7.0 / v0.8.0 |
| P11 | SoundCam substitute + Stage-2 attempt + honesty correction + ADR 0018 disagreement record | done | v0.9.0 / v0.10.0 / v0.10.1 |
| P12 | MELAMINE_FOAM enum (ADR 0019) + CI tense-lint (ADR 0020) + in-situ A10b protocol DOC | **done** | **v0.11.0** |
| P13 | A10b actual in-situ capture (user-volunteer) | pending | v0.12+ |

## OMC pipeline (v0.11+)

Non-trivial changes route through `planner → executor → code-reviewer → verifier` per
`/home/seung/.claude/projects/-home-seung-mmhoa-roomestim/memory/MEMORY.md`. v0.11.0 was the first
release shipped with all four stages explicit; see `.omc/plans/v0.11-design.md` (1123 lines, planner)
and the four-stage verdict in the commit body of `eee3014`.

## Attach to spatial_engine

v0.1-v0.11 ships standalone. Cross-repo PR proposing `room.yaml` upstream stays WITHDRAWN per
[ADR 0018](docs/adr/0018-soundcam-substitute-disagreement-record.md) §Reverse-criterion — needs
≥ 3 captures + both substitute rooms (lab + conference) at A11 PASS. v0.11 satisfies the PASS
condition for lab; conference remains in disagreement-record regime (orthogonal to MELAMINE_FOAM
since conference is glass-heavy, not foam-treated). Re-submission is v0.12+ scope.

See `.omc/plans/decisions.md` (D1, D2, D11) and `docs/weekly_progress_report_2026-05-11.md` §5 for
roadmap.

## Tag policy (D11)

All git tags (`v0.1.1` through `v0.11.0`) are **local-only**. Commits push to `origin/main`. Tag
push is a separate ratification gate (currently undefined).
