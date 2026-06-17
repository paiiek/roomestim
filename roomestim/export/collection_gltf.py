"""Combined glTF / GLB export for a :class:`RoomCollection` (ADR 0049, Phase 2).

Builds ONE :class:`trimesh.Scene` by reusing the single-room scene builder
:func:`roomestim.export.gltf._room_to_trimesh_scene` per room and applying each
room's USER-SUPPLIED offset (from :attr:`RoomCollection.offsets`) as a pure
translation, then exports a single glTF/GLB file.

Honest scope (ADR 0049):
  * This is a **visual assembly** of N independent rooms at user-asserted
    offsets. roomestim NEVER infers inter-room registration. When a room has no
    offset (``None``) it is emitted at its own local origin — with no offsets at
    all the rooms overlap at the origin (documented, honest; not a bug).
  * There is NO geometry merge / footprint union / aggregate acoustics. Each
    room's geometry is kept as its own prefixed sub-tree.

The single-room writer :func:`roomestim.export.gltf.write_gltf` is NOT touched;
this module only CALLS ``_room_to_trimesh_scene`` and re-exports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import trimesh

from roomestim.collection import RoomCollection
from roomestim.export.gltf import _room_to_trimesh_scene

__all__ = ["build_combined_scene", "write_collection_gltf"]


def build_combined_scene(collection: RoomCollection) -> trimesh.Scene:
    """Assemble one :class:`trimesh.Scene` from ``collection`` honoring offsets.

    Each room's scene (built via the single-room ``_room_to_trimesh_scene``) is
    copied into the combined scene under a per-room node/geometry name prefix
    (``room{idx}__...``) and translated by its user-supplied offset. An absent
    offset (``None``) is the identity — the room stays at its local origin.
    """
    combined = trimesh.Scene()
    for idx, (room, placement, offset) in enumerate(
        zip(collection.rooms, collection.placements, collection.offsets)
    ):
        sub = _room_to_trimesh_scene(room, placement)
        if offset is None:
            translation = (0.0, 0.0, 0.0)
        else:
            translation = (float(offset[0]), float(offset[1]), float(offset[2]))
        shift = translation != (0.0, 0.0, 0.0)
        for node_name in sub.graph.nodes_geometry:
            node_transform, geom_name = sub.graph[node_name]
            mesh = sub.geometry[geom_name].copy()
            # Bake the sub-scene node transform (identity for the single-room
            # builder, but applied for robustness), then the user offset.
            mesh.apply_transform(node_transform)
            if shift:
                mesh.apply_translation(np.asarray(translation, dtype=np.float64))
            combined.add_geometry(
                mesh,
                node_name=f"room{idx}__{node_name}",
                geom_name=f"room{idx}__{geom_name}",
            )
    return combined


def write_collection_gltf(
    collection: RoomCollection,
    out_path: Path | str,
    *,
    format: Literal["gltf", "glb"] = "glb",
) -> None:
    """Write ``collection`` to ``out_path`` as ONE combined glTF / GLB file.

    Parameters
    ----------
    collection:
        The :class:`RoomCollection` to assemble. Each room's user-supplied
        offset (``collection.offsets[i]``) is applied as a translation; absent
        offsets keep the room at its local origin (rooms may overlap — honest,
        documented; roomestim never infers registration).
    out_path:
        Destination file path (caller matches the extension to ``format``).
    format:
        ``"glb"`` (single binary file) or ``"gltf"`` (ASCII JSON + ``.bin``).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    scene = build_combined_scene(collection)
    if format == "glb":
        data = cast(bytes, cast(Any, scene).export(file_type="glb"))
        with out_path.open("wb") as fh:
            fh.write(data)
        return

    gltf_payload: Any = cast(Any, scene).export(file_type="gltf")
    if isinstance(gltf_payload, dict):
        target_dir = out_path.parent
        for filename, content in gltf_payload.items():
            dest = out_path if filename.endswith(".gltf") else target_dir / filename
            if isinstance(content, (bytes, bytearray)):
                with dest.open("wb") as fh:
                    fh.write(content)
            elif isinstance(content, str):
                with dest.open("w", encoding="utf-8") as fh:
                    fh.write(content)
            else:
                with dest.open("w", encoding="utf-8") as fh:
                    json.dump(content, fh)
    elif isinstance(gltf_payload, (bytes, bytearray)):
        with out_path.open("wb") as fh:
            fh.write(gltf_payload)
    else:
        with out_path.open("w", encoding="utf-8") as fh:
            fh.write(str(gltf_payload))
