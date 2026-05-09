"""ACE Challenge corpus adapter — E2E GT-dataset reader for RT60 characterisation.

This adapter is NOT a CaptureAdapter (phone-scan → RoomModel pipeline).
It reads pre-tabulated T60 values from user-supplied CSV files and constructs
synthetic RoomModel objects from the published ACE Challenge room geometry table.

Dataset citation
----------------
Eaton, J., Gaubitch, N. D., Moore, A. H., & Naylor, P. A. (2016).
Estimation of room acoustic parameters: The ACE Challenge.
IEEE/ACM Transactions on Audio, Speech, and Language Processing, 24(10), 1681–1693.
https://dl.acm.org/doi/10.1109/TASLP.2016.2577502 (institutional access)

Open-access supporting material: arXiv:1606.03365 (Table 1 used as the
dimensional source-of-truth at v0.5; see in-module caveats below). Material
assignments (walls / ceiling) are not in the canonical published paper —
Eaton 2016 TASLP final was reviewed at v0.5.1 (cover-to-cover; institutional
access); §II-C "Rooms" gives only floor-type + furniture counts, not walls
or ceiling. TASLP §II-C furniture counts are now wired through to a synthetic
MISC_SOFT surface per room (v0.6; see ADR 0013). See ADR 0012 for the
walls/ceiling audit closure.

Corpus Zenodo mirror: https://zenodo.org/records/6257551 (CC-BY-ND 4.0)

Usage
-----
- Set ROOMESTIM_E2E_DATASET_DIR to a local directory containing:
    - ace_corpus_t60.csv       (header: room_id,band_hz,t60_s)
    - ace_corpus_t60_500hz.csv (header: room_id,t60_500hz_s)
- Neither file is distributed with roomestim (CC-BY-ND dataset — no redistribution
  of processed derivatives without author permission).
- The tests/fixtures/ace_challenge_sample/ directory contains PLACEHOLDER values
  for unit testing only — NOT real ACE measurements.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from roomestim.model import (
    ListenerArea,
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
)

# --------------------------------------------------------------------------- #
# Published ACE room geometry table
# Source: ACE Challenge corpus, Imperial College London EEE building, 7 rooms.
#
# Honesty caveats (Critic M1 precedent):
# - Dimensions (L, W, H): VERIFIED byte-for-byte against arXiv:1606.03365
#   Table 1 (TASLP supporting material; open access; transcribed 2026-05-06).
#   See `tests/fixtures/ace_eaton_2016_table_i_arxiv.csv` and the gated audit
#   `tests/test_ace_geometry_audit.py`. Office_2 was patched at v0.5.0
#   (W 3.50 → 3.22, H 3.00 → 2.94) — the only numerical correction in v0.5.0.
# - Material assignments (`floor`, `walls`, `ceiling`): partial cross-check at
#   v0.5.1. Eaton 2016 TASLP final was reviewed cover-to-cover (institutional
#   access) on 2026-05-07; §II-C "Rooms" (p.1683) gives only floor-type
#   ("carpeted" / "hard-floored") + furniture counts. Walls and ceiling
#   assignments are not in the canonical published paper — `wall_painted`,
#   `wall_concrete`, `ceiling_drywall`, `ceiling_acoustic_tile` strings below
#   are best-guess and remain INDETERMINATE (not "TASLP-blocked"). 4/7 floors
#   are BYTE-CONFIRMED at TASLP §II-C: Office_1, Office_2, Meeting_1,
#   Meeting_2 → `carpet`. The other 3 are "hard-floored" (compatible with
#   `wood_floor` but subtype unspecified). See ADR 0012 for the audit closure.
# - TASLP §II-C furniture counts are wired into a synthesised MISC_SOFT
#   surface per furniture-tracked room at v0.6 (see ADR 0013 +
#   `_FURNITURE_BY_ROOM` / `_misc_soft_surface_from_furniture` below).
#   Building_Lobby is intentionally excluded from this surface budget per
#   ADR 0013 §3 OQ-9 (coupled-space caveat below).
# - L/W convention: roomestim keeps "longer dimension as L" for adapter
#   consistency. arXiv 1606.03365 Table 1 lists Office_1 / Office_2 /
#   Building_Lobby with the shorter dimension first; products and V_m³ are
#   identical to the arXiv ordering. Only Office_2 dimensional drift
#   (W=3.50 → W=3.22, H=3.00 → H=2.94) was a real numerical bug; the L/W
#   swap on Office_1 / Building_Lobby is product-equivalent and not patched.
# - Building_Lobby modelling caveat (TASLP §II-C, v0.5.1): the lobby is
#   "large irregular-shaped hard-floored room with coupled spaces including
#   a café, stairwell and staircase. Measurements in Table I correspond to
#   the corner area where the recordings were made whereas the total volume
#   of the lobby is many times larger." `ACE_ROOM_GEOMETRY["Building_Lobby"]`
#   shoebox of 72.9 m³ describes the recording corner, not the room. Sabine
#   RT60 prediction on a non-shoebox coupled space is not expected to match
#   measurement; the v0.4 perf doc's +1.425 s err Sabine on Building_Lobby
#   is consistent with a modelling-assumption violation, not (only) a
#   coefficient/material gap.
# - The runtime adapter does not validate these against the user's
#   dataset_dir contents — only the per-band T60 values are read from the
#   user's CSVs (which raise FileNotFoundError if absent).
# --------------------------------------------------------------------------- #

ACE_ROOM_GEOMETRY: dict[str, dict[str, object]] = {
    "Office_1": {
        "L": 4.83,
        "W": 3.32,
        "H": 2.95,
        "floor": "carpet",
        "walls": "wall_painted",
        "ceiling": "ceiling_drywall",
    },
    "Office_2": {
        "L": 5.10,
        "W": 3.22,
        "H": 2.94,
        "floor": "carpet",
        "walls": "wall_painted",
        "ceiling": "ceiling_drywall",
    },
    "Meeting_1": {
        "L": 6.61,
        "W": 5.11,
        "H": 2.95,
        "floor": "carpet",
        "walls": "wall_painted",
        "ceiling": "ceiling_acoustic_tile",
    },
    "Meeting_2": {
        "L": 10.30,
        "W": 9.07,
        "H": 2.63,
        "floor": "carpet",
        "walls": "wall_painted",
        "ceiling": "ceiling_acoustic_tile",
    },
    "Lecture_1": {
        "L": 6.93,
        "W": 9.73,
        "H": 3.00,
        "floor": "wood_floor",
        "walls": "wall_painted",
        "ceiling": "ceiling_drywall",
    },
    "Lecture_2": {
        "L": 13.60,
        "W": 9.29,
        "H": 2.94,
        "floor": "wood_floor",
        "walls": "wall_painted",
        "ceiling": "ceiling_acoustic_tile",
    },
    "Building_Lobby": {
        "L": 5.13,
        "W": 4.47,
        "H": 3.18,
        "floor": "wood_floor",
        "walls": "wall_concrete",
        "ceiling": "ceiling_drywall",
    },
}

# String label → MaterialLabel enum mapping for the ACE geometry table
_MATERIAL_MAP: dict[str, MaterialLabel] = {
    "carpet": MaterialLabel.CARPET,
    "wood_floor": MaterialLabel.WOOD_FLOOR,
    "wall_painted": MaterialLabel.WALL_PAINTED,
    "wall_concrete": MaterialLabel.WALL_CONCRETE,
    "ceiling_drywall": MaterialLabel.CEILING_DRYWALL,
    "ceiling_acoustic_tile": MaterialLabel.CEILING_ACOUSTIC_TILE,
}


# --------------------------------------------------------------------------- #
# Per-piece equivalent absorption (TASLP §II-C-derived MISC_SOFT budget; v0.6)
# --------------------------------------------------------------------------- #
#
# Per-piece equivalent absorption A_i (m² Sabines per item) at 500 Hz mid-band
# and per octave band. Cited from textbook tables (fair-use; ADR 0012 IP
# guidance):
#   - "office_chair": empty upholstered office chair
#       (Vorländer 2020 *Auralization* §11 Appx A "upholstered seating, empty"
#       row; cross-checked Beranek 2004 *Concert Halls and Opera Houses*
#       Ch.3 Table 3.1 "unoccupied upholstered concert seats" row)
#       → A_500 ≈ 0.50 m² Sabines/chair
#   - "stacking_chair": wood/plastic stacking chair
#       (Vorländer 2020 §11 Appx A "wooden chair" row; representative for
#       hard-shell stacking seats)
#       → A_500 ≈ 0.15 m² Sabines/chair
#   - "lecture_seat": theatre/lecture seat, empty (upholstered base + back)
#       (Beranek 2004 Ch.3 Table 3.1 "unoccupied theatre/lecture seats" row;
#       cross-checked Vorländer 2020 §11 Appx A theatre-seating row)
#       → A_500 ≈ 0.45 m² Sabines/chair
#   - "table": large flat table (per piece, conservative; tables usually
#       contribute negligibly above 250 Hz — included for ledger
#       completeness)
#       (Vorländer 2020 §11 Appx A "large hard table" representative)
#       → A_500 ≈ 0.10 m² Sabines/table
#   - "bookcase": filled bookcase
#       (Vorländer 2020 §11 Appx A "books on shelf" / Beranek 2004
#       Ch.3 row equivalent)
#       → A_500 ≈ 0.30 m² Sabines/bookcase
#
# Per-band profile: each row mirrors the MISC_SOFT band-tuple shape
# (rising mid-to-high) scaled to the row's 500 Hz value.
#
# Honesty marker (M1 / D12 precedent): values are representative-not-verbatim.
# Specific table rows / page numbers are recorded in
# .omc/plans/v0.6-design.md §3 OQ-6 (locked) and ADR 0013 §References.
# Reverse-trigger: a textbook re-read or author lookup surfaces a value that
# differs by > 30% on any band → re-read this dict and ADR 0013.

_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2: dict[str, float] = {
    "office_chair":   0.50,
    "stacking_chair": 0.15,
    "lecture_seat":   0.45,
    "table":          0.10,
    "bookcase":       0.30,
}

_PIECE_EQUIVALENT_ABSORPTION_BANDS_M2: dict[
    str, tuple[float, float, float, float, float, float]
] = {
    # Bands: (125, 250, 500, 1000, 2000, 4000) Hz. Profile mirrors MISC_SOFT
    # rising-mid-to-high shape, scaled to per-piece 500 Hz value.
    "office_chair":   (0.25, 0.375, 0.50, 0.625, 0.75, 0.8125),
    "stacking_chair": (0.075, 0.1125, 0.15, 0.1875, 0.225, 0.24375),
    "lecture_seat":   (0.225, 0.3375, 0.45, 0.5625, 0.675, 0.73125),
    "table":          (0.05, 0.075, 0.10, 0.125, 0.15, 0.1625),
    "bookcase":       (0.15, 0.225, 0.30, 0.375, 0.45, 0.4875),
}


# --------------------------------------------------------------------------- #
# Per-room TASLP §II-C furniture counts (factual data; not copyrightable)
# --------------------------------------------------------------------------- #
#
# Source: Eaton 2016 TASLP §II-C "Rooms" (p.1683), reviewed cover-to-cover
# at v0.5.1; recorded durably in project memory `project_taslp_2016_content.md`.
#
# Building_Lobby is intentionally excluded — TASLP §II-C describes it as
# "irregular shape with coupled spaces"; ACE_ROOM_GEOMETRY shoebox is the
# recording corner only. Adding a furniture-budget MISC_SOFT surface to a
# non-shoebox room compounds modelling error. See §3 OQ-9 + ADR 0012
# Building_Lobby caveat.
#
# Mapping rationale (lecture-seat ↔ office-chair distinction):
#   - Office_1 / Office_2: typical workplace office chairs → "office_chair"
#   - Meeting_1 / Meeting_2: typical meeting-room chairs (mixed upholstered)
#     → "office_chair" as the closer fit (Vorländer 2020 §11 has no separate
#     "meeting chair" row; Beranek 2004 reserves "lecture seat" for
#     fixed-back theatre seating)
#   - Lecture_1 / Lecture_2: fixed theatre-style lecture seating
#     → "lecture_seat" (Beranek 2004 Ch.3 Table 3.1)
#
# Furniture mapping is a planner-locked decision; reverse-trigger via §3 OQ-7.

_FURNITURE_BY_ROOM: dict[str, dict[str, int]] = {
    "Office_1":   {"office_chair":   4},
    "Office_2":   {"office_chair":   6, "bookcase": 1},
    "Meeting_1":  {"office_chair":  14},
    "Meeting_2":  {"office_chair":  30, "table": 6},
    "Lecture_1":  {"lecture_seat":  60, "table": 20},
    "Lecture_2":  {"lecture_seat": 100, "table": 35},
    # Building_Lobby intentionally absent — see ADR 0012 + §3 OQ-9.
}


def _furniture_to_misc_soft_area(furniture: dict[str, int]) -> float:
    """Return synthetic MISC_SOFT surface area (m²) for a furniture inventory.

    The adapter does NOT model individual chairs as separate Surface objects.
    Instead it emits one synthetic MISC_SOFT surface whose AREA is chosen so
    that the Sabine integrand `area * MaterialAbsorption[MISC_SOFT]` equals
    the sum of per-piece equivalent absorption (Σ count_i * A_i).

    Formula (preserves Sabine integrand at 500 Hz):
        area_misc_soft = Σ_pieces count_i * A_500_i / a_misc_soft_500

    With ``MaterialAbsorption[MISC_SOFT] == 0.40`` (v0.5.0 row), this scales
    the per-piece sum to a notional surface area at the 500 Hz reference
    band. Per-band Sabine and Eyring then operate per the MISC_SOFT band
    tuple (which itself is representative-not-verbatim; see model.py).
    The per-band integrand is exactly preserved (by construction; per-piece
    bands mirror the MISC_SOFT band-tuple shape scaled to the per-piece
    500 Hz reference, so Σ count·piece_band[i] = area · MISC_SOFT_band[i]
    is an algebraic identity).

    Parameters
    ----------
    furniture:
        Mapping ``piece_name -> count``. Piece names must be keys of
        ``_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2``.

    Returns
    -------
    float
        Synthetic MISC_SOFT surface area in m² (≥ 0).

    Raises
    ------
    KeyError
        If any piece in ``furniture`` is not in
        ``_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2``.
    ValueError
        If ``MaterialAbsorption[MISC_SOFT]`` is non-positive (defensive).
    """
    a_misc_soft = MaterialAbsorption[MaterialLabel.MISC_SOFT]
    if a_misc_soft <= 0.0:
        raise ValueError("MaterialAbsorption[MISC_SOFT] must be > 0")
    total_eq_abs = 0.0
    for piece, count in furniture.items():
        a_i = _PIECE_EQUIVALENT_ABSORPTION_500HZ_M2[piece]
        total_eq_abs += count * a_i
    return total_eq_abs / a_misc_soft


def _misc_soft_surface_from_furniture(
    room_id: str,
    room_dimensions: tuple[float, float, float],
) -> Surface | None:
    """Build a synthetic MISC_SOFT Surface for ``room_id``, or None if absent.

    The synthetic surface has a square or thin-strip polygon laid out in the
    floor plane (y=0). The polygon coordinates are NOT geometrically
    meaningful — only the polygon area is consumed by
    ``_surface_areas_by_material(...)`` for Sabine / Eyring.

    Returns ``None`` when ``room_id`` is not in ``_FURNITURE_BY_ROOM``
    (e.g. ``Building_Lobby`` per §3 OQ-9, or any unknown room ID). The
    caller (``_build_room_model``) skips appending a None.

    Strip-clip path (R-3): when the requested square side √area exceeds
    ``min(L, W)``, the surface is laid out as a strip along the longer floor
    edge so the integrand is preserved while keeping the polygon inside
    ``L × W``.

    Parameters
    ----------
    room_id:
        ACE Challenge room identifier.
    room_dimensions:
        ``(L, W, H)`` in metres; only ``L`` and ``W`` are used.

    Returns
    -------
    Surface | None
        A ``Surface(material=MaterialLabel.MISC_SOFT, kind="floor", ...)``
        with Newell-area equal to ``_furniture_to_misc_soft_area(...)``,
        or ``None`` if the room has no furniture entry.
    """
    if room_id not in _FURNITURE_BY_ROOM:
        return None
    furniture = _FURNITURE_BY_ROOM[room_id]
    area = _furniture_to_misc_soft_area(furniture)
    if area <= 0.0:
        return None

    L, W, _H = room_dimensions
    side = math.sqrt(area)
    if side <= min(L, W):
        # Square inside floor, near origin corner
        x0, x1 = 0.0, side
        z0, z1 = 0.0, side
    else:
        # Strip along longer edge; clip to fit inside L × W
        long_side = max(L, W)
        short_side = min(L, W)
        # If even the full strip is too long, cap the long side; the polygon
        # is still axis-aligned with Newell-area = strip_long * other.
        strip_long = min(area / short_side, long_side)
        other = area / strip_long
        if L >= W:
            x0, x1 = 0.0, strip_long
            z0, z1 = 0.0, other
        else:
            x0, x1 = 0.0, other
            z0, z1 = 0.0, strip_long

    band_tuple = MaterialAbsorptionBands[MaterialLabel.MISC_SOFT]
    return Surface(
        kind="floor",  # adapter convention — surface lies in floor plane
        polygon=[
            Point3(x0, 0.0, z0),
            Point3(x1, 0.0, z0),
            Point3(x1, 0.0, z1),
            Point3(x0, 0.0, z1),
        ],
        material=MaterialLabel.MISC_SOFT,
        absorption_500hz=MaterialAbsorption[MaterialLabel.MISC_SOFT],
        absorption_bands=band_tuple,
    )


def _misc_soft_surface_from_furniture_with_alpha(
    room_id: str,
    room_dimensions: tuple[float, float, float],
    alpha_500: float,
    alpha_bands: tuple[float, float, float, float, float, float],
) -> Surface | None:
    """Sibling of ``_misc_soft_surface_from_furniture`` with explicit α values.

    Used by the v0.8 Scope-A bracketing harness (see ADR 0015) to construct a
    per-variant MISC_SOFT surface where the seat (and other furniture)
    equivalent absorption is computed against a *supplied* 500 Hz scalar α and
    6-band tuple, rather than the library default
    ``MaterialAbsorption[MISC_SOFT]`` / ``MaterialAbsorptionBands[MISC_SOFT]``.

    The library defaults remain byte-equal when this function is not called
    (the default code path in ``_build_room_model(overrides=None)`` uses
    ``_misc_soft_surface_from_furniture`` unchanged). This sibling is
    intentionally additive and never mutates module-level state.

    The synthetic surface area is computed so the Sabine integrand at 500 Hz
    is preserved against the supplied ``alpha_500`` (i.e.
    ``area * alpha_500 == Σ_pieces count_i * A_500_i``), rather than against
    the library MISC_SOFT scalar. The surface stores the supplied
    ``alpha_500`` and ``alpha_bands`` directly so the per-band predictor sees
    the per-variant α.

    Parameters
    ----------
    room_id:
        ACE Challenge room identifier (must be in ``_FURNITURE_BY_ROOM``).
    room_dimensions:
        ``(L, W, H)`` in metres; only ``L`` and ``W`` are used.
    alpha_500:
        The 500 Hz scalar absorption coefficient to use (replacing
        ``MaterialAbsorption[MISC_SOFT]``).
    alpha_bands:
        The 6-band absorption tuple at (125, 250, 500, 1000, 2000, 4000) Hz
        (replacing ``MaterialAbsorptionBands[MISC_SOFT]``).

    Returns
    -------
    Surface | None
        Same shape as ``_misc_soft_surface_from_furniture(...)`` but with the
        supplied ``alpha_500`` / ``alpha_bands`` written into the Surface, and
        Newell-area scaled to preserve the Sabine integrand at 500 Hz against
        ``alpha_500`` rather than ``MaterialAbsorption[MISC_SOFT]``. Returns
        ``None`` if the room has no furniture entry.
    """
    if room_id not in _FURNITURE_BY_ROOM:
        return None
    if alpha_500 <= 0.0:
        raise ValueError("alpha_500 must be > 0")
    if len(alpha_bands) != 6:
        raise ValueError("alpha_bands must have length 6")
    furniture = _FURNITURE_BY_ROOM[room_id]
    total_eq_abs = 0.0
    for piece, count in furniture.items():
        a_i = _PIECE_EQUIVALENT_ABSORPTION_500HZ_M2[piece]
        total_eq_abs += count * a_i
    area = total_eq_abs / alpha_500
    if area <= 0.0:
        return None

    L, W, _H = room_dimensions
    side = math.sqrt(area)
    if side <= min(L, W):
        x0, x1 = 0.0, side
        z0, z1 = 0.0, side
    else:
        long_side = max(L, W)
        short_side = min(L, W)
        strip_long = min(area / short_side, long_side)
        other = area / strip_long
        if L >= W:
            x0, x1 = 0.0, strip_long
            z0, z1 = 0.0, other
        else:
            x0, x1 = 0.0, other
            z0, z1 = 0.0, strip_long

    return Surface(
        kind="floor",
        polygon=[
            Point3(x0, 0.0, z0),
            Point3(x1, 0.0, z0),
            Point3(x1, 0.0, z1),
            Point3(x0, 0.0, z1),
        ],
        material=MaterialLabel.MISC_SOFT,
        absorption_500hz=alpha_500,
        absorption_bands=alpha_bands,
    )


# --------------------------------------------------------------------------- #
# v0.8 Scope-A bracketing overrides (additive; default-equivalent path is
# byte-equal to v0.7). See ADR 0015 + tests/test_lecture_2_ceiling_seat_bracket.py.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _RoomBuildOverrides:
    """Per-variant overrides used by Scope-A bracketing test (v0.8).

    None of these mutate library defaults — the overrides are constructed at
    the test layer and passed in for one synthesis call. The default
    ``_build_room_model(...)`` path is byte-equal to v0.7 when overrides is
    None.
    """

    ceiling_label: MaterialLabel | None = None        # V1 / V3 / V4
    seat_alpha_500: float | None = None               # V2 / V3
    seat_alpha_bands: tuple[float, float, float, float, float, float] | None = None  # V2 / V3


# --------------------------------------------------------------------------- #
# E2ERoomCase dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class E2ERoomCase:
    """One ACE Challenge room: geometry + pre-tabulated measured RT60."""

    room_id: str
    room: RoomModel
    measured_rt60_per_band_s: dict[int, float]
    measured_rt60_500hz_s: float
    source_rir_path: Path | None = None
    notes: str = ""


# --------------------------------------------------------------------------- #
# Helper: build a rectangular RoomModel from L × W × H
# --------------------------------------------------------------------------- #


def _build_room_model(
    room_id: str,
    geom: dict[str, object],
    *,
    overrides: _RoomBuildOverrides | None = None,
) -> RoomModel:
    """Construct a synthetic RoomModel for one ACE room.

    The room is a rectangular shoebox. Surfaces:
    - 4 walls (vertical rectangles)
    - 1 floor
    - 1 ceiling

    Materials are assigned from the ACE geometry table:
    - floor material → geom["floor"]
    - wall material  → geom["walls"]
    - ceiling material → geom["ceiling"]

    The ListenerArea is centred at the floor polygon centroid, height=1.20 m,
    radius ~0.5 m (no acoustic significance for RT60; required by RoomModel).

    The optional ``overrides`` keyword (v0.8 Scope-A; see ADR 0015) is the
    only library hook for the Lecture_2 ceiling/seat bracketing harness. When
    ``overrides is None`` the output is byte-equal to v0.7 (no surface
    added/removed/reordered; absorption values per surface unchanged).
    """
    L: float = float(geom["L"])  # x direction
    W: float = float(geom["W"])  # z direction
    H: float = float(geom["H"])  # y (ceiling height)

    floor_mat = _MATERIAL_MAP[str(geom["floor"])]
    wall_mat = _MATERIAL_MAP[str(geom["walls"])]
    ceiling_mat = (
        overrides.ceiling_label
        if overrides is not None and overrides.ceiling_label is not None
        else _MATERIAL_MAP[str(geom["ceiling"])]
    )

    # Floor polygon (CCW viewed from above → standard orientation)
    floor_pts_2d = [
        Point2(0.0, 0.0),
        Point2(L, 0.0),
        Point2(L, W),
        Point2(0.0, W),
    ]
    def _absorption_bands(mat: MaterialLabel) -> tuple[float, float, float, float, float, float]:
        return MaterialAbsorptionBands[mat]

    # Floor surface (y=0 plane)
    floor_surf = Surface(
        kind="floor",
        polygon=[
            Point3(0.0, 0.0, 0.0),
            Point3(L, 0.0, 0.0),
            Point3(L, 0.0, W),
            Point3(0.0, 0.0, W),
        ],
        material=floor_mat,
        absorption_500hz=MaterialAbsorption[floor_mat],
        absorption_bands=_absorption_bands(floor_mat),
    )

    # Ceiling surface (y=H plane)
    ceiling_surf = Surface(
        kind="ceiling",
        polygon=[
            Point3(0.0, H, 0.0),
            Point3(L, H, 0.0),
            Point3(L, H, W),
            Point3(0.0, H, W),
        ],
        material=ceiling_mat,
        absorption_500hz=MaterialAbsorption[ceiling_mat],
        absorption_bands=_absorption_bands(ceiling_mat),
    )

    # 4 walls
    # Wall 1: z=0 face (front wall, x 0→L)
    wall1 = Surface(
        kind="wall",
        polygon=[
            Point3(0.0, 0.0, 0.0),
            Point3(L, 0.0, 0.0),
            Point3(L, H, 0.0),
            Point3(0.0, H, 0.0),
        ],
        material=wall_mat,
        absorption_500hz=MaterialAbsorption[wall_mat],
        absorption_bands=_absorption_bands(wall_mat),
    )
    # Wall 2: z=W face (back wall)
    wall2 = Surface(
        kind="wall",
        polygon=[
            Point3(0.0, 0.0, W),
            Point3(L, 0.0, W),
            Point3(L, H, W),
            Point3(0.0, H, W),
        ],
        material=wall_mat,
        absorption_500hz=MaterialAbsorption[wall_mat],
        absorption_bands=_absorption_bands(wall_mat),
    )
    # Wall 3: x=0 face (left wall)
    wall3 = Surface(
        kind="wall",
        polygon=[
            Point3(0.0, 0.0, 0.0),
            Point3(0.0, 0.0, W),
            Point3(0.0, H, W),
            Point3(0.0, H, 0.0),
        ],
        material=wall_mat,
        absorption_500hz=MaterialAbsorption[wall_mat],
        absorption_bands=_absorption_bands(wall_mat),
    )
    # Wall 4: x=L face (right wall)
    wall4 = Surface(
        kind="wall",
        polygon=[
            Point3(L, 0.0, 0.0),
            Point3(L, 0.0, W),
            Point3(L, H, W),
            Point3(L, H, 0.0),
        ],
        material=wall_mat,
        absorption_500hz=MaterialAbsorption[wall_mat],
        absorption_bands=_absorption_bands(wall_mat),
    )

    # ListenerArea: centred in floor polygon, radius 0.5 m
    cx = L / 2.0
    cz = W / 2.0
    r = 0.5
    listener_pts = [
        Point2(cx - r, cz - r),
        Point2(cx + r, cz - r),
        Point2(cx + r, cz + r),
        Point2(cx - r, cz + r),
    ]
    listener_area = ListenerArea(
        polygon=listener_pts,
        centroid=Point2(cx, cz),
        height_m=1.20,
    )

    surfaces = [floor_surf, ceiling_surf, wall1, wall2, wall3, wall4]
    if (
        overrides is not None
        and overrides.seat_alpha_500 is not None
        and overrides.seat_alpha_bands is not None
    ):
        misc_soft_surf = _misc_soft_surface_from_furniture_with_alpha(
            room_id,
            (L, W, H),
            overrides.seat_alpha_500,
            overrides.seat_alpha_bands,
        )
    else:
        misc_soft_surf = _misc_soft_surface_from_furniture(room_id, (L, W, H))
    if misc_soft_surf is not None:
        surfaces.append(misc_soft_surf)

    return RoomModel(
        name=room_id,
        floor_polygon=floor_pts_2d,
        ceiling_height_m=H,
        surfaces=surfaces,
        listener_area=listener_area,
    )


# --------------------------------------------------------------------------- #
# CSV helpers
# --------------------------------------------------------------------------- #


def _load_t60_per_band(dataset_dir: Path) -> dict[str, dict[int, float]]:
    """Parse ace_corpus_t60.csv → {room_id: {band_hz: t60_s}}.

    Expected CSV format (header on first line):
        room_id,band_hz,t60_s
        Office_1,125,0.42
        Office_1,250,0.40
        ...

    Raises FileNotFoundError if the CSV does not exist.
    """
    csv_path = dataset_dir / "ace_corpus_t60.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"ACE corpus per-band T60 CSV not found: {csv_path}\n"
            "Expected format: room_id,band_hz,t60_s (one row per room/band pair).\n"
            "Obtain this file from the ACE Challenge corpus documentation "
            "(https://zenodo.org/records/6257551) and place it in your ROOMESTIM_E2E_DATASET_DIR."
        )
    result: dict[str, dict[int, float]] = {}
    expected_fields = {"room_id", "band_hz", "t60_s"}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or not expected_fields.issubset(reader.fieldnames):
            raise ValueError(
                f"{csv_path}: header must include {sorted(expected_fields)}, "
                f"got {reader.fieldnames}"
            )
        for row in reader:
            room_id = row["room_id"].strip()
            band_hz = int(row["band_hz"].strip())
            t60_s = float(row["t60_s"].strip())
            if band_hz <= 0 or not (0.0 < t60_s < 60.0):
                raise ValueError(
                    f"{csv_path}: implausible row room_id={room_id!r} "
                    f"band_hz={band_hz} t60_s={t60_s}"
                )
            result.setdefault(room_id, {})[band_hz] = t60_s
    return result


def _load_t60_500hz(dataset_dir: Path) -> dict[str, float]:
    """Parse ace_corpus_t60_500hz.csv → {room_id: t60_500hz_s}.

    Expected CSV format:
        room_id,t60_500hz_s
        Office_1,0.42
        ...

    Raises FileNotFoundError if the CSV does not exist.
    """
    csv_path = dataset_dir / "ace_corpus_t60_500hz.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"ACE corpus 500 Hz T60 CSV not found: {csv_path}\n"
            "Expected format: room_id,t60_500hz_s (one row per room).\n"
            "Obtain this file from the ACE Challenge corpus documentation "
            "(https://zenodo.org/records/6257551) and place it in your ROOMESTIM_E2E_DATASET_DIR."
        )
    result: dict[str, float] = {}
    expected_fields = {"room_id", "t60_500hz_s"}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or not expected_fields.issubset(reader.fieldnames):
            raise ValueError(
                f"{csv_path}: header must include {sorted(expected_fields)}, "
                f"got {reader.fieldnames}"
            )
        for row in reader:
            room_id = row["room_id"].strip()
            t60_s = float(row["t60_500hz_s"].strip())
            if not (0.0 < t60_s < 60.0):
                raise ValueError(
                    f"{csv_path}: implausible row room_id={room_id!r} t60_s={t60_s}"
                )
            result[room_id] = t60_s
    return result


# --------------------------------------------------------------------------- #
# Public adapter API
# --------------------------------------------------------------------------- #


def dataset_name() -> str:
    """Return the canonical dataset identifier string."""
    return "ACE Challenge (Imperial College, 2015)"


def list_rooms(dataset_dir: Path) -> list[str]:
    """Return sorted room IDs present in BOTH the geometry table AND the user's CSV.

    A partial dataset (CSV contains only some rooms) is fine — only rooms that
    appear in ace_corpus_t60.csv are returned.

    Raises FileNotFoundError if ace_corpus_t60.csv is missing.
    """
    t60_per_band = _load_t60_per_band(dataset_dir)
    available = set(t60_per_band.keys()) & set(ACE_ROOM_GEOMETRY.keys())
    return sorted(available)


def load_room(dataset_dir: Path, room_id: str) -> E2ERoomCase:
    """Load one ACE Challenge room.

    Constructs a synthetic RoomModel from the hardcoded ACE geometry table,
    assigns materials, and reads measured T60 values from the user's CSV files.

    Parameters
    ----------
    dataset_dir:
        Directory containing ace_corpus_t60.csv and ace_corpus_t60_500hz.csv.
    room_id:
        Must be one of the keys in ACE_ROOM_GEOMETRY.

    Raises
    ------
    KeyError
        If room_id is not in ACE_ROOM_GEOMETRY.
    FileNotFoundError
        If either required CSV file is missing.
    """
    if room_id not in ACE_ROOM_GEOMETRY:
        raise KeyError(
            f"Unknown ACE room_id {room_id!r}. "
            f"Valid rooms: {sorted(ACE_ROOM_GEOMETRY.keys())}"
        )
    geom = ACE_ROOM_GEOMETRY[room_id]
    room = _build_room_model(room_id, geom)

    t60_per_band = _load_t60_per_band(dataset_dir)
    t60_500hz_map = _load_t60_500hz(dataset_dir)

    measured_per_band = t60_per_band.get(room_id, {})
    measured_500hz = t60_500hz_map.get(room_id, measured_per_band.get(500, 0.0))

    return E2ERoomCase(
        room_id=room_id,
        room=room,
        measured_rt60_per_band_s=measured_per_band,
        measured_rt60_500hz_s=measured_500hz,
        notes=(
            f"ACE Challenge corpus — {room_id}. "
            "T60 values from user-supplied CSV (not hardcoded). "
            "Geometry dimensions VERIFIED vs arXiv:1606.03365 Table 1 (v0.5 audit); "
            "floor 4/7 BYTE-CONFIRMED at TASLP §II-C (carpet rooms only); "
            "walls/ceiling INDETERMINATE — not in canonical paper (v0.5.1; ADR 0012). "
            + (
                "MISC_SOFT surface synthesised from TASLP §II-C furniture counts "
                "× textbook per-piece α (v0.6; ADR 0013)."
                if room_id in _FURNITURE_BY_ROOM
                else "MISC_SOFT surface intentionally NOT synthesised "
                "(Building_Lobby coupled-space caveat; v0.6; ADR 0013)."
            )
        ),
    )


# --------------------------------------------------------------------------- #
# Helper functions exposed for test use
# --------------------------------------------------------------------------- #


def _surface_areas_by_material(room: RoomModel) -> dict[MaterialLabel, float]:
    """Aggregate surface areas keyed by MaterialLabel.

    For rectangular wall/floor/ceiling surfaces in this adapter's RoomModel,
    area = base × height computed from the 3D polygon vertex coordinates.
    Uses a simple planar polygon area formula (cross product magnitude).
    """
    from collections import defaultdict

    areas: dict[MaterialLabel, float] = defaultdict(float)
    for surf in room.surfaces:
        pts = surf.polygon
        # Compute polygon area via the 3D cross-product shoelace formula.
        # For convex planar quads: area = 0.5 * |d1 × d2| (diagonals),
        # but generic: Newell's method.
        n = len(pts)
        nx = ny = nz = 0.0
        for i in range(n):
            j = (i + 1) % n
            nx += (pts[i].y - pts[j].y) * (pts[i].z + pts[j].z)
            ny += (pts[i].z - pts[j].z) * (pts[i].x + pts[j].x)
            nz += (pts[i].x - pts[j].x) * (pts[i].y + pts[j].y)
        area = 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)
        areas[surf.material] += area
    return dict(areas)


def _room_volume(room: RoomModel) -> float:
    """Compute volume as floor_area × ceiling_height_m.

    Uses :class:`shapely.geometry.Polygon` for the floor area so the result
    is correct for arbitrary 2D floor polygons (not just axis-aligned
    shoeboxes). The ACE adapter only emits shoeboxes today, but exposing a
    bounding-box-only helper would silently lie if a future caller passes an
    L-shape or convex non-rectangle.
    """
    from shapely.geometry import Polygon as ShapelyPolygon

    coords = [(p.x, p.z) for p in room.floor_polygon]
    floor_area = ShapelyPolygon(coords).area
    return floor_area * room.ceiling_height_m
