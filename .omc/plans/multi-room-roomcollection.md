# roomestim — Multi-room RoomCollection (additive composition layer) — RESUME POINTER

**Started:** 2026-06-17 (autonomous, post external-data-closure). Baseline: **v0.39.0**, default 640p/7s · web 86p/3s · ruff·mypy clean.
**OMC cycle:** explore → planner → executor → code-review → verifier. Hard rules: **NO FAKE CAPABILITY / NO FAKE NUMBERS**, additive-only, single-room goldens BYTE-EQUAL, full gate each phase.

## Framing (why this is NOT the ADR0047-deferred refactor)
ADR0047 DEFERRED true `RoomCollection` for 3 reasons: (1) no real multi-room input path (RoomPlan sidecar is structurally single-room; Apple `CapturedStructure` not ingested), (2) multi-PR blast radius touching ALL RoomModel consumers, (3) partial impl risks breaking single-room goldens.

**This slice sidesteps all 3** by being an **additive composition container**, NOT a RoomModel rewrite:
- Input = **N real single-room captures** (each already a genuine `RoomModel` via existing adapters) → compose into an ordered collection. NO fake multi-room fixture (compose existing single-room goldens).
- **Purely additive**: new container + new CLI subcommand + new combined export. ZERO edits to single-room ingest/place/export/run/edit paths → single-room goldens byte-equal BY CONSTRUCTION.
- Real product value: B2B installer scans a multi-room venue → per-room speaker layouts + one combined model. Matches ADR0047 re-open condition ("per-room placement/export 설계").

## Architecture (confirmed by explore 2026-06-17)
- `RoomModel` (model.py:325) single-room dataclass; 5 creation sites (adapters/{ace,image,mesh,roomplan}, io/room_yaml_reader).
- CLI subcommands (cli.py): ingest/place/export/run/edit. Exports: room_yaml/layout_yaml/gltf/usd. Placement: place/dispatch.run_placement.

## RESUME POINTER
- [x] External-data lever closed (Redwood retry NEGATIVE n=1; fresh sweep no new commercial-OK lever) — `.omc/research/geometry-footprint-gt-dataset-hunt.md` 2026-06-17 sections.
- [x] planner: phased ADR 0049 design (additive composition layer) — DONE 2026-06-17 (see "## Phased plan (planner 2026-06-17)" below + `docs/adr/0049-multi-room-roomcollection-composition.md` DRAFT Status: Proposed). Target version v0.40.0 (MINOR, additive).
- [x] executor: Phase 1 implemented (additive composition layer) — DONE 2026-06-17. Files ADDED: `roomestim/collection.py` (RoomCollection dataclass), `roomestim/proto/collection_schema.v0_1.draft.json` (manifest schema, `additionalProperties:false`, auto-bundled via existing `proto/*.json` package-data — NO pyproject/MANIFEST change needed), `roomestim/export/collection_yaml.py` (collection_to_dict + write_collection_yaml, jsonschema-validated, relative-ref guard rejects absolute refs), `roomestim/io/collection_yaml_reader.py` (read_collection_yaml — validate → resolve refs vs manifest parent → existing readers), `tests/test_collection_cli.py` + `tests/test_collection_roundtrip.py` (+10 tests). Files TOUCHED (additive-only): `cli.py` (new `_add_collection_parser` + `_cmd_collection` + `_unique_room_slug` + 1 dispatch branch + 1 registration; existing 5 subcommands byte-unchanged), `roomestim/__init__.py` (append `RoomCollection` export). Fixtures: REAL existing inputs under DEFAULT gate — `lab_room.json` (roomplan, name "lab_room_synthetic") + `lab_room.ply` (polycam/mesh, name "lab_room"); shoebox `.usdz` NOT used (would need [usd] extra). Per-room artifacts written as `room.<slug>.yaml` + `layout.<slug>.yaml` (collision-safe slug). **Risk #1 byte-equality PROVEN**: `test_collection_layout_byte_equal_to_standalone_place` asserts each collection per-room layout.yaml is byte-identical to standalone `place` (PASS). Risks #3 (relative refs + absolute-ref rejection) + #4 (deterministic collision suffix `-1`) covered. **GATE: default 650p/7s (was 640p/7s, +10) · web 86p/3s (unchanged) · ruff clean · mypy clean — NO regression.** NOT committed (orchestrator commits post-review); version NOT bumped.
- [x] code-review (separate lane, opus): APPROVE no blockers. Orchestrator independently re-verified: additive single-room diff 0, byte-equality test real+passing, schema bundled via `proto/*.json` wildcard, runtime resolution matches room_yaml.
- [x] verifier evidence: full gate GREEN (default 650p/7s · web 86p/3s · ruff · mypy 54 files); version-consistency tests pass post-bump.
- [x] release prep: v0.40.0 bump (__init__/pyproject), README CHANGELOG row (honest Phase-1 scope), ADR 0049 → Accepted.
- [ ] commit to main + memory update — IN PROGRESS
- [ ] Phase 2 (combined 3D export) / Phase 3 (per-room offsets) — DEFER (future cycle)

