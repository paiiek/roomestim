"""roomestim geometry utilities (v0.15.1).

Shared core geometry helpers extracted from ``predictor.py`` and
``ace_challenge.py`` duplicates per LOW-1 follow-up (v0.15.1-patch §2 결정).
"""
from roomestim.geom.polygon import polygon_area_3d, room_volume, shoelace_2d

__all__ = ["polygon_area_3d", "room_volume", "shoelace_2d"]
