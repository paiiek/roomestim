"""v0.8 Scope-B — per-band ex-Building_Lobby MAE snapshot test (default-lane).

Two default-lane tests:

1. ``test_per_band_mae_ex_bl_matches_golden`` — recompute mean(|err|) over the
   6 ex-BL furniture-tracked rooms per band per predictor (Sabine + Eyring),
   assert against the frozen golden at
   ``tests/fixtures/golden/per_band_mae_ex_bl_2026-05-09.json`` within
   ±0.001 s. The golden values are derived once from the v0.6/v0.7-preserved
   `docs/perf_verification_e2e_2026-05-08.md` per-band tables (mean of the
   absolute |err| column over the 6 ex-BL rooms per band per predictor).
   Future predictor / adapter / per-band-table changes that shift any MAE
   force a one-line golden update + PR justification (per ADR 0015 §
   Consequences).

2. ``test_per_band_mae_golden_schema_invariant`` — schema invariants on the
   golden JSON (keys, lengths, Building_Lobby excluded, bands match
   ``OCTAVE_BANDS_HZ``, both predictors present).

The recomputation uses the in-tree measured-T60 fixture at
``tests/fixtures/ace_eaton_2016_table_i_measured_rt60.csv``. No env-gated
data path; default-lane only.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from roomestim.adapters.ace_challenge import (
    _build_room_model,
    _room_volume,
    _surface_areas_by_material,
    ACE_ROOM_GEOMETRY,
)
from roomestim.model import OCTAVE_BANDS_HZ
from roomestim.reconstruct.materials import (
    eyring_rt60_per_band,
    sabine_rt60_per_band,
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "golden" / "per_band_mae_ex_bl_2026-05-09.json"
)
MEASURED_RT60_CSV = (
    REPO_ROOT / "tests" / "fixtures" / "ace_eaton_2016_table_i_measured_rt60.csv"
)

EXCLUDED_ROOMS: tuple[str, ...] = ("Building_Lobby",)
EX_BL_ROOMS: tuple[str, ...] = (
    "Lecture_1",
    "Lecture_2",
    "Meeting_1",
    "Meeting_2",
    "Office_1",
    "Office_2",
)

MAE_TOLERANCE_S: float = 0.001


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _load_golden() -> dict:
    """Parse the JSON golden (raises on malformed JSON)."""
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _load_measured_rt60() -> dict[str, dict[int, float]]:
    """Parse the in-tree measured-T60 CSV → ``{room_id: {band_hz: t60_s}}``."""
    out: dict[str, dict[int, float]] = {}
    with MEASURED_RT60_CSV.open(newline="", encoding="utf-8") as fh:
        rows = [
            line
            for line in fh
            if line.strip() and not line.lstrip().startswith("#")
        ]
    reader = csv.DictReader(rows)
    for row in reader:
        room_id = row["room_id"].strip()
        band_hz = int(row["band_hz"].strip())
        t60_s = float(row["measured_t60_s"].strip())
        out.setdefault(room_id, {})[band_hz] = t60_s
    return out


def _recompute_per_band_mae() -> dict[str, dict[int, float]]:
    """In-process recomputation of per-band MAE over the 6 ex-BL rooms."""
    measured = _load_measured_rt60()
    sabine_errs: dict[int, list[float]] = {b: [] for b in OCTAVE_BANDS_HZ}
    eyring_errs: dict[int, list[float]] = {b: [] for b in OCTAVE_BANDS_HZ}
    # Sort the rooms explicitly to keep the accumulation deterministic.
    for room_id in sorted(EX_BL_ROOMS):
        if room_id in EXCLUDED_ROOMS:
            continue
        room = _build_room_model(room_id, ACE_ROOM_GEOMETRY[room_id])
        areas = _surface_areas_by_material(room)
        volume = _room_volume(room)
        sabine_pb = sabine_rt60_per_band(volume, areas)
        eyring_pb = eyring_rt60_per_band(volume, areas)
        for band in OCTAVE_BANDS_HZ:
            m = measured[room_id][band]
            sabine_errs[band].append(abs(sabine_pb[band] - m))
            eyring_errs[band].append(abs(eyring_pb[band] - m))
    out: dict[str, dict[int, float]] = {"sabine": {}, "eyring": {}}
    for band in OCTAVE_BANDS_HZ:
        out["sabine"][band] = sum(sabine_errs[band]) / len(sabine_errs[band])
        out["eyring"][band] = sum(eyring_errs[band]) / len(eyring_errs[band])
    return out


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_per_band_mae_ex_bl_matches_golden() -> None:
    """In-process MAE recomputation matches frozen golden within ±0.001 s.

    Tightening this tolerance below the v0.6 perf-doc display precision (3
    decimal places) would force spurious failures on minor floating-point
    drift; loosening it would let predictor/adapter/per-band-table changes
    pass silently. ±0.001 s is the sweet spot.
    """
    golden = _load_golden()
    recomputed = _recompute_per_band_mae()
    for predictor in ("sabine", "eyring"):
        for band in OCTAVE_BANDS_HZ:
            golden_v = golden["mae_per_band_s"][predictor][str(band)]
            actual_v = recomputed[predictor][band]
            delta = abs(actual_v - golden_v)
            assert delta <= MAE_TOLERANCE_S, (
                f"per-band MAE drift on {predictor}@{band}Hz: "
                f"recomputed {actual_v:.6f} s vs golden {golden_v:.3f} s "
                f"(|Δ|={delta:.6f} s > {MAE_TOLERANCE_S:.3f} s). "
                f"Update {GOLDEN_PATH.name} + add a PR justification per ADR 0015 §Consequences."
            )


def test_per_band_mae_golden_schema_invariant() -> None:
    """Schema invariants on the JSON golden (keys / lengths / values)."""
    golden = _load_golden()
    # Required top-level keys
    required_top = {
        "version",
        "source_doc",
        "excluded_rooms",
        "predictors",
        "bands_hz",
        "mae_per_band_s",
    }
    assert required_top.issubset(golden.keys()), (
        f"missing required top-level keys: {required_top - set(golden.keys())}"
    )
    # Building_Lobby must be in the exclusion list
    assert "Building_Lobby" in golden["excluded_rooms"]
    # Bands must equal OCTAVE_BANDS_HZ in order
    assert golden["bands_hz"] == list(OCTAVE_BANDS_HZ)
    # Both predictors present
    assert set(golden["predictors"]) == {"sabine", "eyring"}
    # mae_per_band_s shape
    mae = golden["mae_per_band_s"]
    assert set(mae.keys()) == {"sabine", "eyring"}
    for predictor in ("sabine", "eyring"):
        bands = mae[predictor]
        assert set(bands.keys()) == {str(b) for b in OCTAVE_BANDS_HZ}, (
            f"predictor {predictor!r} band keys mismatch: {sorted(bands.keys())} "
            f"vs expected {sorted(str(b) for b in OCTAVE_BANDS_HZ)}"
        )
        for band, mae_value in bands.items():
            assert isinstance(mae_value, (int, float))
            assert 0.0 <= mae_value < 60.0, (
                f"{predictor}@{band}Hz: implausible MAE {mae_value!r}"
            )
    # version + source_doc are non-empty strings
    assert isinstance(golden["version"], str) and golden["version"]
    assert isinstance(golden["source_doc"], str) and golden["source_doc"]
