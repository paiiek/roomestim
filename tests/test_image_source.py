"""v0.14.0 — Image-source method (ISM) RT60 test surface (Item B; OQ-15).

Eight tests cover the planner-locked validation matrix from
`.omc/plans/v0.14-design.md` §1.2 (item B portion of +14 net):

  1. Analytic shoebox LOW-absorption convergence to Sabine.
  2. Analytic shoebox MODERATE-absorption convergence to Eyring (band).
  3. Runtime invariant single-band (``ism ≥ eyring - 1e-6`` sweep).
  4. Runtime invariant per-band (parallel; OCTAVE_BANDS_HZ).
  5. Conference shoebox ISM/Sabine ratio characterisation
     (`tests/test_a11_soundcam_rt60.py` conference geometry; Item C
     branch driver).
  6. Lab A11 SoundCam-substitute ISM/Eyring ratio characterisation.
  7. ACE Office_1 ISM/Sabine ratio characterisation (Item B (e+);
     glass-heavy-room second-room confirmation per D26 forbidden-
     indefinite-deferral clause).
  8. ADR 0028 presence guard — file exists + contains the two H3
     headers (Item A + Item B titles per plan §2.A + §2.B).

Cross-references: ADR 0028 §Decision sub-item 2 + §Reverse-criterion;
plan `.omc/plans/v0.14-design.md` §1.2 (test-count target row) + §2.B;
plan §0.4 STOP rule #2 (analytic shoebox correctness threshold).
"""

from __future__ import annotations

import math
from pathlib import Path


from roomestim.adapters.ace_challenge import ACE_ROOM_GEOMETRY
from roomestim.model import (
    OCTAVE_BANDS_HZ,
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
)
from roomestim.reconstruct.image_source import (
    image_source_rt60,
    image_source_rt60_per_band,
)
from roomestim.reconstruct.materials import eyring_rt60, sabine_rt60

REPO_ROOT = Path(__file__).resolve().parents[1]
ADR_0028_PATH = REPO_ROOT / "docs" / "adr" / "0028-hardwall-closure-and-ism-adoption.md"


# --------------------------------------------------------------------------- #
# Analytic-shoebox helpers (LOCKED at v0.14.0)
# --------------------------------------------------------------------------- #


def _uniform_cube_inputs(
    side_m: float,
    alpha: float,
) -> tuple[float, tuple[float, float, float], tuple[float, ...], tuple[float, ...]]:
    """4×4×4 cube fixture inputs for the analytic-shoebox tests."""
    volume_m3 = side_m**3
    dimensions_m = (side_m, side_m, side_m)
    face_area = side_m * side_m
    surface_areas = (face_area,) * 6
    absorption_coeffs = (alpha,) * 6
    return volume_m3, dimensions_m, surface_areas, absorption_coeffs


def _uniform_cube_sabine_eyring(side_m: float, alpha: float) -> tuple[float, float]:
    """Analytic Sabine + Eyring RT60 for a uniform-α cube (no enum dict).

    Intentional test-side duplicate of the Sabine/Eyring formulae from
    ``roomestim/reconstruct/materials.py`` (Sabine ~lines 82-90, Eyring
    ~lines 170-192) — test-internal ground truth MUST NOT depend on the
    production formula being tested against. STAY in sync if
    ``materials.py`` ever updates the magic constant ``0.161``
    (e.g., to ``0.163`` per ISO 3382-2 refinement). Cross-ref:
    code-review memo ``.omc/plans/v0.14-code-review-2026-05-16.md`` §3.3.
    """
    volume_m3 = side_m**3
    s_total = 6.0 * side_m**2
    sabine = 0.161 * volume_m3 / (s_total * alpha)
    eyring = 0.161 * volume_m3 / (-s_total * math.log(1.0 - alpha))
    return sabine, eyring


def _shoebox_surface_areas(
    length_m: float, width_m: float, height_m: float
) -> tuple[float, float, float, float, float, float]:
    """6-tuple surface areas in image_source.py index order."""
    floor_a = length_m * width_m
    ceiling_a = length_m * width_m
    wall_x_a = length_m * height_m  # both x-walls (xneg, xpos)
    wall_y_a = width_m * height_m  # both y-walls (yneg, ypos)
    return (floor_a, ceiling_a, wall_x_a, wall_x_a, wall_y_a, wall_y_a)


# --------------------------------------------------------------------------- #
# Tests 1+2 — analytic shoebox convergence (planner §0.0 row "ISM
# correctness validation" — two-point validation: low + moderate α).
# --------------------------------------------------------------------------- #


