# ADR 0033 — Engine Validation Toggle Policy

**Status**: Accepted (v0.16.0, 2026-05-18)
**Deciders**: paiiek
**References**: ADR 0024, ADR 0027, D42, OQ-31

---

## Context

Through v0.15.2, `roomestim export` unconditionally validated the output
`layout.yaml` against `spatial_engine/proto/geometry_schema.json` (Draft
2020-12). This blocked standalone YAML use-cases where:
- The spatial_engine repository is not locally available.
- The user is evaluating roomestim output for a different audio engine.
- CI/CD environments without the engine repo cloned.

v0.16.0 introduces an explicit opt-out with a required audit trail.

---

## §A Scope

**CLI flags** (mutually exclusive group on the `export` subcommand):
- `--validate-engine PATH` — explicit engine repo dir (overrides ENV var).
- `--no-engine-validation` — skip schema validation entirely.

**Web sidebar**: `gr.Checkbox(label="Standalone YAML (skip engine schema check)", value=False)`.
Default unchecked = validation ON.

**ENV var**: `SPATIAL_ENGINE_REPO_DIR` — backward-compatible; used when no
CLI flag is given and the path points to a valid schema file.

---

## §B Precedence (D42)

```
CLI flag > ENV var > hardcoded default (/home/seung/mmhoa/spatial_engine)
```

- CLI `--validate-engine PATH` overrides `SPATIAL_ENGINE_REPO_DIR` when both
  are set (D42 regression lock: `test_cli_export_cli_overrides_env`).
- `--no-engine-validation` is mutually exclusive with `--validate-engine`
  (argparse `add_mutually_exclusive_group()`; exit code 2 on conflict).
- ENV var `SPATIAL_ENGINE_REPO_DIR` is only consulted when no CLI flag is
  given. If the ENV path does not exist, `_engine_schema_path()` falls back
  to the hardcoded default (pre-v0.16 behavior preserved).

---

## §C Default: ON (backward-compat)

Default behavior is unchanged from v0.15.2: validation runs using the engine
schema resolved by the existing `_engine_schema_path()` function. No user
action required to preserve the old behavior.

**Audit trail**: when `--no-engine-validation` is used, the output YAML is
prepended with:

```yaml
# WARNING: schema validation skipped (--no-engine-validation)
# This file has NOT been validated against the spatial_engine schema.
# Use with caution; engine compatibility is the caller's responsibility.
```

This makes it impossible for a downstream consumer to silently receive an
unvalidated file (ADR 0033 §C honesty principle).

---

## §D Failure mode

- Validation failure: export aborted before any write, error to stderr, exit
  code 1 (current behavior, unchanged).
- `--no-engine-validation`: validation skipped, WARNING header prepended to
  YAML, exit 0. Schema mismatch with the engine is the caller's
  responsibility.

---

## §E Reverse-criterion

Revert or extend this ADR when:
- A user requires validation against multiple engine schema targets
  (e.g. SPARTA, IEM Plugin Suite). Action: introduce
  `--validate-engine PATH:target_name` syntax per OQ-31 (v0.18+ cadence,
  D26 forbidden-indefinite-deferral applied — must decide by v0.18).
- The hardcoded default path `/home/seung/mmhoa/spatial_engine` becomes
  permanently unavailable. Action: remove default + make ENV var required.

---

## §Status-update-v0.20.0 (2026-05-28)

**D65 — silent fallback → descriptive error (OQ-42 CLOSED).** Previously, when
neither `SPATIAL_ENGINE_REPO_DIR` nor `--validate-engine` resolved a file, the
resolver returned `_DEFAULT_ENGINE_SCHEMA_PATH` unconditionally and the missing
file surfaced only as a bare deep `FileNotFoundError` from
`schema_file.open()` — non-portable and unactionable on any host without the
engine repo at the canonical absolute path. v0.20.0 routes all three open sites
(`_load_engine_schema`, `write_layout_yaml`, `validate_placement`) through a
single guard `_assert_schema_file_exists`, which raises one descriptive
`FileNotFoundError` tagged `kErrEngineSchemaNotFound` naming all three escape
hatches (`SPATIAL_ENGINE_REPO_DIR`, `--validate-engine`, `--no-engine-validation`).

**§B chain RETAINED.** The documented `CLI > ENV > default` precedence is
unchanged and `_DEFAULT_ENGINE_SCHEMA_PATH` is kept as the documented fallback
constant. This honors §E intent (do not let a missing schema fail silently)
WITHOUT firing §E's breaking-removal trigger: the default path is not yet
*permanently* unavailable, so removing the default + making the ENV var required
remains a future action gated on §E. Option (b) warn-and-skip was rejected
(collides with §C/§D's explicit `--no-engine-validation` audit-trail opt-out);
option (c) vendoring a schema copy was rejected (ADR 0027/0033 keep the engine
schema un-vendored to avoid drift).

**Behavior delta.** Byte-identical output and exit codes on any host where the
schema resolves (env set, repo present, or `--validate-engine` valid). Only a
host where the schema is *genuinely* absent sees the new (actionable) error
instead of the bare one — strictly an improvement. CLI help text updated to drop
the "hardcoded default" phrasing in favor of "the documented default engine repo
dir … errors with guidance if none resolve." Tests: new
`test_engine_schema_missing_raises_descriptive`; `tests/test_engine_toggle.py`
docstrings re-worded to the error-on-missing semantics (the ENV/CLI-precedence
tests themselves are unchanged — they supply a valid schema dir). MINOR bump
`0.19.0 → 0.20.0`.

---

## §Status-update-v0.22.0 (2026-05-28)

**OQ-42 echo-leak residual CLOSED (D71, OQ-45) — without removing the documented
default.** v0.20.0 fixed the silent-fallback path but the dev
`_DEFAULT_ENGINE_SCHEMA_PATH` (a `/home/...` absolute path) could still surface
to a *web* user: a validation `ValueError` carrying the path was echoed verbatim
into the Gradio `_on_submit` error report (and `_on_export` /
`_on_apply_overrides_wrapper` echoed raw exception text generally). v0.22.0
scrubs all three web-facing echo sites in `roomestim_web/app.py` — full detail
stays in `_LOG` server-side, the web user gets a generic
"서버 로그를 확인하세요" message. The leak vector was the **echo**, now closed.

**§B chain RETAINED (again).** `_DEFAULT_ENGINE_SCHEMA_PATH` is **kept** as the
documented `CLI > ENV > default` fallback per §B / D42; this update changes only
the web-facing presentation, not the constant or the CLI's detailed (local-use)
errors. See ADR 0024 §Status-update-v0.22.0 and ADR 0038. No core-schema behavior
change → RT60 byte-equal `1.9190766987173207`.

---

## §References

- ADR 0024 — web-demo separate package (D29 lane separation)
- ADR 0027 — mesh format generalisation
- D42 — CLI > ENV > default precedence decision
- OQ-31 — multi-engine schema target deferral (v0.18+)
- `roomestim/export/layout_yaml.py::write_layout_yaml` — implementation
- `roomestim/cli.py::_add_export_parser` — CLI flag definition
