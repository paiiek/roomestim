"""Coordinate-frame helpers — Python port of spatial_engine/core/src/coords/Coords.h.

Single sign-flip authority for roomestim. ALL frame conversions live here and nowhere else.

Frames:
    Pipeline / vid2spatial-native:
        (az, el) in radians; az = atan2(x_listener, z_listener); RIGHT = +az.
        el = atan2(y, sqrt(x² + z²)); UP = +el. Listener frame.
    AmbiX / SOFA:
        (az, el) in radians; LEFT = +az; UP = +el.
        Conversion: pipeline_to_ambix(az, el) = (-az, el).
    VBAP layout-frame (engine):
        Cartesian XYZ in YAML; speaker (az_deg, el_deg) with RIGHT = +az,
        az measured from front in degrees.
    Image-y-down:
        Pixel y grows downward; el = arcsin(-y_image_normalized).

Parity is enforced against the C++ originals by tests/test_coords_engine_parity.py
(A15) when SPATIAL_ENGINE_BUILD_DIR is set; tests/test_coords_roundtrip.py (A4) is
the unconditional gate.
"""

from __future__ import annotations

import math


def pipeline_to_ambix(az_pipe: float, el_pipe: float) -> tuple[float, float]:
    """Pipeline (RIGHT=+az) -> AmbiX/SOFA (LEFT=+az). Only az flips."""
    return (-az_pipe, el_pipe)


def ambix_to_pipeline(az_ambix: float, el_ambix: float) -> tuple[float, float]:
    """AmbiX/SOFA (LEFT=+az) -> pipeline (RIGHT=+az). Only az flips."""
    return (-az_ambix, el_ambix)


def cartesian_to_pipeline(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Listener-frame Cartesian (x=right, y=up, z=front) -> pipeline (az, el, dist).

    az = atan2(x, z) — right of listener = +x = +az.
    el = atan2(y, sqrt(x²+z²)).
    dist = ||(x, y, z)||.
    """
    dist = math.sqrt(x * x + y * y + z * z)
    az = math.atan2(x, z)
    el = math.atan2(y, math.sqrt(x * x + z * z))
    return (az, el, dist)


def image_y_to_listener_el(y_image_normalized: float) -> float:
    """Image y-down convention -> listener elevation. Below-horizon (y > 0) -> negative el."""
    return math.asin(-y_image_normalized)


def yaml_speaker_to_cartesian(
    az_deg: float, el_deg: float, dist_m: float = 1.0
) -> tuple[float, float, float]:
    """YAML speaker spherical (RIGHT=+az_deg, UP=+el_deg) -> Cartesian XYZ.

    x = dist * cos(el) * sin(az)
    y = dist * sin(el)
    z = dist * cos(el) * cos(az)
    """
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    return (
        dist_m * math.cos(el) * math.sin(az),
        dist_m * math.sin(el),
        dist_m * math.cos(el) * math.cos(az),
    )


def stereo_pan_from_pipeline_az(az_pipe: float) -> float:
    """Stereo pan from pipeline az. RIGHT (+az) -> sin > 0 -> R louder.

    NEVER use sin(-az). The 2026-03-01 inversion bug was sin(-az). Locked here.
    """
    return math.sin(az_pipe)
