# roomestim v0.15.2 — Release Notes

**Date**: 2026-05-18
**Type**: PATCH (core) + MINOR (web lane)
**Predecessor**: v0.15.1 (`18e776e`)

---

## What v0.15.1 shipped but deferred

v0.15.1 landed `roomestim/geom/polygon.py` as a core-internal shared util
(`polygon_area_3d`, `room_volume`, `shoelace_2d`). Two follow-up items were
retained as LOW in the v0.15.1 code-review and promised for the next patch:

1. **LOW retention** — `roomestim_web/report.py` still held private duplicate
   `_polygon_area_3d` / `_shoelace_2d` / `_room_volume` functions (~24 LoC).
   Cross-lane import deferral was intentional (needed ADR 0029 amendment first).

2. **LOW-2** — `roomestim/adapters/ace_challenge.py::_room_volume` was removed
   at v0.15.1 without a deprecation shim or explicit decision record.

---

## What v0.15.2 fixes

### ADR 0029 §Cross-lane-geom-amendment (NEW section in existing ADR)

D29 lane separation was designed to prevent core → web dependency leaks, not
web → core imports of stable public utilities. v0.15.2 formalises this reading:
`roomestim_web/**` may import public symbols from `roomestim.geom.polygon`
(and future `roomestim.geom.*` leaf modules). The core → web direction remains
permanently forbidden; `mypy --strict roomestim/` enforces this at type-check
time.

### `roomestim_web/report.py` — ~24 LoC reduction

- `_polygon_area_3d`, `_shoelace_2d`, `_room_volume` removed.
- Import added: `from roomestim.geom.polygon import polygon_area_3d, room_volume`
- Three callsites updated (no behaviour change; numerical identity confirmed by
  Gate 14 / Gate 15 smokes against v0.15.1 baseline).
- Unused `import math` removed.
- Module docstring patched with §Provenance note.

### LOW-2 clean-close (ace_challenge._room_volume)

The decision NOT to add a deprecation shim is now explicitly recorded in ADR
0030 §Status-update-v0.15.2 §Item-H. Rationale: underscore prefix (module-private
convention) + `__all__` not defined + zero external consumer hits (`grep -rn
"ace_challenge.*_room_volume"` = 0). PATCH-range removal of an internal symbol
is within semver PATCH scope.

---

## What stays the same

- Predictor cascade (ADR 0030 §A–§E): ISM shoebox > Eyring fallback, byte-equal.
- `predict_rt60_default` / `predict_rt60_default_per_band` API: unchanged.
- `AcousticReport` dataclass fields: unchanged.
- OQ-30 (per-wall α decomposition): deferred to v0.15.x+.
- `RoomModel` frozen + no evolve helper: deferred to v0.16 (remat override UI).
- ADR 0009 invariant `ism_rt60 ≥ eyring_rt60 − 1e-6`: enforced (Gate 16).

---

## Lane note

`git diff 18e776e -- roomestim_web/` is **no longer empty** — this is
intentional. v0.15.2 is a policy-change cycle (ADR 0029 §Cross-lane-geom-amendment
landed), not a byte-equal cycle. D30 web-track versioning is satisfied by the
`roomestim_web.__version__` bump to `0.12-web.7`.

---

## Test count

| Lane | v0.15.1 | v0.15.2 | Delta |
|---|---|---|---|
| default (`not lab and not web`) | 161 passed + 4 skipped | 161 passed + 4 skipped | 0 |
| web (`tests/web/`) | 48 passed + 1 skipped | 49 passed + 1 skipped | +1 regression lock |

The new test `test_report_geom_helpers_imported_from_core` (regression lock)
verifies: (a) three private duplicates absent, (b) `polygon_area_3d` /
`room_volume` module-attribute identity with `roomestim.geom.polygon`.

---

## Verification gates (all 20 passed)

| # | Check | Result |
|---|---|---|
| 1 | pytest tests/web/test_acoustic_report.py | 4 passed |
| 2 | pytest -m "not lab and not web" | 161 passed + 4 skipped |
| 3 | pytest tests/web/ | 49 passed + 1 skipped |
| 4 | ruff check roomestim/ roomestim_web/ tests/ | All checks passed |
| 5 | mypy --strict roomestim/ | 0 errors |
| 6–8 | Version strings | 0.15.2 / 0.12-web.7 |
| 9 | git diff 18e776e -- roomestim/ | version line only |
| 10 | git diff 18e776e -- roomestim_web/ | non-empty (intended) |
| 11–20 | grep / smoke / ADR presence checks | all pass |
