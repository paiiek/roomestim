# Commercialization Follow-ups — 4 Candidates Implementation Plan (A/B/C/D)

**Created:** 2026-06-08 (planner)
**Baseline at planning time:** v0.29.0 — canonical default gate
`/home/seung/miniforge3/bin/python -m pytest -m "not web and not vision and not lab and not e2e"`
→ **414 passed, 3 skipped**; web `-m web` → 86p/3s; `ruff check` + `mypy roomestim` (--strict) EXIT 0.
Use `/home/seung/miniforge3/bin/python`, NOT PATH pytest.
**Resume truth source:** `.omc/plans/commercialization-analysis.md` (RESUME POINTER, bottom).
**Governing discipline — 가짜 숫자 금지 (NO fake numbers):** every accuracy/acoustic claim must
be empirically backed in-gate; anything unverifiable is honestly DEFERRED or scoped to its
buildable+verifiable core, never faked. New disclosure strings go in
`roomestim/reconstruct/_disclosure.py` (single source of truth), never inline-retyped.
**Decision numbering:** last committed = D97 (`c2766ad`). This cycle = **D98 (A), D99 (B),
D100 (C), D101 (D)**.

> RESUME POINTER (updated 2026-06-08): **A DONE** (`d3457c5` v0.30.0 D98), **B DONE** (`3a02d7e`
> v0.30.1 D99), **D DONE** (doc-only DEFER, ADR 0045 §honesty (D)). **C = NOT STARTED** (next).
> Session-limit hit during B's review → B committed on rigorous self-verification (independent
> code-review DEFERRED to next session). **NEXT SESSION = build C geometry-only** then run B's
> independent review.
>
> **C resume spec (geometry-only polygon image-source, NO RT60):**
> - NEW `roomestim/reconstruct/polygon_image_source.py` — numpy/shapely-only (NO pyroomacoustics
>   import; must run default lane). Deterministic function: given floor_polygon + ceiling_height,
>   enumerate first-order (optionally low-order) image-source POSITIONS by mirroring the source
>   across each wall plane, with a shapely visibility/validity test (reuse the
>   `roomestim_web/binaural.py:70` `_image_inside_floor` shapely-contains pattern, but keep this
>   module CORE). Emit POSITIONS ONLY — NO RT60, do NOT import/modify `predictor.py` or
>   `image_source.py`.
> - NEW `tests/test_polygon_image_source.py` — for a known shoebox-as-4-corner-polygon, assert
>   first-order image positions == analytic mirror positions (reflect across x=0,x=L,z=0,z=W) to
>   ~1e-9; add an L-shape (non-convex) fixture asserting visibility prunes images whose reflection
>   point falls outside the polygon. Default lane, additive.
> - `docs/adr/0040-polygon-ism-design.md` §Status-update: geometry-only landed; **RT60 cascade
>   DEFERRED** (no non-shoebox measured GT §G/OQ#2; pra RT60-fit unverified OQ#3; pyroomacoustics
>   web-extra reproducibility asymmetry). predictor/image_source byte-equal, shoebox RT60 unchanged.
> - Version: MINOR → 0.31.0, D100. Full gate (default 418+, web 86p/3s, ruff/mypy EXIT0) + no
>   pyroomacoustics import in core.
> Each candidate is a separate commit. After each: re-run the FULL canonical gate
> (default + web + ruff + mypy), not just the new tests (per auto-memory `feedback_verify_each_step`).

---

## Verdict summary (read this first)

