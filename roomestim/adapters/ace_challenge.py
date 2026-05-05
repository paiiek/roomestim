"""ACE Challenge corpus adapter — E2E GT-dataset reader for RT60 characterisation.

This adapter is NOT a CaptureAdapter (phone-scan → RoomModel pipeline).
It reads pre-tabulated T60 values from user-supplied CSV files and constructs
synthetic RoomModel objects from the published ACE Challenge room geometry table.

Dataset citation
----------------
Eaton, J., Gaubitch, N. D., Moore, A. H., & Naylor, P. A. (2016).
Estimation of room acoustic parameters: The ACE Challenge.
IEEE/ACM Transactions on Audio, Speech, and Language Processing, 24(10), 1681–1693.
https://dl.acm.org/doi/10.1109/TASLP.2016.2577502

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
# Source: ACE Challenge corpus documentation / corpus paper Table 1
# (Imperial College London EEE building, 7 rooms)
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
        "W": 3.50,
        "H": 3.00,
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


def _build_room_model(room_id: str, geom: dict[str, object]) -> RoomModel:
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
    """
    L: float = float(geom["L"])  # x direction
    W: float = float(geom["W"])  # z direction
    H: float = float(geom["H"])  # y (ceiling height)

    floor_mat = _MATERIAL_MAP[str(geom["floor"])]
    wall_mat = _MATERIAL_MAP[str(geom["walls"])]
    ceiling_mat = _MATERIAL_MAP[str(geom["ceiling"])]

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

    return RoomModel(
        name=room_id,
        floor_polygon=floor_pts_2d,
        ceiling_height_m=H,
        surfaces=[floor_surf, ceiling_surf, wall1, wall2, wall3, wall4],
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
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            room_id = row["room_id"].strip()
            band_hz = int(row["band_hz"].strip())
            t60_s = float(row["t60_s"].strip())
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
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            room_id = row["room_id"].strip()
            t60_s = float(row["t60_500hz_s"].strip())
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
            "Geometry from published ACE corpus documentation (Table 1)."
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
    import math

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

    For the rectangular shoebox rooms in this adapter, floor polygon is a
    rectangle. Area = L × W.
    """
    pts = room.floor_polygon
    # Shoebox: use first two distinct x and z extents
    xs = [p.x for p in pts]
    zs = [p.z for p in pts]
    floor_area = (max(xs) - min(xs)) * (max(zs) - min(zs))
    return floor_area * room.ceiling_height_m
