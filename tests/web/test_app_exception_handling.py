"""tests/web/test_app_exception_handling.py — top-level guard in _on_submit."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("gradio")

from roomestim_web.app import _on_submit


@pytest.mark.web
def test_on_submit_returns_all_none_on_pipeline_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When run_pipeline raises, _on_submit must return (None,)*6 and log ERROR."""
    mock_file = MagicMock()
    mock_file.name = "tests/fixtures/lab_room.obj"

    with patch("roomestim_web.pipeline.run_pipeline", side_effect=RuntimeError("synthetic")):
        # Also patch the imports inside _on_submit so they don't fail before run_pipeline
        with patch.dict(
            "sys.modules",
            {
                "roomestim_web.archive": MagicMock(),
                "roomestim_web.provenance": MagicMock(),
                "roomestim_web.viewer": MagicMock(),
            },
        ):
            with caplog.at_level(logging.ERROR, logger="roomestim_web"):
                result = _on_submit(mock_file, "vbap", "8", 2.0, 0.0, False, 8000.0)

    # v0.16.1: 12-tuple (added layout_state at index 11).
    # Positions: 0-4 None, 5 binaural_status_md (gr.update/dict), 6-11 None.
    assert len(result) == 12, f"Expected 12-tuple, got {len(result)}: {result!r}"
    assert result[:5] == (None,) * 5, f"Expected first 5 None, got {result[:5]!r}"
    assert result[6] is None, f"Expected position 6 (raw_file) None, got {result[6]!r}"
    assert result[7] is None, f"Expected position 7 (material_table) None, got {result[7]!r}"
    assert result[8] is None, f"Expected position 8 (blueprint_png) None, got {result[8]!r}"
    assert result[9] is None, f"Expected position 9 (blueprint_svg) None, got {result[9]!r}"
    assert result[10] is None, f"Expected position 10 (room_state) None, got {result[10]!r}"
    assert result[11] is None, f"Expected position 11 (layout_state) None, got {result[11]!r}"
    # binaural_status_md (index 5) is hidden update — not strict-None
    assert result[5] is not None, "Expected binaural_status_md to be a gr.update / dict"

    error_records = [
        r for r in caplog.records
        if r.levelno >= logging.ERROR and "run_pipeline failed" in r.message
    ]
    assert error_records, (
        "Expected an ERROR log record with 'run_pipeline failed' on logger 'roomestim_web'. "
        f"Records seen: {[(r.name, r.levelno, r.message) for r in caplog.records]}"
    )


# --------------------------------------------------------------------------- #
# OQ-45 / ADR 0038 — web-facing error strings are scrubbed (no path / raw exc)
# --------------------------------------------------------------------------- #

_LEAK_MARKER = "/home/seung/secret-dev-path/engine_schema.json"


@pytest.mark.web
def test_on_submit_value_error_does_not_leak_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A ValueError carrying a dev path must NOT reach the web-facing report JSON."""
    mock_file = MagicMock()
    mock_file.name = "tests/fixtures/lab_room.obj"

    with patch(
        "roomestim_web.pipeline.run_pipeline",
        side_effect=ValueError(f"validation failed: {_LEAK_MARKER}"),
    ):
        with patch.dict(
            "sys.modules",
            {
                "roomestim_web.archive": MagicMock(),
                "roomestim_web.provenance": MagicMock(),
                "roomestim_web.viewer": MagicMock(),
            },
        ):
            with caplog.at_level(logging.WARNING, logger="roomestim_web"):
                result = _on_submit(mock_file, "vbap", "8", 2.0, 0.0, False, 8000.0)

    error_report = result[2]
    assert isinstance(error_report, dict), f"Expected dict report, got {error_report!r}"
    serialized = repr(error_report)
    assert _LEAK_MARKER not in serialized, f"Dev path leaked into web report: {serialized!r}"
    assert "validation failed" not in serialized, f"Raw exc text leaked: {serialized!r}"
    assert "서버 로그를 확인하세요" in error_report["error"], (
        f"Expected generic message, got {error_report!r}"
    )
    # Full detail must still be logged server-side.
    assert any(_LEAK_MARKER in r.getMessage() for r in caplog.records), (
        "Expected full detail in server-side log"
    )


@pytest.mark.web
def test_on_export_does_not_leak_exception_text() -> None:
    """_on_export exception branch must return a generic message, not raw exc text."""
    from roomestim_web.app import _on_export

    room = MagicMock()
    layout = MagicMock()
    with patch(
        "roomestim.export.write_layout_yaml",
        side_effect=RuntimeError(_LEAK_MARKER),
    ):
        _file, status = _on_export(room, layout, "yaml")

    status_str = repr(status)
    assert _LEAK_MARKER not in status_str, f"Dev path leaked into export status: {status_str!r}"
    assert "서버 로그를 확인하세요" in status_str, f"Expected generic message, got {status_str!r}"


@pytest.mark.web
def test_on_apply_overrides_wrapper_does_not_leak_exception_text() -> None:
    """_on_apply_overrides_wrapper exception branch returns a generic message."""
    from roomestim_web.app import _on_apply_overrides_wrapper

    room = MagicMock()
    with patch(
        "roomestim_web.material_override.on_apply_overrides",
        side_effect=RuntimeError(_LEAK_MARKER),
    ):
        result = _on_apply_overrides_wrapper(room, None, "{}")

    status_str = repr(result[4])
    assert _LEAK_MARKER not in status_str, f"Dev path leaked into status: {status_str!r}"
    assert "서버 로그를 확인하세요" in status_str, f"Expected generic message, got {status_str!r}"


# --------------------------------------------------------------------------- #
# OQ-45 / ADR 0038 (Gap 2) — the upload cap must be bound on the build_demo()
# Blocks object so gradio's server honors it regardless of launch path. The HF
# entrypoint (root app.py: ``demo = build_demo(); demo.launch()``) never runs
# roomestim_web's ``__main__`` guard, so a launch-only cap would be inert there.
# --------------------------------------------------------------------------- #


@pytest.mark.web
def test_build_demo_binds_upload_cap() -> None:
    """build_demo() must set max_file_size on the Blocks object (effective at HF)."""
    from roomestim_web.app import _MAX_UPLOAD_BYTES, build_demo

    demo = build_demo()
    assert demo.max_file_size == _MAX_UPLOAD_BYTES, (
        "build_demo() must bind the upload cap on the Blocks object so gradio's "
        f"server honors it; got {demo.max_file_size!r}, want {_MAX_UPLOAD_BYTES!r}"
    )


@pytest.mark.web
def test_root_entrypoint_carries_upload_cap() -> None:
    """The HF root entrypoint's `demo` object must carry the cap (not launch-only)."""
    import importlib

    root_app = importlib.import_module("app")
    from roomestim_web.app import _MAX_UPLOAD_BYTES

    assert root_app.demo.max_file_size == _MAX_UPLOAD_BYTES, (
        "Root app.py `demo` must carry the upload cap so the HF-served app "
        f"enforces it; got {root_app.demo.max_file_size!r}"
    )
