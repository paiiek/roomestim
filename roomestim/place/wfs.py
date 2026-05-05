"""WFS linear-array placement (A8) — equally-spaced speakers along a wall baseline.

Wave Field Synthesis requires the speaker spacing ``Delta_x`` to satisfy the
spatial-aliasing bound ``Delta_x <= c / (2 f_max)`` (see Spors & Rabenstein 2006,
"Spatial Aliasing Artifacts of Wave Field Synthesis for the Reproduction of
Virtual Point Sources").  Speed of sound is fixed at ``c = 343.0 m/s``.

The aliasing frequency for the chosen spacing,
``f_alias = c / (2 * spacing)``, is computed and stashed on
:attr:`PlacementResult.wfs_f_alias_hz`; ``layout_yaml.write_layout_yaml``
re-emits it as the top-level extension key ``x_wfs_f_alias_hz`` per design §6.1.

Speakers lie on the floor-plane baseline segment ``baseline_p0 -> baseline_p1``
at height ``height_m``; channels are 1..n monotonic; the default per-speaker
``aim_direction`` points from each speaker toward the listener-area centroid
``(0, 0, 0)`` — the same convention as VBAP/DBAP placements.
"""

from __future__ import annotations

import math

from roomestim.model import (
    PlacedSpeaker,
    PlacementResult,
    Point2,
    Point3,
)
from roomestim.place.algorithm import TargetAlgorithm


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

c: float = 343.0  # speed of sound, m/s


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _coerce_point2(p: Point2 | tuple[float, float]) -> Point2:
    """Accept either a :class:`Point2` or a 2-tuple ``(x, z)``."""
    if isinstance(p, Point2):
        return p
    if isinstance(p, tuple) and len(p) == 2:
        return Point2(float(p[0]), float(p[1]))
    raise TypeError(
        f"baseline endpoints must be Point2 or (x, z) tuple, got {type(p).__name__}"
    )


def _aim_to_origin(position: Point3) -> Point3:
    """Unit vector from ``position`` toward the origin (listener centroid)."""
    norm = math.sqrt(
        position.x * position.x + position.y * position.y + position.z * position.z
    )
    if norm == 0.0:
        return Point3(0.0, 0.0, -1.0)
    return Point3(-position.x / norm, -position.y / norm, -position.z / norm)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def place_wfs(
    *,
    baseline_p0: Point2 | tuple[float, float],
    baseline_p1: Point2 | tuple[float, float],
    spacing_m: float,
    f_max_hz: float,
    height_m: float = 1.20,
    layout_name: str = "wfs_array",
) -> PlacementResult:
    """WFS linear-array placement along a wall baseline (A8).

    Parameters
    ----------
    baseline_p0, baseline_p1:
        Endpoints of the wall baseline on the floor plane (``(x, z)`` metres).
        Speakers are placed at ``height_m`` along the segment from ``p0`` to
        ``p1`` at uniform ``spacing_m`` increments.
    spacing_m:
        Per-speaker spacing in metres. Must satisfy
        ``spacing_m <= c / (2 * f_max_hz)`` (lambda/2 anti-aliasing bound).
    f_max_hz:
        Highest reproduction frequency (Hz). Used to bound the spacing.
    height_m:
        Mounting height of the linear array (m). Default 1.20 m.
    layout_name:
        Layout name carried to the YAML.

    Returns
    -------
    :class:`PlacementResult`
        ``target_algorithm == "WFS"``, ``regularity_hint == "LINEAR"``,
        with ``wfs_f_alias_hz = c / (2 * spacing_m)`` populated.
    """
    if spacing_m <= 0.0:
        raise ValueError(f"spacing_m must be > 0, got {spacing_m}")
    if f_max_hz <= 0.0:
        raise ValueError(f"f_max_hz must be > 0, got {f_max_hz}")

    bound: float = c / (2.0 * f_max_hz)
    if spacing_m > bound:
        raise ValueError(
            f"kErrWfsSpacingTooLarge: spacing_m={spacing_m} > "
            f"c/(2*f_max)={bound}"
        )

    p0 = _coerce_point2(baseline_p0)
    p1 = _coerce_point2(baseline_p1)

    dx = p1.x - p0.x
    dz = p1.z - p0.z
    seg_len = math.sqrt(dx * dx + dz * dz)
    if seg_len == 0.0:
        raise ValueError("baseline_p0 and baseline_p1 are coincident")

    tx = dx / seg_len
    tz = dz / seg_len

    # Tolerant floor of seg_len / spacing_m: bare ``//`` is bit-exact and bites
    # us when seg_len is an exact integer multiple of spacing_m but not
    # representable in IEEE-754 (e.g. 5.0 / 0.10 == 49.99999... // -> 49).
    ratio = seg_len / spacing_m
    n_intervals = int(math.floor(ratio + 1e-9))
    n_speakers = max(2, n_intervals + 1)

    speakers: list[PlacedSpeaker] = []
    for i in range(n_speakers):
        s_along = float(i) * spacing_m
        x = p0.x + s_along * tx
        z = p0.z + s_along * tz
        position = Point3(x=float(x), y=float(height_m), z=float(z))
        speakers.append(
            PlacedSpeaker(
                channel=i + 1,
                position=position,
                aim_direction=_aim_to_origin(position),
            )
        )

    f_alias: float = c / (2.0 * spacing_m)

    return PlacementResult(
        target_algorithm=TargetAlgorithm.WFS.value,
        regularity_hint="LINEAR",
        speakers=speakers,
        layout_name=layout_name,
        wfs_f_alias_hz=f_alias,
    )


__all__ = ["place_wfs", "c"]
