# RELEASE NOTES — roomestim v0.7.0

v0.7.0 ships two zero-risk additive items vs the v0.6 numerical baseline:

- **Scope A** — WFS CLI ergonomics. The default invocation
  `roomestim run --algorithm wfs --n-speakers 8 --layout-radius 2.0`
  no longer surfaces a raw `ValueError(kErrWfsSpacingTooLarge: ...)`.
  Two new optional flags expose the previously-hardcoded `f_max_hz`
  constant and add an explicit-spacing escape hatch; the CLI wraps
  the bound-violation `ValueError` and re-raises with a constructive
  remediation message naming both `--wfs-f-max-hz` and `--n-speakers`
  paths concretely.
- **Scope C** — Building_Lobby coupled-space ADR. ADR 0014 ratifies
  the v0.6 implicit Building_Lobby exclusion (D17 / OQ-9 / ADR 0013
  §Alternatives considered (d)) as the v0.7 explicit, citable
  decision. Zero code change.

A12 byte-equality of every v0.6.0 default-lane test is preserved
(100 → 104; +4 new WFS-ergonomics tests; nothing existing is modified).
`__schema_version__` stays `"0.1-draft"`. No new enum entry. No
predictor change. No coefficient revision. No perf doc regeneration.

---

## Highlights

- **WFS CLI no longer requires reading the source to recover from the
  default error**:
  - `roomestim/cli.py` `place` and `run` parsers gain
    `--wfs-f-max-hz FLOAT` (default 8000.0) and `--wfs-spacing-m FLOAT`
    (default None — derived).
  - `_run_placement(...)` wraps `place_wfs(...)` in try/except. On
    spatial-aliasing-bound failure, the CLI re-raises with:
    `"... Either pass --wfs-f-max-hz <X> (max safe --wfs-f-max-hz
    for current spacing is X = c/(2*spacing_m) = ... Hz) OR pass
    --n-speakers <Y> (minimum safe --n-speakers for current f_max_hz
    is Y = ceil(baseline_len/(c/(2*f_max))) + 1 = ...)."`
  - Library-level `roomestim/place/wfs.py::place_wfs(...)` `ValueError`
    API contract is **UNCHANGED** — `kErrWfsSpacingTooLarge: ...`
    still raises with the same message.
- **Building_Lobby exclusion now explicitly cited**:
  - ADR 0014 documents the decision once. Future aggregate-stat
    reporting (perf doc, octave-band aggregates, external tooling)
    references ADR 0014 directly rather than re-litigating the
    exclusion or pointing at parenthetical caveats.
  - ADR 0012 and ADR 0013 References gain one cross-link line each
    pointing forward to ADR 0014.

---

## What changed

### CLI — Scope A

