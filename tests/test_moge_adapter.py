"""Tests for the [moge] extra: metric single-image geometry (MoGeAdapter).

Skip-guarded via importorskip — they run where the `moge` extra (torch + MoGe
weights, git-only) is installed and skip otherwise (matching the vision/usd/audio
extra convention; the canonical miniforge gate ships a broken torchvision and no
MoGe, so these skip there). They lock the ADAPTER contract + honesty (provenance
reconstructed, materials UNKNOWN, objects=[]) + the torch-free import boundary —
NOT MoGe accuracy (that is the out-of-gate ``tests/eval/moge_image_benchmark.py``).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("moge")
pytest.importorskip("torch")

from roomestim.adapters.base import CaptureAdapter
from roomestim.adapters.moge import MoGeAdapter
from roomestim.model import MaterialLabel, RoomModel

# One real equirectangular pano (PanoContext / Stanford2D3D). Smoke tests skip
# cleanly when the external dataset is not present on this machine.
_SAMPLE_PANO = Path(
    "/home/seung/mmhoa/spike-image-geometry/panocontext_data/pano_s2d3d/"
    "train/img/camera_0004591bfdc749a88db196a5d8b345cb_office_6_frame_"
    "equirectangular_domain_.png"
)


def test_satisfies_capture_adapter_protocol() -> None:
    assert isinstance(MoGeAdapter(), CaptureAdapter)


@pytest.mark.moge
@pytest.mark.skipif(not _SAMPLE_PANO.exists(), reason="sample pano not present")
def test_parse_returns_honest_room_model() -> None:
    adapter = MoGeAdapter()
    with pytest.warns(UserWarning):  # experimental-tier disclosure
        room = adapter.parse(_SAMPLE_PANO)

    assert isinstance(room, RoomModel)
    # Geometry is image-reconstructed (no depth sensor).
    assert room.provenance == "reconstructed"
    # No visual material inference: every surface is UNKNOWN.
    assert all(s.material == MaterialLabel.UNKNOWN for s in room.surfaces)
    # No furniture detection.
    assert room.objects == []
    # A plausible, positive ceiling height and a closed (>=3 corner) footprint.
    assert room.ceiling_height_m > 0.0
    assert len(room.floor_polygon) >= 3
    # The fusion diagnostics are recorded as the honesty side-channel.
    diag = adapter.last_diagnostics
    assert diag["n_crops"] >= 1
    assert diag["n_points_fused"] > 0


@pytest.mark.moge
@pytest.mark.skipif(not _SAMPLE_PANO.exists(), reason="sample pano not present")
def test_scale_anchor_ignored_with_warning() -> None:
    """A supplied scale_anchor is accepted but IGNORED (MoGe is metric) + warns."""
    from roomestim.adapters.base import ScaleAnchor

    adapter = MoGeAdapter()
    with pytest.warns(UserWarning, match="IGNORED"):
        room = adapter.parse(
            _SAMPLE_PANO, scale_anchor=ScaleAnchor("known_distance", 1.6)
        )
    assert room.ceiling_height_m > 0.0


def test_core_import_does_not_pull_torch() -> None:
    """`import roomestim` and `import roomestim.adapters.moge` must NOT import
    torch/moge — the heavy deps are lazy, keeping the core boundary torch-free."""
    code = (
        "import sys; import roomestim; import roomestim.adapters.moge; "
        "assert 'torch' not in sys.modules, 'torch eagerly imported'; "
        "assert 'moge' not in sys.modules, 'moge eagerly imported'; "
        "print('ok')"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout
