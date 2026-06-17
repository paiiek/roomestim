"""Phase 2 (combined glTF) + Phase 3 (user-supplied offsets) for RoomCollection.

All tests run under the DEFAULT pytest gate (roomplan JSON + mesh .ply ingest,
trimesh is a core dep). Honesty contract (ADR 0049): offsets are USER-SUPPLIED
only; absent ⇒ identity and byte-equal to the offset-free Phase-1 path; the
combined glTF is a visual assembly of independent rooms at user-asserted offsets.
"""

from __future__ import annotations

import json
from pathlib import Path

import trimesh
import yaml
from jsonschema import Draft202012Validator

from roomestim.cli import main
from roomestim.io.collection_yaml_reader import read_collection_yaml

_FIXTURES = Path(__file__).parent / "fixtures"
_LAB_JSON = _FIXTURES / "lab_room.json"
_LAB_PLY = _FIXTURES / "lab_room.ply"
_SCHEMA = (
    Path(__file__).parent.parent
    / "roomestim"
    / "proto"
    / "collection_schema.v0_1.draft.json"
)


def _ingest_pair(tmp_path: Path) -> tuple[Path, Path]:
    a = tmp_path / "A"
    b = tmp_path / "B"
    a.mkdir()
    b.mkdir()
    assert main(["ingest", "--backend", "roomplan", "--input", str(_LAB_JSON),
                 "--out-dir", str(a)]) == 0
    assert main(["ingest", "--backend", "polycam", "--input", str(_LAB_PLY),
                 "--out-dir", str(b)]) == 0
    return a / "room.yaml", b / "room.yaml"


# --------------------------------------------------------------------------- #
# Phase 3 — offsets
# --------------------------------------------------------------------------- #


def test_offsets_roundtrip_in_manifest(tmp_path: Path) -> None:
    room_a, room_b = _ingest_pair(tmp_path)
    coll = tmp_path / "coll"
    assert main(["collection", "--in-rooms", str(room_a), str(room_b),
                 "--algorithm", "vbap", "--n-speakers", "8", "--name", "venue",
                 "--offsets", "1,2,3", "10,0,0",
                 "--out-dir", str(coll)]) == 0

    data = yaml.safe_load((coll / "collection.yaml").read_text(encoding="utf-8"))
    assert data["rooms"][0]["offset"] == [1.0, 2.0, 3.0]
    assert data["rooms"][1]["offset"] == [10.0, 0.0, 0.0]

    loaded = read_collection_yaml(coll / "collection.yaml")
    assert loaded.offsets == [(1.0, 2.0, 3.0), (10.0, 0.0, 0.0)]


def test_offset_absent_is_byte_equal_to_phase1(tmp_path: Path) -> None:
    """Offset absent on every room ⇒ Phase-1-identical manifest (no offset key)."""
    room_a, room_b = _ingest_pair(tmp_path)
    coll = tmp_path / "coll"
    assert main(["collection", "--in-rooms", str(room_a), str(room_b),
                 "--algorithm", "vbap", "--n-speakers", "8", "--name", "venue",
                 "--out-dir", str(coll)]) == 0

    manifest_text = (coll / "collection.yaml").read_text(encoding="utf-8")
    # No additive Phase-2/3 keys leak into the offset-free path.
    assert "offset" not in manifest_text
    assert "combined_ref" not in manifest_text
    data = yaml.safe_load(manifest_text)
    for entry in data["rooms"]:
        assert set(entry.keys()) == {"name", "room_ref", "layout_ref"}
    assert set(data.keys()) == {"version", "name", "rooms"}


def test_offsets_count_mismatch_errors(tmp_path: Path) -> None:
    room_a, room_b = _ingest_pair(tmp_path)
    coll = tmp_path / "coll"
    rc = main(["collection", "--in-rooms", str(room_a), str(room_b),
               "--algorithm", "vbap", "--n-speakers", "8",
               "--offsets", "1,2,3",  # only one offset for two rooms
               "--out-dir", str(coll)])
    assert rc == 1


def test_offset_malformed_token_errors(tmp_path: Path) -> None:
    room_a, room_b = _ingest_pair(tmp_path)
    coll = tmp_path / "coll"
    rc = main(["collection", "--in-rooms", str(room_a), str(room_b),
               "--algorithm", "vbap", "--n-speakers", "8",
               "--offsets", "1,2", "3,4,5",  # first token has 2 components
               "--out-dir", str(coll)])
    assert rc == 1


def test_offset_non_finite_errors(tmp_path: Path) -> None:
    """NaN/inf offset components are rejected (offsets must be finite metres)."""
    room_a, room_b = _ingest_pair(tmp_path)
    coll = tmp_path / "coll"
    rc = main(["collection", "--in-rooms", str(room_a), str(room_b),
               "--algorithm", "vbap", "--n-speakers", "8",
               "--offsets", "0,0,0", "1,nan,2",  # NaN component
               "--out-dir", str(coll)])
    assert rc == 1


