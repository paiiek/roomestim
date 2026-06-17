# CAND-3 — Ambisonics rig placement (ADR 0041 PR2+PR3) — IMPLEMENTATION PLAN

**VERDICT: BUILD — experimental, opt-in, honestly-disclosed coordinate-generation slice.**
PR2 (platonic rig geometry) + PR3 (dispatch/CLI wiring) are shippable under ADR 0041 §D-3a
point 2's explicit carve-out ("합의 전에는 … roomestim 측 좌표 생성에 한정되며, end-to-end
디코딩 경로는 미확정임을 명시"). PR4 (t-design) stays DEFER. This mirrors how the `image`
backend shipped experimental with load-bearing honest labels.

**Status of inputs (verified 2026-06-17):**
- PR1 (`x_target_algorithm` round-trip) is INTACT — writer `layout_yaml.py:254-255` emits
  for non-VBAP, reader `placement_yaml_reader.py:99-106` restore-first + enum-validates,
  AMBISONICS round-trip test `tests/test_layout_round_trip.py:167` present. **Do NOT touch.**
- scipy>=1.10 already a core dep; the IMPLEMENTATION needs only **numpy** (closed-form coords).
  The verification proxy is also **numpy-only** (second-moment / spherical-2-design test) — see
  Risk-2: scipy renamed `sph_harm`→`sph_harm_y` in 1.15+, so SH-matrix `np.linalg.cond` via
  `scipy.special` is version-fragile; the numpy second-moment proxy is equivalent for these
  symmetric rigs and avoids the coupling. **New-dep count = 0.**

---

## 1. Why the §D-3a carve-out legitimately applies (gate-respecting)

D-3a has TWO points. Point 1 (engine identifies/ routes the rig to the SH decoder) is the
END-TO-END gate and remains UNMET (require.md still 0 `ambison` hits per the 2026-06-12
Status-update; no engine-team agreement). Point 2 EXPLICITLY permits roomestim-side rig
**coordinate generation** to proceed as long as the end-to-end decoding uncertainty is
disclosed. We ship ONLY coordinate generation (pure, closed-form, exactly verifiable math)
and make the "decoding/routing is engine-gated and UNCONFIRMED" statement load-bearing:
CLI stderr NOTE on every ambisonics run + single-source-of-truth constant + README + ADR.
No fake capability is claimed: roomestim emits rig COORDINATES; it does NOT decode, does NOT
encode SH, does NOT assert the engine will consume them.

This is honest because the disclosure is accurate and unavoidable at the user surface, and the
math is the kind that is verifiable WITHOUT the engine (angle error vs reference, symmetry,
isotropy). The fake-completeness trap §D-3a warns about is "emit a rig and imply end-to-end
ambisonics works"; we do the opposite — emit a rig and state end-to-end is unconfirmed.

---

## 2. Closed-form platonic vertex sets (NO external table) — numerically verified

φ = (1+√5)/2. All vertices below are normalized to the unit sphere, then scaled by `radius_m`.
Verified (miniforge scipy 1.17 / numpy): equal radii, centroid == origin exactly, second-moment
matrix M = (1/n)·VᵀV == (1/3)·I (isotropy cond = 1.000000; max|M−I/3| ≤ 5.6e-17).

- **order 1 → octahedron, n=6** (n ≥ (1+1)²=4 ✓):
  `(±1,0,0), (0,±1,0), (0,0,±1)` (already unit).
  (Cube-8 is a documented future alternative for order 1; v1 ships octahedron-6 only — keeps
  n deterministic and sidesteps the n_speakers-inference OQ; see Scope.)
- **order 2 → icosahedron, n=12** (n ≥ 9 ✓): all even permutations / sign combos of
  `(0, ±1, ±φ)` → `(0,±1,±φ), (±1,±φ,0), (±φ,0,±1)`; divide each by √(1+φ²).
- **order 3 → dodecahedron, n=20** (n ≥ 16 ✓): the 8 cube vertices `(±1,±1,±1)` PLUS
  `(0, ±1/φ, ±φ), (±1/φ, ±φ, 0), (±φ, 0, ±1/φ)`; all 20 have norm √3 → divide by √3.

These unit vectors are the rig directions in listener-frame `(x=right, y=up, z=front)`; multiply
by `radius_m` to get `Point3` positions. Aim = toward origin (reuse `vbap._unit_aim_to_listener`).

---

## 3. Files to add / modify (with anchors)

**Touched: 11 files (2 new code, 1 new test, 1 new golden, 7 modified). New deps: 0.**

