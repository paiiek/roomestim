# Plan — robust footprint mode (ⓐ) + ceiling_confidence honesty fix (ⓑ)

**Date:** 2026-06-22 · **Type:** additive product change (MINOR) · **Executor → code-review → verifier**
**Baseline:** default 686p/7s ([[reference_canonical_test_env]]) · **NO FAKE NUMBERS** (only validated figures from the two research notes)

## Context
Two SCRREAM-validated findings motivate two **independent, additive** changes to `MeshAdapter`:
- **ⓐ** Vertex noise inflates the concave-hull footprint monotonically (+19.4%@5cm, +39%@10cm). A
  density-percentile boundary trim before the hull roughly halves this (+8.3%@5cm, +12%@10cm) and is
  unchanged on clean input. Validated end-to-end in `scrream-gt/scrream_seg_frontend_proto.py`.
- **ⓑ** At extreme noise the ceiling height collapses (1.34 m vs true 2.58 m) yet `ceiling_confidence`
  reports "high" because it keys ONLY on `ceiling_coverage >= 0.50` — a wrong-but-dense plane still has
  high coverage. Confidence must also gate on plane plausibility.

Grounding read this session (file:line facts the executor must honor):
- `roomestim/adapters/mesh.py` — `FloorReconstruction` Literal (L59), `_resolve_floor_reconstruction`
  (L256-278), reconstruction dispatch (L940-962), `_robust_floor_ceiling_y` (L397-478),
  `_ceiling_coverage` (L480-527), `_classify_ceiling_confidence` (L529-543), production call site
  (L900-908). Confidence constants L189-191.
- `roomestim/reconstruct/floor_polygon.py` — `floor_polygon_from_mesh` (L123-227), the occupancy
  variant's synthetic-(N,3) reuse trick (L327-328). **No `floor_band_points` exists** — the prompt's
  assumed helper is absent; the proto's `floor_band` is the reference.
- `roomestim/model.py` — `RoomModel.ceiling_coverage`/`ceiling_confidence` already exist (L341-346);
  `CeilingConfidence` Literal L166. **No schema bump needed.**
- `roomestim/cli.py` — `--floor-reconstruction` choices (L80), help (L82-91), notice block (L656-701).
- scipy is a **hard dependency** (`pyproject.toml` L36 `scipy>=1.10`; `scipy.spatial.distance` already
  imported in `vision/horizonnet/misc/post_proc.py`). ⇒ **use `scipy.spatial.cKDTree`; no new dep.**

## Guardrails
**Must have**
- `robust` is a NEW opt-in `floor_reconstruction` value; deterministic (no RNG).
- All EXISTING modes (`convex`/`concave`/`occupancy`/`auto`) byte-identical → every golden unchanged.
- ⓑ leaves `ceiling_height_m` UNCHANGED (annotation only); clean shoebox (`lab_room.obj`, 2.5 m) stays
  `ceiling_confidence="high"`; tabletop mis-pick stays `"low"`; degenerate stays `"unknown"`.
- Full gate green: `/home/seung/miniforge3/bin/python -m pytest` + web markers + `ruff check` + `mypy`.

**Must NOT have**
- No default behavior change; no schema_version bump; no new third-party dependency.
- No accuracy claim for `robust` beyond the validated n=1 noise-sweep numbers; no Primitive-B
  (through-opening) capability (design-only, not shipped).
- No tuning of existing constants (`_CEILING_COVERAGE_MIN`, ratios, bins) to force a test green.

---

## Change ⓐ — `floor_reconstruction="robust"` (density-percentile boundary trim)

