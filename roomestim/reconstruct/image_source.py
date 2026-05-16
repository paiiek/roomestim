"""Image-source method (ISM) RT60 for shoebox rooms (v0.14.0; OQ-15).

Shoebox-only ISM landing point per planner-locked default at
`.omc/plans/v0.14-design.md` §0.0 row "Library location lock" + Critical
Correction CC-1 (lands under `roomestim/reconstruct/`, NOT a new
`roomestim/predict/` package).

Algorithm (Allen & Berkley 1979 JASA; Vorlaender 2020 *Auralization*
§11.2 / §4.2.4):

  - For a shoebox L×W×H with a single source-receiver pair, the
    image-source method enumerates virtual image sources by mirroring
    the original source across each of the six walls (and recursively
    across mirrored walls). The image-source lattice is parameterised
    by ``(nx, ny, nz)`` ∈ Z^3 (cell indices) and the eight parity
    choices ``(px, py, pz)`` ∈ {0, 1}^3.
  - An image source at lattice index ``(nx, ny, nz)`` with parity
    ``(px, py, pz)`` reflects ``|nx| + px*sign-correction`` times off
    the two x-normal walls combined (and analogously for y, z). For
    the floor/ceiling and 4 walls, the number of bounces off each
    surface can be derived from the lattice index + parity (Allen &
    Berkley 1979 eq. 7).
  - Each image-source contributes pressure ``∝ R / r`` where
    ``R = ∏_s (1 - α_s)^(n_s / 2)`` is the pressure-reflection-factor
    product over the 6 surfaces (``α`` = absorption coefficient,
    ``n_s`` = number of bounces off surface ``s``) and ``r`` is the
    Euclidean distance from image source to receiver.
  - Energy ``∝ R^2 / r^2 = ∏_s (1 - α_s)^(n_s) / r^2`` per image
    (energy lower bound on intensity arriving at the receiver). We bin
    energy contributions into time bins ``t = r / c`` (sound speed),
    yielding an energy decay curve (EDC) after Schroeder-style
    backward integration.
  - RT60 is fit as ``T60 = -60 / slope`` where ``slope`` is the
    least-squares slope of ``10 * log10(EDC)`` vs ``t`` over the
    decay window [-5 dB, energy_threshold_db] (default
    [-5 dB, -35 dB] window if -60 dB unreachable; conservative T20/T30
    extrapolation per ISO 3382-2). We extrapolate to the -60 dB level.

The shoebox-only library is co-located with
:func:`roomestim.reconstruct.materials.sabine_rt60` /
:func:`roomestim.reconstruct.materials.eyring_rt60`. Polygon ISM is
deferred to v0.15+ (OQ-23 NEW per D34).

Runtime invariant (ADR 0028 §Decision sub-item 2; pattern source
ADR 0009 / D9 runtime invariant ``eyring ≤ sabine + 1e-9``):

  ``image_source_rt60 ≥ eyring_rt60 - 1e-6``

absolute lower-bound — ISM is the most physically detailed predictor
(image-source enumeration captures specular-reflection bookkeeping
that the diffuse-field Sabine + Eyring formulae approximate); in the
diffuse-field limit ISM converges to Eyring. NOT a strict ratio bound.

API parity (planner-locked at `.omc/plans/v0.14-design.md` §0.0 row
"Item B: ISM API shape"):

- :func:`image_source_rt60` — single-band (500 Hz mid-band default).
- :func:`image_source_rt60_per_band` — per-octave-band variant.

Both accept ``volume_m3`` + ``dimensions_m`` + ``surface_areas`` +
``absorption_coeffs`` (6-tuples) as pure-Python types; numpy is
used internally only.

References:
- Allen, J. B. & Berkley, D. A. (1979). Image method for efficiently
  simulating small-room acoustics. JASA 65(4), 943-950.
- Vorlaender, M. (2020). *Auralization*, §11.2 (image-source method)
  + §4.2.4 (Sabine / Eyring diffuse-field limit). Springer.
- ADR 0028 §Decision sub-item 2 + §References; D34 (v0.14 ADR + OQ
  re-numbering); plan `.omc/plans/v0.14-design.md` §2.B.
"""

from __future__ import annotations

import math

