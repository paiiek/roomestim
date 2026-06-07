"""ImageAdapter — single-panorama → RoomModel capture (ADR 0045 §image backend).

A single equirectangular RGB panorama is run through the vendored HorizonNet
layout estimator (the optional ``[vision]`` extra) to recover wall-wall corners,
then a TORCH-FREE trig core converts those corners + a metric camera-height
anchor into a metric floor polygon and ceiling height — exactly the
``ScaleAnchor(known_distance=camera height)`` resolution.

Honesty (ADR 0045 §F):
  * This is an experimental, rough-estimate tier (NOT install-grade; the ≤15 cm
    accuracy budget is reserved for LiDAR/RoomPlan-class depth capture).
  * A Manhattan/gravity-aligned equirectangular panorama is assumed.
  * Scale is either a measured anchor (``scale_anchor``) or an ASSUMED default
    camera height (OQ-58 scale-source disclosure).
  * No visual material inference (§E): floor/ceiling/walls are
    :data:`MaterialLabel.UNKNOWN`. ``provenance="reconstructed"`` (image, no
    depth). ``objects=[]`` (no furniture detection).
  * A near-horizon floor corner blows up ``r = cam_h / tan(-v_floor)``; a corner
    recovered beyond :data:`_MAX_PLAUSIBLE_RADIUS_M` is rejected loudly with a
    ``ValueError`` rather than silently emitting a physically-absurd giant room.

torch boundary (ADR 0045 gate #4): ``import roomestim.adapters.image`` MUST stay
torch-free. ``torch`` and the vendored torch-backed model are imported lazily
inside :func:`_infer_corners` only.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

from roomestim.adapters.base import ScaleAnchor
from roomestim.model import (
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
    canonicalize_ccw,
)
from roomestim.reconstruct._disclosure import IMAGE_CAM_H_SCALE_NOTE
from roomestim.reconstruct.listener_area import default_listener_area
from roomestim.reconstruct.walls import walls_from_floor_polygon

__all__ = ["ImageAdapter"]

# Equirectangular working resolution HorizonNet was trained at.
_PANO_W = 1024
_PANO_H = 512

# Below this floor-ray tangent a corner column is effectively at/above the
# horizon and yields a degenerate (infinite) radius; such columns are skipped.
_MIN_FLOOR_TAN = 1e-6

# A recovered floor corner farther than this from the camera implies a room
# dimension approaching ~40 m, which single-pano HorizonNet-st3d cannot
# reconstruct reliably (near-horizon corner mis-detection blows up
# r = cam_h / tan(-v_floor)). Measured on 240 real panos: legit-room max
# corner-radius p95 = 14.5 m, p99 = 27.9 m. This 20 m bound rejects ~2.9% of
# panos — the absurd near-horizon tail plus a thin slice of genuine p95–p99
# very-large rooms that single-pano st3d cannot reconstruct reliably anyway.
# ADR 0045 honesty: reject loudly, never emit a giant room.
_MAX_PLAUSIBLE_RADIUS_M = 20.0


def _corners_to_room(
    cor_id: list[tuple[float, float]] | object,
    cam_h: float,
    *,
    name: str,
    octave_band: bool = False,
) -> RoomModel:
    """Convert normalized HorizonNet corners + camera height → :class:`RoomModel`.

    TORCH-FREE. ``cor_id`` is a ``(2N, 2)`` array-like of normalized ``(u, v)``
    in ``[0, 1]`` ordered ceiling-then-floor per wall column (HorizonNet order:
    even index = ceiling, odd index = floor). ``cam_h`` is the metric camera
    height above the floor in metres.

    Geometry (mirrors ``spike_metric.metric_layout``): for each floor corner at
    image angle ``u`` and below-horizon elevation ``v_floor < 0``, the
    horizontal radius is ``r = cam_h / tan(-v_floor)`` and the floor point is
    ``x = r·sin(u)``, ``z = -r·cos(u)``. The ceiling above the camera for the
    same column is ``r·tan(v_ceil)`` so the room height is ``cam_h + that``.
    """
    # Torch-free: shapely arrives transitively via canonicalize_ccw /
    # default_listener_area; no torch/model import in this geometry core.
    if cam_h <= 0.0:
        raise ValueError(f"ImageAdapter: cam_h must be > 0, got {cam_h}")

    # Normalize cor_id into a flat list of (u_norm, v_norm) float pairs without
    # requiring numpy at import time (numpy IS available, but we avoid pinning
    # cor_id's concrete type so a mocked list works in-gate).
    pairs = [(float(uv[0]), float(uv[1])) for uv in cor_id]  # type: ignore[union-attr]
    if len(pairs) < 6 or len(pairs) % 2 != 0:
        raise ValueError(
            f"ImageAdapter: expected an even cor_id with >=6 rows "
            f"(>=3 wall columns), got {len(pairs)}"
        )

    ceil_pts = pairs[0::2]
    floor_pts = pairs[1::2]

    floor_polygon_2d: list[Point2] = []
    heights: list[float] = []
    for (u_c_norm, v_c_norm), (u_f_norm, v_f_norm) in zip(ceil_pts, floor_pts):
        # De-normalize to pixel columns/rows then to equirectangular angles.
        # u in (-pi, pi]; v in (-pi/2, pi/2). Floor v < 0 (looking down).
        col = u_f_norm * _PANO_W
        u = ((col + 0.5) / _PANO_W - 0.5) * 2.0 * math.pi
        row_f = v_f_norm * _PANO_H
        v_floor = -((row_f + 0.5) / _PANO_H - 0.5) * math.pi
        row_c = v_c_norm * _PANO_H
        v_ceil = -((row_c + 0.5) / _PANO_H - 0.5) * math.pi

        tan_floor = math.tan(-v_floor)
        if tan_floor <= _MIN_FLOOR_TAN:
            # Degenerate column (corner at/above horizon); skip it.
            continue
        r = cam_h / tan_floor
        if r > _MAX_PLAUSIBLE_RADIUS_M:
            raise ValueError(
                f"ImageAdapter: recovered a floor corner {r:.1f} m from the camera "
                f"(depression angle {math.degrees(-v_floor):.2f}°), exceeding the "
                f"{_MAX_PLAUSIBLE_RADIUS_M:.0f} m single-pano plausibility bound. The "
                f"panorama layout could not be reliably reconstructed (near-horizon "
                f"corner mis-detection); rejected rather than emitting an implausible "
                f"dimension. Use a more accurate --cam-height or a depth-capture backend."
            )
        x = r * math.sin(u)
        z = -r * math.cos(u)
        floor_polygon_2d.append(Point2(x, z))
        heights.append(cam_h + r * math.tan(v_ceil))

    if len(floor_polygon_2d) < 3:
        raise ValueError(
            "ImageAdapter: fewer than 3 valid floor corners after layout "
            "projection; the panorama layout could not be reconstructed."
        )

    floor_polygon_2d = canonicalize_ccw(floor_polygon_2d)

    # Median ceiling height is robust to a single mis-detected column.
    ceiling_height_m = _median(heights)
    if ceiling_height_m <= 0.0:
        raise ValueError(
            f"ImageAdapter: non-positive ceiling height {ceiling_height_m}"
        )

    # §E: NO visual material inference — every surface is UNKNOWN.
    unknown = MaterialLabel.UNKNOWN
    unknown_a500 = MaterialAbsorption[unknown]
    unknown_bands = MaterialAbsorptionBands[unknown] if octave_band else None

    floor_surface = Surface(
        kind="floor",
        polygon=[Point3(p.x, 0.0, p.z) for p in floor_polygon_2d],
        material=unknown,
        absorption_500hz=unknown_a500,
        absorption_bands=unknown_bands,
    )
    ceiling_surface = Surface(
        kind="ceiling",
        polygon=[
            Point3(p.x, ceiling_height_m, p.z) for p in reversed(floor_polygon_2d)
        ],
        material=unknown,
        absorption_500hz=unknown_a500,
        absorption_bands=unknown_bands,
    )
    walls = walls_from_floor_polygon(
        floor_polygon_2d,
        ceiling_height_m,
        default_material=unknown,
        octave_band=octave_band,
    )
    surfaces: list[Surface] = [floor_surface, ceiling_surface, *walls]

    listener = default_listener_area(floor_polygon_2d)

    return RoomModel(
        name=name,
        floor_polygon=floor_polygon_2d,
        ceiling_height_m=ceiling_height_m,
        surfaces=surfaces,
        listener_area=listener,
        objects=[],  # §E: no furniture detection
        schema_version="0.2-draft",
        provenance="reconstructed",  # image-derived, no depth sensor
    )


def _median(values: list[float]) -> float:
    """Median of a non-empty list (avoids a numpy dependency in the core)."""
    if not values:
        raise ValueError("ImageAdapter: empty height list")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _cam_h_sensitivity(
    cor_id: list[tuple[float, float]] | object,
    *,
    ref_cam_h: float,
) -> dict[str, float | None]:
    """Pure-geometry sensitivity of the recovered room scale to ``cam_h``.

    TORCH-FREE and exactly invertible (deterministic). Because every floor point
    is ``r·(sin u, -cos u)`` with ``r = cam_h / tan(-v_floor)``, the entire
    recovered room scales EXACTLY linearly with ``cam_h``: a fractional cam_h
    error maps 1:1 to a fractional room-scale error (and floor area scales with
    its square). This surfaces the dominant image-backend error lever WITHOUT
    inferring an absolute cam_h — a single pano is scale-ambiguous, see
    :data:`IMAGE_CAM_H_SCALE_NOTE`.

    Reported from the recovered corners + a reference cam_h alone (no metric
    anchor needed):

    * ``ref_cam_h_m`` — the reference camera height the report is anchored at.
    * ``max_radius_coeff`` — the largest ``1/tan(-v_floor)`` over valid floor
      columns, i.e. the farthest corner's horizontal radius PER METRE of cam_h
      (``r = max_radius_coeff · cam_h``). ``None`` when no valid floor column.
    * ``max_plausible_cam_h_m`` — the upper bound on cam_h that keeps every
      corner within :data:`_MAX_PLAUSIBLE_RADIUS_M`
      (``_MAX_PLAUSIBLE_RADIUS_M / max_radius_coeff``); ``None`` when no valid
      floor column. Above this the core radius guard rejects the layout.
    * ``scale_pct_per_10cm`` — at ``ref_cam_h``, the room-scale change for a
      10 cm cam_h error (``0.10 / ref_cam_h · 100``); exact, since scale is
      linear in cam_h. This is NOT an accuracy figure — it quantifies how a
      cam_h *assumption* propagates, not how wrong the assumption is.
    """
    if ref_cam_h <= 0.0:
        raise ValueError(f"ImageAdapter: ref_cam_h must be > 0, got {ref_cam_h}")

    pairs = [(float(uv[0]), float(uv[1])) for uv in cor_id]  # type: ignore[union-attr]
    if len(pairs) < 6 or len(pairs) % 2 != 0:
        raise ValueError(
            f"ImageAdapter: expected an even cor_id with >=6 rows "
            f"(>=3 wall columns), got {len(pairs)}"
        )

    floor_pts = pairs[1::2]
    coeffs: list[float] = []
    for _u_f_norm, v_f_norm in floor_pts:
        # Same de-normalization as _corners_to_room: row -> floor depression.
        row_f = v_f_norm * _PANO_H
        v_floor = -((row_f + 0.5) / _PANO_H - 0.5) * math.pi
        tan_floor = math.tan(-v_floor)
        if tan_floor <= _MIN_FLOOR_TAN:
            # Degenerate column (corner at/above horizon); skipped by the core.
            continue
        coeffs.append(1.0 / tan_floor)

    max_radius_coeff = max(coeffs) if coeffs else None
    max_plausible_cam_h_m = (
        _MAX_PLAUSIBLE_RADIUS_M / max_radius_coeff
        if max_radius_coeff is not None and max_radius_coeff > 0.0
        else None
    )
    return {
        "ref_cam_h_m": ref_cam_h,
        "max_radius_coeff": max_radius_coeff,
        "max_plausible_cam_h_m": max_plausible_cam_h_m,
        "scale_pct_per_10cm": 0.10 / ref_cam_h * 100.0,
    }


def _infer_corners(
    pano_path: Path,
    *,
    weights: str,
    accept_noncommercial: bool,
) -> list[tuple[float, float]]:
    """Run the vendored HorizonNet on ``pano_path`` → normalized ``cor_id``.

    TORCH PATH. ``torch``, the vendored :class:`HorizonNet`, and the post-proc
    helpers are imported lazily here so the module stays torch-free on import.
    Raises a clear :class:`ImportError` pointing at the ``[vision]`` extra when
    torch / the vendored model is unavailable.
    """
    try:
        import numpy as np
        import torch
        from PIL import Image

        from roomestim.vision.checkpoints import resolve_checkpoint
        from roomestim.vision.horizonnet.misc import post_proc
        from roomestim.vision.horizonnet.misc.utils import load_trained_model
        from roomestim.vision.horizonnet.model import HorizonNet
    except ImportError as exc:  # pragma: no cover - exercised out-of-gate
        raise ImportError(
            "ImageAdapter requires the optional vision stack (torch + Pillow); "
            "install it with: pip install 'roomestim[vision]'"
        ) from exc

    device = torch.device("cpu")
    ckpt = resolve_checkpoint(weights, accept_noncommercial=accept_noncommercial)
    net = load_trained_model(HorizonNet, str(ckpt)).to(device)  # type: ignore[no-untyped-call]
    net.eval()

    # Preprocess: equirect RGB → 1024×512 → CHW float tensor in [0, 1].
    img: Image.Image = Image.open(pano_path)
    if img.size != (_PANO_W, _PANO_H):
        img = img.resize((_PANO_W, _PANO_H), Image.Resampling.BICUBIC)
    img_ori = np.array(img)[..., :3].transpose([2, 0, 1]).copy()
    x = torch.FloatTensor(np.array([img_ori / 255.0]))

    # Translated HorizonNet inference (force_cuboid path; no test-time aug).
    h_img, w_img = tuple(x.shape[2:])
    with torch.no_grad():
        y_bon_, y_cor_ = net(x.to(device))
    y_bon = y_bon_[0].cpu().numpy()
    y_cor = torch.sigmoid(y_cor_[0, 0]).cpu().numpy()

    y_bon = (y_bon / np.pi + 0.5) * h_img - 0.5
    y_bon[0] = np.clip(y_bon[0], 1, h_img / 2 - 1)
    y_bon[1] = np.clip(y_bon[1], h_img / 2 + 1, h_img - 2)

    z0 = 50.0
    _, z1 = post_proc.np_refine_by_fix_z(y_bon[0], y_bon[1], z0)  # type: ignore[no-untyped-call]

    from scipy.ndimage import maximum_filter  # type: ignore[import-untyped]

    r_px = int(round(w_img * 0.05 / 2))
    max_v = maximum_filter(y_cor, size=r_px, mode="wrap")
    pk_loc = np.where(max_v == y_cor)[0]
    pk_loc = pk_loc[y_cor[pk_loc] > 0]
    order = np.argsort(-y_cor[pk_loc])
    pk_loc = pk_loc[order[:4]]
    xs_ = pk_loc[np.argsort(pk_loc)]

    cor, _xy_cor = post_proc.gen_ww(  # type: ignore[no-untyped-call]
        xs_, y_bon[0], z0, tol=abs(0.16 * z1 / 1.6), force_cuboid=True
    )
    cor = np.hstack(
        [cor, post_proc.infer_coory(cor[:, 1], z1 - z0, z0)[:, None]]  # type: ignore[no-untyped-call]
    )

    cor_id = np.zeros((len(cor) * 2, 2), np.float32)
    for j in range(len(cor)):
        cor_id[j * 2] = cor[j, 0], cor[j, 1]
        cor_id[j * 2 + 1] = cor[j, 0], cor[j, 2]
    cor_id[:, 0] /= w_img
    cor_id[:, 1] /= h_img

    return [(float(u), float(v)) for u, v in cor_id]


class ImageAdapter:
    """``CaptureAdapter`` for a single equirectangular RGB panorama.

    Recovers room geometry from one gravity-aligned 360° photo via the vendored
    HorizonNet layout estimator plus a metric camera-height anchor. Experimental
    rough-estimate tier — NOT install-grade.

    Parameters
    ----------
    weights:
        HorizonNet checkpoint name (``"st3d"`` default, or ``"zind"`` which
        requires ``accept_noncommercial``).
    default_cam_height_m:
        Camera height above the floor used when no ``scale_anchor`` is supplied.
    accept_noncommercial:
        Acknowledge the ZInD non-commercial ToU when ``weights="zind"``.
    """

    def __init__(
        self,
        *,
        weights: str = "st3d",
        default_cam_height_m: float = 1.6,
        accept_noncommercial: bool = False,
    ) -> None:
        self._weights = weights
        self._default_cam_height_m = default_cam_height_m
        self._accept_noncommercial = accept_noncommercial

    def parse(
        self,
        path: Path | str,
        *,
        scale_anchor: ScaleAnchor | None = None,
        octave_band: bool = False,
    ) -> RoomModel:
        path_obj = Path(path)

        # Tier honesty (a): experimental rough-estimate, not install-grade.
        warnings.warn(
            "ImageAdapter is an experimental, rough-estimate capture tier "
            "(image layout estimation, no depth sensor); it is NOT "
            "install-grade. The <=15 cm accuracy budget is reserved for "
            "LiDAR/RoomPlan-class depth capture.",
            UserWarning,
            stacklevel=2,
        )
        # Assumption (b): Manhattan / gravity-aligned equirectangular pano.
        warnings.warn(
            "ImageAdapter assumes a Manhattan, gravity-aligned equirectangular "
            "panorama; tilted or non-Manhattan inputs degrade silently.",
            UserWarning,
            stacklevel=2,
        )

        # Scale source (c) — measured anchor vs assumed default (OQ-58).
        if scale_anchor is not None:
            if scale_anchor.type != "known_distance":
                raise ValueError(
                    "ImageAdapter: scale_anchor must be a 'known_distance' "
                    "(camera height above floor, in metres); got "
                    f"{scale_anchor.type!r}."
                )
            cam_h = scale_anchor.length_m
        else:
            cam_h = self._default_cam_height_m

        cor_id = _infer_corners(
            path_obj,
            weights=self._weights,
            accept_noncommercial=self._accept_noncommercial,
        )

        # Assumed-scale disclosure (OQ-58) — cite the cam_h scale sensitivity
        # (single-source IMAGE_CAM_H_SCALE_NOTE). Emitted after inference so the
        # plausibility window reflects the actual recovered corners. Honesty:
        # the percent quantifies how a cam_h ASSUMPTION propagates to room scale,
        # NOT an accuracy figure — a single pano cannot recover absolute cam_h.
        if scale_anchor is None:
            sens = _cam_h_sensitivity(cor_id, ref_cam_h=cam_h)
            pct = sens["scale_pct_per_10cm"]
            assert pct is not None  # always set for ref_cam_h > 0
            window = sens["max_plausible_cam_h_m"]
            window_txt = (
                f" cam_h above ~{window:.1f} m would push a corner past the "
                f"{_MAX_PLAUSIBLE_RADIUS_M:.0f} m single-pano plausibility bound."
                if window is not None
                else ""
            )
            warnings.warn(
                "ImageAdapter: no scale_anchor supplied; scale is ASSUMED from "
                f"the default camera height ({cam_h} m), not measured. "
                f"{IMAGE_CAM_H_SCALE_NOTE} At {cam_h} m a +/-10 cm cam_h error is "
                f"approximately +/-{pct:.1f}% room scale.{window_txt} Pass "
                "ScaleAnchor('known_distance', <camera height m>) for a measured "
                "anchor.",
                UserWarning,
                stacklevel=2,
            )

        return _corners_to_room(
            cor_id, cam_h, name=path_obj.stem, octave_band=octave_band
        )
