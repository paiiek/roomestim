"""DBAP greedy coverage placement (A7).

Strategy:
  1. For each mount surface, compute the surface plane and a 2D-in-plane basis.
  2. Inset the polygon by ``inset_m`` (default 0.10 m) using shapely.
  3. Sample a regular ``samples_per_dim x samples_per_dim`` grid over the inset
     polygon's axis-aligned 2D bbox; reject samples that fall outside the
     inset polygon.
  4. Lift each 2D surface-plane sample back to 3D Cartesian — this is the
     candidate pool.
  5. Build a 5x5 listener-area sample grid (intersected with the listener-area
     polygon).
  6. For each candidate, precompute the per-listener-sample DBAP gain
     ``g = 1 / d^2``.
  7. Greedy max-min coverage: starting from the empty selected set, iteratively
     pick the candidate that maximizes the **minimum** total received gain at
     any listener sample. Stop when ``n_speakers`` are picked.
  8. Return picked positions as a ``PlacementResult`` with channels ``1..n``
     in pick order; ``regularity_hint = "IRREGULAR"`` and
     ``target_algorithm = "DBAP"``.

A7 acceptance: every position lies on at least one mount surface (guaranteed
by construction — candidates are sampled inside inset polygons of the
surface), and the listener-area coverage min/max gain ratio (linear) is
> ``10**(-3/20) ≈ 0.708`` (i.e., min coverage > -3 dB relative to max).
"""

from __future__ import annotations

import math

import numpy as np
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.model import (
    ListenerArea,
    PlacedSpeaker,
    PlacementResult,
    Point3,
    Surface,
)
from roomestim.place.algorithm import TargetAlgorithm


# --------------------------------------------------------------------------- #
# Surface plane / 2D basis
# --------------------------------------------------------------------------- #


