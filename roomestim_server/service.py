"""roomestim_server.service — the THIN adapter (validated request → core → dict).

D29 (web → core, single direction): ALL physics is delegated to
``roomestim.design.tradeoff.evaluate_layout`` / ``tradeoff_to_dict``; the built-in
specs come from ``roomestim.spec.speaker_spec.BUILTIN_SPEAKER_CATALOG``; the room
geometry comes from :mod:`roomestim_server.rooms`. This module ONLY normalises the
validated request into core objects, calls the engine, and serialises the result.
NO physics is re-derived here — the returned dict is byte-for-byte
``tradeoff_to_dict(evaluate_layout(...))``.

Honesty (ADR 0038 / OQ-45): a core ``ValueError`` (drive_w<=0, <2 speakers, bad
spec key, non-positive injected RT60, …) is logged server-side and re-raised as a
generic :class:`roomestim_server.errors.EvaluateError` (→ 400); the client never
sees the raw text. Mirrors ``roomestim_web/immersive_design.py::_on_evaluate``.
"""

from __future__ import annotations

import base64
import binascii
import dataclasses
import logging
import math
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from roomestim_server.errors import EvaluateError
from roomestim_server.rooms import (
    get_room,
    register_uploaded_room,
    room_geometry_to_dict,
)
from roomestim_server.schemas import (
    EvaluateRequest,
    LayoutExportRequest,
    MaterialsOverrideIn,
    PlaceRequest,
    PlacementIn,
    UploadMeshRequest,
    UploadRoomPlanRequest,
    UploadRoomRequest,
    UploadStructureRequest,
)

if TYPE_CHECKING:
    from roomestim.model import RoomModel

_LOG = logging.getLogger("roomestim_server.service")

_T = TypeVar("_T")

__all__ = [
    "evaluate_request",
    "export_layout",
    "list_examples",
    "list_materials",
    "list_specs",
    "load_example",
    "place_request",
    "upload_mesh",
    "upload_room",
    "upload_roomplan",
    "upload_structure",
]

#: Placement algorithms whose ``run_placement`` output is LISTENER-EAR-CENTRIC —
#: i.e. built around the listener at the origin ``(0, 0, 0)`` with an el=0 ring on
#: the ``y=0`` plane (``vbap``/``dome``: rings around the ear; ``ambisonics``: a
#: sphere centred on the ear). To land them in the canonical Frame A (floor at
#: ``y=0``, ear plane at ``listener_area.height_m``) the seeded speakers are lifted
#: vertically by ``listener_area.height_m`` in the client-facing :func:`place_request`
#: output (see the Part-2 note there). ``dbap`` (on wall/ceiling mount surfaces),
#: ``coverage`` (on the ``y=ceiling_height_m`` ceiling plane), and ``wfs`` (a linear
#: array at its own absolute mount ``height_m``) are ALREADY room-absolute (Frame A
#: after the room is recentred at registration) and must NOT be lifted — lifting
#: them would float ceiling/wall speakers above the room, re-introducing the bug.
_EAR_ORIGIN_ALGORITHMS = frozenset({"vbap", "dome", "ambisonics"})

#: Mesh filename suffixes the mesh-upload endpoint accepts (mirror of core
#: ``MeshAdapter._SUPPORTED_SUFFIXES``). An unsupported suffix is rejected at the
#: endpoint with a generic 400 BEFORE any decode/parse — we never write an unknown
#: file type to disk. ``.usdz`` additionally needs the ``[usd]`` extra (pxr); its
#: absence surfaces as a generic 400 from the adapter's ImportError, not here.
_MESH_SUFFIXES = frozenset({".obj", ".gltf", ".glb", ".ply", ".usdz"})

#: Bundled example capture files (shipped under ``roomestim_server/examples/``).
_EXAMPLES_DIR = Path(__file__).parent / "examples"

#: Static example manifest — id → {filename, format, name, description}. ``format``
#: selects the parse path: ``"roomplan"`` → single-room ``RoomPlanAdapter`` (returns
#: ``{"room": ...}``), ``"structure"`` → multi-room ``parse_structure`` (returns
#: ``{"rooms": [...]}``). The two ``capturedstructure_*`` files are REAL Apple
#: exports redistributed under the MIT License (see ``examples/ATTRIBUTION.md``).
#: Every id MUST map to a real shipped file (guarded by ``tests/server/test_examples``).
_EXAMPLES: dict[str, dict[str, str]] = {
    "lab_room_synthetic": {
        "filename": "lab_room_synthetic.json",
        "format": "roomplan",
        "name": "Lab room (synthetic RoomPlan sidecar)",
        "description": (
            "Synthetic single-room RoomPlan JSON sidecar (our own fixture) — "
            "a quick smoke room for the viewer."
        ),
    },
    "lab_room_with_column": {
        "filename": "lab_room_with_column.json",
        "format": "roomplan",
        "name": "Lab room + column (synthetic RoomPlan sidecar)",
        "description": (
            "Synthetic single-room RoomPlan JSON sidecar (our own fixture) with "
            "one free-standing column — a click-test room for the obstacle box "
            "render (route speakers around the pillar)."
        ),
    },
    "capturedstructure_single": {
        "filename": "capturedstructure_single.json",
        "format": "structure",
        "name": "RoomPlan capture — single room (real, MIT)",
        "description": (
            "Real Apple RoomPlan CapturedStructure export with one section "
            "(living room). MIT-attributed (theLodgeBots/open3dFloorplan)."
        ),
    },
    "capturedstructure_multiroom": {
        "filename": "capturedstructure_multiroom.json",
        "format": "structure",
        "name": "RoomPlan capture — multi-room (real, 4 rooms, MIT)",
        "description": (
            "Real Apple RoomPlan CapturedStructure export split into 4 rooms "
            "(2 bedrooms, bathroom, unidentified). MIT-attributed "
            "(theLodgeBots/open3dFloorplan)."
        ),
    },
}


