# Real Apple RoomPlan `CapturedStructure` export fixtures

These two JSON files are genuine Apple RoomPlan `CapturedStructure` exports
(device LiDAR scans, `CapturedStructure`/`CapturedRoom` `Encodable` serialization),
used as test fixtures for roomestim's real-export ingest path.

- `capturedstructure_multiroom.json` — 4 sections (2 bedrooms, bathroom, unidentified);
  20 walls / 4 doors / 4 windows / 13 objects / 1 floor.
- `capturedstructure_single.json` — 1 section (livingRoom).

## Source & license
- Source: https://github.com/theLodgeBots/open3dFloorplan (`static/` + repo root).
- License: **MIT** (https://github.com/theLodgeBots/open3dFloorplan/blob/main/LICENSE).
  Copyright (c) theLodgeBots. Redistributed here under the MIT License with attribution.
- Acquired 2026-06-17. Real-vs-synthetic verification in
  `.omc/research/roomplan-real-export-acquisition.md`.
