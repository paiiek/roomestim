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

D56 (v0.18.3): all emitted numeric degree/distance fields are normalized to 9
decimal places via ``_round9`` as the LAST step on every write — idempotent
fixed point, position error ≤ 1.7e-11 m (≪ D50 Level-1 ≤1e-9 contract).
See ADR 0036 §Status-update-v0.18.3.
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
    kErrEngineSchemaNotFound,
    kErrNonFiniteValue,
    kErrTooFewSpeakers,
)


# --------------------------------------------------------------------------- #
# Schema resolution — engine-side, never vendored
# --------------------------------------------------------------------------- #


def _engine_schema_path() -> Path | None:
    """Resolve geometry_schema.json from the ``SPATIAL_ENGINE_REPO_DIR`` env var.

    Precedence (ADR 0033 §B): ``SPATIAL_ENGINE_REPO_DIR`` env → (no default).
    There is intentionally NO machine-specific default path: the engine geometry
    schema lives in the external spatial_engine repository and is *read at write
    time, never vendored* (module docstring contract). When the env var is unset
    or empty this returns ``None`` — signalling "no usable schema location" — and
    the caller fails loud via :func:`_assert_schema_file_exists`. Engine
    validation is opt-in: ``--no-engine-validation`` skips it cleanly (ADR 0033
    §C), and ``--validate-engine`` overrides this env path via
    :func:`_resolve_schema_file` (the documented ``CLI > ENV > explicit-only``
    chain). The candidate is returned without an existence check so a misconfigured
    location is named in the :func:`_assert_schema_file_exists` error message.
    """
    repo_dir = os.environ.get("SPATIAL_ENGINE_REPO_DIR")
    if repo_dir:
        return Path(repo_dir) / "proto" / "geometry_schema.json"
    return None


def _assert_schema_file_exists(path: Path | None) -> Path:
    """Raise a descriptive :exc:`FileNotFoundError` when no schema resolves.

    Single source for the missing-engine-schema error (v0.20.0 / OQ-42). All
    three open sites (:func:`_load_engine_schema`, :func:`write_layout_yaml`,
    :func:`validate_placement`) route their resolved path through here, so the
    bare deep ``FileNotFoundError`` from ``path.open()`` is replaced by one
    actionable message naming all three escape hatches. ``path`` is ``None`` when
    neither ``SPATIAL_ENGINE_REPO_DIR`` nor ``--validate-engine`` is set (no
    machine-specific default exists by design); a non-``None`` ``path`` that is
    not a file means the configured location is wrong. The documented
    ``CLI > ENV > explicit-only`` chain (ADR 0033 §B) is retained.
    """
    if path is None or not path.is_file():
        where = (
            path
            if path is not None
            else "(neither SPATIAL_ENGINE_REPO_DIR nor --validate-engine set)"
        )
        raise FileNotFoundError(
            f"{kErrEngineSchemaNotFound}: engine geometry schema not found at "
            f"{where}. Set SPATIAL_ENGINE_REPO_DIR=<spatial_engine repo dir>, "
            f"pass --validate-engine <dir>, or use --no-engine-validation to "
            f"skip (ADR 0033)."
        )
    return path


def _load_engine_schema() -> dict[str, Any]:
    path = _assert_schema_file_exists(_engine_schema_path())
    with path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def _resolve_schema_file(schema_path_override: str | None) -> Path:
    """Single source for engine schema path resolution.

    De-duplicates the ``schema_path_override → <dir>/proto/geometry_schema.json``
    join previously inlined in :func:`write_layout_yaml` and now also needed by
    :func:`validate_placement` (third copy consolidation; v0.15.1 / v0.15.2
    geom-util precedent). Behaviour is identical to the prior inline join — same
    path returned — so writer output is byte-equal when the schema is present.

    v0.20.0 (OQ-42): the resolved path is checked via
    :func:`_assert_schema_file_exists`, so a genuinely-missing engine schema
    raises one descriptive :exc:`FileNotFoundError` (naming the env var,
    ``--validate-engine``, and ``--no-engine-validation``) instead of a bare
    deep ``FileNotFoundError`` from ``open()``. The ``CLI > ENV > default`` chain
    (ADR 0033 §B) is unchanged.
    """
    if schema_path_override is not None:
        candidate = Path(schema_path_override) / "proto" / "geometry_schema.json"
        return _assert_schema_file_exists(candidate)
    return _assert_schema_file_exists(_engine_schema_path())


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
# D56 — writer float normalization (v0.18.3, ADR 0036 §Status-update-v0.18.3)
# --------------------------------------------------------------------------- #


