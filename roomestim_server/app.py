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
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from roomestim_server.errors import (
    GENERIC_EXAMPLE_NOT_FOUND_MESSAGE,
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
from roomestim_server.schemas import (
    EvaluateRequest,
    LayoutExportRequest,
    PlaceRequest,
    UploadMeshRequest,
    UploadRoomPlanRequest,
    UploadRoomRequest,
    UploadStructureRequest,
)
from roomestim_server.service import (
    evaluate_request,
    export_layout,
    list_examples,
    list_materials,
    list_specs,
    load_example,
    place_request,
    upload_mesh,
    upload_room,
    upload_roomplan,
    upload_structure,
)

_LOG = logging.getLogger("roomestim_server.app")

#: The P5.2 static frontend (index.html + main.js) lives beside this module.
_STATIC_DIR = Path(__file__).parent / "static"

__all__ = ["create_app"]


def _build_router() -> APIRouter:
    """Construct the API router (endpoints close over the core service)."""
    router = APIRouter()

    @router.get("/")
    def index() -> FileResponse:
        # Serve the static viewer shell (P5.2). The Three.js/main.js assets are
        # served by the ``/static`` StaticFiles mount added in create_app().
        return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")

    @router.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/api/rooms")
    def get_rooms() -> dict[str, object]:
        return {"rooms": list_rooms()}

    @router.get("/api/specs")
    def get_specs() -> dict[str, object]:
        # Catalog metadata only (model_key/price/provenance) — NO physics (D29).
        return {"specs": list_specs()}

    @router.get("/api/materials")
    def get_materials() -> dict[str, object]:
        # Curated material rule-base (label/name/absorption_500hz) for the UI
        # dropdowns — real Vorländer 2020 coefficients, NO physics here (P5.9).
        return {"materials": list_materials()}

    @router.post("/api/rooms/upload")
    def post_upload_room(request: UploadRoomRequest) -> dict[str, object]:
        # Parse room.yaml text via core read_room_yaml (D29 — zero geometry math
        # here). A bad file → generic EvaluateError (→ 400); the app handlers cover
        # errors. Distinct from the GET ``/api/rooms/{id}`` route (different method).
        result = upload_room(request)
        return {"ok": True, **result}

    @router.post("/api/rooms/upload/roomplan")
    def post_upload_roomplan(request: UploadRoomPlanRequest) -> dict[str, object]:
        # Parse an Apple RoomPlan JSON sidecar via core RoomPlanAdapter (D29 — zero
        # geometry math here; torch-free json+numpy adapter). A bad/`.usdz` body →
        # generic EvaluateError (→ 400); the app handlers cover errors. This is an
        # EXACT POST path (not shadowed by the GET ``/api/rooms/{room_id:path}``
        # route: different method, and exact paths win over the path-param route).
        result = upload_roomplan(request)
        return {"ok": True, **result}

    @router.post("/api/rooms/upload/structure")
    def post_upload_structure(request: UploadStructureRequest) -> dict[str, object]:
        # Parse an Apple CapturedStructure (multi-room) export via core
        # parse_structure (D29 — zero geometry math here; torch-free
        # json+numpy+shapely splitter). Returns {"rooms": [...]} (one per section,
        # each with its own uploaded:<n> id). A bad body → generic EvaluateError
        # (→ 400). EXACT POST path (not shadowed by the GET path-param route).
        result = upload_structure(request)
        return {"ok": True, **result}

    @router.post("/api/rooms/upload/mesh")
    def post_upload_mesh(request: UploadMeshRequest) -> dict[str, object]:
        # Parse a BINARY mesh file (base64 in JSON — NO multipart) via core
        # MeshAdapter (D29 — zero geometry math here; trimesh for
        # .obj/.gltf/.glb/.ply, the [usd] extra for .usdz). An unsupported suffix /
        # bad base64 / oversize / .usdz-without-[usd] → generic EvaluateError
        # (→ 400). EXACT POST path (not shadowed by the GET path-param route).
        result = upload_mesh(request)
        return {"ok": True, **result}

    @router.post("/api/export/layout")
    def post_export_layout(request: LayoutExportRequest) -> dict[str, object]:
        # Emit the engine-contract layout.yaml for the request placement via core
        # write_layout_yaml (D29 — zero placement math here). Returns
        # {"filename": "layout.yaml", "yaml": <text>}. Validation is env-gated on
        # SPATIAL_ENGINE_REPO_DIR; an R10/WFS contract violation → generic
        # EvaluateError (→ 400). EXACT POST path (no route clash).
        result = export_layout(request)
        return {"ok": True, **result}

    @router.get("/api/examples")
    def get_examples() -> dict[str, object]:
        # Bundled example-capture manifest (metadata only — files parsed only on
        # load). No physics (D29).
        return {"examples": list_examples()}

    @router.post("/api/examples/{example_id}/load")
    def post_load_example(example_id: str) -> JSONResponse:
        # Load a bundled example by id via the SAME parse+register path as an
        # upload: {"room": ...} for a roomplan example, {"rooms": [...]} for a
        # structure example. Unknown id → generic 404 (mirrors the /api/rooms/{id}
        # 404 shape); a broken shipped example → generic 400 via EvaluateError
        # (handled by the app-level handler). Distinct exact path — no route clash.
        try:
            result = load_example(example_id)
        except KeyError:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": "EXAMPLE_NOT_FOUND",
                        "message": GENERIC_EXAMPLE_NOT_FOUND_MESSAGE,
                    },
                },
            )
        return JSONResponse(content={"ok": True, **result})

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
        # ``report`` is the verbatim engine dict; ``install`` (P6.C) is the additive
        # per-speaker installer guide (geometry only, or None if it could not build).
        result = evaluate_request(request)
        return {
            "ok": True,
            "report": result["report"],
            "install": result["install"],
        }

    @router.post("/api/place")
    def post_place(request: PlaceRequest) -> dict[str, object]:
        # Seed a layout via core run_placement (D29 — zero placement math here).
        # EvaluateError (→ 400) / uncaught (→ 500) handled by the app handlers.
        placement = place_request(request)
        return {"ok": True, "placement": placement}

    return router


def create_app() -> FastAPI:
    """Build the FastAPI app: router + the generic-message exception handlers."""
    app = FastAPI(
        title="roomestim immersive-layout server",
        version="0.63.0",
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

    # Mount the static frontend LAST — a distinct ``/static`` prefix that does not
    # shadow the ``/api/*``, ``/healthz`` or ``/`` routes registered above.
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    return app