def _is_finite_positive(value: Any) -> bool:
    """True iff *value* coerces to a finite float strictly greater than 0."""
    if value is None:
        return False
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f) and f > 0.0


def _plan_dist_point_to_segment(
    px: float, pz: float, ax: float, az: float, bx: float, bz: float
) -> float:
    """Perpendicular plan-view distance from ``(px,pz)`` to segment ``A→B`` (metres).

    Pure 2-D geometry (the floor plane; y is dropped): the projection parameter is
    clamped to ``[0,1]`` so a speaker beyond a wall's ends measures to the nearer
    endpoint, not the infinite line. A degenerate (zero-length) segment falls back
    to the point-to-endpoint distance.
    """
    dx = bx - ax
    dz = bz - az
    denom = dx * dx + dz * dz
    if denom <= 0.0:
        return math.hypot(px - ax, pz - az)
    t = ((px - ax) * dx + (pz - az) * dz) / denom
    t = max(0.0, min(1.0, t))
    cx = ax + t * dx
    cz = az + t * dz
    return math.hypot(px - cx, pz - cz)


def _wall_plan_segment(surf: Any) -> tuple[float, float, float, float] | None:
    """Collapse a wall :class:`Surface` to its plan-view segment ``(ax,az,bx,bz)``.

    A wall polygon is a vertical rectangle; projected to the floor plane its four
    corners collapse onto a single line segment. The two most-distant projected
    ``(x,z)`` vertices are that segment's endpoints (robust to vertex order /
    duplicated corners). Returns ``None`` if the wall has no extent in plan view.
    """
    pts = [(p.x, p.z) for p in surf.polygon]
    best: tuple[float, float, float, float] | None = None
    best_d = -1.0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = (pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2
            if d > best_d:
                best_d = d
                best = (pts[i][0], pts[i][1], pts[j][0], pts[j][1])
    return best if best_d > 0.0 else None


def _build_install_block(
    room: "RoomModel",
    placement: Any,
    spl_by_channel: dict[int, float] | None = None,
) -> dict[str, object]:
    """Per-speaker installer guide (geometry + optional per-speaker SPL — D29).

    For each placed speaker emit its verbatim world ``position`` + mounting
    ``height_m`` (= ``position.y``), the listener-relative ``az_deg``/``el_deg``/
    ``dist_m`` via the SINGLE sign-flip authority
    :func:`roomestim.coords.cartesian_to_pipeline` (fed the vector from the listener
    ear point ``(centroid.x, listener_area.height_m, centroid.z)`` to the speaker —
    exactly what the engine / layout.yaml use, so no client/server drift), and a
    mounting hint an installer can lay out with a tape measure:

    * ``nearest_wall_index`` — index into the room's WALL surfaces (same order as
      ``room_geometry_to_dict``'s ``walls`` list, so the viewer can cross-reference),
      with ``wall_offset_m`` = perpendicular plan-view distance to that wall segment;
    * ``nearest_corner`` — index into ``floor_polygon``, with ``corner_dist_m`` =
      plan-view distance to that floor vertex.

    When ``spl_by_channel`` is supplied (P6.D), each speaker also gets
    ``spl_at_listener_db`` = that channel's INDIVIDUAL direct-field SPL at the
    listener ear point (from core
    :func:`roomestim.spec.speaker_spec.per_speaker_direct_spl_at_listener` — direct
    field only, NOT a measurement; see ``SPL_DIRECT_FIELD_NOTE``). A missing channel
    (or ``spl_by_channel=None``) leaves the field ``None``.

    All angle/distance numbers are computed here (server-side) so the browser only
    renders them. ``az_deg``/``el_deg`` are the pipeline (az, el) in DEGREES.
    """
    from roomestim.coords import cartesian_to_pipeline  # noqa: PLC0415

    listener = room.listener_area
    ear_x = listener.centroid.x
    ear_y = listener.height_m
    ear_z = listener.centroid.z

    wall_segments = [
        seg
        for surf in room.surfaces
        if surf.kind == "wall"
        for seg in (_wall_plan_segment(surf),)
    ]
    corners = [(p.x, p.z) for p in room.floor_polygon]

    speakers_out: list[dict[str, object]] = []
    for s in placement.speakers:
        px, py, pz = s.position.x, s.position.y, s.position.z
        az, el, dist = cartesian_to_pipeline(px - ear_x, py - ear_y, pz - ear_z)

        nearest_wall_index: int | None = None
        wall_offset_m: float | None = None
        for wi, seg in enumerate(wall_segments):
            if seg is None:
                continue
            off = _plan_dist_point_to_segment(px, pz, seg[0], seg[1], seg[2], seg[3])
            if wall_offset_m is None or off < wall_offset_m:
                wall_offset_m = off
                nearest_wall_index = wi

        nearest_corner: int | None = None
        corner_dist_m: float | None = None
        for ci, (cx, cz) in enumerate(corners):
            cd = math.hypot(px - cx, pz - cz)
            if corner_dist_m is None or cd < corner_dist_m:
                corner_dist_m = cd
                nearest_corner = ci

        speakers_out.append(
            {
                "channel": s.channel,
                "position": {"x": px, "y": py, "z": pz},
                "height_m": py,
                "az_deg": math.degrees(az),
                "el_deg": math.degrees(el),
                "dist_m": dist,
                "nearest_wall_index": nearest_wall_index,
                "wall_offset_m": wall_offset_m,
                "nearest_corner": nearest_corner,
                "corner_dist_m": corner_dist_m,
                "spl_at_listener_db": (
                    None
                    if spl_by_channel is None
                    else spl_by_channel.get(s.channel)
                ),
            }
        )

    return {"speakers": speakers_out}


def _build_placement(placement: PlacementIn) -> Any:
    """Build a core ``PlacementResult`` from the validated placement block."""
    from roomestim.model import PlacedSpeaker, Point3, PlacementResult  # noqa: PLC0415

    speakers = [
        PlacedSpeaker(
            channel=s.channel,
            position=Point3(s.position.x, s.position.y, s.position.z),
            aim_direction=(
                None
                if s.aim_direction is None
                else Point3(s.aim_direction.x, s.aim_direction.y, s.aim_direction.z)
            ),
        )
        for s in placement.speakers
    ]
    return PlacementResult(
        target_algorithm=placement.target_algorithm,
        regularity_hint=placement.regularity_hint,
        speakers=speakers,
        layout_name=placement.layout_name,
    )


#: Override-field name → the ``Surface.kind`` it targets (P5.9). ``walls`` (plural,
#: matches the UI label) maps to the singular ``"wall"`` surface kind.
_MATERIAL_OVERRIDE_KINDS: dict[str, str] = {
    "floor": "floor",
    "walls": "wall",
    "ceiling": "ceiling",
}


def _apply_material_overrides(
    room: "RoomModel", materials: MaterialsOverrideIn
) -> None:
    """Set floor/wall/ceiling surface materials IN PLACE from the curated rule-base.

    For each provided override field the label NAME is resolved to a
    :class:`roomestim.model.MaterialLabel` (unknown name → generic 400, logged, no
    leak) and EVERY surface of the matching kind has its ``material`` /
    ``absorption_500hz`` / ``absorption_bands`` set from the core tables so the
    downstream ``predict_rt60_default`` (keyed by ``surf.material``) reflects the
    choice. ``room`` MUST be a caller-owned copy (``get_room`` guarantees this —
    fresh build for built-ins, deepcopy for uploaded); ``Surface`` is frozen, so the
    surfaces list is rebuilt element-wise via :func:`dataclasses.replace`. A
    null/absent field is a no-op → an all-null override leaves the room byte-equal.
    """
    from roomestim.model import (  # noqa: PLC0415
        MaterialAbsorption,
        MaterialAbsorptionBands,
        MaterialLabel,
    )

    resolved: dict[str, MaterialLabel] = {}
    for field, target_kind in _MATERIAL_OVERRIDE_KINDS.items():
        name = getattr(materials, field)
        if name is None:
            continue
        try:
            resolved[target_kind] = MaterialLabel[name]
        except KeyError as exc:
            _LOG.warning("evaluate: unknown material label %r", name)
            raise EvaluateError() from exc

    if not resolved:
        return  # all fields null → no change (byte-equal)

    for i, surf in enumerate(room.surfaces):
        label = resolved.get(surf.kind)
        if label is None:
            continue
        room.surfaces[i] = dataclasses.replace(
            surf,
            material=label,
            absorption_500hz=MaterialAbsorption[label],
            absorption_bands=MaterialAbsorptionBands[label],
        )


def evaluate_request(request: EvaluateRequest) -> dict[str, object]:
    """Resolve the request to core objects and return ``{report, install}``.

    ``report`` is the VERBATIM ``tradeoff_to_dict(evaluate_layout(...))`` (byte-for-
    byte the engine output — no physics re-derived here). ``install`` is an ADDITIVE
    server-side per-speaker installer guide (:func:`_build_install_block`, geometry
    only, D29) built from the SAME resolved room + placement so the on-screen
    positions/angles match what the viewer renders and what layout.yaml exports; it
    NEVER folds into ``report``. Building it is defensive: any failure degrades to
    ``install: None`` (logged, no raw leak — ADR 0038) so a valid evaluate always
    returns.

    Raises :class:`EvaluateError` (→ 400, generic) for any client-attributable
    failure: unknown ``room_id``, unknown spec ``model_key``, or a core
    ``ValueError`` (drive_w<=0, <2 speakers, …). The real cause is logged
    server-side; the raised error carries only a generic message.
    """
    from roomestim.design.tradeoff import (  # noqa: PLC0415
        evaluate_layout,
        tradeoff_to_dict,
    )
    from roomestim.spec.speaker_spec import (  # noqa: PLC0415
        BUILTIN_SPEAKER_CATALOG,
    )

    # Resolve the room (geometry only; unknown id → generic 400).
    try:
        room = get_room(request.room_id)
    except KeyError as exc:
        _LOG.warning("evaluate: unknown room_id %r", request.room_id)
        raise EvaluateError() from exc

    # P5.9 — optional per-kind material override (curated rule-base, label-only).
    # Applied to the room copy get_room returns (a fresh build for built-ins, a
    # deepcopy for uploaded rooms — never shared state) BEFORE evaluate, so the
    # predicted RT60 reflects the new materials. Absent → room is untouched (the
    # evaluate path is byte-identical to today).
    if request.materials is not None:
        _apply_material_overrides(room, request.materials)

    # Resolve the built-in spec (unknown key → generic 400).
    spec_in = request.spec
    if spec_in.model_key not in BUILTIN_SPEAKER_CATALOG:
        _LOG.warning("evaluate: unknown spec model_key %r", spec_in.model_key)
        raise EvaluateError()
    spec = BUILTIN_SPEAKER_CATALOG[spec_in.model_key]
    if _is_finite_positive(spec_in.price):
        spec = dataclasses.replace(spec, price=float(spec_in.price))  # type: ignore[arg-type]

    placement = _build_placement(request.placement)

    params = request.params
    # blank / None / <=0 → use the model-predicted RT60 (rt60.source="predicted"),
    # mirroring the Gradio panel (core itself rejects a non-positive injection).
    measured: float | None = None
    if _is_finite_positive(params.measured_rt60_s):
        measured = float(params.measured_rt60_s)  # type: ignore[arg-type]

    optional: dict[str, float] = {}
    if params.grid_resolution_m is not None:
        optional["grid_resolution_m"] = float(params.grid_resolution_m)
    if params.min_separation_deg is not None:
        optional["min_separation_deg"] = float(params.min_separation_deg)

    try:
        report = evaluate_layout(
            room,
            placement,
            spec,
            listener_area=room.listener_area,
            drive_w=float(params.drive_w),
            target_spl_db=float(params.target_spl_db),
            measured_rt60=measured,
            **optional,
        )
    except ValueError as exc:
        # ADR 0038 / OQ-45: real text logged server-side; client gets a generic
        # message (no raw exception / path in the web-facing response).
        _LOG.warning("evaluate_layout rejected inputs: %s", exc)
        raise EvaluateError() from exc

    report_dict = tradeoff_to_dict(report)
    # ADDITIVE per-speaker installer guide (P6.C geometry + P6.D per-speaker SPL,
    # D29). Built from the SAME room + placement + spec + drive so it matches the
    # render/export/report. The per-speaker direct-field SPL is delegated to core
    # ``per_speaker_direct_spl_at_listener`` (NO acoustics re-derived here); it is
    # computed under its own guard so a failure degrades ONLY spl_at_listener_db to
    # null (channel-keyed) — never the geometry. The whole install build is then
    # guarded again so any failure degrades to install=None (never crashes a valid
    # evaluate, never leaks a raw exception — ADR 0038).
    spl_by_channel: dict[int, float] | None
    try:
        from roomestim.spec.speaker_spec import (  # noqa: PLC0415
            per_speaker_direct_spl_at_listener,
        )

        spl_by_channel = {
            ch: spl
            for ch, spl in per_speaker_direct_spl_at_listener(
                spec,
                drive_w=float(params.drive_w),
                speakers=placement.speakers,
                listener_area=room.listener_area,
            )
        }
    except Exception as exc:  # pragma: no cover - defensive
        _LOG.warning("evaluate: per-speaker SPL compute failed: %s", exc)
        spl_by_channel = None

    install: dict[str, object] | None
    try:
        install = _build_install_block(room, placement, spl_by_channel)
    except Exception as exc:  # pragma: no cover - defensive (geometry is total)
        _LOG.warning("evaluate: install block build failed: %s", exc)
        install = None

    return {"report": report_dict, "install": install}


def place_request(request: PlaceRequest) -> dict[str, object]:
    """Seed a layout via core ``run_placement`` and serialise its speakers.

    D29: ALL placement physics is delegated to
    ``roomestim.place.dispatch.run_placement``; this function ONLY resolves the
    room, forwards the five request fields, and serialises the returned
    ``PlacementResult`` into a plain dict the frontend can drop straight into an
    ``/api/evaluate`` placement block. NO placement math is done here.

    Raises :class:`EvaluateError` (→ 400, generic) for any client-attributable
    failure: unknown ``room_id`` or a core ``ValueError`` (unknown algorithm,
    too-few speakers, …). The real cause is logged server-side.
    """
    from roomestim.place.dispatch import run_placement  # noqa: PLC0415

    try:
        room = get_room(request.room_id)
    except KeyError as exc:
        _LOG.warning("place: unknown room_id %r", request.room_id)
        raise EvaluateError() from exc

    try:
        result = run_placement(
            room,
            request.algorithm,
            request.n_speakers,
            request.layout_radius_m,
            request.el_deg,
        )
    except ValueError as exc:
        _LOG.warning("run_placement rejected inputs: %s", exc)
        raise EvaluateError() from exc

    # Part 2 (frame consistency): listener-ear-centric algorithms (vbap/dome/
    # ambisonics) place around the ear at the origin, so an el=0 ring sits on the
    # ``y=0`` plane. The canonical Frame A (matching the recentred room, the SEED,
    # and ``evaluate_layout``'s ear-plane sampling at ``listener_area.height_m``)
    # puts the ear at ``y=height_m``, so we lift these speakers by ``height_m``
    # here — a CLIENT-FACING VIEW ADJUSTMENT only. This keeps the round-trip
    # correct WITHOUT touching evaluate: the client sends these lifted speakers
    # back to ``/api/evaluate``, which samples the listener at ``height_m`` and
    # treats speaker ``y`` as absolute → both share Frame A (dy=0 for the ring →
    # distances ≈ layout_radius, not the mismatched sqrt(radius²+height²)). Room-
    # absolute algorithms (dbap/coverage/wfs) already emit Frame A after the room
    # is recentred at registration and are NOT lifted (see _EAR_ORIGIN_ALGORITHMS).
    lift = (
        room.listener_area.height_m
        if request.algorithm.lower() in _EAR_ORIGIN_ALGORITHMS
        else 0.0
    )

    return {
        "target_algorithm": result.target_algorithm,
        "regularity_hint": result.regularity_hint,
        "layout_name": result.layout_name,
        "speakers": [
            {
                "channel": s.channel,
                "position": {
                    "x": s.position.x,
                    "y": s.position.y + lift,
                    "z": s.position.z,
                },
                "aim_direction": (
                    None
                    if s.aim_direction is None
                    else {
                        "x": s.aim_direction.x,
                        "y": s.aim_direction.y,
                        "z": s.aim_direction.z,
                    }
                ),
            }
            for s in result.speakers
        ],
    }


def export_layout(request: LayoutExportRequest) -> dict[str, object]:
    """Emit the engine-contract ``layout.yaml`` for the request placement.

    D29: the layout.yaml is produced ENTIRELY by core
    ``roomestim.export.layout_yaml.write_layout_yaml`` — the server only builds the
    ``PlacementResult`` from the validated placement block (via the shared
    :func:`_build_placement` helper, identical to :func:`evaluate_request`), lets the
    core writer serialise it to a temp OUTPUT file, and reads the text back to return
    ``{"filename": "layout.yaml", "yaml": <text>}``. NO geometry/placement math here.

    Validation is env-gated: ``validate = bool(SPATIAL_ENGINE_REPO_DIR)`` — full
    engine schema validation runs ONLY when the deploy has the spatial_engine repo
    (there is no machine-specific default path); otherwise the writer skips it and
    prepends its honest ``# WARNING: schema validation skipped`` header (kept
    verbatim). ``room_id`` is accepted for symmetry/forward-compat and validated to
    resolve (a nonexistent room → generic 400), though layout.yaml is placement-only.

    Honesty (ADR 0038 / OQ-45): a layout that violates the engine contract (R10
    too-few-speakers, WFS without an alias frequency) makes the core writer raise
    ``ValueError``; that — and any other exception — is caught by
    :func:`_export_to_temp_file`, logged server-side, and re-raised as a generic
    :class:`EvaluateError` (→ 400). The temp file is ALWAYS deleted.
    """
    from roomestim.export.layout_yaml import write_layout_yaml  # noqa: PLC0415

    # Reject a nonexistent room up front (symmetry with evaluate/place); the
    # layout.yaml itself is derived purely from the placement block.
    try:
        get_room(request.room_id)
    except KeyError as exc:
        _LOG.warning("export_layout: unknown room_id %r", request.room_id)
        raise EvaluateError() from exc

    result = _build_placement(request.placement)
    validate = bool(os.environ.get("SPATIAL_ENGINE_REPO_DIR"))

    def _write(path: str) -> None:
        write_layout_yaml(result, path, validate=validate)

    text = _export_to_temp_file(".yaml", _write)
    return {"filename": "layout.yaml", "yaml": text}


def list_specs() -> list[dict[str, object]]:
    """List the built-in speaker specs (catalog metadata only — NO physics).

    Returns ``{"model_key", "price", "provenance"}`` per entry in
    ``roomestim.spec.speaker_spec.BUILTIN_SPEAKER_CATALOG`` so the frontend can
    populate a spec dropdown. NO SPL/directivity math is done here; the catalog
    is imported lazily so ``import roomestim_server`` stays cheap.
    """
    from roomestim.spec.speaker_spec import (  # noqa: PLC0415
        BUILTIN_SPEAKER_CATALOG,
    )

    return [
        {"model_key": key, "price": spec.price, "provenance": spec.provenance}
        for key, spec in BUILTIN_SPEAKER_CATALOG.items()
    ]


def list_materials() -> list[dict[str, object]]:
    """List the curated material rule-base for the UI dropdowns (P5.9 — NO physics).

    Returns ``{"label", "name", "absorption_500hz"}`` per
    :class:`roomestim.model.MaterialLabel` — ``label`` is the enum NAME (what the
    override field expects back), ``name`` is a human-readable label, and
    ``absorption_500hz`` is the REAL 500 Hz coefficient from
    :data:`roomestim.model.MaterialAbsorption` (Vorländer 2020) so the UI can show
    each material's honest α. NO RT60/absorption math is done here; the tables are
    imported lazily so ``import roomestim_server`` stays cheap.
    """
    from roomestim.model import (  # noqa: PLC0415
        MaterialAbsorption,
        MaterialLabel,
    )

    return [
        {
            "label": label.name,
            "name": label.name.replace("_", " ").title(),
            "absorption_500hz": MaterialAbsorption[label],
        }
        for label in MaterialLabel
    ]


def _with_temp_file(text: str, suffix: str, fn: Callable[[str], _T]) -> _T:
    """Write ``text`` to a temp file, run ``fn(path)``, ALWAYS unlink, and map ANY
    parse exception to a generic :class:`EvaluateError`.

    The single point that owns the temp-file write + ``finally`` unlink + the
    generic-``EvaluateError``-on-any-exception discipline, shared by the single-room
    (:func:`_parse_and_register`) and multi-room (:func:`_parse_and_register_many`)
    upload paths so the two never drift.

    Honesty (ADR 0038 / OQ-45): the ENTIRE operation is parsing client-supplied
    (or bundled-example) text, so EVERY failure is treated as client-attributable.
    Any exception from ``fn`` (``ValueError``/``NotImplementedError``/``KeyError``/…
    — a malformed body, a schema violation, a shapely GEOSException on NaN coords)
    is logged server-side and re-raised as a generic :class:`EvaluateError` (→ 400);
    the client never sees the raw text. The temp file is ALWAYS deleted.
    """
    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    try:
        tmp.write(text)
        tmp.close()
        try:
            return fn(tmp.name)
        except Exception as exc:
            _LOG.warning("upload parse (%s) rejected input: %s", suffix, exc)
            raise EvaluateError() from exc
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            _LOG.warning("failed to delete temp upload file %r", tmp.name)


def _with_temp_bytes_file(
    data: bytes, suffix: str, fn: Callable[[str], _T]
) -> _T:
    """Write raw ``data`` BYTES to a temp file, run ``fn(path)``, ALWAYS unlink, and
    map ANY parse exception to a generic :class:`EvaluateError`.

    The binary counterpart of :func:`_with_temp_file` (which writes decoded text) —
    used by :func:`upload_mesh`, whose payload is a base64-decoded BINARY mesh file
    (``.obj``/``.gltf``/``.glb``/``.ply``/``.usdz``). The temp-file write +
    ``finally`` unlink + generic-``EvaluateError``-on-any-exception discipline is
    IDENTICAL to the text path so the two never drift.

    Honesty (ADR 0038 / OQ-45): the ENTIRE operation is parsing a client-supplied
    mesh, so EVERY failure is client-attributable. Any exception from ``fn``
    (``ValueError`` on an unsupported/oversize/degenerate mesh, ``ImportError`` on a
    ``.usdz`` body when the ``[usd]`` extra is missing, a shapely GEOSException, …)
    is logged server-side and re-raised as a generic :class:`EvaluateError` (→ 400);
    the client never sees the raw text. The temp file is ALWAYS deleted.
    """
    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
        mode="wb", suffix=suffix, delete=False
    )
    try:
        tmp.write(data)
        tmp.close()
        try:
            return fn(tmp.name)
        except Exception as exc:
            _LOG.warning("mesh upload parse (%s) rejected input: %s", suffix, exc)
            raise EvaluateError() from exc
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            _LOG.warning("failed to delete temp upload file %r", tmp.name)


