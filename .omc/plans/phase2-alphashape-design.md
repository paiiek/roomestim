# Phase 2 / Backlog ⑥ — alpha-shape non-convex footprint (ADR 0042): ARCHITECT DESIGN (READ-ONLY)

Date: 2026-06-08 · roomestim v0.31.1 · baseline default 446p/6s (per master plan Phase 1 note)
Author: architect (read-only analysis; no files edited)
Master plan: `.omc/plans/autopilot-predictor-geometry-ambisonics.md` Phase 2

## HEADLINE / CRISP RECOMMENDATION

**The substantive core of ⑥ is ALREADY SHIPPED (v0.24.0 / D82). STOP on the algorithm.**
The alpha-shape (concave-hull) footprint extractor exists, is opt-in, is regression-pinned
byte-equal on the convex default, has degeneracy guards + convex fallback, and is tested on a
non-tautological L-shape. `shapely.concave_hull` IS an alpha-shape-family algorithm; ADR 0042
§Status-update-v0.24.0 explicitly records that it "honors §A's (a) alpha-shape recommendation
in substance."

Only a **thin residual** of ADR 0042's PR plan is genuinely unbuilt, and NONE of it can improve
accuracy because **footprint GT is absent** (validation ① reconfirmed horizontal localization is
unsolved). The two honest, non-overfit, non-regressive residual slices are:
  1. **PR3 — CLI flag** exposing the existing opt-in (`--floor-reconstruction concave`). Pure
     reachability; no golden drift; no GT needed.
  2. **PR2-partial — noise/jitter robustness test** (the ADR's σ=1–3 cm acceptance gate that
     never landed). Pure hardening of an existing structural claim; synthetic; no GT needed.

**Recommendation: prefer DEFER of ⑥ as an "accuracy" item to Phase 3 (data hunt).** If the
autopilot wants a code deliverable this phase, ship ONLY slices (1)+(2) as a MINOR bump,
explicitly framed as *usability + robustness hardening, NOT an accuracy improvement*. Do NOT
add new tuning knobs (auto-α, `floor_band_m`) — they are unvalidatable without GT and would be
magic parameters.

---

## 1. WHAT ALREADY EXISTS vs WHAT ⑥ GENUINELY ADDS

### Already shipped (v0.24.0 / D82 — "PR1-equivalent landed")

| ADR 0042 deliverable | Status | Evidence |
|---|---|---|
| `floor_polygon_from_mesh` real impl (concave) | DONE | `roomestim/reconstruct/floor_polygon.py:42-146` |
| Algorithm = concave hull (alpha-shape family) | DONE (via `shapely.concave_hull(ratio=0.4)`) | `floor_polygon.py:114` |
| Default byte-equal convex preserved | DONE | `mesh.py:281-298` `_convex_floor_polygon`; `mesh.py:904-916` |
| Opt-in wiring (constructor + env) | DONE | `mesh.py:213-250` ctor arg `floor_reconstruction`; env `ROOMESTIM_MESH_FLOOR_RECON` |
| Precedence arg > env > "convex" | DONE | `mesh.py:229-250` `_resolve_floor_reconstruction` |
| Degeneracy guards (MultiPolygon→largest, holes→exterior, ratio range, <3 pts, collinear) | DONE | `floor_polygon.py:93-127` |
| Self-intersection guard (§D) | DONE | `floor_polygon.py:140-144` via `is_simple_polygon` |
| Convex fallback + UserWarning on degeneracy | DONE | `mesh.py:904-914` |
| Douglas-Peucker simplify (noise tooth removal, §E item iii) | DONE | `floor_polygon.py:130` `simplify(0.05)` |
| Walls = extrusion reused, RANSAC NOT adopted (§C) | DONE (unchanged) | `walls_from_floor_polygon` |
| Honest dense-cloud caveat (sparse undershoot ~10-20%) | DONE | `floor_polygon.py:80-91` docstring |
| Non-tautological L-shape test (interior vertices → convex is wrong) | DONE | `tests/test_reconstruct_floor_polygon.py:19-80` (cloud has 3 y-levels + interior; convex=31.5 vs concave=27) |
| Adapter round-trip tests (constructor, env, env-override-by-arg, degeneracy fallback) | DONE | `tests/test_adapter_mesh.py:145-244, 729-747` |

