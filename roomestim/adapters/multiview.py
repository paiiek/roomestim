"""MultiviewAdapter — reconstructed point-cloud input for room estimation.

Fills the gap the :class:`~roomestim.adapters.mesh.MeshAdapter` leaves: that
adapter requires a surface mesh and explicitly rejects a points-only PLY
(downstream hull-of-projection is undefined for a bare cloud). Multi-view /
video reconstruction (e.g. VGGT) produces exactly such a **point cloud** —
metric, gravity-aligned, with NO faces — so this adapter ingests it directly.

Supported inputs (a reconstructed cloud, NOT raw frames):
  - ``.ply`` points-only (trimesh ``PointCloud``)
  - ``.npz`` with an ``(N, 3)`` array under key ``points`` / ``xyz`` / ``P_m`` /
    ``vertices`` (else the first ``(N, 3)`` array)
  - ``.xyz`` / ``.txt`` whitespace-delimited ``x y z`` (extra columns ignored)

Footprint / ceiling / walls / listener area reuse the SAME extraction the
mesh adapter runs (``MeshAdapter._extract_room_model``), so
``floor_reconstruction`` ("convex"/"concave"/"occupancy"/"auto"/"robust") and
the robust floor/ceiling density-plane logic apply unchanged.

Honesty (PLACEMENT_SENSITIVITY_VERDICT.md): a rough phone/video cloud rarely
reaches the ceiling, so the auto-extracted ceiling is unreliable. This adapter
marks ``provenance="reconstructed"`` and supports a ``ceiling_height_m``
override (a single user-measured scalar) — pairing the two is the recommended
A-consumer flow. Scope: ingesting the cloud; the upstream frames→cloud
reconstruction (VGGT) is out of scope (heavy GPU dependency).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from roomestim.adapters.base import ScaleAnchor
from roomestim.adapters.mesh import FloorReconstruction, MeshAdapter, UpAxis
from roomestim.edit import _MAX_USER_CEILING_M, evolve_room_ceiling_height
from roomestim.model import RoomModel

__all__ = ["MultiviewAdapter"]

_SUPPORTED_SUFFIXES = frozenset({".ply", ".npz", ".xyz", ".txt"})

# Preferred npz keys for the point array, in priority order. ``P_m`` matches the
# spike (spike-vggt-multiview) cache convention; the others are generic.
_NPZ_POINT_KEYS = ("points", "xyz", "P_m", "vertices")

# DoS guard mirroring the mesh adapter's file-byte cap (ADR 0038); the publicly
# deployable web upload path reaches this loader too.
_MAX_CLOUD_FILE_BYTES = int(
    os.environ.get("ROOMESTIM_MAX_CLOUD_BYTES", 500 * 1024 * 1024)  # ~500 MB
)

# The only scale-anchor type this adapter accepts: the known longest floor
# dimension (metres). Unlike the image backend's camera-height "known_distance",
# a multiview cloud has no camera frame — the floor footprint is the anchor.
_FLOOR_LENGTH_ANCHOR_TYPE = "known_floor_length"

# Plausibility bound on the supplied floor length (metres); mirrors the ceiling
# bound and rejects obviously-wrong scalars (e.g. a value entered in cm).
_MAX_FLOOR_LENGTH_M = 100.0


def _validate_floor_length_anchor(anchor: ScaleAnchor | None) -> None:
    """Fail fast on an unusable scale anchor (None is allowed = metric-native)."""
    if anchor is None:
        return
    if anchor.type != _FLOOR_LENGTH_ANCHOR_TYPE:
        raise ValueError(
            f"MultiviewAdapter: scale_anchor must be type "
            f"{_FLOOR_LENGTH_ANCHOR_TYPE!r} (the known longest floor dimension in "
            f"metres); got {anchor.type!r}."
        )
    if not np.isfinite(anchor.length_m) or anchor.length_m <= 0.0:
        raise ValueError(
            f"MultiviewAdapter: scale_anchor.length_m must be a positive finite "
            f"length in metres; got {anchor.length_m!r}."
        )
    if anchor.length_m > _MAX_FLOOR_LENGTH_M:
        raise ValueError(
            f"MultiviewAdapter: scale_anchor.length_m={anchor.length_m} m exceeds "
            f"the {_MAX_FLOOR_LENGTH_M} m plausibility bound (value in cm?)."
        )


def _footprint_diameter(room: RoomModel) -> float:
    """Longest pairwise distance between floor-polygon corners (metres).

    A rotation-invariant extent of the footprint, used to match the cloud's
    scale to the user's known floor length. Pure-numpy (footprints have few
    corners) to avoid a scipy dependency in this core adapter.
    """
    pts = np.asarray([[p.x, p.z] for p in room.floor_polygon], dtype=float)
    if pts.shape[0] < 2:
        return 0.0
    diff = pts[:, None, :] - pts[None, :, :]
    return float(np.sqrt((diff * diff).sum(axis=-1)).max())


class MultiviewAdapter:
    """``CaptureAdapter`` for a reconstructed point cloud (no faces required).

    Parameters
    ----------
    floor_reconstruction:
        Footprint extractor mode, forwarded to the shared mesh extraction
        (default ``"convex"``; honors ``ROOMESTIM_MESH_FLOOR_RECON``). For rough
        consumer clouds ``"robust"`` (noise-trim) or ``"convex"`` are the
        validated choices.
    up_axis:
        Gravity-axis hint forwarded to the shared extraction (default ``"auto"``).
    ceiling_height_m:
        Optional USER-supplied ceiling height (metres). When given, the
        auto-extracted ceiling is overridden via
        :func:`roomestim.edit.evolve_room_ceiling_height` — the recommended path
        for ceiling-less rough clouds.
    """

    def __init__(
        self,
        *,
        floor_reconstruction: FloorReconstruction | None = None,
        up_axis: UpAxis = "auto",
        ceiling_height_m: float | None = None,
    ) -> None:
        if ceiling_height_m is not None:
            if not np.isfinite(ceiling_height_m) or ceiling_height_m <= 0.0:
                raise ValueError(
                    f"MultiviewAdapter: ceiling_height_m must be > 0, "
                    f"got {ceiling_height_m!r}."
                )
            # Fail fast at construction with the same plausibility bound
            # evolve_room_ceiling_height applies at parse() time.
            if ceiling_height_m > _MAX_USER_CEILING_M:
                raise ValueError(
                    f"MultiviewAdapter: ceiling_height_m={ceiling_height_m} m "
                    f"exceeds the {_MAX_USER_CEILING_M} m plausibility bound."
                )
        self._mesh = MeshAdapter(
            floor_reconstruction=floor_reconstruction, up_axis=up_axis
        )
        self._ceiling_height_m = ceiling_height_m

    def parse(
        self,
        path: Path | str,
        *,
        scale_anchor: ScaleAnchor | None = None,
        octave_band: bool = False,
    ) -> RoomModel:
        # scale_anchor is honored for the "known_floor_length" type (below): a
        # raw VGGT/multiview cloud is NOT metric-native (per-room 1–5x off), so a
        # single user-supplied known floor length sets metric scale. With no
        # anchor the cloud is assumed already metric (e.g. anchored upstream).
        _validate_floor_length_anchor(scale_anchor)
        path_obj = Path(path)
        suffix = path_obj.suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError(
                f"MultiviewAdapter: unsupported extension {suffix!r}; expected "
                f"one of {sorted(_SUPPORTED_SUFFIXES)}."
            )
        file_bytes = path_obj.stat().st_size
        if file_bytes > _MAX_CLOUD_FILE_BYTES:
            raise ValueError(
                f"MultiviewAdapter: cloud file is {file_bytes} bytes, exceeding "
                f"the {_MAX_CLOUD_FILE_BYTES}-byte cap (set "
                f"ROOMESTIM_MAX_CLOUD_BYTES to raise it)."
            )

        points = self._load_points(path_obj, suffix)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError(
                f"MultiviewAdapter: expected an (N, 3) point array, got shape "
                f"{points.shape}."
            )
        if points.shape[0] < 3:
            raise ValueError(
                f"MultiviewAdapter: need >=3 points to reconstruct a footprint, "
                f"got {points.shape[0]}."
            )
        if not np.all(np.isfinite(points)):
            raise ValueError(
                "MultiviewAdapter: point cloud contains non-finite coordinates."
            )

        from dataclasses import replace

        def _extract(pts: np.ndarray) -> RoomModel:
            # Reuse the mesh adapter's vertex-array extraction (footprint mode,
            # robust floor/ceiling planes, walls, listener area). It stamps
            # provenance="measured"; a reconstruction is downgraded here.
            r = self._mesh._extract_room_model(
                pts, name=path_obj.stem, octave_band=octave_band
            )
            return replace(r, provenance="reconstructed")

        room = _extract(points)

        # Metric-scale anchor (PLACEMENT_SENSITIVITY_VERDICT.md): VGGT/multiview
        # native scale is per-room 1–5x off, so re-scale the cloud isotropically
        # until the convex footprint's longest dimension equals the user-supplied
        # known floor length, then re-extract. The floor is always reconstructed
        # (the ceiling is not), so a floor length is the one reliable anchor.
        if scale_anchor is not None:
            diameter = _footprint_diameter(room)
            if diameter <= 0.0:
                raise ValueError(
                    "MultiviewAdapter: cannot apply scale anchor — the extracted "
                    "footprint is degenerate (diameter 0)."
                )
            scale = scale_anchor.length_m / diameter
            room = _extract(points * scale)

        if self._ceiling_height_m is not None:
            room = evolve_room_ceiling_height(room, self._ceiling_height_m)
        return room

    @staticmethod
    def _load_points(path: Path, suffix: str) -> np.ndarray:
        if suffix == ".npz":
            return MultiviewAdapter._points_from_npz(path)
        if suffix in (".xyz", ".txt"):
            arr = np.loadtxt(path, dtype=float)
            arr = np.atleast_2d(arr)
            return np.ascontiguousarray(arr[:, :3], dtype=float)
        # .ply -> trimesh PointCloud (or a mesh; either exposes .vertices).
        import trimesh

        loaded = trimesh.load(path, process=False)
        vertices = getattr(loaded, "vertices", None)
        if vertices is None:
            raise ValueError(
                f"MultiviewAdapter: {path!r} exposed no vertices (not a point "
                "cloud / mesh?)."
            )
        return np.asarray(vertices, dtype=float)

    @staticmethod
    def _points_from_npz(path: Path) -> np.ndarray:
        with np.load(path, allow_pickle=False) as data:
            for key in _NPZ_POINT_KEYS:
                if key in data:
                    arr = np.asarray(data[key], dtype=float)
                    # Parity with the .xyz/.txt loader: a named point key that
                    # carries extra columns (e.g. (N, 6) xyzrgb) is sliced to xyz
                    # rather than rejected by the downstream (N, 3) shape check.
                    if arr.ndim == 2 and arr.shape[1] > 3:
                        arr = arr[:, :3]
                    return arr
            # Fall back to the first (N, 3) array in the archive.
            for key in data.files:
                arr = np.asarray(data[key])
                if arr.ndim == 2 and arr.shape[1] == 3:
                    return arr.astype(float)
            raise ValueError(
                f"MultiviewAdapter: npz {path!r} has no (N, 3) point array "
                f"(looked for keys {_NPZ_POINT_KEYS} then any (N, 3) array; "
                f"found {list(data.files)})."
            )
