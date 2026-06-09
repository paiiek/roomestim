"""Tests for the polygon image-source GEOMETRY-only enumerator (ADR 0040).

GEOMETRY ONLY — these tests assert image-source *positions* + visibility
pruning; they make NO RT60 / acoustic-accuracy claim (the polygon-ISM RT60
cascade is DEFERRED, see ADR 0040 §Status-update). numpy/shapely only — no
torch, no pyroomacoustics — so they run in the default gate lane.
"""

from __future__ import annotations

import math

import pytest

from roomestim.model import Point2, Point3
from roomestim.reconstruct.polygon_image_source import (
    ImagePath,
    ImageSource,
    _reflect_point_across_line_2d,
    first_order_image_sources,
    first_order_path_lengths,
)


def _wall_image(images: list[ImageSource], wall_index: int) -> ImageSource:
    """Return the single wall image produced by ``wall_index``."""
    matches = [
        im
        for im in images
        if im.surface_kind == "wall" and im.wall_index == wall_index
    ]
    assert len(matches) == 1, f"expected one image for wall {wall_index}"
    return matches[0]


def _surface_image(images: list[ImageSource], kind: str) -> ImageSource:
    matches = [im for im in images if im.surface_kind == kind]
    assert len(matches) == 1, f"expected one {kind} image"
    return matches[0]


def _assert_point_close(actual: Point3, expected: tuple[float, float, float]) -> None:
    assert math.isclose(actual.x, expected[0], abs_tol=1e-9), (actual, expected)
    assert math.isclose(actual.y, expected[1], abs_tol=1e-9), (actual, expected)
    assert math.isclose(actual.z, expected[2], abs_tol=1e-9), (actual, expected)


# --------------------------------------------------------------------------- #
# Test 1 — analytic shoebox: first-order image positions == analytic mirrors.
# --------------------------------------------------------------------------- #


def test_shoebox_first_order_positions_match_analytic_mirrors() -> None:
    """A known shoebox expressed as a 4-corner polygon: enumerated first-order
    image positions equal the analytic mirror positions (reflect the source
    across x=0, x=L, z=0, z=W and the floor/ceiling planes) to ~1e-9.

    Corners (0,0),(L,0),(L,W),(0,W) in the (x, z) floor plane → edges:
        edge 0: z=0, edge 1: x=L, edge 2: z=W, edge 3: x=0.
    """
    length_m = 6.0  # x extent (L)
    width_m = 4.0  # z extent (W)
    height_m = 3.0  # y extent (H)
    sx, sy, sz = 2.0, 1.2, 1.5
    source = Point3(sx, sy, sz)

    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(length_m, 0.0),
        Point2(length_m, width_m),
        Point2(0.0, width_m),
    ]

    images = first_order_image_sources(
        floor_polygon, ceiling_height_m=height_m, source=source
    )

    # 4 walls + floor + ceiling.
    assert len(images) == 6
    # Every shoebox wall image is visible (convex room).
    assert all(im.valid for im in images)

    # edge 0 → reflect across z=0.
    _assert_point_close(_wall_image(images, 0).position, (sx, sy, -sz))
    # edge 1 → reflect across x=L.
    _assert_point_close(
        _wall_image(images, 1).position, (2.0 * length_m - sx, sy, sz)
    )
    # edge 2 → reflect across z=W.
    _assert_point_close(
        _wall_image(images, 2).position, (sx, sy, 2.0 * width_m - sz)
    )
    # edge 3 → reflect across x=0.
    _assert_point_close(_wall_image(images, 3).position, (-sx, sy, sz))
    # floor plane y=0.
    _assert_point_close(_surface_image(images, "floor").position, (sx, -sy, sz))
    # ceiling plane y=H.
    _assert_point_close(
        _surface_image(images, "ceiling").position,
        (sx, 2.0 * height_m - sy, sz),
    )


