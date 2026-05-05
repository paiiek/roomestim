# roomestim — v0 Strategic Design Plan

- **Status**: DRAFT (consensus-mode RALPLAN-DR, short)
- **Mode**: SHORT (architect + critic review pending; no `--deliberate` signal)
- **Date**: 2026-05-03
- **Owner**: paiiek
- **Repo path**: `/home/seung/mmhoa/roomestim/`
- **Sibling (read-only)**: `/home/seung/mmhoa/spatial_engine/`
- **Plan file**: `.omc/plans/roomestim-v0-design.md`

> Goal: ship v0.1 of a Python tool that takes room-capture artifacts (RoomPlan/Polycam/COLMAP), produces a simplified `RoomModel` + speaker placement, and emits engine-ready `layout.yaml` (validated against `spatial_engine/proto/geometry_schema.json`) plus a new proposed `room.yaml` schema. Precision target: cm-grade (walls ±10 cm, speaker angles ±2–5°). NOT mm-grade BIM.

---

## 1. Requirements Summary

`roomestim` is a capture-to-config tool sitting **upstream of `spatial_engine`**. It ingests a phone scan (Apple RoomPlan or Polycam) — or, as a fallback, monocular video via COLMAP / a single-image room layout estimator — and produces three outputs an audio-installation engineer needs to bring up a venue: (a) a simplified `RoomModel` (room polygon, ceiling height, listener area, surface material/absorption hints), (b) algorithm-aware **speaker placement recommendations** for VBAP, WFS, DBAP, or Ambisonics, and (c) **engine-compatible YAML files** — `layout.yaml` against the existing `spatial_engine/proto/geometry_schema.json`, and a new `room.yaml` whose schema this project owns and proposes upstream.

The precision target is fit-for-purpose installation work in performance/exhibition venues: walls within ±10 cm, speaker pointing within ±2–5°, RT60 estimates within ±20% (acoustic estimates are recommendations, not measurements). The tool is Python-only at v0.1, mirrors the dependency discipline of sibling `claude_text2traj` (setuptools, optional-dependency groups, pytest markers), and lives as **its own git repo** so it can be pinned/versioned independently before being attached as a `spatial_engine` submodule. All coordinate output uses the engine's VBAP layout-frame convention (`docs/coordinate_convention.md`): listener at origin, RIGHT=+az_deg, UP=+el_deg, z forward, metres. No coordinate sign-flips outside the conversion helpers.

---

## 2. RALPLAN-DR Summary

### 2.1 Principles (5)

