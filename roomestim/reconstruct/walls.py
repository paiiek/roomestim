"""Minimal wall-extraction stub used by the Polycam OBJ reconstruction path.

Given a CCW floor polygon and a ceiling height, synthesize one vertical
rectangular :class:`Surface` per polygon edge. The resulting walls share
``default_material`` (default :data:`MaterialLabel.WALL_PAINTED`) and the
matching 500 Hz absorption coefficient from :data:`MaterialAbsorption`.

Each wall polygon is wound bottom-edge first so the in-plane basis derived by
``dbap._surface_basis`` (``u = p1 - p0``) is horizontal — matching the
shoebox synthetic-room convention in :mod:`tests.fixtures.synthetic_rooms`.
"""

from __future__ import annotations

from roomestim.model import (
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    Point2,
    Point3,
    Surface,
)


def walls_from_floor_polygon(
    floor_polygon: list[Point2],
    ceiling_height_m: float,
    *,
    default_material: MaterialLabel = MaterialLabel.WALL_PAINTED,
    octave_band: bool = False,
) -> list[Surface]:
    """Return one :class:`Surface` per CCW edge of ``floor_polygon``.

    Each wall is a vertical rectangle with corners
    ``(p_i, 0), (p_{i+1}, 0), (p_{i+1}, h), (p_i, h)`` where ``h`` is
    ``ceiling_height_m``.
    """
    if len(floor_polygon) < 3:
        raise ValueError(
            f"floor_polygon must have >=3 vertices, got {len(floor_polygon)}"
        )
    if ceiling_height_m <= 0.0:
        raise ValueError(
            f"ceiling_height_m must be > 0, got {ceiling_height_m}"
        )

    absorption: float = MaterialAbsorption[default_material]
    walls: list[Surface] = []
    n = len(floor_polygon)
    for i in range(n):
        p0 = floor_polygon[i]
        p1 = floor_polygon[(i + 1) % n]
        polygon = [
            Point3(p0.x, 0.0, p0.z),
            Point3(p1.x, 0.0, p1.z),
            Point3(p1.x, ceiling_height_m, p1.z),
            Point3(p0.x, ceiling_height_m, p0.z),
        ]
        walls.append(
            Surface(
                kind="wall",
                polygon=polygon,
                material=default_material,
                absorption_500hz=absorption,
                absorption_bands=MaterialAbsorptionBands[default_material] if octave_band else None,
            )
        )
    return walls


__all__ = ["walls_from_floor_polygon"]
