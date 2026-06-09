# Phase B — `floor_reconstruction="occupancy"` (third footprint mode) — READ-ONLY design

Status: DESIGN (architect, read-only). No production/test files edited.
Target version bump: MINOR **0.33.0 → 0.34.0** (additive opt-in mode, no default change).
Canonical Python: `/home/seung/miniforge3/bin/python`.

---

## 1. Crisp recommendation

Ship `occupancy` as a **third opt-in** mesh footprint mode that is a *denoising
front-end* to the already-shipped concave reconstructor:

1. Project floor vertices to the **(x, z)** plane (columns 0/2 — the vertices are
   already Y-up-normalized by `_normalize_to_y_up` before floor reconstruction runs,
   so **do NOT re-detect the up axis** the way the scratch `occ.py` does).
2. Build a 0.05 m occupancy grid, `np.add.at` accumulate, `mask = grid >= min_count`.
3. Keep the **largest 8-connected component** (`scipy.ndimage.label`, `structure=np.ones((3,3))`).
4. Back-project that component's cells to metric (x, z) centers.
5. **Hand the denoised cell-center cloud to the EXISTING `floor_polygon_from_mesh`**
   (concave-hull ratio=0.4 + simplify + `is_simple_polygon` guard + `canonicalize_ccw`).

This is the smallest correct, most elegant shape: occupancy does what convex/concave
cannot — reject sparse floaters via **density + connectivity** — and then reuses the
entire proven guard/degeneracy discipline of the concave path instead of duplicating it.

### Polygon-construction choice: **(c) concave-hull of the component cell centers**, implemented by delegating to `floor_polygon_from_mesh`

