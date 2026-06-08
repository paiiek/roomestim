"""Tests for ``roomestim.reconstruct.floor_polygon`` — Cycle B1/B3.

``floor_polygon_from_mesh`` recovers a *concave* footprint from a 3D vertex
cloud, preserving re-entrant corners that the convex-hull path erases. These
tests assert the L-shaped notch survives (area ≈ true L, not bounding hull)
and that degenerate clouds raise a clear ``ValueError`` (the B3 guards).
"""

from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.geom.polygon import is_simple_polygon
from roomestim.reconstruct.floor_polygon import floor_polygon_from_mesh


def _l_shaped_cloud() -> np.ndarray:
    """Dense L-shaped vertex cloud (x, y, z) at floor / mid / ceiling heights.

    Footprint: a 6 m × 6 m square minus a 3 m × 3 m notch (x > 3 and z > 3).
    True L area = 36 − 9 = 27 m²; the convex hull of the same cloud has the
    larger bounding-square area of 36 m². Vertices are seeded at three y
    levels (floor, mid-wall, ceiling) so the projection-to-floor step is
    exercised against non-floor geometry too.
    """
    pts: list[tuple[float, float, float]] = []
    step = 0.25
    for y in (0.0, 1.25, 2.5):
        x = 0.0
        while x <= 6.0 + 1e-9:
            z = 0.0
            while z <= 6.0 + 1e-9:
                if not (x > 3.0 + 1e-9 and z > 3.0 + 1e-9):
                    pts.append((x, y, z))
                z += step
            x += step
    return np.array(pts, dtype=float)


def test_floor_polygon_from_mesh_preserves_concave_notch() -> None:
    """An L-shaped cloud yields a simple CCW polygon that keeps the notch."""
    cloud = _l_shaped_cloud()
    polygon = floor_polygon_from_mesh(cloud)

    coords = [(p.x, p.z) for p in polygon]
    area = float(ShapelyPolygon(coords).area)

    # Concave area tracks the true L (27 m²), NOT the convex bounding square.
    assert area == pytest.approx(27.0, rel=0.10), (
        f"concave area {area} should track the true L area 27, not 36"
    )
    assert is_simple_polygon(coords), "reconstructed ring must be simple"
    # An L has 6 corners; a rectangle (convex collapse) would have 4.
    assert len(polygon) >= 6, (
        f"expected >=6 vertices for an L footprint, got {len(polygon)}"
    )


def test_floor_polygon_from_mesh_survives_scan_jitter() -> None:
    """ADR 0042 acceptance gate: the notch survives σ=2 cm scan jitter.

    Seeded Gaussian noise (σ=0.02 m) is added to every vertex of the clean
    L-cloud — a realistic stand-in for LiDAR/photogrammetry scan noise. The
    recovered footprint must still track the true L area (27 m²) within an
    HONEST loose tolerance (rel=0.15, looser than the clean rel=0.10 because
    jitter legitimately degrades the hull) AND keep the re-entrant corner
    (>=6 vertices) AND stay a simple ring. Empirically (rng seed 0):
    area ≈ 28.58 m² (5.9% over), 8 vertices.
    """
    cloud = _l_shaped_cloud()
    rng = np.random.default_rng(0)
    jittered = cloud + rng.normal(0.0, 0.02, size=cloud.shape)
    polygon = floor_polygon_from_mesh(jittered)

    coords = [(p.x, p.z) for p in polygon]
    area = float(ShapelyPolygon(coords).area)

    assert area == pytest.approx(27.0, rel=0.15), (
        f"jittered concave area {area} should still track the true L area 27"
    )
    assert is_simple_polygon(coords), "jittered ring must still be simple"
    assert len(polygon) >= 6, (
        f"notch must survive σ=2cm jitter (>=6 vertices), got {len(polygon)}"
    )


def test_floor_polygon_from_mesh_convex_hull_is_larger() -> None:
    """Contrast: the convex hull of the same cloud has the larger area.

    The convex hull of an L cloud cuts a single diagonal across the notch
    (a pentagon, area 31.5 m²), still strictly larger than the concave L's
    27 m² because it erases the re-entrant corner.
    """
    cloud = _l_shaped_cloud()
    from shapely.geometry import MultiPoint

    convex_area = float(
        MultiPoint([(float(v[0]), float(v[2])) for v in cloud]).convex_hull.area
    )
    concave_area = float(
        ShapelyPolygon([(p.x, p.z) for p in floor_polygon_from_mesh(cloud)]).area
    )
    assert convex_area > concave_area, (
        f"convex hull area {convex_area} should exceed concave {concave_area}"
    )
    assert convex_area == pytest.approx(31.5, rel=0.05)


def test_floor_polygon_from_mesh_collinear_raises() -> None:
    """B3: a perfectly collinear cloud has no areal hull → ValueError."""
    cloud = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]], dtype=float
    )
    with pytest.raises(ValueError):
        floor_polygon_from_mesh(cloud)


def test_floor_polygon_from_mesh_too_few_points_raises() -> None:
    """B3: fewer than 3 distinct projected points → ValueError."""
    cloud = np.array(
        [[1.0, 0.0, 2.0], [1.0, 9.0, 2.0]], dtype=float  # same (x, z)
    )
    with pytest.raises(ValueError, match="distinct projected"):
        floor_polygon_from_mesh(cloud)


def test_floor_polygon_from_mesh_rejects_bad_ratio() -> None:
    """B3: ratio outside (0, 1] raises ValueError."""
    cloud = _l_shaped_cloud()
    with pytest.raises(ValueError, match="ratio"):
        floor_polygon_from_mesh(cloud, ratio=0.0)
    with pytest.raises(ValueError, match="ratio"):
        floor_polygon_from_mesh(cloud, ratio=1.5)


def test_floor_polygon_from_mesh_rejects_bad_shape() -> None:
    """A non-(N, 3) array raises ValueError."""
    with pytest.raises(ValueError, match=r"\(N, 3\)"):
        floor_polygon_from_mesh(np.zeros((4, 2), dtype=float))