| # | Candidate | Honesty verdict | Buildable core (one line) | Version bump | Order |
|---|---|---|---|---|---|
| **A** | spatial_engine path decouple + PyPI-ready packaging | **BUILD** (low-risk, fully verifiable) | Remove machine-specific hardcoded default → bundled/None fail-loud; prove clean wheel build + console-script in isolated env; flip ADR 0007 to PyPI-ready | **MINOR** 0.29.0→0.30.0 (new pip-install capability) — but schema-resolution change is behavior-preserving where env/CLI set | **1st** |
| **B** | multi-room | **SCOPE DOWN** — bounded honest slice only; full RoomCollection = DEFER | Stop the *silent* `floor_entries[0]` data loss: detect >1 floor entry, fail-loud or merge-with-disclosure; do NOT fake a multi-room container | **PATCH** 0.30.0→0.30.1 (robustness/honesty fix, no model change) | **2nd** |
| **C** | polygon-ISM acoustics (ADR 0040) | **SCOPE DOWN to geometry-only OR DEFER** — full RT60 cascade is a fake-number trap this cycle | Deterministic numpy-only polygon image-source POSITION enumerator + visibility, verified against analytic shoebox positions, emitting NO acoustic number | **MINOR** (additive sibling module, no predictor wiring) IF built; else doc-only DEFER | **3rd** |
| **D** | cam_h known-size-reference prior | **DEFER** (be skeptical) — only honest slice duplicates existing `--cam-height` with extra UX burden + zero accuracy gain; auto-detection is unverifiable | (optional, not recommended) a manual user-supplied known-object-height anchor that solves cam_h deterministically, labelled ASSUMED | **doc-only** ADR 0045 note (DEFER); MINOR only if user insists on the manual anchor | **4th** |

**Net recommendation:** ship **A** (clean win), ship **B's bounded slice** (kills a real silent
bug), build **C geometry-only** *or* defer it (NOT the RT60 cascade), **defer D** with an ADR note.
Zero unbacked accuracy/acoustic numbers introduced in any path.

---

## Cross-cutting honesty rule (applies to all four)

`provenance` (`model.py:336`), `ceiling_confidence`/`ceiling_coverage` (`model.py:341-346`), and
the `_disclosure.py` strings exist precisely to keep unverified output from masquerading as
measured. Every new code path MUST set the least-claim label and MUST NOT introduce a number
presented as an accuracy/acoustic figure unless an empirical in-gate fixture backs it. C and D are
where the trap lives — see their risk sections.

---

## Candidate (A) — spatial_engine absolute-path decouple + PyPI-ready packaging  ★ DO FIRST

### Why first
Lowest risk, clearest in-gate verification, removes a happy-path failure on every machine that is
not this one. No accuracy/acoustic surface area → no fake-number exposure at all.

### Current state (file:line) — already PARTLY done
- `roomestim/export/layout_yaml.py:58-60` — `_DEFAULT_ENGINE_SCHEMA_PATH =
  Path("/home/seung/mmhoa/spatial_engine/proto/geometry_schema.json")` — the **machine-specific
  hardcoded default**. This is the SWOT `layout_yaml.py:58` finding.
- `layout_yaml.py:63-77` `_engine_schema_path()` — precedence **already implemented**:
  `SPATIAL_ENGINE_REPO_DIR` env var → falls back to the hardcoded default.
- `layout_yaml.py:80-98` `_assert_schema_file_exists()` — **already** raises a descriptive
  `FileNotFoundError` naming `SPATIAL_ENGINE_REPO_DIR`, `--validate-engine`, `--no-engine-validation`
  (OQ-42, v0.20.0). So a missing schema already fails loud with escape hatches.
