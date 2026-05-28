"""Tests for ``roomestim.adapters.mesh.MeshAdapter`` — P2 acceptance.

Parametrised over 4 mesh formats: .obj, .gltf, .glb, .ply.
Each asserts that ``MeshAdapter().parse(fixture)`` returns a ``RoomModel``
consistent with the synthetic 4 m × 4 m × 2.5 m shoebox.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.adapters import MeshAdapter
from roomestim.model import MaterialLabel, RoomModel

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

# Parametrise over all 4 supported mesh formats.
MESH_FIXTURES = [
    pytest.param(FIXTURE_DIR / "lab_room.obj", id="obj"),
    pytest.param(FIXTURE_DIR / "lab_room.gltf", id="gltf"),
    pytest.param(FIXTURE_DIR / "lab_room.glb", id="glb"),
    pytest.param(FIXTURE_DIR / "lab_room.ply", id="ply"),
]


def _floor_area(room: RoomModel) -> float:
    coords = [(p.x, p.z) for p in room.floor_polygon]
    return float(ShapelyPolygon(coords).area)


@pytest.mark.parametrize("fixture_path", MESH_FIXTURES)
def test_mesh_adapter_parses_shoebox(fixture_path: Path) -> None:
    """All 4 mesh formats produce a RoomModel with the expected shoebox dims."""
    room = MeshAdapter().parse(fixture_path)

    assert isinstance(room, RoomModel)
    assert room.schema_version == "0.2-draft"
    assert room.ceiling_height_m == pytest.approx(2.5, abs=0.10), (
        f"ceiling height {room.ceiling_height_m} not ~2.5 m"
    )

    area = _floor_area(room)
    assert area == pytest.approx(16.0, rel=0.05), (
        f"floor area {area} not within 5% of 16.0"
    )

    walls = [s for s in room.surfaces if s.kind == "wall"]
    assert len(walls) >= 4, f"expected >=4 walls, got {len(walls)}"

    # Default material triple unchanged
    floor_surfaces = [s for s in room.surfaces if s.kind == "floor"]
    ceiling_surfaces = [s for s in room.surfaces if s.kind == "ceiling"]
    assert floor_surfaces[0].material == MaterialLabel.WOOD_FLOOR
    assert ceiling_surfaces[0].material == MaterialLabel.CEILING_DRYWALL
    assert all(s.material == MaterialLabel.WALL_PAINTED for s in walls)


def test_mesh_adapter_usdz_raises() -> None:
    """USDZ raises NotImplementedError regardless of file existence."""
    with pytest.raises(NotImplementedError):
        MeshAdapter().parse(FIXTURE_DIR / "missing.usdz")


def test_mesh_adapter_unsupported_extension_raises() -> None:
    """Unknown extensions raise ValueError."""
    with pytest.raises(ValueError):
        MeshAdapter().parse(FIXTURE_DIR / "missing.json")


def test_mesh_adapter_vertex_color_ply() -> None:
    """PLY with per-vertex RGB colour still parses correctly (faces present)."""
    room = MeshAdapter().parse(FIXTURE_DIR / "lab_room_vertex_color.ply")
    assert isinstance(room, RoomModel)
    assert room.ceiling_height_m == pytest.approx(2.5, abs=0.10)


def test_mesh_adapter_points_only_ply_raises() -> None:
    """OQ-21: a points-only PLY (0 faces) raises a clear ValueError.

    ``trimesh.load(force="mesh")`` yields a Trimesh with ``len(faces)==0`` for a
    points-only export; the ``(N, 3)`` vertex-shape check does NOT catch it. The
    no-faces guard must reject it before the undefined convex-hull path.
    """
    with pytest.raises(ValueError, match="0 faces"):
        MeshAdapter().parse(FIXTURE_DIR / "points_only.ply")


# --------------------------------------------------------------------------- #
# OQ-45 / ADR 0038 — input resource bounds (DoS guard)
# --------------------------------------------------------------------------- #


def test_mesh_adapter_vertex_cap_rejects_over_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0038: monkeypatching the vertex cap LOW makes a normal fixture exceed it.

    No huge fixture is committed — the existing shoebox has far more than 3
    vertices, so a cap of 3 forces the ValueError on a real parse path.
    """
    import roomestim.adapters.mesh as mesh_mod

    monkeypatch.setattr(mesh_mod, "_MAX_MESH_VERTICES", 3)
    with pytest.raises(ValueError, match="vertices, exceeding"):
        MeshAdapter().parse(FIXTURE_DIR / "lab_room.obj")


def test_mesh_adapter_byte_cap_rejects_over_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0038: monkeypatching the byte cap LOW makes a normal fixture exceed it."""
    import roomestim.adapters.mesh as mesh_mod

    monkeypatch.setattr(mesh_mod, "_MAX_MESH_FILE_BYTES", 1)
    with pytest.raises(ValueError, match="bytes, exceeding"):
        MeshAdapter().parse(FIXTURE_DIR / "lab_room.obj")


def test_mesh_adapter_default_bounds_leave_fixtures_unaffected() -> None:
    """Default caps are far above the test fixtures — the shoebox still parses."""
    import roomestim.adapters.mesh as mesh_mod

    assert mesh_mod._MAX_MESH_FILE_BYTES == 200 * 1024 * 1024
    assert mesh_mod._MAX_MESH_VERTICES == 5_000_000
    room = MeshAdapter().parse(FIXTURE_DIR / "lab_room.obj")
    assert isinstance(room, RoomModel)
