# roomestim v0.16.0 Release Notes

**Date**: 2026-05-18
**Core version**: `0.16.0` (MINOR bump)
**Web version**: `0.13-web.0` (web MINOR bump)

---

## What v0.15.2 missed

- No user-accessible path to correct per-surface materials after phone-scan
  ingest (users had to edit raw YAML directly).
- No 2D architectural blueprint export (Setup PDF had only a 3D viewer screenshot).
- No CLI toggle to skip engine schema validation for standalone YAML use-cases.

---

## What v0.16.0 ships

### ① Material Override (core + web)

**Core** (`roomestim/edit.py` NEW — 4 public helpers):
- `evolve_surface(surf, *, material, polygon)` — single-surface mutation with
  absorption auto-lookup from `MaterialAbsorption` / `MaterialAbsorptionBands`.
- `evolve_room(room, *, surfaces, listener_area, name)` — room-level mutation.
- `evolve_room_material(room, surface_index, material)` — convenience: one
  surface index → new room.
- `evolve_room_materials_bulk(room, changes: dict[int, MaterialLabel])` — atomic
  multi-surface change (web Apply button entry point).

All helpers use `dataclasses.replace` chain; `Surface` frozen invariant (ADR
0002) and ADR 0009 ISM ≥ Eyring invariant (D43) are preserved.

**Web**: Material Override Tab in `roomestim_web/app.py` — surface table +
Apply button (D40 manual recompute trigger). Acoustic report and RT60 bar chart
are recomputed on Apply.

### ③ 2D Blueprint Export (core + web)

**Core** (`roomestim/viz/blueprint.py` NEW):
- `render_blueprint(room, placement, out_path, *, fmt, dpi, ...)` — PNG (300
  dpi) or SVG export.
- Coordinate convention (D41): x=right, z=north-up (architectural drawing
  standard).
- Content layers: floor polygon, wall labels, listener area, speaker positions,
  dimension arrow, north arrow, 1 m scale bar.
- Byte-equal PNG determinism under matplotlib Agg backend (ADR 0032 §D).

**Web**: 2D Blueprint Tab + Setup PDF page 2.

### ④ Engine Validation Toggle (CLI + web)

**CLI** (`roomestim export`): mutually exclusive group:
- `--validate-engine PATH` — explicit engine repo dir (CLI > ENV > default; D42).
- `--no-engine-validation` — skip schema check; WARNING header prepended to
  output YAML (ADR 0033 §C audit trail).

**Web**: sidebar "Standalone YAML (skip engine schema check)" checkbox (default
OFF = validation ON).

---

## What stays the same

- `Surface` is `frozen=True`; `RoomModel` itself uses bare `@dataclass`
  (mutable, not `frozen=True`) for backward-compat with `PlacementResult` and
  existing adapters. Evolve helpers always return new instances —
  mutation-by-convention preserved. `RoomModel` frozen migration is a v0.17+
  candidate if no callsite mutates in-place (ADR 0031 §D).
- `__schema_version__ = "0.1-draft"` — no YAML schema bump in v0.16.
- ADR 0009 ISM ≥ Eyring runtime invariant preserved on all evolved rooms (D43
  regression lock: 50 random seeds).
- `roomestim/model.py` byte-equal (D39: edit logic lives in `roomestim/edit.py`).
- `write_layout_yaml` backward-compat: `validate=True` default, no flag needed.

---

## Test count

| Suite | v0.15.2 baseline | v0.16.0 | Delta |
|---|---|---|---|
| `pytest -m "not lab and not web"` | 161 passed + 4 skipped | 185 passed + 4 skipped | +24 |
| `pytest tests/web/` | 49 passed + 1 skipped | 55 passed + 1 skipped | +6 |

New test files: `tests/test_edit_room.py` (8), `tests/test_viz_blueprint.py`
(5), `tests/test_engine_toggle.py` (6), `tests/web/test_material_override_ui.py`
(4), `tests/web/test_blueprint_ui.py` (2).

---

## Migration note

**CLI export**: default behavior unchanged. `--no-engine-validation` is opt-in.

**Web UI**: two new output tabs (재질 정정, 2D 블루프린트) + one sidebar
checkbox. `_on_submit` return tuple expanded 7→10 (material_table,
blueprint_png, blueprint_svg added at positions 7-9). Existing tests that
unpacked the 7-tuple have been migrated to `*_extra` star-unpack.

**`from roomestim import evolve_room, ...`**: new public API, no breaking
changes to existing imports.

---

## New policy decisions

- **ADR 0031** — Material override policy + recompute trigger (D39/D40/D43).
- **ADR 0032** — 2D blueprint export + coordinate convention (D41).
- **ADR 0033** — Engine validation toggle precedence (D42).
- **ADR 0030 §Status-update-v0.16** — Items I/J/K closure.
- **D39–D43** — 5 new D-decisions.
- **OQ-31** — Multi-engine schema target deferral (v0.18+).

---

## Known gaps (v0.16.x+ / v0.17+)

- 3D viewer mesh color not updated after material override (OQ-32 NEW — v0.16.x
  patch candidate).
- `Surface.kind` enum extension for doors/windows/columns (v0.17 —
  `schema_version` bump to `"0.2-obstacles"` required).
- Per-wall absorption decomposition for mixed-material walls (OQ-30 v0.15.x+).
- HF Spaces deployment dry-run (ADR 0029 §B daemon thread policy unchanged).
- **MEDIUM-2 (deferred v0.16.1)**: `render_blueprint` does not force
  `matplotlib.use("Agg")` before the first import; non-Agg backends on some
  systems may produce non-byte-equal PNG output. Mitigation: add
  `matplotlib.use("Agg")` guard in `roomestim/viz/blueprint.py` before `import
  matplotlib.pyplot`.
- **MEDIUM-3 (deferred v0.16.1)**: positive-precedence test for CLI >
  ENV engine-validation flag is covered by the design but the
  `test_cli_export_cli_overrides_env` gate relies on a fake path — a live-path
  integration variant is not yet present. Add in next patch cycle.
- **LOW-1**: `_on_apply_overrides_wrapper` in `app.py` uses an inline `import
  json` via `__import__` to count changes; extract to a named helper in v0.16.1.
- **LOW-2**: Material Override Tab `changes_state` is pre-seeded to `"{}"` and
  is never updated by the surface-table Dataframe interaction — users must type
  JSON manually or via a future dropdown-to-JSON bridge (v0.16.x UX follow-up).
- **LOW-3**: `build_material_override_tab()` Dataframe uses `interactive=False`;
  editing is not yet wired (v0.16.x — Gradio dropdown column support pending
  verification per design §Phase 4 risk note).
