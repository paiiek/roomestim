# roomestim v0.21.0 — edit/predict correctness

MINOR bump `0.20.0` → `0.21.0`. See ADR 0037 §Status-update-v0.21.0
(`docs/adr/0037-wall-index-reference-frame.md`), ADR 0031 §Status-update-v0.21.0
(`docs/adr/0031-material-override-policy.md`), D68 / D69 / D70
(`.omc/plans/decisions.md`), and OQ-43 / OQ-44 (`.omc/plans/open-questions.md`).

This cycle (Cycle A of the v0.21 post-audit fix-program) closes the two
correctness items the v0.20.0 multi-perspective audit surfaced: OQ-43 (dual
surface-index frame, the wall_index bug's latent twin) and OQ-44 (silent
state/predictor changes on out-of-range or edited input). The numeric acoustic
path is byte-equal for valid input.

## ① Shared walls-only surface-index resolver (D68, OQ-43 CLOSED)

Two "surface index" frames coexisted with no shared authority:
`evolve_room_material` / `evolve_room_materials_bulk` index the FULL
`room.surfaces` list (correct for their only shipping caller — the web Material
Override Tab), while `Object.wall_index` resolves on the WALLS-ONLY filtered list
(predictor α overrides + web 3D viewer; ADR 0037). Because adapter surface order
is not uniform (`roomplan.py` `[floor, *ceilings, *walls]`; `mesh.py`
`[floor, ceiling, *walls]`; `ace_challenge.py` trailing floor), a future
"edit wall N" feature wiring a walls-relative index into `evolve_room_material`
would patch the WRONG surface — the exact latent condition that produced the
v0.19.0 defect.

`roomestim/model.py` gained two module-level read accessors:

- `wall_surfaces(room) -> list[Surface]` — the ONE walls-only authority.
- `surface_index_for_wall(room, wall_ordinal) -> int` — bridges a walls-only
  ordinal to its full-`room.surfaces` index (`IndexError` out of range).

The four predictor walls-only filters and the web viewer's `_wall_attached_traces`
filter now route through `wall_surfaces` — identical result, single source. This
is **additive + defensive only**: `evolve_room_material` / `_bulk` signatures and
full-list-index semantics are byte-identical; no shipping caller passes a
walls-relative index into them yet.

Characterization test `tests/test_surface_index_frame.py` (the `edit.py`-side
analogue of `tests/test_wall_index_frame.py`) pins
`wall_surfaces(room)[k] is room.surfaces[surface_index_for_wall(room, k)]` across
two adapter orderings: RoomPlan `[floor, ceiling, wall×4]` (ordinal 2 → full
index 4) + an inline synthetic trailing-floor `RoomModel` (chosen as the cheapest
ordering-independence proof, no mesh fixture). Revert-sanity confirmed the test
fails under a naive identity resolver (load-bearing).

## ② ISM→Eyring downgrade is now diagnosable (D69, OQ-44(a))

An out-of-range `wall_index` on a door/window makes
`_objects_to_wall_alpha_overrides` raise, which `predict_rt60_default` /
`predict_rt60_default_per_band` catch and gracefully downgrade the whole room
ISM→Eyring — but the offending index (carried in the exception text) was
discarded from the rationale. The fallback rationale tail now surfaces it:

```
... ISM fallback to Eyring (ValueError: object wall_index=999 out of range ...)
```

This is a **rationale-string-only** change: `rt60_s` is computed by `eyring_rt60`
on the same inputs → byte-equal for the fallback path, and the valid-input ISM
numeric path is untouched (negative control `1.9190766987173207` byte-equal). The
graceful fallback is PRESERVED — a bad object still never crashes RT60; the
downgrade is now merely visible. Locked by
`tests/test_objects_acoustic_invariant.py::test_out_of_range_wall_index_rationale_carries_index`
(pins `"999"` in both scalar + per-band rationale).

## ③ wall_index upper-bound at every entry point (D69, OQ-44(b))

