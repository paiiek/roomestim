# Plan: Ceiling-confidence flag (measured-path under-report guard)

Status: READY (direct-mode plan, not yet executed)
Owner: executor → code-reviewer → verifier (full-gate per repo MEMORY rules)
Version bump: MINOR `0.27.0 → 0.28.0`
RESUME POINTER: this file. Update the Phase checkboxes below as you go.

---

## Context

The measured path (`MeshAdapter`) extracts the ceiling as the **topmost still-dense
Y-bin** in the upper half of a gravity-aligned scan (`roomestim/adapters/mesh.py`
`_robust_floor_ceiling_y`, lines ~358-438). The function's own docstring
(mesh.py:390-404) documents a residual, UNFIXED failure mode: a dense horizontal
plane that is BOTH dense AND nearer than the true ceiling (a large tabletop/desk,
mid-height shelving, a mezzanine/loft slab, or a true ceiling so under-sampled no
bin clears the density-FRAC) can be mis-picked, **UNDER-reporting** the height. The
docstring explicitly names the deferred fix: "an explicit plane-area / coverage
check (the ceiling should span most of the footprint, a tabletop should not) or a
confidence/uncertainty flag on the returned height."

This plan implements **exactly that deferred annotation** — a genuine geometric
coverage measurement plus a heuristic categorical flag. It does NOT change
`ceiling_height_m` (no behavior change to the extracted value); it only ANNOTATES it.

### Honesty posture (HARD — repo culture)
- `ceiling_coverage` is a **genuine geometric MEASUREMENT** (a fraction). Honest.
- `ceiling_confidence` ("high"/"low"/"unknown") is a **documented HEURISTIC** derived
  from a conservative threshold. It is NOT a calibrated probability. Labeled as such
  everywhere it surfaces.
- The threshold is validated **only on synthetic fixtures** (clean shoebox → high;
  tabletop mis-pick → low). NO calibration claim against real data. This mirrors why
  OQ-57 per-corner uncertainty is DEFERRED (calibration unavailable).
- **Additive only.** `ceiling_height_m`, RT60, and every existing committed fixture /
  room.yaml golden stay byte-equal (new yaml keys are emitted ONLY when measured →
  non-mesh rooms keep byte-equal output).

---

## (a) Field names + types + defaults

Add to `roomestim/model.py`:

```python
# next to Provenance (model.py:156)
CeilingConfidence = Literal["high", "low", "unknown"]
```

Add two keyword-defaulted fields to the `RoomModel` dataclass (model.py:315-326),
**after** `provenance` so existing positional constructors stay byte-equal:

```python
    #: Genuine geometric measurement: fraction of the floor-footprint grid cells
    #: that contain a scan vertex within the detected ceiling band. None when the
    #: capture path did not measure it (image/assumed/hand-authored rooms). Honest.
    ceiling_coverage: float | None = None
    #: HEURISTIC under-report guard derived from ceiling_coverage via a documented
    #: conservative threshold (NOT a calibrated probability). "unknown" when
    #: coverage was not measured. Annotates ceiling_height_m; never changes it.
    ceiling_confidence: CeilingConfidence = "unknown"
```

Least-claim defaults (`None` / `"unknown"`): a RoomModel with no coverage
measurement makes **no claim**. Only the measured mesh path sets "high"/"low".
This is the exact precedent of `provenance` defaulting to `"assumed"`.

---

## (b) Coverage metric definition (precise)

Computed in `_extract_room_model` **after** `floor_y, ceiling_y` are known, on the
already-Y-up-normalized `vertices` (N×3; XZ = columns 0 and 2, Y = column 1).

New constants in `roomestim/adapters/mesh.py` (next to `_FLOOR_CEILING_BIN_M`, ~line 170):

```python
# Ceiling-confidence coverage metric (under-report guard; see _disclosure note).
_CEILING_COVERAGE_CELL_M = 0.25     # XZ grid resolution (25 cm cells)
_CEILING_COVERAGE_BAND_M = 0.10     # half-width of the ceiling band: ceiling_y ± 10 cm
_CEILING_COVERAGE_MIN    = 0.50     # coverage >= 0.50 → "high", else "low" (HEURISTIC)
```

Definition:
- **Grid**: bin the XZ extent of ALL vertices into square cells of edge
  `_CEILING_COVERAGE_CELL_M` (25 cm). Cell index = `(floor(x/cell), floor(z/cell))`.
