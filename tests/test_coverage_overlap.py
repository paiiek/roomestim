"""Tests for the B2 geometric coverage-circle overlap check.

Pure geometry (the same coverage-circle model B1 sizes with) => default gate, no
pyroomacoustics. These lock the geometric invariants: a well-overlapped grid
covers its footprint with overlap, a concave notch / narrow geometry leaves a
gap, a denser overlap mode raises the >=2 share, and the honesty note disclaims
any SPL/acoustic claim.
"""

from __future__ import annotations

import pytest

from roomestim.model import Point2
from roomestim.place.coverage_grid import place_coverage_grid
from roomestim.place.coverage_overlap import (
    COVERAGE_OVERLAP_NOTE,
    CoverageOverlapScore,
    coverage_overlap_to_dict,
    format_coverage_overlap_lines,
    score_coverage_overlap,
)


def _rect(w: float, d: float) -> list[Point2]:
    return [Point2(0.0, 0.0), Point2(w, 0.0), Point2(w, d), Point2(0.0, d)]


def _score(
    w: float = 10.0,
    d: float = 8.0,
    ceiling: float = 3.0,
    ear: float = 1.0,
    overlap: str = "background",
    grid: str = "square",
    res: float = 0.5,
    poly: list[Point2] | None = None,
    **kw: object,
) -> CoverageOverlapScore:
    fp = poly if poly is not None else _rect(w, d)
    result = place_coverage_grid(
        floor_polygon=fp,
        ceiling_height_m=ceiling,
        ear_height_m=ear,
        overlap_mode=overlap,  # type: ignore[arg-type]
        grid_type=grid,  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )
    return score_coverage_overlap(result, fp, grid_resolution_m=res)


def test_basic_shape_and_bounds() -> None:
    s = _score()
    assert s.n_grid_points > 0
    assert 0.0 <= s.fraction_covered <= 1.0
    assert 0.0 <= s.fraction_overlap_2plus <= s.fraction_covered
    assert s.min_overlap >= 0
    assert s.mean_overlap >= s.min_overlap
    assert s.coverage_radius_m > 0.0


def test_denser_overlap_improves_coverage_and_overlap2() -> None:
    """The denser 'speech' (23%%) mode tightens spacing => more floor covered AND
    a larger >=2 overlap share than 'background' (the honest geometric truth that
    B1's 1-D AVIXA spacing leaves 2-D gaps the denser mode partially fills)."""
    bg = _score(w=8.0, d=6.0, ceiling=3.0, ear=1.2, overlap="background", res=0.25)
    sp = _score(w=8.0, d=6.0, ceiling=3.0, ear=1.2, overlap="speech", res=0.25)
    assert sp.fraction_covered >= bg.fraction_covered
    assert sp.fraction_overlap_2plus >= bg.fraction_overlap_2plus


def test_square_grid_leaves_real_diagonal_gaps() -> None:
    """B2's value: a square grid sized by the 1-D AVIXA spacing rule does NOT
    fully cover the 2-D floor (diagonal cell centres fall outside every circle).
    This is the honest finding the check surfaces — not full coverage."""
    s = _score(w=8.0, d=6.0, ceiling=3.0, ear=1.2, grid="square",
               overlap="background", res=0.25)
    assert s.fraction_covered < 1.0   # real gaps exist
    assert s.min_overlap == 0


def test_concave_l_shape_may_leave_gap_but_runs() -> None:
    """An L-shaped (concave) footprint: notch nodes are dropped by B1, so the
    realised coverage can dip below full — the check must surface that, not crash."""
    lshape = [
        Point2(0.0, 0.0),
        Point2(12.0, 0.0),
        Point2(12.0, 4.0),
        Point2(4.0, 4.0),
        Point2(4.0, 12.0),
        Point2(0.0, 12.0),
    ]
    s = _score(poly=lshape, ceiling=3.0, ear=1.0)
    assert 0.0 < s.fraction_covered <= 1.0
    x, z = s.worst_point_xz
    # worst point lies inside the L bounding box
    assert 0.0 <= x <= 12.0 and 0.0 <= z <= 12.0


def test_sparse_high_room_has_gaps() -> None:
    """A big room with a sparse grid leaves uncovered holes (fraction_covered<1)."""
    s = _score(w=30.0, d=30.0, ceiling=6.0, ear=1.2, nominal_dispersion_deg=120.0)
    assert s.fraction_covered < 1.0
    assert s.min_overlap == 0


def test_to_dict_note_first_no_spl_key() -> None:
    import json

    s = _score()
    d = coverage_overlap_to_dict(s)
    assert list(d)[0] == "note"
    assert d["note"] == COVERAGE_OVERLAP_NOTE
    # geometric metric keys only — no absolute SPL/level value is emitted
    assert {"fraction_covered", "fraction_overlap_2plus", "min_overlap",
            "mean_overlap", "coverage_radius_m"} <= set(d)
    assert "db" not in {k.lower() for k in d}
    assert d["fraction_covered"] == round(s.fraction_covered, 4)
    json.loads(json.dumps(d))


def test_note_honesty_invariants() -> None:
    low = COVERAGE_OVERLAP_NOTE.lower()
    assert "not an acoustic" in low or "no" in low
    assert "spl" in low  # explicitly disclaims SPL
    assert "not a measurement" in low
    assert "guidance" in low


def test_format_lines_nonempty_no_spl_claim() -> None:
    lines = format_coverage_overlap_lines(_score())
    assert lines
    joined = " ".join(lines).lower()
    assert "no spl" in joined or "geometric" in joined


@pytest.mark.parametrize("res", [-1.0, 0.0])
def test_bad_resolution_raises(res: float) -> None:
    result = place_coverage_grid(
        floor_polygon=_rect(10.0, 8.0), ceiling_height_m=3.0, ear_height_m=1.0
    )
    with pytest.raises(ValueError):
        score_coverage_overlap(result, _rect(10.0, 8.0), grid_resolution_m=res)


def test_degenerate_polygon_raises() -> None:
    result = place_coverage_grid(
        floor_polygon=_rect(10.0, 8.0), ceiling_height_m=3.0, ear_height_m=1.0
    )
    with pytest.raises(ValueError):
        score_coverage_overlap(
            result, [Point2(0.0, 0.0), Point2(1.0, 0.0)], grid_resolution_m=0.5
        )


def test_finer_resolution_samples_more_points() -> None:
    coarse = _score(res=1.0)
    fine = _score(res=0.25)
    assert fine.n_grid_points > coarse.n_grid_points
    assert fine.grid_resolution_m == 0.25
