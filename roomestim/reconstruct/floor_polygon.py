"""Mesh -> 2D floor polygon reconstruction (concave-hull footprint).

:func:`floor_polygon_from_mesh` projects a 3D mesh vertex cloud onto the
floor plane and recovers a *concave* footprint via :func:`shapely.concave_hull`.
Unlike a convex hull, the concave hull preserves re-entrant corners, so an
L-shaped or otherwise non-shoebox room keeps its notch instead of collapsing
to its bounding hull.

:func:`floor_polygon_from_mesh_occupancy` adds a density + connected-component
denoising front-end to that concave path: it rasterizes the floor-projected
cloud onto a fixed-resolution occupancy grid, keeps only the single largest
connected dense component (rejecting sparse, disconnected floater points that
both convex and concave hulls would otherwise envelop), and hands the surviving
cell centres back to :func:`floor_polygon_from_mesh` to reuse all of its guards.

The default :data:`MeshAdapter` floor path remains convex-hull based; these
reconstructions are the opt-in modes selected via
``floor_reconstruction="concave"`` / ``"occupancy"`` (or the
``ROOMESTIM_MESH_FLOOR_RECON`` environment override). See
``roomestim/adapters/mesh.py``.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import label, sum as ndimage_sum  # type: ignore[import-untyped]
from scipy.spatial import cKDTree  # type: ignore[import-untyped]
from shapely import concave_hull
from shapely.geometry import MultiPoint, MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.geom.polygon import is_simple_polygon
from roomestim.model import Point2, canonicalize_ccw

__all__ = [
    "AUTO_FLOOR_RECON_NOTE",
    "auto_should_use_occupancy",
    "disconnected_floater_phi",
    "floor_polygon_from_mesh",
    "floor_polygon_from_mesh_occupancy",
    "floor_polygon_robust",
]

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

# Occupancy-grid denoiser parameters (the ``"occupancy"`` floor mode).
#
# ``_OCC_CELL_M`` is the square grid resolution (metres) the floor-projected
# cloud is rasterized onto. 0.05 m was validated on Redwood RGB-D and is 5x
# denser than ``floor_polygon_from_mesh``'s documented ~0.25 m "dense cloud"
# requirement, so the surviving cell-centre cloud resolves the concave boundary
# cleanly.
_OCC_CELL_M = 0.05

# ``_OCC_MIN_COUNT`` is the minimum number of vertices a cell must hold to count
# as occupied. There is NO single correct value (clean laser scans tolerate 5,
# noisy reconstructions need 3); 3 is chosen as the SAFE failure direction —
# under-rejection keeps the room, whereas an over-aggressive threshold can
# fragment a sparsely-sampled real scan and let the connected-component step
# pick a sub-room, silently UNDER-reading the footprint. The connected-component
# step is the dominant floater rejector (floaters are disconnected sparse
# clusters that lose to the room's giant component regardless), so a low count
# threshold only needs to strip the sparsest noise. Operators with a clean,
# dense scan may pass ``min_count=5`` as a function kwarg.
_OCC_MIN_COUNT = 3

# Robust boundary-trim parameters (the ``"robust"`` floor mode).
#
# Density-percentile boundary trim BEFORE the concave hull. SCRREAM n=1 vertex-
# noise validation (``scrream-gt/scrream_seg_frontend_proto.py``) showed Gaussian
# vertex noise inflates the concave footprint monotonically (+19.4% @ 5 cm, +39%
# @ 10 cm); dropping the top ``_ROBUST_DROP_PCT`` % of points by sparse k-NN mean
# distance (the boundary "flyers") roughly HALVES that over-read (+8.3% @ 5 cm,
# +12% @ 10 cm) and is UNCHANGED on clean (σ=0) input. ``_ROBUST_BAND_M`` is the
# bottom-band thickness (metres above the 1st-percentile floor) the trim runs on;
# ``_ROBUST_KNN_K`` is the k-NN neighbour count whose mean distance ranks point
# sparseness. These are the proto's validated values; the figures are n=1 SCRREAM
# noise-sweep specific and are NOT an accuracy guarantee on real room scans.
_ROBUST_BAND_M = 0.15
_ROBUST_KNN_K = 12
_ROBUST_DROP_PCT = 8.0

# ``auto`` floater-detection signal parameters (the ``"auto"`` floor mode).
#
# The signal is a convex-hull AREA-INFLATION ratio computed on a COARSE
# connectivity grid that is DECOUPLED from the 0.05 m / min_count=3 extraction
# grid above. The coarse grid exists ONLY to answer one question cheaply: is the
# floor cloud a single connected mass, or is there a spatially-DISCONNECTED
# cluster the convex hull would engulf? Running the area ratio on the fine
# extraction grid false-fires — a clean L-room fragments into edge components
# and a density-marginal clean room speckles — so the detection grid uses a
# coarse cell and ``min_count_det = 1`` (any point occupies). At this resolution
# every clean case (rectangular / L-shaped / sparse) collapses to ONE component
# → φ = 1.0 exactly, which is the byte-equal guarantee: a single connected mass
# has no separated floater, so ``auto`` stays on the convex path.
_AUTO_DET_CELL_M = 0.25
_AUTO_DET_MIN_COUNT = 1

# Fire threshold for the area-inflation ratio φ. φ measures the exact harm the
# fix targets — convex-hull area ENGULFMENT by a disconnected cluster. Edge
# fragmentation / non-rect geometry add negligible area (handled by the single-
# component early return → φ = 1.0); a distant disconnected floater inflates the
# hull (φ grows with separation: 0.5 m → 1.11, 1.0 m → 1.23, 2.0 m → 1.45). The
# 1.10 bar has two-sided margin: clean input is exactly 1.0, the synthetic
# fixture is 1.3375. The SAFE failure direction is false-NEGATIVE (a small/near
# floater inflating < 10 % stays convex == today's behaviour); the dangerous
# false-positive on clean input is locked off by the single-component early
# return, not by this threshold.
_AUTO_FLOATER_PHI_THRESHOLD = 1.10

# Single source of truth for the honest ``auto`` mode disclosure. Imported by
# ``roomestim.adapters.mesh`` and ``roomestim.cli`` so the wording never drifts.
# DO NOT add a bleed / re-entrant / notch-recovery claim here: connected
# geometry is a single coarse component → φ = 1.0 → the signal never fires, so
# ``auto`` cannot be those things by construction.
AUTO_FLOOR_RECON_NOTE = (
    "auto footprint = DISCONNECTED-floater rejection only (switches to the "
    "occupancy extractor when a coarse-grid convex-hull area-inflation signal "
    "detects a spatially-separated cluster; else stays convex, byte-equal). It "
    "is NOT a through-opening-bleed fix and NOT a re-entrant/notch-recovery "
    "capability (connected geometry never triggers it). Threshold validated on "
    "a deterministic synthetic floater fixture only; design justification cites "
    "the established Redwood noisy-recon result (+22% convex over-read → +5% "
    "occupancy, n=1). Opt-in, NOT the default; a genuinely-detached REAL "
    "structure separated by a scan gap would also be dropped."
)


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


def floor_polygon_from_mesh_occupancy(
    mesh_vertices: np.ndarray,
    *,
    cell: float = _OCC_CELL_M,
    min_count: int = _OCC_MIN_COUNT,
    ratio: float = _DEFAULT_RATIO,
) -> list[Point2]:
    """Reconstruct a 2D floor polygon via occupancy-grid denoising + concave hull.

    A density + connected-component front-end to :func:`floor_polygon_from_mesh`.
    The floor-projected (``x = v[0]``, ``z = v[2]``) cloud is rasterized onto a
    ``cell``-metre occupancy grid; cells holding at least ``min_count`` vertices
    are "occupied"; the single largest 8-connected component is kept and its cell
    *centres* are handed back to :func:`floor_polygon_from_mesh`. This rejects the
    sparse, disconnected floater points that a convex (and even a concave) hull
    would otherwise envelop — the room is recovered by **density + connectivity**,
    not by hugging every outlier — while reusing 100% of the concave path's
    ratio guard, MultiPolygon/holes handling, ``simplify``, ``is_simple_polygon``,
    and ``canonicalize_ccw``.

    The vertices are assumed ALREADY Y-up-normalized (the
    :mod:`roomestim.adapters.mesh` convention runs ``_normalize_to_y_up`` before
    floor reconstruction), so the up axis is NOT re-detected here.

    Parameters
    ----------
    mesh_vertices:
        ``(N, 3)`` array of mesh vertex positions in listener-frame metres.
    cell:
        Occupancy-grid square cell size in metres. Defaults to
        :data:`_OCC_CELL_M` (``0.05``). Must be ``> 0`` (NaN fails the guard).
    min_count:
        Minimum vertices per cell to count as occupied. Defaults to
        :data:`_OCC_MIN_COUNT` (``3``). Must be ``>= 1`` (NaN fails the guard).
    ratio:
        Concave-hull tightness in ``(0, 1]`` forwarded to
        :func:`floor_polygon_from_mesh`. Defaults to :data:`_DEFAULT_RATIO`.

    Returns
    -------
    list[Point2]
        CCW floor polygon (``(x, z)`` vertices, closing duplicate stripped).

    Raises
    ------
    ValueError
        If ``mesh_vertices`` is not ``(N, 3)``; if ``cell <= 0`` or
        ``min_count < 1`` (including NaN); if no cell reaches ``min_count``
        (cloud too sparse / floater-only); if the largest component has fewer
        than 3 cells; or any degeneracy raised by the delegated
        :func:`floor_polygon_from_mesh`. The :data:`MeshAdapter` caller converts
        the degeneracy case into a convex-hull fallback with a warning.
    """
    vertices = np.asarray(mesh_vertices, dtype=float)
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError(
            f"occupancy: expected (N, 3) vertex array, got shape "
            f"{vertices.shape}"
        )
    if not (np.isfinite(cell) and cell > 0.0):
        raise ValueError(f"occupancy: cell must be > 0, got {cell}")
    if not (np.isfinite(min_count) and min_count >= 1):
        raise ValueError(f"occupancy: min_count must be >= 1, got {min_count}")

    # Project to the (x, z) floor plane (Y-up convention; up axis already
    # normalized upstream — do NOT re-detect it here).
    xz = vertices[:, [0, 2]]
    if not np.isfinite(xz).all():
        raise ValueError("occupancy: non-finite vertex coordinates")
    origin = xz.min(axis=0)
    ij = np.floor((xz - origin) / cell).astype(np.int64)
    h, w = int(ij[:, 0].max()) + 1, int(ij[:, 1].max()) + 1
    grid = np.zeros((h, w), dtype=np.int32)
    np.add.at(grid, (ij[:, 0], ij[:, 1]), 1)
    mask = grid >= min_count

    lab, n = label(mask, structure=np.ones((3, 3)))
    if n == 0 or not mask.any():
        raise ValueError(
            f"occupancy: no cell met min_count={min_count}; the cloud is too "
            "sparse or floater-only."
        )

    # Largest 8-connected component (the room); floaters are smaller, disconnected.
    sizes = ndimage_sum(mask, lab, index=range(1, n + 1))
    big = 1 + int(np.argmax(sizes))
    rows, cols = np.where(lab == big)
    if rows.size < 3:
        raise ValueError(
            f"occupancy: largest component has only {rows.size} cell(s); at "
            "least 3 are required for a footprint."
        )

    # Back-project occupied cell CENTRES to metric (x, z). Row index → x axis,
    # col index → z axis (consistent with how ``ij`` was built).
    x = rows * cell + float(origin[0]) + 0.5 * cell
    z = cols * cell + float(origin[1]) + 0.5 * cell
    synth = np.column_stack([x, np.zeros_like(x), z])
    return floor_polygon_from_mesh(synth, ratio=ratio)


def floor_polygon_robust(
    mesh_vertices: np.ndarray,
    *,
    band_m: float = _ROBUST_BAND_M,
    k: int = _ROBUST_KNN_K,
    drop_pct: float = _ROBUST_DROP_PCT,
    ratio: float = _DEFAULT_RATIO,
) -> list[Point2]:
    """Reconstruct a 2D floor polygon via density-percentile boundary trim.

    A noise-robust front-end to :func:`floor_polygon_from_mesh`. Faithfully ports
    the validated SCRREAM prototype pipeline
    (``scrream-gt/scrream_seg_frontend_proto.py``): take the bottom ``band_m``
    floor band, drop the top ``drop_pct`` % of band points by sparse k-NN mean
    distance (the boundary "flyers" that vertex noise sprays outside the true
    footprint), and hand the survivors back to the concave path. Gaussian vertex
    noise inflates the raw concave footprint monotonically (validated n=1 SCRREAM:
    +19.4% @ 5 cm, +39% @ 10 cm); the trim roughly HALVES that over-read
    (+8.3% @ 5 cm, +12% @ 10 cm) and leaves clean (σ=0) input unchanged. These
    figures are noise-sweep-specific (n=1) and are NOT an accuracy guarantee on
    real room scans.

    The vertices are assumed ALREADY Y-up-normalized (the
    :mod:`roomestim.adapters.mesh` convention runs ``_normalize_to_y_up`` before
    floor reconstruction), so the vertical is index 1 and the floor plane is
    ``(x, z) = (index 0, index 2)``; the up axis is NOT re-detected here.

    Parameters
    ----------
    mesh_vertices:
        ``(N, 3)`` array of mesh vertex positions in listener-frame metres.
    band_m:
        Thickness (metres) of the bottom floor band trimmed, measured above the
        1st-percentile floor height. Defaults to :data:`_ROBUST_BAND_M` (0.15).
        Must be ``> 0``.
    k:
        k-NN neighbour count whose mean distance ranks point sparseness. Defaults
        to :data:`_ROBUST_KNN_K` (12). Must be ``>= 1``.
    drop_pct:
        Percentage of the sparsest band points (highest k-NN mean distance) to
        drop. Defaults to :data:`_ROBUST_DROP_PCT` (8.0). Must be in ``(0, 100)``.
    ratio:
        Concave-hull tightness in ``(0, 1]`` forwarded to
        :func:`floor_polygon_from_mesh`. Defaults to :data:`_DEFAULT_RATIO`.

    Returns
    -------
    list[Point2]
        CCW floor polygon (``(x, z)`` vertices, closing duplicate stripped).

    Raises
    ------
    ValueError
        If ``mesh_vertices`` is not ``(N, 3)`` or non-finite; if ``band_m <= 0``,
        ``k < 1``, or ``drop_pct`` is outside ``(0, 100)`` (including NaN); or any
        degeneracy raised by the delegated :func:`floor_polygon_from_mesh`. The
        :data:`MeshAdapter` caller converts the degeneracy case into a convex-hull
        fallback with a warning.

    Notes
    -----
    **Deterministic.** No RNG anywhere: :class:`scipy.spatial.cKDTree.query` and
    :func:`numpy.percentile` are deterministic, and the ``<=`` keep threshold
    includes ties deterministically, so the same input always yields the same
    polygon.
    """
    vertices = np.asarray(mesh_vertices, dtype=float)
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError(
            f"robust: expected (N, 3) vertex array, got shape {vertices.shape}"
        )
    if not np.isfinite(vertices).all():
        raise ValueError("robust: non-finite vertex coordinates")
    if not (np.isfinite(band_m) and band_m > 0.0):
        raise ValueError(f"robust: band_m must be > 0, got {band_m}")
    if not (np.isfinite(k) and k >= 1):
        raise ValueError(f"robust: k must be >= 1, got {k}")
    if not (np.isfinite(drop_pct) and 0.0 < drop_pct < 100.0):
        raise ValueError(f"robust: drop_pct must be in (0, 100), got {drop_pct}")

    # Floor band: the bottom ``band_m`` above the 1st-percentile floor height
    # (Y-up convention; up axis already normalized upstream). Project to (x, z).
    fy = float(np.percentile(vertices[:, 1], 1.0))
    band = vertices[vertices[:, 1] <= fy + band_m]
    xz = band[:, [0, 2]]

    # Density trim (verbatim port of the validated proto ``density_trim``): drop
    # points whose k-NN mean distance is in the top ``drop_pct`` (sparse flyers).
    if len(xz) <= k + 1:
        kept = xz
    else:
        tree = cKDTree(xz)
        d, _ = tree.query(xz, k=k + 1)
        md = d[:, 1:].mean(1)
        kept = xz[md <= np.percentile(md, 100 - drop_pct)]

    # Reuse the concave path (inherits every guard, simplify, is_simple_polygon,
    # canonicalize_ccw) by re-synthesizing a Y-up (N, 3) cloud at floor level.
    synth = np.column_stack([kept[:, 0], np.zeros(len(kept)), kept[:, 1]])
    return floor_polygon_from_mesh(synth, ratio=ratio)


def disconnected_floater_phi(mesh_vertices: np.ndarray) -> float:
    """Convex-hull area-inflation ratio φ for the ``"auto"`` floater detector.

    Rasterizes the floor-projected (``x = v[0]``, ``z = v[2]``) cloud onto a
    COARSE :data:`_AUTO_DET_CELL_M` (0.25 m) connectivity grid where any cell
    holding ``>= _AUTO_DET_MIN_COUNT`` (1) vertex is occupied, 8-connected-
    component labels it, and returns

        convex_hull_area(ALL occupied cell centres)
        / convex_hull_area(LARGEST-component cell centres).

    φ is the harm-weighted measure of convex-hull ENGULFMENT: a spatially-
    DISCONNECTED cluster (a floater across a ``>= 0.25 m`` gap) extends the all-
    cells hull beyond the room's largest component, so φ grows with the
    floater's separation; edge fragmentation and non-rectangular geometry add
    negligible area.

    This is decoupled from the 0.05 m extraction grid ON PURPOSE — running the
    ratio on the fine grid false-fires (a clean L-room fragments into edge
    components, a density-marginal clean room speckles). On the coarse grid every
    CLEAN case (rectangular, L-shaped, sparse, or a connected through-opening
    "bleed") is a SINGLE component, so this returns ``1.0`` exactly. It is
    therefore NOT a through-opening-bleed fix and NOT a re-entrant/notch-recovery
    capability — connected geometry cannot inflate φ.

    Never raises: any degeneracy (empty / non-finite / fewer than 3 cells in the
    largest component / a hull that is not a polygon) returns ``1.0`` ("do not
    fire" → stay convex → byte-equal → safe). Returns ``1.0`` exactly when the
    coarse grid has ``<= 1`` component (the byte-equal early return).
    """
    try:
        vertices = np.asarray(mesh_vertices, dtype=float)
        if vertices.ndim != 2 or vertices.shape[1] != 3:
            return 1.0
        xz = vertices[:, [0, 2]]
        if xz.shape[0] < 3 or not np.isfinite(xz).all():
            return 1.0
        origin = xz.min(axis=0)
        span = xz.max(axis=0) - origin
        if not np.all(np.isfinite(span)) or np.any(span < 0.0):
            return 1.0
        ij = np.floor((xz - origin) / _AUTO_DET_CELL_M).astype(np.int64)
        h = int(ij[:, 0].max()) + 1
        w = int(ij[:, 1].max()) + 1
        grid = np.zeros((h, w), dtype=np.int64)
        np.add.at(grid, (ij[:, 0], ij[:, 1]), 1)
        mask = grid >= _AUTO_DET_MIN_COUNT
        if not mask.any():
            return 1.0

        lab, n = label(mask, structure=np.ones((3, 3)))
        # A single connected mass has no separated floater → byte-equal guarantee.
        if n <= 1:
            return 1.0

        sizes = ndimage_sum(mask, lab, index=range(1, n + 1))
        big = 1 + int(np.argmax(sizes))

        def _centres(component_mask: np.ndarray) -> list[tuple[float, float]]:
            rows, cols = np.where(component_mask)
            xc = rows * _AUTO_DET_CELL_M + float(origin[0]) + 0.5 * _AUTO_DET_CELL_M
            zc = cols * _AUTO_DET_CELL_M + float(origin[1]) + 0.5 * _AUTO_DET_CELL_M
            return list(zip(xc.tolist(), zc.tolist(), strict=True))

        big_centres = _centres(lab == big)
        if len(big_centres) < 3:
            return 1.0
        all_hull = MultiPoint(_centres(mask)).convex_hull
        big_hull = MultiPoint(big_centres).convex_hull
        if not isinstance(all_hull, ShapelyPolygon) or not isinstance(
            big_hull, ShapelyPolygon
        ):
            return 1.0
        big_area = float(big_hull.area)
        if not np.isfinite(big_area) or big_area <= 0.0:
            return 1.0
        phi = float(all_hull.area) / big_area
        if not np.isfinite(phi) or phi < 1.0:
            return 1.0
        return phi
    except Exception:  # noqa: BLE001 — the detector must NEVER raise; degenerate → stay convex.
        return 1.0


def auto_should_use_occupancy(
    mesh_vertices: np.ndarray,
    *,
    threshold: float = _AUTO_FLOATER_PHI_THRESHOLD,
) -> bool:
    """``True`` iff the ``"auto"`` floater signal fires (switch to occupancy).

    Thin wrapper over :func:`disconnected_floater_phi`: fires when the convex-
    hull area-inflation ratio φ reaches ``threshold`` (default
    :data:`_AUTO_FLOATER_PHI_THRESHOLD`, 1.10). Clean input yields φ = 1.0
    exactly, so this returns ``False`` and the caller stays on the byte-equal
    convex path. Inherits the never-raise guarantee of the underlying signal.
    """
    return disconnected_floater_phi(mesh_vertices) >= threshold
