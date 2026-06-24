# B1 — Room-Aware AVIXA Ceiling-Speaker Coverage-Grid Optimizer — Implementation Spec

**Date:** 2026-06-24
**Feature ID:** B1 (distributed ceiling coverage grid)
**Version bump:** v0.44.0 → **v0.45.0** (MINOR, additive / opt-in)
**Status:** SPEC (no production code written here)
**Author:** planner (Opus)

> RESUME POINTER: this file is the single source of truth for the B1 build. Update
> it as the build progresses. If a session is interrupted, an executor resumes
> from the "Build Steps" checklist below.

---

## 0. One-paragraph summary

Add a new **room-aware distributed-ceiling coverage-grid** placement to
`roomestim/place/`. Given the room **floor polygon** + **ceiling height** + ear
height + nominal loudspeaker dispersion angle + overlap mode, it deterministically
computes a square OR hexagonal grid of ceiling speaker positions, clips them to the
footprint polygon (shapely), and returns a new `CoverageGridResult` dataclass
carrying coverage metadata (radius, spacing, n_speakers, grid type, overlap %). It
is **geometric AVIXA-formula-based only** — NO acoustic-performance / SPL claim
(that is B2, deferred), guarded by a single-source-of-truth `COVERAGE_GRID_NOTE`
that mirrors `LAYOUT_ANGLE_CHECK_NOTE`. It is wholly distinct from the existing
listener-centric VBAP/DBAP/WFS/ambisonics rendering rigs.

---

## 1. Ground-truth facts verified in the codebase (READ before building)

### 1.1 Data model (`roomestim/model.py`)
- `RoomModel` field for the footprint is **`floor_polygon: list[Point2]`** (NOT
  `footprint`). `Point2` carries `.x` (right) and `.z` (front), metres, CCW via
  `canonicalize_ccw`.
- `RoomModel.ceiling_height_m: float` — always a float (not Optional). Floor is at
  `y = 0`, ceiling at `y = ceiling_height_m`.
- `RoomModel.listener_area: ListenerArea` with `.height_m` (default `1.20`, the ear
  height) and `.centroid: Point2`.
- `RoomModel.ceiling_confidence: CeilingConfidence` ∈ {`high`,`low`,`unknown`} and
  `ceiling_coverage: float | None` — the honest under-report guard already shipped
  (v0.28.0 / v0.44.0). B1 SHOULD surface `ceiling_confidence == "low"` as a warning
  but MUST NOT block on it.
- `Point3(x=right, y=up, z=front)`, all frozen dataclasses.
- `PlacedSpeaker(channel: int, position: Point3, aim_direction: Point3|None=None,
  notes: str="")`.
- `PlacementResult(target_algorithm, regularity_hint, speakers, layout_name,
  layout_version="1.0", wfs_f_alias_hz=None, geometry_provenance="assumed")`.
- `Surface(kind, polygon: list[Point3], material, absorption_500hz, absorption_bands)`.

### 1.2 The honesty-NOTE single-source-of-truth pattern (MUST mirror)
- `roomestim/place/standards.py` (B5/B6) defines `LAYOUT_ANGLE_CHECK_NOTE` and
  `LAYOUT_METRICS_NOTE` as module-level `str` constants, exported in `__all__`,
  referenced (never retyped) by docstrings, `*_to_dict`, and CLI `format_*_lines`.
  Each result dataclass carries a `note: str` field set to the constant.
- `roomestim/reconstruct/_disclosure.py` is the sister pattern for RT60 / ceiling
  disclosures (`RT60_DISCLOSURE`, `POLYGON_ISM_GEOMETRY_NOTE`, …). B1's NOTE lives
  **in the new module** alongside the code it describes (same as standards.py),
  NOT in `_disclosure.py`.

### 1.3 Serialization conventions to mirror (`standards.py`)
- `*_to_dict(result) -> dict[str, object]` returns a plain JSON-serialisable dict
  with `"note"` first.
- `format_*_lines(result) -> list[str]` returns CLI lines, last line `f"  NOTE: …"`.
- CLI writes sidecar JSON via `json.dumps(d, indent=2) + "\n"` (see
  `_emit_layout_angle_check`, cli.py ~L895). The angle sidecar is
  `layout.angles.json`; B1's is `layout.coverage.json`.