### NOT shipped (ADR 0042 §I residual; §Status-update lists these OPEN)

| Residual | Honest? without GT | Recommendation |
|---|---|---|
| **PR3 — CLI flag** `--floor-reconstruction` | YES (reachability only) | SHIP (optional, small) |
| **PR2 — noise/jitter (σ=1–3 cm) acceptance gate** | YES (synthetic robustness) | SHIP (optional, small) |
| auto-α heuristic (kNN spacing → 1/alpha) | NO — unvalidatable; `ratio=0.4` already covers the knob more interpretably | DEFER (do not build) |
| `floor_band_m` (floor-near vertex filter) | NO — could help OR hurt; no GT to tune | DEFER (do not build) |
| **PR4 — SoundCam A10a non-tautological promotion** | BLOCKED — no mesh access (OQ-13e(i)) | DEFER (unchanged) |
| Default flip convex→concave | NO — golden drift + sparse undershoot regression | DO NOT DO |

**Net: ⑥ is ~80–85% complete.** The algorithm, opt-in, guards, fallback, and structural
(L-shape) test are all in place. What remains is reachability (CLI) + one robustness test.
There is NO accuracy work left that can be honestly validated with current data.

---

## 2. RECOMMENDED APPROACH

### 2a. Algorithm — KEEP `shapely.concave_hull`; do NOT re-implement Delaunay α-shape
`shapely.concave_hull(geom, ratio)` is GEOS's concave-hull (chi-shape), built on a Delaunay
triangulation with a normalized edge-length threshold — i.e. it IS the alpha-shape family the
ADR §A recommended, with a *more interpretable* knob than absolute α: `ratio=1.0`=convex hull,
`ratio→0` hugs concavities. The ADR §B `scipy.spatial.Delaunay` + `shapely.ops.polygonize`
recipe was deliberately superseded (D82) for a smaller surface and is correctly NOT worth
re-introducing. **No new dependency, no new core algorithm.**

On the "α must be principled, not magic" requirement: the shipped `ratio=0.4` is empirical but
(a) bounded/normalized [0,1] with documented endpoints, (b) caller-overridable
(`floor_polygon_from_mesh(..., ratio=...)`), and (c) accuracy-irrelevant given no GT. A
"principled" auto-ratio cannot be calibrated without footprint GT, so building it now would
manufacture false precision. KEEP the documented constant; expose the override (already exists
at the function level).

### 2b. Default behavior — OPT-IN, unchanged (mandatory)
Keep `floor_reconstruction="convex"` as the default. Rationale is decisive:
- **Golden drift**: concave_hull(ratio=0.4)+simplify(0.05) on a clean rectangular cloud is NOT
  guaranteed byte-equal to the convex hull (different vertex count/ordering/simplify rounding).
  The fixtures are cuboid-dominated → a default flip risks silently changing cuboid goldens =
  REGRESSION.
- **Sparse undershoot**: concave undershoots area ~10–20% on low-poly meshes
  (`floor_polygon.py:80-91`). Convex is the safe over-estimate (upper bound, per validation ①).
- **No GT**: we cannot prove concave is more accurate, so we cannot justify making it the
  default output everyone receives.

### 2c. Where the (optional) new slices plug in
- **CLI flag**: `roomestim/cli.py` — add a `--floor-reconstruction {convex,concave}` arg to the
  `ingest` and `run` subparsers (default `convex`), thread it through `_get_adapter` into
  `MeshAdapter(floor_reconstruction=...)`. Only meaningful for mesh backends (`polycam`, and any
  `.usdz`/mesh path); for non-mesh backends (`roomplan`, `image`) it is silently ignored or
  validated to default — see touch-list.
- **Noise test**: `tests/test_reconstruct_floor_polygon.py` — add a jittered-L-shape case.

---

## 3. EXACT FILE / FUNCTION TOUCH-LIST (smallest correct diff)