import numpy as np

__all__ = [
    "image_source_rt60",
    "image_source_rt60_per_band",
]


# Surface index convention (LOCKED at v0.14.0):
#   0 = floor          (z = 0)
#   1 = ceiling        (z = H)
#   2 = wall_x_neg     (x = 0)
#   3 = wall_x_pos     (x = L)
#   4 = wall_y_neg     (y = 0)
#   5 = wall_y_pos     (y = W)
#
# The 6-tuple ``surface_areas`` / ``absorption_coeffs`` follows this
# order. The convention is fixed; callers passing dimensions for a
# shoebox (L, W, H) get this ordering by construction.

_SURFACE_INDEX_FLOOR: int = 0
_SURFACE_INDEX_CEILING: int = 1
_SURFACE_INDEX_WALL_X_NEG: int = 2
_SURFACE_INDEX_WALL_X_POS: int = 3
_SURFACE_INDEX_WALL_Y_NEG: int = 4
_SURFACE_INDEX_WALL_Y_POS: int = 5


def _validate_shoebox_inputs(
    volume_m3: float,
    dimensions_m: tuple[float, float, float],
    surface_areas: tuple[float, ...],
    absorption_coeffs: tuple[float, ...],
    max_order: int,
    energy_threshold_db: float,
    sound_speed_m_s: float,
) -> None:
    """Argument validation shared by single-band and per-band variants."""
    if volume_m3 <= 0.0:
        raise ValueError(
            f"image_source_rt60: volume_m3 must be > 0; got {volume_m3}"
        )
    if len(dimensions_m) != 3:
        raise ValueError(
            f"image_source_rt60: dimensions_m must be a 3-tuple (L, W, H); "
            f"got len={len(dimensions_m)}"
        )
    length_m, width_m, height_m = dimensions_m
    if length_m <= 0.0 or width_m <= 0.0 or height_m <= 0.0:
        raise ValueError(
            f"image_source_rt60: dimensions_m components must be > 0; "
            f"got {dimensions_m}"
        )
    if len(surface_areas) != 6:
        raise ValueError(
            f"image_source_rt60: surface_areas must be a 6-tuple "
            f"(floor, ceiling, wall_xneg, wall_xpos, wall_yneg, wall_ypos); "
            f"got len={len(surface_areas)}"
        )
    if len(absorption_coeffs) != 6:
        raise ValueError(
            f"image_source_rt60: absorption_coeffs must be a 6-tuple parallel "
            f"to surface_areas; got len={len(absorption_coeffs)}"
        )
    for idx, alpha in enumerate(absorption_coeffs):
        if not (0.0 <= alpha < 1.0):
            raise ValueError(
                f"image_source_rt60: absorption_coeffs[{idx}]={alpha} "
                "outside [0.0, 1.0); fully-reflective (=0) is acceptable, "
                "fully-absorptive (=1) is not (ISM reflection factor undefined)"
            )
    if max_order < 1:
        raise ValueError(
            f"image_source_rt60: max_order must be >= 1; got {max_order}"
        )
    if energy_threshold_db >= 0.0:
        raise ValueError(
            f"image_source_rt60: energy_threshold_db must be < 0 dB; "
            f"got {energy_threshold_db}"
        )
    if sound_speed_m_s <= 0.0:
        raise ValueError(
            f"image_source_rt60: sound_speed_m_s must be > 0; "
            f"got {sound_speed_m_s}"
        )


