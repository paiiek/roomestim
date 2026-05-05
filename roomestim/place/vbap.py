"""VBAP-oriented placements — equal-angle ring (A5) and stacked dome (A6).

Both placements are deterministic and depend only on the speaker count and
geometric parameters (radius, elevation, ring spacing). They are independent of
room geometry by construction; the produced positions are listener-frame
Cartesian (x=right, y=up, z=front), assuming the listener is at the origin.

`regularity_hint` follows `spatial_engine/core/src/geometry/SpeakerLayout.h`:
single equal-angle rings are CIRCULAR; stacked rings are IRREGULAR (the dome
is not a single planar ring, so we down-grade conservatively per
`layout_yaml._min_speaker_count`).
"""

from __future__ import annotations

import math

from roomestim.coords import yaml_speaker_to_cartesian
from roomestim.model import (
    PlacedSpeaker,
    PlacementResult,
    Point3,
    kErrTooFewSpeakers,
)
from roomestim.place.algorithm import TargetAlgorithm


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _unit_aim_to_listener(position: Point3) -> Point3:
    """Return the unit vector from ``position`` toward the origin (listener).

    The listener is at the origin in the listener-frame, so the aim is
    ``-position / ||position||``. If the speaker is exactly at the origin
    (degenerate), return ``Point3(0, 0, -1)`` as a safe forward-pointing
    default — this should never happen in practice for ring/dome (radius>0).
    """
    norm = math.sqrt(position.x * position.x + position.y * position.y + position.z * position.z)
    if norm == 0.0:
        return Point3(0.0, 0.0, -1.0)
    return Point3(-position.x / norm, -position.y / norm, -position.z / norm)


def _equal_angle_ring(
    n: int,
    *,
    radius_m: float,
    el_deg: float,
    channel_offset: int,
    phase_offset_deg: float = 0.0,
) -> list[PlacedSpeaker]:
    """Build ``n`` speakers on an equal-angle ring at elevation ``el_deg``.

    Channels are ``channel_offset+1 .. channel_offset+n`` monotonically.
    Az angles are ``phase_offset_deg + i * 360°/n`` for ``i in range(n)``.
    Default ``phase_offset_deg=0.0`` reproduces v0.1 behaviour byte-for-byte.
    """
    speakers: list[PlacedSpeaker] = []
    for i in range(n):
        az_deg = phase_offset_deg + (i * 360.0) / n
        x, y, z = yaml_speaker_to_cartesian(az_deg, el_deg, radius_m)
        position = Point3(x=x, y=y, z=z)
        aim = _unit_aim_to_listener(position)
        speakers.append(
            PlacedSpeaker(
                channel=channel_offset + i + 1,
                position=position,
                aim_direction=aim,
            )
        )
    return speakers


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def place_vbap_ring(
    n: int,
    *,
    radius_m: float = 2.0,
    el_deg: float = 0.0,
    listener_pos: Point3 | None = None,
    layout_name: str = "vbap_ring",
    phase_offset_deg: float = 0.0,
) -> PlacementResult:
    """Equal-angle VBAP ring of ``n`` speakers (A5).

    Speakers are at angles ``phase_offset_deg + i * 360°/n`` (i=0..n-1) at
    constant elevation ``el_deg`` and radius ``radius_m``. Channels are
    ``1..n`` monotonic.

    Use ``phase_offset_deg = -135.0`` to match the spatial_engine
    ``lab_8ch_aligned`` lower-ring origin; default ``0.0`` reproduces v0.1
    behaviour byte-for-byte.

    Raises ``ValueError`` (`kErrTooFewSpeakers`) if ``n < 3`` (CIRCULAR
    minimum per `SpeakerLayout.h:38`).

    ``listener_pos`` is reserved for future support; v0.1 always places
    speakers around the origin (the engine's listener-frame origin).
    """
    if n < 3:
        raise ValueError(
            f"{kErrTooFewSpeakers}: VBAP ring requires n>=3, got {n}"
        )
    # listener_pos is informational only in v0.1; positions remain in
    # listener-frame around origin.
    _ = listener_pos
    speakers = _equal_angle_ring(
        n,
        radius_m=radius_m,
        el_deg=el_deg,
        channel_offset=0,
        phase_offset_deg=phase_offset_deg,
    )
    return PlacementResult(
        target_algorithm=TargetAlgorithm.VBAP.value,
        regularity_hint="CIRCULAR",
        speakers=speakers,
        layout_name=layout_name,
    )


