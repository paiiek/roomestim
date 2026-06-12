# C1 — Floater-robust footprint via AUTO-SELECT, convex-preserving (v0.37.0)

PLANNER deliverable. Parent: `.omc/plans/data-unblock-validation-cycle.md` Tier 2 C1.
Baseline (RE-MEASURED LIVE 2026-06-12 @v0.36.1, miniforge `pytest -q`): **default 596p/7s · web 86p/3s ·
ruff clean · mypy clean (50 files)**. (562p/7s was the v0.35.0 pin; A3/B5/B6 added +34 tests since.
"No regression" checks against 596p/7s + additive growth only.)
Hard rules: NO FAKE NUMBERS · doc/test numbers all derived in this plan are reproducible (see Step 4 derivation).
OMC route: planner → executor → code-review → verifier (independent passes; the validation test is NOT the gate).

---

## Scope (LOCKED — do not re-litigate)
- **Disconnected-floater-engulfing fix ONLY.** A new opt-in `auto` mode that switches to the existing
  `occupancy` extractor *only when* a cheap signal detects a spatially-DISCONNECTED floater cluster engulfed by
  the convex hull; otherwise stays on the exact convex path.
- **NOT a new default.** `convex` remains the default. `auto` is opt-in via the same arg / env / CLI surface.
- **NO bleed claim, NO re-entrant-recovery claim.** Connected through-opening bleed stays a single connected
  component → signal cannot fire → never switches → *by construction* this cannot be advertised as a bleed or
  notch-recovery fix. The code-review MUST confirm H1's removed re-entrant over-claim (ex-`mesh.py:199`) is not
  silently re-introduced in any new docstring / NOTE / README line.
- **Convex-preserving / byte-equal by construction.** Clean input (any room shape, any plausible density)
  yields a single coarse-connected component → φ = 1.0 *exactly* → signal does not fire → the dispatch calls
  `_convex_floor_polygon(vertices)` on the **same** vertices with zero perturbation → identical bytes.

---

## Verified code anchors (read before editing)
- `roomestim/adapters/mesh.py:54` — `FloorReconstruction = Literal["convex","concave","occupancy"]`.
- `roomestim/adapters/mesh.py:241-263` — `_resolve_floor_reconstruction` (arg > env `ROOMESTIM_MESH_FLOOR_RECON`
  > "convex"); error strings enumerate the three modes; `_FLOOR_RECON_ENV` const at `mesh.py:132`.
- `roomestim/adapters/mesh.py:293-311` — `_convex_floor_polygon` (the byte-equal legacy path).
- `roomestim/adapters/mesh.py:919-937` — dispatch: `recon in ("concave","occupancy")` → extractor with
  `ValueError → _convex_floor_polygon` fallback + `UserWarning`; else convex.
- `roomestim/reconstruct/floor_polygon.py` — `floor_polygon_from_mesh` (concave),
  `floor_polygon_from_mesh_occupancy` (grid cell `_OCC_CELL_M=0.05`, `_OCC_MIN_COUNT=3`, largest 8-CC; raises on
  no-cell / <3-cell). This is the extractor `auto` reuses unchanged.
- `roomestim/cli.py:70-88` — `_add_floor_reconstruction_arg` (`choices=["convex","concave","occupancy"]`).
- `roomestim/cli.py:409-444` — `_get_adapter` per-backend NOTE block (mesh = polycam; roomplan/image emit
  "ignored" NOTE).
- Tests: `tests/test_reconstruct_floor_polygon.py` (keystone `test_occupancy_rejects_sparse_floaters`, helper
  `_dense_rect_cloud`), `tests/test_adapter_mesh.py:289` (`test_mesh_adapter_default_is_convex_byte_equal` — the
  byte-equal pattern to copy).
- `docs/adr/` highest = `0047` → **new ADR = 0048**. `scripts/lint_tense.py` gate active.
- Version single source: `roomestim/__init__.py:3` + `pyproject.toml:7` (both `0.36.1` → `0.37.0`).