### 1.4 Placement dispatch + CLI wiring
- `roomestim/place/dispatch.py::run_placement(room, algorithm, n_speakers,
  layout_radius_m, el_deg, wfs_f_max_hz=…, wfs_spacing_m=None, order=None)` is the
  single dispatch. Only `dbap` consumes room geometry today; vbap/wfs/ambisonics
  are room-blind (documented in its docstring).
- `roomestim/cli.py::_cmd_place` (L863) reads room.yaml, calls `_run_placement`
  (L819 wrapper that stamps `result.geometry_provenance = room.provenance`), writes
  `layout.yaml` via `write_layout_yaml`, and optionally `_emit_layout_angle_check`.
- `place` sub-parser (cli.py L125): `--algorithm {vbap,dbap,wfs,ambisonics}`
  default `vbap`, plus `--check-angles`. `run` sub-parser (L251) mirrors the algo
  flags.
- `write_layout_yaml` enforces R10 `min_speaker_count`: LINEAR≥2, CIRCULAR≥3,
  **PLANAR_GRID≥4**, IRREGULAR≥1. (Drives the `regularity_hint` choice in §3.4.)

### 1.5 Dependency availability (verified in `pyproject.toml`)
- Core deps include **`numpy>=1.24`** and **`shapely>=2.0`** (also `scipy>=1.10`).
  B1 uses **numpy + shapely only** — NO scipy, NO web-extras, NO new dependency.
- Module must be import-safe at `import roomestim` time (core boundary, torch-free)
  — numpy + shapely are already imported by the core (`model.py`, `dbap.py`).

### 1.6 Research basis (`.omc/research/usable-tech-facet5-speaker-layout-2026-06-23.md` §1A/§1C)
```
Coverage Radius   = (H_ceil − H_ear) · tan(θ_effective / 2)
θ_effective       = nominal_dispersion · 0.75            (effective ≈ 70–80% nominal)
Coverage Diameter = 2 · Coverage Radius
Spacing (rule)    ≈ 1.5 · H_ceil   (edge-to-edge industry heuristic)
First/last spkr   = half-spacing from the wall
Overlap           = 15% (background music) / 20–25% (speech)
Grid              = square or hexagonal
```
Standard: AVIXA Audio Coverage Uniformity (formerly InfoComm 1M:2012). The formula
is geometric and unencumbered. **The AVIXA standard defines a ±3 dB uniformity
MEASUREMENT procedure — B1 does NOT compute SPL or ±3 dB; that is B2 (deferred).**

---

## 2. New module — `roomestim/place/coverage_grid.py` (NEW FILE)

### 2.1 The honesty NOTE (single source of truth)
```python
COVERAGE_GRID_NOTE: str = (
    "Geometric ceiling-coverage grid only — NO acoustic-performance or SPL claim. "
    "Speaker positions are placed on a square or hexagonal lattice on the ceiling "
    "plane and clipped to the room floor polygon, using the AVIXA-style geometric "
    "coverage model (AVIXA Audio Coverage Uniformity, formerly InfoComm 1M:2012): "
    "coverage_radius = (ceiling_height - ear_height) * tan(effective_dispersion/2), "
    "effective_dispersion = nominal_dispersion * 0.75, center-to-center spacing = "
    "2 * coverage_radius * (1 - overlap_fraction), first/last speaker half a spacing "
    "from the footprint edge. It is a DETERMINISTIC GEOMETRIC layout: it does NOT "
    "compute sound pressure level, does NOT verify the AVIXA +/-3 dB uniformity "
    "criterion (that requires an SPL/coverage simulation — deferred to B2), assumes "
    "an idealized circular cone of the stated effective dispersion, and makes NO "
    "claim about a real loudspeaker's polar response. Coverage radius/spacing are "
    "nominal geometry, not a measurement. The nominal dispersion angle is a "
    "user-supplied datasheet value, not inferred from the room."
)
```
Export it in `__all__`; reference (never retype) it from the dataclass `note`
field, `to_dict`, `format_lines`, and the CLI.