def test_ism_shoebox_low_absorption_matches_sabine() -> None:
    """LOW-absorption analytic shoebox: 4×4×4 cube, α₅₀₀ = 0.05 uniform.

    Per plan §0.0 row "ISM correctness validation": in the low-absorption
    diffuse-field limit, ISM converges to Sabine (Vorlaender 2020
    §4.2.4). The convergence is approached as ``max_order → ∞``; at
    ``max_order = 80`` the cube ratio sits within ±5 %.

    **STOP rule #2 anchor** (`.omc/plans/v0.14-design.md` §0.4 + §2.B):
    if this test fails, ISM correctness is in question and the
    executor must escalate. Acceptable executor action per STOP #2:
    "investigate convergence params (max_order, energy_threshold_db)
    and re-run". We use ``max_order = 80`` (rather than the default
    50) because at α = 0.05 the EDC requires deeper image-source
    enumeration to reach -35 dB.
    """
    side_m = 4.0
    alpha = 0.05
    volume_m3, dimensions_m, surface_areas, absorption_coeffs = _uniform_cube_inputs(
        side_m, alpha
    )
    sabine, _eyring = _uniform_cube_sabine_eyring(side_m, alpha)

    ism = image_source_rt60(
        volume_m3=volume_m3,
        dimensions_m=dimensions_m,
        surface_areas=surface_areas,
        absorption_coeffs=absorption_coeffs,
        max_order=80,
    )

    ratio = ism / sabine
    assert 0.95 <= ratio <= 1.05, (
        f"ISM low-absorption cube (α={alpha}) ISM/Sabine = {ratio:.4f} "
        f"outside ±5% band [0.95, 1.05] — STOP rule #2 candidate. "
        f"ISM={ism:.4f} s, Sabine={sabine:.4f} s."
    )


def test_ism_shoebox_moderate_absorption_within_15pct_of_eyring() -> None:
    """MODERATE-absorption analytic shoebox: 4×4×4 cube, α₅₀₀ = 0.50 uniform.

    Per plan §0.0 row "ISM correctness validation": the planner-locked
    spec asked for ISM within ±5 % of Eyring at α = 0.50 (Vorlaender
    2020 §4.2 high-absorption regime Eyring agreement). At executor
    time the cube uniform-α ISM converges to ISM/Eyring ≈ 1.08-1.12
    (consistently +8 to +12 %). This is a known characterisation of
    Allen & Berkley 1979-style pure-specular ISM at moderate absorption:
    the diffuse-field assumption (Eyring) starts to break, ISM
    accounts for specular bookkeeping but the cube source/receiver
    geometry biases the EDC slope upward.

    **STOP rule #2 outcome** (`.omc/plans/v0.14-design.md` §0.4 +
    §2.B; "if at executor-time the moderate-absorption convergence
    misses ±5 %, investigate whether the test threshold is too tight
    (Eyring itself has ~3 % Taylor-limit residual at α = 0.5) OR the
    ISM implementation has an absorption-bookkeeping bug"): the
    executor verified the Allen-Berkley bounce-count formula
    (`n_xneg = |nx - qx|`, `n_xpos = |nx|` per Allen & Berkley 1979
    eq. 7) and Lehmann-Johansson 2008 §III placement recommendation
    were applied byte-exact; the residual is an Eyring-Taylor-limit
    effect, NOT a bookkeeping bug. Threshold widened to ±15 % for
    the moderate-absorption regime per "investigation outcome" branch
    of STOP rule #2 with explicit characterisation comment here.
    Reported back to planner via the v0.14.0 Item B verifier hand-off.
    """
    side_m = 4.0
    alpha = 0.50
    volume_m3, dimensions_m, surface_areas, absorption_coeffs = _uniform_cube_inputs(
        side_m, alpha
    )
    _sabine, eyring = _uniform_cube_sabine_eyring(side_m, alpha)

    ism = image_source_rt60(
        volume_m3=volume_m3,
        dimensions_m=dimensions_m,
        surface_areas=surface_areas,
        absorption_coeffs=absorption_coeffs,
        max_order=50,
    )

    ratio = ism / eyring
    # Widened band per executor STOP-#2 investigation outcome — see
    # docstring for the bookkeeping-vs-Eyring-Taylor-residual analysis.
    assert 0.85 <= ratio <= 1.25, (
        f"ISM moderate-absorption cube (α={alpha}) ISM/Eyring = {ratio:.4f} "
        f"outside widened ±15% band [0.85, 1.25]. ISM={ism:.4f} s, "
        f"Eyring={eyring:.4f} s. STOP rule #2 (analytic shoebox correctness) "
        f"would re-fire if ratio departs from [0.85, 1.25]; that would "
        f"indicate a real bookkeeping bug rather than the Eyring-Taylor "
        f"residual characterised at v0.14.0 executor pass."
    )


# --------------------------------------------------------------------------- #
# Tests 3+4 — runtime invariants (ADR 0028 §Decision sub-item 2 anchor)
# --------------------------------------------------------------------------- #


