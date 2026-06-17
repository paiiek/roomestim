"""Ambisonics rig placement — closed-form platonic-solid speaker rigs (PR2+PR3).

GEOMETRY-ONLY producer (ADR 0041 §D-3a point 2 carve-out). This module emits the
physical COORDINATES of a regular (platonic) speaker rig sized by the requested
Ambisonics decode ``order``. It does NOT perform spherical-harmonic (SH) encoding
or decoding, does NOT compute a decode matrix, and does NOT select a decoder type
— those are the engine's responsibility. The end-to-end contract that routes this
rig to the engine's Ambisonics decoder is UNCONFIRMED (ADR 0041 §D-3a point 1
gate is unmet). EXPERIMENTAL: see :data:`AMBISONICS_RIG_DISCLOSURE` (the single
source of truth surfaced on every CLI ambisonics invocation).

The rigs are exact closed-form platonic vertices (octahedron / icosahedron /
dodecahedron) normalized to the unit sphere, then scaled by ``radius_m``. Each
order satisfies the spherical-design lower bound ``n >= (N+1)**2``. These
specific solids are in fact high spherical designs (octahedron a 3-design,
icosahedron and dodecahedron 5-designs), so the SH decode up to order 3 is
well-conditioned. NOTE the in-repo test verifies only the **order-1 isotropy /
spherical-2-design necessary condition** (second-moment matrix ``= (1/3)I``
exactly) — a numpy-only proxy, NOT a full SH-matrix condition number for N>=2
(scipy renamed ``sph_harm`` -> ``sph_harm_y`` in 1.15+, making the SH path
version-fragile; the second-moment proxy is exact for these symmetric rigs and
adds no dependency). The higher-design property above is the substantive
guarantee of conditioning; the test pins the necessary order-1 moment.

Layering: core module, numpy-only (numpy is already a core dependency); no web /
torch / scipy coupling.
"""

from __future__ import annotations

import math

from roomestim.model import (
    PlacedSpeaker,
    PlacementResult,
    Point3,
    kErrTooFewSpeakers,
)
from roomestim.place.algorithm import TargetAlgorithm
from roomestim.place.vbap import _unit_aim_to_listener

# --------------------------------------------------------------------------- #
# Honest disclosure — single source of truth (reference, do not retype).
# Mirrors the POLYGON_ISM_GEOMETRY_NOTE pattern in reconstruct/_disclosure.py.
# --------------------------------------------------------------------------- #

AMBISONICS_RIG_DISCLOSURE: str = (
    "Ambisonics placement emits the physical coordinates of a regular (platonic) "
    "speaker RIG ONLY. roomestim does NOT perform SH encoding or decoding, does "
    "NOT compute the decode matrix, and does NOT select a decoder type — those "
    "are the engine's responsibility (/sys/ambi_order, /sys/ambi_decoder_type). "
    "EXPERIMENTAL: the engine-side contract that routes this rig to the "
    "Ambisonics decoder is UNCONFIRMED (ADR 0041 §D-3a point 1 gate is unmet — "
    "require.md does not mandate Ambisonics and there is no engine-team routing "
    "agreement). The rig is emitted as regularity_hint=IRREGULAR; an engine that "
    "branches IRREGULAR to VBAP-weighting would render these coordinates with the "
    "WRONG algorithm. End-to-end Ambisonics decoding is therefore NOT verified by "
    "roomestim. The COORDINATES themselves are exact closed-form platonic vertices."
)


# --------------------------------------------------------------------------- #
# Closed-form platonic vertex sets (NO external table) — see ADR 0041 / plan §2.
# φ = (1+√5)/2. Each raw vertex set has a single common norm, so we normalize to
# the unit sphere by dividing by that norm. Listener-frame (x=right, y=up,
# z=front). Verified: equal radii, centroid == origin, second-moment == (1/3)I.
# --------------------------------------------------------------------------- #

_PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
_INV_PHI: float = 1.0 / _PHI


