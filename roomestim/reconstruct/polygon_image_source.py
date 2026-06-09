"""Polygon image-source GEOMETRY-only enumerator (v0.31.0; ADR 0040).

**GEOMETRY ONLY — this is NOT an acoustic predictor.** This module enumerates
first-order image-source *positions* for an extruded simple polygon (a
``floor_polygon`` in the xz floor plane + a scalar ``ceiling_height_m``), by
mirroring a source point across each wall plane (and, optionally, the floor and
ceiling planes). Each enumerated image carries a deterministic shapely-based
visibility/validity flag. The module emits **NO RT60 and NO acoustic number**
and is deliberately **NOT wired into** :mod:`roomestim.reconstruct.predictor`
or :mod:`roomestim.reconstruct.image_source` (shoebox RT60 stays byte-equal).

Why geometry only (ADR 0040 §Status-update; 가짜 숫자 금지):

  - Polygon-ISM **RT60** is DEFERRED — there is no non-shoebox MEASURED
    ground-truth corpus, so any polygon RT60 magnitude is unverifiable
    (ADR 0040 §G); the web ISM-library RT60 Schroeder-fit on a sparse ISM-only
    RIR is itself unverified (ADR 0040 §B); and that library is a *web-extra*,
    so any RT60 path built on it would carry a default-lane reproducibility
    asymmetry (ADR 0040 §C2). The full rationale is the single-source
    disclosure :data:`POLYGON_ISM_GEOMETRY_NOTE` — do not retype it.
  - The deterministic, in-gate-verifiable part — image-source **positions** +
    visibility — is exactly what this module provides. It is the honest
    foundation a future cycle could turn into RT60 *once a measured
    non-shoebox GT exists*.
  - A receiver-relative first-order **path length** (metres) / **TOA** (seconds)
    is likewise pure geometry — the image-source identity ``‖image − receiver‖``
    — and is emitted with still **NO RT60, NO absorption, NO energy**.

Core purity: this module imports only numpy + shapely (both core
dependencies) and the core disclosure string — NO web-extra ISM library — so
it runs in the default gate lane.

Geometry conventions (matching :class:`roomestim.model.Point2` /
:class:`roomestim.model.Point3`):

  - The floor polygon lives in the floor plane spanned by ``(x, z)``
    (:class:`Point2` is ``(x, z)``); the room is extruded vertically along
    ``y`` from the floor plane ``y = 0`` to the ceiling plane
    ``y = ceiling_height_m``.
  - A *wall* is the vertical plane containing one polygon edge (the segment
    between two consecutive vertices), spanning all ``y``. Mirroring across a
    wall leaves ``y`` unchanged and reflects the source ``(x, z)`` across the
    edge's supporting line.
  - The *floor* plane is ``y = 0`` (mirror: ``y -> -y``); the *ceiling* plane
    is ``y = ceiling_height_m`` (mirror: ``y -> 2*H - y``).

Visibility/validity test (deterministic, shapely):

  For a wall image, the **reflection point** is the foot of the perpendicular
  dropped from the source onto the edge's supporting line (the specular hit
  point for a receiver co-located with the source). The ``valid`` flag is an
  **on-segment specular test** (necessary, NOT sufficient for full
  visibility): it is ``True`` iff that foot lies *on the finite wall segment* —
  tested via ``shapely.LineString(edge).distance(Point(foot)) <= tol_m``. It
  does NOT test path occlusion by other walls, so on a non-convex room a
  ``valid=True`` image can still be physically occluded (a false positive for
  *true* visibility). This is the same shapely "is the reflection point on the
  wall" idea proven in ``roomestim_web/binaural.py``'s ``_image_inside_floor``
  (kept core here, no web dependency). For an axis-aligned rectangle/shoebox
  every wall foot lies on its segment; for a **non-convex** polygon (e.g. an
  L-shape) an edge's supporting line can put the foot *off* the finite segment,
  and that image is pruned (``valid = False``) — a convex assumption would
  wrongly keep it. (Even for some convex polygons the perpendicular foot from
  an interior source can fall off an edge; only the shoebox case is tested.)
  Floor and ceiling images use the source's ``(x, z)`` as the reflection point
  and are valid iff that point lies within the polygon footprint.

References:
- ADR 0040 (polygon-ISM design; §A option (a) scoped strictly to geometry,
  §G verification, §Status-update geometry-only landing + RT60 DEFER).
- Allen, J. B. & Berkley, D. A. (1979). Image method for efficiently
  simulating small-room acoustics. JASA 65(4), 943-950.
- :data:`roomestim.reconstruct._disclosure.POLYGON_ISM_GEOMETRY_NOTE` —
  single source of truth for the geometry-only disclosure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np
from shapely.geometry import LineString, Point as ShapelyPoint, Polygon

from roomestim.model import Point2, Point3
from roomestim.reconstruct._disclosure import POLYGON_ISM_GEOMETRY_NOTE

__all__ = [
    "ImagePath",
    "ImageSource",
    "POLYGON_ISM_GEOMETRY_NOTE",
    "first_order_image_sources",
    "first_order_path_lengths",
]

# Surface that produced an image source.
ImageSurfaceKind = Literal["wall", "floor", "ceiling"]


@dataclass(frozen=True)
class ImageSource:
    """A single first-order image-source POSITION (geometry only, no acoustics).

    Attributes
    ----------
    position:
        The mirrored source position (:class:`Point3`, listener-frame
        ``x``/``y``/``z`` in metres).
    surface_kind:
        Which surface produced the mirror: ``"wall"``, ``"floor"`` or
        ``"ceiling"``.
    wall_index:
        For a wall image, the index of the polygon edge that produced it
        (edge ``i`` joins ``floor_polygon[i]`` and
        ``floor_polygon[(i + 1) % n]``). ``None`` for floor / ceiling images.
    reflection_point:
        The specular reflection point on the surface (:class:`Point3`): the
        foot of the perpendicular from the source onto the wall's supporting
        line for a wall, or the source's ``(x, z)`` at the floor/ceiling height
        for floor/ceiling images.
    valid:
        ``True`` iff the reflection point lies on the finite wall segment
        (wall) or within the polygon footprint (floor/ceiling). A convex room
        keeps every wall image; a non-convex room may prune some.
    """

    position: Point3
    surface_kind: ImageSurfaceKind
    wall_index: int | None
    reflection_point: Point3
    valid: bool


@dataclass(frozen=True)
class ImagePath:
    """A receiver-relative first-order path length / TOA (geometry only).

    GEOMETRY ONLY — no RT60, no absorption, no energy. By the image-source
    identity, the broken ``source -> surface -> receiver`` path length of a
    first-order reflection equals the straight-line distance from the mirrored
    image position to the receiver.

    Attributes
    ----------
    image:
        The first-order :class:`ImageSource` this path belongs to.
    receiver:
        The receiver position (:class:`Point3`, metres) the path terminates at.
    path_length_m:
        ``‖image.position − receiver‖`` in metres — the broken reflected-path
        length (geometry only).
    toa_s:
        ``path_length_m / sound_speed_m_s`` in seconds when a sound speed was
        supplied, else ``None``. A time-of-arrival, not an acoustic magnitude.
    """

    image: ImageSource
    receiver: Point3
    path_length_m: float
    toa_s: float | None


def _reflect_point_across_line_2d(
    point_xz: tuple[float, float],
    seg_a: tuple[float, float],
    seg_b: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Reflect ``point_xz`` across the line through ``seg_a`` and ``seg_b``.

    Returns ``(reflected_xz, foot_xz)`` where ``foot_xz`` is the foot of the
    perpendicular from ``point_xz`` onto the supporting line. ``seg_a`` and
    ``seg_b`` must be distinct (zero-length edges are filtered by the caller).
    """
    px, pz = point_xz
    ax, az = seg_a
    bx, bz = seg_b
    dx = bx - ax
    dz = bz - az
    denom = dx * dx + dz * dz
    # Fail loud on a degenerate (zero/near-zero-length) edge: a tiny denom
    # would otherwise yield a huge `t` and a garbage foot. The caller filters
    # exact seg_a == seg_b, but a distinct-but-near-coincident pair must not
    # silently produce a meaningless reflection.
    if denom <= 1e-18:
        raise ValueError(
            "polygon image-source: degenerate edge (near-zero length) "
            f"between {seg_a} and {seg_b}; cannot reflect."
        )
    t = ((px - ax) * dx + (pz - az) * dz) / denom
    foot_x = ax + t * dx
    foot_z = az + t * dz
    reflected_x = 2.0 * foot_x - px
    reflected_z = 2.0 * foot_z - pz
    return (reflected_x, reflected_z), (foot_x, foot_z)


