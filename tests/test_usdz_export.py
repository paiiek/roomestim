"""tests/test_usdz_export.py — v0.17 Phase 6 USDZ export.

Covers Phase 6 acceptance gates per .omc/plans/v0.17-design.md (Phase 6,
line 687-696):

- ``write_usdz`` produces a non-trivial USDZ file (≥ 1 KB).
- The package round-trips via :class:`pxr.Usd.Stage` and exposes a
  vertex-bearing prim hierarchy.
- ``with_acoustics_sidecar=True`` writes ``<out>.acoustics.json`` listing
  every surface.
- Adding a column object produces extra column-derived prims in the USDZ.

The whole module is skipped when ``pxr`` is not installed (i.e. the
``[usd]`` extras are absent).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pxr")

from pxr import Usd  # noqa: E402  (must come after importorskip)

from roomestim import Object, evolve_room_add_object  # noqa: E402
from roomestim.adapters.roomplan import RoomPlanAdapter  # noqa: E402
from roomestim.export.usd import write_usdz  # noqa: E402
from roomestim.model import (  # noqa: E402
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
        regularity_hint="IRREGULAR",
        speakers=[
            PlacedSpeaker(channel=0, position=Point3(x=1.0, y=1.2, z=1.0)),
            PlacedSpeaker(channel=1, position=Point3(x=-1.0, y=1.2, z=1.0)),
        ],
        layout_name="usdz-test",
    )


def _count_mesh_vertices(stage: Usd.Stage) -> int:
    total = 0
    for prim in stage.Traverse():
        if prim.GetTypeName() == "Mesh":
            attr = prim.GetAttribute("points")
            if attr.IsValid():
                pts = attr.Get()
                if pts is not None:
                    total += len(pts)
    return total


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_write_usdz_smoke(
    lab_room: RoomModel, placement: PlacementResult, tmp_path: Path
) -> None:
    """``write_usdz`` produces a non-trivial USDZ file."""
    out = tmp_path / "test.usdz"
    write_usdz(lab_room, placement, out)
    assert out.exists()
    assert out.stat().st_size >= 1024, f"USDZ smaller than 1 KB: {out.stat().st_size}"


def test_write_usdz_round_trip_mesh_vertex_count(
    lab_room: RoomModel, placement: PlacementResult, tmp_path: Path
) -> None:
    """Opening the USDZ via Usd.Stage exposes mesh prims with ≥ 8 vertices."""
    out = tmp_path / "rt.usdz"
    write_usdz(lab_room, placement, out)
    stage = Usd.Stage.Open(str(out))
    assert stage is not None
    total_verts = _count_mesh_vertices(stage)
    assert total_verts >= 8, f"too few mesh vertices in USDZ: {total_verts}"


def test_write_usdz_with_acoustics_sidecar(
    lab_room: RoomModel, placement: PlacementResult, tmp_path: Path
) -> None:
    """``with_acoustics_sidecar=True`` writes a JSON sidecar listing every surface."""
    out = tmp_path / "side.usdz"
    write_usdz(lab_room, placement, out, with_acoustics_sidecar=True)
    sidecar = out.with_suffix(out.suffix + ".acoustics.json")
    assert sidecar.exists(), f"sidecar missing: {sidecar}"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert "surfaces" in payload
    assert len(payload["surfaces"]) == len(lab_room.surfaces)


def test_write_usdz_objects_included(
    lab_room: RoomModel, placement: PlacementResult, tmp_path: Path
) -> None:
    """Adding a column object emits additional mesh prims into the USDZ."""
    out_base = tmp_path / "base.usdz"
    write_usdz(lab_room, placement, out_base)
    stage_base = Usd.Stage.Open(str(out_base))
    assert stage_base is not None
    base_mesh_count = sum(
        1 for prim in stage_base.Traverse() if prim.GetTypeName() == "Mesh"
    )

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
    out_col = tmp_path / "col.usdz"
    write_usdz(room_with_col, placement, out_col)
    stage_col = Usd.Stage.Open(str(out_col))
    assert stage_col is not None
    col_mesh_count = sum(
        1 for prim in stage_col.Traverse() if prim.GetTypeName() == "Mesh"
    )
    # A column emits 5 extra faces (4 sides + top) → mesh count strictly grows.
    assert col_mesh_count > base_mesh_count, (
        f"USDZ mesh count did not grow after adding column: "
        f"base={base_mesh_count}, with_col={col_mesh_count}"
    )
