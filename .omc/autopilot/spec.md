# roomestim v0.2 + v0.3 + E2E Verification — Autopilot Spec

- **Date authored**: 2026-05-06
- **Author**: analyst (oh-my-claudecode)
- **Predecessor release**: v0.1.1 (commit `cd78c0d`, tag `v0.1.1` pushed; default-lane 63/63 collected, 18/18 perf checks)
- **Source decisions**: `.omc/plans/decisions.md` D1, D7, D8; `.omc/plans/v0.1.1-closeout.md` §7 ADR template; `RELEASE_NOTES_v0.1.1.md` style.
- **Hard constraint**: read-only on `/home/seung/mmhoa/spatial_engine/`; cross-repo work delivered as PR text only. No tag is pushed by autopilot — release tagging is human-confirmed (v0.1.1 precedent in `.omc/plans/v0.1.1-closeout.md` §8 "do not push tag automatically").

---

## 1. Headline

This autopilot run ships **three independent deliverables** under the v0.2 + v0.3 banner without flipping Stage-2 of `proto/room_schema.json` and without touching `spatial_engine/`:

1. **roomestim v0.2** — bumps `pyproject.toml`/`__version__` to `0.2.0`. Adds **ADR 0007** (`docs/adr/0007-distribution-model.md`) which records the D1 distribution-model decision (standalone-repo / submodule / PyPI) with reverse criteria. Adds a cross-repo PR-body draft at `.omc/autopilot/cross-repo-pr-room-schema.md` that proposes `proto/room_schema.json` to the `spatial_engine` team for engine-side adoption. Neither D2 Stage-2 flip nor A10 physical capture is performed (both remain D8 human-gated).
2. **roomestim v0.3** — bumps `pyproject.toml`/`__version__` to `0.3.0` (sequenced **after** v0.2 ships, but bundled into the same autopilot run as a second commit / second tag candidate). Extends `proto/room_schema.draft.json` and `proto/room_schema.json` with an OPTIONAL `absorption` block carrying 6 octave-band coefficients (125 / 250 / 500 / 1k / 2k / 4k Hz) per surface. The legacy `absorption_500hz` field stays REQUIRED in the schema and remains the canonical fallback when `absorption` is absent. Material lookup table extended to populate all 6 bands per material (Vorländer 2020 *Auralization* Appendix A). RT60 API gains `sabine_rt60_per_band(...)` returning a `dict[band_hz, float]` plus a backwards-compatible `sabine_rt60(...)` that keeps its v0.1 signature byte-for-byte.
3. **E2E GT-dataset performance verification** — adds ONE adapter under `roomestim/adapters/<dataset_name>.py` plus a gated test at `tests/test_e2e_<dataset_name>_rt60.py` (markers `@pytest.mark.e2e` and `@pytest.mark.network`, both gated by env var `ROOMESTIM_E2E_DATASET_DIR`). Produces a report at `docs/perf_verification_e2e_2026-05-06.md` that PRINTS per-room RT60 error in seconds + total mean/p95/max. **No accuracy threshold is asserted** — same characterisation framing as the v0.1.1 DBAP-noise test (see `.omc/plans/v0.1.1-closeout.md` §4 Step 4).

What stays deferred:

