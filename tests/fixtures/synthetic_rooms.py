"""Procedural :class:`RoomModel` generators for tests."""

from __future__ import annotations

import random

from roomestim.model import (
    ListenerArea,
    MaterialAbsorption,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
    canonicalize_ccw,
)


def _wall_polygon(p0: Point2, p1: Point2, height: float) -> list[Point3]:
    """Return a vertical rectangular wall polygon (CCW from inside the room).

    Two floor-plane corners ``p0 -> p1`` are lifted to a 4-corner rectangle:
    floor-p0, floor-p1, top-p1, top-p0.
    """
    return [
        Point3(p0.x, 0.0, p0.z),
        Point3(p1.x, 0.0, p1.z),
        Point3(p1.x, height, p1.z),
        Point3(p0.x, height, p0.z),
    ]


def _lift_polygon(polygon: list[Point2], y: float) -> list[Point3]:
    return [Point3(p.x, y, p.z) for p in polygon]


def shoebox(
    width: float = 5.0,
    depth: float = 4.0,
    height: float = 2.8,
    name: str = "synthetic_shoebox",
) -> RoomModel:
    """Build a CCW shoebox :class:`RoomModel` centred at the origin.

    x in ``[-w/2, w/2]``, z in ``[-d/2, d/2]``. Defaults: 5 x 4 m floor, 2.8 m
    ceiling. Walls = ``wall_painted``; floor = ``wood_floor``;
    ceiling = ``ceiling_acoustic_tile``.
    """
    hw, hd = width / 2.0, depth / 2.0

    # CCW corners on the floor plane (viewed from above with +x right, +z up).
    floor = [
        Point2(-hw, -hd),
        Point2(hw, -hd),
        Point2(hw, hd),
        Point2(-hw, hd),
    ]
    floor = canonicalize_ccw(floor)

    listener_polygon = [
        Point2(-0.75, -0.75),
        Point2(0.75, -0.75),
        Point2(0.75, 0.75),
        Point2(-0.75, 0.75),
    ]
    listener_polygon = canonicalize_ccw(listener_polygon)
    listener = ListenerArea(
        polygon=listener_polygon,
        centroid=Point2(0.0, 0.0),
        height_m=1.20,
    )

    floor_surface = Surface(
        kind="floor",
        polygon=_lift_polygon(floor, 0.0),
        material=MaterialLabel.WOOD_FLOOR,
        absorption_500hz=MaterialAbsorption[MaterialLabel.WOOD_FLOOR],
    )
    ceiling_surface = Surface(
        kind="ceiling",
        polygon=_lift_polygon(list(reversed(floor)), height),
        material=MaterialLabel.CEILING_ACOUSTIC_TILE,
        absorption_500hz=MaterialAbsorption[MaterialLabel.CEILING_ACOUSTIC_TILE],
    )

    walls: list[Surface] = []
    for i in range(len(floor)):
        p0 = floor[i]
        p1 = floor[(i + 1) % len(floor)]
        walls.append(
            Surface(
                kind="wall",
                polygon=_wall_polygon(p0, p1, height),
                material=MaterialLabel.WALL_PAINTED,
                absorption_500hz=MaterialAbsorption[MaterialLabel.WALL_PAINTED],
            )
        )

    surfaces = [floor_surface, ceiling_surface, *walls]

    return RoomModel(
        name=name,
        floor_polygon=floor,
        ceiling_height_m=height,
        surfaces=surfaces,
        listener_area=listener,
    )