def _ism_rt60_core(
    dimensions_m: tuple[float, float, float],
    absorption_coeffs: tuple[float, ...],
    max_order: int,
    energy_threshold_db: float,
    sound_speed_m_s: float,
) -> float:
    """ISM RT60 core (shoebox; no input validation; assumes inputs validated).

    **Layering note** (added 2026-05-16 per code-reviewer pass MINOR
    finding #3.5): input validation is performed in the **public API
    wrappers** :func:`image_source_rt60` (single-band) and
    :func:`image_source_rt60_per_band` (per-band) via
    :func:`_validate_shoebox_inputs`. This core function is a
    private helper (NOT in ``__all__``); any future internal caller
    MUST either go through the public wrappers OR call
    :func:`_validate_shoebox_inputs` explicitly before invoking the
    core. The core may emit numerically garbage results for inputs
    that violate the validator preconditions (negative dimensions,
    α ∈ {0, 1}, max_order < 1, etc.). Cross-ref: code-review memo
    ``.omc/plans/v0.14-code-review-2026-05-16.md`` §3.5.

    Computes the energy decay curve via image-source enumeration on a
    fixed diagonal source-receiver pair (source at ``(0.3L, 0.3W, 0.5H)``,
    receiver at ``(0.7L, 0.7W, 0.5H)``). The diagonal placement avoids
    the direct-sound singularity that would dominate the EDC if source
    and receiver were co-located at the centroid — Lehmann & Johansson
    (2008) "Prediction of energy decay in room impulse responses
    simulated with an image-source model" §III documents the
    placement-bias sensitivity of ISM EDC fits and recommends
    non-degenerate source-receiver separation for RT60 estimation.

    The numerical procedure:

      1. Place source ``s = (0.3L, 0.3W, 0.5H)`` and receiver
         ``r = (0.7L, 0.7W, 0.5H)``. This diagonal placement gives a
         direct-path length comparable to the first-order reflections
         and produces a well-behaved EDC for slope-fitting across the
         ±absorption sweep of the unit-tests in
         ``tests/test_image_source.py``.
      2. For each lattice cell ``(nx, ny, nz)`` with
         ``|nx| + |ny| + |nz| <= max_order`` and each parity
         ``(px, py, pz) in {0, 1}^3``, compute the image source
         position and the bounce-count tuple ``(n_floor, n_ceiling,
         n_xneg, n_xpos, n_yneg, n_ypos)``.
      3. The bounce counts follow the Allen-Berkley convention
         (eq. 7): for a lattice cell ``(nx, ny, nz)`` with parity
         ``(px, py, pz)``, the image source is at
         ``(2*nx*L + (-1)^px * sx, 2*ny*W + (-1)^py * sy,
           2*nz*H + (-1)^pz * sz)``, and the per-wall bounce counts
         are ``n_xpos = |nx - px|``, ``n_xneg = |nx + px|`` (and
         analogously for y, z). Floor = z-neg; ceiling = z-pos.
      4. Energy per image = ``∏_s (1 - α_s)^(n_s) / r^2`` (intensity
         attenuation; the ``1/r^2`` spherical spread + product of
         per-surface energy-reflection factors).
      5. Bin energies into time bins indexed by ``t = r / c`` with
         bin width ``dt = 1 ms`` (1 ms = Allen-Berkley sample
         convention for fs = 1 kHz; sufficient resolution for RT60
         fitting which operates on tens-of-milliseconds windows).
      6. Schroeder-integrate the energy time series (running sum
         from t_max → t_min) to get the energy decay curve EDC(t)
         in linear units. Convert to dB: ``L(t) = 10*log10(EDC / EDC_0)``.
      7. Fit a line to ``L(t)`` over the decay window. Standard
         choice: [-5 dB, -35 dB] (T30 extrapolation per ISO 3382-2).
         If the EDC does not reach -35 dB within the image-source
         time span, fall back to [-5 dB, T_floor] where T_floor is
         the lowest dB-level achieved (with T20 if -25 dB reached,
         else T10). Multiply slope (dB/s) by -60 to get RT60.
    """
    length_m, width_m, height_m = dimensions_m

    # Fixed diagonal source-receiver placement (Lehmann & Johansson 2008
    # §III recommendation: non-degenerate separation avoids direct-sound
    # dominance of the EDC fit). Asymmetric placement on all three axes
    # avoids degenerate horizontal-plane image-source clustering (which
    # would over-weight low-α wall bounces and under-weight floor /
    # ceiling absorption when those differ from wall α — see Lehmann &
    # Johansson 2008 §III "placement-bias" appendix).
    source_x = 0.3 * length_m
    source_y = 0.3 * width_m
    source_z = 0.4 * height_m
    receiver_x = 0.7 * length_m
    receiver_y = 0.7 * width_m
    receiver_z = 0.6 * height_m

    alpha_floor = absorption_coeffs[_SURFACE_INDEX_FLOOR]
    alpha_ceiling = absorption_coeffs[_SURFACE_INDEX_CEILING]
    alpha_x_neg = absorption_coeffs[_SURFACE_INDEX_WALL_X_NEG]
    alpha_x_pos = absorption_coeffs[_SURFACE_INDEX_WALL_X_POS]
    alpha_y_neg = absorption_coeffs[_SURFACE_INDEX_WALL_Y_NEG]
    alpha_y_pos = absorption_coeffs[_SURFACE_INDEX_WALL_Y_POS]

    # Energy reflection coefficient per surface (1 - α).
    r2_floor = 1.0 - alpha_floor
    r2_ceiling = 1.0 - alpha_ceiling
    r2_x_neg = 1.0 - alpha_x_neg
    r2_x_pos = 1.0 - alpha_x_pos
    r2_y_neg = 1.0 - alpha_y_neg
    r2_y_pos = 1.0 - alpha_y_pos

    # Time-binning resolution. 1 ms bins match the Allen-Berkley
    # fs = 1 kHz convention (sufficient for RT60 fit on 10-100 ms windows).
    bin_dt_s = 0.001
    # Bound lattice indices so every image source has path length
    # ≤ max_path_m. With ``max_order`` as an L1 cap on
    # ``|nx| + |ny| + |nz|`` (the standard ISM lattice cap), the
    # maximum path is ``max_order * max(L, W, H) + sqrt(L²+W²+H²)``.
    max_path_m = (
        max_order * max(length_m, width_m, height_m)
        + math.sqrt(length_m**2 + width_m**2 + height_m**2)
    ) * 2.0  # safety factor for time-bin allocation
    n_bins = int(math.ceil(max_path_m / sound_speed_m_s / bin_dt_s)) + 1
    energy_bins = np.zeros(n_bins, dtype=np.float64)

    # Vectorised image-source enumeration over the lattice cube
    # ``[-max_order, max_order]^3`` (L_infinity cap; tighter than L1
    # for total reflection count, but cleaner to vectorise — the
    # extra-corner images decay fast and don't bias the EDC fit).
    # Per Allen & Berkley (1979) eq. 7 + Lehmann & Johansson (2008)
    # §II reproduction, for lattice index ``(nx, ny, nz)`` and parity
    # ``(qx, qy, qz)`` ∈ {0, 1}^3:
    #   image position:
    #     img_x = (1 - 2*qx) * sx + 2 * nx * L
    #   bounce counts:
    #     n_xneg (wall x=0)   = |nx - qx|
    #     n_xpos (wall x=L)   = |nx|
    #     n_yneg (wall y=0)   = |ny - qy|
    #     n_ypos (wall y=W)   = |ny|
    #     n_zneg (wall z=0,
    #             "floor")    = |nz - qz|
    #     n_zpos (wall z=H,
    #             "ceiling")  = |nz|
    # (Verified by hand: (nx=0, qx=0) → 0 reflections; (nx=0, qx=1)
    # → 1 reflection on xneg; (nx=1, qx=0) → 1 each on xneg + xpos;
    # (nx=1, qx=1) → 1 on xpos only. Reproduces Allen-Berkley §II
    # Table.)
    lattice_indices = np.arange(-max_order, max_order + 1, dtype=np.int64)
    nx_arr, ny_arr, nz_arr = np.meshgrid(
        lattice_indices, lattice_indices, lattice_indices, indexing="ij"
    )
    nx_flat = nx_arr.ravel()
    ny_flat = ny_arr.ravel()
    nz_flat = nz_arr.ravel()
    # L1-cap on lattice index (tightest standard ISM convergence
    # parameter; equivalent to "max_order total walls crossed by the
    # image path"). Drops the corner images of the L_inf cube.
    l1_mask = np.abs(nx_flat) + np.abs(ny_flat) + np.abs(nz_flat) <= max_order
    nx_flat = nx_flat[l1_mask]
    ny_flat = ny_flat[l1_mask]
    nz_flat = nz_flat[l1_mask]

    for qx in (0, 1):
        img_x_base = (1 - 2 * qx) * source_x + 2.0 * nx_flat * length_m
        n_xneg = np.abs(nx_flat - qx)
        n_xpos = np.abs(nx_flat)
        for qy in (0, 1):
            img_y_base = (1 - 2 * qy) * source_y + 2.0 * ny_flat * width_m
            n_yneg = np.abs(ny_flat - qy)
            n_ypos = np.abs(ny_flat)
            for qz in (0, 1):
                img_z = (1 - 2 * qz) * source_z + 2.0 * nz_flat * height_m
                n_zneg = np.abs(nz_flat - qz)  # floor bounces
                n_zpos = np.abs(nz_flat)  # ceiling bounces

                dx = img_x_base - receiver_x
                dy = img_y_base - receiver_y
                dz = img_z - receiver_z
                r_arr = np.sqrt(dx * dx + dy * dy + dz * dz)
                # Drop degenerate r=0 (would only happen if source ==
                # receiver at the lattice origin; our diagonal
                # placement guarantees r > 0, but guard anyway).
                valid = r_arr > 0.0
                if not np.any(valid):
                    continue

                # Per-image energy attenuation: product of per-surface
                # energy-reflection factors (1-α) raised to the bounce
                # count for that surface.
                energy_factor = (
                    np.power(r2_floor, n_zneg)
                    * np.power(r2_ceiling, n_zpos)
                    * np.power(r2_x_neg, n_xneg)
                    * np.power(r2_x_pos, n_xpos)
                    * np.power(r2_y_neg, n_yneg)
                    * np.power(r2_y_pos, n_ypos)
                )
                # Intensity: ``energy_factor / r^2`` (free-field
                # spherical spread + reflection attenuation).
                energies = np.where(
                    valid, energy_factor / (r_arr * r_arr), 0.0
                )

                # Time-of-flight bin indices.
                t_arr = r_arr / sound_speed_m_s
                bin_idx_arr = (t_arr / bin_dt_s).astype(np.int64)
                in_range = valid & (bin_idx_arr >= 0) & (bin_idx_arr < n_bins)
                if not np.any(in_range):
                    continue
                np.add.at(
                    energy_bins,
                    bin_idx_arr[in_range],
                    energies[in_range],
                )

    # Schroeder backward integration: EDC(t) = sum_{tau >= t} energy(tau).
    edc = np.flip(np.cumsum(np.flip(energy_bins)))
    if edc[0] <= 0.0:
        raise ValueError(
            "image_source_rt60: total integrated energy is zero; "
            "check inputs (max_order too small or fully-absorptive room)"
        )

    # Convert to dB relative to peak.
    edc_db = 10.0 * np.log10(np.maximum(edc / edc[0], 1e-300))

    # Time axis for each bin (use bin midpoint).
    t_axis = (np.arange(n_bins) + 0.5) * bin_dt_s

    # Fit decay slope over the [-5 dB, target] window. ISO 3382-2:
    # T30 ⇒ fit [-5, -35]; T20 ⇒ fit [-5, -25]; T10 ⇒ fit [-5, -15].
    # We try in order T30 / T20 / T10 and require user threshold be
    # at least reached (energy_threshold_db).
    upper_db = -5.0
    decay_targets = (
        ("T30", -35.0),
        ("T20", -25.0),
        ("T10", -15.0),
    )

    # Pick the deepest decay window that the EDC actually reaches.
    rt60: float | None = None
    for _label, lower_db in decay_targets:
        if edc_db.min() > lower_db:
            # EDC never reached this level — try a shallower window
            continue
        # Find indices in [-5 dB, lower_db]
        mask = (edc_db <= upper_db) & (edc_db >= lower_db)
        if mask.sum() < 2:
            continue
        t_window = t_axis[mask]
        dB_window = edc_db[mask]
        # Linear least-squares slope (dB/s)
        slope, _intercept = np.polyfit(t_window, dB_window, 1)
        if slope >= 0.0:
            # Non-decaying window — try a deeper level (shouldn't happen
            # given upper_db = -5 dB anchor, but guard anyway).
            continue
        rt60 = -60.0 / float(slope)
        break

    if rt60 is None:
        raise ValueError(
            "image_source_rt60: EDC did not reach -15 dB within image-source "
            f"time span; increase max_order (currently {max_order}) or check "
            "absorption_coeffs (room may be too reflective for the requested "
            "max_order)"
        )

    # Also enforce the user-specified energy_threshold_db: warn-equivalent
    # silent check — if EDC didn't reach energy_threshold_db we already
    # fell back to a shallower fit window; the returned RT60 is the
    # extrapolated -60 dB value. We do NOT raise here because the
    # extrapolation is standard ISO 3382-2 practice.
    _ = energy_threshold_db  # acknowledged; used for documentation

    return rt60


