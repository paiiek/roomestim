"""TASLP-derived MISC_SOFT surface budget — unit tests (v0.6).

Default-lane tests. Verify the per-piece equivalent absorption table, the
per-room furniture counts, the integrand-preserving area helper, the surface
synthesis (including the Lecture_2 strip-clip path), and the per-band band-2
↔ legacy-scalar invariant for the synthesised MISC_SOFT surface.
"""

from __future__ import annotations

import math

import pytest

from roomestim.adapters.ace_challenge import (
    _FURNITURE_BY_ROOM,
    _PIECE_EQUIVALENT_ABSORPTION_500HZ_M2,
    _PIECE_EQUIVALENT_ABSORPTION_BANDS_M2,
    _build_room_model,
    _furniture_to_misc_soft_area,
    _misc_soft_surface_from_furniture,
    ACE_ROOM_GEOMETRY,
)
from roomestim.model import (
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
)


# --------------------------------------------------------------------------- #
# Per-piece α table invariants
# --------------------------------------------------------------------------- #


def test_per_piece_500hz_matches_band_index_2() -> None:
    """Each per-piece band-tuple's index 2 (500 Hz) equals the 500 Hz scalar."""
    for piece, scalar in _PIECE_EQUIVALENT_ABSORPTION_500HZ_M2.items():
        assert piece in _PIECE_EQUIVALENT_ABSORPTION_BANDS_M2
        bands = _PIECE_EQUIVALENT_ABSORPTION_BANDS_M2[piece]
        assert len(bands) == 6
        assert bands[2] == pytest.approx(scalar)


# --------------------------------------------------------------------------- #
# Per-room exact-area assertions (closed-form)
# --------------------------------------------------------------------------- #


def test_office_1_has_4_office_chairs_at_0_50() -> None:
    """Office_1: 4 office chairs → 5.0 m² (4 * 0.50 / 0.40)."""
    area = _furniture_to_misc_soft_area({"office_chair": 4})
    assert area == pytest.approx(5.0)


def test_office_2_has_6_office_chairs_plus_bookcase() -> None:
    """Office_2: 6 office chairs + 1 bookcase → 8.25 m² ((6*0.50 + 1*0.30)/0.40)."""
    area = _furniture_to_misc_soft_area(_FURNITURE_BY_ROOM["Office_2"])
    expected = (6 * 0.50 + 1 * 0.30) / 0.40
    assert area == pytest.approx(expected)
    assert area == pytest.approx(8.25)


def test_meeting_1_has_14_office_chairs() -> None:
    """Meeting_1: 14 office chairs → 17.5 m² (14*0.50/0.40)."""
    area = _furniture_to_misc_soft_area(_FURNITURE_BY_ROOM["Meeting_1"])
    expected = 14 * 0.50 / 0.40
    assert area == pytest.approx(expected)
    assert area == pytest.approx(17.5)


def test_meeting_2_has_30_office_chairs_plus_6_tables() -> None:
    """Meeting_2: 30 office chairs + 6 tables → 39.0 m² ((30*0.50 + 6*0.10)/0.40)."""
    area = _furniture_to_misc_soft_area(_FURNITURE_BY_ROOM["Meeting_2"])
    expected = (30 * 0.50 + 6 * 0.10) / 0.40
    assert area == pytest.approx(expected)
    assert area == pytest.approx(39.0)


def test_lecture_1_has_60_lecture_seats_plus_20_tables() -> None:
    """Lecture_1: 60 lecture seats + 20 tables → 72.5 m² ((60*0.45 + 20*0.10)/0.40)."""
    area = _furniture_to_misc_soft_area(_FURNITURE_BY_ROOM["Lecture_1"])
    expected = (60 * 0.45 + 20 * 0.10) / 0.40
    assert area == pytest.approx(expected)
    assert area == pytest.approx(72.5)


def test_lecture_2_has_100_lecture_seats_plus_35_tables() -> None:
    """Lecture_2: 100 lecture seats + 35 tables → 121.25 m² ((100*0.45 + 35*0.10)/0.40)."""
    area = _furniture_to_misc_soft_area(_FURNITURE_BY_ROOM["Lecture_2"])
    expected = (100 * 0.45 + 35 * 0.10) / 0.40
    assert area == pytest.approx(expected)
    assert area == pytest.approx(121.25)