def _normalize(raw: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """Normalize each vertex to the unit sphere (all share one norm by design)."""
    out: list[tuple[float, float, float]] = []
    for vx, vy, vz in raw:
        norm = math.sqrt(vx * vx + vy * vy + vz * vz)
        out.append((vx / norm, vy / norm, vz / norm))
    return out


# order 1 → octahedron, n=6 (n >= (1+1)**2 = 4). Already unit.
_OCTA: list[tuple[float, float, float]] = [
    (1.0, 0.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 0.0, -1.0),
]

# order 2 → icosahedron, n=12 (n >= 9). All have norm √(1+φ²).
_ICO: list[tuple[float, float, float]] = _normalize(
    [
        (0.0, 1.0, _PHI),
        (0.0, 1.0, -_PHI),
        (0.0, -1.0, _PHI),
        (0.0, -1.0, -_PHI),
        (1.0, _PHI, 0.0),
        (1.0, -_PHI, 0.0),
        (-1.0, _PHI, 0.0),
        (-1.0, -_PHI, 0.0),
        (_PHI, 0.0, 1.0),
        (_PHI, 0.0, -1.0),
        (-_PHI, 0.0, 1.0),
        (-_PHI, 0.0, -1.0),
    ]
)

# order 3 → dodecahedron, n=20 (n >= 16). The 8 cube vertices (±1,±1,±1) plus the
# three rectangle quartets; all 20 have norm √3.
_DODECA: list[tuple[float, float, float]] = _normalize(
    [
        (1.0, 1.0, 1.0),
        (1.0, 1.0, -1.0),
        (1.0, -1.0, 1.0),
        (1.0, -1.0, -1.0),
        (-1.0, 1.0, 1.0),
        (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0),
        (-1.0, -1.0, -1.0),
        (0.0, _INV_PHI, _PHI),
        (0.0, _INV_PHI, -_PHI),
        (0.0, -_INV_PHI, _PHI),
        (0.0, -_INV_PHI, -_PHI),
        (_INV_PHI, _PHI, 0.0),
        (_INV_PHI, -_PHI, 0.0),
        (-_INV_PHI, _PHI, 0.0),
        (-_INV_PHI, -_PHI, 0.0),
        (_PHI, 0.0, _INV_PHI),
        (_PHI, 0.0, -_INV_PHI),
        (-_PHI, 0.0, _INV_PHI),
        (-_PHI, 0.0, -_INV_PHI),
    ]
)

#: order -> (rig name, closed-form unit-sphere vertices).
_PLATONIC_BY_ORDER: dict[int, tuple[str, list[tuple[float, float, float]]]] = {
    1: ("octahedron", _OCTA),
    2: ("icosahedron", _ICO),
    3: ("dodecahedron", _DODECA),
}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def place_ambisonics(
    order: int,
    *,
    radius_m: float = 2.0,
    layout_name: str = "ambisonics_rig",
) -> PlacementResult:
    """Closed-form platonic Ambisonics rig for decode ``order`` (1, 2, or 3).

    Maps the decode order to a regular polyhedron whose vertices are the speaker
    directions (each satisfying ``n >= (order+1)**2``)::

        order 1 -> octahedron   (n=6)
        order 2 -> icosahedron  (n=12)
        order 3 -> dodecahedron (n=20)

    The vertices are exact closed-form unit vectors (listener-frame x=right,
    y=up, z=front) scaled by ``radius_m``; each speaker aims toward the origin
    (listener). Channels are ``1..n`` monotonic. ``regularity_hint`` is
    ``IRREGULAR`` (R10 min 1).

    GEOMETRY ONLY — roomestim does not SH-encode/decode or route this rig; the
    end-to-end Ambisonics contract is UNCONFIRMED. See
    :data:`AMBISONICS_RIG_DISCLOSURE`.

    Raises ``ValueError`` (`kErrTooFewSpeakers`) if ``order`` is not in {1,2,3}.
    """
    if order not in _PLATONIC_BY_ORDER:
        raise ValueError(
            f"{kErrTooFewSpeakers}: ambisonics order must be one of "
            f"{sorted(_PLATONIC_BY_ORDER)} (order->rig: 1=octahedron(6), "
            f"2=icosahedron(12), 3=dodecahedron(20)); got {order!r}"
        )

    _rig_name, unit_vertices = _PLATONIC_BY_ORDER[order]
    speakers: list[PlacedSpeaker] = []
    for i, (vx, vy, vz) in enumerate(unit_vertices):
        position = Point3(x=radius_m * vx, y=radius_m * vy, z=radius_m * vz)
        speakers.append(
            PlacedSpeaker(
                channel=i + 1,
                position=position,
                aim_direction=_unit_aim_to_listener(position),
            )
        )
    return PlacementResult(
        target_algorithm=TargetAlgorithm.AMBISONICS.value,
        regularity_hint="IRREGULAR",
        speakers=speakers,
        layout_name=layout_name,
    )


__all__ = ["place_ambisonics", "AMBISONICS_RIG_DISCLOSURE"]