### 2.2 Inputs and the public API

```python
GridType = Literal["square", "hex"]
OverlapMode = Literal["background", "speech"]

#: Effective-to-nominal dispersion derate (AVIXA rule of thumb; §1A).
EFFECTIVE_DISPERSION_FACTOR: float = 0.75
#: Overlap fraction by mode (center-to-center spacing = 2R*(1-overlap)).
OVERLAP_FRACTION: dict[OverlapMode, float] = {
    "background": 0.15,   # background music: 15% overlap (§1C)
    "speech": 0.23,       # speech intelligibility: midpoint of 20–25% band (§1C)
}
DEFAULT_NOMINAL_DISPERSION_DEG: float = 90.0   # typical full-range ceiling cone
DEFAULT_EAR_HEIGHT_M: float = 1.20             # matches ListenerArea default

@dataclass(frozen=True)
class CoverageGridResult:
    """Geometric ceiling coverage grid + honesty `note`. NO acoustic claim."""
    speakers: tuple[PlacedSpeaker, ...]          # ceiling positions, channel 1..n
    grid_type: GridType
    overlap_mode: OverlapMode
    overlap_fraction: float
    nominal_dispersion_deg: float
    effective_dispersion_deg: float
    ceiling_height_m: float
    ear_height_m: float
    coverage_radius_m: float
    coverage_diameter_m: float
    center_to_center_spacing_m: float
    n_speakers: int
    footprint_area_m2: float                     # shapely polygon area (floor)
    note: str                                    # = COVERAGE_GRID_NOTE
```

```python
def place_coverage_grid(
    *,
    floor_polygon: list[Point2],
    ceiling_height_m: float,
    ear_height_m: float = DEFAULT_EAR_HEIGHT_M,
    nominal_dispersion_deg: float = DEFAULT_NOMINAL_DISPERSION_DEG,
    overlap_mode: OverlapMode = "background",
    grid_type: GridType = "square",
    layout_name: str = "coverage_grid",
    edge_inclusion_tol_m: float = 1e-9,
) -> CoverageGridResult:
    ...
```

Convenience room-level wrapper (keeps dispatch/CLI thin and reuses
`listener_area.height_m` as the ear height default honestly):
```python
def place_coverage_grid_for_room(
    room: RoomModel,
    *,
    ear_height_m: float | None = None,     # None -> room.listener_area.height_m
    nominal_dispersion_deg: float = DEFAULT_NOMINAL_DISPERSION_DEG,
    overlap_mode: OverlapMode = "background",
    grid_type: GridType = "square",
    layout_name: str = "coverage_grid",
) -> CoverageGridResult:
    ...
```

### 2.3 Algorithm (deterministic; document each step in the module docstring)

1. **Validate inputs** (fail loud, BEFORE any geometry):
   - `len(floor_polygon) >= 3`, else `ValueError("coverage grid requires a polygon
     with >=3 vertices")`.
   - Build `ShapelyPolygon([(p.x, p.z) for p in floor_polygon])`; require
     `poly.is_valid and not poly.is_empty and poly.area > 0`, else
     `ValueError("degenerate floor polygon (zero area / self-intersecting)")`.
   - `ceiling_height_m` and `ear_height_m` finite (use `assert_finite` from
     `model.py`) and `nominal_dispersion_deg` in `(0, 180)`.
   - **`ceiling_height_m > ear_height_m`** else
     `ValueError("ceiling_height_m <= ear_height_m: no coverage geometry (ceiling "
     "must be above the ear plane)")`. This covers the "ceiling < ear" and the
     "missing/0 ceiling height" edge cases at once.
   - `overlap_mode` in `OVERLAP_FRACTION`; `grid_type` in `{"square","hex"}`.