| Option | Verdict | Why |
|--------|---------|-----|
| (a) min-area-rect (scratch's return) | **REJECT** | Always rectangular → silently throws away every re-entrant corner. That directly contradicts the brief ("must not silently throw away re-entrant corners") and would make occupancy strictly *worse* than concave on non-shoebox rooms. The scratch returns a rect only because it needed scalar W/L to compare against `doc=` dims, not because a rect is the right product polygon. |
| (b) polygonize the mask boundary | REJECT | Preserves L-shapes but yields a 0.05 m **staircase** ring (every cell edge is a vertex) → noisy, needs its own simplification + guard code (duplication), and is more fragile than concave_hull on the same points. |
| **(c) concave-hull of cell centers (via `floor_polygon_from_mesh`)** | **RECOMMEND** | Preserves concavity (L-notches survive); the 0.05 m grid is **5× denser** than concave_hull's documented ~0.25 m "dense cloud" requirement (`floor_polygon.py:82-91`), so the boundary resolves cleanly; and it inherits — for free — the `(0,1]` ratio guard, MultiPolygon/holes handling, `simplify(0.05)`, `is_simple_polygon`, and `canonicalize_ccw` already shipped and tested. Occupancy = the *robust denoiser*; concave = the *boundary recoverer*. Clean separation of concerns. |

**Mechanism (zero guard duplication):** the occupancy function synthesizes an `(N,3)`
array from the surviving cell centers — `column 0 = x`, `column 2 = z`, `column 1 = 0.0`
(dummy; `floor_polygon_from_mesh` only reads `v[0]` and `v[2]`) — and calls
`floor_polygon_from_mesh(synth, ratio=...)`. All degeneracy paths (empty component,
<3 distinct points, collinear, non-areal hull) are then raised by the existing function
and converted to the **convex fallback + UserWarning** by the existing adapter
`try/except` at `mesh.py:904-914`.

---

## 2. scipy-dependency finding (REQUIRED REPORT)

**scipy is a HARD dependency.** `pyproject.toml:16` declares `scipy>=1.10` in
`[project].dependencies` (not an extra). It is already imported in production at
`roomestim/adapters/image.py:329` (`from scipy.ndimage import maximum_filter`) and in
the vendored HorizonNet (`vision/horizonnet/misc/post_proc.py`, `panostretch.py`).

Therefore **no lazy-import gate is needed** — `scipy.ndimage.label` can be imported at
module top of `floor_polygon.py` (or function-local; either is fine — recommend
function-local to keep the import-light module convention used elsewhere).

**mypy:** scipy ships no stubs; mypy strict (`python_version=3.10`) will flag the import.
Use the **exact existing pattern** from `image.py:329`:
`from scipy.ndimage import label  # type: ignore[import-untyped]`.

---

## 3. EXACT touch-list (file / function / line / smallest diff shape)

### 3.1 `roomestim/reconstruct/floor_polygon.py` — NEW function alongside `floor_polygon_from_mesh`
- Add module constants near `_DEFAULT_RATIO` (line 32) / `_SIMPLIFY_TOLERANCE_M` (line 39):
  - `_OCC_CELL_M = 0.05` — grid cell (validated on Redwood).
  - `_OCC_MIN_COUNT = 3` — see §5 rationale (permissive default; connectivity does the heavy floater rejection).
- Add `floor_polygon_from_mesh_occupancy(mesh_vertices, *, cell=_OCC_CELL_M, min_count=_OCC_MIN_COUNT, ratio=_DEFAULT_RATIO) -> list[Point2]`:
  1. `np.asarray(..., float)`; validate `(N,3)` (mirror lines 98-103) → `ValueError`.
  2. Project `xz = vertices[:, [0, 2]]` (Y-up convention, **not** a re-detected axis).
  3. Validate `cell > 0` and `min_count >= 1` (finite) → `ValueError` (parallels the `ratio` guard at 93-96; NaN must fail).
  4. Grid: `ij = floor((xz - xz.min(0))/cell)`, `H,W = ij.max(0)+1`, `grid=zeros((H,W),int32)`, `np.add.at(grid, (ij[:,0], ij[:,1]), 1)`, `mask = grid >= min_count`.
  5. `lab, n = label(mask, structure=np.ones((3,3)))`; if `n == 0` or `mask.sum()==0` → `ValueError("occupancy: no cell met min_count=...; cloud too sparse or floater-only")`.
  6. Largest component: `sizes = ndimage.sum(mask, lab, range(1, n+1))`; `big = 1 + argmax(sizes)`; `ys, xs = where(lab == big)`.
  7. Back-project cell **centers** (use `+0.5*cell`, cleaner than the scratch's corner): `x = xs*cell + xmin + 0.5*cell`, `z = ys*cell + zmin + 0.5*cell`. (Mapping: row index → x-min axis, col index → z-min axis — keep consistent with how `ij` was built; `ij[:,0]` came from `xz[:,0]=x`, so **row=x, col=z**.)
  8. If fewer than 3 cells → `ValueError` (let the delegate also guard, but fail early with a clear occupancy message).
  9. `synth = np.column_stack([x, zeros_like(x), z])`; `return floor_polygon_from_mesh(synth, ratio=ratio)`.
- Update module docstring (lines 1-13) and `__all__` (line 25) to add the new symbol.
- **Optional refactor (cleaner, slightly larger diff):** extract lines 114-146 (hull→guard→simplify→ring→`is_simple`→`canonicalize_ccw`) into a private `_ring_from_xz(xz_points, ratio)` shared by both functions. **Not required** — the delegation in step 9 already reuses 100% of that tail with zero duplication. Recommend delegation (smaller diff).

### 3.2 `roomestim/adapters/mesh.py` — thread `"occupancy"` through type + resolver + parse
- **Line 49** `FloorReconstruction = Literal["convex", "concave"]` → add `"occupancy"`.
- **Line 41** import: add `floor_polygon_from_mesh_occupancy` to the existing import from `roomestim.reconstruct.floor_polygon`.
- **`_resolve_floor_reconstruction` (lines 229-250):** two hardcoded tuples `("convex", "concave")` at **line 235** (ctor validation) and **line 245** (env validation) must include `"occupancy"`. **Elegant single-source alternative:** replace both literals with `get_args(FloorReconstruction)` (already imported at line 22) so the Literal is the only place modes are listed — recommend this; update the two error-message strings (236-239, 246-249) to read `'convex', 'concave', or 'occupancy'`.
- **Parse dispatch (lines 900-916):** the current `if self._floor_reconstruction == "concave":` block must also cover `"occupancy"`. Smallest correct shape:
  ```
  recon = self._floor_reconstruction
  if recon in ("concave", "occupancy"):
      extractor = (floor_polygon_from_mesh if recon == "concave"
                   else floor_polygon_from_mesh_occupancy)
      try:
          floor_polygon_2d = extractor(vertices)
      except ValueError as exc:
          warnings.warn(f"MeshAdapter: {recon} floor reconstruction failed "
                        f"({exc}); falling back to convex hull.", UserWarning, stacklevel=2)
          floor_polygon_2d = self._convex_floor_polygon(vertices)
  else:
      floor_polygon_2d = self._convex_floor_polygon(vertices)
  ```
  This preserves the **same fallback-to-convex + UserWarning** contract for both modes
  and keeps the convex path byte-identical (provenance stays `"measured"`).
- Class docstring (lines 192-199) — add a one-line `"occupancy"` description.

### 3.3 `roomestim/cli.py` — extend choices, help, and honest NOTE
- **`_add_floor_reconstruction_arg` line 79:** `choices=["convex", "concave"]` → add `"occupancy"`; extend help (lines 81-85) with: *"'occupancy' (density + connected-component footprint; rejects sparse floaters in noisy RGB-D reconstructions — robustness lever, n=1 Redwood evidence, NOT an accuracy guarantee)."*
- **`_get_adapter` (lines 396-446):** the three `== "concave"` guards must also handle occupancy:
  - **roomplan line 402** and **image line 425** ("ignored for --backend X" NOTE): change `== "concave"` → `in ("concave", "occupancy")` so the inert-on-non-mesh NOTE still fires (no silent no-op).
  - **polycam line 413** (the STRUCTURAL/UNVALIDATED NOTE): add an occupancy-specific branch emitting an **honest** stderr NOTE distinct from concave's, e.g. *"NOTE: occupancy footprint is a ROBUSTNESS lever (density + connectivity rejects floaters); accuracy is UNVALIDATED as a default — single-scene (n=1) Redwood evidence, NOT an accuracy guarantee."* Keep the existing concave message unchanged.
- No change needed to `cast("FloorReconstruction | None", ...)` at line 422 — the widened Literal covers it.

### 3.4 `roomestim/adapters/polycam.py` — no change
`PolycamAdapter(MeshAdapter)` passes `floor_reconstruction` straight through the
constructor; the widened Literal + resolver cover it. (Confirmed: polycam.py has no
mode enumeration of its own.)

### 3.5 No web-layer change
Grep confirms no web module enumerates the modes; the CLI `choices` list is the only
user-facing enumeration.

---

## 4. Test set (non-tautological; mirror existing patterns)

### 4.1 `tests/test_reconstruct_floor_polygon.py` (unit — the algorithm)
- **`test_occupancy_rejects_sparse_floaters`** (THE non-tautological test): build a dense
  room cloud (reuse `_l_shaped_cloud` or a simple dense rectangle) PLUS a handful of
  **sparse floater points** placed several metres outside the room (1-2 points per stray
  location, below `min_count` and disconnected). Assert:
  - convex hull of the SAME cloud (`MultiPoint(...).convex_hull.area`) is **inflated** by
    the floaters, while
  - `floor_polygon_from_mesh_occupancy(cloud)` area ≈ the TRUE room area and is
    **strictly smaller** than the floater-polluted convex area. This proves occupancy
    *recovers the room by rejecting floaters* — not a tautology against convex.
- **`test_occupancy_preserves_concave_notch`**: dense L-cloud → ≥6 vertices, simple ring,
  area ≈ 27 m² (parallels `test_floor_polygon_from_mesh_preserves_concave_notch`). Proves
  the delegation keeps re-entrant corners (option (a) min-rect would fail this).
- **`test_occupancy_floater_only_or_empty_raises`** (degeneracy): a cloud that is ALL
  sparse noise (no cell reaches `min_count`) → `ValueError`. Also a `<3`-distinct-cell
  cloud → `ValueError`.
- **`test_occupancy_rejects_bad_params`**: `cell<=0`, `min_count<1`, NaN → `ValueError`
  (parallels `test_floor_polygon_from_mesh_rejects_bad_ratio`).
- **`test_occupancy_rejects_bad_shape`**: non-(N,3) → `ValueError`.

### 4.2 `tests/test_adapter_mesh.py` (adapter integration)
- **`test_mesh_adapter_occupancy_mode_constructor`**: `MeshAdapter(floor_reconstruction="occupancy").parse(l_obj)` → `RoomModel`, `len(floor_polygon) > 4`, `provenance == "measured"`, one wall per edge (parallels lines 198-219).
- **`test_mesh_adapter_occupancy_mode_env_var`**: `ROOMESTIM_MESH_FLOOR_RECON=occupancy` honored (parallels 222-231).
- **`test_mesh_adapter_explicit_arg_overrides_env`** extension: env=occupancy + ctor=convex → convex result (precedence).
- **`test_mesh_adapter_occupancy_degeneracy_falls_back_to_convex`**: monkeypatch
  `floor_polygon_from_mesh_occupancy` to raise → `pytest.warns(UserWarning, match="falling back to convex")`, 4-vertex shoebox floor (parallels 729-752).
- **`test_mesh_adapter_invalid_env_value_raises`** already covers `bogus`; add an assert
  that `occupancy` is now accepted (negative-of-negative guard).
- **Byte-equal guard (REGRESSION):** `test_mesh_adapter_default_is_convex_byte_equal`
  (line 180) already proves default==convex; no change needed — occupancy is never the
  default, so cuboid goldens stay byte-equal.

### 4.3 `tests/test_cli_input_validation.py` (CLI parse + NOTE)
- **`test_cli_floor_reconstruction_occupancy_ingests_mesh`**: `--floor-reconstruction occupancy` on `--backend polycam` with the L-mesh → rc==0, footprint recovered (parallels 219-231).
- **`test_cli_occupancy_notice_for_mesh_backend`**: occupancy on polycam emits the
  ROBUSTNESS/UNVALIDATED/n=1 NOTE on stderr (parallels 263-277).
- **`test_cli_occupancy_notice_ignored_for_non_mesh_backend`**: occupancy + roomplan →
  "ignored for --backend roomplan" NOTE (parallels 250-260).
- **argparse choices**: an invalid `--floor-reconstruction foo` still exits 2 (argparse),
  and `occupancy` now parses — add/extend a choices assertion.

---

## 5. min_count / cell — defaults & exposure (NO false precision)

- **`cell = 0.05 m`** — fixed default (Redwood-validated). Exposed as a **function-level
  kwarg only** (like concave's `ratio`). NOT a CLI flag.
- **`min_count = 3`** default. **Rationale (honest):** the scratch used 5 for clean laser
  and 3 for noisy recon — i.e. there is **no single correct value**; it trades
  floater-rejection against room-erosion and is intrinsically scan-density-dependent.
  Choose **3** because (a) it is the **safe failure direction** — under-rejection keeps
  the room, whereas an over-aggressive 5 on a sparsely-sampled real scan can fragment the
  room and let the connected-component step pick a *sub-room*, silently UNDER-reading the
  footprint (a wrong answer dressed as measured); and (b) the **connected-component step
  is the dominant floater rejector** (floaters are disconnected sparse clusters that lose
  to the room's giant component regardless), so `min_count` only needs to strip the
  sparsest noise — a low threshold suffices. Document both validated values in the
  docstring; expose `min_count` as a function kwarg for the clean-dense-scan operator who
  wants `min_count=5`. **No auto-tuning** (no footprint GT — auto-tuning would manufacture
  false precision; explicitly out of scope, consistent with the ADR 0042 "UNVALIDATED
  accuracy" honesty posture).

---

## 6. Honesty / guardrails (encoded above, restated)

- **Default stays `convex`.** Occupancy is opt-in (ctor > env > convex precedence
  unchanged). `test_mesh_adapter_default_is_convex_byte_equal` (mesh.py path) + cuboid
  goldens remain **byte-equal** — occupancy is exercised ONLY by its own tests.
- **Provenance stays `"measured"`** (the parse path that sets `provenance="measured"` at
  `mesh.py:959` is shared; occupancy changes only the polygon, not the provenance/height).
- **Fail-loud / fallback:** every degeneracy (empty mask, no component, <3 cells,
  collinear, non-areal hull, bad params) raises `ValueError`; the adapter converts that to
  **convex fallback + UserWarning** exactly like concave (`mesh.py:904-914` pattern reused).
- **No new false-precision CLI knobs:** `cell`/`min_count` are function-level only.
- **Honest CLI NOTE:** occupancy selection prints a robustness-lever / n=1-evidence /
  NOT-an-accuracy-guarantee NOTE — never an accuracy claim.

---

## 7. Gate-impact prediction

- **default suite:** purely additive. No existing test changes behavior (convex path
  byte-identical; goldens byte-equal). New tests ≈ **+12** (5 unit + 4 adapter + 3 CLI),
  all PASS by construction. Net: baseline pass count **+~12**, skips unchanged.
- **web suite:** no web code touched → unchanged.
- **ruff:** new function + tests must satisfy line-length/docstring rules (the module is
  docstring-heavy; match its style).
- **mypy strict:** the ONLY new friction is the scipy.ndimage import — annotate with
  `# type: ignore[import-untyped]` (exact pattern at `image.py:329`). `np.add.at`,
  `ndimage.label/sum`, `np.where` are all `Any`/typed-OK; the synthesized `(N,3)` float
  array satisfies `floor_polygon_from_mesh`'s signature. Widening the `Literal` + using
  `get_args(FloorReconstruction)` keeps the resolver exhaustive with no `cast` churn.
- **smoke:** unchanged (occupancy not on any default/smoke path).
- Run the canonical gate: `/home/seung/miniforge3/bin/python -m pytest` (default), then
  `-m web`, then `ruff check`, `mypy`, smoke — per the project's "full gate = GREEN" rule.

---

## 8. Version bump

`0.33.0 → 0.34.0` (MINOR): new public symbol
`reconstruct.floor_polygon.floor_polygon_from_mesh_occupancy`, widened
`FloorReconstruction` Literal, new CLI choice — all additive, backward-compatible.
Update `pyproject.toml:7` and `roomestim/__init__.py:3`.

---

## 9. Touch-list summary (files)

| File | Change |
|------|--------|
| `roomestim/reconstruct/floor_polygon.py` | NEW `floor_polygon_from_mesh_occupancy` (+2 consts, `__all__`, docstring); delegates to existing concave tail. |
| `roomestim/adapters/mesh.py` | Widen `FloorReconstruction` Literal (49); resolver tuples→`get_args` (235/245) + messages; import occupancy fn (41); parse dispatch covers occupancy w/ same fallback+UserWarning (900-916); docstring. |
| `roomestim/cli.py` | `choices` + help (79-85); `_get_adapter` NOTE guards `in ("concave","occupancy")` (402/425) + occupancy-specific honest NOTE (413). |
| `roomestim/adapters/polycam.py` | none (passthrough). |
| `tests/test_reconstruct_floor_polygon.py` | +5 unit (floater-rejection is the key non-tautological one). |
| `tests/test_adapter_mesh.py` | +~4 (ctor/env/precedence/degeneracy-fallback). |
| `tests/test_cli_input_validation.py` | +3 (parse + 2 NOTE). |
| `pyproject.toml`, `roomestim/__init__.py` | version → 0.34.0. |

