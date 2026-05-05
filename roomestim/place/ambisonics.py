"""Ambisonics placement — deferred to v0.3 per ADR 0003."""

from __future__ import annotations

from roomestim.model import PlacementResult


def place_ambisonics(*args: object, **kwargs: object) -> PlacementResult:
    raise NotImplementedError(
        "Ambisonics placement deferred to v0.3 per ADR 0003."
    )


__all__ = ["place_ambisonics"]