### NEW `roomestim/place/ambisonics.py`
- Module docstring states: geometry-only rig producer; SH decode/route = engine; experimental.
- `AMBISONICS_RIG_DISCLOSURE: str` — **single source of truth NOTE constant** (mirrors
  `POLYGON_ISM_GEOMETRY_NOTE` in `reconstruct/_disclosure.py:93`, exported + "reference, do not
  retype"). Exact wording in §4.
- `_PLATONIC_BY_ORDER: dict[int, tuple[str, list[tuple[float,float,float]]]]` — closed-form unit
  vertices per §2 (computed at import via numpy, or written as literals; literals preferred for
  golden-stability/determinism).
- `place_ambisonics(order: int, *, radius_m: float = 2.0, layout_name: str = "ambisonics_rig") ->
  PlacementResult`:
  - validate `order in {1,2,3}` else `ValueError` (kErrTooFewSpeakers-style message).
  - build `PlacedSpeaker(channel=i+1, position=Point3(radius*vx,vy,vz),
    aim_direction=_unit_aim_to_listener(position))`.
  - return `PlacementResult(target_algorithm=TargetAlgorithm.AMBISONICS.value,
    regularity_hint="IRREGULAR", speakers=..., layout_name=...)` (D-4: IRREGULAR → R10 min 1 ✓).
- `__all__ = ["place_ambisonics", "AMBISONICS_RIG_DISCLOSURE"]`.

### `roomestim/place/__init__.py`
- import + export `place_ambisonics` (current exports at lines 5-16).

### `roomestim/place/dispatch.py`  (`run_placement`, 14-101)
- add kwarg `order: int | None = None` to `run_placement` signature (line 14-22).
- add branch BEFORE the final raise (after the `wfs` block, ~line 100):
  `if algorithm == "ambisonics":` → require `order is not None` (else ValueError telling the
  user to pass `--order`), then `from roomestim.place.ambisonics import place_ambisonics;
  return place_ambisonics(order, radius_m=layout_radius_m)`.
- extend the module/func docstring's "geometry-blind" note: ambisonics is geometry-blind like
  vbap (room arg unused; rig is a fixed regular solid), AND end-to-end decode is engine-gated.

### `roomestim/cli.py`
- `_add_place_parser` (120): `--algorithm` choices (125) += `"ambisonics"`; add `--order`
  (`type=int, choices=[1,2,3], default=None`, help: "Ambisonics decode order (1|2|3); required
  for --algorithm ambisonics. order→rig: 1=octahedron(6), 2=icosahedron(12), 3=dodecahedron(20).").
- `_add_run_parser` (236): same two edits (choices line 248; add `--order`).
- `_run_placement` (537-557): add `order: int | None = None` param; pass `order=order` into
  `run_placement` (549-552).
- `_cmd_place` (587-614) and `_cmd_run` (~744): pass `order=getattr(args,"order",None)`; when
  `args.algorithm == "ambisonics"`: (a) if `args.el_deg` was explicitly set / non-default OR
  `args.n_speakers != 8` default → `print("WARNING: --el-deg/--n-speakers are ignored for "
  "ambisonics; rig geometry is fixed by --order.", file=sys.stderr)` (warn, NOT silent — D-5);
  (b) ALWAYS `print(f"NOTE: {AMBISONICS_RIG_DISCLOSURE}", file=sys.stderr)` (mirror the
  `AUTO_FLOOR_RECON_NOTE` print at cli.py:448).

### NEW `tests/test_ambisonics_placement.py` — see §5.
### NEW `tests/fixtures/golden/place_ambisonics_order1_octa.yaml` — see §5.
### `roomestim/__init__.py:3` + `pyproject.toml:7` — version `0.38.0` → `0.39.0`.
### `README.md` — changelog row (§6) + algorithm-list mention (the v0.38.0 note at ~line 245
references `--algorithm`; add ambisonics as experimental there).
### `docs/adr/0041-ambisonics-placement-design.md` — append `## Status-update (2026-06-17,
CAND-3 — PR2+PR3 SHIPPED experimental)`; update top `Status:` line (§6).
### `.omc/plans/decisions.md` — new **D104** entry (latest is D103).

---

## 4. Disclosure mechanism + exact wording (single source of truth)

Constant `AMBISONICS_RIG_DISCLOSURE` in `roomestim/place/ambisonics.py` (exported; "reference,
do not retype" — same pattern as `POLYGON_ISM_GEOMETRY_NOTE`). Surfaces: CLI stderr (place+run),
README changelog cell, ADR Status-update. Proposed wording:

> "Ambisonics placement emits the physical coordinates of a regular (platonic) speaker RIG ONLY.
> roomestim does NOT perform SH encoding or decoding, does NOT compute the decode matrix, and
> does NOT select a decoder type — those are the engine's responsibility (/sys/ambi_order,
> /sys/ambi_decoder_type). EXPERIMENTAL: the engine-side contract that routes this rig to the
> Ambisonics decoder is UNCONFIRMED (ADR 0041 §D-3a point 1 gate is unmet — require.md does not
> mandate Ambisonics and there is no engine-team routing agreement). The rig is emitted as
> regularity_hint=IRREGULAR; an engine that branches IRREGULAR to VBAP-weighting would render
> these coordinates with the WRONG algorithm. End-to-end Ambisonics decoding is therefore NOT
> verified by roomestim. The COORDINATES themselves are exact closed-form platonic vertices."

---

## 5. Test plan (ADR §검증 strategy) + golden

`tests/test_ambisonics_placement.py` (default-suite, no web/torch; numpy-only):
1. **Angle precision ≤5°**: for each order, recompute expected unit vertices from the closed-form
   formulas independently and assert max angular error between produced rig directions and the
   reference set (after best-match pairing) ≤ 5° (will be ~0; assert < 1e-6 rad → also ≤5°).
2. **Symmetry**: all `dist_m` equal within tol (1e-9); centroid of unit directions ≈ origin
   (atol 1e-9). (Verified: octa/ico/dode all pass exactly.)
3. **Quasi-isotropy / decoder-stability PROXY (numpy-only)**: second-moment matrix
   `M = VᵀV / n` of the unit directions equals `(1/3)·I` within tol → `np.linalg.cond(M)` ≈ 1.0
   (assert < 1.01). DOCUMENT in-test that this is a spherical-2-design isotropy proxy for decoder
   stability, NOT a scipy SH-matrix condition number (scipy `sph_harm`→`sph_harm_y` rename in
   1.15+ makes the SH path version-fragile; the proxy is exact for these symmetric rigs).
4. **n_speakers ≥ (N+1)²**: assert 6≥4, 12≥9, 20≥16 per order.
5. **Round-trip label preservation**: `write_layout_yaml` → `read_placement_yaml` →
   `target_algorithm == "AMBISONICS"` preserved; and write→read→write D50 fixed-point
   (positions stable ≤1e-9). (Leverages PR1 `x_target_algorithm`.)
6. **R10/R11 pre-flight**: `write_layout_yaml` succeeds for each order with `validate=False`
   (no engine schema in CI) — IRREGULAR min=1 passes; finite-sweep passes.
7. **Errors**: `order=0/4` → ValueError; dispatch `algorithm="ambisonics", order=None` →
   ValueError naming `--order`.
8. **CLI warn**: `--algorithm ambisonics --el-deg 30` emits the WARNING; every ambisonics run
   emits the NOTE (capture stderr).
- **Golden**: `tests/fixtures/golden/place_ambisonics_order1_octa.yaml` from
  `place_ambisonics(1, radius_m=2.0)` written with `validate=False` (header-free path is
  validate=True; use the env-schema-independent golden via `placement_to_dict`+dump OR commit
  the validate=False output and assert byte-equal). Confirms `x_target_algorithm: AMBISONICS`,
  `regularity_hint: IRREGULAR`, 6 speakers, D56 9-dp rounding.

Gate suite (per canonical env, MEMORY [[reference_canonical_test_env]]):
`/home/seung/miniforge3/bin/python -m pytest` default + web + `ruff` + `mypy --strict` + smoke.
New baseline expected ≈ 611p + (new tests) / 7s.

---

## 6. Version + docs + ADR + decisions

- **v0.39.0** (MINOR — new experimental, opt-in capability; existing `--algorithm vbap|dbap|wfs`
  byte-equal unchanged; VBAP golden untouched).
- **README changelog row** (insert above v0.38.0 at line 142): "ambisonics 배치 알고리즘
  (MINOR, additive, EXPERIMENTAL) — 신규 `place/ambisonics.py` `place_ambisonics(order)`: platonic
  closed-form 리그(1=octahedron6/2=icosahedron12/3=dodecahedron20, n≥(N+1)²), numpy-only, **신규
  의존 0**. `--algorithm ambisonics --order {1,2,3}` (place/run). **정직 고지(load-bearing
  `AMBISONICS_RIG_DISCLOSURE`): roomestim 은 리그 좌표만 방출 — SH 인코딩/디코딩·decoder 선택은
  engine 책임이며 end-to-end 라우팅 계약(ADR 0041 §D-3a point 1)은 미확정/UNCONFIRMED.** PR4
  t-design DEFER. (D104 / [ADR 0041](docs/adr/0041-ambisonics-placement-design.md))."
- **ADR 0041**: flip top `Status:` PR2-3 from DEFERRED→SHIPPED-experimental; append
  `## Status-update (2026-06-17, CAND-3)`: record §D-3a-point-2 justification, octa-6 choice for
  order 1, IRREGULAR mapping, numpy-only isotropy proxy substitution for the SH cond number,
  PR4 still DEFER, and that point-1 end-to-end gate remains the trigger for removing
  "experimental".
