"""Apple RoomPlan ``CapturedStructure`` -> N single-room ``RoomModel`` splitter.

Phase S1 (ADR 0050): walls + a per-room wall-hull footprint.
Phase S2: ``objects[]`` (free-standing furniture) assigned by the same
nearest-section-center heuristic, and ``doors``/``windows`` routed to a room via
``parentIdentifier`` -> the parent wall's room with a **re-based per-room
``wall_index``** (ADR 0037 walls-only frame), falling back to nearest-center with
``wall_index=None``.
Phase S3: ``openings[]`` ingested on the SAME path as walls (wall-like
surfaces); degenerate sections (< 3 assigned walls) emit a ``UserWarning`` carrying
:data:`~roomestim.reconstruct._disclosure.ROOMPLAN_STRUCTURE_SPLIT_NOTE` instead
of crashing; equidistant ties resolve to the lowest section index.

A real device-scan ``CapturedStructure`` export is a genuine multi-room capture,
but Apple gives **no element->room foreign key**: ``sections`` (= rooms) carry
only ``{label, story, center[x,y,z]}`` and ``walls/doors/windows/openings/
objects/floors`` are flat arrays with no room membership. This adapter therefore
assigns each wall to a section by a documented HEURISTIC (floor-plane
nearest-section-center, story-matched). The resulting per-room split is a
RECONSTRUCTION, not Apple-authoritative data — see
:data:`~roomestim.reconstruct._disclosure.ROOMPLAN_STRUCTURE_SPLIT_NOTE`.

This is an additive module: ``roomestim/adapters/roomplan.py`` (the single-room
sidecar path) is NOT edited; its sound helpers are reused by import.

Schema facts (re-verified by ``json.load`` on the real fixtures):
  * ``Section`` = ``{label, story, center[x,y,z]}`` only (no geometry).
  * ``Surface.category`` / ``confidence`` are single-key dicts (``{"wall": {}}``).
  * ``Surface.transform`` is a **flat 16-float column-major** simd_float4x4;
    ``reshape(4, 4).T`` puts the origin at column 3 and the width axis at column
    0 — exactly the contract of ``roomplan._wall_polygon_from_transform``.
  * ``floors[]`` has exactly ONE building-wide entry for ALL sections, so a
    per-room floor polygon does NOT exist in the export. The per-room footprint
    is therefore the floor-projected convex hull of that room's assigned walls
    (an over-estimate, NOT a measured floor polygon).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any, cast

import numpy as np
from shapely.geometry import MultiPoint, Polygon

from roomestim.adapters.roomplan import _extract_objects, _wall_polygon_from_transform
from roomestim.model import (
    DEFAULT_OBJECT_MATERIAL,
    MaterialAbsorption,
    MaterialLabel,
    Object,
    ObjectKind,
    Point2,
    Point3,
    RoomModel,
    Surface,
    canonicalize_ccw,
)
from roomestim.reconstruct._disclosure import ROOMPLAN_STRUCTURE_SPLIT_NOTE
from roomestim.reconstruct.listener_area import default_listener_area

__all__ = ["parse_structure"]

# Minimal half-extent (metres) of the synthetic footprint built for a degenerate
# section whose assigned walls do not span a finite-area polygon (< 3 distinct,
# non-collinear floor points). Keeps the model constructible without crashing;
# full degenerate-section warning hardening is Phase S3.
_DEGENERATE_HALF_EXTENT_M: float = 0.25


def _mat4_from_flat(flat: list[float]) -> np.ndarray:
    """Reshape a flat 16-float column-major simd_float4x4 into a 4x4 matrix.

    Apple serialises ``simd_float4x4`` column-major, so flat indices 12, 13, 14
    are the translation. ``np.asarray(flat).reshape(4, 4).T`` yields a matrix
    whose column 3 is the origin and column 0 is the local X (width) axis — the
    exact layout :func:`roomestim.adapters.roomplan._wall_polygon_from_transform`
    consumes (``transform[:3, 3]`` = origin, ``transform[:3, 0]`` = width axis).
    """
    arr = np.asarray(flat, dtype=float)
    if arr.shape != (16,):
        raise ValueError(
            f"CapturedStructure transform must be 16 flat floats; got {arr.shape}"
        )
    return cast("np.ndarray", arr.reshape(4, 4).T)


def _enum_key(value: Any) -> str:
    """Extract the category/confidence enum from its single-key-dict encoding.

    RoomPlan encodes ``category``/``confidence`` as a one-entry dict
    (``{"wall": {}}`` -> ``"wall"``). Falls back to ``str(value)`` for any
    non-dict encoding so the parser never crashes on schema drift.
    """
    if isinstance(value, dict) and value:
        return str(next(iter(value)))
    return str(value)


def _nearest_section(
    ox: float,
    oz: float,
    story: int,
    centers_xz: list[tuple[float, float]],
    stories: list[int],
) -> int:
    """Return the index of the nearest section center in the floor plane.

    HEURISTIC, load-bearing honesty: an element is assigned to the story-matched
    section whose ``center`` is nearest in ``(x, z)`` to the element origin.
    Equidistant ties resolve to the lowest section index (strict ``<`` keeps the
    first-seen winner => deterministic). If no section shares the element's story,
    falls back to the global nearest (never drop an element). Section ``center.y``
    is a constant structure-mean, so it carries no vertical signal and is ignored.
    """
    best_idx = -1
    best_d2 = float("inf")
    for s_idx, (cx, cz) in enumerate(centers_xz):
        if stories[s_idx] != story:
            continue
        d2 = (ox - cx) ** 2 + (oz - cz) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_idx = s_idx
    if best_idx < 0:
        for s_idx, (cx, cz) in enumerate(centers_xz):
            d2 = (ox - cx) ** 2 + (oz - cz) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_idx = s_idx
    return best_idx


def _assign_walls_to_sections(
    walls: list[dict[str, Any]], sections: list[dict[str, Any]]
) -> list[list[int]]:
    """Partition wall indices across sections (HEURISTIC, load-bearing honesty).

    Each wall is assigned via :func:`_nearest_section` (story-matched
    nearest-center, lowest-index tie-break). Returns a list parallel to
    ``sections``; ``result[s]`` is the list of wall indices assigned to section
    ``s``. Partition invariant: every wall index appears in exactly one section's
    list.
    """
    centers_xz = [(float(s["center"][0]), float(s["center"][2])) for s in sections]
    stories = [int(s.get("story", 0)) for s in sections]
    buckets: list[list[int]] = [[] for _ in sections]
    for w_idx, wall in enumerate(walls):
        mat = _mat4_from_flat(list(wall["transform"]))
        ox, oz = float(mat[0, 3]), float(mat[2, 3])
        w_story = int(wall.get("story", 0))
        best_idx = _nearest_section(ox, oz, w_story, centers_xz, stories)
        buckets[best_idx].append(w_idx)
    return buckets


def _assign_objects_to_sections(
    objects: list[dict[str, Any]], sections: list[dict[str, Any]]
) -> list[list[Object]]:
    """Assign free-standing furniture objects to sections (S2).

    Each raw object is routed to a section by the same nearest-section-center
    heuristic (anchor = ``transform`` col 3, story-matched). Per section, the
    routed raw entries are normalised into the sidecar shape consumed by
    :func:`roomestim.adapters.roomplan._extract_objects` (flat-16 transform ->
    4x4 nested list, enum-dict category -> string) and run through that EXACT
    policy, so sofa/table/bed/storage are kept as free-standing boxes and
    chair/sink/toilet are dropped — identical to the single-room RoomPlan path.

    Returns a list parallel to ``sections``; ``result[s]`` is the kept objects for
    section ``s`` (doors/windows are handled separately).
    """
    centers_xz = [(float(s["center"][0]), float(s["center"][2])) for s in sections]
    stories = [int(s.get("story", 0)) for s in sections]
    raw_by_section: list[list[dict[str, Any]]] = [[] for _ in sections]
    for entry in objects:
        transform = entry.get("transform")
        if transform is None:
            continue
        mat = _mat4_from_flat(list(transform))
        ox, oz = float(mat[0, 3]), float(mat[2, 3])
        story = int(entry.get("story", 0))
        s_idx = _nearest_section(ox, oz, story, centers_xz, stories)
        raw_by_section[s_idx].append(
            {
                "category": _enum_key(entry.get("category")),
                "transform": mat.tolist(),
                "dimensions": entry.get("dimensions", [0.0, 0.0, 0.0]),
            }
        )
    return [_extract_objects({"objects": raw}) for raw in raw_by_section]


def _assign_openings_to_sections(
    openings: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    wall_id_to_loc: dict[str, tuple[int, int]],
    walls_per_section: list[int],
) -> list[list[Object]]:
    """Route doors/windows to a section and re-base their ``wall_index`` (S2).

    PRIMARY: ``parentIdentifier`` -> the parent wall's section, with
    ``wall_index`` re-based into that section's walls-only frame (ADR 0037 /
    ``wall_surfaces`` ordering). FALLBACK (parent missing/unresolved): nearest
    section center with ``wall_index=None`` (the predictor ignores a ``None``
    index). ``walls_per_section`` is unused for routing but documents the per-room
    wall count the re-based index is bounded against by the caller's guard.

    Returns a list parallel to ``sections``; ``result[s]`` is the door/window
    :class:`Object` list for section ``s``.
    """
    del walls_per_section  # bound by _room_from_section's ADR 0037 guard
    centers_xz = [(float(s["center"][0]), float(s["center"][2])) for s in sections]
    stories = [int(s.get("story", 0)) for s in sections]
    by_section: list[list[Object]] = [[] for _ in sections]
    for entry in openings:
        cat = _enum_key(entry.get("category"))
        kind: ObjectKind
        if "door" in cat:
            kind = "door"
        elif "window" in cat:
            kind = "window"
        else:
            continue  # not a door/window opening
        transform = entry.get("transform")
        if transform is None:
            continue
        mat = _mat4_from_flat(list(transform))
        anchor = Point3(float(mat[0, 3]), float(mat[1, 3]), float(mat[2, 3]))
        dims = entry.get("dimensions", [0.0, 0.0, 0.0])
        width_m = float(dims[0]) if len(dims) > 0 else 0.0
        height_m = float(dims[1]) if len(dims) > 1 else 0.0

        parent = entry.get("parentIdentifier")
        loc = wall_id_to_loc.get(parent) if parent is not None else None
        wall_index: int | None
        if loc is not None:
            s_idx, wall_index = loc
        else:
            story = int(entry.get("story", 0))
            s_idx = _nearest_section(
                anchor.x, anchor.z, story, centers_xz, stories
            )
            wall_index = None
        by_section[s_idx].append(
            Object(
                kind=kind,
                anchor=anchor,
                width_m=width_m,
                height_m=height_m,
                depth_m=0.0,
                wall_index=wall_index,
                material=DEFAULT_OBJECT_MATERIAL[kind],
            )
        )
    return by_section


def _section_footprint(
    wall_polys: list[list[Point3]], center_xz: tuple[float, float]
) -> tuple[list[Point2], bool]:
    """Build a per-room footprint = floor-projected convex hull of wall corners.

    Returns ``(polygon_2d_ccw, degenerate)``. ``degenerate`` is ``True`` when the
    assigned walls do not span a finite-area polygon (< 3 distinct, non-collinear
    floor points), in which case a minimal box around the available points (or
    the section center) is returned so the model stays constructible. The hull
    over-estimates concave rooms — it is NOT a measured floor polygon.
    """
    pts_xz = [(p.x, p.z) for poly in wall_polys for p in poly]
    if pts_xz:
        hull = MultiPoint(pts_xz).convex_hull
        if isinstance(hull, Polygon) and hull.area > 0.0:
            coords = list(hull.exterior.coords)[:-1]  # drop the closing duplicate
            poly = [Point2(float(x), float(z)) for x, z in coords]
            return canonicalize_ccw(poly), False
        cx = float(np.mean([p[0] for p in pts_xz]))
        cz = float(np.mean([p[1] for p in pts_xz]))
    else:
        cx, cz = center_xz
    h = _DEGENERATE_HALF_EXTENT_M
    box = [
        Point2(cx - h, cz - h),
        Point2(cx + h, cz - h),
        Point2(cx + h, cz + h),
        Point2(cx - h, cz + h),
    ]
    return canonicalize_ccw(box), True


def _unique_name(label: str, seen: dict[str, int]) -> str:
    """Deterministic per-room name; duplicate labels get a ``-N`` suffix.

    First ``bedroom`` -> ``"bedroom"``, second -> ``"bedroom-2"`` (1-based count,
    so the suffix matches the human ordinal). ``seen`` is mutated.
    """
    seen[label] = seen.get(label, 0) + 1
    n = seen[label]
    return label if n == 1 else f"{label}-{n}"


def _room_from_section(
    section: dict[str, Any],
    name: str,
    walls: list[dict[str, Any]],
    wall_indices: list[int],
    *,
    fallback_height_m: float,
    objects: list[Object] | None = None,
) -> RoomModel:
    """Build one single-room :class:`RoomModel` from a section's assigned walls.

    ``ceiling_height_m`` is the median assigned wall height (RoomPlan captures no
    ceiling — it is SYNTHESIZED; ``ceiling_coverage=None``,
    ``ceiling_confidence="unknown"``). Materials are UNKNOWN (no hint in the
    export). ``provenance="measured"`` (LiDAR geometry); the heuristic room
    MEMBERSHIP is conveyed by the disclosure note + CLI warning, NOT by the
    provenance literal. ``objects`` (S2) is the section's assigned furniture +
    doors/windows; each door/window ``wall_index`` is bounded against this room's
    walls-only frame (ADR 0037) so a cross-room index cannot leak.
    """
    wall_polys: list[list[Point3]] = []
    heights: list[float] = []
    floor_ys: list[float] = []
    for w_idx in wall_indices:
        wall = walls[w_idx]
        dims = wall.get("dimensions", [0.0, 0.0, 0.0])
        width_m = float(dims[0]) if len(dims) > 0 else 0.0
        height_m = float(dims[1]) if len(dims) > 1 and float(dims[1]) > 0.0 else 0.0
        if height_m <= 0.0:
            height_m = fallback_height_m
        mat = _mat4_from_flat(list(wall["transform"]))
        polygon = _wall_polygon_from_transform(mat.tolist(), width_m, height_m)
        wall_polys.append(polygon)
        heights.append(height_m)
        floor_ys.append(min(p.y for p in polygon))

    ceiling_height_m = float(np.median(heights)) if heights else fallback_height_m
    floor_y = float(np.median(floor_ys)) if floor_ys else 0.0

    center_xz = (float(section["center"][0]), float(section["center"][2]))
    footprint_2d, _degenerate = _section_footprint(wall_polys, center_xz)

    floor_material = MaterialLabel.UNKNOWN
    floor_surface = Surface(
        kind="floor",
        polygon=[Point3(p.x, floor_y, p.z) for p in footprint_2d],
        material=floor_material,
        absorption_500hz=MaterialAbsorption[floor_material],
    )
    wall_surfaces: list[Surface] = []
    for polygon in wall_polys:
        material = MaterialLabel.UNKNOWN
        wall_surfaces.append(
            Surface(
                kind="wall",
                polygon=polygon,
                material=material,
                absorption_500hz=MaterialAbsorption[material],
            )
        )

    surfaces: list[Surface] = [floor_surface, *wall_surfaces]
    listener = default_listener_area(footprint_2d)

    room_objects = objects or []
    # ADR 0037 / D69: bound each door/window's re-based wall_index against THIS
    # room's walls-only frame. A cross-room or stale index would otherwise
    # silently downgrade the room RT60 to Eyring at predict time. Mirrors the
    # single-room RoomPlanAdapter guard exactly.
    n_walls = len(wall_surfaces)
    for obj in room_objects:
        if obj.kind in ("door", "window") and obj.wall_index is not None:
            if not (0 <= obj.wall_index < n_walls):
                raise ValueError(
                    f"object wall_index={obj.wall_index} out of range "
                    f"[0, {n_walls}); room '{name}' has {n_walls} walls."
                )

    return RoomModel(
        name=name,
        floor_polygon=footprint_2d,
        ceiling_height_m=ceiling_height_m,
        surfaces=surfaces,
        listener_area=listener,
        objects=room_objects,
        schema_version="0.2-draft",
        provenance="measured",  # LiDAR geometry; membership heuristic via disclosure
    )


def parse_structure(path: Path | str) -> list[RoomModel]:
    """Parse a RoomPlan ``CapturedStructure`` JSON into N single-room models.

    One :class:`~roomestim.model.RoomModel` per ``section`` (INCLUDING
    ``unidentified``), in section order. Walls are partitioned across sections by
    the documented floor-plane nearest-section-center heuristic (see
    :func:`_assign_walls_to_sections`); the partition is total (every wall to
    exactly one section). The per-room split is a RECONSTRUCTION — see
    :data:`~roomestim.reconstruct._disclosure.ROOMPLAN_STRUCTURE_SPLIT_NOTE`.

    Phase S2 adds furniture objects + doors/windows (re-based per-room
    ``wall_index``); Phase S3 ingests ``openings[]`` on the wall path and emits a
    ``UserWarning`` for degenerate sections (< 3 assigned walls).
    """
    path_obj = Path(path)
    suffix = path_obj.suffix.lower()
    if suffix != ".json":
        raise ValueError(
            f"parse_structure: unsupported extension {suffix!r}; expected a "
            "CapturedStructure .json export."
        )
    with path_obj.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)

    sections: list[dict[str, Any]] = list(data.get("sections", []))
    if not sections:
        raise ValueError(
            "parse_structure: CapturedStructure has no sections[]; cannot build "
            "per-room models."
        )
    # Walls + openings share the wall path (S3): an opening is a wall-like surface
    # (a gap in a wall). Both partition into sections and become wall surfaces, so
    # the walls-only frame the door/window wall_index re-bases against (ADR 0037)
    # includes them. (The real multiroom fixture has 0 openings, so this is
    # additive for it.)
    walls: list[dict[str, Any]] = [
        w for w in data.get("walls", []) if _enum_key(w.get("category")) == "wall"
    ]
    walls += list(data.get("openings", []))

    # Robust building-wide fallback height for sections/walls lacking a height.
    all_heights = [
        float(w["dimensions"][1])
        for w in walls
        if len(w.get("dimensions", [])) > 1 and float(w["dimensions"][1]) > 0.0
    ]
    fallback_height_m = float(np.median(all_heights)) if all_heights else 2.44

    buckets = _assign_walls_to_sections(walls, sections)

    # Map each wall's UUID -> (section index, re-based per-room wall index) so
    # doors/windows can follow their parent wall into the right room (S2).
    wall_id_to_loc: dict[str, tuple[int, int]] = {}
    for s_idx, bucket in enumerate(buckets):
        for local_idx, w_idx in enumerate(bucket):
            wall_id = walls[w_idx].get("identifier")
            if wall_id is not None:
                wall_id_to_loc[str(wall_id)] = (s_idx, local_idx)

    furniture_by_section = _assign_objects_to_sections(
        list(data.get("objects", [])), sections
    )
    opening_objs = (
        _assign_openings_to_sections(
            list(data.get("doors", [])),
            sections,
            wall_id_to_loc,
            [len(b) for b in buckets],
        ),
        _assign_openings_to_sections(
            list(data.get("windows", [])),
            sections,
            wall_id_to_loc,
            [len(b) for b in buckets],
        ),
    )

    rooms: list[RoomModel] = []
    seen: dict[str, int] = {}
    for s_idx, section in enumerate(sections):
        label = str(section.get("label", "room"))
        name = _unique_name(label, seen)
        if len(buckets[s_idx]) < 3:
            # Degenerate section: < 3 walls cannot bound a confident footprint.
            # Warn (not crash) and fall through to the minimal low-confidence
            # footprint in _section_footprint. Single-source disclosure message.
            warnings.warn(
                f"section '{name}' has {len(buckets[s_idx])} assigned wall(s) "
                f"(< 3): footprint is LOW-CONFIDENCE. {ROOMPLAN_STRUCTURE_SPLIT_NOTE}",
                UserWarning,
                stacklevel=2,
            )
        room_objects = [
            *furniture_by_section[s_idx],
            *opening_objs[0][s_idx],
            *opening_objs[1][s_idx],
        ]
        rooms.append(
            _room_from_section(
                section,
                name,
                walls,
                buckets[s_idx],
                fallback_height_m=fallback_height_m,
                objects=room_objects,
            )
        )
    return rooms