- **Footprint cells (denominator)** = set of cells containing **≥1 vertex at ANY
  height**. This is the room's occupied footprint (robust for L-shaped/non-shoebox
  rooms — uses occupancy, not the bbox rectangle).
- **Ceiling-band cells (numerator)** = set of cells containing ≥1 vertex whose Y is
  within `±_CEILING_COVERAGE_BAND_M` of `ceiling_y`.
- **`ceiling_coverage` = |ceiling-band cells| / |footprint cells|**, clamped to [0, 1].
- **Fail-safe**: if the footprint-cell set is empty (degenerate input), return
  `coverage = None`, `confidence = "unknown"` — never raise (mirrors the existing
  min/max fall-back style in `_robust_floor_ceiling_y`).

Rationale: a true ceiling plane spans essentially the whole footprint (coverage ≈ 1.0
on a clean shoebox — floor+walls+ceiling all populate every cell). A tabletop /
mezzanine slab occupies only its own small XZ region → small ratio. A severely
under-sampled true ceiling also yields low coverage → correctly flagged uncertain.

Implement as a static method:
```python
@staticmethod
def _ceiling_coverage(vertices: np.ndarray, ceiling_y: float) -> float | None: ...
```
and classify via the single-source helper (see section g).

---

## (c) Threshold + rationale

`_CEILING_COVERAGE_MIN = 0.50`. `coverage >= 0.50 → "high"`, else `"low"`.

Rationale (documented, NOT calibrated): a trustworthy ceiling plane should cover the
**majority** of the footprint; furniture/tabletop/mezzanine planes and badly
under-sampled ceilings do not. 0.50 is a deliberately conservative midpoint between
the ~1.0 of a well-scanned ceiling and the <0.3 of a localized slab. It is a
geometric rule of thumb **validated only on synthetic fixtures**, not tuned against
measured data — stated explicitly in the heuristic note (g). Picking the midpoint
(rather than a fitted boundary) is itself the honesty signal: no calibration is claimed.

---

## (d) Files to edit (file:line → specific change)

1. **`roomestim/model.py`**
   - ~line 156: add `CeilingConfidence = Literal["high", "low", "unknown"]`.
   - ~lines 324-326 (RoomModel): add `ceiling_coverage: float | None = None` and
     `ceiling_confidence: CeilingConfidence = "unknown"` after `provenance`.
   - Export `CeilingConfidence` in `__all__` if model.py maintains one.

2. **`roomestim/reconstruct/_disclosure.py`** (single source of truth, core/no-torch)
   - Add `CEILING_CONFIDENCE_HEURISTIC_NOTE` string (see g) + add to `__all__`.

3. **`roomestim/adapters/mesh.py`**
   - ~line 170: add the three `_CEILING_COVERAGE_*` constants.
   - Add `_ceiling_coverage(vertices, ceiling_y) -> float | None` static method and a
     `_classify` call using the single-source classifier (import from `_disclosure` or
     a tiny helper — see g). Keep classify logic = `coverage >= _CEILING_COVERAGE_MIN`.
   - In `_extract_room_model` after line 796 (`ceiling_height_m` computed, guards pass):
     `coverage = self._ceiling_coverage(vertices, ceiling_y)` then
     `confidence = "unknown" if coverage is None else ("high" if coverage >= _CEILING_COVERAGE_MIN else "low")`.
   - In the `return RoomModel(...)` (lines 867-876): add
     `ceiling_coverage=coverage, ceiling_confidence=confidence,`.
   - Add a one-line cross-reference in the residual-failure-mode docstring
     (mesh.py:401-404): note this guard now ANNOTATES the residual via
     `ceiling_confidence` (still does not correct the height).

4. **`roomestim/export/usd.py`** (`_build_acoustics_sidecar`, return dict ~306-317)
   - Add three keys mirroring the `acoustics_model`/`disclaimer` pattern:
     `"ceiling_confidence": room.ceiling_confidence,`
     `"ceiling_coverage": room.ceiling_coverage,`  (may be `None`)
     `"ceiling_confidence_note": CEILING_CONFIDENCE_HEURISTIC_NOTE,`
   - Import the note alongside the existing `RT60_DISCLOSURE` import.

5. **`roomestim/export/gltf.py`** (`_build_acoustics_sidecar`, return dict ~231-242)
   - Identical 3-key addition + import. Keep usd.py and gltf.py byte-identical here.