- **decisions.md D104**: "Ambisonics rig coordinate generation SHIPPED experimental under ADR
  0041 §D-3a point-2 carve-out; engine routing (point 1) unmet → load-bearing UNCONFIRMED
  disclosure; PR4 t-design DEFER." Reference D102 (PR1).

---

## 7. Scope boundary — explicitly NOT done (and how disclosed)

- **PR4 t-design**: NOT done — external coordinate table + license/source = new OQ. Disclosed in
  ADR Status-update + README ("PR4 t-design DEFER"). order 3 ships dodecahedron-20 (closed-form);
  t-design would only raise order-3 decoder quality, not required for the experimental slice.
- **Engine routing agreement (§D-3a point 1)**: NOT obtained — this is the END-TO-END gate;
  disclosed as load-bearing UNCONFIRMED in `AMBISONICS_RIG_DISCLOSURE` (CLI/README/ADR).
- **SH encode/decode, decoder-type selection, audio render**: NOT done (engine責任 per §Scope);
  disclosed in the NOTE.
- **n_speakers inference / non-standard-n rounding**: NOT done — order fully determines the rig
  (octa-6/ico-12/dode-20); `--n-speakers` warned+ignored for ambisonics. The n-inference OQ
  stays DEFER (kept out of scope deliberately → tighter, no new OQ opened).
