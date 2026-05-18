"""tests/web/test_binaural_fallback.py — binaural fallback UX test (v0.12-web.4)."""
from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.web


def test_binaural_fallback_when_source_missing(tmp_path: Path) -> None:
    """When source.wav is absent, binaural_str is None and report_json has binaural_status."""
    from roomestim_web.app import _on_submit

    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")

    src = shutil.copy(fixture, tmp_path / "lab_room.json")

    class _FakeFile:
        name = str(src)

    # Patch _BINAURAL_DATA_ROOT so source.wav and SOFA files do not exist
    fake_data_root = tmp_path / "data"
    (fake_data_root / "hrtf").mkdir(parents=True)
    (fake_data_root / "audio").mkdir(parents=True)
    # Do NOT create source.wav or kemar.sofa — simulating missing data

    with patch("roomestim_web.app._BINAURAL_DATA_ROOT", fake_data_root):
        result = _on_submit(
            _FakeFile(),
            "vbap",
            "8",
            2.0,
            0.0,
            False,
            1500.0,  # wfs_f_max_hz (unused for vbap)
        )

    viewer, report_chart, report_json, pdf, binaural, binaural_status_md, raw, *_extra = result
    # binaural audio must be None (no data)
    assert binaural is None, f"Expected binaural=None, got {binaural}"
    # report_json must contain binaural_status explaining missing data (legacy key)
    assert isinstance(report_json, dict), f"Expected dict report_json, got {type(report_json)}"
    assert "binaural_status" in report_json, (
        f"Expected 'binaural_status' key in report_json: {report_json}"
    )
    status_msg = report_json["binaural_status"]
    assert "미준비" in status_msg or "없습니다" in status_msg or "data" in status_msg.lower(), (
        f"Unexpected binaural_status message: {status_msg}"
    )
    # binaural_status_md must surface the same message in the Markdown component
    from tests.web._md_helpers import get_md_payload

    md_value, md_visible = get_md_payload(binaural_status_md)
    assert md_visible is True, f"Expected binaural_status_md visible=True, got {md_visible}"
    assert md_value and ("미준비" in md_value or "없습니다" in md_value), (
        f"Expected Markdown to surface fallback message, got value={md_value!r}"
    )
