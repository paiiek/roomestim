"""A3 acceptance — RoomModel -> room.yaml writer + schema validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from roomestim.export import write_room_yaml
from roomestim.model import (
    ListenerArea,
    MaterialAbsorption,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
)
from tests.fixtures.synthetic_rooms import l_shape_room, shoebox


REPO_ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = REPO_ROOT / "proto"


def _load_schema(name: str) -> dict[str, Any]:
    with (PROTO_DIR / name).open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def test_writes_valid_yaml(tmp_path: Path) -> None:
    room = shoebox()
    out = tmp_path / "shoebox.yaml"
    write_room_yaml(room, out)

    with out.open("r", encoding="utf-8") as fh:
        loaded: dict[str, Any] = yaml.safe_load(fh)

    schema = _load_schema("room_schema.draft.json")
    Draft202012Validator(schema).validate(loaded)
    assert loaded["version"] == "0.1-draft"
    assert loaded["name"] == "synthetic_shoebox"
    assert len(loaded["surfaces"]) == 6  # floor + ceiling + 4 walls
    assert loaded["ceiling_height_m"] == pytest.approx(2.8)


def test_l_shape_writes_valid_yaml(tmp_path: Path) -> None:
    room = l_shape_room()
    out = tmp_path / "l_shape.yaml"
    write_room_yaml(room, out)

    with out.open("r", encoding="utf-8") as fh:
        loaded: dict[str, Any] = yaml.safe_load(fh)

    schema = _load_schema("room_schema.draft.json")
    Draft202012Validator(schema).validate(loaded)
    assert len(loaded["floor_polygon"]) == 6
    assert len(loaded["surfaces"]) == 8  # floor + ceiling + 6 walls


def test_rejects_nonfinite(tmp_path: Path) -> None:
    bad_room = RoomModel(
        name="bad",
        floor_polygon=[Point2(-1, -1), Point2(1, -1), Point2(1, 1), Point2(-1, 1)],
        ceiling_height_m=float("inf"),
        surfaces=[
            Surface(
                kind="floor",
                polygon=[
                    Point3(-1, 0, -1),
                    Point3(1, 0, -1),
                    Point3(1, 0, 1),
                    Point3(-1, 0, 1),
                ],
                material=MaterialLabel.WOOD_FLOOR,
                absorption_500hz=MaterialAbsorption[MaterialLabel.WOOD_FLOOR],
            )
        ],
        listener_area=ListenerArea(
            polygon=[
                Point2(-0.5, -0.5),
                Point2(0.5, -0.5),
                Point2(0.5, 0.5),
                Point2(-0.5, 0.5),
            ],
            centroid=Point2(0.0, 0.0),
            height_m=1.20,
        ),
    )
    out = tmp_path / "bad.yaml"
    with pytest.raises(ValueError, match="kErrNonFiniteValue"):
        write_room_yaml(bad_room, out)
    assert not out.exists(), "must not write when finite-sweep fails"


def test_stage1_uses_draft_schema(tmp_path: Path) -> None:
    room = shoebox()
    out = tmp_path / "shoebox_draft.yaml"
    write_room_yaml(room, out, schema_version="0.1-draft")
    with out.open("r", encoding="utf-8") as fh:
        loaded: dict[str, Any] = yaml.safe_load(fh)
    assert loaded["version"] == "0.1-draft"


def test_stage2_strict_schema(tmp_path: Path) -> None:
    room = shoebox()
    out = tmp_path / "shoebox_locked.yaml"
    write_room_yaml(room, out, schema_version="0.1")
    with out.open("r", encoding="utf-8") as fh:
        loaded: dict[str, Any] = yaml.safe_load(fh)
    assert loaded["version"] == "0.1"
    schema = _load_schema("room_schema.json")
    Draft202012Validator(schema).validate(loaded)
