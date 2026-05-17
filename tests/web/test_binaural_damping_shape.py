"""tests/web/test_binaural_damping_shape.py — P5 damping-shape ladder tests.

Unit tests for _resolve_damping_scalar covering:
  (a) 1-D passthrough
  (b) 6-band → index 2 (500 Hz)
  (c) 1-band 2-D → index 0
  (d) arbitrary band count (e.g. pra 8-band) → geometric mean fallback
  (e) 0-D (>2-D) → ValueError
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
def test_resolve_damping_arbitrary_bands_geometric_mean() -> None:
    """Arbitrary band count (e.g. pra 8-band default) collapses via geometric mean."""
    d = np.array([[0.1, 0.2], [0.4, 0.8]])  # 2 bands, 2 images
    result = _resolve_damping_scalar(d)
    expected = np.exp(np.mean(np.log(d), axis=0))
    np.testing.assert_allclose(result, expected)


@pytest.mark.web
def test_resolve_damping_8band_pra_default() -> None:
    """8-band damping (pyroomacoustics default) collapses to broadband scalar."""
    rng = np.random.default_rng(0)
    d = rng.uniform(0.05, 0.95, size=(8, 1561))
    result = _resolve_damping_scalar(d)
    assert result.shape == (1561,)
    assert np.all(result > 0)


@pytest.mark.web
def test_resolve_damping_3d_raises_value_error() -> None:
    """3-D damping (unexpected) raises ValueError."""
    d = np.ones((2, 3, 4))
    with pytest.raises(ValueError, match="unexpected damping shape"):
        _resolve_damping_scalar(d)
