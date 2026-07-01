"""Sabine RT60 estimate + Vorlaender 2020 Appx A absorption table re-export.

Used by P4 acceptance criterion A11. The mid-band 500 Hz absorption table is
imported from :mod:`roomestim.model` and re-exported here for callers that
work in the reconstruction layer.

The synthetic-shoebox reference RT60 (D8 / ralplan-iter1-resolutions.md fix 3)
is computed analytically below as the v0.1 acceptance source-of-truth so that
A11 does not depend on a real lab capture.

v0.4 also exposes Eyring as a parallel RT60 predictor (Eyring 1930 JASA;
Vorlaender 2020 §4.2). Eyring corrects Sabine's overestimate in heavily-absorbed
rooms by replacing the linear ``alpha_total`` denominator with
``-S_total * ln(1 - alpha_bar)``, where ``alpha_bar`` is the surface-area-weighted
mean absorption. Sabine remains the default predictor in CLI and adapter
codepaths; Eyring is callable-level only at v0.4.
"""

from __future__ import annotations

from collections.abc import Sequence

from roomestim.model import MaterialAbsorption, MaterialLabel

__all__ = [
    "MaterialAbsorption",
    "MaterialLabel",
    "SABINE_REFERENCE_SHOEBOX_RT60_S",
    "SABINE_REFERENCE_SHOEBOX_RT60_PER_BAND_S",
    "eyring_rt60",
    "eyring_rt60_from_pairs",
    "eyring_rt60_per_band",
    "eyring_rt60_per_band_from_pairs",
    "sabine_rt60",
    "sabine_rt60_per_band",
]


# --------------------------------------------------------------------------- #
# Synthetic-shoebox Sabine reference (Vorlaender 2020 Appendix A)
# --------------------------------------------------------------------------- #

# Sabine reference for synthetic shoebox 5 x 4 x 2.8 m, Vorlaender 2020 Appx A:
#   walls   : 50.4 m^2 x 0.05 = 2.520
#   floor   : 20.0 m^2 x 0.10 = 2.000
#   ceiling : 20.0 m^2 x 0.55 = 11.000
#   total absorption = 15.52 sabins
#   V = 5 * 4 * 2.8 = 56 m^3
#   RT60 = 0.161 * 56 / 15.52 ~= 0.5810 s
SABINE_REFERENCE_SHOEBOX_RT60_S: float = 0.581


def sabine_rt60(
    volume_m3: float,
    surface_areas: dict[MaterialLabel, float],
) -> float:
    """Classic Sabine RT60 estimate at 500 Hz.

    Formula (textbook Sabine):

        RT60 = 0.161 * V / sum_i (S_i * a_i)

    where ``S_i`` is the area in m^2 of surfaces with material label ``i`` and
    ``a_i`` is the mid-band 500 Hz absorption coefficient from
    :data:`roomestim.model.MaterialAbsorption` (Vorlaender 2020 Appendix A).

    Parameters
    ----------
    volume_m3:
        Room volume in cubic metres.
    surface_areas:
        Mapping ``MaterialLabel -> area_m2`` summed across all surfaces of
        that material.

    Returns
    -------
    float
        Estimated RT60 in seconds.

    Raises
    ------
    ValueError
        If the total absorption is zero (empty surface set or all-reflective
        room), since RT60 would be infinite.
    """
    total_absorption: float = 0.0
    for material, area in surface_areas.items():
        coefficient = MaterialAbsorption[material]
        total_absorption += area * coefficient
    if total_absorption <= 0.0:
        raise ValueError(
            "sabine_rt60: total_absorption is zero; cannot compute finite RT60"
        )
    return 0.161 * volume_m3 / total_absorption


