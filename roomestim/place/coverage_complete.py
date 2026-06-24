"""Densify a B1 coverage grid to a MEASURED coverage target (B4).

The B1 grid (:mod:`roomestim.place.coverage_grid`) is sized by the AVIXA 1-D
adjacent-circle overlap rule, which a B2 overlap check
(:mod:`roomestim.place.coverage_overlap`) showed leaves real 2-D diagonal gaps —
across realistic rooms the default square/background grid covers only ~54-77 %
of the floor. This module closes that honestly: it tightens the grid spacing
until the *measured* fraction-covered (the B2 oracle, not a hand-derived
closed-form) reaches a requested target, or reports honestly that a speaker cap
was hit first.

Method: ``place_coverage_grid`` exposes a ``spacing_scale`` lever (1.0 = AVIXA
nominal, < 1.0 densifies). This searches ``spacing_scale`` downward from 1.0,
re-placing and re-scoring at each step, and stops at the first grid whose
``fraction_covered >= target_coverage`` (CONVERGED) or when the speaker count
exceeds ``max_speakers`` / the scale floor is reached (NOT converged — the best,
densest grid tried is returned with an honest flag). Coverage is the same
geometric -6 dB coverage-circle quantity B2 measures; NO acoustic / SPL claim.

numpy-free; import-safe at ``import roomestim`` time.
"""

from __future__ import annotations

from dataclasses import dataclass

from roomestim.model import Point2
from roomestim.place.coverage_grid import (
    DEFAULT_EAR_HEIGHT_M,
    DEFAULT_NOMINAL_DISPERSION_DEG,
    CoverageGridResult,
    GridType,
    OverlapMode,
    place_coverage_grid,
)
from roomestim.place.coverage_overlap import (
    CoverageOverlapScore,
    score_coverage_overlap,
)

__all__ = [
    "COVERAGE_COMPLETE_NOTE",
    "CoverageTargetResult",
    "DEFAULT_TARGET_COVERAGE",
    "place_coverage_grid_to_target",
]

#: Default measured coverage target (fraction of footprint within >= 1 circle).
DEFAULT_TARGET_COVERAGE: float = 0.90
#: Multiplicative spacing step per densify iteration (< 1.0).
_SPACING_STEP: float = 0.9
#: Floor on spacing_scale — below this the grid is absurdly dense; give up.
_MIN_SPACING_SCALE: float = 0.4
#: Hard cap on speakers while densifying (cost + practicality guard).
DEFAULT_MAX_SPEAKERS: int = 200


@dataclass(frozen=True)
class CoverageTargetResult:
    """Outcome of densifying a coverage grid to a measured coverage target.

    See :data:`COVERAGE_COMPLETE_NOTE`; ``achieved_coverage`` is the geometric
    -6 dB circle coverage (B2 oracle), not an acoustic measurement.
    """

    grid: CoverageGridResult
    score: CoverageOverlapScore
    target_coverage: float
    achieved_coverage: float
    spacing_scale: float       # 1.0 = AVIXA nominal; < 1.0 = densified
    converged: bool            # achieved_coverage >= target_coverage
    n_iterations: int
    note: str  # = COVERAGE_COMPLETE_NOTE


COVERAGE_COMPLETE_NOTE: str = (
    "Coverage-completeness densification: the grid spacing was tightened below "
    "the AVIXA 1-D nominal until the MEASURED geometric coverage (B2 "
    "coverage-circle overlap oracle, NOT a hand-derived formula) reached the "
    "target, or a speaker cap was hit (converged=false). achieved_coverage is the "
    "fraction of the footprint inside >= 1 coverage circle — a GEOMETRIC quantity, "
    "NOT an acoustic / SPL claim: it makes no statement about sound pressure level "
    "or uniformity, and the coverage circle is an idealised cone, not a measured "
    "polar response. It is SAMPLING-RESOLUTION dependent (coarser grid_resolution_m "
    "OVER-reports coverage — a gap smaller than the sample step is missed), so "
    "compare at a fixed resolution. spacing_scale < 1.0 means the grid was "
    "densified past the AVIXA nominal to close the 2-D diagonal gaps the 1-D "
    "overlap leaves. If converged=false the target was NOT reached within the "
    "speaker cap — the densest grid tried is returned. Geometric coverage "
    "GUIDANCE, not a guarantee."
)


def place_coverage_grid_to_target(
    *,
    floor_polygon: list[Point2],
    ceiling_height_m: float,
    ear_height_m: float = DEFAULT_EAR_HEIGHT_M,
    nominal_dispersion_deg: float = DEFAULT_NOMINAL_DISPERSION_DEG,
    overlap_mode: OverlapMode = "background",
    grid_type: GridType = "square",
    layout_name: str = "coverage_grid",
    target_coverage: float = DEFAULT_TARGET_COVERAGE,
    grid_resolution_m: float = 0.5,
    max_speakers: int = DEFAULT_MAX_SPEAKERS,
) -> CoverageTargetResult:
    """Densify a coverage grid until measured coverage >= ``target_coverage``.

    Deterministic. Raises ``ValueError`` if ``target_coverage`` is outside
    ``(0, 1]`` or ``max_speakers < 1`` (other inputs are validated by
    :func:`place_coverage_grid` / :func:`score_coverage_overlap`).

    Returns the first grid that meets the target (``converged=True``) or, if the
    speaker cap / scale floor is hit first, the densest grid tried
    (``converged=False``) — never silently a sparse grid.
    """
    if not (0.0 < target_coverage <= 1.0):
        raise ValueError(
            f"target_coverage must be in (0, 1], got {target_coverage}"
        )
    if max_speakers < 1:
        raise ValueError(f"max_speakers must be >= 1, got {max_speakers}")

    scale = 1.0
    best: CoverageTargetResult | None = None
    iters = 0
    while scale >= _MIN_SPACING_SCALE:
        iters += 1
        grid = place_coverage_grid(
            floor_polygon=floor_polygon,
            ceiling_height_m=ceiling_height_m,
            ear_height_m=ear_height_m,
            nominal_dispersion_deg=nominal_dispersion_deg,
            overlap_mode=overlap_mode,
            grid_type=grid_type,
            layout_name=layout_name,
            spacing_scale=scale,
        )
        score = score_coverage_overlap(
            grid, floor_polygon, grid_resolution_m=grid_resolution_m
        )
        candidate = CoverageTargetResult(
            grid=grid,
            score=score,
            target_coverage=target_coverage,
            achieved_coverage=score.fraction_covered,
            spacing_scale=scale,
            converged=score.fraction_covered >= target_coverage,
            n_iterations=iters,
            note=COVERAGE_COMPLETE_NOTE,
        )
        # Densifying tightens spacing => more speakers and (monotonically in
        # practice, though each step is a re-centred position set, not a strict
        # superset) higher coverage, so the latest candidate is the best tried.
        best = candidate
        if candidate.converged:
            return candidate
        if grid.n_speakers >= max_speakers:
            break  # cap hit before target -> return densest tried (not converged)
        scale *= _SPACING_STEP

    assert best is not None  # loop runs at least once (scale starts at 1.0)
    return best
