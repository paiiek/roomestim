# Phase 4 — ⑦ Ambisonics layout (ADR 0041): dead enum + OQ-38 round-trip — DESIGN (READ-ONLY)

Target version: v0.32.0. Status: design pass (no edits made).
Verdict up front: **DO the OQ-38 round-trip slice (small, honest, additive). DEFER the
ambisonics placement producer (PR2-4) — engine-gated + product-peripheral + fake-completeness risk.**

## 1. Exact diagnosis

### 1a. The "dead enum"
- `roomestim/place/algorithm.py:19` — `TargetAlgorithm.AMBISONICS = "AMBISONICS"`.
- It is the ONLY enum member with **zero producers**. The other three each have a
  producer that stamps `target_algorithm=<X>.value`:
  - VBAP: `roomestim/place/vbap.py:122, 208`
  - DBAP: `roomestim/place/dbap.py:325`
  - WFS:  `roomestim/place/wfs.py:151`
  - AMBISONICS: none. No `roomestim/place/ambisonics.py` exists.
- It has **zero handlers**: `roomestim/place/dispatch.py:24-93` branches only
  vbap/dbap/wfs and raises `ValueError("unknown algorithm: ...")` at `:93`. CLI
  `choices=["vbap","dbap","wfs"]` at `roomestim/cli.py:119, 231` never exposes it.
- It is **silently lossy on read**: `roomestim/io/placement_yaml_reader.py:82-91`
  infers `target_algorithm` from `regularity_hint` + presence of `x_wfs_f_alias_hz`.
  An AMBISONICS (or DBAP) layout therefore reads back as `"VBAP"`. This collapse is
  codified as intended contract in
  `tests/test_layout_round_trip.py:149-167`
  (`test_dbap_target_algorithm_collapses_to_vbap`,
  `test_ambisonics_target_algorithm_collapses_to_vbap`).

So "dead" has two layers: (i) no algorithm *produces* an AMBISONICS layout; (ii) even
if one is hand-constructed, the label is *silently destroyed* on round-trip.

### 1b. OQ-38 round-trip gap
- OQ-38 (`.omc/plans/open-questions.md:524-535`, re-deferred to v0.20 at D61
  `:665-675`): the layout.yaml writer never persists `target_algorithm`; the reader
  re-infers it. `{DBAP, AMBISONICS}` have no discriminator → both collapse to `"VBAP"`.
- Writer side: `roomestim/export/layout_yaml.py:223-252` (`placement_to_dict`). It
  emits `x_wfs_f_alias_hz` only for WFS (`:238-244`) and `x_geometry_provenance` only
  when non-default (`:250-251`). There is **no `x_target_algorithm` key**.
- Reader side: `roomestim/io/placement_yaml_reader.py:82-91` — the inference block.
- The "round-trip" OQ-38 refers to = write→read→write fixed-point that preserves the
  *algorithm label* (positions already round-trip ≤1e-9 under D50; only the label is lost).

### 1c. Why the schema does not block this
- `spatial_engine/proto/geometry_schema.json:8` root `additionalProperties: true`
  (confirmed) → a new `x_target_algorithm` extension key validates with **no schema
  change** (identical mechanism to the existing `x_wfs_f_alias_hz` / `x_geometry_provenance`).
- `regularity_hint` enum (`geometry_schema.json:20`) = `LINEAR/CIRCULAR/PLANAR_GRID/IRREGULAR`
  — no AMBISONICS value. The algorithm label rides in `x_target_algorithm`, NOT in
  `regularity_hint`. So OQ-38 closure needs no schema work.

## 2. Recommended minimal honest change (the ONLY thing to ship in Phase 4)

Close OQ-38 with the `x_target_algorithm` extension key (ADR 0041 PR1). This makes the
AMBISONICS *label* live (faithfully round-trips instead of silently collapsing) WITHOUT
adding an unverifiable placement producer.

Touch-list (additive, ~25 LOC + tests):

1. `roomestim/export/layout_yaml.py` — in `placement_to_dict` (~after `:244`, alongside
   the existing extension-key block) emit `out["x_target_algorithm"] = result.target_algorithm`
   **only for non-VBAP algorithms** (DBAP / WFS / AMBISONICS). Recommended over
   emit-for-all because it (a) keeps the single existing golden byte-equal — zero churn,
   (b) matches the established "emit only when non-default" pattern of
   `x_wfs_f_alias_hz` and `x_geometry_provenance`. VBAP is the reader's natural default.

2. `roomestim/io/placement_yaml_reader.py` — replace the inference block (`:82-91`) with
   "restore-first, infer-fallback":
   ```
   if "x_target_algorithm" in data:
       target_algorithm = str(data["x_target_algorithm"])   # validate vs known set, raise ValueError on unknown
       wfs_f_alias_hz = float(data["x_wfs_f_alias_hz"]) if "x_wfs_f_alias_hz" in data else None
   else:
       # existing inference, unchanged — backward-compat with pre-v0.32 layouts
   ```
   Validate the restored label against `{VBAP,DBAP,WFS,AMBISONICS}` and raise `ValueError`
   on an out-of-enum value (mirror the `_parse_provenance` guardrail). Keep it inside the
   existing try/except to honor the documented `ValueError` contract.

3. `tests/test_layout_round_trip.py:149-167` — **invert** the two collapse tests to expect
   label preservation (`assert r2.target_algorithm == "DBAP"` / `== "AMBISONICS"`), and
   update the module docstring (`:4`) that currently describes collapse as the contract.
   Add: (a) a WFS round-trip test confirming WFS still restores (now via the key), (b) a
   backward-compat test that a key-less layout (e.g. the existing golden) still reads as VBAP,
   (c) a write→read→write fixed-point assertion for an AMBISONICS-labelled result.

