"""Mesh -> 2D floor polygon reconstruction (concave-hull footprint).

:func:`floor_polygon_from_mesh` projects a 3D mesh vertex cloud onto the
floor plane and recovers a *concave* footprint via :func:`shapely.concave_hull`.
Unlike a convex hull, the concave hull preserves re-entrant corners, so an
L-shaped or otherwise non-shoebox room keeps its notch instead of collapsing
to its bounding hull.

The default :data:`MeshAdapter` floor path remains convex-hull based; this
module is the opt-in concave reconstruction selected via
``floor_reconstruction="concave"`` (or the ``ROOMESTIM_MESH_FLOOR_RECON``
environment override). See ``roomestim/adapters/mesh.py``.
"""

from __future__ import annotations

import numpy as np
from shapely import concave_hull
from shapely.geometry import MultiPoint, MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.geom.polygon import is_simple_polygon
from roomestim.model import Point2, canonicalize_ccw

__all__ = ["floor_polygon_from_mesh"]

# Concave-hull tightness. ``ratio=1.0`` is the convex hull; ``ratio→0.0``
# over-tightens into a jagged boundary that hugs every outlier. ``0.4`` is the
# empirically-chosen midpoint: it recovers the re-entrant notch of an L-shaped
# room (area within a few percent of truth) while staying robust to the dense,
# slightly-noisy vertex grids that LiDAR/photogrammetry scans produce.
_DEFAULT_RATIO = 0.4

# Douglas-Peucker simplification tolerance (metres). ``concave_hull`` over a
# dense scan emits many near-collinear boundary coordinates; a 5 cm tolerance
# collapses those into clean straight edges (and drops sub-5 cm scan jitter)
# without eroding real structural corners, which are separated by tens of
# centimetres or more.
_SIMPLIFY_TOLERANCE_M = 0.05


def floor_polygon_from_mesh(
    mesh_vertices: np.ndarray,
    *,
    ratio: float = _DEFAULT_RATIO,
) -> list[Point2]:
    """Reconstruct a 2D floor polygon from a 3D mesh vertex cloud.

    Projects the cloud onto the floor plane (``x = v[0]``, ``z = v[2]``, the
    :mod:`roomestim.adapters.mesh` convention), computes a concave hull, and
    regularizes the resulting ring. The concave hull preserves re-entrant
    corners, so non-shoebox footprints (e.g. L-shaped rooms) survive instead
    of collapsing to their convex bounding hull.

    Parameters
    ----------
    mesh_vertices:
        ``(N, 3)`` array of mesh vertex positions in listener-frame metres.
    ratio:
        Concave-hull tightness in ``(0, 1]`` passed to
        :func:`shapely.concave_hull`. ``1.0`` reproduces the convex hull;
        smaller values hug concavities more tightly. Defaults to
        :data:`_DEFAULT_RATIO` (``0.4``). NaN fails the ``(0, 1]`` guard
        and raises ``ValueError``.

    Returns
    -------
    list[Point2]
        CCW floor polygon (``(x, z)`` vertices, closing duplicate stripped).

    Raises
    ------
    ValueError
        If ``ratio`` is outside ``(0, 1]`` (including NaN); if fewer than 3
        distinct points project onto the floor plane; or if the concave hull
        degenerates into a non-polygon / collinear / self-intersecting ring.
        The :data:`MeshAdapter` caller converts the degeneracy case into a
        convex-hull fallback with a warning.

    Notes
    -----
    **Dense-cloud assumption.** The concave-hull approach gives accurate
    footprint recovery only when the projected vertex cloud is *dense* — a
    point spacing of roughly 0.25 m or finer (e.g. a LiDAR scan or
    photogrammetry mesh with thousands of floor/wall/ceiling vertices). On
    *sparse* low-poly meshes (e.g. a 6-point extruded L prism with only one
    vertex per footprint corner) the boundary samples are too coarse for
    ``shapely.concave_hull`` to resolve the notch, and the recovered area
    undershoots truth by ~10–20 %. In those cases callers should either
    increase ``ratio`` toward ``1.0`` (approaching the convex hull) or use
    the explicit convex path in :class:`MeshAdapter`.
    """
    if not (0.0 < ratio <= 1.0):
        raise ValueError(
            f"floor_polygon_from_mesh: ratio must be in (0, 1], got {ratio}"
        )

    vertices = np.asarray(mesh_vertices, dtype=float)
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError(
            f"floor_polygon_from_mesh: expected (N, 3) vertex array, got shape "
            f"{vertices.shape}"
        )

    # Project to the (x, z) floor plane and deduplicate. ``concave_hull`` needs
    # at least 3 distinct points to bound an area.
    xz_points = {(float(v[0]), float(v[2])) for v in vertices}
    if len(xz_points) < 3:
        raise ValueError(
            f"floor_polygon_from_mesh: only {len(xz_points)} distinct projected "
            f"point(s); at least 3 are required for a footprint."
        )

    hull = concave_hull(MultiPoint(sorted(xz_points)), ratio=ratio)

    # B3 degeneracy guards. ``concave_hull`` can return a MultiPolygon (take the
    # largest-area component), a Polygon with holes (use the exterior — a floor
    # footprint is a simple ring), or a non-areal geometry on collinear/empty
    # input (raise so the caller can fall back to convex).
    if isinstance(hull, MultiPolygon):
        hull = max(hull.geoms, key=lambda g: g.area)
    if not isinstance(hull, ShapelyPolygon) or hull.is_empty or hull.area <= 0.0:
        raise ValueError(
            "floor_polygon_from_mesh: concave hull is not a usable polygon "
            f"(geom_type={hull.geom_type!r}); the projected cloud appears "
            "degenerate (collinear, disconnected, or empty)."
        )

    # Regularize: drop near-collinear coordinates from dense scans.
    simplified = hull.simplify(_SIMPLIFY_TOLERANCE_M, preserve_topology=True)
    if isinstance(simplified, ShapelyPolygon) and not simplified.is_empty:
        ring_source = simplified
    else:
        ring_source = hull

    # Exterior only — discard any interior rings (holes); a floor is a simple ring.
    exterior_coords: list[tuple[float, float]] = [
        (float(x), float(z)) for x, z in ring_source.exterior.coords[:-1]
    ]
    if not is_simple_polygon(exterior_coords):
        raise ValueError(
            "floor_polygon_from_mesh: reconstructed ring is not a simple "
            "polygon (self-intersecting or collinear)."
        )

    return canonicalize_ccw([Point2(x, z) for x, z in exterior_coords])
