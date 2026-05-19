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
from roomestim.model import (
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    Object,
    Point3,
    RoomModel,
    Surface,
)
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
    *,
    extra_surfaces: list[Surface] | None = None,
    wall_overrides: dict[int, list[tuple[float, MaterialLabel]]] | None = None,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Return (areas_6, alphas_6) parallel arrays at 500 Hz for ISM.

    Index convention: ``(floor, ceiling, wall_x_neg, wall_x_pos, wall_y_neg, wall_y_pos)``.
    Wall α is the area-weighted average across all ``kind == "wall"`` surfaces
    in ``room.surfaces``. Per-wall α decomposition is OQ-30 NEW.

    Parameters
    ----------
    extra_surfaces:
        Additional surfaces (e.g. from :func:`_objects_to_surfaces`) folded
        into the area-weighted wall / ceiling averages. ``kind == "wall"``
        rows merge with the wall α; ``kind == "ceiling"`` rows merge with the
        ceiling α. ``kind == "floor"`` rows merge with the floor α.
    wall_overrides:
        ``{wall_index: [(area_m2, material), ...]}`` from
        :func:`_objects_to_wall_alpha_overrides` (door / window α patches).
        Currently applied as a global wall-α blend (per-wall decomposition is
        OQ-30 deferred): the override areas are pooled and the resulting α
        blends against the area-weighted base wall α.
    """
    L, W, H = _shoebox_dimensions_m(room)
    areas = (L * W, L * W, L * H, L * H, W * H, W * H)

    floor_surfs = [s for s in room.surfaces if s.kind == "floor"]
    ceil_surfs = [s for s in room.surfaces if s.kind == "ceiling"]
    walls = [s for s in room.surfaces if s.kind == "wall"]

    if extra_surfaces:
        for extra in extra_surfaces:
            if extra.kind == "floor":
                floor_surfs.append(extra)
            elif extra.kind == "ceiling":
                ceil_surfs.append(extra)
            elif extra.kind == "wall":
                walls.append(extra)

    def _area_weighted_alpha(surfs: list[Surface], default: float = 0.10) -> float:
        if not surfs:
            return default
        total = sum(polygon_area_3d(s.polygon) for s in surfs)
        if total <= 0.0:
            return default
        return sum(
            float(s.absorption_500hz) * polygon_area_3d(s.polygon) for s in surfs
        ) / total

    floor_alpha = _area_weighted_alpha(floor_surfs)
    ceil_alpha = _area_weighted_alpha(ceil_surfs)
    wall_alpha = _area_weighted_alpha(walls)

    if wall_overrides:
        # Pool override areas across all walls; blend with base wall α.
        # Total wall area = L*H + L*H + W*H + W*H = 2*(L+W)*H.
        total_wall_area = 2.0 * (L + W) * H
        override_area_sum = 0.0
        override_sabins = 0.0
        for entries in wall_overrides.values():
            for area_m2, mat in entries:
                a = float(MaterialAbsorption[mat])
                override_area_sum += area_m2
                override_sabins += area_m2 * a
        if total_wall_area > 0.0 and override_area_sum > 0.0:
            frac = min(override_area_sum / total_wall_area, 1.0)
            override_alpha = override_sabins / override_area_sum
            wall_alpha = wall_alpha * (1.0 - frac) + override_alpha * frac

    alphas = (floor_alpha, ceil_alpha, wall_alpha, wall_alpha, wall_alpha, wall_alpha)
    return areas, alphas


# --------------------------------------------------------------------------- #
# v0.17 object-aware helpers (ADR 0034 §C + D46 + D47)
# --------------------------------------------------------------------------- #


def _objects_to_surfaces(objects: list[Object]) -> list[Surface]:
    """Convert column objects into 5-face surface lists (4 sides + top).

    Door/window objects do NOT produce new surfaces — those become wall α
    overrides via :func:`_objects_to_wall_alpha_overrides`.

    Column orientation: anchor = base center on floor; faces emitted CCW
    when viewed from outside the column. Top face (kind=="ceiling") is
    CCW when viewed from above. Material defaults flow through from
    :data:`MaterialAbsorption` / :data:`MaterialAbsorptionBands`.
    """
    extra: list[Surface] = []
    for obj in objects:
        if obj.kind != "column":
            continue
        cx, cy, cz = obj.anchor.x, obj.anchor.y, obj.anchor.z
        hw = obj.width_m / 2.0
        hd = obj.depth_m / 2.0
        # Base CCW (viewed from above): SW, SE, NE, NW
        base_corners = [
            Point3(cx - hw, cy, cz - hd),
            Point3(cx + hw, cy, cz - hd),
            Point3(cx + hw, cy, cz + hd),
            Point3(cx - hw, cy, cz + hd),
        ]
        top_corners = [
            Point3(p.x, p.y + obj.height_m, p.z) for p in base_corners
        ]
        alpha_500 = MaterialAbsorption[obj.material]
        alpha_bands = MaterialAbsorptionBands[obj.material]
        # 4 vertical side faces (kind=="wall"). CCW from outside of column =
        # base[i] -> base[j] -> top[j] -> top[i].
        for i in range(4):
            j = (i + 1) % 4
            extra.append(
                Surface(
                    kind="wall",
                    polygon=[
                        base_corners[i],
                        base_corners[j],
                        top_corners[j],
                        top_corners[i],
                    ],
                    material=obj.material,
                    absorption_500hz=alpha_500,
                    absorption_bands=alpha_bands,
                )
            )
        # Top face (kind=="ceiling"). CCW viewed from above (i.e. from
        # outside-and-above the column).
        extra.append(
            Surface(
                kind="ceiling",
                polygon=list(top_corners),
                material=obj.material,
                absorption_500hz=alpha_500,
                absorption_bands=alpha_bands,
            )
        )
    return extra


def _objects_to_wall_alpha_overrides(
    objects: list[Object],
    walls: list[Surface],
) -> dict[int, list[tuple[float, MaterialLabel]]]:
    """Convert door / window objects into per-wall α overrides.

    Returns ``{wall_index: [(area_m2, material), ...]}``. Validates that the
    total override area on any wall does not exceed that wall's area.

    Raises
    ------
    ValueError
        When ``sum(override_area) > wall_area`` on any single wall.
    """
    overrides: dict[int, list[tuple[float, MaterialLabel]]] = {}
    for obj in objects:
        if obj.kind not in ("door", "window"):
            continue
        if obj.wall_index is None:
            continue
        area = float(obj.width_m) * float(obj.height_m)
        if area <= 0.0:
            continue
        overrides.setdefault(obj.wall_index, []).append((area, obj.material))

    for wall_idx, entries in overrides.items():
        if not (0 <= wall_idx < len(walls)):
            raise ValueError(
                f"object wall_index={wall_idx} out of range "
                f"[0, {len(walls)}); cannot apply α override."
            )
        wall_area = polygon_area_3d(walls[wall_idx].polygon)
        total_override_area = sum(a for a, _ in entries)
        if total_override_area > wall_area + 1e-6:
            raise ValueError(
                f"object α overrides on wall_index={wall_idx} sum to "
                f"{total_override_area:.4f} m^2 which exceeds wall area "
                f"{wall_area:.4f} m^2."
            )
    return overrides


def _shoebox_per_band_alphas(
    room: RoomModel,
    *,
    extra_surfaces: list[Surface] | None = None,
    wall_overrides: dict[int, list[tuple[float, MaterialLabel]]] | None = None,
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

    floor_surfs = [s for s in room.surfaces if s.kind == "floor"]
    ceil_surfs = [s for s in room.surfaces if s.kind == "ceiling"]
    # Wall index in fallback names ("wall_0", "wall_1", …) is positional within
    # this filtered list, not a stable surface ID. Stable per call; not stable
    # across mutations of room.surfaces ordering. See v0.15.1 code-review
    # MEDIUM-1 — promotion to a stable surf.id is OQ-31 follow-up if needed.
    walls = [s for s in room.surfaces if s.kind == "wall"]

    extra_floor: list[Surface] = []
    extra_ceil: list[Surface] = []
    extra_wall: list[Surface] = []
    if extra_surfaces:
        for extra in extra_surfaces:
            if extra.kind == "floor":
                extra_floor.append(extra)
            elif extra.kind == "ceiling":
                extra_ceil.append(extra)
            elif extra.kind == "wall":
                extra_wall.append(extra)

    fallback_set: set[str] = set()

    def _band_alpha(surf: Surface | None, name: str, band_idx: int) -> float:
        if surf is None:
            return 0.10
        bands = surf.absorption_bands
        if bands is not None:
            return float(bands[band_idx])
        fallback_set.add(name)
        return float(surf.absorption_500hz)

    def _area_weighted_band(
        surfs: list[Surface],
        prefix: str,
        band_idx: int,
        *,
        default: float = 0.10,
    ) -> float:
        if not surfs:
            return default
        total_area = sum(polygon_area_3d(s.polygon) for s in surfs)
        if total_area <= 0.0:
            return default
        return sum(
            _band_alpha(s, f"{prefix}_{i}", band_idx) * polygon_area_3d(s.polygon)
            for i, s in enumerate(surfs)
        ) / total_area

    # Total wall area for override blending.
    total_base_wall_area = 2.0 * (L + W) * H

    # Pre-compute override band-α: blends one fractional area on every wall row.
    def _wall_alpha_with_overrides(base: float, band_idx: int) -> float:
        if not wall_overrides:
            return base
        override_area_sum = 0.0
        # per-band sabin equivalent for the override patches
        override_sabins = 0.0
        for entries in wall_overrides.values():
            for area_m2, mat in entries:
                bands = MaterialAbsorptionBands.get(mat)
                if bands is not None:
                    a = float(bands[band_idx])
                else:
                    a = float(MaterialAbsorption[mat])
                override_area_sum += area_m2
                override_sabins += area_m2 * a
        if total_base_wall_area <= 0.0 or override_area_sum <= 0.0:
            return base
        frac = min(override_area_sum / total_base_wall_area, 1.0)
        override_alpha = override_sabins / override_area_sum
        return base * (1.0 - frac) + override_alpha * frac

    out: dict[int, tuple[float, ...]] = {}
    for band_idx, band_hz in enumerate(OCTAVE_BANDS_HZ):
        # Floor: merge room floors with extra floor objects (none typical).
        f_combined = floor_surfs + extra_floor
        f_a = _area_weighted_band(f_combined, "floor", band_idx) if f_combined else 0.10
        # Ceiling: merge room ceilings with column-top extra surfaces.
        c_combined = ceil_surfs + extra_ceil
        c_a = _area_weighted_band(c_combined, "ceiling", band_idx) if c_combined else 0.10
        # Walls: merge room walls with column side-face extras + apply door/window overrides.
        w_combined = walls + extra_wall
        w_a_base = _area_weighted_band(w_combined, "wall", band_idx) if w_combined else 0.10
        w_a = _wall_alpha_with_overrides(w_a_base, band_idx)
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
        objects = list(room.objects)
        column_count = sum(1 for o in objects if o.kind == "column")
        override_count = sum(
            1 for o in objects if o.kind in ("door", "window") and o.wall_index is not None
        )
        try:
            extras = _objects_to_surfaces(objects) if objects else None
            base_walls = [s for s in room.surfaces if s.kind == "wall"]
            overrides = (
                _objects_to_wall_alpha_overrides(objects, base_walls)
                if objects
                else None
            )
            areas, alphas = _shoebox_surface_areas_and_alphas(
                room,
                extra_surfaces=extras,
                wall_overrides=overrides,
            )
            rt60 = image_source_rt60(
                volume_m3=volume_m3,
                dimensions_m=dims,
                surface_areas=areas,
                absorption_coeffs=alphas,
                max_order=max_order,
            )
        except (ValueError, IndexError) as exc:
            # Robust guard (D47): column / override ISM mapping failed —
            # fall back to Eyring with explanatory rationale.
            rt60 = eyring_rt60(volume_m3, surface_areas_by_material)
            return RT60Prediction(
                rt60_s=rt60,
                rt60_per_band_s={},
                predictor_name="eyring",
                rationale=(
                    f"shoebox L={dims[0]:.2f} W={dims[1]:.2f} H={dims[2]:.2f}: "
                    f"objects present, ISM fallback to Eyring ({type(exc).__name__})"
                ),
            )
        rationale = (
            f"shoebox L={dims[0]:.2f} W={dims[1]:.2f} H={dims[2]:.2f}: "
            f"ISM (max_order={max_order})"
        )
        if column_count:
            rationale += f"; objects: +{column_count * 5} column surfaces"
        if override_count:
            rationale += f"; objects: +{override_count} wall α overrides"
        return RT60Prediction(
            rt60_s=rt60,
            rt60_per_band_s={},
            predictor_name="image_source",
            rationale=rationale,
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
        objects = list(room.objects)
        column_count = sum(1 for o in objects if o.kind == "column")
        override_count = sum(
            1 for o in objects if o.kind in ("door", "window") and o.wall_index is not None
        )
        try:
            extras = _objects_to_surfaces(objects) if objects else None
            base_walls = [s for s in room.surfaces if s.kind == "wall"]
            overrides = (
                _objects_to_wall_alpha_overrides(objects, base_walls)
                if objects
                else None
            )
            areas, per_band_alphas, fallback_surfaces = _shoebox_per_band_alphas(
                room,
                extra_surfaces=extras,
                wall_overrides=overrides,
            )
            rt60_band: dict[int, float] = {}
            for band_hz, alphas in per_band_alphas.items():
                rt60_band[band_hz] = image_source_rt60(
                    volume_m3=volume_m3,
                    dimensions_m=dims,
                    surface_areas=areas,
                    absorption_coeffs=alphas,
                    max_order=max_order,
                )
        except (ValueError, IndexError) as exc:
            # Robust guard (D47): column / override ISM mapping failed.
            rt60_band_fb = eyring_rt60_per_band(volume_m3, surface_areas_by_material)
            return RT60Prediction(
                rt60_s=rt60_band_fb.get(500, 0.0),
                rt60_per_band_s=rt60_band_fb,
                predictor_name="eyring",
                rationale=(
                    f"shoebox L={dims[0]:.2f} W={dims[1]:.2f} H={dims[2]:.2f}: "
                    f"objects present, per-band ISM fallback to Eyring "
                    f"({type(exc).__name__})"
                ),
            )
        rationale = (
            f"shoebox L={dims[0]:.2f} W={dims[1]:.2f} H={dims[2]:.2f}: "
            f"per-band ISM (max_order={max_order})"
        )
        if fallback_surfaces:
            rationale += (
                f"; per-band α fallback used for surfaces: "
                f"[{', '.join(fallback_surfaces)}]"
            )
        if column_count:
            rationale += f"; objects: +{column_count * 5} column surfaces"
        if override_count:
            rationale += f"; objects: +{override_count} wall α overrides"
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
