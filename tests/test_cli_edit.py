"""v0.18 — CLI ``roomestim edit`` subcommand (ADR 0036 §A/§D; Phase 4).

read → nudge → re-validate (collector) → write + unified diff. Flag→kwarg map:
--daz→daz_deg, --del-deg→del_deg, --ddist→ddist_m, --dx/--dy/--dz→dx/dy/dz.
``--del`` alone is invalid Python (args.del) — the spelling is always --del-deg.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from roomestim.cli import main
from roomestim.export.layout_yaml import write_layout_yaml
from roomestim.io.placement_yaml_reader import read_placement_yaml
from roomestim.model import PlacedSpeaker, PlacementResult, Point3


def _write_fixture(path: Path, *, algorithm: str = "VBAP") -> None:
    speakers: list[PlacedSpeaker] = []
    for i, az_deg in enumerate((0.0, 90.0, 180.0, 270.0)):
        az = math.radians(az_deg)
        speakers.append(
            PlacedSpeaker(
                channel=i + 1,
                position=Point3(x=2.0 * math.sin(az), y=0.0, z=2.0 * math.cos(az)),
            )
        )
    r = PlacementResult(
        target_algorithm=algorithm,
        regularity_hint="CIRCULAR",
        speakers=speakers,
        layout_name="fixture",
    )
    write_layout_yaml(r, path, validate=False)


def test_cli_edit_spherical_writes_layout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = tmp_path / "layout.yaml"
    _write_fixture(fixture)
    out_dir = tmp_path / "out"
    rc = main(
        ["edit", "--in-placement", str(fixture), "--speaker", "0", "--daz", "5",
         "--out-dir", str(out_dir), "--no-engine-validation"]
    )
    assert rc == 0
    assert (out_dir / "layout.yaml").exists()
    captured = capsys.readouterr()
    assert "az_deg" in captured.out  # diff body present


def test_cli_edit_elevation_del_deg_flag(tmp_path: Path) -> None:
    fixture = tmp_path / "layout.yaml"
    _write_fixture(fixture)
    out_dir = tmp_path / "out"
    rc = main(
        ["edit", "--in-placement", str(fixture), "--speaker", "0", "--del-deg", "3",
         "--out-dir", str(out_dir), "--no-engine-validation"]
    )
    assert rc == 0
    edited = read_placement_yaml(out_dir / "layout.yaml")
    # elevation Δ moved speaker 0 off the y=0 plane
    assert edited.speakers[0].position.y == pytest.approx(2.0 * math.sin(math.radians(3.0)), abs=1e-6)


def test_cli_edit_cartesian(tmp_path: Path) -> None:
    fixture = tmp_path / "layout.yaml"
    _write_fixture(fixture)
    out_dir = tmp_path / "out"
    rc = main(
        ["edit", "--in-placement", str(fixture), "--speaker", "0", "--dx", "0.1",
         "--out-dir", str(out_dir), "--no-engine-validation"]
    )
    assert rc == 0


def test_cli_edit_mixing_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = tmp_path / "layout.yaml"
    _write_fixture(fixture)
    out_dir = tmp_path / "out"
    rc = main(
        ["edit", "--in-placement", str(fixture), "--speaker", "0", "--daz", "5", "--dx", "0.1",
         "--out-dir", str(out_dir), "--no-engine-validation"]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert "mutually exclusive" in captured.err


def test_cli_edit_dbap_fixture(tmp_path: Path) -> None:
    # DBAP layout: read collapses target_algorithm to "VBAP" (OQ-38) but the
    # CLI edit + write path works normally. Compound-covers the label-loss path.
    fixture = tmp_path / "layout.yaml"
    _write_fixture(fixture, algorithm="DBAP")
    out_dir = tmp_path / "out"
    rc = main(
        ["edit", "--in-placement", str(fixture), "--speaker", "0", "--daz", "5",
         "--out-dir", str(out_dir), "--no-engine-validation"]
    )
    assert rc == 0
    assert (out_dir / "layout.yaml").exists()


def test_cli_edit_no_engine_validation(tmp_path: Path) -> None:
    fixture = tmp_path / "layout.yaml"
    _write_fixture(fixture)
    out_dir = tmp_path / "out"
    rc = main(
        ["edit", "--in-placement", str(fixture), "--speaker", "0", "--daz", "5",
         "--out-dir", str(out_dir), "--no-engine-validation"]
    )
    assert rc == 0
    text = (out_dir / "layout.yaml").read_text(encoding="utf-8")
    assert text.startswith("# WARNING: schema validation skipped")


def test_cli_edit_el_out_of_range_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = tmp_path / "layout.yaml"
    _write_fixture(fixture)  # speakers at el=0
    out_dir = tmp_path / "out"
    rc = main(
        ["edit", "--in-placement", str(fixture), "--speaker", "0",
         "--del-deg", "95", "--out-dir", str(out_dir), "--no-engine-validation"]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert "outside [-90, 90]" in captured.err
    # rejected before write → no output file
    assert not (out_dir / "layout.yaml").exists()