---

## Resolved design decisions (with rationale)

### D1 — Mode shape: new `FloorReconstruction` value `"auto"`, dispatched in mesh.py; signal lives in floor_polygon.py
Add `"auto"` to the `Literal` and to the arg/env/CLI choices (one opt-in surface, identical to existing modes).
The **detection signal is a pure function in `floor_polygon.py`** (no adapter state, no I/O) so it is unit-
testable in isolation. mesh.py only orchestrates: resolve `auto` → call the signal → pick `occupancy` or
`convex` → reuse the existing extractor/fallback block.

### D2 — Floater-detection signal (ONE primary signal, cheap, decoupled from the 0.05 m extraction grid)
**Signal = convex-hull area-inflation ratio φ on a COARSE connectivity grid.**
- Rasterize the floor-projected (`x=v[0]`, `z=v[2]`) cloud onto a coarse grid `cell_det = 0.25 m`,
  `min_count_det = 1` (any point occupies). 8-connected-component label.
- **If ≤ 1 component → return φ = 1.0 exactly (early return).** This is the byte-equal guarantee: a single
  connected mass has no separated floater.
- Else φ = `convex_hull_area(ALL occupied cell centres) / convex_hull_area(LARGEST-CC cell centres)`.
- **Fire (switch `auto`→`occupancy`) iff φ ≥ θ, θ = `_AUTO_FLOATER_PHI_THRESHOLD = 1.10`.**

**Why a COARSE detection grid, decoupled from the 0.05 m extraction grid (load-bearing — verified):** running
the area-ratio on the 0.05 m / min_count=3 occupancy grid FALSE-FIRES — a clean L-room fragments into edge
components (φ=1.25) and a density-marginal clean room speckles (φ=4661). At `cell_det=0.25, min_count_det=1`
**every** clean case collapses to a single component → φ = 1.0 exactly (verified: 4×5 dense, sp 0.04, sp 0.10,
6×8 sp 0.03, L-room dense, L-room sp 0.10 — all φ = 1.000000). Only a cluster separated by a ≥ 0.25 m gap that
also extends the hull by ≥ 10 % produces φ ≥ θ.

**Why this is the right SINGLE signal (harm-weighted):** φ measures the exact harm we fix — convex-hull area
*engulfment*. Edge fragmentation / non-rect geometry add negligible area (φ→1.0 via the single-component early
return); a distant disconnected floater adds large area (φ grows with distance: 0.5 m→1.11, 1.0 m→1.23,
2.0 m→1.45, 3.0 m→1.68). The fraction-of-cells-outside-largest-CC alternative is rejected: it is polluted by
edge fragments (304 "outside" cells where only ~16 are the real floater) and is not distance/harm-weighted.

**SAFE failure direction = false-NEGATIVE.** Under-firing (a small/near floater inflating < 10 %) → stay convex
→ identical to today's behavior → no regression, just no improvement. The DANGEROUS direction (false-positive on
clean input → break byte-equal / under-read) is locked off by construction: clean input is a single component →
φ = 1.0 < θ. `min_count_det = 1` maximizes sensitivity in the SAFE direction only; the dangerous direction is
already pinned by the single-component early return.

**Bleed / non-rect exclusion is by construction, not by tuning:** connected through-opening bleed and L-shaped
rooms are single coarse-connected components → φ = 1.0 → never fires. This *guarantees* `auto` cannot be a bleed
or notch fix (matches the V1 3DSES finding and the locked scope).

**Robustness:** the signal helper must never raise — wrap the rasterize/label/hull in a guard that returns
"do not fire" (φ = 1.0 / `False`) on any degeneracy (empty, non-finite, <3 cells in largest CC, hull not a
polygon). Degeneracy → convex → byte-equal → safe.

