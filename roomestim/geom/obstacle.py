"""Obstacle geometry primitives for obstacle-aware speaker placement (P7.1).

Plan-view (top-down, ``x``/``z``) axis-aligned footprints of free-standing
objects, a single clearance predicate (0 when a point is inside a box), and a
plan-view line-of-sight test. Pure shapely + the core model — **no new
dependency**, no acoustic claim. The honesty framing (axis-aligned box,
plan-view distance, no diffraction/height unless opted in) lives in
:data:`roomestim.place.obstacle_aware.OBSTACLE_AWARE_PLACEMENT_NOTE`.

Only :data:`roomestim.model.FREESTANDING_OBJECT_KINDS`
(``column``/``sofa``/``table``/``bed``/``storage``) are floor obstacles;
``door``/``window`` (``WALL_ATTACHED_OBJECT_KINDS``) are per-wall α overrides,
NOT boxes on the floor, and are excluded.
"""

from __future__ import annotations

from shapely.geometry import LineString
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.model import (
    FREESTANDING_OBJECT_KINDS,
    Object,
    Point3,
    RoomModel,
)


def object_footprint(obj: Object) -> ShapelyPolygon | None:
    """Axis-aligned plan ``(x, z)`` rectangle from ``anchor ± (width/2, depth/2)``.

    Returns ``None`` for wall-attached objects (``door``/``window``) and for
    zero-area boxes (non-positive width or depth). Object rotation is NOT
    modelled — the box is axis-aligned in the room frame (honest limit, see the
    placement NOTE).
    """
    if obj.kind not in FREESTANDING_OBJECT_KINDS:
        return None
    half_w = obj.width_m / 2.0
    half_d = obj.depth_m / 2.0
    if half_w <= 0.0 or half_d <= 0.0:
        return None
    cx = obj.anchor.x
    cz = obj.anchor.z
    poly = ShapelyPolygon(
        [
            (cx - half_w, cz - half_d),
            (cx + half_w, cz - half_d),
            (cx + half_w, cz + half_d),
            (cx - half_w, cz + half_d),
        ]
    )
    if not poly.is_valid or poly.is_empty or poly.area <= 0.0:
        return None
    return poly


def freestanding_footprints(room: RoomModel) -> list[ShapelyPolygon]:
    """Plan footprints for every free-standing object in ``room`` (None-filtered)."""
    footprints: list[ShapelyPolygon] = []
    for obj in room.objects:
        fp = object_footprint(obj)
        if fp is not None:
            footprints.append(fp)
    return footprints


def plan_clearance_m(x: float, z: float, footprints: list[ShapelyPolygon]) -> float:
    """Min plan-view distance from ``(x, z)`` to any footprint.

    Uses shapely ``.distance()``, which is ``0.0`` when the point is covered
    (inside a box). Returns ``+inf`` when there are no footprints (a point is
    infinitely clear of nothing).
    """
    if not footprints:
        return float("inf")
    pt = ShapelyPoint(x, z)
    return min(fp.distance(pt) for fp in footprints)


def position_is_clear(
    x: float, z: float, footprints: list[ShapelyPolygon], *, clearance_m: float
) -> bool:
    """True iff ``(x, z)`` is outside every box by at least ``clearance_m``.

    A single predicate ``plan_clearance_m(...) >= clearance_m`` enforces both
    "not inside any box" (distance ``0`` inside) and "≥ margin".
    """
    return plan_clearance_m(x, z, footprints) >= clearance_m


def line_of_sight_blocked(
    spk: Point3,
    listener: Point3,
    footprints: list[ShapelyPolygon],
    *,
    height_aware: bool = False,
    object_tops_m: list[float] | None = None,
) -> bool:
    """True iff the plan-view segment ``spk→listener`` intersects any footprint.

    Plan-view only (top-down ``x``/``z``); ignores diffraction and, unless
    ``height_aware`` is enabled, obstacle/speaker height. When ``height_aware``
    is set and ``object_tops_m`` aligns index-for-index with ``footprints``, a
    footprint whose top is below BOTH endpoints' ``y`` is skipped (a speaker and
    listener both above a short column are not occluded by it).
    """
    seg = LineString([(spk.x, spk.z), (listener.x, listener.z)])
    for i, fp in enumerate(footprints):
        if (
            height_aware
            and object_tops_m is not None
            and i < len(object_tops_m)
            and object_tops_m[i] < spk.y
            and object_tops_m[i] < listener.y
        ):
            continue
        if seg.intersects(fp):
            return True
    return False


__all__ = [
    "object_footprint",
    "freestanding_footprints",
    "plan_clearance_m",
    "position_is_clear",
    "line_of_sight_blocked",
]
