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

from dataclasses import replace
from typing import TYPE_CHECKING

from roomestim.model import (
    ListenerArea,
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
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
) -> RoomModel:
    """Return a new RoomModel with the given fields replaced.

    ``floor_polygon`` is not modified (v0.16 scope; v0.17 will add
    ``floor_polygon`` evolution for door/window/obstacle schema extension).

    The returned instance uses a *shallow copy* of the surfaces list so the
    caller's original list cannot mutate the new room's surface collection.
    The Surface objects themselves are ``frozen=True`` (ADR 0002 invariant).

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

    Returns
    -------
    RoomModel
        New RoomModel instance.
    """
    new_surfaces = list(surfaces) if surfaces is not None else list(room.surfaces)
    new_listener_area = listener_area if listener_area is not None else room.listener_area
    new_name = name if name is not None else room.name

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


__all__ = [
    "evolve_surface",
    "evolve_room",
    "evolve_room_material",
    "evolve_room_materials_bulk",
]
