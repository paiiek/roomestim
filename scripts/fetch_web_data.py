"""fetch_web_data.py — Data population script for roomestim-web (v0.12-web.4).

Downloads KEMAR SOFA (2.5 MB, CC BY 4.0) and LibriVox MP3 (12.9 MB, Public Domain),
then trims the audio to 30s mono 48kHz WAV using ffmpeg.

HUTUBS (1.36 GB zip) is NOT auto-downloaded; a manual guide is printed instead.

Usage:
    python scripts/fetch_web_data.py            # print guide only
    python scripts/fetch_web_data.py --auto     # download KEMAR + LibriVox (non-interactive)
    python scripts/fetch_web_data.py --download # same as --auto (explicit)
    python scripts/fetch_web_data.py --data-dir /path/to/data  # override data dir

Environment:
    ROOMESTIM_WEB_AUTO_FETCH=0   skip auto-download even with --auto (CI opt-out)
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


_LOG = logging.getLogger("fetch_web_data")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# URL constants (filled at v0.12-web.4; executor-verified)
# ---------------------------------------------------------------------------

KEMAR_SOFA_URL = "https://raw.githubusercontent.com/spatialaudio/lf-corrected-kemar-hrtfs/master/KEMAR_HRTFs_lfcorr.sofa"
LIBRIVOX_MP3_URL = "https://archive.org/download/stories_001_librivox/black_cat_poe_ty_64kb.mp3"
HUTUBS_ZIP_URL = "https://api-depositonce.tu-berlin.de/server/api/core/bitstreams/9f8b8874-c567-43fa-9085-eac010599a66/content"

# Default data directories (relative to repo root)
_DEFAULT_DATA_ROOT = Path("roomestim_web/data")
_HRTF_DIR_NAME = "hrtf"
_AUDIO_DIR_NAME = "audio"


# ---------------------------------------------------------------------------
# SHA-256 helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def _download_file(
    url: str,
    dest: Path,
    desc: str = "",
    expected_sha256: str | None = None,
) -> Path:
    """Download *url* to *dest* atomically (tmp + os.replace).

    Shows a simple progress counter. Idempotent if dest already exists.
    Uses a temporary file in the same directory for atomic rename.

    If *expected_sha256* is provided, verifies the digest after download.
    On mismatch the partial file is deleted and RuntimeError is raised.
    Pass ``expected_sha256=None`` to skip verification (logs a WARNING).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    label = desc or dest.name

    if expected_sha256 is None:
        _LOG.warning(
            "No SHA-256 pin for %s — integrity not verified (OQ-27).", dest.name
        )

    tmp_path = dest.parent / (dest.name + ".tmp")
    try:
        def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
            if total_size > 0:
                pct = min(100, block_num * block_size * 100 // total_size)
                print(f"\r  {label}: {pct}%", end="", flush=True)

        _LOG.info("Downloading %s → %s", url, dest)
        urllib.request.urlretrieve(url, tmp_path, reporthook=_reporthook)
        print()  # newline after progress

        if expected_sha256 is not None:
            actual = _sha256(tmp_path)
            if actual != expected_sha256:
                tmp_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"SHA-256 mismatch for {dest.name}: "
                    f"expected {expected_sha256}, got {actual}"
                )

        os.replace(tmp_path, dest)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    return dest


# ---------------------------------------------------------------------------
# KEMAR SOFA
# ---------------------------------------------------------------------------


def fetch_kemar(hrtf_dir: Path, *, force: bool = False) -> Path:
    """Download KEMAR SOFA to *hrtf_dir*/kemar.sofa.

    Returns path to the file. Skips if already present (idempotent) unless force=True.
    """
    dest = hrtf_dir / "kemar.sofa"
    if dest.exists() and not force:
        _LOG.info("KEMAR SOFA already present at %s — skipping.", dest)
        return dest
    _download_file(KEMAR_SOFA_URL, dest, desc="KEMAR SOFA (CC BY 4.0)")
    digest = _sha256(dest)
    _LOG.info("KEMAR SOFA SHA-256: %s", digest)
    return dest


