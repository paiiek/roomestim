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


# --------------------------------------------------------------------------- #
# Cycle B — non-shoebox (concave) floor reconstruction
# --------------------------------------------------------------------------- #


def _write_l_prism_obj(path: Path) -> None:
    """Write a watertight L-shaped prism mesh (no committed binary fixture).

    Footprint corners (x, z), CCW; y is up; extruded 2.5 m tall. The L is a
    6 m × 6 m square minus a 3 m × 3 m notch (x > 3 and z > 3). Faces are
    authored by hand (side quads + floor/ceiling fans) so no triangulation
    engine is required. The sparse 12-vertex cloud is enough for the concave
    hull to recover all 6 footprint corners.
    """
    import numpy as np
    import trimesh

    foot = [(0.0, 0.0), (6.0, 0.0), (6.0, 3.0), (3.0, 3.0), (3.0, 6.0), (0.0, 6.0)]
    h = 2.5
    n = len(foot)
    bottom = [(x, 0.0, z) for (x, z) in foot]
    top = [(x, h, z) for (x, z) in foot]
    verts = np.array(bottom + top, dtype=float)
    faces: list[list[int]] = []
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, j + n])
        faces.append([i, j + n, i + n])
    for i in range(1, n - 1):  # floor fan
        faces.append([0, i + 1, i])
    for i in range(1, n - 1):  # ceiling fan
        faces.append([n, n + i, n + i + 1])
    mesh = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=False)
    mesh.export(path)


def test_mesh_adapter_default_is_convex_byte_equal() -> None:
    """B2(a): the default adapter still takes the convex hull (no regression).

    A box fixture parsed through the default ``MeshAdapter()`` yields the SAME
    floor polygon as parsing through an explicit ``floor_reconstruction=
    "convex"`` adapter — value-equal vertex list.
    """
    default_room = MeshAdapter().parse(FIXTURE_DIR / "lab_room.obj")
    explicit_convex = MeshAdapter(floor_reconstruction="convex").parse(
        FIXTURE_DIR / "lab_room.obj"
    )
    default_coords = [(p.x, p.z) for p in default_room.floor_polygon]
    convex_coords = [(p.x, p.z) for p in explicit_convex.floor_polygon]
    assert default_coords == convex_coords
    # A shoebox floor is a 4-vertex rectangle under either path.
    assert len(default_coords) == 4


def test_mesh_adapter_concave_mode_constructor(tmp_path: Path) -> None:
    """B2(b): concave mode (constructor) round-trips an L-mesh with a notch."""
    obj_path = tmp_path / "l_room.obj"
    _write_l_prism_obj(obj_path)

    room = MeshAdapter(floor_reconstruction="concave").parse(obj_path)

    assert isinstance(room, RoomModel)
    # Concave keeps the re-entrant corner → more than 4 floor vertices.
    assert len(room.floor_polygon) > 4
    walls = [s for s in room.surfaces if s.kind == "wall"]
    assert len(walls) == len(room.floor_polygon), "one wall per floor edge"

    # Concave footprint area is strictly smaller than the convex bounding hull.
    concave_area = float(
        ShapelyPolygon([(p.x, p.z) for p in room.floor_polygon]).area
    )
    convex_room = MeshAdapter().parse(obj_path)
    convex_area = float(
        ShapelyPolygon([(p.x, p.z) for p in convex_room.floor_polygon]).area
    )
    assert concave_area < convex_area


def test_mesh_adapter_concave_mode_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B2(b): the ``ROOMESTIM_MESH_FLOOR_RECON`` env var opts into concave mode."""
    obj_path = tmp_path / "l_room.obj"
    _write_l_prism_obj(obj_path)

    monkeypatch.setenv("ROOMESTIM_MESH_FLOOR_RECON", "concave")
    room = MeshAdapter().parse(obj_path)
    assert len(room.floor_polygon) > 4


def test_mesh_adapter_explicit_arg_overrides_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Precedence: an explicit constructor arg wins over the env override."""
    obj_path = tmp_path / "l_room.obj"
    _write_l_prism_obj(obj_path)

    monkeypatch.setenv("ROOMESTIM_MESH_FLOOR_RECON", "concave")
    room = MeshAdapter(floor_reconstruction="convex").parse(obj_path)
    # Convex erases the L's re-entrant corner: the hull cuts a single diagonal
    # across the notch, yielding a 5-vertex pentagon (vs the concave 6).
    assert len(room.floor_polygon) == 5


def test_mesh_adapter_invalid_env_value_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognized env value raises a clear ValueError at construction."""
    monkeypatch.setenv("ROOMESTIM_MESH_FLOOR_RECON", "bogus")
    with pytest.raises(ValueError, match="ROOMESTIM_MESH_FLOOR_RECON"):
        MeshAdapter()


def test_mesh_adapter_concave_degeneracy_falls_back_to_convex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B3: concave-mode degeneracy falls back to convex with a UserWarning.

    The concave reconstruction is monkeypatched to raise ``ValueError`` (the
    degeneracy signal); the adapter must still return a valid RoomModel by
    falling back to the convex hull, emitting a ``UserWarning`` that names the
    fallback reason.
    """
    import roomestim.adapters.mesh as mesh_mod

    def _boom(_vertices: object) -> object:
        raise ValueError("synthetic degeneracy")

    monkeypatch.setattr(mesh_mod, "floor_polygon_from_mesh", _boom)

    with pytest.warns(UserWarning, match="falling back to convex"):
        room = MeshAdapter(floor_reconstruction="concave").parse(
            FIXTURE_DIR / "lab_room.obj"
        )
    assert isinstance(room, RoomModel)
    # Fallback yields the convex shoebox floor (4 vertices).
    assert len(room.floor_polygon) == 4
