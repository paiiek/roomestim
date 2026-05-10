"""v0.10 A11 — SoundCam paper-retrieved RT60 disagreement-record (default-lane).

Two default-lane tests, one per remaining SoundCam room (lab, conference).
v0.9.0 framing: 3 PASS-gate tests asserting predicted-vs-measured ≤ 20 %.
v0.10 framing: 2 disagreement-record tests asserting predicted-vs-measured
matches the recorded disagreement signature.

**v0.10 disclosure (REQUIRED reading)**:

v0.9.0 used placeholder RT60 values (0.35 / 0.45 / 0.55 s — chosen so the
default-enum Sabine prediction passed ±20 %). v0.10 replaces those with
paper-retrieved Schroeder broadband means (0.158 / N/A / 0.581 s — paper
does not publish living_room dims so that room is removed). Under
paper-faithful material maps + the existing 9-entry MaterialLabel enum:

- **lab**: predicted (Sabine, 500 Hz, default enum max α_avg ≈ 0.46) =
  0.254 s; measured (paper Table 7 broadband) = 0.158 s; rel-err ≈ +60 %.
  Default enum SYSTEMATICALLY OVER-PREDICTS treated-room RT60 because
  it cannot represent NRC 1.26 melamine foam / NRC 1.0 fiberglass
  treatment. v0.11+ candidate: add MELAMINE_FOAM + FIBERGLASS_CEILING
  enums (OQ-13a). v0.10 records this disagreement; does NOT pretend
  it is within ±20 %.

- **conference**: predicted (Sabine, 500 Hz, paper-faithful material
  map = carpet + 3 drywall + 1 glass + ceiling tiles) = 0.449 s;
  measured (paper Table 7 broadband) = 0.581 s; rel-err ≈ -22.7 %.
  Just outside ±20 % gate. Default enum REPRESENTS paper materials
  adequately; the residual is a Sabine-shoebox-approximation effect
  (single glass wall under-counted). v0.11+ candidate: glass-heavy-room
  residual study (OQ-13b). v0.10 records this disagreement; does NOT
  pretend it is within ±20 %.

The unit mismatch (Sabine 500 Hz prediction vs paper Schroeder broadband
measurement) is itself recorded as part of the disagreement signature.
v0.10 makes this mismatch explicit; v0.11+ may sharpen it via per-band
prediction + Figure 10 graph-reading reconciliation.

ACE A11 corpus (gated E2E) is unchanged — substitute disagreement does
NOT invalidate ACE evidence; it bounds the SUBSTITUTE's reach.

See ADR 0018 + OQ-13a/b for full disagreement-record + remediation plan.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from roomestim.model import MaterialAbsorption, MaterialLabel

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "soundcam_synthesized"

# Per-room expected disagreement signature (v0.10 honesty correction).
# These values are deliberately RECORDED, not asserted-equal — the test
# checks predicted-vs-measured falls in the recorded-disagreement BAND
# (~±5 % around the recorded signature) so any silent enum/coefficient
# drift will trip the test. See ADR 0018 + OQ-13a/b.
_LAB_EXPECTED = {
    "predicted_s_min": 0.235,
    "predicted_s_max": 0.270,  # ~0.254 s ± ~5%
    "measured_s": 0.158,
    "rel_err_min": 0.45,
    "rel_err_max": 0.70,  # +60% ± window
    "disagreement_signature": "default_enum_underrepresents_treated_room_absorption",
}
_CONFERENCE_EXPECTED = {
    "predicted_s_min": 0.430,
    "predicted_s_max": 0.470,  # ~0.449 s ± ~5%
    "measured_s": 0.581,
    "rel_err_min": -0.27,
    "rel_err_max": -0.18,  # -22.7% window
    "disagreement_signature": "sabine_shoebox_underestimates_glass_wall_specular",
}


def _load_dims(room_id: str) -> dict[str, object]:
    with (FIXTURE_ROOT / room_id / "dims.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_measured_rt60_broadband(room_id: str) -> float:
    with (FIXTURE_ROOT / room_id / "rt60.csv").open("r", encoding="utf-8") as fh:
        rows = [line for line in fh if line.strip() and not line.lstrip().startswith("#")]
    reader = csv.DictReader(rows)
    for row in reader:
        if row["band_label"] == "broadband":
            return float(row["measured_t60_s"])
    raise KeyError(f"no broadband row in {room_id} rt60.csv")


def _predict_lab() -> float:
    """Lab: paper material map cannot be represented — use best-achievable
    default-enum proxy (carpet floor + misc_soft walls + ceiling_acoustic_tile).
    """
    dims = _load_dims("lab")
    length = float(dims["length_m"])
    width = float(dims["width_m"])
    height = float(dims["height_m"])
    volume = length * width * height
    floor_a = ceiling_a = length * width
    walls_a = 2.0 * (length + width) * height
    absorption = (
        floor_a * MaterialAbsorption[MaterialLabel.CARPET]
        + ceiling_a * MaterialAbsorption[MaterialLabel.CEILING_ACOUSTIC_TILE]
        + walls_a * MaterialAbsorption[MaterialLabel.MISC_SOFT]
    )
    return 0.161 * volume / absorption


def _predict_conference() -> float:
    """Conference: paper-faithful material map (carpet + 3 drywall + 1 glass + tiles)."""
    dims = _load_dims("conference")
    length = float(dims["length_m"])
    width = float(dims["width_m"])
    height = float(dims["height_m"])
    volume = length * width * height
    floor_a = ceiling_a = length * width
    walls_total = 2.0 * (length + width) * height
    # Glass wall area = 8.91 m² (3.3 × 2.7 short wall) — paper does not specify which wall
    # is glass; see conference/dims.yaml material_rationale.
    glass_a = float(dims["walls_minority_area_m2"])
    drywall_a = walls_total - glass_a
    absorption = (
        floor_a * MaterialAbsorption[MaterialLabel.CARPET]
        + ceiling_a * MaterialAbsorption[MaterialLabel.CEILING_ACOUSTIC_TILE]
        + drywall_a * MaterialAbsorption[MaterialLabel.WALL_PAINTED]
        + glass_a * MaterialAbsorption[MaterialLabel.GLASS]
    )
    return 0.161 * volume / absorption


def test_a11_soundcam_lab_disagreement_record() -> None:
    """Lab disagreement-record: default enum cannot represent treated-room.

    v0.10 disclosure: this test EXPECTS the prediction to fail ±20% by
    a recorded margin. See ADR 0018 + OQ-13a.
    """
    predicted = _predict_lab()
    measured = _load_measured_rt60_broadband("lab")
    rel_err = (predicted - measured) / measured
    assert _LAB_EXPECTED["predicted_s_min"] <= predicted <= _LAB_EXPECTED["predicted_s_max"], (
        f"lab predicted {predicted:.3f} s outside expected disagreement band "
        f"[{_LAB_EXPECTED['predicted_s_min']:.3f}, {_LAB_EXPECTED['predicted_s_max']:.3f}]"
    )
    assert abs(measured - _LAB_EXPECTED["measured_s"]) < 1e-6, (
        f"lab measured {measured} drift from paper-retrieved {_LAB_EXPECTED['measured_s']}"
    )
    assert _LAB_EXPECTED["rel_err_min"] <= rel_err <= _LAB_EXPECTED["rel_err_max"], (
        f"lab rel_err {rel_err*100:+.1f}% outside expected disagreement signature "
        f"[{_LAB_EXPECTED['rel_err_min']*100:+.0f}%, {_LAB_EXPECTED['rel_err_max']*100:+.0f}%] "
        f"({_LAB_EXPECTED['disagreement_signature']})"
    )


def test_a11_soundcam_conference_disagreement_record() -> None:
    """Conference disagreement-record: Sabine + paper materials misses ±20% by ~3pp.

    v0.10 disclosure: this test EXPECTS the prediction to fail ±20% by a
    recorded ~22.7% margin. See ADR 0018 + OQ-13b.
    """
    predicted = _predict_conference()
    measured = _load_measured_rt60_broadband("conference")
    rel_err = (predicted - measured) / measured
    assert (
        _CONFERENCE_EXPECTED["predicted_s_min"]
        <= predicted
        <= _CONFERENCE_EXPECTED["predicted_s_max"]
    ), (
        f"conference predicted {predicted:.3f} s outside expected band "
        f"[{_CONFERENCE_EXPECTED['predicted_s_min']:.3f}, "
        f"{_CONFERENCE_EXPECTED['predicted_s_max']:.3f}]"
    )
    assert abs(measured - _CONFERENCE_EXPECTED["measured_s"]) < 1e-6
    assert (
        _CONFERENCE_EXPECTED["rel_err_min"] <= rel_err <= _CONFERENCE_EXPECTED["rel_err_max"]
    ), (
        f"conference rel_err {rel_err*100:+.1f}% outside expected disagreement signature "
        f"[{_CONFERENCE_EXPECTED['rel_err_min']*100:+.0f}%, "
        f"{_CONFERENCE_EXPECTED['rel_err_max']*100:+.0f}%] "
        f"({_CONFERENCE_EXPECTED['disagreement_signature']})"
    )
