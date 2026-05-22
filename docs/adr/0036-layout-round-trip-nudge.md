# ADR 0036 — Layout round-trip + speaker nudge policy

**Status**: Accepted (v0.18.0, 2026-05-22).
**Supersedes**: none. **Amends**: none.
**Related**: ADR 0002 (Point3 frame), ADR 0024 (web separate package), ADR 0029
§Cross-lane (web→core single direction), ADR 0031 (evolve_room pattern), ADR 0033
(engine validation toggle — D42 reuse), D48 / D49 / D50 / D51 / D52.

## Context

Through v0.17.0 the roomestim data flow was one-directional read-only: phone-scan
→ RoomModel (editable: materials/objects) → placement algorithm →
`PlacementResult` → `layout.yaml` write. Once `layout.yaml` was written there was
no path to read its speaker coordinates back, fine-tune them, and re-write. A
user who received an auto-placement (e.g. a VBAP ring) and wanted a manual tweak
("move speaker 3 five degrees right", "shrink the whole radius by 0.2 m") had to
hand-edit YAML, with no way to re-check that the result still satisfied the
engine schema (`geometry_schema.json`: min_speaker_count, finite sweep,
az/x mutual exclusion).

The skeleton design assumed a new module `roomestim/load_layout.py`. That was
wrong: parsing (`read_placement_yaml`) and serialization (`write_layout_yaml`)
already exist. A planner code run also confirmed that `read_placement_yaml`
**drops** `aim_direction` and `notes`, and infers only WFS-vs-VBAP from
`regularity_hint` + the `x_wfs_f_alias_hz` key — so DBAP/AMBISONICS collapse to
"VBAP" on read. Position is structurally preserved (az/el/dist → cartesian →
az/el/dist within ~1e-9).

## §A — Module strategy (D48)

No new module. Round-trip is reader + edit + writer:
`read_placement_yaml(p)` → `nudge_speaker(r, ...)` → `write_layout_yaml(r2, p2)`.
The reader is augmented to restore aim (§C); `roomestim/edit.py` gains
`evolve_placement` / `nudge_speaker` (§B). Rejected: a new `load_layout.py`
(duplicates reader/writer, DRY/D29 violation) and a wholesale
`roomestim/layout/` package merge (out of scope, import-path regression risk).

## §B — Nudge API (D49)

`evolve_placement(result, *, speakers, regularity_hint, layout_name)` mirrors
`evolve_room` (frozen-respecting, `dataclasses.replace`, shallow-copied speakers
list, finite-validated positions and aim).

`nudge_speaker(result, speaker_index, *, daz_deg, del_deg, ddist_m, dx, dy, dz)`
applies a spherical Δ (az/el/dist) XOR a Cartesian Δ (xyz). Supplying both
non-zero frames raises `ValueError` — the frame ordering would otherwise be
ambiguous. All conversion goes through `roomestim.coords` (the single sign-flip
authority); the nudge code never calls trigonometry directly. A non-positive
resulting distance raises `ValueError`; an out-of-range index raises
`IndexError`.

Web UI granularity: az/el step 1°, dist step 0.05 m, Cartesian step 0.05 m. CLI
accepts arbitrary float (user responsibility). Snap-to-grid is a non-goal.

## §C — Round-trip fidelity (D50)

**Level 1** ({VBAP, WFS} only): `read(write(r)) == r` holds for position (≤1e-9),
channel, regularity, `wfs_f_alias_hz` (≤1e-9), and aim direction (reader-restored).
`target_algorithm` is preserved only for {VBAP, WFS}; a result whose
`target_algorithm ∈ {DBAP, AMBISONICS}` reads back as "VBAP", so the label is
explicitly excluded from the contract (OQ-38). `notes` and per-speaker `id` are
excluded — no engine-schema slot (notes = OQ-37; id is regenerated from channel).

**Aim restore branch-switch (HIGH-1)**: the writer **always** emits
`x_aim_az_deg`/`x_aim_el_deg` — toward-origin default when `aim_direction is None`
(`layout_yaml.py` None branch), explicit otherwise. After the reader restores aim,
every re-write takes the explicit branch. The two writes are byte-equal because
aim carries direction only and `coords.cartesian_to_pipeline`'s atan2-based az/el
is scale-invariant (a unit-vector restore is sufficient). This is the
**aim** fixed point.

