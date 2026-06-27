"""MoGeAdapter — metric single-image → RoomModel capture (ADR 0057, [moge] extra).

MoGe (Microsoft, github.com/microsoft/MoGe; MIT code + MIT/Apache weights —
commercially clean, UNLIKE the HorizonNet [vision] weights) recovers a METRIC
point map directly from one perspective RGB image with NO camera-height
assumption, removing the dominant scale-ambiguity lever of the HorizonNet image
backend (see ``IMAGE_CAM_H_SCALE_NOTE`` / ``MOGE_METRIC_NOTE``).

Modality bridge (algorithm A–G, ADR 0057):
  * (A) An equirectangular panorama (aspect ~2:1) is re-rendered into N
    known-rotation perspective crops (a torch-free numpy gnomonic sampler). WE
    generate the crops, so every per-crop camera rotation ``R_i`` is known
    EXACTLY — no pose estimation.
  * (B) Each crop is run through ``MoGe.infer`` (lazy torch) with the crop's
    KNOWN ``fov_x`` so the metric point map is consistent with the generation
    rays (MoGe otherwise estimates its own focal length).
  * (C) Per-crop points are rotated into one common gravity-aligned (Y-up) pano
    frame by the known ``R_i`` and fused into a single metric cloud. The metric
    scale comes from MoGe alone — no cam_h anywhere. Per-crop metric-scale
    dispersion is recorded as an honesty metric (``last_diagnostics``).
  * (D–F) The fused, gravity-aligned cloud is handed to
    :meth:`MeshAdapter._extract_room_model` — the SAME robust floor/ceiling
    density-plane + footprint extraction the mesh / multiview backends use (NO
    duplicated geometry; ``MultiviewAdapter`` is the precedent).
  * (G) Emit ``provenance="reconstructed"``, materials :data:`MaterialLabel.UNKNOWN`
    (no visual material inference), ``objects=[]``.

A single perspective (non-pano) input is supported as a fallback with a LOUD
partial-coverage warning: one perspective view cannot see a closed room, so the
footprint is the VISIBLE EXTENT only.

torch boundary (ADR 0057, gate #4): ``import roomestim.adapters.moge`` MUST stay
torch-free. ``torch`` and ``moge`` are imported lazily inside
:meth:`MoGeAdapter._load_model` / :meth:`_infer_points` only.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from roomestim.adapters.base import ScaleAnchor
from roomestim.adapters.mesh import FloorReconstruction, MeshAdapter
from roomestim.model import (
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    RoomModel,
    Surface,
)
from roomestim.reconstruct._disclosure import MOGE_METRIC_NOTE

__all__ = ["MoGeAdapter"]

# Default MoGe checkpoint (HuggingFace hub id). vitl is the released metric
# model; weights (~1-2 GB) download once into the per-user HF cache (not
# vendored). MIT/Apache licensed (commercial advantage over HorizonNet weights).
_DEFAULT_WEIGHTS = "Ruicheng/moge-vitl"

# Panorama detection: an equirectangular pano is ~2:1 (360x180 deg). A tolerant
# band so slightly-cropped panos still take the multi-crop path.
_PANO_ASPECT_LO = 1.8
_PANO_ASPECT_HI = 2.2

# Perspective-crop geometry. 8 horizontal crops at 45 deg yaw spacing (90 deg
# FoV overlaps to cover the full 360 deg ring of walls), plus a down- and an
# up-pitched crop to strengthen the floor and ceiling density planes. WE control
# the FoV, so it is passed to MoGe (fov_x) for generation-consistent points.
_CROP_FOV_DEG = 90.0
_CROP_RES = 512
_RING_YAWS_DEG = (0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0)
_PITCH_DEG = 65.0  # down/up crop pitch (|pitch| < 90 keeps the basis non-degenerate)

# Fused-cloud voxel downsample (metres). ~3 cm keeps the floor/ceiling planes and
# footprint sharp while collapsing the ~2.6M raw crop points to a tractable size
# for the shapely hull + density-plane extraction (and well under MeshAdapter's
# vertex cap). Pure-numpy (torch-free).
_VOXEL_M = 0.03

# Camera convention (verified against MoGe on real crops): MoGe returns points in
# the OpenCV camera frame (x-right, y-down, z-forward, z = metric depth). The
# pano frame is Y-up: a pano direction at azimuth ``lon`` / elevation ``lat`` is
# ``(sin lon cos lat, sin lat, -cos lon cos lat)``.


def _pano_direction(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Equirectangular (lon, lat) -> unit direction in the Y-up pano frame."""
    cl = np.cos(lat)
    return np.stack([np.sin(lon) * cl, np.sin(lat), -np.cos(lon) * cl], axis=-1)


