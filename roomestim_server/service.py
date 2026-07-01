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
from typing import Any

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
    UploadRoomRequest,
)

_LOG = logging.getLogger("roomestim_server.service")

__all__ = ["evaluate_request", "list_specs", "place_request", "upload_room"]


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

    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    try:
        tmp.write(request.room_yaml)
        tmp.close()
        try:
            room = read_room_yaml(tmp.name)
        except Exception as exc:
            # The ENTIRE operation is parsing client-supplied text, so EVERY
            # failure is client-attributable → generic 400 (a rare non-ValueError
            # slipping the schema — e.g. a shapely GEOSException on NaN coords —
            # thus maps to 400, not 500). Real cause logged server-side only.
            _LOG.warning("read_room_yaml rejected uploaded room.yaml: %s", exc)
            raise EvaluateError() from exc
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            _LOG.warning("failed to delete temp upload file %r", tmp.name)

    room_id = register_uploaded_room(room)
    return {"room": room_geometry_to_dict(room, room_id)}
