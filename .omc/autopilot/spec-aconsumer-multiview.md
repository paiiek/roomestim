# Autopilot spec — A-consumer placement wiring + multiview point-cloud ingest

Source: PLACEMENT_SENSITIVITY_VERDICT.md (spike-vggt-multiview). Working dir: /home/seung/mmhoa/roomestim.

## Findings that drive scope (vs the mature roomestim codebase)
- Footprint front-ends ALREADY exist (`--floor-reconstruction convex|concave|occupancy|auto|robust`).
- `place_dbap` ALREADY mounts speakers ON the room's surfaces (on-surface by construction).
- The MeshAdapter **rejects points-only PLY** (`mesh.py` ~690) → **point-cloud ingest is the real gap** (Task 2).
- Verdict: ceiling height is **unrecoverable from rough cloud** (cloud z-range 1-2 m vs 2.3-5.3 m GT) →
  the real new product lever is a **user-supplied ceiling-height override** (Task 1a).
- Verdict mitigation "snap-to-surface" → useful as a **layout post-processor** that snaps placed
  speakers onto the room's mount surfaces (for edited/imported/drifted layouts) (Task 1b).

## Task 1 — A-consumer placement levers (additive, low-risk)
### 1a. User ceiling-height override
- New `roomestim/edit.py::evolve_room_ceiling_height(room, height_m) -> RoomModel`:
  rebuilds ceiling surface (lift polygon to new y) + walls (new height) consistently; floor unchanged;
  preserves materials/octave bands; sets `ceiling_confidence="high"`, `ceiling_coverage=None`.
- CLI: `--ceiling-height-m FLOAT` on `ingest` and `run`; applied after adapter.parse(). Bounded (>0, ≤20).
### 1b. Snap layout to surfaces (install-time mitigation)
- New `roomestim/edit.py::snap_layout_to_surfaces(room, result) -> PlacementResult`:
  each PlacedSpeaker.position → nearest point on any wall/ceiling Surface (clamped 3D point-to-polygon).
  New helper `roomestim/geom/surface_distance.py::closest_point_on_surface(point, surface)`.
- CLI: `place --snap-to-surfaces`.

## Task 2 — Multiview point-cloud adapter
- New `roomestim/adapters/multiview.py::MultiviewAdapter(CaptureAdapter)`:
  ingests a reconstructed **point cloud** (.ply points-only, .npz with points array, .xyz/.txt) →
  RoomModel by reusing `MeshAdapter._extract_room_model(points, ...)` (same footprint/ceiling/walls/listener).
- Marks `provenance="reconstructed"`; ceiling from a ceiling-less rough cloud is low-confidence →
  recommend pairing with `--ceiling-height-m`. Optional `ceiling_height_m` constructor arg.
- VGGT frames→cloud reconstruction is OUT OF SCOPE (GPU dep) — adapter ingests the cloud.
- CLI: `ingest --backend multiview` (+ existing `--floor-reconstruction`, new `--ceiling-height-m`).

## Verification
- New unit tests: ceiling-override, snap-to-surfaces, multiview ingest (.ply/.npz/.xyz) on synthetic clouds.
- Full `pytest` suite stays green.

## Out of scope
- VGGT frames→cloud reconstruction (upstream/GPU). Real-acoustics sim. Web UI changes.