1. **Engine contract is the north star.** Every output must round-trip through `spatial_engine`'s loaders. `layout.yaml` must validate against the existing JSON Schema (`proto/geometry_schema.json`) and parse successfully through `core/src/geometry/LayoutLoader.cpp`. `room.yaml` is a NEW schema we own and propose upstream — but its coordinate convention is locked to `core/src/coords/Coords.h` from day one.
2. **Cm-grade, not mm-grade.** RoomPlan/Polycam scans inherit ±2–5 cm scan noise. We do not pretend to BIM precision. We make the precision contract explicit (acceptance criterion #4) and refuse to ship features that depend on better.
3. **Pluggable adapters around a stable internal model.** Capture backends differ (USDZ, OBJ, COLMAP point cloud, single-image layout). The internal `RoomModel` is the only stable abstraction; adapters are throwaway-grade. New backends must not require schema changes.
4. **Algorithm-aware placement, not generic.** A "place 8 speakers in this room" function is useless without knowing whether the renderer is VBAP, WFS, or DBAP. The placement module dispatches on a `target_algorithm` enum mirroring `spatial_engine`'s rendering algorithms (`require.md` §2: WFS/VBAP/DBAP) and `SpeakerLayout.h::Regularity`.
5. **Verifiability over polish.** v0.1 ships a CLI + headless tests + one sample USDZ fixture. No GUI. Every acceptance criterion has a numeric tolerance and a corresponding test.

### 2.2 Decision Drivers (top 3)

1. **Attach-readiness for `spatial_engine`** — outputs validate cleanly against the engine's loader and schema. Without this, the project has no purpose.
2. **Capture-backend availability on the team's hardware** — RoomPlan needs an iPhone Pro / iPad Pro (LiDAR), Polycam works on most modern phones with their own scan, COLMAP works from any video but is slow and scale-ambiguous. Whichever the team can run *today* defines v0.1.
3. **Schema stability cost** — if we lock `room.yaml` too early, every schema bump cascades into `spatial_engine`. If we lock it too late, downstream code on both sides churns. Pick an explicit window.

### 2.3 Viable Options per Major Decision

#### Q1 — Capture backend priority (≥2 viable options)

| Option | Pros | Cons |
|---|---|---|
| **A. RoomPlan-first** *(RECOMMENDED v0.1)* | Apple RoomPlan emits structured walls/floors/openings as parametric primitives; LiDAR gives metric scale; USDZ is documented and has open parsers. Most "scan a room" results in literature use RoomPlan. | iOS / iPad Pro only at capture time; not available on Linux dev machines (capture artifact is portable, though). |
| **B. Polycam-first** | Cross-platform capture (iOS + Android); also exports USDZ/OBJ; users likely already have it. | Output is a textured mesh, not parametric walls — we have to *re-detect* walls from the mesh. More CV work in v0.1. |
| C. COLMAP-only | Works from any phone video; no proprietary tool. | No metric scale unless ArUco/known-size cue; slow (minutes-to-hours per scan); scale ambiguity is a research problem, not a v0.1 problem. |

**Decision: A first-class, B as supported secondary, C as fallback.** RoomPlan's parametric output dramatically reduces v0.1 CV scope; B reuses the same `RoomModel` with a wall-detection step; C is gated behind an `--experimental` flag.

#### Q2 — Internal room representation (≥2 viable options)

| Option | Pros | Cons |
|---|---|---|
| **A. Polygon (2.5D) + ceiling height** *(RECOMMENDED)* | Captures non-shoebox rooms (L-shape, alcoves) which are common in exhibition spaces; cheap to compute (project mesh to floor plane → polygonize); maps cleanly to engine's future `RoomGeometry` and to room-acoustics tools. | Slightly more code than shoebox-only. |
| B. Shoebox-only (axis-aligned bbox) | Simplest possible model; matches naive 3D-reverb "shoebox" assumptions. | Most exhibition venues are NOT shoebox; failure mode is silent (room model wrong, listener and reflections incorrect). |
| C. Polygon + textured mesh | Maximum fidelity; preserves visual; supports future material classification from texture. | Scope creep for v0.1; `RoomModel` becomes large; not needed for v0.1 placement decisions. |

**Decision: A.** Polygon (2.5D) — a closed 2D floor polygon plus scalar `ceiling_height_m`, plus a list of `Surface` annotations referencing polygon edges + ceiling/floor. Mesh is kept as an *optional sidecar* (`room.glb`) for visualization only; the engine never reads it.

#### Q3 — Placement algorithm priority (≥2 viable options)

| Option | Pros | Cons |
|---|---|---|
| **A. VBAP-first → DBAP → WFS → Ambisonics** *(RECOMMENDED)* | VBAP equal-angle ring is the simplest deterministic placement; matches the engine's most-developed rendering algorithm path; serves as a smoke-test for the full pipeline. DBAP is "place anywhere, derive gains" — robust to irregular venues. WFS has the strictest geometric constraint (λ/2 spacing) and ships last. | Ambisonics buyers wait until v0.3. |
| B. WFS-first | Highest geometric ambition; would shake out the placement engine hardest. | λ/2 constraint at f_max=8 kHz means ~2 cm spacing — impossible in a real venue without a custom array. v0.1 demo would not run on the team's lab. |
| C. Ambisonics-first (equal-spaced t-design dome) | Mathematically clean; well-understood placement. | Ambisonics not yet in `spatial_engine/require.md` mandatory list (object-based + WFS/VBAP/DBAP are mandatory). Would ship a renderer roomestim can't validate against. |

**Decision: A.** Order: VBAP → DBAP → WFS → Ambisonics (Ambisonics deferred to v0.3 unless engine-side prio changes).

#### Q5 — `room.yaml` schema lock-in timing (≥2 viable options)

| Option | Pros | Cons |
|---|---|---|
| **A. Propose v1.0 schema in roomestim v0.1; mark `version: "0.1"`; propose to engine in roomestim v0.2** *(RECOMMENDED)* | Forces design discipline early; engineers on both sides see the contract immediately; `version` field allows breakage with strict-validation flag. Engine integration follows once roomestim has produced ≥10 real `room.yaml` files in CI. | Risk of revising schema once engine team weighs in — but `version` field anticipates that. |
| B. Lock in roomestim v0.1 AND propose to engine v0.1 (write `proto/room_schema.json` upstream simultaneously) | Single canonical source of truth from day one. | Asks engine team to accept a schema before it has been exercised by any caller. Cross-repo PR coordination tax. |
| C. Keep schema fully experimental until v0.2 (no `version`, no JSON Schema) | Maximum flexibility. | Downstream consumers (including spatial_engine prototypes) have no contract; every change breaks them silently. |

**Decision: A.** roomestim v0.1 ships a frozen-API `room.yaml` with `version: "0.1"` and a JSON Schema in `roomestim/proto/room_schema.json`. roomestim v0.2 (after ≥10 real `room.yaml` produced and reviewed) proposes copy to `spatial_engine/proto/room_schema.json` via cross-repo PR.

#### Q4 — Validation strategy (no ≥2 options needed; design choice)

**Decision: Hybrid.**

- **Synthetic GT (primary CI)**: procedural shoebox + L-shape + non-convex rooms with known wall coordinates and a planted listener-area; adapter-free entrypoint takes a `RoomModel` directly. Tests assert `RoomModel.floor_polygon` matches GT to <5 cm Hausdorff distance and speaker placement matches the VBAP/DBAP/WFS expected geometry to <1° / <λ/4.
- **Real measurement (acceptance gate)**: one capture of the lab room described in `spatial_engine/docs/lab_setup.md` (RoomPlan scan from an iPad Pro). Manual ground-truth: tape-measured wall corners (3 corners minimum) and a tape-measured speaker layout post-placement. v0.1 ships if and only if the lab scan produces a `room.yaml` whose corner-vs-tape error is <10 cm and a `layout.yaml` whose speaker positions are within ±5° angular and ±10 cm radial of the actual placed speakers.

#### Q6 — User interaction (no ≥2 options needed)

**Decision: Pure CLI in v0.1**, with an optional `--preview` flag that opens a matplotlib top-down floor plan + speaker overlay PNG (saved, not interactive). 3D Open3D viewer is deferred to v0.3. Reasoning: v0.1 must be CI-runnable and headless; an interactive viewer is a wishlist item that would gate the milestone on Qt/Open3D portability.

#### Q7 — Repo bootstrap (no ≥2 options needed)

**Decision: Separate git repo at `/home/seung/mmhoa/roomestim/`.** Matches `vid2spatial`/`claude_text2traj` precedent; allows independent versioning and pinning before submodule attachment. README documents the eventual submodule path (`spatial_engine/third_party/roomestim/` or similar) but does not block on it.

#### Q8 — Tech stack (no ≥2 options needed)

**Decision: Python ≥3.10, setuptools build, optional-dependency groups, pyproject.toml mirroring `claude_text2traj`.** Locked deps:

- Core: `numpy>=1.24`, `pyyaml>=6`, `jsonschema>=4`, `shapely>=2.0` (polygon ops), `scipy>=1.10` (KDTree, optimization for placement).
- USDZ/OBJ parse: `trimesh>=4.0` (handles OBJ + USDZ via plugin), `pyusd` optional (Apple USDZ via `pxr.Usd` if available — gated behind `usd` extra).
- COLMAP (experimental): `pycolmap>=0.6` under `colmap` extra.
- Visualization: `matplotlib>=3.7` under `viz` extra.
- Dev: `pytest>=7`, `pytest-mock`, `hypothesis>=6`, `ruff>=0.5` (lint+format), `mypy>=1.8` (typed APIs only).

Rationale per dep: `shapely` is the de-facto polygon library and avoids reimplementing wall-segment intersection; `trimesh` parses OBJ + GLB and has USDZ via optional pyusd; `pycolmap` is the official COLMAP binding; `jsonschema` is already used by `claude_text2traj` for the trajectory schema and gives the same validation discipline.

#### Q9 — v0.1 milestone definition (no ≥2 options needed)

**Decision: end-to-end demo on the lab room.** v0.1 ships when:

1. `roomestim ingest --backend roomplan tests/fixtures/lab_room.usdz` produces a `RoomModel` whose floor-polygon corner error vs hand-tape ground truth is <10 cm.
2. `roomestim place --algorithm vbap --n-speakers 8` produces a `layout.yaml` that loads cleanly through a small Python harness calling into `spatial_engine`'s loader (or, if no Python binding yet, validates against `proto/geometry_schema.json` AND has a `pytest` that subprocess-invokes `spatial_engine/build/.../layout_loader_smoke` if available).
3. `roomestim export --room-yaml --layout-yaml` writes both files; `room.yaml` validates against `roomestim/proto/room_schema.json`.
4. CI green on Ubuntu 22.04 (matches `spatial_engine/docs/lab_setup.md`) with optional-dep groups installable cleanly.

---

## 3. Acceptance Criteria

> All numeric tolerances are upper bounds. Each criterion has a corresponding test path indicated in §10.

1. **A1 — `layout.yaml` schema-validates AND is finite.** Generated `layout.yaml` files validate against `/home/seung/mmhoa/spatial_engine/proto/geometry_schema.json` with `jsonschema` strict mode. Required fields `version`, `name`, `speakers[]` present; per-speaker `id` ≥ 1, `channel` ≥ 1; spherical/Cartesian mutual exclusion respected. **Finiteness invariant** (REVISION iter 2/5, item #6): every numeric leaf passes `numpy.isfinite`; non-finite values raise `kErrNonFiniteValue` before write. Test: `tests/test_export_layout_yaml.py` (incl. `test_rejects_nonfinite`).
2. **A2 — `layout.yaml` parses cleanly through engine loader.** A subprocess test invokes a small C++ smoke binary (`spatial_engine/build/.../layout_loader_smoke`) when present; if not present, falls back to schema-validation only and emits a SKIP warning. Test: `tests/test_engine_roundtrip.py` (skips if engine binary not built).
3. **A3 — `room.yaml` schema-validates AND is finite.** Every produced `room.yaml` validates against `roomestim/proto/room_schema.json` (Stage 2 LOCKED) or `roomestim/proto/room_schema.draft.json` (Stage 1 DRAFT) with `jsonschema` strict mode, per the §6.0 two-stage lock. **Finiteness invariant** (REVISION iter 2/5, item #6): every numeric leaf passes `numpy.isfinite`; non-finite values raise `kErrNonFiniteValue` before write. Test: `tests/test_export_room_yaml.py` (incl. `test_rejects_nonfinite`).
4. **A4 — Coordinate-frame contract.** All `az_deg` / `el_deg` / `xyz` values follow `spatial_engine/docs/coordinate_convention.md` (RIGHT=+az, UP=+el, z=front). A property test (hypothesis) for any random `(az_deg, el_deg, dist_m)` round-trips through `cartesian_to_pipeline` Python port to within 1e-4. Test: `tests/test_coords_roundtrip.py`.
5. **A5 — VBAP equal-angle ring placement deviation.** For `place_vbap_ring(n=8, radius=2.0m, el_deg=0)`, max angular deviation from ideal (45°·k offset) is <1°. Channel indices are 1..8 monotonically. Test: `tests/test_placement_vbap.py`.
6. **A6 — VBAP dome placement.** `place_vbap_dome(n_lower=8, n_upper=8, el_lower=0°, el_upper=30°)` produces 16 speakers, 8 at each elevation, equal-angle within elevation ring (deviation <1°). Test: `tests/test_placement_vbap.py`.
7. **A7 — DBAP coverage on irregular surface set.** `place_dbap(mount_surfaces=…, n_speakers=12)` returns positions all on declared mount surfaces (point-on-polygon test passes for each), and listener-area coverage gain map has min value > -3 dB at any sample point. Test: `tests/test_placement_dbap.py`.
8. **A8 — WFS spacing constraint AND aliasing-frequency surfacing.** `place_wfs(front_wall, spacing_m, f_max_hz)` rejects `spacing_m > 343.0/(2*f_max_hz)` with named error `kErrWfsSpacingTooLarge`. **Additionally** (REVISION iter 2/5, item #4): every successful WFS `PlacementResult` must carry a finite, strictly positive `wfs_f_alias_hz = 343.0 / (2 * spacing_m)` field; the produced `layout.yaml` must include `x_wfs_f_alias_hz` at the top level (extension key per §6.1) with the same value. Test: `tests/test_placement_wfs.py` (incl. `test_alias_freq_finite_positive` and `test_layout_yaml_has_x_wfs_f_alias_hz`).
9. **A9 — RoomPlan adapter parses sample USDZ.** Given `tests/fixtures/lab_room.usdz`, `roomplan_adapter.parse(...)` returns a `RoomModel` with: ≥4 wall segments, `ceiling_height_m` within ±10 cm of fixture metadata, floor-polygon area within ±5% of fixture metadata. Test: `tests/test_adapter_roomplan.py`.
10. **A10 — Lab-scan acceptance gate.** Manually-captured `tests/fixtures/lab_real.usdz` (from `lab_setup.md` room) produces a `room.yaml` whose listed corner positions are <10 cm from tape-measured ground truth (3 corners), and a VBAP-8 `layout.yaml` whose speaker positions are within ±5° azimuth and ±10 cm radial of the eventually-placed speakers. Test: `tests/test_acceptance_lab_room.py` (marked `@pytest.mark.lab`, skipped in default CI).
11. **A11 — Surface-material absorption assignment.** Every surface in `RoomModel.surfaces` has a `material_label` from a closed enum (`{wall_painted, wall_concrete, wood_floor, carpet, glass, ceiling_acoustic_tile, …}`) and an associated `absorption_500hz` float in [0,1]. RT60-Sabine estimate from these is within ±20% of a reference value for the lab room. Test: `tests/test_room_acoustics.py`.
12. **A12 — Idempotent CLI.** Running the full pipeline twice on the same input produces byte-identical `room.yaml` and `layout.yaml`. Test: `tests/test_cli_idempotent.py`.
13. **A13 — Headless CI.** Full test suite (excluding `@pytest.mark.lab`) runs green on Ubuntu 22.04 in <120 s with only `pip install -e .[dev]`. Test: GitHub Actions CI workflow.
14. **A14 — No file writes outside `roomestim/` and `--out-dir`.** A test asserts the CLI does not modify `spatial_engine/` or any other path. Test: `tests/test_no_external_writes.py`.
15. **A15 — Coords parity with engine C++ helpers** (REVISION iter 2/5, item #2; resolves Architect T1). When env var `SPATIAL_ENGINE_BUILD_DIR` is set, `tests/test_coords_engine_parity.py` subprocess-invokes a tiny C++ harness exposing `spe::coords::yaml_speaker_to_cartesian` and `spe::coords::cartesian_to_pipeline` and asserts numerical equality with the Python `roomestim.coords` port across **≥1000 Hypothesis-generated `(az_deg ∈ [-180, 180], el_deg ∈ [-90, 90], dist_m ∈ (0, 50])` triples** to **≤1e-5 absolute** on each output component. SKIPs with a warning if the env var is unset (mirrors A2's pattern). Test: `tests/test_coords_engine_parity.py`.
16. **A16 — Noisy-synthetic placement-degradation test** (REVISION iter 2/5, item #3; resolves Architect T3; **runs in default `pytest -m "not lab"` lane, NOT `@pytest.mark.lab`**). Inject ±3 cm uniform vertex noise on `floor_polygon` and ±1° random yaw rotation on the synthetic shoebox + L-shape fixtures from `tests/fixtures/synthetic_rooms.py`. Run VBAP-8 ring placement under both clean and noisy inputs. Cite the no-noise baseline value (synthetic shoebox: max angular deviation = 0.0° by construction; L-shape: max angular deviation < 0.5°). Assert noisy-input max angular deviation **<2× the clean baseline** with a strict floor of 1.0° to avoid divide-by-zero on perfect-shoebox baselines. Test: `tests/test_placement_under_noise.py`.

---

## 4. Implementation Steps

### Directory tree (proposed)

```
/home/seung/mmhoa/roomestim/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml
├── proto/
│   └── room_schema.json                # Owns the room.yaml JSON Schema
├── roomestim/                           # package root
│   ├── __init__.py
│   ├── __main__.py                      # CLI entrypoint via `python -m roomestim`
│   ├── cli.py                           # argparse-based CLI
│   ├── coords.py                        # Python port of spe::coords helpers
│   ├── model.py                         # RoomModel, ListenerArea, Surface, MountSurface, PlacementResult
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py                      # CaptureAdapter protocol
│   │   ├── roomplan.py                  # USDZ/JSON parser
│   │   ├── polycam.py                   # USDZ/OBJ+MTL parser, mesh→polygon
│   │   └── colmap.py                    # experimental; gated behind `colmap` extra
│   ├── reconstruct/
│   │   ├── __init__.py
│   │   ├── floor_polygon.py             # Mesh → 2.5D polygon (alpha-shape on floor-projected verts)
│   │   ├── walls.py                     # Plane segmentation → wall segments
│   │   ├── listener_area.py             # Centre-of-room or user-specified rectangle/polygon
│   │   └── materials.py                 # Surface labels → absorption coefficients
│   ├── place/
│   │   ├── __init__.py
│   │   ├── algorithm.py                 # enum TargetAlgorithm {VBAP, DBAP, WFS, AMBISONICS}
│   │   ├── vbap.py                      # ring + dome placements
│   │   ├── dbap.py                      # greedy coverage on mount surfaces
│   │   ├── wfs.py                       # linear array, λ/2 constraint
│   │   └── ambisonics.py                # deferred (v0.3); stub raises NotImplementedError
│   ├── export/
│   │   ├── __init__.py
│   │   ├── layout_yaml.py               # PlacementResult → layout.yaml
│   │   └── room_yaml.py                 # RoomModel → room.yaml
│   └── viz/
│       ├── __init__.py
│       └── floorplan_png.py             # matplotlib top-down render
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── lab_room.usdz                # synthetic GT for CI
│   │   ├── lab_real.usdz                # real lab scan, .gitignored, manual download
│   │   └── synthetic_rooms.py           # procedural shoebox/L-shape generators
│   ├── test_adapter_roomplan.py
│   ├── test_adapter_polycam.py
│   ├── test_reconstruct_polygon.py
│   ├── test_placement_vbap.py
│   ├── test_placement_dbap.py
│   ├── test_placement_wfs.py
│   ├── test_export_layout_yaml.py
│   ├── test_export_room_yaml.py
│   ├── test_engine_roundtrip.py         # subprocess smoke against spatial_engine binary
│   ├── test_coords_roundtrip.py
│   ├── test_room_acoustics.py
│   ├── test_cli_idempotent.py
│   ├── test_no_external_writes.py
│   └── test_acceptance_lab_room.py      # @pytest.mark.lab; skipped in default CI
└── docs/
    ├── architecture.md
    ├── coordinate_convention.md         # cross-references spatial_engine doc
    ├── room_yaml_spec.md                # human-readable spec for the new schema
    └── adr/
        ├── 0001-capture-backend-priority.md
        ├── 0002-room-representation.md
        ├── 0003-placement-algorithm-priority.md
        ├── 0004-room-yaml-schema-lockin.md
        └── 0005-tech-stack.md
```

### Steps

**P0 — Repo bootstrap and contracts (1 day)**

- Create `pyproject.toml` mirroring `claude_text2traj` style: setuptools, optional-deps `[dev]`, `[viz]`, `[colmap]`, `[usd]`, pytest markers `live`, `lab`. File: `roomestim/pyproject.toml`.
- Create `roomestim/__init__.py`, `roomestim/cli.py` skeleton.
- Author `proto/room_schema.json` (see §6 for content).
- Author `roomestim/coords.py` — Python port of helpers from `spatial_engine/core/src/coords/Coords.h`. WHY a port: roomestim is Python-only at v0.1, no pybind11 yet.
- Author `tests/test_coords_roundtrip.py` (A4 acceptance criterion).
- Author 5 ADRs (see directory tree above) — short form following `spatial_engine/docs/adr/0001-process-model.md` style.
- **Acceptance**: `pip install -e .[dev]` green; `pytest tests/test_coords_roundtrip.py` green.

**P1 — Internal data model + CaptureAdapter protocol (1 day) — P0/P1 GATE before P4**

- Author `roomestim/model.py` (see §5 for sketches).
- Author `tests/fixtures/synthetic_rooms.py` — procedural shoebox + L-shape `RoomModel` generators (no adapter needed).
- Author `roomestim/export/room_yaml.py` and `tests/test_export_room_yaml.py` (A3, including the `kErrNonFiniteValue` test per item #6).
- **Author `roomestim/adapters/base.py` — `CaptureAdapter` Protocol exactly as specified below** (REVISION iter 2/5, item #5). NO backend-specific types in the signature:

  ```python
  # roomestim/adapters/base.py
  from pathlib import Path
  from typing import Protocol, runtime_checkable
  from dataclasses import dataclass

  @dataclass(frozen=True)
  class ScaleAnchor:
      """Optional metric anchor for scale-ambiguous backends (COLMAP).
      Backends that emit metric scale natively (RoomPlan, Polycam) ignore this."""
      type: str               # "aruco" | "known_distance" | "user_provided"
      length_m: float

  @runtime_checkable
  class CaptureAdapter(Protocol):
      def parse(self, path: Path, *, scale_anchor: ScaleAnchor | None = None) -> "RoomModel":
          ...
  ```

- **Acceptance gate (must pass before P4 starts)**: A3 green; protocol type-checks under `mypy --strict`; `tests/test_adapter_protocol.py` asserts every concrete adapter (`RoomPlanAdapter`, `PolycamAdapter`, `ColmapAdapter`) is `isinstance(adapter, CaptureAdapter)` via `runtime_checkable`. Can produce `room.yaml` from a synthetic `RoomModel`.

**P2 — Layout export + engine round-trip (1 day)**

- Author `roomestim/export/layout_yaml.py` — emits `layout.yaml` matching `spatial_engine/configs/lab_8ch.yaml` shape (spherical form preferred, Cartesian optional).
- Author `tests/test_export_layout_yaml.py` (A1) using `jsonschema` against `spatial_engine/proto/geometry_schema.json` (read at test time, never copied).
- Author `tests/test_engine_roundtrip.py` (A2). The test discovers an engine binary via env var `SPATIAL_ENGINE_BUILD_DIR` and SKIPs if absent.
- **Acceptance**: A1 green; A2 green-or-skip.

**P3 — Placement engine for VBAP and DBAP (2 days)**

- Author `roomestim/place/algorithm.py` (TargetAlgorithm enum, dispatch entry).
- Author `roomestim/place/vbap.py`: `place_vbap_ring(n, radius_m, el_deg, listener_pos)` and `place_vbap_dome(...)`.
- Author `roomestim/place/dbap.py`: greedy coverage solver on `MountSurface` set. Uses `scipy.optimize` for gain-uniformity objective.
- Tests: A5, A6, A7.
- **Acceptance**: A5–A7 green.

**P4 — RoomPlan adapter + reconstruction (2–3 days)**

- Author `roomestim/adapters/roomplan.py`. Strategy: prefer the JSON sidecar that RoomPlan emits alongside USDZ when available (parametric walls); fall back to USDZ mesh parse via `trimesh` + `pyusd` (under `usd` extra).
- Author `roomestim/reconstruct/floor_polygon.py` (mesh→polygon via floor-plane projection + alpha-shape via `shapely`).
- Author `roomestim/reconstruct/walls.py` (RANSAC plane segmentation if needed for Polycam path).
- Author `roomestim/reconstruct/listener_area.py` (default: centre-of-room rectangle 1.5 × 1.5 m; user-overridable via CLI).
- Author `roomestim/reconstruct/materials.py` (default surface labels keyed by detected wall/floor/ceiling; closed enum from §3 A11).
- Generate `tests/fixtures/lab_room.usdz` via a tiny Apple USDZ writer or use a hand-authored fixture; or, if too costly, ship a JSON sidecar mock that exercises the same parser path.
- Tests: A9, A11.
- **Acceptance**: A9, A11 green.

**P5 — WFS placement + Polycam adapter (2 days)**

- Author `roomestim/place/wfs.py` with the λ/2 constraint check (A8).
- Author `roomestim/adapters/polycam.py`. Polycam exports OBJ+MTL or USDZ — use `trimesh` for OBJ; reuse `floor_polygon.py` for wall detection.
- Tests: A8, `tests/test_adapter_polycam.py`.
- **Acceptance**: A8 green; Polycam fixture produces a valid `RoomModel`.

**P6 — CLI, viz, and acceptance gate (1 day)**

- Wire `roomestim/cli.py`: `roomestim ingest`, `roomestim place`, `roomestim export`, `roomestim run` (composite).
- Author `roomestim/viz/floorplan_png.py`: top-down PNG with walls + listener area + speakers.
- Idempotency test (A12), no-external-writes test (A14).
- Capture `tests/fixtures/lab_real.usdz` (manual; not in CI), write `tests/test_acceptance_lab_room.py` (A10) under `@pytest.mark.lab`.
- CI workflow (A13) at `.github/workflows/ci.yml`.
- **Acceptance**: A10 (manual-run gate), A12, A13, A14 all green.

**P7 — Docs and ADR finalization (0.5 day)**

- Author `docs/architecture.md`, `docs/room_yaml_spec.md`.
- Finalize the 5 ADRs (Status: Accepted; add Falsifier and Follow-ups sections).
- README with quickstart, capture-backend matrix, attach-to-spatial_engine pointer.

**Total estimated effort: 9–10 working days for v0.1.**

---

## 5. Internal Data Model

> All in `roomestim/model.py`. Use `dataclasses` (or `pydantic` if validation is wanted later — defer for now). Coordinate frame: VBAP layout-frame from `spatial_engine/docs/coordinate_convention.md` — listener at origin, x=right, y=up, z=front, metres.

```python
# roomestim/model.py — sketch only, not for execution

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

# ----- Surface materials (closed enum; absorption table in materials.py) -----

class MaterialLabel(str, Enum):
    WALL_PAINTED = "wall_painted"
    WALL_CONCRETE = "wall_concrete"
    WOOD_FLOOR = "wood_floor"
    CARPET = "carpet"
    GLASS = "glass"
    CEILING_ACOUSTIC_TILE = "ceiling_acoustic_tile"
    CEILING_DRYWALL = "ceiling_drywall"
    UNKNOWN = "unknown"

# ----- Geometry primitives -----

@dataclass(frozen=True)
class Point2:    # floor-plane (x_right, z_front) in metres
    x: float
    z: float

@dataclass(frozen=True)
class Point3:    # listener-frame Cartesian (x=right, y=up, z=front)
    x: float
    y: float
    z: float

# ----- Surfaces -----

SurfaceKind = Literal["wall", "floor", "ceiling"]

@dataclass
class Surface:
    """A bounded planar surface in listener-frame coordinates.
    Walls are vertical rectangles; floor/ceiling are arbitrary polygons."""
    kind: SurfaceKind
    polygon: list[Point3]            # CCW-ordered when viewed from inside the room
    material: MaterialLabel
    absorption_500hz: float          # [0, 1], from materials table

@dataclass
class MountSurface:
    """A subset-of-Surface where speakers may be placed.
    Used by DBAP placement; usually walls + ceiling."""
    surface_index: int               # references RoomModel.surfaces[i]
    inset_m: float = 0.10            # inset from edges to avoid corner mounting

# ----- Listener area -----

@dataclass
class ListenerArea:
    """The region occupied by listeners. Speakers point at the centroid by default."""
    polygon: list[Point2]            # on the floor plane (y=0)
    centroid: Point2
    height_m: float = 1.20           # ear height of seated listener

# ----- Room model (the stable internal abstraction) -----

@dataclass
class RoomModel:
    name: str                                # human-readable label
    floor_polygon: list[Point2]              # CCW
    ceiling_height_m: float                  # uniform; non-uniform is v0.3
    surfaces: list[Surface]
    listener_area: ListenerArea
    schema_version: str = "0.1"              # roomestim's own schema version

# ----- Placement output -----

@dataclass
class PlacedSpeaker:
    channel: int                             # 1-based; matches engine's Speaker.channel
    position: Point3                         # listener-frame metres
    aim_direction: Point3 | None = None      # unit vector; default: -position (point at listener)
    notes: str = ""

@dataclass
class PlacementResult:
    target_algorithm: str                    # "VBAP" | "WFS" | "DBAP" | "AMBISONICS"
    regularity_hint: str                     # "LINEAR" | "CIRCULAR" | "PLANAR_GRID" | "IRREGULAR"
    speakers: list[PlacedSpeaker]
    layout_name: str
    layout_version: str = "1.0"              # matches spatial_engine schema version
    # REVISION iter 2/5, item #4 — WFS aliasing-frequency surfacing.
    # MUST be a finite, strictly positive float when target_algorithm == "WFS".
    # MUST be None for VBAP/DBAP/AMBISONICS.
    # Exported into layout.yaml as top-level extension key `x_wfs_f_alias_hz`
    # (geometry_schema.json:8 declares additionalProperties: true at root).
    wfs_f_alias_hz: float | None = None

```

### Mapping to engine primitives

| roomestim type                     | maps to                                                                                                | notes |
|---|---|---|
| `PlacementResult.speakers[i]`      | `spe::geometry::Speaker { channel, x, y, z }` (`SpeakerLayout.h`)                                      | One-to-one. `channel` field name preserved. |
| `PlacementResult.regularity_hint`  | `spe::geometry::Regularity` enum (`SpeakerLayout.h`)                                                   | String→enum on engine side; matches `geometry_schema.json` `regularity_hint`. |
| `PlacementResult` → YAML           | parsed by `spe::geometry::load_layout()` (`LayoutLoader.cpp:16`)                                       | Required: `version`, `name`, `speakers[]`. |
| `RoomModel`                        | future `spe::geometry::RoomGeometry` (proposed; lives at `spatial_engine/core/src/geometry/RoomGeometry.{h,cpp}` — see §11) | Not yet defined upstream; we propose it via `room.yaml`. |
| `Surface.material/absorption_500hz`| feeds future `RoomReverb` (spec `require.md` §3 "3D 리버브 또는 IR 리버브 지원")                       | RT60 estimation via Sabine equation; see materials.py. |

---

## 6. `room.yaml` Schema (proposed)

> Owned by roomestim v0.1 at `roomestim/proto/room_schema.json`. To be proposed upstream to `spatial_engine/proto/room_schema.json` in roomestim v0.2 after ≥10 real `room.yaml` files have been produced and reviewed. Coordinate frame: VBAP layout-frame (`spatial_engine/docs/coordinate_convention.md`).

### 6.0 Two-stage schema lock (REVISION iter 2/5, item #1)

The schema ships in **two distinct stages** within v0.1 to prevent premature lock-down while still giving downstream consumers a real contract:

| Stage | `version` value | `additionalProperties` | When | Gating criterion |
|---|---|---|---|---|
| **Stage 1 — DRAFT** | `"0.1-draft"` | `true` (permissive) | Initial v0.1 ship | Default for all CI fixtures and synthetic-room tests until the lab fixture has produced a real `room.yaml`. |
| **Stage 2 — LOCKED** | `"0.1"` | `false` (strict) | After A10 lab fixture has produced ≥1 real `room.yaml` from `tests/fixtures/lab_real.usdz` and that file has been reviewed and committed as `tests/fixtures/lab_real_room.yaml` | Acceptance gate: schema-validation pass against the `version: "0.1"` strict variant; reviewer sign-off on the locked schema. |

**Falsifier-style milestone gate**: if after Stage 2 lock, the next ≥3 real-world `room.yaml` files produced by independent captures require schema patches (i.e. fields the lock didn't anticipate), revert to Stage 1 (`additionalProperties: true`) and reopen the schema for v0.2.

The repo ships **both** schema variants in `roomestim/proto/`:
- `room_schema.draft.json` — Stage 1 (permissive)
- `room_schema.json` — Stage 2 (strict, locked)

Tests select via `--schema-stage draft|locked` (default `draft` until A10 passes; flips to `locked` post-gate).

```yaml
# Example room.yaml emitted by roomestim (Stage 1 draft form)
version: "0.1-draft"
name: "lab_main_room"
schema: "https://roomestim/proto/room_schema.json"
ceiling_height_m: 2.85
floor_polygon:
  - { x: -2.50, z: -3.00 }
  - { x:  2.50, z: -3.00 }
  - { x:  2.50, z:  3.00 }
  - { x: -2.50, z:  3.00 }
listener_area:
  centroid: { x: 0.0, z: 0.0 }
  polygon:
    - { x: -0.75, z: -0.75 }
    - { x:  0.75, z: -0.75 }
    - { x:  0.75, z:  0.75 }
    - { x: -0.75, z:  0.75 }
  height_m: 1.20
surfaces:
  - kind: floor
    material: wood_floor
    absorption_500hz: 0.10
    polygon: [...]   # mirrors floor_polygon, lifted to y=0
  - kind: ceiling
    material: ceiling_acoustic_tile
    absorption_500hz: 0.55
    polygon: [...]   # at y=ceiling_height_m
  - kind: wall
    material: wall_painted
    absorption_500hz: 0.05
    polygon: [...]   # 4 corners, vertical rectangle
mount_surfaces:
  - surface_index: 2     # references surfaces[2]
    inset_m: 0.10
```

### Schema (JSON Schema 2020-12 sketch)

> Two variants ship per §6.0. The diff between Stage 1 (DRAFT) and Stage 2 (LOCKED) is:
> - `properties.version.const`: `"0.1-draft"` (Stage 1) vs `"0.1"` (Stage 2)
> - `additionalProperties`: `true` at root (Stage 1) vs `false` (Stage 2)
> The Stage 2 variant is shown below; Stage 1 is mechanically derived (relax `additionalProperties` to `true` and replace the `version.const` value).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://roomestim/proto/room_schema.json",
  "title": "RoomModel",
  "type": "object",
  "required": ["version", "name", "ceiling_height_m", "floor_polygon",
               "listener_area", "surfaces"],
  "additionalProperties": false,
  "properties": {
    "version":           { "type": "string", "const": "0.1" },
    "name":              { "type": "string", "minLength": 1 },
    "schema":            { "type": "string", "format": "uri" },
    "ceiling_height_m":  { "type": "number", "exclusiveMinimum": 0,
                            "maximum": 30.0 },
    "floor_polygon": {
      "type": "array", "minItems": 3,
      "items": {
        "type": "object",
        "required": ["x", "z"], "additionalProperties": false,
        "properties": { "x": {"type": "number"}, "z": {"type": "number"} }
      }
    },
    "listener_area": {
      "type": "object",
      "required": ["centroid", "polygon", "height_m"],
      "additionalProperties": false,
      "properties": {
        "centroid": { "$ref": "#/$defs/point2" },
        "polygon":  { "type": "array", "minItems": 3,
                      "items": { "$ref": "#/$defs/point2" } },
        "height_m": { "type": "number", "exclusiveMinimum": 0,
                       "maximum": 3.0 }
      }
    },
    "surfaces": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object",
        "required": ["kind", "material", "absorption_500hz", "polygon"],
        "additionalProperties": false,
        "properties": {
          "kind":     { "type": "string",
                          "enum": ["wall", "floor", "ceiling"] },
          "material": { "type": "string",
                          "enum": ["wall_painted", "wall_concrete",
                                   "wood_floor", "carpet", "glass",
                                   "ceiling_acoustic_tile",
                                   "ceiling_drywall", "unknown"] },
          "absorption_500hz": { "type": "number",
                                  "minimum": 0.0, "maximum": 1.0 },
          "polygon": { "type": "array", "minItems": 3,
                          "items": { "$ref": "#/$defs/point3" } }
        }
      }
    },
    "mount_surfaces": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["surface_index"],
        "additionalProperties": false,
        "properties": {
          "surface_index": { "type": "integer", "minimum": 0 },
          "inset_m":       { "type": "number", "minimum": 0.0,
                              "default": 0.10 }
        }
      }
    },
    "wfs_baseline_edge": {
      "description": "Optional in 0.1-draft; REQUIRED whenever a WFS placement is requested. Names a parametric edge along surfaces[surface_index].polygon as the WFS array baseline. t0/t1 are arc-length-normalised positions along the polygon perimeter (CCW), each in [0,1]. Default-populated by reconstruction (longest straight wall segment); user-overridable via `--wfs-baseline-edge`.",
      "type": "object",
      "required": ["surface_index", "t0", "t1"],
      "additionalProperties": false,
      "properties": {
        "surface_index": { "type": "integer", "minimum": 0 },
        "t0":            { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "t1":            { "type": "number", "minimum": 0.0, "maximum": 1.0 }
      }
    }
  },
  "$defs": {
    "point2": {
      "type": "object",
      "required": ["x", "z"], "additionalProperties": false,
      "properties": { "x": {"type": "number"}, "z": {"type": "number"} }
    },
    "point3": {
      "type": "object",
      "required": ["x", "y", "z"], "additionalProperties": false,
      "properties": {
        "x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}
      }
    }
  }
}
```

**Why these properties:**
- `version` mirrors `geometry_schema.json` discipline; gates breakage. Two-stage lock per §6.0.
- `floor_polygon` (2D) + `ceiling_height_m` (scalar) is the 2.5D representation per Q2.
- `surfaces[].polygon` (3D) is the canonical container — wall/floor/ceiling all use the same shape, allowing a future `RoomGeometry` C++ struct to be a uniform array of polygonal surfaces.
- `mount_surfaces` is purely advisory for the placement engine; downstream consumers (engine reverb) can ignore it.
- `material` is a **closed enum** for v0.1 (free-form labels lead to schema rot). v0.2 may extend.
- `absorption_500hz` is a single mid-band coefficient; full octave-band coefficients deferred to v0.3.
- `wfs_baseline_edge` (REVISION iter 2/5, item #7) resolves Architect's T2 (WFS edge ambiguity). Optional in `0.1-draft`; **required** when WFS placement is requested. Default-populated by reconstruction; user-overridable.

### 6.1 `layout.yaml` extension keys (REVISION iter 2/5, item #4 + #12)

`spatial_engine/proto/geometry_schema.json` declares `additionalProperties: true` at both root and per-speaker level (verified at `proto/geometry_schema.json:8` and per-speaker block). roomestim therefore emits the following extension keys, prefixed `x_` to mark them as roomestim-side metadata that the engine MAY ignore safely:

| Extension key | Scope | Type | Purpose |
|---|---|---|---|
| `x_wfs_f_alias_hz` | top-level | number > 0 | The first WFS spatial-aliasing frequency `c / (2 * spacing_m)` for the produced array. Surfaces the actual aliasing limit so engine + listener-test reports can plot it. **Required** for WFS-produced layouts (item #4). |
| `x_aim_az_deg` | per-speaker | number in [-180, 180] | Aim azimuth in the same VBAP layout-frame as `az_deg`. Default = vector from speaker → listener-area centroid. **Resolution of item #12**: ship in v0.1. |
| `x_aim_el_deg` | per-speaker | number in [-90, 90] | Aim elevation. Default = `arctan2(-y, sqrt(x²+z²))` toward listener-area centroid. |

Engine-side semantics: `LayoutLoader.cpp` does not parse these today; it ignores unknown keys (`additionalProperties: true`). roomestim does NOT propose schema changes upstream for these keys in v0.1; they are tested only via `tests/test_export_layout_yaml.py` (presence + range) and `tests/test_engine_roundtrip.py` (still loads cleanly with extension keys present, which is the cross-check that engine ignore-policy holds).

---

## 7. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **R1 — RoomPlan iOS-only at capture time** | High | Medium | Document iPhone-Pro/iPad-Pro requirement in README. Polycam (Q1 option B) is supported as cross-platform fallback. CI uses synthetic fixture, not a real device. |
| **R2 — COLMAP scale ambiguity** | High | Low (gated experimental) | COLMAP path is gated behind `[colmap]` extra and `--experimental` flag. Require either ArUco marker of known size or user-provided scale-anchor measurement. CI does not test COLMAP path. |
| **R3 — Schema drift between roomestim's `room.yaml` and engine's eventual `RoomGeometry`** | Medium | High | Q5 timing decision: ship roomestim's schema with `version: "0.1"`; do not propose to engine until v0.2. Both sides version-gate. ADR 0004 documents the contract. |
| **R4 — RT60-Sabine accuracy** | Medium | Medium | Document ±20% RT60 tolerance up front (A11). `roomestim/reconstruct/materials.py` ships an **inline** per-material absorption-coefficient table at 500 Hz, sourced from **Vorländer, "Auralization: Fundamentals of Acoustics, Modelling, Simulation, Algorithms and Acoustic Virtual Reality" (2nd ed., Springer 2020), Appendix A — Table of absorption coefficients of common building materials**. The 8 closed-enum entries are mapped 1:1 to that table's mid-band values; the citation appears as a docstring in `materials.py` and is referenced from `docs/room_yaml_spec.md`. RT60 is advisory metadata, not a renderer input at v0.1. (REVISION iter 2/5, item #8 — citation locked, no "TBD" wording.) |
| **R5 — Wall detection fails on cluttered Polycam mesh** | Medium | Medium | Ship a `--manual-walls PATH` CLI flag accepting a JSON file with the shape `{"floor_polygon": [[x, z], [x, z], …]}` — a CCW-ordered list of `[x, z]` floats in metres, mirroring §6 `floor_polygon` (just unpacked from `{x, z}` objects to `[x, z]` arrays for hand-editing). Validation: ≥3 points, CCW (assert via `shapely.geometry.Polygon(...).exterior.is_ccw`). The same shape is documented in `--help` output and `docs/architecture.md`. roomestim falls back to manual mode when RANSAC plane segmentation finds <3 walls; CI fixture covers both the success path and the fallback path (`tests/fixtures/synthetic_rooms.py::manual_walls_l_shape`). (REVISION iter 2/5, item #9a.) |
| **R6 — Engine binary not built in CI** | High | Low | A2 (engine-roundtrip test) SKIPs if `SPATIAL_ENGINE_BUILD_DIR` env var is unset; schema-validation (A1) is the unconditional gate. |
| **R7 — `pyusd` (USD parser) install friction on Linux** | Medium | Medium | Make `pyusd` an optional `[usd]` extra. RoomPlan adapter has a JSON-sidecar fallback path that does not require pyusd. CI runs both paths. |
| **R8 — Polygon order (CW vs CCW) ambiguity bugs** | Medium | Medium | Single normalize-on-load step in `model.py`: every polygon is canonicalized CCW (when viewed from inside the room) at construction. Property test asserts `shapely.geometry.Polygon(p).exterior.is_ccw`. |
| **R9 — Listener-area defaults wrong for L-shaped rooms** | Medium | Low | Default centroid is geometric centroid of the floor polygon; if the centroid is outside the polygon (concave room), use `shapely.point_on_surface(...)` instead. The fallback emits a named Python warning class **`kWarnConcaveListenerCentroid`** (defined in `roomestim/reconstruct/listener_area.py`). Unit test `tests/test_reconstruct_polygon.py::test_concave_l_shape_emits_warning` constructs a known L-shape fixture and asserts the warning is emitted via `pytest.warns(kWarnConcaveListenerCentroid)`. (REVISION iter 2/5, item #9b.) |
| **R10 — Speaker layout violates engine `min_speaker_count` invariants** | Low | High | Pre-flight check in `export/layout_yaml.py`: reject placements where `n_speakers < min_speaker_count(regularity_hint)` per `SpeakerLayout.h:38` (LINEAR≥2, CIRCULAR≥3, PLANAR_GRID≥4, IRREGULAR≥1). Named error: `kErrTooFewSpeakers`. |
| **R11 — Non-finite numerics leak into YAML output** | Low | High | Both `export/layout_yaml.py` and `export/room_yaml.py` run a `numpy.isfinite(...)` sweep over every numeric leaf before write and raise named error `kErrNonFiniteValue` on any NaN/Inf encountered. Asserted in A1 (`tests/test_export_layout_yaml.py::test_rejects_nonfinite`) and A3 (`tests/test_export_room_yaml.py::test_rejects_nonfinite`). (REVISION iter 2/5, item #6.) |
| **R12 — Coords drift between Python port and engine C++ helpers** | Medium | High | A15 parity test `tests/test_coords_engine_parity.py` compares the Python port to the engine's C++ `spe::coords::yaml_speaker_to_cartesian` / `cartesian_to_pipeline` over ≥1000 Hypothesis-generated triples to ≤1e-5 absolute when `SPATIAL_ENGINE_BUILD_DIR` is set; SKIP otherwise. Resolves Architect's T1. (REVISION iter 2/5, item #2.) |
| **R13 — Placement quality untested in CI under realistic noise** | Medium | High | A16 noisy-synthetic placement-degradation test `tests/test_placement_under_noise.py` runs in default `pytest -m "not lab"` lane; injects ±3 cm vertex noise + ±1° rotation noise and asserts placement deviation under noise <2× no-noise baseline. Resolves Architect's T3. (REVISION iter 2/5, item #3.) |

---

## 8. Verification Steps

### 8.1 Local developer flow

```bash
# Install
cd /home/seung/mmhoa/roomestim
pip install -e .[dev,viz]

# Lint + type-check
ruff check .
ruff format --check .
mypy roomestim/

# Unit tests (default CI lane; excludes lab fixture)
pytest -m "not lab" -v

# Engine round-trip (when spatial_engine is built)
SPATIAL_ENGINE_BUILD_DIR=/home/seung/mmhoa/spatial_engine/build pytest tests/test_engine_roundtrip.py -v

# Lab acceptance gate (manual; requires lab_real.usdz)
pytest -m lab tests/test_acceptance_lab_room.py -v
```

### 8.2 End-to-end smoke

```bash
# RoomPlan adapter → VBAP-8 ring → both YAMLs
python -m roomestim run \
    --backend roomplan \
    --input tests/fixtures/lab_room.usdz \
    --algorithm vbap \
    --n-speakers 8 \
    --layout-radius 2.0 \
    --out-dir /tmp/roomestim_out

# Validate outputs
python -c "
import json, yaml, jsonschema
schema_layout = json.load(open('/home/seung/mmhoa/spatial_engine/proto/geometry_schema.json'))
schema_room = json.load(open('roomestim/proto/room_schema.json'))
jsonschema.validate(yaml.safe_load(open('/tmp/roomestim_out/layout.yaml')), schema_layout)
jsonschema.validate(yaml.safe_load(open('/tmp/roomestim_out/room.yaml')), schema_room)
print('OK')
"
```

### 8.3 Cross-repo engine verification (A2 + A15)

When `spatial_engine` is built, `tests/test_engine_roundtrip.py` shells out to a tiny C++ smoke binary (one to be added in `spatial_engine` follow-up; see §11) that loads the YAML through `spe::geometry::load_layout()` and prints `OK` on success or the named error string on failure. The Python test checks for `OK\n` on stdout. If the binary is not present, the test SKIPs with a warning — A1 (pure JSON-Schema validation) remains the unconditional gate.

**A15 — Coords parity test** (REVISION iter 2/5, item #2): `tests/test_coords_engine_parity.py` follows the same gate-by-env-var pattern. When `SPATIAL_ENGINE_BUILD_DIR` is set, it locates a small C++ harness binary (proposed at `spatial_engine/build/.../coords_parity_harness`) that reads `(az_deg, el_deg, dist_m)` triples from stdin and prints back `(x, y, z)` and `(az_pipe, el_pipe, dist_pipe)`. The Python test generates ≥1000 Hypothesis-driven triples and asserts all components match `roomestim.coords` to ≤1e-5 absolute. SKIP otherwise.

### 8.4 Default-lane noisy-placement verification (A16)

`tests/test_placement_under_noise.py` runs in the unconditional `pytest -m "not lab"` lane (no env-var gate, no skip). It loads `tests/fixtures/synthetic_rooms.py::shoebox_5m_x_4m_x_2p8m` and `::l_shape_room`, applies ±3 cm uniform vertex noise + ±1° random yaw rotation (seeded RNG for determinism), runs `place_vbap_ring(n=8, radius=2.0m)`, and asserts the noisy max angular deviation is <2× the clean baseline (with a 1.0° floor to avoid divide-by-zero on perfect-shoebox cases).

### 8.4 Acceptance gate checklist (release-time)

Before tagging v0.1:
- [ ] All `pytest -m "not lab"` green on Ubuntu 22.04 + Python 3.10/3.11/3.12.
- [ ] CI workflow green on the same matrix.
- [ ] Lab-room scan acceptance test (A10) passes manually with tape-measured ground truth recorded in `tests/fixtures/lab_real_groundtruth.yaml`.
- [ ] Engine round-trip (A2) green with a freshly built `spatial_engine` checkout.
- [ ] All 5 ADRs in `docs/adr/` have `Status: Accepted`.
- [ ] README updated; `docs/room_yaml_spec.md` finalized.

---

## 9. Tech Stack Lock-in

```toml
# pyproject.toml — outline (not final content)
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "roomestim"
version = "0.1.0"
description = "Capture-to-config tool: room scan -> RoomModel + speaker placement -> spatial_engine YAMLs"
requires-python = ">=3.10"
dependencies = [
    "numpy>=1.24",
    "pyyaml>=6",
    "jsonschema>=4",
    "shapely>=2.0",
    "scipy>=1.10",
    "trimesh>=4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7",
    "pytest-mock",
    "hypothesis>=6",
    "ruff>=0.5",
    "mypy>=1.8",
]
viz   = ["matplotlib>=3.7"]
usd   = ["pyusd"]                 # Apple USDZ parametric parse
colmap= ["pycolmap>=0.6"]         # experimental fallback path

[project.scripts]
roomestim = "roomestim.cli:main"

[tool.setuptools.packages.find]
include = ["roomestim*"]
exclude = ["tests*"]

[tool.pytest.ini_options]
markers = [
    "lab: requires lab_real.usdz fixture; skipped in default CI",
]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
strict = true
files = ["roomestim"]
```

**Python version**: 3.10 floor (matches `claude_text2traj`); CI matrix 3.10/3.11/3.12.
**Lint/format**: `ruff` (one tool, fast). **Type-check**: `mypy --strict` on `roomestim/` (tests are non-strict).
**CI**: GitHub Actions, Ubuntu 22.04 (matches `spatial_engine/docs/lab_setup.md`).

---

## 10. v0.1 → v1.0 Roadmap (deferred items)

| Feature | Defer to | Reason |
|---|---|---|
| Interactive 3D viewer (Open3D / Qt) | v0.3 | Headless CI is the v0.1 priority; interactive UI is a wishlist that gates milestone on Qt portability. |
| Full COLMAP fallback (without ArUco) | v0.4 | Scale-ambiguity is a research problem; v0.1 ships with experimental flag only. |
| Octave-band absorption per surface | v0.3 | v0.1 ships single mid-band (500 Hz) which is sufficient for Sabine RT60 estimate to ±20%. |
| C++ `RoomGeometry` loader in spatial_engine | v0.2 (cross-repo PR after schema settles) | Schema must be exercised by ≥10 real `room.yaml` files first. |
| Ambisonics placement (t-design dome) | v0.3 | Not yet in `spatial_engine/require.md` mandatory list. |
| Non-uniform ceiling height | v0.3 | `ceiling_height_m` is scalar in v0.1; complex venues (vaulted ceilings) are out of scope. |
| Material classification from texture/photo (CV) | v1.0 | v0.1 uses default labels per surface kind; user can override via CLI. |
| Speaker auto-aim (toward listener-area centroid plus weighted coverage) | v0.2 | v0.1 default `aim_direction = -position` is sufficient for the 4 mandated algorithms. |
| WebGUI / Electron preview | v1.0 | Aligns with `spatial_engine`'s GUI track; out of scope for capture-side tool. |

---

## 11. Attach-to-spatial_engine Plan

> All file paths under `/home/seung/mmhoa/spatial_engine/` listed below are PROPOSALS. roomestim does not modify spatial_engine in v0.1. Cross-repo PRs land in roomestim v0.2.

### 11.1 Integration points

1. **YAML contracts** (locked by v0.1):
   - `layout.yaml` — already validated against `spatial_engine/proto/geometry_schema.json` (existing, unchanged).
   - `room.yaml` — proposed; v0.1 ships at `roomestim/proto/room_schema.json` only.

2. **Engine-side C++ loader** (proposed for spatial_engine v-next):
   - New header: `spatial_engine/core/src/geometry/RoomGeometry.h`. Mirrors `SpeakerLayout.h` style.
   - New impl: `spatial_engine/core/src/geometry/RoomGeometry.cpp`. Mirrors `LayoutLoader.cpp` style — `std::variant<RoomGeometry, std::string>`, named error strings (e.g. `kErrMissingFloorPolygon`, `kErrInvalidMaterial`, `kErrCeilingHeightOutOfRange`).
   - JSON Schema: `spatial_engine/proto/room_schema.json` — copy of `roomestim/proto/room_schema.json`, version-gated.

3. **Submodule attachment** (v0.2):
   - Option Sa: `spatial_engine/third_party/roomestim/` as git submodule pinned to a `v0.1.0` tag.
   - Option Sb: PyPI publish (`roomestim==0.1.0`) and depend in a future `spatial_engine` Python tooling layer.
   - Decision deferred; ADR will be authored in roomestim v0.2 post-feedback.

### 11.2 What stays Python-only vs gets a C++ counterpart

| Component | Python (roomestim) | C++ (spatial_engine, future) |
|---|---|---|
| Capture adapters (RoomPlan/Polycam/COLMAP) | YES | NO (capture is offline) |
| Mesh→polygon reconstruction | YES | NO (offline) |
| Speaker placement (VBAP/DBAP/WFS) | YES | NO at v0.1; engine consumes precomputed `layout.yaml` |
| `room.yaml` parsing | YES (`roomestim/export/room_yaml.py` reverse) | YES at v0.2 (`RoomGeometry.cpp`) |
| `layout.yaml` parsing | YES (export only) | YES (existing `LayoutLoader.cpp`) |
| RT60-Sabine estimate | YES (advisory metadata) | NO; engine reverb may use absorption coefficients directly |

### 11.3 Reference patterns to mirror

When authoring `RoomGeometry.{h,cpp}` upstream:
- Header style: `SpeakerLayout.h` (POD struct, `std::vector<>` members, no JUCE deps in geometry layer).
- Loader style: `LayoutLoader.cpp` — yaml-cpp parse, named error string constants in header, `std::variant<T, std::string>` result.
- Coordinate-frame discipline: route any conversion through `core/src/coords/Coords.h` (no inline trig in the loader; matches the §4 "Stereo Pan Anti-Regression Lock" pattern).
- ADR style: follow `docs/adr/0001-process-model.md` — Status / Date / Context / Decision / Drivers / Alternatives (with Steelman) / Why chosen / Consequences (+/−) / Falsifier / Follow-ups.

### 11.4 Cross-repo PR checklist (roomestim v0.2)

When proposing `room.yaml` upstream:
- [ ] ≥10 real `room.yaml` files produced and reviewed.
- [ ] No breaking changes to roomestim's `room_schema.json` for ≥4 weeks.
- [ ] Cross-repo PR: copy `proto/room_schema.json` to `spatial_engine/proto/`; add `RoomGeometry.{h,cpp}`; add unit tests mirroring `core/tests/core_unit/` style.
- [ ] ADR in `spatial_engine/docs/adr/000N-room-geometry-schema.md` referencing roomestim's ADR 0004.

---

## 12. ADR (Architecture Decision Record)

### ADR — roomestim v0.1 (this plan)

- **Status**: PROPOSED (consensus review pending: architect + critic)
- **Date**: 2026-05-03

**Decision**: Build roomestim as a standalone Python ≥3.10 tool (separate git repo at `/home/seung/mmhoa/roomestim/`) that ingests RoomPlan/Polycam/COLMAP captures, produces a 2.5D `RoomModel` (polygon + ceiling height), runs algorithm-aware speaker placement (VBAP first → DBAP → WFS → Ambisonics deferred), and exports both the existing `layout.yaml` (validated against `spatial_engine/proto/geometry_schema.json`) and a new `room.yaml` (whose JSON Schema lives at `roomestim/proto/room_schema.json` for v0.1, proposed upstream in v0.2).

**Drivers**:
1. Attach-readiness for `spatial_engine` — outputs must validate cleanly against the engine's existing loader.
2. Capture-backend availability — RoomPlan is the most structured option for v0.1.
3. Schema stability cost — early-lock with `version: "0.1"` field gates breakage; cross-repo lock waits until v0.2 after exercise.

**Alternatives considered**:
- **A — Embed roomestim inside `spatial_engine` as a Python subdir**: rejected. Cross-cutting CI; mixes capture-side (offline, slow, heavy CV deps) with realtime audio core (latency-sensitive, minimal deps). Submodule attachment in v0.2 is cleaner.
- **B — Ship `room.yaml` schema upstream in roomestim v0.1 immediately**: rejected. Schema is unexercised; cross-repo PR coordination tax; risks both repos churning together. Q5 picks the version-gated propose-later path.
- **C — Shoebox-only `RoomModel`**: rejected. Most exhibition venues are not shoeboxes; failure mode is silent (wrong reflections, wrong placement). 2.5D polygon is cheap and sufficient.
- **D — WFS-first placement**: rejected. λ/2 spacing at f_max=8 kHz is ~2 cm — incompatible with any real lab. Would block v0.1 on a research array nobody has.

**Why chosen**: The chosen path minimizes v0.1 scope (one capture backend first-class, one placement algorithm first-class, one new schema with version gate) while making the engine contract a hard test from day one. Every deferred item has an explicit owner and version (§10).

**Consequences**:
- (+) v0.1 ships in 9–10 working days.
- (+) Engine contract (A1, A2) is enforced by CI, not docs.
- (+) Submodule attachment in v0.2 has a clear cross-repo PR list.
- (−) iOS RoomPlan capture device required — partially mitigated by Polycam fallback.
- (−) `pyusd` installation friction — mitigated by JSON-sidecar fallback path.
- (−) `room.yaml` may need a v0.2 schema bump after engine team review.

**Falsifier**: If after v0.1 ships, ≥3 of 10 captured `room.yaml` files require manual editing to produce a usable placement, the `RoomModel` abstraction is wrong (likely 2.5D is insufficient or material enum too narrow). Re-open Q2 / A11 in v0.2.

**Follow-ups**:
- ADR 0001..0005 in `roomestim/docs/adr/` finalized at v0.1 release.
- Cross-repo PR proposing `room_schema.json` to `spatial_engine` in v0.2.
- Engine-side ADR for `RoomGeometry` loader to be authored in v0.2.

---

## 13. Open Questions

> Persisted to `.omc/plans/open-questions.md` per planner protocol.

- [ ] Will roomestim be attached as a git submodule under `spatial_engine/third_party/`, or distributed via PyPI? — Affects v0.2 CI and packaging story.
- [ ] Does the engine team accept the proposed `room.yaml` shape (2.5D polygon + scalar ceiling)? — Affects v0.2 cross-repo PR.
- [ ] Is the closed `material` enum (8 entries) sufficient, or do we need a free-form fallback with a `custom_label` field? — Affects A11 and v0.3.
- [ ] Are the lab speakers in `lab_setup.md` already mounted, or are we placing them as part of the v0.1 acceptance test? — Affects A10 ground-truth procedure.
- [ ] Should `aim_direction` be exported in `layout.yaml` (extension field) or only kept in roomestim's `PlacementResult`? — Affects schema extension story.

---

## 14. Verification Hand-off

This plan is ready for:
- **architect** review — focus on §5 data-model fitness, §11 attach plan correctness, §6 schema design.
- **critic** review — focus on §3 acceptance criteria measurability, §7 risk completeness, §2 RALPLAN-DR options bounded pros/cons.

After their reviews, this document is updated in place; ADR §12 transitions from `PROPOSED` to `Accepted` once both reviews pass.

---

## Executive Summary (≤200 words)

`roomestim` v0.1 is a 9–10-day Python project that converts a phone room-scan into engine-ready spatial-audio configs. Capture: RoomPlan first-class (USDZ + JSON sidecar), Polycam supported, COLMAP experimental. Internal model: 2.5D polygon (`floor_polygon` + scalar `ceiling_height_m`) plus typed surfaces with closed-enum materials. Placement: algorithm-aware (VBAP ring/dome → DBAP greedy → WFS λ/2 → Ambisonics deferred). Outputs: existing `layout.yaml` (validated against `spatial_engine/proto/geometry_schema.json` and round-tripped through `LayoutLoader.cpp`) plus a new `room.yaml` whose JSON Schema lives at `roomestim/proto/room_schema.json` with `version: "0.1"`; proposal to `spatial_engine/proto/` deferred to v0.2 after exercise. Tech: Python ≥3.10, setuptools, optional-dep groups (`dev`, `viz`, `usd`, `colmap`), `shapely`+`trimesh`+`scipy`. 14 numerically-bounded acceptance criteria gate release; CI is headless on Ubuntu 22.04; the lab-room scan is the manual acceptance gate (±10 cm walls, ±5° speaker angles). All coordinate output flows through a Python port of `spe::coords` — no sign-flips outside the helpers. Attach-to-engine plan (§11) details the future `RoomGeometry.{h,cpp}` C++ counterpart and submodule strategy.
