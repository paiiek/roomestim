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
                result = _on_submit(mock_file, "vbap", "8", 2.0, 0.0, False)

    assert result == (None,) * 6, f"Expected (None,)*6 but got {result!r}"

    error_records = [
        r for r in caplog.records
        if r.levelno >= logging.ERROR and "run_pipeline failed" in r.message
    ]
    assert error_records, (
        "Expected an ERROR log record with 'run_pipeline failed' on logger 'roomestim_web'. "
        f"Records seen: {[(r.name, r.levelno, r.message) for r in caplog.records]}"
    )
