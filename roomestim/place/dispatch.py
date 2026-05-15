"""Placement dispatch — public surface for roomestim_web and other callers.

Extracted from ``roomestim.cli._run_placement`` (Phase P13a refactor).
No behaviour change; the CLI now delegates here.
"""

from __future__ import annotations

import math

from roomestim.model import PlacementResult, RoomModel, Surface


def run_placement(
    room: RoomModel,
    algorithm: str,
    n_speakers: int,
    layout_radius_m: float,
    el_deg: float,
    wfs_f_max_hz: float = 8000.0,
    wfs_spacing_m: float | None = None,
) -> PlacementResult:
    """Dispatch to the right placement function and return a PlacementResult."""
    if algorithm == "vbap":
        from roomestim.place.vbap import place_vbap_ring

        return place_vbap_ring(n_speakers, radius_m=layout_radius_m, el_deg=el_deg)

    if algorithm == "dbap":
        from roomestim.place.dbap import place_dbap

        mount_surfaces: list[Surface] = [
            s for s in room.surfaces if s.kind in ("wall", "ceiling")
        ]
        if not mount_surfaces:
            raise ValueError(
                "DBAP placement requires at least one wall or ceiling surface; "
                "none found in room.yaml."
            )
        return place_dbap(
            mount_surfaces=mount_surfaces,
            n_speakers=n_speakers,
            listener_area=room.listener_area,
        )

    if algorithm == "wfs":
        from roomestim.model import Point2
        from roomestim.place.wfs import c as wfs_c
        from roomestim.place.wfs import place_wfs

        p0 = Point2(x=-layout_radius_m, z=layout_radius_m)
        p1 = Point2(x=layout_radius_m, z=layout_radius_m)
        baseline_len = abs(p1.x - p0.x)
        if wfs_spacing_m is not None:
            spacing_m = float(wfs_spacing_m)
        else:
            spacing_m = (
                baseline_len / max(n_speakers - 1, 1) if n_speakers > 1 else baseline_len
            )
        try:
            return place_wfs(
                baseline_p0=p0,
                baseline_p1=p1,
                spacing_m=spacing_m,
                f_max_hz=wfs_f_max_hz,
            )
        except ValueError as exc:
            # Re-raise with a constructive remediation message at the CLI layer.
            # Library-level place_wfs ValueError contract is unchanged.
            bound = wfs_c / (2.0 * wfs_f_max_hz)
            if spacing_m > bound:
                # Max safe f_max for the *current* (derived or supplied) spacing.
                max_safe_f_max = wfs_c / (2.0 * spacing_m)
                # Min safe n for the *current* f_max_hz, derived from baseline_len.
                # n - 1 >= baseline_len / bound = baseline_len * 2 * f_max / c.
                if baseline_len > 0.0:
                    min_safe_n = int(math.ceil(baseline_len / bound)) + 1
                else:
                    min_safe_n = n_speakers
                raise ValueError(
                    f"WFS spatial-aliasing bound violated: "
                    f"spacing_m={spacing_m:.4f} > c/(2*f_max_hz)={bound:.4f} "
                    f"(c=343.0 m/s, f_max_hz={wfs_f_max_hz}). "
                    f"Either pass --wfs-f-max-hz <X> "
                    f"(max safe --wfs-f-max-hz for current spacing is "
                    f"X = c/(2*spacing_m) = {max_safe_f_max:.2f} Hz) "
                    f"OR pass --n-speakers <Y> "
                    f"(minimum safe --n-speakers for current f_max_hz is "
                    f"Y = ceil(baseline_len/(c/(2*f_max))) + 1 = {min_safe_n})."
                ) from exc
            raise

    raise ValueError(f"unknown algorithm: {algorithm!r}")
