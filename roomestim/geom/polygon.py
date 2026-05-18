"""Shared geometry utilities for planar polygon area and room volume.

Provenance: ``predictor.py`` + ``ace_challenge.py`` 두 곳 duplicate를 v0.15.1에서
통합. D29 lane separation은 web↔core 경계이며 core 내부 추출은 OK
(v0.15.1-patch §2 결정).

Public API
----------
- :func:`polygon_area_3d` — 3-D polygon area via Newell's normal-vector method.
- :func:`room_volume` — floor-area × ceiling-height (prismatic room).
- :func:`shoelace_2d` — signed-area shoelace for 2-D polygon; returns absolute area.
"""
from __future__ import annotations

import math

from roomestim.model import RoomModel

__all__ = ["polygon_area_3d", "room_volume", "shoelace_2d"]


def shoelace_2d(coords: list[tuple[float, float]]) -> float:
    """Signed-area shoelace formula; returns absolute area.

    Parameters
    ----------
    coords:
        List of ``(x, y)`` 2-D coordinate pairs (at least 3 required;
        fewer returns 0.0).
    """
    n = len(coords)
    if n < 3:
        return 0.0
    acc = 0.0
    for i in range(n):
        j = (i + 1) % n
        acc += coords[i][0] * coords[j][1]
        acc -= coords[j][0] * coords[i][1]
    return abs(acc) * 0.5


def polygon_area_3d(polygon: object) -> float:
    """Area of a 3-D polygon via Newell's normal-vector method.

    Parameters
    ----------
    polygon:
        Iterable of point objects with ``.x``, ``.y``, ``.z`` float attributes
        (at least 3 required; fewer returns 0.0).
    """
    pts = list(polygon)  # type: ignore[call-overload]
    n = len(pts)
    if n < 3:
        return 0.0
    nx = ny = nz = 0.0
    for i in range(n):
        j = (i + 1) % n
        a = pts[i]
        b = pts[j]
        nx += (a.y - b.y) * (a.z + b.z)
        ny += (a.z - b.z) * (a.x + b.x)
        nz += (a.x - b.x) * (a.y + b.y)
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def room_volume(room: RoomModel) -> float:
    """Floor-area × ceiling-height (assumes prismatic / extruded room).

    Parameters
    ----------
    room:
        :class:`roomestim.model.RoomModel` instance. Uses
        ``room.floor_polygon`` (x, z coordinates) and
        ``room.ceiling_height_m``.

    Notes
    -----
    Convex simple polygons (incl. all ACE shoeboxes) return values byte-equal
    to ``shapely.geometry.Polygon(coords).area * ceiling_height_m`` — the
    predecessor implementation in ``ace_challenge.py`` at v0.15.0. Shoelace
    and shapely diverge for self-intersecting polygons (bow-ties): shoelace
    returns the signed-area magnitude, shapely returns 0.0. Self-intersecting
    floor polygons are not a supported input shape.
    """
    floor_coords = [(p.x, p.z) for p in room.floor_polygon]
    return shoelace_2d(floor_coords) * float(room.ceiling_height_m)
