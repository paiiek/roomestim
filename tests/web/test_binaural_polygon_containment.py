"""tests/web/test_binaural_polygon_containment.py — P5 polygon-containment guard.

Tests for _image_inside_floor helper: unit-level containment checks on an
L-shaped 6-vertex floor polygon.
"""
from __future__ import annotations

import pytest

pytest.importorskip("shapely")

from roomestim_web.binaural import _image_inside_floor


# ---------------------------------------------------------------------------
# Minimal Point2 stub — needs only .x and .z attributes
# ---------------------------------------------------------------------------


class _P2:
    def __init__(self, x: float, z: float) -> None:
        self.x = x
        self.z = z


# L-shape: [(0,0), (4,0), (4,2), (2,2), (2,4), (0,4)]
# The convex bite (missing rectangle) is x∈[2,4], z∈[2,4].
_L_FLOOR = [
    _P2(0, 0),
    _P2(4, 0),
    _P2(4, 2),
    _P2(2, 2),
    _P2(2, 4),
    _P2(0, 4),
]


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


@pytest.mark.web
def test_image_inside_floor_outside_bite() -> None:
    """Point (3, 3) is inside the cut-out corner — must be False."""
    assert _image_inside_floor((3.0, 3.0), _L_FLOOR) is False


@pytest.mark.web
def test_image_inside_floor_inside_body() -> None:
    """Point (1, 1) is well inside the lower-left body — must be True."""
    assert _image_inside_floor((1.0, 1.0), _L_FLOOR) is True


@pytest.mark.web
def test_image_inside_floor_upper_arm() -> None:
    """Point (1, 3) is inside the upper-left arm of the L — must be True."""
    assert _image_inside_floor((1.0, 3.0), _L_FLOOR) is True


@pytest.mark.web
def test_image_inside_floor_far_outside() -> None:
    """Point (5, 5) is entirely outside the polygon — must be False."""
    assert _image_inside_floor((5.0, 5.0), _L_FLOOR) is False


@pytest.mark.web
def test_image_inside_floor_right_arm_edge() -> None:
    """Point (3, 1) is in the lower-right arm of the L (below the bite) — must be True."""
    assert _image_inside_floor((3.0, 1.0), _L_FLOOR) is True
