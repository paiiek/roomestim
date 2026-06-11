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
from roomestim.reconstruct.floor_polygon import (
    _AUTO_FLOATER_PHI_THRESHOLD,
    auto_should_use_occupancy,
    disconnected_floater_phi,
    floor_polygon_from_mesh,
    floor_polygon_from_mesh_occupancy,
)


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


# --------------------------------------------------------------------------- #
# Phase B — occupancy-grid denoising footprint (floor_polygon_from_mesh_occupancy)
# --------------------------------------------------------------------------- #


def _dense_rect_cloud(
    rng: np.random.Generator,
    *,
    x0: float,
    x1: float,
    z0: float,
    z1: float,
    n: int = 40_000,
    y_hi: float = 2.5,
) -> np.ndarray:
    """Dense random (x, y, z) cloud uniformly filling a rectangle footprint.

    Sub-cell point spread (uniform sampling) is required: a cloud whose points
    sit exactly on the 5 cm cell boundaries would put ~1 point per cell and
    never reach ``min_count``. Real RGB-D scans pack many points per cell, which
    this models.
    """
    x = rng.uniform(x0, x1, n)
    z = rng.uniform(z0, z1, n)
    y = rng.uniform(0.0, y_hi, n)
    return np.column_stack([x, y, z])


def _dense_l_cloud(rng: np.random.Generator, n: int = 60_000) -> np.ndarray:
    """Dense random L-shaped cloud: 6x6 square minus a 3x3 notch (x>3 and z>3).

    True L area = 36 - 9 = 27 m². Uniform rejection sampling gives sub-cell
    point spread so each occupied 5 cm cell clears ``min_count``.
    """
    x = rng.uniform(0.0, 6.0, n)
    z = rng.uniform(0.0, 6.0, n)
    y = rng.uniform(0.0, 2.5, n)
    keep = ~((x > 3.0) & (z > 3.0))
    return np.column_stack([x[keep], y[keep], z[keep]])


def test_occupancy_rejects_sparse_floaters() -> None:
    """THE keystone: occupancy recovers the room by REJECTING sparse floaters.

    A dense 4 m × 4 m room cloud plus a handful of sparse, disconnected floater
    points placed several metres outside. The convex hull of the SAME cloud is
    badly inflated by the floaters, while occupancy (density + connectivity)
    recovers the true room area — strictly SMALLER than the floater-polluted
    convex hull. This is not a tautology against convex: it proves occupancy
    strips the floaters that convex cannot.
    """
    from shapely.geometry import MultiPoint

    rng = np.random.default_rng(0)
    room = _dense_rect_cloud(rng, x0=0.0, x1=4.0, z0=0.0, z1=4.0)
    # Sparse floaters: 1-2 points each, metres outside, mutually disconnected.
    floaters = np.array(
        [
            [9.0, 0.0, 9.0],
            [9.03, 0.0, 9.0],
            [-6.0, 0.0, -6.0],
            [-6.0, 0.0, 8.0],
        ],
        dtype=float,
    )
    cloud = np.vstack([room, floaters])

    occ_poly = floor_polygon_from_mesh_occupancy(cloud)
    occ_coords = [(p.x, p.z) for p in occ_poly]
    occ_area = float(ShapelyPolygon(occ_coords).area)
    convex_area = float(
        MultiPoint([(float(v[0]), float(v[2])) for v in cloud]).convex_hull.area
    )

    assert is_simple_polygon(occ_coords), "occupancy ring must be simple"
    # Occupancy tracks the true 16 m² room (slight concave erosion is honest).
    assert occ_area == pytest.approx(16.0, rel=0.10), (
        f"occupancy area {occ_area} should track the true room area 16"
    )
    # The floaters inflate the convex hull far past the room.
    assert convex_area > 50.0, (
        f"sanity: floaters should inflate convex hull, got {convex_area}"
    )
    assert occ_area < convex_area, (
        f"occupancy {occ_area} must reject floaters that bloat convex "
        f"{convex_area}"
    )


