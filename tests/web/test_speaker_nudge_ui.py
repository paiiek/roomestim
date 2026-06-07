"""tests/web/test_speaker_nudge_ui.py — v0.18 Phase 5 Speaker Nudge UI.

Covers ADR 0036 §B web surface:
- ``build_demo`` exposes a "스피커 조정" tab with channel + 6 Δ Numbers + Apply.
- ``_on_nudge_speaker`` spherical Δ updates the layout.
- frame mixing (daz + dx) shows a red error and leaves the layout unchanged.
- a successful nudge rebuilds the 3D figure (build_room_figure not None).
"""

from __future__ import annotations

import math

import pytest

pytestmark = pytest.mark.web

pytest.importorskip("gradio")
pytest.importorskip("plotly")

from pathlib import Path  # noqa: E402

from roomestim.adapters.roomplan import RoomPlanAdapter  # noqa: E402
from roomestim.model import (  # noqa: E402
    PlacedSpeaker,
    PlacementResult,
    Point3,
    RoomModel,
)
from roomestim_web.speaker_nudge import _channel_to_index, _on_nudge_speaker  # noqa: E402


@pytest.fixture
def lab_room() -> RoomModel:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    return RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)


@pytest.fixture
def layout() -> PlacementResult:
    speakers = []
    for i, az_deg in enumerate((0.0, 90.0, 180.0)):
        az = math.radians(az_deg)
        speakers.append(
            PlacedSpeaker(
                channel=i + 1,
                position=Point3(x=2.0 * math.sin(az), y=0.0, z=2.0 * math.cos(az)),
            )
        )
    return PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="CIRCULAR",
        speakers=speakers,
        layout_name="nudge-test",
    )


def test_nudge_tab_components() -> None:
    import gradio as gr

    from roomestim_web.app import build_demo

    demo = build_demo()
    assert isinstance(demo, gr.Blocks)
    # the "스피커 조정" Tab label must appear among the components
    labels = [
        getattr(c, "label", None)
        for c in demo.blocks.values()
    ]
    assert "스피커 조정" in labels


def test_on_nudge_spherical_updates_layout(layout: PlacementResult) -> None:
    new_layout, fig, status = _on_nudge_speaker(
        None, layout, 1, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0
    )
    assert new_layout is not layout
    idx = _channel_to_index(layout, 1)
    assert idx is not None
    assert new_layout.speakers[idx].position != layout.speakers[idx].position
    assert "조정" in status or "적용" in status


def test_on_nudge_mixing_shows_error(layout: PlacementResult) -> None:
    new_layout, fig, status = _on_nudge_speaker(
        None, layout, 1, 5.0, 0.0, 0.0, 0.1, 0.0, 0.0
    )
    assert new_layout is layout  # unchanged
    assert fig is None
    assert status.startswith("오류")


def test_on_nudge_viewer_rebuild(lab_room: RoomModel, layout: PlacementResult) -> None:
    new_layout, fig, status = _on_nudge_speaker(
        lab_room, layout, 1, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0
    )
    assert fig is not None
    assert new_layout is not layout


# --------------------------------------------------------------------------- #
# OQ-45 / ADR 0038 (Gap 1) — the validate_placement-echo path must NOT leak the
# dev engine schema path to the web user. Load-bearing: if the speaker_nudge
# boundary scrub is reverted, this test fails (the path appears in `status`).
# --------------------------------------------------------------------------- #


def test_on_nudge_engine_validation_failure_does_not_leak_schema_path(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    layout: PlacementResult,
) -> None:
    """A missing engine schema makes validate_placement return a path-bearing
    FileNotFoundError string; the web user must see ONLY a generic message.

    This drives the REAL validate_placement (not a mock): the schema is forced
    to resolve to a missing file so the genuine engine FileNotFoundError carries
    the dev path. The web boundary must scrub it; the full detail is logged.
    """
    import logging

    # Point the ENV candidate at a missing dir so _resolve_schema_file raises the
    # descriptive FileNotFoundError naming the resolved schema path (the engine
    # path is no longer hardcoded; ENV is the only resolution leg — Candidate A).
    monkeypatch.setenv("SPATIAL_ENGINE_REPO_DIR", "/tmp/roomestim_nonexistent_engine_dir")

    # Sanity: the RAW collector still contains the path (CLI behavior intact).
    from roomestim.export import validate_placement

    raw_errs = validate_placement(layout)
    assert any("geometry_schema" in e for e in raw_errs), (
        "Test precondition broken: validate_placement should surface the missing "
        f"schema path for CLI use; got {raw_errs!r}"
    )

    with caplog.at_level(logging.WARNING, logger="roomestim_web.speaker_nudge"):
        new_layout, fig, status = _on_nudge_speaker(
            None, layout, 1, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0
        )

    # Web-facing string is scrubbed: no path, no schema filename, no raw errs.
    assert "/home/" not in status, f"Dev path leaked into web status: {status!r}"
    assert "geometry_schema" not in status, f"Schema filename leaked: {status!r}"
    assert "서버 로그를 확인하세요" in status, f"Expected generic message, got {status!r}"
    # Layout must be returned unchanged on validation failure.
    assert new_layout is layout
    assert fig is None
    # Full detail must still be logged server-side.
    assert any("geometry_schema" in r.getMessage() for r in caplog.records), (
        "Expected the full validate_placement detail (with path) in the server log"
    )
