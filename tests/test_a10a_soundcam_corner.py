"""v0.9 A10a — SoundCam synthesised corner substitute (default-lane).

Three default-lane tests, one per SoundCam room (lab, living_room,
conference). Each test:

1. Loads the synthesised fixture room from
   ``tests/fixtures/soundcam_synthesized/<room_id>/`` (dims.yaml +
   GT_corners.json).
2. Builds a roomestim ``RoomModel`` via the existing shoebox path
   (``tests/fixtures/synthetic_rooms.shoebox``) using the fixture
   dimensions.
3. Compares each predicted floor-polygon corner to the cached GT corner
   (Euclidean xz distance < 10 cm).

**Honesty marker (required in 4 places — release notes + ADR 0016 +
ADR 0017 + this docstring)**:

> GT corners + RT60 derived from SoundCam paper-published dimensions;
> live-mesh corner extraction is v0.10+ upgrade path.

The cached-GT framing means this test is a fixture-integrity +
path-execution check, NOT a mesh-extraction validation. The A10b in-situ
user-lab test remains the authoritative corner-error gate per ADR 0016
§Reverse-criterion.

Building on the v0.8 default-lane convention: no ``@pytest.mark.lab``
or ``@pytest.mark.e2e``; the fixture metadata is checked into-tree at
``tests/fixtures/soundcam_synthesized/`` per v0.9 design §2.1.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import yaml

from tests.fixtures.synthetic_rooms import shoebox

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "soundcam_synthesized"

# A10a substitute corner-error tolerance: 10 cm Euclidean per ADR 0016.
CORNER_TOLERANCE_M: float = 0.10


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _load_dims(room_id: str) -> dict[str, object]:
    with (FIXTURE_ROOT / room_id / "dims.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_gt_corners(room_id: str) -> list[tuple[float, float]]:
    with (FIXTURE_ROOT / room_id / "GT_corners.json").open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return [(float(c[0]), float(c[1])) for c in data["corners_m"]]


def _euclidean_xz(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _corner_errors(room_id: str) -> list[float]:
    """Build a synthesised RoomModel for ``room_id`` and return per-corner
    Euclidean distances (m) to the cached GT corners.

    The roomestim ``shoebox`` factory generates an axis-aligned shoebox
    centred at the floor-plane origin — the same construction the GT
    corners JSON encodes — so a defect-free path produces zero error in
    machine epsilon. The tolerance allows for any future numerical drift.
    """
    dims = _load_dims(room_id)
    L = float(dims["length_m"])
    W = float(dims["width_m"])
    H = float(dims["height_m"])
    room = shoebox(width=L, depth=W, height=H, name=f"soundcam_{room_id}")

    predicted = [(p.x, p.z) for p in room.floor_polygon]
    gt = _load_gt_corners(room_id)

    # Match each predicted corner to its nearest GT corner. Both lists are
    # 4 entries (rectangular shoebox); use a one-shot greedy match (sorted
    # by minimum Euclidean) so corner ordering doesn't matter.
    remaining_gt = list(gt)
    errors: list[float] = []
    for pc in predicted:
        nearest_idx = min(
            range(len(remaining_gt)), key=lambda i: _euclidean_xz(pc, remaining_gt[i])
        )
        errors.append(_euclidean_xz(pc, remaining_gt[nearest_idx]))
        remaining_gt.pop(nearest_idx)
    return errors


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_a10a_soundcam_lab_corner_under_10cm() -> None:
    """SoundCam lab — synthesised shoebox corners within 10 cm of GT.

    Honesty marker: GT corners + RT60 derived from SoundCam paper-published
    dimensions; live-mesh corner extraction is v0.10+ upgrade path.
    """
    errors = _corner_errors("lab")
    assert len(errors) == 4, f"expected 4 corners, got {len(errors)}"
    for i, err in enumerate(errors):
        assert err <= CORNER_TOLERANCE_M, (
            f"SoundCam lab corner {i}: err={err*100:.2f} cm > "
            f"{CORNER_TOLERANCE_M*100:.0f} cm tolerance"
        )


def test_a10a_soundcam_living_room_corner_under_10cm() -> None:
    """SoundCam living_room — synthesised shoebox corners within 10 cm of GT.

    Honesty marker: GT corners + RT60 derived from SoundCam paper-published
    dimensions; live-mesh corner extraction is v0.10+ upgrade path.
    """
    errors = _corner_errors("living_room")
    assert len(errors) == 4
    for i, err in enumerate(errors):
        assert err <= CORNER_TOLERANCE_M, (
            f"SoundCam living_room corner {i}: err={err*100:.2f} cm > "
            f"{CORNER_TOLERANCE_M*100:.0f} cm tolerance"
        )


def test_a10a_soundcam_conference_corner_under_10cm() -> None:
    """SoundCam conference — synthesised shoebox corners within 10 cm of GT.

    Honesty marker: GT corners + RT60 derived from SoundCam paper-published
    dimensions; live-mesh corner extraction is v0.10+ upgrade path.
    """
    errors = _corner_errors("conference")
    assert len(errors) == 4
    for i, err in enumerate(errors):
        assert err <= CORNER_TOLERANCE_M, (
            f"SoundCam conference corner {i}: err={err*100:.2f} cm > "
            f"{CORNER_TOLERANCE_M*100:.0f} cm tolerance"
        )