def test_occupancy_preserves_axis_extents_no_wl_swap() -> None:
    """Lock the grid row/col -> metric axis mapping against a silent W/L swap.

    A transpose-symmetric fixture (square / notched-L) cannot catch a swapped
    back-projection. An asymmetric 8 m (x) x 2 m (z) rectangle does: a swap
    would emit x-extent ~= 2 and z-extent ~= 8 instead of ~= 8 and ~= 2.
    """
    rng = np.random.default_rng(0)
    cloud = _dense_rect_cloud(rng, x0=0.0, x1=8.0, z0=0.0, z1=2.0)
    poly = floor_polygon_from_mesh_occupancy(cloud)
    xs = [p.x for p in poly]
    zs = [p.z for p in poly]
    assert max(xs) - min(xs) == pytest.approx(8.0, abs=0.2), "x-extent must stay ~8 m"
    assert max(zs) - min(zs) == pytest.approx(2.0, abs=0.2), "z-extent must stay ~2 m"


def test_occupancy_preserves_concave_notch() -> None:
    """A dense L-cloud keeps its re-entrant corner (option (a) min-rect fails this)."""
    rng = np.random.default_rng(1)
    cloud = _dense_l_cloud(rng)
    polygon = floor_polygon_from_mesh_occupancy(cloud)

    coords = [(p.x, p.z) for p in polygon]
    area = float(ShapelyPolygon(coords).area)

    assert area == pytest.approx(27.0, rel=0.10), (
        f"occupancy area {area} should track the true L area 27"
    )
    assert is_simple_polygon(coords), "occupancy L ring must be simple"
    assert len(polygon) >= 6, (
        f"expected >=6 vertices for an L footprint, got {len(polygon)}"
    )


def test_occupancy_floater_only_or_empty_raises() -> None:
    """Degeneracy: an all-sparse cloud (no cell reaches min_count) raises."""
    # Each point at a distinct location, well-separated → every cell count == 1.
    sparse = np.array(
        [[float(i) * 2.0, 0.0, float(j) * 2.0] for i in range(3) for j in range(3)],
        dtype=float,
    )
    with pytest.raises(ValueError, match="occupancy: no cell met min_count"):
        floor_polygon_from_mesh_occupancy(sparse)

    # A dense but tiny component spanning < 3 cells → ValueError (too few cells).
    rng = np.random.default_rng(2)
    tiny = _dense_rect_cloud(rng, x0=0.0, x1=0.04, z0=0.0, z1=0.04, n=2000)
    with pytest.raises(ValueError):
        floor_polygon_from_mesh_occupancy(tiny)


def test_occupancy_rejects_bad_params() -> None:
    """cell<=0, min_count<1, and NaN params all raise ValueError."""
    rng = np.random.default_rng(3)
    cloud = _dense_rect_cloud(rng, x0=0.0, x1=4.0, z0=0.0, z1=4.0, n=4000)
    with pytest.raises(ValueError, match="cell"):
        floor_polygon_from_mesh_occupancy(cloud, cell=0.0)
    with pytest.raises(ValueError, match="cell"):
        floor_polygon_from_mesh_occupancy(cloud, cell=float("nan"))
    with pytest.raises(ValueError, match="min_count"):
        floor_polygon_from_mesh_occupancy(cloud, min_count=0)
    with pytest.raises(ValueError, match="min_count"):
        floor_polygon_from_mesh_occupancy(cloud, min_count=float("nan"))  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# C1 — `auto` disconnected-floater signal (ADR 0048)