6. **`roomestim/export/room_yaml.py`** (`room_model_to_dict`, ~lines 133-139)
   - On `schema_version == "0.2-draft"` AND `room.ceiling_coverage is not None`
     (i.e. measured only), emit `out["ceiling_confidence"] = room.ceiling_confidence`
     and `out["ceiling_coverage"] = room.ceiling_coverage`. **Conditional on
     `is not None`** so non-mesh 0.2-draft rooms keep byte-equal yaml (no new keys),
     preserving every committed yaml golden. `None`-absent == "not measured" (honest).

7. **`roomestim/io/room_yaml_reader.py`** (`read_room_yaml`, after provenance ~line 230)
   - Parse `ceiling_coverage = data.get("ceiling_coverage")` (float or None) and
     `ceiling_confidence` via a defensive validator mirroring `_parse_provenance`
     (allowed = `("high","low","unknown")`, default `"unknown"` when key absent).
   - Pass both into the `RoomModel(...)` constructor (~lines 232-241).

8. **`proto/room_schema.v0_2.draft.json`** (properties block, after `provenance` ~line 154)
   - Add OPTIONAL (not in `required`) documented properties:
     `"ceiling_coverage": { "type": ["number","null"], "minimum": 0, "maximum": 1, "description": "..." }`
     `"ceiling_confidence": { "type": "string", "enum": ["high","low","unknown"], "description": "HEURISTIC under-report guard; NOT calibrated. ..." }`
   - This honors the v0.27.0 lesson (a new round-tripped field MUST be in the schema).
     Root already has `additionalProperties: true`, but we add explicit properties so
     the field is documented and the enum is enforced.

9. **`roomestim/cli.py`** (near `_maybe_print_estimated_notice`, ~line 420)
   - Add sibling `_maybe_print_low_ceiling_notice(room)`: if
     `getattr(room, "ceiling_confidence", "unknown") == "low"`, print to `stderr`:
     `"NOTE: ceiling height may be UNDER-reported — the detected ceiling plane covers
     only {coverage:.0%} of the floor footprint (heuristic threshold 50%). A tabletop,
     mezzanine slab, or under-sampled ceiling may have been mis-picked. Verify ceiling
     height before install. (ceiling_confidence=low, HEURISTIC not calibrated.)"`
   - Call it at the SAME site(s) as `_maybe_print_estimated_notice` (so measured rooms
     get the warning, reconstructed rooms get theirs — they are not mutually exclusive).

---

## (e) Test list (synthetic only — `tests/test_adapter_mesh.py` + `tests/test_export_room_yaml.py`)

1. **High-confidence (existing fixtures)**: parse a clean shoebox fixture
   (`lab_room.obj` / `shoebox_yup.usdz`) → `room.ceiling_confidence == "high"` and
   `room.ceiling_coverage` ≈ 1.0 (assert `>= 0.9`).
2. **`ceiling_height_m` byte-equal**: assert the shoebox `ceiling_height_m` is
   UNCHANGED vs the pre-change expected value (the new fields must not perturb it).
   Reuse the existing `test_mesh_adapter_parses_shoebox` expectations.
3. **Low-confidence (constructed mis-pick mesh)**: build a synthetic vertex set via
   `trimesh.Trimesh(...)` mirroring the existing concave/up-axis test helpers
   (test_adapter_mesh.py ~166-281): a full room shell (dense floor + four walls
   spanning the whole XZ footprint) with the TRUE ceiling **sparse / under-sampled**,
   plus a **small high tabletop** (dense horizontal plane on a small XZ patch) sitting
   just below the true ceiling so it is the topmost still-dense bin. Assert
   `room.ceiling_confidence == "low"` and `room.ceiling_coverage < 0.50`. This is the
   documented tabletop/mezzanine mis-pick scenario.
4. **Fail-safe**: degenerate / single-plane input → `ceiling_confidence == "unknown"`,
   `ceiling_coverage is None`, no raise. (Unit-test `_ceiling_coverage` directly on a
   tiny array if a full mesh is awkward.)
