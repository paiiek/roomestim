"""v0.11 A11 — SoundCam paper-retrieved RT60 record (default-lane).

Three tests covering lab + conference. v0.11 (ADR 0019) flips lab walls
MISC_SOFT → MELAMINE_FOAM (α₅₀₀ = 0.85, planner-locked envelope per
Vorländer 2020 §11 / Appx A); §2.4 executor decision-point landed
sub-branch A — lab returns to A11 PASS-gate (rel_err ≈ +2.4 %; signature
`RECOVERED_under_melamine_foam_enum`). Conference byte-equal (no foam in
paper-faithful map); residual is a Sabine-shoebox approximation effect
(OQ-13b). v0.11 adds redundant structural-sign assertions on both tests
(OQ-13f). ACE A11 (gated E2E) unchanged. See ADR 0018 + ADR 0019.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from roomestim.model import MaterialAbsorption, MaterialLabel

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "soundcam_synthesized"

# Per-room expected band (v0.11: lab returns to A11 PASS-gate under
# MELAMINE_FOAM (sub-branch A); conference preserved as disagreement-record).
# Values are deliberately RECORDED, not asserted-equal — the tests check
# predicted-vs-measured falls in the recorded BAND (~±5 % around the
# observed predicted value) so any silent enum/coefficient drift trips the
# test. See ADR 0018 + ADR 0019 + OQ-13a/f.
_LAB_EXPECTED = {
    "predicted_s_min": 0.150,
    "predicted_s_max": 0.175,  # ~0.162 s ± ~8% under MELAMINE_FOAM walls
    "measured_s": 0.158,
    "rel_err_min": -0.20,
    "rel_err_max": 0.20,  # A11 ±20% PASS-gate recovered at v0.11 (ADR 0019)
    "disagreement_signature": "RECOVERED_under_melamine_foam_enum",
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
    """v0.11 paper-faithful: walls = MELAMINE_FOAM (ADR 0019); floor = CARPET;
    ceiling = CEILING_ACOUSTIC_TILE (FIBERGLASS_CEILING deferred to OQ-14)."""
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
        + walls_a * MaterialAbsorption[MaterialLabel.MELAMINE_FOAM]
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


def test_a11_soundcam_lab_band_record() -> None:
    """v0.11 sub-branch A (PASS-gate recovered) — renamed from disagreement_record.

    Redundant `assert rel_err < 0.20` guards against silent regression. See ADR 0019.
    """
    predicted = _predict_lab()
    measured = _load_measured_rt60_broadband("lab")
    rel_err = (predicted - measured) / measured
    assert _LAB_EXPECTED["predicted_s_min"] <= predicted <= _LAB_EXPECTED["predicted_s_max"], (
        f"lab predicted {predicted:.3f} s outside expected band "
        f"[{_LAB_EXPECTED['predicted_s_min']:.3f}, {_LAB_EXPECTED['predicted_s_max']:.3f}]"
    )
    assert abs(measured - _LAB_EXPECTED["measured_s"]) < 1e-6, (
        f"lab measured {measured} drift from paper-retrieved {_LAB_EXPECTED['measured_s']}"
    )
    assert _LAB_EXPECTED["rel_err_min"] <= rel_err <= _LAB_EXPECTED["rel_err_max"], (
        f"lab rel_err {rel_err*100:+.1f}% outside expected band "
        f"[{_LAB_EXPECTED['rel_err_min']*100:+.0f}%, {_LAB_EXPECTED['rel_err_max']*100:+.0f}%] "
        f"({_LAB_EXPECTED['disagreement_signature']})"
    )
    # v0.11 redundant structural-sign assertion (sub-branch A PASS-gate).
    assert rel_err < 0.20, (
        f"lab rel_err {rel_err*100:+.1f}% > +20% PASS-gate (ADR 0019)"
    )


def test_a11_soundcam_lab_pass_gate_recovered() -> None:
    """v0.11 NEW (ADR 0019): named-companion recording the lab regime change
    (disagreement-record → PASS-gate). Any re-opening of the gap is loud."""
    predicted = _predict_lab()
    measured = _load_measured_rt60_broadband("lab")
    rel_err = (predicted - measured) / measured
    assert -0.20 <= rel_err <= 0.20, (
        f"lab PASS-gate regression (ADR 0019): rel_err {rel_err*100:+.1f}% "
        f"outside ±20%; predicted {predicted:.3f} s vs measured {measured:.3f} s."
    )


def test_a11_soundcam_conference_disagreement_record() -> None:
    """Conference: Sabine + paper materials miss ±20% by ~3pp (rel_err ≈ -22.7%).

    v0.11 byte-equal (no foam in paper map) + adds `assert rel_err < -0.10`
    per OQ-13f. See ADR 0018 + OQ-13b."""
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
    # v0.11 redundant structural-sign assertion (OQ-13f conference branch).
    assert rel_err < -0.10, (
        f"conference rel_err {rel_err*100:+.1f}% > -10% (OQ-13f; ADR 0018)"
    )