**Numerical note (position dist_m)**: position `dist_m` is *not* universally a
single-iteration fixed point — for non-axis-aligned azimuths (e.g. 120°) the
cartesian↔spherical cycle drifts by ~1 ULP per round-trip and converges after a
few iterations. Byte-equal idempotency gates therefore use axis-aligned fixtures
(az ∈ {0,90,180,270}°, el=0, integer radius), which are genuine single
write→read→write fixed points. Editing UX does not require byte-equal (Level 1
structural equivalence is sufficient); the broader CLI/web edit path is unaffected.

**Export bug repair framing (HIGH-2)**: D50 does more than enable nudge — it
repairs a pre-existing `roomestim export` aim silent-corruption bug. Before D50,
`_cmd_export` read a placement whose aim was `None`, so the writer recomputed a
toward-origin default; a user's explicit `x_aim_az_deg: 0.0` was silently
transformed (e.g. to `-135.0`) on re-export. default-restore (not opt-in) is
adopted precisely to repair this, and the export byte-gates (acceptance Gate 22
default-aim regression + Gate 23 explicit-aim FIX) seal it as a regression-locked
contract rather than prose.

**Partial aim key (Fix 7a)**: when exactly one of `x_aim_az_deg`/`x_aim_el_deg`
is present the aim cannot be reconstructed from a single axis, so the reader
treats it as missing (`aim_direction = None`). Both keys are required.

## §D — Re-validation after edit

`validate_placement(result, *, schema_path_override=None) -> list[str]` is a
**non-raising collector** (MED-1): it never calls `write_layout_yaml` and never
alters the writer's raise path. The writer keeps its order-sensitive 5-step
sequence and typed raises (`ValueError`/`ValidationError`) for safety; the
collector independently re-checks R10 (min_speaker_count) + R11 (finite sweep) +
the Draft 2020-12 engine schema and returns issue strings ([] = valid) for
CLI/web UX. The schema path-join is consolidated into the `_resolve_schema_file`
helper (third copy; v0.15.1/v0.15.2 geom-util precedent). Web shows a red error;
CLI exits 1. D42 precedence (CLI flag > ENV > default ON) is reused.

## §E — Schema invariance (D52)

`__schema_version__` stays "0.2-draft". It versions the **RoomModel**
(`room.yaml`) serialization; v0.18 edits **`layout.yaml`** (engine
`geometry_schema.json`, its own `version: "1.0"` label), which is orthogonal to
the RoomModel schema (ADR 0029 / D29). v0.18 adds/changes no RoomModel field, so
no bump. `PlacementResult.layout_version` ("1.0") is likewise unchanged.

## §F — Byte-equal round-trip is a non-goal (D51)

Byte-equal (comment + key-order + float-format preservation) would require
`ruamel.yaml` round-trip mode and replacing `write_layout_yaml`'s
`yaml.safe_dump` — a new dependency, broad writer regression, and re-validation
of the dict-based schema path against ruamel `CommentedMap`. Edit UX does not
need it; Level 1 (structural equivalence) is sufficient. Core keeps
`yaml.safe_dump` as the single serialization authority.

## §G — Reverse-criterion

- (i) User requests group transform (whole-ring scale) ≥ 2 times → add a
  `scale_layout` helper + ADR 0036 §Status-update.
- (ii) `layout.yaml` hand-written comment preservation requested ≥ 2 times →
  reverse D51 (ruamel ADR).
- (iii) Engine schema adds a required per-speaker metadata field (e.g. `gain_db`)
  → decide a `PlacedSpeaker` field extension.
- (iv) `notes` round-trip requested ≥ 1 time → OQ-37 → engine `x_notes`
  extension consultation.

## Consequences

- New public API: `evolve_placement`, `nudge_speaker` (`roomestim.edit`),
  `validate_placement` (`roomestim.export`).
- `read_placement_yaml` now restores `aim_direction` (signature unchanged; the
  returned PlacementResult's aim is populated instead of always `None`). This
  also fixes the `roomestim export` aim-corruption bug.
- New CLI subcommand `roomestim edit`; new web "스피커 조정" tab (web
  0.14-web.0 → 0.15-web.0).
- `PlacedSpeaker` / `PlacementResult` stay frozen-respecting (all edits via
  `dataclasses.replace`); D29 lane separation preserved (web → core only).
