"""Room-aware AVIXA-style distributed-ceiling coverage grid (B1).

Given a room **floor polygon** + **ceiling height** + ear height + a nominal
loudspeaker dispersion angle + an overlap mode, this module deterministically
computes a square OR hexagonal lattice of ceiling-speaker positions, clips it to
the footprint polygon (shapely), and returns a :class:`CoverageGridResult`
carrying the coverage geometry (radius, diameter, spacing, counts, grid type,
overlap fraction).

It is a **DETERMINISTIC GEOMETRIC layout only** — it is wholly distinct from the
listener-centric VBAP/DBAP/WFS/ambisonics rendering rigs. It makes NO
acoustic-performance / SPL claim and does NOT verify the AVIXA +/-3 dB coverage
uniformity criterion (that is B2, deferred). The single source of truth for that
framing is :data:`COVERAGE_GRID_NOTE`; it is referenced (never retyped) by the
result ``note`` field, :func:`coverage_to_dict`, :func:`format_coverage_lines`,
and the CLI.

Geometry (AVIXA Audio Coverage Uniformity, formerly InfoComm 1M:2012)::

    effective_dispersion = nominal_dispersion * EFFECTIVE_DISPERSION_FACTOR (0.75)
    coverage_radius      = (ceiling_height - ear_height) * tan(effective/2)
    coverage_diameter    = 2 * coverage_radius
    spacing (S)          = 2 * coverage_radius * (1 - overlap_fraction)

Lattice / inset rule (honest, documented): speaker centers lie on the closed
interval ``[minx + S/2, maxx - S/2]`` x ``[minz + S/2, maxz - S/2]`` of the
footprint AABB — i.e. the FIRST and LAST speaker on each axis sit half a spacing
``S/2`` from the footprint edge (the AVIXA wall-inset rule; mirrors the
:data:`COVERAGE_GRID_NOTE`). The square grid steps ``S`` on both axes; the hex
grid steps ``S`` along x and ``S*sqrt(3)/2`` along z with odd rows offset by
``S/2``. Nodes are emitted in row-major (z then x) order, so the result is fully
deterministic (no randomness, no set-ordering ambiguity).

Inclusion rule (EXACT, documented verbatim): a lattice point ``(x, z)`` is kept
iff its floor-projected coverage **centroid** lies inside or within
``edge_inclusion_tol_m`` of the footprint polygon —
``poly.covers(ShapelyPoint(x, z)) or poly.buffer(tol).covers(ShapelyPoint(x, z))``
(``covers`` includes the boundary; the tiny buffer absorbs float noise, mirroring
the ``inset.buffer(1e-9).contains(...)`` idiom in :mod:`roomestim.place.dbap`).
B1 deliberately uses **centroid-in-polygon**, NOT circle-area-overlap: near a
concave re-entrant notch a kept speaker's coverage circle may overhang the wall —
that is honestly stated in the NOTE and is NOT an acoustic claim.

Tiny-room / empty-grid fallback (>=1 speaker guarantee): when the footprint is
smaller than one spacing on an axis, or every lattice node falls outside a
concave footprint, exactly ONE speaker is placed at ``poly.representative_point()``
(shapely guarantees it lies inside, unlike the centroid for concave shapes).

Ceiling speakers aim straight down (``aim_direction = Point3(0, -1, 0)``) — these
are distributed downward-firing ceiling cans, NOT a listener-aimed ring.

numpy is NOT required: the bounded lattice is generated with deterministic stdlib
``math`` loops; only shapely is used (both already core deps). Import-safe at
``import roomestim`` time (core/torch-free boundary).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.model import (
    PlacedSpeaker,
    PlacementResult,
    Point2,
    Point3,
    RoomModel,
    assert_finite,
)
from roomestim.place.algorithm import TargetAlgorithm

__all__ = [
    "COVERAGE_GRID_NOTE",
    "CoverageGridResult",
    "GridType",
    "OverlapMode",
    "OVERLAP_FRACTION",
    "EFFECTIVE_DISPERSION_FACTOR",
    "DEFAULT_NOMINAL_DISPERSION_DEG",
    "DEFAULT_EAR_HEIGHT_M",
    "place_coverage_grid",
    "place_coverage_grid_for_room",
    "coverage_to_dict",
    "format_coverage_lines",
    "coverage_result_to_placement",
]


# --------------------------------------------------------------------------- #
# Honesty NOTE — single source of truth (reference, never retype)
# --------------------------------------------------------------------------- #

COVERAGE_GRID_NOTE: str = (
    "Geometric ceiling-coverage grid only — NO acoustic-performance or SPL claim. "
    "Speaker positions are placed on a square or hexagonal lattice on the ceiling "
    "plane and clipped to the room floor polygon, using the AVIXA-style geometric "
    "coverage model (AVIXA Audio Coverage Uniformity, formerly InfoComm 1M:2012): "
    "coverage_radius = (ceiling_height - ear_height) * tan(effective_dispersion/2), "
    "effective_dispersion = nominal_dispersion * 0.75, center-to-center spacing = "
    "2 * coverage_radius * (1 - overlap_fraction), first/last speaker half a spacing "
    "from the footprint edge. It is a DETERMINISTIC GEOMETRIC layout: it does NOT "
    "compute sound pressure level, does NOT verify the AVIXA +/-3 dB uniformity "
    "criterion (that requires an SPL/coverage simulation — deferred to B2), assumes "
    "an idealized circular cone of the stated effective dispersion, and makes NO "
    "claim about a real loudspeaker's polar response. Coverage radius/spacing are "
    "nominal geometry, not a measurement. The nominal dispersion angle is a "
    "user-supplied datasheet value, not inferred from the room."
)


# --------------------------------------------------------------------------- #
# Public constants + type aliases
# --------------------------------------------------------------------------- #

GridType = Literal["square", "hex"]
OverlapMode = Literal["background", "speech"]

#: Effective-to-nominal dispersion derate (AVIXA rule of thumb; research §1A).
EFFECTIVE_DISPERSION_FACTOR: float = 0.75
#: Overlap fraction by mode (center-to-center spacing = 2R*(1-overlap)).
OVERLAP_FRACTION: dict[OverlapMode, float] = {
    "background": 0.15,  # background music: 15% overlap (research §1C)
    "speech": 0.23,      # speech intelligibility: midpoint of 20-25% band (§1C)
}
DEFAULT_NOMINAL_DISPERSION_DEG: float = 90.0  # typical full-range ceiling cone
DEFAULT_EAR_HEIGHT_M: float = 1.20            # matches ListenerArea default

#: Absolute tolerance (m) absorbing float noise on the lattice upper bound so a
#: node landing exactly at ``maxx - S/2`` is not spuriously dropped. Far smaller
#: than any meaningful placement difference.
_LATTICE_EPS_M: float = 1e-9


# --------------------------------------------------------------------------- #
# Result dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CoverageGridResult:
    """Geometric ceiling coverage grid + honesty ``note``. NO acoustic claim.

    All scalars are formula-derived nominal geometry (see
    :data:`COVERAGE_GRID_NOTE`); none is a measurement. ``layout_name`` is carried
    so :func:`coverage_result_to_placement` can wrap the result for the existing
    ``write_layout_yaml`` boundary with one argument.
    """

    speakers: tuple[PlacedSpeaker, ...]  # ceiling positions, channel 1..n
    grid_type: GridType
    overlap_mode: OverlapMode
    overlap_fraction: float
    nominal_dispersion_deg: float
    effective_dispersion_deg: float
    ceiling_height_m: float
    ear_height_m: float
    coverage_radius_m: float
    coverage_diameter_m: float
    center_to_center_spacing_m: float
    n_speakers: int
    footprint_area_m2: float  # shapely polygon area (floor)
    layout_name: str
    note: str  # = COVERAGE_GRID_NOTE


# --------------------------------------------------------------------------- #
# Lattice generation (deterministic; half-spacing inset from BOTH edges)
# --------------------------------------------------------------------------- #


def _square_centers(
    minx: float, minz: float, maxx: float, maxz: float, spacing: float
) -> list[tuple[float, float]]:
    """Square lattice centers in ``[minx+S/2, maxx-S/2] x [minz+S/2, maxz-S/2]``.

    Row-major (z outer, x inner) order. Empty when the footprint AABB is smaller
    than one spacing on either axis (caller falls back to one speaker).
    """
    centers: list[tuple[float, float]] = []
    x_hi = maxx - spacing / 2.0 + _LATTICE_EPS_M
    z_hi = maxz - spacing / 2.0 + _LATTICE_EPS_M
    j = 0
    while True:
        z = minz + spacing / 2.0 + j * spacing
        if z > z_hi:
            break
        i = 0
        while True:
            x = minx + spacing / 2.0 + i * spacing
            if x > x_hi:
                break
            centers.append((x, z))
            i += 1
        j += 1
    return centers


def _hex_centers(
    minx: float, minz: float, maxx: float, maxz: float, spacing: float
) -> list[tuple[float, float]]:
    """Hex lattice centers: row pitch ``S*sqrt(3)/2``, odd rows offset ``S/2``.

    Same half-spacing inset and row-major order as :func:`_square_centers`.
    """
    centers: list[tuple[float, float]] = []
    row_pitch = spacing * math.sqrt(3.0) / 2.0
    x_hi = maxx - spacing / 2.0 + _LATTICE_EPS_M
    z_hi = maxz - spacing / 2.0 + _LATTICE_EPS_M
    j = 0
    while True:
        z = minz + spacing / 2.0 + j * row_pitch
        if z > z_hi:
            break
        x_start = minx + spacing / 2.0 + (spacing / 2.0 if j % 2 == 1 else 0.0)
        i = 0
        while True:
            x = x_start + i * spacing
            if x > x_hi:
                break
            centers.append((x, z))
            i += 1
        j += 1
    return centers


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def place_coverage_grid(
    *,
    floor_polygon: list[Point2],
    ceiling_height_m: float,
    ear_height_m: float = DEFAULT_EAR_HEIGHT_M,
    nominal_dispersion_deg: float = DEFAULT_NOMINAL_DISPERSION_DEG,
    overlap_mode: OverlapMode = "background",
    grid_type: GridType = "square",
    layout_name: str = "coverage_grid",
    edge_inclusion_tol_m: float = 1e-9,
    spacing_scale: float = 1.0,
) -> CoverageGridResult:
    """Compute the geometric ceiling coverage grid (see module docstring + NOTE).

    Deterministic; raises ``ValueError`` on degenerate / non-physical inputs:
    fewer than 3 vertices, a self-intersecting / zero-area polygon, a non-finite
    height/dispersion, a dispersion outside ``(0, 180)``, or
    ``ceiling_height_m <= ear_height_m`` (no coverage geometry — the ceiling must
    be above the ear plane; this single guard also covers a missing/zero ceiling).

    ``spacing_scale`` (default 1.0 → byte-equal with the AVIXA spacing) multiplies
    the center-to-center spacing; values < 1.0 DENSIFY the grid (closing the 2-D
    diagonal gaps the 1-D AVIXA overlap leaves). It is the lever
    :func:`place_coverage_grid_to_target` (B4) tightens to hit a measured coverage
    target. Must be finite and in ``(0, 1]`` — densify only, never sparsen below
    the AVIXA nominal.
    """
    # --- Step 1: validate inputs (fail loud BEFORE any geometry) ----------- #
    if len(floor_polygon) < 3:
        raise ValueError(
            "coverage grid requires a polygon with >=3 vertices"
        )
    poly = ShapelyPolygon([(p.x, p.z) for p in floor_polygon])
    if not poly.is_valid or poly.is_empty or poly.area <= 0.0:
        raise ValueError(
            "degenerate floor polygon (zero area / self-intersecting)"
        )
    assert_finite(ceiling_height_m, field="ceiling_height_m")
    assert_finite(ear_height_m, field="ear_height_m")
    assert_finite(nominal_dispersion_deg, field="nominal_dispersion_deg")
    if not (0.0 < nominal_dispersion_deg < 180.0):
        raise ValueError(
            f"nominal_dispersion_deg must be in (0, 180), got {nominal_dispersion_deg}"
        )
    if ceiling_height_m <= ear_height_m:
        raise ValueError(
            "ceiling_height_m <= ear_height_m: no coverage geometry (ceiling "
            "must be above the ear plane)"
        )
    if overlap_mode not in OVERLAP_FRACTION:
        raise ValueError(
            f"overlap_mode must be one of {sorted(OVERLAP_FRACTION)}, got "
            f"{overlap_mode!r}"
        )
    if grid_type not in ("square", "hex"):
        raise ValueError(
            f"grid_type must be 'square' or 'hex', got {grid_type!r}"
        )
    assert_finite(spacing_scale, field="spacing_scale")
    if not (0.0 < spacing_scale <= 1.0):
        raise ValueError(
            f"spacing_scale must be in (0, 1] (densify only), got {spacing_scale}"
        )

    # --- Step 2: coverage geometry ---------------------------------------- #
    eff_deg = nominal_dispersion_deg * EFFECTIVE_DISPERSION_FACTOR
    radius_m = (ceiling_height_m - ear_height_m) * math.tan(math.radians(eff_deg / 2.0))
    diameter_m = 2.0 * radius_m
    overlap = OVERLAP_FRACTION[overlap_mode]
    spacing_m = 2.0 * radius_m * (1.0 - overlap) * spacing_scale
    # Valid inputs (ceiling>ear, 0<disp<180, overlap in {0.15,0.23}) => spacing>0.
    if spacing_m <= 0.0:
        raise ValueError(
            f"non-positive center-to-center spacing ({spacing_m}); check inputs"
        )

    # --- Step 3: lattice seeding (half-spacing inset from both edges) ------ #
    minx, minz, maxx, maxz = poly.bounds
    if grid_type == "square":
        centers = _square_centers(minx, minz, maxx, maxz, spacing_m)
    else:
        centers = _hex_centers(minx, minz, maxx, maxz, spacing_m)

    # --- Step 4: polygon clipping (EXACT centroid-in-polygon inclusion) ---- #
    poly_buffered = poly.buffer(edge_inclusion_tol_m)
    kept: list[tuple[float, float]] = [
        (x, z)
        for (x, z) in centers
        if poly.covers(ShapelyPoint(x, z))
        or poly_buffered.covers(ShapelyPoint(x, z))
    ]

    # --- Step 5: tiny-room / empty-grid fallback (>=1 speaker) ------------- #
    if not kept:
        rep = poly.representative_point()  # guaranteed interior, incl. concave
        kept = [(float(rep.x), float(rep.y))]

    # --- Step 6: lift to ceiling + build speakers (aim straight down) ------ #
    speakers = tuple(
        PlacedSpeaker(
            channel=i + 1,
            position=Point3(x=x, y=ceiling_height_m, z=z),
            aim_direction=Point3(0.0, -1.0, 0.0),
        )
        for i, (x, z) in enumerate(kept)
    )

    # --- Step 7: return result -------------------------------------------- #
    return CoverageGridResult(
        speakers=speakers,
        grid_type=grid_type,
        overlap_mode=overlap_mode,
        overlap_fraction=overlap,
        nominal_dispersion_deg=nominal_dispersion_deg,
        effective_dispersion_deg=eff_deg,
        ceiling_height_m=ceiling_height_m,
        ear_height_m=ear_height_m,
        coverage_radius_m=radius_m,
        coverage_diameter_m=diameter_m,
        center_to_center_spacing_m=spacing_m,
        n_speakers=len(speakers),
        footprint_area_m2=float(poly.area),
        layout_name=layout_name,
        note=COVERAGE_GRID_NOTE,
    )


def place_coverage_grid_for_room(
    room: RoomModel,
    *,
    ear_height_m: float | None = None,  # None -> room.listener_area.height_m
    nominal_dispersion_deg: float = DEFAULT_NOMINAL_DISPERSION_DEG,
    overlap_mode: OverlapMode = "background",
    grid_type: GridType = "square",
    layout_name: str = "coverage_grid",
) -> CoverageGridResult:
    """Room-level wrapper: defaults the ear height to ``listener_area.height_m``.

    Reuses the room's :attr:`RoomModel.floor_polygon` + :attr:`ceiling_height_m`.
    The caller (CLI / dispatch) surfaces a ``ceiling_confidence == "low"``
    advisory separately; this function never blocks on it.
    """
    ear = room.listener_area.height_m if ear_height_m is None else ear_height_m
    return place_coverage_grid(
        floor_polygon=room.floor_polygon,
        ceiling_height_m=room.ceiling_height_m,
        ear_height_m=ear,
        nominal_dispersion_deg=nominal_dispersion_deg,
        overlap_mode=overlap_mode,
        grid_type=grid_type,
        layout_name=layout_name,
    )


# --------------------------------------------------------------------------- #
# Serialization helpers (mirror standards.py)
# --------------------------------------------------------------------------- #


def coverage_to_dict(result: CoverageGridResult) -> dict[str, object]:
    """Return a plain JSON-serialisable dict for the ``layout.coverage.json`` sidecar.

    ``"note"`` first (mirrors ``report_to_dict``), then the geometry scalars, then
    a ``"speakers"`` list of ``{channel, x, y, z, aim_x, aim_y, aim_z}``.
    """
    speakers: list[dict[str, object]] = []
    for sp in result.speakers:
        aim = sp.aim_direction if sp.aim_direction is not None else Point3(0.0, 0.0, 0.0)
        speakers.append(
            {
                "channel": sp.channel,
                "x": sp.position.x,
                "y": sp.position.y,
                "z": sp.position.z,
                "aim_x": aim.x,
                "aim_y": aim.y,
                "aim_z": aim.z,
            }
        )
    return {
        "note": result.note,
        "grid_type": result.grid_type,
        "overlap_mode": result.overlap_mode,
        "overlap_fraction": result.overlap_fraction,
        "nominal_dispersion_deg": result.nominal_dispersion_deg,
        "effective_dispersion_deg": result.effective_dispersion_deg,
        "ceiling_height_m": result.ceiling_height_m,
        "ear_height_m": result.ear_height_m,
        "coverage_radius_m": result.coverage_radius_m,
        "coverage_diameter_m": result.coverage_diameter_m,
        "center_to_center_spacing_m": result.center_to_center_spacing_m,
        "n_speakers": result.n_speakers,
        "footprint_area_m2": result.footprint_area_m2,
        "speakers": speakers,
    }


def format_coverage_lines(result: CoverageGridResult) -> list[str]:
    """Return human-readable CLI lines; last line is ``  NOTE: {note}``."""
    return [
        "ceiling coverage grid (geometry only, no acoustic/SPL claim):",
        f"  grid type: {result.grid_type}",
        f"  ceiling height: {result.ceiling_height_m:.3f} m, "
        f"ear height: {result.ear_height_m:.3f} m",
        f"  nominal dispersion: {result.nominal_dispersion_deg:.1f} deg, "
        f"effective: {result.effective_dispersion_deg:.1f} deg",
        f"  coverage radius: {result.coverage_radius_m:.3f} m "
        f"(diameter {result.coverage_diameter_m:.3f} m)",
        f"  center-to-center spacing: {result.center_to_center_spacing_m:.3f} m",
        f"  overlap mode: {result.overlap_mode} ({result.overlap_fraction:.0%})",
        f"  n speakers: {result.n_speakers}",
        f"  footprint area: {result.footprint_area_m2:.2f} m^2",
        f"  NOTE: {result.note}",
    ]


# --------------------------------------------------------------------------- #
# Adapter to the existing layout pipeline (reuse PlacementResult)
# --------------------------------------------------------------------------- #


def coverage_result_to_placement(result: CoverageGridResult) -> PlacementResult:
    """Wrap a :class:`CoverageGridResult` as a :class:`PlacementResult`.

    Lets the existing ``write_layout_yaml`` / ``check_layout_angles`` /
    ``compute_layout_metrics`` surfaces consume the coverage layout unchanged.
    ``regularity_hint`` is ``"PLANAR_GRID"`` when ``n >= 4`` else ``"IRREGULAR"``,
    so the R10 ``min_speaker_count`` gate passes for tiny 1-3-speaker rooms.
    ``target_algorithm = "COVERAGE_GRID"`` (round-trips via the ``x_target_algorithm``
    extension key — VBAP layouts stay byte-equal because the writer only emits that
    key for non-VBAP labels).
    """
    regularity_hint = "PLANAR_GRID" if result.n_speakers >= 4 else "IRREGULAR"
    return PlacementResult(
        target_algorithm=TargetAlgorithm.COVERAGE_GRID.value,
        regularity_hint=regularity_hint,
        speakers=list(result.speakers),
        layout_name=result.layout_name,
    )