# Computed analytically from MaterialAbsorptionBands at v0.3 (deterministic).
# 5x4x2.8 m shoebox, walls=WALL_PAINTED 50.4 m², floor=WOOD_FLOOR 20.0 m², ceiling=CEILING_ACOUSTIC_TILE 20.0 m².
# V=56 m³. RT60_b = 0.161 * V / sum_i(S_i * a_i_b).
SABINE_REFERENCE_SHOEBOX_RT60_PER_BAND_S: dict[int, float] = {
    # Pre-computed at v0.3 from constants below — keys MUST equal OCTAVE_BANDS_HZ.
    # walls: (0.10,0.07,0.05,0.06,0.07,0.09) * 50.4
    # floor: (0.15,0.11,0.10,0.07,0.06,0.07) * 20.0
    # ceil:  (0.30,0.45,0.55,0.70,0.75,0.80) * 20.0
    125:  0.161 * 56.0 / (50.4 * 0.10 + 20.0 * 0.15 + 20.0 * 0.30),
    250:  0.161 * 56.0 / (50.4 * 0.07 + 20.0 * 0.11 + 20.0 * 0.45),
    500:  0.161 * 56.0 / (50.4 * 0.05 + 20.0 * 0.10 + 20.0 * 0.55),
    1000: 0.161 * 56.0 / (50.4 * 0.06 + 20.0 * 0.07 + 20.0 * 0.70),
    2000: 0.161 * 56.0 / (50.4 * 0.07 + 20.0 * 0.06 + 20.0 * 0.75),
    4000: 0.161 * 56.0 / (50.4 * 0.09 + 20.0 * 0.07 + 20.0 * 0.80),
}


def sabine_rt60_per_band(
    volume_m3: float,
    surface_areas: dict[MaterialLabel, float],
) -> dict[int, float]:
    """Per-octave-band Sabine RT60 estimate.

    Returns ``{band_hz: rt60_seconds}`` for each band in
    :data:`roomestim.model.OCTAVE_BANDS_HZ`. Uses
    :data:`roomestim.model.MaterialAbsorptionBands`.

    Raises :class:`ValueError` if any single band has zero total absorption
    (a per-band failure mode users want surfaced; the aggregate Sabine sum
    is not the relevant invariant per band).
    """
    from roomestim.model import MaterialAbsorptionBands, OCTAVE_BANDS_HZ

    out: dict[int, float] = {}
    for band_idx, band_hz in enumerate(OCTAVE_BANDS_HZ):
        total_absorption: float = 0.0
        for material, area in surface_areas.items():
            coefficient = MaterialAbsorptionBands[material][band_idx]
            total_absorption += area * coefficient
        if total_absorption <= 0.0:
            raise ValueError(
                f"sabine_rt60_per_band: total_absorption is zero in band {band_hz} Hz; "
                "cannot compute finite RT60"
            )
        out[band_hz] = 0.161 * volume_m3 / total_absorption
    return out


# --------------------------------------------------------------------------- #
# Eyring RT60 (Eyring 1930 JASA; Vorlaender 2020 §4.2) — parallel predictor
# --------------------------------------------------------------------------- #


def eyring_rt60(
    volume_m3: float,
    surface_areas: dict[MaterialLabel, float],
) -> float:
    """Eyring RT60 estimate at 500 Hz (parallel predictor; Sabine remains default).

    Formula (Eyring 1930 JASA; Vorlaender 2020 §4.2):

        RT60 = 0.161 * V / (-S_total * ln(1 - alpha_bar))

    where ``S_total = sum(surface_areas.values())`` and
    ``alpha_bar = sum_i(S_i * a_i) / S_total`` is the surface-area-weighted
    mean absorption at 500 Hz (from
    :data:`roomestim.model.MaterialAbsorption`). In the low-absorption limit
    ``-ln(1-x) -> x`` so Eyring converges to Sabine; in the high-absorption
    limit Eyring is strictly smaller, undoing Sabine's overestimate in
    heavily-absorbed rooms.

    Raises
    ------
    ValueError
        If ``surface_areas`` is empty or ``S_total <= 0`` (no surfaces),
        if total absorption is zero (all-reflective room), or if the
        weighted mean absorption ``alpha_bar >= 1.0`` (Eyring undefined).
    """
    import math

    s_total: float = sum(surface_areas.values())
    if s_total <= 0.0:
        raise ValueError(
            "eyring_rt60: surface_areas is empty / S_total is zero"
        )
    weighted_alpha_sum: float = 0.0
    for material, area in surface_areas.items():
        coefficient = MaterialAbsorption[material]
        weighted_alpha_sum += area * coefficient
    if weighted_alpha_sum <= 0.0:
        raise ValueError(
            "eyring_rt60: total absorption is zero; cannot compute finite RT60"
        )
    alpha_bar: float = weighted_alpha_sum / s_total
    if alpha_bar >= 1.0:
        raise ValueError(
            f"eyring_rt60: alpha_bar={alpha_bar:.4f} >= 1.0; "
            "Eyring undefined for fully-absorptive alpha_bar"
        )
    return 0.161 * volume_m3 / (-s_total * math.log(1.0 - alpha_bar))