2. **Coverage geometry:**
   - `eff_deg = nominal_dispersion_deg * EFFECTIVE_DISPERSION_FACTOR`
   - `R = (ceiling_height_m - ear_height_m) * tan(radians(eff_deg / 2))`
   - `D = 2 * R`
   - `overlap = OVERLAP_FRACTION[overlap_mode]`
   - `S = 2 * R * (1 - overlap)`  (center-to-center spacing; for `overlap=0`,
     circles just touch at `S=2R`). Guard `S > 0` (always true for valid inputs).
   - Cross-check value (informational, recorded in NOTE/dict only): the §1A
     `1.5 * H_ceil` heuristic — NOT used to drive geometry; the overlap-derived `S`
     is authoritative. Document that the two agree to within ~15% for a 90° cone at
     2.5–3 m ceilings.
3. **Lattice seeding (half-spacing wall inset):**
   - Compute polygon AABB `(minx, minz, maxx, maxz)` from `poly.bounds`.
   - **Square grid:** start the lattice at `x0 = minx + S/2`, `z0 = minz + S/2`;
     step `S` in both axes; generate all `(x, z)` with `x <= maxx - S/2 + S` …
     i.e. iterate `x = x0 + i*S while x <= maxx` and similarly `z`. (Generating one
     extra ring beyond the AABB is harmless — clipping in step 4 removes outliers;
     but to keep counts analytic, iterate strictly `x0 + i*S <= maxx`,
     `z0 + j*S <= maxz`.)
   - **Hex grid:** row pitch `dz = S * sqrt(3)/2`; even rows start at `x0`, odd rows
     offset by `S/2`. `z` from `z0` stepping `dz` while `<= maxz`; per row, `x` from
     `x0 (+S/2 on odd rows)` stepping `S` while `<= maxx`.
   - All lattice points are deterministic (numpy `arange`/explicit loops; no
     randomness, no set ordering ambiguity — emit in row-major (z then x) order).
4. **Polygon clipping (EXACT inclusion rule, document verbatim):**
   - A lattice point `(x, z)` is **kept iff its floor-projected coverage centroid
     lies inside or within `edge_inclusion_tol_m` of the footprint polygon**:
     `poly.covers(ShapelyPoint(x, z))` OR
     `poly.buffer(edge_inclusion_tol_m).covers(ShapelyPoint(x, z))`.
     (`covers` includes the boundary; the tiny buffer absorbs float noise — mirrors
     the `inset.buffer(1e-9).contains(...)` idiom in `dbap.py`.) The coverage
     *centroid* is the speaker's `(x, z)`; B1 deliberately uses centroid-in-polygon,
     NOT circle-area-overlap, and the NOTE/docstring state this so a partially
     overhanging coverage circle near a concave notch is honestly described as
     "centroid inside, circle may overhang the wall — no acoustic claim".
5. **Tiny-room / empty-grid fallback (≥1 speaker guarantee):**
   - If step 4 yields **zero** kept points (room smaller than one spacing, or all
     lattice nodes fell outside a concave footprint), place **exactly one** speaker
     at a guaranteed-interior point: `poly.representative_point()` (shapely
     guarantees it is inside, unlike the centroid for concave shapes). `n_speakers
     = 1`.
6. **Lift to ceiling + build speakers:**
   - For each kept `(x, z)` in deterministic order, `position = Point3(x=x,
     y=ceiling_height_m, z=z)`, `channel = i+1`.
   - **Aim:** ceiling speakers point straight down →
     `aim_direction = Point3(0.0, -1.0, 0.0)` (honest default; NOT aim-at-origin —
     these are distributed downward-firing ceiling cans, not a listener ring).
7. **Return** `CoverageGridResult(...)` with all metadata + `note=COVERAGE_GRID_NOTE`.

### 2.4 Serialization helpers (mirror standards.py)
```python
def coverage_to_dict(result: CoverageGridResult) -> dict[str, object]:
    # "note" first, then geometry scalars, then a "speakers" list of
    # {channel, x, y, z, aim_x, aim_y, aim_z}. JSON-serialisable plain floats.

def format_coverage_lines(result: CoverageGridResult) -> list[str]:
    # header: "ceiling coverage grid (geometry only, no acoustic/SPL claim):"
    # lines: grid type, ceiling/ear, effective dispersion, radius, spacing,
    #        overlap mode/%, n_speakers, footprint area
    # last line: f"  NOTE: {result.note}"
```

