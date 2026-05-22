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


__all__ = [
    "evolve_surface",
    "evolve_room",
    "evolve_room_material",
    "evolve_room_materials_bulk",
    "evolve_room_add_object",
    "evolve_room_remove_object",
    "evolve_placement",
    "nudge_speaker",
]
