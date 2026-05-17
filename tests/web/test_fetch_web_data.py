"""tests/web/test_fetch_web_data.py — fetch_web_data.py unit tests (v0.12-web.4)."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.web


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_download_file_atomic_and_sha256(tmp_path: Path) -> None:
    """_download_file writes atomically and sha256 helper returns correct digest."""
    from scripts.fetch_web_data import _download_file, _sha256

    fake_content = b"FAKE SOFA DATA" * 100
    expected_digest = _sha256_bytes(fake_content)

    def _fake_urlretrieve(url: str, dest: str, reporthook: object = None) -> tuple[str, object]:
        Path(dest).write_bytes(fake_content)
        return dest, {}

    dest = tmp_path / "kemar.sofa"
    with patch("urllib.request.urlretrieve", side_effect=_fake_urlretrieve):
        result = _download_file("https://fake.example/kemar.sofa", dest, desc="test")

    assert result == dest
    assert dest.exists()
    assert _sha256(dest) == expected_digest


def test_fetch_kemar_idempotent(tmp_path: Path) -> None:
    """fetch_kemar skips download if file already exists."""
    from scripts.fetch_web_data import fetch_kemar

    hrtf_dir = tmp_path / "hrtf"
    hrtf_dir.mkdir()
    existing = hrtf_dir / "kemar.sofa"
    existing.write_bytes(b"EXISTING")

    with patch("scripts.fetch_web_data._download_file") as mock_dl:
        result = fetch_kemar(hrtf_dir)
        mock_dl.assert_not_called()

    assert result == existing


def test_download_file_sha256_mismatch_raises_and_unlinks(tmp_path: Path) -> None:
    """_download_file raises RuntimeError and removes file on SHA-256 mismatch."""
    from scripts.fetch_web_data import _download_file

    fake_content = b"FAKE DATA"

    def _fake_urlretrieve(url: str, dest: str, reporthook: object = None) -> tuple[str, object]:
        Path(dest).write_bytes(fake_content)
        return dest, {}

    dest = tmp_path / "kemar.sofa"
    with patch("urllib.request.urlretrieve", side_effect=_fake_urlretrieve):
        with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
            _download_file(
                "https://fake.example/kemar.sofa",
                dest,
                expected_sha256="0000000000000000000000000000000000000000000000000000000000000000",
            )

    assert not dest.exists()


def test_fetch_kemar_passes_sha256_pin(tmp_path: Path) -> None:
    """fetch_kemar forwards KEMAR_SOFA_SHA256 to _download_file (OQ-27 pin landed)."""
    from scripts import fetch_web_data as fwd

    hrtf_dir = tmp_path / "hrtf"
    hrtf_dir.mkdir()
    # Ensure no existing file so the idempotent skip-branch doesn't fire
    with patch("scripts.fetch_web_data._download_file") as mock_dl, \
            patch("scripts.fetch_web_data._sha256", return_value=fwd.KEMAR_SOFA_SHA256):
        fwd.fetch_kemar(hrtf_dir)
        mock_dl.assert_called_once()
        _, kwargs = mock_dl.call_args
        assert kwargs.get("expected_sha256") == fwd.KEMAR_SOFA_SHA256, (
            f"Expected KEMAR pin to be forwarded, got kwargs={kwargs!r}"
        )


def test_extract_hutubs_finds_pp1(tmp_path: Path) -> None:
    """extract_hutubs extracts a pp1*.sofa from a zip archive."""
    from scripts.fetch_web_data import extract_hutubs

    # Build a fake HUTUBS zip with a pp1 entry
    zip_path = tmp_path / "hutubs.zip"
    fake_sofa_data = b"FAKE HUTUBS SOFA pp1"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("HUTUBS_HRTFs/pp1_HRIR_48kHz.sofa", fake_sofa_data)
        zf.writestr("HUTUBS_HRTFs/pp2_HRIR_48kHz.sofa", b"pp2 data")

    hrtf_dir = tmp_path / "hrtf"
    result = extract_hutubs(zip_path, hrtf_dir)

    assert result == hrtf_dir / "hutubs_pp1.sofa"
    assert result.read_bytes() == fake_sofa_data