`Object.wall_index` had no upper bound at any entry point, so an out-of-range
index reached predict time and silently downgraded the whole-room RT60. The bound
`0 <= wall_index < len(wall_surfaces(room))` is now enforced for door/window
objects at the three independent entry points:

- `read_room_yaml` — raises `ValueError` post object-parse (the reader is
  context-free per-object, so the bound lives in `read_room_yaml`).
- `roomestim_web.object_add._on_add_object` — user-facing error string, room
  returned unchanged, no crash.
- `RoomPlanAdapter._room_model_from_sidecar` — raises. The adapter DOES emit
  objects (`_extract_objects` maps door/window/column categories with
  `wall_index`), so this guard is LIVE, not dead.

Revert-sanity confirmed the reader-bound test fails when the guard is removed
(load-bearing). New tests:
`tests/test_objects.py::test_read_room_yaml_rejects_out_of_range_wall_index` (+
in-range round-trip), and `tests/web/test_object_add_ui.py` reject/accept cases.

## ④ evolve_surface band-promotion gated on source bands (D70, OQ-44(c))

`evolve_surface` unconditionally set `absorption_bands =
MaterialAbsorptionBands[material]` on a material change, promoting a single-band
surface (`absorption_bands=None`, the `octave_band=False` ingest default) to
per-band — silently shifting an edited room onto the per-band predictor branch.
The promotion is now gated on `surf.absorption_bands is not None`; the scalar
`absorption_500hz` update stays UNCONDITIONAL (single-band rooms keep correct
500 Hz acoustics). Single-band surfaces stay single-band after a material edit;
per-band surfaces still refresh their bands.

**Commit-coupling note (load-bearing):** this gate necessarily changes the
contract of `tests/test_edit_room.py::test_evolve_surface_material_only`, which
was split into `test_evolve_surface_material_only_single_band_stays_none` (None
stays None) + `test_evolve_surface_material_only_per_band_promotes` (bands still
refresh). **If the gate is reverted, BOTH tests must revert with it** — do not
decouple them in a bisect.

## What stays the same

| Item | Value |
|---|---|
| `__schema_version__` | `0.2-draft` (no RoomModel field added — the two `model.py` functions are accessors) |
| RT60 negative control | `1.9190766987173207` (valid-input numeric path byte-equal) |
| `evolve_room_material` / `_bulk` signatures + full-list-index semantics | byte-identical |
| Graceful Eyring fallback on a bad object | preserved (now diagnosable, never fatal) |
| Viewer out-of-range robustness contract | preserved (returns `[]`) |
| All prior §Status-update blocks (D22) | byte-equal |

## Versioning

- `roomestim`: `0.20.0` → `0.21.0` (MINOR). OQ-44(b) adds an observable new error
  path (out-of-range `wall_index` now raises at load / errors in the web),
  OQ-44(a) changes the observable rationale string, and OQ-44(c) changes the
  observable band-promotion contract of a public `edit.py` helper —
  behavior-observable-from-outside changes, hence MINOR not PATCH. OQ-43 alone
  would be PATCH (pure additive helper + test) but rides the MINOR bundle.
  `pyproject.toml` + `roomestim/__init__.py`.
- `roomestim_web`: `0.16-web.0` → `0.17-web.0`. `roomestim_web/object_add.py`
  (OQ-44(b) bound) and `roomestim_web/viewer.py` (OQ-43 resolver routing) are
  touched → web source changes → bump required (`roomestim_web/__init__.py`).

## Known deferred items

- **OQ-45** — web public-deployment hardening (unbounded mesh-parse DoS,
  stale-dep CVEs, dev-path/exception leak into web errors, tempdir reaper scope,
  `on_apply_overrides` list-input crash). Cycle B of the v0.21 fix-program; gated
  on a public-deployment decision.
- **PolycamAdapter alias removal** — excluded (BREAKING; D33).
- OQ-37 `notes` round-trip / OQ-38 DBAP/AMBISONICS label collapse; OQ-30 per-wall
  α decomposition; OQ-34 / OQ-35.

## Tag note

Local-only MINOR tag (no PyPI release).
