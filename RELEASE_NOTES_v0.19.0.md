# roomestim v0.19.0 — wall_index reference-frame fix + adapter schema_version unification

MINOR bump `0.18.5` → `0.19.0`. See ADR 0037
(`docs/adr/0037-wall-index-reference-frame.md`), D63 / D64
(`.omc/plans/decisions.md`), and OQ-42 (`.omc/plans/open-questions.md`).

## ① Viewer wall geometry correctness fix (D63, ADR 0037)

`Object.wall_index` is canonically zero-based into the **walls-only** surface
list (`[s for s in surfaces if s.kind == "wall"]`), NOT the full `surfaces`
array (`[floor, *ceilings, *walls]`).

The predictor (`reconstruct/predictor.py`) already used the walls-only frame for
its α overrides. The viewer (`roomestim_web/viewer.py:_wall_attached_traces`)
used the full-surfaces frame (`room.surfaces[obj.wall_index]`) — the single
divergent consumer. For any nonzero `wall_index` the two resolved to different
surfaces (e.g. `wall_index=0` was the first wall for the predictor but the FLOOR
for the viewer), so wall-attached door/window quads rendered against the wrong
surface. The viewer now mirrors the predictor. Out-of-range still returns `[]`
(robustness contract preserved). The acoustic path was untouched — zero
predictor edits, RT60 negative control byte-equal `1.9190766987173207`.

Locked by two regression tests using a door at `wall_index=2` (so the
floor/ceiling-vs-wall divergence is observable):

| Lane | Test |
|---|---|
| default | `tests/test_wall_index_frame.py` (predictor side) |
| web | `tests/web/test_wall_index_viewer.py` (viewer side) |

Both assert the predictor and viewer resolve to the **same** wall surface; both
fail on the pre-fix viewer code. The schema `wall_index` property
(`proto/room_schema.v0_2.draft.json`) gained a `description` documenting the
walls-only frame.

## ② MeshAdapter schema_version unified to 0.2-draft (D64)

`adapters/mesh.py` emitted `schema_version="0.1-draft"` while `RoomPlanAdapter`
and the `RoomModel` default emit `"0.2-draft"`. This was a stale label: mesh
output is never jsonschema-validated, so the change has no validation
consequence. Bumped to `"0.2-draft"`; one test updated
(`tests/test_adapter_mesh.py`). The 0.1-draft backward-parse path
(reader/exporter) is unchanged.

This output-contract change of a public adapter is the specific SemVer driver
for the MINOR bump (consumers keying on the emitted string see different output;
backward-compatible since the reader accepts both 0.1-draft and 0.2-draft).

## ③ CaptureAdapter Protocol repair (typing-only)

`roomestim/adapters/base.py` `CaptureAdapter.parse` Protocol signature gained
`octave_band: bool = False` (all three adapters already accepted it). The
`getattr(adapter, "parse")` shim in `roomestim/cli.py` (`_cmd_ingest`,
`_cmd_run`) — a workaround for the Protocol mismatch — was replaced with direct
`adapter.parse(...)`, with `_get_adapter` now returning `CaptureAdapter`. The
`# type: ignore[union-attr]` in `roomestim_web/pipeline.py` was removed. No
runtime behavior change; `mypy --strict roomestim/` stays at 0 errors — note
this gate scopes to `roomestim/` only (`pyproject.toml` `files = ["roomestim"]`),
so it statically verifies the `cli.py` shim removal but NOT the `roomestim_web/`
edits (`pipeline.py`, `viewer.py`), which are outside mypy scope. Scoping mypy
to cover `roomestim_web/` is deferred (it would surface pre-existing
`plotly`/`gradio` untyped-import noise — a separate hygiene task).

## What stays the same

| Item | Value |
|---|---|
| `__schema_version__` | `0.2-draft` (no RoomModel field change) |
| RT60 negative control | `1.9190766987173207` (acoustic path untouched) |
| Predictor `_objects_to_wall_alpha_overrides` | byte-equal (canon = its existing behavior) |
| 0.1-draft backward-parse (reader/exporter) | unchanged |
| All prior §Status-update blocks (D22) | byte-equal |

## Versioning

- `roomestim`: `0.18.5` → `0.19.0` (MINOR — ② mesh schema_version output
  change). `pyproject.toml` + `roomestim/__init__.py`.
- `roomestim_web`: `0.15-web.0` → `0.16-web.0` (D30 — ① edits
  `roomestim_web/viewer.py`, a real runtime-source behavior fix, so the
  parallel-track string advances one minor alongside the core MINOR).

## Known deferred items

- **OQ-42** (NEW, opened this cycle) — ④ hardcoded engine-schema absolute path
  fallback (`layout_yaml.py:57–59`). Portability/UX wart, orthogonal to ①/②/③;
  blast radius touches `tests/test_export_layout_yaml.py`,
  `tests/test_engine_toggle.py`, cli help, and ADR 0033. Cadence v0.20.
- OQ-40 gradio `col_count` Dataframe-kwarg deprecation noise (web lane).
- OQ-37 `notes` round-trip / OQ-38 DBAP/AMBISONICS label collapse (v0.20 re-exam).
- OQ-30 per-wall α decomposition; OQ-34/35 (v0.21 re-exam).

## Tag note

Local-only MINOR tag (no PyPI release).
