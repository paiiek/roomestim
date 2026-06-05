"""T1 — geometry capture provenance propagated into the layout.yaml artifact.

OQ-54 / ADR 0046: the rough-tier honesty marker (room-level ``provenance``)
must survive past the volatile stderr notice into the *placement* boundary.
``placement_to_dict`` emits a top-level ``x_geometry_provenance`` extension key
ONLY when non-default (``!= "assumed"``), so every pre-existing layout stays
byte-equal; ``reconstructed`` (rough marker) and ``measured`` (positive claim)
are carried and round-trip through the reader.

Tests use ``validate=False`` (matching tests/test_layout_round_trip.py) so they
are hermetic w.r.t. the engine geometry schema.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml

from roomestim.export.layout_yaml import write_layout_yaml
from roomestim.io.placement_yaml_reader import read_placement_yaml
from roomestim.model import PlacedSpeaker, PlacementResult, Point3, Provenance


def _result(*, geometry_provenance: Provenance = "assumed") -> PlacementResult:
    """4-speaker axis-aligned CIRCULAR VBAP layout (≥ _MIN_SPEAKERS CIRCULAR=3)."""
    speakers: list[PlacedSpeaker] = []
    for i, az_deg in enumerate((0.0, 90.0, 180.0, 270.0)):
        az = math.radians(az_deg)
        pos = Point3(x=2.0 * math.sin(az), y=0.0, z=2.0 * math.cos(az))
        speakers.append(PlacedSpeaker(channel=i + 1, position=pos))
    return PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="CIRCULAR",
        speakers=speakers,
        layout_name="prov",
        geometry_provenance=geometry_provenance,
    )


def _write_load(result: PlacementResult, path: Path) -> dict:
    write_layout_yaml(result, path, validate=False)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_reconstructed_emits_key(tmp_path: Path) -> None:
    data = _write_load(_result(geometry_provenance="reconstructed"), tmp_path / "l.yaml")
    assert data["x_geometry_provenance"] == "reconstructed"


def test_assumed_default_omits_key(tmp_path: Path) -> None:
    # byte-equal guarantee: the default "assumed" never emits the extension key.
    data = _write_load(_result(), tmp_path / "l.yaml")
    assert "x_geometry_provenance" not in data


def test_measured_emits_key(tmp_path: Path) -> None:
    data = _write_load(_result(geometry_provenance="measured"), tmp_path / "l.yaml")
    assert data["x_geometry_provenance"] == "measured"


def test_round_trip_reconstructed_stable(tmp_path: Path) -> None:
    p1 = tmp_path / "a.yaml"
    p2 = tmp_path / "b.yaml"
    write_layout_yaml(_result(geometry_provenance="reconstructed"), p1, validate=False)
    loaded = read_placement_yaml(p1)
    assert loaded.geometry_provenance == "reconstructed"
    # edit round-trip stability: re-writing the loaded result keeps the key.
    write_layout_yaml(loaded, p2, validate=False)
    data2 = yaml.safe_load(p2.read_text(encoding="utf-8"))
    assert data2["x_geometry_provenance"] == "reconstructed"


def test_reader_missing_key_defaults_assumed(tmp_path: Path) -> None:
    p = tmp_path / "l.yaml"
    write_layout_yaml(_result(), p, validate=False)  # default → no key emitted
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert "x_geometry_provenance" not in data
    loaded = read_placement_yaml(p)
    assert loaded.geometry_provenance == "assumed"


def test_reader_rejects_out_of_enum_value(tmp_path: Path) -> None:
    p = tmp_path / "l.yaml"
    write_layout_yaml(_result(), p, validate=False)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    data["x_geometry_provenance"] = "bogus"
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError):
        read_placement_yaml(p)