# ---------------------------------------------------------------------------
# LibriVox + ffmpeg trim
# ---------------------------------------------------------------------------


def fetch_librivox(audio_dir: Path, *, force: bool = False) -> Path:
    """Download LibriVox MP3 and trim to 30s mono 48kHz WAV.

    Returns path to source.wav. Skips if already present unless force=True.
    Requires ffmpeg in PATH.
    """
    dest_wav = audio_dir / "source.wav"
    if dest_wav.exists() and not force:
        _LOG.info("source.wav already present at %s — skipping.", dest_wav)
        return dest_wav

    audio_dir.mkdir(parents=True, exist_ok=True)

    # Download MP3 to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_mp3 = Path(tmp.name)

    try:
        _download_file(LIBRIVOX_MP3_URL, tmp_mp3, desc="LibriVox MP3 (Public Domain)")

        # Trim with ffmpeg: skip 60s intro, take 30s, mono, 48kHz
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError(
                "ffmpeg not found in PATH. Install ffmpeg and retry, "
                "or manually place source.wav at roomestim_web/data/audio/source.wav"
            )

        dest_wav_tmp = audio_dir / "source.wav.tmp"
        try:
            cmd = [
                ffmpeg,
                "-y", "-i", str(tmp_mp3),
                "-ss", "60", "-t", "30",
                "-ac", "1", "-ar", "48000",
                "-sample_fmt", "s16",
                str(dest_wav_tmp),
            ]
            _LOG.info("Running: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed:\n{result.stderr}")
            os.replace(dest_wav_tmp, dest_wav)
        finally:
            if dest_wav_tmp.exists():
                dest_wav_tmp.unlink(missing_ok=True)
    finally:
        tmp_mp3.unlink(missing_ok=True)

    digest = _sha256(dest_wav)
    _LOG.info("source.wav SHA-256: %s", digest)
    return dest_wav


# ---------------------------------------------------------------------------
# HUTUBS manual guide
# ---------------------------------------------------------------------------


def print_hutubs_guide(hrtf_dir: Path) -> None:
    """Print manual HUTUBS download instructions."""
    sep = "=" * 70
    print(sep)
    print("HUTUBS HRTF Dataset — MANUAL DOWNLOAD REQUIRED (1.36 GB zip)")
    print(sep)
    print()
    print("  HUTUBS is not auto-downloaded because the full zip is 1.36 GB,")
    print("  which exceeds the HF Spaces cold-boot budget.")
    print()
    print("  1. Open in browser:")
    print(f"     {HUTUBS_ZIP_URL}")
    print()
    print("  2. Download the zip and run:")
    print("       python scripts/fetch_web_data.py --extract-hutubs /path/to/download.zip")
    print()
    print(f"  3. The pp1 SOFA will be placed at: {hrtf_dir}/hutubs_pp1.sofa")
    print()
    print("  Attribution (CC BY 4.0):")
    print("    Brinkmann F. et al., 'The HUTUBS HRTF database', TU Berlin, 2019.")
    print("    DOI: 10.14279/depositonce-9429")
    print(sep)


def extract_hutubs(zip_path: Path, hrtf_dir: Path) -> Path:
    """Extract hutubs pp1 SOFA from a locally-downloaded HUTUBS zip.

    Searches the zip for a file matching '*pp1*.sofa' (case-insensitive)
    and extracts it to hrtf_dir/hutubs_pp1.sofa.
    """
    hrtf_dir.mkdir(parents=True, exist_ok=True)
    dest = hrtf_dir / "hutubs_pp1.sofa"

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        candidates = [n for n in names if "pp1" in n.lower() and n.lower().endswith(".sofa")]
        if not candidates:
            raise ValueError(
                f"No pp1 SOFA found in {zip_path}. "
                f"Available .sofa files: {[n for n in names if n.lower().endswith('.sofa')][:10]}"
            )
        sofa_name = candidates[0]
        _LOG.info("Extracting %s → %s", sofa_name, dest)
        with zf.open(sofa_name) as src, open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)

    digest = _sha256(dest)
    _LOG.info("hutubs_pp1.sofa SHA-256: %s", digest)
    return dest


