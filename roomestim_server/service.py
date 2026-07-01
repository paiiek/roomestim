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
    PlaceRequest,
    PlacementIn,
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
    "list_examples",
    "list_specs",
    "load_example",
    "place_request",
    "upload_room",
    "upload_roomplan",
    "upload_structure",
]

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


def evaluate_request(request: EvaluateRequest) -> dict[str, object]:
    """Resolve the request to core objects and return ``tradeoff_to_dict(...)``.

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

    return tradeoff_to_dict(report)


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

    return {
        "target_algorithm": result.target_algorithm,
        "regularity_hint": result.regularity_hint,
        "layout_name": result.layout_name,
        "speakers": [
            {
                "channel": s.channel,
                "position": {
                    "x": s.position.x,
                    "y": s.position.y,
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
    return {"room": room_geometry_to_dict(room, room_id)}


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
        out.append(room_geometry_to_dict(room, room_id))
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
