# roomestim Architecture

> Audience: an engineer joining mid-stream who needs to understand roomestim end-to-end
> without reading the design plan.

---

## Mission

roomestim converts a phone room-scan into two machine-readable artefacts: `room.yaml` (a
proposed new schema owned by roomestim that captures the geometry and acoustic surface
properties of a physical room) and `layout.yaml` (an engine-ready speaker placement, validated
against `spatial_engine/proto/geometry_schema.json`). The overall pipeline is **capture →
adapt → model → reconstruct → place → export**. No BIM precision is claimed; tolerances are
cm-grade (walls ±10 cm, speaker angles ±2–5°, Sabine RT60 ±20%).

---

## Coordinate Frame

All internal geometry uses the **listener-frame** convention documented in
`spatial_engine/docs/coordinate_convention.md`:

- **Origin**: listener position (or listener-area centroid when a region is specified).
- **x** = right, **y** = up, **z** = front (into the room). Units: metres.
- **az_deg**: azimuth in degrees. **RIGHT = +az_deg** (matches `spatial_engine` VBAP
  layout-frame). Range: (−180, +180].
- **el_deg**: elevation in degrees. **UP = +el_deg**. Range: [−90, +90].

Floor-plane coordinates use `Point2(x, z)` (the y dimension is implicit; zero = floor).
Three-dimensional coordinates use `Point3(x, y, z)`.

---

## Pipeline Stages

```
Phone scan
    │
    ▼
[CaptureAdapter]         roomestim/adapters/{roomplan,polycam}.py
    │  parses USDZ / JSON sidecar / OBJ
    │  emits ──► RoomModel
    ▼
[RoomModel]              roomestim/model.py
    │  stable internal abstraction; CCW floor_polygon, surfaces, listener_area
    │
    ├──► [Reconstruct]   roomestim/reconstruct/{floor_polygon,walls,listener_area,materials}.py
    │        projects raw geometry to 2.5D polygon, infers surfaces + materials
    │
    ├──► [Place]         roomestim/place/{vbap,dbap,wfs}.py
    │        algorithm-aware speaker placement → PlacementResult
    │
    └──► [Export]
             ├── room.yaml   roomestim/export/room_yaml.py
             └── layout.yaml roomestim/export/layout_yaml.py
```

### Capture Adapters (`roomestim/adapters/`)

| File | Backend | Notes |
|---|---|---|
| `roomplan.py` | Apple RoomPlan | First-class; LiDAR metric scale; JSON sidecar + USDZ. See ADR 0001. |
| `polycam.py` | Polycam | Supported secondary; mesh-only, cross-platform. |

COLMAP is experimental, behind `[colmap]` extra and `--experimental` flag.
See [ADR 0001](adr/0001-capture-backend-priority.md).

### RoomModel (`roomestim/model.py`)

The only stable abstraction that crosses adapter boundaries. Key fields:

```python
@dataclass
class RoomModel:
    name: str
    floor_polygon: list[Point2]   # CCW on floor plane
    ceiling_height_m: float       # scalar; vaulted ceilings deferred to v0.3
    surfaces: list[Surface]       # walls + floor + ceiling with material labels
    listener_area: ListenerArea   # polygon + centroid + height_m (default 1.20 m)
    schema_version: str           # "0.1-draft" (Stage 1) or "0.1" (Stage 2)
```

See [ADR 0002](adr/0002-room-representation.md) for why 2.5D was chosen over shoebox or
full mesh.

### Reconstruct (`roomestim/reconstruct/`)

| File | Responsibility |
|---|---|
| `floor_polygon.py` | Project mesh vertices to floor plane; Shapely convex/concave hull; CCW canonicalization via `model.canonicalize_ccw`. |
| `walls.py` | Lift floor edges to vertical rectangular `Surface` objects. |
| `listener_area.py` | Detect or default the listener region. |
| `materials.py` | Map raw surface labels to `MaterialLabel` enum; look up `MaterialAbsorption` table. |

### Place (`roomestim/place/`)

Algorithm priority: **VBAP → DBAP → WFS** (Ambisonics deferred to v0.3).
See [ADR 0003](adr/0003-placement-algorithm-priority.md).

| File | Algorithm | Notes |
|---|---|---|
| `vbap.py` | VBAP | Equal-angle ring; fastest deterministic placement. |
| `dbap.py` | DBAP | Robust to irregular venues. |
| `wfs.py` | WFS | λ/2 spacing constraint; emits `x_wfs_f_alias_hz`. |
| `ambisonics.py` | Ambisonics | Stub; deferred to v0.3. |

