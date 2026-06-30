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
    order: int | None = None,
    coverage_dispersion_deg: float | None = None,
    coverage_ear_height_m: float | None = None,
    coverage_overlap_mode: str = "background",
    coverage_grid_type: str = "square",
) -> PlacementResult:
    """Dispatch to the right placement function and return a PlacementResult.

    Room-geometry awareness (honest disclosure): ``dbap`` and ``coverage`` are
    the room-geometry-aware paths. ``dbap`` consumes the room's actual
    wall/ceiling surfaces + listener area; ``coverage`` consumes the floor
    polygon + ceiling height + ear height to lay an AVIXA-style ceiling grid
    (geometric only, NO acoustic/SPL claim — see ``COVERAGE_GRID_NOTE``).
    ``vbap`` produces a fixed-radius ring and ``wfs`` synthesizes its baseline
    from the layout radius — both are independent of room geometry by
    construction (the room argument is unused for those two paths).
    ``dome`` is likewise geometry-blind like ``vbap`` (the room argument is
    unused); it splits ``n_speakers`` across two stacked equal-angle rings (a
    lower ring at 0° and an upper ring tilted by ``el_deg``) and is reported
    with the conservative ``IRREGULAR`` regularity hint — it is NOT a single
    planar ring nor a calibrated dome, just two stacked rings.
    ``ambisonics`` is likewise geometry-blind like ``vbap`` (the room argument
    is unused; the rig is a fixed regular platonic solid sized by ``order``),
    AND its end-to-end SH decode/route is engine-gated and UNCONFIRMED (see
    ``AMBISONICS_RIG_DISCLOSURE``). Use ``dbap`` or ``coverage`` for
    geometry-aware placement.

    The four ``coverage_*`` keyword arguments are only consumed by the
    ``coverage`` branch and default to the placement's standard behaviour, so
    every existing caller (room-blind vbap/wfs/ambisonics, dbap) is byte-equal.
    """
    if algorithm == "coverage":
        from typing import cast

        from roomestim.place.coverage_grid import (
            DEFAULT_NOMINAL_DISPERSION_DEG,
            GridType,
            OverlapMode,
            coverage_result_to_placement,
            place_coverage_grid_for_room,
        )

        dispersion = (
            DEFAULT_NOMINAL_DISPERSION_DEG
            if coverage_dispersion_deg is None
            else coverage_dispersion_deg
        )
        result = place_coverage_grid_for_room(
            room,
            ear_height_m=coverage_ear_height_m,
            nominal_dispersion_deg=dispersion,
            overlap_mode=cast(OverlapMode, coverage_overlap_mode),
            grid_type=cast(GridType, coverage_grid_type),
        )
        return coverage_result_to_placement(result)

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

    if algorithm == "dome":
        from roomestim.place.vbap import place_vbap_dome

        # Each ring needs >=3 speakers, so the dome needs >=6 total. Pre-validate
        # here for a clear message; place_vbap_dome itself also raises per-ring.
        if n_speakers < 6:
            raise ValueError(
                f"dome requires n_speakers>=6 (two rings of >=3); got {n_speakers}"
            )
        # Lower ring gets the odd extra speaker; upper ring is tilted by el_deg
        # (el_deg <= 0 -> sensible 30° default; a downward/flat upper ring is
        # nonsensical for a dome, so non-positive elevations fall back to 30°).
        n_lower = (n_speakers + 1) // 2
        n_upper = n_speakers // 2
        el_upper_deg = el_deg if el_deg > 0.0 else 30.0
        return place_vbap_dome(
            n_lower=n_lower,
            n_upper=n_upper,
            el_lower_deg=0.0,
            el_upper_deg=el_upper_deg,
            radius_m=layout_radius_m,
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

    if algorithm == "ambisonics":
        if order is None:
            raise ValueError(
                "ambisonics placement requires an Ambisonics decode order; "
                "pass --order {1,2,3} (1=octahedron(6), 2=icosahedron(12), "
                "3=dodecahedron(20))."
            )
        from roomestim.place.ambisonics import place_ambisonics

        return place_ambisonics(order, radius_m=layout_radius_m)

    raise ValueError(f"unknown algorithm: {algorithm!r}")