def perturb_room_with_walls(
    room: RoomModel, sigma_m: float, seed: int
) -> RoomModel:
    """Return a perturbed copy of ``room`` with floor_polygon and walls jittered.

    Each floor_polygon vertex is offset by an independent uniform draw from
    ``[-sigma_m, +sigma_m]`` in both x and z (planar). Wall surfaces are
    regenerated from the perturbed polygon so vertex-shared edges stay
    coincident. The floor surface polygon is kept consistent with the new
    floor_polygon; the ceiling polygon is the lifted reverse of the new
    perturbed floor (mirroring :func:`shoebox`). Listener area, ceiling
    height, and material assignments are unchanged.

    Used by ``tests/test_placement_dbap_under_noise.py`` to characterise DBAP
    placement under floor-vertex noise.
    """
    rng = random.Random(seed)
    height = room.ceiling_height_m

    perturbed_floor: list[Point2] = []
    for p in room.floor_polygon:
        perturbed_floor.append(
            Point2(
                p.x + rng.uniform(-sigma_m, sigma_m),
                p.z + rng.uniform(-sigma_m, sigma_m),
            )
        )
    # Re-canonicalise in case perturbation flipped CCW orientation.
    perturbed_floor = canonicalize_ccw(perturbed_floor)

    floor_surface = Surface(
        kind="floor",
        polygon=_lift_polygon(perturbed_floor, 0.0),
        material=MaterialLabel.WOOD_FLOOR,
        absorption_500hz=MaterialAbsorption[MaterialLabel.WOOD_FLOOR],
    )
    ceiling_surface = Surface(
        kind="ceiling",
        polygon=_lift_polygon(list(reversed(perturbed_floor)), height),
        material=MaterialLabel.CEILING_ACOUSTIC_TILE,
        absorption_500hz=MaterialAbsorption[MaterialLabel.CEILING_ACOUSTIC_TILE],
    )

    walls: list[Surface] = []
    for i in range(len(perturbed_floor)):
        p0 = perturbed_floor[i]
        p1 = perturbed_floor[(i + 1) % len(perturbed_floor)]
        walls.append(
            Surface(
                kind="wall",
                polygon=_wall_polygon(p0, p1, height),
                material=MaterialLabel.WALL_PAINTED,
                absorption_500hz=MaterialAbsorption[MaterialLabel.WALL_PAINTED],
            )
        )

    return RoomModel(
        name=f"{room.name}__pert_sigma{sigma_m:g}_seed{seed}",
        floor_polygon=perturbed_floor,
        ceiling_height_m=height,
        surfaces=[floor_surface, ceiling_surface, *walls],
        listener_area=room.listener_area,
    )


def l_shape_room(name: str = "synthetic_l_shape") -> RoomModel:
    """Build a CCW 6-vertex L-shaped :class:`RoomModel`.

    Outer footprint 6x6 m with a 3x3 m corner cut out at the +x,+z corner,
    giving a 6-vertex L polygon. Ceiling 2.8 m. Same material defaults as
    :func:`shoebox`.
    """
    height = 2.8

    # 6-vertex CCW L-shape (origin-centred-ish; outer 6x6 with +x,+z 3x3 cut out).
    # Walking CCW (viewed from above):
    floor = [
        Point2(-3.0, -3.0),
        Point2(3.0, -3.0),
        Point2(3.0, 0.0),
        Point2(0.0, 0.0),
        Point2(0.0, 3.0),
        Point2(-3.0, 3.0),
    ]
    floor = canonicalize_ccw(floor)

    listener_polygon = [
        Point2(-1.5, -1.5),
        Point2(0.0, -1.5),
        Point2(0.0, 0.0),
        Point2(-1.5, 0.0),
    ]
    listener_polygon = canonicalize_ccw(listener_polygon)
    listener = ListenerArea(
        polygon=listener_polygon,
        centroid=Point2(-0.75, -0.75),
        height_m=1.20,
    )

    floor_surface = Surface(
        kind="floor",
        polygon=_lift_polygon(floor, 0.0),
        material=MaterialLabel.WOOD_FLOOR,
        absorption_500hz=MaterialAbsorption[MaterialLabel.WOOD_FLOOR],
    )
    ceiling_surface = Surface(
        kind="ceiling",
        polygon=_lift_polygon(list(reversed(floor)), height),
        material=MaterialLabel.CEILING_ACOUSTIC_TILE,
        absorption_500hz=MaterialAbsorption[MaterialLabel.CEILING_ACOUSTIC_TILE],
    )

    walls: list[Surface] = []
    for i in range(len(floor)):
        p0 = floor[i]
        p1 = floor[(i + 1) % len(floor)]
        walls.append(
            Surface(
                kind="wall",
                polygon=_wall_polygon(p0, p1, height),
                material=MaterialLabel.WALL_PAINTED,
                absorption_500hz=MaterialAbsorption[MaterialLabel.WALL_PAINTED],
            )
        )

    surfaces = [floor_surface, ceiling_surface, *walls]

    return RoomModel(
        name=name,
        floor_polygon=floor,
        ceiling_height_m=height,
        surfaces=surfaces,
        listener_area=listener,
    )