### Export (`roomestim/export/`)

#### `room_yaml.py`

Serialises `RoomModel` → `room.yaml`. Validates against `proto/room_schema.draft.json`
(Stage 1) or `proto/room_schema.json` (Stage 2) using `Draft202012Validator` from
`jsonschema`. Every numeric leaf is checked with `assert_finite` before writing.

#### `layout_yaml.py` (lines 50–65)

Serialises `PlacementResult` → `layout.yaml`. The geometry schema is **never vendored**;
it is read at write-time from:

1. `$SPATIAL_ENGINE_REPO_DIR/proto/geometry_schema.json` (if env var is set), else
2. `/home/seung/mmhoa/spatial_engine/proto/geometry_schema.json` (hardcoded default).

roomestim never copies `geometry_schema.json` into its own tree.

---

## Two-Stage `room.yaml` Schema Lock

Defined in design plan §6.0 and [ADR 0004](adr/0004-room-yaml-schema-lockin.md).

| Stage | `version` field | `additionalProperties` | When |
|---|---|---|---|
| 1 — draft | `"0.1-draft"` | `true` (permissive) | Ships immediately in v0.1 autopilot |
| 2 — locked | `"0.1"` | `false` (strict) | After A10 lab fixture produces ≥1 real `room.yaml`; human-gated (D8) |

The Stage-2 flip requires:
- `tests/fixtures/lab_real_room.yaml` committed.
- Reviewer sign-off (D8/D2 reversal criteria).
- Cross-repo PR proposing `spatial_engine/proto/room_schema.json` → roomestim v0.2.

---

## Layout Extension Keys

roomestim emits the following `x_`-prefixed extension keys in `layout.yaml`.
`geometry_schema.json` declares `additionalProperties: true` at root and per-speaker,
so the engine ignores these safely.

| Key | Scope | Value |
|---|---|---|
| `x_aim_az_deg` | per-speaker | Azimuth of aim direction in VBAP layout-frame (°). Default: speaker → listener centroid. |
| `x_aim_el_deg` | per-speaker | Elevation of aim direction (°). Same convention. |
| `x_wfs_f_alias_hz` | top-level | WFS spatial-aliasing frequency (Hz). Required when `target_algorithm == "WFS"`; forbidden otherwise. |

See decisions.md D5 and design plan §6.1 for rationale.

---

## Cross-Repo Posture

roomestim is a **standalone git repo** for v0.1 (decisions.md D1). Interaction with
`spatial_engine` is read-only:

- `layout.yaml` is validated against `spatial_engine/proto/geometry_schema.json` at export
  time (resolved via `SPATIAL_ENGINE_REPO_DIR` env var or default path —
  `roomestim/export/layout_yaml.py:52–64`).
- roomestim **never vendors** `geometry_schema.json`.
- Cross-repo PR proposing `room.yaml` upstream is roomestim v0.2 work (after ≥10 real
  `room.yaml` files are exercised).

---

## Test Taxonomy

| Lane | Command | When it runs |
|---|---|---|
| Default CI | `pytest -m "not lab"` | Always; Linux CI; no physical device needed. |
| Lab gate | `pytest -m lab` | Skipped unless `tests/fixtures/lab_real.usdz` + ground-truth file exist. Human-gated per D8. |

The lab gate (`test_acceptance_lab_room.py`) is the A10 acceptance criterion: tape-measured
speaker positions within ±5° azimuth / ±10 cm radial, room corners <10 cm error.

A11 (RT60 validation) falls back to a **synthetic-shoebox reference** in default CI so
it does not depend on A10.

---

## ADR Index

| ADR | Decision |
|---|---|
| [0001](adr/0001-capture-backend-priority.md) | Capture backend priority (RoomPlan first, Polycam secondary, COLMAP experimental) |
| [0002](adr/0002-room-representation.md) | Internal room representation (2.5D polygon + scalar ceiling) |
| [0003](adr/0003-placement-algorithm-priority.md) | Placement algorithm priority (VBAP → DBAP → WFS → Ambisonics v0.3) |
| [0004](adr/0004-room-yaml-schema-lockin.md) | `room.yaml` two-stage schema lock-in timing |
| [0005](adr/0005-tech-stack.md) | Tech stack (Python ≥3.10, shapely, trimesh, jsonschema, ruff, mypy) |
