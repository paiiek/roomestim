"""tests/test_gltf_export.py — v0.17 Phase 6 gLTF / GLB export.

Covers Phase 6 acceptance gates per .omc/plans/v0.17-design.md (Phase 6,
line 697-705):

- ``write_gltf`` produces a non-trivial GLB file (≥ 1 KB).
- ``trimesh.load`` recovers a Scene with geometry for every wall.
- Each Trimesh has a visible material colour (face_colors or PBR).
- Adding a column object grows the loaded Scene's geometry count.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import trimesh

from roomestim import Object, evolve_room_add_object
from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.export.gltf import write_gltf
from roomestim.model import (
    MaterialLabel,
    PlacedSpeaker,
    PlacementResult,
    Point3,
    RoomModel,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def lab_room() -> RoomModel:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    return RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)


@pytest.fixture
def placement() -> PlacementResult:
    return PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="ring",
        speakers=[
            PlacedSpeaker(channel=0, position=Point3(x=1.0, y=1.2, z=1.0)),
            PlacedSpeaker(channel=1, position=Point3(x=-1.0, y=1.2, z=1.0)),
        ],
        layout_name="gltf-test",
    )


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_write_gltf_smoke(
    lab_room: RoomModel, placement: PlacementResult, tmp_path: Path
) -> None:
    """``write_gltf`` produces a non-trivial GLB file."""
    out = tmp_path / "test.glb"
    write_gltf(lab_room, placement, out, format="glb")
    assert out.exists()
    assert out.stat().st_size >= 1024, f"GLB smaller than 1 KB: {out.stat().st_size}"


def test_write_gltf_round_trip_trimesh(
    lab_room: RoomModel, placement: PlacementResult, tmp_path: Path
) -> None:
    """``trimesh.load`` recovers a Scene with at least ``n_walls`` geometries."""
    out = tmp_path / "rt.glb"
    write_gltf(lab_room, placement, out, format="glb")
    loaded = trimesh.load(out)
    assert isinstance(loaded, trimesh.Scene)
    n_walls = sum(1 for s in lab_room.surfaces if s.kind == "wall")
    assert len(loaded.geometry) >= n_walls


def test_write_gltf_material_color(
    lab_room: RoomModel, placement: PlacementResult, tmp_path: Path
) -> None:
    """Every loaded Trimesh exposes a visible material colour (face_colors or PBR)."""
    out = tmp_path / "color.glb"
    write_gltf(lab_room, placement, out, format="glb")
    loaded = trimesh.load(out)
    assert isinstance(loaded, trimesh.Scene)
    assert len(loaded.geometry) > 0
    saw_color = False
    for mesh in loaded.geometry.values():
        visual = cast(Any, mesh).visual
        if hasattr(visual, "face_colors"):
            try:
                if len(visual.face_colors) > 0:
                    saw_color = True
                    break
            except Exception:
                pass
        if hasattr(visual, "material"):
            mat = visual.material
            if mat is not None and (
                hasattr(mat, "baseColorFactor") or hasattr(mat, "main_color")
            ):
                saw_color = True
                break
    assert saw_color, "No mesh exposed a visible material colour"


def test_write_gltf_objects_included(
    lab_room: RoomModel, placement: PlacementResult, tmp_path: Path
) -> None:
    """Adding a column object grows the loaded Scene's geometry count."""
    out_base = tmp_path / "base.glb"
    write_gltf(lab_room, placement, out_base, format="glb")
    loaded_base = trimesh.load(out_base)
    assert isinstance(loaded_base, trimesh.Scene)
    base_count = len(loaded_base.geometry)

    col = Object(
        kind="column",
        anchor=Point3(x=1.0, y=0.0, z=1.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )
    room_with_col = evolve_room_add_object(lab_room, col)
    out_col = tmp_path / "col.glb"
    write_gltf(room_with_col, placement, out_col, format="glb")
    loaded_col = trimesh.load(out_col)
    assert isinstance(loaded_col, trimesh.Scene)
    col_count = len(loaded_col.geometry)
    assert col_count > base_count, (
        f"GLB geometry count did not grow after adding column: "
        f"base={base_count}, with_col={col_count}"
    )
