"""Angular-uniformity + interference-proxy metrics for an immersive rig (P2).

An immersive / surround layout surrounds a LISTENER at the origin. The quality
that matters for smooth VBAP/DBAP panning is the ANGULAR regularity of the
speakers as seen from that listener: even angular spacing means no big holes and
no tight clusters. The correct primitive is therefore the GEODESIC (great-circle)
angle between speaker DIRECTION unit vectors on the unit sphere — NOT an
azimuth-only spacing, because a dome has elevation too.

What it computes (pure geometry — :data:`IMMERSIVE_QUALITY_NOTE`)
----------------------------------------------------------------
For each speaker the DIRECTION is the unit vector of its ``position`` (origin ->
speaker = where the speaker sits around the listener). The geodesic angle between
two directions ``u_i, u_j`` is ``acos(clamp(dot(u_i, u_j), -1, 1))``.

* :func:`angular_uniformity` — per-speaker NEAREST-NEIGHBOUR geodesic gap (the
  smallest geodesic angle to any other speaker). The min / max / mean of that
  nearest-neighbour-gap set describe how evenly the rig is spread; the 0..1
  ``uniformity`` score is ``min_nn_gap / max_nn_gap`` (1.0 = perfectly even).
  ``worst_pair`` is the two channels with the smallest pairwise geodesic angle
  (the tightest cluster — the biggest local non-uniformity).
* :func:`interference_proxy` — a GEOMETRIC minimum-separation flag: speaker PAIRS
  whose direction separation is below ``min_separation_deg`` (a documented 10 deg
  rule-of-thumb, NOT calibrated) are flagged as too close (comb-filter / redundant
  coverage risk). This is NOT a psychoacoustic / comb-filter prediction.

Both are deterministic. ``aim_direction`` is intentionally NOT used for the
angular layout — where a speaker SITS around the listener (its position
direction) is what governs panning coverage, not where it is aimed.

Cost: :func:`angular_uniformity` and :func:`interference_proxy` each independently
recompute the direction unit vectors and run an O(n^2) pairwise geodesic-angle
loop (no shared cache between them); negligible at real rig sizes (n <= ~64).

numpy-free (stdlib ``math`` only); import-safe at ``import roomestim`` time
(core / torch-free boundary).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from roomestim.model import PlacedSpeaker, assert_finite, kErrTooFewSpeakers
from roomestim.reconstruct._disclosure import IMMERSIVE_QUALITY_NOTE

__all__ = [
    "IMMERSIVE_QUALITY_NOTE",
    "DEFAULT_MIN_SEPARATION_DEG",
    "MAX_REPORTED_CLOSE_PAIRS",
    "AngularUniformityScore",
    "InterferenceScore",
    "angular_uniformity",
    "interference_proxy",
    "angular_uniformity_to_dict",
    "interference_to_dict",
    "format_angular_uniformity_lines",
    "format_interference_lines",
]

#: Default too-close direction-separation threshold (deg). A documented
#: rule-of-thumb, NOT calibrated against measured comb-filter data.
DEFAULT_MIN_SEPARATION_DEG: float = 10.0

#: Cap on the number of close pairs listed in an :class:`InterferenceScore`
#: (the count ``n_close_pairs`` is always exact; the list is truncated with a flag).
MAX_REPORTED_CLOSE_PAIRS: int = 20


@dataclass(frozen=True)
class AngularUniformityScore:
    """Angular-spacing regularity of an immersive rig. Pure geometry.

    See :data:`IMMERSIVE_QUALITY_NOTE`; none of these is an acoustic measurement.
    """

    n_speakers: int
    min_nn_gap_deg: float   # smallest per-speaker nearest-neighbour geodesic gap
    max_nn_gap_deg: float   # largest  per-speaker nearest-neighbour geodesic gap
    mean_nn_gap_deg: float  # mean of the nearest-neighbour gaps
    uniformity: float       # = min_nn_gap_deg / max_nn_gap_deg in [0, 1]; 1.0 = perfectly even
    worst_pair: tuple[int, int]  # channels of the tightest (smallest-angle) pair
    note: str  # = IMMERSIVE_QUALITY_NOTE


@dataclass(frozen=True)
class InterferenceScore:
    """Geometric minimum-separation flag for too-close speaker pairs. NOT acoustic.

    See :data:`IMMERSIVE_QUALITY_NOTE`: a comb-filter / redundant-coverage RISK
    proxy, not a psychoacoustic prediction.
    """

    n_speakers: int
    min_separation_deg: float       # the threshold used
    min_pair_separation_deg: float  # the actual smallest pairwise geodesic angle
    n_close_pairs: int              # exact count of pairs below the threshold
    close_pairs: list[tuple[int, int]]  # channels (each sorted), capped to MAX_REPORTED_CLOSE_PAIRS
    close_pairs_truncated: bool     # True when n_close_pairs > len(close_pairs)
    note: str  # = IMMERSIVE_QUALITY_NOTE


def _direction_unit_vector(speaker: PlacedSpeaker) -> tuple[float, float, float]:
    """Unit DIRECTION vector of a speaker's ``position`` (origin -> speaker).

    Raises ``ValueError`` if the speaker is exactly at the origin (degenerate
    direction) or carries a non-finite position component.
    """
    px, py, pz = speaker.position.x, speaker.position.y, speaker.position.z
    assert_finite(px, field="position.x")
    assert_finite(py, field="position.y")
    assert_finite(pz, field="position.z")
    norm = math.sqrt(px * px + py * py + pz * pz)
    if norm <= 0.0:
        raise ValueError(
            f"channel {speaker.channel} is at the listener origin "
            "(degenerate direction; cannot compute an angular layout)"
        )
    return (px / norm, py / norm, pz / norm)


def _geodesic_angle_deg(
    u: tuple[float, float, float], v: tuple[float, float, float]
) -> float:
    """Great-circle angle (deg) between two unit direction vectors.

    ``acos(clamp(dot(u, v), -1, 1))`` — the clamp keeps acos in-domain against
    float round-off; the dot is finite-checked before acos.
    """
    dot = u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
    assert_finite(dot, field="direction_dot")
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def angular_uniformity(speakers: list[PlacedSpeaker]) -> AngularUniformityScore:
    """Angular-spacing regularity of an immersive rig (nearest-neighbour gaps).

    Each speaker's DIRECTION is the unit vector of its ``position`` (where it
    sits around the listener at the origin). For each speaker the
    nearest-neighbour gap is the smallest geodesic angle to any other speaker;
    ``uniformity = min_nn_gap / max_nn_gap`` over that set (1.0 = perfectly
    even). ``worst_pair`` is the two channels with the smallest pairwise geodesic
    angle (tightest cluster), reported in sorted (min, max) channel order; ties
    (e.g. a perfectly uniform rig) resolve to the first ``i < j`` pair scanned.
    Deterministic.

    Raises ``ValueError`` (``kErrTooFewSpeakers``) if fewer than 2 speakers, or
    if any speaker is at the origin / has a non-finite position.
    """
    if len(speakers) < 2:
        raise ValueError(
            f"{kErrTooFewSpeakers}: angular uniformity requires >=2 speakers, "
            f"got {len(speakers)}"
        )
    dirs = [_direction_unit_vector(sp) for sp in speakers]
    n = len(dirs)

    nn_gaps: list[float] = []
    min_pair_angle = math.inf
    c0, c1 = speakers[0].channel, speakers[1].channel
    worst_pair = (c0, c1) if c0 <= c1 else (c1, c0)
    for i in range(n):
        nearest = math.inf
        for j in range(n):
            if i == j:
                continue
            ang = _geodesic_angle_deg(dirs[i], dirs[j])
            if ang < nearest:
                nearest = ang
            if i < j and ang < min_pair_angle:
                min_pair_angle = ang
                a, b = speakers[i].channel, speakers[j].channel
                # sorted (min, max) channel order — consistent with the
                # close_pairs normalisation in interference_proxy.
                worst_pair = (a, b) if a <= b else (b, a)
        nn_gaps.append(nearest)

    min_gap = min(nn_gaps)
    max_gap = max(nn_gaps)
    # max_gap >= min_gap >= 0; max_gap can be 0 only if every direction coincides
    # (all speakers in the same direction) — then the layout is degenerate but
    # "perfectly uniform" at 0 spacing, so report uniformity 1.0 rather than 0/0.
    uniformity = 1.0 if max_gap <= 0.0 else min_gap / max_gap
    return AngularUniformityScore(
        n_speakers=n,
        min_nn_gap_deg=min_gap,
        max_nn_gap_deg=max_gap,
        mean_nn_gap_deg=sum(nn_gaps) / n,
        uniformity=uniformity,
        worst_pair=worst_pair,
        note=IMMERSIVE_QUALITY_NOTE,
    )


def interference_proxy(
    speakers: list[PlacedSpeaker],
    *,
    min_separation_deg: float = DEFAULT_MIN_SEPARATION_DEG,
) -> InterferenceScore:
    """Geometric minimum-separation flag for too-close speaker pairs.

    Flags speaker PAIRS whose geodesic direction separation (from the listener at
    the origin) is below ``min_separation_deg`` — too-close pairs risk
    comb-filtering / redundant coverage. This is a GEOMETRIC proxy ONLY, NOT a
    psychoacoustic / comb-filter prediction; the 10 deg default is a documented
    rule-of-thumb threshold, NOT calibrated. Deterministic.

    The exact ``n_close_pairs`` count is always reported; the ``close_pairs``
    list is capped at :data:`MAX_REPORTED_CLOSE_PAIRS` with
    ``close_pairs_truncated`` set (pairs are NOT silently dropped). Raises
    ``ValueError`` on fewer than 2 speakers, a non-finite / non-positive
    threshold, or an origin / non-finite speaker position.
    """
    if len(speakers) < 2:
        raise ValueError(
            f"{kErrTooFewSpeakers}: interference proxy requires >=2 speakers, "
            f"got {len(speakers)}"
        )
    assert_finite(min_separation_deg, field="min_separation_deg")
    if min_separation_deg <= 0.0:
        raise ValueError(
            f"min_separation_deg must be > 0, got {min_separation_deg}"
        )
    dirs = [_direction_unit_vector(sp) for sp in speakers]
    n = len(dirs)

    close: list[tuple[int, int]] = []
    min_pair_separation = math.inf
    for i in range(n):
        for j in range(i + 1, n):
            ang = _geodesic_angle_deg(dirs[i], dirs[j])
            if ang < min_pair_separation:
                min_pair_separation = ang
            if ang < min_separation_deg:
                a, b = speakers[i].channel, speakers[j].channel
                close.append((a, b) if a <= b else (b, a))

    close.sort()
    n_close = len(close)
    truncated = n_close > MAX_REPORTED_CLOSE_PAIRS
    return InterferenceScore(
        n_speakers=n,
        min_separation_deg=min_separation_deg,
        min_pair_separation_deg=min_pair_separation,
        n_close_pairs=n_close,
        close_pairs=close[:MAX_REPORTED_CLOSE_PAIRS],
        close_pairs_truncated=truncated,
        note=IMMERSIVE_QUALITY_NOTE,
    )


def angular_uniformity_to_dict(score: AngularUniformityScore) -> dict[str, object]:
    """Plain JSON-serialisable dict (``"note"`` first; mirrors coverage_overlap)."""
    return {
        "note": score.note,
        "n_speakers": score.n_speakers,
        "min_nn_gap_deg": round(score.min_nn_gap_deg, 3),
        "max_nn_gap_deg": round(score.max_nn_gap_deg, 3),
        "mean_nn_gap_deg": round(score.mean_nn_gap_deg, 3),
        "uniformity": round(score.uniformity, 4),
        "worst_pair": [score.worst_pair[0], score.worst_pair[1]],
    }


def interference_to_dict(score: InterferenceScore) -> dict[str, object]:
    """Plain JSON-serialisable dict (``"note"`` first; mirrors coverage_overlap)."""
    return {
        "note": score.note,
        "n_speakers": score.n_speakers,
        "min_separation_deg": round(score.min_separation_deg, 3),
        "min_pair_separation_deg": round(score.min_pair_separation_deg, 3),
        "n_close_pairs": score.n_close_pairs,
        "close_pairs": [[a, b] for a, b in score.close_pairs],
        "close_pairs_truncated": score.close_pairs_truncated,
    }


def format_angular_uniformity_lines(score: AngularUniformityScore) -> list[str]:
    """Human-readable CLI summary lines (geometric angular spacing; NO acoustic claim).

    On an essentially-uniform rig (``uniformity >= 0.999``) the tightest pair is a
    tied, arbitrary pick, so naming it would be misleading; that line instead
    states the layout is angularly uniform. Otherwise the closest pair is reported
    as informational (not a flag).
    """
    lines = [
        "angular uniformity (geodesic spacing as seen from listener, NO acoustic claim):",
        f"  {score.n_speakers} speakers; nearest-neighbour gap "
        f"min {score.min_nn_gap_deg:.1f} / mean {score.mean_nn_gap_deg:.1f} / "
        f"max {score.max_nn_gap_deg:.1f} deg",
    ]
    if score.uniformity >= 0.999:
        lines.append(
            f"  uniformity {score.uniformity:.2f} (min/max gap; 1.0 = perfectly even); "
            "layout is angularly uniform (no outlier pair)"
        )
    else:
        lines.append(
            f"  uniformity {score.uniformity:.2f} (min/max gap; 1.0 = perfectly even); "
            f"closest pair (informational): channels {score.worst_pair[0]} & "
            f"{score.worst_pair[1]}"
        )
    lines.append("  geometric panning-smoothness GUIDANCE only (see note)")
    return lines


def format_interference_lines(score: InterferenceScore) -> list[str]:
    """Human-readable CLI summary lines (geometric proxy; NOT a comb-filter prediction)."""
    lines = [
        "interference proxy (geometric min-separation flag, NOT a comb-filter prediction):",
        f"  smallest pair separation {score.min_pair_separation_deg:.1f} deg "
        f"(threshold {score.min_separation_deg:.1f} deg)",
        f"  {score.n_close_pairs} too-close pair(s) flagged",
    ]
    if score.n_close_pairs:
        shown = ", ".join(f"{a}&{b}" for a, b in score.close_pairs)
        suffix = " ..." if score.close_pairs_truncated else ""
        lines.append(f"    pairs (channels): {shown}{suffix}")
    lines.append("  geometric RISK guidance only, not a psychoacoustic prediction (see note)")
    return lines
