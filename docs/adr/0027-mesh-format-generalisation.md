# ADR 0027 — Mesh-format generalisation via single MeshAdapter

- **Status**: Accepted (v0.12-web.1)
- **Date**: 2026-05-15b
- **Cross-ref**: D33 (MeshAdapter rename rationale), D6 (convex-hull-of-projection
  deferral), ADR 0024 (web demo separate package; parallel-track boundary),
  OQ-20 (glTF binary byte-equal reproducibility), OQ-21 (PLY no-faces degenerate
  case), `.omc/plans/v0.12-web.1-design.md` §6.

## Status

Accepted (v0.12-web.1).

## Context

v0.12-web.0 shipped a `PolycamAdapter` that accepted only `.obj` files — a name
and scope mismatch from day one, since the class parsed any OBJ mesh (not Polycam
exports exclusively) and HF Spaces users export room scans in a mix of formats:
Polycam (`.usdz` / `.obj`), Reality Capture (`.gltf`), Apple Object Capture (`.ply`),
and Sketchfab (`.glb`). Four new mesh formats were requested without requiring any new
core dependency because `trimesh>=4.0` (already pinned in `pyproject.toml`) natively
loads all four via `trimesh.load(force="mesh")`.

Two surfacing options were available: (i) rename `PolycamAdapter` → `MeshAdapter` and
retain the old name as a deprecated alias; (ii) keep `PolycamAdapter` as-is and add
a new sibling class. Option (i) was chosen (D33).

## Decision

Generalise the OBJ-only `PolycamAdapter` into a single mesh-format-agnostic
`MeshAdapter` (new module `roomestim/adapters/mesh.py`) accepting `.obj`, `.gltf`,
`.glb`, `.ply` via `trimesh.load(force="mesh")`. The convex-hull-of-vertex-projection
geometry, the default `MaterialLabel` triple (`WALL_PAINTED` + `WOOD_FLOOR` +
`CEILING_DRYWALL`), and `RoomModel.schema_version="0.1-draft"` were all preserved
byte-equal across the four mesh formats.

`PolycamAdapter` was retained as a `DeprecationWarning`-emitting subclass alias in
`roomestim/adapters/polycam.py` (D33). `.usdz` continued to raise
`NotImplementedError` (no `[usd]` extra in default CI). `.json` (RoomPlan sidecar)
continued to delegate to `RoomPlanAdapter` directly from `pipeline.py` — the `.json`
route was NOT handed to `MeshAdapter` in order to preserve the byte-equivalence claim
cleanly across the rename.

## Drivers

1. **HF Spaces on-ramp**: users export room scans from Polycam (`.usdz`/`.obj`),
   Reality Capture (`.gltf`), Apple Object Capture (`.ply`), and Sketchfab (`.glb`);
   accepting all four closed the v0.12-web.0 on-ramp gap.
2. **Zero new core dependency**: `trimesh>=4.0` was already pinned and natively loads
   all four formats.
3. **Rename over shim** (D33): the v0.1-era class name `PolycamAdapter` no longer
   matched its actual scope; renaming avoided freezing the misnomer as the canonical
   implementation.
4. **Backward compatibility**: `isinstance(PolycamAdapter(), MeshAdapter)` returned
   `True`; all duck-typing call sites continued to work byte-equal.

## Consequences

- **(+)** Users uploaded `.gltf`, `.glb`, and `.ply` room scans to the Gradio demo
  without any new install step.
- **(+)** `PolycamAdapter` deprecation surfaced in pytest only when a caller invoked
  `.parse()` (one `DeprecationWarning` per location); existing tests passed byte-equal
  because pytest's default capture mode deduped and did not fail on warnings.
- **(−) glTF axis-convention caveat**: `trimesh.load(force="mesh")` flattened
  scene-graph transforms but did NOT correct for source-tool axis conventions (Reality
  Capture: Z-up; Polycam OBJ: Y-up; Apple Object Capture: variable). `MeshAdapter`
  used the convex-hull-of-XY-projection (`vertices[:,0]` + `vertices[:,1]`) for the
  floor polygon and `vertices[:,2]` max−min for ceiling height. For glTF/glb files
  exported with a Z-up root transform, the result was geometrically valid but the
  "floor" and "ceiling" axes were swapped relative to the user's intent. Documented
  as a known caveat in `RELEASE_NOTES_v0.12-web.1.md` § "Known gaps"; OQ-20 broadened
  to cover this case.
- **(−) glTF scene-graph semantic material labels NOT extracted**: `trimesh.load(force="mesh")`
  flattened to a single mesh; only vertex coordinates were used — same caveat as `.obj`
  (D6).
- **(−) Alpha-shape reconstruction (D6) deferred to v0.3**: v0.12-web.1 inherited the
  convex-hull caveat byte-equal across all four mesh formats.
- **(−) PLY no-faces degenerate case (OQ-21)**: if a user uploaded a points-only PLY
  (no triangular faces), `trimesh.load(force="mesh")` returned a `Trimesh` with 0
  faces; the existing `vertices.shape[1] != 3` guard did NOT catch this. Documented
  as a known gap; resolution deferred to v0.12-web.2 on user report.