### Slice (1) — CLI flag (PR3)
- `roomestim/cli.py`
  - `_add_ingest_parser` (~line 70) and `_add_run_parser` (~line 200): add
    `p.add_argument("--floor-reconstruction", choices=["convex","concave"], default="convex",
    help="Mesh footprint extraction: 'convex' (default, safe over-estimate) or 'concave'
    (recovers re-entrant corners; UNVALIDATED accuracy, see ADR 0042).")`.
  - `_get_adapter` (line 376-401): for `backend == "polycam"` (the MeshAdapter alias) pass
    `PolycamAdapter(floor_reconstruction=getattr(args,"floor_reconstruction","convex"))`.
    `PolycamAdapter(MeshAdapter)` already accepts the kwarg (`polycam.py:20`). For `roomplan`/
    `image` backends, the flag is inert (RoomPlan footprint comes from the sidecar polygon, not
    mesh extraction; image is its own tier) — leave those constructors unchanged. If `--floor-
    reconstruction concave` is passed with a non-mesh backend, emit a one-line stderr notice
    that it is ignored (honest, no silent no-op) OR (simpler) document it as mesh-only in help.
- Provenance/labeling: the resulting `RoomModel.provenance` stays `"measured"`. Concave does NOT
  earn a stronger provenance. To label honestly, prefer adding a stderr NOTE in the CLI when
  concave is selected ("concave footprint is a STRUCTURAL estimate; accuracy is UNVALIDATED — no
  footprint ground truth exists, ADR 0042") rather than a new RoomModel field (avoid schema
  churn for an unvalidatable flag). If a durable label is wanted later, that is a separate
  schema decision (defer).

### Slice (2) — noise/jitter robustness test (PR2-partial)
- `tests/test_reconstruct_floor_polygon.py`: add
  `test_floor_polygon_from_mesh_survives_scan_jitter` — take `_l_shaped_cloud()`, add Gaussian
  jitter (seeded `np.random.default_rng(0)`, σ=0.02 m), assert recovered area ≈ 27 m² within a
  HONEST tolerance (rel≈0.15, looser than the clean rel=0.10 — jitter legitimately degrades it)
  AND `len(polygon) >= 6` (notch survives) AND `is_simple_polygon`. This is the ADR's MAJOR-#2
  acceptance gate; it proves the ±-tolerance claim is robust to scan noise, not just clean
  vertices. NO GT required (synthetic, area is known by construction).

### Nothing else changes
- `floor_polygon.py`, `mesh.py` core extraction: NO change (already correct/shipped).
- `roomestim/model.py` RoomModel: NO new field (avoid schema churn).
- Web (`roomestim_web`): NO change (core-only; web default unchanged — D30 lane separation).

---

## 4. GATE IMPACT

- **Goldens/fixtures changed: NONE.** Default stays convex → all cuboid goldens byte-equal.
  Concave remains opt-in and is exercised only by its own dedicated tests.
- **New deps: NONE.** `shapely>=2.0` already core; the algorithm is already in-tree.
- **New tests:**
  - `tests/test_reconstruct_floor_polygon.py`: +1 (jitter robustness).
  - `tests/test_cli*.py`: +1–2 (parse `--floor-reconstruction`; concave path round-trips an
    L-mesh via CLI ingest; non-mesh-backend inert/notice behavior).
- **Version bump:** MINOR (0.31.1 → 0.32.0) — additive CLI surface + new observable flag, no
  default behavior change. (If autopilot DEFERS and ships nothing, no bump.)
- **Gate suite** (must stay GREEN per master plan): default ~446→~449p, web 86p/3s unchanged,
  ruff + mypy(strict) clean, CLI smoke gains `--floor-reconstruction` help line.

---

## 5. HONESTY GUARDRAILS

- **Un-validated labeling**: CLI help text + a stderr NOTE on concave selection must say the
  concave footprint accuracy is UNVALIDATED (no footprint GT; validation ① showed localization
  unsolved). Do NOT imply concave is "more accurate" — it is *structurally* tighter (recovers
  re-entrant corners) and is an unvalidated estimate. ADR 0042 header stays PROPOSED.
- **Degenerate-case handling (already in place, keep)**:
  - α/ratio too small → MultiPolygon/fragments → take largest component, but holes→exterior;
    self-intersecting → `is_simple_polygon` ValueError → adapter convex fallback + UserWarning
    (`floor_polygon.py:120-144`, `mesh.py:904-914`).
  - α/ratio too large → converges to convex hull (the safe over-estimate). `ratio=1.0` is exactly
    convex.
  - <3 distinct projected points / collinear / bad ratio (incl. NaN) / wrong shape → fail-loud
    ValueError (`floor_polygon.py:93-127`).
