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
from typing import Any, Literal, cast

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
    """

    def __init__(
        self,
        *,
        floor_reconstruction: FloorReconstruction | None = None,
    ) -> None:
        self._floor_reconstruction = self._resolve_floor_reconstruction(
            floor_reconstruction
        )

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
        )
