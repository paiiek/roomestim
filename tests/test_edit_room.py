"""tests/test_edit_room.py — roomestim.edit helpers (v0.16.0 / D39 + D43).

Covers:
  - evolve_surface: material-only change → absorption auto-lookup.
  - evolve_surface: polygon-only change → material unchanged.
  - evolve_room: surfaces replace → listener_area preserved.
  - evolve_room_material: out-of-range index → IndexError with "valid range".
  - evolve_room_materials_bulk: multi-surface atomic change.
  - evolve_room frozen invariant: new surfaces list instance.
  - ADR 0009 ISM ≥ Eyring invariant on 50 evolved rooms (D43 regression lock).
  - canonicalize_ccw preserved after evolve.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from roomestim.edit import (
    evolve_room,
    evolve_room_material,
    evolve_room_materials_bulk,
    evolve_surface,
)
from roomestim.model import (
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    RoomModel,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def lab_room() -> RoomModel:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    from roomestim.adapters.roomplan import RoomPlanAdapter
    room = RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)
    assert isinstance(room, RoomModel)
    return room


# --------------------------------------------------------------------------- #
# Test cases
# --------------------------------------------------------------------------- #


def test_evolve_surface_material_only(lab_room: RoomModel) -> None:
    """Material change → absorption_500hz and absorption_bands auto-lookup."""
    surf = lab_room.surfaces[0]
    new_surf = evolve_surface(surf, material=MaterialLabel.GLASS)

    assert new_surf.material == MaterialLabel.GLASS
    assert new_surf.absorption_500hz == MaterialAbsorption[MaterialLabel.GLASS]
    assert new_surf.absorption_bands == MaterialAbsorptionBands[MaterialLabel.GLASS]
    # polygon is unchanged
    assert new_surf.polygon == surf.polygon
    # kind is unchanged
    assert new_surf.kind == surf.kind


def test_evolve_surface_polygon_only(lab_room: RoomModel) -> None:
    """Polygon-only change keeps material and absorption identical."""
    surf = lab_room.surfaces[0]
    new_polygon = list(surf.polygon)  # same vertices, new list
    new_surf = evolve_surface(surf, polygon=new_polygon)

    assert new_surf.material == surf.material
    assert new_surf.absorption_500hz == surf.absorption_500hz
    assert new_surf.absorption_bands == surf.absorption_bands


def test_evolve_room_surfaces_replace(lab_room: RoomModel) -> None:
    """Replacing surfaces leaves listener_area byte-equal."""
    new_surfaces = list(lab_room.surfaces)
    new_room = evolve_room(lab_room, surfaces=new_surfaces)

    # listener_area is the same object (not copied)
    assert new_room.listener_area is lab_room.listener_area
    assert new_room.name == lab_room.name
    assert len(new_room.surfaces) == len(lab_room.surfaces)


def test_evolve_room_material_index_out_of_range(lab_room: RoomModel) -> None:
    """surface_index=99 → IndexError with 'valid range' in message."""
    with pytest.raises(IndexError, match="valid range"):
        evolve_room_material(lab_room, 99, MaterialLabel.GLASS)


def test_evolve_room_materials_bulk(lab_room: RoomModel) -> None:
    """Bulk change {0: GLASS, 2: CARPET} — only those two surfaces change."""
    changes = {0: MaterialLabel.GLASS, 2: MaterialLabel.CARPET}
    new_room = evolve_room_materials_bulk(lab_room, changes)

    assert new_room.surfaces[0].material == MaterialLabel.GLASS
    assert new_room.surfaces[2].material == MaterialLabel.CARPET
    # All other surfaces remain byte-equal
    for i, (orig, new) in enumerate(zip(lab_room.surfaces, new_room.surfaces)):
        if i not in changes:
            assert new.material == orig.material, f"surface {i} should be unchanged"


def test_evolve_room_frozen_invariant(lab_room: RoomModel) -> None:
    """evolve_room returns a new surfaces list instance (not aliased)."""
    assert dataclasses.is_dataclass(lab_room)
    new_room = evolve_room(lab_room)
    # New surfaces list is a distinct object
    assert new_room.surfaces is not lab_room.surfaces


def test_evolve_room_material_shuffle_adr_0009_invariant(lab_room: RoomModel) -> None:
    """D43 regression lock: ISM >= Eyring - 1e-6 on evolved rooms (50 random seeds).

    10 MaterialLabel values × 5 seeds = 50 instances, each with one random
    surface set to a random material. Checks ADR 0009 invariant on all.
    """
    import random

    from roomestim.geom.polygon import polygon_area_3d
    from roomestim.reconstruct.predictor import (
        predict_rt60_default,
    )

    materials = list(MaterialLabel)
    n_surfaces = len(lab_room.surfaces)

    for seed in range(5):
        rng = random.Random(seed)
        for mat in materials:
            idx = rng.randint(0, n_surfaces - 1)
            evolved = evolve_room_material(lab_room, idx, mat)

            from collections import defaultdict
            areas: dict[object, float] = defaultdict(float)
            for s in evolved.surfaces:
                areas[s.material] += polygon_area_3d(s.polygon)
            area_dict = dict(areas)

            pred_ism = predict_rt60_default(evolved, area_dict, prefer_ism=True)
            pred_eyr = predict_rt60_default(evolved, area_dict, prefer_ism=False)

            assert pred_ism.rt60_s >= pred_eyr.rt60_s - 1e-6, (
                f"ADR 0009 violated: seed={seed}, surface={idx}, mat={mat.value}, "
                f"ISM={pred_ism.rt60_s:.4f} < Eyring={pred_eyr.rt60_s:.4f} - 1e-6"
            )


def test_evolve_room_canonicalize_ccw_preserved(lab_room: RoomModel) -> None:
    """floor_polygon CCW invariant is preserved after evolve (re-canonicalized)."""
    from shapely.geometry import Polygon as ShapelyPolygon

    new_room = evolve_room(lab_room)
    new_fp = new_room.floor_polygon

    # evolve_room now calls canonicalize_ccw → new list, not same reference
    assert isinstance(new_fp, list)

    # Verify CCW
    coords = [(p.x, p.z) for p in new_fp]
    if len(coords) >= 3:
        shp = ShapelyPolygon(coords)
        assert shp.exterior.is_ccw, "floor_polygon should be CCW after evolve"


def test_evolve_room_re_canonicalizes_floor_polygon(lab_room: RoomModel) -> None:
    """evolve_room with a CW floor_polygon override produces a CCW result (HIGH-2).

    Constructs a reversed (CW) version of the floor_polygon via dataclasses.replace
    directly on the room (bypassing evolve), then calls evolve_room — which must
    re-canonicalize back to CCW.
    """
    import dataclasses as dc
    from shapely.geometry import Polygon as ShapelyPolygon

    orig_fp = lab_room.floor_polygon
    if len(orig_fp) < 3:
        pytest.skip("floor_polygon too short to test CW/CCW")

    # Check original orientation
    orig_coords = [(p.x, p.z) for p in orig_fp]
    orig_ccw = ShapelyPolygon(orig_coords).exterior.is_ccw

    # Reverse the polygon to get the opposite winding
    cw_fp = list(reversed(orig_fp))
    # Directly set on room (bypassing evolve to simulate a bad input)
    cw_room = dc.replace(lab_room, floor_polygon=cw_fp)

    # Now evolve_room must re-canonicalize
    new_room = evolve_room(cw_room)
    new_coords = [(p.x, p.z) for p in new_room.floor_polygon]
    new_ccw = ShapelyPolygon(new_coords).exterior.is_ccw

    # Result must be CCW regardless of input winding
    assert new_ccw, (
        f"evolve_room must canonicalize floor_polygon to CCW; "
        f"orig_ccw={orig_ccw}, after_evolve_ccw={new_ccw}"
    )
