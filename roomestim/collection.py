"""RoomCollection — additive multi-room composition container (ADR 0049).

A :class:`RoomCollection` is an **ordered bundle of N independent single-room
models**, nothing more. roomestim does NOT infer multiple rooms from one
capture; a collection is composed from N explicit single-room inputs (each a
genuine :class:`~roomestim.model.RoomModel` produced by an existing adapter).

Honest scope (Phase 1, ADR 0049 §Decision):
  * Rooms are **independent** — there is NO per-room transform / offset / pose.
    roomestim has no measured inter-room registration GT, so fabricating a
    shared building frame would be a fake number. Offsets are opt-in / user
    supplied only and are DEFERRED to a later phase.
  * Acoustics stay **per-room**. There is intentionally NO aggregate footprint
    union, combined volume, or combined RT60 (that is the ADR 0047 fake-number
    trap; re-opens only with measured multi-room GT).

This module only imports from :mod:`roomestim.model`; it does not edit any
single-room code path, so single-room goldens stay byte-equal by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from roomestim.model import PlacementResult, RoomModel


@dataclass
class RoomCollection:
    """An ordered, typed bundle of independent single-room models.

    Attributes
    ----------
    name:
        Human-readable collection / venue name. Carries no geometric meaning.
    rooms:
        Ordered list of independent :class:`~roomestim.model.RoomModel` members.
    placements:
        Parallel-indexed per-room placement results
        (``placements[i]`` belongs to ``rooms[i]``). ``None`` marks a room with
        no placement yet. When constructed empty it is normalized to a list of
        ``None`` the same length as ``rooms`` so the parallel-index invariant
        always holds.
    """

    name: str
    rooms: list[RoomModel]
    placements: list[PlacementResult | None] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.placements:
            self.placements = [None] * len(self.rooms)
        elif len(self.placements) != len(self.rooms):
            raise ValueError(
                "RoomCollection.placements must be parallel-indexed with rooms: "
                f"got {len(self.placements)} placements for {len(self.rooms)} rooms."
            )


__all__ = ["RoomCollection"]