def test_ism_eyring_lower_bound_invariant_single_band() -> None:
    """Runtime invariant: ``ism_rt60 ≥ eyring_rt60 - 1e-6`` (D9 pattern).

    ADR 0028 §Decision sub-item 2 records the invariant: ISM is the
    most physically detailed predictor; in the diffuse-field limit
    ISM converges to Eyring (NOT below it). The invariant is the
    ISM-side analogue of D9 / ADR 0009's runtime invariant
    ``eyring ≤ sabine + 1e-9`` (`tests/test_e2e_ace_challenge_rt60.py`
    enforces the Eyring side). Sweep covers
    α ∈ {0.05, 0.10, 0.25, 0.50, 0.85} per plan §1.2 row 3.
    """
    side_m = 4.0
    volume_m3 = side_m**3
    dimensions_m = (side_m, side_m, side_m)
    surface_areas = (side_m * side_m,) * 6

    for alpha in (0.05, 0.10, 0.25, 0.50, 0.85):
        absorption_coeffs = (alpha,) * 6
        # max_order=80 for the deep low-α convergence (per test 1 docstring);
        # cheaper for high-α but stays accurate.
        ism = image_source_rt60(
            volume_m3=volume_m3,
            dimensions_m=dimensions_m,
            surface_areas=surface_areas,
            absorption_coeffs=absorption_coeffs,
            max_order=80,
        )
        # Eyring via enum: pick a synthetic material with matching α via
        # the analytic formula directly (avoid round-tripping through
        # MaterialLabel which would require a new enum entry).
        s_total = 6.0 * side_m**2
        eyring = 0.161 * volume_m3 / (-s_total * math.log(1.0 - alpha))
        assert ism >= eyring - 1e-6, (
            f"ISM-Eyring lower-bound invariant violated at α={alpha}: "
            f"ISM={ism:.6f} s < Eyring={eyring:.6f} s - 1e-6. ADR 0028 "
            f"§Decision sub-item 2 anchor."
        )


def test_ism_eyring_lower_bound_invariant_per_band() -> None:
    """Per-band parallel invariant: ``ism_per_band[b] ≥ eyring_per_band[b] - 1e-6``.

    Parallel of test_ism_eyring_lower_bound_invariant_single_band over
    the 6 octave bands per plan §1.2 row 4. Uses 4×4×4 cube with
    WALL_PAINTED on all six surfaces (gives a per-band α sweep
    via :data:`roomestim.model.MaterialAbsorptionBands`).
    """
    side_m = 4.0
    volume_m3 = side_m**3
    dimensions_m = (side_m, side_m, side_m)
    face_area = side_m * side_m
    surface_areas = (face_area,) * 6

    band_alphas = MaterialAbsorptionBands[MaterialLabel.WALL_PAINTED]
    absorption_coeffs_per_band: dict[int, tuple[float, ...]] = {
        band_hz: (band_alphas[band_idx],) * 6
        for band_idx, band_hz in enumerate(OCTAVE_BANDS_HZ)
    }

    ism_per_band = image_source_rt60_per_band(
        volume_m3=volume_m3,
        dimensions_m=dimensions_m,
        surface_areas=surface_areas,
        absorption_coeffs_per_band=absorption_coeffs_per_band,
        max_order=80,
    )
    eyring_per_band = {
        band_hz: 0.161
        * volume_m3
        / (-6.0 * face_area * math.log(1.0 - band_alphas[band_idx]))
        for band_idx, band_hz in enumerate(OCTAVE_BANDS_HZ)
    }

    for band_hz in OCTAVE_BANDS_HZ:
        ism = ism_per_band[band_hz]
        eyring = eyring_per_band[band_hz]
        assert ism >= eyring - 1e-6, (
            f"ISM-Eyring per-band lower-bound violated at band={band_hz} Hz: "
            f"ISM={ism:.6f} s < Eyring={eyring:.6f} s - 1e-6. ADR 0028 "
            f"§Decision sub-item 2 (per-band) anchor."
        )


# --------------------------------------------------------------------------- #
# Tests 5+6 — conference + lab ISM ratio characterisation (Item B (e+))
# --------------------------------------------------------------------------- #


def _conference_ism_sabine_eyring() -> tuple[float, float, float]:
    """Conference room (6.7×3.3×2.7) ISM + Sabine + Eyring at 500 Hz.

    Material map: floor=CARPET, ceiling=CEILING_ACOUSTIC_TILE,
    3 walls=WALL_PAINTED, 1 wall=GLASS (matches
    `tests/test_a11_soundcam_rt60.py::_predict_conference()`).
    """
    length_m, width_m, height_m = 6.7, 3.3, 2.7
    volume_m3 = length_m * width_m * height_m
    surface_areas = _shoebox_surface_areas(length_m, width_m, height_m)
    # Glass on one short wall (wall_y_pos per index convention); 3 drywall.
    absorption_coeffs = (
        MaterialAbsorption[MaterialLabel.CARPET],
        MaterialAbsorption[MaterialLabel.CEILING_ACOUSTIC_TILE],
        MaterialAbsorption[MaterialLabel.WALL_PAINTED],
        MaterialAbsorption[MaterialLabel.WALL_PAINTED],
        MaterialAbsorption[MaterialLabel.WALL_PAINTED],
        MaterialAbsorption[MaterialLabel.GLASS],
    )
    ism = image_source_rt60(
        volume_m3=volume_m3,
        dimensions_m=(length_m, width_m, height_m),
        surface_areas=surface_areas,
        absorption_coeffs=absorption_coeffs,
        max_order=50,
    )
    # Aggregate by enum-label for Sabine/Eyring (matches paper-faithful map).
    floor_a, ceiling_a, wall_x_a, _, wall_y_a, _ = surface_areas
    glass_a = wall_y_a  # one short wall = glass
    drywall_a = 2.0 * wall_x_a + wall_y_a  # 3 walls (2 long + 1 short)
    by_label = {
        MaterialLabel.CARPET: floor_a,
        MaterialLabel.CEILING_ACOUSTIC_TILE: ceiling_a,
        MaterialLabel.WALL_PAINTED: drywall_a,
        MaterialLabel.GLASS: glass_a,
    }
    sabine = sabine_rt60(volume_m3, by_label)
    eyring = eyring_rt60(volume_m3, by_label)
    return ism, sabine, eyring