- D2 Stage-2 schema flip (`version: "0.1"`, `additionalProperties: false` already in the strict file at `proto/room_schema.json`, but `__schema_version__` in `roomestim/__init__.py:4` stays `"0.1-draft"` until A10 lab capture per D8).
- A10 physical lab capture (post-autopilot human session).
- A2 / A15 C++ harness binaries (D10 — deferred to spatial_engine v0.2; not in roomestim's gift).
- Distribution-model migration TO PyPI or TO submodule — v0.2 only RECORDS the choice in ADR 0007 and proposes the schema cross-repo. Actually moving artefacts to PyPI / vendoring under `spatial_engine/third_party/` is post-autopilot human work.
- COLMAP first-class promotion (ADR 0001 follow-up; v0.3 scope per ADR 0001 line 45 but not in this autopilot run).
- Ambisonics placement (ADR 0003 follow-up; deferred until `spatial_engine/require.md` lists it mandatory).

---

## 2. Workstream (c) — roomestim v0.2

### 2.1 What v0.2 ships

A version bump and two text-only artefacts. **No production code** at `roomestim/` is touched. **No file at `/home/seung/mmhoa/spatial_engine/`** is touched. All 63 v0.1.1 default-lane tests stay byte-for-byte green.

### 2.2 Files touched (allowlist)

- `pyproject.toml` — `version = "0.1.1"` → `version = "0.2.0"`. (Line 7.)
- `roomestim/__init__.py` — `__version__ = "0.1.0"` → `__version__ = "0.2.0"`. (Line 3. Note: this string was never bumped at v0.1.1 — flag for the architect; see Open Decisions §7.)
- `docs/adr/0007-distribution-model.md` — NEW ADR (~80–120 lines, template per `.omc/plans/v0.1.1-closeout.md` §7).
- `.omc/autopilot/cross-repo-pr-room-schema.md` — NEW cross-repo PR body draft (~60–100 lines).
- `RELEASE_NOTES_v0.2.md` — NEW (mirrors `RELEASE_NOTES_v0.1.1.md` structure).
- `docs/adr/0004-room-yaml-schema-lockin.md` — APPEND a "v0.2 status" note: "Cross-repo PR drafted in `.omc/autopilot/cross-repo-pr-room-schema.md`; engine-team review pending. D2 Stage-2 flip remains gated by A10 capture per D8." NO `## Decision` rewrite.
- `.omc/plans/decisions.md` — APPEND a "**D11** — distribution-model decision" entry referencing ADR 0007.

### 2.3 Files NOT touched (denylist — autopilot must verify with `git diff --name-only`)

- `/home/seung/mmhoa/spatial_engine/**` — entire sibling repo (matches v0.1.1 R3 boundary).
- `proto/room_schema.json` (Stage-2 strict file) — NOT MODIFIED in workstream (c). Workstream (d) touches it; (c) does not.
- `proto/room_schema.draft.json` — NOT MODIFIED in workstream (c). Workstream (d) touches it.
- `roomestim/place/**`, `roomestim/coords.py`, `roomestim/adapters/**`, `roomestim/export/**`, `roomestim/io/**`, `roomestim/model.py`, `roomestim/cli.py` — algorithm + I/O code is untouched at v0.2.
- All `tests/test_*.py` files — test deltas live entirely in workstream (d).

### 2.4 ADR 0007 template (Decision / Drivers / Alternatives / Why-chosen / Consequences / Follow-ups)

Sections (per `.omc/plans/v0.1.1-closeout.md` §7):

```
# ADR 0007 — Distribution model for roomestim

- **Status**: Accepted (v0.2)
- **Date**: <YYYY-MM-DD>
- **Cross-ref**: design plan §11.3, decisions D1, D11; v0.1.1 closeout §7 (a)/(c).

## Context
Three viable distribution paths since D1:
  (a) Standalone git repo (current; v0.1 + v0.1.1 ship-state).
  (b) Git submodule under spatial_engine/third_party/roomestim/.
  (c) PyPI publish under name `roomestim`.

## Decision
<chosen option, ONE of (a) | (b) | (c)>.

## Drivers
1. Engine-team integration friction (cross-repo PR cadence, version pinning).
2. CI maintenance cost since v0.1 (target < 1 day/month per D1 reverse criteria).
3. Real-world room.yaml count produced since v0.1.1 (target ≥10 per ADR 0004 falsifier — note: as of autopilot run, count is 0 produced via lab).
4. Sibling-repo precedent (vid2spatial, claude_text2traj are standalone).

## Alternatives (rejected)
- For each non-chosen of {(a), (b), (c)}: a numbered "rejected because…" paragraph.

## Why chosen
Evidence: cite the count of room.yaml files produced since v0.1.1 (likely 0 or 1),
the count of cross-repo schema PR rounds since v0.1.1 (likely 0), the engine-team
request status (`<engine-team-confirmation-status>`), and the actual CI-maintenance
hours measured between v0.1 and the v0.2 cut (best-effort estimate).

## Consequences
- (+) <chosen-option positive>
- (−) <chosen-option negative>
- Migration plan: <if (a) → (b): submodule add command, branch hygiene>;
                  <if (a) → (c): PyPI namespace claim + pyproject metadata>;
                  <if "stay on (a)": no migration; just ADR-record-the-decision>.

## Reverse criteria (per D1)
- Reverse to <next option> if: <one or more measurable triggers>.

## Follow-ups
- Cross-repo PR for room_schema.json: see `.omc/autopilot/cross-repo-pr-room-schema.md`.
- Engine-team review of the schema: blocks the schema-side D2 flip (independent of D1).
```

**Hard rule for the architect**: the ADR is **evidence-based**. Vacuous "we choose (a) because we already use (a)" is rejected by the critic at review. Drivers must cite measurable values (CI hours, PR-round count, room.yaml count, engine-team request status). If the architect cannot produce a defensible answer for a driver, that driver becomes an "Open Decision" in §7 and the ADR explicitly records "evidence not yet available" rather than fabricating a number (mirrors v0.1.1 closeout Critic M1 honesty principle).

### 2.5 Cross-repo PR body skeleton (`.omc/autopilot/cross-repo-pr-room-schema.md`)

The file is a markdown document the user will copy-paste into a PR they manually open against `spatial_engine`. Skeleton:

```
# [spatial_engine] Adopt roomestim's room_schema.json as engine-side proto/room_schema.json

## Summary
roomestim has shipped `proto/room_schema.json` (Stage-2 strict, 105 lines, Draft 2020-12)
since v0.1.1. This PR proposes adopting it verbatim as `spatial_engine/proto/room_schema.json`
so that the engine's RoomGeometry C++ loader and roomestim's Python emitter validate against
a single source of truth.

## Schema, verbatim
<inline copy of /home/seung/mmhoa/roomestim/proto/room_schema.json — 105 lines>
SHA256: <computed at PR-draft time>

## What this PR proposes
- ADD: spatial_engine/proto/room_schema.json (verbatim from roomestim v0.2).
- ADD: a CMake/CI hook that runs jsonschema validation on every committed
  test fixture under spatial_engine/configs/ that names version "0.1".
- NO C++ loader change in this PR. The loader work is a follow-up PR
  authored by the engine team.

## Why now (drivers)
1. roomestim v0.1.1 has shipped, used the Stage-1 draft schema for <N> real fixtures,
   and the Stage-1 → Stage-2 flip is the next discrete step (gated by A10 lab capture).
2. The engine's RoomGeometry loader currently has no JSON-schema validation — adopting
   roomestim's schema gives the engine the same finite-leaf + enum-closed guarantees
   that roomestim's Python writer enforces (`roomestim/export/room_yaml.py:108–125`).

## Why this is NOT a Stage-2 flip
roomestim's Stage-2 flip (writer's default schema_version flips from "0.1-draft" to "0.1",
i.e. `roomestim/__init__.py:4` changes from "0.1-draft" to "0.1") is a SEPARATE decision
gated by A10 lab capture per D8. This PR only proposes the schema FILE. The writer-side
flip happens later, independent of engine-team review timing.

## Backwards compat
Engine adopts the schema as a NEW file. No engine-side existing file changes.
roomestim continues to validate against its own copy at /home/seung/mmhoa/roomestim/proto/.
If the engine-team merges this with edits, roomestim v0.3 will diff and re-sync.

## Review questions for the engine team
- [ ] Is the closed material enum sufficient? (D3 reverse criteria: ≥30% surfaces in `unknown`.)
- [ ] Does `additionalProperties: false` at root + per-surface match engine-side strictness goals?
- [ ] Should `mount_surfaces` and `wfs_baseline_edge` be required vs optional from the engine's view?
- [ ] Octave-band absorption block (added in roomestim v0.3) — does the engine want it now or later?

## Acceptance for engine-team merge
- [ ] CI on the engine repo passes with the new schema file.
- [ ] At least one engine reviewer signs off on the field set.
- [ ] No forced re-sync requested back into roomestim within 30 days of engine merge
  (else reverse v0.2 cross-repo decision and re-open ADR 0004).

🤖 Drafted via roomestim v0.2 autopilot
```

**Constraint**: roomestim must NOT modify any file at `/home/seung/mmhoa/spatial_engine/`. The PR-body markdown is the deliverable; opening the actual GitHub PR is human-gated.

### 2.6 Acceptance criteria for workstream (c) (testable)

- [c1] `git diff --stat` after workstream (c) shows: exactly the files in §2.2 modified; zero files under `/home/seung/mmhoa/spatial_engine/` modified (verified by `find /home/seung/mmhoa/spatial_engine -newer <pre-c-commit-marker>` → empty).
- [c2] `pytest -m "not lab"` collects 63/63 tests, all pass byte-equal to v0.1.1 (no regression — RELEASE_NOTES v0.1.1 line 160 baseline).
- [c3] `docs/adr/0007-distribution-model.md` exists, is parseable as markdown, contains all six section headers from the §2.4 template, and the "Decision" line names exactly one of `(a)`, `(b)`, `(c)`.
- [c4] `.omc/autopilot/cross-repo-pr-room-schema.md` exists, contains a `## Schema, verbatim` section, contains an inline copy whose SHA256 matches `proto/room_schema.json` at the v0.2 commit.
- [c5] `pyproject.toml` line 7 reads `version = "0.2.0"`.
- [c6] `roomestim/__init__.py` line 3 reads `__version__ = "0.2.0"`.
- [c7] `RELEASE_NOTES_v0.2.md` opens with a one-sentence headline naming what v0.2 ships and what stays deferred (mirrors RELEASE_NOTES_v0.1.1.md line 11).
- [c8] No tag is pushed by autopilot. Autopilot may CREATE the local tag `v0.2.0-rc` but MUST NOT `git push --tags`. (Mirrors v0.1.1 closeout §8 hard exit criterion.)

---

## 3. Workstream (d) — roomestim v0.3 octave-band absorption

### 3.1 What v0.3 ships

An optional 6-band absorption block in the schema, an extended material lookup table, a per-band Sabine RT60 API, and unit tests proving (i) v0.1.1 single-band byte-equality is preserved and (ii) the per-band path matches a synthetic-shoebox reference per band.

### 3.2 Schema delta

**File**: `proto/room_schema.json` (Stage-2 strict) AND `proto/room_schema.draft.json` (Stage-1 permissive). Both files MUST be updated identically below.

Current per-surface object (`proto/room_schema.json:36–61`):

```json
{
  "required": ["kind", "material", "absorption_500hz", "polygon"],
  "additionalProperties": false,
  "properties": {
    "kind": ...,
    "material": ...,
    "absorption_500hz": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "polygon": ...
  }
}
```

v0.3 per-surface object delta:

```json
{
  "required": ["kind", "material", "absorption_500hz", "polygon"],
  "additionalProperties": false,
  "properties": {
    "kind": ...,
    "material": ...,
    "absorption_500hz": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "polygon": ...,
    "absorption": {
      "type": "object",
      "description": "Optional octave-band absorption coefficients per Vorländer 2020 Appx A. If absent, callers SHOULD fall back to absorption_500hz.",
      "required": ["a125", "a250", "a500", "a1000", "a2000", "a4000"],
      "additionalProperties": false,
      "properties": {
        "a125":  { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "a250":  { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "a500":  { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "a1000": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "a2000": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "a4000": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
      }
    }
  }
}
```

**Backwards-compat invariants** (these are the test surface for v0.3):

- [d-inv-1] `absorption_500hz` stays REQUIRED (not deprecated, not removed). Files written by v0.1.1 — which never emit `absorption` — MUST validate cleanly against the v0.3 schemas (both draft and strict).
- [d-inv-2] When `absorption` IS present, `absorption.a500` MUST equal `absorption_500hz` (writer-side invariant, asserted by a finite-sweep-style consistency check in `write_room_yaml`). Reader-side: warn (NOT raise) on mismatch ≥ 1e-6, prefer `absorption.a500` per "octave block is more specific" rule.
- [d-inv-3] All v0.1.1 default-lane fixtures (golden + synthetic) replay byte-for-byte through v0.3 reader → writer roundtrip. No tests under `tests/` need to be updated; new tests live in NEW files.

**Schema range note (band coverage)**: The brief mentions "8 kHz" but Vorländer 2020 Appx A typical room-acoustics tables stop at 4 kHz; the brief itself elsewhere says "125/250/500/1k/2k/4k Hz" (6 bands). v0.3 ships 6 bands (125 → 4000 Hz). 8 kHz is **out of scope** for v0.3 — flagged in §6 and Open Decisions §7.

### 3.3 Material table delta

**File**: `roomestim/model.py:51–62` — extend `MaterialAbsorption` from a `dict[MaterialLabel, float]` to a parallel structure that exposes BOTH the legacy single-band scalar AND a 6-band array. Concrete shape:

```python
# Legacy single-band 500 Hz coefficients (v0.1, retained byte-for-byte for d-inv-3).
MaterialAbsorption: dict[MaterialLabel, float] = {
    MaterialLabel.WALL_PAINTED: 0.05,
    MaterialLabel.WALL_CONCRETE: 0.02,
    MaterialLabel.WOOD_FLOOR: 0.10,
    MaterialLabel.CARPET: 0.30,
    MaterialLabel.GLASS: 0.04,
    MaterialLabel.CEILING_ACOUSTIC_TILE: 0.55,
    MaterialLabel.CEILING_DRYWALL: 0.10,
    MaterialLabel.UNKNOWN: 0.10,
}

# v0.3 6-band coefficients per Vorländer 2020 Appendix A.
# Band order is fixed: (125, 250, 500, 1000, 2000, 4000) Hz.
# `MaterialAbsorptionBands[m][2]` MUST equal `MaterialAbsorption[m]` (band a500 ≡ legacy scalar)
# enforced by a unit test: tests/test_room_acoustics_octave.py::test_band_a500_matches_legacy_scalar.
OCTAVE_BANDS_HZ: tuple[int, ...] = (125, 250, 500, 1000, 2000, 4000)
MaterialAbsorptionBands: dict[MaterialLabel, tuple[float, float, float, float, float, float]] = {
    MaterialLabel.WALL_PAINTED:           (0.10, 0.07, 0.05, 0.06, 0.07, 0.09),
    MaterialLabel.WALL_CONCRETE:          (0.01, 0.01, 0.02, 0.02, 0.02, 0.03),
    MaterialLabel.WOOD_FLOOR:             (0.15, 0.11, 0.10, 0.07, 0.06, 0.07),
    MaterialLabel.CARPET:                 (0.05, 0.10, 0.30, 0.40, 0.50, 0.60),
    MaterialLabel.GLASS:                  (0.18, 0.06, 0.04, 0.03, 0.02, 0.02),
    MaterialLabel.CEILING_ACOUSTIC_TILE:  (0.30, 0.45, 0.55, 0.70, 0.75, 0.80),
    MaterialLabel.CEILING_DRYWALL:        (0.29, 0.10, 0.05, 0.04, 0.07, 0.09),
    MaterialLabel.UNKNOWN:                (0.10, 0.10, 0.10, 0.10, 0.10, 0.10),
}
```

**Caveat (architect must verify)**: the numeric values above are **representative** of Vorländer 2020 Appx A but the exact rows must be cross-checked against the textbook before commit. Architect MUST cite a page number per row in a docstring above `MaterialAbsorptionBands`. If a row cannot be cited, that material's row is set to `(legacy_scalar,) * 6` and a `# TODO: Vorländer Appx A row missing — synthetic broadband` comment is added (mirrors v0.1.1 closeout honesty principle). The `UNKNOWN` row legitimately stays flat at 0.10 across all bands.

### 3.4 RT60 API delta

**File**: `roomestim/reconstruct/materials.py`.

- KEEP `sabine_rt60(volume_m3, surface_areas)` byte-equal to v0.1.1 (signature, return type, raise behaviour). This is the load-bearing API for `tests/test_room_acoustics.py:14–49` and v0.1.1 perf-verification §4.
- ADD `sabine_rt60_per_band(volume_m3: float, surface_areas: dict[MaterialLabel, float]) -> dict[int, float]` returning `{125: rt60_125, 250: rt60_250, …, 4000: rt60_4000}`. Internally uses `MaterialAbsorptionBands`. Same `ValueError("sabine_rt60: total_absorption is zero…")` raise on any band whose total absorption is zero (NOT on the sum across bands — single-band-empty is the failure mode users want surfaced).
- ADD `SABINE_REFERENCE_SHOEBOX_RT60_PER_BAND_S: dict[int, float]` constant (same 5×4×2.8 m / wall_painted + wood_floor + ceiling_acoustic_tile shoebox as v0.1.1) computed analytically per band. Used by `test_room_acoustics_octave.py` as the reference comparison (mirrors `SABINE_REFERENCE_SHOEBOX_RT60_S` constant at `roomestim/reconstruct/materials.py:35`).

### 3.5 Reader / writer delta

**Reader** — `roomestim/io/room_yaml_reader.py:54–66`:

- Extend `_surface(d)` to also read `d.get("absorption")`, validate band-key coverage if present, and attach to the `Surface` dataclass.
- New optional field on `Surface` dataclass at `roomestim/model.py:95–106`: `absorption_bands: tuple[float, ...] | None = None`. When `None`, callers fall back to `absorption_500hz` (v0.1 behaviour). When non-`None`, length MUST be 6 and `absorption_bands[2] == absorption_500hz` MUST hold (read-side warn-not-raise per d-inv-2).
- The dataclass MUST stay frozen; `absorption_bands: tuple[...] | None = None` works because tuple is hashable.

**Writer** — `roomestim/export/room_yaml.py:70–76`:

- Extend `_surface_to_dict(s)` to emit `absorption: {a125, a250, …, a4000}` ONLY if `s.absorption_bands is not None`. When `None`, emitted YAML is byte-identical to v0.1.1 (this is d-inv-3 in action).

**Adapters** — `roomestim/adapters/roomplan.py:194,208,227`, `roomestim/adapters/polycam.py:124,133`, `roomestim/reconstruct/walls.py:45–62`:

- Adapters continue to populate `absorption_500hz` from `MaterialAbsorption`. v0.3 ALSO populates `absorption_bands` from `MaterialAbsorptionBands` (length 6). This means v0.3-emitted `room.yaml` will contain the new `absorption` block by default. v0.1.1-emitted `room.yaml` files (legacy on disk) round-trip cleanly because the field is OPTIONAL on the schema side and `absorption_bands=None` on the reader side.
- **Backwards-compat hatch**: a CLI flag `--legacy-single-band` on `roomestim ingest` (and the same flag plumbed through `roomestim run`) that suppresses the `absorption` block emission. Default OFF in v0.3. Architect must decide whether this flag is required or whether v0.3 always emits the block; see Open Decisions §7.

### 3.6 New tests (file allowlist)

- `tests/test_room_acoustics_octave.py` (NEW, ~120 lines, ~6–8 test functions):
  - `test_band_a500_matches_legacy_scalar` — for every material, `MaterialAbsorptionBands[m][2] == MaterialAbsorption[m]`. (Closes d-inv-2 at the table level.)
  - `test_sabine_rt60_per_band_smoke` — synthetic shoebox 56 m³ → returns dict of 6 keys, every value finite and positive.
  - `test_sabine_rt60_per_band_matches_reference` — output matches `SABINE_REFERENCE_SHOEBOX_RT60_PER_BAND_S` per band within ±10% (mirrors v0.1.1 `test_sabine_constant_matches_vorlander_appendix_a` tolerance at `tests/test_room_acoustics.py:34–38`).
  - `test_sabine_rt60_per_band_raises_on_zero_absorption_in_any_band` — single-band-zero scenario.
  - `test_sabine_rt60_legacy_byte_equal_in_v0_3` — same test inputs as `test_sabine_constant_matches_vorlander_appendix_a`, asserts identical numeric output to a frozen pre-v0.3 golden value committed to `tests/fixtures/golden/sabine_legacy_rt60_500hz.txt` (one float, 6 decimal places). Mirrors the v0.1.1 frozen-golden discipline (see `.omc/plans/v0.1.1-closeout.md` §4 Step 0).
- `tests/test_schema_octave_band_compat.py` (NEW, ~80 lines, ~4 test functions):
  - `test_v0_1_1_room_yaml_validates_against_v0_3_draft_schema` — load `tests/fixtures/lab_room.json` (v0.1.1 sidecar), construct a v0.1.1-shape `RoomModel`, write via v0.3 writer with `--legacy-single-band` (or via direct call with `absorption_bands=None`), validate against `proto/room_schema.draft.json` (v0.3) — MUST pass with zero violations.
  - Same for `proto/room_schema.json` (v0.3 strict).
  - `test_v0_3_writer_emits_absorption_block_by_default` — v0.3-default `RoomModel` (with `absorption_bands` auto-populated by adapter) → YAML contains the `absorption: {a125, …, a4000}` block per surface.
  - `test_v0_3_reader_accepts_legacy_no_absorption_block` — a hand-authored YAML missing the `absorption` block reads back with `surface.absorption_bands is None` and `surface.absorption_500hz` populated.
- `tests/fixtures/golden/sabine_legacy_rt60_500hz.txt` (NEW, frozen pre-v0.3, 1 line): captures `sabine_rt60(56.0, {WALL_PAINTED: 50.4, WOOD_FLOOR: 20.0, CEILING_ACOUSTIC_TILE: 20.0})` from v0.1.1 HEAD. **MUST be committed in its own commit BEFORE any code edit lands** — same Step-0 ordering rule as v0.1.1 closeout R5.

### 3.7 Tests NOT touched (regression must stay green)

All 63 v0.1.1 default-lane tests stay collected and passing. Specifically:

- `tests/test_room_acoustics.py` (3 tests) — single-band path, MUST stay byte-identical.
- `tests/test_export_room_yaml.py` (5 tests) — writer path with `absorption_bands=None` must produce identical bytes.
- `tests/test_cli_idempotent.py` (1 test, A12) — v0.3 CLI run with `--legacy-single-band` reproduces v0.1.1 byte output. Architect decides: should CLI default flip the byte output, breaking A12 deliberately? See Open Decisions §7.

### 3.8 Files touched (workstream d allowlist)

- `proto/room_schema.json` — schema delta §3.2.
- `proto/room_schema.draft.json` — schema delta §3.2.
- `roomestim/model.py` — `MaterialAbsorptionBands`, `OCTAVE_BANDS_HZ`, `Surface.absorption_bands` field.
- `roomestim/reconstruct/materials.py` — `sabine_rt60_per_band`, `SABINE_REFERENCE_SHOEBOX_RT60_PER_BAND_S`.
- `roomestim/io/room_yaml_reader.py` — read `absorption` block.
- `roomestim/export/room_yaml.py` — emit `absorption` block conditionally.
- `roomestim/adapters/roomplan.py` — populate `absorption_bands`.
- `roomestim/adapters/polycam.py` — populate `absorption_bands`.
- `roomestim/reconstruct/walls.py` — populate `absorption_bands`.
- `roomestim/cli.py` — IF `--legacy-single-band` flag is adopted: flag wiring on `ingest`/`run`. Otherwise no change.
- `pyproject.toml` — bump to `0.3.0`.
- `roomestim/__init__.py` — bump `__version__` to `0.3.0`.
- `RELEASE_NOTES_v0.3.md` — NEW.
- `docs/adr/0008-octave-band-absorption.md` — NEW ADR (mirrors ADR 0007 template).
- `tests/test_room_acoustics_octave.py` — NEW.
- `tests/test_schema_octave_band_compat.py` — NEW.
- `tests/fixtures/golden/sabine_legacy_rt60_500hz.txt` — NEW frozen pre-edit golden.
- `.omc/plans/decisions.md` — APPEND **D12** entry (octave-band schema extension).

### 3.9 Acceptance criteria for workstream (d) (testable)

- [d1] `pytest -m "not lab"` collects ≥ 63 + 10 = 73 tests (6–8 in `test_room_acoustics_octave.py` + 4 in `test_schema_octave_band_compat.py`); all pass.
- [d2] All 63 v0.1.1 default-lane tests still collected, still passing — count check: `grep -cE "^def test_" tests/test_*.py` baseline + d-new-test-count.
- [d3] `tests/test_cli_idempotent.py` A12 byte-equality holds with `--legacy-single-band` flag (or with default flag if architect decides the CLI default should flip — but then a NEW v0.3 idempotency test asserts the new bytes are stable).
- [d4] `tests/fixtures/golden/sabine_legacy_rt60_500hz.txt` exists; its commit precedes the commit that edits `roomestim/reconstruct/materials.py` (verified by `git log --oneline --reverse`).
- [d5] `MaterialAbsorptionBands[m][2] == MaterialAbsorption[m]` for every `m in MaterialLabel` (asserted by `test_band_a500_matches_legacy_scalar`).
- [d6] `proto/room_schema.json` and `proto/room_schema.draft.json` both parse as Draft 2020-12; both validate the v0.1.1 fixture set with zero violations.
- [d7] Octave-band absorption rows in `MaterialAbsorptionBands` cite a Vorländer 2020 Appx A page number per row in the docstring (or carry a `# TODO: synthetic broadband` marker for any row that cannot be cited).
- [d8] `pyproject.toml` line 7 reads `version = "0.3.0"`; `roomestim/__init__.py:3` reads `__version__ = "0.3.0"`.
- [d9] No tag is pushed by autopilot (mirrors v0.1.1 §8 / [c8]).

---

## 4. Workstream (E2E) — GT-dataset performance verification

### 4.1 What ships

A **single** dataset adapter (`roomestim/adapters/<dataset_name>.py`), a **single** gated test (`tests/test_e2e_<dataset_name>_rt60.py`), and a **report** at `docs/perf_verification_e2e_2026-05-06.md`. The dataset name is decided in **Phase 0b** (architect's job) — see Open Decisions §7. This spec stays dataset-agnostic but pins the adapter SHAPE.

**Default-CI lane is unaffected**. The test is gated by `@pytest.mark.e2e` AND `@pytest.mark.network` AND env var `ROOMESTIM_E2E_DATASET_DIR` must point at a populated local directory. `pytest -m "not lab"` does NOT collect this test (must add `not e2e and not network` to the existing lab marker filter, or add `e2e` to the SKIP path explicitly). Architect MUST update `pyproject.toml`'s `tool.pytest.ini_options.markers` block (lines 42–45) to register both new markers.

### 4.2 Adapter signature (`roomestim/adapters/<dataset_name>.py`)

The adapter is NOT a `CaptureAdapter` (those parse a phone scan into `RoomModel`). The E2E adapter is a **GT-dataset reader** — different protocol, different file. It MUST live at `roomestim/adapters/<dataset_name>.py` per the brief, but it MUST NOT register itself with `_get_adapter()` in `roomestim/cli.py:151–160` (which already declares the `--backend` choices `roomplan` and `polycam`).

Required functions:

```python
from dataclasses import dataclass
from pathlib import Path
from roomestim.model import RoomModel

@dataclass(frozen=True)
class E2ERoomCase:
    """One room from a GT dataset: geometry, GT material annotations, measured RT60."""
    room_id: str            # dataset-native identifier
    room: RoomModel         # roomestim's internal abstraction
    measured_rt60_per_band_s: dict[int, float]   # keys subset of OCTAVE_BANDS_HZ, values seconds
    measured_rt60_500hz_s: float                 # legacy single-band, for v0.1.1-style comparison
    source_rir_path: Path | None = None          # optional: where the measured RT60 came from
    notes: str = ""

def list_rooms(dataset_dir: Path) -> list[str]: ...
def load_room(dataset_dir: Path, room_id: str) -> E2ERoomCase: ...
def dataset_name() -> str: ...    # returns the canonical dataset identifier string
```

The adapter's job is read-only. It MUST NOT download anything (the env-var-pointed directory is the only IO surface). It MUST gracefully return an empty list if the directory is missing required subdirs, with a clear error message.

### 4.3 Gating (env var + markers)

- `ROOMESTIM_E2E_DATASET_DIR` (env var): absolute path to a pre-downloaded local copy of the dataset. If unset → test SKIPs with reason `"E2E test gated; set ROOMESTIM_E2E_DATASET_DIR to a populated dataset directory."`
- `@pytest.mark.e2e` — registered marker meaning "exercises an end-to-end pipeline against external data".
- `@pytest.mark.network` — registered marker even though the actual test does NOT hit the network at run time (the dataset is local). The marker exists to LATER allow a downloader test under a different gate without re-shaping the markers (forward-compat).
- Default CI command must continue to be `pytest -m "not lab"`. Architect MUST also add `and not e2e` to the recommended default invocation in `README.md` and any CI workflow file (`.github/workflows/ci.yml` per ADR 0005). The `e2e` marker is registered alongside `lab` in `pyproject.toml`.

### 4.4 Test signature (`tests/test_e2e_<dataset_name>_rt60.py`)

```python
import os
from pathlib import Path
import pytest
from roomestim.adapters.<dataset_name> import list_rooms, load_room, dataset_name
from roomestim.reconstruct.materials import sabine_rt60, sabine_rt60_per_band

E2E_DIR_ENV = "ROOMESTIM_E2E_DATASET_DIR"


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_rt60_characterisation(capsys) -> None:
    """Characterisation only: PRINT per-room RT60 errors. Do NOT assert magnitude."""
    dataset_dir = os.environ.get(E2E_DIR_ENV)
    if not dataset_dir:
        pytest.skip(f"E2E gated; set {E2E_DIR_ENV} to a populated dataset dir.")
    dpath = Path(dataset_dir)
    rooms = list_rooms(dpath)
    if not rooms:
        pytest.skip(f"{E2E_DIR_ENV}={dataset_dir} contains zero usable rooms.")

    rows: list[tuple[str, float, float, float]] = []   # (room_id, predicted, measured, error_s)
    for rid in rooms:
        case = load_room(dpath, rid)
        # Build surface-area-by-material sum from case.room.surfaces.
        # (Helper extraction left to the implementer; see §4.5.)
        from collections import defaultdict
        areas: dict = defaultdict(float)
        for s in case.room.surfaces:
            # area computed via shapely Polygon over the 3D vertices' planar projection
            ...   # implementer fills in
        predicted = sabine_rt60(volume_m3=..., surface_areas=areas)
        measured = case.measured_rt60_500hz_s
        rows.append((case.room_id, predicted, measured, predicted - measured))

    # Assertions: invariants only. Mirrors v0.1.1 closeout Step 4 framing.
    assert len(rows) == len(rooms), "every room produced a row"
    for rid, pred, meas, err in rows:
        assert pred > 0.0, f"{rid}: predicted RT60 must be positive"
        assert meas > 0.0, f"{rid}: measured RT60 must be positive"
        # Note: NO threshold on |err|. This is characterisation, not bound-test.

    # Diagnostic output: printed via capsys, persisted to the report.
    import statistics
    errs = [abs(e) for _, _, _, e in rows]
    print(f"\n=== E2E RT60 characterisation — {dataset_name()} ===")
    print(f"n_rooms = {len(rows)}")
    print(f"mean |error| = {statistics.mean(errs):.4f} s")
    print(f"p95  |error| = {statistics.quantiles(errs, n=20)[-1]:.4f} s" if len(errs) >= 20 else "p95 unavailable (n<20)")
    print(f"max  |error| = {max(errs):.4f} s")
    for rid, pred, meas, err in rows:
        print(f"  {rid:30s}  predicted={pred:.3f}s  measured={meas:.3f}s  err={err:+.3f}s")
```

**Reasoning for the no-assert framing**: Sabine RT60 is ±20% in real rooms by physics (non-diffuse fields, low-frequency resonances per `RELEASE_NOTES_v0.1.1.md` line 117). Asserting a numeric bound on real-world data is exactly the fabricated-threshold failure mode rejected in v0.1.1 closeout §4 Step 4 (Critic M1). Print, don't assert.

### 4.5 Report skeleton (`docs/perf_verification_e2e_2026-05-06.md`)

```
# roomestim E2E RT60 verification — <dataset_name> (<YYYY-MM-DD>)

**Dataset**: <name + citation + URL>
**Local dataset path**: $ROOMESTIM_E2E_DATASET_DIR
**roomestim version**: 0.3.0 (commit <sha>)
**Method**: Sabine RT60 (v0.1.1 single-band 500 Hz path) computed from GT room geometry +
GT material labels emitted by `roomestim.adapters.<dataset_name>`. Compared against the
dataset-supplied measured RT60 derived from RIRs.

## Per-room results

| room_id | predicted_rt60_500hz_s | measured_rt60_500hz_s | err_s | rel_err_pct |
|---------|-----------------------:|----------------------:|------:|------------:|
| ...     | ...                    | ...                   | ...   | ...         |

## Aggregate
- n_rooms : <int>
- mean |error| : <float> s
- p95  |error| : <float> s
- max  |error| : <float> s
- mean rel_err : <float> %
- p95  rel_err : <float> %

## Caveats / known sources of error
- Sabine assumes a diffuse field and small absorption; real rooms violate this at
  low frequencies and in heavily-absorbed rooms (per Vorländer 2020 §4).
- Material labels are GT-dataset-supplied; mapping from dataset-native labels to
  roomestim's closed `MaterialLabel` enum (D3) involves judgment calls — see
  the adapter source for the mapping table.
- This report is a CHARACTERISATION, not a pass/fail acceptance gate. No accuracy
  bound is asserted. (Same framing as the v0.1.1 DBAP-noise characterisation.)

## Reproducibility
- Run: `ROOMESTIM_E2E_DATASET_DIR=/path/to/dataset pytest -m "e2e and network" -s tests/test_e2e_<dataset_name>_rt60.py`
- Capture: `pytest`'s `-s` flag emits the diagnostic block consumed by this report.
```

The report is **regenerated by the test run**; the markdown body is a captured snapshot of the test's stdout. Architect may either (a) hand-author the markdown and copy the test's `-s` block in, or (b) wire the test to write the markdown directly via `tmp_path` + a CLI helper. Option (a) is simpler; option (b) is reproducible-CI-friendly. See Open Decisions §7.

### 4.6 Files touched (workstream E2E allowlist)

- `roomestim/adapters/<dataset_name>.py` — NEW (~150–250 lines including the E2ERoomCase shape, list/load functions, dataset → MaterialLabel mapping table).
- `tests/test_e2e_<dataset_name>_rt60.py` — NEW (~80–120 lines).
- `docs/perf_verification_e2e_2026-05-06.md` — NEW report.
- `pyproject.toml` — register `e2e` and `network` markers in `[tool.pytest.ini_options].markers` (lines 42–45 currently declare only `lab`).
- `README.md` — append a one-paragraph "E2E verification" section explaining how to run it (env var + marker selection).

### 4.7 Files NOT touched

- `/home/seung/mmhoa/spatial_engine/**` — out of bounds.
- `roomestim/cli.py` — the GT-dataset adapter is NOT a `--backend` choice. v0.3 CLI surface stays exactly as v0.1.1.
- All non-E2E tests stay byte-identical.

### 4.8 Acceptance criteria for workstream (E2E) (testable)

- [e1] `pytest -m "not lab"` collects the SAME 63+d-new-tests from workstream (d) and DOES NOT collect the E2E test (so `e2e and network` markers are correctly excluded by the default lane).
- [e2] `pytest -m "e2e and network"` with `ROOMESTIM_E2E_DATASET_DIR` UNSET → SKIP cleanly (skip reason names the env var).
- [e3] `pytest -m "e2e and network"` with `ROOMESTIM_E2E_DATASET_DIR=/tmp/empty-dir` → SKIP cleanly (skip reason mentions zero usable rooms).
- [e4] `docs/perf_verification_e2e_2026-05-06.md` exists, contains a per-room table with the four required columns (`room_id`, `predicted_rt60_500hz_s`, `measured_rt60_500hz_s`, `err_s`), contains the four aggregate stats (n, mean |err|, p95, max), and contains the verbatim line "This report is a CHARACTERISATION, not a pass/fail acceptance gate."
- [e5] No accuracy threshold appears as a `pytest` `assert` anywhere in `tests/test_e2e_<dataset_name>_rt60.py`. (Negative-test invariant; verified via `grep -E "assert.*rt60.*<|assert.*<.*rt60|assert.*err.*<" tests/test_e2e_*.py` returning zero matches.)
- [e6] Adapter source (`roomestim/adapters/<dataset_name>.py`) does NOT register with `_get_adapter()` (verified via `grep -E "<dataset_name>" roomestim/cli.py` returning zero matches).
- [e7] No download / no network fetch is attempted at test-collection time. (Verified by running the gated test in offline-mode; if any HTTP call appears, the test must be reshaped to defer that call until `ROOMESTIM_E2E_DATASET_DIR` is populated AND a separate `--allow-fetch` opt-in is set — out of scope for this autopilot run.)

---

## 5. Hard exit criteria (autopilot harness checklist)

The autopilot run completes successfully iff ALL of the following hold (numbered for harness consumption):

1. `git diff --name-only main` shows ZERO files under `/home/seung/mmhoa/spatial_engine/` modified.
2. `pyproject.toml` ends at `version = "0.3.0"` (post-workstream-d).
3. `roomestim/__init__.py:3` ends at `__version__ = "0.3.0"` (post-workstream-d).
4. `pytest -m "not lab"` passes; collected count = v0.1.1 baseline (63) + workstream-d new tests (≥10, ≤14). All pass, zero failures, zero errors.
5. `pytest -m lab` SKIPs cleanly (no errors, count unchanged from v0.1.1).
6. `pytest -m "e2e and network"` with `ROOMESTIM_E2E_DATASET_DIR` UNSET → SKIPs cleanly with the env-var skip reason.
7. `docs/adr/0007-distribution-model.md` exists; contains all six template section headers; "Decision" line names exactly one of `(a)`, `(b)`, `(c)`.
8. `docs/adr/0008-octave-band-absorption.md` exists; contains all six template section headers.
9. `.omc/autopilot/cross-repo-pr-room-schema.md` exists; contains a `## Schema, verbatim` section AND an inline copy whose SHA256 matches the file at `proto/room_schema.json` at HEAD.
10. `tests/fixtures/golden/sabine_legacy_rt60_500hz.txt` exists; its first commit precedes the first commit that modifies `roomestim/reconstruct/materials.py` in this autopilot run (verified by `git log --reverse --format="%H %s" -- tests/fixtures/golden/sabine_legacy_rt60_500hz.txt roomestim/reconstruct/materials.py`).
11. `MaterialAbsorptionBands[m][2] == MaterialAbsorption[m]` for every material — asserted by `test_band_a500_matches_legacy_scalar` in workstream (d).
12. `proto/room_schema.json` validates the v0.1.1 fixture set at `tests/fixtures/lab_room.json` (and the writer's emission of it) with zero violations under v0.3 schema. Same for `proto/room_schema.draft.json`.
13. `tests/test_cli_idempotent.py` passes (A12 byte-equality preserved, possibly via `--legacy-single-band` flag — architect's call).
14. `RELEASE_NOTES_v0.2.md` AND `RELEASE_NOTES_v0.3.md` exist; both open with a one-paragraph headline; both contain a "Known limitations" section.
15. `docs/perf_verification_e2e_2026-05-06.md` exists; contains the verbatim string "This report is a CHARACTERISATION, not a pass/fail acceptance gate."
16. No `git push --tags`. Local tags `v0.2.0-rc` and `v0.3.0-rc` MAY be created; pushing them is human-gated. (Mirrors v0.1.1 closeout §8.)
17. `.omc/plans/decisions.md` contains new entries D11 (distribution-model decision rationale) and D12 (octave-band schema extension rationale).
18. `pyproject.toml` `[tool.pytest.ini_options].markers` registers BOTH `e2e` and `network` markers (line 42–45 region) with one-line description each.

If any criterion fails, the harness must STOP and surface the failure — do not paper over (mirrors `.omc/plans/v0.1.1-closeout.md` §8 stop-on-failure rule).

---

## 6. Out-of-scope for this autopilot run

- D2 Stage-2 schema flip — `__schema_version__` in `roomestim/__init__.py:4` stays `"0.1-draft"` (the strict file at `proto/room_schema.json` is updated for v0.3 octave-band but is NOT yet the writer's default — that's the D8-gated flip).
- A10 physical lab capture and the resulting `tests/fixtures/lab_real.usdz` + `tests/fixtures/lab_real_groundtruth.yaml` (post-autopilot human session per D8).
- A2 / A15 C++ harness binaries (D10 — engine team's v0.2 work).
- Distribution-model migration to PyPI or to a `spatial_engine/third_party/` submodule — v0.2 only RECORDS the decision in ADR 0007 and proposes the schema cross-repo. Actually publishing to PyPI / opening the spatial_engine PR is human work.
- COLMAP first-class promotion (ADR 0001 follow-up).
- Ambisonics placement (ADR 0003 follow-up).
- Vaulted / sloped ceiling per-zone `ceiling_height` extension (ADR 0002 falsifier).
- 8 kHz octave band — v0.3 ships 6 bands (125 → 4000 Hz). 8 kHz extension is v0.4 if engine reverb integration demands it.
- RT60 model upgrade (Eyring, Fitzroy, Arau-Puchades) beyond Sabine. v0.3 only adds per-band Sabine; non-Sabine models are v0.4+.
- COLMAP scale-anchor (ArUco / known-distance ref) — ADR 0001 v0.3 scope follow-up but NOT this autopilot run.
- Engine-side `RoomGeometry` C++ loader changes — explicitly the engine team's PR-2 follow-up.

---

## 7. Open decisions for the architect to lock

These are issues the analyst could not resolve from `.omc/plans/` alone. Each must be locked by the architect before the planner emits a phased TODO:

- [ ] **OD-1 (workstream c)**: Which option does ADR 0007 actually choose — (a) standalone, (b) submodule, (c) PyPI? The brief says "evidence-based decision". Evidence available right now: 0 real `room.yaml` files have been produced via lab capture (A10 not yet run); 0 cross-repo schema PR rounds since v0.1.1; CI maintenance hours unmeasured. The architect must either CHOOSE based on the precedent of vid2spatial / claude_text2traj (both standalone) or DEFER ADR 0007 to v0.3 with an "evidence not yet available" paragraph and ship workstream (c) as cross-repo PR draft only. — Why it matters: ADR 0007 is the headline deliverable of v0.2; if it's "TBD" the v0.2 ship is hollow.
- [ ] **OD-2 (workstream E2E)**: Which dataset wins the parallel Phase 0b ranking — dEchorate, MeshRIR, BUT ReverbDB, ARNI, OpenAIR, or MIT IR Survey? Required to fix the file paths `roomestim/adapters/<dataset_name>.py` and `tests/test_e2e_<dataset_name>_rt60.py`. — Why it matters: the spec is dataset-shape-agnostic but the implementation cannot be. Ranking criteria suggestion: must have (i) GT room geometry suitable for RoomModel construction, (ii) GT or readily-derivable material labels mappable to roomestim's 8-entry closed enum (D3), (iii) measured RIRs OR pre-computed measured RT60, (iv) a license that permits redistribution / academic use, (v) a published paper for citation in the report.
- [ ] **OD-3 (workstream d, CLI default)**: Should `roomestim ingest` / `roomestim run` emit the `absorption` octave block by default in v0.3? If YES: A12 byte-equality (CLI idempotency, `tests/test_cli_idempotent.py`) breaks unless we update the v0.1.1-shape golden — which itself is a v0.1.1-frozen artifact. If NO: the new feature ships dormant unless callers pass `--with-octave-band`. Architect must decide: byte-break A12 (with a NEW v0.3 idempotency golden replacing the implicit v0.1.1 one), or ship the feature behind an opt-in flag.
- [ ] **OD-4 (workstream d, table values)**: The `MaterialAbsorptionBands` rows in §3.3 are representative-but-unverified. Architect must either (a) cite Vorländer 2020 Appx A page numbers per row, (b) replace any unverifiable row with `(legacy_scalar,) * 6` and a TODO comment, or (c) defer the entire table to a separate per-row review session. — Why it matters: shipping fabricated coefficients silently is exactly the v0.1.1-closeout-Critic-M1 honesty failure mode the project rejected.
- [ ] **OD-5 (workstream c sequencing)**: Does v0.2 ship as its own commit + tag candidate before workstream (d) work begins, or is v0.2 + v0.3 a single autopilot commit history with two tag candidates? Implementation impact: if (former), there's a v0.2 → v0.3 inter-commit invariant that 63 v0.1.1 tests pass at the v0.2 commit AND at the v0.3 commit. If (latter), only the final state matters.
- [ ] **OD-6 (workstream E2E reproducibility)**: Does the test `tests/test_e2e_<dataset_name>_rt60.py` write the report markdown directly (option b in §4.5) or does the human capture the test's `-s` output and paste it into a hand-authored markdown (option a)? Option (b) is reproducible-CI-friendly but adds I/O coupling between the test and the docs tree.
- [ ] **OD-7 (workstream c, version stamp)**: `roomestim/__init__.py:3` reads `__version__ = "0.1.0"` even at v0.1.1. This is a pre-existing inconsistency with `pyproject.toml` (which correctly reads `0.1.1`). v0.2 must fix this OR keep the inconsistency for backwards-compat. The analyst recommends FIX (set `__version__ = "0.2.0"` in workstream c) on the grounds that A12 idempotency is computed at the YAML level, not via `__version__`, so no byte regression. Architect to confirm.
- [ ] **OD-8 (workstream d, schema range)**: 6 bands (125 → 4000 Hz) per the brief, vs the ADR 0005 follow-up text at line 52 "Octave-band absorption coefficients (125 Hz – 8 kHz)" which suggests 7 bands. Spec defaults to 6. Architect to confirm or expand to 7 (adds 8000 Hz column to `MaterialAbsorptionBands`, `OCTAVE_BANDS_HZ`, schema's `absorption` block).
- [ ] **OD-9 (workstream c + d, RELEASE_NOTES split)**: Two separate release-notes files (`RELEASE_NOTES_v0.2.md` + `RELEASE_NOTES_v0.3.md`) per OD-5 sequencing? Or a single `RELEASE_NOTES_v0.3.md` covering both workstreams (since v0.2 is a thin "ADR + cross-repo PR draft only" release)? Style precedent (`RELEASE_NOTES_v0.1.1.md`) says one file per release.
- [ ] **OD-10 (cross-repo PR safety)**: The cross-repo PR body in §2.5 is a draft; the architect must DECIDE whether autopilot's deliverable is the markdown file ALONE, or markdown file + a `gh pr create` invocation. Per "Do NOT touch spatial_engine source", the autopilot MUST stop at "markdown file delivered" and not invoke `gh` against the engine repo. Architect to confirm.

---

### Open Questions

- [ ] OD-1: ADR 0007 chosen distribution option — standalone / submodule / PyPI / defer to v0.3 — Why it matters: hollow v0.2 ship if unanswered.
- [ ] OD-2: Phase-0b dataset winner — fixes the adapter and test file paths in workstream (E2E).
- [ ] OD-3: v0.3 CLI default — does `roomestim ingest` emit the octave block by default? Affects A12 byte-equality.
- [ ] OD-4: Vorländer 2020 Appx A per-row citation policy for `MaterialAbsorptionBands`.
- [ ] OD-5: Sequencing — single autopilot commit history with two tag candidates, or separate v0.2 ship before v0.3 work begins.
- [ ] OD-6: E2E report generation — test writes markdown directly or human captures `-s` output.
- [ ] OD-7: `roomestim/__init__.py` `__version__` correction policy.
- [ ] OD-8: Octave bands 6 (125 → 4000) vs 7 (125 → 8000).
- [ ] OD-9: Single vs split RELEASE_NOTES file for v0.2 + v0.3.
- [ ] OD-10: Cross-repo PR delivery — markdown file only, or `gh pr create` against the engine repo.

---

*Spec authored 2026-05-06 by analyst (oh-my-claudecode autopilot Phase 0).
Predecessor: roomestim v0.1.1 (commit cd78c0d, 18/18 perf checks, 63/63 default-lane tests).*
