"""Obstacle geometry primitives for obstacle-aware speaker placement (P7).

Two clearance models over free-standing objects, plus a plan-view line-of-sight
test. Pure shapely/math + the core model — **no new dependency**, no acoustic
claim:

* Plan-view (top-down, ``x``/``z``) axis-aligned footprints and the
  ``plan_clearance_m``/``position_is_clear`` predicate (0 when a point is inside
  a box).
* 3D (height-aware) axis-aligned :data:`Box` es (``object_box``/
  ``freestanding_boxes``) and ``clearance_3d_m``/``position_is_clear_3d`` —
  point-to-AABB Euclidean distance so a ceiling/high-wall mount cleanly ABOVE a
  short object is correctly allowed instead of rejected for a footprint overlap
  (P7.5).

Line-of-sight (``line_of_sight_blocked``) is a plan-view segment/box test with
an opt-in ``height_aware`` mode that skips an object whose top is below both
endpoints; the obstacle-aware placers enable it (aligned ``object_tops_m`` from
the boxes) so a mount above short furniture is not falsely occluded. The honesty
framing (axis-aligned box, height-aware clearance + LOS, no diffraction) lives in
:data:`roomestim.place.obstacle_aware.OBSTACLE_AWARE_PLACEMENT_NOTE`.

Only :data:`roomestim.model.FREESTANDING_OBJECT_KINDS`
(``column``/``sofa``/``table``/``bed``/``storage``) are floor obstacles;
``door``/``window`` (``WALL_ATTACHED_OBJECT_KINDS``) are per-wall α overrides,
NOT boxes on the floor, and are excluded.
"""

from __future__ import annotations

import math

from shapely.geometry import LineString
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.model import (
    FREESTANDING_OBJECT_KINDS,
    Object,
    Point3,
    RoomModel,
)

#: An axis-aligned 3D obstacle box as ``(x0, x1, z0, z1, y0, y1)`` with
#: ``x0<=x1``, ``z0<=z1``, ``y0<=y1``. ``y0`` is the object's floor anchor and
#: ``y1 = y0 + height_m`` (the top). Used by the height-aware (3D) clearance so a
#: ceiling mount directly above a short object is correctly allowed.
Box = tuple[float, float, float, float, float, float]


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
    # Non-finite dims would make shapely raise on ring construction; treat a
    # NaN/inf-dimensioned object as a degenerate (skipped) footprint, matching
    # the zero-area contract instead of crashing.
    if not (math.isfinite(half_w) and math.isfinite(half_d)):
        return None
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


def object_box(obj: Object) -> Box | None:
    """Axis-aligned 3D box ``(x0, x1, z0, z1, y0, y1)`` for a free-standing object.

    The ``x``/``z`` extent is ``anchor ± (width/2, depth/2)`` — IDENTICAL to
    :func:`object_footprint`. The ``y`` extent spans ``[anchor.y, anchor.y +
    height_m]``: the object stands on the floor at ``anchor.y`` and rises by its
    height. Returns ``None`` for EXACTLY what :func:`object_footprint` rejects
    (wall-attached ``door``/``window``, zero-area and degenerate/non-finite
    footprints) so :func:`freestanding_footprints` and :func:`freestanding_boxes`
    stay aligned index-for-index — a caller may zip plan footprints with box
    tops. No extra height exclusion; a zero-height box is a flat floor patch.
    """
    # Delegate the plan-view validity gate to object_footprint so the two lists
    # exclude the SAME objects (guards NaN/degenerate dims identically), keeping
    # freestanding_footprints and freestanding_boxes aligned index-for-index.
    if object_footprint(obj) is None:
        return None
    half_w = obj.width_m / 2.0
    half_d = obj.depth_m / 2.0
    cx = obj.anchor.x
    cz = obj.anchor.z
    y_a = obj.anchor.y
    y_b = obj.anchor.y + obj.height_m
    return (
        cx - half_w,
        cx + half_w,
        cz - half_d,
        cz + half_d,
        min(y_a, y_b),
        max(y_a, y_b),
    )


def freestanding_boxes(room: RoomModel) -> list[Box]:
    """3D boxes for every free-standing object in ``room`` (None-filtered)."""
    boxes: list[Box] = []
    for obj in room.objects:
        box = object_box(obj)
        if box is not None:
            boxes.append(box)
    return boxes


def clearance_3d_m(x: float, y: float, z: float, boxes: list[Box]) -> float:
    """Min Euclidean distance from ``(x, y, z)`` to any axis-aligned box.

    Standard point-to-AABB distance per axis (``dx = max(x0 - x, 0, x - x1)``,
    likewise for ``y``/``z``), then ``sqrt(dx² + dy² + dz²)``. Returns ``0.0``
    when the point is inside a box, and ``+inf`` when there are no boxes (a point
    is infinitely clear of nothing). Unlike :func:`plan_clearance_m` this is
    height-aware, so a ceiling mount directly above a short object reports the
    true (large) vertical clearance instead of a plan-view overlap.
    """
    if not boxes:
        return float("inf")
    best = float("inf")
    for x0, x1, z0, z1, y0, y1 in boxes:
        dx = max(x0 - x, 0.0, x - x1)
        dy = max(y0 - y, 0.0, y - y1)
        dz = max(z0 - z, 0.0, z - z1)
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        if d < best:
            best = d
    return best


def position_is_clear_3d(
    x: float, y: float, z: float, boxes: list[Box], *, clearance_m: float
) -> bool:
    """True iff ``(x, y, z)`` is outside every 3D box by at least ``clearance_m``.

    Height-aware counterpart of :func:`position_is_clear`: the single predicate
    ``clearance_3d_m(...) >= clearance_m`` enforces both "not inside any box" and
    "≥ margin", but in 3D — so a speaker cleanly above a short piece of furniture
    is NOT rejected for a plan-view footprint overlap.
    """
    return clearance_3d_m(x, y, z, boxes) >= clearance_m


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
    "Box",
    "object_footprint",
    "freestanding_footprints",
    "plan_clearance_m",
    "position_is_clear",
    "object_box",
    "freestanding_boxes",
    "clearance_3d_m",
    "position_is_clear_3d",
    "line_of_sight_blocked",
]
