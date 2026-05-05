"""A4 — Coordinate-frame contract.

All az_deg / el_deg / xyz values follow spatial_engine/docs/coordinate_convention.md
(RIGHT = +az, UP = +el, z = front). This file is the unconditional gate. The
A15 cross-process parity test (test_coords_engine_parity.py) gates only when
SPATIAL_ENGINE_BUILD_DIR is set.
"""

from __future__ import annotations

import math

import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HAVE_HYPOTHESIS = True
except ImportError:  # pragma: no cover — dev extra not installed
    HAVE_HYPOTHESIS = False

from roomestim.coords import (
    ambix_to_pipeline,
    cartesian_to_pipeline,
    image_y_to_listener_el,
    pipeline_to_ambix,
    stereo_pan_from_pipeline_az,
    yaml_speaker_to_cartesian,
)


# ----- Static identity / sign cases -----


def test_pipeline_ambix_round_trip_static() -> None:
    az_pipe, el_pipe = 0.5, 0.2
    az_a, el_a = pipeline_to_ambix(az_pipe, el_pipe)
    az_back, el_back = ambix_to_pipeline(az_a, el_a)
    assert math.isclose(az_back, az_pipe, abs_tol=1e-12)
    assert math.isclose(el_back, el_pipe, abs_tol=1e-12)
    # Sign convention: pipeline RIGHT=+az -> AmbiX flips az only.
    assert math.isclose(az_a, -az_pipe, abs_tol=1e-12)
    assert math.isclose(el_a, el_pipe, abs_tol=1e-12)


def test_yaml_to_cartesian_axes() -> None:
    # Front: az=0, el=0 -> (0, 0, dist).
    x, y, z = yaml_speaker_to_cartesian(0.0, 0.0, 1.0)
    assert math.isclose(x, 0.0, abs_tol=1e-9)
    assert math.isclose(y, 0.0, abs_tol=1e-9)
    assert math.isclose(z, 1.0, abs_tol=1e-9)
    # Right: az=+90 deg, el=0 -> (1, 0, 0).
    x, y, z = yaml_speaker_to_cartesian(90.0, 0.0, 1.0)
    assert math.isclose(x, 1.0, abs_tol=1e-9)
    assert math.isclose(y, 0.0, abs_tol=1e-9)
    assert math.isclose(z, 0.0, abs_tol=1e-9)
    # Up: az=0, el=+90 deg -> (0, 1, 0).
    x, y, z = yaml_speaker_to_cartesian(0.0, 90.0, 1.0)
    assert math.isclose(x, 0.0, abs_tol=1e-9)
    assert math.isclose(y, 1.0, abs_tol=1e-9)
    assert math.isclose(z, 0.0, abs_tol=1e-9)


def test_cartesian_to_pipeline_axes() -> None:
    # Front: (0, 0, 1) -> az=0, el=0, dist=1.
    az, el, dist = cartesian_to_pipeline(0.0, 0.0, 1.0)
    assert math.isclose(az, 0.0, abs_tol=1e-9)
    assert math.isclose(el, 0.0, abs_tol=1e-9)
    assert math.isclose(dist, 1.0, abs_tol=1e-9)
    # Right: (1, 0, 0) -> az=+pi/2.
    az, el, dist = cartesian_to_pipeline(1.0, 0.0, 0.0)
    assert math.isclose(az, math.pi / 2, abs_tol=1e-9)
    assert math.isclose(el, 0.0, abs_tol=1e-9)
    # Up: (0, 1, 0) -> el=+pi/2.
    az, el, dist = cartesian_to_pipeline(0.0, 1.0, 0.0)
    assert math.isclose(el, math.pi / 2, abs_tol=1e-9)


def test_image_y_to_listener_el_signs() -> None:
    # Image y > 0 (below horizon) -> negative elevation.
    assert image_y_to_listener_el(0.5) < 0
    assert image_y_to_listener_el(-0.5) > 0
    assert math.isclose(image_y_to_listener_el(0.0), 0.0, abs_tol=1e-12)


def test_stereo_pan_sign_lock() -> None:
    """Anti-regression for the 2026-03-01 sin(-az) bug.

    Pipeline RIGHT (+az) -> sin > 0 -> right channel louder.
    """
    assert stereo_pan_from_pipeline_az(math.pi / 4) > 0  # right
    assert stereo_pan_from_pipeline_az(-math.pi / 4) < 0  # left
    assert math.isclose(stereo_pan_from_pipeline_az(0.0), 0.0, abs_tol=1e-12)


# ----- Hypothesis property: yaml_to_cartesian -> cartesian_to_pipeline -----


if HAVE_HYPOTHESIS:

    @given(
        az_deg=st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False),
        el_deg=st.floats(min_value=-89.999, max_value=89.999, allow_nan=False, allow_infinity=False),
        dist_m=st.floats(min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200, deadline=None)
    def test_yaml_to_cartesian_to_pipeline_round_trip(
        az_deg: float, el_deg: float, dist_m: float
    ) -> None:
        x, y, z = yaml_speaker_to_cartesian(az_deg, el_deg, dist_m)
        az_pipe, el_pipe, dist_back = cartesian_to_pipeline(x, y, z)
        # Pipeline az matches yaml az (both RIGHT=+az; pipeline returns radians).
        assert math.isclose(az_pipe, math.radians(az_deg), abs_tol=1e-4) or math.isclose(
            abs(az_pipe), math.pi, abs_tol=1e-4
        )
        assert math.isclose(el_pipe, math.radians(el_deg), abs_tol=1e-4)
        assert math.isclose(dist_back, dist_m, rel_tol=1e-6, abs_tol=1e-6)

else:  # pragma: no cover — dev extra not installed

    def test_yaml_to_cartesian_to_pipeline_round_trip() -> None:
        pytest.skip("hypothesis not installed; install with `pip install -e .[dev]`")
