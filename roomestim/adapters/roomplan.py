"""Apple RoomPlan capture adapter (sidecar JSON path for v0.1 default CI).

The RoomPlan SDK exports two artifacts for any captured room:

1. A ``.usdz`` parametric scene (Apple toolchain only — requires macOS to
   author; v0.1 leaves USDZ ingest as ``NotImplementedError``).
2. A JSON sidecar describing the same parametric primitives in plain
   coordinates. This adapter ships the sidecar path because it is the only
   Linux-CI-buildable option (decisions.md D9, ralplan-iter1-resolutions
   fix 4).

The sidecar schema we accept is intentionally small:

.. code-block:: json

   {
     "version": "1.0",
     "category": "room",
     "label": "...",
     "dimensions": {"width": 5.0, "depth": 4.0, "height": 2.85},
     "walls":   [{"transform": [[..4..],[..4..],[..4..],[..4..]],
                  "dimensions": [w, h, 0.0],
                  "material_hint": "painted"}],
     "floors":  [{"polygon": [[x, y, z], ...], "material_hint": "wood"}],
     "ceilings":[{"polygon": [[x, y, z], ...], "material_hint": "acoustic_tile"}]
   }

Wall transforms follow Apple's column-vector convention: ``transform[i][3]``
is the wall origin and the first column ``transform[i][0]`` is the local
X axis (wall width direction) expressed in listener-frame world coordinates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

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
from roomestim.reconstruct.listener_area import default_listener_area

__all__ = ["RoomPlanAdapter"]


# Hint-string -> closed material enum. Unknown hints fall back to UNKNOWN
# (decisions.md D3).
_MATERIAL_HINT_MAP: dict[str, MaterialLabel] = {
    "painted": MaterialLabel.WALL_PAINTED,
    "concrete": MaterialLabel.WALL_CONCRETE,
    "wood": MaterialLabel.WOOD_FLOOR,
    "carpet": MaterialLabel.CARPET,
    "glass": MaterialLabel.GLASS,
    "acoustic_tile": MaterialLabel.CEILING_ACOUSTIC_TILE,
    "drywall": MaterialLabel.CEILING_DRYWALL,
}


def _material_for_hint(hint: str | None) -> MaterialLabel:
    if hint is None:
        return MaterialLabel.UNKNOWN
    return _MATERIAL_HINT_MAP.get(hint, MaterialLabel.UNKNOWN)


def _wall_polygon_from_transform(
    transform_4x4: list[list[float]],
    width_m: float,
    height_m: float,
) -> list[Point3]:
    """Build a CCW vertical rectangle for a RoomPlan wall.

    The wall origin is taken from the 4th column of the 4x4 transform; the
    in-plane width direction is the 1st column (local X axis). The rectangle
    spans ``+- width_m / 2`` in that direction at floor level
    (``y = origin_y - height_m / 2``) and at ceiling level
    (``y = origin_y + height_m / 2``).
    """
    transform = np.asarray(transform_4x4, dtype=float)
    if transform.shape != (4, 4):
        raise ValueError(
            f"RoomPlan wall transform must be 4x4; got shape {transform.shape}"
        )
    origin = transform[:3, 3]
    width_dir = transform[:3, 0]
    norm = float(np.linalg.norm(width_dir))
    if norm == 0.0:
        raise ValueError("RoomPlan wall transform has zero-length width axis")
    width_dir = width_dir / norm

    half_w = width_m / 2.0
    half_h = height_m / 2.0

    p0_floor = origin + (-half_w) * width_dir
    p1_floor = origin + (+half_w) * width_dir
    floor_y = float(origin[1] - half_h)
    ceiling_y = float(origin[1] + half_h)

    return [
        Point3(float(p0_floor[0]), floor_y, float(p0_floor[2])),
        Point3(float(p1_floor[0]), floor_y, float(p1_floor[2])),
        Point3(float(p1_floor[0]), ceiling_y, float(p1_floor[2])),
        Point3(float(p0_floor[0]), ceiling_y, float(p0_floor[2])),
    ]


def _polygon_3d(points_xyz: list[list[float]]) -> list[Point3]:
    return [
        Point3(float(p[0]), float(p[1]), float(p[2])) for p in points_xyz
    ]


def _project_to_floor_polygon(points_xyz: list[list[float]]) -> list[Point2]:
    return [Point2(float(p[0]), float(p[2])) for p in points_xyz]


class RoomPlanAdapter:
    """``CaptureAdapter`` implementation for Apple RoomPlan output.

    v0.1 default-CI path: read a JSON sidecar mock (``.json``). The
    parametric ``.usdz`` path is reserved for v0.1 manual / v0.2.

    RoomPlan emits metric scale natively, so ``scale_anchor`` is ignored.
    """

    def parse(
        self,
        path: Path | str,
        *,
        scale_anchor: ScaleAnchor | None = None,
        octave_band: bool = False,
    ) -> RoomModel:
        del scale_anchor  # RoomPlan is metric-native; anchor unused
        path_obj = Path(path)
        suffix = path_obj.suffix.lower()
        if suffix == ".usdz":
            raise NotImplementedError(
                "RoomPlanAdapter: USDZ parametric path requires the [usd] "
                "extra and macOS-authored fixture; use the JSON sidecar mock "
                "for v0.1 CI."
            )
        if suffix != ".json":
            raise ValueError(
                f"RoomPlanAdapter: unsupported extension {suffix!r}; "
                "expected .json (sidecar) or .usdz (parametric)."
            )
        with path_obj.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
        return self._room_model_from_sidecar(data, octave_band=octave_band)

    def _room_model_from_sidecar(self, data: dict[str, Any], *, octave_band: bool = False) -> RoomModel:
        name = str(data.get("label", "roomplan_room"))
        dimensions = data.get("dimensions", {})
        ceiling_height_m = float(dimensions.get("height", 0.0))

        wall_entries: list[dict[str, Any]] = list(data.get("walls", []))
        floor_entries: list[dict[str, Any]] = list(data.get("floors", []))
        ceiling_entries: list[dict[str, Any]] = list(data.get("ceilings", []))

        if not floor_entries:
            raise ValueError(
                "RoomPlanAdapter sidecar has no floors[]; cannot build "
                "RoomModel.floor_polygon."
            )

        # ------------------------------------------------------------------ #
        # Walls
        # ------------------------------------------------------------------ #
        wall_surfaces: list[Surface] = []
        for entry in wall_entries:
            transform = entry["transform"]
            dims = entry.get("dimensions", [0.0, 0.0, 0.0])
            width_m = float(dims[0])
            height_m = (
                float(dims[1])
                if len(dims) > 1 and float(dims[1]) > 0.0
                else ceiling_height_m
            )
            material = _material_for_hint(entry.get("material_hint"))
            polygon = _wall_polygon_from_transform(transform, width_m, height_m)
            wall_surfaces.append(
                Surface(
                    kind="wall",
                    polygon=polygon,
                    material=material,
                    absorption_500hz=MaterialAbsorption[material],
                    absorption_bands=MaterialAbsorptionBands[material] if octave_band else None,
                )
            )

        # ------------------------------------------------------------------ #
        # Floors
        # ------------------------------------------------------------------ #
        floor_entry = floor_entries[0]
        floor_polygon_xyz = list(floor_entry["polygon"])
        floor_material = _material_for_hint(floor_entry.get("material_hint"))
        floor_surface = Surface(
            kind="floor",
            polygon=_polygon_3d(floor_polygon_xyz),
            material=floor_material,
            absorption_500hz=MaterialAbsorption[floor_material],
            absorption_bands=MaterialAbsorptionBands[floor_material] if octave_band else None,
        )

        floor_polygon_2d = canonicalize_ccw(
            _project_to_floor_polygon(floor_polygon_xyz)
        )

        # ------------------------------------------------------------------ #
        # Ceilings
        # ------------------------------------------------------------------ #
        ceiling_surfaces: list[Surface] = []
        for entry in ceiling_entries:
            poly_xyz = list(entry["polygon"])
            ceiling_material = _material_for_hint(entry.get("material_hint"))
            ceiling_surfaces.append(
                Surface(
                    kind="ceiling",
                    polygon=_polygon_3d(poly_xyz),
                    material=ceiling_material,
                    absorption_500hz=MaterialAbsorption[ceiling_material],
                    absorption_bands=MaterialAbsorptionBands[ceiling_material] if octave_band else None,
                )
            )

        surfaces: list[Surface] = [floor_surface, *ceiling_surfaces, *wall_surfaces]

        # ------------------------------------------------------------------ #
        # Listener area (centroid of floor polygon, +- half_size square)
        # ------------------------------------------------------------------ #
        listener = default_listener_area(floor_polygon_2d)

        return RoomModel(
            name=name,
            floor_polygon=floor_polygon_2d,
            ceiling_height_m=ceiling_height_m,
            surfaces=surfaces,
            listener_area=listener,
            schema_version="0.1-draft",
        )