def eyring_rt60_per_band(
    volume_m3: float,
    surface_areas: dict[MaterialLabel, float],
) -> dict[int, float]:
    """Per-octave-band Eyring RT60 estimate (parallel predictor).

    Returns ``{band_hz: rt60_seconds}`` for each band in
    :data:`roomestim.model.OCTAVE_BANDS_HZ`. Uses
    :data:`roomestim.model.MaterialAbsorptionBands`.

    Raises :class:`ValueError` per band if surfaces are empty/zero,
    if the per-band absorption is zero, or if the per-band ``alpha_bar >= 1``.
    """
    import math

    from roomestim.model import MaterialAbsorptionBands, OCTAVE_BANDS_HZ

    s_total: float = sum(surface_areas.values())
    if s_total <= 0.0:
        raise ValueError(
            "eyring_rt60_per_band: surface_areas is empty / S_total is zero"
        )

    out: dict[int, float] = {}
    for band_idx, band_hz in enumerate(OCTAVE_BANDS_HZ):
        weighted_alpha_sum: float = 0.0
        for material, area in surface_areas.items():
            coefficient = MaterialAbsorptionBands[material][band_idx]
            weighted_alpha_sum += area * coefficient
        if weighted_alpha_sum <= 0.0:
            raise ValueError(
                f"eyring_rt60_per_band: total absorption is zero in band {band_hz} Hz; "
                "cannot compute finite RT60"
            )
        alpha_bar: float = weighted_alpha_sum / s_total
        if alpha_bar >= 1.0:
            raise ValueError(
                f"eyring_rt60_per_band: alpha_bar={alpha_bar:.4f} >= 1.0 in band {band_hz} Hz; "
                "Eyring undefined for fully-absorptive alpha_bar"
            )
        out[band_hz] = 0.161 * volume_m3 / (-s_total * math.log(1.0 - alpha_bar))
    return out


# --------------------------------------------------------------------------- #
# Per-surface Eyring (v0.62.0) — honors per-surface α on the Eyring path
# --------------------------------------------------------------------------- #
#
# The label-dict variants above look up ``MaterialAbsorption[label]`` (the
# TABLE) and therefore DISCARD any per-surface custom ``absorption_500hz`` /
# ``absorption_bands`` a surface may carry. The Eyring predictor branch (used
# for non-shoebox / captured rooms and as the ISM lower-bound target) routes
# through these ``*_from_pairs`` variants instead so edited / adapter-divergent
# materials actually affect RT60 (ADR 0062). Byte-equality for standard "label"
# rooms is preserved by the CALLER grouping surfaces by ``(material, α)`` and
# pre-summing each group's area before calling here — so a label room collapses
# to one ``(area_sum, table_α)`` pair per material and reproduces the label-dict
# ``Σ_material (Σarea_m) * table[m]`` summation with identical FP association.