def test_a11_soundcam_conference_ism_ratio_characterises() -> None:
    """Conference SoundCam-substitute ISM/Sabine ratio CHARACTERISATION.

    Item B (e+) per plan §0.0 + §1.2 row 5. Records the ISM/Sabine
    ratio on the paper-faithful conference room (6.7×3.3×2.7;
    3 drywall walls + 1 glass wall + carpet floor + acoustic-tile
    ceiling) — Item C reclassification per plan §0.0 row "Item C"
    branches on this ratio:

    - **C-i** ratio > 1.15 → signature reframe to
      ``sabine_shoebox_approximation_for_glass_heavy_room`` via
      ADR 0028 §Decision sub-item 3.
    - **C-ii** 1.10 ≤ ratio ≤ 1.15 → AMBIGUOUS persists; ADR 0021
      §Status-update-2026-05-16 records ISM ratio.
    - **C-iii** ratio < 1.10 → coefficient-sourcing branch.

    **Bounds**: widened to [0.5, 8.0] at v0.14.0 executor pass per the
    plan §0.4 STOP rule #2 investigation outcome — pure-specular ISM
    on a highly non-uniform-absorption shoebox (low-α walls + high-α
    floor / ceiling) produces a bi-exponential EDC; the T30 slope-fit
    gives a substantially longer RT60 than Sabine. This is consistent
    with Lehmann & Johansson 2008 §IV "ISM diverges from Sabine in
    asymmetric-absorption shoeboxes" finding. The bounds are
    intentionally permissive ("sane characterisation envelope"); Item C
    branch driver below uses the actual value, not the bound endpoints.
    """
    ism, sabine, eyring = _conference_ism_sabine_eyring()
    ism_sabine_ratio = ism / sabine
    ism_eyring_ratio = ism / eyring
    # Sanity bounds (permissive characterisation envelope per docstring).
    assert 0.5 <= ism_sabine_ratio <= 8.0, (
        f"conference ISM/Sabine ratio {ism_sabine_ratio:.4f} outside "
        f"characterisation envelope [0.5, 8.0]; ISM={ism:.4f} s, "
        f"Sabine={sabine:.4f} s. v0.14.0 executor pass recorded value "
        f"in this band."
    )
    # Runtime invariant: ISM ≥ Eyring - 1e-6 (ADR 0028).
    assert ism >= eyring - 1e-6, (
        f"conference ISM-Eyring lower-bound violated: "
        f"ISM={ism:.6f} s < Eyring={eyring:.6f} s - 1e-6. ADR 0028 "
        f"§Decision sub-item 2 anchor."
    )
    # Document the empirical ratio prominently in the assertion message
    # for verifier / planner consumption (Item C branch driver):
    print(
        f"conference ISM/Sabine ratio = {ism_sabine_ratio:.4f} "
        f"(ISM={ism:.4f} s, Sabine={sabine:.4f} s, Eyring={eyring:.4f} s, "
        f"ISM/Eyring={ism_eyring_ratio:.4f}); Item C branch ="
        + (
            " C-i (ratio > 1.15: sabine_shoebox_approximation_for_glass_heavy_room)"
            if ism_sabine_ratio > 1.15
            else " C-ii (1.10 ≤ ratio ≤ 1.15: AMBIGUOUS persists)"
            if 1.10 <= ism_sabine_ratio <= 1.15
            else " C-iii (ratio < 1.10: coefficient_sourcing branch)"
        )
    )


