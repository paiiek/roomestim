"""Round-trip + manifest-schema validation for the RoomCollection layer (ADR 0049).

Covers the writer/reader contract (`read_collection_yaml ∘ write_collection_yaml`),
manifest ordering stability, relative-ref portability (Risk #3), and the
collection schema (`additionalProperties:false`, required keys).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from roomestim.cli import main
from roomestim.collection import RoomCollection
from roomestim.export.collection_yaml import collection_to_dict, write_collection_yaml
from roomestim.io.collection_yaml_reader import read_collection_yaml

_FIXTURES = Path(__file__).parent / "fixtures"
_LAB_JSON = _FIXTURES / "lab_room.json"
_LAB_PLY = _FIXTURES / "lab_room.ply"
_SCHEMA = Path(__file__).parent.parent / "roomestim" / "proto" / "collection_schema.v0_1.draft.json"


def _build_collection_dir(tmp_path: Path) -> Path:
    a = tmp_path / "A"
    b = tmp_path / "B"
    a.mkdir()
    b.mkdir()
    assert main(["ingest", "--backend", "roomplan", "--input", str(_LAB_JSON),
                 "--out-dir", str(a)]) == 0
    assert main(["ingest", "--backend", "polycam", "--input", str(_LAB_PLY),
                 "--out-dir", str(b)]) == 0
    coll = tmp_path / "coll"
    assert main(["collection", "--in-rooms", str(a / "room.yaml"), str(b / "room.yaml"),
                 "--algorithm", "vbap", "--n-speakers", "8", "--name", "venue",
                 "--out-dir", str(coll)]) == 0
    return coll


def test_collection_roundtrip_read_after_cli_write(tmp_path: Path) -> None:
    coll_dir = _build_collection_dir(tmp_path)
    collection = read_collection_yaml(coll_dir / "collection.yaml")
    assert collection.name == "venue"
    # Ordering is stable: roomplan first, mesh second.
    assert [r.name for r in collection.rooms] == ["lab_room_synthetic", "lab_room"]
    assert len(collection.placements) == 2
    assert all(p is not None for p in collection.placements)
    # Each loaded placement carries 8 speakers (the per-room placement we ran).
    for p in collection.placements:
        assert p is not None
        assert len(p.speakers) == 8


def test_collection_manifest_validates_against_schema(tmp_path: Path) -> None:
    coll_dir = _build_collection_dir(tmp_path)
    data = yaml.safe_load((coll_dir / "collection.yaml").read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    # Must not raise.
    Draft202012Validator(schema).validate(data)


def test_collection_schema_rejects_additional_property(tmp_path: Path) -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    bad = {
        "version": "0.1-draft",
        "name": "x",
        "rooms": [{"name": "r", "room_ref": "room.r.yaml", "layout_ref": "layout.r.yaml"}],
        "surprise": 1,
    }
    assert validator.iter_errors(bad), "additionalProperties:false must reject extra keys"


def test_collection_schema_requires_room_ref(tmp_path: Path) -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    bad = {
        "version": "0.1-draft",
        "name": "x",
        "rooms": [{"name": "r", "layout_ref": "layout.r.yaml"}],
    }
    assert validator.iter_errors(bad), "room_ref is required per entry"


def test_collection_writer_rejects_absolute_refs(tmp_path: Path) -> None:
    """Risk #3: absolute refs would leak machine paths into goldens — rejected."""
    a = tmp_path / "A"
    a.mkdir()
    assert main(["ingest", "--backend", "roomplan", "--input", str(_LAB_JSON),
                 "--out-dir", str(a)]) == 0
    from roomestim.io.room_yaml_reader import read_room_yaml

    room = read_room_yaml(a / "room.yaml")
    collection = RoomCollection(name="venue", rooms=[room, room])
    with pytest.raises(ValueError, match="relative"):
        collection_to_dict(
            collection,
            room_refs=["/abs/room.0.yaml", "room.1.yaml"],
            layout_refs=[None, None],
        )


def test_collection_to_dict_layout_ref_none_for_unplaced(tmp_path: Path) -> None:
    a = tmp_path / "A"
    a.mkdir()
    assert main(["ingest", "--backend", "roomplan", "--input", str(_LAB_JSON),
                 "--out-dir", str(a)]) == 0
    from roomestim.io.room_yaml_reader import read_room_yaml

    room = read_room_yaml(a / "room.yaml")
    collection = RoomCollection(name="venue", rooms=[room, room])  # placements -> [None, None]
    d = collection_to_dict(
        collection,
        room_refs=["room.0.yaml", "room.1.yaml"],
        layout_refs=[None, None],
    )
    assert d["rooms"][0]["layout_ref"] is None
    # Manifest with null layout_ref still round-trips through the writer + reader.
    out = tmp_path / "manifest"
    out.mkdir()
    # Re-emit the two room.yaml siblings so the reader can resolve them.
    (out / "room.0.yaml").write_bytes((a / "room.yaml").read_bytes())
    (out / "room.1.yaml").write_bytes((a / "room.yaml").read_bytes())
    write_collection_yaml(
        collection, out / "collection.yaml",
        room_refs=["room.0.yaml", "room.1.yaml"], layout_refs=[None, None],
    )
    loaded = read_collection_yaml(out / "collection.yaml")
    assert loaded.placements == [None, None]
    assert [r.name for r in loaded.rooms] == [room.name, room.name]