### Step A1 — new reconstruction function in `reconstruct/floor_polygon.py`
Add `floor_polygon_robust(mesh_vertices, *, band_m=0.15, k=12, drop_pct=8.0, ratio=_DEFAULT_RATIO) -> list[Point2]`.
Faithfully reproduce the validated proto pipeline (vertices arrive **already Y-up-normalized** from
`MeshAdapter._normalize_to_y_up`, so vertical = index 1, floor plane = (x, z) = indices 0, 2):
1. Validate `(N,3)`, finite; validate `band_m>0`, `1<=k`, `0<drop_pct<100` (raise `ValueError` like the
   sibling functions so the MeshAdapter caller's existing try/except → convex fallback applies).
2. Floor band: `fy = float(np.percentile(vertices[:,1], 1.0))`; `band = vertices[vertices[:,1] <= fy + band_m]`;
   `xz = band[:, [0, 2]]`.
3. Density trim (port `density_trim` verbatim): if `len(xz) <= k+1` return `xz` untrimmed; else
   `tree = cKDTree(xz)`, `d,_ = tree.query(xz, k=k+1)`, `md = d[:,1:].mean(1)`,
   keep `xz[md <= np.percentile(md, 100 - drop_pct)]`.
4. Reuse the concave path: build `synth = np.column_stack([kept[:,0], np.zeros(len(kept)), kept[:,1]])`
   and `return floor_polygon_from_mesh(synth, ratio=ratio)` — inherits every guard, `simplify`,
   `is_simple_polygon`, `canonicalize_ccw` (same pattern as `floor_polygon_from_mesh_occupancy` L327-328).
- Add module constants `_ROBUST_BAND_M=0.15`, `_ROBUST_KNN_K=12`, `_ROBUST_DROP_PCT=8.0` with a comment
  citing the validated table (+19.4%→+8.3%@5cm, +39%→+12%@10cm; σ=0 unchanged).
- Add `cKDTree` import: `from scipy.spatial import cKDTree`. Add `floor_polygon_robust` to `__all__`.
- **Determinism:** `cKDTree.query` and `np.percentile` are deterministic; the `<=` threshold includes
  ties deterministically; no RNG anywhere. State this in the docstring.

### Step A2 — wire the mode into `MeshAdapter`
- `mesh.py` L59: `FloorReconstruction = Literal["convex", "concave", "occupancy", "auto", "robust"]`.
- `_resolve_floor_reconstruction` (L256-278): the `get_args` membership check already covers the new
  value; update the two hard-coded error strings (L266, L276) to include `'robust'`.
- Import `floor_polygon_robust` from `reconstruct.floor_polygon` (L43-48 import block).
- Dispatch (L940-962): extend the extractor selection so `recon == "robust"` maps to
  `floor_polygon_robust`. Cleanest: `if recon in ("concave", "occupancy", "robust"):` then pick the
  extractor via a small dict/if — keep the SAME try/except → `_convex_floor_polygon` fallback + warning.
  `"auto"` resolution (L941-944) is untouched.
- Class docstring (L202-226): one sentence describing `robust` = Primitive-A density-percentile boundary
  trim (drop top-`drop_pct` sparse-kNN flyers before the concave hull), citing ONLY the validated
  numbers and noting it is the noise-robust opt-in (not a through-opening/bleed fix).

### Step A3 — CLI surface (`cli.py`)
- L80: add `"robust"` to `choices`.
- L82-91 help: append a `'robust'` clause — "density-percentile boundary trim before the concave hull;
  halves the vertex-noise over-estimate (validated n=1 SCRREAM, +19.4%→+8.3%@5cm); UNVALIDATED on real
  room scans".
- Notice block: add `"robust"` to the roomplan "ignored" tuple (L660) and the image "ignored" tuple
  (L695); add a polycam `elif floor_reconstruction == "robust":` branch (after L684) printing a one-line
  ROBUSTNESS-lever NOTE mirroring the occupancy wording (n=1 validated, NOT an accuracy guarantee).
- Confirm `PolycamAdapter(floor_reconstruction=...)` forwards the value to `MeshAdapter` unchanged (it
  already forwards `concave`/`occupancy`/`auto`); the argparse `choices` gate is the only validation.

### Step A4 — tests (`tests/test_adapter_mesh.py` + `tests/test_cli_input_validation.py`)
New tests (deterministic; build fixtures in-test with a SEEDED `np.random.default_rng`):
1. `test_floor_robust_reduces_noise_overestimate` — synthetic dense rectangular floor-band cloud +
   seeded boundary noise spray; assert `area(robust) < area(concave)` AND `robust` area error vs the
   clean-mesh GT area is materially smaller than `concave` (assert a direction/inequality, NOT the exact
   8.3% figure — that is n=1 SCRREAM-specific; do not hard-code it).
2. `test_floor_robust_matches_concave_on_clean_dense_input` — clean dense fixture; assert robust area ≈
   concave area within a tight tolerance (no harmful change on clean input).
3. `test_floor_robust_deterministic` — parse/extract twice on the same fixture; assert identical polygon
   vertex lists (bit-for-bit list equality).
4. `test_floor_robust_falls_back_on_degenerate` — too-few-points band → `floor_polygon_robust` raises →
   MeshAdapter emits the convex-fallback `UserWarning` (assert via `pytest.warns`), mirroring the
   existing concave/occupancy fallback tests.
5. CLI: `test_cli_floor_reconstruction_robust_ingests_mesh` + the robust polycam NOTE assertion,
   mirroring `test_cli_floor_reconstruction_occupancy_*` (L311-354).
- Optional: a `ROOMESTIM_MESH_FLOOR_RECON=robust` env test mirroring the concave env test (L362-376).

---

## Change ⓑ — `ceiling_confidence` plane-plausibility gate

### Step B1 — add a plausibility predicate to the classifier (`mesh.py`)
- Add a constant near L189-191:
  `_CEILING_PLAUSIBLE_MIN_M = 1.8  # below this a "ceiling" is an implausible collapse, not a room`
  Rationale comment: real ARKit robust ceilings reach down to ~2.24 m and the shoebox fixture is 2.5 m;
  1.8 m sits safely below every legitimate fixture while catching the validated 1.34 m collapse. This is
  a conservative HEURISTIC, NOT calibrated (consistent with `CEILING_CONFIDENCE_HEURISTIC_NOTE`). The
  upper bound is already enforced loud by `_MAX_CEILING_HEIGHT_M` (20 m), so the gate only adds a lower
  plausibility floor. (Executor may align to 2.0 m — the lower edge of the
  `test_roomplan_structure_split` plausible band — if review prefers consistency; either passes all
  fixtures. Default to 1.8 m.)
- Change `_classify_ceiling_confidence(coverage)` → add an OPTIONAL second arg:
  `_classify_ceiling_confidence(coverage, ceiling_height_m: float | None = None)`.
  - `coverage is None` → `"unknown"` (unchanged).
  - `"high"` requires `coverage >= _CEILING_COVERAGE_MIN` **AND** (`ceiling_height_m is None` **OR**
    `_CEILING_PLAUSIBLE_MIN_M <= ceiling_height_m <= _MAX_CEILING_HEIGHT_M`); else `"low"`.
  - The `ceiling_height_m is None` short-circuit preserves the existing classifier-only unit test
    (L1478-1481) which calls with coverage alone → those four assertions stay green WITHOUT editing.
- Docstring: document the added plausibility gate and that it only ever DEMOTES high→low (never the
  reverse), keeping the conservative/honest framing.

### Step B2 — pass the height at the production call site (`mesh.py` L908)
- `ceiling_confidence = self._classify_ceiling_confidence(ceiling_coverage, ceiling_height_m)`.
  `ceiling_height_m` is already computed at L901; `ceiling_height_m` itself is NOT modified.

### Step B3 — tests (`tests/test_adapter_mesh.py`)
1. `test_mesh_adapter_ceiling_confidence_low_on_collapsed_ceiling` — build a fixture whose robust
   ceiling collapses to an implausibly low height (< `_CEILING_PLAUSIBLE_MIN_M`) WITH high coverage
   (dense low plane), reproducing the benchmark bug; assert `ceiling_confidence != "high"` (i.e. `"low"`)
   and that `ceiling_height_m` is the collapsed value (annotation didn't change it).
2. Extend `test_ceiling_coverage_failsafe_returns_none_on_degenerate` (L1461) with explicit
   plausibility-gate assertions: `_classify_ceiling_confidence(1.0, 2.5) == "high"`,
   `_classify_ceiling_confidence(1.0, 1.0) == "low"` (collapse demoted),
   `_classify_ceiling_confidence(1.0) == "high"` (None height → gate skipped, back-compat). Keep the
   existing four single-arg assertions as-is.
3. Confirm (no edit expected) `test_mesh_adapter_ceiling_confidence_high_on_clean_shoebox` (2.5 m → high)
   and `_low_on_tabletop_mispick` (~2.6 m, coverage<0.5 → low) still pass — both heights clear 1.8 m, so
   only the coverage criterion governs them, unchanged.

---

## Byte-equality argument (explicit)
- **ⓐ:** purely additive — a new Literal member + a new dispatch branch + a new function. The
  `convex`/`concave`/`occupancy`/`auto` code paths execute identical statements as before, so every
  existing golden and every existing mode test is byte-identical. `robust` requires explicit opt-in
  (constructor arg, `--floor-reconstruction robust`, or env), so no default invocation reaches it.
- **ⓑ:** `ceiling_height_m` is never written. For ALL existing committed/golden meshes the detected
  ceiling is plausible (`lab_room.obj` = 2.5 m; no committed mesh has a collapsed ceiling — verified: no
  `ceiling_confidence` token in `tests/fixtures/`), so `height >= 1.8 m` is satisfied and the high/low
  output equals the pre-change coverage-only output. The classifier's optional-arg short-circuit keeps
  the four single-arg unit assertions unchanged. Export/disclosure tests set `ceiling_confidence`
  manually on hand-built RoomModels (never via MeshAdapter), so they are untouched. ⇒ all goldens
  byte-equal; behavior differs ONLY for an implausible-collapse mesh, of which none is committed.

## Verification (gate commands — run after each change and at the end)
```
/home/seung/miniforge3/bin/python -m pytest -q
/home/seung/miniforge3/bin/python -m pytest -q -m web
/home/seung/miniforge3/bin/python -m ruff check roomestim tests
/home/seung/miniforge3/bin/python -m mypy roomestim
```
Expected: default ≥ 686p/7s (new tests add to the count; 0 regressions), web markers green, ruff/mypy
clean. New-feature-pass alone is NOT "GREEN" — full suite must pass ([[feature: verify each step]]).

## Risks
- **Floor-band vs whole-cloud divergence:** `robust` bands the bottom ~15 cm (proto fidelity) whereas
  `concave` uses all vertices — so `robust` ≠ `concave` even on clean input. This is intended (the
  validated pipeline) and acceptable because `robust` is a distinct opt-in mode with no golden; test A2
  asserts area-parity, not vertex-parity. Documented, not a regression.
- **cKDTree cost on large clouds:** O(N log N) on the banded subset (banding shrinks N substantially);
  within the existing 5 M-vertex cap. No new bound needed.
- **Plausibility-min choice (1.8 vs 2.0 m):** a genuine sub-1.8 m low room would be demoted to "low" —
  the SAFE/honest failure direction (under-claim, never false-high). Flagged for review; default 1.8 m.
- **Primitive B not shipped:** through-opening leakage remains unaddressed (design-only, no GT). Logged
  in open-questions, not in scope here.

## Open questions (also written to `.omc/plans/open-questions.md`)
- Plausibility lower bound: ship 1.8 m or align to 2.0 m (structure-test band)? — affects which low-but-
  real ceilings are demoted to "low".
- Should `robust` also feed the `"auto"` selector (auto→robust on a noisy-boundary signal) in a later
  cycle? — out of scope; needs a noise-detection signal + validation.