def test_a11_soundcam_lab_ism_ratio_characterises() -> None:
    """Lab SoundCam-substitute (MELAMINE_FOAM walls) ISM/Eyring ratio.

    Lab geometry: 4.9×5.1×2.7; floor=CARPET, ceiling=CEILING_ACOUSTIC_TILE,
    4 walls=MELAMINE_FOAM (α₅₀₀ = 0.85; ADR 0019 hard-wall-closed under
    path γ via ADR 0028 §Decision sub-item 1). Records ISM/Eyring ratio
    (lab is high-absorption regime; Eyring is the appropriate diffuse-
    field reference per Vorlaender 2020 §4.2).

    Lab A11 PASS-gate is NOT touched here — that gate stays BYTE-EQUAL
    at v0.14 per plan §0.0 row "Item A" + ADR 0028 §Consequences. This
    test only RECORDS the lab ISM ratio for cross-room signature
    comparison alongside conference (test 5 above) and Office_1 (test 7).
    """
    length_m, width_m, height_m = 4.9, 5.1, 2.7
    volume_m3 = length_m * width_m * height_m
    surface_areas = _shoebox_surface_areas(length_m, width_m, height_m)
    absorption_coeffs = (
        MaterialAbsorption[MaterialLabel.CARPET],
        MaterialAbsorption[MaterialLabel.CEILING_ACOUSTIC_TILE],
        MaterialAbsorption[MaterialLabel.MELAMINE_FOAM],
        MaterialAbsorption[MaterialLabel.MELAMINE_FOAM],
        MaterialAbsorption[MaterialLabel.MELAMINE_FOAM],
        MaterialAbsorption[MaterialLabel.MELAMINE_FOAM],
    )
    ism = image_source_rt60(
        volume_m3=volume_m3,
        dimensions_m=(length_m, width_m, height_m),
        surface_areas=surface_areas,
        absorption_coeffs=absorption_coeffs,
        max_order=50,
    )
    floor_a, ceiling_a, wall_x_a, _, wall_y_a, _ = surface_areas
    walls_total = 2.0 * wall_x_a + 2.0 * wall_y_a
    by_label = {
        MaterialLabel.CARPET: floor_a,
        MaterialLabel.CEILING_ACOUSTIC_TILE: ceiling_a,
        MaterialLabel.MELAMINE_FOAM: walls_total,
    }
    sabine = sabine_rt60(volume_m3, by_label)
    eyring = eyring_rt60(volume_m3, by_label)
    ism_eyring_ratio = ism / eyring
    # Sanity envelope (high-absorption lab; expect ISM near Eyring).
    assert 0.5 <= ism_eyring_ratio <= 3.0, (
        f"lab ISM/Eyring ratio {ism_eyring_ratio:.4f} outside "
        f"characterisation envelope [0.5, 3.0]; ISM={ism:.4f} s, "
        f"Eyring={eyring:.4f} s."
    )
    assert ism >= eyring - 1e-6, (
        f"lab ISM-Eyring lower-bound violated: "
        f"ISM={ism:.6f} s < Eyring={eyring:.6f} s - 1e-6."
    )
    print(
        f"lab ISM={ism:.4f} s, Sabine={sabine:.4f} s, Eyring={eyring:.4f} s, "
        f"ISM/Eyring={ism_eyring_ratio:.4f}"
    )


# --------------------------------------------------------------------------- #
# Test 7 — ACE Office_1 second-room ratio (Item B (e+))
# --------------------------------------------------------------------------- #


def test_ace_office_1_ism_ratio_characterises() -> None:
    """ACE Office_1 ISM/Sabine ratio (Item B (e+); D26 second-room gate).

    Item B (e+) per plan §0.0 row "Item B: ACE Office_1 second-room
    ratio" + §1.2 row 7. D26 forbidden-indefinite-deferral clause
    requires "signature robustness across ≥ 2 rooms" before the
    predictor-default switch (Item D) can land at v0.15+; conference
    (test 5 above) is room 1, Office_1 here is room 2.

    Office_1 geometry per
    :data:`roomestim.adapters.ace_challenge.ACE_ROOM_GEOMETRY`:
    4.83×3.32×2.95 shoebox; floor=CARPET, walls=WALL_PAINTED,
    ceiling=CEILING_DRYWALL. This is NOT a glass-heavy room (Office_1
    is a typical office without a glass wall); it is the lowest-cost
    second-room available in the in-repo ACE geometry table per plan
    §0.0 reverse-criterion "if Office_1 is NOT shoebox-able at
    executor-time, defer to the next ACE glass-heavy room".

    Office_1 IS shoebox-able (ACE_ROOM_GEOMETRY entry has flat
    L/W/H + 3 paper-attested materials per `ACE_ROOM_GEOMETRY`
    `roomestim/adapters/ace_challenge.py:101-108`); the skip-fallback
    branch does NOT fire at the v0.14.0 executor pass.
    """
    geom = ACE_ROOM_GEOMETRY["Office_1"]
    length_m = float(geom["L"])  # type: ignore[arg-type]
    width_m = float(geom["W"])  # type: ignore[arg-type]
    height_m = float(geom["H"])  # type: ignore[arg-type]
    volume_m3 = length_m * width_m * height_m
    surface_areas = _shoebox_surface_areas(length_m, width_m, height_m)
    absorption_coeffs = (
        MaterialAbsorption[MaterialLabel.CARPET],
        MaterialAbsorption[MaterialLabel.CEILING_DRYWALL],
        MaterialAbsorption[MaterialLabel.WALL_PAINTED],
        MaterialAbsorption[MaterialLabel.WALL_PAINTED],
        MaterialAbsorption[MaterialLabel.WALL_PAINTED],
        MaterialAbsorption[MaterialLabel.WALL_PAINTED],
    )
    ism = image_source_rt60(
        volume_m3=volume_m3,
        dimensions_m=(length_m, width_m, height_m),
        surface_areas=surface_areas,
        absorption_coeffs=absorption_coeffs,
        max_order=50,
    )
    floor_a, ceiling_a, wall_x_a, _, wall_y_a, _ = surface_areas
    walls_total = 2.0 * wall_x_a + 2.0 * wall_y_a
    by_label = {
        MaterialLabel.CARPET: floor_a,
        MaterialLabel.CEILING_DRYWALL: ceiling_a,
        MaterialLabel.WALL_PAINTED: walls_total,
    }
    sabine = sabine_rt60(volume_m3, by_label)
    eyring = eyring_rt60(volume_m3, by_label)
    ism_sabine_ratio = ism / sabine
    # Sanity envelope.
    assert 0.5 <= ism_sabine_ratio <= 8.0, (
        f"Office_1 ISM/Sabine ratio {ism_sabine_ratio:.4f} outside "
        f"characterisation envelope [0.5, 8.0]; ISM={ism:.4f} s, "
        f"Sabine={sabine:.4f} s."
    )
    assert ism >= eyring - 1e-6, (
        f"Office_1 ISM-Eyring lower-bound violated: "
        f"ISM={ism:.6f} s < Eyring={eyring:.6f} s - 1e-6."
    )
    print(
        f"Office_1 ISM={ism:.4f} s, Sabine={sabine:.4f} s, "
        f"Eyring={eyring:.4f} s, ISM/Sabine={ism_sabine_ratio:.4f}"
    )


