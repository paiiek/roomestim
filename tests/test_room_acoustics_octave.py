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
    eyring_rt60,
    eyring_rt60_per_band,
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


def test_eyring_rt60_synthetic_shoebox_closed_form() -> None:
    """eyring_rt60 matches the closed-form value for the synthetic shoebox.

    Shoebox 5x4x2.8 m (V=56), walls=WALL_PAINTED 50.4, floor=WOOD_FLOOR 20,
    ceiling=CEILING_ACOUSTIC_TILE 20.
        S_total = 90.4
        weighted_alpha = 50.4*0.05 + 20*0.10 + 20*0.55 = 15.52
        alpha_bar      = 15.52 / 90.4
        expected       = 0.161 * 56 / (-90.4 * ln(1 - alpha_bar))
    """
    import math

    sa = {
        MaterialLabel.WALL_PAINTED: 50.4,
        MaterialLabel.WOOD_FLOOR: 20.0,
        MaterialLabel.CEILING_ACOUSTIC_TILE: 20.0,
    }
    s_total = 50.4 + 20.0 + 20.0
    weighted_alpha = 50.4 * 0.05 + 20.0 * 0.10 + 20.0 * 0.55
    alpha_bar = weighted_alpha / s_total
    expected = 0.161 * 56.0 / (-s_total * math.log(1.0 - alpha_bar))
    assert eyring_rt60(56.0, sa) == pytest.approx(expected, abs=1e-9)


def test_eyring_low_absorption_converges_to_sabine() -> None:
    """At low absorption, Eyring/Sabine ratio is within ~3% (Taylor limit)."""
    # All-WALL_CONCRETE shoebox: alpha_bar at 500 Hz = 0.02.
    # Taylor: -ln(1-x) ~= x + x^2/2; for x=0.02 the deviation is ~1%.
    sa: dict[MaterialLabel, float] = {
        MaterialLabel.WALL_CONCRETE: 90.4,
    }
    e = eyring_rt60(56.0, sa)
    s = sabine_rt60(56.0, sa)
    assert abs(e / s - 1.0) < 0.03, (
        f"Eyring/Sabine ratio {e / s:.6f} deviates >3% at low alpha"
    )


def test_eyring_high_absorption_below_sabine() -> None:
    """At high absorption, Eyring is strictly less than Sabine (Vorlaender 2020 §4.2)."""
    sa = {
        MaterialLabel.CARPET: 100.0,
        MaterialLabel.CEILING_ACOUSTIC_TILE: 100.0,
    }
    # Sanity: alpha_bar = (100*0.30 + 100*0.55) / 200 = 0.425, well above 0.30.
    s_total = 200.0
    weighted_alpha = 100.0 * 0.30 + 100.0 * 0.55
    assert weighted_alpha / s_total > 0.30
    e = eyring_rt60(200.0, sa)
    s = sabine_rt60(200.0, sa)
    assert e < s, f"Eyring {e:.6f} must be < Sabine {s:.6f} at high absorption"


def test_eyring_raises_on_empty_surfaces() -> None:
    """eyring_rt60 raises ValueError on empty surfaces (S_total = 0)."""
    with pytest.raises(ValueError, match="empty|zero|S_total"):
        eyring_rt60(56.0, {})


def test_eyring_per_band_smoke() -> None:
    """eyring_rt60_per_band returns a 6-key dict of finite positive values."""
    import math

    sa = {
        MaterialLabel.WALL_PAINTED: 50.4,
        MaterialLabel.WOOD_FLOOR: 20.0,
        MaterialLabel.CEILING_ACOUSTIC_TILE: 20.0,
    }
    result = eyring_rt60_per_band(56.0, sa)
    assert set(result.keys()) == set(OCTAVE_BANDS_HZ)
    for band_hz, rt60 in result.items():
        assert rt60 > 0.0, f"Eyring RT60 at {band_hz} Hz must be positive"
        assert math.isfinite(rt60), f"Eyring RT60 at {band_hz} Hz must be finite"


def test_eyring_per_band_500hz_matches_scalar() -> None:
    """eyring_rt60_per_band[500] == eyring_rt60 (same formula at a500)."""
    sa = {
        MaterialLabel.WALL_PAINTED: 50.4,
        MaterialLabel.WOOD_FLOOR: 20.0,
        MaterialLabel.CEILING_ACOUSTIC_TILE: 20.0,
    }
    per_band = eyring_rt60_per_band(56.0, sa)
    scalar = eyring_rt60(56.0, sa)
    assert per_band[500] == pytest.approx(scalar, rel=1e-12)
