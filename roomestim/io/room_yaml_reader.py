"""Read a room.yaml file back into a :class:`~roomestim.model.RoomModel`.

Only round-trips what :func:`roomestim.export.room_yaml.write_room_yaml`
emits — no extra keys required.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any, get_args

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from roomestim.geom.polygon import is_simple_polygon
from roomestim.model import (
    DEFAULT_OBJECT_MATERIAL,
    CeilingConfidence,
    ListenerArea,
    MaterialAbsorption,
    MaterialLabel,
    Object,
    ObjectKind,
    Point2,
    Point3,
    Provenance,
    RoomModel,
    Surface,
    wall_surfaces,
)


#: Allowed room-level provenance values (OQ-54). Typed as the literal tuple so
#: a membership check narrows ``str`` to :data:`~roomestim.model.Provenance` for
#: mypy strict, with no ``cast`` / ``# type: ignore``.
_PROVENANCE_VALUES: tuple[Provenance, ...] = ("measured", "reconstructed", "assumed")


def _parse_provenance(value: str, *, name: str) -> Provenance:
    """Validate ``value`` is one of the three allowed provenance strings.

    The schema already enums this on 0.2-draft; the runtime check is defensive
    (and also covers callers that bypass schema validation). Returns a value
    typed as :data:`~roomestim.model.Provenance` via a narrowing comparison.
    """
    for allowed in _PROVENANCE_VALUES:
        if value == allowed:
            return allowed
    raise ValueError(f"room '{name}': invalid provenance {value!r}")


#: Allowed ceiling-confidence values (under-report guard). Typed as the literal
#: tuple so a membership check narrows ``str`` to
#: :data:`~roomestim.model.CeilingConfidence` for mypy strict (no ``cast``).
_CEILING_CONFIDENCE_VALUES: tuple[CeilingConfidence, ...] = ("high", "low", "unknown")


def _parse_ceiling_confidence(value: str, *, name: str) -> CeilingConfidence:
    """Validate ``value`` is one of the three allowed ceiling-confidence strings.

    The schema enums this on 0.2-draft; this runtime check is defensive (and
    covers callers that bypass schema validation). Returns a value typed as
    :data:`~roomestim.model.CeilingConfidence` via a narrowing comparison.
    """
    for allowed in _CEILING_CONFIDENCE_VALUES:
        if value == allowed:
            return allowed
    raise ValueError(f"room '{name}': invalid ceiling_confidence {value!r}")


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
    """Parse a single object dict (column/door/window/furniture) into :class:`Object`."""
    kind_str = str(d["kind"])
    if kind_str not in get_args(ObjectKind):
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
    # FIX-3 / D76: yaml.YAMLError and jsonschema.ValidationError are NOT
    # ValueError subclasses; without this wrap the documented "Raises ValueError"
    # contract was false and the CLI let a raw traceback escape on malformed
    # input. Catch both at the read boundary and re-raise as ValueError so the
    # docstring is true and main()'s handler maps them to `error: <msg>` exit 1.
    try:
        with path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ValueError(f"room '{path}': invalid YAML — {exc}") from exc

    # Guard: empty file parses to None; top-level list parses to list — neither
    # is a mapping, so data.get(...) would raise AttributeError (not ValueError)
    # and escape the CLI handler as a raw traceback. Reject explicitly here.
    if not isinstance(data, dict):
        raise ValueError(
            f"room '{path}': expected a YAML mapping, got {type(data).__name__}"
        )

    schema_version: str = str(data.get("version", "0.1-draft"))
    schema = _load_schema(schema_version)
    try:
        Draft202012Validator(schema).validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"room '{path}': schema validation failed — {exc.message}"
        ) from exc

    name = str(data["name"])
    ceiling_height_m = float(data["ceiling_height_m"])
    floor_polygon = [_point2(p) for p in data["floor_polygon"]]

    # FIX-5 / D78: reject self-intersecting (bow-tie) floor polygons. The
    # shoelace area magnitude returns a non-zero garbage volume for such rings
    # while shapely correctly reports area 0.0; a malformed floor would silently
    # poison every downstream area/volume/RT60 computation. Validate at the read
    # boundary instead (shapely is already a hard dependency).
    if not is_simple_polygon([(p.x, p.z) for p in floor_polygon]):
        raise ValueError(
            f"room '{name}': floor_polygon is self-intersecting or degenerate "
            "(not a simple polygon); self-intersecting floors are unsupported."
        )

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

    # OQ-54: room-level provenance. Emitted only on 0.2-draft; on 0.1 versions
    # data.get returns the "assumed" default (correct — provenance is unknown for
    # legacy/untagged geometry). Pre-provenance 0.2-draft files (no key) also
    # default to "assumed". Validated defensively even though the schema enums it.
    provenance = _parse_provenance(str(data.get("provenance", "assumed")), name=name)

    # Ceiling under-report guard (measured/mesh path). Both keys are OPTIONAL and
    # emitted by the writer only when coverage was measured, so an absent key
    # honestly means "not measured" → coverage None / confidence "unknown" (the
    # model defaults). ceiling_confidence is validated defensively even though the
    # schema enums it. ceiling_coverage is a plain optional float fraction.
    coverage_raw = data.get("ceiling_coverage")
    ceiling_coverage = float(coverage_raw) if coverage_raw is not None else None
    ceiling_confidence = _parse_ceiling_confidence(
        str(data.get("ceiling_confidence", "unknown")), name=name
    )
    # Couple the two fields on read: the writer emits ``ceiling_confidence`` ONLY
    # alongside a non-None ``ceiling_coverage`` (the measured/mesh path), so a
    # confidence WITHOUT coverage can only come from external hand-authoring. Drop
    # it to "unknown" here so reader and writer agree the fields are coupled and a
    # round-trip never silently mutates (the writer omits both when coverage is
    # None — without this, a hand-authored confidence would vanish on rewrite).
    if ceiling_coverage is None:
        ceiling_confidence = "unknown"

    room = RoomModel(
        name=name,
        floor_polygon=floor_polygon,
        ceiling_height_m=ceiling_height_m,
        surfaces=surfaces,
        listener_area=listener_area,
        objects=objects,
        schema_version=schema_version,
        provenance=provenance,
        ceiling_coverage=ceiling_coverage,
        ceiling_confidence=ceiling_confidence,
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
