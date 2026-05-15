"""roomestim_web.archive — bundle result artefacts into a ZIP."""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArchiveArtefacts:
    """Files to include in the result ZIP."""

    room_yaml: Path
    layout_yaml: Path
    setup_pdf: Path | None  # may be None if reportlab unavailable
    binaural_wav: Path | None  # may be None if pyroomacoustics chain failed
    acoustic_report_json: dict[str, Any] | None  # serialized inline


def build_result_archive(
    artefacts: ArchiveArtefacts,
    readme_text: str,
    out_zip_path: str | Path,
) -> Path:
    """Bundle artefacts into a ZIP file. Returns the path.

    ZIP entries:
      - room.yaml (required)
      - layout.yaml (required)
      - setup_card.pdf (if setup_pdf is not None)
      - binaural_demo.wav (if binaural_wav is not None)
      - acoustic_report.json (if acoustic_report_json is not None)
      - README.txt (always; from readme_text)
    """
    out_zip_path = Path(out_zip_path)

    with zipfile.ZipFile(out_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(artefacts.room_yaml, "room.yaml")
        zf.write(artefacts.layout_yaml, "layout.yaml")

        if artefacts.setup_pdf is not None:
            zf.write(artefacts.setup_pdf, "setup_card.pdf")

        if artefacts.binaural_wav is not None:
            zf.write(artefacts.binaural_wav, "binaural_demo.wav")

        if artefacts.acoustic_report_json is not None:
            json_bytes = json.dumps(
                artefacts.acoustic_report_json, indent=2, ensure_ascii=False
            ).encode("utf-8")
            zf.writestr("acoustic_report.json", json_bytes)

        zf.writestr("README.txt", readme_text.encode("utf-8"))

    return out_zip_path
