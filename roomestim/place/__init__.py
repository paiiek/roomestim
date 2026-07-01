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
from roomestim.place.formats import (
    FORMAT_CATALOG,
    FormatChannel,
    ImmersiveFormat,
    get_format,
    list_format_ids,
)
from roomestim.place.obstacle_aware import (
    OBSTACLE_AWARE_PLACEMENT_NOTE,
    place_coverage_avoid,
    place_format_avoid,
)
from roomestim.place.vbap import place_vbap_dome, place_vbap_ring
from roomestim.place.wfs import place_wfs

__all__ = [
    "AMBISONICS_RIG_DISCLOSURE",
    "COVERAGE_GRID_NOTE",
    "FORMAT_CATALOG",
    "OBSTACLE_AWARE_PLACEMENT_NOTE",
    "CoverageGridResult",
    "FormatChannel",
    "ImmersiveFormat",
    "TargetAlgorithm",
    "coverage_result_to_placement",
    "coverage_to_dict",
    "format_coverage_lines",
    "get_format",
    "list_format_ids",
    "place_ambisonics",
    "place_coverage_avoid",
    "place_coverage_grid",
    "place_coverage_grid_for_room",
    "place_format_avoid",
    "place_vbap_ring",
    "place_vbap_dome",
    "place_dbap",
    "place_wfs",
]
