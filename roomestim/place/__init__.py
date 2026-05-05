"""Speaker placement engine — VBAP / DBAP / WFS / Ambisonics dispatch."""

from __future__ import annotations

from roomestim.place.algorithm import TargetAlgorithm
from roomestim.place.ambisonics import place_ambisonics
from roomestim.place.dbap import place_dbap
from roomestim.place.vbap import place_vbap_dome, place_vbap_ring
from roomestim.place.wfs import place_wfs

__all__ = [
    "TargetAlgorithm",
    "place_vbap_ring",
    "place_vbap_dome",
    "place_dbap",
    "place_wfs",
    "place_ambisonics",
]
