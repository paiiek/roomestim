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

    # v0.17 default schema is "0.2-draft" (adds objects[]).
    schema = _load_schema("room_schema.v0_2.draft.json")
    Draft202012Validator(schema).validate(loaded)
    assert loaded["version"] == "0.2-draft"
    assert loaded["name"] == "synthetic_shoebox"
    assert len(loaded["surfaces"]) == 6  # floor + ceiling + 4 walls
    assert loaded["ceiling_height_m"] == pytest.approx(2.8)
    # objects key always emitted on 0.2-draft (possibly empty).
    assert loaded["objects"] == []


def test_l_shape_writes_valid_yaml(tmp_path: Path) -> None:
    room = l_shape_room()
    out = tmp_path / "l_shape.yaml"
    write_room_yaml(room, out)

    with out.open("r", encoding="utf-8") as fh:
        loaded: dict[str, Any] = yaml.safe_load(fh)

    # v0.17 default schema is "0.2-draft" (adds objects[]).
    schema = _load_schema("room_schema.v0_2.draft.json")
    Draft202012Validator(schema).validate(loaded)
    assert len(loaded["floor_polygon"]) == 6
    assert len(loaded["surfaces"]) == 8  # floor + ceiling + 6 walls
    assert loaded["objects"] == []


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


# --------------------------------------------------------------------------- #
# v0.28.0 — ceiling-confidence under-report guard round-trip + byte-equal-absent
# --------------------------------------------------------------------------- #


def test_ceiling_confidence_round_trips_when_measured(tmp_path: Path) -> None:
    """A measured room (coverage set) round-trips both ceiling fields through YAML.

    Mirrors the provenance schema round-trip: writer emits the optional keys,
    schema validates them, reader restores them.
    """
    from roomestim.io.room_yaml_reader import read_room_yaml

    room = shoebox()
    room.ceiling_coverage = 0.2
    room.ceiling_confidence = "low"
    out = tmp_path / "room.yaml"
    write_room_yaml(room, out, schema_version="0.2-draft")

    raw = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert raw["ceiling_coverage"] == pytest.approx(0.2)
    assert raw["ceiling_confidence"] == "low"

    back = read_room_yaml(out)
    assert back.ceiling_coverage == pytest.approx(0.2)
    assert back.ceiling_confidence == "low"


def test_ceiling_confidence_keys_absent_when_not_measured(tmp_path: Path) -> None:
    """A non-measured room (coverage None, default) emits NO new keys.

    Byte-equal guard: every committed non-mesh 0.2-draft YAML golden stays
    byte-equal because the writer only emits the keys when coverage is measured.
    An absent key honestly means "not measured" → reader defaults None/"unknown".
    """
    from roomestim.io.room_yaml_reader import read_room_yaml

    room = shoebox()  # default ceiling_coverage is None
    assert room.ceiling_coverage is None
    out = tmp_path / "room.yaml"
    write_room_yaml(room, out, schema_version="0.2-draft")

    raw = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "ceiling_coverage" not in raw
    assert "ceiling_confidence" not in raw

    back = read_room_yaml(out)
    assert back.ceiling_coverage is None
    assert back.ceiling_confidence == "unknown"


def test_reader_rejects_invalid_ceiling_confidence(tmp_path: Path) -> None:
    """An out-of-enum ceiling_confidence is rejected at read (ValueError)."""
    from roomestim.io.room_yaml_reader import read_room_yaml

    room = shoebox()
    room.ceiling_coverage = 0.8
    room.ceiling_confidence = "high"
    out = tmp_path / "room.yaml"
    write_room_yaml(room, out, schema_version="0.2-draft")

    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    data["ceiling_confidence"] = "definitely"
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="ceiling_confidence|not one of|enum"):
        read_room_yaml(out)


def test_reader_decouples_confidence_without_coverage(tmp_path: Path) -> None:
    """A hand-authored confidence WITHOUT coverage is dropped to 'unknown' on read.

    The writer only ever emits ``ceiling_confidence`` alongside a non-None
    ``ceiling_coverage`` (measured path), so a confidence-without-coverage pair
    can only come from external authoring. The reader couples the two — dropping
    the orphan confidence to "unknown" — so the round-trip never silently mutates
    (the writer would otherwise drop the orphan confidence on rewrite). Locks the
    v0.28.0 code-review LOW-2 fix.
    """
    from roomestim.io.room_yaml_reader import read_room_yaml

    room = shoebox()  # coverage None by default
    out = tmp_path / "room.yaml"
    write_room_yaml(room, out, schema_version="0.2-draft")

    # Inject an orphan confidence (no coverage key) — the hand-authored case.
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    data["ceiling_confidence"] = "low"
    assert "ceiling_coverage" not in data
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    back = read_room_yaml(out)
    assert back.ceiling_coverage is None
    assert back.ceiling_confidence == "unknown"  # orphan dropped → coupled state

    # And it now round-trips stably: re-write emits neither key.
    out2 = tmp_path / "room2.yaml"
    write_room_yaml(back, out2, schema_version="0.2-draft")
    raw2 = yaml.safe_load(out2.read_text(encoding="utf-8"))
    assert "ceiling_confidence" not in raw2
    assert "ceiling_coverage" not in raw2