def _round9(x: float) -> float:
    """Normalize emitted numeric degree/distance field to 9 decimal places.

    Applied as the LAST step on every write so that place-write and edit-write
    traverse the same code path and produce byte-identical output (idempotent
    fixed point). ``round(-0.0, 9) == -0.0`` is preserved intentionally.
    Position error injected: ≤ 1.7e-11 m at dist ≤ 2 m — well within the D50
    Level-1 ≤1e-9 structural contract. Scheme: stdlib ``round`` (local,
    explicit, dep-free, deterministic). D56 / ADR 0036 §Status-update-v0.18.3.
    """
    return round(x, 9)


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
        "az_deg": _round9(math.degrees(az_rad)),      # D56 — normalize at emit
        "el_deg": _round9(math.degrees(el_rad)),      # D56
        "dist_m": _round9(dist_m),                    # D56
        "x_aim_az_deg": _round9(aim_az_deg),          # D56
        "x_aim_el_deg": _round9(aim_el_deg),          # D56
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
        out["x_wfs_f_alias_hz"] = _round9(float(result.wfs_f_alias_hz))  # D56
    # Top-level extension key — geometry capture provenance (OQ-54 / ADR 0046).
    # Emitted ONLY when non-default so every existing placement (defaults to
    # "assumed") stays byte-equal; reconstructed (rough-tier marker) and measured
    # (positive claim) are carried. Mirrors room.yaml's provenance-at-boundary
    # honesty. geometry_schema.json root additionalProperties:true → validates.
    if result.geometry_provenance != "assumed":
        out["x_geometry_provenance"] = result.geometry_provenance
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


def write_layout_yaml(
    result: PlacementResult,
    out_path: Path | str,
    *,
    validate: bool = True,
    schema_path_override: str | None = None,
) -> None:
    """Serialize ``result`` to ``out_path`` as a layout.yaml file.

    Order of operations (any failure aborts BEFORE any write):
      1. R10 pre-flight: ``len(speakers) >= min_speaker_count(regularity_hint)``.
      2. Build dict via :func:`placement_to_dict` (raises if WFS without
         ``wfs_f_alias_hz``).
      3. R11 finite-sweep over every numeric leaf.
      4. Validate against ``geometry_schema.json`` (Draft 2020-12) — skipped
         when ``validate=False`` (D42 / ADR 0033 §C: ``--no-engine-validation``).
         When skipped a ``# WARNING: schema validation skipped`` header comment
         is prepended to the YAML output for audit-trail purposes.
      5. ``yaml.safe_dump`` with ``sort_keys=False``.

    Parameters
    ----------
    result:
        Placement result to serialise.
    out_path:
        Destination file path.
    validate:
        When ``False``, skip engine schema validation (D42 opt-out). A
        ``# WARNING`` header comment is prepended to the output file so that
        downstream consumers are clearly notified. Default ``True`` preserves
        v0.15.2 backward-compatible behaviour.
    schema_path_override:
        Explicit path to the engine repo directory. When provided it overrides
        the ``SPATIAL_ENGINE_REPO_DIR`` env var (CLI > ENV; there is no
        machine-specific default — see :func:`_engine_schema_path`). Ignored when
        ``validate=False``.
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

    out_path = Path(out_path)

    if validate:
        # Step 4a — schema validation (default ON, backward-compat).
        schema_file = _resolve_schema_file(schema_path_override)
        with schema_file.open("r", encoding="utf-8") as fh:
            schema = json.load(fh)
        Draft202012Validator(schema).validate(data)

        # Step 5a — write without warning header.
        with out_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=False)
    else:
        # Step 4b — validation skipped (ADR 0033 §C opt-out).
        yaml_body = yaml.safe_dump(data, sort_keys=False)
        warning_header = (
            "# WARNING: schema validation skipped (--no-engine-validation)\n"
            "# This file has NOT been validated against the spatial_engine schema.\n"
            "# Use with caution; engine compatibility is the caller's responsibility.\n"
        )
        with out_path.open("w", encoding="utf-8") as fh:
            fh.write(warning_header)
            fh.write(yaml_body)


# --------------------------------------------------------------------------- #
# Non-raising validation collector (v0.18 — ADR 0036 §D; MED-1 safe design)
# --------------------------------------------------------------------------- #


def validate_placement(
    result: PlacementResult, *, schema_path_override: str | None = None
) -> list[str]:
    """Collect validation issues WITHOUT raising or writing a file.

    Independent re-check of R10 (``min_speaker_count``) + R11 (finite sweep) +
    the engine Draft 2020-12 schema. Does NOT call :func:`write_layout_yaml` and
    does NOT alter the writer's raise path — the writer keeps raising for safety;
    this collector exists only for CLI / web UX. An empty list means the
    placement is valid.

    Parameters
    ----------
    result:
        Placement result to validate.
    schema_path_override:
        Explicit path to the engine repo directory (resolved via
        :func:`_resolve_schema_file`).

    Returns
    -------
    list[str]
        Human-readable issue strings; ``[]`` when valid.
    """
    errors: list[str] = []
    try:
        min_n = _min_speaker_count(result.regularity_hint)
        if len(result.speakers) < min_n:
            errors.append(
                f"{kErrTooFewSpeakers}: needs >= {min_n}, got {len(result.speakers)}"
            )
    except ValueError as exc:
        errors.append(str(exc))
    try:
        data = placement_to_dict(result)
        _sweep_finite(data, path="")
        schema_file = _resolve_schema_file(schema_path_override)
        with schema_file.open("r", encoding="utf-8") as fh:
            schema = json.load(fh)
        Draft202012Validator(schema).validate(data)
    except Exception as exc:  # ValidationError/ValueError/OSError → string for UX
        errors.append(str(exc))
    return errors


__all__ = [
    "placement_to_dict",
    "write_layout_yaml",
    "validate_placement",
    "kErrNonFiniteValue",
    "kErrTooFewSpeakers",
    "kErrEngineSchemaNotFound",
]
