"""Unit tests for ``roomestim.geom.obstacle`` — P7.1 obstacle primitives."""

from __future__ import annotations

from types import SimpleNamespace

from roomestim.geom.obstacle import (
    clearance_3d_m,
    freestanding_boxes,
    freestanding_footprints,
    line_of_sight_blocked,
    object_box,
    object_footprint,
    plan_clearance_m,
    position_is_clear,
    position_is_clear_3d,
)
from roomestim.model import Object, Point3


def _column(cx: float, cz: float, w: float = 0.4, d: float = 0.4) -> Object:
    return Object(
        kind="column",
        anchor=Point3(x=cx, y=0.0, z=cz),
        width_m=w,
        height_m=2.5,
        depth_m=d,
    )


# --------------------------------------------------------------------------- #
# object_footprint
# --------------------------------------------------------------------------- #


def test_object_footprint_axis_aligned_rect() -> None:
    fp = object_footprint(_column(1.0, 0.5, w=0.4, d=0.6))
    assert fp is not None
    minx, minz, maxx, maxz = fp.bounds
    assert abs(minx - 0.8) < 1e-9
    assert abs(maxx - 1.2) < 1e-9
    assert abs(minz - 0.2) < 1e-9
    assert abs(maxz - 0.8) < 1e-9
    assert abs(fp.area - 0.24) < 1e-9


def test_object_footprint_none_for_wall_attached() -> None:
    door = Object(
        kind="door",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=0.9,
        height_m=2.0,
        depth_m=0.0,
        wall_index=0,
    )
    assert object_footprint(door) is None


def test_object_footprint_none_for_zero_area() -> None:
    assert object_footprint(_column(0.0, 0.0, w=0.0, d=0.4)) is None
    assert object_footprint(_column(0.0, 0.0, w=0.4, d=0.0)) is None


def test_freestanding_footprints_filters_walls_and_zero() -> None:
    # ``freestanding_footprints`` reads only ``room.objects``.
    room = SimpleNamespace(
        objects=[
            _column(1.0, 0.5),
            _column(0.0, 0.0, w=0.0, d=0.4),  # zero-area -> dropped
            Object(
                kind="window",
                anchor=Point3(x=0.0, y=1.0, z=2.0),
                width_m=1.0,
                height_m=1.0,
                depth_m=0.0,
                wall_index=1,
            ),  # wall-attached -> dropped
        ]
    )
    fps = freestanding_footprints(room)  # type: ignore[arg-type]
    assert len(fps) == 1


# --------------------------------------------------------------------------- #
# clearance
# --------------------------------------------------------------------------- #


def test_point_inside_box_clearance_zero() -> None:
    fps = [object_footprint(_column(1.0, 0.5))]
    fps = [f for f in fps if f is not None]
    # centre of the box
    assert plan_clearance_m(1.0, 0.5, fps) == 0.0
    assert not position_is_clear(1.0, 0.5, fps, clearance_m=0.30)


def test_clearance_margin_outside_box() -> None:
    fps = [f for f in [object_footprint(_column(1.0, 0.5, w=0.4, d=0.4))] if f]
    # box is x[0.8,1.2] z[0.3,0.7]; a point 0.5 m to the right of the near edge
    d = plan_clearance_m(1.7, 0.5, fps)  # 1.7 - 1.2 = 0.5
    assert abs(d - 0.5) < 1e-9
    assert position_is_clear(1.7, 0.5, fps, clearance_m=0.30)
    assert not position_is_clear(1.7, 0.5, fps, clearance_m=0.6)


def test_clearance_no_footprints_is_infinite() -> None:
    assert plan_clearance_m(0.0, 0.0, []) == float("inf")
    assert position_is_clear(0.0, 0.0, [], clearance_m=1000.0)


# --------------------------------------------------------------------------- #
# 3D box + height-aware clearance (P7.5 — obstacle-avoid defect fix)
# --------------------------------------------------------------------------- #


def _low_table(cx: float, cz: float, h: float = 0.7) -> Object:
    """A short free-standing table centred at ``(cx, cz)`` on the floor."""
    return Object(
        kind="table",
        anchor=Point3(x=cx, y=0.0, z=cz),
        width_m=0.8,
        height_m=h,
        depth_m=0.8,
    )


def test_object_box_extents_and_y_span() -> None:
    box = object_box(_low_table(1.0, 0.5, h=0.7))
    assert box is not None
    x0, x1, z0, z1, y0, y1 = box
    assert abs(x0 - 0.6) < 1e-9
    assert abs(x1 - 1.4) < 1e-9
    assert abs(z0 - 0.1) < 1e-9
    assert abs(z1 - 0.9) < 1e-9
    assert abs(y0 - 0.0) < 1e-9
    assert abs(y1 - 0.7) < 1e-9


