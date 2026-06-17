"""Combined USD export for RoomCollection (ADR 0049, Phase 2 — USD parity).

USD parity of the combined glTF increment. These tests SKIP when ``pxr``
(usd-core) is absent — exactly like ``tests/test_cli_export_formats.py`` —
and RUN in the canonical env where ``pxr`` is installed.

Honesty contract (ADR 0049): offsets are USER-SUPPLIED only; absent ⇒ identity
and byte-equal to the no-flag path; the combined USD is a visual assembly of
independent rooms at user-asserted offsets (NO aggregate acoustics).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

from roomestim.cli import main

if importlib.util.find_spec("pxr") is None:  # pragma: no cover - env-gated
    pytest.skip("pxr (usd-core) not installed", allow_module_level=True)

_FIXTURES = Path(__file__).parent / "fixtures"
_LAB_JSON = _FIXTURES / "lab_room.json"
_LAB_PLY = _FIXTURES / "lab_room.ply"


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
# Combined USD — file produced + manifest ref
# --------------------------------------------------------------------------- #


def test_combined_usd_produced_and_manifest_ref(tmp_path: Path) -> None:
    room_a, room_b = _ingest_pair(tmp_path)
    coll = tmp_path / "coll"
    assert main(["collection", "--in-rooms", str(room_a), str(room_b),
                 "--algorithm", "vbap", "--n-speakers", "8", "--name", "venue",
                 "--offsets", "0,0,0", "100,0,0",
                 "--combined-usd", str(coll / "collection.usd"),
                 "--out-dir", str(coll)]) == 0
    usd_out = coll / "collection.usd"
    assert usd_out.exists()

    data = yaml.safe_load((coll / "collection.yaml").read_text(encoding="utf-8"))
    assert data["combined_usd_ref"] == "collection.usd"
    assert not Path(data["combined_usd_ref"]).is_absolute()


def test_combined_usdz_packaged(tmp_path: Path) -> None:
    """A ``.usdz`` suffix packages the stage (mirrors write_usdz)."""
    room_a, room_b = _ingest_pair(tmp_path)
    coll = tmp_path / "coll"
    assert main(["collection", "--in-rooms", str(room_a), str(room_b),
                 "--algorithm", "vbap", "--n-speakers", "8",
                 "--combined-usd", str(coll / "collection.usdz"),
                 "--out-dir", str(coll)]) == 0
    usdz = coll / "collection.usdz"
    assert usdz.exists()
    # No stray temporary .usdc layer left behind.
    assert not (coll / "collection.usdc").exists()


# --------------------------------------------------------------------------- #
# In-memory stage — each room present + offset translate applied
# --------------------------------------------------------------------------- #


def test_combined_stage_contains_each_room_translated(tmp_path: Path) -> None:
    from pxr import UsdGeom

    from roomestim.collection import RoomCollection
    from roomestim.export.collection_usd import build_combined_stage
    from roomestim.io.room_yaml_reader import read_room_yaml

    room_a, room_b = _ingest_pair(tmp_path)
    ra = read_room_yaml(room_a)
    rb = read_room_yaml(room_b)

    collection = RoomCollection(
        name="v", rooms=[ra, rb], offsets=[None, (100.0, 0.0, 0.0)]
    )
    stage = build_combined_stage(collection)

    # Both rooms contribute geometry under their per-room prefix.
    room0 = stage.GetPrimAtPath("/Collection/Room_0/Room")
    room1 = stage.GetPrimAtPath("/Collection/Room_1/Room")
    assert room0.IsValid()
    assert room1.IsValid()
    # Surface meshes survive the copy (geometry intact).
    assert stage.GetPrimAtPath("/Collection/Room_0/Room/Surfaces").IsValid()
    assert stage.GetPrimAtPath("/Collection/Room_1/Room/Surfaces").IsValid()
    mesh_count = sum(
        1 for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)
    )
    assert mesh_count > 0

    # Room_0 (no offset) carries NO translate op; Room_1 is translated +100 x.
    xf0 = UsdGeom.Xformable(stage.GetPrimAtPath("/Collection/Room_0"))
    assert [op.GetOpName() for op in xf0.GetOrderedXformOps()] == []

    xf1 = UsdGeom.Xformable(stage.GetPrimAtPath("/Collection/Room_1"))
    ops1 = xf1.GetOrderedXformOps()
    assert len(ops1) == 1
    translate = ops1[0].Get()
    assert (float(translate[0]), float(translate[1]), float(translate[2])) == (
        100.0,
        0.0,
        0.0,
    )


def test_offset_absent_no_translate_ops(tmp_path: Path) -> None:
    """No offsets ⇒ rooms overlap at origin (no translate op on any room)."""
    from pxr import UsdGeom

    from roomestim.collection import RoomCollection
    from roomestim.export.collection_usd import build_combined_stage
    from roomestim.io.room_yaml_reader import read_room_yaml

    room_a, room_b = _ingest_pair(tmp_path)
    collection = RoomCollection(
        name="v", rooms=[read_room_yaml(room_a), read_room_yaml(room_b)]
    )
    stage = build_combined_stage(collection)
    for idx in (0, 1):
        xf = UsdGeom.Xformable(stage.GetPrimAtPath(f"/Collection/Room_{idx}"))
        assert [op.GetOpName() for op in xf.GetOrderedXformOps()] == []


# --------------------------------------------------------------------------- #
# No-flag ⇒ prior outputs byte-equal
# --------------------------------------------------------------------------- #


def test_no_combined_usd_flag_is_byte_equal(tmp_path: Path) -> None:
    """Omitting --combined-usd leaves the manifest free of combined_usd_ref and
    byte-identical to an otherwise identical run (no USD artifact written)."""
    room_a, room_b = _ingest_pair(tmp_path)

    coll0 = tmp_path / "coll0"
    assert main(["collection", "--in-rooms", str(room_a), str(room_b),
                 "--algorithm", "vbap", "--n-speakers", "8", "--name", "venue",
                 "--out-dir", str(coll0)]) == 0

    coll1 = tmp_path / "coll1"
    assert main(["collection", "--in-rooms", str(room_a), str(room_b),
                 "--algorithm", "vbap", "--n-speakers", "8", "--name", "venue",
                 "--out-dir", str(coll1)]) == 0

    text0 = (coll0 / "collection.yaml").read_text(encoding="utf-8")
    text1 = (coll1 / "collection.yaml").read_text(encoding="utf-8")
    assert text0 == text1
    assert "combined_usd_ref" not in text0
    assert not list(coll0.glob("*.usd"))
    assert not list(coll0.glob("*.usdz"))
    assert not list(coll0.glob("*.usdc"))


def test_combined_gltf_does_not_emit_usd_ref(tmp_path: Path) -> None:
    """The glTF path stays orthogonal: no combined_usd_ref leaks when only
    --combined-gltf is passed."""
    room_a, room_b = _ingest_pair(tmp_path)
    coll = tmp_path / "coll"
    assert main(["collection", "--in-rooms", str(room_a), str(room_b),
                 "--algorithm", "vbap", "--n-speakers", "8",
                 "--combined-gltf", str(coll / "collection.glb"),
                 "--out-dir", str(coll)]) == 0
    text = (coll / "collection.yaml").read_text(encoding="utf-8")
    assert "combined_ref" in text
    assert "combined_usd_ref" not in text
