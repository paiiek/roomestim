"""roomestim_server.schemas — pydantic v2 request/response models (the JSON contract).

These models define the ``POST /api/evaluate`` request shape; FastAPI validates
against them and returns its default ``422`` (field-level, no internals) on a
malformed body. The success/error RESPONSE envelopes are documented here but
emitted as plain dicts by the app (the inner ``report`` is the dynamic note-first
``tradeoff_to_dict`` output, not a fixed pydantic schema).

Imports pydantic (a ``[server]`` transitive dep) at module top — this module is
NEVER imported at ``import roomestim`` time, only lazily via the app factory.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = [
    "PointIn",
    "SpeakerIn",
    "PlacementIn",
    "SpecIn",
    "ParamsIn",
    "EvaluateRequest",
    "PlaceRequest",
    "UploadRoomRequest",
    "UploadRoomPlanRequest",
]


class PointIn(BaseModel):
    """A listener-frame Cartesian point (x=right, y=up, z=front), metres."""

    x: float
    y: float
    z: float


class SpeakerIn(BaseModel):
    """One placed speaker. ``aim_direction`` null → core auto-aims at the listener."""

    channel: int
    position: PointIn
    aim_direction: PointIn | None = None


class PlacementIn(BaseModel):
    """The live-edited layout forwarded verbatim into a ``PlacementResult``."""

    target_algorithm: str = "vbap"
    regularity_hint: str = "ring"
    layout_name: str = "live-edit"
    speakers: list[SpeakerIn]


class SpecIn(BaseModel):
    """Built-in speaker spec selector + optional per-unit price override."""

    model_key: str = "generic_surround_compact"
    price: float | None = Field(
        default=None,
        description="Per-unit price override; only applied when > 0, else the catalog price is used.",
    )


class ParamsIn(BaseModel):
    """Engine parameters (1:1 with ``evaluate_layout`` keyword args).

    ``measured_rt60_s`` null/<=0 → the model RT60 is used (``rt60.source`` =
    ``"predicted"``). ``grid_resolution_m`` / ``min_separation_deg`` null → core
    defaults.
    """

    drive_w: float = 10.0
    target_spl_db: float = 85.0
    measured_rt60_s: float | None = None
    # Lower-bounded (≥0.05 m) so a network client cannot pass a tiny positive
    # value (e.g. 1e-6) that explodes the SPL-grid cell count (nx·nz, one
    # Shapely covers() per cell) into a per-request DoS. null → core default
    # (0.5 m). The floor is 10× finer than the core default — ample for an
    # interactive viewer while capping the worst-case lattice.
    grid_resolution_m: float | None = Field(default=None, ge=0.05)
    min_separation_deg: float | None = None


class EvaluateRequest(BaseModel):
    """``POST /api/evaluate`` request body."""

    room_id: str
    placement: PlacementIn
    spec: SpecIn = Field(default_factory=SpecIn)
    params: ParamsIn = Field(default_factory=ParamsIn)


class PlaceRequest(BaseModel):
    """``POST /api/place`` request body — seed a layout via core ``run_placement``.

    The five fields map 1:1 to ``run_placement``'s first five positional args
    (``room, algorithm, n_speakers, layout_radius_m, el_deg``). The wfs/coverage
    keyword arguments are intentionally NOT exposed here (P5.3) — their defaults
    apply. All placement physics stays in core; the server re-derives nothing.
    """

    room_id: str
    algorithm: str = "vbap"
    # Sanity-bounded (1..128) so a network client cannot request an absurd count
    # that stresses run_placement / the downstream SPL grid — a loose additive
    # guard (mirrors ``grid_resolution_m``'s floor); the REAL per-algorithm minimum
    # (e.g. VBAP ring n≥3) is still enforced by core → generic 400 on violation.
    n_speakers: int = Field(default=6, ge=1, le=128)
    layout_radius_m: float = 1.8
    el_deg: float = 0.0


class UploadRoomRequest(BaseModel):
    """``POST /api/rooms/upload`` request body — a room.yaml as raw TEXT.

    The file content is sent as a JSON string field (NOT multipart) so the
    server needs NO python-multipart dependency. The text is parsed ENTIRELY by
    the torch-free core reader ``roomestim.io.room_yaml_reader.read_room_yaml``
    (P5.4) — the server re-derives nothing and adds no geometry math.
    """

    # Bounded (~2 MB, far beyond any real room.yaml) so a network client cannot
    # stream a multi-GB body into memory + temp file + yaml.safe_load — an oversize
    # body then fails as a clean 422, not an OOM. Additive DoS guard.
    room_yaml: str = Field(max_length=2_000_000)


class UploadRoomPlanRequest(BaseModel):
    """``POST /api/rooms/upload/roomplan`` request body — an Apple RoomPlan JSON
    sidecar as raw TEXT.

    Like :class:`UploadRoomRequest`, the file content is sent as a JSON string
    field (NOT multipart) so the server needs NO python-multipart dependency. The
    text is parsed ENTIRELY by the torch-free core adapter
    ``roomestim.adapters.roomplan.RoomPlanAdapter`` (json+numpy only, both already
    core deps) — the server re-derives nothing and adds no geometry math. RoomPlan
    is metric-native, so ``scale_anchor`` is unused (D29).
    """

    # Bounded (~5 MB) so a network client cannot stream a multi-GB body into
    # memory + temp file + json.load — an oversize body then fails as a clean 422,
    # not an OOM (mirrors ``UploadRoomRequest``'s guard). The cap is ~2.5× the
    # room.yaml cap because a RoomPlan sidecar enumerates every wall/floor/ceiling
    # transform AND per-object (CapturedRoomObject) entry as verbose JSON, so a
    # richly-furnished multi-surface capture is legitimately larger than a
    # hand-authored room.yaml while still far below any adversarial payload.
    roomplan_json: str = Field(max_length=5_000_000)
