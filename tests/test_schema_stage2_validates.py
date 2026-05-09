"""v0.9 §2.4 — Stage-2 schema flip invariants (default-lane).

One default-lane test asserting the post-flip Stage-2 invariants:

- ``roomestim.__schema_version__ == "0.1"`` (was ``"0.1-draft"`` v0.1..v0.8).
- ``RoomModel().schema_version`` default is ``"0.1"``.
- A ``RoomModel`` instance round-trips through the room.yaml writer with
  ``version: "0.1"`` and validates against ``proto/room_schema.json``
  (Stage 2 strict, ``additionalProperties: false``).
- A YAML payload with an unrecognised top-level extension key (e.g.,
  ``unrecognised_extension_key: 42``) is REJECTED by the Stage-2 schema —
  this is the ``additionalProperties: false`` enforcement.
- Backward-compat: a payload with ``version: "0.1-draft"`` STILL validates
  against ``proto/room_schema.draft.json`` (old reads keep working;
  ``_load_schema`` switch in ``room_yaml_reader.py:32`` handles this).

This test is the v0.9 §2.4 acceptance gate per ADR 0016 §Drivers / §Decision.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError

import roomestim
from roomestim.export.room_yaml import write_room_yaml
from roomestim.io.room_yaml_reader import read_room_yaml
from roomestim.model import RoomModel
from tests.fixtures.synthetic_rooms import shoebox

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTO_DIR = REPO_ROOT / "proto"


def _load_schema(name: str) -> dict[str, Any]:
    with (PROTO_DIR / name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_stage2_schema_flip_marker_and_strict_mode(tmp_path: Path) -> None:
    """v0.9 Stage-2 flip: marker + default + strict additionalProperties + back-compat."""
    # 1) Library marker flip.
    assert roomestim.__schema_version__ == "0.1", (
        f"v0.9 expects __schema_version__='0.1', got "
        f"{roomestim.__schema_version__!r}"
    )

    # 2) RoomModel default flip.
    room: RoomModel = shoebox()
    assert room.schema_version == "0.1", (
        f"v0.9 expects RoomModel().schema_version='0.1', got "
        f"{room.schema_version!r}"
    )

    # 3) Round-trip emits version: "0.1" and validates Stage-2 strict.
    out = tmp_path / "room_stage2.yaml"
    write_room_yaml(room, out, schema_version="0.1")
    with out.open("r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh)
    assert payload["version"] == "0.1"
    schema_strict = _load_schema("room_schema.json")
    Draft202012Validator(schema_strict).validate(payload)

    # Reader path is byte-equivalent (the round-trip).
    reread = read_room_yaml(out)
    assert reread.schema_version == "0.1"

    # 4) additionalProperties: false rejects unknown top-level keys.
    bad_payload = dict(payload)
    bad_payload["unrecognised_extension_key"] = 42
    validator = Draft202012Validator(schema_strict)
    with pytest.raises(ValidationError):
        validator.validate(bad_payload)

    # 5) Backward-compat: a version: "0.1-draft" payload still validates
    # against the draft schema.
    draft_payload = dict(payload)
    draft_payload["version"] = "0.1-draft"
    schema_draft = _load_schema("room_schema.draft.json")
    Draft202012Validator(schema_draft).validate(draft_payload)