def test_furniture_to_misc_soft_area_unknown_piece_raises() -> None:
    """Unknown piece name raises KeyError."""
    with pytest.raises(KeyError):
        _furniture_to_misc_soft_area({"throne": 1})


# --------------------------------------------------------------------------- #
# Surface synthesis: Building_Lobby + unknown rooms return None
# --------------------------------------------------------------------------- #


def test_building_lobby_returns_none() -> None:
    """Building_Lobby is excluded by default (TASLP §II-C coupled-space)."""
    geom = ACE_ROOM_GEOMETRY["Building_Lobby"]
    surf = _misc_soft_surface_from_furniture(
        "Building_Lobby",
        (float(geom["L"]), float(geom["W"]), float(geom["H"])),
    )
    assert surf is None


def test_helper_returns_none_for_unknown_room() -> None:
    """Helper returns None for any room id not in _FURNITURE_BY_ROOM."""
    surf = _misc_soft_surface_from_furniture("Atrium_42", (5.0, 4.0, 3.0))
    assert surf is None


# --------------------------------------------------------------------------- #
# Surface synthesis: integrand preservation + strip-clip path
# --------------------------------------------------------------------------- #


def _newell_area_3d(pts) -> float:
    """Newell's polygon-area formula for a planar 3D polygon."""
    n = len(pts)
    nx = ny = nz = 0.0
    for i in range(n):
        j = (i + 1) % n
        nx += (pts[i].y - pts[j].y) * (pts[i].z + pts[j].z)
        ny += (pts[i].z - pts[j].z) * (pts[i].x + pts[j].x)
        nz += (pts[i].x - pts[j].x) * (pts[i].y + pts[j].y)
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def test_misc_soft_strip_clip_for_lecture_2() -> None:
    """Lecture_2 (R-3): √121.25 ≈ 11.01 > min(L=13.6, W=9.29) → strip-clip path.

    Polygon must (a) have area exactly 121.25 m² (Newell), (b) fit inside
    L × W (each side ≤ corresponding floor edge), and (c) carry MISC_SOFT
    material.
    """
    geom = ACE_ROOM_GEOMETRY["Lecture_2"]
    L = float(geom["L"])
    W = float(geom["W"])
    H = float(geom["H"])
    side_naive = math.sqrt(121.25)
    assert side_naive > min(L, W)  # confirms strip-clip path triggers

    surf = _misc_soft_surface_from_furniture("Lecture_2", (L, W, H))
    assert surf is not None
    assert surf.material == MaterialLabel.MISC_SOFT

    # Newell area equals expected exactly
    assert _newell_area_3d(surf.polygon) == pytest.approx(121.25, abs=1e-9)

    # Polygon stays within floor footprint
    xs = [p.x for p in surf.polygon]
    zs = [p.z for p in surf.polygon]
    assert max(xs) - min(xs) <= L + 1e-9
    assert max(zs) - min(zs) <= W + 1e-9


def test_misc_soft_strip_clip_for_lecture_1() -> None:
    """Lecture_1 (R-3): √72.5 ≈ 8.515 > min(L=6.93, W=9.73) = 6.93 → strip-clip path.

    Same R-3 mitigation as Lecture_2 above. Polygon must (a) have area
    exactly 72.5 m² (Newell) and (b) carry MISC_SOFT material.

    Footprint note: Lecture_1's MISC_SOFT area (72.5 m²) exceeds the floor
    rectangle (L*W = 67.43 m²), so the strip-clip cannot bound the polygon
    inside L × W simultaneously on both axes. The strip is laid out along
    the longer edge with `strip_long ≤ max(L, W)`; the orthogonal `other`
    side may exceed `min(L, W)` in this case. The synthetic polygon is a
    notional Sabine-budget surface, not a physical floor patch — the
    integrand-preservation invariant (Newell-area == 72.5 m² exact) is
    what matters acoustically.
    """
    geom = ACE_ROOM_GEOMETRY["Lecture_1"]
    L = float(geom["L"])
    W = float(geom["W"])
    H = float(geom["H"])
    side_naive = math.sqrt(72.5)
    assert side_naive > min(L, W)  # confirms strip-clip path triggers

    surf = _misc_soft_surface_from_furniture("Lecture_1", (L, W, H))
    assert surf is not None
    assert surf.material == MaterialLabel.MISC_SOFT

    # Newell area equals expected exactly
    assert _newell_area_3d(surf.polygon) == pytest.approx(72.5, abs=1e-9)

    # Strip's long axis is bounded by max(L, W) per the strip-clip invariant
    xs = [p.x for p in surf.polygon]
    zs = [p.z for p in surf.polygon]
    long_extent = max(max(xs) - min(xs), max(zs) - min(zs))
    assert long_extent <= max(L, W) + 1e-9


