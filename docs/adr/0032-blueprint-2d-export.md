# ADR 0032 — 2D Blueprint Export Policy

**Status**: Accepted (v0.16.0, 2026-05-18)
**Deciders**: paiiek
**References**: ADR 0024, ADR 0027, D41

---

## Context

Through v0.15.2 the Setup PDF contained only a 3D viewer screenshot (Plotly
Mesh3d). Architects, contractors, and integrators need a 2D top-down floor plan
(blueprint) showing wall labels, room dimensions, listener area, and speaker
positions for physical installation planning.

v0.16.0 adds `roomestim/viz/blueprint.py` with `render_blueprint()` exporting
PNG (300 dpi raster) and SVG (vector) blueprints. The web Blueprint Tab and
Setup PDF page 2 both consume this output.

---

## §A Scope

**Included in v0.16**:
- PNG 300 dpi raster export (`matplotlib.backends.backend_agg`).
- SVG vector export (scalable, CAD-import-ready).
- Content layers: floor outline, wall labels, listener area, speaker positions,
  dimension arrow (longest wall), north arrow, 1 m scale bar.

**Deferred to v0.17+**:
- Architectural standard symbols (door swing arc, window double line, column
  hatching). Requires symbol library or `ezdxf` dependency — ADR 0032
  §Status-update to be written when demand ≥ 2 users.
- DXF export (CAD-native format).

---

## §B Coordinate Convention (D41)

RoomModel internal frame: x=right, y=up, z=front (right-handed, per
`Point3` docstring). Top-down view projects the (x, z) plane.

**Chosen convention**: x → screen x, z → screen y with +z pointing upward
(north-up), matching architectural drawing convention (north at top of page).

```
blueprint x-axis  = RoomModel x  (right, m)
blueprint y-axis  = RoomModel z  (forward / north, m)
```

The result: the room entrance (z ≈ 0) appears at the bottom of the figure;
interior walls extend upward toward +z (north). `ax.set_ylabel("z (forward, m, north-up)")`
makes this explicit. `ax.invert_yaxis()` is NOT called — the mapping is direct.

**Rejected alternatives**:
- y-up screen (matplotlib default): violates architectural drawing convention.
- Absolute (lat, lon) mapping: phone-scan output is in room-local coordinates
  without world orientation; not applicable.

Regression lock: `tests/test_viz_blueprint.py::test_render_blueprint_coordinate_z_up`
verifies the ylabel substring `"z (forward"`.

---

## §C Content Layers

Per ADR 0032 §A scope, the following layers are rendered in order:

| Layer | Description |
|-------|-------------|
| 1 | Floor polygon outline — black, 1.5 pt linewidth |
| 2 | Wall labels W0/W1/… at edge midpoints — 7 pt DejaVu Sans |
| 3 | Listener area polygon — semi-transparent green fill α=0.3 |
| 4 | Speaker positions — red dots (6 pt) + channel label (L/R/C/LS/RS…) |
| 5 | Dimension arrow — longest wall edge + length annotation |
| 6a | North arrow — top-left corner, points toward +z |
| 6b | 1 m scale bar — bottom-right corner |

Each layer can be toggled via `show_dimensions`, `show_north_arrow`,
`show_scale_bar` keyword arguments.

---

## §D Determinism

`matplotlib.use("Agg")` is called before any rendering to enforce the headless
Agg backend regardless of display environment. Font: `DejaVu Sans` (ships with
matplotlib ≥ 3.0 — no extra installation). No random seeds used.

Result: PNG output is byte-equal across identical inputs on the same matplotlib
version. Regression lock: `tests/test_viz_blueprint.py::test_render_blueprint_determinism_png_byte_equal`.

If matplotlib is upgraded and byte equality breaks, degrade the lock to
hash-equality (sha256 of the decompressed PNG pixel data) and pin the matplotlib
version in `pyproject.toml`.

---

## §E Reverse-criterion

Revert or extend this ADR when:
- ≥ 2 users request architectural standard symbols (door swing, window line).
  Action: add symbol library or `ezdxf` optional dep; update §A scope.
- Byte-equal determinism lock breaks after a matplotlib minor upgrade.
  Action: pin matplotlib version or use hash-equality fallback.

---

## §References

- ADR 0024 — web-demo separate package (D29 lane separation)
- ADR 0027 — mesh format generalisation
- D41 — y-down screen ⇔ z-up world coordinate convention decision
- `roomestim/viz/blueprint.py` — implementation
- `roomestim/viz/floorplan_png.py` — predecessor (not deprecated in v0.16)
