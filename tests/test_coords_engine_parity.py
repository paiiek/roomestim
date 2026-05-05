"""A15 acceptance — Python coords vs engine C++ coords parity.

When ``SPATIAL_ENGINE_BUILD_DIR`` is set AND a ``coords_parity_harness`` binary
exists inside it, drive ≥1000 Hypothesis-generated ``(az_deg, el_deg, dist_m)``
triples through the harness and compare against
``roomestim.coords.yaml_speaker_to_cartesian`` + ``cartesian_to_pipeline`` to
≤1e-5 absolute on each component. Otherwise, the entire module SKIPs cleanly.

Harness contract (one triple per invocation):

    $ <BUILD_DIR>/coords_parity_harness <az_deg> <el_deg> <dist_m>
    <x> <y> <z> <az_pipe> <el_pipe> <dist_pipe>

All values whitespace-separated on a single stdout line. Returncode 0.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HAVE_HYPOTHESIS = True
except ImportError:  # pragma: no cover — dev extra not installed
    HAVE_HYPOTHESIS = False

from roomestim.coords import cartesian_to_pipeline, yaml_speaker_to_cartesian


_BUILD_DIR = os.environ.get("SPATIAL_ENGINE_BUILD_DIR")
_HARNESS: str | None = None
if _BUILD_DIR:
    candidate = Path(_BUILD_DIR) / "coords_parity_harness"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        _HARNESS = str(candidate)
    else:
        which = shutil.which("coords_parity_harness", path=str(Path(_BUILD_DIR)))
        if which is not None:
            _HARNESS = which

if _HARNESS is None:
    if _BUILD_DIR:
        _skip_reason = (
            f"SPATIAL_ENGINE_BUILD_DIR={_BUILD_DIR} present but "
            "coords_parity_harness not built — see .omc/plans/decisions.md D10 "
            "(deferred to spatial_engine v0.2)"
        )
    else:
        _skip_reason = (
            "SPATIAL_ENGINE_BUILD_DIR unset — see .omc/plans/decisions.md D10"
        )
    pytest.skip(_skip_reason, allow_module_level=True)

if not HAVE_HYPOTHESIS:  # pragma: no cover — dev extra not installed
    pytest.skip("hypothesis not installed", allow_module_level=True)


def _run_harness(az_deg: float, el_deg: float, dist_m: float) -> tuple[float, ...]:
    assert _HARNESS is not None  # for mypy
    proc = subprocess.run(
        [_HARNESS, repr(az_deg), repr(el_deg), repr(dist_m)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"coords_parity_harness rc={proc.returncode} "
            f"stderr={proc.stderr!r} stdout={proc.stdout!r}"
        )
    parts = proc.stdout.strip().split()
    if len(parts) != 6:
        raise RuntimeError(
            f"expected 6 floats from harness; got {parts!r}"
        )
    return tuple(float(p) for p in parts)


@given(
    az_deg=st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False),
    el_deg=st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False),
    dist_m=st.floats(min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=1000, deadline=None)
def test_coords_parity_with_engine(az_deg: float, el_deg: float, dist_m: float) -> None:
    cx, cy, cz = yaml_speaker_to_cartesian(az_deg, el_deg, dist_m)
    az_pipe, el_pipe, dist_pipe = cartesian_to_pipeline(cx, cy, cz)
    py = (cx, cy, cz, az_pipe, el_pipe, dist_pipe)

    cpp = _run_harness(az_deg, el_deg, dist_m)
    for i, (p, c) in enumerate(zip(py, cpp)):
        assert abs(p - c) <= 1e-5, (
            f"component {i} drift: py={p!r} cpp={c!r} delta={p - c!r} "
            f"input=({az_deg}, {el_deg}, {dist_m})"
        )
