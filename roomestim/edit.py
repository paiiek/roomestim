"""roomestim.edit — RoomModel shape-transition helpers (D39 + ADR 0031).

Purpose
-------
Provides *evolve_* helpers that implement all RoomModel mutations as
``dataclasses.replace``-chain operations returning new frozen instances.
This is the authoritative "edit lane" per D39: no mutation logic lives in
``roomestim.model`` (shape-only) or ``roomestim.reconstruct`` (RT60 prediction).

Frozen invariant
----------------
Every helper returns a *new* RoomModel (or Surface) instance. The input is
never mutated. ``Surface`` is ``frozen=True``; ``RoomModel`` is mutable but
evolve helpers treat it as immutable by always constructing new instances.

Layering
--------
Imports: ``roomestim.model`` only. No web or reconstruct dependencies.
Web UI imports this module via ``roomestim.edit`` public API (D29 lane
separation preserved — web→core single direction).

References: D39, D40, D43, ADR 0031.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

from roomestim.coords import cartesian_to_pipeline, yaml_speaker_to_cartesian
from roomestim.model import (
    ListenerArea,
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    Object,
    PlacedSpeaker,
    PlacementResult,
    Point2,
    Point3,
    RoomModel,
    Surface,
    assert_finite,
    canonicalize_ccw,
)

if TYPE_CHECKING:
    pass


# --------------------------------------------------------------------------- #
# Surface-level helpers
# --------------------------------------------------------------------------- #


def evolve_surface(
    surf: Surface,
    *,
    material: MaterialLabel | None = None,
    polygon: list[Point3] | None = None,
) -> Surface:
    """Return a new Surface with the given fields replaced.

    When *material* is provided the ``absorption_500hz`` and
    ``absorption_bands`` fields are auto-looked up from
    :data:`~roomestim.model.MaterialAbsorption` /
    :data:`~roomestim.model.MaterialAbsorptionBands` so callers do not have
    to manage the absorption table directly.

    When *polygon* is provided every coordinate is validated via
    :func:`~roomestim.model.assert_finite`.

    Parameters
    ----------
    surf:
        Source surface (not mutated).
    material:
        New material label. Triggers absorption auto-lookup.
    polygon:
        New polygon vertex list. Each vertex must be finite.

    Returns
    -------
    Surface
        New frozen Surface instance.
    """
    new_material = material if material is not None else surf.material
    new_absorption_500hz = surf.absorption_500hz
    new_absorption_bands = surf.absorption_bands

    if material is not None:
        new_absorption_500hz = MaterialAbsorption[material]
        # OQ-44(c) / D70: gate the per-band promotion on the source already
        # carrying bands. A single-band surface (absorption_bands is None — the
        # octave_band=False ingest default) stays single-band after a material
        # edit; the unconditional scalar update above keeps its 500 Hz acoustics
        # correct. A per-band surface still gets its bands refreshed. This stops
        # a material edit from silently shifting a single-band room onto the
        # per-band predictor branch. (Test-coupled: reverting this gate must
        # revert tests/test_edit_room.py::test_evolve_surface_material_only_*.)
        if surf.absorption_bands is not None:
            new_absorption_bands = MaterialAbsorptionBands[material]

    new_polygon = surf.polygon
    if polygon is not None:
        # Validate all coordinates
        for i, pt in enumerate(polygon):
            assert_finite(pt.x, field=f"polygon[{i}].x")
            assert_finite(pt.y, field=f"polygon[{i}].y")
            assert_finite(pt.z, field=f"polygon[{i}].z")
        new_polygon = list(polygon)

    return replace(
        surf,
        material=new_material,
        absorption_500hz=new_absorption_500hz,
        absorption_bands=new_absorption_bands,
        polygon=new_polygon,
    )


# --------------------------------------------------------------------------- #
# Room-level helpers
# --------------------------------------------------------------------------- #


def evolve_room(
    room: RoomModel,
    *,
    surfaces: list[Surface] | None = None,
    listener_area: ListenerArea | None = None,
    name: str | None = None,
    objects: list[Object] | None = None,
) -> RoomModel:
    """Return a new RoomModel with the given fields replaced.

    ``floor_polygon`` is not modified directly (v0.17 scope still leaves
    floor_polygon evolution out of band; obstacles attach via ``objects``).

    The returned instance uses a *shallow copy* of the surfaces and objects
    lists so the caller's original lists cannot mutate the new room's
    collections. The Surface and Object instances themselves are
    ``frozen=True`` (ADR 0002 + ADR 0034 invariants).

    Parameters
    ----------
    room:
        Source room (not mutated).
    surfaces:
        Replacement surface list. Shallow-copied internally.
    listener_area:
        Replacement listener area.
    name:
        Replacement room name.
    objects:
        Replacement object list (columns/doors/windows). Shallow-copied
        internally. ``None`` (default) preserves ``room.objects``.

    Returns
    -------
    RoomModel
        New RoomModel instance.
    """
    new_surfaces = list(surfaces) if surfaces is not None else list(room.surfaces)
    new_listener_area = listener_area if listener_area is not None else room.listener_area
    new_name = name if name is not None else room.name
    new_objects = list(objects) if objects is not None else list(room.objects)

    # D39 mandate: re-canonicalize floor_polygon to CCW after any room evolution
    # and re-validate finiteness of all numeric leaves.
    new_floor_polygon = canonicalize_ccw(list(room.floor_polygon))

    # Validate finiteness of all surface polygon coordinates.
    for i, surf in enumerate(new_surfaces):
        for j, pt in enumerate(surf.polygon):
            assert_finite(pt.x, field=f"surfaces[{i}].polygon[{j}].x")
            assert_finite(pt.y, field=f"surfaces[{i}].polygon[{j}].y")
            assert_finite(pt.z, field=f"surfaces[{i}].polygon[{j}].z")

    return replace(
        room,
        surfaces=new_surfaces,
        listener_area=new_listener_area,
        name=new_name,
        floor_polygon=new_floor_polygon,
        objects=new_objects,
    )


def evolve_room_material(
    room: RoomModel,
    surface_index: int,
    material: MaterialLabel,
) -> RoomModel:
    """Convenience helper: change one surface's material and return a new room.

    This is the primary entry point for the web Material Override Tab (D40).
    The new acoustic absorption values are auto-looked up from the material
    table (ADR 0031 §A — closed enum, no arbitrary α input).

    Parameters
    ----------
    room:
        Source room.
    surface_index:
        Zero-based index into ``room.surfaces``.
    material:
        New material label for that surface.

    Raises
    ------
    IndexError
        When ``surface_index`` is out of the valid range
        ``[0, len(room.surfaces))``.

    Returns
    -------
    RoomModel
        New room with the single surface replaced.
    """
    n = len(room.surfaces)
    if not (0 <= surface_index < n):
        raise IndexError(
            f"surface_index={surface_index} is out of valid range [0, {n}); "
            f"room '{room.name}' has {n} surfaces."
        )
    new_surf = evolve_surface(room.surfaces[surface_index], material=material)
    new_surfaces = list(room.surfaces)
    new_surfaces[surface_index] = new_surf
    return evolve_room(room, surfaces=new_surfaces)


def evolve_room_materials_bulk(
    room: RoomModel,
    changes: dict[int, MaterialLabel],
) -> RoomModel:
    """Apply multiple surface material changes atomically.

    Processes ``changes`` in ascending surface-index order (deterministic
    regardless of dict insertion order — commutative because each surface is
    changed independently).

    Parameters
    ----------
    room:
        Source room.
    changes:
        Mapping of ``{surface_index: new_material}``. Empty dict returns a
        structurally-equal new room (not the same object).

    Raises
    ------
    IndexError
        When any key in ``changes`` is out of valid range.

    Returns
    -------
    RoomModel
        New room with all specified surfaces replaced.
    """
    new_surfaces = list(room.surfaces)
    n = len(new_surfaces)
    for surface_index in sorted(changes):
        material = changes[surface_index]
        if not (0 <= surface_index < n):
            raise IndexError(
                f"surface_index={surface_index} is out of valid range [0, {n}); "
                f"room '{room.name}' has {n} surfaces."
            )
        new_surfaces[surface_index] = evolve_surface(new_surfaces[surface_index], material=material)
    return evolve_room(room, surfaces=new_surfaces)


# --------------------------------------------------------------------------- #
# Object-level helpers (v0.17 — ADR 0034 + D44)
# --------------------------------------------------------------------------- #


def evolve_room_add_object(room: RoomModel, obj: Object) -> RoomModel:
    """Return a new RoomModel with ``obj`` appended to ``room.objects``.

    Convenience wrapper over :func:`evolve_room`: surfaces and listener area
    are preserved; only the object list grows by one element.

    Parameters
    ----------
    room:
        Source room (not mutated).
    obj:
        New :class:`~roomestim.model.Object` to append.

    Returns
    -------
    RoomModel
        New room with ``objects = [*room.objects, obj]``.
    """
    return evolve_room(room, objects=[*room.objects, obj])


def evolve_room_remove_object(room: RoomModel, object_index: int) -> RoomModel:
    """Return a new RoomModel with ``room.objects[object_index]`` removed.

    Parameters
    ----------
    room:
        Source room (not mutated).
    object_index:
        Zero-based index into ``room.objects``.

    Raises
    ------
    IndexError
        When ``object_index`` is out of the valid range
        ``[0, len(room.objects))``.

    Returns
    -------
    RoomModel
        New room with the object at ``object_index`` removed.
    """
    n = len(room.objects)
    if not (0 <= object_index < n):
        raise IndexError(
            f"object_index={object_index} is out of valid range [0, {n}); "
            f"room '{room.name}' has {n} objects."
        )
    new_objects = [o for i, o in enumerate(room.objects) if i != object_index]
    return evolve_room(room, objects=new_objects)


# --------------------------------------------------------------------------- #
# Placement-level helpers (v0.18 — ADR 0036 §A/§B + D48 + D49)
# --------------------------------------------------------------------------- #


def evolve_placement(
    result: PlacementResult,
    *,
    speakers: list[PlacedSpeaker] | None = None,
    regularity_hint: str | None = None,
    layout_name: str | None = None,
) -> PlacementResult:
    """Return a new PlacementResult with the given fields replaced.

    Mirrors :func:`evolve_room`: the input is never mutated, the speakers list
    is shallow-copied, and every :class:`~roomestim.model.PlacedSpeaker` is
    frozen. Finite-validates each speaker position (and aim, if present).

    Parameters
    ----------
    result:
        Source placement result (not mutated).
    speakers:
        Replacement speaker list. Shallow-copied internally. ``None`` (default)
        preserves ``result.speakers``.
    regularity_hint:
        Replacement regularity hint. ``None`` preserves the existing value.
    layout_name:
        Replacement layout name. ``None`` preserves the existing value.

    Returns
    -------
    PlacementResult
        New PlacementResult instance.
    """
    new_speakers = list(speakers) if speakers is not None else list(result.speakers)
    for i, sp in enumerate(new_speakers):
        assert_finite(sp.position.x, field=f"speakers[{i}].position.x")
        assert_finite(sp.position.y, field=f"speakers[{i}].position.y")
        assert_finite(sp.position.z, field=f"speakers[{i}].position.z")
        if sp.aim_direction is not None:
            assert_finite(sp.aim_direction.x, field=f"speakers[{i}].aim.x")
            assert_finite(sp.aim_direction.y, field=f"speakers[{i}].aim.y")
            assert_finite(sp.aim_direction.z, field=f"speakers[{i}].aim.z")
    return replace(
        result,
        speakers=new_speakers,
        regularity_hint=(
            regularity_hint if regularity_hint is not None else result.regularity_hint
        ),
        layout_name=layout_name if layout_name is not None else result.layout_name,
    )


def nudge_speaker(
    result: PlacementResult,
    speaker_index: int,
    *,
    daz_deg: float = 0.0,
    del_deg: float = 0.0,
    ddist_m: float = 0.0,
    dx: float = 0.0,
    dy: float = 0.0,
    dz: float = 0.0,
) -> PlacementResult:
    """Nudge one speaker by a spherical Δ (az/el/dist) XOR a Cartesian Δ (xyz).

    The two frames are mutually exclusive: supplying both a non-zero spherical
    Δ and a non-zero Cartesian Δ raises :class:`ValueError` (D49). All frame
    conversion goes through :mod:`roomestim.coords` (the single sign-flip
    authority); this function never calls trigonometry directly.

    Parameters
    ----------
    result:
        Source placement result (not mutated).
    speaker_index:
        Zero-based index into ``result.speakers``.
    daz_deg, del_deg, ddist_m:
        Spherical delta — azimuth (degrees), elevation (degrees), distance
        (metres). Applied relative to the speaker's current spherical form.
    dx, dy, dz:
        Cartesian delta — added directly to the speaker's ``position``.

    Raises
    ------
    IndexError
        When ``speaker_index`` is out of the valid range.
    ValueError
        When both frames are non-zero, when the resulting spherical distance
        is non-positive, or when the resulting spherical elevation is outside
        [-90, 90] degrees (non-physical — would flip the hemisphere).

    Returns
    -------
    PlacementResult
        New PlacementResult with the single speaker replaced.
    """
    n = len(result.speakers)
    if not (0 <= speaker_index < n):
        raise IndexError(
            f"speaker_index={speaker_index} out of valid range [0, {n})"
        )
    spherical = (daz_deg, del_deg, ddist_m) != (0.0, 0.0, 0.0)
    cartesian = (dx, dy, dz) != (0.0, 0.0, 0.0)
    if spherical and cartesian:
        raise ValueError(
            "nudge_speaker: spherical Δ and Cartesian Δ are mutually exclusive"
        )
    sp = result.speakers[speaker_index]
    p = sp.position
    if cartesian:
        new_pos = Point3(x=p.x + dx, y=p.y + dy, z=p.z + dz)
    else:
        az_rad, el_rad, dist = cartesian_to_pipeline(p.x, p.y, p.z)
        az2 = math.degrees(az_rad) + daz_deg
        el2 = math.degrees(el_rad) + del_deg
        # v0.18.1 (D53 / Fix 7b closure): reject non-physical elevation. el ∉
        # [-90, 90] would flip the x/z hemisphere via cos(el)<0 in
        # yaml_speaker_to_cartesian — finite but mirror-reflected (a silent
        # hemisphere flip). Mirrors the existing dist<=0 reject (same frame,
        # same class of non-physical input). Cartesian branch needs no guard:
        # any finite (x,y,z) implies a physical el ∈ [-90,90] via atan2.
        if not (-90.0 <= el2 <= 90.0):
            raise ValueError(
                f"nudge_speaker: resulting elevation {el2}° outside [-90, 90] "
                f"(non-physical); reduce del_deg or use a Cartesian Δ"
            )
        d2 = dist + ddist_m
        if d2 <= 0.0:
            raise ValueError(f"nudge_speaker: resulting dist {d2} must be > 0")
        nx, ny, nz = yaml_speaker_to_cartesian(az2, el2, d2)
        new_pos = Point3(x=nx, y=ny, z=nz)
    new_sp = replace(sp, position=new_pos)
    new_speakers = list(result.speakers)
    new_speakers[speaker_index] = new_sp
    return evolve_placement(result, speakers=new_speakers)


# Absolute ceiling-height plausibility bound (metres), mirroring
# ``MeshAdapter._MAX_CEILING_HEIGHT_M``. A user override is authoritative for the
# height layer but still bounded: a typo'd 250 m must not pass silently.
_MAX_USER_CEILING_M = 20.0


def _wall_base_edge(
    wall: Surface,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Return the wall's base edge as two distinct ``(x, z)`` columns.

    A wall is a vertical rectangle, so its 4 vertices collapse to exactly two
    distinct ``(x, z)`` columns. Returns those two, or ``None`` if the polygon is
    degenerate (fewer than two distinct columns — a collapsed wall).
    """
    seen: list[tuple[float, float]] = []
    for p in wall.polygon:
        xz = (p.x, p.z)
        if xz not in seen:
            seen.append(xz)
        if len(seen) == 2:
            return seen[0], seen[1]
    return None