def _cam_to_pano_rotation(yaw_deg: float, pitch_deg: float) -> np.ndarray:
    """Rotation mapping the OpenCV camera frame to the Y-up pano frame.

    Columns are the pano-frame images of the camera x (right), y (down), z
    (forward) axes for a camera looking at azimuth ``yaw_deg`` / elevation
    ``pitch_deg``. ``points_pano = points_cam @ R.T``.
    """
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    forward = _pano_direction(np.array(yaw), np.array(pitch))  # cam +z
    world_up = np.array([0.0, 1.0, 0.0])
    right = np.cross(forward, world_up)  # cam +x (horizontal)
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)  # cam +y (down); already unit (orthonormal)
    return np.column_stack([right, down, forward])


def _sample_equirect(pano: np.ndarray, dirs: np.ndarray) -> np.ndarray:
    """Bilinearly sample an equirectangular ``pano`` (H,W,3 uint8) along ``dirs``.

    ``dirs`` is an ``(R, R, 3)`` array of unit directions in the pano frame.
    Returns an ``(R, R, 3)`` uint8 crop. Longitude wraps; latitude clamps.
    """
    h, w = pano.shape[:2]
    lon = np.arctan2(dirs[..., 0], -dirs[..., 2])  # (-pi, pi]
    lat = np.arcsin(np.clip(dirs[..., 1], -1.0, 1.0))
    fx = (lon / (2.0 * math.pi) + 0.5) * w - 0.5
    fy = (0.5 - lat / math.pi) * h - 0.5
    x0 = np.floor(fx).astype(np.int64)
    y0 = np.floor(fy).astype(np.int64)
    wx = fx - x0
    wy = fy - y0
    x0m = np.mod(x0, w)
    x1m = np.mod(x0 + 1, w)
    y0c = np.clip(y0, 0, h - 1)
    y1c = np.clip(y0 + 1, 0, h - 1)
    pano_f = pano.astype(np.float64)
    c00 = pano_f[y0c, x0m]
    c01 = pano_f[y0c, x1m]
    c10 = pano_f[y1c, x0m]
    c11 = pano_f[y1c, x1m]
    wx3 = wx[..., None]
    wy3 = wy[..., None]
    top = c00 * (1 - wx3) + c01 * wx3
    bot = c10 * (1 - wx3) + c11 * wx3
    out = top * (1 - wy3) + bot * wy3
    clipped: np.ndarray = np.clip(out, 0, 255).astype(np.uint8)
    return clipped


def _make_crop(
    pano: np.ndarray, yaw_deg: float, pitch_deg: float
) -> tuple[np.ndarray, np.ndarray]:
    """Render one perspective crop from ``pano`` -> ``(crop_uint8, R_cam_to_pano)``.

    Pinhole crop of ``_CROP_RES`` px at ``_CROP_FOV_DEG`` horizontal FoV. Each
    crop pixel's camera ray is rotated into the pano frame and bilinearly
    sampled. Torch-free (numpy only).
    """
    res = _CROP_RES
    f = (res / 2.0) / math.tan(math.radians(_CROP_FOV_DEG) / 2.0)
    rows, cols = np.meshgrid(np.arange(res), np.arange(res), indexing="ij")
    x = (cols - res / 2.0 + 0.5) / f
    y = (rows - res / 2.0 + 0.5) / f
    z = np.ones_like(x)
    d_cam = np.stack([x, y, z], axis=-1)
    d_cam /= np.linalg.norm(d_cam, axis=-1, keepdims=True)
    rot = _cam_to_pano_rotation(yaw_deg, pitch_deg)
    d_pano = d_cam @ rot.T
    crop = _sample_equirect(pano, d_pano)
    return crop, rot


def _voxel_downsample(points: np.ndarray, voxel_m: float = _VOXEL_M) -> np.ndarray:
    """Collapse ``points`` (N,3) to one representative per ``voxel_m`` cell (mean)."""
    if points.shape[0] == 0:
        return points
    keys = np.floor(points / voxel_m).astype(np.int64)
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    inverse = inverse.ravel()
    n_cells = int(inverse.max()) + 1
    sums = np.zeros((n_cells, 3), dtype=np.float64)
    counts = np.zeros(n_cells, dtype=np.int64)
    np.add.at(sums, inverse, points)
    np.add.at(counts, inverse, 1)
    return sums / counts[:, None]


