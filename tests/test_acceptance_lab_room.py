"""A10 — Lab-room acceptance gate (manual; requires real fixture files).

Marked ``@pytest.mark.lab``. Skipped automatically in CI if the real fixture
files are absent (decisions.md D8/D9).

Required files:
    tests/fixtures/lab_real.usdz              -- real RoomPlan capture
    tests/fixtures/lab_real_groundtruth.yaml  -- ground-truth speaker layout

See ``tests/fixtures/lab_real_groundtruth.yaml.template`` for the GT YAML
schema and the field set this test consumes.

Tolerances (decisions.md D8):
    * Azimuth:         ±5° per speaker
    * Radial distance: ±0.10 m per speaker
    * Room corner:     <0.10 m per corner
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
import yaml

_FIXTURES = Path(__file__).parent / "fixtures"
_USDZ = _FIXTURES / "lab_real.usdz"
_GT_YAML = _FIXTURES / "lab_real_groundtruth.yaml"

_SKIP = not (_USDZ.exists() and _GT_YAML.exists())
_SKIP_REASON = (
    "lab_real.usdz or lab_real_groundtruth.yaml not present "
    "(manual fixture; not committed to CI)"
)


@pytest.mark.lab
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_acceptance_lab_room(tmp_path: Path) -> None:
    """Parse real lab USDZ, run VBAP placement, compare against ground truth."""
    from roomestim.adapters.roomplan import RoomPlanAdapter
    from roomestim.export.layout_yaml import write_layout_yaml
    from roomestim.export.room_yaml import write_room_yaml
    from roomestim.place.vbap import place_vbap_ring

    # Parse
    adapter = RoomPlanAdapter()
    room = adapter.parse(_USDZ)

    # Place
    n_speakers = 8
    layout_radius = 2.0
    result = place_vbap_ring(n_speakers, radius_m=layout_radius, el_deg=0.0)

    # Write (smoke-check idempotency)
    write_room_yaml(room, tmp_path / "room.yaml")
    write_layout_yaml(result, tmp_path / "layout.yaml")

    # Load ground truth
    with _GT_YAML.open("r", encoding="utf-8") as fh:
        gt: dict[str, Any] = yaml.safe_load(fh)

    gt_speakers: list[dict[str, Any]] = gt.get("speakers", [])
    assert len(gt_speakers) == n_speakers, (
        f"Ground truth has {len(gt_speakers)} speakers; expected {n_speakers}"
    )

    # Per-speaker angle and radial checks
    from roomestim.coords import cartesian_to_pipeline

    for sp, gt_sp in zip(result.speakers, gt_speakers):
        az_rad, el_rad, dist_m = cartesian_to_pipeline(
            sp.position.x, sp.position.y, sp.position.z
        )
        az_deg = math.degrees(az_rad)
        gt_az = float(gt_sp["az_deg"])
        gt_dist = float(gt_sp["dist_m"])

        az_err = abs(az_deg - gt_az)
        # Wrap to [0, 180]
        if az_err > 180.0:
            az_err = 360.0 - az_err
        assert az_err <= 5.0, (
            f"Speaker {sp.channel}: az error {az_err:.2f}° > 5°"
        )
        assert abs(dist_m - gt_dist) <= 0.10, (
            f"Speaker {sp.channel}: radial error {abs(dist_m - gt_dist):.3f} m > 0.10 m"
        )

    # Room corner check
    gt_corners: list[dict[str, float]] = gt.get("room", {}).get("corner_positions", [])
    if gt_corners:
        room_corners = room.floor_polygon
        assert len(room_corners) == len(gt_corners), (
            f"Room polygon has {len(room_corners)} corners; GT has {len(gt_corners)}"
        )
        for i, (rc, gc) in enumerate(zip(room_corners, gt_corners)):
            err = math.sqrt((rc.x - gc["x"]) ** 2 + (rc.z - gc["z"]) ** 2)
            assert err < 0.10, (
                f"Corner {i}: position error {err:.3f} m >= 0.10 m"
            )
