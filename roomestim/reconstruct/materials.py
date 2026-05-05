"""Sabine RT60 estimate + Vorlaender 2020 Appx A absorption table re-export.

Used by P4 acceptance criterion A11. The mid-band 500 Hz absorption table is
imported from :mod:`roomestim.model` and re-exported here for callers that
work in the reconstruction layer.

The synthetic-shoebox reference RT60 (D8 / ralplan-iter1-resolutions.md fix 3)
is computed analytically below as the v0.1 acceptance source-of-truth so that
A11 does not depend on a real lab capture.
"""

from __future__ import annotations

from roomestim.model import MaterialAbsorption, MaterialLabel

__all__ = [
    "MaterialAbsorption",
    "MaterialLabel",
    "SABINE_REFERENCE_SHOEBOX_RT60_S",
    "sabine_rt60",
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
