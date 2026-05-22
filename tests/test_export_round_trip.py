"""v0.18 — shipped ``roomestim export`` round-trip (HIGH-2; ADR 0036 §C).

The reader aim-restore (D50) fixes a pre-existing ``roomestim export`` bug: an
explicit ``x_aim_az_deg: 0.0`` used to be silently recomputed to a toward-origin
default (e.g. ``-135.0``) on re-export because the reader dropped aim. These
gates lock the fix and the default-aim regression.

Axis-aligned fixtures (az ∈ {0,90,180,270}°, el=0, integer radius) are used for
byte-equal gates because they are single write→read→write fixed points.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pytest
import yaml

from roomestim.cli import main
from roomestim.export.layout_yaml import write_layout_yaml
from roomestim.export.room_yaml import write_room_yaml
from roomestim.io.placement_yaml_reader import read_placement_yaml
from roomestim.model import PlacedSpeaker, PlacementResult, Point3


@pytest.fixture
def lab_room_yaml(tmp_path: Path) -> Path:
    from roomestim.adapters.roomplan import RoomPlanAdapter

    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    room = RoomPlanAdapter().parse(fixture, scale_anchor=None)
    p = tmp_path / "room.yaml"
    write_room_yaml(room, p, schema_version="0.1-draft")
    return p


def _axis_layout(*, explicit_aim: bool, radius_m: float = 2.0) -> PlacementResult:
    speakers: list[PlacedSpeaker] = []
    for i, az_deg in enumerate((0.0, 90.0, 180.0, 270.0)):
        az = math.radians(az_deg)
        pos = Point3(x=radius_m * math.sin(az), y=0.0, z=radius_m * math.cos(az))
        aim = Point3(x=-pos.x, y=-pos.y, z=-pos.z) if explicit_aim else None
        speakers.append(PlacedSpeaker(channel=i + 1, position=pos, aim_direction=aim))
    return PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="CIRCULAR",
        speakers=speakers,
        layout_name="axis",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_export_default_aim_byte_equal(tmp_path: Path, lab_room_yaml: Path) -> None:
    layout_in = tmp_path / "layout.yaml"
    write_layout_yaml(_axis_layout(explicit_aim=False), layout_in, validate=False)
    out_dir = tmp_path / "out"
    rc = main(
        ["export", "--in-room", str(lab_room_yaml), "--in-placement", str(layout_in),
         "--out-dir", str(out_dir), "--no-engine-validation"]
    )
    assert rc == 0
    assert _sha(layout_in) == _sha(out_dir / "layout.yaml")


def test_export_explicit_aim_preserved(tmp_path: Path, lab_room_yaml: Path) -> None:
    layout_in = tmp_path / "layout.yaml"
    write_layout_yaml(_axis_layout(explicit_aim=True), layout_in, validate=False)
    # speaker at az=0 aims toward origin → x_aim_az_deg should be 180 (back)
    before = yaml.safe_load(layout_in.read_text(encoding="utf-8"))
    aim_before = [sp["x_aim_az_deg"] for sp in before["speakers"]]
    out_dir = tmp_path / "out"
    rc = main(
        ["export", "--in-room", str(lab_room_yaml), "--in-placement", str(layout_in),
         "--out-dir", str(out_dir), "--no-engine-validation"]
    )
    assert rc == 0
    after = yaml.safe_load((out_dir / "layout.yaml").read_text(encoding="utf-8"))
    aim_after = [sp["x_aim_az_deg"] for sp in after["speakers"]]
    assert aim_after == aim_before  # explicit aim NOT corrupted on re-export
    assert _sha(layout_in) == _sha(out_dir / "layout.yaml")


def test_export_explicit_aim_via_read_write_helper(tmp_path: Path) -> None:
    # CLI-bypass unit check: read_placement_yaml → write_layout_yaml preserves aim.
    layout_in = tmp_path / "layout.yaml"
    write_layout_yaml(_axis_layout(explicit_aim=True), layout_in, validate=False)
    loaded = read_placement_yaml(layout_in)
    assert all(s.aim_direction is not None for s in loaded.speakers)
    layout_out = tmp_path / "out.yaml"
    write_layout_yaml(loaded, layout_out, validate=False)
    assert _sha(layout_in) == _sha(layout_out)


def test_export_idempotent_second_run(tmp_path: Path, lab_room_yaml: Path) -> None:
    layout_in = tmp_path / "layout.yaml"
    write_layout_yaml(_axis_layout(explicit_aim=True), layout_in, validate=False)
    out1 = tmp_path / "o1"
    out2 = tmp_path / "o2"
    rc1 = main(
        ["export", "--in-room", str(lab_room_yaml), "--in-placement", str(layout_in),
         "--out-dir", str(out1), "--no-engine-validation"]
    )
    rc2 = main(
        ["export", "--in-room", str(lab_room_yaml), "--in-placement", str(out1 / "layout.yaml"),
         "--out-dir", str(out2), "--no-engine-validation"]
    )
    assert rc1 == 0 and rc2 == 0
    assert _sha(out1 / "layout.yaml") == _sha(out2 / "layout.yaml")
