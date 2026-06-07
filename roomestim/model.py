"""Internal data model for roomestim — RoomModel and friends.

All in listener-frame Cartesian (x=right, y=up, z=front), metres. CCW polygon
canonicalization is enforced via :func:`canonicalize_ccw`.

Material absorption table at 500 Hz mid-band per Vorländer 2020 *Auralization*
Appx A. The same table is consumed by P4 reconstruction (`reconstruct/materials.py`)
and the Sabine RT60 reference computation in `reconstruct/`.

The `MISC_SOFT` row is a representative-not-verbatim schema slot reserved for
adapter-emitted furnishings/occupants absorption budget (curtains, fabric panels,
books, light upholstery). It is NOT a verbatim Vorländer Appx A row and NOT a
per-furnishing-item physics model. See ADR 0011.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from shapely.geometry import Polygon as ShapelyPolygon


# --------------------------------------------------------------------------- #
# Named error constants
# --------------------------------------------------------------------------- #

kErrNonFiniteValue: str = "kErrNonFiniteValue"
kErrTooFewSpeakers: str = "kErrTooFewSpeakers"
kErrEngineSchemaNotFound: str = "kErrEngineSchemaNotFound"


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
    MISC_SOFT = "misc_soft"
    MELAMINE_FOAM = "melamine_foam"


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
    MaterialLabel.MISC_SOFT: 0.40,
    # planner-locked envelope per ADR 0019 §References pending verbatim Vorländer 2020 §11 / Appx A lookup
    MaterialLabel.MELAMINE_FOAM: 0.85,
}

OCTAVE_BANDS_HZ: tuple[int, ...] = (125, 250, 500, 1000, 2000, 4000)

# Octave-band absorption coefficients per material.
# Band order: (125, 250, 500, 1000, 2000, 4000) Hz.
#
# Citation policy (OD-4): rows below are representative typical room-acoustics
# coefficients consistent with Vorländer 2020 *Auralization* Appendix A and
# similar textbook tables; they are NOT verbatim Appx A rows. Each row's band
# index 2 (a500) MUST equal MaterialAbsorption[m] (legacy scalar) — enforced
# by tests/test_room_acoustics_octave.py::test_band_a500_matches_legacy_scalar.
# UNKNOWN row is flat at 0.10 (synthetic broadband; D3 fallback).
MaterialAbsorptionBands: dict[MaterialLabel, tuple[float, float, float, float, float, float]] = {
    # representative typical room-acoustics row from Vorländer-class textbook tables; not a verbatim Appx A row
    MaterialLabel.WALL_PAINTED:           (0.10, 0.07, 0.05, 0.06, 0.07, 0.09),
    # representative typical room-acoustics row from Vorländer-class textbook tables; not a verbatim Appx A row
    MaterialLabel.WALL_CONCRETE:          (0.01, 0.01, 0.02, 0.02, 0.02, 0.03),
    # representative typical room-acoustics row from Vorländer-class textbook tables; not a verbatim Appx A row
    MaterialLabel.WOOD_FLOOR:             (0.15, 0.11, 0.10, 0.07, 0.06, 0.07),
    # representative typical room-acoustics row from Vorländer-class textbook tables; not a verbatim Appx A row
    MaterialLabel.CARPET:                 (0.05, 0.10, 0.30, 0.40, 0.50, 0.60),
    # representative typical room-acoustics row from Vorländer-class textbook tables; not a verbatim Appx A row
    MaterialLabel.GLASS:                  (0.18, 0.06, 0.04, 0.03, 0.02, 0.02),
    # representative typical room-acoustics row from Vorländer-class textbook tables; not a verbatim Appx A row
    MaterialLabel.CEILING_ACOUSTIC_TILE:  (0.30, 0.45, 0.55, 0.70, 0.75, 0.80),
    # representative typical room-acoustics row from Vorländer-class textbook tables; not a verbatim Appx A row
    MaterialLabel.CEILING_DRYWALL:        (0.29, 0.10, 0.10, 0.04, 0.07, 0.09),
    # broadband fallback (synthetic; no Appx A row) — UNKNOWN stays flat at 0.10 across all bands
    MaterialLabel.UNKNOWN:                (0.10, 0.10, 0.10, 0.10, 0.10, 0.10),
    # representative mid-band profile for mixed soft furnishings (curtains, fabric panels, books, light upholstery); not a verbatim Vorländer Appx A row. Schema slot reserved for adapter-emitted furnishings/occupants absorption budget — NOT a per-furnishing-item physics model. Reverse if ≥1 adapter starts emitting MISC_SOFT and downstream consumer reports magnitude wrong.
    MaterialLabel.MISC_SOFT:              (0.20, 0.30, 0.40, 0.50, 0.60, 0.65),
    # planner-locked envelope per ADR 0019 §References pending verbatim Vorländer 2020 §11 / Appx A "melamine foam panel" / "acoustic foam absorber" lookup. Typical 2-4" foam panel rising profile; index 2 (500 Hz) equals MaterialAbsorption row above (band-2 invariant).
    MaterialLabel.MELAMINE_FOAM:          (0.35, 0.65, 0.85, 0.92, 0.93, 0.92),
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

ObjectKind = Literal[
    "column", "door", "window", "sofa", "table", "bed", "storage"
]

#: Free-standing objects modelled acoustically as a solid box (4 side faces +
#: top) folded into the RT60 absorption budget, exactly like a column. Furniture
#: (sofa/table/bed/storage from RoomPlan ``CapturedRoomObject`` categories) joins
#: the column here: its exposed box surfaces add absorption (a furnished room is
#: deader). The bounding box + per-kind representative material is an ESTIMATE
#: (real furniture is not a solid uniform box), consistent with the existing
#: TASLP furniture-budget MISC_SOFT model in ``adapters/ace_challenge.py``.
FREESTANDING_OBJECT_KINDS: frozenset[ObjectKind] = frozenset(
    {"column", "sofa", "table", "bed", "storage"}
)
#: Wall-attached objects modelled as a per-wall α override (no new box surface).
WALL_ATTACHED_OBJECT_KINDS: frozenset[ObjectKind] = frozenset({"door", "window"})

#: Room-level capture provenance (OQ-54 / ADR 0045 §F honesty). One of:
#:   ``measured``      — real depth sensor / scan (LiDAR, RGB-D, GT survey);
#:   ``reconstructed`` — inferred from images without depth;
#:   ``assumed``       — unknown / hand-authored / legacy (honest least-claim).
#: Default is ``assumed`` so untagged geometry never masquerades as measured.
Provenance = Literal["measured", "reconstructed", "assumed"]


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
    absorption_bands: tuple[float, float, float, float, float, float] | None = None


@dataclass(frozen=True)
class MountSurface:
    """A subset-of-Surface where speakers may be placed.

    Used by DBAP placement; usually walls + ceiling.
    """

    surface_index: int
    inset_m: float = 0.10


# --------------------------------------------------------------------------- #
# Walls-only surface-index frame (the single authority — D68 / ADR 0037)
# --------------------------------------------------------------------------- #


def wall_surfaces(room: "RoomModel") -> list["Surface"]:
    """Return the room's wall surfaces in ``room.surfaces`` order.

    This is the ONE authority for the walls-only "surface index" frame that
    :attr:`Object.wall_index` resolves against (predictor α overrides + the web
    3D viewer). Adapters do not agree on the position of walls within the full
    ``room.surfaces`` list (RoomPlan emits ``[floor, *ceilings, *walls]``, the
    mesh adapter ``[floor, ceiling, *walls]``, the ACE adapter a trailing
    floor), so the walls-relative ordinal must always be resolved through this
    filter rather than re-derived ad hoc. See ADR 0037 + D68.
    """
    return [s for s in room.surfaces if s.kind == "wall"]


def surface_index_for_wall(room: "RoomModel", wall_ordinal: int) -> int:
    """Return the full ``room.surfaces`` index of the ``wall_ordinal``-th wall.

    ``wall_ordinal`` is a walls-only index (the frame :attr:`Object.wall_index`
    lives in). The returned value is the matching full-``room.surfaces`` index,
    which is what :func:`roomestim.edit.evolve_room_material` consumes — i.e.
    this bridges the two coexisting "surface index" frames so a wall-relative
    edit lands on the correct surface regardless of adapter ordering.

    Raises
    ------
    IndexError
        When ``wall_ordinal`` is outside ``[0, len(wall_surfaces(room)))``.
    """
    walls = wall_surfaces(room)
    n = len(walls)
    if not (0 <= wall_ordinal < n):
        raise IndexError(
            f"wall_ordinal={wall_ordinal} is out of valid range [0, {n}); "
            f"room '{room.name}' has {n} walls."
        )
    target = walls[wall_ordinal]
    for full_index, surf in enumerate(room.surfaces):
        if surf is target:
            return full_index
    # Unreachable: target came from room.surfaces, so identity match exists.
    raise IndexError(
        f"wall_ordinal={wall_ordinal}: matching wall surface not found in "
        f"room '{room.name}' surfaces."
    )


# --------------------------------------------------------------------------- #
# Obstacles (columns / doors / windows) — v0.17 schema extension per ADR 0034
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Object:
    """An obstacle or furnishing inside the RoomModel.

    - column + furniture (sofa/table/bed/storage): standalone
      (wall_index=None); 5 추가 surface (4 측면 + top) folded into the RT60
      absorption budget per ADR 0034 §C / D46. Furniture is modelled as a
      free-standing box exactly like a column — see
      :data:`FREESTANDING_OBJECT_KINDS`.
    - door/window: attached to wall (wall_index 필수); 벽 α override 영역.

    anchor:
        column / furniture → base center (z = floor level).
        door/window → bottom-left corner (in wall-local coord).
    """

    kind: ObjectKind
    anchor: Point3
    width_m: float
    height_m: float
    depth_m: float = 0.0  # column only; door/window = 0
    wall_index: int | None = None  # None for column; required for door/window
    material: MaterialLabel = MaterialLabel.UNKNOWN  # default per kind below


#: Default material per object kind (used by adapters and YAML reader when the
#: source data does not provide a material hint).
DEFAULT_OBJECT_MATERIAL: dict[ObjectKind, MaterialLabel] = {
    "column": MaterialLabel.WALL_CONCRETE,
    "door": MaterialLabel.WALL_PAINTED,
    "window": MaterialLabel.GLASS,
    # Furniture: representative per-category absorption (honest ESTIMATE — the
    # piece is treated as a solid box of this single material). Soft, upholstered
    # furnishings are reliably absorptive (MISC_SOFT, α≈0.40); hard wooden pieces
    # are near the UNKNOWN 0.10 floor (WOOD_FLOOR). Chairs are deliberately
    # excluded (ambiguous hard/soft, small area).
    #
    # Known approximation (honest): OPEN-FRAME furniture — a ``table`` (legs +
    # thin top) most of all — is NOT a solid box, so the 4 full side faces + top
    # over-count its real exposed area. The acoustic error stays small because
    # such pieces carry the low WOOD_FLOOR α≈0.10 (≈ the UNKNOWN floor), but the
    # box fold is a conservative estimate, not a measurement — same honesty bar
    # as the TASLP furniture-budget MISC_SOFT model in ``adapters/ace_challenge``.
    "sofa": MaterialLabel.MISC_SOFT,
    "bed": MaterialLabel.MISC_SOFT,
    "table": MaterialLabel.WOOD_FLOOR,
    "storage": MaterialLabel.WOOD_FLOOR,
}


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
    objects: list[Object] = field(default_factory=list)
    schema_version: str = "0.2-draft"
    provenance: Provenance = "assumed"


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
    #: Capture provenance of the room geometry this placement was derived from
    #: (OQ-54 / ADR 0046). Mirrors :attr:`RoomModel.provenance` so the rough-tier
    #: honesty marker survives into the layout.yaml boundary. Keyword-defaulted to
    #: ``"assumed"`` (least-claim) after ``wfs_f_alias_hz`` so existing positional
    #: constructors are unaffected and existing layouts stay byte-equal.
    geometry_provenance: Provenance = "assumed"


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
