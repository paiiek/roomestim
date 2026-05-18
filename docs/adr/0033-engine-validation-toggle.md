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

## §References

- ADR 0024 — web-demo separate package (D29 lane separation)
- ADR 0027 — mesh format generalisation
- D42 — CLI > ENV > default precedence decision
- OQ-31 — multi-engine schema target deferral (v0.18+)
- `roomestim/export/layout_yaml.py::write_layout_yaml` — implementation
- `roomestim/cli.py::_add_export_parser` — CLI flag definition
