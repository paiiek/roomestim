"""CLI end-to-end + load-bearing guard for the `structure` subcommand (ADR 0050).

Runs under the DEFAULT pytest gate (the real CapturedStructure fixtures ingest
with no extra dependencies). The headline test asserts each per-room layout.yaml
produced by `structure` is BYTE-IDENTICAL to the same emitted room.yaml run
through standalone `place` — the load-bearing "additive, no cross-talk" proof.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

from roomestim.cli import main

_FIXTURES = Path(__file__).parent / "fixtures" / "roomplan_real"
_MULTI = _FIXTURES / "capturedstructure_multiroom.json"
_SINGLE = _FIXTURES / "capturedstructure_single.json"


def _manifest(coll_dir: Path) -> dict[str, object]:
    return yaml.safe_load((coll_dir / "collection.yaml").read_text(encoding="utf-8"))


def test_structure_writes_per_room_files_and_manifest(tmp_path: Path) -> None:
    out = tmp_path / "out"
    rc = main(
        ["structure", "--in-structure", str(_MULTI), "--algorithm", "vbap",
         "--n-speakers", "8", "--name", "flat", "--out-dir", str(out)]
    )
    assert rc == 0
    data = _manifest(out)
    assert data["name"] == "flat"
    rooms = data["rooms"]
    assert len(rooms) == 4  # incl. unidentified
    names = [e["name"] for e in rooms]
    assert names == ["bedroom", "bedroom-2", "bathroom", "unidentified"]
    for entry in rooms:
        assert (out / entry["room_ref"]).exists()
        assert (out / entry["layout_ref"]).exists()
        assert not Path(entry["room_ref"]).is_absolute()
        assert not Path(entry["layout_ref"]).is_absolute()


def test_structure_layout_byte_equal_to_standalone_place(tmp_path: Path) -> None:
    """Load-bearing: each per-room `structure` layout == standalone `place`."""
    out = tmp_path / "out"
    assert main(
        ["structure", "--in-structure", str(_MULTI), "--algorithm", "vbap",
         "--n-speakers", "8", "--layout-radius", "2.0", "--name", "flat",
         "--out-dir", str(out)]
    ) == 0

    data = _manifest(out)
    for entry in data["rooms"]:
        room_path = out / entry["room_ref"]
        struct_layout = out / entry["layout_ref"]
        # Standalone place on the emitted room.yaml.
        pl = tmp_path / f"pl_{entry['name']}"
        assert main(
            ["place", "--in-room", str(room_path), "--algorithm", "vbap",
             "--n-speakers", "8", "--layout-radius", "2.0", "--out-dir", str(pl)]
        ) == 0
        assert (pl / "layout.yaml").read_bytes() == struct_layout.read_bytes()


def test_structure_single_section(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main(
        ["structure", "--in-structure", str(_SINGLE), "--algorithm", "vbap",
         "--out-dir", str(out)]
    ) == 0
    data = _manifest(out)
    assert len(data["rooms"]) == 1
    assert data["rooms"][0]["name"] == "livingRoom"


def test_structure_combined_gltf(tmp_path: Path) -> None:
    """S2: --combined-gltf reuses the ADR 0049 collection writer; the combined
    file is written and the manifest records a relative combined_ref."""
    out = tmp_path / "out"
    glb = out / "structure.glb"
    assert main(
        ["structure", "--in-structure", str(_MULTI), "--algorithm", "vbap",
         "--combined-gltf", str(glb), "--out-dir", str(out)]
    ) == 0
    assert glb.exists() and glb.stat().st_size > 0
    data = _manifest(out)
    assert data["combined_ref"] == "structure.glb"
    assert not Path(data["combined_ref"]).is_absolute()


def test_structure_no_combined_flag_omits_ref(tmp_path: Path) -> None:
    """Without --combined-gltf/--combined-usd the manifest carries no ref key
    (Phase S1 byte-shape preserved)."""
    out = tmp_path / "out"
    assert main(
        ["structure", "--in-structure", str(_MULTI), "--algorithm", "vbap",
         "--out-dir", str(out)]
    ) == 0
    data = _manifest(out)
    assert "combined_ref" not in data
    assert "combined_usd_ref" not in data


@pytest.mark.skipif(
    importlib.util.find_spec("pxr") is None, reason="pxr (usd-core) not installed"
)
def test_structure_combined_usd(tmp_path: Path) -> None:
    """S2: --combined-usd reuses the ADR 0049 collection USD writer (skip if pxr
    absent)."""
    out = tmp_path / "out"
    usd = out / "structure.usd"
    assert main(
        ["structure", "--in-structure", str(_MULTI), "--algorithm", "vbap",
         "--combined-usd", str(usd), "--out-dir", str(out)]
    ) == 0
    assert usd.exists() and usd.stat().st_size > 0
    data = _manifest(out)
    assert data["combined_usd_ref"] == "structure.usd"
    assert not Path(data["combined_usd_ref"]).is_absolute()
