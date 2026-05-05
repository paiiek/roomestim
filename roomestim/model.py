"""Internal data model for roomestim — RoomModel and friends.

All in listener-frame Cartesian (x=right, y=up, z=front), metres. CCW polygon
canonicalization is enforced via :func:`canonicalize_ccw`.

Material absorption table at 500 Hz mid-band per Vorländer 2020 *Auralization*
Appx A. The same table is consumed by P4 reconstruction (`reconstruct/materials.py`)
and the Sabine RT60 reference computation in `reconstruct/`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from shapely.geometry import Polygon as ShapelyPolygon


# --------------------------------------------------------------------------- #
# Named error constants
# --------------------------------------------------------------------------- #

kErrNonFiniteValue: str = "kErrNonFiniteValue"
kErrTooFewSpeakers: str = "kErrTooFewSpeakers"


def assert_finite(value: float, *, field: str) -> None:
    """Raise ``ValueError`` if ``value`` is NaN or +/- inf."""
    if not math.isfinite(value):
        raise ValueError(f"{kErrNonFiniteValue}: {field}={value}")


# --------------------------------------------------------------------------- #
# Surface materials (closed enum; absorption table below)
# --------------------------------------------------------------------------- #


class MaterialLabel(str, Enum):
    WALL_PAINTED = "wall_painted"
    WALL_CONCRETE = "wall_concrete"
    WOOD_FLOOR = "wood_floor"
    CARPET = "carpet"
    GLASS = "glass"
    CEILING_ACOUSTIC_TILE = "ceiling_acoustic_tile"
    CEILING_DRYWALL = "ceiling_drywall"
    UNKNOWN = "unknown"


# Mid-band 500 Hz absorption coefficients per Vorländer 2020,
# *Auralization*, Appendix A. Used by P4 Sabine RT60 reference.
MaterialAbsorption: dict[MaterialLabel, float] = {
    MaterialLabel.WALL_PAINTED: 0.05,
    MaterialLabel.WALL_CONCRETE: 0.02,
    MaterialLabel.WOOD_FLOOR: 0.10,
    MaterialLabel.CARPET: 0.30,
    MaterialLabel.GLASS: 0.04,
    MaterialLabel.CEILING_ACOUSTIC_TILE: 0.55,
    MaterialLabel.CEILING_DRYWALL: 0.10,
    MaterialLabel.UNKNOWN: 0.10,
}


# --------------------------------------------------------------------------- #
# Geometry primitives
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Point2:
    """Floor-plane (x_right, z_front) in metres."""

    x: float
    z: float


@dataclass(frozen=True)
class Point3:
    """Listener-frame Cartesian (x=right, y=up, z=front) in metres."""

    x: float
    y: float
    z: float


SurfaceKind = Literal["wall", "floor", "ceiling"]


# --------------------------------------------------------------------------- #
# Surfaces
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Surface:
    """A bounded planar surface in listener-frame coordinates.

    Walls are vertical rectangles; floor/ceiling are arbitrary polygons.
    Polygons are CCW-ordered when viewed from inside the room.
    """

    kind: SurfaceKind
    polygon: list[Point3]
    material: MaterialLabel
    absorption_500hz: float


@dataclass(frozen=True)
class MountSurface:
    """A subset-of-Surface where speakers may be placed.

    Used by DBAP placement; usually walls + ceiling.
    """

    surface_index: int
    inset_m: float = 0.10


# --------------------------------------------------------------------------- #
# Listener area
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ListenerArea:
    """The region occupied by listeners. Speakers point at the centroid by default."""

    polygon: list[Point2]
    centroid: Point2
    height_m: float = 1.20


# --------------------------------------------------------------------------- #
# Room model
# --------------------------------------------------------------------------- #


@dataclass
class RoomModel:
    """The stable internal abstraction emitted by every CaptureAdapter."""

    name: str
    floor_polygon: list[Point2]
    ceiling_height_m: float
    surfaces: list[Surface]
    listener_area: ListenerArea
    schema_version: str = "0.1-draft"


# --------------------------------------------------------------------------- #
# Placement output
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PlacedSpeaker:
    """One speaker in a placement result."""

    channel: int
    position: Point3
    aim_direction: Point3 | None = None
    notes: str = ""


@dataclass
class PlacementResult:
    """Output of a placement algorithm.

    ``wfs_f_alias_hz`` MUST be a finite, strictly positive float when
    ``target_algorithm == "WFS"`` and MUST be ``None`` for VBAP/DBAP/AMBISONICS.
    Exported into ``layout.yaml`` as top-level extension key
    ``x_wfs_f_alias_hz`` (geometry_schema.json declares
    ``additionalProperties: true`` at root).
    """

    target_algorithm: str
    regularity_hint: str
    speakers: list[PlacedSpeaker]
    layout_name: str
    layout_version: str = "1.0"
    wfs_f_alias_hz: float | None = None


# --------------------------------------------------------------------------- #
# Polygon CCW canonicalization
# --------------------------------------------------------------------------- #


def canonicalize_ccw(polygon: list[Point2]) -> list[Point2]:
    """Return ``polygon`` ordered CCW (counter-clockwise) on the floor plane.

    Uses :class:`shapely.geometry.Polygon` to test orientation and reverses if
    the input is clockwise. Returns a new list; the input is not mutated.
    """
    if len(polygon) < 3:
        return list(polygon)
    coords: list[tuple[float, float]] = [(p.x, p.z) for p in polygon]
    shp = ShapelyPolygon(coords)
    if shp.exterior.is_ccw:
        return list(polygon)
    return list(reversed(polygon))
