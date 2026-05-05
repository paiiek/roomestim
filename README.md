# roomestim

Capture-to-config tool. Phone room-scan (Apple RoomPlan / Polycam / COLMAP fallback) → simplified
`RoomModel` + algorithm-aware speaker placement → engine-ready `layout.yaml` (validated against
`spatial_engine/proto/geometry_schema.json`) plus a new proposed `room.yaml`.

- **Status**: v0.1.1 — closes phase-offset gap and characterises DBAP under noise; A10 lab capture pending (post-autopilot human gate per D8). See `RELEASE_NOTES_v0.1.1.md`.
- **Precision target**: cm-grade — walls ±10 cm, speaker angles ±2–5°, RT60 ±20%. NOT BIM precision.
- **Coordinate frame**: VBAP layout-frame (`spatial_engine/docs/coordinate_convention.md`) — listener
  at origin, x=right, y=up, z=front, metres. RIGHT = +az_deg, UP = +el_deg.
- **Sibling repo (read-only at v0.1)**: `/home/seung/mmhoa/spatial_engine/`.

## Capture backends

| Backend | Status | Notes |
|---|---|---|
| Apple RoomPlan | first-class | LiDAR metric scale; USDZ + JSON sidecar. See [ADR 0001](docs/adr/0001-capture-backend-priority.md). |
| Polycam | supported | Mesh-only; cross-platform (Android, non-Pro iPhone). |
| COLMAP | experimental | Scale-ambiguous; requires `[colmap]` extra + `--experimental` flag. |

## Quickstart

```bash
pip install -e .[dev]

python -m roomestim run \
    --backend roomplan \
    --input tests/fixtures/lab_room.usdz \
    --algorithm vbap --n-speakers 8 --layout-radius 2.0 \
    --out-dir /tmp/roomestim_out

pytest -m "not lab" -v
```

## Repo layout

```
roomestim/        # package source
proto/            # JSON Schema for room.yaml (Stage 1 draft + Stage 2 locked)
tests/            # pytest, fixtures, hypothesis property tests
docs/             # architecture, room_yaml_spec, ADRs
.omc/plans/       # design plan, decisions log, open questions
```

## Placement API (v0.1.1 additions)

Optional kwargs added in v0.1.1 (defaults preserve v0.1 byte-for-byte):

```python
from roomestim.place.vbap import place_vbap_ring, place_vbap_dome

# Single equal-angle ring with phase offset (deg). Default 0.0 = v0.1.
place_vbap_ring(n=8, radius_m=2.0, el_deg=0.0, phase_offset_deg=-135.0)

# Stacked dome, two independent ring offsets [lower, upper]. Default None ≡ [0.0, 0.0].
place_vbap_dome(
    n_lower=4, n_upper=4,
    radius_m=1.0,
    phase_offsets_deg=[-135.0, -135.0],
    layout_name="lab_8ch_aligned",
)
```

See `RELEASE_NOTES_v0.1.1.md` for the cross-repo `regularity_hint` caveat
on the dome path.

## Phase status

| Phase | Description | Status |
|---|---|---|
| P0 | Repo bootstrap, coords port, ADR stubs | done |
| P1 | RoomModel + CaptureAdapter protocol + room.yaml export | done |
| P2 | layout.yaml export + engine round-trip | done |
| P3 | VBAP + DBAP placement | done |
| P4 | RoomPlan adapter + reconstruction | done |
| P5 | WFS placement + Polycam adapter | done |
| P6 | CLI, viz, lab acceptance gate | done |
| P7 | Docs and ADR finalization | done |

## Attach to spatial_engine

v0.1 ships standalone; cross-repo PR proposing `room.yaml` upstream lands in v0.2 after the lab
fixture has produced ≥1 real `room.yaml` and the schema has been exercised. See
`.omc/plans/decisions.md` (D1, D2) for rationale.
