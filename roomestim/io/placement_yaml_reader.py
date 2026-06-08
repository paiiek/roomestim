"""Read a layout.yaml file back into a :class:`~roomestim.model.PlacementResult`.

Only round-trips what :func:`roomestim.export.layout_yaml.write_layout_yaml`
emits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from roomestim.io.room_yaml_reader import _parse_provenance
from roomestim.model import PlacedSpeaker, PlacementResult, Point3

#: Allowed placement-algorithm labels (OQ-38 / ADR 0041). Mirrors
#: :class:`roomestim.place.algorithm.TargetAlgorithm`. Used to validate the
#: ``x_target_algorithm`` extension key on read, mirroring the ``_parse_provenance``
#: guardrail.
_TARGET_ALGORITHM_VALUES: tuple[str, ...] = ("VBAP", "DBAP", "WFS", "AMBISONICS")


def _point3_from_speaker(d: dict[str, Any]) -> Point3:
    """Reconstruct Point3 from az/el/dist spherical form via coords."""
    from roomestim.coords import yaml_speaker_to_cartesian

    az_deg = float(d["az_deg"])
    el_deg = float(d["el_deg"])
    dist_m = float(d["dist_m"])
    x, y, z = yaml_speaker_to_cartesian(az_deg, el_deg, dist_m)
    return Point3(x=x, y=y, z=z)


def _aim_from_speaker(d: dict[str, Any]) -> Point3 | None:
    """Reconstruct ``aim_direction`` from ``x_aim_az_deg`` / ``x_aim_el_deg``.

    Aim carries direction only; the magnitude is irrelevant (the writer's
    ``cartesian_to_pipeline`` discards it). Reconstruct as a unit vector so
    write→read→write is a stable fixed point (D50). Absent keys → ``None``
    (backward-compat with pre-v0.18 layouts).

    Partial-key policy (D50 / Fix 7a): when exactly one of the two keys is
    present the aim cannot be reconstructed from a single axis, so return
    ``None`` (treat-as-missing). Both keys are required for restoration.
    """
    if "x_aim_az_deg" not in d or "x_aim_el_deg" not in d:
        return None
    from roomestim.coords import yaml_speaker_to_cartesian

    ax_deg = float(d["x_aim_az_deg"])
    ael_deg = float(d["x_aim_el_deg"])
    x, y, z = yaml_speaker_to_cartesian(ax_deg, ael_deg, 1.0)
    return Point3(x=x, y=y, z=z)


def read_placement_yaml(path: Path | str) -> PlacementResult:
    """Load a ``layout.yaml`` produced by :func:`write_layout_yaml` into a
    :class:`PlacementResult`.

    Raises
    ------
    ValueError
        If the YAML is malformed or required keys are missing.
    """
    path = Path(path)
    # FIX-3 / D76: yaml.YAMLError is not a ValueError subclass and a missing
    # required key raises KeyError; both escaped the CLI handler as a raw
    # traceback. Wrap to honor the documented ValueError contract.
    try:
        with path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ValueError(f"layout '{path}': invalid YAML — {exc}") from exc

    # Guard: empty file → None; top-level list → list. data["name"] would raise
    # TypeError (not ValueError/KeyError), escaping the CLI handler as a traceback.
    if not isinstance(data, dict):
        raise ValueError(
            f"layout '{path}': expected a YAML mapping, got {type(data).__name__}"
        )

    try:
        layout_name = str(data["name"])
        layout_version = str(data.get("version", "1.0"))
        regularity_hint = str(data["regularity_hint"])

        # target_algorithm: restore-first, infer-fallback (OQ-38 / ADR 0041 PR1).
        # When x_target_algorithm is present (written for every non-VBAP layout),
        # restore the label directly so DBAP/WFS/AMBISONICS no longer collapse to
        # "VBAP". Validate against the known enum (raise ValueError on an
        # out-of-enum value, mirroring the _parse_provenance guardrail); the call
        # stays inside this try/except to honor the module's ValueError contract.
        # When the key is absent (pre-v0.32 / VBAP layouts) fall back to the
        # existing inference for backward compatibility.
        wfs_f_alias_hz: float | None = None
        if "x_wfs_f_alias_hz" in data:
            wfs_f_alias_hz = float(data["x_wfs_f_alias_hz"])
        if "x_target_algorithm" in data:
            target_algorithm = str(data["x_target_algorithm"])
            if target_algorithm not in _TARGET_ALGORITHM_VALUES:
                raise ValueError(
                    f"layout '{path}': invalid x_target_algorithm "
                    f"{target_algorithm!r} (expected one of "
                    f"{sorted(_TARGET_ALGORITHM_VALUES)})"
                )
        elif "x_wfs_f_alias_hz" in data:
            target_algorithm = "WFS"
        elif regularity_hint == "LINEAR":
            target_algorithm = "WFS"
        else:
            target_algorithm = "VBAP"

        speakers: list[PlacedSpeaker] = []
        for sp in data["speakers"]:
            position = _point3_from_speaker(sp)
            speakers.append(
                PlacedSpeaker(
                    channel=int(sp["channel"]),
                    position=position,
                    aim_direction=_aim_from_speaker(sp),
                )
            )

        # OQ-54 / ADR 0046: geometry capture provenance. Absent key → "assumed"
        # (least-claim, matches room reader default). Validated via the shared
        # _parse_provenance (imported at module top — no circular import:
        # room_yaml_reader does not import placement_yaml_reader) so an
        # out-of-enum value raises ValueError consistently. The validation call
        # stays inside this try/except to honor the module's ValueError contract.
        geometry_provenance = _parse_provenance(
            str(data.get("x_geometry_provenance", "assumed")), name=str(path)
        )
    except KeyError as exc:
        raise ValueError(
            f"layout '{path}': missing required key {exc}"
        ) from exc

    return PlacementResult(
        target_algorithm=target_algorithm,
        regularity_hint=regularity_hint,
        speakers=speakers,
        layout_name=layout_name,
        layout_version=layout_version,
        wfs_f_alias_hz=wfs_f_alias_hz,
        geometry_provenance=geometry_provenance,
    )


__all__ = ["read_placement_yaml"]
