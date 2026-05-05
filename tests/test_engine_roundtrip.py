"""A2 acceptance — engine round-trip.

When ``SPATIAL_ENGINE_BUILD_DIR`` is set AND a ``layout_loader_smoke`` binary
exists inside it, write a 3-speaker CIRCULAR ``layout.yaml`` and subprocess-
invoke the smoke binary; expect returncode 0 and stdout containing ``OK``.
Otherwise, the entire module SKIPs cleanly (no collection failure).
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from roomestim.export import write_layout_yaml
from roomestim.model import PlacedSpeaker, PlacementResult, Point3


_BUILD_DIR = os.environ.get("SPATIAL_ENGINE_BUILD_DIR")
_SMOKE_BIN: str | None = None
if _BUILD_DIR:
    candidate = Path(_BUILD_DIR) / "layout_loader_smoke"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        _SMOKE_BIN = str(candidate)
    else:
        # Fall back to PATH-relative discovery within the build dir.
        which = shutil.which("layout_loader_smoke", path=str(Path(_BUILD_DIR)))
        if which is not None:
            _SMOKE_BIN = which

if _SMOKE_BIN is None:
    if _BUILD_DIR:
        _skip_reason = (
            f"SPATIAL_ENGINE_BUILD_DIR={_BUILD_DIR} present but "
            "layout_loader_smoke not built — see .omc/plans/decisions.md D10 "
            "(deferred to spatial_engine v0.2)"
        )
    else:
        _skip_reason = (
            "SPATIAL_ENGINE_BUILD_DIR unset — see .omc/plans/decisions.md D10"
        )
    pytest.skip(_skip_reason, allow_module_level=True)


def _circular_3_speakers(radius_m: float = 2.0) -> list[PlacedSpeaker]:
    out: list[PlacedSpeaker] = []
    for i, az_deg in enumerate((0.0, 120.0, 240.0)):
        az = math.radians(az_deg)
        out.append(
            PlacedSpeaker(
                channel=i + 1,
                position=Point3(
                    x=radius_m * math.sin(az),
                    y=0.0,
                    z=radius_m * math.cos(az),
                ),
            )
        )
    return out


def test_engine_loads_yaml(tmp_path: Path) -> None:
    result = PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="CIRCULAR",
        speakers=_circular_3_speakers(),
        layout_name="roundtrip_circular_3",
    )
    yaml_path = tmp_path / "layout.yaml"
    write_layout_yaml(result, yaml_path)

    assert _SMOKE_BIN is not None  # for mypy
    proc = subprocess.run(
        [_SMOKE_BIN, str(yaml_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"layout_loader_smoke failed: returncode={proc.returncode} "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert "OK" in proc.stdout, f"expected 'OK' in stdout; got {proc.stdout!r}"
