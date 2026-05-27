# ADR 0037 — `Object.wall_index` reference frame is walls-only

**Status**: Accepted (v0.19.0, 2026-05-28).
**Supersedes**: none. **Amends**: none.
**Related**: ADR 0034 (object schema), ADR 0028 (ISM adoption), D63, D64.

## Context

`Object.wall_index` (doors / windows attach to a host wall) was consumed in two
places that disagreed on its reference frame:

- **Predictor** (`reconstruct/predictor.py`): builds
  `base_walls = [s for s in room.surfaces if s.kind == "wall"]` and passes it to
  `_objects_to_wall_alpha_overrides`, which indexes `walls[wall_index]`. This is
  the **walls-only frame**.
- **Viewer** (`roomestim_web/viewer.py:_wall_attached_traces`): did
  `room.surfaces[obj.wall_index]` — the **full-surfaces frame**.

The adapter surface order is `[floor, *ceilings, *walls]`
(`adapters/roomplan.py`). So for any nonzero `wall_index` the two consumers
resolved to **different surfaces**: e.g. in `lab_room.json`
(`[floor, ceiling, wall, wall, wall, wall]`) `wall_index=2` was the THIRD wall
for the predictor but the FIRST wall (`surfaces[2]`) for the viewer; `wall_index=0`
was the first wall for the predictor but the FLOOR for the viewer. The
wall-attached door/window quad rendered against the wrong surface.

The schema (`proto/room_schema.v0_2.draft.json`) documented `wall_index` only as
a bare `integer ≥ 0 | null`, with no frame, leaving the ambiguity unresolved.

## Decision (D63)

`wall_index` is canonically **zero-based into the walls-only surface list**
(`[s for s in surfaces if s.kind == "wall"]`), NOT the full `surfaces` array.

The predictor already used this frame, so the canon is its existing behavior
(**zero acoustic-path edits, no RT60 re-baseline**). The viewer — the single
divergent consumer — was fixed to mirror it. The schema `wall_index` property
gained a `description` documenting the walls-only frame and pointing here.

## Alternatives considered

- **Full-surfaces frame** (make the predictor index `surfaces[wall_index]`):
  rejected. It would force a predictor change, re-baseline every RT60 golden
  that exercises an α override, and re-litigate the field's naming — all to move
  away from the more intuitive `wall_index → wall` mapping the name already
  implies.
- **Leave both as-is, document divergence**: rejected. The viewer geometry is
  observably wrong for any nonzero `wall_index`; that is a correctness defect,
  not a documentable quirk.

## Consequences

- Viewer wall-attached door/window quads render on the correct host wall for all
  `wall_index` values. Out-of-range still returns `[]` (robustness contract
  preserved — no new exception path).
- Schema documents the frame; future consumers have a single authority.
- Two regression tests lock the shared invariant (predictor and viewer pick the
  identical wall surface): `tests/test_wall_index_frame.py` (predictor side) and
  `tests/web/test_wall_index_viewer.py` (viewer side), both using a door at
  `wall_index=2` so the floor/ceiling-vs-wall divergence is observable.
- `MeshAdapter` `schema_version` unified to `0.2-draft` in the same cycle (D64),
  orthogonal to this frame decision.

## Follow-ups

None. `wall_index` semantics are now single-sourced.
