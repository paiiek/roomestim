"""Read a room.yaml file back into a :class:`~roomestim.model.RoomModel`.

Only round-trips what :func:`roomestim.export.room_yaml.write_room_yaml`
emits — no extra keys required.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from roomestim.model import (
    DEFAULT_OBJECT_MATERIAL,
    ListenerArea,
    MaterialAbsorption,
    MaterialLabel,
    Object,
    ObjectKind,
    Point2,
    Point3,
    RoomModel,
    Surface,
    wall_surfaces,
)


def _proto_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "proto"


def _schema_path(schema_version: str) -> Path:
    if schema_version == "0.1-draft":
        return _proto_dir() / "room_schema.draft.json"
    if schema_version == "0.1":
        return _proto_dir() / "room_schema.json"
    if schema_version == "0.2-draft":
        return _proto_dir() / "room_schema.v0_2.draft.json"
    raise ValueError(
        f"Unsupported schema_version: {schema_version!r} "
        f"(supported: '0.1-draft', '0.1', '0.2-draft')"
    )


def _load_schema(schema_version: str) -> dict[str, Any]:
    path = _schema_path(schema_version)
    with path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def _point2(d: dict[str, float]) -> Point2:
    return Point2(x=float(d["x"]), z=float(d["z"]))


def _point3(d: dict[str, float]) -> Point3:
    return Point3(x=float(d["x"]), y=float(d["y"]), z=float(d["z"]))


def _surface(d: dict[str, Any]) -> Surface:
    kind = str(d["kind"])
    if kind not in ("wall", "floor", "ceiling"):
        raise ValueError(f"unknown surface kind: {kind!r}")
    material = MaterialLabel(d["material"])
    absorption_500hz = float(d.get("absorption_500hz", MaterialAbsorption[material]))
    polygon = [_point3(v) for v in d["polygon"]]

    absorption_bands: tuple[float, float, float, float, float, float] | None = None
    ab_raw = d.get("absorption")
    if ab_raw is not None:
        absorption_bands = (
            float(ab_raw["a125"]),
            float(ab_raw["a250"]),
            float(ab_raw["a500"]),
            float(ab_raw["a1000"]),
            float(ab_raw["a2000"]),
            float(ab_raw["a4000"]),
        )
        a500_from_block = absorption_bands[2]
        if abs(a500_from_block - absorption_500hz) >= 1e-6:
            warnings.warn(
                f"Surface absorption.a500 ({a500_from_block}) differs from "
                f"absorption_500hz ({absorption_500hz}) by >= 1e-6; "
                "using absorption.a500 as the more specific value.",
                stacklevel=2,
            )
            absorption_500hz = a500_from_block

    return Surface(
        kind=kind,  # type: ignore[arg-type]
        polygon=polygon,
        material=material,
        absorption_500hz=absorption_500hz,
        absorption_bands=absorption_bands,
    )


def _parse_object(d: dict[str, Any]) -> Object:
    """Parse a single object dict (column/door/window) into :class:`Object`."""
    kind_str = str(d["kind"])
    if kind_str not in ("column", "door", "window"):
        raise ValueError(f"Invalid object kind: {kind_str!r}")
    kind: ObjectKind = kind_str  # type: ignore[assignment]
    anchor = _point3(d["anchor"])
    default_material = DEFAULT_OBJECT_MATERIAL[kind].value
    material = MaterialLabel(d.get("material", default_material))
    wall_index_raw = d.get("wall_index")
    wall_index = int(wall_index_raw) if wall_index_raw is not None else None
    return Object(
        kind=kind,
        anchor=anchor,
        width_m=float(d["width_m"]),
        height_m=float(d["height_m"]),
        depth_m=float(d.get("depth_m", 0.0)),
        wall_index=wall_index,
        material=material,
    )


def read_room_yaml(path: Path | str) -> RoomModel:
    """Load a ``room.yaml`` produced by :func:`write_room_yaml` into a
    :class:`RoomModel`.

    Validates against the matching JSON schema (Stage 1 draft) before
    constructing the model.

    Raises
    ------
    ValueError
        If the YAML does not conform to the schema or contains unknown values.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)

    schema_version: str = str(data.get("version", "0.1-draft"))
    schema = _load_schema(schema_version)
    Draft202012Validator(schema).validate(data)

    name = str(data["name"])
    ceiling_height_m = float(data["ceiling_height_m"])
    floor_polygon = [_point2(p) for p in data["floor_polygon"]]

    la_raw: dict[str, Any] = data["listener_area"]
    listener_area = ListenerArea(
        polygon=[_point2(p) for p in la_raw["polygon"]],
        centroid=_point2(la_raw["centroid"]),
        height_m=float(la_raw.get("height_m", 1.20)),
    )

    surfaces = [_surface(s) for s in data.get("surfaces", [])]

    # D44: objects[] is schema-versioned. 0.1-draft / 0.1 → empty list (backward
    # parse — pre-v0.17 YAMLs have no obstacle data). 0.2-draft → parse list.
    objects: list[Object]
    if schema_version in ("0.1-draft", "0.1"):
        objects = []
    elif schema_version == "0.2-draft":
        objects = [_parse_object(o) for o in data.get("objects", [])]
    else:
        # Defensive: _schema_path already rejects unknown versions, but keep
        # this branch in sync with the supported set.
        raise ValueError(
            f"Unsupported schema_version: {schema_version!r} "
            f"(supported: '0.1-draft', '0.1', '0.2-draft')"
        )

    room = RoomModel(
        name=name,
        floor_polygon=floor_polygon,
        ceiling_height_m=ceiling_height_m,
        surfaces=surfaces,
        listener_area=listener_area,
        objects=objects,
        schema_version=schema_version,
    )

    # OQ-44(b) / D69: bound each door/window's wall_index against the walls-only
    # frame (the frame Object.wall_index resolves in — see ADR 0037 + D68).
    # An out-of-range index would otherwise silently downgrade the whole-room
    # RT60 to Eyring at predict time; reject it here at load instead.
    n_walls = len(wall_surfaces(room))
    for obj in room.objects:
        if obj.kind in ("door", "window") and obj.wall_index is not None:
            if not (0 <= obj.wall_index < n_walls):
                raise ValueError(
                    f"object wall_index={obj.wall_index} out of range "
                    f"[0, {n_walls}); room '{room.name}' has {n_walls} walls."
                )

    return room


__all__ = ["read_room_yaml"]
