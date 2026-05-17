"""tests/web/test_wfs_ux.py — WFS UX error surface tests (v0.12-web.4)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest


pytestmark = pytest.mark.web


def test_wfs_error_surfaces_in_report_json(tmp_path: Path) -> None:
    """WFS spatial-aliasing ValueError is surfaced as report_json["error"]."""
    from roomestim_web.app import _on_submit

    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")

    src = shutil.copy(fixture, tmp_path / "lab_room.json")

    class _FakeFile:
        name = str(src)

    # n_speakers=4, radius=2.0 → spacing≈1.33m, f_max=300 Hz → bound≈0.57m → fails aliasing
    result = _on_submit(
        _FakeFile(),
        "wfs",
        "4",
        2.0,
        0.0,
        False,
        300.0,  # wfs_f_max_hz — triggers spatial aliasing error
    )
    viewer, report_chart, report_json, pdf, binaural, binaural_status_md, raw = result
    assert viewer is None
    assert report_chart is None
    assert pdf is None
    assert binaural is None
    assert raw is None
    assert isinstance(report_json, dict), f"Expected dict, got {type(report_json)}"
    assert "error" in report_json, f"Expected 'error' key in {report_json}"
    assert report_json.get("algorithm") == "wfs"
    # binaural_status_md is gr.update / dict fallback; on ValueError path it's hidden.
    assert binaural_status_md is not None


def test_wfs_error_message_contains_aliasing_info() -> None:
    """WFS ValueError message from dispatch includes aliasing details."""
    from roomestim.place.dispatch import run_placement
    from roomestim.adapters.roomplan import RoomPlanAdapter

    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")

    room = RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=False)

    with pytest.raises(ValueError) as exc_info:
        run_placement(
            room,
            "wfs",
            n_speakers=4,
            layout_radius_m=2.0,
            el_deg=0.0,
            wfs_f_max_hz=300.0,
        )

    msg = str(exc_info.value)
    # dispatch.py raises with "WFS spatial-aliasing bound violated"
    assert "aliasing" in msg.lower() or "spacing" in msg.lower() or "WFS" in msg