def place_vbap_dome(
    *,
    n_lower: int,
    n_upper: int,
    el_lower_deg: float = 0.0,
    el_upper_deg: float = 30.0,
    radius_m: float = 2.0,
    layout_name: str = "vbap_dome",
    phase_offsets_deg: list[float] | None = None,
) -> PlacementResult:
    """Two stacked equal-angle rings — VBAP dome (A6).

    Lower ring has ``n_lower`` speakers at elevation ``el_lower_deg``.
    Upper ring has ``n_upper`` speakers at elevation ``el_upper_deg``.
    Channels: ``1..n_lower`` for lower ring, then ``n_lower+1 .. n_lower+n_upper``
    for upper ring.

    ``phase_offsets_deg`` is an optional length-2 list giving the phase
    offset (deg) for the lower and upper ring respectively. Default
    ``None`` is equivalent to ``[0.0, 0.0]`` and reproduces v0.1 behaviour
    byte-for-byte. The list-of-offsets shape generalises cleanly when v0.2
    adds an N-ring stack.

    To match the spatial_engine ``lab_8ch_aligned`` lab fixture
    (4×lower + 4×upper at -135° origin, radius 1.0 m, el ∈ {0°, 30°}), call::

        place_vbap_dome(
            n_lower=4, n_upper=4,
            el_lower_deg=0.0, el_upper_deg=30.0,
            radius_m=1.0,
            phase_offsets_deg=[-135.0, -135.0],
            layout_name="lab_8ch_aligned",
        )

    Note (cross-repo): the lab fixture annotates ``regularity_hint:
    CIRCULAR`` for this stacked-ring layout, while this function emits
    ``IRREGULAR`` (conservative downgrade per the module docstring). The
    engine's VBAP weighting (`SpeakerLayout.h:38`) selects different code
    paths on the two values, so position equality does NOT imply runtime
    behavioural equivalence. Reconciliation is v0.2 work.

    Raises ``ValueError`` (`kErrTooFewSpeakers`) if either ring has fewer
    than 3 speakers, or if ``phase_offsets_deg`` length is not 2.
    """
    if n_lower < 3:
        raise ValueError(
            f"{kErrTooFewSpeakers}: VBAP dome lower ring requires n_lower>=3, "
            f"got {n_lower}"
        )
    if n_upper < 3:
        raise ValueError(
            f"{kErrTooFewSpeakers}: VBAP dome upper ring requires n_upper>=3, "
            f"got {n_upper}"
        )

    if phase_offsets_deg is None:
        phase_offsets_deg = [0.0, 0.0]
    if len(phase_offsets_deg) != 2:
        raise ValueError(
            f"{kErrTooFewSpeakers}: phase_offsets_deg length "
            f"{len(phase_offsets_deg)} != ring count 2"
        )

    lower = _equal_angle_ring(
        n_lower,
        radius_m=radius_m,
        el_deg=el_lower_deg,
        channel_offset=0,
        phase_offset_deg=phase_offsets_deg[0],
    )
    upper = _equal_angle_ring(
        n_upper,
        radius_m=radius_m,
        el_deg=el_upper_deg,
        channel_offset=n_lower,
        phase_offset_deg=phase_offsets_deg[1],
    )
    speakers = [*lower, *upper]
    return PlacementResult(
        target_algorithm=TargetAlgorithm.VBAP.value,
        regularity_hint="IRREGULAR",
        speakers=speakers,
        layout_name=layout_name,
    )


__all__ = ["place_vbap_ring", "place_vbap_dome"]