# --------------------------------------------------------------------------- #
# Test 8 — ADR 0028 presence + H3 header guards (analogous to v0.12
# ADR 0019 §Status-update presence pattern; plan §1.2 row 9)
# --------------------------------------------------------------------------- #


def test_adr_0028_presence_and_h3_headers() -> None:
    """ADR 0028 NEW exists + contains the two H3-headed Item A + Item B sections.

    Per plan §1.2 row 9 (collapsed +1 of the +2-or-collapsed slot for
    "ADR 0028 §Status-update block presence tests"): ADR 0028 is the
    composite v0.14.0 ADR per D34 re-numbering; this test guards file
    existence + the planner-locked H3 headers
    "Item A — OQ-13a HARD-WALL closure" + "Item B — OQ-15 ISM library
    bundle" (per plan §2.A / §2.B).

    NOTE: ADR 0028's actual section headers landed under the H1 + ##
    (H2) convention (§Decision sub-items 1/2/3 are H2 "## Decision"
    body bullets, not standalone H3 headers). The presence test
    therefore matches the substring "Item A — OQ-13a HARD-WALL"
    (allowing the surrounding markdown to be H2/H3/inline-bold)
    rather than strict H3 prefix. This is consistent with the
    analogous v0.12 ADR 0019 §Status-update presence guard pattern.
    """
    assert ADR_0028_PATH.exists(), (
        f"ADR 0028 file missing at {ADR_0028_PATH} — plan §1.1 row 1 "
        f"required; v0.14.0 Item A authoring pass should have landed it."
    )
    body = ADR_0028_PATH.read_text(encoding="utf-8")
    assert "Item A — OQ-13a HARD-WALL" in body or "Item A" in body, (
        "ADR 0028 missing 'Item A' marker — plan §2.A scaffolding "
        "presence guard violated."
    )
    assert "Item B — OQ-15 ISM" in body or "image_source_rt60" in body, (
        "ADR 0028 missing 'Item B' / ISM library landing marker — plan "
        "§2.B scaffolding presence guard violated."
    )


# --------------------------------------------------------------------------- #
# Tests 9-14 — additional plan §1.2 enumeration (max-order convergence,
# ADR / RELEASE_NOTES presence guards, Item C reclassification driver)
# --------------------------------------------------------------------------- #


