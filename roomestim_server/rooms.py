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
import dataclasses
import threading
from typing import Callable

from roomestim.model import (
    FREESTANDING_OBJECT_KINDS,
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


def _recenter_to_listener_origin(room: RoomModel) -> RoomModel:
    """Rigid-translate ``room`` into the canonical listener-centric frame (Frame A).

    The tool's canonical frame — matching the built-in shoebox, the viewer SEED,
    and the ``evaluate_layout`` listener sampling (which puts the ear plane at
    ``listener_area.height_m`` and treats speaker ``y`` as absolute) — is:

    * floor at ``y = 0``;
    * listener-area centroid at the horizontal origin ``x = z = 0``;
    * seeded (el=0) speakers at ear height ``y = listener_area.height_m``.

    Captured/uploaded rooms arrive in their OWN world frame (e.g. the real Apple
    RoomPlan living-room floor sits near ``x≈1.22, z≈0.04`` with the floor at
    ``y≈−1.02``), so the origin-centric SEED / placement speakers float off
    relative to them AND ``evaluate_layout`` compares speaker↔listener across
    mismatched frames. This normaliser removes that mismatch at the single upload
    choke point.

    The transform is a PURE RIGID TRANSLATION by ``(−dx, −dy, −dz)`` — no
    rotation, scale, or geometry recompute — so it is physics-preserving (every
    surface area / material / RT60 input is invariant under translation):

    * ``dx = listener_area.centroid.x``, ``dz = listener_area.centroid.z``;
    * ``dy = `` the floor height = the MINIMUM ``y`` over every ``Surface``
      polygon point (``0`` for a degenerate surface-less room).

    ``listener_area.height_m`` is floor-relative and is left UNCHANGED. Free-standing
    object anchors (columns/furniture) are world-frame base centres and ARE
    translated so they stay attached; door/window anchors are WALL-LOCAL
    (:data:`WALL_ATTACHED_OBJECT_KINDS`) so they are left untouched. Object
    width/height/depth are relative extents and never move. Returns a NEW
    :class:`RoomModel` (the caller's input is untouched). Idempotent: an
    already-canonical room (all offsets ``0``) is returned unchanged.
    """
    dx = room.listener_area.centroid.x
    dz = room.listener_area.centroid.z
    ys = [p.y for surf in room.surfaces for p in surf.polygon]
    dy = min(ys) if ys else 0.0

    if dx == 0.0 and dy == 0.0 and dz == 0.0:
        return room  # already canonical (e.g. the built-in shoebox) — no-op

    def _t2(p: Point2) -> Point2:
        return Point2(p.x - dx, p.z - dz)

    def _t3(p: Point3) -> Point3:
        return Point3(p.x - dx, p.y - dy, p.z - dz)

    listener = room.listener_area
    return dataclasses.replace(
        room,
        floor_polygon=[_t2(p) for p in room.floor_polygon],
        surfaces=[
            dataclasses.replace(s, polygon=[_t3(p) for p in s.polygon])
            for s in room.surfaces
        ],
        listener_area=dataclasses.replace(
            listener,
            polygon=[_t2(p) for p in listener.polygon],
            centroid=_t2(listener.centroid),
        ),
        objects=[
            dataclasses.replace(o, anchor=_t3(o.anchor))
            if o.kind in FREESTANDING_OBJECT_KINDS
            else o
            for o in room.objects
        ],
    )


def register_uploaded_room(room: RoomModel) -> str:
    """Store an uploaded ``room`` and return its ``"uploaded:<n>"`` id.

    The room is first normalised to the canonical listener-centric frame (Frame A)
    via :func:`_recenter_to_listener_origin` — this single choke point catches
    EVERY uploaded room (room.yaml / RoomPlan / CapturedStructure / mesh /
    load_example) so the viewer render, the SEED, and ``evaluate_layout`` all agree
    on one frame (floor at ``y=0``, listener centroid at the horizontal origin).

    Evicts the OLDEST uploaded room once the count exceeds :data:`_UPLOADED_CAP`
    so the registry stays memory-bounded (see the module docstring for the
    deliberate-statefulness rationale). Thread-safe via :data:`_UPLOAD_LOCK`.
    """
    room = _recenter_to_listener_origin(room)
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