def image_source_rt60(
    volume_m3: float,
    dimensions_m: tuple[float, float, float],
    surface_areas: tuple[float, ...],
    absorption_coeffs: tuple[float, ...],
    max_order: int = 50,
    energy_threshold_db: float = -60.0,
    sound_speed_m_s: float = 343.0,
) -> float:
    """Single-band ISM RT60 via image-source energy integration.

    Shoebox-only at v0.14.0 (polygon ISM deferred to v0.15+ per OQ-23 NEW
    via D34). API parity with
    :func:`roomestim.reconstruct.materials.sabine_rt60` /
    :func:`roomestim.reconstruct.materials.eyring_rt60` per plan §0.0
    row "Item B: ISM API shape".

    Parameters
    ----------
    volume_m3:
        Room volume in cubic metres. Used for validation only (the
        ISM time-of-flight computation derives all path lengths from
        ``dimensions_m`` directly); the parameter is accepted for API
        parity with the Sabine / Eyring predictors.
    dimensions_m:
        Shoebox dimensions ``(L, W, H)`` in metres. All components
        must be strictly positive.
    surface_areas:
        6-tuple of surface areas ``(floor, ceiling, wall_x_neg,
        wall_x_pos, wall_y_neg, wall_y_pos)`` in m². Accepted for
        API parity; the ISM does not use ``surface_areas`` directly
        (per-surface bounce counts are derived from the lattice
        indices), but the tuple is validated for length and is
        documented at the call site for callers who want to
        cross-check the shoebox surface budget. Index convention is
        LOCKED at v0.14.0 — see module docstring.
    absorption_coeffs:
        6-tuple of absorption coefficients ``α ∈ [0, 1)`` parallel
        to ``surface_areas`` (same index convention). ``α = 1.0``
        (fully absorptive) is rejected because the ISM reflection
        factor ``(1 - α)`` would degenerate to zero on every bounce.
    max_order:
        Maximum total reflection order ``|n_x| + |n_y| + |n_z|``
        per image source (L1-cap, standard ISM convergence parameter).
        Default 50 is sufficient for typical small/medium rooms
        (volume ≤ ~500 m³ at α ≥ ~0.05). Larger rooms or very
        reflective rooms may require higher orders; raise this only
        after verifying convergence with the
        ``test_ism_max_order_convergence`` companion (planned in
        ``tests/test_image_source.py``).
    energy_threshold_db:
        **RESERVED for v0.15+ EDC threshold trim** (per code-reviewer
        pass MINOR finding #3.2; cross-ref
        ``.omc/plans/v0.14-code-review-2026-05-16.md`` §3.2). Validated
        for ``< 0 dB`` at the public-API boundary but NOT yet wired
        into the decay-slope fit cascade. v0.14.0 always cascades
        T30 → T20 → T10 per ISO 3382-2 regardless of user value;
        the returned RT60 is the slope extrapolated to -60 dB. v0.15+
        wiring of a user-supplied fourth cascade tier is tracked
        under the parameter-retention path (OQ to be filed if v0.15+
        planner accepts the wiring; otherwise the parameter is
        deprecated under a SemVer minor at v0.15+).
    sound_speed_m_s:
        Speed of sound for time-of-flight conversion. Default
        343 m/s (Vorlaender 2020 §1.1 reference value).

    Returns
    -------
    float
        Estimated RT60 in seconds.

    Raises
    ------
    ValueError
        On invalid inputs (non-positive volume / dimensions, wrong
        tuple lengths, ``α`` outside ``[0, 1)``, ``max_order < 1``,
        ``energy_threshold_db >= 0``, or non-positive sound speed);
        on degenerate-output conditions (zero total integrated
        energy; EDC never reaching -15 dB even with T10 fallback).

    Notes
    -----
    Runtime invariant (ADR 0028 §Decision sub-item 2; documented at
    `.omc/plans/v0.14-design.md` §0.0 row "Item B: ISM API shape"):
    ``image_source_rt60 ≥ eyring_rt60 - 1e-6`` — ISM is the most
    physically detailed predictor; in the diffuse-field limit ISM
    converges to Eyring. NOT enforced inside this function (would
    create a circular dependency with `materials.eyring_rt60`);
    enforced by ``tests/test_image_source.py`` test
    ``test_ism_eyring_lower_bound_invariant``.
    """
    _validate_shoebox_inputs(
        volume_m3=volume_m3,
        dimensions_m=dimensions_m,
        surface_areas=surface_areas,
        absorption_coeffs=absorption_coeffs,
        max_order=max_order,
        energy_threshold_db=energy_threshold_db,
        sound_speed_m_s=sound_speed_m_s,
    )
    return _ism_rt60_core(
        dimensions_m=dimensions_m,
        absorption_coeffs=absorption_coeffs,
        max_order=max_order,
        energy_threshold_db=energy_threshold_db,
        sound_speed_m_s=sound_speed_m_s,
    )


