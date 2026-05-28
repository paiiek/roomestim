# roomestim v0.22.0 — web public-deployment hardening

MINOR bump `0.21.0` → `0.22.0`. See ADR 0038
(`docs/adr/0038-input-resource-bounds.md`, NEW), ADR 0024 §Status-update-v0.22.0
(`docs/adr/0024-web-demo-separate-package.md`), ADR 0033 §Status-update-v0.22.0
(`docs/adr/0033-engine-validation-toggle.md`), D71 (`.omc/plans/decisions.md`),
and OQ-45 (CLOSED) / OQ-46 (NEW) (`.omc/plans/open-questions.md`).

This cycle (Cycle B of the v0.21 post-audit fix program, the final cycle) closes
OQ-45 — the five web public-deployment hardening items the v0.20.0
multi-perspective security audit surfaced. The audit found NO CRITICAL/RCE (YAML
`safe_load` uniform; no eval/exec/pickle/shell); these are defense-in-depth on a
publicly-deployable Gradio Space. The numeric acoustic path is byte-equal.

## ① Mesh input resource bounds (ADR 0038, SemVer-MINOR driver)

`MeshAdapter` now bounds untrusted mesh input at the single adapter chokepoint
reachable from every entry path (CLI, library, web), via two env-overridable
module constants:

- `_MAX_MESH_FILE_BYTES` — default ~200 MB; override `ROOMESTIM_MAX_MESH_BYTES`.
  The **pre-load parse-memory bound**: checked in `parse()` via
  `Path.stat().st_size` **before** `trimesh.load` reads the bytes, so a
  DoS-sized file is rejected before it is parsed into memory. This is the
  load-bearing parse-memory guard.
- `_MAX_MESH_VERTICES` — default 5,000,000; override `ROOMESTIM_MAX_MESH_VERTICES`.
  A **post-parse hull-projection guard**, NOT a parse-memory bound: it runs
  AFTER `trimesh.load` (in `_room_model_from_mesh`, after the `(N, 3)`
  vertex-shape check and before the 0-faces guard; ordering: shape →
  vertex-count → faces) and bounds the O(N) convex-hull projection that follows.
  It does NOT bound the memory `trimesh.load` itself consumes — the byte-cap
  does that.

Both raise a clear `ValueError` naming the offending size and the env knob. A
matching Gradio `max_file_size` cap is bound on the Blocks object in
`build_demo()` (`demo.max_file_size = _MAX_UPLOAD_BYTES`) so gradio's server
honors it regardless of launch path — gradio 6.14.0's `gr.Blocks` ctor does NOT
accept `max_file_size` (only `launch()` does), and the HF Spaces root `app.py`
(`demo = build_demo(); demo.launch()`) never runs `roomestim_web`'s `__main__`
guard, so a launch-only cap would be inert in production. This is gradio's own
server-side size rejection at the request boundary (gradio still streams the
upload to a temp file before handlers run — it is NOT a "before bytes hit disk"
guard). The SemVer-MINOR driver is the adapter change: `parse()` gains a new
observable error path on oversized input.

New core tests (`tests/test_adapter_mesh.py`) monkeypatch the constants LOW
against the existing small shoebox fixture — no multi-MB fixture is committed.
Revert-sanity: both bound tests fail when their guard is removed (load-bearing).

## ② Web-facing error-string scrub (OQ-42 echo-leak residual closed)

Every `roomestim_web` site that interpolated an exception, a path, or
`validate_placement()` output into a user-visible string now logs the full
detail server-side (`_LOG.exception`/`warning`) and returns a generic
"서버 로그를 확인하세요" (check the server log) message. The leak this closes:
the dev `_DEFAULT_ENGINE_SCHEMA_PATH` (a `/home/...` absolute path) embedded in
a validation `FileNotFoundError`/`ValueError` could reach the web user.

An independent security re-review found the first pass scrubbed only three
`app.py` sites and **missed** the Speaker Nudge path, where
`validate_placement()`'s error list — which can carry the schema path — was
echoed verbatim. The exhaustive site list now fixed:

- `app.py` — `_on_submit` ValueError branch, `_on_apply_overrides_wrapper`,
  `_on_export` (the original three).
- `speaker_nudge.py` — `_on_nudge_speaker` engine-validation branch (the
  `validate_placement()` echo; the **Gap 1** leak) **and** the nudge
  `ValueError`/`IndexError` branch.
- `object_add.py` — `_on_add_object` (`ValueError` + catch-all) and
  `_on_remove_object` (`IndexError` + catch-all) `{exc}` branches.
- `material_override.py` — `on_apply_overrides` `JSONDecodeError` and per-entry
  `ValueError`/`KeyError` `{exc}` messages.

