"""roomestim_server.rooms — built-in synthetic room registry + geometry serialiser.

P5.1 ships ONE deterministic built-in shoebox (``builtin:shoebox``) constructed
directly as a :class:`roomestim.model.RoomModel` (no external file, no adapter
deps), mirroring ``tests/fixtures/synthetic_rooms.py::shoebox`` so the viewer is
unblocked without solving capture ingest (upload→adapter is deferred to P5.4).

The serialiser emits GEOMETRY ONLY (floor polygon, ceiling height, listener area,
walls-from-surfaces) — NO physics. Pure-Python (core import only, no fastapi /
pydantic), so it stays on the right side of the ``[server]`` extra boundary.

Uploaded rooms (P5.4): a room.yaml uploaded via ``POST /api/rooms/upload`` is
parsed by core ``read_room_yaml`` and kept in a PROCESS-LOCAL, NON-PERSISTENT,
BOUNDED registry (:data:`_UPLOADED`, cap :data:`_UPLOADED_CAP`). This is a
DELIBERATE, bounded exception to the otherwise-stateless server — acceptable for a
single-user localhost tool: uploaded rooms vanish on restart, are NOT shared
across workers, and the oldest is evicted once the cap is exceeded so memory is
bounded. Everything else (evaluate/place) stays stateless.
"""

from __future__ import annotations

import copy
import threading
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
    "register_uploaded_room",
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

#: Maximum number of uploaded rooms retained at once (oldest evicted past this).
_UPLOADED_CAP = 32

#: Process-local, non-persistent, bounded registry of uploaded rooms keyed by
#: ``"uploaded:<n>"`` (insertion order preserved for oldest-first eviction). A
#: deliberate bounded exception to the stateless server — see the module docstring.
_UPLOADED: dict[str, RoomModel] = {}

#: Monotone counter for uploaded-room ids (never reused, so a stale client id can
#: never alias a newer upload). Not reset even after eviction.
_UPLOADED_SEQ = 0

#: Guards the mutations of :data:`_UPLOADED` / :data:`_UPLOADED_SEQ`. Sync FastAPI
#: endpoints run in the anyio threadpool, so concurrent uploads could otherwise
#: race on the non-atomic counter increment + eviction; the lock makes register /
#: read atomic (cheap — held only around dict/int ops).
_UPLOAD_LOCK = threading.Lock()


def register_uploaded_room(room: RoomModel) -> str:
    """Store an uploaded ``room`` and return its ``"uploaded:<n>"`` id.

    Evicts the OLDEST uploaded room once the count exceeds :data:`_UPLOADED_CAP`
    so the registry stays memory-bounded (see the module docstring for the
    deliberate-statefulness rationale). Thread-safe via :data:`_UPLOAD_LOCK`.
    """
    global _UPLOADED_SEQ
    with _UPLOAD_LOCK:
        _UPLOADED_SEQ += 1
        room_id = f"uploaded:{_UPLOADED_SEQ}"
        _UPLOADED[room_id] = room
        while len(_UPLOADED) > _UPLOADED_CAP:
            oldest = next(iter(_UPLOADED))
            del _UPLOADED[oldest]
    return room_id


def get_room(room_id: str) -> RoomModel:
    """Return a fresh :class:`RoomModel` for ``room_id`` (built-in or uploaded).

    Built-in builders are consulted FIRST (a fresh build per request), then the
    uploaded registry (a ``deepcopy`` is returned so a stored room is never
    mutated by a caller — preserving the no-shared-state invariant the built-in
    builders already have). Raises ``KeyError`` for an unknown id (the caller
    maps it to 404 on the geometry endpoint, or to a generic 400 in evaluate).
    """
    builder = _ROOM_BUILDERS.get(room_id)
    if builder is not None:
        return builder()
    with _UPLOAD_LOCK:  # atomic read vs a concurrent eviction
        return copy.deepcopy(_UPLOADED[room_id])


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
