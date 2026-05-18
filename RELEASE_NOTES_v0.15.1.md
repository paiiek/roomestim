# roomestim v0.15.1 — predictor.py follow-up patch

**Date**: 2026-05-17
**Predecessor**: v0.15.0 (`63ae18a` — predictor-default switch ADR 0030 NEW)
**Bump**: PATCH (`0.15.0` → `0.15.1`; `roomestim_web` unchanged at `0.12-web.6`)

---

## What v0.15.0 missed

v0.15.0 code-reviewer flagged two follow-ups as known-gaps (not absorbed into
the v0.15.0 patch):

| # | Label | Description |
|---|---|---|
| MEDIUM-1 | Per-band fallback rationale | `_band_alpha` silent 500 Hz fallback not reported in `RT60Prediction.rationale` |
| LOW-1 | Geom duplicate | `_polygon_area_3d` / `_room_volume` / `_shoelace_2d` duplicated in `predictor.py` and `ace_challenge.py` |

---

## What v0.15.1 fixes

### MEDIUM-1 — Per-band fallback rationale (predictor.py)

`_shoebox_per_band_alphas` now returns a third element: a sorted tuple of
surface names (`"floor"`, `"ceiling"`, `"wall_0"`, …) where `absorption_bands`
was `None` and the 500 Hz scalar was broadcast across all 6 bands.

`predict_rt60_default_per_band` appends to the rationale string when the set
is non-empty:

```
; per-band α fallback used for surfaces: [wall_0, wall_2]
```

The frozen `RT60Prediction` dataclass gains **no new field** — backward-compat
with external serialisers is preserved. Single-band `predict_rt60_default` is
**unaffected** (uses 500 Hz scalars throughout; no per-band fallback path).

### LOW-1 — `roomestim/geom/polygon.py` shared util (NEW)

New files:
- `roomestim/geom/__init__.py` — re-exports 3 public symbols.
- `roomestim/geom/polygon.py` (~80 LoC) — `polygon_area_3d`, `room_volume`,
  `shoelace_2d` (public, underscore prefix removed).

`roomestim/reconstruct/predictor.py` now imports from `roomestim.geom.polygon`
in place of its private `_polygon_area_3d` / `_room_volume` duplicates.

`roomestim/adapters/ace_challenge.py` had a `_room_volume` duplicate that was
consumed only by tests (the adapter has no internal `_room_volume` callsite).
The duplicate is deleted; the 3 test modules that used it
(`test_e2e_ace_challenge_rt60.py`, `test_per_band_mae_ex_bl_snapshot.py`,
`test_lecture_2_ceiling_seat_bracket.py`) now import directly from
`roomestim.geom.polygon`. No `room_volume` import is added to `ace_challenge.py`
itself (it would be dead code).

D29 lane separation (web↔core) is preserved: extraction is core-internal,
`roomestim_web/` is byte-equal vs v0.15.0 (`git diff 63ae18a -- roomestim_web/`
empty). `roomestim_web/report.py` retains its own private duplicates per D29;
consolidating across the web↔core boundary is out of scope for v0.15.1.

---

## What stays the same

- **Predictor cascade**: ISM (rectilinear shoebox) > Eyring (non-shoebox) —
  identical to v0.15.0. ADR 0030 §Decision unchanged.
- **OQ-30 deferred**: per-wall α decomposition for mixed-material walls remains
  v0.15.x+ scope.
- **Web lane byte-equal**: `roomestim_web/__version__ == "0.12-web.6"`;
  `git diff roomestim_web/` vs `63ae18a` is empty.
- **ADR 0009 invariant**: `ism_rt60 >= eyring_rt60 - 1e-6` confirmed on
  lab_room.
- **500 Hz smoke**: `predict_rt60_default(lab_room).rt60_s ==
  1.9190766987173207 s` (byte-equal vs v0.15.0).

---

## Default-lane test count

| Version | passed | skipped | notes |
|---|---|---|---|
| v0.15.0 | 159 | 4 | writer env (mypy installed) |
| v0.15.1 | 162 | 4 | `test_geom_polygon.py` 3 NEW + `test_predict_rt60_default.py::test_per_band_fallback_surfaces_in_rationale` 1 NEW = +4 new tests; `test_mypy_strict_baseline.py` skip drift in the local exec env (`python3 -m mypy` not on import path even when the `mypy` CLI binary is installed) accounts for the −1 vs. nominal 163. Gate 6 (mypy CLI direct) reports `Success: no issues found in 35 source files`. |

---

## Known gaps (v0.15.2+ follow-up)

v0.15.1 code-review absorbed 1 of 3 findings into this patch (the MEDIUM
positional-wall-index comment in `predictor.py:174` + the LOW-1 docstring
clarification in `polygon.py::room_volume`). One LOW remains as a known gap:

- **LOW-2** — No backward-compat deprecation shim for the removed
  `roomestim.adapters.ace_challenge._room_volume`. Out-of-tree consumers that
  import the (underscore-prefixed, private-by-convention) name will get
  `ImportError`. In-repo migration is complete; PEP 8's `_` private prefix
  removes the semver guarantee. Add `_room_volume = room_volume` shim only if
  an actual external consumer is reported.

## Tag

Local-only tag `v0.15.1` — HF Spaces deploy and PyPI publish out of scope for
this patch. Web lane unchanged; no HF Spaces re-deploy required.