def first_order_image_sources(
    floor_polygon: Sequence[Point2],
    ceiling_height_m: float,
    source: Point3,
    *,
    include_floor_ceiling: bool = True,
    tol_m: float = 1e-9,
) -> list[ImageSource]:
    """Enumerate first-order image-source POSITIONS for an extruded polygon.

    GEOMETRY ONLY — emits no RT60 / acoustic number (see module docstring and
    :data:`POLYGON_ISM_GEOMETRY_NOTE`). Deterministic: no randomness.

    For each polygon edge (wall) the source is mirrored across the edge's
    vertical supporting plane; when ``include_floor_ceiling`` is ``True`` the
    source is also mirrored across the floor plane (``y = 0``) and the ceiling
    plane (``y = ceiling_height_m``). Every enumerated image is returned with a
    shapely-based visibility ``valid`` flag (see module docstring); the caller
    decides whether to filter on it. Wall images appear in polygon-edge order,
    followed by floor then ceiling (when included).

    Parameters
    ----------
    floor_polygon:
        Simple (non-self-intersecting) floor polygon as a sequence of
        :class:`Point2` ``(x, z)`` vertices in the floor plane. At least 3
        vertices are required; a closing duplicate vertex is tolerated.
    ceiling_height_m:
        Extrusion height (metres), the ceiling plane ``y = ceiling_height_m``.
        Must be strictly positive.
    source:
        Source position as a :class:`Point3` ``(x, y, z)`` in metres.
    include_floor_ceiling:
        When ``True`` (default) also enumerate the floor and ceiling image
        sources. When ``False`` only the wall images are returned.
    tol_m:
        Absolute tolerance (metres) for the shapely on-segment / in-footprint
        visibility test. Defaults to ``1e-9``.

    Returns
    -------
    list[ImageSource]
        One :class:`ImageSource` per wall edge (in edge order), then the floor
        and ceiling images when ``include_floor_ceiling`` is ``True``. Each
        carries its mirrored ``position``, the producing surface, the wall edge
        index (``None`` for floor/ceiling), the ``reflection_point`` and the
        ``valid`` visibility flag.

    Raises
    ------
    ValueError
        If ``floor_polygon`` has fewer than 3 (de-duplicated) vertices, is
        self-intersecting (not a simple polygon), or contains a near-zero-length
        edge; if ``ceiling_height_m`` is not strictly positive; or if any
        coordinate is non-finite.
    """
    if not np.isfinite(ceiling_height_m) or ceiling_height_m <= 0.0:
        raise ValueError(
            "first_order_image_sources: ceiling_height_m must be a finite "
            f"value > 0; got {ceiling_height_m!r}"
        )
    for attr, value in (
        ("x", source.x),
        ("y", source.y),
        ("z", source.z),
    ):
        if not np.isfinite(value):
            raise ValueError(
                f"first_order_image_sources: source.{attr} must be finite; "
                f"got {value!r}"
            )

    # De-duplicate an explicit closing vertex (poly[-1] == poly[0]).
    verts: list[tuple[float, float]] = [(float(p.x), float(p.z)) for p in floor_polygon]
    if len(verts) >= 2 and verts[0] == verts[-1]:
        verts = verts[:-1]
    if len(verts) < 3:
        raise ValueError(
            "first_order_image_sources: floor_polygon must have at least 3 "
            f"distinct vertices; got {len(verts)}"
        )
    for vx, vz in verts:
        if not (np.isfinite(vx) and np.isfinite(vz)):
            raise ValueError(
                "first_order_image_sources: floor_polygon coordinates must be "
                f"finite; got ({vx!r}, {vz!r})"
            )

    polygon = Polygon(verts)
    # Fail loud on a self-intersecting / degenerate polygon: shapely
    # ``contains``/``distance`` give meaningless results on an invalid polygon,
    # which would silently corrupt the floor/ceiling visibility test.
    if not polygon.is_valid:
        raise ValueError(
            "first_order_image_sources: floor_polygon must be simple "
            "(non-self-intersecting); got an invalid polygon."
        )
    source_xz = (float(source.x), float(source.z))
    source_y = float(source.y)

    images: list[ImageSource] = []

    n = len(verts)
    for i in range(n):
        seg_a = verts[i]
        seg_b = verts[(i + 1) % n]
        if seg_a == seg_b:
            # Degenerate zero-length edge; skip (no wall plane).
            continue
        reflected_xz, foot_xz = _reflect_point_across_line_2d(
            source_xz, seg_a, seg_b
        )
        # Visibility: the reflection point (perpendicular foot) must lie on the
        # finite wall segment, not merely on its infinite supporting line.
        segment = LineString([seg_a, seg_b])
        on_segment = bool(
            segment.distance(ShapelyPoint(foot_xz[0], foot_xz[1])) <= tol_m
        )
        images.append(
            ImageSource(
                position=Point3(reflected_xz[0], source_y, reflected_xz[1]),
                surface_kind="wall",
                wall_index=i,
                reflection_point=Point3(foot_xz[0], 0.0, foot_xz[1]),
                valid=on_segment,
            )
        )

    if include_floor_ceiling:
        # Floor/ceiling reflection point is the source (x, z) at the plane
        # height; valid iff that point lies within the polygon footprint.
        source_point = ShapelyPoint(source_xz[0], source_xz[1])
        in_footprint = bool(
            polygon.contains(source_point)
            or polygon.boundary.distance(source_point) <= tol_m
        )
        # Floor plane y = 0: mirror y -> -y.
        images.append(
            ImageSource(
                position=Point3(source_xz[0], -source_y, source_xz[1]),
                surface_kind="floor",
                wall_index=None,
                reflection_point=Point3(source_xz[0], 0.0, source_xz[1]),
                valid=in_footprint,
            )
        )
        # Ceiling plane y = H: mirror y -> 2H - y.
        images.append(
            ImageSource(
                position=Point3(
                    source_xz[0],
                    2.0 * float(ceiling_height_m) - source_y,
                    source_xz[1],
                ),
                surface_kind="ceiling",
                wall_index=None,
                reflection_point=Point3(
                    source_xz[0], float(ceiling_height_m), source_xz[1]
                ),
                valid=in_footprint,
            )
        )

    return images