- **cube-8 alt for order 1**: NOT shipped (documented future option).

---

## 8. Risks + reverse-criterion

- **Risk 1 (biggest): engine routes IRREGULAR → VBAP-weighting**, rendering the rig with the
  wrong algorithm end-to-end. Mitigation: load-bearing UNCONFIRMED disclosure + EXPERIMENTAL
  label; we claim only coordinate correctness, never end-to-end decode. This is exactly the
  §D-3a-point-2 boundary.
- **Risk 2: scipy SH API churn** (`sph_harm`→`sph_harm_y`, scipy 1.15+). Mitigation: use the
  numpy-only second-moment isotropy proxy (verified equivalent for these rigs); zero scipy
  coupling, zero new deps.
- **Risk 3: golden byte-stability** under D56 rounding / schema-env dependence. Mitigation: golden
  produced via the validate=False path (env-schema-independent), 9-dp normalized; VBAP golden
  untouched (ambisonics never emits when algorithm!=ambisonics).
- **Risk 4: user mis-expectation** ("Ambisonics support" = SH output). Mitigation: NOTE explicitly
  says rig-coordinates-only and decode=engine.

**Reverse-criterion (already in ADR 0041, applies as-is):**
- (a) if engine confirmed NOT to consume `x_target_algorithm`/`x_ambisonics_order` → keep rig
  coords, drop the extension-key reliance.
- (b) if engine/require.md demands SH channels not a rig → revisit option (b) + schema
  negotiation (current `geometry_schema.json` requires positions → blocks (b)).
- (c) if ±2-5° precision unmet by platonic → promote t-design (PR4). (Not triggered: platonic
  error is ~0.)
- **Promotion trigger to remove "experimental":** require.md promotes Ambisonics to mandatory
  OR engine-team agreement that `x_target_algorithm=="AMBISONICS"` routes to the SH decoder
  (§D-3a point 1).

---

## 9. Execution order (for executor)
1. `place/ambisonics.py` (constant + producer) → `place/__init__.py` export.
2. `dispatch.py` branch + `order` kwarg.
3. `cli.py` choices/`--order`/warn/NOTE in place+run + `_run_placement` plumbing.
4. Tests + golden.
5. Version bump + README + ADR Status-update + decisions D104.
6. Full gate suite (default+web+ruff+mypy+smoke); then code-review + verifier (separate passes).

RESUME POINTER: this file. Update per phase.
