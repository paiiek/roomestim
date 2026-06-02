# roomestim v0.24.0 — non-shoebox floor reconstruction (opt-in concave hull)

MINOR bump `0.23.1` → `0.24.0`. See ADR 0042 §Status-update-v0.24.0
(`docs/adr/0042-live-mesh-corner-extraction.md`), D82 (`.omc/plans/decisions.md`),
and OQ-13e (partial progress — still OPEN) (`.omc/plans/open-questions.md`).

This cycle (Cycle B — non-shoebox floor reconstruction) lands the
concave-hull floor-polygon reconstruction ADR 0042 specifies, as an **opt-in**
`MeshAdapter` mode. The previously dead `floor_polygon_from_mesh` stub is now a
real implementation; the `MeshAdapter` default path stays **byte-equal** to the
prior convex-hull behavior, so no existing caller — CLI, library, or web —
changes output unless it explicitly opts in. The SemVer-MINOR driver is the
additive `MeshAdapter(floor_reconstruction=...)` constructor argument: a new
observable mode, no removed or altered default behavior.

## ① Concave floor reconstruction (`floor_polygon_from_mesh`, ADR 0042 PR1)

`roomestim/reconstruct/floor_polygon.py` — the `floor_polygon_from_mesh(mesh_vertices, *, ratio=0.4)`
stub that had **zero production callers** is now implemented. It projects the
`(N, 3)` vertex cloud onto the `(x, z)` floor plane (the `MeshAdapter`
convention), recovers a *concave* footprint via `shapely.concave_hull`,
simplifies with a 5 cm Douglas-Peucker tolerance, and canonicalizes CCW. Unlike
a convex hull, the concave hull **preserves re-entrant corners**, so an
L-shaped or otherwise non-shoebox room keeps its notch instead of collapsing to
its bounding hull.

The implementation uses **`shapely.concave_hull` — zero new dependencies**
(`shapely>=2.0` is already core, `pyproject.toml:15`). ADR 0042 §B sketched a
`scipy.spatial.Delaunay` + `shapely.ops.polygonize` recipe; the landed code
takes the simpler `shapely.concave_hull` path, which is the same zero-dep
constraint with a smaller surface (no manual α/circumradius heuristic, one
`ratio` knob).

Tuning constants (module-level, documented in source):
- `ratio=0.4` — concave-hull tightness in `(0, 1]`. `1.0` reproduces the convex
  hull; `→0.0` over-tightens into a jagged boundary hugging every outlier.
  `0.4` is the empirically-chosen midpoint that recovers an L-shaped notch
  while staying robust to dense, slightly-noisy LiDAR/photogrammetry grids.
- `simplify(0.05)` — a 5 cm tolerance collapses near-collinear boundary
  coordinates from a dense scan into clean straight edges (and drops sub-5 cm
  jitter) without eroding real structural corners, which are separated by tens
  of centimetres or more.

**Degeneracy guards** (all raise a clear `ValueError`, which the caller converts
to a convex fallback — see ② below): `ratio` outside `(0, 1]` including NaN;
fewer than 3 distinct projected points; a `MultiPolygon` result (the
largest-area component is taken); interior holes (the exterior ring is used —
a floor footprint is a simple ring); a non-`Polygon` / empty / zero-area
geometry; and a final ring that fails the `is_simple_polygon` check
(self-intersecting or collinear).

## ② Opt-in wiring + byte-equal default (`MeshAdapter`)

`roomestim/adapters/mesh.py` — `MeshAdapter` gains a keyword-only
`floor_reconstruction="convex" | "concave"` constructor argument and a matching
`ROOMESTIM_MESH_FLOOR_RECON` environment override, in the same env style as the
existing `ROOMESTIM_MAX_MESH_*` resource-bound knobs (ADR 0038).

Precedence: an explicit constructor argument wins; when the argument is left at
its sentinel default the env var is consulted; absent both, the mode is
`"convex"`. The `"convex"` path is the **byte-equal legacy code** — the same
inline `MultiPoint(...).convex_hull` projection, relocated into a
`_convex_floor_polygon` helper but otherwise unchanged. A regression test pins
this byte-equality against the existing mesh fixtures, so the default produces
identical `RoomModel` output to v0.23.1.

In `"concave"` mode, a `ValueError` from `floor_polygon_from_mesh` (any
degeneracy from ①) is caught and the adapter **falls back to the convex hull
with a `UserWarning`** — concave reconstruction never hard-fails a parse that
the convex path could have handled.

## ③ Dense-cloud accuracy caveat (honest)

