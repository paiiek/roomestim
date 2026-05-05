"""Tests for ``roomestim.place.dbap`` — A7."""

from __future__ import annotations

import math

import numpy as np
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.model import Point3, Surface
from roomestim.place.dbap import place_dbap
from tests.fixtures.synthetic_rooms import shoebox


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _wall_surfaces(surfaces: list[Surface]) -> list[Surface]:
    return [s for s in surfaces if s.kind == "wall"]


def _surface_basis_2d(
    surface: Surface,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    p0 = np.array([surface.polygon[0].x, surface.polygon[0].y, surface.polygon[0].z])
    p1 = np.array([surface.polygon[1].x, surface.polygon[1].y, surface.polygon[1].z])
    p2 = np.array([surface.polygon[2].x, surface.polygon[2].y, surface.polygon[2].z])
    u_raw = p1 - p0
    u = u_raw / np.linalg.norm(u_raw)
    n_raw = np.cross(p1 - p0, p2 - p0)
    normal = n_raw / np.linalg.norm(n_raw)
    v = np.cross(normal, u)
    return p0, u, v, normal


def _project_point_to_surface_2d(
    point: Point3, surface: Surface
) -> tuple[float, float, float]:
    """Return (u, v, signed_distance_from_plane) of ``point`` on ``surface``."""
    origin, u, v, normal = _surface_basis_2d(surface)
    rel = np.array([point.x, point.y, point.z]) - origin
    return (
        float(np.dot(rel, u)),
        float(np.dot(rel, v)),
        float(np.dot(rel, normal)),
    )


def _surface_polygon_2d(surface: Surface) -> ShapelyPolygon:
    origin, u, v, _normal = _surface_basis_2d(surface)
    coords: list[tuple[float, float]] = []
    for p in surface.polygon:
        rel = np.array([p.x, p.y, p.z]) - origin
        coords.append((float(np.dot(rel, u)), float(np.dot(rel, v))))
    return ShapelyPolygon(coords)


def _is_on_any_surface(point: Point3, surfaces: list[Surface], slack_m: float = 0.01) -> bool:
    """Return True if ``point`` lies on (or within ``slack_m`` of) any surface polygon."""
    for surface in surfaces:
        u_c, v_c, dist_plane = _project_point_to_surface_2d(point, surface)
        if abs(dist_plane) > slack_m:
            continue
        poly = _surface_polygon_2d(surface)
        # Allow boundary slack via buffer.
        if poly.buffer(slack_m).contains(ShapelyPoint(u_c, v_c)):
            return True
    return False


# --------------------------------------------------------------------------- #
# A7 — DBAP placement
# --------------------------------------------------------------------------- #


def test_place_dbap_returns_n_speakers() -> None:
    room = shoebox()
    walls = _wall_surfaces(room.surfaces)
    result = place_dbap(
        mount_surfaces=walls,
        n_speakers=12,
        listener_area=room.listener_area,
    )
    assert result.target_algorithm == "DBAP"
    assert result.regularity_hint == "IRREGULAR"
    assert len(result.speakers) == 12
    channels = [sp.channel for sp in result.speakers]
    assert channels == list(range(1, 13))


def test_place_dbap_positions_on_mount_surface() -> None:
    """Every placed speaker is on (within 1 cm slack) of a mount surface."""
    room = shoebox()
    walls = _wall_surfaces(room.surfaces)
    result = place_dbap(
        mount_surfaces=walls,
        n_speakers=12,
        listener_area=room.listener_area,
    )
    for sp in result.speakers:
        assert _is_on_any_surface(sp.position, walls, slack_m=0.01), (
            f"speaker {sp.channel} at {sp.position} not on any wall"
        )


def test_place_dbap_coverage_min_gt_minus_3db() -> None:
    """Listener-area coverage min/max gain ratio (linear) > 10**(-3/20)."""
    room = shoebox()
    walls = _wall_surfaces(room.surfaces)
    result = place_dbap(
        mount_surfaces=walls,
        n_speakers=12,
        listener_area=room.listener_area,
    )

    # Sample listener area on the same 5x5 grid the placer uses.
    coords_2d = [(p.x, p.z) for p in room.listener_area.polygon]
    poly = ShapelyPolygon(coords_2d)
    minx, miny, maxx, maxy = poly.bounds
    xs = np.linspace(minx, maxx, 5)
    zs = np.linspace(miny, maxy, 5)
    listener_points: list[tuple[float, float, float]] = []
    for xv in xs:
        for zv in zs:
            if poly.contains(ShapelyPoint(float(xv), float(zv))):
                listener_points.append(
                    (float(xv), room.listener_area.height_m, float(zv))
                )

    assert listener_points, "listener-area sample grid is empty"

    # For each listener sample, sum the DBAP gains across all speakers.
    received: list[float] = []
    for lx, ly, lz in listener_points:
        total = 0.0
        for sp in result.speakers:
            d2 = (
                (sp.position.x - lx) ** 2
                + (sp.position.y - ly) ** 2
                + (sp.position.z - lz) ** 2
            )
            d2 = max(d2, 1e-4)
            total += 1.0 / d2
        received.append(total)

    min_gain = min(received)
    max_gain = max(received)
    ratio = min_gain / max_gain
    threshold = 10 ** (-3.0 / 20.0)  # ≈ 0.708
    assert ratio > threshold, (
        f"min/max coverage ratio {ratio:.4f} <= -3 dB threshold {threshold:.4f}; "
        f"min={min_gain:.4f}, max={max_gain:.4f}"
    )


def test_place_dbap_aim_direction_unit_to_listener() -> None:
    """Each aim_direction is unit-norm and points toward origin."""
    room = shoebox()
    walls = _wall_surfaces(room.surfaces)
    result = place_dbap(
        mount_surfaces=walls,
        n_speakers=8,
        listener_area=room.listener_area,
    )
    for sp in result.speakers:
        assert sp.aim_direction is not None
        norm = math.sqrt(
            sp.aim_direction.x ** 2
            + sp.aim_direction.y ** 2
            + sp.aim_direction.z ** 2
        )
        assert abs(norm - 1.0) < 1e-9, f"aim not unit-norm: {norm}"