- `roomestim/cli.py`:
  - +`--wfs-f-max-hz FLOAT` and +`--wfs-spacing-m FLOAT` on both the
    `place` and `run` parsers (4 `add_argument` calls; symmetric
    placement).
  - `_run_placement(...)` signature: gained
    `wfs_f_max_hz: float = 8000.0` and
    `wfs_spacing_m: float | None = None` keyword args.
  - WFS branch derives `spacing_m` from `wfs_spacing_m` if supplied,
    else from `n_speakers` / `layout_radius` (existing formula).
  - Wrapped `place_wfs(...)` call in try/except `ValueError`. On
    `spacing_m > c/(2*f_max_hz)`, computes `max_safe_f_max =
    c/(2*spacing_m)` and `min_safe_n =
    ceil(baseline_len/(c/(2*f_max))) + 1`; re-raises with both
    remediation clauses.
  - `_cmd_place` and `_cmd_run` thread the new args via `getattr(...)`
    defaults (defensive for `_cmd_ingest` / `_cmd_export` namespaces
    that don't carry the WFS flags).
- `roomestim/place/wfs.py`: **NOT TOUCHED**. Library API is the same
  as v0.6.

### Tests — Scope A

- `tests/test_cli_wfs_ergonomics.py` (NEW; +4 default-lane tests):
  - `test_run_wfs_default_n8_emits_constructive_error` — asserts
    stderr/stdout contain both `"max safe --wfs-f-max-hz"` and
    `"minimum safe --n-speakers"` clauses.
  - `test_run_wfs_with_low_fmax_succeeds` — `--wfs-f-max-hz 300`
    unblocks the default n=8 / radius=2.0 invocation.
  - `test_run_wfs_with_explicit_spacing_succeeds` — `--n-speakers 200
    --layout-radius 2.0 --wfs-spacing-m 0.02 --wfs-f-max-hz 8000`
    succeeds.
  - `test_run_wfs_explicit_spacing_overrides_derived` — explicit
    `--wfs-spacing-m 0.10` produces `x_wfs_f_alias_hz == 1715.0` Hz,
    not the derived spacing's f_alias.

### Documentation — Scope C

- `docs/adr/0014-building-lobby-coupled-space-exclusion.md` (NEW):
  Status / Date / Predecessor / Decision / Drivers / Alternatives
  considered / Why chosen / Consequences / Reverse if / References.
  Cites Eaton 2016 TASLP §II-C, Vorländer 2020 §4.4 + §4.2, and
  the `+1.425 s` Building_Lobby empirical evidence in v0.6 perf doc.
- `docs/adr/0012-eaton-taslp-materials-not-in-paper.md`: References
  cross-ref appended (one line) pointing forward to ADR 0014. Body
  byte-equal to v0.6.
- `docs/adr/0013-taslp-misc-soft-surface-budget.md`: References
  cross-ref appended (one line) pointing forward to ADR 0014. Body
  byte-equal to v0.6.

### Bookkeeping

- `.omc/plans/decisions.md`: D18 appended (D14, D15, D16, D17 bodies
  untouched).
- `.omc/plans/open-questions.md`: unchanged. Both Scope A and Scope C
  have planner-locked decisions baked into D18; no new OQs raised.
- `.omc/plans/v0.7-design.md` (NEW): scope-A + scope-C design doc.
- `.omc/plans/v0.7-audit-findings.md` (NEW): post-implementation
  audit findings.
- `pyproject.toml`, `roomestim/__init__.py`: 0.6.0 → 0.7.0.
  `__schema_version__` stays `"0.1-draft"` (D8 not satisfied; A10 lab
  capture has not shipped).

---

## Constructive error — example

Default invocation (v0.6.0 behaviour):
```
$ roomestim run --backend polycam --input tests/fixtures/lab_room.json \
                --algorithm wfs --n-speakers 8 --layout-radius 2.0 \
                --out-dir /tmp/out
error: kErrWfsSpacingTooLarge: spacing_m=0.5714285714285714 >
c/(2*f_max)=0.0214375
```

Same invocation (v0.7.0 behaviour):
```
$ roomestim run --backend polycam --input tests/fixtures/lab_room.json \
                --algorithm wfs --n-speakers 8 --layout-radius 2.0 \
                --out-dir /tmp/out
error: WFS spatial-aliasing bound violated: spacing_m=0.5714 >
c/(2*f_max_hz)=0.0214 (c=343.0 m/s, f_max_hz=8000.0). Either pass
--wfs-f-max-hz <X> (max safe --wfs-f-max-hz for current spacing is
X = c/(2*spacing_m) = 300.12 Hz) OR pass --n-speakers <Y> (minimum
safe --n-speakers for current f_max_hz is Y =
ceil(baseline_len/(c/(2*f_max))) + 1 = 188).
```

Recovery paths (both validated by v0.7 tests):
```
# Option A — relax f_max
$ roomestim run ... --wfs-f-max-hz 300 --out-dir /tmp/out
wrote /tmp/out/room.yaml
wrote /tmp/out/layout.yaml

# Option B — densify the array
$ roomestim run ... --n-speakers 188 --out-dir /tmp/out
wrote /tmp/out/room.yaml
wrote /tmp/out/layout.yaml

# Option C — explicit spacing escape hatch
$ roomestim run ... --n-speakers 200 --wfs-spacing-m 0.02 --out-dir /tmp/out
wrote /tmp/out/room.yaml
wrote /tmp/out/layout.yaml
```

---

## What stays deferred

- **F1 walls / ceiling materials**: INDETERMINATE (not TASLP-blocked;
  no canonical source). Unchanged from v0.6.
- **F3 — Lecture_2 ceiling material hypothesis**: canonical evidence
  path closed; non-canonical evidence still required.
- **F4a — `MaterialAbsorptionBands` coefficient revision**: D14 5b
  pre-condition unchanged.
- **`lecture_seat` α₅₀₀ revision** (RELEASE_NOTES_v0.6.0.md flagged
  this as a v0.7+ candidate): re-anchors on F3 ceiling-material
  entanglement; separate data-table ADR; would change v0.6 numerical
  baseline. v0.7 is locked to zero-risk items.
- **Coupled-space predictor (Cremer/Müller two-room formula;
  Vorländer 2020 §4.4)**: ADR 0014 §Alternatives considered (b) —
  out of scope; needs per-sub-volume geometry the ACE adapter does
  not have.
- **Hard-floor subtype**: needs lab visit / author email.
- **Stage-2 schema flip / A10 lab capture** (D8).
- **Millington-Sette predictor** (ADR 0009 alt-considered).
- **8 kHz octave band** (ADR 0008 reverse criterion).
- **PyPI / submodule** (D11).

---

## Tests

| File | Count | Markers |
| --- | ---: | --- |
| `tests/test_cli_wfs_ergonomics.py` | +4 | (none — default lane 100 → 104) |
| All other test files | unchanged | — |

Default-lane collected: **104** tests (100 v0.6.0 + 4 v0.7
WFS-ergonomics). `ruff check` clean. Gated e2e deselected: 3 (unchanged).

| Step | Command | Expected |
| --- | --- | --- |
| Default lane | `python -m pytest -m "not lab and not e2e" -q` | 104 passed, 3 skipped, 3 deselected |
| Lint | `python -m ruff check` | All checks passed! |
| Version | `grep '^version\|__version__' pyproject.toml roomestim/__init__.py` | both 0.7.0 |
| Smoke OK | `roomestim run ... --wfs-f-max-hz 300 --out-dir /tmp/v0.7_smoke` | room.yaml + layout.yaml |
| Smoke FAIL | `roomestim run ... --out-dir /tmp/v0.7_smoke_fail` | exits 1; stderr names both remediation paths |
| E2E (gated) | `ROOMESTIM_E2E_DATASET_DIR=/tmp/ace_corpus python -m pytest -m e2e -s tests/test_e2e_ace_challenge_rt60.py` | passes; v0.6 numbers byte-equal (B-L exclusion + per-band invariants unchanged) |

---

## Backwards compatibility

- `place_wfs(...)` signature: **UNCHANGED**.
- `place_wfs(...)` `ValueError("kErrWfsSpacingTooLarge: ...")`:
  **UNCHANGED**. Library callers that depend on the marker string
  continue to work.
- `roomestim run --algorithm wfs ...` without the new flags: behaves
  the same as v0.6 EXCEPT the error path produces a more helpful
  message; exit code (1) and `argparse` semantics are unchanged.
- `MaterialAbsorption`, `MaterialAbsorptionBands`, `MaterialLabel`
  (9 entries), `_FURNITURE_BY_ROOM`, `_PIECE_EQUIVALENT_ABSORPTION_*`
  byte-equal to v0.6.
- `__schema_version__`: `"0.1-draft"` unchanged.
- `sabine_rt60`, `sabine_rt60_per_band`, `eyring_rt60`,
  `eyring_rt60_per_band`: byte-equal to v0.6.
- All 100 v0.6.0 default-lane tests pass byte-for-byte. v0.6 perf doc
  at `docs/perf_verification_e2e_2026-05-08.md` remains the current
  characterisation reference (no v0.7 regeneration).
- Eyring monotonicity (`eyring_500hz <= sabine_500hz + 1e-9`) preserved
  per room and per band — v0.7 introduces no predictor change. v0.6
  perf doc Building_Lobby +1.425 s row stays in the per-room table for
  transparency, excluded from cross-room aggregates per ADR 0014.

---

## Schema status

`__schema_version__ = "0.1-draft"` (Stage-1; `additionalProperties: true`).
Stage-2 flip remains deferred per D8. v0.7 is CLI-UX + bookkeeping only;
no schema change.
