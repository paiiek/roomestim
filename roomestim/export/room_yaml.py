"""RoomModel -> room.yaml writer.

Validates against ``proto/room_schema.draft.json`` (Stage 1) by default and
``proto/room_schema.json`` (Stage 2 strict) when ``schema_version="0.1"``.
Every numeric leaf is checked with :func:`assert_finite` BEFORE writing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from roomestim.model import (
    Point2,
    Point3,
    RoomModel,
    Surface,
    assert_finite,
    kErrNonFiniteValue,
)


# --------------------------------------------------------------------------- #
# Schema resolution
# --------------------------------------------------------------------------- #


def _proto_dir() -> Path:
    """Resolve the repo-root ``proto/`` directory.

    The schema files live at the repo root (``/.../roomestim/proto/``), not
    inside the package. ``__file__`` is at
    ``<repo>/roomestim/export/room_yaml.py`` so ``parents[2]`` is the repo root.
    """
    return Path(__file__).resolve().parents[2] / "proto"


def _schema_path(schema_version: str) -> Path:
    if schema_version == "0.1-draft":
        return _proto_dir() / "room_schema.draft.json"
    if schema_version == "0.1":
        return _proto_dir() / "room_schema.json"
    raise ValueError(f"unknown schema_version: {schema_version}")


def _load_schema(schema_version: str) -> dict[str, Any]:
    path = _schema_path(schema_version)
    with path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


# --------------------------------------------------------------------------- #
# Dict serialization
# --------------------------------------------------------------------------- #


def _point2_to_dict(p: Point2) -> dict[str, float]:
    return {"x": p.x, "z": p.z}


def _point3_to_dict(p: Point3) -> dict[str, float]:
    return {"x": p.x, "y": p.y, "z": p.z}


def _surface_to_dict(s: Surface) -> dict[str, Any]:
    return {
        "kind": s.kind,
        "material": s.material.value,
        "absorption_500hz": s.absorption_500hz,
        "polygon": [_point3_to_dict(v) for v in s.polygon],
    }


def room_model_to_dict(room: RoomModel, *, schema_version: str = "0.1-draft") -> dict[str, Any]:
    """Return a YAML-serializable dict matching the room schema (Stage 1 by default).

    The ``schema_version`` argument selects the ``version`` field value
    (``"0.1-draft"`` or ``"0.1"``) but does not validate; that happens in
    :func:`write_room_yaml`.
    """
    if schema_version not in ("0.1-draft", "0.1"):
        raise ValueError(f"unknown schema_version: {schema_version}")

    out: dict[str, Any] = {
        "version": schema_version,
        "name": room.name,
        "ceiling_height_m": room.ceiling_height_m,
        "floor_polygon": [_point2_to_dict(p) for p in room.floor_polygon],
        "listener_area": {
            "centroid": _point2_to_dict(room.listener_area.centroid),
            "polygon": [_point2_to_dict(p) for p in room.listener_area.polygon],
            "height_m": room.listener_area.height_m,
        },
        "surfaces": [_surface_to_dict(s) for s in room.surfaces],
    }
    return out


# --------------------------------------------------------------------------- #
# Finite-sweep
# --------------------------------------------------------------------------- #


def _sweep_finite(node: Any, *, path: str) -> None:
    """Recursively assert every numeric leaf in ``node`` is finite."""
    if isinstance(node, bool):
        # bool is an int subclass in Python — skip explicitly.
        return
    if isinstance(node, (int, float)):
        assert_finite(float(node), field=path)
        return
    if isinstance(node, dict):
        for k, v in node.items():
            _sweep_finite(v, path=f"{path}.{k}" if path else str(k))
        return
    if isinstance(node, list):
        for i, v in enumerate(node):
            _sweep_finite(v, path=f"{path}[{i}]")
        return
    # str, None, etc. — non-numeric; skip.


# --------------------------------------------------------------------------- #
# Public writer
# --------------------------------------------------------------------------- #


def write_room_yaml(
    room: RoomModel,
    out_path: Path | str,
    *,
    schema_version: str = "0.1-draft",
) -> None:
    """Serialize ``room`` to ``out_path`` as YAML, validated against the schema.

    Order of operations:
      1. Build the dict via :func:`room_model_to_dict`.
      2. Sweep every numeric leaf with :func:`assert_finite`. Non-finite
         values raise ``ValueError(kErrNonFiniteValue: ...)`` BEFORE any write.
      3. Validate the dict against the selected JSON Schema variant.
      4. Write via ``yaml.safe_dump(..., sort_keys=False)``.
    """
    data = room_model_to_dict(room, schema_version=schema_version)

    # Step 2 — finite-sweep BEFORE schema validation and BEFORE write.
    _sweep_finite(data, path="")

    # Step 3 — schema validation.
    schema = _load_schema(schema_version)
    Draft202012Validator(schema).validate(data)

    # Step 4 — write.
    out_path = Path(out_path)
    with out_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


__all__ = [
    "room_model_to_dict",
    "write_room_yaml",
    "kErrNonFiniteValue",
]
