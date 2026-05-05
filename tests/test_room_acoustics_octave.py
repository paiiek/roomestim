"""Tests for octave-band absorption table and sabine_rt60_per_band (v0.3).

All invariants are deterministic — no lab fixture or network access required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from roomestim.model import (
    OCTAVE_BANDS_HZ,
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
)
from roomestim.reconstruct.materials import (
    SABINE_REFERENCE_SHOEBOX_RT60_PER_BAND_S,
    sabine_rt60,
    sabine_rt60_per_band,
)

_GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"


def test_band_a500_matches_legacy_scalar() -> None:
    """MaterialAbsorptionBands[m][2] == MaterialAbsorption[m] for every material."""
    for m in MaterialLabel:
        assert MaterialAbsorptionBands[m][2] == pytest.approx(
            MaterialAbsorption[m], rel=1e-9
        ), f"a500 mismatch for {m}"


def test_sabine_rt60_per_band_smoke() -> None:
    """Synthetic shoebox returns dict of 6 keys, all finite positive."""
    result = sabine_rt60_per_band(
        56.0,
        {
            MaterialLabel.WALL_PAINTED: 50.4,
            MaterialLabel.WOOD_FLOOR: 20.0,
            MaterialLabel.CEILING_ACOUSTIC_TILE: 20.0,
        },
    )
    assert set(result.keys()) == set(OCTAVE_BANDS_HZ)
    for band_hz, rt60 in result.items():
        assert rt60 > 0.0, f"RT60 at {band_hz} Hz must be positive"
        import math
        assert math.isfinite(rt60), f"RT60 at {band_hz} Hz must be finite"


def test_sabine_rt60_per_band_matches_synthetic_shoebox() -> None:
    """Output matches SABINE_REFERENCE_SHOEBOX_RT60_PER_BAND_S within ±1%."""
    result = sabine_rt60_per_band(
        56.0,
        {
            MaterialLabel.WALL_PAINTED: 50.4,
            MaterialLabel.WOOD_FLOOR: 20.0,
            MaterialLabel.CEILING_ACOUSTIC_TILE: 20.0,
        },
    )
    for band_hz in OCTAVE_BANDS_HZ:
        expected = SABINE_REFERENCE_SHOEBOX_RT60_PER_BAND_S[band_hz]
        actual = result[band_hz]
        assert actual == pytest.approx(expected, rel=0.01), (
            f"Band {band_hz} Hz: expected {expected:.6f}, got {actual:.6f}"
        )


def test_sabine_rt60_per_band_raises_on_zero_band_absorption() -> None:
    """sabine_rt60_per_band raises ValueError when surface_areas is empty."""
    with pytest.raises(ValueError, match="zero"):
        sabine_rt60_per_band(56.0, {})


def test_sabine_rt60_legacy_byte_equal_to_pre_v0_3_golden() -> None:
    """sabine_rt60 at v0.3 HEAD is byte-equal to the frozen pre-v0.3 golden."""
    golden_path = _GOLDEN_DIR / "sabine_legacy_rt60_500hz.txt"
    golden_str = golden_path.read_text(encoding="utf-8").strip()
    computed = sabine_rt60(
        56.0,
        {
            MaterialLabel.WALL_PAINTED: 50.4,
            MaterialLabel.WOOD_FLOOR: 20.0,
            MaterialLabel.CEILING_ACOUSTIC_TILE: 20.0,
        },
    )
    computed_str = f"{computed:.6f}"
    assert computed_str == golden_str, (
        f"sabine_rt60 output {computed_str!r} != golden {golden_str!r}; "
        "sabine_rt60 was modified — d-inv-3 violated"
    )


def test_octave_bands_hz_constant() -> None:
    """OCTAVE_BANDS_HZ equals the expected 6-band tuple."""
    assert OCTAVE_BANDS_HZ == (125, 250, 500, 1000, 2000, 4000)
