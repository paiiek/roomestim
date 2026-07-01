"""roomestim_server.rooms — built-in synthetic room registry + geometry serialiser.

P5.1 ships ONE deterministic built-in shoebox (``builtin:shoebox``) constructed
directly as a :class:`roomestim.model.RoomModel` (no external file, no adapter
deps), mirroring ``tests/fixtures/synthetic_rooms.py::shoebox`` so the viewer is
unblocked without solving capture ingest (upload→adapter is deferred to P5.4).

The serialiser emits GEOMETRY ONLY (floor polygon, ceiling height, listener area,
walls-from-surfaces) — NO physics. Pure-Python (core import only, no fastapi /
pydantic), so it stays on the right side of the ``[server]`` extra boundary.
"""

from __future__ import annotations

from typing import Callable

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

__all__ = [
    "BUILTIN_SHOEBOX_ID",
    "list_rooms",
    "get_room",
    "room_geometry_to_dict",
]

#: The single built-in room id shipped in P5.1.
BUILTIN_SHOEBOX_ID = "builtin:shoebox"


def _wall_polygon(p0: Point2, p1: Point2, height: float) -> list[Point3]:
    """Vertical rectangular wall polygon (floor-p0, floor-p1, top-p1, top-p0)."""
    return [
        Point3(p0.x, 0.0, p0.z),
        Point3(p1.x, 0.0, p1.z),
        Point3(p1.x, height, p1.z),
        Point3(p0.x, height, p0.z),
    ]


def _lift_polygon(polygon: list[Point2], y: float) -> list[Point3]:
    return [Point3(p.x, y, p.z) for p in polygon]


def _build_shoebox(
    width: float = 5.0,
    depth: float = 4.0,
    height: float = 3.0,
    name: str = "builtin shoebox 5x4x3",
) -> RoomModel:
    """Deterministic origin-centred CCW shoebox (mirrors the test fixture).

    Replicated locally rather than imported from ``tests/`` so production code
    never depends on the test tree. A valid :class:`ListenerArea` is attached
    (the trade-off engine evaluates the SPL field over it).
    """
    hw, hd = width / 2.0, depth / 2.0

    floor = canonicalize_ccw(
        [
            Point2(-hw, -hd),
            Point2(hw, -hd),
            Point2(hw, hd),
            Point2(-hw, hd),
        ]
    )

    listener_polygon = canonicalize_ccw(
        [
            Point2(-0.75, -0.75),
            Point2(0.75, -0.75),
            Point2(0.75, 0.75),
            Point2(-0.75, 0.75),
        ]
    )
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

    return RoomModel(
        name=name,
        floor_polygon=floor,
        ceiling_height_m=height,
        surfaces=[floor_surface, ceiling_surface, *walls],
        listener_area=listener,
    )


#: Builder registry — each entry constructs a FRESH RoomModel on demand (RoomModel
#: is mutable, so a fresh build per request avoids accidental shared-state edits).
_ROOM_BUILDERS: dict[str, Callable[[], RoomModel]] = {
    BUILTIN_SHOEBOX_ID: _build_shoebox,
}


def get_room(room_id: str) -> RoomModel:
    """Return a fresh built-in :class:`RoomModel` for ``room_id``.

    Raises ``KeyError`` for an unknown id (the caller maps it to 404 on the
    geometry endpoint, or to a generic 400 inside the evaluate path).
    """
    builder = _ROOM_BUILDERS[room_id]
    return builder()


def _footprint_summary(room: RoomModel) -> dict[str, object]:
    """Axis-aligned bounding-box summary of the floor polygon (geometry only)."""
    xs = [p.x for p in room.floor_polygon]
    zs = [p.z for p in room.floor_polygon]
    return {
        "width_m": round(max(xs) - min(xs), 3) if xs else 0.0,
        "depth_m": round(max(zs) - min(zs), 3) if zs else 0.0,
        "ceiling_height_m": round(room.ceiling_height_m, 3),
        "n_vertices": len(room.floor_polygon),
    }


def list_rooms() -> list[dict[str, object]]:
    """List the built-in rooms with id, name, and a footprint summary."""
    out: list[dict[str, object]] = []
    for room_id in _ROOM_BUILDERS:
        room = get_room(room_id)
        out.append(
            {
                "id": room_id,
                "name": room.name,
                "footprint": _footprint_summary(room),
            }
        )
    return out


def room_geometry_to_dict(room: RoomModel, room_id: str) -> dict[str, object]:
    """Serialise GEOMETRY ONLY for rendering (no physics, no materials).

    Emits the floor polygon (x,z), ceiling height, listener area (polygon +
    centroid + height), and the wall surfaces as 3-D polygons. Materials /
    absorption / RT60 are intentionally NOT exposed here.
    """
    listener = room.listener_area
    walls = [
        {
            "kind": surf.kind,
            "polygon": [{"x": p.x, "y": p.y, "z": p.z} for p in surf.polygon],
        }
        for surf in room.surfaces
        if surf.kind == "wall"
    ]
    return {
        "id": room_id,
        "name": room.name,
        "ceiling_height_m": round(room.ceiling_height_m, 3),
        "floor_polygon": [{"x": p.x, "z": p.z} for p in room.floor_polygon],
        "listener_area": {
            "polygon": [{"x": p.x, "z": p.z} for p in listener.polygon],
            "centroid": {"x": listener.centroid.x, "z": listener.centroid.z},
            "height_m": listener.height_m,
        },
        "walls": walls,
    }