`validate_placement` itself is **left intact** — CLI use wants the detailed path;
the scrub is at the web boundary only (D29 lane separation preserved). The
`_DEFAULT_ENGINE_SCHEMA_PATH` constant is **kept** as the documented
`CLI > ENV > default` fallback (ADR 0033 §B); the fix is to stop *echoing* it to
the web user, not to remove it. CLI error verbosity (local use) is unchanged. A
new load-bearing web test drives the real `validate_placement` with a missing
schema and asserts the user-facing string contains no `/home/` / `geometry_schema`
(fails if the scrub is reverted).

## ③ Tempdir reaper per-PID namespacing

`_reap_stale_tempdirs` now globs `roomestim_{os.getpid()}_*` (was `roomestim_*`)
and the two creation prefixes (`_on_submit`, `_on_export`) embed the PID. The
reaper can no longer delete another process's tempdirs on a shared host while
still reaping this process's own stale dirs at `atexit`. A crashed process's dirs
are no longer reaped by a fresh process (accepted — HF Spaces containers cycle
≤ 24 h and the OS clears the temp root on recycle; OQ-22).

New web test asserts an alien-PID stale dir survives while this PID's stale dir
is reaped.

## ④ `on_apply_overrides` list-input type guard

`roomestim_web/material_override.on_apply_overrides` guards a non-dict JSON
payload (e.g. `'["glass"]'` → a list) after `json.loads` and before the
`.items()` loop: it surfaces a user-facing error ("변경 사항은 객체(JSON dict)여야
합니다.") and treats the payload as empty (a safe no-op) instead of raising
`AttributeError`. Revert-sanity: the new web test raises `AttributeError` when the
guard is removed (load-bearing).

## ⑤ Dependency reconcile (declaration-only)

- `pyproject.toml` web extra `gradio>=4.0` → `gradio>=4.44` — a floor **≤** the
  installed 6.14.0, so the `pip install` contract widens forward (pulling
  gradio's transitive starlette / aiohttp / pillow / requests / urllib3 floors
  past the audit-flagged CVE lines) WITHOUT forcing a downgrade or an untested
  major. `requests`/`urllib3`/`pillow` are transitive (no direct import in this
  repo; `fetch_web_data` uses stdlib `urllib.request`) → not over-declared.
- README front-matter `sdk_version` `"4.0.0"` → `"6.14.0"` reconciled to the
  installed reality (single source of truth).

This is **declaration-only**: it changes what a fresh `pip install` resolves, NOT
the already-installed canonical env. RT60 negative control stays byte-equal
`1.9190766987173207`, proving the gates run against the unchanged installed tree.
The CI `pip-audit` + lockfile follow-up is a process/infra change deferred to
**OQ-46**.

## What stays the same

| Item | Value |
|---|---|
| `__schema_version__` | `0.2-draft` (no RoomModel field added) |
| RT60 negative control | `1.9190766987173207` (numeric path byte-equal) |
| `_DEFAULT_ENGINE_SCHEMA_PATH` | KEPT (ADR 0033 §B / OQ-42 — only the echo is closed) |
| CLI error verbosity | unchanged (local use; detailed errors are a feature) |
| Installed canonical miniforge env | unchanged (declaration-only dep floors) |
| `roomestim/place/*`, predictor branches, material coefficients | untouched |

## Versioning

- `roomestim`: `0.21.0` → `0.22.0` (MINOR). The `MeshAdapter` byte/vertex bound
  is a new observable `parse()` error path (additive contract) → MINOR not PATCH.
  `pyproject.toml` + `roomestim/__init__.py`.
- `roomestim_web`: `0.17-web.0` → `0.18-web.0`. `app.py` (error scrub + reaper +
  `max_file_size` bound on the Blocks object), `speaker_nudge.py` /
  `object_add.py` / `material_override.py` (web-boundary error scrub), and the
  root `app.py` entrypoint (carries the cap) are touched → web source changes →
  bump required (`roomestim_web/__init__.py`, D30).

## Known deferred items

- **OQ-46** — CI `pip-audit` + dependency lockfile for the web extras
  (process/infra; split from OQ-45 this cycle).
- **PolycamAdapter alias removal** — excluded (BREAKING; D33).
- OQ-30 per-wall α decomposition; OQ-34 / OQ-35 / OQ-37 / OQ-38.

## Fix-program note

This is the final cycle (Cycle B) of the v0.21 post-audit fix program
(`.omc/plans/v0.21-fix-program.md`); the program is complete with OQ-43 / OQ-44
(Cycle A, v0.21.0) and OQ-45 (this cycle) all CLOSED.

## Tag note

Local-only MINOR tag (no PyPI release).