- **Sparse-mesh honesty**: keep the docstring caveat that sparse low-poly meshes undershoot
  ~10–20%; the jitter test must NOT hide this by using an over-dense cloud — use the existing
  0.25 m grid (realistic) + σ=0.02 m.
- **No magic params**: do NOT add auto-α or `floor_band_m`; both need GT to tune honestly.

---

## 6. STOP / DEFER RECOMMENDATION

**STOP on the algorithm — ⑥'s core is shipped (D82).** The concave/alpha-shape extractor, opt-in
wiring, guards, fallback, simplify, and non-tautological L-shape test already exist and are
green. Re-building any of it (especially the ADR §B Delaunay recipe) is duplicate work.

**DEFER the "accuracy" framing of ⑥ entirely to Phase 3 (data hunt).** No remaining ⑥ work can
be validated for accuracy without footprint GT, and validation ① proved that GT does not exist
in current datasets (whole-floor/whole-building laser, missing extrinsic, non-identifiable local
ICP). Building auto-α / `floor_band_m` now would be unvalidatable knob-tuning = exactly the fake-
precision trap the project forbids.

**OPTIONAL minimal ship (only if a Phase-2 code deliverable is required):** slices (1) CLI flag
+ (2) jitter robustness test, as a MINOR bump, explicitly framed as *reachability + robustness
hardening of an existing opt-in feature, NOT an accuracy gain*. This is honest, non-regressive
(default unchanged, zero golden drift), and dependency-free. Even so, it does not advance the
north-star (spatial-reasoning robustness needs GT, which is Phase 3's job) — so if forced to
choose, **proceed directly to Phase 3** and leave ⑥ as "core done, CLI/robustness polish
deferred."

---

## TRADE-OFFS

| Option | Pros | Cons |
|---|---|---|
| A. DEFER ⑥ entirely → Phase 3 | Honest (no GT to validate); zero risk; unblocks the real blocker (footprint validation needs data) | No Phase-2 code artifact; backlog item stays "core-done, polish-open" |
| B. Ship CLI flag + jitter test only | Additive, opt-in, zero golden drift, no deps; closes the genuine PR3 gap + ADR's missing noise gate; users can finally reach concave from CLI | Polishing an unvalidatable feature; MINOR bump for non-accuracy work; concave still not the default (so most users never hit it) |
| C. Flip default to concave | Recovers re-entrant corners for everyone; matches validation ①'s "convex over-estimates" finding | REGRESSION risk: cuboid golden drift (concave≠convex byte-equal), sparse undershoot ~10-20%, and no GT to justify it — REJECTED |
| D. Build auto-α / floor_band_m | Theoretically better noise handling | Unvalidatable magic params without GT; fake precision — REJECTED |

## REFERENCES
- `roomestim/reconstruct/floor_polygon.py:42-146` — shipped concave extractor (concave_hull ratio=0.4 + simplify + guards).
- `roomestim/adapters/mesh.py:213-250` — opt-in resolution (ctor>env>convex).
- `roomestim/adapters/mesh.py:281-298, 900-916` — convex byte-equal default + concave fallback+UserWarning.
- `tests/test_reconstruct_floor_polygon.py:19-114` — non-tautological L-shape tests (no jitter case → the gap).
- `tests/test_adapter_mesh.py:145-244, 729-747` — adapter concave round-trip + env + degeneracy fallback.
- `roomestim/cli.py:70-92, 200-260, 376-401` — ingest/run subparsers + `_get_adapter` (no `--floor-reconstruction` → the PR3 gap).
- `roomestim/adapters/polycam.py:20-39` — PolycamAdapter(MeshAdapter) already accepts floor_reconstruction.
- `docs/adr/0042-live-mesh-corner-extraction.md` — §A/§B/§I plan + §Status-update-v0.24.0 (records D82 landed PR1-equivalent, PR2/3/4 open).
- `.omc/plans/decisions.md:2354-2406` — D82 full record (concave opt-in shipped).
- `.omc/research/arkit-footprint-wall-laser-validation.md` — validation ① (0/5 footprint GT; localization unsolved → accuracy unvalidatable).
