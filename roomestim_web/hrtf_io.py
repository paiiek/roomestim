"""roomestim_web.hrtf_io — HRTF SOFA loader and nearest-direction lookup.

Loads HUTUBS or MIT KEMAR SOFA files via pysofaconventions (lazy import),
resamples 44100 → 48000 Hz, and provides great-circle nearest-neighbour
direction lookup for the binaural renderer.

pysofaconventions is optional at import time; it is imported lazily inside
load_hutubs() and load_kemar(). Tests that exercise real SOFA files must
guard with pytest.importorskip("pysofaconventions").
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Data root
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent / "data"
_HRTF_DIR = _DATA_DIR / "hrtf"


# ---------------------------------------------------------------------------
# HrtfTable
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HrtfTable:
    """HRIR table at a fixed sample rate.

    Attributes:
        sample_rate_hz: int (always 48000 after resampling).
        directions: np.ndarray, shape (M, 2) — columns (az_deg, el_deg) in
            SOFA spherical convention (az 0..360 CCW from front, el -90..+90).
        hrirs_left:  np.ndarray, shape (M, N) — left-ear HRIRs (N samples per).
        hrirs_right: np.ndarray, shape (M, N) — right-ear HRIRs.
        attribution: str — short cite string for UI footer.
    """

    sample_rate_hz: int
    directions: np.ndarray
    hrirs_left: np.ndarray
    hrirs_right: np.ndarray
    attribution: str


# ---------------------------------------------------------------------------
# Resampling helper
# ---------------------------------------------------------------------------


def _resample_44100_to_48000(hrirs: np.ndarray) -> np.ndarray:
    """Resample HRIRs from 44100 → 48000 Hz along the last axis.

    Uses scipy.signal.resample_poly with (up=160, down=147):
        44100 × 160 / 147 = 48000.0 exactly.

    Args:
        hrirs: shape (M, N_44100).

    Returns:
        shape (M, N_48000).
    """
    from scipy.signal import resample_poly  # type: ignore[import-untyped]

    result: np.ndarray = resample_poly(hrirs, up=160, down=147, axis=-1)
    return result


# ---------------------------------------------------------------------------
# SOFA loading helpers
# ---------------------------------------------------------------------------


def _load_sofa(path: Path, attribution: str, src_sr: int = 44100) -> HrtfTable:
    """Core SOFA loader shared by load_hutubs and load_kemar.

    Reads Data.IR (M × R × N) and SourcePosition (M × 3, az/el/radius).
    R=0 → left ear, R=1 → right ear.
    Resamples if src_sr != 48000.
    """
    try:
        from pysofaconventions import SOFAFile  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "pysofaconventions is required to load SOFA files. "
            "Install it with: pip install pysofaconventions"
        ) from exc

    sofa = SOFAFile(str(path), "r")
    try:
        # Data.IR shape: (M, R, N) — M measurements, R=2 ears, N samples
        ir_data: np.ndarray = np.array(sofa.getDataIR())  # (M, R, N)
        # SourcePosition shape: (M, 3) — az_deg, el_deg, radius_m
        src_pos: np.ndarray = np.array(sofa.getVariableValue("SourcePosition"))  # (M, 3)
    finally:
        sofa.close()

    hrirs_left: np.ndarray = ir_data[:, 0, :]   # (M, N)
    hrirs_right: np.ndarray = ir_data[:, 1, :]  # (M, N)
    directions: np.ndarray = src_pos[:, :2]      # (M, 2) — az, el

    if src_sr != 48000:
        hrirs_left = _resample_44100_to_48000(hrirs_left)
        hrirs_right = _resample_44100_to_48000(hrirs_right)

    return HrtfTable(
        sample_rate_hz=48000,
        directions=directions,
        hrirs_left=hrirs_left,
        hrirs_right=hrirs_right,
        attribution=attribution,
    )


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def load_hutubs(subject_id: str = "pp1") -> HrtfTable:
    """Load a HUTUBS subject SOFA file and resample 44100 → 48000 Hz.

    Path: roomestim_web/data/hrtf/hutubs_{subject_id}.sofa
    Lazy-imports pysofaconventions. Raises FileNotFoundError if the SOFA
    file is missing (let the caller decide whether to fall back).
    """
    sofa_path = _HRTF_DIR / f"hutubs_{subject_id}.sofa"
    if not sofa_path.exists():
        raise FileNotFoundError(
            f"HUTUBS SOFA file not found: {sofa_path}\n"
            "Run 'python scripts/fetch_web_data.py' for the download protocol."
        )
    return _load_sofa(
        sofa_path,
        attribution="HUTUBS HRTF DB (TU Berlin, CC BY 4.0) — Brinkmann et al. 2019",
        src_sr=44100,
    )


def load_kemar() -> HrtfTable:
    """Load the MIT KEMAR fallback SOFA (Public Domain). 44100 → 48000 Hz."""
    sofa_path = _HRTF_DIR / "kemar.sofa"
    if not sofa_path.exists():
        raise FileNotFoundError(
            f"KEMAR SOFA file not found: {sofa_path}\n"
            "Run 'python scripts/fetch_web_data.py' for the download protocol."
        )
    return _load_sofa(
        sofa_path,
        attribution="MIT KEMAR HRTF (Gardner & Martin 1994, Public Domain)",
        src_sr=44100,
    )


def load_default_hrtf() -> HrtfTable:
    """Try HUTUBS pp1; on FileNotFoundError, fall back to KEMAR.

    On second failure, raises FileNotFoundError with a clear message.
    """
    try:
        return load_hutubs("pp1")
    except FileNotFoundError:
        pass
    try:
        return load_kemar()
    except FileNotFoundError:
        raise FileNotFoundError(
            "Neither HUTUBS pp1 nor KEMAR SOFA files are present.\n"
            "Run 'python scripts/fetch_web_data.py' for the download protocol.\n"
            "Expected paths:\n"
            f"  {_HRTF_DIR / 'hutubs_pp1.sofa'}\n"
            f"  {_HRTF_DIR / 'kemar.sofa'}"
        )


# ---------------------------------------------------------------------------
# Nearest-direction lookup
# ---------------------------------------------------------------------------


def _great_circle_distance(
    az1_deg: float,
    el1_deg: float,
    az2_arr: np.ndarray,
    el2_arr: np.ndarray,
) -> np.ndarray:
    """Vectorised great-circle distance between (az1, el1) and each (az2, el2).

    All angles in degrees. Returns array of distances in radians.
    """
    az1 = math.radians(az1_deg)
    el1 = math.radians(el1_deg)
    az2 = np.radians(az2_arr)
    el2 = np.radians(el2_arr)

    # Convert spherical → unit Cartesian
    x1 = math.cos(el1) * math.cos(az1)
    y1 = math.cos(el1) * math.sin(az1)
    z1 = math.sin(el1)

    x2 = np.cos(el2) * np.cos(az2)
    y2 = np.cos(el2) * np.sin(az2)
    z2 = np.sin(el2)

    dot = np.clip(x1 * x2 + y1 * y2 + z1 * z2, -1.0, 1.0)
    arccos: np.ndarray = np.arccos(dot)
    return arccos


def nearest_hrir(
    table: HrtfTable, az_deg: float, el_deg: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return (left_hrir, right_hrir) for the closest direction by great-circle
    distance. Wraps azimuth to [0, 360).
    """
    az_deg = az_deg % 360.0
    dists = _great_circle_distance(
        az_deg, el_deg, table.directions[:, 0], table.directions[:, 1]
    )
    idx = int(np.argmin(dists))
    return table.hrirs_left[idx], table.hrirs_right[idx]
