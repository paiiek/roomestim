"""Point-to-surface distance + closest point (clamped to the surface polygon).

Shared primitive for install-time speaker snapping (``edit.snap_layout_to_surfaces``).
A :class:`~roomestim.model.Surface` is a bounded planar polygon in 3D; this module
projects a query point onto the surface plane and clamps it to the polygon, so the
returned closest point always lies ON the surface (its interior or boundary).

Mirrors the geometry validated in the Placement-Sensitivity measurement
(spike-vggt-multiview/scripts/placement_sensitivity.py): an installer mounting a
planned speaker onto the nearest real wall/ceiling.
"""

from __future__ import annotations

import math

import numpy as np
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import nearest_points

from roomestim.model import Point3, Surface


def closest_point_on_surface(point: Point3, surface: Surface) -> tuple[float, Point3]:
    """Return ``(distance_m, closest_point)`` from ``point`` to ``surface``.

    The closest point is clamped to the surface polygon (interior or boundary),
    so it always lies on the physical surface. Distance is the 3D Euclidean
    distance to that clamped point.

    A degenerate surface (fewer than 3 vertices, or a collinear first three)
    falls back to the distance to its first vertex — never raises, mirroring the
    fail-safe style used elsewhere in :mod:`roomestim`.
    """
    poly = np.array([[q.x, q.y, q.z] for q in surface.polygon], dtype=float)
    if poly.shape[0] < 3:
        p0 = poly[0] if poly.shape[0] else np.zeros(3)
        return _fallback(point, p0)

    p0 = poly[0]
    u_raw = poly[1] - poly[0]
    u_norm = float(np.linalg.norm(u_raw))
    if u_norm == 0.0:
        return _fallback(point, p0)
    u = u_raw / u_norm
    n_raw = np.cross(poly[1] - poly[0], poly[2] - poly[0])
    n_norm = float(np.linalg.norm(n_raw))
    if n_norm == 0.0:
        return _fallback(point, p0)
    normal = n_raw / n_norm
    v = np.cross(normal, u)

    pt = np.array([point.x, point.y, point.z], dtype=float)
    rel = pt - p0
    uu, vv, normal_d = float(rel @ u), float(rel @ v), float(rel @ normal)

    coords2d = [(float((q - p0) @ u), float((q - p0) @ v)) for q in poly]
    spoly = ShapelyPolygon(coords2d)
    query = ShapelyPoint(uu, vv)
    if spoly.is_valid and spoly.contains(query):
        cu, cv, in_plane = uu, vv, 0.0
    elif spoly.is_valid:
        near = nearest_points(spoly.exterior, query)[0]
        cu, cv = float(near.x), float(near.y)
        in_plane = float(math.hypot(cu - uu, cv - vv))
    else:
        # Degenerate / self-intersecting projection: clamp to the nearest
        # polygon vertex (a safe over-estimate, never raises).
        d2 = [(cx - uu) ** 2 + (cz - vv) ** 2 for cx, cz in coords2d]
        cu, cv = coords2d[int(np.argmin(d2))]
        in_plane = float(math.hypot(cu - uu, cv - vv))

    closest = p0 + cu * u + cv * v
    dist = math.hypot(in_plane, abs(normal_d))
    return dist, Point3(float(closest[0]), float(closest[1]), float(closest[2]))


def _fallback(point: Point3, p0: np.ndarray) -> tuple[float, Point3]:
    d = float(np.linalg.norm(np.array([point.x, point.y, point.z]) - p0))
    return d, Point3(float(p0[0]), float(p0[1]), float(p0[2]))
