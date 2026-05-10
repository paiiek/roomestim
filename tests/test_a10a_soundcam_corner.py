"""v0.10 A10a — SoundCam synthesised corner test (revealed-tautology framing).

Two default-lane tests, one per remaining SoundCam room (lab, conference).
Living-room was removed in v0.10 (paper publishes no authoritative dims;
fabricated dims are dishonest).

**v0.10 disclosure (REQUIRED reading)**:

These tests are STRUCTURALLY TAUTOLOGICAL: GT_corners.json corners are
synthesised-from-paper-published-dims (axis-aligned shoebox); the
``shoebox(width=L, depth=W, height=H)`` factory builds the same shoebox
from the same dims; therefore the predicted corners equal the GT corners
to machine epsilon BY CONSTRUCTION. v0.9.0 advertised this as "A10a
PASS — corner err 0.00 cm" without acknowledging the tautology; v0.10
makes the tautology explicit per ADR 0018 §Consequences.

The 10 cm tolerance is preserved for forward-compatibility ONLY: when
v0.11+ swaps synthesised-shoebox GT for live-mesh-extracted GT (per
OQ-13e), this test inherits the same tolerance against substantively
different GT, at which point the test becomes non-tautological.

The substantive A10 corner gate is therefore **A10b in-situ user-lab
capture** (ADR 0016, ADR 0017, ADR 0018) — A10a substitute is now
formally a smoke-test, not a verification gate.
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
# v0.10 disclosure: tolerance is preserved for forward-compat; current
# synthesised-shoebox-vs-synthesised-shoebox comparison is 0 cm by
# construction (revealed tautology per ADR 0018).
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
    centred at the floor-plane origin — and at v0.10 the GT corners JSON
    encodes the same axis-aligned shoebox synthesised from paper-published
    dimensions — so a defect-free path produces zero error in machine
    epsilon. The tolerance allows for any future numerical drift and for
    the v0.11+ live-mesh-extraction upgrade (OQ-13e) at which point the
    comparison becomes non-tautological.
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


def test_a10a_soundcam_lab_corner_smoke() -> None:
    """SoundCam lab — synthesised shoebox corners equal GT (revealed tautology).

    v0.10 disclosure: GT corners synthesised-from-paper-dims =
    ``shoebox(L, W, H)`` corners by construction. Test is a smoke-test
    for fixture-integrity, NOT a corner-extraction validation. See
    ADR 0018 §Consequences.
    """
    errors = _corner_errors("lab")
    assert len(errors) == 4
    for i, err in enumerate(errors):
        assert err <= CORNER_TOLERANCE_M, (
            f"SoundCam lab corner {i}: err={err*100:.2f} cm > "
            f"{CORNER_TOLERANCE_M*100:.0f} cm tolerance (this is a smoke-test "
            f"failure — fixture-integrity broken since GT and prediction are "
            f"synthesised from the same dims by construction)"
        )


def test_a10a_soundcam_conference_corner_smoke() -> None:
    """SoundCam conference — synthesised shoebox corners equal GT (revealed tautology).

    v0.10 disclosure: GT corners synthesised-from-paper-dims =
    ``shoebox(L, W, H)`` corners by construction. Test is a smoke-test
    for fixture-integrity, NOT a corner-extraction validation. See
    ADR 0018 §Consequences.
    """
    errors = _corner_errors("conference")
    assert len(errors) == 4
    for i, err in enumerate(errors):
        assert err <= CORNER_TOLERANCE_M, (
            f"SoundCam conference corner {i}: err={err*100:.2f} cm > "
            f"{CORNER_TOLERANCE_M*100:.0f} cm tolerance (this is a smoke-test "
            f"failure — fixture-integrity broken since GT and prediction are "
            f"synthesised from the same dims by construction)"
        )
