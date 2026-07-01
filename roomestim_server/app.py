"""roomestim_server.app — FastAPI ``create_app()`` factory + JSON endpoints.

Stateless REST MVP over the frozen P3 trade-off engine (immersive-layout P5.1).
Endpoints: ``POST /api/evaluate`` (the engine contract in one call),
``GET /api/rooms`` + ``GET /api/rooms/{id}`` (geometry only), ``GET /healthz``.

Honesty boundary (ADR 0038 / OQ-45): a client-attributable failure
(:class:`EvaluateError`) renders ``{"ok": false, "error": {...}}`` with a generic
message + stable code; ANY uncaught exception is caught by a global handler that
logs the real error server-side and returns a generic ``500`` — a stack trace,
internal path, or raw ``ValueError`` text is NEVER leaked to the client.

Importing this module requires the ``[server]`` extra (fastapi); it is reached
ONLY lazily via :func:`roomestim_server.create_app`, so ``import roomestim`` and
``import roomestim_server`` stay fastapi-free.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from roomestim_server.errors import (
    GENERIC_INTERNAL_MESSAGE,
    GENERIC_ROOM_NOT_FOUND_MESSAGE,
    GENERIC_VALIDATION_MESSAGE,
    EvaluateError,
)
from roomestim_server.rooms import (
    get_room,
    list_rooms,
    room_geometry_to_dict,
)
from roomestim_server.schemas import EvaluateRequest
from roomestim_server.service import evaluate_request

_LOG = logging.getLogger("roomestim_server.app")

__all__ = ["create_app"]


def _build_router() -> APIRouter:
    """Construct the API router (endpoints close over the core service)."""
    router = APIRouter()

    @router.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/api/rooms")
    def get_rooms() -> dict[str, object]:
        return {"rooms": list_rooms()}

    # ``:path`` captures the id WHOLE so ids containing a colon/slash
    # (e.g. ``builtin:shoebox``, a future ``builtin:foo/bar``) are matched
    # intact; it does NOT shadow the exact ``/api/rooms`` list route above.
    @router.get("/api/rooms/{room_id:path}")
    def get_room_geometry(room_id: str) -> JSONResponse:
        try:
            room = get_room(room_id)
        except KeyError:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": "ROOM_NOT_FOUND",
                        "message": GENERIC_ROOM_NOT_FOUND_MESSAGE,
                    },
                },
            )
        return JSONResponse(content=room_geometry_to_dict(room, room_id))

    @router.post("/api/evaluate")
    def post_evaluate(request: EvaluateRequest) -> dict[str, object]:
        # EvaluateError (→ 400) and any uncaught error (→ 500) are handled by the
        # app-level exception handlers; the success path returns the envelope.
        report = evaluate_request(request)
        return {"ok": True, "report": report}

    return router


def create_app() -> FastAPI:
    """Build the FastAPI app: router + the generic-message exception handlers."""
    app = FastAPI(
        title="roomestim immersive-layout server",
        version="0.61.0",
        description=(
            "Stateless REST API over the frozen 4-axis immersive-layout "
            "trade-off engine (no physics in this layer)."
        ),
    )
    app.include_router(_build_router())

    @app.exception_handler(RequestValidationError)
    async def _on_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Fold FastAPI's default 422 into the uniform envelope. ``fields`` lists
        # only the dotted loc paths (these describe the CLIENT's own request
        # shape, safe to return); the pydantic msg/input/url/ctx are dropped so
        # nothing echoes the input or a pydantic-internal URL.
        fields = [".".join(str(p) for p in e["loc"]) for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "error": {
                    "code": "VALIDATION",
                    "message": GENERIC_VALIDATION_MESSAGE,
                    "fields": fields,
                },
            },
        )

    @app.exception_handler(EvaluateError)
    async def _on_evaluate_error(
        request: Request, exc: EvaluateError
    ) -> JSONResponse:
        # The real cause was already logged by the service; emit the generic body.
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": {"code": exc.code, "message": exc.message},
            },
        )

    @app.exception_handler(Exception)
    async def _on_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # ADR 0038 / OQ-45: log full detail server-side, leak NOTHING to client.
        _LOG.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {"code": "INTERNAL", "message": GENERIC_INTERNAL_MESSAGE},
            },
        )

    return app