def evolve_room_ceiling_height(room: RoomModel, height_m: float) -> RoomModel:
    """Return a new room with a USER-supplied ceiling height (A-consumer lever).

    Motivation (PLACEMENT_SENSITIVITY_VERDICT.md): ceiling height is essentially
    unrecoverable from a rough phone/video point cloud (the cloud rarely reaches
    the ceiling), yet it is a single scalar the user can measure with a tape.
    Supplying it makes the height layer (ceiling-mounted speakers) mountable —
    in the measurement the ceiling-speaker surface error dropped 45 cm → 0.

    The floor footprint and floor surface are left unchanged. Walls are rebuilt
    as vertical rectangles ``[floor_y, floor_y + height_m]`` and the ceiling
    surface is lifted to ``floor_y + height_m`` (consistent with
    ``reconstruct.walls.walls_from_floor_polygon``). Each rebuilt surface keeps
    its existing material and per-band absorption. Note that walls are
    intentionally re-anchored to the floor surface's ``y``: mesh extraction
    builds walls from ``y=0`` while placing the floor at its detected plane, so
    for a floor detected at a non-zero offset this override makes walls, floor,
    and ceiling vertically consistent (rather than preserving any ``[0, h]``
    span). Because a measured ceiling is
    authoritative, ``ceiling_confidence`` becomes ``"high"`` and
    ``ceiling_coverage`` is cleared (it described the discarded auto-estimate).

    Raises ``ValueError`` for a non-positive or implausibly large height.
    """
    if not math.isfinite(height_m) or height_m <= 0.0:
        raise ValueError(
            f"evolve_room_ceiling_height: height_m must be > 0, got {height_m!r}"
        )
    if height_m > _MAX_USER_CEILING_M:
        raise ValueError(
            f"evolve_room_ceiling_height: height_m={height_m} m exceeds the "
            f"{_MAX_USER_CEILING_M} m plausibility bound; refusing a likely typo."
        )

    # Anchor everything to the existing floor surface's y so walls/ceiling stay
    # vertically consistent with the floor (floor_y is ~0 for consumer/multiview
    # clouds but may be offset on a measured mesh).
    floor_surfaces = [s for s in room.surfaces if s.kind == "floor"]
    floor_y = float(floor_surfaces[0].polygon[0].y) if floor_surfaces else 0.0
    ceil_y = floor_y + height_m

    new_surfaces: list[Surface] = []
    for surf in room.surfaces:
        if surf.kind == "wall":
            # Rebuild each wall on ITS OWN base edge at the new height — no
            # dependence on wall/floor-edge ordering or count (robust to edited
            # rooms). The base edge is the wall's two distinct (x, z) columns;
            # rebuild as the vertical rectangle [floor_y, ceil_y] over it.
            base_edge = _wall_base_edge(surf)
            if base_edge is None:
                new_surfaces.append(surf)  # degenerate wall: leave untouched
                continue
            (x0, z0), (x1, z1) = base_edge
            new_poly = [
                Point3(x0, floor_y, z0),
                Point3(x1, floor_y, z1),
                Point3(x1, ceil_y, z1),
                Point3(x0, ceil_y, z0),
            ]
            new_surfaces.append(replace(surf, polygon=new_poly))
        elif surf.kind == "ceiling":
            new_poly = [Point3(p.x, ceil_y, p.z) for p in surf.polygon]
            new_surfaces.append(replace(surf, polygon=new_poly))
        else:
            new_surfaces.append(surf)

    return replace(
        evolve_room(room, surfaces=new_surfaces),
        ceiling_height_m=float(height_m),
        ceiling_confidence="high",
        ceiling_coverage=None,
    )