def _materials_to_unknown(room: RoomModel, *, octave_band: bool) -> RoomModel:
    """Rewrite every surface material to UNKNOWN (no visual material inference).

    MoGe is image-only (like HorizonNet): it recovers geometry, not materials.
    :meth:`MeshAdapter._extract_room_model` stamps mesh-default materials
    (WOOD_FLOOR / CEILING_DRYWALL / WALL_PAINTED); this downgrades them to
    :data:`MaterialLabel.UNKNOWN` with the matching absorption, mirroring
    ``ImageAdapter``.
    """
    unknown = MaterialLabel.UNKNOWN
    a500 = MaterialAbsorption[unknown]
    bands = MaterialAbsorptionBands[unknown] if octave_band else None
    new_surfaces: list[Surface] = [
        replace(s, material=unknown, absorption_500hz=a500, absorption_bands=bands)
        for s in room.surfaces
    ]
    return replace(room, surfaces=new_surfaces, provenance="reconstructed")


class MoGeAdapter:
    """``CaptureAdapter`` for metric single-image geometry via MoGe.

    Experimental rough-estimate tier — NOT install-grade. Metric scale is
    UNVALIDATED against real measured metric ground truth (see
    :data:`MOGE_METRIC_NOTE`).

    Parameters
    ----------
    weights:
        MoGe HuggingFace checkpoint id (default ``"Ruicheng/moge-vitl"``).
    floor_reconstruction:
        Footprint extractor forwarded to the shared mesh-cloud extraction
        (``"convex"`` default; ``"robust"`` trims vertex-noise flyers).
    """

    def __init__(
        self,
        *,
        weights: str = _DEFAULT_WEIGHTS,
        floor_reconstruction: FloorReconstruction | None = None,
    ) -> None:
        self._weights = weights
        # The pano is gravity-aligned by construction (Manhattan equirect), so the
        # fused cloud is Y-up: pin up_axis="y" rather than re-detecting it.
        self._mesh = MeshAdapter(
            floor_reconstruction=floor_reconstruction, up_axis="y"
        )
        self._model: Any = None
        self._device: str = "cpu"
        #: Diagnostics from the most recent :meth:`parse` (honesty side-channel):
        #: ``n_crops``, ``n_points_fused``, ``per_crop_scale``, ``scale_cv``.
        self.last_diagnostics: dict[str, Any] = {}

    # -- lazy torch / MoGe boundary ---------------------------------------- #

    def _load_model(self) -> Any:
        """Load + cache the MoGe model (lazy torch/MoGe import)."""
        if self._model is not None:
            return self._model
        try:
            import torch

            from moge.model.v1 import MoGeModel
        except ImportError as exc:  # pragma: no cover - exercised out-of-gate
            raise ImportError(
                "MoGeAdapter requires the optional [moge] extra (torch + MoGe); "
                "install it with: pip install 'roomestim[moge]' (git-only — MoGe "
                "is not on PyPI)."
            ) from exc
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        model = MoGeModel.from_pretrained(self._weights).to(self._device).eval()
        self._model = model
        return model

    def _infer_points(
        self, crop: np.ndarray, *, fov_x_deg: float | None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Run MoGe on one ``crop`` (R,R,3 uint8) -> ``(points HxWx3, mask HxW)``.

        TORCH PATH (lazy). ``points`` are metric, in the OpenCV camera frame.
        ``fov_x_deg`` pins the known crop FoV (panorama crops); ``None`` lets
        MoGe estimate it (single-perspective fallback).
        """
        import torch

        model = self._load_model()
        img = (
            torch.tensor(crop.astype(np.float32) / 255.0, device=self._device)
            .permute(2, 0, 1)
        )
        with torch.no_grad():
            out = model.infer(img, fov_x=fov_x_deg)
        points = out["points"].detach().cpu().numpy().astype(np.float64)
        mask = out["mask"].detach().cpu().numpy().astype(bool)
        return points, mask

    # -- fusion front-end --------------------------------------------------- #

    def _reconstruct_cloud(self, pano: np.ndarray, *, is_pano: bool) -> np.ndarray:
        """Fuse per-crop MoGe points into one Y-up metric cloud + record diagnostics."""
        if is_pano:
            views = [(yaw, 0.0) for yaw in _RING_YAWS_DEG] + [
                (0.0, -_PITCH_DEG),
                (0.0, _PITCH_DEG),
            ]
            fov_x: float | None = _CROP_FOV_DEG
            crops = [_make_crop(pano, yaw, pitch) for yaw, pitch in views]
        else:
            # Single perspective: feed the whole image (square-resized so MoGe's
            # aspect matches). R maps the OpenCV cam frame to Y-up (assumes a
            # roughly level photo); MoGe estimates its own FoV.
            crop = _resize_square(pano, _CROP_RES)
            crops = [(crop, _cam_to_pano_rotation(0.0, 0.0))]
            fov_x = None

        fused: list[np.ndarray] = []
        per_crop_scale: list[float] = []
        for crop, rot in crops:
            points, mask = self._infer_points(crop, fov_x_deg=fov_x)
            valid = points[mask]
            if valid.shape[0] == 0:
                per_crop_scale.append(float("nan"))
                continue
            per_crop_scale.append(float(np.median(np.linalg.norm(valid, axis=1))))
            fused.append(valid @ rot.T)

        if not fused:
            raise ValueError(
                "MoGeAdapter: MoGe returned no valid points for any crop; the "
                "image could not be reconstructed."
            )
        cloud = _voxel_downsample(np.vstack(fused))
        finite_scales = [s for s in per_crop_scale if math.isfinite(s)]
        mean_scale = float(np.mean(finite_scales)) if finite_scales else float("nan")
        scale_cv = (
            float(np.std(finite_scales) / mean_scale)
            if finite_scales and mean_scale > 0.0
            else float("nan")
        )
        self.last_diagnostics = {
            "n_crops": len(crops),
            "n_points_fused": int(cloud.shape[0]),
            "per_crop_scale": per_crop_scale,
            "scale_cv": scale_cv,
        }
        return cloud

    # -- CaptureAdapter contract ------------------------------------------- #

    def parse(
        self,
        path: Path | str,
        *,
        scale_anchor: ScaleAnchor | None = None,
        octave_band: bool = False,
    ) -> RoomModel:
        path_obj = Path(path)

        warnings.warn(
            "MoGeAdapter is an EXPERIMENTAL rough-estimate capture tier (metric "
            "single-image geometry); it is NOT install-grade. " + MOGE_METRIC_NOTE,
            UserWarning,
            stacklevel=2,
        )
        if scale_anchor is not None:
            warnings.warn(
                "MoGeAdapter: scale_anchor / camera height is IGNORED — MoGe is a "
                "metric backend (scale comes from the model, not a cam_h prior).",
                UserWarning,
                stacklevel=2,
            )

        from PIL import Image

        pano = np.asarray(Image.open(path_obj).convert("RGB"))
        h, w = pano.shape[:2]
        aspect = w / h if h else 0.0
        is_pano = _PANO_ASPECT_LO <= aspect <= _PANO_ASPECT_HI
        if not is_pano:
            warnings.warn(
                "MoGeAdapter: input aspect "
                f"{aspect:.2f} is not equirectangular (~2:1); treating it as a "
                "SINGLE PERSPECTIVE image. A single perspective view sees only "
                "part of a room, so the footprint is the VISIBLE EXTENT, NOT a "
                "closed floor polygon. A level photo (gravity down) is assumed.",
                UserWarning,
                stacklevel=2,
            )

        cloud = self._reconstruct_cloud(pano, is_pano=is_pano)
        cv = self.last_diagnostics.get("scale_cv")
        if is_pano and cv is not None and math.isfinite(cv):
            warnings.warn(
                f"MoGeAdapter: per-crop metric-scale dispersion (CV) = {cv:.1%} "
                "across the fused crops (honesty metric; large dispersion means "
                "MoGe's per-crop metric scale drifts and the fused geometry is "
                "less reliable).",
                UserWarning,
                stacklevel=2,
            )

        room = self._mesh._extract_room_model(
            cloud, name=path_obj.stem, octave_band=octave_band, up_axis_hint="y"
        )
        return _materials_to_unknown(room, octave_band=octave_band)


def _resize_square(img: np.ndarray, size: int) -> np.ndarray:
    """Resize an ``(H,W,3)`` uint8 image to ``(size,size,3)`` (PIL, torch-free)."""
    from PIL import Image

    return np.asarray(
        Image.fromarray(img).resize((size, size), Image.Resampling.BICUBIC)
    )
