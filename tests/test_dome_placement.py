"""Dome dispatch wiring — ``run_placement(room, "dome", ...)`` (v0.60.0).

Geometry-only tests for the ``dome`` branch of ``roomestim.place.dispatch``.
The dome is two stacked equal-angle VBAP rings (``place_vbap_dome``); the single
``n_speakers`` is split lower=(n+1)//2 / upper=n//2 (lower gets the odd extra),
the lower ring sits at 0° and the upper ring is tilted by ``el_deg`` (0 → 30°
default). No acoustic numbers are asserted — geometry only.
"""

from __future__ import annotations

import math

import pytest

from roomestim.model import ListenerArea, Point2, RoomModel
from roomestim.place.dispatch import run_placement


def _room() -> RoomModel:
    # dome is geometry-blind; this minimal room is never consumed.
    return RoomModel(
        name="t",
        floor_polygon=[
            Point2(0.0, 0.0),
            Point2(4.0, 0.0),
            Point2(4.0, 4.0),
            Point2(0.0, 4.0),
        ],
        ceiling_height_m=3.0,
        surfaces=[],
        listener_area=ListenerArea(
            polygon=[
                Point2(1.0, 1.0),
                Point2(3.0, 1.0),
                Point2(3.0, 3.0),
                Point2(1.0, 3.0),
            ],
            centroid=Point2(2.0, 2.0),
            height_m=1.2,
        ),
    )


def _finite(v: float) -> bool:
    return math.isfinite(v)


def test_dome_n8_splits_4_4() -> None:
    res = run_placement(_room(), "dome", 8, 2.0, 30.0)
    assert res.target_algorithm == "VBAP"
    assert res.regularity_hint == "IRREGULAR"
    assert len(res.speakers) == 8
    # All positions finite.
    for s in res.speakers:
        assert _finite(s.position.x) and _finite(s.position.y) and _finite(s.position.z)
    # Lower ring (channels 1..4) at y≈0; upper ring (channels 5..8) lifted.
    lower = [s for s in res.speakers if s.channel <= 4]
    upper = [s for s in res.speakers if s.channel >= 5]
    assert len(lower) == 4 and len(upper) == 4
    assert all(abs(s.position.y) < 1e-9 for s in lower)
    assert all(s.position.y > 0.0 for s in upper)


def test_dome_n7_splits_4_3() -> None:
    """Odd count: lower ring gets the extra speaker (4 lower + 3 upper)."""
    res = run_placement(_room(), "dome", 7, 2.0, 30.0)
    assert len(res.speakers) == 7
    lower = [s for s in res.speakers if abs(s.position.y) < 1e-9]
    upper = [s for s in res.speakers if s.position.y > 1e-9]
    assert len(lower) == 4
    assert len(upper) == 3


def test_dome_below_six_raises() -> None:
    with pytest.raises(ValueError, match=r"dome requires n_speakers>=6"):
        run_placement(_room(), "dome", 5, 2.0, 30.0)


def test_dome_el_deg_tilts_upper_ring() -> None:
    """A positive el_deg lifts the upper ring above the lower ring's height."""
    res = run_placement(_room(), "dome", 8, 2.0, 45.0)
    lower = [s for s in res.speakers if s.channel <= 4]
    upper = [s for s in res.speakers if s.channel >= 5]
    max_lower_y = max(s.position.y for s in lower)
    min_upper_y = min(s.position.y for s in upper)
    assert min_upper_y > max_lower_y
    # 45° tilt at radius 2.0 → upper-ring y ≈ 2.0*sin(45°) ≈ 1.414.
    assert all(s.position.y == pytest.approx(2.0 * math.sin(math.radians(45.0)), abs=1e-6) for s in upper)


def test_dome_zero_el_deg_uses_default_30() -> None:
    """el_deg<=0 falls back to a sensible 30° upper-ring tilt (not flat)."""
    res = run_placement(_room(), "dome", 8, 2.0, 0.0)
    upper = [s for s in res.speakers if s.channel >= 5]
    expected_y = 2.0 * math.sin(math.radians(30.0))
    assert all(s.position.y == pytest.approx(expected_y, abs=1e-6) for s in upper)