def _export_to_temp_file(suffix: str, write_fn: Callable[[str], None]) -> str:
    """Run ``write_fn(path)`` to PRODUCE a temp OUTPUT file, read its text back,
    ALWAYS unlink, and map ANY exception to a generic :class:`EvaluateError`.

    The OUTPUT-oriented counterpart of :func:`_with_temp_file` (which writes an
    INPUT temp file for a parser to read): here the core writer OWNS the write, and
    the server reads the produced text back to return it in the JSON body. Used by
    :func:`export_layout`. Same ``finally``-unlink + generic-error discipline.

    Honesty (ADR 0038 / OQ-45): a ``write_fn`` failure is client-attributable — a
    layout that violates the engine contract (R10 too-few-speakers, WFS without an
    alias frequency) raises ``ValueError`` — so ANY exception (that, a schema
    ``FileNotFoundError`` when validation is enabled but the engine repo is
    mis-set, a read error, …) is logged server-side and re-raised as a generic
    :class:`EvaluateError` (→ 400). The temp file is ALWAYS deleted.
    """
    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    tmp.close()
    try:
        try:
            write_fn(tmp.name)
            return Path(tmp.name).read_text(encoding="utf-8")
        except Exception as exc:
            _LOG.warning("export (%s) failed: %s", suffix, exc)
            raise EvaluateError() from exc
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            _LOG.warning("failed to delete temp export file %r", tmp.name)


