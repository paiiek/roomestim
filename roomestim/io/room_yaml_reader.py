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
    ListenerArea,
    MaterialAbsorption,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
)


def _proto_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "proto"


def _schema_path(schema_version: str) -> Path:
    if schema_version == "0.1-draft":
        return _proto_dir() / "room_schema.draft.json"
    if schema_version == "0.1":
        return _proto_dir() / "room_schema.json"
    raise ValueError(f"unknown schema_version: {schema_version!r}")


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

    return RoomModel(
        name=name,
        floor_polygon=floor_polygon,
        ceiling_height_m=ceiling_height_m,
        surfaces=surfaces,
        listener_area=listener_area,
        schema_version=schema_version,
    )


__all__ = ["read_room_yaml"]