def test_object_box_none_for_wall_attached_and_zero_area() -> None:
    door = Object(
        kind="door",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=0.9,
        height_m=2.0,
        depth_m=0.0,
        wall_index=0,
    )
    assert object_box(door) is None
    zero = Object(kind="table", anchor=Point3(0.0, 0.0, 0.0), width_m=0.0,
                  height_m=0.7, depth_m=0.8)
    assert object_box(zero) is None


def test_clearance_3d_point_above_short_box_is_clear() -> None:
    # 0.7 m table; a point 2.0 m up (e.g. a ceiling mount) is > clearance away
    # even though its plan-view (x,z) sits directly over the footprint.
    boxes = [b for b in [object_box(_low_table(0.0, 0.0, h=0.7))] if b]
    d = clearance_3d_m(0.0, 2.0, 0.0, boxes)  # dy = 2.0 - 0.7 = 1.3
    assert abs(d - 1.3) < 1e-9
    assert position_is_clear_3d(0.0, 2.0, 0.0, boxes, clearance_m=0.30)
    # plan-view would (wrongly) reject the same point — it overlaps the footprint
    assert not position_is_clear(
        0.0, 0.0, [f for f in [object_footprint(_low_table(0.0, 0.0))] if f],
        clearance_m=0.30,
    )


def test_clearance_3d_point_inside_box_is_zero_and_not_clear() -> None:
    boxes = [b for b in [object_box(_low_table(0.0, 0.0, h=0.7))] if b]
    assert clearance_3d_m(0.0, 0.35, 0.0, boxes) == 0.0  # inside the solid box
    assert not position_is_clear_3d(0.0, 0.35, 0.0, boxes, clearance_m=0.30)


def test_clearance_3d_point_beside_within_margin_not_clear() -> None:
    # box x[-0.4,0.4]; a point 0.1 m to the right at a height within [0,0.7]
    boxes = [b for b in [object_box(_low_table(0.0, 0.0, h=0.7))] if b]
    d = clearance_3d_m(0.5, 0.35, 0.0, boxes)  # dx = 0.5 - 0.4 = 0.1, dy = 0
    assert abs(d - 0.1) < 1e-9
    assert not position_is_clear_3d(0.5, 0.35, 0.0, boxes, clearance_m=0.30)


def test_clearance_3d_no_boxes_is_infinite() -> None:
    assert clearance_3d_m(0.0, 0.0, 0.0, []) == float("inf")
    assert position_is_clear_3d(0.0, 0.0, 0.0, [], clearance_m=1000.0)


def test_freestanding_boxes_filters_walls_and_zero() -> None:
    room = SimpleNamespace(
        objects=[
            _low_table(1.0, 0.5),
            Object(kind="table", anchor=Point3(0.0, 0.0, 0.0), width_m=0.0,
                   height_m=0.7, depth_m=0.8),  # zero-area -> dropped
            Object(
                kind="window",
                anchor=Point3(x=0.0, y=1.0, z=2.0),
                width_m=1.0,
                height_m=1.0,
                depth_m=0.0,
                wall_index=1,
            ),  # wall-attached -> dropped
        ]
    )
    assert len(freestanding_boxes(room)) == 1  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# line of sight
# --------------------------------------------------------------------------- #


def test_line_of_sight_blocked_true_through_box() -> None:
    fps = [f for f in [object_footprint(_column(0.0, 0.0, w=0.4, d=0.4))] if f]
    spk = Point3(x=-2.0, y=1.0, z=0.0)
    listener = Point3(x=2.0, y=1.0, z=0.0)
    assert line_of_sight_blocked(spk, listener, fps) is True


def test_line_of_sight_clear_false_when_box_off_axis() -> None:
    fps = [f for f in [object_footprint(_column(0.0, 3.0, w=0.4, d=0.4))] if f]
    spk = Point3(x=-2.0, y=1.0, z=0.0)
    listener = Point3(x=2.0, y=1.0, z=0.0)
    assert line_of_sight_blocked(spk, listener, fps) is False


def test_line_of_sight_height_aware_skips_short_box() -> None:
    fps = [f for f in [object_footprint(_column(0.0, 0.0, w=0.4, d=0.4))] if f]
    spk = Point3(x=-2.0, y=2.0, z=0.0)
    listener = Point3(x=2.0, y=2.0, z=0.0)
    # plan-view says blocked
    assert line_of_sight_blocked(spk, listener, fps) is True
    # height-aware: a 1.0 m column top is below both 2.0 m endpoints -> not blocked
    assert (
        line_of_sight_blocked(
            spk, listener, fps, height_aware=True, object_tops_m=[1.0]
        )
        is False
    )
    # a tall box (top above endpoints) still blocks
    assert (
        line_of_sight_blocked(
            spk, listener, fps, height_aware=True, object_tops_m=[2.5]
        )
        is True
    )