### D3 — Byte-equal mechanism
mesh.py dispatch resolves `auto` to an *effective* mode BEFORE the existing extractor block:
```
recon = self._floor_reconstruction
if recon == "auto":
    effective = "occupancy" if _auto_should_use_occupancy(vertices) else "convex"
else:
    effective = recon
if effective in ("concave", "occupancy"):
    try: floor_polygon_2d = extractor(vertices)
    except ValueError: <existing UserWarning convex fallback>
else:
    floor_polygon_2d = self._convex_floor_polygon(vertices)   # SAME vertices, zero perturbation
```
When the signal does not fire, `effective == "convex"` → the *identical* `_convex_floor_polygon(vertices)` call
as `convex` mode → byte-identical output. The signal helper only READS `vertices` (rasterize copy); it never
mutates the array handed to the convex path. **Test pins this** with a room.yaml byte-compare (Step 4, T-A) and
a value-equal floor-polygon assertion on a clean fixture.

### D4 — Honesty: single-source NOTE constant + wording list
New module constant `AUTO_FLOOR_RECON_NOTE` (single source of truth, in `floor_polygon.py`, imported where
needed), exact text:
> `auto` footprint = DISCONNECTED-floater rejection only (switches to the occupancy extractor when a coarse-grid
> convex-hull area-inflation signal detects a spatially-separated cluster; else stays convex, byte-equal). It is
> NOT a through-opening-bleed fix and NOT a re-entrant/notch-recovery capability (connected geometry never
> triggers it). Threshold validated on a deterministic synthetic floater fixture only; design justification
> cites the established Redwood noisy-recon result (+22% convex over-read → +5% occupancy, n=1). Opt-in, NOT the
> default; a genuinely-detached REAL structure separated by a scan gap would also be dropped.

---

## File-by-file change list (exact functions)

1. **`roomestim/reconstruct/floor_polygon.py`** (signal + constants + NOTE; no change to existing extractors)
   - Add module constants: `_AUTO_DET_CELL_M = 0.25`, `_AUTO_DET_MIN_COUNT = 1`,
     `_AUTO_FLOATER_PHI_THRESHOLD = 1.10`, and `AUTO_FLOOR_RECON_NOTE` (D4 text).
   - Add `disconnected_floater_phi(mesh_vertices: np.ndarray) -> float` — pure, returns φ (1.0 if single coarse
     component or any degeneracy). Reuses `scipy.ndimage.label`/`sum`, `shapely` convex hull (already imported).
   - Add `auto_should_use_occupancy(mesh_vertices, *, threshold=_AUTO_FLOATER_PHI_THRESHOLD) -> bool` — thin
     wrapper `return disconnected_floater_phi(v) >= threshold`. Export both in `__all__`.
   - Docstrings: describe the harm-weighted area ratio + coarse-grid rationale; **explicitly state NOT bleed /
     NOT re-entrant** (avoid re-introducing the H1 over-claim).

2. **`roomestim/adapters/mesh.py`**
   - `FloorReconstruction` literal (`:54`): add `"auto"`.
   - `_resolve_floor_reconstruction` (`:246-263`): `modes = get_args(...)` already covers `"auto"`; update the
     two error strings (`:249-252`, `:259-262`) to list `'convex', 'concave', 'occupancy', or 'auto'`.
   - Import `auto_should_use_occupancy` + `AUTO_FLOOR_RECON_NOTE` from `floor_polygon`.
   - Dispatch (`:919-937`): insert the `auto`→effective resolution shown in D3 ahead of the extractor block.
   - Class docstring (`:197-211`) + dispatch comment (`:913-918`): document `auto` per D4; no bleed/notch claim.

3. **`roomestim/cli.py`**
   - `_add_floor_reconstruction_arg` (`:78-88`): add `"auto"` to `choices`; extend help with one honest clause
     (disconnected-floater auto-select; opt-in; synthetic-validated).
   - `_get_adapter` (`:423-444` polycam branch): add an `elif floor_reconstruction == "auto"` stderr NOTE
     reusing `AUTO_FLOOR_RECON_NOTE` (or a one-line summary citing it). The roomplan/image "ignored" NOTEs
     (`:415`, `:446`) use `in ("concave","occupancy")` — extend to include `"auto"` so it is not a silent no-op.

