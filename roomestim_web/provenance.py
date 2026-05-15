"""roomestim_web.provenance — build README.txt content for result ZIPs."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path


def build_provenance_readme(
    *,
    input_path: str | Path,
    algorithm: str,
    n_speakers: int,
    layout_radius_m: float,
    el_deg: float,
    octave_band: bool,
    roomestim_version: str,
    roomestim_web_version: str,
) -> str:
    """Return the README.txt contents (string) that goes inside the result ZIP.

    Includes:
      - timestamp (UTC ISO 8601)
      - input filename + SHA-256 of input file bytes (if file exists)
      - roomestim core version + roomestim_web version
      - algorithm + config knobs (n_speakers, radius, elevation, octave_band)
      - HRTF attribution (HUTUBS CC BY 4.0 + KEMAR PD) one-liner
      - Source audio attribution (LibriVox PD) one-liner
      - "See HRTF_ATTRIBUTION.md / SOURCE_ATTRIBUTION.md for full citations"
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    input_path = Path(input_path)
    filename = input_path.name

    # SHA-256 of input file (chunked to avoid large memory use)
    if input_path.exists():
        h = hashlib.sha256()
        with open(input_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        file_sha256 = h.hexdigest()
    else:
        file_sha256 = "unavailable (file not present at archive time)"

    lines = [
        "roomestim Result Bundle",
        "=" * 40,
        "",
        f"Generated:              {timestamp}",
        "",
        "Input",
        "-" * 20,
        f"Filename:               {filename}",
        f"SHA-256:                {file_sha256}",
        "",
        "Software Versions",
        "-" * 20,
        f"roomestim core:         {roomestim_version}",
        f"roomestim_web:          {roomestim_web_version}",
        "",
        "Configuration",
        "-" * 20,
        f"Algorithm:              {algorithm}",
        f"N speakers:             {n_speakers}",
        f"Layout radius (m):      {layout_radius_m}",
        f"Elevation (deg):        {el_deg}",
        f"Octave-band absorption: {octave_band}",
        "",
        "Attributions",
        "-" * 20,
        "HRTF: HUTUBS dataset (CC BY 4.0) + KEMAR (Public Domain).",
        "Source audio: LibriVox recordings (Public Domain).",
        "",
        "See HRTF_ATTRIBUTION.md / SOURCE_ATTRIBUTION.md for full citations.",
        "",
    ]
    return "\n".join(lines)
