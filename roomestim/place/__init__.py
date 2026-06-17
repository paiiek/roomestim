"""Speaker placement engine — VBAP / DBAP / WFS dispatch."""

from __future__ import annotations

from roomestim.place.algorithm import TargetAlgorithm
from roomestim.place.ambisonics import AMBISONICS_RIG_DISCLOSURE, place_ambisonics
from roomestim.place.dbap import place_dbap
from roomestim.place.vbap import place_vbap_dome, place_vbap_ring
from roomestim.place.wfs import place_wfs

__all__ = [
    "AMBISONICS_RIG_DISCLOSURE",
    "TargetAlgorithm",
    "place_ambisonics",
    "place_vbap_ring",
    "place_vbap_dome",
    "place_dbap",
    "place_wfs",
]
