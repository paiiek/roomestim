"""Real-model golden regression for the image backend (``vision``-marked).

Every other in-gate image test is torch-free (synthetic ``cor_id``); the real
torch path :func:`roomestim.adapters.image._infer_corners` (vendored HorizonNet)
is otherwise unguarded. This test runs that real path on a vendored procedural
pano (``tests/fixtures/image/roomA_synth_pano.png``) and locks the output.

It SKIPS cleanly when the vision stack is unavailable — notably the canonical
miniforge env has torch but a BROKEN torchvision (``operator torchvision::nms
does not exist`` is a ``RuntimeError``, not ``ImportError``), so the guard must
catch broad ``Exception``. Run it in the ``[vision]`` extra venv with the
HorizonNet checkpoint reachable (``ROOMESTIM_HORIZONNET_CKPT`` or network).

Captured golden (deterministic to 1e-4 across runs), ScaleAnchor
``known_distance``=1.6 m::

    width_x = 4.7327, depth_z = 3.9647, ceiling_height_m = 3.1528,
    provenance = reconstructed, materials = {UNKNOWN}, objects = [],
    n_surfaces = 6 (floor + ceiling + 4 walls).

Ground truth is W=4.0 D=3.0 H=2.7 m → est error ≈ +73/+96/+45 cm: this is
ROUGH, NOT install-grade. This test is a determinism / regression lock on the
real inference path, NOT an accuracy claim.
"""

from __future__ import annotations

import subprocess
import sys
import warnings
from pathlib import Path

import pytest

from roomestim.adapters.base import ScaleAnchor
from roomestim.adapters.image import ImageAdapter
from roomestim.model import MaterialLabel

# Probed in a SUBPROCESS so the import never pollutes the parent's
# ``sys.modules``: the torch-free boundary tests (gate #4) assert
# ``"torch" not in sys.modules`` in-process, and this guard runs at collection
# time, so an in-process ``import torch`` here would break the default gate.
_VISION_PROBE = (
    "import torch, torchvision, roomestim.vision.horizonnet.model"  # noqa: F401
)


def _vision_stack_available() -> bool:
    """True only if torch, torchvision, and HorizonNet import cleanly.

    The probe runs in a child process and catches broad failures: a broken
    torchvision raises a ``RuntimeError`` (``operator torchvision::nms does not
    exist``) at import, not an ``ImportError``, and that must still gate this
    test to a skip. A non-zero child exit (any import error) → unavailable.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-c", _VISION_PROBE],
            capture_output=True,
            timeout=60,
        )
    except Exception:
        return False
    return result.returncode == 0


@pytest.mark.vision
@pytest.mark.skipif(
    not _vision_stack_available(),
    reason="vision stack (torch+torchvision+HorizonNet) unavailable",
)
def test_image_backend_real_model_golden() -> None:
    pano = Path(__file__).parent / "fixtures" / "image" / "roomA_synth_pano.png"
    if not pano.is_file():
        pytest.skip(f"synthetic pano fixture missing: {pano}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            room = ImageAdapter().parse(
                pano, scale_anchor=ScaleAnchor("known_distance", 1.6)
            )
        except (OSError, ConnectionError, ImportError) as exc:
            # No ROOMESTIM_HORIZONNET_CKPT and offline → resolve_checkpoint
            # fails; skip rather than fail.
            pytest.skip(f"HorizonNet weights unavailable (offline / no ckpt): {exc}")

    # Honesty invariants (rough-tier reconstruction; ADR 0046).
    assert room.provenance == "reconstructed"
    for surf in room.surfaces:
        assert surf.material == MaterialLabel.UNKNOWN
    assert room.objects == []

    assert len(room.surfaces) == 6
    assert sum(1 for s in room.surfaces if s.kind == "wall") == 4

    # Regression lock to the captured golden. GT is W=4.0 D=3.0 H=2.7 m; the
    # estimate is ROUGH (err ≈ 45-96 cm), so these are determinism anchors, not
    # accuracy bars. On a fixed env the output is deterministic to ~1e-4, so the
    # abs=0.2 m here is NOT slack for this machine — it is a deliberate
    # CROSS-MACHINE jitter bound (CPU / torchvision build variation) chosen so
    # the lock stays portable across the [vision] stacks this may run under.
    # The load-bearing exact asserts are the honesty invariants above
    # (provenance / materials / objects / n_surfaces); these dimensional checks
    # only guard against gross regression of the real inference path.
    xs = [p.x for p in room.floor_polygon]
    zs = [p.z for p in room.floor_polygon]
    width_x = max(xs) - min(xs)
    depth_z = max(zs) - min(zs)

    assert width_x == pytest.approx(4.7327, abs=0.2)
    assert depth_z == pytest.approx(3.9647, abs=0.2)
    assert room.ceiling_height_m == pytest.approx(3.1528, abs=0.2)