# ---------------------------------------------------------------------------
# Auto-fetch entry point (called from app.py background thread)
# ---------------------------------------------------------------------------


def auto_fetch(data_root: Path | None = None) -> None:
    """Non-interactive fetch of KEMAR + LibriVox.

    Respects ROOMESTIM_WEB_AUTO_FETCH=0 env opt-out.
    Silently swallows errors (background thread; must not crash the UI).
    """
    if os.environ.get("ROOMESTIM_WEB_AUTO_FETCH", "1") == "0":
        _LOG.info("ROOMESTIM_WEB_AUTO_FETCH=0; skipping auto-fetch.")
        return

    root = data_root or _DEFAULT_DATA_ROOT
    hrtf_dir = root / _HRTF_DIR_NAME
    audio_dir = root / _AUDIO_DIR_NAME

    try:
        kemar_dest = hrtf_dir / "kemar.sofa"
        if not kemar_dest.exists():
            _LOG.info("Auto-fetching KEMAR SOFA…")
            fetch_kemar(hrtf_dir)
    except Exception as exc:
        _LOG.warning("KEMAR auto-fetch failed: %s", exc)

    try:
        wav_dest = audio_dir / "source.wav"
        if not wav_dest.exists():
            _LOG.info("Auto-fetching LibriVox source clip…")
            fetch_librivox(audio_dir)
    except Exception as exc:
        _LOG.warning("LibriVox auto-fetch failed: %s", exc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _separator() -> None:
    print("=" * 70)


def _print_guide(hrtf_dir: Path, audio_dir: Path) -> None:
    _separator()
    print("roomestim-web · data population guide (v0.12-web.4)")
    _separator()
    print()
    print("AUTO-DOWNLOAD (KEMAR SOFA + LibriVox):")
    print("  python scripts/fetch_web_data.py --auto")
    print()
    print(f"  KEMAR SOFA  → {hrtf_dir}/kemar.sofa   (2.5 MB, CC BY 4.0)")
    print(f"  source.wav  → {audio_dir}/source.wav   (30s, 48kHz, mono)")
    print()
    print_hutubs_guide(hrtf_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch or guide data population for roomestim-web binaural demo."
    )
    parser.add_argument(
        "--auto", "--download",
        dest="download",
        action="store_true",
        help="Download KEMAR SOFA + LibriVox automatically (non-interactive).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override data root directory (default: roomestim_web/data).",
    )
    parser.add_argument(
        "--extract-hutubs",
        type=Path,
        metavar="ZIP_PATH",
        help="Extract hutubs_pp1.sofa from a locally-downloaded HUTUBS zip.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if files already exist.",
    )
    args = parser.parse_args(argv)

    root = args.data_dir or _DEFAULT_DATA_ROOT
    hrtf_dir = root / _HRTF_DIR_NAME
    audio_dir = root / _AUDIO_DIR_NAME

    if args.extract_hutubs:
        extract_hutubs(args.extract_hutubs, hrtf_dir)
        return 0

    if not args.download:
        _print_guide(hrtf_dir, audio_dir)
        return 0

    if os.environ.get("ROOMESTIM_WEB_AUTO_FETCH", "1") == "0":
        print("ROOMESTIM_WEB_AUTO_FETCH=0 — skipping download.")
        return 0

    errors: list[str] = []

    try:
        fetch_kemar(hrtf_dir, force=args.force)
        print(f"[OK] KEMAR SOFA → {hrtf_dir / 'kemar.sofa'}")
    except Exception as exc:
        errors.append(f"KEMAR: {exc}")
        print(f"[FAIL] KEMAR: {exc}", file=sys.stderr)

    try:
        fetch_librivox(audio_dir, force=args.force)
        print(f"[OK] source.wav → {audio_dir / 'source.wav'}")
    except Exception as exc:
        errors.append(f"LibriVox: {exc}")
        print(f"[FAIL] LibriVox: {exc}", file=sys.stderr)

    print()
    print_hutubs_guide(hrtf_dir)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
