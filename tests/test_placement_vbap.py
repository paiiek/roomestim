"""Tests for ``roomestim.place.vbap`` — A5 (ring) and A6 (dome)."""

from __future__ import annotations

import math

import pytest

from roomestim.coords import cartesian_to_pipeline
from roomestim.place.vbap import place_vbap_dome, place_vbap_ring


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _angular_deviation_deg(actual_deg: float, expected_deg: float) -> float:
    """Return the absolute angular deviation in degrees, mod 360."""
    diff = (actual_deg - expected_deg + 180.0) % 360.0 - 180.0
    return abs(diff)


# --------------------------------------------------------------------------- #
# A5 — VBAP ring
# --------------------------------------------------------------------------- #


def test_place_vbap_ring_n8() -> None:
    """8 equal-angle speakers; each within 1° of ideal 45°·k offset."""
    result = place_vbap_ring(n=8, radius_m=2.0, el_deg=0.0)

    assert result.target_algorithm == "VBAP"
    assert result.regularity_hint == "CIRCULAR"
    assert len(result.speakers) == 8

    # Channels 1..8 monotonic.
    channels = [sp.channel for sp in result.speakers]
    assert channels == list(range(1, 9))

    # Angular deviation < 1°.
    for i, sp in enumerate(result.speakers):
        az_rad, _el_rad, _dist = cartesian_to_pipeline(
            sp.position.x, sp.position.y, sp.position.z
        )
        actual_az_deg = math.degrees(az_rad)
        expected_az_deg = (i * 45.0) % 360.0
        # Wrap actual into [0, 360) for fair comparison.
        actual_az_deg_wrapped = actual_az_deg % 360.0
        deviation = _angular_deviation_deg(actual_az_deg_wrapped, expected_az_deg)
        assert deviation < 1.0, (
            f"speaker {i}: az={actual_az_deg_wrapped:.4f}°, "
            f"expected {expected_az_deg:.4f}°, deviation {deviation:.4f}°"
        )


def test_place_vbap_ring_radius() -> None:
    """All speakers at distance ``radius_m`` from origin within 1e-9."""
    radius = 2.5
    result = place_vbap_ring(n=12, radius_m=radius, el_deg=0.0)
    for sp in result.speakers:
        d = math.sqrt(
            sp.position.x ** 2 + sp.position.y ** 2 + sp.position.z ** 2
        )
        assert abs(d - radius) < 1e-9, f"speaker {sp.channel}: d={d}"


def test_place_vbap_ring_too_few_raises() -> None:
    """n=2 raises ValueError with kErrTooFewSpeakers."""
    with pytest.raises(ValueError, match="kErrTooFewSpeakers"):
        place_vbap_ring(n=2)


def test_place_vbap_aim_direction_defaults_to_listener() -> None:
    """Each aim_direction approx equals -position / |position|."""
    result = place_vbap_ring(n=8, radius_m=2.0, el_deg=0.0)
    for sp in result.speakers:
        norm = math.sqrt(
            sp.position.x ** 2 + sp.position.y ** 2 + sp.position.z ** 2
        )
        expected_x = -sp.position.x / norm
        expected_y = -sp.position.y / norm
        expected_z = -sp.position.z / norm
        assert sp.aim_direction is not None
        assert abs(sp.aim_direction.x - expected_x) < 1e-9
        assert abs(sp.aim_direction.y - expected_y) < 1e-9
        assert abs(sp.aim_direction.z - expected_z) < 1e-9


# --------------------------------------------------------------------------- #
# A6 — VBAP dome
# --------------------------------------------------------------------------- #


def test_place_vbap_dome() -> None:
    """8+8 dome; per-ring < 1° angular deviation; channels 1..8 lower, 9..16 upper."""
    result = place_vbap_dome(
        n_lower=8,
        n_upper=8,
        el_lower_deg=0.0,
        el_upper_deg=30.0,
        radius_m=2.0,
    )

    assert result.target_algorithm == "VBAP"
    assert result.regularity_hint == "IRREGULAR"
    assert len(result.speakers) == 16

    channels = [sp.channel for sp in result.speakers]
    assert channels == list(range(1, 17))

    # Lower ring: channels 1..8, el ≈ 0°.
    for i in range(8):
        sp = result.speakers[i]
        az_rad, el_rad, _dist = cartesian_to_pipeline(
            sp.position.x, sp.position.y, sp.position.z
        )
        assert abs(math.degrees(el_rad) - 0.0) < 1e-6, (
            f"lower ring channel {sp.channel}: el={math.degrees(el_rad)}"
        )
        actual_az = math.degrees(az_rad) % 360.0
        expected_az = (i * 45.0) % 360.0
        deviation = _angular_deviation_deg(actual_az, expected_az)
        assert deviation < 1.0, (
            f"lower ring channel {sp.channel}: dev={deviation}"
        )

    # Upper ring: channels 9..16, el ≈ 30°.
    for j in range(8):
        sp = result.speakers[8 + j]
        az_rad, el_rad, _dist = cartesian_to_pipeline(
            sp.position.x, sp.position.y, sp.position.z
        )
        assert abs(math.degrees(el_rad) - 30.0) < 1e-6, (
            f"upper ring channel {sp.channel}: el={math.degrees(el_rad)}"
        )
        actual_az = math.degrees(az_rad) % 360.0
        expected_az = (j * 45.0) % 360.0
        deviation = _angular_deviation_deg(actual_az, expected_az)
        assert deviation < 1.0, (
            f"upper ring channel {sp.channel}: dev={deviation}"
        )


def test_place_vbap_dome_too_few_raises() -> None:
    """Dome with n_lower<3 or n_upper<3 raises kErrTooFewSpeakers."""
    with pytest.raises(ValueError, match="kErrTooFewSpeakers"):
        place_vbap_dome(n_lower=2, n_upper=8)
    with pytest.raises(ValueError, match="kErrTooFewSpeakers"):
        place_vbap_dome(n_lower=8, n_upper=2)
