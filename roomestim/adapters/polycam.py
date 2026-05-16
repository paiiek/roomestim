"""Deprecated alias — ``PolycamAdapter`` is now :class:`MeshAdapter`.

This module is retained for v0.1-era callers. Scheduled for removal at v0.14
or later (decisions.md D33).
"""

from __future__ import annotations

import warnings
from pathlib import Path

from roomestim.adapters.base import ScaleAnchor
from roomestim.adapters.mesh import MeshAdapter
from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.model import RoomModel

__all__ = ["PolycamAdapter"]


class PolycamAdapter(MeshAdapter):
    """Deprecated alias for :class:`MeshAdapter`.

    Retained for v0.1-era callers; emits one ``DeprecationWarning`` on first
    ``.parse()`` call per location (Python's default ``simplefilter`` dedupes
    per ``__warningregistry__``). Scheduled for removal at v0.14 or later.

    Legacy behaviour preserved: ``.json`` (RoomPlan sidecar) is delegated to
    :class:`RoomPlanAdapter` as in v0.1.
    """

    def parse(
        self,
        path: Path | str,
        *,
        scale_anchor: ScaleAnchor | None = None,
        octave_band: bool = False,
    ) -> RoomModel:
        warnings.warn(
            "PolycamAdapter is deprecated; use roomestim.adapters.MeshAdapter",
            DeprecationWarning,
            stacklevel=2,
        )
        path_obj = Path(path)
        if path_obj.suffix.lower() == ".json":
            return RoomPlanAdapter().parse(path_obj, octave_band=octave_band)
        return super().parse(
            path_obj, scale_anchor=scale_anchor, octave_band=octave_band
        )