def snap_layout_to_surfaces(
    room: RoomModel, result: PlacementResult
) -> PlacementResult:
    """Snap every placed speaker onto the nearest wall/ceiling mount surface.

    Install-time mitigation from PLACEMENT_SENSITIVITY_VERDICT.md: a layout
    planned on a rough room model puts speakers ~35 cm off the real surfaces;
    snapping each to the nearest actual mount surface recovers coverage to
    within ~0.03 dB of the oracle. Useful for edited/imported/drifted layouts
    whose positions no longer lie on a surface.

    Floors are excluded as mount surfaces (speakers are not floor-mounted).
    Only ``position`` is changed; each speaker keeps its existing
    ``aim_direction`` (the snap displacement is small, so the original aim stays
    valid — re-aiming is left to ``nudge_speaker`` if desired). Returns the
    layout unchanged when the room has no wall/ceiling surface.
    """
    from roomestim.geom.surface_distance import closest_point_on_surface

    mounts = [s for s in room.surfaces if s.kind in ("wall", "ceiling")]
    if not mounts:
        return result

    new_speakers: list[PlacedSpeaker] = []
    for sp in result.speakers:
        best_d = math.inf
        best_pt = sp.position
        for surf in mounts:
            d, pt = closest_point_on_surface(sp.position, surf)
            if d < best_d:
                best_d, best_pt = d, pt
        new_speakers.append(replace(sp, position=best_pt))
    return evolve_placement(result, speakers=new_speakers)