def _parse_and_register(
    text: str,
    suffix: str,
    parse_fn: Callable[[str], "RoomModel"],
) -> dict[str, object]:
    """Parse ``text`` into ONE room, register it, and return ``{"room": geom}``.

    Shared by :func:`upload_room` (room.yaml) and :func:`upload_roomplan`
    (RoomPlan JSON sidecar). D29: ALL geometry is derived by ``parse_fn`` (a
    torch-free core reader/adapter) — the server adds no geometry math. The parsed
    room is stored in the bounded uploaded-room registry and its geometry (with the
    assigned id embedded) is returned for rendering. The temp-file / error-envelope
    discipline lives in :func:`_with_temp_file`.
    """
    room = _with_temp_file(text, suffix, parse_fn)
    room_id = register_uploaded_room(room)
    # Serialise the STORED room (register recentres it to the canonical Frame A),
    # NOT the pre-recentre local, so the render matches what place/evaluate see.
    return {"room": room_geometry_to_dict(get_room(room_id), room_id)}


def _parse_and_register_many(
    text: str,
    suffix: str,
    parse_fn: Callable[[str], "list[RoomModel]"],
) -> dict[str, object]:
    """Parse ``text`` into N rooms, register EACH, and return ``{"rooms": [geom,…]}``.

    The multi-room counterpart of :func:`_parse_and_register`, used by
    :func:`upload_structure` (an Apple ``CapturedStructure`` export splits into one
    :class:`RoomModel` per section). Section order is preserved. Each room gets its
    own ``"uploaded:<n>"`` id so the frontend can render a picker and drive
    ``/api/evaluate`` per room. D29: ALL geometry is derived by ``parse_fn``; the
    temp-file / error-envelope discipline lives in :func:`_with_temp_file`.
    """
    rooms = _with_temp_file(text, suffix, parse_fn)
    out: list[dict[str, object]] = []
    for room in rooms:
        room_id = register_uploaded_room(room)
        # Serialise the STORED (recentred, Frame A) room so render == place/eval.
        out.append(room_geometry_to_dict(get_room(room_id), room_id))
    return {"rooms": out}


