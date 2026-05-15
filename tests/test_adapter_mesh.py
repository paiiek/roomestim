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
    assert room.schema_version == "0.1-draft"
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