5. **Round-trip (schema-threaded)** in `tests/test_export_room_yaml.py`:
   - Build a `RoomModel(..., ceiling_coverage=0.2, ceiling_confidence="low")`,
     `write_room_yaml` → `read_room_yaml`, assert both fields preserved. Mirrors the
     v0.27.0 schema round-trip test.
   - **Byte-equal guard**: a RoomModel with `ceiling_coverage=None` (default) writes
     yaml with NO `ceiling_coverage`/`ceiling_confidence` keys (assert keys absent) →
     existing non-mesh yaml goldens stay byte-equal.
6. **Sidecar**: `_build_acoustics_sidecar` for a measured room contains
   `ceiling_confidence`, `ceiling_coverage`, and `ceiling_confidence_note`; for an
   "unknown" room `ceiling_confidence == "unknown"` and `ceiling_coverage is None`.
7. **CLI** (optional, if a CLI test harness is cheap): a low-confidence room triggers
   the stderr NOTE; a high-confidence room does not.

Gate (per repo MEMORY `reference_canonical_test_env`): run the FULL suite via
`/home/seung/miniforge3/bin/python -m pytest` — default + web + ruff + mypy + smoke.
Baseline to hold/raise: default 396p/3s (v0.27.0). New-feature-only green is NOT GREEN.

---

## (f) Explicit schema / CLI threading decision + justification

**Schema/room.yaml: THREAD IT (optional fields, conditional emit).**
- *Why thread it*: room.yaml is the primary measured-path artifact. If the mesh
  adapter produces `confidence="low"` and the writer dropped it, the under-report
  warning would be silently lost at the yaml boundary — exactly the silent-drop class
  the repo rejects, and exactly the v0.27.0 HIGH (new field not in schema → broken
  round-trip). So we add documented optional schema properties + reader support.
- *Why byte-equal is preserved*: emit ONLY when `ceiling_coverage is not None`
  (measured paths). Non-mesh / image / hand-authored 0.2-draft rooms emit no new keys
  → every committed yaml golden is byte-equal. Absent key == "not measured" (honest,
  matches the `None`/"unknown" defaults). This is stricter-but-safer than `provenance`
  (which is always emitted) because coverage is genuinely optional.

**CLI: THREAD IT (minimal stderr notice).**
- *Why*: the measured/LiDAR path is the B2B install-grade product; an under-reported
  ceiling silently degrades placement. A one-line stderr NOTE (mirroring the existing
  reconstructed notice) is cheap and high-value, and explicitly labels itself HEURISTIC.
- *Kept minimal*: stderr only, single function, fires solely on `confidence == "low"`.

---

## (g) Honesty labeling (exact strings / docstrings)

**Single source of truth** — add to `roomestim/reconstruct/_disclosure.py` (the
established honesty-disclosure module, already imported by usd/gltf exports):

```python
# Ceiling-confidence under-report guard. ceiling_coverage is a genuine geometric
# measurement; ceiling_confidence is a HEURISTIC label, NOT a calibrated probability.
CEILING_CONFIDENCE_HEURISTIC_NOTE: str = (
    "ceiling_confidence is a HEURISTIC label (NOT a calibrated probability) derived "
    "from ceiling_coverage = the fraction of 25 cm floor-footprint grid cells that "
    "contain a scan vertex within +/-10 cm of the detected ceiling plane. "
    "coverage >= 0.50 -> 'high'; coverage < 0.50 -> 'low' (the densest upper plane "
    "spans a minority of the footprint, so a tabletop, mezzanine slab, or severely "
    "under-sampled ceiling may have been mis-picked and the height UNDER-reported). "
    "The 0.50 threshold is a conservative geometric rule of thumb validated only on "
    "synthetic fixtures; it is NOT calibrated against measured data. 'unknown' means "
    "coverage was not measured (e.g. image-reconstructed or hand-authored geometry)."
)
```

Plus:
- The two `RoomModel` field docstrings (section a) state measurement-vs-heuristic.
- The `_ceiling_coverage` method docstring restates the metric and the no-calibration
  caveat, and notes it never changes `ceiling_height_m`.
- mesh.py:401-404 docstring updated to point at the new annotation.
- The CLI NOTE string ends with `(ceiling_confidence=low, HEURISTIC not calibrated.)`.

This keeps ALL user-facing wording single-sourced from `_disclosure.py`, mirroring the
`RT60_DISCLOSURE` pattern — no retyped/divergent disclosure strings.

---

## (h) Version bump + commit-message sketch

`pyproject.toml:7` and `roomestim/__init__.py:3`: `0.27.0 → 0.28.0` (MINOR — additive
capability, no numeric change to `ceiling_height_m` or RT60).

