"""OQ-54 — room-level provenance field round-trip and adapter wiring.

Provenance ∈ {measured, reconstructed, assumed} lives at the ROOM level so
image-derived geometry can never masquerade as sensor-measured (ADR 0045
Reverse-criterion #4 / §F honesty). It is emitted in YAML ONLY on the
0.2-draft schema (like ``objects[]``), keeping legacy 0.1 output byte-equal.
The default is the honest least-claim ``"assumed"``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from roomestim.export import write_room_yaml
from roomestim.io.room_yaml_reader import read_room_yaml
from tests.fixtures.synthetic_rooms import shoebox


def test_default_provenance_is_assumed() -> None:
    # Honest least-claim: a hand-built / untagged model does NOT claim measured.
    room = shoebox()
    assert room.provenance == "assumed"


def test_measured_roundtrip_on_0_2_draft(tmp_path: Path) -> None:
    room = shoebox()
    room.provenance = "measured"
    out = tmp_path / "room.yaml"
    write_room_yaml(room, out, schema_version="0.2-draft")

    raw = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert raw["provenance"] == "measured"

    back = read_room_yaml(out)
    assert back.provenance == "measured"


def test_no_provenance_key_on_0_1_draft(tmp_path: Path) -> None:
    # 0.1 output stays byte-equal to pre-provenance: NO provenance key emitted.
    room = shoebox()
    room.provenance = "measured"  # even an explicit value is dropped on 0.1
    out = tmp_path / "room.yaml"
    write_room_yaml(room, out, schema_version="0.1-draft")

    raw = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "provenance" not in raw

    # Reading a 0.1 file (no key) defaults to the honest least-claim "assumed".
    back = read_room_yaml(out)
    assert back.provenance == "assumed"


def test_legacy_0_2_draft_without_key_reads_assumed(tmp_path: Path) -> None:
    # A pre-provenance 0.2-draft file (objects present, no provenance key) must
    # still read, defaulting to the honest least-claim "assumed". Locks the
    # read-side default against regression (root additionalProperties: true).
    room = shoebox()
    room.provenance = "measured"
    out = tmp_path / "room.yaml"
    write_room_yaml(room, out, schema_version="0.2-draft")

    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["version"] == "0.2-draft"
    del data["provenance"]  # simulate a file written before provenance existed
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    back = read_room_yaml(out)
    assert back.provenance == "assumed"


def test_reader_rejects_invalid_provenance(tmp_path: Path) -> None:
    room = shoebox()
    out = tmp_path / "room.yaml"
    write_room_yaml(room, out, schema_version="0.2-draft")

    # Corrupt the emitted YAML with an out-of-enum provenance value.
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    data["provenance"] = "guessed"
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    # Rejected at read: the schema enum catches it first (it is the on-disk
    # guard); the reader's own _parse_provenance is the defensive net for any
    # caller that bypasses schema validation. Either way → ValueError.
    with pytest.raises(ValueError, match="provenance|not one of"):
        read_room_yaml(out)


def test_parse_provenance_helper_rejects_invalid() -> None:
    # Defensive net for callers that bypass schema validation.
    from roomestim.io.room_yaml_reader import _parse_provenance

    assert _parse_provenance("measured", name="r") == "measured"
    assert _parse_provenance("reconstructed", name="r") == "reconstructed"
    assert _parse_provenance("assumed", name="r") == "assumed"
    with pytest.raises(ValueError, match="invalid provenance"):
        _parse_provenance("guessed", name="r")


def test_roomplan_adapter_is_measured() -> None:
    from roomestim.adapters.roomplan import RoomPlanAdapter

    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    room = RoomPlanAdapter().parse(fixture)
    assert room.provenance == "measured"


def test_mesh_adapter_is_measured() -> None:
    from roomestim.adapters import MeshAdapter

    fixture = Path("tests/fixtures/lab_room_vertex_color.ply")
    if not fixture.exists():
        pytest.skip("mesh fixture not found")
    room = MeshAdapter().parse(fixture)
    assert room.provenance == "measured"


def test_ace_adapter_is_measured() -> None:
    from roomestim.adapters.ace_challenge import list_rooms, load_room

    fixture_dir = Path(__file__).parent / "fixtures" / "ace_challenge_sample"
    if not fixture_dir.is_dir():
        pytest.skip("ace_challenge_sample fixture not found")
    rooms = list_rooms(fixture_dir)
    case = load_room(fixture_dir, rooms[0])
    assert case.room.provenance == "measured"