# --------------------------------------------------------------------------- #
# RoomModel surfaces wiring (6 → 7 for furniture-tracked rooms)
# --------------------------------------------------------------------------- #


def test_build_room_model_lecture2_has_misc_soft_surface() -> None:
    """Lecture_2 RoomModel surfaces include exactly one MISC_SOFT surface."""
    geom = ACE_ROOM_GEOMETRY["Lecture_2"]
    room = _build_room_model("Lecture_2", geom)
    misc = [s for s in room.surfaces if s.material == MaterialLabel.MISC_SOFT]
    assert len(misc) == 1
    other = [s for s in room.surfaces if s.material != MaterialLabel.MISC_SOFT]
    assert len(other) == 6  # 1 floor + 1 ceiling + 4 walls (unchanged)


def test_build_room_model_building_lobby_has_no_misc_soft_surface() -> None:
    """Building_Lobby RoomModel still has 6 surfaces (no MISC_SOFT)."""
    geom = ACE_ROOM_GEOMETRY["Building_Lobby"]
    room = _build_room_model("Building_Lobby", geom)
    misc = [s for s in room.surfaces if s.material == MaterialLabel.MISC_SOFT]
    assert len(misc) == 0
    assert len(room.surfaces) == 6


def test_building_lobby_absent_from_furniture_dict() -> None:
    # Future maintainers must not silently add Building_Lobby to the dict —
    # the coupled-space exclusion is a deliberate v0.6 decision (ADR 0013 §OQ-9).
    assert "Building_Lobby" not in _FURNITURE_BY_ROOM


# --------------------------------------------------------------------------- #
# Per-band invariant for the synthesised MISC_SOFT surface
# --------------------------------------------------------------------------- #


def test_band_index_2_equals_legacy_scalar_for_synthesized_misc_soft_surface() -> None:
    """The synthesised Surface carries the canonical MISC_SOFT band tuple
    whose index 2 (500 Hz) equals the legacy scalar — extends the global
    invariant `MaterialAbsorptionBands[m][2] == MaterialAbsorption[m]` to
    the runtime-emitted surface object.
    """
    geom = ACE_ROOM_GEOMETRY["Lecture_1"]
    surf = _misc_soft_surface_from_furniture(
        "Lecture_1",
        (float(geom["L"]), float(geom["W"]), float(geom["H"])),
    )
    assert surf is not None
    assert surf.absorption_bands is not None
    assert len(surf.absorption_bands) == 6
    assert surf.absorption_bands[2] == surf.absorption_500hz
    assert surf.absorption_500hz == MaterialAbsorption[MaterialLabel.MISC_SOFT]
    assert surf.absorption_bands == MaterialAbsorptionBands[MaterialLabel.MISC_SOFT]


# --------------------------------------------------------------------------- #
# v0.11 MELAMINE_FOAM enum extension (ADR 0019)
# --------------------------------------------------------------------------- #


def test_melamine_foam_a500_in_expected_range() -> None:
    """MaterialAbsorption[MELAMINE_FOAM] is in the Vorländer 2020 §11 / Appx A
    typical-2-to-4-inch-panel envelope (planner-locked: 0.80 ≤ α₅₀₀ ≤ 0.95).

    Guards against silent coefficient drift outside the ADR 0019 envelope.
    A future verbatim Vorländer lookup may tighten this bracket; the
    envelope-band assertion is the v0.11 honesty-marker contract.
    """
    value = MaterialAbsorption[MaterialLabel.MELAMINE_FOAM]
    assert 0.80 <= value <= 0.95, (
        f"MELAMINE_FOAM α₅₀₀ = {value} outside Vorländer 2020 §11 / Appx A "
        f"envelope [0.80, 0.95]; ADR 0019 §References must be revisited "
        f"before re-shipping."
    )