### 2.5 Adapter to the existing layout pipeline (reuse, do not duplicate)
```python
def coverage_result_to_placement(result: CoverageGridResult) -> PlacementResult:
    """Wrap a CoverageGridResult as a PlacementResult so the existing
    write_layout_yaml / check_layout_angles / compute_layout_metrics surfaces work
    unchanged. regularity_hint = "PLANAR_GRID" when n>=4 else "IRREGULAR" (so the
    R10 min_speaker_count gate passes for tiny 1–3-speaker rooms).
    target_algorithm = "COVERAGE_GRID"."""
```
- **Decision (recorded):** B1 **reuses** `PlacedSpeaker`/`PlacementResult` for the
  layout.yaml boundary **and** adds the richer `CoverageGridResult` for the coverage
  metadata sidecar. Rationale: layout.yaml/geometry_schema.json + the B5/B6 angle &
  metrics surfaces all consume `PlacementResult`; re-using it means
  `layout.yaml` round-trips with zero schema change (root
  `additionalProperties:true`; the `x_target_algorithm` extension key already
  persists any non-VBAP label — see `layout_yaml.py` L254). `CoverageGridResult`
  carries the coverage-specific numbers that have no home on `PlacementResult` and
  feeds the new `layout.coverage.json` sidecar (parallel to `layout.angles.json`).
- **New `TargetAlgorithm` member:** add `COVERAGE_GRID = "COVERAGE_GRID"` to
  `roomestim/place/algorithm.py` (additive enum value; the writer emits
  `x_target_algorithm="COVERAGE_GRID"` because it != "VBAP", so existing VBAP
  layouts stay byte-equal). The placement-yaml READER currently collapses unknown
  labels — confirm it tolerates the new label (it round-trips the string only; no
  COVERAGE_GRID *producer* is needed on read). If the reader validates against a
  closed label set, extend it additively; otherwise no change.

### 2.6 `__all__` for the module
`["COVERAGE_GRID_NOTE", "CoverageGridResult", "GridType", "OverlapMode",
"OVERLAP_FRACTION", "EFFECTIVE_DISPERSION_FACTOR", "place_coverage_grid",
"place_coverage_grid_for_room", "coverage_to_dict", "format_coverage_lines",
"coverage_result_to_placement"]`

---

## 3. Edge cases (explicit, all deterministic)

| Case | Behaviour |
|---|---|
| Tiny room (AABB < one spacing) | step-5 fallback → exactly **1** speaker at `representative_point()`. `regularity_hint="IRREGULAR"` (min 1) so layout.yaml passes R10. |
| Concave / non-convex footprint | shapely `covers` honestly drops lattice nodes in the notch; coverage circles may overhang re-entrant walls — stated in NOTE, **no acoustic claim**. No crash. |
| Self-intersecting / zero-area polygon | `ValueError` in step 1 (`poly.is_valid`/`area>0`). |
| `ceiling_height_m <= ear_height_m` (incl. 0 / unset) | `ValueError` (single guard, step 1). |
| `nominal_dispersion_deg` ∉ (0,180) | `ValueError`. |
| NaN/inf in any input | `assert_finite` → `ValueError(kErrNonFiniteValue …)` (reuse model.py helper). |
| `ceiling_confidence == "low"` | NOT an error. `place_coverage_grid_for_room` records it; CLI prints a one-line advisory (mirrors `_maybe_print_low_ceiling_notice`). Geometry still produced. |
| Very large room | numpy lattice; bounded by AABB/S; no perf concern for realistic rooms (≤ a few thousand nodes). |
| `n_speakers` huge from a small spacing | acceptable — it is the geometric answer; no cap (a cap would be an acoustic/cost judgement, out of scope). |

---

## 4. CLI integration (additive)

**Decision:** expose via a **new `--algorithm coverage` choice** on the existing
`place` (and `run`) sub-parsers, plus coverage-only flags. Default `--algorithm`
stays `vbap`, so every existing invocation is byte-equal.

New flags (added to `_add_place_parser`, and mirrored in `_add_run_parser`):
- `--ceiling-dispersion-deg FLOAT` (default `90.0`) — nominal datasheet dispersion.
- `--ear-height-m FLOAT` (default: unset → uses `room.listener_area.height_m`).
- `--overlap-mode {background,speech}` (default `background`).
- `--grid {square,hex}` (default `square`).

