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


def test_mesh_adapter_usdz_no_longer_raises_not_implemented() -> None:
    """Phase 1: ``.usdz`` is a real loader now, not a NotImplementedError stub.

    Parsing a committed USDZ fixture must NOT raise ``NotImplementedError``
    (the old behaviour). It requires pxr; skip cleanly if the [usd] extra is
    absent so this stays green on a no-USD install.
    """
    pytest.importorskip("pxr")
    fixture = FIXTURE_DIR / "shoebox_yup.usdz"
    if not fixture.exists():
        pytest.skip("shoebox_yup.usdz fixture not found")
    try:
        room = MeshAdapter().parse(fixture)
    except NotImplementedError:  # pragma: no cover - regression guard
        pytest.fail("MeshAdapter.parse(.usdz) still raises NotImplementedError")
    assert isinstance(room, RoomModel)


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


def _write_dense_l_prism_obj(path: Path) -> None:
    """Write a DENSE L-prism mesh (subdivided) for the occupancy footprint mode.

    The occupancy grid needs many vertices per 5 cm cell; the sparse 12-vertex
    ``_write_l_prism_obj`` would put ~1 vertex per cell and fail ``min_count``.
    Subdividing every edge below 4 cm packs the floor/walls densely enough for
    the occupancy path to recover the true L footprint.
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
    for i in range(1, n - 1):
        faces.append([0, i + 1, i])
    for i in range(1, n - 1):
        faces.append([n, n + i, n + i + 1])
    dense_v, dense_f = trimesh.remesh.subdivide_to_size(
        verts, np.array(faces), max_edge=0.04
    )
    mesh = trimesh.Trimesh(vertices=dense_v, faces=dense_f, process=False)
    mesh.export(path)


def test_mesh_adapter_occupancy_mode_constructor(tmp_path: Path) -> None:
    """Phase B: occupancy mode (constructor) round-trips a dense L-mesh with a notch."""
    obj_path = tmp_path / "dense_l.obj"
    _write_dense_l_prism_obj(obj_path)

    room = MeshAdapter(floor_reconstruction="occupancy").parse(obj_path)

    assert isinstance(room, RoomModel)
    assert room.provenance == "measured"
    # Occupancy keeps the re-entrant corner → more than 4 floor vertices.
    assert len(room.floor_polygon) > 4
    walls = [s for s in room.surfaces if s.kind == "wall"]
    assert len(walls) == len(room.floor_polygon), "one wall per floor edge"
    # Recovers the true L area (27 m²), not the convex bounding hull.
    area = float(ShapelyPolygon([(p.x, p.z) for p in room.floor_polygon]).area)
    assert area == pytest.approx(27.0, rel=0.10)


def test_mesh_adapter_occupancy_mode_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase B: ``ROOMESTIM_MESH_FLOOR_RECON=occupancy`` opts into occupancy mode."""
    obj_path = tmp_path / "dense_l.obj"
    _write_dense_l_prism_obj(obj_path)

    monkeypatch.setenv("ROOMESTIM_MESH_FLOOR_RECON", "occupancy")
    room = MeshAdapter().parse(obj_path)
    assert len(room.floor_polygon) > 4


def test_mesh_adapter_occupancy_explicit_arg_overrides_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Precedence: ctor convex wins over env=occupancy (uses the sparse L-prism)."""
    obj_path = tmp_path / "l_room.obj"
    _write_l_prism_obj(obj_path)

    monkeypatch.setenv("ROOMESTIM_MESH_FLOOR_RECON", "occupancy")
    room = MeshAdapter(floor_reconstruction="convex").parse(obj_path)
    # Convex erases the L's re-entrant corner → a 5-vertex pentagon hull.
    assert len(room.floor_polygon) == 5


def test_mesh_adapter_occupancy_degeneracy_falls_back_to_convex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase B: occupancy degeneracy falls back to convex with a UserWarning."""
    import roomestim.adapters.mesh as mesh_mod

    def _boom(_vertices: object) -> object:
        raise ValueError("synthetic occupancy degeneracy")

    monkeypatch.setattr(mesh_mod, "floor_polygon_from_mesh_occupancy", _boom)

    with pytest.warns(UserWarning, match="falling back to convex"):
        room = MeshAdapter(floor_reconstruction="occupancy").parse(
            FIXTURE_DIR / "lab_room.obj"
        )
    assert isinstance(room, RoomModel)
    # Fallback yields the convex shoebox floor (4 vertices).
    assert len(room.floor_polygon) == 4


def test_mesh_adapter_occupancy_env_value_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative-of-negative: ``occupancy`` is a now-VALID env value (no ValueError).

    Contrast ``test_mesh_adapter_invalid_env_value_raises`` (``bogus`` raises);
    construction alone exercises the resolver, so no dense parse is needed.
    """
    monkeypatch.setenv("ROOMESTIM_MESH_FLOOR_RECON", "occupancy")
    adapter = MeshAdapter()
    assert adapter._floor_reconstruction == "occupancy"


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


# --------------------------------------------------------------------------- #
# robust floor reconstruction (density-percentile boundary trim)
# --------------------------------------------------------------------------- #
#
# Validated n=1 SCRREAM noise sweep (scrream-gt/scrream_seg_frontend_proto.py):
# vertex noise inflates the concave footprint monotonically and the boundary
# trim roughly HALVES that over-read while leaving clean input unchanged. The
# tests assert DIRECTIONS/inequalities, never the n=1-specific percentages.


def _robust_floor_band_vertices(*, sigma: float = 0.0) -> "object":
    """Y-up (N, 3) floor-band cloud of a 4 m x 3 m rectangle (GT area 12 m²).

    Dense interior grid + a reinforced perimeter ring (mimicking a real floor-
    wall junction, so a clean boundary survives the trim). With ``sigma > 0`` a
    seeded Gaussian XZ spray pushes boundary points outward, inflating the raw
    concave hull — the over-read the density trim targets.
    """
    import numpy as np

    rng = np.random.default_rng(42)
    xs = np.linspace(0.0, 4.0, 81)
    zs = np.linspace(0.0, 3.0, 61)
    gx, gz = np.meshgrid(xs, zs)
    interior = np.column_stack([gx.ravel(), gz.ravel()])
    t = np.linspace(0.0, 4.0, 400)
    s = np.linspace(0.0, 3.0, 300)
    edges = np.vstack(
        [
            np.column_stack([t, np.zeros_like(t)]),
            np.column_stack([t, np.full_like(t, 3.0)]),
            np.column_stack([np.zeros_like(s), s]),
            np.column_stack([np.full_like(s, 4.0), s]),
        ]
    )
    xz = np.vstack([interior, edges, edges])
    if sigma > 0.0:
        xz = xz + rng.normal(0.0, sigma, xz.shape)
    return np.column_stack([xz[:, 0], np.zeros(len(xz)), xz[:, 1]])


def _poly_area(poly: "object") -> float:
    return float(ShapelyPolygon([(p.x, p.z) for p in poly]).area)  # type: ignore[attr-defined]


def test_floor_robust_reduces_noise_overestimate() -> None:
    """Robust trim shrinks the noise-inflated footprint toward the clean GT.

    Asserts only DIRECTION (the validated n=1 8.3% figure is NOT hard-coded):
    on a noisy cloud the robust footprint is strictly smaller than the raw
    concave footprint AND materially closer to the clean GT area (12 m²).
    """
    from roomestim.reconstruct.floor_polygon import (
        floor_polygon_from_mesh,
        floor_polygon_robust,
    )

    gt_area = 12.0  # the clean 4 m x 3 m rectangle
    noisy = _robust_floor_band_vertices(sigma=0.05)
    concave_area = _poly_area(floor_polygon_from_mesh(noisy))
    robust_area = _poly_area(floor_polygon_robust(noisy))

    # Both over-read on noisy input; robust over-reads strictly less.
    assert robust_area < concave_area
    # ...and lands materially closer to truth than the raw concave hull.
    assert abs(robust_area - gt_area) < abs(concave_area - gt_area)


def test_floor_robust_matches_concave_on_clean_dense_input() -> None:
    """On clean dense input the trim is harmless: robust area ≈ concave area."""
    from roomestim.reconstruct.floor_polygon import (
        floor_polygon_from_mesh,
        floor_polygon_robust,
    )

    clean = _robust_floor_band_vertices(sigma=0.0)
    concave_area = _poly_area(floor_polygon_from_mesh(clean))
    robust_area = _poly_area(floor_polygon_robust(clean))
    assert robust_area == pytest.approx(concave_area, rel=0.01)


def test_floor_robust_deterministic() -> None:
    """Same input → bit-for-bit identical polygon (no RNG, no order sensitivity)."""
    from roomestim.reconstruct.floor_polygon import floor_polygon_robust

    verts = _robust_floor_band_vertices(sigma=0.05)
    poly_a = floor_polygon_robust(verts)
    poly_b = floor_polygon_robust(verts)
    assert [(p.x, p.z) for p in poly_a] == [(p.x, p.z) for p in poly_b]


def test_floor_robust_falls_back_on_degenerate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Robust degeneracy falls back to convex with a UserWarning.

    Mirrors the concave/occupancy fallback tests: the robust reconstruction is
    monkeypatched to raise ``ValueError`` so the MeshAdapter caller's try/except
    converts it into a convex-hull fallback with a ``UserWarning``.
    """
    import roomestim.adapters.mesh as mesh_mod

    def _boom(_vertices: object) -> object:
        raise ValueError("synthetic robust degeneracy")

    monkeypatch.setattr(mesh_mod, "floor_polygon_robust", _boom)

    with pytest.warns(UserWarning, match="falling back to convex"):
        room = MeshAdapter(floor_reconstruction="robust").parse(
            FIXTURE_DIR / "lab_room.obj"
        )
    assert isinstance(room, RoomModel)
    # Fallback yields the convex shoebox floor (4 vertices).
    assert len(room.floor_polygon) == 4


