"""CaptureAdapter Protocol — backend-agnostic ingest contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from roomestim.model import RoomModel


@dataclass(frozen=True)
class ScaleAnchor:
    """Optional metric anchor for scale-ambiguous backends (COLMAP).

    Backends that emit metric scale natively (RoomPlan, Polycam) ignore this.
    """

    type: str  # "aruco" | "known_distance" | "user_provided"
    length_m: float


@runtime_checkable
class CaptureAdapter(Protocol):
    def parse(self, path: Path, *, scale_anchor: ScaleAnchor | None = None) -> RoomModel: ...