def upload_room(request: UploadRoomRequest) -> dict[str, object]:
    """Parse an uploaded room.yaml (text) via core ``read_room_yaml`` and register it.

    D29: the room.yaml text is written to a temp file and parsed ENTIRELY by
    ``roomestim.io.room_yaml_reader.read_room_yaml`` — the server adds no geometry
    math. The parsed room is stored in the bounded uploaded-room registry and its
    geometry (with the assigned id embedded) is returned for rendering.

    Honesty (ADR 0038 / OQ-45): ALL parse/validation failures are
    client-attributable (a bad uploaded file), so any error from the reader
    (``read_room_yaml`` already wraps YAML + schema errors as ``ValueError``, but
    a stray ``KeyError``/``TypeError`` on hand-mangled input is caught too) is
    logged server-side and re-raised as a generic :class:`EvaluateError` (→ 400).
    The temp file is ALWAYS deleted in a ``finally``.
    """
    from roomestim.io.room_yaml_reader import read_room_yaml  # noqa: PLC0415

    return _parse_and_register(request.room_yaml, ".yaml", read_room_yaml)


def upload_roomplan(request: UploadRoomPlanRequest) -> dict[str, object]:
    """Parse an uploaded Apple RoomPlan JSON sidecar via core ``RoomPlanAdapter``.

    D29: the RoomPlan JSON text is written to a temp file and parsed ENTIRELY by
    ``roomestim.adapters.roomplan.RoomPlanAdapter().parse`` (torch-free, json+numpy
    only) — the server adds no geometry math. RoomPlan is metric-native, so the
    adapter ignores ``scale_anchor`` (the server never supplies one). The parsed
    room is stored in the bounded uploaded-room registry and its geometry (id
    embedded) is returned for rendering, exactly like :func:`upload_room`.

    Honesty (ADR 0038 / OQ-45): ALL parse/validation failures are
    client-attributable. ``RoomPlanAdapter().parse`` raises ``ValueError`` on a
    malformed/unsupported sidecar and ``NotImplementedError`` on a ``.usdz`` body;
    both — and any other exception — are caught by :func:`_parse_and_register`,
    logged server-side, and re-raised as a generic :class:`EvaluateError` (→ 400).
    """
    from roomestim.adapters.roomplan import RoomPlanAdapter  # noqa: PLC0415

    return _parse_and_register(
        request.roomplan_json, ".json", RoomPlanAdapter().parse
    )