4. **`README.md`** — add the v0.37.0 changelog row (table at `:140`) + one honest sentence wherever footprint
   modes are described; bind the design number to the cited Redwood result, never to "wall accuracy".

5. **`docs/adr/0048-auto-floater-footprint-select.md`** — new ADR (stub in Step 6).

6. **`roomestim/__init__.py:3` + `pyproject.toml:7`** — `0.36.1` → `0.37.0`.

7. **Tests** — `tests/test_reconstruct_floor_polygon.py` (signal + extractor recovery) and
   `tests/test_adapter_mesh.py` (auto dispatch + byte-equal). See Step 4. Also grep for any test enumerating
   `{"convex","concave","occupancy"}` or `get_args(FloorReconstruction)` and extend to include `"auto"`.

---

## Step 4 — Synthetic fixture spec + COMPUTED expected numbers (all reproduced via miniforge python)

**Deterministic, in-repo, no RNG** (pure `np.meshgrid` on pinned bounds/spacing).

- **Clean room cloud (true area = 20.0 m²):** rectangle `x∈[0,4]`, `z∈[0,5]`, floor points on a fixed grid at
  0.025 m spacing (`np.arange(0,4+1e-9,0.025) × np.arange(0,5+1e-9,0.025)`), y=0 → 161×201 = 32 361 points.
  (0.025 m = 2 pts per 0.05 m cell per axis → every interior 0.05 cell holds 4 ≥ min_count, so the occupancy
  extractor recovers it; at the 0.25 m detection grid it is one solid component.)
- **Disconnected floater blob:** `x∈[5.5,5.7]`, `z∈[6.5,6.7]` at 0.02 m spacing (11×11 = 121 points), i.e. a
  0.2 m blob whose nearest corner is ~1.5 m beyond the room's (4,5) corner — disconnected (>0.25 m gap) yet
  dense enough (count 6 ≥ min_count=3 at 0.05) to survive the occupancy extractor as its own small component.
- `cloud = vstack([room, floater])`.

**COMPUTED expected values (locked; reproduce with the Step-4 snippet at execution and pin in asserts):**

| quantity | value | role in test |
|---|---|---|
| φ_clean (detection, room only) | **1.000000** (single component, exact) | T-B: does NOT fire |
| φ_floater (detection, cloud) | **1.3375** | T-C: fires (≥ θ=1.10) |
| convex-hull area, clean | **20.0000 m²** (= true) | byte-equal sanity |
| convex-hull area, floater cloud | **27.99 m²** → **+39.9 %** vs true 20 | T-C: over-read magnitude |
| occupancy (auto-fired) recovered area | **19.005 m²** → **−5.0 %** vs true 20 | T-C: recovered ≈ truth |
| net effect | convex **+40 %** → auto **−5 %** | mirrors cited Redwood +22%→+5% |
| boundary: floater @0.5 m | φ = **1.1125** (fires) | T-D: just-fires boundary |
| boundary: clean | φ = **1.0** (never fires) | T-D: never-fire boundary |

Derivation note for the convex +39.9 %: the floater point at ~(5.7,6.7) is outside the room rectangle hull, so
the convex hull of room∪floater is the room corners with the far corner extended toward the floater, adding a
triangular wedge → 27.99 m². The occupancy extractor keeps only the largest 8-CC (the room) and its concave
hull (ratio 0.4) erodes ~5 % → 19.005 m². θ=1.10 sits with comfortable two-sided margin (clean exact 1.0;
fixture 1.3375; nearest false-fire risk would need a real detached ≥10%-area mass across a ≥0.25 m gap).

---

## Step 5 — Test list (additive; pin the Step-4 numbers)

In `tests/test_reconstruct_floor_polygon.py`:
- **T-sig-clean:** `disconnected_floater_phi(clean_room)` == 1.0 exactly (and `auto_should_use_occupancy` False)
  — across the clean room AND an L-room AND a sparse (0.10 m) room (parametrized) → all 1.0 (locks the coarse-
  grid single-component guarantee, incl. non-rect & bleed-proxy).
