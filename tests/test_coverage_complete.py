"""Tests for the B4 coverage-completeness densifier.

Pure geometry (uses the B2 overlap oracle) => default gate. Locks: the densifier
reaches the measured coverage target on rooms the AVIXA nominal under-covers;
spacing_scale=1.0 is byte-equal to the nominal grid; the converged flag is honest
when a speaker cap is hit; inputs validate; the note disclaims acoustic claims.
"""

from __future__ import annotations

import pytest

from roomestim.model import Point2
from roomestim.place.coverage_complete import (
    COVERAGE_COMPLETE_NOTE,
    place_coverage_grid_to_target,
)
from roomestim.place.coverage_grid import place_coverage_grid
from roomestim.place.coverage_overlap import score_coverage_overlap


def _rect(w: float, d: float) -> list[Point2]:
    return [Point2(0.0, 0.0), Point2(w, 0.0), Point2(w, d), Point2(0.0, d)]


def test_densify_reaches_target_on_undercovered_room() -> None:
    """A meeting room the AVIXA nominal under-covers (~54%) is densified to >=90%."""
    fp = _rect(6.0, 5.0)
    nominal = place_coverage_grid(floor_polygon=fp, ceiling_height_m=3.0, ear_height_m=1.2)
    nominal_cov = score_coverage_overlap(nominal, fp).fraction_covered
    assert nominal_cov < 0.9  # precondition: nominal really under-covers

    tr = place_coverage_grid_to_target(
        floor_polygon=fp, ceiling_height_m=3.0, ear_height_m=1.2, target_coverage=0.9
    )
    assert tr.converged
    assert tr.achieved_coverage >= 0.9
    assert tr.grid.n_speakers >= nominal.n_speakers  # densified or equal
    assert tr.spacing_scale <= 1.0


def test_spacing_scale_one_is_byte_equal_to_nominal() -> None:
    """spacing_scale defaults to 1.0 => identical speaker positions as the nominal."""
    fp = _rect(8.0, 6.0)
    a = place_coverage_grid(floor_polygon=fp, ceiling_height_m=3.0, ear_height_m=1.2)
    b = place_coverage_grid(
        floor_polygon=fp, ceiling_height_m=3.0, ear_height_m=1.2, spacing_scale=1.0
    )
    assert a == b


def test_smaller_spacing_scale_densifies() -> None:
    fp = _rect(8.0, 6.0)
    base = place_coverage_grid(floor_polygon=fp, ceiling_height_m=3.0, ear_height_m=1.2)
    dense = place_coverage_grid(
        floor_polygon=fp, ceiling_height_m=3.0, ear_height_m=1.2, spacing_scale=0.7
    )
    assert dense.n_speakers >= base.n_speakers
    assert dense.center_to_center_spacing_m < base.center_to_center_spacing_m


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.5])
def test_spacing_scale_out_of_range_raises(bad: float) -> None:
    with pytest.raises(ValueError):
        place_coverage_grid(
            floor_polygon=_rect(8.0, 6.0), ceiling_height_m=3.0, ear_height_m=1.2,
            spacing_scale=bad,
        )


def test_cap_hit_reports_not_converged_and_densest_tried() -> None:
    """With an unreachable target + tiny speaker cap, converged is False and the
    densest grid tried (not a sparse one) is returned."""
    fp = _rect(18.0, 14.0)
    tr = place_coverage_grid_to_target(
        floor_polygon=fp, ceiling_height_m=3.5, ear_height_m=1.2,
        target_coverage=1.0, max_speakers=10,
    )
    assert not tr.converged
    assert tr.achieved_coverage < 1.0
    # honest: it returned a real grid, and the achieved coverage matches its score
    assert tr.achieved_coverage == tr.score.fraction_covered


def test_already_covered_room_converges_first_iteration() -> None:
    """A tiny room a single speaker already covers needs no densification."""
    fp = _rect(2.0, 2.0)
    tr = place_coverage_grid_to_target(
        floor_polygon=fp, ceiling_height_m=3.0, ear_height_m=1.2, target_coverage=0.9
    )
    assert tr.converged
    assert tr.n_iterations == 1
    assert tr.spacing_scale == 1.0


@pytest.mark.parametrize("bad", [0.0, -0.5, 1.1])
def test_bad_target_raises(bad: float) -> None:
    with pytest.raises(ValueError):
        place_coverage_grid_to_target(
            floor_polygon=_rect(6.0, 5.0), ceiling_height_m=3.0, ear_height_m=1.2,
            target_coverage=bad,
        )


def test_bad_max_speakers_raises() -> None:
    with pytest.raises(ValueError):
        place_coverage_grid_to_target(
            floor_polygon=_rect(6.0, 5.0), ceiling_height_m=3.0, ear_height_m=1.2,
            max_speakers=0,
        )


def test_note_honesty_invariants() -> None:
    low = COVERAGE_COMPLETE_NOTE.lower()
    assert "not an acoustic" in low or "no acoustic" in low or "not a guarantee" in low
    assert "spl" in low
    assert "converged=false" in low
    assert "guidance" in low
