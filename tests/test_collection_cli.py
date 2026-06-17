"""CLI end-to-end + load-bearing guards for the `collection` subcommand (ADR 0049).

These run under the DEFAULT pytest gate: both inputs (a roomplan JSON and a mesh
.ply) ingest with no extra dependencies. The headline test (Risk #1) asserts each
per-room layout.yaml produced by `collection` is BYTE-IDENTICAL to the same room
run through standalone `place` — the load-bearing "additive, no cross-talk" claim.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from roomestim.cli import main

_FIXTURES = Path(__file__).parent / "fixtures"
_LAB_JSON = _FIXTURES / "lab_room.json"
_LAB_PLY = _FIXTURES / "lab_room.ply"


def _ingest_roomplan(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rc = main(
        ["ingest", "--backend", "roomplan", "--input", str(_LAB_JSON),
         "--out-dir", str(out_dir)]
    )
    assert rc == 0
    return out_dir / "room.yaml"


def _ingest_mesh(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rc = main(
        ["ingest", "--backend", "polycam", "--input", str(_LAB_PLY),
         "--out-dir", str(out_dir)]
    )
    assert rc == 0
    return out_dir / "room.yaml"


def _manifest_layouts_by_name(coll_dir: Path) -> dict[str, Path]:
    data = yaml.safe_load((coll_dir / "collection.yaml").read_text(encoding="utf-8"))
    return {e["name"]: coll_dir / e["layout_ref"] for e in data["rooms"]}


def test_collection_writes_manifest_and_per_room_files(tmp_path: Path) -> None:
    room_a = _ingest_roomplan(tmp_path / "A")
    room_b = _ingest_mesh(tmp_path / "B")
    coll = tmp_path / "coll"

    rc = main(
        ["collection", "--in-rooms", str(room_a), str(room_b),
         "--algorithm", "vbap", "--n-speakers", "8", "--name", "venue",
         "--out-dir", str(coll)]
    )
    assert rc == 0
    manifest = coll / "collection.yaml"
    assert manifest.exists()
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    assert data["version"] == "0.1-draft"
    assert data["name"] == "venue"
    assert len(data["rooms"]) == 2
    for entry in data["rooms"]:
        assert (coll / entry["room_ref"]).exists()
        assert (coll / entry["layout_ref"]).exists()
        # Risk #3: refs are relative, not absolute.
        assert not Path(entry["room_ref"]).is_absolute()
        assert not Path(entry["layout_ref"]).is_absolute()


def test_collection_layout_byte_equal_to_standalone_place(tmp_path: Path) -> None:
    """Risk #1 (load-bearing): per-room collection layout == standalone place."""
    room_a = _ingest_roomplan(tmp_path / "A")
    room_b = _ingest_mesh(tmp_path / "B")

    # Standalone place for each room.
    pl_a = tmp_path / "plA"
    pl_b = tmp_path / "plB"
    assert main(["place", "--in-room", str(room_a), "--algorithm", "vbap",
                 "--n-speakers", "8", "--layout-radius", "2.0",
                 "--out-dir", str(pl_a)]) == 0
    assert main(["place", "--in-room", str(room_b), "--algorithm", "vbap",
                 "--n-speakers", "8", "--layout-radius", "2.0",
                 "--out-dir", str(pl_b)]) == 0

    # Collection.
    coll = tmp_path / "coll"
    assert main(["collection", "--in-rooms", str(room_a), str(room_b),
                 "--algorithm", "vbap", "--n-speakers", "8",
                 "--layout-radius", "2.0", "--name", "venue",
                 "--out-dir", str(coll)]) == 0

    layouts = _manifest_layouts_by_name(coll)
    # roomplan name == "lab_room_synthetic", mesh name == "lab_room".
    assert (pl_a / "layout.yaml").read_bytes() == layouts["lab_room_synthetic"].read_bytes()
    assert (pl_b / "layout.yaml").read_bytes() == layouts["lab_room"].read_bytes()


def test_collection_name_collision_suffixing(tmp_path: Path) -> None:
    """Risk #4: two same-named rooms get deterministic, distinct filenames."""
    room_a = _ingest_roomplan(tmp_path / "A")
    room_a2 = _ingest_roomplan(tmp_path / "A2")  # same name → collision

    coll = tmp_path / "coll"
    assert main(["collection", "--in-rooms", str(room_a), str(room_a2),
                 "--algorithm", "vbap", "--n-speakers", "8",
                 "--out-dir", str(coll)]) == 0

    data = yaml.safe_load((coll / "collection.yaml").read_text(encoding="utf-8"))
    layout_refs = [e["layout_ref"] for e in data["rooms"]]
    room_refs = [e["room_ref"] for e in data["rooms"]]
    # Distinct filenames despite identical room names; all on disk.
    assert len(set(layout_refs)) == 2
    assert len(set(room_refs)) == 2
    assert layout_refs == ["layout.lab_room_synthetic.yaml",
                           "layout.lab_room_synthetic-1.yaml"]
    for ref in room_refs + layout_refs:
        assert (coll / ref).exists()


def test_collection_requires_two_inputs(tmp_path: Path) -> None:
    room_a = _ingest_roomplan(tmp_path / "A")
    rc = main(["collection", "--in-rooms", str(room_a), "--out-dir", str(tmp_path / "c")])
    assert rc == 1  # ValueError -> exit 1