def evolve_room_listener_point(
    room: RoomModel, x_m: float, z_m: float
) -> RoomModel:
    """Recenter the listener area on a user-specified listening point (D lever).

    The auto listener area sits at the floor centroid; letting the user mark
    their actual seat re-optimizes coverage there, lifting placement quality
    independently of geometry error (PLACEMENT_SENSITIVITY_VERDICT.md calls this
    the cheap, high-impact "D" lever). The point is given in the room/floor frame
    ``(x_right, z_front)`` in metres. The existing listener-area shape and ear
    height are preserved — only the centre moves (the polygon is translated).

    Raises ``ValueError`` for a non-finite point or one outside the floor
    footprint (a listening seat must be inside the room).
    """
    if not (math.isfinite(x_m) and math.isfinite(z_m)):
        raise ValueError(
            f"evolve_room_listener_point: point must be finite, got ({x_m!r}, {z_m!r})"
        )
    from shapely.geometry import Point as ShapelyPoint
    from shapely.geometry import Polygon as ShapelyPolygon

    footprint = ShapelyPolygon([(p.x, p.z) for p in room.floor_polygon])
    if not footprint.contains(ShapelyPoint(x_m, z_m)):
        raise ValueError(
            f"evolve_room_listener_point: listening point ({x_m}, {z_m}) lies "
            "outside the room footprint."
        )

    la = room.listener_area
    dx = x_m - la.centroid.x
    dz = z_m - la.centroid.z
    new_polygon = [Point2(p.x + dx, p.z + dz) for p in la.polygon]
    new_area = ListenerArea(
        polygon=new_polygon, centroid=Point2(x_m, z_m), height_m=la.height_m
    )
    return replace(room, listener_area=new_area)


__all__ = [
    "evolve_surface",
    "evolve_room",
    "evolve_room_material",
    "evolve_room_materials_bulk",
    "evolve_room_add_object",
    "evolve_room_remove_object",
    "evolve_room_ceiling_height",
    "evolve_room_listener_point",
    "evolve_placement",
    "nudge_speaker",
    "snap_layout_to_surfaces",
]
