"""Default RT60 predictor — ADR 0030 (v0.15.0).

Selects ISM (rectilinear shoebox) > Eyring (non-shoebox) cascade per ADR 0028
§Reverse-criterion item 2 + D26 forbidden-indefinite-deferral clause. The
v0.14.0 evidence (Office_1 ISM/Sabine = 2.0059 + conference ISM/Sabine = 5.0537)
confirmed signature robustness across ≥ 2 glass-heavy rooms, triggering the
default switch from Sabine to ISM-preferred at v0.15.0.

Public API:
- :func:`is_rectilinear_shoebox` — geometric predicate.
- :func:`predict_rt60_default` — single-band (500 Hz) wrapper.
- :func:`predict_rt60_default_per_band` — per-octave-band wrapper.
- :class:`RT60Prediction` — frozen dataclass return type.

Backwards compatibility: :func:`roomestim.reconstruct.materials.sabine_rt60`
and :func:`roomestim.reconstruct.materials.eyring_rt60` remain available and
unchanged. Callers that want the v0.14.0 Sabine default explicitly should
call those directly.

Layering: this module is core (no web dependency). Geometry helpers
:func:`polygon_area_3d` and :func:`room_volume` are imported from
``roomestim.geom.polygon`` (v0.15.1). The web report
(:mod:`roomestim_web.report`) calls into this module via the public wrappers.

Per-band data fallbacks: when a surface lacks ``absorption_bands`` data, the
per-band path silently falls back to that surface's ``absorption_500hz`` scalar
broadcast across all 6 bands. This matches
:func:`roomestim.reconstruct.materials.eyring_rt60_per_band` behaviour.
v0.15.1부터 fallback 발동 시 surface 이름이 ``RT60Prediction.rationale``에
누적된다 (``predict_rt60_default_per_band`` only; single-band
``predict_rt60_default`` uses 500 Hz scalars throughout and cannot trigger
per-band fallback).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from roomestim.geom.polygon import polygon_area_3d, room_volume
from roomestim.model import MaterialLabel, RoomModel
from roomestim.reconstruct.image_source import image_source_rt60
from roomestim.reconstruct.materials import (
    eyring_rt60,
    eyring_rt60_per_band,
)

PredictorName = Literal["image_source", "eyring"]

__all__ = [
    "PredictorName",
    "RT60Prediction",
    "is_rectilinear_shoebox",
    "predict_rt60_default",
    "predict_rt60_default_per_band",
]


@dataclass(frozen=True)
class RT60Prediction:
    """Result of :func:`predict_rt60_default` / `_per_band`.

    Attributes
    ----------
    rt60_s:
        Predicted RT60 in seconds at 500 Hz (single-band variant) OR the
        500 Hz entry of ``rt60_per_band_s`` (per-band variant).
    rt60_per_band_s:
        Per-octave-band RT60 dict for the per-band variant; empty dict for
        the single-band variant.
    predictor_name:
        ``"image_source"`` if the ISM branch fired (rectilinear shoebox);
        ``"eyring"`` otherwise.
    rationale:
        Short human-readable reason ("shoebox: ISM" / "non-shoebox: Eyring fallback").
    """

    rt60_s: float
    rt60_per_band_s: dict[int, float]
    predictor_name: PredictorName
    rationale: str


# --------------------------------------------------------------------------- #
# Public predicates + wrappers
# --------------------------------------------------------------------------- #


def is_rectilinear_shoebox(room: RoomModel) -> bool:
    """True iff ``room.floor_polygon`` is a 4-point axis-aligned rectangle.

    Shoebox detection criterion: exactly 4 floor-polygon vertices with
    exactly 2 unique x-coordinates and 2 unique z-coordinates (rounded to
    6 decimals). Matches the ``_is_rectilinear_shoebox`` predicate in
    :mod:`roomestim_web.binaural` line 97 — duplicated here to avoid a web
    dependency from core. Any rotation off-axis breaks the predicate
    (n_unique > 2), which is the intended behaviour: ISM
    (:func:`roomestim.reconstruct.image_source.image_source_rt60`) is
    shoebox-only at v0.15.0 per OQ-23.
    """
    pts = room.floor_polygon
    if len(pts) != 4:
        return False
    unique_x = {round(p.x, 6) for p in pts}
    unique_z = {round(p.z, 6) for p in pts}
    return len(unique_x) == 2 and len(unique_z) == 2


def _shoebox_dimensions_m(room: RoomModel) -> tuple[float, float, float]:
    """Extract ``(L, W, H)`` from a confirmed rectilinear-shoebox room."""
    pts = room.floor_polygon
    xs = sorted({round(p.x, 6) for p in pts})
    zs = sorted({round(p.z, 6) for p in pts})
    L = abs(xs[1] - xs[0])
    W = abs(zs[1] - zs[0])
    H = float(room.ceiling_height_m)
    return (L, W, H)


def _shoebox_surface_areas_and_alphas(
    room: RoomModel,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Return (areas_6, alphas_6) parallel arrays at 500 Hz for ISM.

    Index convention: ``(floor, ceiling, wall_x_neg, wall_x_pos, wall_y_neg, wall_y_pos)``.
    Wall α is the area-weighted average across all ``kind == "wall"`` surfaces
    in ``room.surfaces``. Per-wall α decomposition is OQ-30 NEW.
    """
    L, W, H = _shoebox_dimensions_m(room)
    areas = (L * W, L * W, L * H, L * H, W * H, W * H)

    floor_surf = next((s for s in room.surfaces if s.kind == "floor"), None)
    ceil_surf = next((s for s in room.surfaces if s.kind == "ceiling"), None)
    walls = [s for s in room.surfaces if s.kind == "wall"]

    floor_alpha = float(floor_surf.absorption_500hz) if floor_surf else 0.10
    ceil_alpha = float(ceil_surf.absorption_500hz) if ceil_surf else 0.10
    if walls:
        total_area = sum(polygon_area_3d(w.polygon) for w in walls)
        if total_area > 0.0:
            wall_alpha = sum(
                float(w.absorption_500hz) * polygon_area_3d(w.polygon) for w in walls
            ) / total_area
        else:
            wall_alpha = 0.10
    else:
        wall_alpha = 0.10

    alphas = (floor_alpha, ceil_alpha, wall_alpha, wall_alpha, wall_alpha, wall_alpha)
    return areas, alphas


