"""Speaker placement engine — VBAP / DBAP / WFS dispatch."""

from __future__ import annotations

from roomestim.place.algorithm import TargetAlgorithm
from roomestim.place.ambisonics import AMBISONICS_RIG_DISCLOSURE, place_ambisonics
from roomestim.place.coverage_grid import (
    COVERAGE_GRID_NOTE,
    CoverageGridResult,
    coverage_result_to_placement,
    coverage_to_dict,
    format_coverage_lines,
    place_coverage_grid,
    place_coverage_grid_for_room,
)
from roomestim.place.dbap import place_dbap
from roomestim.place.vbap import place_vbap_dome, place_vbap_ring
from roomestim.place.wfs import place_wfs

__all__ = [
    "AMBISONICS_RIG_DISCLOSURE",
    "COVERAGE_GRID_NOTE",
    "CoverageGridResult",
    "TargetAlgorithm",
    "coverage_result_to_placement",
    "coverage_to_dict",
    "format_coverage_lines",
    "place_ambisonics",
    "place_coverage_grid",
    "place_coverage_grid_for_room",
    "place_vbap_ring",
    "place_vbap_dome",
    "place_dbap",
    "place_wfs",
]
