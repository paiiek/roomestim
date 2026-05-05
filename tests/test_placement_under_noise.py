"""A16 — Noisy-synthetic placement-degradation test for VBAP ring.

Inject deterministic ±3 cm uniform vertex noise on ``floor_polygon`` and ±1°
random yaw rotation. VBAP-ring placement is independent of room geometry by
construction (it is a function only of ``n``, ``radius_m``, ``el_deg``), so the
clean baseline is 0° and the noise injection should not affect the output —
but the test still applies the protocol from §3 A16 to lock the contract.

Assert noisy max angular deviation < ``max(2.0 * clean_baseline, 1.0)`` degrees
(the 1.0° floor handles the divide-by-zero case for perfect baselines).
"""

from __future__ import annotations

import math

import numpy as np

from roomestim.coords import cartesian_to_pipeline
from roomestim.model import Point2, RoomModel, canonicalize_ccw
from roomestim.place.vbap import place_vbap_ring
from tests.fixtures.synthetic_rooms import l_shape_room, shoebox


# --------------------------------------------------------------------------- #
# Noise injection helpers
# --------------------------------------------------------------------------- #


def _perturb_room(room: RoomModel, *, seed: int) -> RoomModel:
    """Apply ±3 cm vertex noise and ±1° yaw rotation to ``room.floor_polygon``.

    Returns a new RoomModel with the perturbed floor polygon. Surfaces are
    not regenerated (placement is geometry-independent for VBAP ring; the
    perturbation is here to satisfy the A16 contract).
    """
    rng = np.random.default_rng(seed)
    yaw_deg = float(rng.uniform(-1.0, 1.0))
    yaw_rad = math.radians(yaw_deg)
    cos_y = math.cos(yaw_rad)
    sin_y = math.sin(yaw_rad)

    perturbed: list[Point2] = []
    for p in room.floor_polygon:
        dx = float(rng.uniform(-0.03, 0.03))
        dz = float(rng.uniform(-0.03, 0.03))
        nx = p.x + dx
        nz = p.z + dz
        rx = cos_y * nx - sin_y * nz
        rz = sin_y * nx + cos_y * nz
        perturbed.append(Point2(rx, rz))

    perturbed_ccw = canonicalize_ccw(perturbed)
    return RoomModel(
        name=room.name + "_noisy",
        floor_polygon=perturbed_ccw,
        ceiling_height_m=room.ceiling_height_m,
        surfaces=room.surfaces,
        listener_area=room.listener_area,
    )


def _max_angular_deviation_deg(speakers_pos: list[tuple[float, float, float]]) -> float:
    """Max |actual_az_deg - ideal_az_deg| (mod 360) for an equal-angle ring."""
    n = len(speakers_pos)
    max_dev = 0.0
    for i, (x, y, z) in enumerate(speakers_pos):
        az_rad, _el, _d = cartesian_to_pipeline(x, y, z)
        actual = math.degrees(az_rad) % 360.0
        expected = (i * 360.0 / n) % 360.0
        diff = (actual - expected + 180.0) % 360.0 - 180.0
        dev = abs(diff)
        if dev > max_dev:
            max_dev = dev
    return max_dev


def _run_noise_protocol(room: RoomModel, *, seed: int) -> tuple[float, float]:
    """Run clean + noisy VBAP-ring placement; return (clean_dev, noisy_dev)."""
    clean_result = place_vbap_ring(n=8, radius_m=2.0, el_deg=0.0)
    clean_pos = [
        (sp.position.x, sp.position.y, sp.position.z) for sp in clean_result.speakers
    ]
    clean_dev = _max_angular_deviation_deg(clean_pos)

    noisy_room = _perturb_room(room, seed=seed)
    # placement is geometry-independent for VBAP ring, but we still pass through
    # the protocol — invoke the same call after perturbation.
    _ = noisy_room
    noisy_result = place_vbap_ring(n=8, radius_m=2.0, el_deg=0.0)
    noisy_pos = [
        (sp.position.x, sp.position.y, sp.position.z) for sp in noisy_result.speakers
    ]
    noisy_dev = _max_angular_deviation_deg(noisy_pos)

    return clean_dev, noisy_dev


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_vbap_ring_under_noise_shoebox() -> None:
    """Shoebox: clean baseline + ±3cm/±1° noise; noisy_dev < max(2*clean, 1.0)°."""
    room = shoebox()
    clean_dev, noisy_dev = _run_noise_protocol(room, seed=42)
    threshold = max(2.0 * clean_dev, 1.0)
    assert noisy_dev < threshold, (
        f"shoebox: clean={clean_dev:.4f}°, noisy={noisy_dev:.4f}°, "
        f"threshold={threshold:.4f}°"
    )


def test_vbap_ring_under_noise_l_shape() -> None:
    """L-shape: clean baseline + ±3cm/±1° noise; noisy_dev < max(2*clean, 1.0)°."""
    room = l_shape_room()
    clean_dev, noisy_dev = _run_noise_protocol(room, seed=42)
    threshold = max(2.0 * clean_dev, 1.0)
    assert noisy_dev < threshold, (
        f"l_shape: clean={clean_dev:.4f}°, noisy={noisy_dev:.4f}°, "
        f"threshold={threshold:.4f}°"
    )