def _shoebox_per_band_alphas(
    room: RoomModel,
) -> tuple[tuple[float, ...], dict[int, tuple[float, ...]], tuple[str, ...]]:
    """Return (areas_6, {band_hz: alphas_6}, fallback_surfaces) for per-band ISM.

    Bands without per-band data on a surface fall back to that surface's
    500 Hz scalar (broadcast across bands), matching
    :func:`roomestim.reconstruct.materials.eyring_rt60_per_band` behavior.

    The third element is a sorted tuple of surface names (e.g. ``"floor"``,
    ``"ceiling"``, ``"wall_0"``) where the 500 Hz fallback fired for at least
    one band. Empty tuple when all surfaces have full per-band data.
    """
    from roomestim.model import OCTAVE_BANDS_HZ

    L, W, H = _shoebox_dimensions_m(room)
    areas = (L * W, L * W, L * H, L * H, W * H, W * H)

    floor_surf = next((s for s in room.surfaces if s.kind == "floor"), None)
    ceil_surf = next((s for s in room.surfaces if s.kind == "ceiling"), None)
    # Wall index in fallback names ("wall_0", "wall_1", …) is positional within
    # this filtered list, not a stable surface ID. Stable per call; not stable
    # across mutations of room.surfaces ordering. See v0.15.1 code-review
    # MEDIUM-1 — promotion to a stable surf.id is OQ-31 follow-up if needed.
    walls = [s for s in room.surfaces if s.kind == "wall"]

    fallback_set: set[str] = set()

    def _band_alpha(surf: object, name: str, band_idx: int) -> float:
        if surf is None:
            return 0.10
        bands = getattr(surf, "absorption_bands", None)
        if bands is not None:
            return float(bands[band_idx])
        fallback_set.add(name)
        return float(getattr(surf, "absorption_500hz", 0.10))

    out: dict[int, tuple[float, ...]] = {}
    for band_idx, band_hz in enumerate(OCTAVE_BANDS_HZ):
        f_a = _band_alpha(floor_surf, "floor", band_idx)
        c_a = _band_alpha(ceil_surf, "ceiling", band_idx)
        if walls:
            total_area = sum(polygon_area_3d(w.polygon) for w in walls)
            if total_area > 0.0:
                w_a = sum(
                    _band_alpha(w, f"wall_{i}", band_idx) * polygon_area_3d(w.polygon)
                    for i, w in enumerate(walls)
                ) / total_area
            else:
                w_a = 0.10
        else:
            w_a = 0.10
        out[band_hz] = (f_a, c_a, w_a, w_a, w_a, w_a)
    return areas, out, tuple(sorted(fallback_set))


