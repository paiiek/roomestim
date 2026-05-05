"""Schema compatibility tests for v0.3 octave-band absorption block.

Tests verify:
- Legacy (v0.1.1) YAML without absorption block validates against v0.3 schemas.
- v0.3 writer emits absorption block when absorption_bands is set.
- v0.3 reader returns absorption_bands=None for legacy YAML.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from roomestim.export.room_yaml import write_room_yaml
from roomestim.io.room_yaml_reader import read_room_yaml
from roomestim.model import (
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    Surface,
)

_PROTO_DIR = Path(__file__).parent.parent / "proto"


def _load_schema(name: str) -> dict[str, Any]:
    with (_PROTO_DIR / name).open("r", encoding="utf-8") as fh:
        return json.load(fh)  # type: ignore[no-any-return]


def _make_legacy_room_yaml(tmp_path: Path) -> Path:
    """Write a minimal v0.1.1-shape room.yaml (no absorption block)."""
    from tests.fixtures.synthetic_rooms import shoebox

    room = shoebox()
    out = tmp_path / "room_legacy.yaml"
    write_room_yaml(room, out, schema_version="0.1-draft")
    return out


def test_v0_1_1_room_yaml_validates_against_v0_3_draft_schema(tmp_path: Path) -> None:
    """v0.1.1-shape YAML (no absorption block) validates against v0.3 draft schema."""
    room_path = _make_legacy_room_yaml(tmp_path)
    with room_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    schema = _load_schema("room_schema.draft.json")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    assert errors == [], f"Unexpected validation errors: {errors}"


def test_v0_1_1_room_yaml_validates_against_v0_3_strict_schema(tmp_path: Path) -> None:
    """v0.1.1-shape YAML (no absorption block) validates against v0.3 strict schema."""
    from tests.fixtures.synthetic_rooms import shoebox

    # Strict schema requires version="0.1" (not "0.1-draft").
    room = shoebox()
    out = tmp_path / "room_strict.yaml"
    write_room_yaml(room, out, schema_version="0.1")

    with out.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    schema = _load_schema("room_schema.json")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    assert errors == [], f"Unexpected validation errors: {errors}"


def test_v0_3_writer_emits_absorption_block_when_bands_set(tmp_path: Path) -> None:
    """Writer emits absorption: {a125,...,a4000} when absorption_bands is non-None."""
    from tests.fixtures.synthetic_rooms import shoebox

    room = shoebox()
    # Replace first surface with one that has absorption_bands set.
    mat = MaterialLabel.WALL_PAINTED
    bands = MaterialAbsorptionBands[mat]
    surface_with_bands = Surface(
        kind=room.surfaces[0].kind,
        polygon=room.surfaces[0].polygon,
        material=mat,
        absorption_500hz=MaterialAbsorption[mat],
        absorption_bands=bands,
    )
    import dataclasses
    new_surfaces = [surface_with_bands] + list(room.surfaces[1:])
    room_with_bands = dataclasses.replace(room, surfaces=new_surfaces)

    out = tmp_path / "room_bands.yaml"
    write_room_yaml(room_with_bands, out, schema_version="0.1-draft")

    with out.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    surface_dict = data["surfaces"][0]
    assert "absorption" in surface_dict, "absorption block missing from emitted YAML"
    ab = surface_dict["absorption"]
    for key in ("a125", "a250", "a500", "a1000", "a2000", "a4000"):
        assert key in ab, f"key {key!r} missing from absorption block"


def test_v0_3_reader_returns_none_for_legacy_yaml(tmp_path: Path) -> None:
    """Reader returns absorption_bands=None when absorption block is absent."""
    # Hand-author a minimal legacy YAML without absorption block.
    legacy_yaml = textwrap.dedent("""\
        version: "0.1-draft"
        name: legacy_room
        ceiling_height_m: 2.8
        floor_polygon:
          - {x: -2.5, z: -2.0}
          - {x: 2.5, z: -2.0}
          - {x: 2.5, z: 2.0}
          - {x: -2.5, z: 2.0}
        listener_area:
          centroid: {x: 0.0, z: 0.0}
          polygon:
            - {x: -0.75, z: -0.75}
            - {x: 0.75, z: -0.75}
            - {x: 0.75, z: 0.75}
            - {x: -0.75, z: 0.75}
          height_m: 1.2
        surfaces:
          - kind: floor
            material: wood_floor
            absorption_500hz: 0.10
            polygon:
              - {x: -2.5, y: 0.0, z: -2.0}
              - {x: 2.5, y: 0.0, z: -2.0}
              - {x: 2.5, y: 0.0, z: 2.0}
              - {x: -2.5, y: 0.0, z: 2.0}
          - kind: ceiling
            material: ceiling_drywall
            absorption_500hz: 0.10
            polygon:
              - {x: -2.5, y: 2.8, z: -2.0}
              - {x: 2.5, y: 2.8, z: -2.0}
              - {x: 2.5, y: 2.8, z: 2.0}
              - {x: -2.5, y: 2.8, z: 2.0}
          - kind: wall
            material: wall_painted
            absorption_500hz: 0.05
            polygon:
              - {x: -2.5, y: 0.0, z: -2.0}
              - {x: 2.5, y: 0.0, z: -2.0}
              - {x: 2.5, y: 2.8, z: -2.0}
              - {x: -2.5, y: 2.8, z: -2.0}
    """)
    room_path = tmp_path / "legacy.yaml"
    room_path.write_text(legacy_yaml, encoding="utf-8")

    room = read_room_yaml(room_path)
    for surface in room.surfaces:
        assert surface.absorption_bands is None, (
            f"Expected absorption_bands=None for legacy YAML surface {surface.kind}, "
            f"got {surface.absorption_bands}"
        )