#
# Deterministic, RNG-free fixtures (pure np.meshgrid on pinned bounds/spacing).
# The COMPUTED expected numbers below were reproduced live with miniforge python
# against these exact arrays before pinning (planner derivation, NO FAKE NUMBERS):
#   phi_clean = 1.0 (exact, single coarse component)
#   phi_floater(cloud) = 1.3375
#   convex-hull area clean = 20.0 m^2 ; floater cloud = 27.99 m^2 (+39.9%)
#   occupancy(auto-fired) recovered = 19.0075 m^2 (-5.0%)  [planner table: 19.005]
#   boundary floater @0.5 m: phi = 1.1125 (fires)
# --------------------------------------------------------------------------- #


def _clean_room_cloud() -> np.ndarray:
    """Dense clean rectangle x in [0,4], z in [0,5] at 0.025 m spacing, y=0.

    161 x 201 = 32 361 points. 0.025 m = 2 pts per 0.05 m cell per axis, so every
    interior 0.05 cell holds 4 >= min_count (occupancy recovers it); at the
    0.25 m detection grid it is one solid component (phi = 1.0 exactly).
    True floor area = 20.0 m^2.
    """
    xr = np.arange(0.0, 4.0 + 1e-9, 0.025)
    zr = np.arange(0.0, 5.0 + 1e-9, 0.025)
    gx, gz = np.meshgrid(xr, zr, indexing="ij")
    return np.column_stack([gx.ravel(), np.zeros(gx.size), gz.ravel()])


def _floater_blob(x0: float, z0: float) -> np.ndarray:
    """0.2 m x 0.2 m dense blob at 0.02 m spacing (11 x 11 = 121 points), y=0.

    Dense enough (>= min_count=3 at the 0.05 m occupancy grid) to survive as its
    own small connected component, disconnected (> 0.25 m gap) from the room.
    """
    fx = np.arange(x0, x0 + 0.2 + 1e-9, 0.02)
    fz = np.arange(z0, z0 + 0.2 + 1e-9, 0.02)
    fgx, fgz = np.meshgrid(fx, fz, indexing="ij")
    return np.column_stack([fgx.ravel(), np.zeros(fgx.size), fgz.ravel()])


def _l_room_cloud_dense() -> np.ndarray:
    """Deterministic dense L-room (6x6 minus 3x3 notch) at 0.05 m spacing, y=0.

    A connected non-rectangular footprint — the coarse-grid signal must read it
    as a SINGLE component (phi = 1.0), locking the no-false-fire-on-non-rect /
    bleed-proxy guarantee.
    """
    pts: list[tuple[float, float, float]] = []
    xr = np.arange(0.0, 6.0 + 1e-9, 0.05)
    zr = np.arange(0.0, 6.0 + 1e-9, 0.05)
    for x in xr:
        for z in zr:
            if not (x > 3.0 + 1e-9 and z > 3.0 + 1e-9):
                pts.append((float(x), 0.0, float(z)))
    return np.array(pts, dtype=float)


def _sparse_room_cloud() -> np.ndarray:
    """Sparse clean rectangle x in [0,4], z in [0,5] at 0.10 m spacing, y=0.

    Coarser than a cell-per-point density yet still a single coarse component →
    phi = 1.0 (the coarse detection grid is robust to sparse-but-connected
    clouds).
    """
    xr = np.arange(0.0, 4.0 + 1e-9, 0.10)
    zr = np.arange(0.0, 5.0 + 1e-9, 0.10)
    gx, gz = np.meshgrid(xr, zr, indexing="ij")
    return np.column_stack([gx.ravel(), np.zeros(gx.size), gz.ravel()])


@pytest.mark.parametrize(
    "make_cloud",
    [_clean_room_cloud, _l_room_cloud_dense, _sparse_room_cloud],
    ids=["rect", "l_room", "sparse"],
)
def test_auto_signal_clean_never_fires(make_cloud) -> None:  # type: ignore[no-untyped-def]
    """T-sig-clean: clean clouds are a single coarse component → phi = 1.0, no fire.

    Locks the coarse-grid single-component guarantee across rectangular,
    non-rectangular (L), and sparse footprints (incl. bleed-proxy by
    construction: connected geometry cannot inflate phi).
    """
    cloud = make_cloud()
    assert disconnected_floater_phi(cloud) == 1.0
    assert auto_should_use_occupancy(cloud) is False