def image_source_rt60_per_band(
    volume_m3: float,
    dimensions_m: tuple[float, float, float],
    surface_areas: tuple[float, ...],
    absorption_coeffs_per_band: dict[int, tuple[float, ...]],
    max_order: int = 50,
    energy_threshold_db: float = -60.0,
    sound_speed_m_s: float = 343.0,
) -> dict[int, float]:
    """Per-octave-band ISM RT60 estimate (parallel predictor).

    Returns ``{band_hz: rt60_seconds}`` for each band present in
    ``absorption_coeffs_per_band``. Each band's RT60 is computed
    independently by invoking the single-band ISM core with the
    band-specific absorption tuple.

    Parameters
    ----------
    volume_m3:
        Room volume in cubic metres (API parity; see
        :func:`image_source_rt60`).
    dimensions_m:
        Shoebox dimensions ``(L, W, H)`` in metres.
    surface_areas:
        6-tuple of surface areas (API parity; see
        :func:`image_source_rt60`).
    absorption_coeffs_per_band:
        Mapping ``band_hz -> 6-tuple of α`` parallel to
        ``surface_areas``. Typical keys are
        ``(125, 250, 500, 1000, 2000, 4000)`` matching
        :data:`roomestim.model.OCTAVE_BANDS_HZ`, but any positive
        integer band keys are accepted.
    max_order, energy_threshold_db, sound_speed_m_s:
        See :func:`image_source_rt60`.

    Returns
    -------
    dict[int, float]
        ``{band_hz: rt60_seconds}`` for each band in
        ``absorption_coeffs_per_band``.

    Raises
    ------
    ValueError
        On invalid inputs (same conditions as :func:`image_source_rt60`,
        checked per band) or empty ``absorption_coeffs_per_band``.

    Notes
    -----
    Per-band runtime invariant (ADR 0028 §Decision sub-item 2):
    ``ism_rt60_per_band[band] ≥ eyring_rt60_per_band[band] - 1e-6``
    for every band. Enforced by ``tests/test_image_source.py`` test
    ``test_ism_eyring_lower_bound_invariant_per_band``.
    """
    if not absorption_coeffs_per_band:
        raise ValueError(
            "image_source_rt60_per_band: absorption_coeffs_per_band is empty"
        )
    out: dict[int, float] = {}
    for band_hz, alpha_tuple in absorption_coeffs_per_band.items():
        if band_hz <= 0:
            raise ValueError(
                f"image_source_rt60_per_band: band_hz must be > 0; "
                f"got {band_hz}"
            )
        _validate_shoebox_inputs(
            volume_m3=volume_m3,
            dimensions_m=dimensions_m,
            surface_areas=surface_areas,
            absorption_coeffs=alpha_tuple,
            max_order=max_order,
            energy_threshold_db=energy_threshold_db,
            sound_speed_m_s=sound_speed_m_s,
        )
        out[band_hz] = _ism_rt60_core(
            dimensions_m=dimensions_m,
            absorption_coeffs=alpha_tuple,
            max_order=max_order,
            energy_threshold_db=energy_threshold_db,
            sound_speed_m_s=sound_speed_m_s,
        )
    return out
