# ADR 0038 — Input resource bounds (bound untrusted input at the adapter)

**Status**: Accepted (v0.22.0, 2026-05-28).
**Supersedes**: none. **Amends**: none.
**Related**: ADR 0024 (web demo separate package), ADR 0033 (engine-validation
toggle / `_DEFAULT_ENGINE_SCHEMA_PATH`), D71, OQ-45 (CLOSED), OQ-46.

## Context

The tool is a publicly-deployable Gradio app (`app.py` → `roomestim_web.app`,
HF Spaces). The v0.20.0 multi-perspective security audit found NO CRITICAL/RCE
(YAML `safe_load` uniform; no eval/exec/pickle/shell). It did surface that an
untrusted uploaded mesh reaches `trimesh.load(force="mesh")` (`mesh.py`) from the
web upload boundary with NO file-size or vertex-count cap — a trivial DoS on a
shared Space (memory exhaustion via an oversized or pathologically dense mesh).
The same unbounded path is reachable from the CLI / library.

## Decision

Bound untrusted mesh input — both file bytes and vertex count — **inside
`MeshAdapter`** via env-overridable module constants, raising a clear
`ValueError` when a limit is exceeded:

- `_MAX_MESH_FILE_BYTES` (default ~200 MB; `ROOMESTIM_MAX_MESH_BYTES` override) —
  the **pre-load parse-memory bound**. Checked in `parse()` via
  `Path.stat().st_size` BEFORE `trimesh.load` reads the bytes, so a DoS-sized
  file is rejected before it is parsed into memory. This is the load-bearing
  parse-memory guard.
- `_MAX_MESH_VERTICES` (default 5,000,000; `ROOMESTIM_MAX_MESH_VERTICES`
  override) — a **post-parse hull-projection guard**, NOT a parse-memory bound.
  It runs AFTER `trimesh.load` (in `_room_model_from_mesh`, after the `(N, 3)`
  vertex-shape check and before the 0-faces guard; ordering: shape →
  vertex-count → faces) and bounds the O(N) convex-hull projection that follows;
  it does NOT bound the memory consumed by `trimesh.load` itself (the byte-cap
  does that).

Apply a matching Gradio `max_file_size` cap at the web upload boundary. Bind it
on the Blocks object in `build_demo()` (`demo.max_file_size = _MAX_UPLOAD_BYTES`)
so gradio's server honors it regardless of launch path — gradio 6.14.0's
`gr.Blocks` ctor does NOT accept `max_file_size` (only `launch()` does), and HF
Spaces' root `app.py` (`demo = build_demo(); demo.launch()`) never runs
`roomestim_web`'s `__main__` guard, so a launch-only cap would be inert in
production. gradio's upload route reads `app.get_blocks().max_file_size` at
request time. NOTE: gradio still streams the upload to a temp file before
handlers run, so this is **gradio's own server-side size rejection at the
request boundary** — NOT a "before bytes hit disk" guard. The MeshAdapter
byte-cap above remains the defense-in-depth chokepoint that also protects the
CLI/library path.

## Drivers

- Publicly-deployable Gradio app reaches `trimesh.load(force="mesh")` unbounded;
  trivial DoS on a shared Space.
- Defense-in-depth: the adapter byte-cap protects every entry path (CLI,
  library, web) before parse; the web `max_file_size` is gradio's server-side
  size rejection at the request boundary (an additional outer layer).
- Unit-testability: a module constant can be monkeypatched LOW to exercise the
  error path against an existing small fixture — no multi-MB fixture committed.

## Alternatives considered

- **(a) Web-only cap** — rejected: leaves the CLI / library path unguarded, and
  the bound is untestable without a browser.
- **(b) Hard-coded limits** — rejected: legitimate large-scan operators need an
  override; env-overridable constants preserve flexibility while keeping the
  policy discoverable in the module.

## Why chosen

The adapter-level bound is the single chokepoint reachable from every entry
path and is unit-testable by monkeypatching the constant LOW; the env override
preserves flexibility; module constants keep the policy discoverable.

## Consequences

- `MeshAdapter.parse` gains a new public error path (oversized input now raises),
  an observable additive contract change → SemVer-MINOR (`roomestim` 0.22.0).
- Future adapters that ingest untrusted input should adopt the same
  env-overridable module-constant bound pattern.
- The web track gains a `max_file_size` boundary cap (`roomestim_web`
  0.18-web.0).

## Reverse-criterion

- If a legitimate operator's large-scan workflow routinely trips the default
  caps → raise the defaults (or document the env knobs more prominently); the
  override path already exists, so no code change is forced.

## Follow-ups

- OQ-46 — CI `pip-audit` + lockfile (process/infra, deferred this cycle).

## References

- D71 — `.omc/plans/decisions.md` (web public-deployment hardening bundle).
- ADR 0024 §Status-update-v0.22.0 — web package error scrub + reaper +
  `max_file_size` + version bump.
- ADR 0033 §Status-update-v0.22.0 — OQ-42 schema-path echo-leak closed without
  removing the documented default.
- OQ-45 (CLOSED) / OQ-46 (NEW) — `.omc/plans/open-questions.md`.
- `.omc/plans/v0.22-web-hardening.md` — implementing plan.