## Acceptance criteria (pre-pinned)
- Single-room goldens/round-trip BYTE-EQUAL (additive-only, by construction).
- Full gate GREEN vs v0.39.0 baseline (640p/7s default · 86p/3s web · ruff · mypy).
- NO claim that roomestim infers multi-room from one capture — composition is from N explicit single-room inputs (honest framing in README/ADR).
- New collection fixture = composed from REAL existing single-room fixtures (no fabricated geometry).

---

## Phased plan (planner 2026-06-17)

### Design decisions (resolved + justified)

**D-A · Container shape — flat ordered list, offsets DEFERRED (least-claim).**
`RoomCollection` = `name: str` + `rooms: list[RoomModel]` (ordered) + `placements: list[PlacementResult | None]` (parallel-indexed, optional per-room).
Rooms are **independent** in phase 1 — NO per-room transform/offset/pose. Rationale: roomestim has no measured inter-room registration (the B2B installer scans rooms separately; there is no GT for their relative pose). Fabricating a shared-building frame = fake numbers. Offsets are **opt-in, user-supplied only** and DEFERRED to Phase 3; until then a "collection" is a typed, ordered bundle of independent rooms, which is exactly what the product can honestly produce. New module **`roomestim/collection.py`** (NOT an edit to `model.py`) so `model.py` stays byte-untouched; it imports `RoomModel`/`PlacementResult` from `model.py`.

**D-B · CLI surface — new `collection` subcommand, composes via library functions (NOT `_cmd_place`).**
New subcommand `collection`: `--in-rooms PATH [PATH ...]` (N≥2 room.yaml), reuse of the existing placement flags (`--algorithm/--n-speakers/--layout-radius/--el-deg/--order/--wfs-*`), `--name`, `--out-dir`. Handler `_cmd_collection` loops the inputs and per room calls the SAME library functions `_cmd_place` already uses — `read_room_yaml` (io) → `run_placement` (place/dispatch) → `write_layout_yaml` (export) — it does NOT call `_cmd_place`. Writes one `layout.<room-name>.yaml` per room (collision-safe: index-suffixed if names repeat) + a `collection.yaml` manifest. `_cmd_place/_cmd_run` are NOT edited; the shared notices (`_maybe_print_*`) are reused as plain function calls.

**D-C · Combined export — manifest only in phase 1; new SEPARATE proto schema.**
Phase-1 combined artifact = `collection.yaml` **manifest**: collection `name`, `version`, and an ordered `rooms[]` list of `{name, room_ref, layout_ref}` (relative paths to the per-room room.yaml + layout.yaml). NO geometry merge, NO combined 3D file in phase 1. Schema = **new file** `roomestim/proto/collection_schema.v0_1.draft.json` (manifest-only: refs + names + version; `additionalProperties:false` at root). The single-room `room_schema.v0_2.draft.json` is NOT edited. New writer `roomestim/export/collection_yaml.py` + reader `roomestim/io/collection_yaml_reader.py`, mirroring the room.yaml writer/reader (finite-sweep N/A — manifest is strings; jsonschema-validated). Combined glTF/USD (concatenate per-room scenes) = Phase 2, gated behind explicit offsets.

**D-D · Phasing — 3 phases, each gate-GREEN + single-room goldens byte-equal by construction.**

---

