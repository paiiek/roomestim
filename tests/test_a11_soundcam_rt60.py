"""v0.9 A11 boost — SoundCam synthesised RT60 substitute (default-lane).

Three default-lane tests, one per SoundCam room (lab, living_room,
conference). Each test:

1. Loads the synthesised fixture room from
   ``tests/fixtures/soundcam_synthesized/<room_id>/`` (dims.yaml + rt60.csv).
2. Computes the Sabine RT60 at 500 Hz from the synthesised geometry plus
   the per-room defensible material map recorded in ``dims.yaml``
   (rationale comment block).
3. Asserts ``|predicted - measured| / measured ≤ 0.20`` (±20 % tolerance).
   This is a HARD test, not a sensitivity-only bracket — if any room
   exceeds 20 %, the test FAILS.

Honesty marker: GT corners + RT60 derived from SoundCam paper-published
dimensions; live-mesh corner extraction is v0.10+ upgrade path. The
material map is the v0.9 substitute-driven defensible mapping recorded
in each ``dims.yaml`` rationale block; v0.10+ live-mesh-driven runs may
sharpen the mapping with measured-spectrum data.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from roomestim.model import MaterialLabel
from roomestim.reconstruct.materials import sabine_rt60

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "soundcam_synthesized"

# A11 substitute RT60 tolerance: ±20 % per v0.9 design §2.3 (matches A11
# acceptance gate framing in v0.1 P4).
RT60_REL_TOLERANCE: float = 0.20


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _load_dims(room_id: str) -> dict[str, object]:
    with (FIXTURE_ROOT / room_id / "dims.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_measured_rt60_500hz(room_id: str) -> float:
    """Read the measured RT60 at 500 Hz from rt60.csv."""
    with (FIXTURE_ROOT / room_id / "rt60.csv").open("r", encoding="utf-8") as fh:
        rows = [line for line in fh if line.strip() and not line.lstrip().startswith("#")]
    reader = csv.DictReader(rows)
    for row in reader:
        if int(row["band_hz"]) == 500:
            return float(row["measured_t60_s"])
    raise KeyError(f"no 500 Hz row in {room_id} rt60.csv")


def _surface_areas_from_dims(
    L: float, W: float, H: float,
    floor_label: MaterialLabel,
    walls_label: MaterialLabel,
    ceiling_label: MaterialLabel,
) -> dict[MaterialLabel, float]:
    """Return ``{material_label: area_m²}`` for an axis-aligned shoebox.

    Aggregates by material so duplicate labels (e.g., ceiling == floor) sum
    correctly into the Sabine integrand.
    """
    floor_area = L * W
    ceiling_area = L * W
    walls_area = 2.0 * (L + W) * H
    out: dict[MaterialLabel, float] = {}
    out[floor_label] = out.get(floor_label, 0.0) + floor_area
    out[ceiling_label] = out.get(ceiling_label, 0.0) + ceiling_area
    out[walls_label] = out.get(walls_label, 0.0) + walls_area
    return out


def _predict_rt60_500hz(room_id: str) -> tuple[float, float]:
    """Return ``(predicted_sabine_rt60_s, measured_rt60_s)`` at 500 Hz."""
    dims = _load_dims(room_id)
    L = float(dims["length_m"])
    W = float(dims["width_m"])
    H = float(dims["height_m"])
    floor_label = MaterialLabel(str(dims["floor_material"]))
    walls_label = MaterialLabel(str(dims["walls_material"]))
    ceiling_label = MaterialLabel(str(dims["ceiling_material"]))

    volume = L * W * H
    areas = _surface_areas_from_dims(L, W, H, floor_label, walls_label, ceiling_label)
    predicted = sabine_rt60(volume, areas)
    measured = _load_measured_rt60_500hz(room_id)
    return predicted, measured


def _assert_rt60_within_tolerance(room_id: str) -> None:
    predicted, measured = _predict_rt60_500hz(room_id)
    rel_err = abs(predicted - measured) / measured
    assert rel_err <= RT60_REL_TOLERANCE, (
        f"SoundCam {room_id} 500 Hz Sabine RT60 outside ±{RT60_REL_TOLERANCE*100:.0f} %: "
        f"predicted={predicted:.3f} s, measured={measured:.3f} s, "
        f"rel_err={rel_err*100:.1f} %"
    )


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_a11_soundcam_lab_rt60_within_20pct() -> None:
    """SoundCam lab — Sabine 500 Hz within ±20 % of measured RT60.

    Honesty marker: GT corners + RT60 derived from SoundCam paper-published
    dimensions; live-mesh corner extraction is v0.10+ upgrade path.
    """
    _assert_rt60_within_tolerance("lab")


def test_a11_soundcam_living_room_rt60_within_20pct() -> None:
    """SoundCam living_room — Sabine 500 Hz within ±20 % of measured RT60.

    Honesty marker: GT corners + RT60 derived from SoundCam paper-published
    dimensions; live-mesh corner extraction is v0.10+ upgrade path.
    """
    _assert_rt60_within_tolerance("living_room")


def test_a11_soundcam_conference_rt60_within_20pct() -> None:
    """SoundCam conference — Sabine 500 Hz within ±20 % of measured RT60.

    Honesty marker: GT corners + RT60 derived from SoundCam paper-published
    dimensions; live-mesh corner extraction is v0.10+ upgrade path.
    """
    _assert_rt60_within_tolerance("conference")
