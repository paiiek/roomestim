"""Coverage-circle overlap verification for a B1 ceiling grid (B2).

B1 (:mod:`roomestim.place.coverage_grid`) SIZES a ceiling-speaker lattice from
the AVIXA Audio Coverage Uniformity geometric model — each speaker covers a
floor-projected circle of ``coverage_radius_m`` and the spacing is chosen so
neighbouring circles overlap by the requested fraction — but explicitly DEFERS
checking whether the placed grid actually ACHIEVES that overlap on the real
(possibly concave / clipped) footprint. This module closes that deferral by
measuring the realised coverage on the listening plane.

What it computes (pure geometry, the SAME coverage-circle model B1 sizes with)
-----------------------------------------------------------------------------
The ear-plane footprint is sampled on a lattice; for each sample the number of
speakers whose floor-projected coverage circle (centre = speaker ``(x, z)``,
radius = ``coverage_radius_m``) contains it is the local *overlap multiplicity*.
From that field:

* ``fraction_covered``      — share of the footprint inside >= 1 coverage circle
                              (1.0 means no gaps; < 1.0 locates real holes).
* ``fraction_overlap_2plus``— realised share inside >= 2 circles (B1 SIZES for
                              1-D adjacent-circle overlap; this is the achieved
                              2-D >=2-coverage share, NOT a calibrated AVIXA
                              threshold).
* ``min_overlap`` / ``mean_overlap`` — multiplicity distribution.
* ``worst_point_xz``        — a least-covered sample, to locate the worst gap
                              (only meaningful when ``fraction_covered < 1.0``;
                              when fully covered it is just a min-multiplicity pt).

Cost is ``O(n_samples * n_speakers)`` (a pure-Python double loop); the default
0.5 m resolution keeps this small, but a very fine ``grid_resolution_m`` over a
large footprint with many speakers grows quadratically.

Why overlap, not an SPL number (load-bearing honesty — :data:`COVERAGE_OVERLAP_NOTE`)
------------------------------------------------------------------------------------
This is a GEOMETRIC coverage check, NOT an acoustic / SPL prediction: a
direct-sound SPL field is dominated by the near-field peak directly under each
ceiling speaker and is not a robust uniformity comparator, while absolute SPL
needs speaker sensitivity + drive level that roomestim does not have. The
coverage-circle overlap is exactly the quantity B1's spacing math is derived
from, so this verifies B1's own geometric promise without inventing acoustic
numbers.

numpy-free (stdlib ``math`` + shapely, both core deps); import-safe at
``import roomestim`` time (core / torch-free boundary).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.model import Point2, assert_finite
from roomestim.place.coverage_grid import CoverageGridResult

__all__ = [
    "COVERAGE_OVERLAP_NOTE",
    "CoverageOverlapScore",
    "DEFAULT_GRID_RESOLUTION_M",
    "score_coverage_overlap",
    "coverage_overlap_to_dict",
    "format_coverage_overlap_lines",
]

#: Default ear-plane sampling resolution (m).
DEFAULT_GRID_RESOLUTION_M: float = 0.5


@dataclass(frozen=True)
class CoverageOverlapScore:
    """Realised coverage-circle overlap statistics for a B1 grid. Pure geometry.

    See :data:`COVERAGE_OVERLAP_NOTE`; none of these is an acoustic measurement.
    """

    n_grid_points: int
    grid_resolution_m: float
    coverage_radius_m: float
    fraction_covered: float        # share inside >= 1 coverage circle
    fraction_overlap_2plus: float  # realised share inside >= 2 circles (not a calibrated threshold)
    min_overlap: int               # fewest overlapping circles at any sample
    mean_overlap: float            # mean multiplicity over the footprint
    worst_point_xz: tuple[float, float]  # a least-covered sample (x, z)
    note: str  # = COVERAGE_OVERLAP_NOTE


COVERAGE_OVERLAP_NOTE: str = (
    "Geometric coverage-circle OVERLAP check only — NOT an acoustic / SPL "
    "prediction and NOT a measurement. Each ceiling speaker is treated as "
    "covering the floor-projected circle of radius coverage_radius_m that B1's "
    "AVIXA spacing math is derived from; this verifies whether the PLACED grid "
    "actually achieves >= 1 (no gaps) and >= 2 (overlap) circle coverage on the "
    "real, possibly concave / clipped footprint. It makes NO claim about sound "
    "pressure level, frequency response, or the reverberant field: absolute SPL "
    "needs speaker sensitivity + drive level roomestim does not have, and a "
    "direct-sound field is dominated by the near-field peak under each speaker. "
    "fraction_covered < 1.0 locates true coverage holes; worst_point_xz points at "
    "one. Treat as geometric coverage GUIDANCE, not an acoustic guarantee."
)


def score_coverage_overlap(
    result: CoverageGridResult,
    floor_polygon: list[Point2],
    *,
    grid_resolution_m: float = DEFAULT_GRID_RESOLUTION_M,
) -> CoverageOverlapScore:
    """Measure realised coverage-circle overlap of a B1 grid on its footprint.

    Samples the footprint on a ``grid_resolution_m`` lattice and counts, per
    sample, how many speaker coverage circles (radius ``coverage_radius_m``,
    horizontal distance) contain it. Deterministic. Raises ``ValueError`` on a
    degenerate polygon, a non-finite / non-positive resolution, or no speakers.
    """
    if not result.speakers:
        raise ValueError("coverage result has no speakers to score")
    assert_finite(grid_resolution_m, field="grid_resolution_m")
    if grid_resolution_m <= 0.0:
        raise ValueError(f"grid_resolution_m must be > 0, got {grid_resolution_m}")
    if len(floor_polygon) < 3:
        raise ValueError("coverage scoring requires a polygon with >=3 vertices")
    poly = ShapelyPolygon([(p.x, p.z) for p in floor_polygon])
    if not poly.is_valid or poly.is_empty or poly.area <= 0.0:
        raise ValueError("degenerate floor polygon (zero area / self-intersecting)")

    radius = result.coverage_radius_m
    r2 = radius * radius
    centers = [(sp.position.x, sp.position.z) for sp in result.speakers]

    # --- footprint sampling grid (cell-centred, symmetric inset) ----------- #
    minx, minz, maxx, maxz = poly.bounds
    nx = max(1, int(math.floor((maxx - minx) / grid_resolution_m)))
    nz = max(1, int(math.floor((maxz - minz) / grid_resolution_m)))
    x0 = minx + (maxx - minx - (nx - 1) * grid_resolution_m) / 2.0
    z0 = minz + (maxz - minz - (nz - 1) * grid_resolution_m) / 2.0
    samples: list[tuple[float, float]] = []
    for ix in range(nx):
        for iz in range(nz):
            x = x0 + ix * grid_resolution_m
            z = z0 + iz * grid_resolution_m
            if poly.covers(ShapelyPoint(x, z)):
                samples.append((x, z))
    if not samples:  # footprint smaller than one cell
        rep = poly.representative_point()
        samples.append((float(rep.x), float(rep.y)))

    counts: list[tuple[float, float, int]] = []
    for x, z in samples:
        c = 0
        for cx, cz in centers:
            dx, dz = x - cx, z - cz
            if dx * dx + dz * dz <= r2:
                c += 1
        counts.append((x, z, c))

    n = len(counts)
    multiplicities = [c[2] for c in counts]
    covered = sum(1 for m in multiplicities if m >= 1) / n
    overlap2 = sum(1 for m in multiplicities if m >= 2) / n
    worst = min(counts, key=lambda c: c[2])

    return CoverageOverlapScore(
        n_grid_points=n,
        grid_resolution_m=grid_resolution_m,
        coverage_radius_m=radius,
        fraction_covered=covered,
        fraction_overlap_2plus=overlap2,
        min_overlap=min(multiplicities),
        mean_overlap=sum(multiplicities) / n,
        worst_point_xz=(worst[0], worst[1]),
        note=COVERAGE_OVERLAP_NOTE,
    )


def coverage_overlap_to_dict(score: CoverageOverlapScore) -> dict[str, object]:
    """Plain JSON-serialisable dict for the ``layout.coverage.json`` ``overlap`` key.

    ``"note"`` first (mirrors :func:`coverage_grid.coverage_to_dict`).
    """
    return {
        "note": score.note,
        "n_grid_points": score.n_grid_points,
        "grid_resolution_m": score.grid_resolution_m,
        "coverage_radius_m": round(score.coverage_radius_m, 4),
        "fraction_covered": round(score.fraction_covered, 4),
        "fraction_overlap_2plus": round(score.fraction_overlap_2plus, 4),
        "min_overlap": score.min_overlap,
        "mean_overlap": round(score.mean_overlap, 3),
        "worst_point_xz": [round(score.worst_point_xz[0], 3), round(score.worst_point_xz[1], 3)],
    }


def format_coverage_overlap_lines(score: CoverageOverlapScore) -> list[str]:
    """Human-readable CLI summary lines (geometric overlap; no acoustic claim)."""
    wx, wz = score.worst_point_xz
    gap = "" if score.fraction_covered >= 1.0 else (
        f" — GAP near (x={wx:.1f}, z={wz:.1f})"
    )
    return [
        "coverage overlap (geometric circles, NO SPL/acoustic claim):",
        f"  sampled {score.n_grid_points} ear-plane pts @ {score.grid_resolution_m:.2f} m, "
        f"r={score.coverage_radius_m:.2f} m",
        f"  {score.fraction_covered * 100:.0f}% covered (>=1 circle){gap}; "
        f"{score.fraction_overlap_2plus * 100:.0f}% overlapped (>=2)",
        f"  overlap multiplicity: min {score.min_overlap}, mean {score.mean_overlap:.1f} "
        "— geometric guidance only (see note)",
    ]