### Phase 1 — Thinnest vertical slice (container + N room.yaml → per-room place → collection.yaml manifest)
**Scope:** `RoomCollection` dataclass; `collection.yaml` manifest writer/reader + new proto schema; `collection` CLI subcommand composing per-room placement via library functions; real composed fixture + tests.
**Files ADDED (all new):**
- `roomestim/collection.py` — `RoomCollection` dataclass (`name`, `rooms`, `placements`).
- `roomestim/proto/collection_schema.v0_1.draft.json` — manifest schema (refs/names/version; `additionalProperties:false`).
- `roomestim/export/collection_yaml.py` — `collection_to_dict` + `write_collection_yaml` (jsonschema-validated, `yaml.safe_dump(sort_keys=False)`).
- `roomestim/io/collection_yaml_reader.py` — `read_collection_yaml` (validate → load referenced room.yaml/layout.yaml via existing readers).
- `tests/test_collection_*.py` — round-trip + CLI + manifest-schema + "single-room goldens unchanged" guard.
- `tests/fixtures/collection/` — composed fixture (see Fixtures below).
**Files TOUCHED for single-room code:** **ZERO.** (`cli.py` gets a NEW `_add_collection_parser` + `_cmd_collection` + one dispatch branch in `main()`/`_build_parser` — additive only; existing subcommand parsers/handlers byte-unchanged. `roomestim/__init__.py` may export `RoomCollection` — additive append.)
**Fixtures (REAL, composed):** generate 2 room.yaml by ingesting EXISTING real inputs already used by the suite — `tests/fixtures/lab_room.json` (`--backend roomplan`) and `tests/fixtures/shoebox_zup.usdz` (mesh) — then assemble them into one `collection.yaml`. No fabricated geometry; each member is a genuine adapter output. (Executor: if shoebox usdz ingest needs the `[usd]` extra not in the default gate, fall back to a second roomplan/mesh fixture that ingests under the default gate — still two genuine, distinct single-room outputs.)
**Acceptance:**
- `roomestim collection --in-rooms A.yaml B.yaml --algorithm vbap --out-dir D` writes `D/layout.<A>.yaml`, `D/layout.<B>.yaml`, `D/collection.yaml`; each per-room layout is BYTE-IDENTICAL to running `roomestim place --in-room <that room> ...` standalone (proves composition = N independent single-room placements, no cross-talk).
- `read_collection_yaml(write_collection_yaml(c))` round-trips (manifest refs + ordering stable).
- A test asserts every existing single-room golden / round-trip output is byte-unchanged (diff the v0.39.0 outputs).
- Honest disclosure: manifest carries no inter-room pose; CLI/README state composition is from N explicit inputs (no multi-room inference).
**Gate:** `/home/seung/miniforge3/bin/python -m pytest -q` (default) + `-m web` + ruff + mypy — all GREEN vs v0.39.0 (640p/7s · 86p/3s · clean); new tests strictly additive.

### Phase 2 — Combined 3D export (opt-in)
**Scope:** OPTIONAL `--format gltf|usdz` on `collection` → concatenate per-room scenes into one combined file by reusing `export/gltf.py` / `export/usd.py` per room. With NO offsets (Phase 3), rooms are emitted at their own local origins (documented overlap; honest — no fabricated registration). Manifest gains an optional `combined_ref`.
**Files ADDED:** extension to `export/collection_yaml.py` or new `export/collection_gltf.py`/`collection_usd.py`; tests.
**Files TOUCHED for single-room code:** ZERO (call existing `write_gltf`/`write_usdz` per room; do not edit them).
**Acceptance:** combined file opens; per-room sub-scenes equal the standalone per-room exports; manifest+single-room goldens byte-equal.
**Gate:** full gate GREEN.

### Phase 3 — Explicit per-room offsets + richer fixtures
**Scope:** opt-in user-supplied per-room offset (e.g. `--offsets` file or per-room field in an input collection manifest) placing rooms in a shared building frame. STILL no inferred registration — offsets are user-asserted; absent ⇒ phase-1 behaviour (byte-equal). Combined export (Phase 2) then honours offsets. Add a 3-room fixture.
**Files ADDED:** offset parsing + an optional `offset` field in `collection.yaml` (additive schema key; absent ⇒ identity); tests.
**Files TOUCHED for single-room code:** ZERO.
**Acceptance:** offset absent ⇒ Phase-1/2 output byte-equal; offset present ⇒ combined export shifts only that room; single-room goldens byte-equal.
**Gate:** full gate GREEN.

### Risks to flag before execution
1. **Per-room layout byte-equality is the load-bearing test.** The whole "additive, no cross-talk" claim rests on per-room `layout.yaml` from `collection` being byte-identical to standalone `place`. Executor MUST assert this directly (not just "looks similar"). If `run_placement` ever reads global state this would surface here.
2. **Fixture ingest under the DEFAULT gate.** `shoebox_*.usdz` may require the `[usd]` extra that is not in the default gate env. If so, compose from two inputs that BOTH ingest under the default gate (e.g. lab_room.json roomplan + a mesh `.ply`/`.obj` already in fixtures) so the new collection tests run in the default suite, not only `-m web`/extra-gated.
3. **Manifest path semantics.** `room_ref`/`layout_ref` should be RELATIVE to the manifest dir for portability; reader resolves against the manifest's parent. Decide+document (avoid absolute paths leaking into goldens).
4. **Name collisions.** Two rooms named identically ⇒ per-room filename collision. Index-suffix deterministically and cover with a test.
5. **Scope creep into geometry merge.** Do NOT union footprints or compute a combined volume/RT60 — that is the ADR0047 fake-number trap. Collection RT60/acoustics is per-room only; no aggregate acoustic claim.