def test_shoebox_exclude_floor_ceiling_returns_walls_only() -> None:
    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(5.0, 0.0),
        Point2(5.0, 3.0),
        Point2(0.0, 3.0),
    ]
    images = first_order_image_sources(
        floor_polygon,
        ceiling_height_m=2.5,
        source=Point3(1.0, 1.0, 1.0),
        include_floor_ceiling=False,
    )
    assert len(images) == 4
    assert all(im.surface_kind == "wall" for im in images)


# --------------------------------------------------------------------------- #
# Test 2 — non-convex (L-shape) visibility pruning.
# --------------------------------------------------------------------------- #


def test_lshape_visibility_prunes_off_segment_reflections() -> None:
    """Non-convex L-shape: images whose perpendicular reflection point falls
    outside the finite wall segment are pruned (valid=False) — a convex
    assumption would wrongly keep them.

    L-shape vertices (x, z):
        (0,0),(4,0),(4,2),(2,2),(2,4),(0,4)
    Edges:
        0:(0,0)-(4,0) z=0 | 1:(4,0)-(4,2) x=4 | 2:(4,2)-(2,2) z=2
        3:(2,2)-(2,4) x=2 | 4:(2,4)-(0,4) z=4 | 5:(0,4)-(0,0) x=0
    Source at (1,1) in the bottom arm. The supporting lines of the concave
    edges 2 (z=2, x in [2,4]) and 3 (x=2, z in [2,4]) put the perpendicular
    foot at (1,2) and (2,1) respectively — OFF those finite segments → pruned.
    """
    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(4.0, 0.0),
        Point2(4.0, 2.0),
        Point2(2.0, 2.0),
        Point2(2.0, 4.0),
        Point2(0.0, 4.0),
    ]
    source = Point3(1.0, 1.2, 1.0)

    images = first_order_image_sources(
        floor_polygon, ceiling_height_m=3.0, source=source
    )

    # Concave edges whose foot lands off the finite segment are pruned.
    assert _wall_image(images, 2).valid is False
    assert _wall_image(images, 3).valid is False
    # The image still carries a position + reflection point, just flagged invalid.
    pruned = _wall_image(images, 3)
    _assert_point_close(pruned.reflection_point, (2.0, 0.0, 1.0))

    # Edges whose foot lands on their segment remain valid.
    for valid_edge in (0, 1, 4, 5):
        assert _wall_image(images, valid_edge).valid is True, valid_edge

    # The pruned wall image (edge 3, line x=2) would be at the mirror x=3,
    # which a naive convex enumerator would have wrongly kept.
    _assert_point_close(pruned.position, (3.0, 1.2, 1.0))


def test_lshape_pruned_image_position_still_returned() -> None:
    """Pruning sets valid=False but does NOT drop the image from the list."""
    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(4.0, 0.0),
        Point2(4.0, 2.0),
        Point2(2.0, 2.0),
        Point2(2.0, 4.0),
        Point2(0.0, 4.0),
    ]
    images = first_order_image_sources(
        floor_polygon,
        ceiling_height_m=3.0,
        source=Point3(1.0, 1.0, 1.0),
        include_floor_ceiling=False,
    )
    # One image per edge regardless of validity.
    assert len(images) == 6
    assert {im.wall_index for im in images} == {0, 1, 2, 3, 4, 5}


# --------------------------------------------------------------------------- #
# Test 3 — determinism + input validation.
# --------------------------------------------------------------------------- #


def test_enumeration_is_deterministic() -> None:
    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(5.0, 0.0),
        Point2(5.0, 4.0),
        Point2(0.0, 4.0),
    ]
    source = Point3(2.0, 1.0, 1.0)
    first = first_order_image_sources(floor_polygon, 3.0, source)
    second = first_order_image_sources(floor_polygon, 3.0, source)
    assert first == second


