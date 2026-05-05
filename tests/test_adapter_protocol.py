"""CaptureAdapter Protocol structural-type tests."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from roomestim.adapters import CaptureAdapter, ScaleAnchor
from roomestim.model import RoomModel
from tests.fixtures.synthetic_rooms import shoebox


class _StubAdapter:
    """Concrete adapter that satisfies :class:`CaptureAdapter` structurally."""

    def parse(
        self,
        path: Path,
        *,
        scale_anchor: ScaleAnchor | None = None,
    ) -> RoomModel:
        return shoebox()


class _EmptyAdapter:
    """Class that does NOT implement ``parse`` — must NOT match the protocol."""


def test_protocol_runtime_checkable() -> None:
    instance = _StubAdapter()
    assert isinstance(instance, CaptureAdapter)
    room = instance.parse(Path("/tmp/whatever"))
    assert isinstance(room, RoomModel)


def test_protocol_rejects_missing_method() -> None:
    instance = _EmptyAdapter()
    assert not isinstance(instance, CaptureAdapter)


def test_scale_anchor_dataclass() -> None:
    anchor = ScaleAnchor(type="aruco", length_m=0.20)
    assert anchor.type == "aruco"
    assert anchor.length_m == 0.20

    # Frozen dataclass — assignment raises FrozenInstanceError.
    with pytest.raises(dataclasses.FrozenInstanceError):
        anchor.length_m = 0.40  # type: ignore[misc]