# --------------------------------------------------------------------------- #
# Phase 2 — combined glTF
# --------------------------------------------------------------------------- #


def test_combined_glb_produced_and_offset_shifts_geometry(tmp_path: Path) -> None:
    room_a, room_b = _ingest_pair(tmp_path)

    # No offset: rooms overlap at origin.
    coll0 = tmp_path / "coll0"
    assert main(["collection", "--in-rooms", str(room_a), str(room_b),
                 "--algorithm", "vbap", "--n-speakers", "8",
                 "--combined-gltf", str(coll0 / "collection.glb"),
                 "--out-dir", str(coll0)]) == 0
    glb0 = coll0 / "collection.glb"
    assert glb0.exists()
    scene0 = trimesh.load(str(glb0))
    bounds0 = scene0.bounds  # (2,3) min/max

    # Second room shifted +100 m in x.
    coll1 = tmp_path / "coll1"
    assert main(["collection", "--in-rooms", str(room_a), str(room_b),
                 "--algorithm", "vbap", "--n-speakers", "8",
                 "--offsets", "0,0,0", "100,0,0",
                 "--combined-gltf", str(coll1 / "collection.glb"),
                 "--out-dir", str(coll1)]) == 0
    glb1 = coll1 / "collection.glb"
    assert glb1.exists()
    scene1 = trimesh.load(str(glb1))
    bounds1 = scene1.bounds

    # The +100 m x offset pushes the combined max-x at least ~100 m further out.
    assert bounds1[1][0] >= bounds0[1][0] + 90.0

    # combined_ref recorded relative to the manifest dir.
    data = yaml.safe_load((coll1 / "collection.yaml").read_text(encoding="utf-8"))
    assert data["combined_ref"] == "collection.glb"
    assert not Path(data["combined_ref"]).is_absolute()


def test_combined_scene_contains_each_room_translated(tmp_path: Path) -> None:
    """In-memory assembly: both rooms present (prefixed) and room1 is translated."""
    from roomestim.export.collection_gltf import build_combined_scene
    from roomestim.io.room_yaml_reader import read_room_yaml

    room_a, room_b = _ingest_pair(tmp_path)
    ra = read_room_yaml(room_a)
    rb = read_room_yaml(room_b)

    from roomestim.collection import RoomCollection

    base = RoomCollection(name="v", rooms=[ra, rb])
    shifted = RoomCollection(
        name="v", rooms=[ra, rb], offsets=[None, (100.0, 0.0, 0.0)]
    )
    scene_base = build_combined_scene(base)
    scene_shifted = build_combined_scene(shifted)

    # Both rooms contribute geometry, kept under per-room prefixes.
    geom_names = list(scene_base.geometry.keys())
    assert any(n.startswith("room0__") for n in geom_names)
    assert any(n.startswith("room1__") for n in geom_names)
    # Same geometry count regardless of offsets (pure translation).
    assert len(scene_shifted.geometry) == len(scene_base.geometry)

    # room1's geometry is shifted by +100 m in x; room0's is unchanged.
    for name, mesh in scene_base.geometry.items():
        smesh = scene_shifted.geometry[name]
        if name.startswith("room1__"):
            assert abs((smesh.bounds[0][0] - mesh.bounds[0][0]) - 100.0) < 1e-6
        else:
            assert abs(smesh.bounds[0][0] - mesh.bounds[0][0]) < 1e-6


# --------------------------------------------------------------------------- #
# Schema backward-compat
# --------------------------------------------------------------------------- #


def test_schema_backward_compat_v0_1_without_offset(tmp_path: Path) -> None:
    """A Phase-1 manifest (no offset / no combined_ref) still validates."""
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    v0_1 = {
        "version": "0.1-draft",
        "name": "venue",
        "rooms": [
            {"name": "r0", "room_ref": "room.r0.yaml", "layout_ref": "layout.r0.yaml"},
            {"name": "r1", "room_ref": "room.r1.yaml", "layout_ref": None},
        ],
    }
    assert not list(validator.iter_errors(v0_1))


def test_schema_accepts_offset_and_combined_ref(tmp_path: Path) -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    manifest = {
        "version": "0.1-draft",
        "name": "venue",
        "combined_ref": "collection.glb",
        "rooms": [
            {"name": "r0", "room_ref": "room.r0.yaml",
             "layout_ref": "layout.r0.yaml", "offset": [1.0, 2.0, 3.0]},
        ],
    }
    assert not list(validator.iter_errors(manifest))


def test_schema_rejects_bad_offset_length(tmp_path: Path) -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    bad = {
        "version": "0.1-draft",
        "name": "venue",
        "rooms": [
            {"name": "r0", "room_ref": "room.r0.yaml",
             "layout_ref": None, "offset": [1.0, 2.0]},  # only 2 components
        ],
    }
    assert list(validator.iter_errors(bad))
