# roomestim v0.16.1 — Patch Release Notes (2026-05-18)

**Predecessor**: v0.16.0 (`2d71523`). **Type**: PATCH — v0.16.0 follow-up closure (no new policy).

---

## §What v0.16.0 missed

v0.16.0 code-review absorbed HIGH-1/MEDIUM-1/MEDIUM-4/HIGH-2 and deferred 5 follow-ups + OQ-32:

| Item | Source | Issue |
|---|---|---|
| MEDIUM-2 | `roomestim/viz/blueprint.py` | `matplotlib.use("Agg")` was inside `render_blueprint()` body — import-only consumers could break PNG byte-equal determinism if another backend was initialised first |
| MEDIUM-3 | `tests/test_engine_toggle.py` | CLI > ENV precedence test was negative-only (CLI invalid path → fail); positive variant (CLI valid → success, ENV anti-permissive → would fail) was missing |
| LOW-1 | `roomestim_web/app.py` | Inline `__import__("json").loads(...)` in `_on_apply_overrides_wrapper` — not testable, not readable |
| LOW-2 | `roomestim_web/material_override.py` | Dataframe `interactive=False` — no Dataframe → `changes_state` auto-update |
| LOW-3 | `roomestim_web/material_override.py` | Same line as LOW-2 — no Dataframe interaction wiring |
| OQ-32 | `roomestim_web/app.py` + `viewer.py` | 3D viewer mesh color stale after Apply (room.material updated, Plotly figure not rebuilt) |

---

## §What v0.16.1 fixes

### Item L — MEDIUM-2: matplotlib Agg backend module-level guard

- `roomestim/viz/blueprint.py`: `try: import matplotlib; if backend != "agg": matplotlib.use("Agg", force=True); except ImportError: pass` block added at import time (after `from __future__` line).
- Existing `matplotlib.use("Agg")` inside `render_blueprint()` body removed (now redundant).
- `graceful degradation`: `try/except ImportError` preserves behaviour when `[viz]` extra absent.
- New test: `test_blueprint_module_locks_agg_backend` — imports module, asserts `matplotlib.get_backend().lower() == "agg"`.

### Item M — MEDIUM-3: positive CLI > ENV integration test

- `tests/test_engine_toggle.py`: `test_cli_export_cli_overrides_env_positive_success` added (6 → 7 test cases).
- ENV = anti-permissive schema (`required: [__MUST_NOT_EXIST_PROP__]`) — would reject layout YAML.
- CLI = permissive schema (`{"type": "object"}`) — accepts any object → exit 0 + layout.yaml + no WARNING.
- Proof: if ENV were used, required-prop validation would reject the YAML → non-zero exit.
- Existing negative variant (`test_cli_export_cli_overrides_env`) retained.

### Item N — LOW-1: app.py JSON import refactor

- `roomestim_web/app.py`: module-level `import json` added; `_count_changes(changes_json: str) -> int` named helper extracted (module-level, testable).
- Helper returns 0 on empty string / invalid JSON / non-dict (`JSONDecodeError`, `ValueError`, `TypeError` all caught).
- New test: `test_count_changes_helper` — 5 inputs → 0/0/1/0/0 regression lock.

### Item O — LOW-2 + LOW-3: Dataframe interactive wiring + changes_textbox

- `roomestim_web/material_override.py`:
  - `gr.Dataframe(interactive=True, label="표면 목록 (material 열 클릭하여 재질 정정)")`.
  - `changes_textbox: gr.Textbox` added — shows current JSON, user can also edit directly.
  - `_dataframe_to_changes_json(rows, initial_room) -> str` helper (~30 LoC) — diffs current rows against baseline, emits only changed entries.
  - Return dict extended: `{"tab", "dataframe", "apply_btn", "status_md", "changes_textbox"}`.
- `roomestim_web/app.py`:
  - `_dataframe_to_changes_json` imported from `material_override`.
  - `_changes_textbox` extracted from `_mat_comps`.
  - Dataframe `change` event → `_changes_textbox` → `changes_state` wiring (try/except fallback).
- New tests: `test_dataframe_changes_to_json_helper` + `test_dataframe_changes_to_json_no_change`.

### Item P — OQ-32 CLOSED: 3D viewer mesh color refresh on Apply

- `roomestim_web/app.py`:
  - `layout_state: gr.State = gr.State(value=None)` added alongside `room_state`.
  - `_on_submit` return: 11-tuple → 12-tuple (last element = `result.layout`); all 4 return paths updated.
  - `submit_btn.click outputs` extended to 12 elements (`layout_state` added at index 11).
  - `_on_apply_overrides_wrapper`: 2-arg → 3-arg (`room, layout, changes_json`); returns 5-tuple → 6-tuple (`viewer_plot` added at index 1); `build_room_figure(new_room, layout)` called after material evolve.
  - `_apply_btn.click inputs=[room_state, layout_state, changes_state]` / `outputs=[room_state, viewer_plot, report_plot, report_json, _override_status_md, changes_state]`.
- `roomestim_web/viewer.py`: byte-equal (color mapping already correct in v0.13+; only re-call needed).
- New test: `test_apply_returns_viewer_figure` — 6-tuple + `result[1]` non-None regression lock.

---

## §What stays the same

- ADR 0030 §A–§E (predictor cascade policy) byte-equal — no ISM/Eyring change.
- ADR 0031 (material override policy), ADR 0032 (blueprint), ADR 0033 (engine toggle) byte-equal.
- RoomModel frozen invariant (D3) preserved.
- ADR 0009 ISM ≥ Eyring invariant preserved on all evolved rooms (D43 regression lock unmodified).
- `__schema_version__ = "0.1-draft"` unchanged.
- `roomestim_web/viewer.py` byte-equal.
- No new ADR / D-decision / OQ (OQ-32 is closed, not new).

---

## §Test count table

| Lane | v0.16.0 | v0.16.1 | Delta |
|---|---|---|---|
| default (`-m "not lab and not web"`) | 185 passed + 4 skipped | 187 passed + 4 skipped | +2 (blueprint guard, engine toggle positive) |
| web (`tests/web/`) | 48 passed + 4 skipped | 51 passed + 5 skipped | +3 non-web-marked new tests pass; +1 web skip |

Note: web lane `@pytest.mark.web` tests requiring Gradio skip on environments without `fsspec`
(system Python 3.12 without miniforge). This is a pre-existing env drift (same as v0.15.1 footnote).
The 6 pre-existing failures (`ModuleNotFoundError: fsspec`) are unchanged.

---

## §Migration note

- `_on_submit` returns 12-tuple (was 11). Callers using positional unpacking must extend to 12.
- `_on_apply_overrides_wrapper` returns 6-tuple (was 5). `layout` is new 2nd input arg.
- Both are internal helpers — `roomestim_web` has no public API contract for these.

---

## §Known gaps (v0.17+ deferral)

- OQ-30 per-wall α decomposition (v0.15.x+).
- OQ-23 polygon ISM non-shoebox (v0.15.x+).
- OQ-31 stable surface ID (v0.18+).
- `Surface.kind` enum extension — column/door/window (v0.17 schema bump).
- USDZ/gLTF export (v0.17).
- Speaker nudge + layout round-trip (v0.18).

No new known gaps introduced in v0.16.1.

---

## §Tag: local-only

D30 web-track versioning patron. `roomestim_web.__version__` `0.13-web.0` → `0.13-web.1`.
HF Spaces redeploy triggered by PATCH bump (expected; no system dep changes, packages.txt byte-equal).
