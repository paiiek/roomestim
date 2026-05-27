"""Regression: viewer ``_wall_attached_traces`` resolves ``wall_index`` on the
WALLS-ONLY frame, identical to the predictor (① fix, ADR 0037).

Pre-fix the viewer did ``room.surfaces[obj.wall_index]`` (full-surfaces frame).
For ``lab_room.json`` (surface order ``[floor, ceiling, wall, wall, wall, wall]``)
that resolved ``wall_index=2`` to the FIRST wall (``walls[0]``), while the
predictor resolved it to the THIRD wall (``walls[2]``). This test asserts the
produced quad lies on ``walls[2]`` — it FAILS on the pre-fix viewer (the quad
would lie on ``walls[0]``, whose ``polygon[0]`` differs in both x and z).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("plotly")

import plotly.graph_objects as go  # noqa: E402

from roomestim.adapters.roomplan import RoomPlanAdapter  # noqa: E402
from roomestim.model import MaterialLabel, Object, Point3  # noqa: E402
from roomestim_web.viewer import _wall_attached_traces  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lab_room.json"

WALL_INDEX = 2  # nonzero → distinguishes walls-only frame from full-surfaces


def _door_at(wall_index: int) -> Object:
    # anchor.x == 0 → the quad's first corner sits exactly on wall.polygon[0].
    return Object(
        kind="door",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=0.9,
        height_m=2.0,
        depth_m=0.0,
        wall_index=wall_index,
        material=MaterialLabel.WOOD_FLOOR,
    )


def test_viewer_resolves_wall_index_on_walls_only_frame() -> None:
    """The wall-attached quad lies on walls[wall_index], the same surface the
    predictor's α-override picks — not full-surfaces[wall_index]."""
    room = RoomPlanAdapter().parse(FIXTURE)
    walls = [s for s in room.surfaces if s.kind == "wall"]
    assert len(walls) > WALL_INDEX

    obj = _door_at(WALL_INDEX)
    traces = _wall_attached_traces(obj, room, color="#888888", go=go)
    assert len(traces) == 1
    quad = traces[0]

    expected = walls[WALL_INDEX].polygon[0]  # predictor-frame wall
    # With anchor.x == 0 the bottom-left corner equals walls[2].polygon[0].
    assert quad.x[0] == pytest.approx(expected.x)
    assert quad.z[0] == pytest.approx(expected.z)

    # Load-bearing guard: the picked wall is NOT full-surfaces[WALL_INDEX]
    # (which in lab_room is walls[0], a DIFFERENT wall). Pre-fix code resolved
    # to that surface and would fail the assertions above.
    wrong = room.surfaces[WALL_INDEX].polygon[0]
    assert (wrong.x, wrong.z) != (expected.x, expected.z)


def test_viewer_and_predictor_pick_same_wall() -> None:
    """Shared invariant: viewer-picked wall surface IS walls[wall_index] — the
    identical object the predictor's _objects_to_wall_alpha_overrides indexes."""
    room = RoomPlanAdapter().parse(FIXTURE)
    walls = [s for s in room.surfaces if s.kind == "wall"]
    picked = walls[WALL_INDEX]
    assert picked.kind == "wall"

    obj = _door_at(WALL_INDEX)
    traces = _wall_attached_traces(obj, room, color="#888888", go=go)
    quad = traces[0]
    # The viewer's p0 is walls[WALL_INDEX].polygon[0]; assert quad anchors there.
    assert quad.x[0] == pytest.approx(picked.polygon[0].x)
    assert quad.z[0] == pytest.approx(picked.polygon[0].z)