def test_auto_signal_floater_fires() -> None:
    """T-sig-floater: a disconnected floater inflates phi past the threshold."""
    cloud = np.vstack([_clean_room_cloud(), _floater_blob(5.5, 6.5)])
    phi = disconnected_floater_phi(cloud)
    assert phi == pytest.approx(1.3375, abs=1e-4), f"reproduced phi_floater {phi}"
    assert phi >= _AUTO_FLOATER_PHI_THRESHOLD
    assert auto_should_use_occupancy(cloud) is True


def test_auto_signal_boundary_pins_threshold() -> None:
    """T-boundary: a floater 0.5 m beyond the corner just fires; clean never does.

    Pins theta=1.10 from both sides: the @0.5 m floater gives phi = 1.1125
    (>= theta, fires); the clean room gives phi = 1.0 (< theta, never fires).
    """
    near = np.vstack([_clean_room_cloud(), _floater_blob(4.5, 5.5)])
    phi_near = disconnected_floater_phi(near)
    assert phi_near == pytest.approx(1.1125, abs=1e-4), f"reproduced @0.5 m {phi_near}"
    assert phi_near >= _AUTO_FLOATER_PHI_THRESHOLD

    phi_clean = disconnected_floater_phi(_clean_room_cloud())
    assert phi_clean == 1.0
    assert phi_clean < _AUTO_FLOATER_PHI_THRESHOLD


def test_auto_signal_degenerate_never_raises() -> None:
    """T-sig-degenerate: empty / <3-point / non-finite input → 1.0 / False, no raise."""
    empty = np.empty((0, 3), dtype=float)
    assert disconnected_floater_phi(empty) == 1.0
    assert auto_should_use_occupancy(empty) is False

    two_pts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 1.0]], dtype=float)
    assert disconnected_floater_phi(two_pts) == 1.0

    nonfinite = np.array(
        [[0.0, 0.0, 0.0], [np.nan, 0.0, 1.0], [1.0, 0.0, np.inf]], dtype=float
    )
    assert disconnected_floater_phi(nonfinite) == 1.0

    wrong_shape = np.zeros((5, 2), dtype=float)
    assert disconnected_floater_phi(wrong_shape) == 1.0


def test_auto_recover_area_rejects_floater() -> None:
    """T-recover: occupancy (auto-fired) recovers ~truth, strictly < convex over-read.

    On the floater cloud the convex hull over-reads to ~27.99 m^2 (+39.9% vs the
    true 20 m^2 room), while the occupancy extractor the signal selects recovers
    ~19.0 m^2 (-5.0%) by keeping only the room's largest component.
    """
    from shapely.geometry import MultiPoint

    cloud = np.vstack([_clean_room_cloud(), _floater_blob(5.5, 6.5)])

    occ_poly = floor_polygon_from_mesh_occupancy(cloud)
    occ_area = float(ShapelyPolygon([(p.x, p.z) for p in occ_poly]).area)
    convex_area = float(
        MultiPoint([(float(v[0]), float(v[2])) for v in cloud]).convex_hull.area
    )

    assert convex_area == pytest.approx(27.99, rel=0.02), f"convex over-read {convex_area}"
    assert occ_area == pytest.approx(19.0, rel=0.05), f"occupancy recovered {occ_area}"
    assert occ_area < convex_area
    assert abs(occ_area - 20.0) / 20.0 <= 0.06


def test_occupancy_rejects_bad_shape() -> None:
    """A non-(N, 3) array raises ValueError."""
    with pytest.raises(ValueError, match=r"\(N, 3\)"):
        floor_polygon_from_mesh_occupancy(np.zeros((4, 2), dtype=float))
