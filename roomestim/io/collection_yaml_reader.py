"""Read a collection.yaml manifest back into a :class:`RoomCollection`.

Validates the manifest against ``collection_schema.v0_1.draft.json``, then
resolves each ``room_ref`` / ``layout_ref`` RELATIVE to the manifest's own
directory and loads the referenced single-room artifacts via the EXISTING
readers (:func:`read_room_yaml`, :func:`read_placement_yaml`). No single-room
code path is touched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from roomestim.collection import Offset, RoomCollection
from roomestim.io.placement_yaml_reader import read_placement_yaml
from roomestim.io.room_yaml_reader import read_room_yaml
from roomestim.model import PlacementResult


def _proto_dir() -> Path:
    """Resolve the in-package ``roomestim/proto/`` directory (ADR 0007).

    ``__file__`` is at ``<...>/roomestim/io/collection_yaml_reader.py`` so
    ``parents[1]`` is the ``roomestim/`` package root.
    """
    return Path(__file__).resolve().parents[1] / "proto"


def _load_schema() -> dict[str, Any]:
    with (_proto_dir() / "collection_schema.v0_1.draft.json").open(
        "r", encoding="utf-8"
    ) as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def _resolve_ref(ref: str, *, manifest_dir: Path, name: str) -> Path:
    """Resolve a manifest ref against ``manifest_dir``; reject absolute paths."""
    if Path(ref).is_absolute():
        raise ValueError(
            f"collection '{name}': ref must be relative to the manifest "
            f"directory, got absolute path: {ref!r}"
        )
    return manifest_dir / ref


def read_collection_yaml(path: Path | str) -> RoomCollection:
    """Load a ``collection.yaml`` manifest into a :class:`RoomCollection`.

    Validates against ``collection_schema.v0_1.draft.json`` then loads each
    referenced ``room.yaml`` (and ``layout.yaml`` when present) via the existing
    single-room readers. Refs are resolved relative to the manifest's directory.

    Raises
    ------
    ValueError
        If the YAML is malformed, fails schema validation, or carries an
        absolute ref.
    """
    path = Path(path)
    manifest_dir = path.parent
    try:
        with path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ValueError(f"collection '{path}': invalid YAML — {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"collection '{path}': expected a YAML mapping, got {type(data).__name__}"
        )

    try:
        Draft202012Validator(_load_schema()).validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"collection '{path}': schema validation failed — {exc.message}"
        ) from exc

    name = str(data["name"])
    rooms = []
    placements: list[PlacementResult | None] = []
    offsets: list[Offset | None] = []
    for entry in data["rooms"]:
        room_path = _resolve_ref(
            str(entry["room_ref"]), manifest_dir=manifest_dir, name=name
        )
        rooms.append(read_room_yaml(room_path))
        layout_ref = entry.get("layout_ref")
        if layout_ref is None:
            placements.append(None)
        else:
            layout_path = _resolve_ref(
                str(layout_ref), manifest_dir=manifest_dir, name=name
            )
            placements.append(read_placement_yaml(layout_path))
        offset = entry.get("offset")
        if offset is None:
            offsets.append(None)
        else:
            offsets.append((float(offset[0]), float(offset[1]), float(offset[2])))

    return RoomCollection(
        name=name, rooms=rooms, placements=placements, offsets=offsets
    )


__all__ = ["read_collection_yaml"]