def test_mesh_adapter_robust_env_value_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``robust`` is a now-VALID env value (no ValueError at construction)."""
    monkeypatch.setenv("ROOMESTIM_MESH_FLOOR_RECON", "robust")
    adapter = MeshAdapter()
    assert adapter._floor_reconstruction == "robust"


# --------------------------------------------------------------------------- #
# Phase 0 (commercialization plan 0a) — gravity / up-axis normalization
# --------------------------------------------------------------------------- #


def _write_box_obj(path: Path, up_axis: int) -> None:
    """Write a watertight 4 m x 4 m x 2.5 m box with the given up-axis.

    The footprint is 4 m x 4 m and the height (along ``up_axis``) is 2.5 m, so a
    correct up-axis detection must yield ceiling_height_m == 2.5 and floor area
    == 16 regardless of which axis gravity points along. ``up_axis == 1`` is the
    Y-up convention; ``up_axis == 2`` is the Z-up convention of real ARKit /
    RoomPlan scans.
    """
    import numpy as np
    import trimesh

    # Build a Y-up box, then permute axes so the height lands on ``up_axis``.
    base = trimesh.creation.box(extents=(4.0, 2.5, 4.0))
    verts = np.asarray(base.vertices, dtype=float)
    if up_axis == 0:  # height -> X
        verts = verts[:, [1, 0, 2]]
    elif up_axis == 2:  # height -> Z
        verts = verts[:, [0, 2, 1]]
    box = trimesh.Trimesh(vertices=verts, faces=base.faces, process=False)
    box.export(path)


@pytest.mark.parametrize("up_axis", [1, 2], ids=["y_up", "z_up"])
def test_mesh_adapter_detects_up_axis(tmp_path: Path, up_axis: int) -> None:
    """0a: the detector recovers the correct up-axis for Y-up and Z-up boxes.

    Both a Y-up box (synthetic/glTF convention) and a Z-up box (ARKit/RoomPlan)
    must yield the SAME RoomModel: ceiling height 2.5 m and floor area 16 m^2.
    Before the fix the Z-up box mistook the 4 m horizontal dimension for the
    ceiling height.
    """
    obj_path = tmp_path / f"box_up{up_axis}.obj"
    _write_box_obj(obj_path, up_axis)

    room = MeshAdapter().parse(obj_path)

    assert room.ceiling_height_m == pytest.approx(2.5, abs=0.05), (
        f"up_axis={up_axis}: ceiling height {room.ceiling_height_m} not ~2.5 m"
    )
    assert _floor_area(room) == pytest.approx(16.0, rel=0.05), (
        f"up_axis={up_axis}: floor area {_floor_area(room)} not ~16 m^2"
    )


def test_mesh_adapter_up_axis_override(tmp_path: Path) -> None:
    """0a: an explicit ``up_axis`` override forces the gravity axis.

    Forcing ``up_axis="x"`` on a Y-up box mislabels the 4 m horizontal X span as
    the height (4 m), proving the override actually drives extraction (and that
    auto-detect would otherwise have chosen Y).
    """
    obj_path = tmp_path / "box_yup.obj"
    _write_box_obj(obj_path, up_axis=1)

    forced = MeshAdapter(up_axis="x").parse(obj_path)
    assert forced.ceiling_height_m == pytest.approx(4.0, abs=0.05)

    auto = MeshAdapter().parse(obj_path)
    assert auto.ceiling_height_m == pytest.approx(2.5, abs=0.05)


def test_mesh_adapter_invalid_up_axis_raises() -> None:
    """An unrecognized ``up_axis`` raises a clear ValueError at construction."""
    with pytest.raises(ValueError, match="up_axis"):
        MeshAdapter(up_axis="diagonal")  # type: ignore[arg-type]


def test_mesh_adapter_ceiling_robust_to_vertical_outliers(tmp_path: Path) -> None:
    """0b: ceiling_height_m tracks the floor/ceiling PLANES, not scan outliers.

    Synthetic analogue of the Phase 0b real-scan bug. A clean, densely sampled
    box has its floor plane at y=0 and ceiling plane at y=2.5 (true height
    2.5 m). We add a handful of vertical OUTLIERS — points well below the floor
    (y=-0.8) and above the ceiling (y=+0.7), as furniture / scan noise produces
    on real captures. The naive full vertical extent would read ~4.0 m
    (0.7 - (-0.8) + 2.5); the robust density-peak estimate must reject the
    sparse outliers and recover ~2.5 m. On real ARKit scans this exact failure
    inflated ceilings by up to +1.34 m (Faro laser GT, 0b).
    """
    import numpy as np
    import trimesh

    # Dense clean box: floor plane at y=0, ceiling plane at y=2.5, 4 m x 4 m.
    box = trimesh.creation.box(extents=(4.0, 2.5, 4.0))
    box.apply_translation((0.0, 1.25, 0.0))  # y in [0, 2.5]
    box = box.subdivide().subdivide()  # densify the planes
    verts = np.asarray(box.vertices, dtype=float)

    # A few vertical outliers below the floor and above the ceiling.
    outliers = np.array(
        [
            [0.0, -0.8, 0.0],
            [1.0, -0.8, -1.0],
            [-1.5, -0.8, 0.5],
            [0.5, 3.2, 0.5],  # 2.5 + 0.7
            [-1.0, 3.2, 1.0],
        ],
        dtype=float,
    )
    all_verts = np.vstack([verts, outliers])
    # Reference the outliers from two triangles so the mesh stays a surface mesh
    # (the adapter rejects points-only PLYs); only vertices feed the histogram.
    n = len(verts)
    extra_faces = np.array([[n, n + 1, n + 2], [n + 2, n + 3, n + 4]], dtype=np.int64)
    all_faces = np.vstack([np.asarray(box.faces, dtype=np.int64), extra_faces])

    full_extent = float(all_verts[:, 1].max() - all_verts[:, 1].min())
    assert full_extent == pytest.approx(4.0, abs=0.05), (
        f"fixture sanity: full extent {full_extent} should be ~4.0 m"
    )

    mesh_path = tmp_path / "box_with_outliers.ply"
    mesh = trimesh.Trimesh(vertices=all_verts, faces=all_faces, process=False)
    mesh.export(mesh_path)

    # up_axis is pinned to Y so this isolates the 0b floor/ceiling-PLANE
    # robustness (the densified square box is deliberately up-axis-ambiguous; the
    # gravity detector has its own dedicated tests above).
    room = MeshAdapter(up_axis="y").parse(mesh_path)
    assert room.ceiling_height_m == pytest.approx(2.5, abs=0.1), (
        f"ceiling height {room.ceiling_height_m} not ~2.5 m — vertical outliers "
        f"(full extent {full_extent:.2f} m) leaked into the height (0b regression)."
    )


# --------------------------------------------------------------------------- #
# Up-axis HARDENING — planar-density discriminator (aspect-ratio-robust)
# --------------------------------------------------------------------------- #
#
# The original detector scored axes by extreme-slab convex-hull AREA. That picks
# the up-axis only when the room's shorter horizontal span exceeds the ceiling
# height; it silently picks a WALL axis for narrow/tall rooms (corridors,
# closets, small tall rooms) — part of the B2B input domain. The hardened
# detector uses a floor/ceiling planar-DENSITY signal (independent of aspect
# ratio) with area only as a tiebreaker for the sparse-corner-box degeneracy.


def _write_lidar_box_ply(
    path: Path,
    *,
    footprint_x: float,
    footprint_z: float,
    height: float,
    up_axis: int,
    floor_n: int = 8000,
    ceil_n: int = 8000,
    wall_n: int = 4000,
    seed: int = 0,
) -> None:
    """Write a points+faces box with REALISTIC LiDAR-like vertex density.

    A real depth/LiDAR scan packs most of its vertex mass onto the two large
    horizontal surfaces it sweeps (floor + ceiling); walls are comparatively
    sparse. An *area-weighted* face sampling does the OPPOSITE — for a corridor
    the two long side walls are the largest faces, so they would carry the most
    vertices and a density metric would mistake a wall plane for the floor. We
    therefore sample floor/ceiling densely and walls sparsely, matching the real
    ARKit distribution (verified: floor/ceiling bins ~5-10x denser than walls).
    The floor/ceiling are dense planes at the extremes along ``up_axis``, so the
    planar-density detector must recover ``up_axis`` regardless of footprint
    aspect ratio. A trivial triangle face is attached so the no-faces guard and
    trimesh's surface-mesh load both pass; geometry keys off the vertices only.
    """
    import numpy as np
    import trimesh

    rng = np.random.default_rng(seed)
    fx, fz, h = footprint_x, footprint_z, height
    floor = np.column_stack(
        [rng.uniform(0, fx, floor_n), np.zeros(floor_n), rng.uniform(0, fz, floor_n)]
    )
    ceil = np.column_stack(
        [rng.uniform(0, fx, ceil_n), np.full(ceil_n, h), rng.uniform(0, fz, ceil_n)]
    )
    per = wall_n // 4
    walls = [
        np.column_stack([rng.uniform(0, fx, per), rng.uniform(0, h, per), np.zeros(per)]),
        np.column_stack([rng.uniform(0, fx, per), rng.uniform(0, h, per), np.full(per, fz)]),
        np.column_stack([np.zeros(per), rng.uniform(0, h, per), rng.uniform(0, fz, per)]),
        np.column_stack([np.full(per, fx), rng.uniform(0, h, per), rng.uniform(0, fz, per)]),
    ]
    verts = np.vstack([floor, ceil, *walls])
    # Build in Y-up, then permute so the height lands on ``up_axis``.
    if up_axis == 0:
        verts = verts[:, [1, 0, 2]]
    elif up_axis == 2:
        verts = verts[:, [0, 2, 1]]
    # Every vertex must be referenced by a face, else trimesh's PLY/OBJ export
    # silently drops the unreferenced points (verified: 100 -> 3). Trim to a
    # multiple of 3 and group consecutive triples into faces. The triangles are
    # in-plane (3 points sampled on one surface) and never read by the detector,
    # which keys on vertex coordinates only — they exist purely to retain mass.
    n_keep = (verts.shape[0] // 3) * 3
    verts = verts[:n_keep]
    faces = np.arange(n_keep).reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    mesh.export(path)


@pytest.mark.parametrize("up_axis", [1, 2], ids=["y_up", "z_up"])
def test_mesh_adapter_corridor_detects_up_axis(tmp_path: Path, up_axis: int) -> None:
    """Narrow corridor (10 x 2 m, h 2.6 m): density picks the right up-axis.

    The reviewer's counterexample: the old AREA metric scored a corridor
    [x=5.2, y=26.0, z=20.0] and picked the WRONG (long-wall) axis by ~1.3x — a
    silent wrong answer a margin guard would not catch. The planar-density
    detector keys on the dense floor/ceiling planes instead, which sit at the
    extremes of the true up-axis regardless of the 5:1 footprint aspect ratio.
    """
    ply = tmp_path / f"corridor_up{up_axis}.ply"
    _write_lidar_box_ply(
        ply, footprint_x=10.0, footprint_z=2.0, height=2.6, up_axis=up_axis
    )

    room = MeshAdapter().parse(ply)

    assert room.ceiling_height_m == pytest.approx(2.6, abs=0.05), (
        f"corridor up={up_axis}: height {room.ceiling_height_m} not ~2.6 m "
        "(up-axis misdetected — picked a wall span)"
    )
    assert _floor_area(room) == pytest.approx(20.0, rel=0.05), (
        f"corridor up={up_axis}: floor area {_floor_area(room)} not ~20 m^2"
    )


@pytest.mark.parametrize("up_axis", [1, 2], ids=["y_up", "z_up"])
def test_mesh_adapter_tall_narrow_detects_up_axis(
    tmp_path: Path, up_axis: int
) -> None:
    """Tall/small room (2 x 2 m, h 4 m): density picks the right up-axis.

    Reviewer counterexample #2: the AREA metric picks a horizontal axis when the
    height exceeds the shorter horizontal span. The density detector is immune —
    the floor/ceiling are still the dense extreme planes along the up-axis.
    """
    ply = tmp_path / f"tall_up{up_axis}.ply"
    _write_lidar_box_ply(
        ply, footprint_x=2.0, footprint_z=2.0, height=4.0, up_axis=up_axis
    )

    room = MeshAdapter().parse(ply)

    assert room.ceiling_height_m == pytest.approx(4.0, abs=0.05), (
        f"tall up={up_axis}: height {room.ceiling_height_m} not ~4.0 m"
    )
    assert _floor_area(room) == pytest.approx(4.0, rel=0.05), (
        f"tall up={up_axis}: floor area {_floor_area(room)} not ~4 m^2"
    )


def test_mesh_adapter_corridor_density_beats_old_area_metric(tmp_path: Path) -> None:
    """Prove the density signal picks the up-axis where the old AREA metric failed.

    For a Z-up corridor the slab-AREA score still peaks on a wall axis (Y, the
    long side-wall plane), reproducing the original silent bug; the planar
    DENSITY score peaks on the true up-axis (Z). This pins the fix to the
    discriminator change, not to incidental fixture geometry.
    """
    import numpy as np
    import trimesh

    ply = tmp_path / "corridor_zup.ply"
    _write_lidar_box_ply(
        ply, footprint_x=10.0, footprint_z=2.0, height=2.6, up_axis=2
    )
    verts = np.asarray(trimesh.load(ply, force="mesh").vertices, dtype=float)

    area_scores = [
        max(MeshAdapter._slab_footprint_area(verts, a)) for a in range(3)
    ]
    density_scores = [MeshAdapter._planar_density(verts, a) for a in range(3)]

    # Old metric: a wall axis (not Z) wins -> the original silent wrong answer.
    assert int(np.argmax(area_scores)) != 2, (
        f"area scores {area_scores} unexpectedly already picked Z — fixture "
        "no longer reproduces the bug"
    )
    # New metric: Z (the true up-axis) wins, and by a real margin.
    assert int(np.argmax(density_scores)) == 2, (
        f"density scores {density_scores} did not pick Z"
    )
    srt = sorted(density_scores, reverse=True)
    assert srt[0] / srt[1] > 1.5, f"density margin too small: {density_scores}"


def test_mesh_adapter_near_cubic_ambiguous_raises(tmp_path: Path) -> None:
    """A perfect uniform-density cube is genuinely ambiguous → raises (no guess).

    When NEITHER the density nor the area signal favours an axis (a sparse
    axis-aligned cube: density ties 1/1/1, slab area ties), the detector must
    fail loud rather than silently return a low-confidence axis. The error must
    point the caller at the explicit ``up_axis`` override.
    """
    import numpy as np
    import trimesh

    cube = trimesh.creation.box(extents=(3.0, 3.0, 3.0))
    ply = tmp_path / "cube.ply"
    trimesh.Trimesh(
        vertices=np.asarray(cube.vertices, dtype=float),
        faces=np.asarray(cube.faces),
        process=False,
    ).export(ply)

    with pytest.raises(ValueError, match="ambiguous"):
        MeshAdapter().parse(ply)

    # The explicit override resolves it (the actionable recovery path).
    room = MeshAdapter(up_axis="z").parse(ply)
    assert room.ceiling_height_m == pytest.approx(3.0, abs=0.05)


def test_mesh_adapter_near_cubic_bedroom_detects_without_raising(
    tmp_path: Path,
) -> None:
    """A near-cubic but realistically-scanned bedroom (3.5 x 3 x 2.5 m) PASSES.

    The ambiguity guard must not be over-eager: a real near-cubic room still has
    dense floor/ceiling planes, so density wins cleanly and no ValueError fires.
    """
    ply = tmp_path / "bedroom.ply"
    _write_lidar_box_ply(
        ply, footprint_x=3.5, footprint_z=3.0, height=2.5, up_axis=1
    )
    room = MeshAdapter().parse(ply)
    assert room.ceiling_height_m == pytest.approx(2.5, abs=0.05)


def test_mesh_adapter_sparse_narrow_raises(tmp_path: Path) -> None:
    """A SPARSE narrow box (10 x 2 x 2.6 m) is area-ambiguous → raises (no guess).

    On a coarse 8-corner box the planar-density signal ties exactly across all
    axes, so detection falls through to the AREA tiebreaker. For a NARROW room a
    long wall's cross-section (10 x 2.6 = 26 m^2) exceeds the floor footprint
    (10 x 2 = 20 m^2), so the area "winner" is a WALL — the discredited round-1
    heuristic would silently report the 10 m horizontal span (or the 2.6 m wall)
    as the up-axis. The clear-floor margin (1.50) is NOT met (26/20 = 1.30), so
    the detector must fail loud rather than return a wrong axis. The explicit
    ``up_axis="z"`` override then recovers the correct 2.6 m ceiling.
    """
    import numpy as np
    import trimesh

    # Height along Z (up_axis=2): a sparse 8-vertex box, the regime that reaches
    # the density-degenerate area tiebreaker.
    box = trimesh.creation.box(extents=(10.0, 2.0, 2.6))
    ply = tmp_path / "narrow.ply"
    trimesh.Trimesh(
        vertices=np.asarray(box.vertices, dtype=float),
        faces=np.asarray(box.faces),
        process=False,
    ).export(ply)

    with pytest.raises(ValueError, match=r"ambiguous|up.?axis"):
        MeshAdapter().parse(ply)

    room = MeshAdapter(up_axis="z").parse(ply)
    assert room.ceiling_height_m == pytest.approx(2.6, abs=0.05), (
        f"up_axis='z' recovery: ceiling {room.ceiling_height_m} not ~2.6 m"
    )


# --------------------------------------------------------------------------- #
# Phase 0 (0a) — real-scan regression (ARKitScenes); excluded from default gate
# --------------------------------------------------------------------------- #

_ARKIT_ROOT = Path(
    "/home/seung/mmhoa/spike-vggt-multiview/data/arkit/raw/Validation"
)

# 41159529 is a genuine multi-level / tall scan (floor at z=-1.07, dense ceiling
# plane at z=1.48, roof structure above to z=4.7), so its true vertical extent
# is ~5.76 m, not a single-room height. Excluded from the strict 2-4 m bound
# but still required to detect the up-axis (a horizontal-axis confusion would
# put it well outside even this relaxed cap).
_ARKIT_MULTILEVEL_IDS = {"41159529"}


def _arkit_meshes() -> list[Path]:
    if not _ARKIT_ROOT.is_dir():
        return []
    return sorted(_ARKIT_ROOT.glob("*/*_3dod_mesh.ply"))


@pytest.mark.lab
@pytest.mark.skipif(
    not _ARKIT_ROOT.is_dir(),
    reason=f"ARKit validation data not present at {_ARKIT_ROOT}",
)
@pytest.mark.parametrize(
    "mesh_path",
    _arkit_meshes() or [pytest.param(None, marks=pytest.mark.skip)],
    ids=lambda p: p.parent.name if p is not None else "no-data",
)
def test_mesh_adapter_arkit_ceiling_height_regression(mesh_path: Path) -> None:
    """0a+0b regression: real Z-up ARKit scans detect Z and yield robust heights.

    Two stacked fixes are guarded here:

    * 0a (up-axis): the planar-density detector locks onto the gravity axis.
      ARKit 3dod meshes are gravity-aligned Z-up, so the detector must return Z
      for every scene (a horizontal-axis confusion produced the pre-0a 6.5-9.6 m
      heights on ~2.4-3 m rooms).
    * 0b (robust floor/ceiling planes): the reported ``ceiling_height_m`` is the
      density-peak floor/ceiling-PLANE height, NOT the full vertical extent
      ``z_max - z_min``. Full-extent grabs scan outliers (furniture, sub-floor /
      above-ceiling noise) and inflated these scenes by up to +1.34 m; the robust
      method matched an independent Faro laser GT to ~1 mm on scene-class data
      (42444946 → 3.034 m). The values asserted below are therefore the LOWER,
      corrected robust heights, not the pre-0b full-extent values (~2.49-3.69 m).

    On the 10 local Validation scenes the robust heights are (full-extent →
    robust): 41069021 3.15→2.35, 41069042 3.53→2.27, 41069048 2.51→2.24,
    41125696 3.15→2.79, 41125718 3.69→2.65, 41125756 2.93→2.72, 41142278
    2.49→2.31, 41159503 2.94→2.34, 41159519 3.54→2.46, 41159529 (multi-level)
    5.76→4.83. Single-level rooms must land in the realistic [2.2, 3.2] m band
    (tightened from the pre-0b [2.2, 3.8] that had to admit the inflated values);
    the one known multi-level scan is held to a relaxed [2.0, 6.0] m bound. Every
    scene must also report a robust height strictly BELOW its full vertical
    extent — proof the outlier-rejecting plane estimate engaged (each of these
    real scans has vertical outliers; clean synthetic meshes have none and there
    robust == full-extent, asserted separately).
    """
    import numpy as np
    import trimesh

    verts = np.asarray(trimesh.load(mesh_path, force="mesh").vertices, dtype=float)
    detected = MeshAdapter._detect_up_axis(verts)
    assert detected == 2, (
        f"{mesh_path.parent.name}: detected up-axis {detected} != Z (2); ARKit "
        "3dod meshes are gravity-aligned Z-up."
    )

    # Full vertical extent in the model's Y-up frame (the pre-0b, outlier-grabbing
    # quantity) — the robust height must come in strictly below it.
    verts_up = MeshAdapter._normalize_to_y_up(verts, detected)
    full_extent = float(verts_up[:, 1].max() - verts_up[:, 1].min())

    room = MeshAdapter().parse(mesh_path)

    assert room.provenance == "measured"
    scene_id = mesh_path.parent.name
    if scene_id in _ARKIT_MULTILEVEL_IDS:
        lower, upper = 2.0, 6.0
    else:
        lower, upper = 2.2, 3.2
    assert lower <= room.ceiling_height_m <= upper, (
        f"{scene_id}: robust ceiling height {room.ceiling_height_m:.2f} m outside "
        f"[{lower}, {upper}] — up-axis misdetect or floor/ceiling-plane failure "
        f"(pre-0a was 6.5-9.6 m; pre-0b full-extent was {full_extent:.2f} m)."
    )
    # Tightened (0b review LOW #3): a bare ``< full_extent`` is satisfied by a
    # sub-mm difference and would not prove outlier rejection actually engaged.
    # Every real Validation scene rejected >=0.18 m of spurious vertical extent
    # (smallest observed margin: 41142278 2.49->2.31 = 0.18 m), so require a
    # meaningful >=0.10 m gap — strict enough to be a real regression guard,
    # with ~8 cm headroom below the tightest observed case to stay non-flaky.
    _OUTLIER_REJECTION_MIN_M = 0.10
    assert room.ceiling_height_m <= full_extent - _OUTLIER_REJECTION_MIN_M, (
        f"{scene_id}: robust height {room.ceiling_height_m:.2f} m is not at least "
        f"{_OUTLIER_REJECTION_MIN_M:.2f} m below the full extent {full_extent:.2f} m "
        "— the 0b outlier-rejecting floor/ceiling plane estimate did not engage "
        "on a real scan (every such scan has vertical outliers to reject)."
    )


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


# --------------------------------------------------------------------------- #
# Phase 1 (commercialization plan) — USDZ mesh ingest
# --------------------------------------------------------------------------- #
#
# The committed fixtures (shoebox_yup.usdz / shoebox_zup.usdz) are generated by
# pxr in scripts/gen_usdz_fixtures.py — a 4 (x) x 3 (depth) x 2.5 (height) m
# shoebox UsdGeom.Mesh. The two stages declare upAxis=Y and upAxis=Z so the USD
# path is exercised through both up-axis conventions. They REQUIRE pxr (the
# [usd] extra); each test skips cleanly if pxr is absent.

pxr = pytest.importorskip("pxr")  # noqa: F841  (module-level USD gate)

# Known box dims (must match scripts/gen_usdz_fixtures.py).
_USDZ_FOOTPRINT_X = 4.0
_USDZ_FOOTPRINT_DEPTH = 3.0
_USDZ_HEIGHT = 2.5

USDZ_FIXTURES = [
    pytest.param(FIXTURE_DIR / "shoebox_yup.usdz", id="usdz_yup"),
    pytest.param(FIXTURE_DIR / "shoebox_zup.usdz", id="usdz_zup"),
]


@pytest.mark.parametrize("fixture_path", USDZ_FIXTURES)
def test_mesh_adapter_parses_usdz_shoebox(fixture_path: Path) -> None:
    """Both Y-up and Z-up USDZ shoeboxes parse to the known box geometry.

    Asserts: floor bbox ≈ 4 x 3 m, floor area ≈ 12 m^2, ceiling_height ≈ 2.5 m
    (the VERTICAL extent, NOT a horizontal span — the up-axis bug), walls
    present, provenance=="measured". The Z-up fixture proves the stage-upAxis
    hint / normalization carries USDZ scans through the shared Y-up pipeline.
    """
    if not fixture_path.exists():
        pytest.skip(f"{fixture_path.name} fixture not found")

    room = MeshAdapter().parse(fixture_path)

    assert isinstance(room, RoomModel)
    assert room.schema_version == "0.2-draft"
    assert room.provenance == "measured"

    assert room.ceiling_height_m == pytest.approx(_USDZ_HEIGHT, abs=0.1), (
        f"{fixture_path.name}: ceiling height {room.ceiling_height_m} not ~2.5 m "
        "(up-axis likely misdetected — a horizontal span was taken as height)"
    )

    xs = [p.x for p in room.floor_polygon]
    zs = [p.z for p in room.floor_polygon]
    span_a = max(xs) - min(xs)
    span_b = max(zs) - min(zs)
    # bbox should be 4 x 3 (orientation of which horizontal lands on X/Z may
    # swap under the axis permutation, so compare the sorted spans).
    lo_span, hi_span = sorted([span_a, span_b])
    assert lo_span == pytest.approx(_USDZ_FOOTPRINT_DEPTH, abs=0.1), (
        f"{fixture_path.name}: short floor span {lo_span} not ~3 m"
    )
    assert hi_span == pytest.approx(_USDZ_FOOTPRINT_X, abs=0.1), (
        f"{fixture_path.name}: long floor span {hi_span} not ~4 m"
    )

    area = _floor_area(room)
    assert area == pytest.approx(
        _USDZ_FOOTPRINT_X * _USDZ_FOOTPRINT_DEPTH, rel=0.05
    ), f"{fixture_path.name}: floor area {area} not ~12 m^2"

    walls = [s for s in room.surfaces if s.kind == "wall"]
    assert len(walls) >= 4, f"expected >=4 walls, got {len(walls)}"


def test_mesh_adapter_usdz_uses_stage_up_axis_hint() -> None:
    """The Z-up USDZ resolves correctly even though auto-detect is bypassable.

    The stage declares upAxis=Z; ``_vertices_from_usdz`` returns that hint and
    ``_extract_room_model`` trusts it (skipping gravity detection). The 8-corner
    box is exactly the SPARSE regime where pure auto-detect is ambiguous, so a
    correct 2.5 m height here demonstrates the declared hint is what drives it.
    """
    fixture = FIXTURE_DIR / "shoebox_zup.usdz"
    if not fixture.exists():
        pytest.skip("shoebox_zup.usdz fixture not found")

    _verts, hint = MeshAdapter()._vertices_from_usdz(fixture)
    assert hint == "z", f"stage upAxis hint not read as 'z': {hint!r}"

    room = MeshAdapter().parse(fixture)
    assert room.ceiling_height_m == pytest.approx(_USDZ_HEIGHT, abs=0.1)


def test_mesh_adapter_usdz_world_space_transform(tmp_path: Path) -> None:
    """Multi-prim USDZ: each prim's local-to-world transform is baked in.

    A box authored under a translated/scaled Xform must land at its WORLD
    coordinates, not its local ones — proving ComputeLocalToWorldTransform is
    applied. Build a unit box translated by (10, 0, 5) and confirm the floor
    bbox sits at that world offset.
    """
    from pxr import Gf, Usd, UsdGeom, UsdUtils, Vt

    out = tmp_path / "translated.usdz"
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(root.GetPrim())
    # Xform with a translate op; the mesh below is authored in LOCAL space.
    xf = UsdGeom.Xform.Define(stage, "/Room/Group")
    xf.AddTranslateOp().Set(Gf.Vec3d(10.0, 0.0, 5.0))
    mesh = UsdGeom.Mesh.Define(stage, "/Room/Group/Box")
    fx, fd, h = 4.0, 3.0, 2.5
    base = [(0, 0, 0), (fx, 0, 0), (fx, 0, fd), (0, 0, fd)]
    top = [(0, h, 0), (fx, h, 0), (fx, h, fd), (0, h, fd)]
    mesh.CreatePointsAttr(
        Vt.Vec3fArray([tuple(float(c) for c in p) for p in base + top])
    )
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4, 4, 4, 4, 4, 4]))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray(
            [0, 1, 2, 3, 4, 7, 6, 5, 0, 4, 5, 1, 1, 5, 6, 2, 2, 6, 7, 3, 3, 7, 4, 0]
        )
    )
    tmp_usdc = out.with_suffix(".usdc")
    stage.GetRootLayer().Export(str(tmp_usdc))
    UsdUtils.CreateNewUsdzPackage(str(tmp_usdc), str(out))
    tmp_usdc.unlink()

    verts, _hint = MeshAdapter()._vertices_from_usdz(out)
    # World-space X should start at 10 (local 0 + translate 10), not 0.
    assert verts[:, 0].min() == pytest.approx(10.0, abs=0.01), (
        f"local-to-world transform not applied: min X {verts[:, 0].min()} != 10"
    )
    assert verts[:, 0].max() == pytest.approx(14.0, abs=0.01)

    room = MeshAdapter().parse(out)
    assert room.ceiling_height_m == pytest.approx(h, abs=0.1)


def test_mesh_adapter_usdz_no_mesh_prims_raises(tmp_path: Path) -> None:
    """A USDZ with no UsdGeom.Mesh geometry raises a clear ValueError.

    (e.g. a parametric-only / xform-only stage). The error must point the caller
    at exporting a mesh USDZ rather than silently returning a degenerate model.
    """
    from pxr import Usd, UsdGeom, UsdUtils

    out = tmp_path / "empty.usdz"
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    root = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(root.GetPrim())
    tmp_usdc = out.with_suffix(".usdc")
    stage.GetRootLayer().Export(str(tmp_usdc))
    UsdUtils.CreateNewUsdzPackage(str(tmp_usdc), str(out))
    tmp_usdc.unlink()

    with pytest.raises(ValueError, match="no UsdGeom.Mesh"):
        MeshAdapter().parse(out)


def test_mesh_adapter_usdz_centimetre_units_scale_to_metres(tmp_path: Path) -> None:
    """A USDZ authored in centimetres ingests at correct METRIC scale.

    Apple RoomPlan / Reality Composer USDZ exports declare metersPerUnit=0.01:
    a 2.5 m room is authored as raw points of 250. Ignoring metersPerUnit stamps
    a 250 m ceiling as provenance=="measured" — the silent 100x-wrong-scale class
    this path must reject. The box below is sized so its VERTICAL extent is 250
    units (== 2.5 m at cm scale); the recovered ceiling_height_m must be ~2.5,
    NOT 250. This is the regression that would have caught the missing scale.
    """
    from pxr import Usd, UsdGeom, UsdUtils, Vt

    out = tmp_path / "centimetres.usdz"
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    # Authored in CENTIMETRES — the real RoomPlan/Reality Composer convention.
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)
    root = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(root.GetPrim())
    mesh = UsdGeom.Mesh.Define(stage, "/Room/Box")
    # 4 m x 3 m footprint, 2.5 m height — all expressed in cm (x100).
    fx, fd, h = 400.0, 300.0, 250.0
    base = [(0, 0, 0), (fx, 0, 0), (fx, 0, fd), (0, 0, fd)]
    top = [(0, h, 0), (fx, h, 0), (fx, h, fd), (0, h, fd)]
    mesh.CreatePointsAttr(
        Vt.Vec3fArray([tuple(float(c) for c in p) for p in base + top])
    )
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4, 4, 4, 4, 4, 4]))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray(
            [0, 1, 2, 3, 4, 7, 6, 5, 0, 4, 5, 1, 1, 5, 6, 2, 2, 6, 7, 3, 3, 7, 4, 0]
        )
    )
    tmp_usdc = out.with_suffix(".usdc")
    stage.GetRootLayer().Export(str(tmp_usdc))
    UsdUtils.CreateNewUsdzPackage(str(tmp_usdc), str(out))
    tmp_usdc.unlink()

    room = MeshAdapter().parse(out)
    assert room.provenance == "measured"
    assert room.ceiling_height_m == pytest.approx(2.5, abs=0.05), (
        f"cm-unit USDZ ingested at wrong scale: ceiling {room.ceiling_height_m} m "
        "(metersPerUnit=0.01 ignored — raw 250 taken as metres)"
    )
    area = _floor_area(room)
    assert area == pytest.approx(12.0, rel=0.05), (
        f"cm-unit USDZ floor area {area} not ~12 m^2 (scale not applied to footprint)"
    )


def test_mesh_adapter_usdz_recovers_instanced_geometry(tmp_path: Path) -> None:
    """A mesh reached ONLY through an instance proxy is still recovered.

    USD native instancing places geometry in a prototype; ``stage.Traverse()``
    with the default predicate stops at the instance boundary and silently drops
    those meshes. Here the box lives under a ``class`` prim (not traversed
    directly) and is reachable solely via an Instanceable prim inheriting it, so
    a non-empty vertex set proves the instance-proxy traversal descends into it.
    """
    from pxr import Usd, UsdGeom, UsdUtils, Vt

    out = tmp_path / "instanced.usdz"
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    # Prototype as a class prim: excluded from the default traversal, so the only
    # path to its mesh is through the instance proxy below.
    stage.CreateClassPrim("/_Proto")
    mesh = UsdGeom.Mesh.Define(stage, "/_Proto/Box")
    fx, fd, h = 4.0, 3.0, 2.5
    base = [(0, 0, 0), (fx, 0, 0), (fx, 0, fd), (0, 0, fd)]
    top = [(0, h, 0), (fx, h, 0), (fx, h, fd), (0, h, fd)]
    mesh.CreatePointsAttr(
        Vt.Vec3fArray([tuple(float(c) for c in p) for p in base + top])
    )
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4, 4, 4, 4, 4, 4]))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray(
            [0, 1, 2, 3, 4, 7, 6, 5, 0, 4, 5, 1, 1, 5, 6, 2, 2, 6, 7, 3, 3, 7, 4, 0]
        )
    )
    root = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(root.GetPrim())
    inst = UsdGeom.Xform.Define(stage, "/Room/Inst")
    inst.GetPrim().GetInherits().AddInherit("/_Proto")
    inst.GetPrim().SetInstanceable(True)

    tmp_usdc = out.with_suffix(".usdc")
    stage.GetRootLayer().Export(str(tmp_usdc))
    UsdUtils.CreateNewUsdzPackage(str(tmp_usdc), str(out))
    tmp_usdc.unlink()

    verts, _hint = MeshAdapter()._vertices_from_usdz(out)
    assert verts.shape[0] > 0, (
        "instanced mesh dropped — instance-proxy traversal not applied"
    )
    room = MeshAdapter().parse(out)
    assert room.ceiling_height_m == pytest.approx(h, abs=0.1)


def test_mesh_adapter_usdz_concrete_prototype_not_double_counted(
    tmp_path: Path,
) -> None:
    """A concrete (``def``) prototype source is NOT counted alongside its proxies.

    When a USDZ authors a CONCRETE prototype prim (``def``, not ``class``) as a
    sibling of the default prim and references it from ``instanceable=True``
    prims, a whole-stage ``Usd.TraverseInstanceProxies`` traversal visits that
    raw prototype mesh at its OWN authored location AND once per instance proxy —
    double-counting the geometry and corrupting the bounding box. Here the raw
    ``/Proto/Box`` sits at the floor (y∈[0, 2.5]) while the two instances are
    raised to y∈[10, 12.5]; the true room height is 2.5 m, but the phantom
    prototype copy would inflate the Y span to 12.5 m. Scoping the traversal to
    the default prim (``/Room``) excludes the sibling prototype source, so the
    recovered height stays correct. (The ``class``-prim instanced test masks this
    bug because class prims are never traversed directly.)
    """
    from pxr import Usd, UsdGeom, UsdUtils, Vt

    out = tmp_path / "concrete_proto.usdz"
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    # CONCRETE (def) prototype authored OUTSIDE the default prim, at the floor.
    UsdGeom.Xform.Define(stage, "/Proto")
    mesh = UsdGeom.Mesh.Define(stage, "/Proto/Box")
    fx, fd, h = 4.0, 3.0, 2.5
    base = [(0, 0, 0), (fx, 0, 0), (fx, 0, fd), (0, 0, fd)]
    top = [(0, h, 0), (fx, h, 0), (fx, h, fd), (0, h, fd)]
    mesh.CreatePointsAttr(
        Vt.Vec3fArray([tuple(float(c) for c in p) for p in base + top])
    )
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4, 4, 4, 4, 4, 4]))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray(
            [0, 1, 2, 3, 4, 7, 6, 5, 0, 4, 5, 1, 1, 5, 6, 2, 2, 6, 7, 3, 3, 7, 4, 0]
        )
    )
    root = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(root.GetPrim())
    # Two instances of the concrete prototype, both raised to y∈[10, 12.5] so the
    # legitimate room height is 2.5 m. A phantom floor-level prototype copy would
    # inflate the Y span to 12.5 m.
    for i, tx in enumerate((0.0, 4.0)):
        inst = UsdGeom.Xform.Define(stage, f"/Room/Inst{i}")
        inst.AddTranslateOp().Set((tx, 10.0, 0.0))
        inst.GetPrim().GetReferences().AddInternalReference("/Proto")
        inst.GetPrim().SetInstanceable(True)

    tmp_usdc = out.with_suffix(".usdc")
    stage.GetRootLayer().Export(str(tmp_usdc))
    UsdUtils.CreateNewUsdzPackage(str(tmp_usdc), str(out))
    tmp_usdc.unlink()

    room = MeshAdapter().parse(out)
    assert room.provenance == "measured"
    assert room.ceiling_height_m == pytest.approx(h, abs=0.1), (
        f"concrete prototype double-counted: ceiling {room.ceiling_height_m:.2f} m "
        f"inflated (phantom /Proto/Box copy); expected ~{h} m"
    )


def test_mesh_adapter_usdz_ceiling_bound_rejects_implausible_height(
    tmp_path: Path,
) -> None:
    """A height beyond the absolute plausibility bound fails loud (not measured).

    A metersPerUnit lie or mixed-unit mesh can survive per-prim scaling and still
    stamp an absurd height as ``provenance="measured"``. The ~25 m box below
    exceeds the default 20 m bound and must raise; the normally-scaled committed
    fixtures (≤2.5 m) stay well under it and continue to parse.
    """
    from pxr import Usd, UsdGeom, UsdUtils, Vt

    out = tmp_path / "too_tall.usdz"
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(root.GetPrim())
    mesh = UsdGeom.Mesh.Define(stage, "/Room/Box")
    fx, fd, h = 4.0, 3.0, 25.0  # 25 m height — above the 20 m bound.
    base = [(0, 0, 0), (fx, 0, 0), (fx, 0, fd), (0, 0, fd)]
    top = [(0, h, 0), (fx, h, 0), (fx, h, fd), (0, h, fd)]
    mesh.CreatePointsAttr(
        Vt.Vec3fArray([tuple(float(c) for c in p) for p in base + top])
    )
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4, 4, 4, 4, 4, 4]))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray(
            [0, 1, 2, 3, 4, 7, 6, 5, 0, 4, 5, 1, 1, 5, 6, 2, 2, 6, 7, 3, 3, 7, 4, 0]
        )
    )
    tmp_usdc = out.with_suffix(".usdc")
    stage.GetRootLayer().Export(str(tmp_usdc))
    UsdUtils.CreateNewUsdzPackage(str(tmp_usdc), str(out))
    tmp_usdc.unlink()

    with pytest.raises(ValueError, match="implausible|bound"):
        MeshAdapter().parse(out)

    # The normally-scaled fixture stays under the default bound and still parses.
    fixture = FIXTURE_DIR / "shoebox_yup.usdz"
    if fixture.exists():
        room = MeshAdapter().parse(fixture)
        assert room.ceiling_height_m == pytest.approx(_USDZ_HEIGHT, abs=0.1)


def test_mesh_adapter_usdz_upaxis_conflict_raises(tmp_path: Path) -> None:
    """A stage declaring upAxis=Y but with Z-up geometry fails loud.

    A mis-authored stage (declared up-axis disagrees with the actual gravity
    axis) would silently report a horizontal span as the ceiling height. The
    geometry here is a DENSE Z-up box (sharp floor/ceiling planes on Z), so the
    planar-density detector is confident it is Z-up while the stage declares Y;
    the adapter must raise a clear ValueError naming the declared/detected
    conflict rather than trust the blind hint.
    """
    import numpy as np
    from pxr import Usd, UsdGeom, UsdUtils, Vt

    rng = np.random.default_rng(0)
    fx, fy, h = 4.0, 3.0, 2.5
    n = 8000
    floor = np.column_stack(
        [rng.uniform(0, fx, n), rng.uniform(0, fy, n), np.zeros(n)]
    )
    ceil = np.column_stack(
        [rng.uniform(0, fx, n), rng.uniform(0, fy, n), np.full(n, h)]
    )
    per = 1000
    walls = [
        np.column_stack([rng.uniform(0, fx, per), np.zeros(per), rng.uniform(0, h, per)]),
        np.column_stack([rng.uniform(0, fx, per), np.full(per, fy), rng.uniform(0, h, per)]),
        np.column_stack([np.zeros(per), rng.uniform(0, fy, per), rng.uniform(0, h, per)]),
        np.column_stack([np.full(per, fx), rng.uniform(0, fy, per), rng.uniform(0, h, per)]),
    ]
    verts = np.vstack([floor, ceil, *walls])
    n_keep = (verts.shape[0] // 3) * 3
    verts = verts[:n_keep]
    faces = np.arange(n_keep).reshape(-1, 3)

    out = tmp_path / "conflict.usdz"
    stage = Usd.Stage.CreateInMemory()
    # DECLARE Y-up — but the geometry above is unambiguously Z-up.
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(root.GetPrim())
    mesh = UsdGeom.Mesh.Define(stage, "/Room/Scan")
    mesh.CreatePointsAttr(
        Vt.Vec3fArray([(float(v[0]), float(v[1]), float(v[2])) for v in verts])
    )
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(faces)))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray([int(i) for f in faces for i in f])
    )
    tmp_usdc = out.with_suffix(".usdc")
    stage.GetRootLayer().Export(str(tmp_usdc))
    UsdUtils.CreateNewUsdzPackage(str(tmp_usdc), str(out))
    tmp_usdc.unlink()

    with pytest.raises(ValueError, match="mis-authored|unambiguously"):
        MeshAdapter().parse(out)


# --------------------------------------------------------------------------- #
# Phase 1 — real-data USDZ proof (ARKit .ply → .usdz); excluded from default gate
# --------------------------------------------------------------------------- #


@pytest.mark.lab
@pytest.mark.skipif(
    not _ARKIT_ROOT.is_dir(),
    reason=f"ARKit validation data not present at {_ARKIT_ROOT}",
)
def test_mesh_adapter_usdz_from_real_arkit_scan(tmp_path: Path) -> None:
    """Convert one real ARKit .ply scan to .usdz and confirm a realistic height.

    Strong real-data proof that the USD path handles a genuine Z-up LiDAR scan:
    convert the .ply mesh to .usdz via pxr, parse it, and assert the recovered
    ceiling height lands in the realistic single/multi-room band.
    """
    import numpy as np
    import trimesh
    from pxr import Usd, UsdGeom, UsdUtils, Vt

    meshes = _arkit_meshes()
    if not meshes:
        pytest.skip("no ARKit *_3dod_mesh.ply found")
    src = meshes[0]
    tm = trimesh.load(src, force="mesh")
    verts = np.asarray(tm.vertices, dtype=float)
    faces = np.asarray(tm.faces)

    out = tmp_path / "arkit.usdz"
    stage = Usd.Stage.CreateInMemory()
    # ARKit 3dod meshes are gravity-aligned Z-up.
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(root.GetPrim())
    mesh = UsdGeom.Mesh.Define(stage, "/Room/Scan")
    mesh.CreatePointsAttr(
        Vt.Vec3fArray([(float(v[0]), float(v[1]), float(v[2])) for v in verts])
    )
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(faces)))
    mesh.CreateFaceVertexIndicesAttr(
        Vt.IntArray([int(i) for f in faces for i in f])
    )
    tmp_usdc = out.with_suffix(".usdc")
    stage.GetRootLayer().Export(str(tmp_usdc))
    UsdUtils.CreateNewUsdzPackage(str(tmp_usdc), str(out))
    tmp_usdc.unlink()

    room = MeshAdapter().parse(out)
    assert room.provenance == "measured"
    # Realistic single/multi-room ceiling band (matches the .ply regression).
    assert 2.0 <= room.ceiling_height_m <= 6.0, (
        f"{src.parent.name}: USDZ ceiling height {room.ceiling_height_m:.2f} m "
        "outside [2.0, 6.0] — up-axis likely misdetected through the USD path."
    )


# --------------------------------------------------------------------------- #
# v0.28.0 — ceiling-confidence under-report guard (annotation only)
# --------------------------------------------------------------------------- #
#
# ceiling_coverage is a genuine geometric MEASUREMENT (fraction of the floor
# footprint the detected ceiling plane spans); ceiling_confidence is a
# documented HEURISTIC label (high/low/unknown), NOT a calibrated probability.
# The flag only ANNOTATES ceiling_height_m — it never changes the extracted
# value. Synthetic fixtures only (no calibration claim against real data).


def test_mesh_adapter_ceiling_confidence_high_on_clean_shoebox() -> None:
    """A clean committed shoebox reads coverage ~ 1.0 and confidence 'high'.

    Floor + walls + ceiling all populate every footprint cell, so the detected
    ceiling plane spans essentially the whole footprint.
    """
    room = MeshAdapter().parse(FIXTURE_DIR / "lab_room.obj")
    assert room.ceiling_coverage is not None
    assert room.ceiling_coverage >= 0.9, (
        f"clean shoebox coverage {room.ceiling_coverage} unexpectedly < 0.9"
    )
    assert room.ceiling_confidence == "high"


def test_mesh_adapter_ceiling_height_byte_equal_with_confidence() -> None:
    """The confidence annotation must NOT perturb ceiling_height_m.

    The new fields only annotate; the extracted shoebox height stays exactly the
    pre-change 2.5 m (within the same tolerance the dedicated dims test uses).
    """
    room = MeshAdapter().parse(FIXTURE_DIR / "lab_room.obj")
    assert room.ceiling_height_m == pytest.approx(2.5, abs=0.10)
    # Annotation present but height unchanged: the flag is additive metadata.
    assert room.ceiling_confidence in ("high", "low", "unknown")


def _write_tabletop_mispick_ply(path: Path) -> None:
    """Write a room shell whose TRUE ceiling is under-sampled and a small dense
    tabletop sits just below it (the documented mis-pick scenario).

    Dense floor (y=0) + four dense walls spanning the whole 6 m x 6 m footprint
    up to the true ceiling at y=3.0, but the true ceiling is SPARSE (40 points).
    A small (1 m x 1 m) DENSE horizontal plane at y=2.6 is the topmost still-dense
    bin, so ``_robust_floor_ceiling_y`` mis-picks it as the ceiling and
    UNDER-reports the height (~2.58 m vs the true 3.0 m). The coverage metric must
    catch this: the tabletop spans only a small XZ patch of the footprint.
    """
    import numpy as np
    import trimesh

    rng = np.random.default_rng(1)
    fx = fz = 6.0
    height = 3.0
    floor = np.column_stack(
        [rng.uniform(0, fx, 6000), np.zeros(6000), rng.uniform(0, fz, 6000)]
    )
    per = 2000
    walls = [
        np.column_stack(
            [rng.uniform(0, fx, per), rng.uniform(0, height, per), np.zeros(per)]
        ),
        np.column_stack(
            [rng.uniform(0, fx, per), rng.uniform(0, height, per), np.full(per, fz)]
        ),
        np.column_stack(
            [np.zeros(per), rng.uniform(0, height, per), rng.uniform(0, fz, per)]
        ),
        np.column_stack(
            [np.full(per, fx), rng.uniform(0, height, per), rng.uniform(0, fz, per)]
        ),
    ]
    # SPARSE true ceiling (under-sampled) at y=3.0.
    ceil = np.column_stack(
        [rng.uniform(0, fx, 40), np.full(40, height), rng.uniform(0, fz, 40)]
    )
    # Small DENSE tabletop (1 m x 1 m) at y=2.6, just below the true ceiling.
    tw = 1.0
    cx = cz = 2.5
    tab = np.column_stack(
        [rng.uniform(cx, cx + tw, 3000), np.full(3000, 2.6), rng.uniform(cz, cz + tw, 3000)]
    )
    verts = np.vstack([floor, *walls, ceil, tab])
    n_keep = (verts.shape[0] // 3) * 3
    verts = verts[:n_keep]
    faces = np.arange(n_keep).reshape(-1, 3)
    trimesh.Trimesh(vertices=verts, faces=faces, process=False).export(path)


def test_mesh_adapter_ceiling_confidence_low_on_tabletop_mispick(tmp_path: Path) -> None:
    """A tabletop mis-pick is flagged 'low' with coverage well below 0.50.

    up_axis is pinned to Y so this isolates the coverage metric from the
    gravity detector (which has its own tests). The fixture is built so the
    tabletop is unambiguously small — coverage lands far from the 0.50 boundary.
    """
    ply = tmp_path / "tabletop_mispick.ply"
    _write_tabletop_mispick_ply(ply)

    room = MeshAdapter(up_axis="y").parse(ply)

    # The adapter mis-picked the tabletop (~2.6 m), UNDER-reporting the true 3.0 m
    # ceiling — exactly the residual the flag exists to catch.
    assert room.ceiling_height_m < 2.9, (
        f"fixture sanity: expected an under-reported height (<2.9 m), got "
        f"{room.ceiling_height_m:.3f} m"
    )
    assert room.ceiling_coverage is not None
    assert room.ceiling_coverage < 0.50, (
        f"tabletop coverage {room.ceiling_coverage} not < 0.50 — fixture too "
        "close to the boundary; make the tabletop smaller (do NOT tune constants)."
    )
    assert room.ceiling_confidence == "low"


def _write_collapsed_ceiling_ply(path: Path) -> None:
    """Write a room whose ceiling COLLAPSES to an implausibly low dense plane.

    Dense floor (y=0) + four dense walls + a dense full-footprint horizontal
    plane at y=1.3 (no real ceiling above it). ``_robust_floor_ceiling_y`` picks
    the 1.3 m plane as the ceiling, UNDER-reporting the height to ~1.27 m — the
    validated collapse failure mode (n=1 SCRREAM: 1.34 m vs true 2.58 m at
    extreme noise). Because the wrong plane spans the WHOLE footprint, coverage
    reads ~1.0 (high) — so coverage alone would falsely report 'high'; only the
    plane-plausibility gate catches it.
    """
    import numpy as np
    import trimesh

    rng = np.random.default_rng(7)
    fx = fz = 4.0
    collapse_y = 1.3
    floor = np.column_stack(
        [rng.uniform(0, fx, 6000), np.zeros(6000), rng.uniform(0, fz, 6000)]
    )
    plane = np.column_stack(
        [rng.uniform(0, fx, 6000), np.full(6000, collapse_y), rng.uniform(0, fz, 6000)]
    )
    per = 2000
    walls = [
        np.column_stack(
            [rng.uniform(0, fx, per), rng.uniform(0, collapse_y, per), np.zeros(per)]
        ),
        np.column_stack(
            [rng.uniform(0, fx, per), rng.uniform(0, collapse_y, per), np.full(per, fz)]
        ),
        np.column_stack(
            [np.zeros(per), rng.uniform(0, collapse_y, per), rng.uniform(0, fz, per)]
        ),
        np.column_stack(
            [np.full(per, fx), rng.uniform(0, collapse_y, per), rng.uniform(0, fz, per)]
        ),
    ]
    verts = np.vstack([floor, plane, *walls])
    n_keep = (verts.shape[0] // 3) * 3
    verts = verts[:n_keep]
    faces = np.arange(n_keep).reshape(-1, 3)
    trimesh.Trimesh(vertices=verts, faces=faces, process=False).export(path)


def test_mesh_adapter_ceiling_confidence_low_on_collapsed_ceiling(
    tmp_path: Path,
) -> None:
    """A COLLAPSED ceiling (implausibly low) is demoted to 'low' despite high coverage.

    The collapsed plane spans the whole footprint, so coverage reads ~1.0 (which
    alone would say 'high'); the plane-plausibility gate (height < 1.8 m) must
    demote it to 'low'. ``ceiling_height_m`` is NOT modified by the annotation —
    it stays the collapsed value.
    """
    ply = tmp_path / "collapsed_ceiling.ply"
    _write_collapsed_ceiling_ply(ply)

    room = MeshAdapter(up_axis="y").parse(ply)

    # The annotation did NOT change the height: it is the collapsed value.
    assert room.ceiling_height_m < 1.8, (
        f"fixture sanity: expected a collapsed height (<1.8 m), got "
        f"{room.ceiling_height_m:.3f} m"
    )
    # Coverage is high (the wrong plane spans the footprint) yet confidence is
    # demoted by the plausibility gate.
    assert room.ceiling_coverage is not None
    assert room.ceiling_coverage >= 0.50, (
        f"fixture sanity: collapsed plane should span the footprint "
        f"(coverage {room.ceiling_coverage} unexpectedly < 0.50)"
    )
    assert room.ceiling_confidence != "high"
    assert room.ceiling_confidence == "low"


def test_ceiling_coverage_failsafe_returns_none_on_degenerate() -> None:
    """``_ceiling_coverage`` never raises; degenerate input → None → 'unknown'.

    A single-plane / tiny array with no finite footprint or an empty array must
    return None (fail-safe), and the classifier must map None → 'unknown'.
    """
    import numpy as np

    # Empty input → None.
    empty = np.empty((0, 3), dtype=float)
    assert MeshAdapter._ceiling_coverage(empty, ceiling_y=0.0) is None

    # Non-finite input → None (no raise).
    nan_verts = np.array([[np.nan, 0.0, 0.0], [1.0, 1.0, 1.0]], dtype=float)
    assert MeshAdapter._ceiling_coverage(nan_verts, ceiling_y=1.0) is None

    # Classifier maps the fail-safe None to the least-claim 'unknown'.
    assert MeshAdapter._classify_ceiling_confidence(None) == "unknown"
    assert MeshAdapter._classify_ceiling_confidence(1.0) == "high"
    assert MeshAdapter._classify_ceiling_confidence(0.0) == "low"
    assert MeshAdapter._classify_ceiling_confidence(0.5) == "high"  # boundary inclusive

    # Plane-plausibility gate (optional second arg). A plausible height keeps the
    # coverage verdict; a collapsed height demotes 'high' -> 'low'; a None height
    # skips the gate (back-compat — the four assertions above are unchanged).
    assert MeshAdapter._classify_ceiling_confidence(1.0, 2.5) == "high"
    assert MeshAdapter._classify_ceiling_confidence(1.0, 1.0) == "low"
    assert MeshAdapter._classify_ceiling_confidence(1.0) == "high"


# --------------------------------------------------------------------------- #
# C1 — `auto` floor-reconstruction dispatch (ADR 0048)
# --------------------------------------------------------------------------- #


def _make_dense_box(
    foot: list[tuple[float, float]], h: float, *, max_edge: float = 0.04
) -> tuple["object", "object"]:
    """Dense watertight prism from a CONVEX CCW footprint (vertices, faces).

    Floor/ceiling are authored as fans (valid for a convex footprint) and side
    quads close the perimeter; ``subdivide_to_size`` then packs many vertices per
    5 cm cell so the occupancy extractor recovers the footprint.
    """
    import numpy as np
    import trimesh

    n = len(foot)
    bottom = [(x, 0.0, z) for (x, z) in foot]
    top = [(x, h, z) for (x, z) in foot]
    verts = np.array(bottom + top, dtype=float)
    faces: list[list[int]] = []
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, j + n])
        faces.append([i, j + n, i + n])
    for i in range(1, n - 1):
        faces.append([0, i + 1, i])
    for i in range(1, n - 1):
        faces.append([n, n + i, n + i + 1])
    return trimesh.remesh.subdivide_to_size(verts, np.array(faces), max_edge=max_edge)


def _write_dense_box_with_floater_obj(path: Path) -> None:
    """Dense 4x4x2.5 room + a small DISCONNECTED dense floater box (Y-up .obj).

    The floater (0.3 m cube at x,z ~ 8 m, > 0.25 m from the room) survives the
    occupancy grid as its own small component but is rejected by the largest-
    component step; the convex hull engulfs it. ``auto`` must detect it (φ ≥ θ)
    and switch to occupancy.
    """
    import numpy as np
    import trimesh

    room_v, room_f = _make_dense_box(
        [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)], 2.5
    )
    floater_v, floater_f = _make_dense_box(
        [(8.0, 8.0), (8.3, 8.0), (8.3, 8.3), (8.0, 8.3)], 0.3
    )
    room_v = np.asarray(room_v)
    floater_v = np.asarray(floater_v)
    verts = np.vstack([room_v, floater_v])
    faces = np.vstack([np.asarray(room_f), np.asarray(floater_f) + room_v.shape[0]])
    trimesh.Trimesh(vertices=verts, faces=faces, process=False).export(path)


def _write_dense_dumbbell_obj(path: Path) -> None:
    """Dense CONNECTED two-room mesh joined by a 0.5 m-wide neck (Y-up .obj).

    Rooms A [0,2]x[0,2] and B [4,6]x[0,2] joined by a neck [2,4]x[0.75,1.25].
    A through-opening "bleed" proxy: a SINGLE coarse-grid component → φ = 1.0 →
    ``auto`` must NOT fire → byte-equal to convex (locks the no-bleed-claim by
    construction). Floor/ceiling are authored from the 3 component rectangles
    (no triangulation engine needed); side quads close the 12-edge perimeter.
    """
    import numpy as np
    import trimesh

    # 12 perimeter corners (CCW), interior on the left.
    foot = [
        (0.0, 0.0), (2.0, 0.0), (2.0, 0.75), (4.0, 0.75), (4.0, 0.0), (6.0, 0.0),
        (6.0, 2.0), (4.0, 2.0), (4.0, 1.25), (2.0, 1.25), (2.0, 2.0), (0.0, 2.0),
    ]
    h = 2.5
    n = len(foot)
    bottom = [(x, 0.0, z) for (x, z) in foot]
    top = [(x, h, z) for (x, z) in foot]
    verts = np.array(bottom + top, dtype=float)
    faces: list[list[int]] = []
    # Side walls around the true perimeter.
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, j + n])
        faces.append([i, j + n, i + n])
    # Floor + ceiling caps from the 3 rectangles (indices into ``foot``):
    #   A = (0,1,10,11)  neck = (2,3,8,9)  B = (4,5,6,7)
    rects = [(0, 1, 10, 11), (2, 3, 8, 9), (4, 5, 6, 7)]
    for a, b, c, d in rects:
        faces.append([a, b, c])
        faces.append([a, c, d])
        faces.append([a + n, c + n, b + n])
        faces.append([a + n, d + n, c + n])
    dense_v, dense_f = trimesh.remesh.subdivide_to_size(
        verts, np.array(faces), max_edge=0.04
    )
    trimesh.Trimesh(vertices=dense_v, faces=dense_f, process=False).export(path)


def test_mesh_adapter_auto_clean_byte_equal_to_convex(tmp_path: Path) -> None:
    """T-A (THE convex-preserving gate): auto == convex on clean input.

    Parsing a clean shoebox through ``floor_reconstruction="auto"`` yields a
    value-equal floor polygon AND a BYTE-EQUAL serialized room.yaml vs
    ``"convex"``: the signal returns φ = 1.0 (single coarse component), so auto
    dispatches the SAME ``_convex_floor_polygon`` call with un-perturbed vertices.
    """
    from roomestim.export.room_yaml import write_room_yaml

    auto_room = MeshAdapter(floor_reconstruction="auto").parse(
        FIXTURE_DIR / "lab_room.obj"
    )
    convex_room = MeshAdapter(floor_reconstruction="convex").parse(
        FIXTURE_DIR / "lab_room.obj"
    )

    assert [(p.x, p.z) for p in auto_room.floor_polygon] == [
        (p.x, p.z) for p in convex_room.floor_polygon
    ]

    auto_yaml = tmp_path / "auto_room.yaml"
    convex_yaml = tmp_path / "convex_room.yaml"
    write_room_yaml(auto_room, auto_yaml)
    write_room_yaml(convex_room, convex_yaml)
    assert auto_yaml.read_bytes() == convex_yaml.read_bytes(), (
        "auto must be BYTE-EQUAL to convex on clean input"
    )


def test_mesh_adapter_auto_fires_on_floater(tmp_path: Path) -> None:
    """T-fire-adapter: auto rejects a disconnected floater (area < convex mode)."""
    obj_path = tmp_path / "floater.obj"
    _write_dense_box_with_floater_obj(obj_path)

    auto_room = MeshAdapter(floor_reconstruction="auto").parse(obj_path)
    convex_room = MeshAdapter(floor_reconstruction="convex").parse(obj_path)

    auto_area = _floor_area(auto_room)
    convex_area = _floor_area(convex_room)
    assert auto_area < convex_area, (
        f"auto {auto_area} must reject the floater that bloats convex {convex_area}"
    )
    # Auto recovered the true ~16 m^2 room (floater rejected).
    assert auto_area == pytest.approx(16.0, rel=0.10), f"auto recovered {auto_area}"


def test_mesh_adapter_auto_no_fire_on_connected_bleed(tmp_path: Path) -> None:
    """T-no-fire-bleed: a connected through-opening fixture stays byte-equal to convex.

    A single coarse-grid component → φ = 1.0 → auto never fires → identical to
    convex. Locks the NO-bleed-claim by construction.
    """
    from roomestim.export.room_yaml import write_room_yaml

    obj_path = tmp_path / "dumbbell.obj"
    _write_dense_dumbbell_obj(obj_path)

    auto_room = MeshAdapter(floor_reconstruction="auto").parse(obj_path)
    convex_room = MeshAdapter(floor_reconstruction="convex").parse(obj_path)

    assert [(p.x, p.z) for p in auto_room.floor_polygon] == [
        (p.x, p.z) for p in convex_room.floor_polygon
    ]
    auto_yaml = tmp_path / "auto.yaml"
    convex_yaml = tmp_path / "convex.yaml"
    write_room_yaml(auto_room, auto_yaml)
    write_room_yaml(convex_room, convex_yaml)
    assert auto_yaml.read_bytes() == convex_yaml.read_bytes()


def test_mesh_adapter_auto_resolve_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-resolve: 'auto' resolves via arg + env; the bad-value error lists all four modes."""
    assert MeshAdapter._resolve_floor_reconstruction("auto") == "auto"

    monkeypatch.setenv("ROOMESTIM_MESH_FLOOR_RECON", "auto")
    assert MeshAdapter()._floor_reconstruction == "auto"

    monkeypatch.setenv("ROOMESTIM_MESH_FLOOR_RECON", "bogus")
    with pytest.raises(ValueError, match="auto") as exc:
        MeshAdapter()
    msg = str(exc.value)
    assert all(m in msg for m in ("convex", "concave", "occupancy", "auto"))