def _surface_basis(
    surface: Surface,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(origin, u, v, normal)`` for ``surface``.

    ``origin`` is the first polygon vertex (3D). ``u`` and ``v`` are unit
    in-plane orthonormal axes; ``normal`` is the unit surface normal computed
    via ``(p1-p0) x (p2-p0)``.

    Raises ``ValueError`` if the polygon is degenerate (fewer than 3 vertices
    or collinear).
    """
    if len(surface.polygon) < 3:
        raise ValueError(
            f"surface polygon must have >=3 vertices, got {len(surface.polygon)}"
        )
    p0 = np.array([surface.polygon[0].x, surface.polygon[0].y, surface.polygon[0].z])
    p1 = np.array([surface.polygon[1].x, surface.polygon[1].y, surface.polygon[1].z])
    p2 = np.array([surface.polygon[2].x, surface.polygon[2].y, surface.polygon[2].z])
    u_raw = p1 - p0
    u_norm = float(np.linalg.norm(u_raw))
    if u_norm == 0.0:
        raise ValueError("degenerate surface polygon: p0 == p1")
    u = u_raw / u_norm
    n_raw = np.cross(p1 - p0, p2 - p0)
    n_norm = float(np.linalg.norm(n_raw))
    if n_norm == 0.0:
        raise ValueError("degenerate surface polygon: collinear first three vertices")
    normal = n_raw / n_norm
    v = np.cross(normal, u)
    return p0, u, v, normal


def _project_to_2d(
    surface: Surface, origin: np.ndarray, u: np.ndarray, v: np.ndarray
) -> list[tuple[float, float]]:
    """Project the 3D polygon vertices to 2D (u, v) coords."""
    coords_2d: list[tuple[float, float]] = []
    for p in surface.polygon:
        rel = np.array([p.x, p.y, p.z]) - origin
        coords_2d.append((float(np.dot(rel, u)), float(np.dot(rel, v))))
    return coords_2d


def _lift_to_3d(
    u_coord: float,
    v_coord: float,
    origin: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
) -> Point3:
    """Lift a (u, v) sample back to 3D Cartesian."""
    p = origin + u_coord * u + v_coord * v
    return Point3(x=float(p[0]), y=float(p[1]), z=float(p[2]))


# --------------------------------------------------------------------------- #
# Candidate sampling
# --------------------------------------------------------------------------- #


def _candidates_on_surface(
    surface: Surface, *, inset_m: float, samples_per_dim: int
) -> list[Point3]:
    """Return up to ``samples_per_dim**2`` 3D candidate positions on ``surface``.

    Sampled inside the inset polygon (inset by ``inset_m``).
    """
    origin, u, v, _normal = _surface_basis(surface)
    coords_2d = _project_to_2d(surface, origin, u, v)
    poly = ShapelyPolygon(coords_2d)
    if not poly.is_valid or poly.is_empty:
        return []
    inset = poly.buffer(-inset_m)
    if inset.is_empty:
        return []

    minx, miny, maxx, maxy = inset.bounds
    if samples_per_dim < 1:
        return []
    if samples_per_dim == 1:
        u_samples = [0.5 * (minx + maxx)]
        v_samples = [0.5 * (miny + maxy)]
    else:
        u_samples = list(np.linspace(minx, maxx, samples_per_dim))
        v_samples = list(np.linspace(miny, maxy, samples_per_dim))

    candidates: list[Point3] = []
    for uc in u_samples:
        for vc in v_samples:
            pt = ShapelyPoint(uc, vc)
            # ``contains`` is strict; allow boundary via ``intersects`` with
            # a tiny buffer to keep numerical edge cases inside.
            if inset.contains(pt) or inset.buffer(1e-9).contains(pt):
                candidates.append(_lift_to_3d(float(uc), float(vc), origin, u, v))
    return candidates


# --------------------------------------------------------------------------- #
# Listener-area sampling
# --------------------------------------------------------------------------- #


def _listener_samples(
    listener_area: ListenerArea, *, samples_per_dim: int = 5
) -> list[Point3]:
    """Return a grid of 3D listener-area sample points at ``listener_area.height_m``.

    Samples are drawn over the listener polygon's 2D bbox, rejected if they
    fall outside the polygon. At least one sample (the centroid) is always
    returned.
    """
    coords_2d = [(p.x, p.z) for p in listener_area.polygon]
    poly = ShapelyPolygon(coords_2d)
    samples: list[Point3] = []
    if poly.is_valid and not poly.is_empty:
        minx, miny, maxx, maxy = poly.bounds
        xs = np.linspace(minx, maxx, samples_per_dim) if samples_per_dim > 1 else [0.5 * (minx + maxx)]
        zs = np.linspace(miny, maxy, samples_per_dim) if samples_per_dim > 1 else [0.5 * (miny + maxy)]
        for xv in xs:
            for zv in zs:
                if poly.contains(ShapelyPoint(float(xv), float(zv))):
                    samples.append(
                        Point3(
                            x=float(xv),
                            y=listener_area.height_m,
                            z=float(zv),
                        )
                    )
    if not samples:
        samples.append(
            Point3(
                x=listener_area.centroid.x,
                y=listener_area.height_m,
                z=listener_area.centroid.z,
            )
        )
    return samples


# --------------------------------------------------------------------------- #
# DBAP gain & greedy selection
# --------------------------------------------------------------------------- #


def _dbap_gain_matrix(
    candidates: list[Point3], listener_samples: list[Point3]
) -> np.ndarray:
    """Return the (n_candidates, n_listeners) DBAP gain matrix ``g = 1 / d^2``.

    Uses a small floor on ``d`` (1 cm) to avoid divide-by-zero for samples
    coincident with a candidate.
    """
    cand = np.array([[c.x, c.y, c.z] for c in candidates], dtype=float)  # (C, 3)
    lis = np.array(
        [[lp.x, lp.y, lp.z] for lp in listener_samples], dtype=float
    )  # (L, 3)
    diff = cand[:, None, :] - lis[None, :, :]  # (C, L, 3)
    d2 = np.sum(diff * diff, axis=-1)  # (C, L)
    d2 = np.maximum(d2, 1e-4)  # 1 cm floor
    gain: np.ndarray = 1.0 / d2
    return gain


def _greedy_max_min_select(
    gain_matrix: np.ndarray, n_speakers: int
) -> list[int]:
    """Greedy max-min coverage selection.

    Starting from no selection, iteratively pick the candidate whose addition
    maximizes the minimum total received gain across listener samples.
    Returns the selected candidate indices in pick order.
    """
    n_cand = gain_matrix.shape[0]
    if n_speakers > n_cand:
        raise ValueError(
            f"DBAP candidate pool too small: requested {n_speakers} speakers, "
            f"only {n_cand} candidate positions available"
        )
    selected: list[int] = []
    received = np.zeros(gain_matrix.shape[1], dtype=float)  # per-listener total gain
    available = list(range(n_cand))
    for _ in range(n_speakers):
        best_idx = -1
        best_min = -math.inf
        for idx in available:
            new_received = received + gain_matrix[idx]
            min_gain = float(np.min(new_received))
            if min_gain > best_min:
                best_min = min_gain
                best_idx = idx
        if best_idx < 0:
            raise RuntimeError("DBAP greedy selection failed: no candidate selected")
        selected.append(best_idx)
        received = received + gain_matrix[best_idx]
        available.remove(best_idx)
    return selected


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def _aim_to_origin(position: Point3) -> Point3:
    """Unit vector from ``position`` toward the origin (listener)."""
    norm = math.sqrt(
        position.x * position.x + position.y * position.y + position.z * position.z
    )
    if norm == 0.0:
        return Point3(0.0, 0.0, -1.0)
    return Point3(-position.x / norm, -position.y / norm, -position.z / norm)


def place_dbap(
    *,
    mount_surfaces: list[Surface],
    n_speakers: int,
    listener_area: ListenerArea,
    layout_name: str = "dbap_coverage",
    samples_per_dim: int = 5,
    inset_m: float = 0.10,
) -> PlacementResult:
    """DBAP greedy coverage placement on ``mount_surfaces`` (A7).

    Parameters
    ----------
    mount_surfaces:
        Walls and/or ceiling surfaces where speakers may be placed. Floors are
        usually excluded by the caller.
    n_speakers:
        Number of speakers to pick.
    listener_area:
        Listener polygon used to evaluate coverage.
    samples_per_dim:
        Per-dimension grid resolution for both surface candidate sampling and
        listener-area sampling. Default 5 (=> 25 candidates per surface and
        25 listener samples).
    inset_m:
        Surface-edge inset for candidate sampling (m). Default 0.10 m.
    """
    if n_speakers < 1:
        raise ValueError(f"n_speakers must be >=1, got {n_speakers}")
    if not mount_surfaces:
        raise ValueError("mount_surfaces is empty")

    candidates: list[Point3] = []
    for surface in mount_surfaces:
        candidates.extend(
            _candidates_on_surface(
                surface, inset_m=inset_m, samples_per_dim=samples_per_dim
            )
        )
    if not candidates:
        raise ValueError(
            "DBAP candidate pool is empty after inset; check mount_surfaces and inset_m"
        )

    listener_samples = _listener_samples(listener_area, samples_per_dim=samples_per_dim)
    gain_matrix = _dbap_gain_matrix(candidates, listener_samples)
    picked_indices = _greedy_max_min_select(gain_matrix, n_speakers)

    speakers: list[PlacedSpeaker] = []
    for i, cand_idx in enumerate(picked_indices):
        position = candidates[cand_idx]
        speakers.append(
            PlacedSpeaker(
                channel=i + 1,
                position=position,
                aim_direction=_aim_to_origin(position),
            )
        )

    return PlacementResult(
        target_algorithm=TargetAlgorithm.DBAP.value,
        regularity_hint="IRREGULAR",
        speakers=speakers,
        layout_name=layout_name,
    )


__all__ = ["place_dbap"]