The concave-hull approach gives accurate footprint recovery only when the
projected vertex cloud is **dense** — a point spacing of roughly 0.25 m or
finer (a LiDAR scan or photogrammetry mesh with thousands of floor / wall /
ceiling vertices). On **sparse low-poly meshes** (e.g. a 6-point extruded L
prism with one vertex per footprint corner) the boundary samples are too coarse
for `shapely.concave_hull` to resolve the notch, and the recovered area
**undershoots truth by ~10–20 %**. This is documented in the
`floor_polygon_from_mesh` docstring; for those inputs callers should raise
`ratio` toward `1.0` (approaching the convex hull) or use the explicit convex
mode. This caveat is the reason the mode stays **opt-in** rather than becoming
the default.

## What stays the same

| Item | Value |
|---|---|
| `MeshAdapter` default mode | `"convex"` (byte-equal to v0.23.1 — regression-pinned) |
| CLI / web user-facing default | unchanged (concave is opt-in via arg / env; no flag flipped) |
| `__schema_version__` | `0.2-draft` (no RoomModel field added — output is still a floor polygon) |
| New runtime dependencies | none (`shapely.concave_hull`; `shapely>=2.0` already core) |
| `roomestim_web` | untouched (`roomestim_web.__version__` stays `0.18-web.0`; core change) |
| RANSAC wall-plane fit | NOT adopted (ADR 0042 §C — extrusion walls reused) |

## Downstream tolerance

This is a **core change** to the floor-polygon extraction stage; nothing
downstream needed adjustment because the consumers were already polygon-tolerant
for simple non-convex input. `geom/polygon.py` (shoelace / volume),
`reconstruct/listener_area.py` (the concave-centroid `representative_point`
fallback), and the `RoomModel` / placement / Sabine path already accept simple
non-convex footprints (ADR 0042 §Context (4)); a non-shoebox floor flows through
unchanged, with RT60 routing to Eyring for non-shoebox geometry exactly as
before (the ADR 0040 track — untouched here). The self-intersecting case is the
only unsupported footprint, and the new `is_simple_polygon` guard in ① rejects
it at the extraction boundary.

## Test / gate evidence

Run under the canonical miniforge env (`/home/seung/miniforge3/bin/python -m pytest`):

- new test file `tests/test_reconstruct_floor_polygon.py` + appended
  `tests/test_adapter_mesh.py` (byte-equal default regression + concave path +
  degeneracy fallback).
- default (`-m "not lab and not web and not e2e"`): **312 passed / 5 skipped**
  (was 300 / 5 at v0.23.1 — +12 core tests this cycle).
- web (`-m web`): **86 passed / 4 skipped** (unchanged — no web source touched).
- full collection (`pytest -q`): **399 passed / 8 skipped**.
- ruff `roomestim tests`: clean.
- mypy `--strict roomestim`: 0 errors across 38 source files.
- lint_tense: exit 0.
- code-review: APPROVE-WITH-NITS (applied); independent verifier: PASS.

## ADR 0042 / OQ-13e linkage

- **ADR 0042** (`docs/adr/0042-live-mesh-corner-extraction.md`, §Status-update-v0.24.0)
  — the ADR specified an alpha-shape / concave-hull floor reconstruction with a
  byte-equal convex default and opt-in entry. This cycle lands the PR1-equivalent
  (algorithm + integration). The ADR header stays its original PROPOSED framing:
  parts remain unimplemented (see below), so it is **not** flipped to Accepted.
- **OQ-13e** (`.omc/plans/open-questions.md`) — stays **OPEN** with a
  partial-progress note. The concave-extraction code has landed (opt-in); the
  real-mesh corner-error ≤ 10 cm validation against an authoritative GT remains
  gated on SoundCam mesh download access, which is unavailable.

## Known deferred items

- **Non-tautological real-mesh validation** — the A10a corner test stays
  tautological (paper-dims shoebox compared to itself); its non-tautological
  promotion is gated on SoundCam mesh access (OQ-13e (i)). The dense-cloud
  ≤ 10 cm corner-error claim is therefore **not yet empirically validated on a
  real scan**.
- **RANSAC wall-plane fit** — NOT adopted (ADR 0042 §C). Walls remain
  floor-edge extrusion; the concave footprint extrudes to non-shoebox walls
  without a separate plane-fit stage.

## Versioning

- `roomestim`: `0.23.1` → `0.24.0` (MINOR). The additive
  `MeshAdapter(floor_reconstruction=...)` mode is a new observable behavior with
  no default change → MINOR not PATCH. `pyproject.toml` + `roomestim/__init__.py`.
- `roomestim_web`: `0.18-web.0` (unchanged — core change, no web source touched; D30).
- `__schema_version__`: `0.2-draft` (unchanged).

## Tag note

Local-only MINOR tag (no PyPI release).
