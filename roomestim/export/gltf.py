"""gLTF / GLB export for RoomModel + PlacementResult (v0.17 — ADR 0035).

§Purpose
    Round-trip a :class:`~roomestim.model.RoomModel` (with optional
    :class:`~roomestim.model.PlacementResult`) to a gLTF or GLB file
    suitable for opening in Blender, three.js, model-viewer, etc.

§Backend
    Uses ``trimesh``, which is already a core runtime dependency. No extra
    install step is required.

§Layering
    Pure write path — no acoustic computation here. Column geometry is
    derived from
    :func:`roomestim.reconstruct.predictor._objects_to_surfaces` so the
    visual scene matches the predictor's view of object surfaces.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import trimesh

from roomestim.model import (
    MaterialAbsorption,
    MaterialAbsorptionBands,
    PlacementResult,
    Point3,
    RoomModel,
)

__all__ = ["write_gltf"]


# --------------------------------------------------------------------------- #
# Color palette mirror (RGBA 0..1; see usd.py rationale).
# --------------------------------------------------------------------------- #


_MATERIAL_BASECOLOR_RGB: dict[str, tuple[float, float, float]] = {
    "wall_painted":           (0.910, 0.866, 0.827),
    "wall_concrete":          (0.612, 0.612, 0.612),
    "wood_floor":             (0.627, 0.322, 0.176),
    "carpet":                 (0.545, 0.451, 0.333),
    "glass":                  (0.659, 0.847, 0.918),
    "ceiling_acoustic_tile":  (0.961, 0.961, 0.863),
    "ceiling_drywall":        (0.941, 0.941, 0.941),
    "unknown":                (0.753, 0.753, 0.753),
    "misc_soft":              (0.482, 0.408, 0.651),
    "melamine_foam":          (1.000, 0.702, 0.278),
}


def _rgba(material: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    r, g, b = _MATERIAL_BASECOLOR_RGB.get(material, (0.6, 0.6, 0.6))
    return (r, g, b, alpha)


# --------------------------------------------------------------------------- #
# Polygon → Trimesh helpers
# --------------------------------------------------------------------------- #


def _polygon_to_mesh(polygon: list[Point3], color_rgba: tuple[float, float, float, float]) -> trimesh.Trimesh:
    """Triangulate a planar polygon with a fan from vertex[0].

    The fan triangulation preserves the polygon's vertex ordering (CCW or
    CW) so face normals continue to point in the same direction as the
    source polygon's winding.
    """
    n = len(polygon)
    if n < 3:
        # Degenerate; return an empty mesh.
        return trimesh.Trimesh()
    vertices = np.asarray(
        [[p.x, p.y, p.z] for p in polygon], dtype=np.float64
    )
    faces = np.asarray(
        [[0, i, i + 1] for i in range(1, n - 1)], dtype=np.int64
    )
    rgba255 = tuple(int(round(c * 255)) for c in color_rgba)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    cast(Any, mesh.visual).face_colors = np.tile(rgba255, (len(faces), 1))
    return mesh


def _marker_mesh(position: Point3, radius_m: float, color_rgba: tuple[float, float, float, float]) -> trimesh.Trimesh:
    """Small icosphere marker for listener / speakers."""
    sphere = cast(trimesh.Trimesh, trimesh.creation.icosphere(subdivisions=2, radius=radius_m))
    sphere.apply_translation([position.x, position.y, position.z])
    rgba255 = tuple(int(round(c * 255)) for c in color_rgba)
    cast(Any, sphere.visual).face_colors = np.tile(rgba255, (len(sphere.faces), 1))
    return sphere


# --------------------------------------------------------------------------- #
# Scene builder
# --------------------------------------------------------------------------- #


def _room_to_trimesh_scene(
    room: RoomModel,
    placement: PlacementResult | None,
) -> trimesh.Scene:
    """Build a :class:`trimesh.Scene` from ``room`` + optional ``placement``."""
    scene = trimesh.Scene()

    # Surfaces
    for i, surf in enumerate(room.surfaces):
        mesh = _polygon_to_mesh(surf.polygon, _rgba(surf.material.value))
        if len(mesh.vertices) == 0:
            continue
        scene.add_geometry(mesh, node_name=f"Surface_{i}", geom_name=f"Surface_{i}")

    # Objects
    if room.objects:
        try:
            from roomestim.reconstruct.predictor import _objects_to_surfaces

            column_surfaces = _objects_to_surfaces(list(room.objects))
        except Exception:
            column_surfaces = []
        column_cursor = 0
        for obj_idx, obj in enumerate(room.objects):
            if obj.kind == "column":
                for face_i in range(5):
                    if column_cursor >= len(column_surfaces):
                        break
                    cs = column_surfaces[column_cursor]
                    column_cursor += 1
                    cmesh = _polygon_to_mesh(cs.polygon, _rgba(cs.material.value))
                    if len(cmesh.vertices) == 0:
                        continue
                    scene.add_geometry(
                        cmesh,
                        node_name=f"Object_{obj_idx}_Face_{face_i}",
                        geom_name=f"Object_{obj_idx}_Face_{face_i}",
                    )
            else:
                a = obj.anchor
                hw = obj.width_m / 2.0
                hh = obj.height_m
                quad = [
                    Point3(a.x - hw, a.y, a.z),
                    Point3(a.x + hw, a.y, a.z),
                    Point3(a.x + hw, a.y + hh, a.z),
                    Point3(a.x - hw, a.y + hh, a.z),
                ]
                # Semi-transparent for window; opaque for door.
                alpha = 0.3 if obj.kind == "window" else 1.0
                qmesh = _polygon_to_mesh(quad, _rgba(obj.material.value, alpha))
                if len(qmesh.vertices) == 0:
                    continue
                scene.add_geometry(
                    qmesh,
                    node_name=f"Object_{obj_idx}",
                    geom_name=f"Object_{obj_idx}",
                )

    # Listener + Speakers
    if placement is not None:
        centroid_2d = room.listener_area.centroid
        listener_pt = Point3(
            centroid_2d.x, room.listener_area.height_m, centroid_2d.z
        )
        listener_mesh = _marker_mesh(
            listener_pt, radius_m=0.15, color_rgba=(0.2, 0.2, 0.9, 1.0)
        )
        scene.add_geometry(listener_mesh, node_name="Listener", geom_name="Listener")
        for sp in placement.speakers:
            speaker_mesh = _marker_mesh(
                sp.position, radius_m=0.10, color_rgba=(0.9, 0.2, 0.2, 1.0)
            )
            scene.add_geometry(
                speaker_mesh,
                node_name=f"Speaker_Channel_{int(sp.channel)}",
                geom_name=f"Speaker_Channel_{int(sp.channel)}",
            )

    return scene


# --------------------------------------------------------------------------- #
# Acoustic sidecar
# --------------------------------------------------------------------------- #


def _build_acoustics_sidecar(room: RoomModel) -> dict[str, Any]:
    """Per-surface + per-object acoustic metadata for ``.acoustics.json``."""
    surfaces_out: list[dict[str, Any]] = []
    for i, surf in enumerate(room.surfaces):
        bands = surf.absorption_bands or MaterialAbsorptionBands[surf.material]
        surfaces_out.append(
            {
                "surface_idx": i,
                "kind": surf.kind,
                "material": surf.material.value,
                "absorption_500hz": float(surf.absorption_500hz),
                "absorption_bands_125_250_500_1000_2000_4000": [
                    float(b) for b in bands
                ],
            }
        )
    objects_out: list[dict[str, Any]] = []
    for i, obj in enumerate(room.objects):
        bands = MaterialAbsorptionBands[obj.material]
        objects_out.append(
            {
                "object_idx": i,
                "kind": obj.kind,
                "material": obj.material.value,
                "absorption_500hz": float(MaterialAbsorption[obj.material]),
                "absorption_bands_125_250_500_1000_2000_4000": [
                    float(b) for b in bands
                ],
                "width_m": float(obj.width_m),
                "height_m": float(obj.height_m),
                "depth_m": float(obj.depth_m),
                "wall_index": obj.wall_index,
            }
        )
    return {
        "version": "0.17",
        "room_name": room.name,
        "schema_version": room.schema_version,
        "surfaces": surfaces_out,
        "objects": objects_out,
    }


def _write_acoustics_sidecar(room: RoomModel, out_path: Path) -> None:
    sidecar = out_path.with_suffix(out_path.suffix + ".acoustics.json")
    with sidecar.open("w", encoding="utf-8") as fh:
        json.dump(_build_acoustics_sidecar(room), fh, indent=2)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def write_gltf(
    room: RoomModel,
    placement: PlacementResult | None,
    out_path: Path | str,
    *,
    format: Literal["gltf", "glb"] = "glb",
    with_acoustics_sidecar: bool = False,
) -> None:
    """Write ``room`` + optional ``placement`` to ``out_path`` as a gLTF / GLB file.

    Parameters
    ----------
    room:
        Source room model.
    placement:
        Optional placement result; listener / speaker markers are skipped
        when ``None``.
    out_path:
        Destination file path. The caller is responsible for matching the
        extension (``.gltf`` or ``.glb``) to ``format``.
    format:
        ``"glb"`` produces a single binary file; ``"gltf"`` produces an
        ASCII JSON file with a ``.bin`` sidecar in the same directory.
    with_acoustics_sidecar:
        When True, additionally write ``<out_path>.acoustics.json`` with
        per-surface + per-object material absorption (500 Hz + 6-band).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    scene = _room_to_trimesh_scene(room, placement)
    if format == "glb":
        data = cast(bytes, cast(Any, scene).export(file_type="glb"))
        with out_path.open("wb") as fh:
            fh.write(data)
    else:
        gltf_payload: Any = cast(Any, scene).export(file_type="gltf")
        # trimesh.exchange.gltf.export_gltf returns a dict of filename → bytes
        # when called via scene.export(file_type="gltf").
        if isinstance(gltf_payload, dict):
            target_dir = out_path.parent
            for filename, content in gltf_payload.items():
                # Repath all assets next to ``out_path`` keeping their names
                # except for the principal .gltf file which uses out_path.
                if filename.endswith(".gltf"):
                    dest = out_path
                else:
                    dest = target_dir / filename
                if isinstance(content, (bytes, bytearray)):
                    with dest.open("wb") as fh:
                        fh.write(content)
                elif isinstance(content, str):
                    with dest.open("w", encoding="utf-8") as fh:
                        fh.write(content)
                else:
                    with dest.open("w", encoding="utf-8") as fh:
                        json.dump(content, fh)
        else:
            # Fallback path: trimesh returned raw bytes / str.
            if isinstance(gltf_payload, (bytes, bytearray)):
                with out_path.open("wb") as fh:
                    fh.write(gltf_payload)
            else:
                with out_path.open("w", encoding="utf-8") as fh:
                    fh.write(str(gltf_payload))

    if with_acoustics_sidecar:
        _write_acoustics_sidecar(room, out_path)
