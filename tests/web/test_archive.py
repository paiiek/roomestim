"""tests/web/test_archive.py — archive + provenance unit tests."""
from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from roomestim_web.archive import ArchiveArtefacts, build_result_archive
from roomestim_web.provenance import build_provenance_readme


@pytest.fixture
def fake_artefacts(tmp_path: Path) -> tuple[ArchiveArtefacts, str]:
    room_yaml = tmp_path / "room.yaml"
    room_yaml.write_text("schema_version: '0.1-draft'\nname: test\n")
    layout_yaml = tmp_path / "layout.yaml"
    layout_yaml.write_text("version: '1.0'\nname: test\n")
    pdf = tmp_path / "setup.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%fake\n")
    wav = tmp_path / "binaural.wav"
    wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfake")
    art = ArchiveArtefacts(
        room_yaml=room_yaml,
        layout_yaml=layout_yaml,
        setup_pdf=pdf,
        binaural_wav=wav,
        acoustic_report_json={"sabine_rt60_500hz_s": 0.5},
    )
    readme = build_provenance_readme(
        input_path="/tmp/fake.usdz",
        algorithm="vbap",
        n_speakers=8,
        layout_radius_m=2.0,
        el_deg=0.0,
        octave_band=True,
        roomestim_version="0.13.0",
        roomestim_web_version="0.12-web.0",
    )
    return art, readme


@pytest.mark.web
def test_archive_contains_6_files(fake_artefacts: tuple[ArchiveArtefacts, str], tmp_path: Path) -> None:
    art, readme = fake_artefacts
    zip_path = build_result_archive(art, readme, tmp_path / "out.zip")
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert names == {
        "room.yaml",
        "layout.yaml",
        "setup_card.pdf",
        "binaural_demo.wav",
        "acoustic_report.json",
        "README.txt",
    }


@pytest.mark.web
def test_archive_readme_lists_provenance(fake_artefacts: tuple[ArchiveArtefacts, str], tmp_path: Path) -> None:
    art, readme = fake_artefacts
    zip_path = build_result_archive(art, readme, tmp_path / "out.zip")
    with zipfile.ZipFile(zip_path) as zf:
        readme_text = zf.read("README.txt").decode("utf-8")
    assert "roomestim" in readme_text
    assert "0.13.0" in readme_text
    assert "0.12-web.0" in readme_text
    assert "vbap" in readme_text
    assert "HUTUBS" in readme_text or "HRTF" in readme_text


@pytest.mark.web
def test_archive_optional_files_excluded(tmp_path: Path) -> None:
    """ZIP without PDF / WAV / JSON contains only the mandatory entries."""
    room_yaml = tmp_path / "room.yaml"
    room_yaml.write_text("schema_version: '0.1-draft'\n")
    layout_yaml = tmp_path / "layout.yaml"
    layout_yaml.write_text("version: '1.0'\n")
    art = ArchiveArtefacts(
        room_yaml=room_yaml,
        layout_yaml=layout_yaml,
        setup_pdf=None,
        binaural_wav=None,
        acoustic_report_json=None,
    )
    readme = "Minimal provenance.\n"
    zip_path = build_result_archive(art, readme, tmp_path / "out.zip")
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert names == {"room.yaml", "layout.yaml", "README.txt"}
