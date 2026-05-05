"""A11 — Sabine RT60 estimate against Vorlaender 2020 Appx A reference."""

from __future__ import annotations

import pytest

from roomestim.model import MaterialAbsorption, MaterialLabel
from roomestim.reconstruct.materials import (
    SABINE_REFERENCE_SHOEBOX_RT60_S,
    sabine_rt60,
)


def test_sabine_constant_matches_vorlander_appendix_a() -> None:
    """A11 — synthetic shoebox RT60 within +-10 % of textbook Sabine.

    Synthetic shoebox 5 x 4 x 2.8 m with Vorlaender 2020 Appx A coefficients:
        walls (painted)            : 50.4 m^2 @ a=0.05 -> 2.520 sabins
        floor (wood)               : 20.0 m^2 @ a=0.10 -> 2.000 sabins
        ceiling (acoustic tile)    : 20.0 m^2 @ a=0.55 -> 11.00 sabins
        total absorption                              -> 15.52 sabins
        V = 56 m^3
        RT60 = 0.161 * 56 / 15.52 ~= 0.581 s
    """
    rt60 = sabine_rt60(
        volume_m3=56.0,
        surface_areas={
            MaterialLabel.WALL_PAINTED: 50.4,
            MaterialLabel.WOOD_FLOOR: 20.0,
            MaterialLabel.CEILING_ACOUSTIC_TILE: 20.0,
        },
    )

    lower = SABINE_REFERENCE_SHOEBOX_RT60_S * 0.9
    upper = SABINE_REFERENCE_SHOEBOX_RT60_S * 1.1
    assert lower <= rt60 <= upper, (
        f"sabine_rt60 = {rt60:.4f} s outside [{lower:.4f}, {upper:.4f}] "
        f"(reference {SABINE_REFERENCE_SHOEBOX_RT60_S:.4f} s +-10%)"
    )

    # Unit-self-consistency guard: SABINE_REFERENCE_SHOEBOX_RT60_S must
    # itself match the closed-form Sabine value within 1 %.
    closed_form = 0.161 * 56.0 / 15.52
    assert SABINE_REFERENCE_SHOEBOX_RT60_S == pytest.approx(
        closed_form, rel=0.01
    ), (
        f"SABINE_REFERENCE_SHOEBOX_RT60_S={SABINE_REFERENCE_SHOEBOX_RT60_S} "
        f"drifted from closed form {closed_form:.4f} s"
    )


def test_sabine_rt60_function_smoke() -> None:
    """Empty surface set -> ValueError (cannot compute finite RT60)."""
    with pytest.raises(ValueError):
        sabine_rt60(volume_m3=56.0, surface_areas={})


def test_sabine_uses_vorlander_table() -> None:
    """Vorlaender 2020 Appx A absorption coefficients are pinned."""
    assert MaterialAbsorption[MaterialLabel.WALL_PAINTED] == 0.05
    assert MaterialAbsorption[MaterialLabel.WOOD_FLOOR] == 0.10
    assert MaterialAbsorption[MaterialLabel.CEILING_ACOUSTIC_TILE] == 0.55
