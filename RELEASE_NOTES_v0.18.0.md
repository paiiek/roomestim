# roomestim v0.18.0 — speaker nudge + layout round-trip

MINOR bump `0.17.0` → `0.18.0`. See ADR 0036 and ADR 0030 §Status-update-v0.18.

## What v0.17.0 missed

The data flow was one-directional read-only: scan → RoomModel → placement →
`layout.yaml` write. There was no path to read a written `layout.yaml`, fine-tune
a speaker, and re-write it with re-validation. Worse, `read_placement_yaml`
dropped `aim_direction`, which meant the shipped `roomestim export` had a silent
aim-corruption bug: an explicit `x_aim_az_deg: 0.0` was recomputed to a
toward-origin default (e.g. `-135.0`) on re-export.

## What v0.18.0 adds

- `roomestim.edit.evolve_placement(...)` — frozen-respecting PlacementResult
  evolve (mirrors `evolve_room`).
- `roomestim.edit.nudge_speaker(...)` — nudge one speaker by a spherical Δ
  (az/el/dist) XOR a Cartesian Δ (xyz); mixing the two frames raises ValueError;
  all conversion goes through `roomestim.coords`.
- `roomestim.export.validate_placement(...)` — non-raising validation collector
  (R10 + R11 + engine schema) returning a list of issue strings for CLI/web UX.
  The writer's raise path is untouched.
- `read_placement_yaml` now restores `aim_direction` from
  `x_aim_az_deg`/`x_aim_el_deg`. This also repairs the `roomestim export`
  aim-corruption bug.
- CLI `roomestim edit --in-placement layout.yaml --speaker N (--daz | --del-deg |
  --ddist | --dx | --dy | --dz) --out-dir DIR` → read → nudge → re-validate →
  write + unified diff.
- Web "스피커 조정" tab (channel select + 6 Δ inputs + Apply → re-validate →
  3D viewer rebuild). Speaker markers carry `customdata=[channel]`.

## What stays the same

- RoomModel `room.yaml` schema `0.2-draft` (`__schema_version__`) unchanged —
  v0.18 edits `layout.yaml` (engine schema, `version: "1.0"`), orthogonal to the
  RoomModel schema (D52).
- `PlacedSpeaker` / `PlacementResult` stay frozen-respecting (all edits via
  `dataclasses.replace`).
- `write_layout_yaml`'s 5-step order, typed raises, and byte output are
  unchanged (`validate_placement` is an independent collector).
- ADR 0009 ISM ≥ Eyring invariant / ADR 0030 cascade are untouched (placement
  editing does not touch the RT60 prediction path).

## Round-trip fidelity

| Preserved (Level 1, {VBAP, WFS}) | Excluded |
|---|---|
| position (≤1e-9) | `notes` (no schema slot — OQ-37) |
| channel | per-speaker `id` (regenerated from channel) |
| regularity_hint | DBAP/AMBISONICS `target_algorithm` label (reads as "VBAP" — OQ-38) |
| `wfs_f_alias_hz` (≤1e-9) | comment / key order / float format (D51 — byte-equal non-goal) |
| aim direction (reader-restored, ≤1e-9) | |

Byte-equal idempotency holds for axis-aligned layouts (az ∈ {0,90,180,270}°,
el=0, integer radius), which are single write→read→write fixed points. Other
azimuths drift ~1 ULP in `dist_m` per cycle and converge after a few iterations;
this does not affect editing UX, which relies on Level 1 structural equivalence.

## Migration note

`read_placement_yaml` now returns a populated `aim_direction` instead of always
`None`. Code that relied on the previous always-`None` behaviour should review
the change. `notes` and per-speaker `id` round-trip is still unsupported (OQ-37 /
channel regeneration). DBAP/AMBISONICS layouts read back with `target_algorithm`
collapsed to "VBAP" (OQ-38).

## Test count

| Lane | Before | After |
|---|---|---|
| default (`-m "not lab and not web"`) | 232 | 260 (+28) |
| web (`tests/web/`) | 66 | 70 (+4) |

New modules: `tests/test_edit_placement.py` (8), `tests/test_layout_round_trip.py`
(10), `tests/test_cli_edit.py` (6), `tests/test_export_round_trip.py` (4),
`tests/web/test_speaker_nudge_ui.py` (4).

## Tag

Local-only. The user tags/commits separately.