- `layout_yaml.py:108-127` `_resolve_schema_file()` — CLI `--validate-engine <dir>` override path.
- `roomestim/cli.py:177-200` — `--validate-engine` / `--no-engine-validation` engine group (ADR 0033).
- `pyproject.toml:1-78` — packaging is **mostly there**: `[build-system]` (setuptools+wheel),
  `[project]` (name/version/deps), `[project.scripts] roomestim = "roomestim.cli:main"`,
  `[tool.setuptools.packages.find]` (include `roomestim*`, exclude `tests*`),
  `[tool.setuptools.package-data]` (proto/*.json + HorizonNet LICENSE/NOTICE).
- `docs/adr/0007-distribution-model.md` — distribution **DEFERRED** (standalone, not PyPI).

### Key insight (de-risks scope)
The env-var + CLI + fail-loud machinery already exists. The ONLY genuinely broken thing is the
**hardcoded absolute default** at `layout_yaml.py:58-60` — it makes "schema validation with no env
and no CLI flag" silently succeed only on this one machine and is dead/misleading everywhere else.
"PyPI-ready" does NOT mean publishing to PyPI (ADR 0007 reverse-criteria for that have not fired);
it means the wheel **builds and installs cleanly in an isolated env and the console script runs** —
i.e. machine-independence + packaging hygiene, not a registry upload.

### Buildable + verifiable core (honest)
1. **Neutralize the machine-specific default** (`layout_yaml.py:58-77`). Replace the hardcoded
   absolute path with a non-machine-specific resolution. Options, in honesty/robustness order:
   (a) **fail-loud sentinel** — when neither `SPATIAL_ENGINE_REPO_DIR` nor `--validate-engine` is
   set, `_engine_schema_path()` returns no usable default and the existing
   `_assert_schema_file_exists` message fires (engine validation is opt-in anyway via ADR 0033 —
   `--no-engine-validation` skips it cleanly); OR (b) a documented relative/bundled fallback IF a
   copy of `geometry_schema.json` is legitimately vendorable (note: docstring line 3 says the schema
   is "read at write time, never copied" — so do NOT vendor it; prefer (a)). **Decision in-plan: (a)
   fail-loud** — it preserves the "never vendor the engine schema" contract and removes the only
   machine-specific line. The precedence chain `CLI > ENV > (now: explicit-only)` stays per ADR 0033.
2. **Behavior preservation where it matters.** When `SPATIAL_ENGINE_REPO_DIR` or `--validate-engine`
   IS set and points at a real schema, output must be **byte-equal** to today (existing tests cover
   this). The only behavior change is: "no env + no flag + engine validation requested" now fails
   loud instead of silently reading this machine's path. That is a *bug fix*, not a regression.
3. **Packaging readiness proof.** In an isolated venv, `python -m build` (or `pip wheel .`) →
   `pip install` the wheel → `roomestim --help` console script runs → `import roomestim` is
   torch-free (core/web boundary, per pyproject vision-extra comment). Capture as a smoke check.
   Confirm `package-data` ships `proto/*.json` so a pip-installed copy can self-validate its OWN
   room schema (distinct from the engine schema, which stays external).
4. **ADR 0007 status update.** Flip from "DEFERRED (standalone)" to a §Status-update recording
   "machine-specific path removed; wheel builds + installs + console-script verified in isolated
   env; PyPI **publish** still deferred (reverse-criteria unchanged) but packaging is now
   PyPI-*ready*." Do not claim a publish that did not happen.

### Honestly deferred (with reason)
- **Actual PyPI publish / name claim.** ADR 0007 reverse-criteria (external `pip install roomestim`
  request; submodule-vs-PyPI decision) have NOT fired. Stay packaging-ready, do not upload.
- **room.yaml schema freeze (0.2-draft → 0.2).** Separate concern (ADR 0004); not in A's scope.

### Verification strategy
- **In-gate (default lane):** existing `tests/test_export_layout_yaml.py` (engine-schema resolution
  tests) must stay GREEN with env/CLI set; add a test asserting the no-env/no-flag path now raises
  the descriptive `FileNotFoundError` (naming the three escape hatches) instead of touching any
  absolute path. Assert byte-equal layout.yaml output when the schema is resolvable.
- **Packaging smoke (out-of-gate, scripted):** isolated-venv `build` + `pip install` + `roomestim
  --help` + torch-free `import roomestim`. Report as evidence; not a default-lane test (it shells
  out / builds). Can live under a `scripts/` smoke or be run manually and recorded in the commit.
- **What CANNOT be claimed:** that roomestim is "on PyPI" or "published." Only "wheel builds +
  installs cleanly + machine-independent."
- **Gate markers:** default lane unchanged baseline + new resolution test. web 86p/3s, ruff/mypy EXIT0.

### Risk / honesty (fake-number trap?)
None — A touches path resolution + packaging, no accuracy/acoustic numbers. The only honesty point
is the ADR wording: say "PyPI-ready," not "published."

### Files to touch
`roomestim/export/layout_yaml.py` (neutralize default), `tests/test_export_layout_yaml.py` (no-env
fail-loud test + byte-equal assertion), `docs/adr/0007-distribution-model.md` (§Status-update),
optional `scripts/packaging_smoke.sh` (isolated build+install+console-script), optional
`pyproject.toml` (only if a packaging gap surfaces during the smoke — e.g. missing package-data).

### Acceptance criteria
- [ ] No machine-specific absolute path remains in `roomestim/` (grep `"/home/"` in package = 0).
- [ ] Engine-schema resolution byte-equal when env/CLI set; no-env/no-flag path fails loud with the
      three escape hatches.
- [ ] Isolated-venv wheel build + `pip install` + `roomestim --help` succeed; `import roomestim` torch-free.
- [ ] ADR 0007 §Status-update: PyPI-ready (NOT published); reverse-criteria unchanged.
- [ ] Full gate GREEN: default 414+ (+resolution test), web 86p/3s, ruff/mypy EXIT0.

---

## Candidate (B) — multi-room  ★ DO SECOND — BOUNDED SLICE ONLY

### Honest scope finding (critical — read before any code)
The SWOT line "`roomplan.py:262` floor_entries[0] only, dropping other rooms" **overstates** what
exists. The RoomPlan **sidecar schema this adapter accepts is single-room by construction**
(`roomplan.py:1-37` docstring: `"category": "room"`, one `dimensions`, flat `walls[]/floors[]/
ceilings[]`). Apple's true multi-room is `CapturedStructure` (multiple `CapturedRoom`s) — that is
**NOT in this sidecar schema at all**. So:
- `floor_entries[0]` (`roomplan.py:294`) does NOT drop *rooms*; it silently drops any **additional
  floor polygons within one room** (split-level / disjoint floor patches). Today `floor_entries[1:]`
  are **silently discarded with no warning** (confirmed: only `[0]` referenced, no `len()` guard).
- `RoomModel` (`model.py:326-346`) is single-room by design: one `floor_polygon: list[Point2]`, one
  scalar `ceiling_height_m`. True multi-room requires a **new container concept**.

### Full multi-room blast radius (why the full thing is DEFERRED)
A real `RoomCollection`/multi-room container touches **every** RoomModel consumer:
- 5 `RoomModel(` construction sites: `adapters/{ace_challenge,image,mesh,roomplan}.py`,
  `io/room_yaml_reader.py:271`.
- exports: `export/room_yaml.py` (`room_model_to_dict`), `export/gltf.py:112`, `export/usd.py:169`
  (+ their acoustics sidecars).
- placement: `place/dispatch.py:11-15` (listener area, VBAP/DBAP/WFS all assume one room).
- CLI: `cli.py` ingest/place flow (`_maybe_print_*` notices at 420/436 assume one room).
- schema: `proto/room_schema.v0_2.draft.json` (single-room shape) + `io/room_yaml_reader.py`.
- every single-room golden test would need a multi-room sibling without breaking the existing ones.
This is a **multi-PR core refactor**, not a one-cycle increment. Doing a partial version that
breaks single-room golden round-trips would violate `feedback_verify_each_step`. → **DEFER the
container.**

### Buildable + verifiable core (honest, bounded)
Fix the **silent data-loss bug** without touching the model contract:
1. In `roomplan.py:_room_model_from_sidecar` (around `:257`/`:294`), when `len(floor_entries) > 1`,
   stop silently dropping. Two honest options (pick in execution; (a) preferred for minimal risk):
   (a) **fail-loud / disclose** — emit a clear `UserWarning` (single-source string in
   `_disclosure.py`, e.g. `ROOMPLAN_MULTI_FLOOR_NOTE`) that N floor entries were found and only the
   primary is represented by the single-room `RoomModel.floor_polygon`, so the capture is
   single-room-only; OR raise a descriptive `ValueError` if silently-partial geometry is judged
   unsafe. (b) **merge** — union the floor polygons into one footprint IFF they are coplanar and
   form a single simple polygon (shapely union); if union is multi-polygon/non-simple, fall back to
   (a). Merging changes geometry numbers, so it MUST be covered by a fixture with a known unioned
   area (no fake number).
2. Same treatment for `ceilings[]` is already a list (handled), and `walls[]` already iterate — so
   only `floors[]` has the silent `[0]` truncation. Keep the change surgical.
3. **No `RoomModel` change, no new container, no schema change** → single-room golden tests stay
   byte-equal (additive warning path only).

### Honestly deferred (with reason)
- **True multi-room `RoomCollection`** (multiple `CapturedRoom`s, per-room placement/export).
  Large core refactor (blast radius above); no real multi-room sidecar fixture exists; would risk
  single-room goldens. DEFER to a dedicated phased ADR (propose new ADR + OQ). State plainly that
  the current product is single-room and that the bounded slice only removes the *silent* loss.

### Verification strategy
- **In-gate:** add a `tests/test_adapter_roomplan.py` fixture with `floors: [poly_a, poly_b]`:
  assert option (a) emits the disclosure warning (or raises) — deterministic, no accuracy claim; OR
  if (b) merge is chosen, assert the unioned footprint area equals a hand-computed known value
  (±epsilon) — empirical, backed by the fixture. Existing single-floor test
  (`test_adapter_roomplan.py:103-105`, `len(floors)==1`) must stay GREEN.
- **What CANNOT be claimed:** "roomestim supports multi-room." It does not. Only "multi-floor-entry
  captures no longer silently lose geometry."
- **Gate markers:** default lane; baseline +1/+2 tests. web/ruff/mypy unchanged.

### Risk / honesty (fake-number trap?)
Low. The trap would be *merging* polygons and reporting a footprint/area as if measured without a
backing fixture — avoided by (a) preferring disclose-only, or (b) gating merge behind a
known-area fixture. No acoustic surface touched.

### Files to touch
`roomestim/adapters/roomplan.py` (multi-floor guard/merge), `roomestim/reconstruct/_disclosure.py`
(`ROOMPLAN_MULTI_FLOOR_NOTE` if disclose path), `tests/test_adapter_roomplan.py` (multi-floor
fixture + assertion), optional new ADR/ OQ entry recording the multi-room DEFER + phased plan.

### Acceptance criteria
- [ ] `floor_entries[1:]` no longer silently dropped — either disclosed (warning, single-source
      string) or merged-with-known-area-fixture, or raised with a descriptive error.
- [ ] `RoomModel` contract unchanged; all existing single-room golden/round-trip tests byte-equal.
- [ ] Multi-room container explicitly DEFERRED with blast-radius rationale (ADR/OQ).
- [ ] Full gate GREEN (default 414+, web 86p/3s, ruff/mypy EXIT0).

---

## Candidate (C) — polygon-ISM acoustics (ADR 0040)  ★ DO THIRD — GEOMETRY-ONLY SLICE OR DEFER

### Honest scope finding (critical)
The repo **already has a complete, deterministic, in-gate shoebox ISM**:
`roomestim/reconstruct/image_source.py` (`image_source_rt60`, `_ism_rt60_core`, lattice enumeration;
analytic-shoebox tests at `tests/test_image_source.py:101-188`). ADR 0040 proposes extending RT60 to
**non-shoebox prismatic polygons** and recommends **reusing pyroomacoustics** (option b) via a
`polygon_image_source.py` sibling + lazy import + a 3-tier predictor cascade. Three facts make the
**full RT60 polygon-ISM a fake-number trap this cycle**:
1. **No non-shoebox measured GT exists** (ADR 0040 §G explicitly retracts the synthetic-deform GT
   as "공허/폐기"; OQ proposal #2). So any polygon-ISM **RT60 magnitude is unverifiable** → forbidden
   to present as accurate under 가짜 숫자 금지. The repo's acoustics already has NO accuracy gate
   (tests assert ordering/ratio, not magnitude; RT60 error up to ±1.4 s per analysis line 14).
2. **pyroomacoustics RT60-fit reliability is itself unverified** on sparse ISM-only RIR (ADR 0040
   §B, §I PR1, OQ proposal #3) — Schroeder fit on a discrete tail is unstable.
3. **pyroomacoustics is a web-extra** (`pyproject.toml:39`), so any predictor path using it is
   excluded from the default gate and introduces an environment-dependent reproducibility asymmetry
   (ADR 0040 §C2/§R2). The default lane could not verify it.

### Buildable + verifiable core (honest) — geometry-only, NO acoustic number
Build the part that is deterministic and in-gate verifiable, and that ADR 0040's recommended pra
path does NOT actually provide as a checkable artifact: a **numpy-only polygon image-source
POSITION + visibility enumerator**, emitting NO RT60.
1. New sibling `roomestim/reconstruct/polygon_image_source.py` with a deterministic function that,
   for an extruded simple polygon (floor_polygon + ceiling_height), enumerates **first-order (and
   optionally low-order) image-source positions** by mirroring the source across each wall plane,
   with a shapely visibility/validity test. Reuse the proven pattern from
   `roomestim_web/binaural.py:70` `_image_inside_floor` (shapely `contains`) — but keep this module
   **core, numpy/shapely-only, NO pyroomacoustics import** (no web-extra dependency, runs in default
   lane). This is ADR 0040 option (a) **scoped strictly to geometry** (not the ±400-600 LoC full
   RT60 mirror-ISM; just positions + visibility).
2. **Emit NO RT60 and DO NOT wire into `predictor.py`.** The module produces image-source positions
   only. No `PredictorName` change, no cascade, `predict_rt60_default` untouched → shoebox RT60
   byte-equal, zero acoustic regression.

### Verification strategy (geometric / deterministic — the user's exact ask)
- **In-gate (default lane):** for a **known shoebox expressed as a 4-corner polygon**, assert the
  enumerated first-order image-source positions equal the **analytic mirror positions**
  (reflect source across x=0, x=L, z=0, z=W planes) to ~1e-9. This is exactly the
  "image-source positions for a known shoebox match analytic positions" check the user specified —
  deterministic, no acoustic-accuracy claim. Add a non-convex (L-shape) fixture asserting visibility
  correctly prunes images whose reflection point falls outside the polygon.
- **What CANNOT be claimed:** any RT60 / acoustic-accuracy number. The module is geometry only; it
  is the *foundation* a future cycle could turn into RT60 **once a non-shoebox measured GT exists**.
- **Gate markers:** default lane (numpy/shapely only), additive tests. web/ruff/mypy unchanged.

### Honestly deferred (with reason) — this is most of ADR 0040
- **Polygon-ISM RT60 + predictor cascade (ADR 0040 §D, PR3).** DEFER — no non-shoebox measured GT
  (§G/OQ#2) → magnitude unverifiable; pra RT60-fit reliability unverified (OQ#3); web-extra
  reproducibility asymmetry (§C2). Building it now = fabricating acoustic numbers.
- **pyroomacoustics core lazy-import (ADR 0040 §C2).** DEFER with the cascade.
- **coupled-space marker (ADR 0040 §F / R4).** Out of scope; separate OQ.

### Decision: BUILD geometry-only, or DEFER whole candidate
If the user wants a shippable artifact this cycle, build the **geometry-only enumerator** (additive,
in-gate, no acoustic claim). If the user only values RT60 (the actual ADR 0040 goal), then C should
be **DEFERRED in full** until a non-shoebox measured GT corpus exists (OQ#2) — because the RT60 part
is the fake-number trap. **Planner recommendation: build geometry-only** (honest foundation, real
in-gate verification) **and DEFER the RT60 cascade** with the GT/pra/web rationale recorded in ADR
0040 §Status-update. Do NOT ship RT60.

### Risk / honesty (fake-number trap)
The trap is shipping a polygon RT60 number with no measured non-shoebox GT and an unverified pra
fit. Avoided by emitting positions only and explicitly deferring RT60. State in the module docstring
+ ADR that this is geometry, not an acoustic predictor.

### Files to touch
`roomestim/reconstruct/polygon_image_source.py` (new, geometry-only), `tests/test_polygon_image_source.py`
(analytic shoebox position match + non-convex visibility), `docs/adr/0040-polygon-ism-design.md`
(§Status-update: geometry-only landed; RT60 cascade DEFERRED with reasons), optional OQ entries
(#2 non-shoebox GT, #3 pra-fit reliability). **predictor.py / image_source.py untouched.**

### Acceptance criteria
- [ ] Geometry-only enumerator lands; first-order image positions match analytic shoebox to 1e-9.
- [ ] Non-convex visibility pruning covered by a fixture.
- [ ] NO RT60 emitted; `predictor.py` / `image_source.py` byte-equal; shoebox acoustics unchanged.
- [ ] ADR 0040 §Status-update records geometry-only landing + RT60-cascade DEFER rationale.
- [ ] Full gate GREEN (default 414+, web 86p/3s, ruff/mypy EXIT0). No pyroomacoustics import in core.

---

## Candidate (D) — cam_h known-size-reference prior  ★ DO LAST — DEFER (skeptical)

### Honest scope finding (be very skeptical — prior session already deferred this)
- A single pano is **scale-ambiguous**: `r = cam_h / tan(-v_floor)`, the whole room scales exactly
  linearly with cam_h, and **there is no pixel-only signal for absolute cam_h** (ADR 0045
  §image-backend-honesty (1)/(3); `_disclosure.py::IMAGE_CAM_H_SCALE_NOTE`). cam_h without an
  external metric prior is ASSUMED, not measured.
- v0.29.0 candidate (6) **already shipped** the verifiable scale-honesty machinery:
  `image.py:208` `_cam_h_sensitivity` (torch-free, exact-invertible), the extended ASSUMED
  `UserWarning`, and the single-source disclosure (3-candidates plan + ADR 0045 §honesty).
- The external metric prior the user "supplies explicitly" **already exists** as
  `--cam-height` (`cli.py:38`) → `ScaleAnchor("known_distance", cam_height)` (`base.py:13`) →
  `image.py:419`. That IS a user-supplied, opt-in, ASSUMED-labelled metric anchor today.
- The 244-pano GT is **100% cuboid-labelled** → any cam_h-prior **accuracy** claim is unverifiable
  on current data (ADR 0045 §honesty (4); memory cold-eval). Auto-detection of a known-size object
  (e.g. "detect a door") needs a vision detector (a new capability) AND is unverifiable here — the
  exact thing prior sessions deferred.

### The only honest buildable slice (and why it is NOT recommended)
A new **opt-in, manual** anchor type, e.g. `ScaleAnchor("known_object_height", length_m)` plus
user-supplied angular/pixel extent of that object in the pano, from which cam_h is solved
deterministically and labelled ASSUMED/user-supplied. Properties:
- **Verifiable part:** only the geometric inverse (angles + known height → cam_h) on a synthetic
  fixture with a known answer. Deterministic, torch-free, unit-testable.
- **Why not worth it:** (1) it requires the user to manually read pixel rows / mark the object in an
  equirectangular pano — a UX nobody requested; (2) it produces the **same** metric prior that
  `--cam-height` already provides, with MORE friction and ZERO accuracy gain; (3) its accuracy is
  **unverifiable** on the cuboid-only GT, so no "improves by N cm" claim is allowed; (4) the genuinely
  useful version (auto-detect the door) is exactly the vision/unverifiable part that must stay
  deferred. Building the manual slice adds surface area without honest value.

### Verdict: DEFER
- **DEFER** the auto-detection known-size-reference (needs a detector + verifiable prior that does
  not exist; unverifiable on cuboid GT). This matches the prior explicit deferral.
- **DEFER** the manual known-object-height anchor too (recommended): it only duplicates
  `--cam-height` with extra friction and no accuracy gain. Record the option + rationale so it is
  not re-litigated. **If the user explicitly insists** on the manual anchor as a UX convenience,
  it can be built as a MINOR additive `ScaleAnchor` variant with a synthetic-only geometric test and
  an ASSUMED label — but it must carry NO accuracy claim and NEVER silently override `--cam-height`.

### Verification strategy
- If DEFER (recommended): doc-only — extend `docs/adr/0045-image-to-geometry-capture-backend.md`
  §image-backend-honesty with a (D) note (known-size reference: auto = unverifiable/needs detector;
  manual = duplicates `--cam-height`, no accuracy gain → DEFER). Baseline unchanged (414/3).
- If manual anchor is built anyway: synthetic-only unit test (known height + angles → cam_h to
  1e-9); assert it never overrides a user `--cam-height`; ASSUMED warning + `_disclosure.py` string.
  No real-pano accuracy claim (cuboid-GT gap). web/ruff/mypy unchanged.

### Risk / honesty (fake-number trap)
HIGH if mis-scoped. Any auto-cam_h that silently emits a number, or any "accuracy improves" claim on
the cuboid-only GT, is a fake-number generator. The safe path is DEFER; the only safe code is the
manual deterministic anchor with an explicit ASSUMED/user-supplied label and a synthetic-only test.

### Files to touch
DEFER path: `docs/adr/0045-image-to-geometry-capture-backend.md` (§honesty (D) note), optional
`.omc/plans/open-questions.md` (track re-open conditions). **No production code.**
IF manual anchor built (not recommended): `roomestim/adapters/base.py` (anchor type),
`roomestim/adapters/image.py` (solve cam_h), `roomestim/reconstruct/_disclosure.py` (note),
`roomestim/cli.py` (flag), `tests/test_adapter_image.py` (synthetic inverse).

### Acceptance criteria (DEFER path)
- [ ] ADR 0045 §honesty records (D): auto known-size-reference = DEFER (needs detector + verifiable
      prior; unverifiable on cuboid GT); manual anchor = DEFER (duplicates `--cam-height`, no gain).
- [ ] Re-open conditions recorded (a verifiable non-cuboid GT + a detector, or explicit user demand
      for the manual anchor).
- [ ] Zero production changes; baseline 414/3 unchanged.

---

## Recommended order & dependencies

1. **(A)** — independent, low-risk, fully in-gate verifiable, no fake-number surface. **DO FIRST.**
2. **(B) bounded slice** — independent; surgical robustness/honesty fix; full multi-room DEFERRED.
3. **(C) geometry-only** — independent additive module; NO RT60 (cascade DEFERRED). Or defer wholly.
4. **(D)** — DEFER (doc-only ADR note); skeptical verdict, only honest code duplicates existing flag.

No hard inter-dependencies; order reflects value × verifiability × honesty-risk (low→high).

---

## ADR (decision record for this planning cycle)
- **Decision:** Ship A (path decouple + PyPI-ready packaging, D98) and B's bounded slice (multi-floor
  silent-loss fix, D99); build C geometry-only OR defer (D100); defer D (D101). A/B/C ship code only
  within empirically verifiable bounds; D ships an ADR note.
- **Drivers:** 가짜 숫자 금지; in-gate verifiability of each claim; A removes a real cross-machine
  happy-path failure; B removes a real silent data-loss bug without touching the model contract;
  C's RT60 has no measured non-shoebox GT (unverifiable) → only its geometry is honest; D's useful
  form needs a detector + verifiable prior that does not exist (cuboid-only GT).
- **Alternatives considered:** (A) vendor the engine schema — rejected (docstring contract "never
  copied"; fail-loud opt-in validation is cleaner). (B) ship a real RoomCollection now — rejected
  (multi-PR core refactor, no fixture, would risk single-room goldens). (C) ship the ADR 0040
  pyroomacoustics RT60 cascade — rejected (no non-shoebox GT, unverified pra fit, web-extra
  reproducibility asymmetry → fabricates acoustic numbers). (D) ship auto known-size-reference cam_h
  — rejected (needs vision detector, unverifiable on cuboid GT); manual anchor — rejected (duplicates
  `--cam-height`, no accuracy gain).
- **Why chosen:** each retained scope has a deterministic in-gate verification (path resolution,
  multi-floor fixture, analytic image-source positions) or an explicit DEFER label; none introduces
  an unbacked accuracy/acoustic number.
- **Consequences:** A → machine-independent + pip-installable (publish still deferred per ADR 0007);
  B → no silent multi-floor loss, still single-room product; C → honest geometry foundation, no RT60;
  D → unchanged, documented defer.
- **Follow-ups:** PyPI publish (ADR 0007 reverse-criteria); true multi-room RoomCollection (phased
  ADR + fixture); non-shoebox measured RT60 GT corpus (unblocks C's RT60) + pra-fit reliability
  spike; a verifiable non-cuboid image GT + a known-size detector (unblocks D).