def upload_structure(request: UploadStructureRequest) -> dict[str, object]:
    """Parse an uploaded Apple ``CapturedStructure`` (multi-room) JSON export.

    D29: the CapturedStructure text is written to a temp file and split ENTIRELY by
    ``roomestim.adapters.roomplan_structure.parse_structure`` (torch-free —
    json+numpy+shapely) into one :class:`RoomModel` per section — the server adds no
    geometry math. Each room is stored in the bounded uploaded-room registry; the
    list of room geometries (each with its assigned ``"uploaded:<n>"`` id) is
    returned in section order for the frontend room-picker.

    Honesty (ADR 0038 / OQ-45): ALL parse/validation failures are
    client-attributable. ``parse_structure`` raises ``ValueError`` on a
    malformed/sectionless/wrong-extension export; that — and any other exception —
    is caught by :func:`_with_temp_file`, logged server-side, and re-raised as a
    generic :class:`EvaluateError` (→ 400).
    """
    from roomestim.adapters.roomplan_structure import (  # noqa: PLC0415
        parse_structure,
    )

    return _parse_and_register_many(
        request.structure_json, ".json", parse_structure
    )


def upload_mesh(request: UploadMeshRequest) -> dict[str, object]:
    """Parse an uploaded BINARY mesh file (base64) via core ``MeshAdapter`` and register it.

    D29: the base64 payload is decoded to bytes, written to a temp file whose suffix
    is taken from ``request.filename``, and parsed ENTIRELY by
    ``roomestim.adapters.mesh.MeshAdapter().parse`` (trimesh for
    ``.obj``/``.gltf``/``.glb``/``.ply``; the ``[usd]`` extra for ``.usdz``) — the
    server adds no geometry math. Mesh files are metric-native, so the adapter
    ignores ``scale_anchor`` (the server never supplies one). The parsed room is
    stored in the bounded uploaded-room registry and its geometry (id embedded) is
    returned for rendering, exactly like :func:`upload_room`.

    Honesty (ADR 0038 / OQ-45): ALL failures are client-attributable. An
    unsupported filename suffix is rejected BEFORE any decode/parse (we never write
    an unknown file type to disk); a malformed base64 body (``binascii.Error`` /
    ``ValueError``) is caught here; and any adapter failure — ``ValueError`` on an
    unsupported/oversize/degenerate mesh, ``ImportError`` on a ``.usdz`` body when
    the ``[usd]`` extra is missing, a shapely error — is caught by
    :func:`_with_temp_bytes_file`. Every case is logged server-side and re-raised as
    a generic :class:`EvaluateError` (→ 400); the temp file is ALWAYS deleted.
    """
    from roomestim.adapters.mesh import MeshAdapter  # noqa: PLC0415

    suffix = Path(request.filename).suffix.lower()
    if suffix not in _MESH_SUFFIXES:
        _LOG.warning("upload_mesh: unsupported filename suffix %r", suffix)
        raise EvaluateError()

    try:
        data = base64.b64decode(request.content_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        _LOG.warning("upload_mesh: base64 decode failed: %s", exc)
        raise EvaluateError() from exc

    room = _with_temp_bytes_file(data, suffix, MeshAdapter().parse)
    room_id = register_uploaded_room(room)
    # Serialise the STORED (recentred, Frame A) room so render == place/eval.
    return {"room": room_geometry_to_dict(get_room(room_id), room_id)}


def list_examples() -> list[dict[str, object]]:
    """List the bundled example captures (metadata only — NO parsing/physics).

    Returns ``[{"id", "name", "format", "description"}, …]`` from the static
    :data:`_EXAMPLES` manifest so the frontend can populate a "load example"
    dropdown. ``format`` is ``"roomplan"`` (single-room sidecar) or ``"structure"``
    (multi-room CapturedStructure); the files are read only when actually loaded.
    """
    return [
        {
            "id": example_id,
            "name": entry["name"],
            "format": entry["format"],
            "description": entry["description"],
        }
        for example_id, entry in _EXAMPLES.items()
    ]


def load_example(example_id: str) -> dict[str, object]:
    """Load a bundled example by id and parse it via the SAME path as an upload.

    Dispatches by the example's declared ``format``: ``"roomplan"`` →
    :func:`_parse_and_register` (returns ``{"room": …}``, exactly like
    :func:`upload_roomplan`); ``"structure"`` → :func:`_parse_and_register_many`
    (returns ``{"rooms": […]}``, exactly like :func:`upload_structure`). The parsed
    room(s) land in the same bounded registry, so the returned id(s) are usable in
    ``/api/evaluate`` / ``/api/place`` just like an uploaded room.

    An unknown ``example_id`` raises ``KeyError`` (the app maps it to a generic
    404). A shipped-but-broken example (unreadable file / parse failure) is a
    SERVER bug, but is still logged server-side and surfaced as a generic
    :class:`EvaluateError` (→ 400) — internals are never leaked to the client
    (ADR 0038). ``tests/server/test_examples`` guards that every shipped example
    actually parses.
    """
    entry = _EXAMPLES[example_id]  # KeyError → 404 (mapped by the app)
    path = _EXAMPLES_DIR / entry["filename"]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        _LOG.error("bundled example %r is unreadable: %s", example_id, exc)
        raise EvaluateError() from exc

    if entry["format"] == "structure":
        from roomestim.adapters.roomplan_structure import (  # noqa: PLC0415
            parse_structure,
        )

        return _parse_and_register_many(text, ".json", parse_structure)

    from roomestim.adapters.roomplan import RoomPlanAdapter  # noqa: PLC0415

    return _parse_and_register(text, ".json", RoomPlanAdapter().parse)
