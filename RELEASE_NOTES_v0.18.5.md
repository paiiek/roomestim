# roomestim v0.18.5 — test-hygiene PATCH (PolycamAdapter → MeshAdapter migration in 4 web test files)

PATCH bump `0.18.4` → `0.18.5`. See D62 (`.omc/plans/decisions.md`) and ADR
0027 §Status-update-v0.18.5 (`docs/adr/0027-mesh-format-generalisation.md`).

## What v0.18.5 cleans up (D62)

The four `tests/web/*.py` files that used the **deprecated** `PolycamAdapter`
alias purely as a generic mesh parser were migrated to the canonical
`roomestim.adapters.MeshAdapter` (D33's intended end-state):

| File | Changed lines |
|---|---|
| `tests/web/test_setup_pdf.py` | import :12, parse :19 |
| `tests/web/test_acoustic_report.py` | import :9, parse :15 |
| `tests/web/test_binaural_renderer.py` | import :24, parse :79 |
| `tests/web/test_3d_viewer.py` | import :11, construct :19 |

Each parse target is `tests/fixtures/lab_room.obj` (a `.obj` mesh). The swap
is **behavior-preserving**: `PolycamAdapter(MeshAdapter)` is a subclass that
only adds a `DeprecationWarning` and a `.json`-delegation branch, neither of
which applies to a `.obj` input.

**Effect**: the four migrated files emit zero `PolycamAdapter`
`DeprecationWarning`s under `-W error::DeprecationWarning`. The alias's
intentional warning now fires only from the contract test
`tests/test_adapter_polycam.py` — the desired single canonical trigger
(3 passed, 3 warnings — unchanged).

## What stays the same

| Item | Value |
|---|---|
| `roomestim_web.__version__` | `0.15-web.0` (web byte-equal — `tests/web/*.py` are test files, not part of the `roomestim_web` package; `git diff 35e691d -- roomestim_web/` = 0 bytes) |
| `__schema_version__` | `0.2-draft` (no schema/model/serialization change) |
| `PolycamAdapter` alias | Kept alive — `roomestim/adapters/__init__.py` export + `roomestim/adapters/polycam.py` shim byte-equal (D33 reverse-criterion still gates full removal) |
| Contract test | `tests/test_adapter_polycam.py` byte-equal — 3 passed, 3 warnings (intentional, contractual deprecated-path coverage) |
| `cli.py` `--backend polycam` `.json` path | `roomestim/cli.py` byte-equal — `_get_adapter("polycam")` stays on `PolycamAdapter` (`MeshAdapter` rejects `.json`; swap would regress) |
| ADR 0009 ISM ≥ Eyring invariant | Unaffected |
| RT60 negative control | `1.9190766987173207` (acoustic path untouched) |
| All prior §Status-update blocks (D22) | Byte-equal above new §Status-update-v0.18.5 sections |
| Default-lane test count | 271 passed / 6 skipped (byte-equal to v0.18.4 — rename only, no tests added/removed) |
| Web-lane test count | 70 passed / 1 skipped (unchanged) |

## Known deferred items

- **OQ-40** (NEW, allocated this cycle) — gradio `col_count` Dataframe-kwarg
  deprecation noise (`roomestim_web/material_override.py:196`,
  `roomestim_web/object_add.py:218`). SEPARATE from D62; deferred pending a
  gradio-6 upgrade decision. Web-lane warning noise from this source is
  third-party and out of scope for this test-only PATCH.
- **PolycamAdapter full removal** — still deferred under D33 reverse-criterion
  (BREAKING → needs successor D-decision + "Breaking changes" RELEASE_NOTES
  callout). D62 does NOT authorize removal; the shim's stale "v0.14 or later"
  docstring is noted as a known deferred follow-up.
- OQ-30 per-wall α decomposition (v0.20+ or trigger-gated)
- OQ-37 `notes` round-trip (v0.20 re-exam)
- OQ-38 DBAP/AMBISONICS label collapse (v0.20 re-exam)
- OQ-34 cylinder column (v0.21 re-exam)
- OQ-35 acoustic metadata standard (v0.21 re-exam)

## Versioning note (PATCH rationale)

PATCH `0.18.5` per D30: test-suite changes that remove warning noise alter CI
log output and suite API usage, but introduce no feature/schema/acoustic/runtime
behavior change → PATCH is correct. `roomestim_web.__version__` is unchanged
(`0.15-web.0`) because `tests/web/*.py` are test files outside the importable
`roomestim_web` package.

## Tag note

Local-only PATCH tag (no PyPI release). `git diff 35e691d -- roomestim_web/` =
0 bytes (web byte-equal confirmed). `git diff 35e691d -- roomestim/cli.py` =
0 bytes (cli.py untouched — TRAP guard confirmed).