Wiring:
- `dispatch.run_placement` gains **optional, defaulted** kwargs
  (`coverage_dispersion_deg: float | None = None`, `coverage_ear_height_m: float |
  None = None`, `coverage_overlap_mode: str = "background"`, `coverage_grid_type:
  str = "square"`) and a new branch `if algorithm == "coverage":` that calls
  `place_coverage_grid_for_room(...)` then returns
  `coverage_result_to_placement(result)`. All existing callers
  (`roomestim_web`, tests) pass no new kwargs → **byte-equal** dispatch behaviour.
  Update the dispatch docstring to add `coverage` to the room-geometry-aware list
  (it joins `dbap` as the second room-aware path; the others stay room-blind).
- `_cmd_place` / `_cmd_run`: when `args.algorithm == "coverage"`, after writing
  `layout.yaml`, also write `layout.coverage.json` via `coverage_to_dict` and print
  `format_coverage_lines` — a new `_emit_coverage_grid(...)` helper mirroring
  `_emit_layout_angle_check` (cli.py ~L895). `--check-angles` continues to work on
  the coverage layout (it consumes the wrapped `PlacementResult`).
  - To get the `CoverageGridResult` (not just the wrapped `PlacementResult`) into
    the CLI for the sidecar, `_cmd_place` calls
    `place_coverage_grid_for_room` directly in the coverage branch (the cleanest
    path), or `run_placement` returns the result and the CLI recomputes
    `coverage_to_dict` — **prefer the direct call** in the coverage branch to avoid
    double computation; keep `run_placement` as the layout.yaml producer.

---

## 5. Files touched (complete list + additive guarantee)

| File | New/Edit | Change | Additive guarantee |
|---|---|---|---|
| `roomestim/place/coverage_grid.py` | **NEW** | Whole module (§2). | New file — touches nothing existing. |
| `roomestim/place/algorithm.py` | EDIT | Add `COVERAGE_GRID = "COVERAGE_GRID"` enum member. | Additive enum value; existing members unchanged; VBAP layouts byte-equal (writer only emits `x_target_algorithm` for non-VBAP). |
| `roomestim/place/__init__.py` | EDIT | Export `place_coverage_grid`, `place_coverage_grid_for_room`, `CoverageGridResult`, `COVERAGE_GRID_NOTE`. | Append to imports + `__all__`; no existing export changed. |
| `roomestim/place/dispatch.py` | EDIT | New `coverage` branch + 4 optional defaulted kwargs; docstring update. | New kwargs default to None/"background"/"square"; existing call sites byte-equal. |
| `roomestim/cli.py` | EDIT | Add `coverage` to `--algorithm` choices on `place`+`run`; add 4 flags; `_emit_coverage_grid` helper; coverage branch in `_cmd_place`/`_cmd_run`. | `--algorithm` default stays `vbap`; new flags default to current behaviour; existing CLI invocations byte-equal. |
| `tests/test_coverage_grid.py` | **NEW** | Deterministic unit tests (§6). | New test file. |
| `pyproject.toml` | EDIT | `version = "0.45.0"`. | Version-only line. |
| `README.md` | EDIT (optional, recommended) | Document the coverage grid + its honesty NOTE + B2 deferral. | Doc-only, additive section. |
| `docs/adr/ADR-0052-coverage-grid.md` (or repo ADR convention) | **NEW** (recommended) | Record the decision (geometric-only, reuse PlacementResult, B2 SPL deferred). | Doc-only. |

**No edits to:** `model.py`, `layout_yaml.py`, `room_yaml_reader.py`,
`geometry_schema.json`, `standards.py`, `dbap.py`/`vbap.py`/`wfs.py`/`ambisonics.py`,
or any synthetic fixture. The placement-yaml reader is touched **only if** it
validates a closed `x_target_algorithm` set (verify first; extend additively if so).

---

## 6. Test plan (`tests/test_coverage_grid.py`)

