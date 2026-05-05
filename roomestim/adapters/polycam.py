"""Polycam capture adapter — OBJ + MTL or USDZ mesh input.

For v0.1 default CI we exercise:

* ``.json`` — RoomPlan-format sidecar (test fixture); delegates to
  :class:`RoomPlanAdapter` for parsing. Same metric / parametric path.
* ``.obj``  — small synthetic mesh; loaded with :mod:`trimesh`, projected to
  the floor plane via ``y_min``, polygonized as the convex hull of projected
  vertices using :class:`shapely.geometry.MultiPoint`. Walls are generated
  per convex-hull edge by :func:`walls_from_floor_polygon`. Material defaults
  per :data:`MaterialLabel`.
* ``.usdz`` — raises ``NotImplementedError`` (requires the optional ``usd``
  extra; not part of the default-CI smoke surface).

Full alpha-shape reconstruction is deferred to v0.3 (decisions.md D6); the
P5 acceptance only requires "Polycam fixture produces a valid ``RoomModel``".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import trimesh
from shapely.geometry import MultiPoint
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.adapters.base import ScaleAnchor
from roomestim.adapters.roomplan import RoomPlanAdapter
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
from roomestim.reconstruct.listener_area import default_listener_area
from roomestim.reconstruct.walls import walls_from_floor_polygon

__all__ = ["PolycamAdapter"]


class PolycamAdapter:
    """``CaptureAdapter`` implementation for Polycam mesh exports.

    Polycam exports metric scale natively, so ``scale_anchor`` is ignored.
    """

    def parse(
        self,
        path: Path | str,
        *,
        scale_anchor: ScaleAnchor | None = None,
        octave_band: bool = False,
    ) -> RoomModel:
        del scale_anchor  # Polycam is metric-native; anchor unused
        path_obj = Path(path)
        suffix = path_obj.suffix.lower()
        if suffix == ".json":
            # RoomPlan-format sidecar — same parametric primitives.
            return RoomPlanAdapter().parse(path_obj, octave_band=octave_band)
        if suffix == ".obj":
            return self._room_model_from_obj(path_obj, octave_band=octave_band)
        if suffix == ".usdz":
            raise NotImplementedError(
                "Polycam USDZ requires [usd] extra; use .obj for default CI"
            )
        raise ValueError(
            f"PolycamAdapter: unsupported extension {suffix!r}; "
            "expected .obj (mesh), .json (RoomPlan-format sidecar), or .usdz."
        )

    def _room_model_from_obj(self, path: Path, *, octave_band: bool = False) -> RoomModel:
        loaded = trimesh.load(path, force="mesh")
        # ``force='mesh'`` coerces a Scene into a single Trimesh; vertices is
        # always an ndarray of shape (N, 3) at that point.
        vertices_attr = getattr(loaded, "vertices", None)
        if vertices_attr is None:
            raise ValueError(
                f"PolycamAdapter: trimesh.load({path!r}) returned no vertices"
            )
        vertices = np.asarray(vertices_attr, dtype=float)
        if vertices.ndim != 2 or vertices.shape[1] != 3:
            raise ValueError(
                f"PolycamAdapter: expected (N, 3) vertex array, got shape "
                f"{vertices.shape}"
            )

        y_min = float(vertices[:, 1].min())
        y_max = float(vertices[:, 1].max())
        ceiling_height_m = float(y_max - y_min)
        if ceiling_height_m <= 0.0:
            raise ValueError(
                f"PolycamAdapter: degenerate mesh height "
                f"(y_max={y_max}, y_min={y_min})"
            )

        # Project vertices to the (x, z) floor plane and take their convex
        # hull. v0.1 smoke geometry only — alpha-shape reconstruction is
        # deferred (decisions.md D6).
        xz_points = [(float(v[0]), float(v[2])) for v in vertices]
        hull = MultiPoint(xz_points).convex_hull
        if not isinstance(hull, ShapelyPolygon):
            raise ValueError(
                "PolycamAdapter: convex hull of projected vertices is not a "
                "polygon; the mesh appears degenerate (collinear or single-point)."
            )

        # Drop the duplicate closing vertex shapely returns on the exterior.
        exterior_coords = list(hull.exterior.coords)[:-1]
        floor_polygon_2d = canonicalize_ccw(
            [Point2(float(x), float(z)) for x, z in exterior_coords]
        )

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

        # Fall back to the file stem as the room name.
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
            schema_version="0.1-draft",
        )