def first_order_path_lengths(
    images: Sequence[ImageSource],
    receiver: Point3,
    *,
    sound_speed_m_s: float | None = None,
) -> list[ImagePath]:
    """Compute receiver-relative first-order path lengths / TOAs (geometry only).

    GEOMETRY ONLY — emits no RT60 / absorption / energy number (see module
    docstring and :data:`POLYGON_ISM_GEOMETRY_NOTE`). Deterministic: preserves
    the input image order.

    By the image-source identity, the broken ``source -> surface -> receiver``
    path length of a first-order reflection equals the straight-line distance
    from the mirrored image position to the receiver. This function therefore
    returns, for each image, ``path_length_m = ‖image.position − receiver‖`` and
    (optionally) ``toa_s = path_length_m / sound_speed_m_s``.

    Parameters
    ----------
    images:
        The first-order :class:`ImageSource` sequence (e.g. the output of
        :func:`first_order_image_sources`).
    receiver:
        Receiver position as a :class:`Point3` ``(x, y, z)`` in metres.
    sound_speed_m_s:
        When given, must be finite and strictly positive; the per-image
        ``toa_s`` is then ``path_length_m / sound_speed_m_s`` (seconds). When
        ``None`` (default) every ``toa_s`` is ``None``.

    Returns
    -------
    list[ImagePath]
        One :class:`ImagePath` per input image, in the same order, each carrying
        the source image, the receiver, the broken-path length and the optional
        TOA.

    Raises
    ------
    ValueError
        If any ``receiver`` coordinate is non-finite, or if
        ``sound_speed_m_s`` is given but is non-finite or not strictly positive.
    """
    for attr, value in (
        ("x", receiver.x),
        ("y", receiver.y),
        ("z", receiver.z),
    ):
        if not np.isfinite(value):
            raise ValueError(
                f"first_order_path_lengths: receiver.{attr} must be finite; "
                f"got {value!r}"
            )
    if sound_speed_m_s is not None and (
        not np.isfinite(sound_speed_m_s) or sound_speed_m_s <= 0.0
    ):
        raise ValueError(
            "first_order_path_lengths: sound_speed_m_s must be a finite "
            f"value > 0 when given; got {sound_speed_m_s!r}"
        )

    receiver_xyz = np.array(
        [float(receiver.x), float(receiver.y), float(receiver.z)], dtype=float
    )

    paths: list[ImagePath] = []
    for image in images:
        image_xyz = np.array(
            [
                float(image.position.x),
                float(image.position.y),
                float(image.position.z),
            ],
            dtype=float,
        )
        path_length_m = float(np.linalg.norm(image_xyz - receiver_xyz))
        toa_s = (
            path_length_m / float(sound_speed_m_s)
            if sound_speed_m_s is not None
            else None
        )
        paths.append(
            ImagePath(
                image=image,
                receiver=receiver,
                path_length_m=path_length_m,
                toa_s=toa_s,
            )
        )

    return paths
