"""A1 acceptance — PlacementResult -> layout.yaml writer.

Validates against ``spatial_engine/proto/geometry_schema.json`` (read at test
time, never vendored). Also exercises:

* Per-speaker extension keys ``x_aim_az_deg`` / ``x_aim_el_deg`` (D5 / §6.1).
* Top-level extension key ``x_wfs_f_alias_hz`` (A8 + §6.1) — emitted only for
  WFS, required when present.
* R10 ``kErrTooFewSpeakers`` pre-flight.
* R11 ``kErrNonFiniteValue`` finite-sweep.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from roomestim.export import write_layout_yaml
from roomestim.model import PlacedSpeaker, PlacementResult, Point3


_DEFAULT_ENGINE_SCHEMA_PATH = Path(
    "/home/seung/mmhoa/spatial_engine/proto/geometry_schema.json"
)


def _engine_schema() -> dict[str, Any]:
    repo_dir = os.environ.get("SPATIAL_ENGINE_REPO_DIR")
    if repo_dir:
        candidate = Path(repo_dir) / "proto" / "geometry_schema.json"
        if candidate.is_file():
            with candidate.open("r", encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
            return data
    with _DEFAULT_ENGINE_SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        loaded: dict[str, Any] = yaml.safe_load(fh)
    return loaded


def _circular_3_speakers_on_ring(radius_m: float = 2.0) -> list[PlacedSpeaker]:
    """Return 3 speakers at azimuths {0, 120, 240}° on a horizontal ring."""
    out: list[PlacedSpeaker] = []
    for i, az_deg in enumerate((0.0, 120.0, 240.0)):
        az = math.radians(az_deg)
        # x = r*sin(az), z = r*cos(az), y = 0 (azimuth=0 -> +z front).
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


def _vbap_circular_result() -> PlacementResult:
    return PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="CIRCULAR",
        speakers=_circular_3_speakers_on_ring(),
        layout_name="test_circular_3",
    )


# --------------------------------------------------------------------------- #
# A1 base case — schema-valid output
# --------------------------------------------------------------------------- #


def test_writes_valid_layout_yaml(tmp_path: Path) -> None:
    result = _vbap_circular_result()
    out = tmp_path / "layout.yaml"
    write_layout_yaml(result, out)

    loaded = _load_yaml(out)
    Draft202012Validator(_engine_schema()).validate(loaded)

    assert loaded["version"] == "1.0"
    assert loaded["name"] == "test_circular_3"
    assert loaded["regularity_hint"] == "CIRCULAR"
    assert len(loaded["speakers"]) == 3
    # Each speaker carries spherical form + extension keys.
    for sp in loaded["speakers"]:
        assert "az_deg" in sp and "el_deg" in sp and "dist_m" in sp
        assert "x" not in sp and "xyz" not in sp  # spherical-only per schema not.anyOf
        assert sp["dist_m"] > 0
    # No top-level x_wfs_f_alias_hz on a VBAP layout.
    assert "x_wfs_f_alias_hz" not in loaded


# --------------------------------------------------------------------------- #
# Aim default: speaker at (1,0,0) -> aim at origin -> aim direction = (-1,0,0).
# (-1, 0, 0) -> az = atan2(-1, 0) = -pi/2 -> -90°; el = 0°.
# --------------------------------------------------------------------------- #


def test_extension_keys_aim_default(tmp_path: Path) -> None:
    result = PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="CIRCULAR",
        speakers=[
            PlacedSpeaker(channel=1, position=Point3(1.0, 0.0, 0.0)),
            PlacedSpeaker(channel=2, position=Point3(-1.0, 0.0, 0.0)),
            PlacedSpeaker(channel=3, position=Point3(0.0, 0.0, 1.0)),
        ],
        layout_name="aim_defaults",
    )
    out = tmp_path / "aim.yaml"
    write_layout_yaml(result, out)
    loaded = _load_yaml(out)

    s1 = loaded["speakers"][0]
    s2 = loaded["speakers"][1]
    s3 = loaded["speakers"][2]
    # Speaker at (1,0,0) -> aim toward origin -> aim direction (-1,0,0)
    # -> az = atan2(-1, 0) = -90°, el = 0°.
    assert s1["x_aim_az_deg"] == pytest.approx(-90.0, abs=1e-9)
    assert s1["x_aim_el_deg"] == pytest.approx(0.0, abs=1e-9)
    # Speaker at (-1,0,0) -> aim direction (+1,0,0) -> az = atan2(1, 0) = +90°.
    assert s2["x_aim_az_deg"] == pytest.approx(90.0, abs=1e-9)
    assert s2["x_aim_el_deg"] == pytest.approx(0.0, abs=1e-9)
    # Speaker at (0,0,1) (front) -> aim direction (0,0,-1) -> az = atan2(0,-1) = 180°.
    assert abs(abs(s3["x_aim_az_deg"]) - 180.0) < 1e-9
    assert s3["x_aim_el_deg"] == pytest.approx(0.0, abs=1e-9)


def test_extension_keys_aim_explicit(tmp_path: Path) -> None:
    # Speaker at (1, 0, 0) but explicitly aimed at +front (0, 0, 1)
    # -> az = atan2(0, 1) = 0°, el = 0°.
    explicit_speaker = PlacedSpeaker(
        channel=1,
        position=Point3(1.0, 0.0, 0.0),
        aim_direction=Point3(0.0, 0.0, 1.0),
    )
    result = PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="CIRCULAR",
        speakers=[
            explicit_speaker,
            PlacedSpeaker(channel=2, position=Point3(-1.0, 0.0, 0.0)),
            PlacedSpeaker(channel=3, position=Point3(0.0, 0.0, 1.0)),
        ],
        layout_name="aim_explicit",
    )
    out = tmp_path / "aim_explicit.yaml"
    write_layout_yaml(result, out)
    loaded = _load_yaml(out)
    s1 = loaded["speakers"][0]
    assert s1["x_aim_az_deg"] == pytest.approx(0.0, abs=1e-9)
    assert s1["x_aim_el_deg"] == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# A8 — x_wfs_f_alias_hz emission discipline
# --------------------------------------------------------------------------- #


def test_wfs_alias_freq_emitted_only_for_wfs(tmp_path: Path) -> None:
    # 1) VBAP — must NOT emit x_wfs_f_alias_hz.
    vbap_result = _vbap_circular_result()
    vbap_path = tmp_path / "vbap.yaml"
    write_layout_yaml(vbap_result, vbap_path)
    assert "x_wfs_f_alias_hz" not in _load_yaml(vbap_path)

    # 2) WFS with finite alias freq — must emit and round-trip the value.
    wfs_result = PlacementResult(
        target_algorithm="WFS",
        regularity_hint="LINEAR",
        speakers=[
            PlacedSpeaker(channel=1, position=Point3(-0.5, 0.0, 2.0)),
            PlacedSpeaker(channel=2, position=Point3(0.5, 0.0, 2.0)),
        ],
        layout_name="wfs_linear",
        wfs_f_alias_hz=4000.0,
    )
    wfs_path = tmp_path / "wfs.yaml"
    write_layout_yaml(wfs_result, wfs_path)
    loaded = _load_yaml(wfs_path)
    assert loaded["x_wfs_f_alias_hz"] == pytest.approx(4000.0, abs=1e-9)

    # 3) WFS with None alias freq — must raise ValueError.
    wfs_bad = PlacementResult(
        target_algorithm="WFS",
        regularity_hint="LINEAR",
        speakers=[
            PlacedSpeaker(channel=1, position=Point3(-0.5, 0.0, 2.0)),
            PlacedSpeaker(channel=2, position=Point3(0.5, 0.0, 2.0)),
        ],
        layout_name="wfs_bad",
        wfs_f_alias_hz=None,
    )
    bad_path = tmp_path / "wfs_bad.yaml"
    with pytest.raises(ValueError, match=r"x_wfs_f_alias_hz|wfs"):
        write_layout_yaml(wfs_bad, bad_path)
    assert not bad_path.exists()


def test_layout_yaml_has_x_wfs_f_alias_hz(tmp_path: Path) -> None:
    """A8 piece — WFS placement writes top-level ``x_wfs_f_alias_hz: 4000.0``."""
    wfs_result = PlacementResult(
        target_algorithm="WFS",
        regularity_hint="LINEAR",
        speakers=[
            PlacedSpeaker(channel=1, position=Point3(-0.5, 0.0, 2.0)),
            PlacedSpeaker(channel=2, position=Point3(0.5, 0.0, 2.0)),
        ],
        layout_name="wfs_alias",
        wfs_f_alias_hz=4000.0,
    )
    out = tmp_path / "wfs_alias.yaml"
    write_layout_yaml(wfs_result, out)
    loaded = _load_yaml(out)
    assert "x_wfs_f_alias_hz" in loaded
    assert loaded["x_wfs_f_alias_hz"] == pytest.approx(4000.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# R11 — non-finite leak rejection
# --------------------------------------------------------------------------- #


def test_rejects_nonfinite(tmp_path: Path) -> None:
    bad = PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="CIRCULAR",
        speakers=[
            PlacedSpeaker(channel=1, position=Point3(float("inf"), 0.0, 0.0)),
            PlacedSpeaker(channel=2, position=Point3(-1.0, 0.0, 0.0)),
            PlacedSpeaker(channel=3, position=Point3(0.0, 0.0, 1.0)),
        ],
        layout_name="bad_nonfinite",
    )
    out = tmp_path / "bad.yaml"
    with pytest.raises(ValueError, match="kErrNonFiniteValue"):
        write_layout_yaml(bad, out)
    assert not out.exists()


# --------------------------------------------------------------------------- #
# R10 — too-few-speakers rejection
# --------------------------------------------------------------------------- #


def test_rejects_too_few_speakers(tmp_path: Path) -> None:
    bad = PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="CIRCULAR",
        speakers=[
            PlacedSpeaker(channel=1, position=Point3(1.0, 0.0, 0.0)),
            PlacedSpeaker(channel=2, position=Point3(-1.0, 0.0, 0.0)),
        ],
        layout_name="too_few",
    )
    out = tmp_path / "too_few.yaml"
    with pytest.raises(ValueError, match="kErrTooFewSpeakers"):
        write_layout_yaml(bad, out)
    assert not out.exists()
