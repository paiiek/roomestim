"""Tests for ``roomestim.place.wfs`` — A8."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml

from roomestim.export.layout_yaml import write_layout_yaml
from roomestim.place.wfs import c, place_wfs


# --------------------------------------------------------------------------- #
# A8 — WFS placement basics
# --------------------------------------------------------------------------- #


def test_place_wfs_basic() -> None:
    """5 m baseline @ 0.10 m spacing, f_max=1500 Hz -> 51 speakers, LINEAR."""
    result = place_wfs(
        baseline_p0=(-2.5, 0.0),
        baseline_p1=(2.5, 0.0),
        spacing_m=0.10,
        f_max_hz=1500.0,
    )
    assert result.target_algorithm == "WFS"
    assert result.regularity_hint == "LINEAR"
    assert len(result.speakers) == 51
    channels = [sp.channel for sp in result.speakers]
    assert channels == list(range(1, 52))


def test_place_wfs_alias_freq_finite_positive() -> None:
    """``wfs_f_alias_hz`` is finite, positive, equals c/(2*spacing)."""
    result = place_wfs(
        baseline_p0=(-2.5, 0.0),
        baseline_p1=(2.5, 0.0),
        spacing_m=0.10,
        f_max_hz=1500.0,
    )
    f_alias = result.wfs_f_alias_hz
    assert f_alias is not None
    assert math.isfinite(f_alias)
    assert f_alias > 0.0
    assert f_alias == pytest.approx(c / (2.0 * 0.10), abs=1e-9)
    assert f_alias == pytest.approx(1715.0, abs=1e-9)


def test_place_wfs_layout_yaml_has_x_wfs_f_alias_hz(tmp_path: Path) -> None:
    """Round-trip through layout.yaml emits top-level ``x_wfs_f_alias_hz``."""
    result = place_wfs(
        baseline_p0=(-2.5, 0.0),
        baseline_p1=(2.5, 0.0),
        spacing_m=0.10,
        f_max_hz=1500.0,
    )
    out = tmp_path / "wfs.yaml"
    write_layout_yaml(result, out)
    with out.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)
    assert "x_wfs_f_alias_hz" in loaded
    assert loaded["x_wfs_f_alias_hz"] == pytest.approx(1715.0, abs=1e-9)


def test_place_wfs_rejects_spacing_too_large() -> None:
    """spacing > c/(2*f_max) raises ValueError(kErrWfsSpacingTooLarge)."""
    # c/(2*8000) = 0.0214 m; requested 0.05 violates the bound.
    with pytest.raises(ValueError, match="kErrWfsSpacingTooLarge"):
        place_wfs(
            baseline_p0=(-1.0, 0.0),
            baseline_p1=(1.0, 0.0),
            spacing_m=0.05,
            f_max_hz=8000.0,
        )


def test_place_wfs_rejects_zero_spacing() -> None:
    """spacing_m == 0 (or negative) raises ValueError."""
    with pytest.raises(ValueError):
        place_wfs(
            baseline_p0=(-1.0, 0.0),
            baseline_p1=(1.0, 0.0),
            spacing_m=0.0,
            f_max_hz=1500.0,
        )
    with pytest.raises(ValueError):
        place_wfs(
            baseline_p0=(-1.0, 0.0),
            baseline_p1=(1.0, 0.0),
            spacing_m=-0.05,
            f_max_hz=1500.0,
        )


def test_place_wfs_speakers_along_baseline() -> None:
    """Positions x_i monotone increasing; y == height_m; z constant on baseline."""
    height = 1.20
    result = place_wfs(
        baseline_p0=(-2.5, 1.5),
        baseline_p1=(2.5, 1.5),
        spacing_m=0.10,
        f_max_hz=1500.0,
        height_m=height,
    )
    xs = [sp.position.x for sp in result.speakers]
    for i in range(1, len(xs)):
        assert xs[i] > xs[i - 1] - 1e-12, (
            f"x not monotone at i={i}: {xs[i - 1]} -> {xs[i]}"
        )
    for sp in result.speakers:
        assert sp.position.y == pytest.approx(height, abs=1e-12)
        # baseline z is constant at 1.5
        assert sp.position.z == pytest.approx(1.5, abs=1e-12)
