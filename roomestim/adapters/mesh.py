"""MeshAdapter — generic mesh-file input for room estimation.

Accepts ``.obj``, ``.gltf``, ``.glb``, ``.ply`` and ``.usdz`` mesh files.
``.usdz`` requires the optional ``usd`` extra (``pip install
'roomestim[usd]'``): all :class:`UsdGeom.Mesh` prims are read, baked to
world space, and fed into the SAME up-axis-normalized floor/ceiling/wall
extraction the other formats use (geometry meshes — Polycam/ARKit/generic;
RoomPlan's parametric CapturedRoom schema is a richer follow-up).

Geometry: convex hull of XY-projected vertices by default; opt-in
reconstructions (``floor_reconstruction="concave"``/``"occupancy"`` or the
``ROOMESTIM_MESH_FLOOR_RECON`` env override) recover non-shoebox footprints via
:func:`roomestim.reconstruct.floor_polygon.floor_polygon_from_mesh`, with
``"occupancy"`` first rejecting sparse floaters via a density + connected-
component grid (:func:`...floor_polygon_from_mesh_occupancy`).
Material defaults per :data:`MaterialLabel`.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any, Literal, cast, get_args

import numpy as np
import trimesh
from shapely.geometry import MultiPoint
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.adapters.base import ScaleAnchor
from roomestim.model import (
    CeilingConfidence,
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
    canonicalize_ccw,
)
from roomestim.reconstruct.floor_polygon import (
    AUTO_FLOOR_RECON_NOTE,
    auto_should_use_occupancy,
    floor_polygon_from_mesh,
    floor_polygon_from_mesh_occupancy,
    floor_polygon_robust,
)
from roomestim.reconstruct.listener_area import default_listener_area
from roomestim.reconstruct.walls import walls_from_floor_polygon

# ``AUTO_FLOOR_RECON_NOTE`` is re-exported (single source lives in
# ``reconstruct.floor_polygon``) so CLI/web honesty NOTEs import it from the
# adapter surface alongside ``FloorReconstruction``.
__all__ = ["AUTO_FLOOR_RECON_NOTE", "MeshAdapter"]

_SUPPORTED_SUFFIXES = frozenset({".obj", ".gltf", ".glb", ".ply", ".usdz"})

FloorReconstruction = Literal["convex", "concave", "occupancy", "auto", "robust"]

# Explicit up-axis override. ``"auto"`` (default) runs the gravity-axis
# detector; ``"x"`` / ``"y"`` / ``"z"`` force a known axis when the caller has
# gravity metadata (e.g. RoomPlan/ARKit transform). The model's internal frame
# is Y-up, so a non-Y override triggers the same normalization the detector
# uses.
UpAxis = Literal["auto", "x", "y", "z"]

_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}

# USD stage upAxis token → the ``UpAxis`` hint the adapter understands. USD only
# defines Y-up and Z-up stages (X-up is not a USD convention), so a declared
# stage upAxis lets the USDZ path skip gravity auto-detect entirely.
_USD_UPAXIS_TO_HINT: dict[str, UpAxis] = {"Y": "y", "Z": "z"}

# Gravity-axis detection slab thickness (metres). The lowest/highest ~12 cm of
# vertices along a candidate up-axis. A real floor/ceiling is a wide, thin,
# horizontal plane, so its slab projects to a large 2D footprint; a wrong
# axis' extreme slab is a thin vertical slice with a tiny projected area.
# 12 cm is thick enough to capture a single dense floor layer on a noisy LiDAR
# scan yet thin enough not to fold in wall vertices. Used by the area co-signal
# (tiebreaker) and the confidence guard, not the primary density discriminator.
_UP_DETECT_SLAB_M = 0.12

# Planar-density discriminator parameters (primary up-axis signal).
#
# Physical basis: along the TRUE up-axis a gravity-aligned scan packs vertices
# into two sharp horizontal planes (floor + ceiling) at the extremes, while
# along a horizontal axis the floor/ceiling/wall vertices smear across the whole
# span. The density of the single densest bin AT each extreme therefore peaks
# on the up-axis — independent of the room's aspect ratio (so corridors and
# tall/narrow rooms are handled, unlike a footprint-area metric which a long
# wall can win).
#
# ``_UP_DETECT_BIN_M`` is an ABSOLUTE bin width (metres), not a fixed bin count:
# a fixed count would give a short axis finer bins and an unfair density boost
# (this is exactly what mis-ranked ARKit scene 41125756). A real floor settles
# within a few cm regardless of room size, so a physical 4 cm bin compares axes
# fairly. ``_UP_DETECT_EDGE_M`` is the ABSOLUTE window at each extreme in which
# the floor/ceiling plane is searched — the floor IS at the boundary, so a
# near-but-not-at-the-end cluster must not be mistaken for it.
_UP_DETECT_BIN_M = 0.04
_UP_DETECT_EDGE_M = 0.15

# Confidence thresholds (ratios of best score to runner-up). The density signal
# ties (≈1.0) on a sparse axis-aligned box (8 corners → 2 verts at each
# extreme on every axis), so a near-tie hands off to the area co-signal rather
# than guessing. The guard only RAISES when BOTH signals are ambiguous — a near
# cubic uniform-density mesh where no axis wins. Tuned against the 10 ARKit
# scenes (min density margin ≈2.0), realistic LiDAR-sampled corridors/tall
# rooms (≈5.8), and near-cubic bedrooms (≈6.4): all PASS; only a true cube
# (density 1,1,1 / area 9,9,9) raises.
_UP_DETECT_TIE_RATIO = 1.10

# ``_UP_DETECT_AREA_AMBIG_RATIO`` gates the density-degenerate AREA tiebreaker:
# the area heuristic (largest extreme-slab footprint == floor) is the discredited
# round-1 metric and is reliable ONLY when the room is not narrow — a long wall's
# cross-section (footprint_long × height) can exceed the floor footprint, so on a
# narrow box the area "winner" is a WALL, not the floor. We therefore require the
# top area to beat the runner-up by a CLEAR margin before trusting it; otherwise
# RAISE (fail loud) rather than silently report a horizontal span as the ceiling
# height. Empirically (sparse 8-corner boxes, where density ties exactly so this
# branch is reached): a square-ish room separates the floor from every wall
# cleanly (4×4×2.5 → floor 16 vs wall 10 = 1.60×; cube 3³ → 9/9 = 1.00×) while a
# narrow corridor does not (10×2×2.6 → wall 26 vs floor 20 = 1.30×, and the wall
# wins). A 1.50 bar trusts the square (1.60 ≥ 1.50) and the cube already failed
# the old 1.10 bar, but now RAISES the narrow corridor (1.30 < 1.50) instead of
# silently picking its long wall. Dense real scans never reach this branch
# (density margin ≥2.0), so this only governs coarse/parametric .obj/.ply input.
_UP_DETECT_AREA_AMBIG_RATIO = 1.50

# Floor-reconstruction mode (env override). ``ROOMESTIM_MESH_FLOOR_RECON``
# lets CLI/web opt into concave reconstruction without a code change,
# consistent with the ``ROOMESTIM_MAX_MESH_*`` env style. Precedence: an
# explicit ``MeshAdapter(floor_reconstruction=...)`` constructor argument wins;
# when the constructor argument is left at its sentinel default the env var is
# consulted; absent both, the mode is ``"convex"`` (byte-equal legacy path).
_FLOOR_RECON_ENV = "ROOMESTIM_MESH_FLOOR_RECON"

# Input resource bounds (ADR 0038). An untrusted mesh reaches
# ``trimesh.load(force="mesh")`` from both the CLI and the publicly-deployable
# web upload boundary; without a cap that path is a trivial DoS vector. Both
# limits are env-overridable so legitimate large-scan operators can raise them.
_MAX_MESH_FILE_BYTES = int(os.environ.get("ROOMESTIM_MAX_MESH_BYTES", 200 * 1024 * 1024))  # ~200 MB
_MAX_MESH_VERTICES = int(os.environ.get("ROOMESTIM_MAX_MESH_VERTICES", 5_000_000))  # ~5M

# Absolute ceiling-height plausibility bound (metres). A metersPerUnit lie or a
# mixed-unit mesh can survive the per-prim scaling and still stamp an absurd
# height as ``provenance="measured"`` — the silent-wrong-scale failure class this
# path exists to reject. 20 m clears every real room/venue in scope (synthetic
# fixtures ≤3 m, real ARKit scans 2.49–3.69 m) while catching the 250 m (raw cm)
# / 8.96 m (prototype double-count) class. Fail-loud is consistent with the 0a
# up-axis ambiguity guard and the image-backend near-horizon 20 m bound; env-
# overridable for the rare legitimate >20 m venue.
_MAX_CEILING_HEIGHT_M = float(os.environ.get("ROOMESTIM_MAX_CEILING_M", 20.0))

# Robust floor/ceiling plane estimation parameters. Phase 0b real-data
# validation (independent Faro laser GT) showed the naive full vertical extent
# (y_max - y_min) grabs scan OUTLIERS — furniture and ~1-3% of points that fall
# below the floor plane or poke above the ceiling plane — instead of the actual
# floor/ceiling PLANES, inflating the ceiling by +0.27 to +1.34 m (median +0.43,
# always positive; 0/5 scenes within ±10 cm of GT). The fix histograms the
# vertical (Y) coordinate at ``_FLOOR_CEILING_BIN_M`` (3 cm) resolution — fine
# enough to separate a sharp gravity-aligned floor/ceiling layer from nearby
# clutter, coarse enough that a single dense plane lands in one bin — and
# recovers the floor/ceiling as dense planes per Y-half (split at the midpoint).
#
# Plane selection: the floor is the BOTTOMMOST and the ceiling the TOPMOST bin
# whose count is at least ``_FLOOR_CEILING_DENSITY_FRAC`` of that half's peak.
# This is the validated density-peak method hardened against real-scan clutter:
# when the densest bin already sits at the dense-plane extreme — every clean
# fixture and well-scanned scene — "outermost dense" == "densest", so the result
# is byte-identical to the plain argmax (scene 42444946 → 3.035 m vs laser GT
# 3.034 m, 1 mm; synthetic fixtures → robust == full-extent exactly). It diverges
# only when a denser NON-extreme layer exists: a furniture/desk plane that the
# plain upper-half argmax mistook for the ceiling (e.g. ARKit 41069042 a desktop
# at y=-0.62 outranked the true ceiling at y=+1.03, collapsing the height to
# 0.63 m; 41142278 to 1.12 m). Anchoring to the outermost dense plane rejects
# that and recovers a plausible 2.27 / 2.31 m. The 0.5 fraction is the loosest
# threshold that still keeps the real (sometimes sparser) ceiling above sparse
# outlier tails on every Phase 0b + Validation scene.
_FLOOR_CEILING_BIN_M = 0.03
_FLOOR_CEILING_DENSITY_FRAC = 0.5

# Ceiling-confidence coverage metric (under-report guard for the residual
# mis-pick failure mode documented in ``_robust_floor_ceiling_y``). These ONLY
# annotate ``ceiling_height_m`` via ``ceiling_coverage`` / ``ceiling_confidence``;
# they never change the extracted height. See CEILING_CONFIDENCE_HEURISTIC_NOTE
# in ``roomestim/reconstruct/_disclosure.py`` (single source of truth).
_CEILING_COVERAGE_CELL_M = 0.25     # XZ grid resolution (25 cm cells)
_CEILING_COVERAGE_BAND_M = 0.10     # half-width of the ceiling band: ceiling_y +/- 10 cm
_CEILING_COVERAGE_MIN = 0.50        # coverage >= 0.50 -> "high", else "low" (HEURISTIC)

# Ceiling plane-plausibility floor (metres). At extreme vertex noise the robust
# ceiling height can COLLAPSE to an implausible value (validated n=1 SCRREAM:
# 1.34 m vs true 2.58 m) while still reading high coverage — a wrong-but-dense
# low plane spans the footprint. ``ceiling_confidence="high"`` must therefore
# also require a plausible height. 1.8 m sits safely below every legitimate
# fixture (the shoebox is 2.5 m; real ARKit robust ceilings reach down to
# ~2.24 m) while catching the validated 1.34 m collapse. This is a conservative
# HEURISTIC, NOT calibrated (consistent with CEILING_CONFIDENCE_HEURISTIC_NOTE);
# the upper bound is already enforced loud by _MAX_CEILING_HEIGHT_M, so this only
# adds a lower plausibility floor — it can ONLY demote "high" -> "low".
_CEILING_PLAUSIBLE_MIN_M = 1.8


class MeshAdapter:
    """``CaptureAdapter`` implementation for generic mesh exports.

    Supported formats: ``.obj``, ``.gltf``, ``.glb``, ``.ply``.
    Mesh must be metric-scale (metres). ``scale_anchor`` is ignored.

    Parameters
    ----------
    floor_reconstruction:
        ``"convex"`` (default) takes the convex hull of the floor-projected
        vertices — the legacy, byte-equal path. ``"concave"`` can in principle
        *represent* re-entrant geometry via :func:`floor_polygon_from_mesh`, but
        at the shipped default (``ratio=0.4``) does **not** recover real
        re-entrant corners — ICL-NUIM L-shape validation (n=1) shows concave
        +8.8% over-read vs. GT +5.5% concavity (convex +10.1%); notch recovery
        only appeared at a hand-tuned, non-default ``min_count=5`` knife-edge.
        ``"occupancy"`` denoises first via a density + connected-component grid
        (:func:`floor_polygon_from_mesh_occupancy`) that rejects sparse floaters
        before delegating to the concave path (occupancy +8.6% on the same
        scene). ``"auto"`` is convex-PRESERVING: a cheap coarse-grid (0.25 m)
        convex-hull area-inflation signal
        (:func:`disconnected_floater_phi`) switches to the ``"occupancy"``
        extractor ONLY when it detects a spatially-DISCONNECTED floater cluster
        (φ ≥ 1.10); on clean input the signal returns φ = 1.0 (a single coarse
        component) so ``"auto"`` resolves to the SAME convex call → byte-equal by
        construction. It is NOT a through-opening-bleed fix and NOT a re-entrant/
        notch-recovery capability (connected geometry never triggers it); see
        :data:`AUTO_FLOOR_RECON_NOTE`. ``"robust"`` is the Primitive-A density-
        percentile boundary trim (:func:`floor_polygon_robust`): it drops the top
        ``drop_pct`` % sparsest-kNN boundary "flyers" of the floor band before the
        concave hull, halving the vertex-noise over-estimate (validated n=1
        SCRREAM: +19.4%→+8.3% @ 5 cm, +39%→+12% @ 10 cm; unchanged on clean
        input). It is the noise-robust opt-in only — NOT a through-opening/bleed
        fix and NOT an accuracy guarantee on real room scans. The
        ``"concave"``/``"occupancy"``/``"robust"`` modes
        (and the occupancy branch ``"auto"`` may pick) fall back to the convex
        hull (with a :class:`UserWarning`) when reconstruction degenerates. When
        left at its sentinel default the
        ``ROOMESTIM_MESH_FLOOR_RECON`` environment variable selects the mode; an
        explicit argument always wins over the env var.
    up_axis:
        Which mesh axis points "up" (against gravity). ``"auto"`` (default)
        detects the gravity axis from the mesh geometry — required for real
        gravity-aligned scans (ARKitScenes, RoomPlan, generic ``.ply``/``.obj``
        exports) which are commonly Z-up, not the Y-up convention the synthetic
        fixtures and glTF use. Pass ``"x"`` / ``"y"`` / ``"z"`` to force a known
        axis when the caller has gravity metadata. The model's internal frame
        is Y-up, so any non-Y axis is normalized (axes permuted so up → +Y)
        before extraction. ``"auto"`` assumes the mesh is gravity-aligned to one
        of its principal axes (true for ARKit/RoomPlan and gravity-aligned
        scans); a tilted mesh is not corrected — pass an explicit axis for it.
    """

    def __init__(
        self,
        *,
        floor_reconstruction: FloorReconstruction | None = None,
        up_axis: UpAxis = "auto",
    ) -> None:
        self._floor_reconstruction = self._resolve_floor_reconstruction(
            floor_reconstruction
        )
        if up_axis not in get_args(UpAxis):
            raise ValueError(
                f"MeshAdapter: up_axis must be one of {list(get_args(UpAxis))}, "
                f"got {up_axis!r}."
            )
        self._up_axis = up_axis

    @staticmethod
    def _resolve_floor_reconstruction(
        explicit: FloorReconstruction | None,
    ) -> FloorReconstruction:
        """Resolve the floor-reconstruction mode (constructor arg > env > convex)."""
        modes = get_args(FloorReconstruction)
        if explicit is not None:
            if explicit not in modes:
                raise ValueError(
                    f"MeshAdapter: floor_reconstruction must be 'convex', "
                    f"'concave', 'occupancy', 'auto', or 'robust', got {explicit!r}."
                )
            return explicit
        env_value = os.environ.get(_FLOOR_RECON_ENV)
        if env_value is None:
            return "convex"
        normalized = env_value.strip().lower()
        if normalized not in modes:
            raise ValueError(
                f"MeshAdapter: {_FLOOR_RECON_ENV}={env_value!r} is invalid; "
                f"expected 'convex', 'concave', 'occupancy', 'auto', or 'robust'."
            )
        return cast(FloorReconstruction, normalized)

    def parse(
        self,
        path: Path | str,
        *,
        scale_anchor: ScaleAnchor | None = None,
        octave_band: bool = False,
    ) -> RoomModel:
        del scale_anchor  # mesh adapters assume metric-native input
        path_obj = Path(path)
        suffix = path_obj.suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError(
                f"MeshAdapter: unsupported extension {suffix!r}; "
                f"expected one of {sorted(_SUPPORTED_SUFFIXES)}."
            )
        # ADR 0038: bound file size BEFORE any reader touches the bytes. Guards
        # both the CLI and the web upload path against a DoS-sized mesh.
        file_bytes = path_obj.stat().st_size
        if file_bytes > _MAX_MESH_FILE_BYTES:
            raise ValueError(
                f"MeshAdapter: mesh file is {file_bytes} bytes, exceeding the "
                f"{_MAX_MESH_FILE_BYTES}-byte cap (set ROOMESTIM_MAX_MESH_BYTES "
                f"to raise it)."
            )
        if suffix == ".usdz":
            return self._room_model_from_usdz(path_obj, octave_band=octave_band)
        return self._room_model_from_mesh(path_obj, octave_band=octave_band)

    @staticmethod
    def _convex_floor_polygon(vertices: np.ndarray) -> list[Point2]:
        """Convex hull of the floor-projected vertices (legacy byte-equal path).

        Projects vertices to the (x, z) floor plane and takes their convex
        hull, dropping the duplicate closing vertex shapely returns on the
        exterior. v0.1 smoke geometry semantics — no concavity recovery.
        """
        xz_points = [(float(v[0]), float(v[2])) for v in vertices]
        hull = MultiPoint(xz_points).convex_hull
        if not isinstance(hull, ShapelyPolygon):
            raise ValueError(
                "MeshAdapter: convex hull of projected vertices is not a "
                "polygon; the mesh appears degenerate (collinear or single-point)."
            )
        exterior_coords = list(hull.exterior.coords)[:-1]
        return canonicalize_ccw(
            [Point2(float(x), float(z)) for x, z in exterior_coords]
        )

    @staticmethod
    def _slab_footprint_area(
        vertices: np.ndarray, axis: int, *, slab_m: float = _UP_DETECT_SLAB_M
    ) -> tuple[float, float]:
        """Projected footprint area of the lowest/highest slab along ``axis``.

        For ``axis`` treated as "up", take the vertices within ``slab_m`` of its
        minimum and of its maximum, project each slab onto the other two axes,
        and return ``(low_area, high_area)`` — the 2D convex-hull area of each
        projection. A real horizontal floor/ceiling plane yields a large area;
        a wrong axis' extreme slab is a thin vertical slice with near-zero area.
        """
        others = [a for a in range(3) if a != axis]
        coord = vertices[:, axis]
        lo, hi = float(coord.min()), float(coord.max())

        def _area(mask: np.ndarray) -> float:
            pts = vertices[mask][:, others]
            if pts.shape[0] < 3:
                return 0.0
            hull = MultiPoint([(float(x), float(y)) for x, y in pts]).convex_hull
            if not isinstance(hull, ShapelyPolygon):
                return 0.0
            return float(hull.area)

        low_mask = coord <= lo + slab_m
        high_mask = coord >= hi - slab_m
        return _area(low_mask), _area(high_mask)

    @staticmethod
    def _planar_density(
        vertices: np.ndarray,
        axis: int,
        *,
        bin_m: float = _UP_DETECT_BIN_M,
        edge_m: float = _UP_DETECT_EDGE_M,
    ) -> float:
        """Floor+ceiling planar concentration of ``axis`` (primary up signal).

        Build a 1-D histogram of the vertex coordinates along ``axis`` with an
        absolute ``bin_m`` bin width, then return the summed fraction of
        vertices in the single densest bin within ``edge_m`` of the minimum
        (floor) and the single densest bin within ``edge_m`` of the maximum
        (ceiling). Along the true up-axis those two planes are sharp and dense;
        along a horizontal axis the mass is spread out, so the score is lower.

        Aspect-ratio-independent: it measures *concentration*, not footprint
        size, so a 10 m corridor and a 2 m tall closet score the floor/ceiling
        the same way a square room does.
        """
        coord = vertices[:, axis]
        lo, hi = float(coord.min()), float(coord.max())
        ext = hi - lo
        if ext <= 0.0:
            return 0.0
        n_bins = max(8, int(round(ext / bin_m)))
        hist, edges = np.histogram(coord, bins=n_bins, range=(lo, hi))
        total = hist.sum()
        if total == 0:
            return 0.0
        frac = hist / total
        centers = (edges[:-1] + edges[1:]) / 2.0
        low_win = frac[centers <= lo + edge_m]
        high_win = frac[centers >= hi - edge_m]
        low_peak = float(low_win.max()) if low_win.size else 0.0
        high_peak = float(high_win.max()) if high_win.size else 0.0
        return low_peak + high_peak

    @staticmethod
    def _robust_floor_ceiling_y(coord: np.ndarray) -> tuple[float, float]:
        """Robust floor/ceiling plane heights along the (Y-up) vertical axis.

        Phase 0b real-data validation against independent Faro laser GT proved
        the naive full vertical extent (``y_max - y_min``) is wrong on real
        scans: it grabs OUTLIERS — furniture and the ~1-3% of vertices that fall
        below the floor plane or poke above the ceiling plane — rather than the
        actual floor/ceiling PLANES, inflating the ceiling by +0.27 to +1.34 m
        (median +0.43 m, always positive; 0/5 scenes within ±10 cm of GT). On
        scene 42444946 the full extent reads 4.370 m but the true ceiling is
        3.034 m (laser GT).

        A gravity-aligned scan packs the floor and ceiling into two sharp,
        horizontal, dense layers. We histogram the Y coordinate at
        ``_FLOOR_CEILING_BIN_M`` (3 cm) resolution and split at the Y midpoint,
        then recover the floor as the BOTTOMMOST and the ceiling as the TOPMOST
        bin whose count is at least ``_FLOOR_CEILING_DENSITY_FRAC`` of that
        half's peak bin. On clean fixtures and well-scanned rooms the densest bin
        already sits at the dense-plane extreme, so "outermost dense" reduces to
        the plain densest bin — robust == full-extent on synthetic meshes and
        3.035 m (1 mm from GT) on scene 42444946. Anchoring to the *outermost*
        dense plane (rather than the global argmax within the half) is the
        hardening real scans require: a desktop/furniture layer can be DENSER
        than the true ceiling (ARKit 41069042: desk at y=-0.62 outranks the
        ceiling at y=+1.03), so a plain argmax collapses the height to 0.63 m;
        taking the topmost still-dense bin recovers the real 2.27 m ceiling.

        Robustness: if a Y-half holds too few points to histogram (degenerate or
        near-flat input), fall back to that half's min/max so this never crashes,
        mirroring the existing fail-safe style.

        Residual failure mode (honest limitation, NOT fixed here): the ceiling is
        taken as the TOPMOST still-dense bin in the upper half, so a horizontal
        plane that is both dense AND nearer the true ceiling than the actual
        ceiling layer can be mis-picked, UNDER-reporting height — e.g. a large
        flat table/desk surface or dense mid-height shelving sitting high in the
        upper half, a mezzanine/loft slab, or a true ceiling so severely
        under-sampled that no bin clears the density-FRAC threshold (then the
        next-lower dense plane wins). This was acceptable for the cases validated
        against independent Faro laser GT (living rooms with ordinary furniture,
        where the topmost dense plane IS the ceiling) and is a known, bounded
        residual rather than a silent correctness hole — heights stay plausible
        and the absolute-ceiling guard still fires. This residual is now ANNOTATED
        (not corrected) by :meth:`_ceiling_coverage` + the ``ceiling_confidence``
        flag on the returned :class:`RoomModel`: the coverage check (the ceiling
        should span most of the footprint, a tabletop should not) flags a likely
        mis-pick as ``ceiling_confidence="low"``. The extracted height itself is
        unchanged here.
        """
        lo, hi = float(coord.min()), float(coord.max())
        ext = hi - lo
        if ext <= 0.0:
            return lo, hi
        mid = (lo + hi) / 2.0

        def _dense_plane_center(half: np.ndarray, *, topmost: bool) -> float | None:
            if half.size == 0:
                return None
            half_lo, half_hi = float(half.min()), float(half.max())
            half_ext = half_hi - half_lo
            if half_ext <= 0.0:
                return half_lo
            n_bins = max(1, int(round(half_ext / _FLOOR_CEILING_BIN_M)))
            hist, edges = np.histogram(half, bins=n_bins, range=(half_lo, half_hi))
            peak = int(hist.max())
            if peak == 0:
                return None
            # Bins forming a "dense plane": at least FRAC of this half's peak.
            dense = np.nonzero(hist >= peak * _FLOOR_CEILING_DENSITY_FRAC)[0]
            # Ceiling = topmost such bin; floor = bottommost. On clean data the
            # peak bin IS the extreme, so this equals the plain densest bin.
            idx = int(dense[-1] if topmost else dense[0])
            return float((edges[idx] + edges[idx + 1]) / 2.0)

        floor_y = _dense_plane_center(coord[coord <= mid], topmost=False)
        ceiling_y = _dense_plane_center(coord[coord >= mid], topmost=True)
        # Fall back to the raw extremes if a half could not be histogrammed.
        if floor_y is None:
            floor_y = lo
        if ceiling_y is None:
            ceiling_y = hi
        return floor_y, ceiling_y

    @staticmethod
    def _ceiling_coverage(vertices: np.ndarray, ceiling_y: float) -> float | None:
        """Fraction of the floor footprint spanned by the detected ceiling plane.

        Honest GEOMETRIC measurement (not a heuristic): bin the XZ extent of all
        (Y-up-normalized) ``vertices`` into ``_CEILING_COVERAGE_CELL_M`` (25 cm)
        square cells, then return

            |cells holding a vertex within +/-_CEILING_COVERAGE_BAND_M of
             ``ceiling_y``| / |cells holding a vertex at ANY height|

        clamped to ``[0, 1]``. The denominator is the room's occupied footprint
        (occupancy, not the bbox rectangle — robust for L-shaped / non-shoebox
        rooms). NOTE this is a vertex-OCCUPANCY measure, so it also tracks how
        densely the ceiling is SAMPLED: a true ceiling that spans the footprint
        AND is tessellated/scanned comparably to the floor and walls reads
        ~1.0 (the densely-sampled real-LiDAR and clean-shoebox case); a tabletop
        / mezzanine slab occupies only its own small XZ patch (small ratio), and
        a true ceiling that is geometrically complete but coarsely tessellated
        (e.g. a single low-poly quad) or severely under-sampled also reads low.
        That makes the metric deliberately CONSERVATIVE — it raises a false
        "low" on an under-sampled-but-complete ceiling, never a false "high" on a
        mis-picked one — which is the safe failure direction for a guard.

        This NEVER changes ``ceiling_height_m`` — it only annotates it. Returns
        ``None`` on degenerate input (no footprint cells), mirroring the fail-safe
        min/max fall-back style in :meth:`_robust_floor_ceiling_y` (never raises).
        The ``ceiling_confidence`` label this feeds is a HEURISTIC, NOT a
        calibrated probability — see CEILING_CONFIDENCE_HEURISTIC_NOTE.
        """
        if vertices.shape[0] == 0:
            return None
        # Guard the full XYZ (not just XZ): a non-finite Y silently fails the
        # band comparison below (NaN <= band is False) and would understate
        # coverage rather than fail safe. Reject any non-finite vertex outright.
        if not np.all(np.isfinite(vertices[:, :3])):
            return None
        xz = vertices[:, [0, 2]]
        cells = np.floor(xz / _CEILING_COVERAGE_CELL_M).astype(np.int64)
        footprint = {(int(cx), int(cz)) for cx, cz in cells}
        if not footprint:
            return None
        in_band = np.abs(vertices[:, 1] - ceiling_y) <= _CEILING_COVERAGE_BAND_M
        band_cells = {
            (int(cx), int(cz)) for cx, cz in cells[in_band]
        }
        coverage = len(band_cells) / len(footprint)
        return float(min(1.0, max(0.0, coverage)))

    @staticmethod
    def _classify_ceiling_confidence(
        coverage: float | None,
        ceiling_height_m: float | None = None,
    ) -> CeilingConfidence:
        """Map ``ceiling_coverage`` (+ height) to the HEURISTIC confidence label.

        ``None`` coverage (not measured) -> ``"unknown"``. Otherwise ``"high"``
        requires BOTH ``coverage >= _CEILING_COVERAGE_MIN`` AND a plausible
        height (``ceiling_height_m is None`` — gate skipped, back-compat — OR
        ``_CEILING_PLAUSIBLE_MIN_M <= ceiling_height_m <= _MAX_CEILING_HEIGHT_M``);
        anything else is ``"low"``.

        The plausibility gate exists because a wrong-but-dense COLLAPSED ceiling
        plane (validated n=1 SCRREAM: 1.34 m vs true 2.58 m at extreme noise)
        still reads high coverage, so coverage alone falsely reports ``"high"``.
        The gate only ever DEMOTES ``"high"`` -> ``"low"`` (never the reverse),
        keeping the conservative/honest framing. The 0.50 coverage threshold and
        the 1.8 m plausibility floor are conservative geometric rules of thumb
        validated only on synthetic fixtures — NOT calibrated against measured
        data (see CEILING_CONFIDENCE_HEURISTIC_NOTE). ``ceiling_height_m`` is read
        only; this never changes the extracted height.
        """
        if coverage is None:
            return "unknown"
        plausible_height = ceiling_height_m is None or (
            _CEILING_PLAUSIBLE_MIN_M <= ceiling_height_m <= _MAX_CEILING_HEIGHT_M
        )
        if coverage >= _CEILING_COVERAGE_MIN and plausible_height:
            return "high"
        return "low"

    @classmethod
    def _detect_up_axis(cls, vertices: np.ndarray) -> int:
        """Detect the gravity (up) axis via a floor/ceiling planar-density signal.

        Assumes the mesh is gravity-aligned to one of its principal axes (true
        for ARKit/RoomPlan and gravity-aligned LiDAR exports); the only question
        is *which* axis. Tilted meshes are NOT corrected here — pass an explicit
        ``up_axis`` for those.

        Primary signal (:meth:`_planar_density`): along the up-axis the vertices
        form two sharp planar concentrations (floor + ceiling) at the extremes;
        horizontal axes are flatter. This is independent of room aspect ratio,
        so it picks the up-axis correctly for corridors and tall/narrow rooms
        where a footprint-area metric would lose to a long wall.

        Tiebreaker (:meth:`_slab_footprint_area`): on a sparse axis-aligned box
        (8 corners) the density signal ties exactly across all axes, so a
        near-tie hands off to the larger floor footprint — the floor spans more
        than any wall.

        Confidence guard: when BOTH signals are ambiguous (a near-cubic,
        uniform-density mesh where no axis wins) this RAISES ``ValueError``
        recommending an explicit ``up_axis`` rather than silently returning a
        low-confidence guess.
        """
        density = [cls._planar_density(vertices, axis) for axis in range(3)]
        order = sorted(range(3), key=lambda a: density[a], reverse=True)
        top, runner = order[0], order[1]

        # Clear density winner: the up-axis's floor/ceiling planes dominate.
        if density[runner] <= 0.0 or density[top] / density[runner] >= _UP_DETECT_TIE_RATIO:
            return top

        # Density near-tie → break with the floor-footprint area among the tied
        # axes (the floor spans more than any wall). This area heuristic is the
        # discredited round-1 metric and is trustworthy ONLY when the room is not
        # narrow: on a narrow box a long wall's cross-section can beat the floor,
        # so the area "winner" would be a WALL. We therefore demand a CLEAR
        # floor-over-runner-up margin (_UP_DETECT_AREA_AMBIG_RATIO) below — when
        # it is not met the geometry is ambiguous and we fail loud rather than
        # silently report a horizontal span as the ceiling height.
        areas = [max(cls._slab_footprint_area(vertices, axis)) for axis in range(3)]
        tied = [
            a
            for a in range(3)
            if density[top] > 0.0 and density[a] / density[top] >= 1.0 / _UP_DETECT_TIE_RATIO
        ]
        ranked = sorted(tied, key=lambda a: areas[a], reverse=True)

        # No clear floor (near-cubic, or narrow room where a wall rivals the
        # floor) → ambiguous geometry; fail loud (measured path).
        if (
            len(ranked) > 1
            and areas[ranked[1]] > 0.0
            and areas[ranked[0]] / areas[ranked[1]] < _UP_DETECT_AREA_AMBIG_RATIO
        ):
            raise ValueError(
                "MeshAdapter: up-axis is ambiguous — no axis is a clear "
                f"floor/ceiling plane (density={[round(d, 3) for d in density]}, "
                f"slab_area={[round(a, 3) for a in areas]}). The mesh may be "
                "near-cubic or not gravity-aligned to a principal axis; pass an "
                "explicit up_axis='x'|'y'|'z' to resolve it."
            )
        return ranked[0]

    @staticmethod
    def _normalize_to_y_up(vertices: np.ndarray, up_axis: int) -> np.ndarray:
        """Permute axes so the detected up-axis maps to +Y (the model frame).

        roomestim's RoomModel frame is Y-up (``Point2`` is ``(x, z)``; ceiling
        lifts at ``y``). Remapping the mesh once here lets every downstream
        extraction step (floor band, ceiling height, floor polygon, walls,
        ``Point3`` lifts) keep the existing, verified Y-up logic unchanged.

        The horizontal axes are kept in ascending index order, so a Y-up mesh
        (``up_axis == 1``) is returned byte-identical (identity permutation).
        """
        if up_axis == 1:
            return vertices
        horizontals = [a for a in range(3) if a != up_axis]
        # New order: (x, y, z) = (horizontal_lo, up, horizontal_hi). This axis
        # permutation may be orientation-reversing (determinant −1, e.g. the
        # (x, z) → (z, x) swap when up_axis == 0). That is SAFE: every
        # downstream floor polygon is re-canonicalized CCW via canonicalize_ccw,
        # so winding is fixed regardless of handedness. Do NOT "fix" this into a
        # det=+1 rotation — that would change which horizontal lands on X/Z.
        order = [horizontals[0], up_axis, horizontals[1]]
        return vertices[:, order]

    def _room_model_from_mesh(self, path: Path, *, octave_band: bool = False) -> RoomModel:
        loaded = trimesh.load(path, force="mesh")
        # ``force='mesh'`` coerces a Scene into a single Trimesh; vertices is
        # always an ndarray of shape (N, 3) at that point.
        vertices_attr = getattr(loaded, "vertices", None)
        if vertices_attr is None:
            raise ValueError(
                f"MeshAdapter: trimesh.load({path!r}) returned no vertices"
            )
        vertices = np.asarray(vertices_attr, dtype=float)
        if vertices.ndim != 2 or vertices.shape[1] != 3:
            raise ValueError(
                f"MeshAdapter: expected (N, 3) vertex array, got shape "
                f"{vertices.shape}"
            )

        # OQ-21: a points-only PLY (vertices but no triangular faces) loads as a
        # Trimesh with len(faces)==0; the (N, 3) vertex check above does NOT
        # catch it. Reject early — a surface mesh is required (downstream
        # convex-hull-of-projection logic is undefined for point clouds).
        faces = np.asarray(getattr(loaded, "faces", []))
        if len(faces) == 0:
            raise ValueError(
                "MeshAdapter: mesh has 0 faces (points-only PLY); a surface "
                "mesh with triangular faces is required."
            )

        # ``cast`` keeps mypy strict happy where trimesh attribute access
        # returns ``Any`` — we only use ``vertices`` numerically above.
        _ = cast(Any, loaded)

        return self._extract_room_model(
            vertices, name=path.stem, octave_band=octave_band
        )

    @staticmethod
    def _import_pxr() -> Any:
        """Import ``pxr`` lazily with a helpful ImportError when missing.

        Mirrors :func:`roomestim.export.usd._import_pxr` so the adapter module
        stays import-light (and torch-free): ``pxr`` is only required when a
        ``.usdz`` is actually parsed, not at module import.
        """
        try:
            # Import the submodules explicitly: ``import pxr`` alone does not
            # populate ``pxr.Usd`` / ``pxr.UsdGeom`` (they are separate C-ext
            # modules). Returning the package after importing them mirrors how
            # downstream code reads ``pxr.Usd`` etc.
            import pxr
            from pxr import Usd, UsdGeom  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "USDZ input requires the [usd] extra; install with "
                "`pip install 'roomestim[usd]'` or "
                "`pip install 'roomestim[mesh-export]'`."
            ) from exc
        return pxr

    def _room_model_from_usdz(
        self, path: Path, *, octave_band: bool = False
    ) -> RoomModel:
        """Load a ``.usdz`` geometry scan into a ``RoomModel``.

        Reads every :class:`UsdGeom.Mesh` prim, bakes it to world space via the
        prim's local-to-world transform, combines all prims into one world-space
        vertex set, and feeds that into the SAME up-axis-normalized extraction
        the other formats use. When the stage declares an ``upAxis`` it is passed
        as a hint (more robust than gravity auto-detect); otherwise auto-detect
        runs. Scope: geometry meshes (Polycam/ARKit/generic). RoomPlan's
        parametric CapturedRoom schema is a follow-up.
        """
        vertices, up_axis_hint = self._vertices_from_usdz(path)
        if vertices.shape[0] == 0:
            raise ValueError(
                f"MeshAdapter: USDZ {path!r} contains no UsdGeom.Mesh geometry. "
                "Parametric RoomPlan USD (CapturedRoom analytic walls) is not "
                "yet supported; export a textured/plain mesh USDZ instead."
            )
        return self._extract_room_model(
            vertices,
            name=path.stem,
            octave_band=octave_band,
            up_axis_hint=up_axis_hint,
        )

    def _vertices_from_usdz(self, path: Path) -> tuple[np.ndarray, UpAxis | None]:
        """Return ``(world_space_vertices, up_axis_hint)`` from a ``.usdz``.

        Opens the USD stage, traverses all :class:`UsdGeom.Mesh` prims (including
        those reached through instance proxies), applies each prim's
        local-to-world transform (so a multi-prim scene combines into one
        consistent world-space cloud), scales every vertex by the stage's
        ``metersPerUnit`` so the output is always in METRES, and stacks the
        points into a single ``(N, 3)`` array. ``up_axis_hint`` is the stage's
        declared ``upAxis`` (``"y"`` / ``"z"``) when present, else ``None`` (let
        auto-detect run). Faces are not returned: downstream extraction keys on
        vertices only.
        """
        pxr = self._import_pxr()
        Usd = pxr.Usd
        UsdGeom = pxr.UsdGeom

        stage = Usd.Stage.Open(str(path))
        if stage is None:
            raise ValueError(
                f"MeshAdapter: could not open USD stage from {path!r} "
                "(not a valid USD/USDZ package?)."
            )

        # metersPerUnit is the stage's authored linear scale. Apple RoomPlan /
        # Reality Composer USDZ exports are authored in CENTIMETRES
        # (metersPerUnit == 0.01), so a 2.5 m room arrives as raw points of 250 —
        # ingesting that unscaled stamps a 250 m ceiling as ``provenance="measured"``,
        # the exact silent-wrong-scale class this path must reject. USD's API
        # returns the stage's effective value (default 0.01 when unauthored), so
        # we trust it and scale world vertices by it; we only reject a degenerate
        # non-positive / non-finite value rather than divide-by-zero or pass garbage.
        mpu = float(UsdGeom.GetStageMetersPerUnit(stage))
        if not np.isfinite(mpu) or mpu <= 0.0:
            raise ValueError(
                f"MeshAdapter: USDZ {path!r} declares a non-positive / non-finite "
                f"metersPerUnit ({mpu!r}); cannot scale geometry to metres."
            )

        # Stage upAxis is authoritative when declared (skip gravity detection).
        up_token = str(UsdGeom.GetStageUpAxis(stage))
        up_axis_hint = _USD_UPAXIS_TO_HINT.get(up_token)

        xform_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
        chunks: list[np.ndarray] = []
        # ``TraverseInstanceProxies`` descends INTO instance prototypes: the
        # default predicate stops at instance boundaries, so meshes authored once
        # in a prototype and referenced as ``Usd.Instanceable`` instances (common
        # in furnished RoomPlan/Reality Composer scenes) would be silently
        # dropped. ``XformCache.GetLocalToWorldTransform`` resolves correctly on
        # the instance-proxy prims, so each instance lands at its world placement.
        #
        # Scope the traversal to the stage's DEFAULT PRIM subtree, which
        # idiomatically IS the asset. A CONCRETE (``def``, not ``class``)
        # prototype source authored as a sibling of the default prim and
        # referenced by ``instanceable=True`` prims would otherwise be DOUBLE-
        # COUNTED: the raw prototype mesh is visited once at its own authored
        # location AND once per instance proxy, inflating the bounding box /
        # ceiling height (a 2.5 m room read as 8.96 m, still stamped "measured").
        # Restricting to the default prim excludes library/prototype scopes
        # authored outside it while still descending into legitimate instances
        # placed under it. Keep the whole-stage fallback for stages that author
        # no default prim.
        default_prim = stage.GetDefaultPrim()
        if default_prim and default_prim.IsValid():
            prim_iter: Any = iter(
                Usd.PrimRange(
                    default_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
                )
            )
        else:
            prim_iter = stage.Traverse(
                Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
            )
        for prim in prim_iter:
            if not prim.IsA(UsdGeom.Mesh):
                continue
            mesh = UsdGeom.Mesh(prim)
            points_attr = mesh.GetPointsAttr()
            points = points_attr.Get() if points_attr.IsValid() else None
            if points is None or len(points) == 0:
                continue
            local_pts = np.asarray(points, dtype=float)
            # Bake the prim's local-to-world transform so multi-prim scenes share
            # one world frame. USD matrices are row-vector convention
            # (v' = v · M), so right-multiply the (N, 3) homogeneous points.
            xf = xform_cache.GetLocalToWorldTransform(prim)
            mat = np.asarray(
                [[xf[r][c] for c in range(4)] for r in range(4)], dtype=float
            )
            homo = np.column_stack([local_pts, np.ones(local_pts.shape[0])])
            world = homo @ mat
            chunks.append(world[:, :3])

        if not chunks:
            return np.empty((0, 3), dtype=float), up_axis_hint
        # Scale to metres ONCE, consistently across all prim chunks, before any
        # downstream extraction (the gravity detector's bins are absolute metres,
        # so the scale must be applied before it runs in the cross-check below).
        vertices = np.vstack(chunks) * mpu

        # Cross-check the declared upAxis against the geometry. A mis-authored
        # stage (declares Y-up but the mesh is Z-up) would otherwise silently
        # yield a wrong ceiling height. We only cross-check when the hint would
        # actually be used (constructor up_axis left at "auto"). The
        # planar-density detector is the arbiter: agreement → trust the hint
        # (fast path, unchanged); a CLEAR disagreement → fail loud naming both;
        # detector-ambiguous (it RAISES on e.g. a sparse 8-corner box, where it
        # cannot tell) → trust the declared hint, which is still better than a
        # blind guess. This keeps the correctly-authored committed fixtures
        # passing while catching a genuinely mis-declared stage.
        if self._up_axis == "auto" and up_axis_hint is not None:
            try:
                detected = self._detect_up_axis(vertices)
            except ValueError:
                detected = None  # detector ambiguous → defer to the declared hint
            if detected is not None and detected != _AXIS_INDEX[up_axis_hint]:
                detected_label = {0: "x", 1: "y", 2: "z"}.get(detected, str(detected))
                raise ValueError(
                    f"MeshAdapter: USDZ {path!r} declares upAxis={up_token!r} "
                    f"(→ '{up_axis_hint}') but its geometry is unambiguously "
                    f"'{detected_label}'-up (gravity detector). The stage appears "
                    "mis-authored; pass an explicit up_axis='x'|'y'|'z' override "
                    "to resolve the conflict."
                )
        return vertices, up_axis_hint

    def _extract_room_model(
        self,
        vertices: np.ndarray,
        *,
        name: str,
        octave_band: bool = False,
        up_axis_hint: UpAxis | None = None,
    ) -> RoomModel:
        """Build a ``RoomModel`` from a world-space ``(N, 3)`` vertex array.

        Shared by every format (trimesh-loaded ``.obj``/``.ply``/… and the
        ``.usdz`` USD path). All up-axis normalization and floor/ceiling/wall
        extraction lives here so the geometry logic is single-sourced.

        ``up_axis_hint`` lets a caller that already knows the gravity axis (e.g.
        a USD stage that declares its ``upAxis``) skip auto-detect; ``None``
        falls back to the adapter's own ``up_axis`` setting (``"auto"`` → the
        gravity-axis detector).
        """
        # ADR 0038: bound vertex count (after shape validation, before the O(N)
        # hull projection below). A file under the byte cap can still expand to a
        # pathological vertex count after parsing.
        if vertices.shape[0] > _MAX_MESH_VERTICES:
            raise ValueError(
                f"MeshAdapter: mesh has {vertices.shape[0]} vertices, exceeding "
                f"the {_MAX_MESH_VERTICES}-vertex cap (set "
                f"ROOMESTIM_MAX_MESH_VERTICES to raise it)."
            )

        # P0 (commercialization plan 0a): real gravity-aligned scans
        # (ARKitScenes, RoomPlan, many .ply/.obj exports) are commonly Z-up, not
        # the Y-up convention of the synthetic fixtures and glTF. Resolve the up
        # (gravity) axis, then normalize the mesh into the model's Y-up frame so
        # all downstream extraction keys on the correct vertical axis. Without
        # this, a horizontal room dimension is mistaken for ceiling height
        # (observed 6.5–9.6 m on real ARKit rooms that are ≈2.4–3 m).
        #
        # Precedence: an explicit constructor ``up_axis`` always wins; otherwise
        # a declared stage hint (USD ``upAxis``) is trusted (more robust than
        # detection); absent both, the gravity-axis detector runs.
        if self._up_axis != "auto":
            up_axis = _AXIS_INDEX[self._up_axis]
        elif up_axis_hint is not None and up_axis_hint != "auto":
            up_axis = _AXIS_INDEX[up_axis_hint]
        else:
            up_axis = self._detect_up_axis(vertices)
        vertices = self._normalize_to_y_up(vertices, up_axis)

        # Floor/ceiling as ROBUST density-peak planes, not the full vertical
        # extent. Phase 0b (independent Faro laser GT) showed full-extent
        # (y_max - y_min) grabs scan outliers (furniture, ~1-3% of points below
        # the floor / above the ceiling) and inflates the ceiling by up to
        # +1.34 m; the densest-bin floor/ceiling planes match the laser GT to
        # ~1 mm on scene-class data and are byte-identical on clean fixtures.
        floor_y, ceiling_y = self._robust_floor_ceiling_y(vertices[:, 1])
        ceiling_height_m = float(ceiling_y - floor_y)
        # Annotate (never change) the height with a coverage/confidence flag for
        # the residual mis-pick failure mode of _robust_floor_ceiling_y (a
        # tabletop / mezzanine slab / under-sampled ceiling can be the topmost
        # still-dense bin). ceiling_coverage is an honest geometric measurement;
        # ceiling_confidence is a HEURISTIC label, NOT a calibrated probability.
        ceiling_coverage = self._ceiling_coverage(vertices, ceiling_y)
        ceiling_confidence = self._classify_ceiling_confidence(
            ceiling_coverage, ceiling_height_m
        )
        if ceiling_height_m <= 0.0:
            raise ValueError(
                f"MeshAdapter: degenerate mesh height "
                f"(ceiling_y={ceiling_y}, floor_y={floor_y})"
            )
        # Absolute plausibility bound. A correctly-scaled real room/venue never
        # exceeds this; a height beyond it is almost always a unit/scale
        # (metersPerUnit) mismatch or a corrupt bounding box (e.g. a phantom
        # prototype copy), which we refuse to silently stamp as "measured".
        if ceiling_height_m > _MAX_CEILING_HEIGHT_M:
            raise ValueError(
                f"MeshAdapter: implausible ceiling height {ceiling_height_m:.2f} m "
                f"exceeds the {_MAX_CEILING_HEIGHT_M:.1f} m bound. This almost "
                "always indicates a unit/scale (metersPerUnit) mismatch or a "
                "corrupt mesh; refusing to stamp it as measured. Set "
                "ROOMESTIM_MAX_CEILING_M to raise the bound for a genuinely "
                "larger venue."
            )

        # Reconstruct the floor footprint. ``convex`` (default) takes the
        # convex hull of the floor-projected vertices — the byte-equal legacy
        # path. ``concave`` recovers re-entrant corners (non-shoebox rooms);
        # ``occupancy`` adds a density + connected-component denoiser in front
        # of the concave path (rejects sparse floaters). ``auto`` is convex-
        # preserving: it runs a cheap coarse-grid convex-hull area-inflation
        # signal and switches to the occupancy extractor ONLY when a spatially-
        # DISCONNECTED floater is detected; on clean input the signal returns
        # φ = 1.0 (single coarse component) so ``auto`` resolves to the SAME
        # ``_convex_floor_polygon(vertices)`` call as ``convex`` → byte-equal by
        # construction. It is NOT a through-opening-bleed or notch-recovery fix
        # (connected geometry never triggers it). See AUTO_FLOOR_RECON_NOTE.
        recon = self._floor_reconstruction
        if recon == "auto":
            recon = (
                "occupancy" if auto_should_use_occupancy(vertices) else "convex"
            )
        if recon in ("concave", "occupancy", "robust"):
            extractor = {
                "concave": floor_polygon_from_mesh,
                "occupancy": floor_polygon_from_mesh_occupancy,
                "robust": floor_polygon_robust,
            }[recon]
            try:
                floor_polygon_2d = extractor(vertices)
            except ValueError as exc:
                warnings.warn(
                    f"MeshAdapter: {recon} floor reconstruction failed "
                    f"({exc}); falling back to convex hull.",
                    UserWarning,
                    stacklevel=2,
                )
                floor_polygon_2d = self._convex_floor_polygon(vertices)
        else:
            floor_polygon_2d = self._convex_floor_polygon(vertices)

        # Surfaces: floor + ceiling polygons (Point3 lifts at the robust
        # floor_y / ceiling_y planes — keeps the box geometry self-consistent
        # with the reported robust height), walls from convex-hull edges.
        floor_material = MaterialLabel.WOOD_FLOOR
        floor_surface = Surface(
            kind="floor",
            polygon=[Point3(p.x, floor_y, p.z) for p in floor_polygon_2d],
            material=floor_material,
            absorption_500hz=MaterialAbsorption[floor_material],
            absorption_bands=MaterialAbsorptionBands[floor_material] if octave_band else None,
        )
        ceiling_material = MaterialLabel.CEILING_DRYWALL
        ceiling_surface = Surface(
            kind="ceiling",
            polygon=[
                Point3(p.x, ceiling_y, p.z) for p in reversed(floor_polygon_2d)
            ],
            material=ceiling_material,
            absorption_500hz=MaterialAbsorption[ceiling_material],
            absorption_bands=MaterialAbsorptionBands[ceiling_material] if octave_band else None,
        )

        walls = walls_from_floor_polygon(
            floor_polygon_2d,
            ceiling_height_m,
            default_material=MaterialLabel.WALL_PAINTED,
            octave_band=octave_band,
        )

        surfaces: list[Surface] = [floor_surface, ceiling_surface, *walls]

        listener = default_listener_area(floor_polygon_2d)

        return RoomModel(
            name=name,
            floor_polygon=floor_polygon_2d,
            ceiling_height_m=ceiling_height_m,
            surfaces=surfaces,
            listener_area=listener,
            objects=[],  # v0.17: no auto-detection (OQ-33); use evolve_room_add_object()
            schema_version="0.2-draft",
            provenance="measured",  # OQ-54: derived from a real scan mesh
            ceiling_coverage=ceiling_coverage,
            ceiling_confidence=ceiling_confidence,
        )
