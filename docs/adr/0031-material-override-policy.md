# ADR 0031 — Material Override Policy + Acoustic Recompute Trigger

**Status**: Accepted (v0.16.0, 2026-05-18)
**Deciders**: paiiek
**References**: ADR 0002, ADR 0008, ADR 0009, ADR 0019, D39, D40, D43

---

## Context

`RoomModel` surfaces carry a `material: MaterialLabel` field whose absorption
coefficients are auto-assigned by the capture adapter (e.g. RoomPlan assigns
`WALL_PAINTED` to all walls because it cannot infer material from phone-scan
imagery). Through v0.15.2 there was no user-accessible path to correct
per-surface materials after ingest — users had to edit the raw YAML directly.

v0.16.0 introduces:
- `roomestim/edit.py` with `evolve_room` / `evolve_surface` / `evolve_room_material` /
  `evolve_room_materials_bulk` helper functions.
- Web Material Override Tab with an Apply button and surface table.

---

## §A Scope

Material override is limited to the closed `MaterialLabel` enum (ADR 0002 §3 +
ADR 0008 §A). Users select from the fixed set of 10 material labels via a
dropdown; arbitrary `absorption_500hz` float input is refused in v0.16.

When a material is changed, `absorption_500hz` and `absorption_bands` are
automatically looked up from `MaterialAbsorption` and `MaterialAbsorptionBands`
respectively. The user does not need to know (or supply) the numeric
coefficients.

The three core helpers:
- `evolve_surface(surf, *, material, polygon)` — single-surface mutation.
- `evolve_room(room, *, surfaces, listener_area, name)` — room-level mutation.
- `evolve_room_material(room, surface_index, material)` — convenience: one surface.
- `evolve_room_materials_bulk(room, changes: dict[int, MaterialLabel])` — atomic
  multi-surface change for the web Apply button.

All helpers return new instances; the input is never mutated.

---

## §B Trigger — Manual Apply Button (D40)

The acoustic recompute is triggered by an explicit **Apply** button in the web
UI, not by auto-debounce on dropdown change. Rationale: ISM cascade
(`predict_rt60_default`, max_order=50) takes ~1.9 s on the lab room; five rapid
dropdown changes would queue ~9.5 s of work. Manual Apply gives the user a
single commit point after all desired corrections are made.

Implementation: `_on_apply_overrides(room, changes_json)` in
`roomestim_web/material_override.py` → `evolve_room_materials_bulk` → 
`compute_acoustic_report` → updated `AcousticReport`.

---

## §C Invariant (D43)

After material change, the ADR 0009 runtime invariant must hold:

```
ism_rt60 >= eyring_rt60 - 1e-6
```

This is enforced by `tests/test_edit_room.py::test_evolve_room_material_shuffle_adr_0009_invariant`
(50 evolved rooms across 10 materials × 5 seeds). If the invariant is violated
for an extreme material combination, ADR 0009 envelope must be reconsidered
before shipping.

---

## §D RoomModel Frozen Invariant

`Surface` is `frozen=True` (ADR 0002 §Invariant). All helpers use
`dataclasses.replace` chain — never `object.__setattr__` hacks.

`RoomModel` itself uses bare `@dataclass` (mutable, not `frozen=True`) for
backward-compat with `PlacementResult` and existing adapters that set fields
post-construction. Evolve helpers always construct new instances by convention,
making the frozen invariant behaviorally preserved. Migrating `RoomModel` to
`frozen=True` is a v0.17+ candidate if audit confirms no callsite mutates in-place.

Regression lock: `tests/test_edit_room.py::test_evolve_room_frozen_invariant`
verifies `new_room.surfaces is not room.surfaces`.

---

## §E Reverse-criterion

Revert or extend this ADR when:
- ≥ 3 production users request arbitrary absorption coefficient input
  (e.g. acoustician-measured α values not in the lookup table).
- A production user reports the lookup table is systematically inaccurate for
  their room type.

Action: extend ADR 0008 envelope + add `Surface.absorption_500hz_override:
float | None` field (v0.17+ — schema_version bump to `"0.2-alpha-override"` if
the YAML schema changes).

---

## §References

- ADR 0002 — RoomModel shape invariants (`Surface` frozen, CCW polygon)
- ADR 0008 — Octave-band absorption (closed enum origin)
- ADR 0009 — ISM ≥ Eyring runtime invariant
- ADR 0019 — MELAMINE_FOAM precedent for envelope-extension cadence
- D39 — `roomestim/edit.py` placement decision
- D40 — Manual Apply trigger decision
- D43 — ADR 0009 invariant on evolved rooms (regression lock spec)
