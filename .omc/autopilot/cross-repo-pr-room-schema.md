# [spatial_engine] Adopt roomestim's room_schema.json as engine-side proto/room_schema.json

## Summary

roomestim has shipped `proto/room_schema.json` (Stage-2 strict, Draft 2020-12) since v0.1.1,
and v0.3 extends it with an optional octave-band absorption block. This PR proposes adopting it
verbatim as `spatial_engine/proto/room_schema.json` so that the engine's RoomGeometry C++ loader
and roomestim's Python emitter validate against a single source of truth.

## Schema, verbatim

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://roomestim/proto/room_schema.json",
  "title": "RoomModel (Stage 2 LOCKED, strict)",
  "type": "object",
  "required": ["version", "name", "ceiling_height_m", "floor_polygon", "listener_area", "surfaces"],
  "additionalProperties": false,
  "properties": {
    "version": { "type": "string", "const": "0.1" },
    "name": { "type": "string", "minLength": 1 },
    "schema": { "type": "string", "format": "uri" },
    "ceiling_height_m": { "type": "number", "exclusiveMinimum": 0, "maximum": 30.0 },
    "floor_polygon": {
      "type": "array",
      "minItems": 3,
      "items": { "$ref": "#/$defs/point2" }
    },
    "listener_area": {
      "type": "object",
      "required": ["centroid", "polygon", "height_m"],
      "additionalProperties": false,
      "properties": {
        "centroid": { "$ref": "#/$defs/point2" },
        "polygon": {
          "type": "array",
          "minItems": 3,
          "items": { "$ref": "#/$defs/point2" }
        },
        "height_m": { "type": "number", "exclusiveMinimum": 0, "maximum": 3.0 }
      }
    },
    "surfaces": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["kind", "material", "absorption_500hz", "polygon"],
        "additionalProperties": false,
        "properties": {
          "kind": { "type": "string", "enum": ["wall", "floor", "ceiling"] },
          "material": {
            "type": "string",
            "enum": [
              "wall_painted",
              "wall_concrete",
              "wood_floor",
              "carpet",
              "glass",
              "ceiling_acoustic_tile",
              "ceiling_drywall",
              "unknown"
            ]
          },
          "absorption_500hz": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
          "polygon": {
            "type": "array",
            "minItems": 3,
            "items": { "$ref": "#/$defs/point3" }
          },
          "absorption": {
            "type": "object",
            "description": "Optional octave-band absorption coefficients (representative typical room-acoustics values; see roomestim/model.py:MaterialAbsorptionBands for citation policy). If absent, callers SHOULD fall back to absorption_500hz.",
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
    },
    "mount_surfaces": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["surface_index"],
        "additionalProperties": false,
        "properties": {
          "surface_index": { "type": "integer", "minimum": 0 },
          "inset_m": { "type": "number", "minimum": 0.0, "default": 0.10 }
        }
      }
    },
    "wfs_baseline_edge": {
      "type": "object",
      "required": ["surface_index", "t0", "t1"],
      "additionalProperties": false,
      "properties": {
        "surface_index": { "type": "integer", "minimum": 0 },
        "t0": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "t1": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
      }
    }
  },
  "$defs": {
    "point2": {
      "type": "object",
      "required": ["x", "z"],
      "additionalProperties": false,
      "properties": { "x": { "type": "number" }, "z": { "type": "number" } }
    },
    "point3": {
      "type": "object",
      "required": ["x", "y", "z"],
      "additionalProperties": false,
      "properties": {
        "x": { "type": "number" },
        "y": { "type": "number" },
        "z": { "type": "number" }
      }
    }
  }
}
```

SHA256: `057b534e816c70992c7237a4c8d54c9f4186ae436b38a6e310e714d4591f1085`

(Computed at roomestim v0.3 HEAD via `sha256sum proto/room_schema.json`.)

## What this PR proposes

- **ADD**: `spatial_engine/proto/room_schema.json` (verbatim from roomestim v0.3 above).
- **ADD**: a CMake/CI hook that runs jsonschema validation on every committed
  test fixture under `spatial_engine/configs/` that declares `version: "0.1"`.
- **NO C++ loader change in this PR**. The loader work is a follow-up PR
  authored by the engine team.

## Why now (drivers)

1. roomestim v0.1.1 shipped the Stage-1 draft schema; v0.3 adds the optional
   octave-band absorption block (backwards-compatible). Schema is now stable enough
   to propose cross-repo adoption.
2. The engine's RoomGeometry loader currently has no JSON-schema validation — adopting
   roomestim's schema gives the engine the same finite-leaf + enum-closed guarantees
   that roomestim's Python writer enforces (`roomestim/export/room_yaml.py`).
3. Early schema alignment prevents a future breaking schema version bump if the engine
   wants octave-band reverb data (D7 reverse criterion).

## Why this is NOT a Stage-2 flip

roomestim's Stage-2 flip (writer's default schema_version flips from `"0.1-draft"` to `"0.1"`,
i.e. `roomestim/__init__.py` `__schema_version__` changes) is a SEPARATE decision gated by
A10 lab capture per D8. This PR only proposes the schema FILE. The writer-side flip happens
later, independent of engine-team review timing.

## Backwards compat

Engine adopts the schema as a NEW file. No engine-side existing file changes.
roomestim continues to validate against its own copy at `/home/seung/mmhoa/roomestim/proto/`.
If the engine team merges this with edits, roomestim v0.4 will diff and re-sync.

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

---

**Note**: This file is a markdown draft. Opening the actual PR against spatial_engine is
human-gated (OD-10). The autopilot does NOT invoke `gh pr create` against the engine repo.

🤖 Drafted via roomestim v0.3 autopilot (2026-05-06)
