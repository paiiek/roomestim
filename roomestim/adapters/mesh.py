"""MeshAdapter — generic mesh-file input for room estimation.

Accepts ``.obj``, ``.gltf``, ``.glb``, and ``.ply`` mesh files.
``.usdz`` raises :exc:`NotImplementedError` (requires the optional ``usd``
extra; not part of the default-CI smoke surface).

Geometry: convex hull of XY-projected vertices by default; an opt-in concave
reconstruction (``floor_reconstruction="concave"`` or the
``ROOMESTIM_MESH_FLOOR_RECON`` env override) recovers non-shoebox footprints
via :func:`roomestim.reconstruct.floor_polygon.floor_polygon_from_mesh`.
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
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
    canonicalize_ccw,
)
from roomestim.reconstruct.floor_polygon import floor_polygon_from_mesh
from roomestim.reconstruct.listener_area import default_listener_area
from roomestim.reconstruct.walls import walls_from_floor_polygon

__all__ = ["MeshAdapter"]

_SUPPORTED_SUFFIXES = frozenset({".obj", ".gltf", ".glb", ".ply"})

FloorReconstruction = Literal["convex", "concave"]

# Explicit up-axis override. ``"auto"`` (default) runs the gravity-axis
# detector; ``"x"`` / ``"y"`` / ``"z"`` force a known axis when the caller has
# gravity metadata (e.g. RoomPlan/ARKit transform). The model's internal frame
# is Y-up, so a non-Y override triggers the same normalization the detector
# uses.
UpAxis = Literal["auto", "x", "y", "z"]

_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}

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


class MeshAdapter:
    """``CaptureAdapter`` implementation for generic mesh exports.

    Supported formats: ``.obj``, ``.gltf``, ``.glb``, ``.ply``.
    Mesh must be metric-scale (metres). ``scale_anchor`` is ignored.

    Parameters
    ----------
    floor_reconstruction:
        ``"convex"`` (default) takes the convex hull of the floor-projected
        vertices — the legacy, byte-equal path. ``"concave"`` recovers a
        non-shoebox footprint via :func:`floor_polygon_from_mesh`, falling
        back to the convex hull (with a :class:`UserWarning`) when the
        concave reconstruction degenerates. When left at its sentinel
        default the ``ROOMESTIM_MESH_FLOOR_RECON`` environment variable
        selects the mode; an explicit argument always wins over the env var.
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
        if explicit is not None:
            if explicit not in ("convex", "concave"):
                raise ValueError(
                    f"MeshAdapter: floor_reconstruction must be 'convex' or "
                    f"'concave', got {explicit!r}."
                )
            return explicit
        env_value = os.environ.get(_FLOOR_RECON_ENV)
        if env_value is None:
            return "convex"
        normalized = env_value.strip().lower()
        if normalized not in ("convex", "concave"):
            raise ValueError(
                f"MeshAdapter: {_FLOOR_RECON_ENV}={env_value!r} is invalid; "
                f"expected 'convex' or 'concave'."
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
        if suffix == ".usdz":
            raise NotImplementedError(
                "MeshAdapter: USDZ requires [usd] extra; use .obj/.gltf/.glb/.ply"
            )
        if suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError(
                f"MeshAdapter: unsupported extension {suffix!r}; "
                f"expected one of {sorted(_SUPPORTED_SUFFIXES)}."
            )
        # ADR 0038: bound file size BEFORE trimesh reads the bytes. Guards both
        # the CLI and the web upload path against a DoS-sized mesh.
        file_bytes = path_obj.stat().st_size
        if file_bytes > _MAX_MESH_FILE_BYTES:
            raise ValueError(
                f"MeshAdapter: mesh file is {file_bytes} bytes, exceeding the "
                f"{_MAX_MESH_FILE_BYTES}-byte cap (set ROOMESTIM_MAX_MESH_BYTES "
                f"to raise it)."
            )
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

        # ADR 0038: bound vertex count (ordering: shape → vertex-count → faces).
        # A file under the byte cap can still expand to a pathological vertex
        # count after parsing; cap it before the O(N) hull projection below.
        if vertices.shape[0] > _MAX_MESH_VERTICES:
            raise ValueError(
                f"MeshAdapter: mesh has {vertices.shape[0]} vertices, exceeding "
                f"the {_MAX_MESH_VERTICES}-vertex cap (set "
                f"ROOMESTIM_MAX_MESH_VERTICES to raise it)."
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

        # P0 (commercialization plan 0a): real gravity-aligned scans
        # (ARKitScenes, RoomPlan, many .ply/.obj exports) are commonly Z-up, not
        # the Y-up convention of the synthetic fixtures and glTF. Detect the up
        # (gravity) axis, then normalize the mesh into the model's Y-up frame so
        # all downstream extraction keys on the correct vertical axis. Without
        # this, a horizontal room dimension is mistaken for ceiling height
        # (observed 6.5–9.6 m on real ARKit rooms that are ≈2.4–3 m).
        if self._up_axis == "auto":
            up_axis = self._detect_up_axis(vertices)
        else:
            up_axis = _AXIS_INDEX[self._up_axis]
        vertices = self._normalize_to_y_up(vertices, up_axis)

        y_min = float(vertices[:, 1].min())
        y_max = float(vertices[:, 1].max())
        ceiling_height_m = float(y_max - y_min)
        if ceiling_height_m <= 0.0:
            raise ValueError(
                f"MeshAdapter: degenerate mesh height "
                f"(y_max={y_max}, y_min={y_min})"
            )

        # Reconstruct the floor footprint. ``convex`` (default) takes the
        # convex hull of the floor-projected vertices — the byte-equal legacy
        # path. ``concave`` recovers re-entrant corners (non-shoebox rooms) and
        # falls back to convex on degeneracy.
        if self._floor_reconstruction == "concave":
            try:
                floor_polygon_2d = floor_polygon_from_mesh(vertices)
            except ValueError as exc:
                warnings.warn(
                    f"MeshAdapter: concave floor reconstruction failed "
                    f"({exc}); falling back to convex hull.",
                    UserWarning,
                    stacklevel=2,
                )
                floor_polygon_2d = self._convex_floor_polygon(vertices)
        else:
            floor_polygon_2d = self._convex_floor_polygon(vertices)

        # Surfaces: floor + ceiling polygons (Point3 lifts at y_min / y_max),
        # walls from convex-hull edges.
        floor_material = MaterialLabel.WOOD_FLOOR
        floor_surface = Surface(
            kind="floor",
            polygon=[Point3(p.x, y_min, p.z) for p in floor_polygon_2d],
            material=floor_material,
            absorption_500hz=MaterialAbsorption[floor_material],
            absorption_bands=MaterialAbsorptionBands[floor_material] if octave_band else None,
        )
        ceiling_material = MaterialLabel.CEILING_DRYWALL
        ceiling_surface = Surface(
            kind="ceiling",
            polygon=[
                Point3(p.x, y_max, p.z) for p in reversed(floor_polygon_2d)
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

        name = path.stem

        # ``cast`` keeps mypy strict happy where trimesh attribute access
        # returns ``Any`` — we only use ``vertices`` numerically above.
        _ = cast(Any, loaded)

        return RoomModel(
            name=name,
            floor_polygon=floor_polygon_2d,
            ceiling_height_m=ceiling_height_m,
            surfaces=surfaces,
            listener_area=listener,
            objects=[],  # v0.17: no auto-detection (OQ-33); use evolve_room_add_object()
            schema_version="0.2-draft",
            provenance="measured",  # OQ-54: derived from a real scan mesh
        )
