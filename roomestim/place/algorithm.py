"""Placement algorithm enum — mirror of spatial_engine's rendering algorithm set.

See `spatial_engine/require.md` §2 (object-based + WFS/VBAP/DBAP mandatory) and
`SpeakerLayout.h::Regularity`. Ambisonics is deferred to v0.3 but listed for
forward compatibility.
"""

from __future__ import annotations

from enum import Enum


class TargetAlgorithm(str, Enum):
    """Spatial-rendering algorithm a placement is intended for."""

    VBAP = "VBAP"
    DBAP = "DBAP"
    WFS = "WFS"
    AMBISONICS = "AMBISONICS"
    #: B1 — room-aware AVIXA-style distributed-ceiling coverage grid (geometric
    #: only, NO acoustic/SPL claim; see ``roomestim.place.coverage_grid``).
    COVERAGE_GRID = "COVERAGE_GRID"
    #: P7 — obstacle-aware DBAP coverage (walls+ceiling, obstacle/line-of-sight
    #: candidate rejection; geometric heuristic, NO SPL claim; see
    #: ``roomestim.place.obstacle_aware`` / ``OBSTACLE_AWARE_PLACEMENT_NOTE``).
    COVERAGE_AVOID = "COVERAGE_AVOID"
    #: P7 — obstacle-aware format placement (canonical format angles nudged by
    #: the smallest angular offset that clears obstacles; geometric heuristic,
    #: NO SPL claim; see ``roomestim.place.obstacle_aware.place_format_avoid`` /
    #: ``OBSTACLE_AWARE_PLACEMENT_NOTE``).
    FORMAT_AVOID = "FORMAT_AVOID"
