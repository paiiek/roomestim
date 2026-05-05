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