def test_closing_duplicate_vertex_tolerated() -> None:
    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(5.0, 0.0),
        Point2(5.0, 4.0),
        Point2(0.0, 4.0),
        Point2(0.0, 0.0),  # explicit closing vertex
    ]
    images = first_order_image_sources(
        floor_polygon,
        ceiling_height_m=3.0,
        source=Point3(2.0, 1.0, 1.0),
        include_floor_ceiling=False,
    )
    assert len(images) == 4


@pytest.mark.parametrize("bad_height", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_ceiling_height_raises(bad_height: float) -> None:
    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(5.0, 0.0),
        Point2(5.0, 4.0),
        Point2(0.0, 4.0),
    ]
    with pytest.raises(ValueError):
        first_order_image_sources(
            floor_polygon, ceiling_height_m=bad_height, source=Point3(2.0, 1.0, 1.0)
        )


def test_too_few_vertices_raises() -> None:
    with pytest.raises(ValueError):
        first_order_image_sources(
            [Point2(0.0, 0.0), Point2(1.0, 0.0)],
            ceiling_height_m=3.0,
            source=Point3(0.5, 1.0, 0.0),
        )


def test_non_finite_source_raises() -> None:
    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(5.0, 0.0),
        Point2(5.0, 4.0),
        Point2(0.0, 4.0),
    ]
    with pytest.raises(ValueError):
        first_order_image_sources(
            floor_polygon,
            ceiling_height_m=3.0,
            source=Point3(float("nan"), 1.0, 1.0),
        )


def test_self_intersecting_polygon_raises() -> None:
    """A self-intersecting (bowtie) footprint fails loud, not silent garbage."""
    bowtie = [
        Point2(0.0, 0.0),
        Point2(5.0, 4.0),
        Point2(5.0, 0.0),
        Point2(0.0, 4.0),
    ]
    with pytest.raises(ValueError, match="simple"):
        first_order_image_sources(
            bowtie, ceiling_height_m=3.0, source=Point3(2.0, 1.0, 2.0)
        )


def test_degenerate_edge_reflection_raises() -> None:
    """A near-zero-length edge fails loud instead of producing a garbage foot."""
    with pytest.raises(ValueError, match="degenerate edge"):
        _reflect_point_across_line_2d(
            (1.0, 1.0), (2.0, 2.0), (2.0, 2.0 + 1e-12)
        )


# --------------------------------------------------------------------------- #
# Test 4 — receiver-relative first-order path length / TOA (geometry only).
# --------------------------------------------------------------------------- #


def _dist(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))


def _axis_aligned_specular_point(
    source: tuple[float, float, float],
    receiver: tuple[float, float, float],
    axis: int,
    plane_coord: float,
) -> tuple[float, float, float]:
    """True specular reflection point on an axis-aligned plane ``axis = c``.

    Derived INDEPENDENTLY of the module's stored ``reflection_point`` (which is
    computed for a receiver co-located with the source). For a plane normal to
    ``axis`` at ``plane_coord`` with source and receiver on the same side, the
    specular point interpolates source -> receiver in proportion to their
    perpendicular distances to the plane.
    """
    ds = abs(source[axis] - plane_coord)
    dr = abs(receiver[axis] - plane_coord)
    t = ds / (ds + dr)
    p = [source[k] + t * (receiver[k] - source[k]) for k in range(3)]
    p[axis] = plane_coord
    return (p[0], p[1], p[2])


