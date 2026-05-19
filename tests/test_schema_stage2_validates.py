"""v0.17 §3 Phase 1 — Schema marker BUMP to 0.2-draft (default-lane).

One default-lane test asserting the post-v0.17 invariants:

- ``roomestim.__schema_version__ == "0.2-draft"`` (BUMPED from v0.10 ``"0.1-draft"``).
- ``RoomModel().schema_version`` default is ``"0.2-draft"``.
- All three proto schema files survive on disk:
  ``proto/room_schema.json`` (Stage-2 strict, v0.11+ re-flip slot),
  ``proto/room_schema.draft.json`` (Stage-1 draft, v0.10 baseline) and
  ``proto/room_schema.v0_2.draft.json`` (Stage-1 draft + objects[], v0.17 NEW).

Per ADR 0034 + D44 (v0.17): obstacle (`Object`) schema extension lands as
the new default `0.2-draft` marker; legacy `0.1-draft` parse path is
preserved for backward read.
"""

from __future__ import annotations

from pathlib import Path

import roomestim
from tests.fixtures.synthetic_rooms import shoebox


def test_stage2_schema_flip_marker_and_strict_mode() -> None:
    """v0.17 — Schema marker BUMPED to 0.2-draft per ADR 0034 + D44.

    The new ``0.2-draft`` adds an ``objects[]`` field for columns / doors /
    windows. ``0.1-draft`` continues to parse back into a RoomModel with an
    empty ``objects`` list (backward-read), and the Stage-2 strict
    ``0.1`` file is preserved for future re-flip.
    """
    assert roomestim.__schema_version__ == "0.2-draft", (
        "v0.17: marker BUMPED to 0.2-draft per ADR 0034 + D44"
    )
    # The default ``RoomModel.schema_version`` is now "0.2-draft"; we use
    # the ``shoebox()`` factory (which constructs a RoomModel without
    # overriding schema_version) to assert the default propagates.
    room = shoebox()
    assert room.schema_version == "0.2-draft"
    # Backward-compat: Stage-2 strict file + legacy draft + new draft all
    # coexist on disk.
    schema_root = Path(roomestim.__file__).resolve().parent.parent / "proto"
    assert (schema_root / "room_schema.json").exists(), (
        "Stage-2 schema file preserved for re-flip"
    )
    assert (schema_root / "room_schema.draft.json").exists(), (
        "Legacy 0.1-draft schema preserved for backward parse"
    )
    assert (schema_root / "room_schema.v0_2.draft.json").exists(), (
        "v0.17 0.2-draft schema (objects[]) canonical for v0.17"
    )