def eyring_rt60_from_pairs(
    volume_m3: float,
    pairs: Sequence[tuple[float, float]],
) -> float:
    """Eyring RT60 at 500 Hz from ``(area_m2, alpha_500)`` surface-group pairs.

    Identical math and guards to :func:`eyring_rt60`, but the absorption comes
    from the caller-supplied per-surface (or per-group) α rather than a
    ``MaterialLabel`` table lookup:

        S_total   = Σ area_i
        alpha_bar = Σ (area_i * α_i) / S_total
        RT60      = 0.161 * V / (-S_total * ln(1 - alpha_bar))

    Byte-equality: when the caller groups surfaces by ``(material, α)`` and
    pre-sums each group's area, a "label" room (every surface's α equals its
    ``MaterialAbsorption[material]``) yields exactly one pair per material and
    reproduces :func:`eyring_rt60`'s per-material summation bit-for-bit.

    Raises
    ------
    ValueError
        If ``pairs`` is empty / ``S_total <= 0`` (no surfaces), if the total
        absorption is zero (all-reflective room), or if the weighted mean
        absorption ``alpha_bar >= 1.0`` (Eyring undefined).
    """
    import math

    s_total: float = sum(area for area, _ in pairs)
    if s_total <= 0.0:
        raise ValueError(
            "eyring_rt60_from_pairs: pairs is empty / S_total is zero"
        )
    weighted_alpha_sum: float = 0.0
    for area, alpha in pairs:
        weighted_alpha_sum += area * alpha
    if weighted_alpha_sum <= 0.0:
        raise ValueError(
            "eyring_rt60_from_pairs: total absorption is zero; cannot compute finite RT60"
        )
    alpha_bar: float = weighted_alpha_sum / s_total
    if alpha_bar >= 1.0:
        raise ValueError(
            f"eyring_rt60_from_pairs: alpha_bar={alpha_bar:.4f} >= 1.0; "
            "Eyring undefined for fully-absorptive alpha_bar"
        )
    return 0.161 * volume_m3 / (-s_total * math.log(1.0 - alpha_bar))


def eyring_rt60_per_band_from_pairs(
    volume_m3: float,
    pairs: Sequence[tuple[float, tuple[float, ...] | None, float]],
) -> dict[int, float]:
    """Per-octave-band Eyring RT60 from per-surface-group pairs.

    Each pair is ``(area_m2, absorption_bands_or_None, alpha_500_fallback)``.
    For every band the per-band coefficient is ``absorption_bands[band_idx]``
    when the group carries per-band data, else the ``alpha_500_fallback`` scalar
    broadcast across all bands (mirrors the single-band α when a surface lacks
    per-band data).

    Byte-equality: the CALLER resolves each group's band data before calling —
    a label surface with ``absorption_bands is None`` is passed the material's
    :data:`roomestim.model.MaterialAbsorptionBands` tuple (NOT ``None``), which
    is exactly what :func:`eyring_rt60_per_band` uses, so a label room is
    reproduced bit-for-bit. The ``alpha_500_fallback`` branch only fires for a
    genuinely band-less group.

    Returns ``{band_hz: rt60_seconds}`` for each band in
    :data:`roomestim.model.OCTAVE_BANDS_HZ`.

    Raises :class:`ValueError` per band if pairs are empty/zero, if the per-band
    absorption is zero, or if the per-band ``alpha_bar >= 1``.
    """
    import math

    from roomestim.model import OCTAVE_BANDS_HZ

    s_total: float = sum(area for area, _, _ in pairs)
    if s_total <= 0.0:
        raise ValueError(
            "eyring_rt60_per_band_from_pairs: pairs is empty / S_total is zero"
        )

    out: dict[int, float] = {}
    for band_idx, band_hz in enumerate(OCTAVE_BANDS_HZ):
        weighted_alpha_sum: float = 0.0
        for area, bands, alpha_500 in pairs:
            coefficient = float(bands[band_idx]) if bands is not None else alpha_500
            weighted_alpha_sum += area * coefficient
        if weighted_alpha_sum <= 0.0:
            raise ValueError(
                f"eyring_rt60_per_band_from_pairs: total absorption is zero in band "
                f"{band_hz} Hz; cannot compute finite RT60"
            )
        alpha_bar: float = weighted_alpha_sum / s_total
        if alpha_bar >= 1.0:
            raise ValueError(
                f"eyring_rt60_per_band_from_pairs: alpha_bar={alpha_bar:.4f} >= 1.0 in band "
                f"{band_hz} Hz; Eyring undefined for fully-absorptive alpha_bar"
            )
        out[band_hz] = 0.161 * volume_m3 / (-s_total * math.log(1.0 - alpha_bar))
    return out