4. Docs/decisions: mark OQ-38 CLOSED in `.omc/plans/open-questions.md`; add a decisions.md
   entry; update ADR 0041 §OQ status and ADR 0036 §OQ-38 cross-ref. Note in ADR 0041 that
   only PR1 shipped; PR2-4 (the placement producer) remain DEFERRED (see §5).

## 3. Gate impact
- **Golden**: zero churn with the non-VBAP-only choice (the lone golden
  `tests/fixtures/golden/place_vbap_ring_n8_default.yaml` is VBAP → no key added).
  (If emit-for-all were chosen instead, that one file would need `x_target_algorithm: VBAP`
  appended and regenerated — recommend against, for zero blast radius.)
- **New tests**: 2 inverted + ~3 added (see 2.3). All run without external data.
- **Schema**: no change (`additionalProperties: true`). No new dependency.
- **Version**: minor bump v0.31.0 → **v0.32.0** (purely additive; reader stays
  backward-compatible with old key-less layouts).
- **ruff/mypy(strict)**: trivial; keep the str-label validation explicit.
- Run full gate (default + web + ruff + mypy + smoke) per project policy.

## 4. Honesty guardrails — what NOT to claim
- After PR1, do **NOT** say "roomestim supports Ambisonics." It supports the AMBISONICS
  **label round-trip** only. There is still no algorithm that *produces* an ambisonics rig.
  README/docs must keep "Ambisonics placement deferred" (it is engine-gated, see §5).
- The enum member stays declared-but-unproduced **on purpose** — that is the honest state
  (roomestim genuinely does not place ambisonics rigs). Retain-and-round-trip is preferred
  over deleting the member, because deletion contradicts ADR 0003 forward-compat, ADR 0041,
  and the (now-inverted) round-trip tests.
- If PR2 is ever done: canonical positions MUST be principled, not arbitrary —
  **spherical t-design** points (exact SH integration to degree t, choose t ≥ 2N for order N)
  with a **platonic-solid-vertex** fallback for low orders (order1 = octahedron(6)/cube(8),
  order2 = icosahedron(12), order3 = dodecahedron(20)). Constraint n_speakers ≥ (N+1)².
  Do **NOT** reuse `place_vbap_dome` (`vbap.py:129-212`) — it is two stacked equal-angle
  rings, leaves poles empty, and breaks SH orthogonality / decoder conditioning.

## 5. STOP / DEFER recommendation (the ambisonics PRODUCER balloons)

DEFER ADR 0041 PR2-4 (`place/ambisonics.py` producer + dispatch branch + CLI `--order`).
Reasons it is NOT a self-contained additive change:
1. **Unresolved external dependency (ADR 0041 §D-3a, the ADR's own pre-implementation gate):**
   `regularity_hint=IRREGULAR` alone cannot tell the engine an ambisonics rig from a generic
   irregular layout. End-to-end routing (engine reading `x_target_algorithm=="AMBISONICS"` and
   sending it to the SH decoder, `ipc_schema.md:21-22` `/sys/ambi_order`) is **unconfirmed**.
   This requires engine-team agreement — not a roomestim-internal, data-free change.
2. **Precondition unmet:** `spatial_engine/require.md` has not promoted Ambisonics to
   mandatory (ADR 0003 gated the build on exactly that; ADR 0041 §Pre-conditions confirms
   still unmet). ADR 0041 itself gates PR2+ on require.md update or engine agreement.
3. **North-star peripheral:** the product north star is spatial-inference robustness;
   ambisonics rig geometry is product-peripheral (backlog item, explicitly "last").
4. **Fake-completeness trap (directly answers Q4):** emitting a rig labelled AMBISONICS while
   no decoder consumes it would manufacture an acoustically-meaningful *claim* that is
   verifiable only inside roomestim (rig symmetry/conditioning) but **never end-to-end**.
   Shipping that to satisfy the enum is exactly the fake-completeness failure mode — avoid it.

PR1 (OQ-38) is independently valuable (closes a real silent-data-loss defect, cadence
overdue per D26), carries no external dependency, and is fully testable offline — so ship
PR1 as Phase 4, and record PR2-4 as DEFERRED with the §D-3a engine gate as the trigger.

## References
- `roomestim/place/algorithm.py:19` — dead AMBISONICS enum member.
- `roomestim/place/dispatch.py:24-93` — handler set (no ambisonics; raises at :93).
- `roomestim/place/{vbap.py:122,208, dbap.py:325, wfs.py:151}` — the 3 producers (no ambisonics).
- `roomestim/cli.py:119, 231` — place/run choices exclude ambisonics.
- `roomestim/export/layout_yaml.py:223-252` — writer; extension-key emit site (no x_target_algorithm).
- `roomestim/io/placement_yaml_reader.py:82-91` — inference block (collapse to VBAP).
- `roomestim/model.py:364-379` — PlacementResult (target_algorithm: str).
- `tests/test_layout_round_trip.py:149-167` — collapse contract tests to invert.
- `tests/fixtures/golden/place_vbap_ring_n8_default.yaml` — sole golden (VBAP → zero churn).
- `spatial_engine/proto/geometry_schema.json:8,20` — root additionalProperties:true; regularity enum.
- `docs/adr/0041-ambisonics-placement-design.md` — PR split, §D-3a engine gate, §Pre-conditions.
- `.omc/plans/open-questions.md:524-535, 665-675` — OQ-38 + D61 reverse condition.
