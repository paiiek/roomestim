"""tests/web/test_rough_tier_ui.py — Gradio wiring for the rough+ consumer tier.

Verifies the Increment 2 UI wiring: the ceiling-height number input and the
snap-to-surface checkbox reach ``run_pipeline`` through ``_on_submit``, and that
``build_demo`` still assembles with the two new components bound to the submit
click (PLACEMENT_SENSITIVITY_VERDICT.md).
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("gradio")

from roomestim_web.app import _on_submit


def _capture_run_pipeline_kwargs(
    *on_submit_args: object,
) -> dict[str, object]:
    """Call _on_submit, capturing the kwargs passed to run_pipeline.

    run_pipeline is patched to record its kwargs then raise, so _on_submit
    returns via its except path without exercising the heavy downstream chain.
    """
    captured: dict[str, object] = {}

    def _capture(*_a: object, **k: object) -> object:
        captured.update(k)
        raise RuntimeError("stop-after-capture")

    with patch("roomestim_web.pipeline.run_pipeline", side_effect=_capture):
        with patch.dict(
            sys.modules,
            {
                "roomestim_web.archive": MagicMock(),
                "roomestim_web.provenance": MagicMock(),
                "roomestim_web.viewer": MagicMock(),
            },
        ):
            _on_submit(*on_submit_args)
    return captured


@pytest.mark.web
def test_on_submit_forwards_ceiling_and_snap() -> None:
    """A non-zero ceiling + checked snap reach run_pipeline verbatim."""
    mock_file = MagicMock()
    mock_file.name = "rough.npz"
    kwargs = _capture_run_pipeline_kwargs(
        mock_file, "dbap", "8", 2.0, 0.0, False, 8000.0, False, 2.7, True
    )
    assert kwargs["ceiling_height_m"] == pytest.approx(2.7)
    assert kwargs["snap_to_surfaces"] is True


@pytest.mark.web
def test_on_submit_blank_ceiling_becomes_none() -> None:
    """A blank/zero ceiling is coerced to None (auto-estimate)."""
    mock_file = MagicMock()
    mock_file.name = "rough.npz"
    # ceiling 0.0 -> None; snap unchecked
    k0 = _capture_run_pipeline_kwargs(
        mock_file, "dbap", "8", 2.0, 0.0, False, 8000.0, False, 0.0, False
    )
    assert k0["ceiling_height_m"] is None
    assert k0["snap_to_surfaces"] is False
    # ceiling None (Gradio Number left empty) -> None
    kn = _capture_run_pipeline_kwargs(
        mock_file, "dbap", "8", 2.0, 0.0, False, 8000.0, False, None, False
    )
    assert kn["ceiling_height_m"] is None


@pytest.mark.web
def test_on_submit_defaults_backward_compatible() -> None:
    """Legacy 7-positional-arg call (no ceiling/snap) still maps to None/False."""
    mock_file = MagicMock()
    mock_file.name = "tests/fixtures/lab_room.obj"
    kwargs = _capture_run_pipeline_kwargs(
        mock_file, "vbap", "8", 2.0, 0.0, False, 8000.0
    )
    assert kwargs["ceiling_height_m"] is None
    assert kwargs["snap_to_surfaces"] is False
    assert kwargs["floor_length_m"] is None


@pytest.mark.web
def test_on_submit_forwards_floor_length() -> None:
    """A non-zero floor length reaches run_pipeline; blank/0 coerces to None."""
    mock_file = MagicMock()
    mock_file.name = "rough.npz"
    k = _capture_run_pipeline_kwargs(
        mock_file, "dbap", "8", 2.0, 0.0, False, 8000.0, False, 2.7, True, 5.0
    )
    assert k["floor_length_m"] == pytest.approx(5.0)
    # 0.0 → None (no anchor)
    k0 = _capture_run_pipeline_kwargs(
        mock_file, "dbap", "8", 2.0, 0.0, False, 8000.0, False, 2.7, True, 0.0
    )
    assert k0["floor_length_m"] is None


@pytest.mark.web
def test_build_demo_assembles_with_new_inputs() -> None:
    """build_demo() wires the two new components into the submit click w/o error."""
    import gradio as gr

    from roomestim_web.app import build_demo

    # Avoid the background web-data fetch (network) during the smoke build.
    with patch("roomestim_web.app._ensure_web_data", return_value=False):
        with patch("roomestim_web.app._binaural_data_present", return_value=True):
            demo = build_demo()
    assert isinstance(demo, gr.Blocks)