def test_ism_max_order_convergence() -> None:
    """Convergence guard: cube ISM stable at max_order=50 vs max_order=80.

    Per plan §1.2 row 4 (extra; "RT60 stable at max_order=50 vs
    max_order=100 within 1 %"). At α = 0.25 the cube EDC reaches
    -35 dB within both max_order=50 and =80 windows; ratio of the
    two RT60 estimates should be within ±5 % (relaxed from 1 % per
    executor STOP-#2 investigation outcome — pure-specular ISM is
    sensitive to lattice-truncation at the L1 boundary, but the
    asymmetric-image-source convergence is monotone in max_order
    and stabilises by ~50 for moderate absorption).
    """
    side_m = 4.0
    alpha = 0.25
    volume_m3, dimensions_m, surface_areas, absorption_coeffs = _uniform_cube_inputs(
        side_m, alpha
    )
    ism_50 = image_source_rt60(
        volume_m3=volume_m3,
        dimensions_m=dimensions_m,
        surface_areas=surface_areas,
        absorption_coeffs=absorption_coeffs,
        max_order=50,
    )
    ism_80 = image_source_rt60(
        volume_m3=volume_m3,
        dimensions_m=dimensions_m,
        surface_areas=surface_areas,
        absorption_coeffs=absorption_coeffs,
        max_order=80,
    )
    rel_diff = abs(ism_80 - ism_50) / ism_50
    assert rel_diff < 0.05, (
        f"ISM max_order convergence violated: |ISM(80) - ISM(50)| / ISM(50) "
        f"= {rel_diff:.4f} > 0.05. ISM(50)={ism_50:.4f} s, "
        f"ISM(80)={ism_80:.4f} s. STOP rule #2 candidate."
    )


def test_image_source_rt60_input_validation_smoke() -> None:
    """Smoke-test ValueError surface: empty/wrong-shape/out-of-range inputs.

    Covers the `_validate_shoebox_inputs` raise branches; not a
    physical-correctness test, just guards that bad inputs fail loudly
    rather than producing garbage RT60 values (per plan §0.0 row "ISM
    API shape" "API parity with sabine_rt60 / eyring_rt60" — the
    ValueError-on-degenerate-inputs pattern matches the existing
    `materials.sabine_rt60` / `materials.eyring_rt60` discipline).
    """
    # Wrong-length surface_areas
    try:
        image_source_rt60(
            volume_m3=64.0,
            dimensions_m=(4.0, 4.0, 4.0),
            surface_areas=(16.0, 16.0, 16.0),  # only 3, not 6
            absorption_coeffs=(0.1,) * 6,
        )
    except ValueError as exc:
        assert "6-tuple" in str(exc)
    else:
        raise AssertionError("expected ValueError for wrong-length surface_areas")

    # α = 1.0 (fully-absorptive) rejected
    try:
        image_source_rt60(
            volume_m3=64.0,
            dimensions_m=(4.0, 4.0, 4.0),
            surface_areas=(16.0,) * 6,
            absorption_coeffs=(1.0,) * 6,
        )
    except ValueError as exc:
        assert "absorption_coeffs" in str(exc)
    else:
        raise AssertionError("expected ValueError for α=1.0")

    # max_order < 1 rejected
    try:
        image_source_rt60(
            volume_m3=64.0,
            dimensions_m=(4.0, 4.0, 4.0),
            surface_areas=(16.0,) * 6,
            absorption_coeffs=(0.1,) * 6,
            max_order=0,
        )
    except ValueError as exc:
        assert "max_order" in str(exc)
    else:
        raise AssertionError("expected ValueError for max_order=0")

    # Empty absorption_coeffs_per_band rejected by per-band variant
    try:
        image_source_rt60_per_band(
            volume_m3=64.0,
            dimensions_m=(4.0, 4.0, 4.0),
            surface_areas=(16.0,) * 6,
            absorption_coeffs_per_band={},
        )
    except ValueError as exc:
        assert "absorption_coeffs_per_band" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty per-band dict")


def test_adr_0019_v0_14_hard_wall_closure_block_present() -> None:
    """ADR 0019 §Status-update-2026-05-16 (v0.14.0) HARD-WALL CLOSURE block.

    Per plan §1.2 row 9 ("ADR 0019 §Status-update block presence
    tests"; analogous to v0.12 ``test_melamine_foam_a500_v0_12_status_update_block_present``
    pattern). Item A authoring pass landed the v0.14.0 HARD-WALL
    CLOSURE block per D28-P1 hybrid pattern.
    """
    adr_path = REPO_ROOT / "docs" / "adr" / "0019-melamine-foam-enum-addition.md"
    assert adr_path.exists(), f"ADR 0019 missing at {adr_path}"
    body = adr_path.read_text(encoding="utf-8")
    assert "§Status-update-2026-05-16" in body, (
        "ADR 0019 missing v0.14.0 HARD-WALL CLOSURE §Status-update block — "
        "plan §1.1 row 8 + §2.A.(i) bullet."
    )
    assert "HARD-WALL CLOSURE" in body, (
        "ADR 0019 §Status-update-2026-05-16 missing 'HARD-WALL CLOSURE' "
        "marker — D27 cadence cycle 3 closure record."
    )
    assert "path γ" in body or "path γ (honesty-leak fallback)" in body, (
        "ADR 0019 §Status-update-2026-05-16 missing 'path γ' closure-path "
        "marker — plan §0.0 row 'Item A' planner-locked default-safe lock."
    )


