"""tests/web/test_binaural_damping_shape.py — P5 damping-shape ladder tests.

Unit tests for _resolve_damping_scalar covering:
  (a) 1-D passthrough
  (b) 6-band → index 2 (500 Hz)
  (c) 1-band 2-D → index 0
  (d) 3-band → ValueError
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pyroomacoustics")

from roomestim_web.binaural import _resolve_damping_scalar


@pytest.mark.web
def test_resolve_damping_1d_passthrough() -> None:
    """1-D damping array (shape (N,)) is returned unchanged."""
    d = np.array([0.5, 0.4, 0.3])
    result = _resolve_damping_scalar(d)
    np.testing.assert_array_equal(result, d)


@pytest.mark.web
def test_resolve_damping_6band_picks_index2() -> None:
    """6-band 2-D damping (shape (6, N)) returns row 2 (≈500 Hz band)."""
    d = np.arange(18, dtype=float).reshape(6, 3)
    result = _resolve_damping_scalar(d)
    np.testing.assert_array_equal(result, d[2])


@pytest.mark.web
def test_resolve_damping_1band_2d_picks_index0() -> None:
    """1-band 2-D damping (shape (1, N)) returns row 0."""
    d = np.array([[0.5, 0.4, 0.3]])  # shape (1, 3)
    result = _resolve_damping_scalar(d)
    np.testing.assert_array_equal(result, d[0])


@pytest.mark.web
def test_resolve_damping_3band_raises_value_error() -> None:
    """Unexpected 3-band 2-D damping raises ValueError."""
    d = np.ones((3, 5))
    with pytest.raises(ValueError, match="unexpected damping band count"):
        _resolve_damping_scalar(d)
