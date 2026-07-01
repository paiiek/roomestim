"""tests/test_eyring_per_surface_alpha.py — v0.62.0 custom-α Eyring core fix.

ADR 0062. The Eyring RT60 branch (non-shoebox rooms + the ISM lower-bound
target) now derives α from per-surface ``absorption_500hz`` / ``absorption_bands``
instead of a ``MaterialLabel`` table lookup, so edited / adapter-divergent
materials affect RT60. Covers:

  (i)   a custom-α non-shoebox room yields a DIFFERENT, correct-direction RT60
        vs the same room at its label-table α;
  (ii)  a label non-shoebox room is BYTE-EQUAL to the pre-fix label-dict Eyring;
  (iii) per-band variant of both cases;
  (iv)  the empty / alpha_bar>=1 guards on the new helpers still raise.
"""
from __future__ import annotations

import dataclasses

import pytest

from roomestim.design.tradeoff import _surface_areas_by_material
from roomestim.geom.polygon import room_volume
from roomestim.model import (
    ListenerArea,
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    Point3,
    RoomModel,
    Surface,
)
from roomestim.reconstruct.materials import (
    eyring_rt60,
    eyring_rt60_from_pairs,
    eyring_rt60_per_band,
    eyring_rt60_per_band_from_pairs,
)
from roomestim.reconstruct.predictor import (
    is_rectilinear_shoebox,
    predict_rt60_default,
    predict_rt60_default_per_band,
)

_H = 3.0
# L-shaped (6-vertex → non-shoebox) floor polygon.
_FLOOR = [
    Point3(0.0, 0.0, 0.0),
    Point3(4.0, 0.0, 0.0),
    Point3(4.0, 0.0, 3.0),
    Point3(2.0, 0.0, 3.0),
    Point3(2.0, 0.0, 5.0),
    Point3(0.0, 0.0, 5.0),
]


def _wall(a: Point3, b: Point3, mat: MaterialLabel) -> Surface:
    return Surface(
        kind="wall",
        polygon=[
            Point3(a.x, 0.0, a.z),
            Point3(b.x, 0.0, b.z),
            Point3(b.x, _H, b.z),
            Point3(a.x, _H, a.z),
        ],
        material=mat,
        absorption_500hz=MaterialAbsorption[mat],
        absorption_bands=MaterialAbsorptionBands[mat],
    )


def _label_room() -> RoomModel:
    walls = [
        _wall(_FLOOR[i], _FLOOR[(i + 1) % len(_FLOOR)], MaterialLabel.WALL_PAINTED)
        for i in range(len(_FLOOR))
    ]
    floor = Surface(
        kind="floor",
        polygon=list(_FLOOR),
        material=MaterialLabel.WOOD_FLOOR,
        absorption_500hz=MaterialAbsorption[MaterialLabel.WOOD_FLOOR],
        absorption_bands=MaterialAbsorptionBands[MaterialLabel.WOOD_FLOOR],
    )
    ceil = Surface(
        kind="ceiling",
        polygon=[Point3(p.x, _H, p.z) for p in _FLOOR],
        material=MaterialLabel.CEILING_ACOUSTIC_TILE,
        absorption_500hz=MaterialAbsorption[MaterialLabel.CEILING_ACOUSTIC_TILE],
        absorption_bands=MaterialAbsorptionBands[MaterialLabel.CEILING_ACOUSTIC_TILE],
    )
    listener = ListenerArea(
        polygon=[
            Point3(0.5, 1.2, 0.5),
            Point3(1.5, 1.2, 0.5),
            Point3(1.5, 1.2, 1.5),
            Point3(0.5, 1.2, 1.5),
        ],
        centroid=Point3(1.0, 1.2, 1.0),
        height_m=1.2,
    )
    return RoomModel(
        name="L-label",
        floor_polygon=list(_FLOOR),
        ceiling_height_m=_H,
        surfaces=walls + [floor, ceil],
        listener_area=listener,
        objects=[],
    )


def test_label_room_is_non_shoebox() -> None:
    """The L-shaped fixture must route through the Eyring branch."""
    room = _label_room()
    assert is_rectilinear_shoebox(room) is False
    assert predict_rt60_default(room, _surface_areas_by_material(room)).predictor_name == "eyring"


