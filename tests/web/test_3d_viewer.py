"""Tests for roomestim_web.viewer — 3D Plotly figure generation.

Marked @pytest.mark.web; skipped if plotly is not installed.
"""
from __future__ import annotations

import pytest

plotly = pytest.importorskip("plotly")
import plotly.graph_objects as go  # noqa: E402

from roomestim.adapters.polycam import PolycamAdapter
from roomestim.place.dispatch import run_placement
from roomestim_web.material_palette import MATERIAL_PALETTE
from roomestim_web.viewer import build_room_figure


@pytest.fixture
def fixture_room_and_layout():
    adapter = PolycamAdapter()
    room = adapter.parse(
        "tests/fixtures/lab_room.obj", scale_anchor=None, octave_band=False
    )
    layout = run_placement(room, "vbap", 8, 2.0, 0.0)
    return room, layout


@pytest.mark.web
def test_room_figure_trace_count(fixture_room_and_layout):
    """Mesh3d per surface + 1 Scatter3d for speakers + 1 for listener + 1 for aim-lines."""
    room, layout = fixture_room_and_layout
    fig = build_room_figure(room, layout)
    n_surfaces = len(room.surfaces)
    expected = n_surfaces + 3  # surfaces + speakers + listener + aim
    assert len(fig.data) == expected


@pytest.mark.web
def test_room_figure_camera_default(fixture_room_and_layout):
    room, layout = fixture_room_and_layout
    fig = build_room_figure(room, layout)
    cam = fig.layout.scene.camera
    assert cam.eye.x == pytest.approx(1.5)
    assert cam.eye.y == pytest.approx(1.2)
    assert cam.eye.z == pytest.approx(1.5)
    assert cam.up.x == pytest.approx(0.0)
    assert cam.up.y == pytest.approx(1.0)
    assert cam.up.z == pytest.approx(0.0)


@pytest.mark.web
def test_room_figure_material_color_mapping(fixture_room_and_layout):
    """Each Mesh3d trace's color matches the §9.2 palette for its material."""
    room, layout = fixture_room_and_layout
    fig = build_room_figure(room, layout)
    mesh_traces = [t for t in fig.data if t.type == "mesh3d"]
    assert len(mesh_traces) == len(room.surfaces)
    for trace, surface in zip(mesh_traces, room.surfaces):
        expected_color = MATERIAL_PALETTE[surface.material]
        assert trace.color == expected_color
