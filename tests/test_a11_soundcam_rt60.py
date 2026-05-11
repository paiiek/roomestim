"""v0.11/v0.12 A11 — SoundCam paper-retrieved RT60 record (default-lane).

Three baseline tests covering lab + conference. v0.11 (ADR 0019) flipped
lab walls MISC_SOFT → MELAMINE_FOAM (α₅₀₀ = 0.85, planner-locked envelope
per Vorländer 2020 §11 / Appx A); §2.4 executor decision-point landed
sub-branch A — lab returns to A11 PASS-gate (rel_err ≈ +2.4 %; signature
`RECOVERED_under_melamine_foam_enum`). Conference byte-equal (no foam in
paper-faithful map); residual is a Sabine-shoebox approximation effect
(OQ-13b). v0.11 adds redundant structural-sign assertions on both tests
(OQ-13f). ACE A11 (gated E2E) unchanged. See ADR 0018 + ADR 0019.

v0.12 (ADR 0021) adds 2 NEW companion tests for the conference
characterising study: `test_a11_soundcam_conference_eyring_ratio_characterises`
records the Sabine/Eyring ratio (Eyring monotonicity guard via D9 / ADR 0009);
`test_a11_soundcam_conference_disagreement_classification` records the
§2.4 classification per ADR 0021 thresholds (Sabine-approximation effect
ratio > 1.15; coefficient-sourcing issue ratio < 1.10; ambiguous in
between). v0.12 executor decision-point: ratio ≈ 1.128 → AMBIGUOUS;
conference signature UNCHANGED at v0.12 per ADR 0021 §Decision.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from roomestim.model import MaterialAbsorption, MaterialLabel
from roomestim.reconstruct.materials import eyring_rt60

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
    # v0.12 ADR 0021: §2.4 executor decision-point output. Empirical ratio
    # sabine_predicted / eyring_predicted ≈ 1.128 landed in the ambiguous
    # [1.10, 1.15] zone → "ambiguous" classification. Signature unchanged
    # at v0.12 per ADR 0021 §Decision; mirror-image-source comparator
    # required at v0.13+ for further discrimination (OQ-15).
    "disagreement_classification": "ambiguous",
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


def _predict_conference_eyring() -> float:
    """Eyring RT60 on the same conference fixture (v0.12 ADR 0021 comparator).

    Uses the in-repo Eyring predictor (D9 / ADR 0009) with the same
    paper-faithful surface-area map as `_predict_conference()`. Eyring is
    parallel-predictor (Sabine remains default per D9). The runtime
    invariant `eyring ≤ sabine + 1e-9` (D9) guarantees ratio ≥ 1.0 strict
    in the high-absorption regime.
    """
    dims = _load_dims("conference")
    length = float(dims["length_m"])
    width = float(dims["width_m"])
    height = float(dims["height_m"])
    volume = length * width * height
    floor_a = ceiling_a = length * width
    walls_total = 2.0 * (length + width) * height
    glass_a = float(dims["walls_minority_area_m2"])
    drywall_a = walls_total - glass_a
    surface_areas = {
        MaterialLabel.CARPET: floor_a,
        MaterialLabel.CEILING_ACOUSTIC_TILE: ceiling_a,
        MaterialLabel.WALL_PAINTED: drywall_a,
        MaterialLabel.GLASS: glass_a,
    }
    return eyring_rt60(volume, surface_areas)


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


# --------------------------------------------------------------------------- #
# v0.12 ADR 0021 — Conference Sabine-shoebox residual characterising study
# --------------------------------------------------------------------------- #


def test_a11_soundcam_conference_eyring_ratio_characterises() -> None:
    """v0.12 (ADR 0021) — Eyring monotonicity guard + Sabine/Eyring ratio.

    Records the ratio sabine_predicted / eyring_predicted on the paper-faithful
    conference fixture using the in-repo Eyring predictor (D9 / ADR 0009).
    The Eyring monotonicity invariant `eyring ≤ sabine + 1e-9` guarantees
    `sabine_eyring_ratio > 1.0` strict in the high-absorption regime.
    The [1.0, 2.0] band brackets the physically plausible range (1.0 = no
    Sabine-approximation effect; 2.0 = extreme high-absorption regime;
    violation → predictor regression per §0.4 STOP rule #7).
    """
    sabine_predicted = _predict_conference()
    eyring_predicted = _predict_conference_eyring()
    sabine_eyring_ratio = sabine_predicted / eyring_predicted
    # Strict inequality guards against the §5.2 pre-mortem (artefactual
    # ratio = 1.0 from mis-passing the wrong input to either predictor).
    assert sabine_eyring_ratio > 1.0, (
        f"conference sabine_eyring_ratio = {sabine_eyring_ratio:.4f} "
        f"violates Eyring monotonicity invariant (D9 / ADR 0009); "
        f"sabine={sabine_predicted:.6f}, eyring={eyring_predicted:.6f}"
    )
    assert sabine_eyring_ratio < 2.0, (
        f"conference sabine_eyring_ratio = {sabine_eyring_ratio:.4f} "
        f"outside plausible [1.0, 2.0] band; §0.4 STOP rule #7 fires"
    )


def test_a11_soundcam_conference_disagreement_classification() -> None:
    """v0.12 (ADR 0021) — classification REGRESSION-GUARD per §2.4 decision-point.

    **What this test asserts** (regression-detection only):
      (a) `_CONFERENCE_EXPECTED["disagreement_classification"]` is one of
          the three planner-locked categories ("sabine_approximation_effect",
          "coefficient_sourcing_issue", "ambiguous");
      (b) the recorded value matches the empirical ratio under the
          planner-locked thresholds 1.10 / 1.15:
            - ratio > 1.15 → "sabine_approximation_effect"
            - ratio < 1.10 → "coefficient_sourcing_issue"
            - 1.10 ≤ ratio ≤ 1.15 → "ambiguous"

    **What this test does NOT assert** (correctness boundary):
    Threshold *correctness* is **NOT** validated here. The 1.10 / 1.15
    endpoints are planner-chosen heuristic bands (ADR 0021 §Decision
    "Threshold derivation"); they were committed to
    `.omc/plans/v0.12-design.md` §2.4 BEFORE the executor §2.4 measurement
    (audit-trail: planner-locked → AMBIGUOUS verdict is not sandbagged),
    but they are NOT physics-derived at v0.12. A v0.13+ successor ADR
    may revise the endpoints under Eyring-Taylor analysis or
    mirror-image-source comparator calibration (per OQ-15 path).

    **Failure mode this guard catches**: predictor refactor (Sabine OR
    Eyring) shifts the ratio enough to flip the classification → recorded
    `disagreement_classification` no longer matches empirical ratio →
    this test fails noisily, forcing the executor to update
    `_CONFERENCE_EXPECTED` + propagate to ADR 0021 §Status-update.

    **Failure mode this guard does NOT catch**: threshold endpoints
    themselves being wrong (governed by ADR 0021 §Decision; revisable
    only under successor ADR per §Reverse-criterion).
    """
    valid_classifications = {
        "sabine_approximation_effect",
        "coefficient_sourcing_issue",
        "ambiguous",
    }
    recorded = _CONFERENCE_EXPECTED["disagreement_classification"]
    assert recorded in valid_classifications, (
        f"conference disagreement_classification {recorded!r} not in "
        f"{sorted(valid_classifications)}"
    )
    # Cross-check: recorded classification matches empirical ratio at v0.12.
    sabine_predicted = _predict_conference()
    eyring_predicted = _predict_conference_eyring()
    sabine_eyring_ratio = sabine_predicted / eyring_predicted
    if sabine_eyring_ratio > 1.15:
        expected = "sabine_approximation_effect"
    elif sabine_eyring_ratio < 1.10:
        expected = "coefficient_sourcing_issue"
    else:
        expected = "ambiguous"
    assert recorded == expected, (
        f"conference classification drift: recorded {recorded!r} but "
        f"empirical ratio {sabine_eyring_ratio:.4f} maps to {expected!r}"
    )