def test_shoebox_path_length_matches_analytic_broken_path() -> None:
    """For a shoebox, each first-order ``path_length_m`` equals the analytic
    broken-path length ``‖S−P‖ + ‖P−R‖`` for the TRUE specular point P on that
    surface (derived independently of any stored reflection_point), to ~1e-9.
    """
    length_m = 6.0  # x extent (L), edges: x=0 and x=L
    width_m = 4.0  # z extent (W), edges: z=0 and z=W
    height_m = 3.0  # y extent (H)
    sx, sy, sz = 2.0, 1.2, 1.5
    source = Point3(sx, sy, sz)
    source_t = (sx, sy, sz)
    # Arbitrary receiver, strictly inside the room and != source.
    rx, ry, rz = 4.3, 2.1, 2.7
    receiver = Point3(rx, ry, rz)
    receiver_t = (rx, ry, rz)

    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(length_m, 0.0),
        Point2(length_m, width_m),
        Point2(0.0, width_m),
    ]
    images = first_order_image_sources(
        floor_polygon, ceiling_height_m=height_m, source=source
    )
    paths = first_order_path_lengths(images, receiver, sound_speed_m_s=343.0)

    # axis: 0=x, 1=y, 2=z. Map each surface to its plane.
    plane_for_wall = {
        0: (2, 0.0),  # edge 0: z=0
        1: (0, length_m),  # edge 1: x=L
        2: (2, width_m),  # edge 2: z=W
        3: (0, 0.0),  # edge 3: x=0
    }

    assert len(paths) == len(images) == 6
    for path in paths:
        im = path.image
        if im.surface_kind == "wall":
            axis, coord = plane_for_wall[im.wall_index]
        elif im.surface_kind == "floor":
            axis, coord = 1, 0.0
        else:  # ceiling
            axis, coord = 1, height_m
        p = _axis_aligned_specular_point(source_t, receiver_t, axis, coord)
        broken = _dist(source_t, p) + _dist(p, receiver_t)
        assert math.isclose(path.path_length_m, broken, abs_tol=1e-9), (
            im.surface_kind,
            im.wall_index,
            path.path_length_m,
            broken,
        )


def test_path_length_toa_units_and_speed_guard() -> None:
    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(6.0, 0.0),
        Point2(6.0, 4.0),
        Point2(0.0, 4.0),
    ]
    images = first_order_image_sources(
        floor_polygon, ceiling_height_m=3.0, source=Point3(2.0, 1.2, 1.5)
    )
    receiver = Point3(4.3, 2.1, 2.7)

    c = 343.0
    with_speed = first_order_path_lengths(images, receiver, sound_speed_m_s=c)
    for path in with_speed:
        assert path.toa_s is not None
        assert math.isclose(path.toa_s, path.path_length_m / c, rel_tol=0.0, abs_tol=1e-12)

    # sound_speed_m_s=None -> all toa_s is None.
    without_speed = first_order_path_lengths(images, receiver)
    assert all(path.toa_s is None for path in without_speed)

    # Non-positive / non-finite sound speed raises.
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            first_order_path_lengths(images, receiver, sound_speed_m_s=bad)


def test_path_length_non_finite_receiver_raises() -> None:
    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(6.0, 0.0),
        Point2(6.0, 4.0),
        Point2(0.0, 4.0),
    ]
    images = first_order_image_sources(
        floor_polygon, ceiling_height_m=3.0, source=Point3(2.0, 1.2, 1.5)
    )
    for bad_receiver in (
        Point3(float("nan"), 1.0, 1.0),
        Point3(1.0, float("inf"), 1.0),
        Point3(1.0, 1.0, float("nan")),
    ):
        with pytest.raises(ValueError):
            first_order_path_lengths(images, bad_receiver)


def test_path_length_deterministic_and_order_preserving() -> None:
    floor_polygon = [
        Point2(0.0, 0.0),
        Point2(6.0, 0.0),
        Point2(6.0, 4.0),
        Point2(0.0, 4.0),
    ]
    images = first_order_image_sources(
        floor_polygon, ceiling_height_m=3.0, source=Point3(2.0, 1.2, 1.5)
    )
    receiver = Point3(4.3, 2.1, 2.7)
    first = first_order_path_lengths(images, receiver, sound_speed_m_s=343.0)
    second = first_order_path_lengths(images, receiver, sound_speed_m_s=343.0)
    assert first == second
    # Order preserved: each ImagePath wraps the corresponding input image.
    assert [p.image for p in first] == list(images)
    assert all(isinstance(p, ImagePath) for p in first)
