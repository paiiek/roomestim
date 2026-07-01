"""Unit tests for ``roomestim.geom.obstacle`` — P7.1 obstacle primitives."""

from __future__ import annotations

from types import SimpleNamespace

from roomestim.geom.obstacle import (
    freestanding_footprints,
    line_of_sight_blocked,
    object_footprint,
    plan_clearance_m,
    position_is_clear,
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
