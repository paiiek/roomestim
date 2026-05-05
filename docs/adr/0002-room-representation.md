# ADR 0002 — Internal room representation

- **Status**: Accepted (finalized 2026-05-04)
- **Date**: 2026-05-03
- **Cross-ref**: design plan §2.3 Q2.

## Context

The internal `RoomModel` is the only stable abstraction across capture adapters. Three
representations were considered: 2.5D polygon + scalar ceiling, axis-aligned shoebox,
polygon + textured mesh.

## Decision

**2.5D polygon + scalar `ceiling_height_m`** plus a list of `Surface` annotations referencing
polygon edges + ceiling/floor. Mesh is optional sidecar (`room.glb`) for visualization only;
the engine never reads it.

## Drivers

1. Most exhibition venues are NOT shoeboxes (L-shapes, alcoves common).
2. Cheap to compute (project mesh to floor → polygonize via shapely).
3. Maps cleanly to a future `RoomGeometry` C++ struct as a uniform array of polygonal surfaces.

## Alternatives

- **Shoebox-only**: rejected. Failure mode is silent (wrong reflections, wrong placement).
- **Polygon + textured mesh**: rejected for v0.1. Scope creep; not needed for placement.

## Consequences

- (+) Captures non-shoebox rooms (L-shape, alcoves).
- (+) `room.yaml` schema stays simple (2D floor + scalar height).
- (−) Vaulted / sloped ceilings deferred to v0.3 (non-uniform `ceiling_height` per polygon zone).

## Falsifier

If after v0.1, ≥3/10 captured rooms have non-uniform ceilings that require manual editing,
re-open the choice in v0.2.

## Follow-ups

- `docs/room_yaml_spec.md` documents the 2.5D contract (done — P7).
- Vaulted/sloped ceiling extension trigger: if ≥3/10 captures need manual ceiling edits, introduce per-zone `ceiling_height` in v0.2 (cross-ref Falsifier above).