## §Status-update-v0.18.5 (2026-05-27)

**D62 — internal test-caller migration (D33 intended end-state).** The four
`tests/web/*.py` files that used the deprecated `PolycamAdapter` alias purely
as a generic mesh parser were migrated to the canonical `MeshAdapter`:
`tests/web/test_setup_pdf.py` (import :12, parse :19),
`tests/web/test_acoustic_report.py` (import :9, parse :15),
`tests/web/test_binaural_renderer.py` (import :24, parse :79),
`tests/web/test_3d_viewer.py` (import :11, construct :19). Each parse target
is `tests/fixtures/lab_room.obj` (a `.obj` mesh); the swap is
behavior-preserving (`PolycamAdapter(MeshAdapter)` only adds the
`DeprecationWarning` + a `.json`-delegation branch, neither of which applies
to a `.obj` input). Effect: the four files emit zero `PolycamAdapter`
`DeprecationWarning`s; the alias's intentional warning now fires only from the
contract test `tests/test_adapter_polycam.py` (the desired single canonical
trigger).

The alias is **NOT removed** (D33 reverse-criterion still gates full removal —
full removal is a BREAKING change requiring a successor D-decision and a
"Breaking changes" RELEASE_NOTES callout). The shim docstring's "removal at
v0.14 or later" is noted as stale (we are at v0.18.x); editing it would imply
a removal commitment not made this cycle; it remains as-is pending a future
removal decision. `cli.py` `_get_adapter("polycam")` and the contract test
`tests/test_adapter_polycam.py` are byte-equal (DO-NOT-TOUCH invariants —
see D62 for rationale). New OQ filed: OQ-40 (gradio `col_count` deprecation
noise — a separate, deferred web-lane source). PATCH bump `0.18.4 → 0.18.5`.

## §Status-update-v0.20.0 (2026-05-28)

**D66 — PLY no-faces guard (OQ-21 CLOSED).** A points-only PLY (vertices but no
triangular faces — a degenerate point-cloud export) loads via
`trimesh.load(force="mesh")` as a `Trimesh` with `len(faces)==0`. The existing
`(N, 3)` vertex-shape check does NOT catch this (the array is still 2-D with 3
columns, or `(0, 3)` after trimesh drops unreferenced vertices), so the input
slipped through to the convex-hull-of-projection path, which is undefined for a
point cloud. `MeshAdapter._room_model_from_mesh` now adds a guard right after the
vertex-shape check: `faces = np.asarray(getattr(loaded, "faces", []))` →
`if len(faces) == 0: raise ValueError("MeshAdapter: mesh has 0 faces
(points-only PLY); a surface mesh with triangular faces is required.")`. New
fixture `tests/fixtures/points_only.ply` (vertices only, `element face 0`) +
`tests/test_adapter_mesh.py::test_mesh_adapter_points_only_ply_raises` lock it;
the existing 4-format parse test and the vertex-color PLY test (faces present)
are unaffected. This resolves the v0.12-web.1 "known degenerate case" without
vendoring. The mesh output contract (convex-hull floor, D6) is otherwise
byte-equal. MINOR bump `0.19.0 → 0.20.0` (the no-faces guard adds a new
validation error path for a previously-undefined input).

## Follow-ups

- **OQ-20** — glTF binary (`.glb`) byte-equal reproducibility across trimesh versions.
- **OQ-21** — PLY files with vertex colour but no faces (points-only degenerate case).
  CLOSED v0.20.0 (no-faces guard; D66 / ADR 0027 §Status-update-v0.20.0).

## References

- D33 — `.omc/plans/decisions.md` (MeshAdapter rename rationale; PolycamAdapter
  deprecated subclass alias).
- D6 — `.omc/plans/decisions.md` (convex-hull-of-vertex-projection deferral; floor
  polygon geometry unchanged across all four mesh formats).
- ADR 0024 — `docs/adr/0024-web-demo-separate-package.md` (parallel-track package
  boundary; `roomestim_web/` sibling; preserved byte-equal at v0.12-web.1).
- OQ-20 / OQ-21 — `.omc/plans/open-questions.md` (follow-up open questions).
- `roomestim/adapters/mesh.py` — `MeshAdapter` implementation.
- `roomestim/adapters/polycam.py` — deprecated subclass alias shim.
- `roomestim/adapters/__init__.py` — `MeshAdapter` + `PolycamAdapter` exports.
- `roomestim_web/pipeline.py` — format dispatch (`MESH_SUFFIXES` set; `.json` →
  `RoomPlanAdapter` direct path preserved).
- `tests/test_adapter_mesh.py` — parametrised 4-format + 1-usdz-negative acceptance
  tests.
- `RELEASE_NOTES_v0.12-web.1.md` — v0.12-web.1 release notes (§ "Known gaps").
- `.omc/plans/v0.12-web.1-design.md` §6 — ADR sketch source.
