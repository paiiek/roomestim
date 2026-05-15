"""fetch_web_data.py — Manual data-population protocol for roomestim-web.

This script does NOT perform any network requests. It prints the exact steps
required to populate the bundled data files that ship with the roomestim-web
binaural demo (HUTUBS SOFA, KEMAR SOFA, LibriVox source clip).

Run:
    python scripts/fetch_web_data.py

Then follow the printed instructions.
"""
from __future__ import annotations

HRTF_DIR = "roomestim_web/data/hrtf"
AUDIO_DIR = "roomestim_web/data/audio"

HUTUBS_URL = "https://depositonce.tu-berlin.de/handle/11303/9429"
KEMAR_URL = "https://sound.media.mit.edu/resources/KEMAR.html"
LIBRIVOX_URL = "<pending P13e data-bundle commit>"


def _separator() -> None:
    print("=" * 70)


def main() -> None:
    _separator()
    print("roomestim-web · data population protocol")
    print("(No files are downloaded by this script — manual steps only.)")
    _separator()

    print()
    print("STEP 1 — HUTUBS pp1 SOFA (CC BY 4.0, TU Berlin)")
    print(f"  URL   : {HUTUBS_URL}")
    print("  Action: Download the HUTUBS database archive, extract the SOFA")
    print("          file for subject 'pp1' (typically named something like")
    print("          'HRTF_Database_pp1.sofa' or similar), then place it at:")
    print(f"          {HRTF_DIR}/hutubs_pp1.sofa")
    print("  Citation required (CC BY 4.0):")
    print("    Brinkmann F. et al., 'The HUTUBS HRTF database',")
    print("    TU Berlin, 2019. DOI: 10.14279/depositonce-6?")
    print()

    print("STEP 2 — MIT KEMAR SOFA (Public Domain, fallback)")
    print(f"  URL   : {KEMAR_URL}")
    print("  Action: Download the KEMAR HRTF dataset in SOFA format.")
    print("          Several community-converted copies exist; search for")
    print("          'MIT KEMAR SOFA' on GitHub or sofaconventions.org.")
    print("          Place at:")
    print(f"          {HRTF_DIR}/kemar.sofa")
    print()

    print("STEP 3 — LibriVox source clip (Public Domain)")
    print(f"  URL   : {LIBRIVOX_URL}")
    print("  Action: Download any LibriVox MP3 chapter (public domain).")
    print("          Trim to 30 s mono 48 kHz 16-bit PCM using ffmpeg:")
    print()
    print("    ffmpeg -i <upstream_clip>.mp3 -ss 0 -t 30 \\")
    print("           -ar 48000 -ac 1 -sample_fmt s16 \\")
    print(f"           {AUDIO_DIR}/source.wav")
    print()

    print("STEP 4 — Record SHA-256 hashes")
    print("  After placing the files, run:")
    print("    sha256sum roomestim_web/data/hrtf/hutubs_pp1.sofa")
    print("    sha256sum roomestim_web/data/hrtf/kemar.sofa")
    print("    sha256sum roomestim_web/data/audio/source.wav")
    print("  Record the hashes in:")
    print("    roomestim_web/data/hrtf/HRTF_ATTRIBUTION.md")
    print("    roomestim_web/data/audio/SOURCE_ATTRIBUTION.md")
    print()

    print("STEP 5 — Run web tests to generate golden hash")
    print("    pytest -m web -v")
    print("  The golden binaural SHA-256 will be printed by the skipped test.")
    print("  Record it at: tests/web/golden/binaural_pp1_shoebox.sha256")
    _separator()


if __name__ == "__main__":
    main()
