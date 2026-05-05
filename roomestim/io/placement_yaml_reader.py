"""Read a layout.yaml file back into a :class:`~roomestim.model.PlacementResult`.

Only round-trips what :func:`roomestim.export.layout_yaml.write_layout_yaml`
emits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from roomestim.model import PlacedSpeaker, PlacementResult, Point3


def _point3_from_speaker(d: dict[str, Any]) -> Point3:
    """Reconstruct Point3 from az/el/dist spherical form via coords."""
    from roomestim.coords import yaml_speaker_to_cartesian

    az_deg = float(d["az_deg"])
    el_deg = float(d["el_deg"])
    dist_m = float(d["dist_m"])
    x, y, z = yaml_speaker_to_cartesian(az_deg, el_deg, dist_m)
    return Point3(x=x, y=y, z=z)


def read_placement_yaml(path: Path | str) -> PlacementResult:
    """Load a ``layout.yaml`` produced by :func:`write_layout_yaml` into a
    :class:`PlacementResult`.

    Raises
    ------
    ValueError
        If required keys are missing.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)

    layout_name = str(data["name"])
    layout_version = str(data.get("version", "1.0"))
    regularity_hint = str(data["regularity_hint"])

    # Infer target_algorithm from regularity_hint (best-effort; not stored in YAML)
    # Use x_wfs_f_alias_hz presence as the WFS discriminator.
    wfs_f_alias_hz: float | None = None
    if "x_wfs_f_alias_hz" in data:
        wfs_f_alias_hz = float(data["x_wfs_f_alias_hz"])
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
            )
        )

    return PlacementResult(
        target_algorithm=target_algorithm,
        regularity_hint=regularity_hint,
        speakers=speakers,
        layout_name=layout_name,
        layout_version=layout_version,
        wfs_f_alias_hz=wfs_f_alias_hz,
    )


__all__ = ["read_placement_yaml"]