- **T-sig-floater:** `disconnected_floater_phi(cloud)` == approx 1.3375; `auto_should_use_occupancy(cloud)` True.
- **T-sig-degenerate:** signal returns 1.0 / False on empty, <3-point, non-finite input (no raise).
- **T-recover:** occupancy area on `cloud` ≈ 19.0 (rel 0.05); convex area on `cloud` ≈ 27.99 (rel 0.02);
  assert `occ_area < convex_area` and `|occ-20|/20 ≤ 0.06` (recovered ≈ truth; floater rejected).
- **T-boundary:** floater @0.5 m fires (φ≈1.11 ≥ θ); clean never fires (φ=1.0 < θ) — pins θ from both sides.

In `tests/test_adapter_mesh.py`:
- **T-A (byte-equal, THE convex-preserving gate):** parse a clean fixture (existing `lab_room.obj`, or a written
  dense clean `.obj`) through `MeshAdapter(floor_reconstruction="auto")` vs `="convex"`; assert (1) value-equal
  `floor_polygon` coords AND (2) **byte-equal serialized room.yaml** (write both to `tmp_path`, compare
  `read_bytes()`), modeled on `test_mesh_adapter_default_is_convex_byte_equal`.
- **T-fire-adapter:** auto on a written floater `.obj` produces an area strictly < the convex-mode area on the
  same file (auto switched to occupancy and rejected the floater).
- **T-resolve:** `_resolve_floor_reconstruction("auto")`, env `ROOMESTIM_MESH_FLOOR_RECON=auto`, and the bad-
  value error message all behave (env round-trips to `"auto"`; error lists all four modes).
- **T-no-fire-bleed:** a connected "through-opening" fixture (two rooms joined by a ≥0.25 m-wide neck) → auto
  does NOT fire → byte-equal to convex (locks the NO-bleed-claim by construction).

---

## Step 6 — ADR 0048 stub (`docs/adr/0048-auto-floater-footprint-select.md`)
- **Status:** Accepted (v0.37.0).
- **Context:** convex footprint engulfs disconnected RGB-D floaters (+~22–40 % over-read); `occupancy` fixes it
  but as a non-default opt-in with n=1 evidence; need a convex-preserving auto-select that never regresses clean
  input and makes no bleed/notch claim. V1 (3DSES) showed occupancy rejects DISCONNECTED floaters but NOT
  connected through-opening bleed.
- **Decision:** add opt-in `auto` mode; coarse-grid (0.25 m, min_count 1) convex-hull area-inflation signal
  φ ≥ 1.10 switches to the existing occupancy extractor; else exact convex path.
- **Drivers:** byte-equal-by-construction on clean input; harm-weighted single signal; safe failure = false-
  negative; bleed/non-rect excluded by single-component early return.
- **Alternatives considered:** (a) flip default to occupancy — rejected (regresses clean byte-equal; n=1
  evidence); (b) area-ratio on the 0.05 m extraction grid — rejected (false-fires on clean L-room φ=1.25 &
  density-marginal φ=4661); (c) fraction-of-cells-outside-largest-CC — rejected (edge-fragment polluted, not
  harm-weighted); (d) threshold auto-calibration — rejected (nonexistent capability; do not assume it).
- **Why chosen:** the coarse single-component early-return makes clean φ=1.0 exactly → byte-equal is structural,
  not tuned; θ has two-sided margin on the synthetic fixture.
- **Consequences:** threshold synthetic-fixture-validated only (Redwood cited for design, not re-acquired);
  a real detached structure across a scan gap would also be dropped (disclosed); occupancy default min_count=3
  still FAILS the notch (no re-entrant recovery — auto inherits this, must not claim otherwise).
- **Follow-ups:** real-scan threshold calibration (needs floater GT in repo); connected-bleed remains unsolved.

---