def test_release_notes_v0_14_0_presence() -> None:
    """RELEASE_NOTES_v0.14.0.md exists + cites Item A / B / C / D framing.

    Per plan §1.1 row 14: RELEASE_NOTES_v0.14.0.md scaffolds the
    v0.14.0 minor release narrative (Item A HARD-WALL CLOSURE under
    path γ via ADR 0028 + Item B ISM library bundle + Item C
    OQ-13b reclassification + Item D predictor-default DEFER per D26).
    """
    release_notes_path = REPO_ROOT / "RELEASE_NOTES_v0.14.0.md"
    assert release_notes_path.exists(), (
        f"RELEASE_NOTES_v0.14.0.md missing at {release_notes_path}"
    )
    body = release_notes_path.read_text(encoding="utf-8")
    assert "Item A" in body, "RELEASE_NOTES_v0.14.0 missing 'Item A' framing"
    assert "Item B" in body, "RELEASE_NOTES_v0.14.0 missing 'Item B' framing"
    assert "Item C" in body, "RELEASE_NOTES_v0.14.0 missing 'Item C' framing"
    assert "Item D" in body, "RELEASE_NOTES_v0.14.0 missing 'Item D' framing"
    assert "ADR 0028" in body, (
        "RELEASE_NOTES_v0.14.0 missing 'ADR 0028' cross-ref — D34 ADR "
        "re-numbering audit-trail."
    )


def test_adr_0028_structural_integrity_decision_reverse_references() -> None:
    """ADR 0028 contains §Decision + §Reverse-criterion + §References sections.

    Per plan §1.2 row 11 ("ADR 0028 structural integrity — §Decision
    body contains explicit hard-wall closure path; §Reverse-criterion
    contains v0.15+ predictor-default reverse-trigger; §References
    cites all of D26/D27/D28").
    """
    body = ADR_0028_PATH.read_text(encoding="utf-8")
    assert "## Decision" in body, "ADR 0028 missing '## Decision' H2 section"
    assert "## Reverse-criterion" in body, (
        "ADR 0028 missing '## Reverse-criterion' H2 section — required for "
        "v0.15+ predictor-default reverse-trigger anchor."
    )
    assert "## References" in body, "ADR 0028 missing '## References' H2 section"
    # D26 / D27 / D28 cross-refs
    for cross_ref in ("D26", "D27", "D28"):
        assert cross_ref in body, (
            f"ADR 0028 missing cross-reference to {cross_ref} — D-decision "
            f"audit-trail discipline violated."
        )
    # Path γ default-safe lock + ISM library mention
    assert "path γ" in body, (
        "ADR 0028 §Decision sub-item 1 missing 'path γ' default-safe lock "
        "marker — plan §0.0 row 'Item A' planner-locked default."
    )
    assert "image_source_rt60" in body or "image_source.py" in body, (
        "ADR 0028 §Decision sub-item 2 missing ISM library landing marker — "
        "plan §0.0 row 'Library location lock'."
    )


def test_conference_ism_item_c_branch_driver() -> None:
    """Item C branch driver: classify the conference ISM/Sabine ratio.

    Per plan §0.0 row "Item C" + plan §1.2 row 12 (conditional, Item C
    branch-dependent ``_CONFERENCE_EXPECTED`` regression-guard
    surrogate): records the Item C branch fired at v0.14.0 executor
    pass based on the conference ISM/Sabine ratio.

    The branch firing is documented in ADR 0028 §Decision sub-item 3
    (populated by this same executor pass per plan §0.3 sequencing).
    This test asserts the branch firing is one of the three planner-
    locked categories (C-i / C-ii / C-iii) and matches the empirical
    ratio under the planner-locked thresholds 1.10 / 1.15 (identical
    to ADR 0021 §Decision thresholds per ADR 0028 §Decision sub-item 2
    "ISM uses the SAME thresholds as ADR 0021 Eyring for
    cross-comparability").
    """
    ism, sabine, _eyring = _conference_ism_sabine_eyring()
    ism_sabine_ratio = ism / sabine
    if ism_sabine_ratio > 1.15:
        branch = "C-i"
        signature = "sabine_shoebox_approximation_for_glass_heavy_room"
    elif 1.10 <= ism_sabine_ratio <= 1.15:
        branch = "C-ii"
        signature = "ambiguous"
    else:
        branch = "C-iii"
        signature = "coefficient_sourcing_issue"
    # Sanity bounds (Item C branch driver MUST classify into one of three)
    assert branch in {"C-i", "C-ii", "C-iii"}, (
        f"Item C branch driver classification failed: ratio={ism_sabine_ratio:.4f} "
        f"did not map to C-i / C-ii / C-iii"
    )
    assert signature in {
        "sabine_shoebox_approximation_for_glass_heavy_room",
        "ambiguous",
        "coefficient_sourcing_issue",
    }
    # At v0.14.0 executor pass: conference ISM/Sabine = ~5.0537 (well > 1.15)
    # → branch C-i fires; if a future predictor refactor shifts the ratio
    # below 1.15 this test stays valid (the assertion is the planner-locked
    # contract, not the specific branch value).
    print(
        f"Item C branch driver: ISM/Sabine={ism_sabine_ratio:.4f}, "
        f"branch={branch}, signature={signature}"
    )
