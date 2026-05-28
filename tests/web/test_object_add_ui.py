"""tests/web/test_object_add_ui.py — v0.17 Phase 6 Object Add UI.

Covers Phase 6 acceptance gates per .omc/plans/v0.17-design.md (Phase 6,
line 714-721):

- ``build_demo`` returns a Gradio Blocks (smoke).
- ``_on_add_object`` adds a column to a lab_room.
- ``_on_remove_object`` removes the requested index.
- ``build_room_figure`` trace count grows after a column is added.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("gradio")
pytest.importorskip("plotly")

from roomestim import Object, evolve_room_add_object  # noqa: E402
from roomestim.adapters.roomplan import RoomPlanAdapter  # noqa: E402
from roomestim.model import (  # noqa: E402
    MaterialLabel,
    PlacedSpeaker,
    PlacementResult,
    Point3,
    RoomModel,
)
from roomestim_web.object_add import _on_add_object, _on_remove_object  # noqa: E402


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
            PlacedSpeaker(channel=1, position=Point3(x=1.0, y=1.2, z=1.0)),
            PlacedSpeaker(channel=2, position=Point3(x=-1.0, y=1.2, z=1.0)),
        ],
        layout_name="object-add-test",
    )


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_object_add_tab_components() -> None:
    """``build_demo`` boots without exception and yields a Gradio Blocks."""
    import gradio as gr

    from roomestim_web.app import build_demo

    demo = build_demo()
    assert isinstance(demo, gr.Blocks)


def test_on_add_object_column_to_lab_room(lab_room: RoomModel) -> None:
    """``_on_add_object`` appends a column to a lab_room with empty objects."""
    form_data = {
        "anchor_x": 1.0,
        "anchor_y": 0.0,
        "anchor_z": 1.0,
        "width_m": 0.3,
        "height_m": 2.85,
        "depth_m": 0.3,
        "wall_index": None,
        "material": MaterialLabel.WALL_CONCRETE.value,
    }
    new_room, status = _on_add_object(lab_room, "column", form_data)
    assert new_room is not None
    assert len(new_room.objects) == 1
    assert new_room.objects[0].kind == "column"
    assert "추가" in status or "객체" in status


def test_on_add_object_rejects_out_of_range_wall_index(lab_room: RoomModel) -> None:
    """A door whose wall_index exceeds the wall count is rejected with a
    user-facing error and the room is returned unchanged (OQ-44(b) / D69)."""
    n_walls = sum(1 for s in lab_room.surfaces if s.kind == "wall")
    form_data = {
        "anchor_x": 0.0,
        "anchor_y": 0.0,
        "anchor_z": 0.0,
        "width_m": 0.9,
        "height_m": 2.1,
        "depth_m": 0.0,
        "wall_index": n_walls + 5,  # out of range
        "material": MaterialLabel.WALL_PAINTED.value,
    }
    same_room, status = _on_add_object(lab_room, "door", form_data)
    # Room unchanged (same object, still empty objects), error surfaced.
    assert same_room is lab_room
    assert "오류" in status
    assert "wall_index" in status
    assert str(n_walls + 5) in status


def test_on_add_object_accepts_in_range_wall_index(lab_room: RoomModel) -> None:
    """An in-range wall_index door is added (the bound is not over-eager)."""
    form_data = {
        "anchor_x": 0.0,
        "anchor_y": 0.0,
        "anchor_z": 0.0,
        "width_m": 0.9,
        "height_m": 2.1,
        "depth_m": 0.0,
        "wall_index": 0,
        "material": MaterialLabel.WALL_PAINTED.value,
    }
    new_room, status = _on_add_object(lab_room, "door", form_data)
    assert new_room is not None
    assert len(new_room.objects) == 1
    assert new_room.objects[0].kind == "door"
    assert new_room.objects[0].wall_index == 0


def test_on_remove_object(lab_room: RoomModel) -> None:
    """Removing index 0 of a two-object room leaves the second object."""
    col_a = Object(
        kind="column",
        anchor=Point3(x=1.0, y=0.0, z=1.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )
    col_b = Object(
        kind="column",
        anchor=Point3(x=2.0, y=0.0, z=1.0),
        width_m=0.4,
        height_m=2.85,
        depth_m=0.4,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )
    with_two = evolve_room_add_object(
        evolve_room_add_object(lab_room, col_a),
        col_b,
    )
    new_room, status = _on_remove_object(with_two, 0)
    assert new_room is not None
    assert len(new_room.objects) == 1
    # The remaining object is col_b.
    assert new_room.objects[0].anchor.x == pytest.approx(2.0)
    assert "제거" in status or "객체" in status


def test_object_add_3d_viewer_updates(
    lab_room: RoomModel, placement: PlacementResult
) -> None:
    """Adding a column object grows the Plotly figure's trace list."""
    from roomestim_web.viewer import build_room_figure

    base_fig = build_room_figure(lab_room, placement)
    base_traces = len(base_fig.data)

    col = Object(
        kind="column",
        anchor=Point3(x=1.0, y=0.0, z=1.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )
    new_room = evolve_room_add_object(lab_room, col)
    new_fig = build_room_figure(new_room, placement)
    assert len(new_fig.data) > base_traces, (
        f"viewer trace count did not grow: base={base_traces}, "
        f"new={len(new_fig.data)}"
    )
