"""tests/web/test_pipeline_integration.py — end-to-end smoke tests."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

pytest.importorskip("pyroomacoustics")
pytest.importorskip("soundfile")

import numpy as np
import soundfile as sf

from roomestim_web.pipeline import run_pipeline


@pytest.fixture
def synthetic_source_wav(tmp_path: Path) -> Path:
    sr = 48000
    n = int(2.0 * sr)
    t = np.arange(n) / sr
    np.random.seed(0)
    sig = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    p = tmp_path / "source.wav"
    sf.write(str(p), sig, sr, subtype="PCM_16")
    return p


@pytest.mark.web
def test_pipeline_end_to_end_obj_produces_yamls(tmp_path: Path) -> None:
    """Polycam .obj → run_pipeline → both YAMLs exist."""
    result = run_pipeline(
        "tests/fixtures/lab_room.obj",
        algorithm="vbap",
        n_speakers=8,
        layout_radius_m=2.0,
        el_deg=0.0,
        octave_band=False,
        out_dir=tmp_path,
    )
    assert result.room_yaml_path.exists()
    assert result.layout_yaml_path.exists()
    assert len(result.layout.speakers) == 8


@pytest.mark.web
def test_pipeline_end_to_end_with_archive(
    tmp_path: Path, synthetic_source_wav: Path
) -> None:
    """Full chain: pipeline → binaural → archive ZIP."""
    from roomestim_web.archive import ArchiveArtefacts, build_result_archive
    from roomestim_web.binaural import render_binaural_demo
    from roomestim_web.hrtf_io import HrtfTable
    from roomestim_web.provenance import build_provenance_readme

    result = run_pipeline(
        "tests/fixtures/lab_room.obj",
        algorithm="vbap",
        n_speakers=8,
        layout_radius_m=2.0,
        el_deg=0.0,
        octave_band=False,
        out_dir=tmp_path,
    )

    # Synthetic HRTF for fast test
    dirs = np.array(
        [[0, 0], [90, 0], [180, 0], [270, 0], [0, 90], [0, -90]], dtype=np.float64
    )
    hrir = np.zeros((6, 64), dtype=np.float64)
    hrir[:, 0] = 1.0
    hrtf = HrtfTable(
        sample_rate_hz=48000,
        directions=dirs,
        hrirs_left=hrir,
        hrirs_right=hrir,
        attribution="synthetic-integration",
    )

    wav_path = render_binaural_demo(
        result.room,  # type: ignore[arg-type]
        result.layout,  # type: ignore[arg-type]
        synthetic_source_wav,
        tmp_path / "bin.wav",
        hrtf=hrtf,
        max_order=2,
        duration_s=2.0,
    )

    readme = build_provenance_readme(
        input_path="tests/fixtures/lab_room.obj",
        algorithm="vbap",
        n_speakers=8,
        layout_radius_m=2.0,
        el_deg=0.0,
        octave_band=False,
        roomestim_version="test",
        roomestim_web_version="0.12-web.0",
    )
    art = ArchiveArtefacts(
        room_yaml=result.room_yaml_path,
        layout_yaml=result.layout_yaml_path,
        setup_pdf=None,  # reportlab might not be installed
        binaural_wav=wav_path,
        acoustic_report_json=None,  # plotly path is optional
    )
    zip_path = build_result_archive(art, readme, tmp_path / "result.zip")
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert "room.yaml" in names
    assert "layout.yaml" in names
    assert "binaural_demo.wav" in names
    assert "README.txt" in names
