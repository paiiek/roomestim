"""PlacementResult -> layout.yaml writer.

The shape mirrors ``spatial_engine/proto/geometry_schema.json`` (read at write
time, never copied). Top-level required keys: ``version``, ``name``,
``speakers``. Per-speaker required keys: ``id``, ``channel``. Spherical and
Cartesian per-speaker forms are mutually exclusive (the schema's ``not.anyOf``
clause forbids ``az_deg`` together with ``x`` / ``xyz``); roomestim emits the
spherical form only.

Extension keys (``additionalProperties: true`` at root and per-speaker per
``geometry_schema.json:8`` and the per-speaker block) per design §6.1 +
decisions.md D5:

* ``x_aim_az_deg`` / ``x_aim_el_deg`` — per-speaker aim direction in the same
  VBAP layout-frame as ``az_deg``. Default: vector from speaker → listener
  centroid (i.e., the negation of the speaker's position).
* ``x_wfs_f_alias_hz`` — top-level. Required when ``target_algorithm == "WFS"``;
  forbidden otherwise.

R10 pre-flight: enforce ``min_speaker_count`` per
``spatial_engine/core/src/geometry/SpeakerLayout.h:38`` (LINEAR≥2, CIRCULAR≥3,
PLANAR_GRID≥4, IRREGULAR≥1). R11 finite-sweep: every numeric leaf must satisfy
``math.isfinite``.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from roomestim.coords import cartesian_to_pipeline
from roomestim.model import (
    PlacedSpeaker,
    PlacementResult,
    assert_finite,
    kErrNonFiniteValue,
    kErrTooFewSpeakers,
)


# --------------------------------------------------------------------------- #
# Schema resolution — engine-side, never vendored
# --------------------------------------------------------------------------- #


_DEFAULT_ENGINE_SCHEMA_PATH: Path = Path(
    "/home/seung/mmhoa/spatial_engine/proto/geometry_schema.json"
)


def _engine_schema_path() -> Path:
    """Resolve geometry_schema.json. ``SPATIAL_ENGINE_REPO_DIR`` env var wins."""
    repo_dir = os.environ.get("SPATIAL_ENGINE_REPO_DIR")
    if repo_dir:
        candidate = Path(repo_dir) / "proto" / "geometry_schema.json"
        if candidate.is_file():
            return candidate
    return _DEFAULT_ENGINE_SCHEMA_PATH


def _load_engine_schema() -> dict[str, Any]:
    path = _engine_schema_path()
    with path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


# --------------------------------------------------------------------------- #
# min_speaker_count — mirror of SpeakerLayout.h:38
# --------------------------------------------------------------------------- #


_MIN_SPEAKERS_BY_REGULARITY: dict[str, int] = {
    "LINEAR": 2,
    "CIRCULAR": 3,
    "PLANAR_GRID": 4,
    "IRREGULAR": 1,
}


def _min_speaker_count(regularity_hint: str) -> int:
    if regularity_hint not in _MIN_SPEAKERS_BY_REGULARITY:
        raise ValueError(
            f"unknown regularity_hint: {regularity_hint!r} "
            f"(expected one of {sorted(_MIN_SPEAKERS_BY_REGULARITY)})"
        )
    return _MIN_SPEAKERS_BY_REGULARITY[regularity_hint]


# --------------------------------------------------------------------------- #
# Per-speaker dict construction
# --------------------------------------------------------------------------- #


def _aim_az_el_deg(speaker: PlacedSpeaker) -> tuple[float, float]:
    """Return (aim_az_deg, aim_el_deg) for ``speaker``.

    If ``speaker.aim_direction`` is None, default to the unit vector from the
    speaker toward the origin (the listener centroid in v0.1), i.e. the
    negation of ``speaker.position``. Convert via ``cartesian_to_pipeline`` and
    discard the magnitude.
    """
    if speaker.aim_direction is None:
        ax = -speaker.position.x
        ay = -speaker.position.y
        az = -speaker.position.z
    else:
        ax = speaker.aim_direction.x
        ay = speaker.aim_direction.y
        az = speaker.aim_direction.z
    az_rad, el_rad, _ = cartesian_to_pipeline(ax, ay, az)
    return (math.degrees(az_rad), math.degrees(el_rad))


def _placed_speaker_to_dict(speaker: PlacedSpeaker) -> dict[str, Any]:
    az_rad, el_rad, dist_m = cartesian_to_pipeline(
        speaker.position.x, speaker.position.y, speaker.position.z
    )
    aim_az_deg, aim_el_deg = _aim_az_el_deg(speaker)
    out: dict[str, Any] = {
        "id": int(speaker.channel),
        "channel": int(speaker.channel),
        "az_deg": math.degrees(az_rad),
        "el_deg": math.degrees(el_rad),
        "dist_m": dist_m,
        "x_aim_az_deg": aim_az_deg,
        "x_aim_el_deg": aim_el_deg,
    }
    return out


# --------------------------------------------------------------------------- #
# PlacementResult -> dict
# --------------------------------------------------------------------------- #


def placement_to_dict(
    result: PlacementResult, *, layout_name: str | None = None
) -> dict[str, Any]:
    """Return a YAML-serializable dict matching ``geometry_schema.json``.

    ``layout_name`` overrides ``result.layout_name`` when provided.
    """
    name = layout_name if layout_name is not None else result.layout_name
    out: dict[str, Any] = {
        "version": "1.0",
        "name": name,
        "regularity_hint": result.regularity_hint,
        "speakers": [_placed_speaker_to_dict(sp) for sp in result.speakers],
    }
    # Top-level extension key — only for WFS-produced layouts.
    if result.target_algorithm == "WFS":
        if result.wfs_f_alias_hz is None:
            raise ValueError(
                "x_wfs_f_alias_hz is required for WFS-produced layouts "
                "(see design §6.1, A8 item #4); got wfs_f_alias_hz=None"
            )
        out["x_wfs_f_alias_hz"] = float(result.wfs_f_alias_hz)
    return out


# --------------------------------------------------------------------------- #
# Finite sweep (R11)
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


def write_layout_yaml(result: PlacementResult, out_path: Path | str) -> None:
    """Serialize ``result`` to ``out_path`` as a layout.yaml file.

    Order of operations (any failure aborts BEFORE any write):
      1. R10 pre-flight: ``len(speakers) >= min_speaker_count(regularity_hint)``.
      2. Build dict via :func:`placement_to_dict` (raises if WFS without
         ``wfs_f_alias_hz``).
      3. R11 finite-sweep over every numeric leaf.
      4. Validate against ``geometry_schema.json`` (Draft 2020-12).
      5. ``yaml.safe_dump`` with ``sort_keys=False``.
    """
    # Step 1 — R10 pre-flight.
    min_n = _min_speaker_count(result.regularity_hint)
    if len(result.speakers) < min_n:
        raise ValueError(
            f"{kErrTooFewSpeakers}: regularity_hint={result.regularity_hint!r} "
            f"requires at least {min_n} speakers, got {len(result.speakers)}"
        )

    # Step 2 — build dict.
    data = placement_to_dict(result)

    # Step 3 — R11 finite-sweep BEFORE validation and BEFORE write.
    _sweep_finite(data, path="")

    # Step 4 — schema validation against the engine-side schema (read at write
    # time, never vendored).
    schema = _load_engine_schema()
    Draft202012Validator(schema).validate(data)

    # Step 5 — write.
    out_path = Path(out_path)
    with out_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


__all__ = [
    "placement_to_dict",
    "write_layout_yaml",
    "kErrNonFiniteValue",
    "kErrTooFewSpeakers",
]