def test_label_room_single_band_byte_equal() -> None:
    """(ii) A label non-shoebox room is byte-equal to the pre-fix label-dict Eyring."""
    room = _label_room()
    areas = _surface_areas_by_material(room)
    old = eyring_rt60(room_volume(room), areas)
    new = predict_rt60_default(room, areas).rt60_s
    assert new == old  # exact byte-equality, not approx


def test_label_room_per_band_byte_equal() -> None:
    """(iii) Per-band label room is byte-equal to the pre-fix label-dict Eyring."""
    room = _label_room()
    areas = _surface_areas_by_material(room)
    old = eyring_rt60_per_band(room_volume(room), areas)
    new = predict_rt60_default_per_band(room, areas).rt60_per_band_s
    assert new == old  # exact byte-equality, not approx


def test_custom_alpha_changes_single_band_rt60() -> None:
    """(i) A more-absorptive custom α shortens single-band Eyring RT60."""
    room = _label_room()
    areas = _surface_areas_by_material(room)
    base = predict_rt60_default(room, areas).rt60_s

    # Make the floor much more absorptive than its WOOD_FLOOR table α (0.10).
    surfaces = list(room.surfaces)
    floor_idx = next(i for i, s in enumerate(surfaces) if s.kind == "floor")
    surfaces[floor_idx] = dataclasses.replace(surfaces[floor_idx], absorption_500hz=0.9)
    room2 = dataclasses.replace(room, surfaces=surfaces)
    # The label-dict is unchanged (buckets by material → table α); the pre-fix
    # path would return `base`. The fix reads the per-surface α instead.
    custom = predict_rt60_default(room2, areas).rt60_s

    assert custom != base
    assert custom < base  # more absorption → shorter RT60


def test_custom_alpha_changes_per_band_rt60() -> None:
    """(iii) A more-absorptive custom per-band α shortens per-band Eyring RT60."""
    room = _label_room()
    areas = _surface_areas_by_material(room)
    base = predict_rt60_default_per_band(room, areas).rt60_per_band_s

    surfaces = list(room.surfaces)
    floor_idx = next(i for i, s in enumerate(surfaces) if s.kind == "floor")
    surfaces[floor_idx] = dataclasses.replace(
        surfaces[floor_idx],
        absorption_500hz=0.9,
        absorption_bands=(0.9, 0.9, 0.9, 0.9, 0.9, 0.9),
    )
    room2 = dataclasses.replace(room, surfaces=surfaces)
    custom = predict_rt60_default_per_band(room2, areas).rt60_per_band_s

    assert custom != base
    for band_hz in base:
        assert custom[band_hz] < base[band_hz]


def test_from_pairs_guards_raise() -> None:
    """(iv) The new helpers keep the empty / alpha_bar>=1 guards."""
    # Empty pairs → S_total == 0.
    with pytest.raises(ValueError, match="empty|zero|S_total"):
        eyring_rt60_from_pairs(56.0, [])
    with pytest.raises(ValueError, match="empty|zero|S_total"):
        eyring_rt60_per_band_from_pairs(56.0, [])
    # alpha_bar >= 1.0 (fully absorptive) → undefined.
    with pytest.raises(ValueError, match="alpha_bar"):
        eyring_rt60_from_pairs(56.0, [(10.0, 1.0)])
    with pytest.raises(ValueError, match="alpha_bar"):
        eyring_rt60_per_band_from_pairs(56.0, [(10.0, None, 1.0)])


def test_from_pairs_matches_label_dict_directly() -> None:
    """`eyring_rt60_from_pairs` reproduces `eyring_rt60` for grouped label pairs."""
    volume = 120.0
    areas = {
        MaterialLabel.WALL_PAINTED: 84.0,
        MaterialLabel.WOOD_FLOOR: 26.0,
        MaterialLabel.CEILING_ACOUSTIC_TILE: 26.0,
    }
    pairs = [(area, MaterialAbsorption[mat]) for mat, area in areas.items()]
    assert eyring_rt60_from_pairs(volume, pairs) == eyring_rt60(volume, areas)

    band_pairs = [
        (area, MaterialAbsorptionBands[mat], MaterialAbsorption[mat])
        for mat, area in areas.items()
    ]
    assert eyring_rt60_per_band_from_pairs(volume, band_pairs) == eyring_rt60_per_band(
        volume, areas
    )
