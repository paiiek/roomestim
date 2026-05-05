"""Default listener-area construction.

For RoomPlan/Polycam adapters where the user has not specified an explicit
listener region, build a square 1.5 m x 1.5 m listener area centred on the
floor centroid. If the floor polygon is concave and the geometric centroid
falls outside the polygon, fall back to ``shapely.point_on_surface(...)``
and emit :class:`kWarnConcaveListenerCentroid`.
"""

from __future__ import annotations

import warnings

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.model import ListenerArea, Point2, canonicalize_ccw

__all__ = ["default_listener_area", "kWarnConcaveListenerCentroid"]


class kWarnConcaveListenerCentroid(UserWarning):
    """Warn that the floor polygon's geometric centroid lies outside the polygon.

    Emitted by :func:`default_listener_area` when the floor is concave (e.g.,
    L-shape) and ``shapely.point_on_surface`` is used as a fallback.
    """


def default_listener_area(
    floor_polygon: list[Point2],
    *,
    half_size_m: float = 0.75,
    height_m: float = 1.20,
) -> ListenerArea:
    """Build a default :class:`ListenerArea` centred on the floor polygon.

    The returned listener area is a ``2 * half_size_m`` square (CCW) centred
    on the floor centroid (or, for concave polygons whose geometric centroid
    lies outside, on ``shapely.point_on_surface(...)``).

    Parameters
    ----------
    floor_polygon:
        2D floor polygon as a list of :class:`Point2` ``(x, z)`` in metres.
    half_size_m:
        Half-side of the square listener area in metres. Defaults to 0.75 m
        (1.5 m x 1.5 m total).
    height_m:
        Listener ear height in metres. Defaults to 1.20 m (seated/standing
        compromise per design plan).
    """
    coords: list[tuple[float, float]] = [(p.x, p.z) for p in floor_polygon]
    shp = ShapelyPolygon(coords)
    centroid_pt = shp.centroid
    if not shp.contains(centroid_pt):
        warnings.warn(
            "Floor polygon centroid lies outside the polygon (concave); "
            "using shapely.point_on_surface as fallback.",
            kWarnConcaveListenerCentroid,
            stacklevel=2,
        )
        centroid_pt = shp.representative_point()

    cx: float = float(centroid_pt.x)
    cz: float = float(centroid_pt.y)  # shapely uses (x, y) for our (x, z) plane

    listener_polygon = [
        Point2(cx - half_size_m, cz - half_size_m),
        Point2(cx + half_size_m, cz - half_size_m),
        Point2(cx + half_size_m, cz + half_size_m),
        Point2(cx - half_size_m, cz + half_size_m),
    ]
    listener_polygon = canonicalize_ccw(listener_polygon)
    return ListenerArea(
        polygon=listener_polygon,
        centroid=Point2(cx, cz),
        height_m=height_m,
    )


# Re-export Point check for tests: shapely Point is needed by callers that
# want to do their own contains() checks. We do NOT re-export because the
# adapter module imports shapely directly.
_ = ShapelyPoint  # silence unused-import lint