Canonical gate: `/home/seung/miniforge3/bin/python -m pytest`. Baseline **695p / 7s
@ v0.44.0**. B1 adds tests (count rises); existing synthetic golden/round-trip
tests MUST stay byte-equal (feature is opt-in / new algorithm value).

Deterministic analytic cases (no randomness, no I/O):

1. **Known rectangle → known count & spacing (square).** A `10 m × 8 m`
   axis-aligned rectangle, `ceiling=3.0`, `ear=1.0`, `dispersion=90°`:
   - `eff = 67.5°`; `R = (3-1)·tan(33.75°)`; assert `R ≈ 1.3361 m` (compute the
     exact expected with `math.tan` in the test, don't hardcode a rounded literal).
   - `overlap=0.15` → `S = 2R·0.85 ≈ 2.2714 m`.
   - Assert lattice node count along x = `floor((10 - S) / S) + 1` and along z =
     `floor((8 - S) / S) + 1`; assert `n_speakers == nx·nz` (rectangle ⇒ all nodes
     inside). Assert first node x ≈ `0 + S/2`, neighbour pitch == `S`.
   - Assert every `position.y == 3.0` and every `aim_direction == Point3(0,-1,0)`.
2. **Hex grid on the same rectangle:** row pitch `dz = S·√3/2`; assert odd rows
   offset by `S/2`; assert all positions inside; assert `grid_type=="hex"`.
3. **Overlap mode changes spacing & count:** `speech` (0.23) yields smaller `S` and
   `n_speakers_speech > n_speakers_background` on the same room. Assert strictly.
4. **Coverage-radius formula exactness:** parametrize a few
   `(ceiling, ear, dispersion)` triples; assert
   `result.coverage_radius_m == (h-e)·tan(radians(0.75·disp/2))` within `1e-12`.
5. **Tiny room → 1 speaker:** `1.2 m × 1.0 m` rectangle with spacing larger than the
   room ⇒ `n_speakers == 1`, the position is inside the polygon
   (`poly.covers(point)`), `regularity_hint` of the wrapped result == `"IRREGULAR"`.
6. **Concave footprint:** an L-shaped polygon; assert no kept node lies in the notch
   (all `poly.covers((x,z))`), assert `n_speakers >= 1`, no exception.
7. **Edge-case errors:** `ceiling <= ear` raises `ValueError`; `<3` vertices raises;
   self-intersecting polygon raises; NaN ceiling raises (`kErrNonFiniteValue`);
   `dispersion=0`/`>=180` raises.
8. **`ceiling_confidence=="low"`** room produces a grid (no raise); test the
   `place_coverage_grid_for_room` path picks `ear = listener_area.height_m` when
   `ear_height_m is None`.
9. **NOTE / honesty invariants:** `result.note is COVERAGE_GRID_NOTE`;
   `coverage_to_dict(result)["note"] == COVERAGE_GRID_NOTE`;
   `format_coverage_lines(result)[-1].startswith("  NOTE:")`;
   assert the string contains NO SPL/dB performance claim (grep the constant for
   "no acoustic" / absence of "dB" as a *claim* — assert it states "does NOT compute
   sound pressure level").
10. **Pipeline reuse:** wrap via `coverage_result_to_placement`, run
    `write_layout_yaml(..., validate=False)` to a tmp path and assert it writes;
    run `check_layout_angles` + `compute_layout_metrics` on it without error
    (the B5/B6 surfaces accept any `PlacementResult`).
11. **Byte-equal regression guard (implicit):** the existing
    `test_layout_round_trip` / golden suites are NOT modified and must still pass —
    run the full gate, confirm prior count unchanged + the new tests added.

Gate sequence the executor MUST run (per project MEMORY "verify each step"):
`/home/seung/miniforge3/bin/python -m pytest` (default), then web marker, `ruff`,
`mypy --strict`, and the CLI smoke (`place --algorithm coverage`). New code must be
mypy-strict clean (no `Any` leaks; the module is core/torch-free).

---

## 7. Acceptance criteria (executor-verifiable)

- [ ] `roomestim/place/coverage_grid.py` exists with `COVERAGE_GRID_NOTE`,
      `CoverageGridResult`, `place_coverage_grid`, `place_coverage_grid_for_room`,
      `coverage_to_dict`, `format_coverage_lines`, `coverage_result_to_placement`.
- [ ] Square **and** hex grids implemented; half-spacing wall inset; exact inclusion
      rule = centroid `poly.covers`/buffered-tol (documented in docstring).
- [ ] All edge cases (§3) handled; tiny room → 1 speaker; `ceiling<=ear` raises.
- [ ] `COVERAGE_GRID_NOTE` is the single source of truth, geometric-only, cites
      AVIXA Audio Coverage Uniformity, NO SPL/±3 dB claim, B2 deferral stated.
- [ ] CLI `place --algorithm coverage` writes `layout.yaml` + `layout.coverage.json`
      and prints the coverage lines + NOTE; default `vbap` path byte-equal.
- [ ] `numpy` + `shapely` only (no new dependency; no scipy; core-import safe).
- [ ] Full gate GREEN: prior 695 still pass + new `test_coverage_grid.py` passes;
      ruff + mypy-strict clean; existing golden/round-trip byte-equal.
- [ ] `pyproject.toml` version == `0.45.0`.
- [ ] No fake numbers anywhere (formula-derived only).

---

## 8. Build steps (resumable checklist)

1. [x] Add `COVERAGE_GRID` enum to `place/algorithm.py`; verify placement-yaml
       reader tolerates the label (extend additively only if it validates a closed set).
       → DONE. Reader DID validate a closed set (`_TARGET_ALGORITHM_VALUES`); extended
       additively with `"COVERAGE_GRID"`.
2. [x] Write `place/coverage_grid.py` (§2): NOTE → dataclass → validation →
       coverage geometry → square/hex lattice → clip → fallback → lift → serialize →
       adapter. → DONE. (Lattice uses half-spacing inset from BOTH edges, matching the
       NOTE "first/last speaker half a spacing from the footprint edge" + §6 count
       formula; `CoverageGridResult` carries `layout_name` so the 1-arg
       `coverage_result_to_placement(result)` works. stdlib `math`+shapely only, no numpy.)
3. [x] Export from `place/__init__.py`. → DONE.
4. [x] Extend `dispatch.run_placement` with the coverage branch + optional kwargs. → DONE
       (4 defaulted `coverage_*` kwargs; existing callers byte-equal).
5. [x] Extend CLI (`place` + `run`): flags, `coverage` choice, `_emit_coverage_grid`. → DONE
       (`_add_coverage_args` shared helper; `_run_coverage` + `_emit_coverage_grid`;
       coverage branch in `_cmd_place`/`_cmd_run`).
6. [x] Write `tests/test_coverage_grid.py` (§6); run full gate; iterate to GREEN. → DONE.
       Full default gate **715 passed / 7 skipped** (695 baseline + 20 new test items,
       0 regression). ruff clean; mypy --strict clean (58 files). CLI smoke verified.
7. [x] Bump `pyproject.toml` (and `roomestim/__init__.py`) to `0.45.0`; README + ADR doc.
       → DONE. README: status row + algorithm-table row + `--algorithm coverage`
       subsection. ADR 0052 (`docs/adr/0052-coverage-grid.md`; next free number confirmed).
8. [ ] Hand off to code-reviewer (independent pass), then verifier, then commit
       (MINOR additive, mirror v0.44.0 commit style). ← NOT committed by executor.

---

## 9. Out of scope (explicit deferrals)

- **B2 — SPL / ±3 dB AVIXA uniformity scoring** (requires a direct-sound SPL model
  over a listener grid; research §1B suggests numpy + optional pyroomacoustics).
  B1 produces positions only; B2 scores them. Keep B1's NOTE pointing at this gap.
- **Optimization-based placement** (`scipy.optimize.differential_evolution`,
  research §1B) — geometric grid covers ~80% of installs; optimizer is a later lever.
- **Rendering decode** (spaudiopy/DBAP/VBAP panning to the grid) — orthogonal; the
  existing rigs already exist and are listener-centric.
- **Per-speaker model/datasheet polar-pattern ingestion** — dispersion is a single
  user-supplied scalar; GLL/CLF parsing is out of scope.
```