def predict_rt60_default(
    room: RoomModel,
    surface_areas_by_material: dict[MaterialLabel, float],
    *,
    prefer_ism: bool = True,
    max_order: int = 50,
) -> RT60Prediction:
    """ADR 0030 default predictor — ISM (shoebox) > Eyring (non-shoebox).

    Parameters
    ----------
    room:
        Parsed :class:`roomestim.model.RoomModel`.
    surface_areas_by_material:
        ``dict[MaterialLabel, float]`` mapping (area sums per material).
        Used by the Eyring fallback when ISM cannot fire.
    prefer_ism:
        If False, skip the ISM branch and always use Eyring (escape hatch).
    max_order:
        ISM L1-lattice max order; default 50.

    Returns
    -------
    RT60Prediction
        ``predictor_name`` is ``"image_source"`` iff the ISM branch fired,
        else ``"eyring"``. ``rt60_per_band_s`` is empty for this single-band
        variant (use :func:`predict_rt60_default_per_band`).
    """
    volume_m3 = room_volume(room)

    if prefer_ism and is_rectilinear_shoebox(room):
        dims = _shoebox_dimensions_m(room)
        areas, alphas = _shoebox_surface_areas_and_alphas(room)
        rt60 = image_source_rt60(
            volume_m3=volume_m3,
            dimensions_m=dims,
            surface_areas=areas,
            absorption_coeffs=alphas,
            max_order=max_order,
        )
        return RT60Prediction(
            rt60_s=rt60,
            rt60_per_band_s={},
            predictor_name="image_source",
            rationale=f"shoebox L={dims[0]:.2f} W={dims[1]:.2f} H={dims[2]:.2f}: ISM (max_order={max_order})",
        )

    rt60 = eyring_rt60(volume_m3, surface_areas_by_material)
    return RT60Prediction(
        rt60_s=rt60,
        rt60_per_band_s={},
        predictor_name="eyring",
        rationale="non-shoebox or prefer_ism=False: Eyring fallback",
    )


def predict_rt60_default_per_band(
    room: RoomModel,
    surface_areas_by_material: dict[MaterialLabel, float],
    *,
    prefer_ism: bool = True,
    max_order: int = 50,
) -> RT60Prediction:
    """Per-octave-band variant of :func:`predict_rt60_default`."""
    volume_m3 = room_volume(room)

    if prefer_ism and is_rectilinear_shoebox(room):
        dims = _shoebox_dimensions_m(room)
        areas, per_band_alphas, fallback_surfaces = _shoebox_per_band_alphas(room)
        rt60_band: dict[int, float] = {}
        for band_hz, alphas in per_band_alphas.items():
            rt60_band[band_hz] = image_source_rt60(
                volume_m3=volume_m3,
                dimensions_m=dims,
                surface_areas=areas,
                absorption_coeffs=alphas,
                max_order=max_order,
            )
        rationale = f"shoebox L={dims[0]:.2f} W={dims[1]:.2f} H={dims[2]:.2f}: per-band ISM (max_order={max_order})"
        if fallback_surfaces:
            rationale += f"; per-band α fallback used for surfaces: [{', '.join(fallback_surfaces)}]"
        return RT60Prediction(
            rt60_s=rt60_band.get(500, 0.0),
            rt60_per_band_s=rt60_band,
            predictor_name="image_source",
            rationale=rationale,
        )

    rt60_band = eyring_rt60_per_band(volume_m3, surface_areas_by_material)
    return RT60Prediction(
        rt60_s=rt60_band.get(500, 0.0),
        rt60_per_band_s=rt60_band,
        predictor_name="eyring",
        rationale="non-shoebox or prefer_ism=False: per-band Eyring fallback",
    )