Commit sketch:
```
roomestim v0.28.0 — 천장 높이 confidence flag: measured-path under-report 가드 (상용화 Phase 2; D96; mesh.py:390-404 deferred 구현): 천장 plane 이 footprint 를 덮는 비율(ceiling_coverage, 25cm 그리드 ±10cm 밴드)을 정직한 기하 측정으로 산출 + 0.50 보수적 임계 휴리스틱(ceiling_confidence high/low/unknown, NOT calibrated) 로 tabletop/mezzanine/under-sampled 천장 오선택 경고. RoomModel 2필드(additive, keyword-default unknown/None)·sidecar(usd/gltf)·room.yaml optional round-trip(measured 일 때만 emit→기존 golden byte-equal)·CLI stderr NOTE. ceiling_height_m·RT60 무변경, 합성 픽스처만 검증(실데이터 calibration 미주장). _disclosure.py 단일진실원천 NOTE — MINOR(additive, 수치 byte-equal)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

---

## Phase checklist (RESUME POINTER — update each phase)
- [x] P1 model.py: type alias + 2 fields
- [x] P2 _disclosure.py: heuristic NOTE single source
- [x] P3 mesh.py: constants + `_ceiling_coverage` + classify + wire into `_extract_room_model`
- [x] P4 exports usd.py + gltf.py: 3 sidecar keys
- [x] P5 room_yaml writer + reader + schema: optional conditional round-trip
- [x] P6 cli.py: low-ceiling stderr notice
- [x] P7 tests: high / byte-equal / low mis-pick / fail-safe / round-trip / byte-equal-absent / sidecar / CLI notice
- [x] P8 version bump 0.27.0→0.28.0 + FULL gate GREEN (default 407p/3s, web 86p/3s, ruff 0, mypy 0)
- [x] P9 code-reviewer (opus, independent): APPROVE — 0 CRITICAL/HIGH/MEDIUM, 3 LOW all fixed pre-commit + re-gated

### P9 code-review outcome (2026-06-07, independent opus code-reviewer) — APPROVE
3 LOW findings, ALL fixed pre-commit then re-gated GREEN:
- **LOW-1** mesh.py `_ceiling_coverage` docstring overclaimed "coverage ~1.0 for any true
  ceiling" — it's a vertex-OCCUPANCY measure so a complete-but-low-poly / under-sampled
  ceiling reads low. Tempered docstring: it tracks SAMPLING density too and is deliberately
  CONSERVATIVE (false "low" never false "high"). Docs-only.
- **LOW-2** writer/reader asymmetry: a hand-authored `(coverage=None, confidence="low")`
  would drop confidence on rewrite (orphan, unreachable from writer output — NOT the v0.27.0
  measured defect). Reader now couples the fields (coverage None → confidence "unknown") +
  new `test_reader_decouples_confidence_without_coverage` locks the stable round-trip.
- **LOW-3** `_ceiling_coverage` finite-check covered only XZ; extended to full XYZ so a
  non-finite Y fails safe (→ None → "unknown") instead of silently understating coverage.
Re-gate after fixes: default 408p/3s (+1 coupling test), ruff+mypy EXIT0.

### P8 empirical coverage readings (proof metric reads "high" on clean rooms)
Committed fixtures (coverage / confidence): lab_room.obj 1.000/high, lab_room.gltf
1.000/high, lab_room.glb 1.000/high, lab_room.ply 1.000/high,
lab_room_vertex_color.ply 1.000/high, shoebox_yup.usdz 1.000/high,
shoebox_zup.usdz 1.000/high. Generated test fixtures: densified-outlier-box
0.926/high, corridor LiDAR 0.976/high, L-prism 1.000/high. Low-confidence
mis-pick fixture: coverage 0.176/low (under-reported height ~2.58 m vs true 3.0 m).
All clean rooms read "high" without tuning constants; only the genuine tabletop
mis-pick reads "low". No calibration claimed.

## Open questions
- Cell size 0.25 m and band ±0.10 m are first-principles choices, not tuned. If the
  synthetic low-confidence fixture lands too near the 0.50 boundary, prefer adjusting
  the FIXTURE (make the tabletop unambiguously small) over tuning constants — tuning
  constants to pass a test would manufacture a calibration claim. Record any constant
  change with explicit synthetic-only justification.
