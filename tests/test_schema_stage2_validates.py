"""v0.10 §2.4 — Stage-2 schema marker REVERT (default-lane).

One default-lane test asserting the post-revert v0.10 invariants:

- ``roomestim.__schema_version__ == "0.1-draft"`` (REVERTED from v0.9 ``"0.1"``).
- ``RoomModel().schema_version`` default is ``"0.1-draft"``.
- Both ``proto/room_schema.json`` (Stage-2 strict file) and
  ``proto/room_schema.draft.json`` (canonical default at v0.10) are
  preserved on disk; the Stage-2 strict file survives for v0.11+ re-flip
  when paper-faithful evidence arrives.

Per ADR 0018 firing of ADR 0016 §Reverse-criterion item (2): substitute
A11 disagrees with paper-retrieved RT60 by > 20% on lab + conference;
schema marker reverts ``"0.1"`` → ``"0.1-draft"``.
"""

from __future__ import annotations

from pathlib import Path

import roomestim
from tests.fixtures.synthetic_rooms import shoebox


def test_stage2_schema_flip_marker_and_strict_mode() -> None:
    """v0.10 — Stage-2 marker REVERTED per ADR 0016 §Reverse-criterion firing.

    See ADR 0018: substitute A11 disagrees with paper-retrieved RT60 by
    > 20% on lab + conference; reverse-criterion fires; marker reverts to
    "0.1-draft" while disagreement is investigated.
    """
    assert roomestim.__schema_version__ == "0.1-draft", (
        "v0.10: marker REVERTED to 0.1-draft per ADR 0018"
    )
    # The default ``RoomModel.schema_version`` reverts to "0.1-draft"; we
    # use the ``shoebox()`` factory (which constructs a RoomModel without
    # overriding schema_version) to assert the default propagates.
    room = shoebox()
    assert room.schema_version == "0.1-draft"
    # Backward-compat: Stage-2 strict file is preserved (NOT deleted) for
    # v0.11+ re-flip when paper-faithful evidence arrives.
    schema_root = Path(roomestim.__file__).resolve().parent.parent / "proto"
    assert (schema_root / "room_schema.json").exists(), (
        "Stage-2 schema file preserved for v0.11+ re-flip"
    )
    assert (schema_root / "room_schema.draft.json").exists(), (
        "Draft schema canonical for v0.10"
    )