## Step 7 — Changelog / version row (README table at `:140`; v0.37.0)
> `| **v0.37.0** | 2026-06-12 | (commit) | floater-robust auto-select footprint (MINOR, additive, opt-in) — new`
> `--floor-reconstruction auto: coarse-grid (0.25 m) convex-hull area-inflation signal (φ≥1.10) switches to the`
> `occupancy extractor ONLY when a DISCONNECTED floater is detected, else stays convex (clean input byte-equal`
> `by construction). NOT default · NOT a bleed/re-entrant fix · threshold synthetic-fixture-validated (Redwood`
> `+22%→+5% cited). Single source AUTO_FLOOR_RECON_NOTE. (C1 / [ADR 0048](docs/adr/0048-auto-floater-footprint-select.md)). |`

---

## GATE checklist (all must pass; verifier collects evidence independently)
- [ ] Baseline re-measured & written into this file BEFORE code (default / web / ruff / mypy).
- [ ] **Clean byte-equal:** T-A room.yaml byte-identical (auto == convex) + value-equal floor polygon.
- [ ] **Synthetic floater detection:** T-sig-floater fires (φ≈1.3375); T-recover area ≈ 19 (−5 %) < convex
      ≈ 27.99 (+39.9 %); T-fire-adapter area < convex.
- [ ] **No false-fire:** T-sig-clean / T-no-fire-bleed φ=1.0 (clean, L-room, sparse, connected-bleed).
- [ ] **Boundary:** T-boundary pins θ from both sides.
- [ ] Full default suite GREEN, **no regression vs re-measured baseline** + only additive tests.
- [ ] Web suite GREEN (86p/3s or re-measured), ruff clean, mypy `--strict` clean, `lint_tense` clean.
- [ ] **code-review APPROVE** explicitly confirming: (a) no re-entrant/notch/bleed over-claim re-introduced in
      any docstring/NOTE/README (H1 regression check); (b) byte-equal call path is the same `_convex_floor_polygon`
      with un-perturbed vertices; (c) signal helper cannot raise.
- [ ] **verifier VERIFIED** (independent run of the suite + byte-equal + floater asserts; not the author).
- [ ] ADR 0048 + README changelog row + version bumped; RESUME POINTER in owner plan updated.

---

## RESUME POINTER (C1)
- [x] Step 1 floor_polygon.py signal + constants + NOTE
- [x] Step 2 mesh.py literal + resolve + dispatch + docstrings
- [x] Step 3 cli.py choices + NOTE branches
- [x] Step 4/5 fixtures + tests (pin computed numbers)
- [x] Step 6 ADR 0048
- [x] Step 7 README changelog + version bump
- [ ] GATE: code-review APPROVE → verifier VERIFIED → commit v0.37.0 → update owner plan line 211/231

### Reproduction note (executor, 2026-06-12, miniforge python — NO FAKE NUMBERS)
All planner numbers reproduced LIVE against the exact in-test fixtures BEFORE pinning:
- φ_clean = **1.0** exact ✓ ; φ_floater(cloud) = **1.3375** ✓ ; boundary @0.5 m = **1.1125** ✓
- convex clean = **20.0 m²** ✓ ; convex floater cloud = **27.99 m²** (+39.9 %) ✓
- occupancy (auto-fired) recovered = **19.0075 m²** (−5.0 %) — planner table said 19.005 m²;
  Δ = +0.0025 m² (both round to −5.0 %). Pinned the REPRODUCED value (T-recover uses
  `pytest.approx(19.0, rel=0.05)`, robust to the delta). No other deltas.

### Gate evidence (executor self-check; independent verifier still required)
- Baseline (pre-change, live): default **596p/7s**, web **86p/3s**, ruff clean, mypy clean (50 files), lint_tense clean.
- Post-change: default **607p/7s** (+11 additive, 0 regressions), web **86p/3s**, ruff clean,
  mypy clean (50 files), lint_tense clean. T-A byte-equal room.yaml gate PASSED (auto == convex).
- Working tree left UNCOMMITTED for independent review.
