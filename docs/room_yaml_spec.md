# `room.yaml` Specification

> Source of truth: `proto/room_schema.json` (Stage 2 strict) and
> `proto/room_schema.draft.json` (Stage 1 permissive).
> See also [ADR 0004](adr/0004-room-yaml-schema-lockin.md) and
> [ADR 0002](adr/0002-room-representation.md).

---

## File Header

```yaml
version: "0.1-draft"   # Stage 1; becomes "0.1" after Stage-2 flip (human-gated)
name: "lab_room"       # Non-empty string; typically the scan filename stem
ceiling_height_m: 2.50 # Scalar, metres. Uniform ceiling only (vaulted → v0.3)
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `version` | string | yes | `"0.1-draft"` (Stage 1) or `"0.1"` (Stage 2) |
| `name` | string (≥1 char) | yes | Human-readable room identifier |
| `ceiling_height_m` | number > 0 | yes | Uniform ceiling height in metres |

---

## `floor_polygon`

A list of `Point2` objects ordered **counter-clockwise (CCW)** when viewed from above
(i.e., looking down the −y axis onto the floor plane). Units: metres.

```yaml
floor_polygon:
  - {x: 0.0, z: 0.0}
  - {x: 4.0, z: 0.0}
  - {x: 4.0, z: 3.0}
  - {x: 0.0, z: 3.0}
```

- **x** = right (metres from origin), **z** = front/depth (metres from origin).
- Minimum 3 points. No self-intersections.
- CCW orientation is enforced by `roomestim.model.canonicalize_ccw(polygon)`, which uses
  `shapely.geometry.Polygon.exterior.is_ccw` and reverses if clockwise.
- The polygon represents the floor boundary; walls are inferred by lifting each edge
  vertically to `ceiling_height_m` (see `roomestim/reconstruct/walls.py`).

---

## `listener_area`

Describes the region occupied by listeners. Speakers point toward the centroid by default.

```yaml
listener_area:
  centroid: {x: 2.0, z: 1.5}
  polygon:
    - {x: 1.5, z: 1.0}
    - {x: 2.5, z: 1.0}
    - {x: 2.5, z: 2.0}
    - {x: 1.5, z: 2.0}
  height_m: 1.20
```

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `centroid` | Point2 | yes | — | Centre of the listener region |
| `polygon` | list[Point2] | yes | — | CCW boundary of the listener region |
| `height_m` | number > 0 | no | `1.20` | Ear height above floor in metres |

---

## `surfaces`

An ordered list of surface objects. Each surface has a `kind`, `material`, optional
`absorption_500hz`, and a `polygon` (3-D vertices in listener-frame Cartesian coordinates).

### `kind` enum

| Value | Meaning |
|---|---|
| `wall` | Vertical planar surface (inferred from floor edges) |
| `floor` | Floor surface |
| `ceiling` | Ceiling surface |

### `material` enum and absorption table

Closed 8-entry enum per decisions.md D3. Absorption coefficients at 500 Hz (mid-band)
from Vorländer 2020, *Auralization*, Appendix A.

| `material` value | α₅₀₀ (absorption coefficient) |
|---|---|
| `wall_painted` | 0.05 |
| `wall_concrete` | 0.02 |
| `wood_floor` | 0.10 |
| `carpet` | 0.30 |
| `glass` | 0.04 |
| `ceiling_acoustic_tile` | 0.55 |
| `ceiling_drywall` | 0.10 |
| `unknown` | 0.10 (fallback) |

Source: `roomestim/model.py` — `MaterialLabel` enum and `MaterialAbsorption` dict.

Octave-band absorption (125 Hz – 8 kHz) is deferred to v0.3 per decisions.md D7.

### Surface polygon shape rules

- Walls: 4-vertex CCW rectangle `[bottom-left, bottom-right, top-right, top-left]` in
  listener-frame 3-D coordinates (x, y, z). y=0 is floor, y=ceiling_height_m is ceiling.
- Floor/Ceiling: same vertices as `floor_polygon` extruded to y=0 or y=ceiling_height_m.
- All polygons are CCW when viewed from **inside** the room.

```yaml
surfaces:
  - kind: floor
    material: carpet
    absorption_500hz: 0.30
    polygon:
      - {x: 0.0, y: 0.0, z: 0.0}
      - {x: 4.0, y: 0.0, z: 0.0}
      - {x: 4.0, y: 0.0, z: 3.0}
      - {x: 0.0, y: 0.0, z: 3.0}
  - kind: wall
    material: wall_painted
    absorption_500hz: 0.05
    polygon:
      - {x: 0.0, y: 0.0, z: 0.0}
      - {x: 4.0, y: 0.0, z: 0.0}
      - {x: 4.0, y: 2.5, z: 0.0}
      - {x: 0.0, y: 2.5, z: 0.0}
