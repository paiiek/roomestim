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
    grid_resolution_m: float | None = None
    min_separation_deg: float | None = None


class EvaluateRequest(BaseModel):
    """``POST /api/evaluate`` request body."""

    room_id: str
    placement: PlacementIn
    spec: SpecIn = Field(default_factory=SpecIn)
    params: ParamsIn = Field(default_factory=ParamsIn)
