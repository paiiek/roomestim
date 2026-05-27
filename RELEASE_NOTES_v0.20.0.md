# roomestim v0.20.0 — robustness hardening

MINOR bump `0.19.0` → `0.20.0`. See ADR 0033 §Status-update-v0.20.0
(`docs/adr/0033-engine-validation-toggle.md`), ADR 0027 §Status-update-v0.20.0
(`docs/adr/0027-mesh-format-generalisation.md`), D65 / D66 / D67
(`.omc/plans/decisions.md`), and OQ-42 / OQ-21 (`.omc/plans/open-questions.md`).

This cycle is the architect priority list item ④ (engine-schema path, closes
OQ-42) plus two low-risk robustness add-ons (PLY no-faces guard closes OQ-21;
removal of the misleading ambisonics stub export). No acoustic-path edits.

## ① Engine-schema resolution: descriptive error (D65, OQ-42 CLOSED)

`export/layout_yaml.py` previously returned the hardcoded
`_DEFAULT_ENGINE_SCHEMA_PATH` whenever neither `SPATIAL_ENGINE_REPO_DIR` nor
`--validate-engine` resolved a file; a genuinely-missing schema then surfaced
only as a bare deep `FileNotFoundError` from `schema_file.open()` —
non-portable and unactionable off the author machine.

v0.20.0 routes all three open sites (`_load_engine_schema`, `write_layout_yaml`,
`validate_placement`) through one guard `_assert_schema_file_exists`, which
raises a single descriptive `FileNotFoundError` tagged `kErrEngineSchemaNotFound`
naming all three escape hatches:

```
kErrEngineSchemaNotFound: engine geometry schema not found at <path>. Set
SPATIAL_ENGINE_REPO_DIR=<spatial_engine repo dir>, pass --validate-engine <dir>,
or use --no-engine-validation to skip (ADR 0033).
```

The documented `CLI > ENV > default` precedence (ADR 0033 §B) is RETAINED and
`_DEFAULT_ENGINE_SCHEMA_PATH` stays as the documented fallback constant. This
honors §E intent (no silent missing-schema failure) WITHOUT firing §E's
breaking-removal trigger — the default path is not yet *permanently* unavailable.
Option (b) warn-and-skip was rejected (collides with the `--no-engine-validation`
audit-trail opt-out); option (c) vendoring a schema copy was rejected (the engine
schema is deliberately un-vendored to avoid drift).

**Behavior delta**: byte-identical output and exit codes on any host where the
schema resolves; only a host where it is genuinely absent sees the new
(actionable) error instead of the bare one. CLI help text dropped the "hardcoded
default" phrasing.

Locked by `tests/test_export_layout_yaml.py::test_engine_schema_missing_raises_descriptive`
(monkeypatches resolution to a non-existent dir, asserts the error names all
three escape hatches). `tests/test_engine_toggle.py` docstrings were re-worded to
the error-on-missing semantics; the ENV/CLI-precedence tests themselves supply a
valid schema dir and are unchanged.

## ② PLY no-faces guard (D66, OQ-21 CLOSED)

A points-only PLY (vertices, zero triangular faces — a degenerate point-cloud
export) loads via `trimesh.load(force="mesh")` as a `Trimesh` with
`len(faces)==0`. The existing `(N, 3)` vertex-shape check does NOT catch it, so
the input reached the convex-hull-of-projection path (undefined for a point
cloud). `MeshAdapter._room_model_from_mesh` now rejects it right after the
vertex-shape check:

```
MeshAdapter: mesh has 0 faces (points-only PLY); a surface mesh with triangular
faces is required.
```

New fixture `tests/fixtures/points_only.ply` (vertices only, `element face 0`) +
`tests/test_adapter_mesh.py::test_mesh_adapter_points_only_ply_raises` lock it.
This closes the v0.12-web.1 "known degenerate case" without vendoring. The
existing 4-format parse test and the vertex-color PLY test (faces present) are
unaffected; the convex-hull floor contract (D6) is otherwise byte-equal.

## ③ Ambisonics stub export removed (D67)

`roomestim/place/ambisonics.py` was a pure `NotImplementedError` stub whose only
consumer was the `place/__init__.py` re-export — NOT in `dispatch.py`, NOT a CLI
`--algorithm {vbap,dbap,wfs}` choice, NOT imported by any test. The file was
deleted and the import + `"place_ambisonics"` `__all__` entry removed from
`place/__init__.py` (module docstring de-"Ambisonics"-ed). This leaves zero
misleading public surface; `from roomestim.place import place_ambisonics` now
raises `ImportError`. Not a breaking change in the D33 sense (the stub was never
functional and never wired to CLI/dispatch). A future revival of ambisonics gets
a real implementation plus an ADR.

## What stays the same

| Item | Value |
|---|---|
| `__schema_version__` | `0.2-draft` (no RoomModel field change) |
| RT60 negative control | `1.9190766987173207` (acoustic path untouched) |
| `CLI > ENV > default` precedence | retained (ADR 0033 §B) |
| `_DEFAULT_ENGINE_SCHEMA_PATH` constant | retained (documented fallback) |
| layout.yaml byte output (schema present) | byte-equal |
| All prior §Status-update blocks (D22) | byte-equal |

## Versioning

- `roomestim`: `0.19.0` → `0.20.0` (MINOR). The observable engine-schema
  resolution contract changes for callers without the engine repo (bare
  `FileNotFoundError` → guided actionable error), and the PLY no-faces guard adds
  a defined error path for a previously-undefined input — additive/behavioral
  public-contract changes, hence MINOR not PATCH. `pyproject.toml` +
  `roomestim/__init__.py`.
- `roomestim_web`: NOT touched → stays `0.16-web.0` (no `roomestim_web/` file
  changes this cycle).

## Known deferred items

- **PolycamAdapter alias removal** — excluded (BREAKING; D33 reverse-criterion
  requires a successor D-decision + a "Breaking changes" callout; out of scope).
- OQ-40 gradio `col_count` Dataframe-kwarg deprecation noise (web lane).
- OQ-37 `notes` round-trip / OQ-38 DBAP/AMBISONICS label collapse.
- OQ-30 per-wall α decomposition; OQ-34/35.

## Audit findings (multi-perspective review, deferred)

A whole-engine independent review (critic + security + functional-QA + verifier)
ran against this changeset. Verdict: **v0.20.0 safe to commit; the full feature
set works end-to-end (37/37 functional checks pass, all gates green)**. The review
surfaced pre-existing latent issues (NOT v0.20.0 regressions), now tracked:

- **OQ-43** — `edit.py` dual surface-index frame (`evolve_room_material` full-list
  vs `wall_index` walls-only): the same class as the v0.19.0 wall_index bug,
  currently dormant. **Recommended next correctness cycle.**
- **OQ-44** — silent whole-room ISM→Eyring downgrade on out-of-range `wall_index`
  (no upper-bound at object-add/reader) + `evolve_surface` single→per-band
  promotion on material edit.
- **OQ-45** — web public-deployment hardening (unbounded mesh-parse DoS, stale-dep
  CVEs, dev-path/exception leak into web errors, tempdir reaper scope,
  `on_apply_overrides` list-input crash). Gated on a public-deployment decision.

## Tag note

Local-only MINOR tag (no PyPI release).