```

---

## Worked Example — Shoebox 4m × 3m × 2.5m

One carpeted floor and four painted walls (ceiling omitted for brevity).

```yaml
version: "0.1-draft"
name: "shoebox_example"
ceiling_height_m: 2.50

floor_polygon:
  - {x: 0.0, z: 0.0}
  - {x: 4.0, z: 0.0}
  - {x: 4.0, z: 3.0}
  - {x: 0.0, z: 3.0}

listener_area:
  centroid: {x: 2.0, z: 1.5}
  polygon:
    - {x: 1.5, z: 1.0}
    - {x: 2.5, z: 1.0}
    - {x: 2.5, z: 2.0}
    - {x: 1.5, z: 2.0}
  height_m: 1.20

surfaces:
  - kind: floor
    material: carpet
    absorption_500hz: 0.30
    polygon:
      - {x: 0.0, y: 0.0, z: 0.0}
      - {x: 4.0, y: 0.0, z: 0.0}
      - {x: 4.0, y: 0.0, z: 3.0}
      - {x: 0.0, y: 0.0, z: 3.0}
  - kind: wall
    material: wall_painted
    absorption_500hz: 0.05
    polygon:  # front wall (z=0)
      - {x: 0.0, y: 0.0, z: 0.0}
      - {x: 4.0, y: 0.0, z: 0.0}
      - {x: 4.0, y: 2.5, z: 0.0}
      - {x: 0.0, y: 2.5, z: 0.0}
  - kind: wall
    material: wall_painted
    absorption_500hz: 0.05
    polygon:  # right wall (x=4)
      - {x: 4.0, y: 0.0, z: 0.0}
      - {x: 4.0, y: 0.0, z: 3.0}
      - {x: 4.0, y: 2.5, z: 3.0}
      - {x: 4.0, y: 2.5, z: 0.0}
  - kind: wall
    material: wall_painted
    absorption_500hz: 0.05
    polygon:  # back wall (z=3)
      - {x: 4.0, y: 0.0, z: 3.0}
      - {x: 0.0, y: 0.0, z: 3.0}
      - {x: 0.0, y: 2.5, z: 3.0}
      - {x: 4.0, y: 2.5, z: 3.0}
  - kind: wall
    material: wall_painted
    absorption_500hz: 0.05
    polygon:  # left wall (x=0)
      - {x: 0.0, y: 0.0, z: 3.0}
      - {x: 0.0, y: 0.0, z: 0.0}
      - {x: 0.0, y: 2.5, z: 0.0}
      - {x: 0.0, y: 2.5, z: 3.0}
```

Sabine RT60 estimate for this room (single mid-band 500 Hz):
- Total surface area S ≈ 2(4×3) + 2(4×2.5) + 2(3×2.5) = 59 m²
- Mean absorption ᾱ ≈ (0.30×12 + 0.05×47) / 59 ≈ 0.10
- RT60 ≈ 0.161 × V / (S × ᾱ) = 0.161 × 30 / (59 × 0.10) ≈ 0.82 s

---

## Stage-1 vs Stage-2 Differences

| Aspect | Stage 1 (`"0.1-draft"`) | Stage 2 (`"0.1"`) |
|---|---|---|
| Schema file | `proto/room_schema.draft.json` | `proto/room_schema.json` |
| `version` const | `"0.1-draft"` | `"0.1"` |
| `additionalProperties` | `true` (extra keys silently accepted) | `false` (extra keys are validation errors) |
| When used | Autopilot ships this; default CI lane | After A10 lab capture + reviewer sign-off |

The flip is human-gated per decisions.md D8. See [ADR 0004](adr/0004-room-yaml-schema-lockin.md)
for the full checklist.

---

## Validation

roomestim validates `room.yaml` using `jsonschema.Draft202012Validator` from the
`jsonschema>=4` package.

**Where**: `roomestim/export/room_yaml.py` — called automatically at write time.

**How to invoke from CLI**:

```bash
python -m roomestim validate --schema stage1 room.yaml
python -m roomestim validate --schema stage2 room.yaml
```

**How to invoke in tests**:

```python
from roomestim.export.room_yaml import validate_room_yaml
validate_room_yaml(room_model)  # raises jsonschema.ValidationError on failure
```

**From pytest**: default lane (`pytest -m "not lab"`) covers Stage-1 validation;
Stage-2 validation runs in the lab lane (`pytest -m lab`) after the real fixture exists.
