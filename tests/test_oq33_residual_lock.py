"""tests/test_oq33_residual_lock.py — v0.18.2 OQ-33 regression lock.

Two invariants locked by D54 (v0.18.2):

1. **Adapter placeholder lock**: MeshAdapter and ACEChallengeAdapter still return
   ``objects==[]``. If either adapter silently gains auto-detection without a
   fired Reverse-criterion (D54), this test fails immediately, forcing a
   deliberate decision rather than silent scope creep.

2. **Manual-path round-trip**: ``evolve_room_add_object`` adds an Object that
   survives a ``room.yaml`` write → read cycle (declared DONE as of v0.17).
   Locks the shipped manual-annotation path against silent regression.

Gates: G10 (adapter placeholder) + G11 (manual round-trip) per
``.omc/plans/v0.18.2-patch.md`` §5.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from roomestim import Object, evolve_room_add_object, evolve_room_remove_object
from roomestim.export.room_yaml import write_room_yaml
from roomestim.io.room_yaml_reader import read_room_yaml
from roomestim.model import MaterialLabel, Point3, RoomModel


# --------------------------------------------------------------------------- #
# Shared fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def lab_room() -> RoomModel:
    """RoomPlan lab_room.json fixture — shared baseline."""
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    from roomestim.adapters.roomplan import RoomPlanAdapter

    room = RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)
    assert isinstance(room, RoomModel)
    return room


# --------------------------------------------------------------------------- #
# G10 — Adapter placeholder lock
# --------------------------------------------------------------------------- #


def test_mesh_adapter_objects_empty() -> None:
    """MeshAdapter must still return objects=[] (OQ-33 auto-detection residual).

    D54: MeshAdapter keeps objects=[] until a Reverse-criterion fires at v0.20.
    If this test fails, an adapter gained auto-detection without a deliberate
    D54-override decision — must be reviewed against D26 trigger conditions.
    """
    fixture = Path("tests/fixtures/lab_room.obj")
    if not fixture.exists():
        pytest.skip("lab_room.obj fixture not found")

    from roomestim.adapters.mesh import MeshAdapter

    room = MeshAdapter().parse(fixture)
    assert isinstance(room, RoomModel)
    assert room.objects == [], (
        "MeshAdapter returned non-empty objects — OQ-33 auto-detection residual "
        "must remain deferred until a D54 Reverse-criterion fires (v0.20 hard wall). "
        f"Got: {room.objects}"
    )


def test_ace_challenge_adapter_objects_empty() -> None:
    """ACE Challenge adapter (load_room) must still return objects=[] (OQ-33 residual).

    D54: ACEChallengeAdapter's _build_room_model sets objects=[] placeholder until
    a D54 Reverse-criterion fires at v0.20.
    """
    fixture_dir = Path("tests/fixtures/ace_challenge_sample")
    if not fixture_dir.exists():
        pytest.skip("ace_challenge_sample fixture not found")

    from roomestim.adapters.ace_challenge import list_rooms, load_room

    rooms = list_rooms(fixture_dir)
    if not rooms:
        pytest.skip("ace_challenge_sample has no rooms")

    case = load_room(fixture_dir, rooms[0])
    room = case.room
    assert isinstance(room, RoomModel)
    assert room.objects == [], (
        "ACE Challenge load_room returned non-empty objects — OQ-33 auto-detection "
        "residual must remain deferred until a D54 Reverse-criterion fires. "
        f"Got: {room.objects}"
    )


# --------------------------------------------------------------------------- #
# G11 — Manual-path round-trip
# --------------------------------------------------------------------------- #


def test_evolve_room_add_object_yaml_round_trip(
    lab_room: RoomModel, tmp_path: Path
) -> None:
    """evolve_room_add_object → write_room_yaml → read_room_yaml preserves object.

    Locks the manual-annotation path declared DONE at v0.17 (D54 §1.2).
    An object added via the core evolve helper must survive a room.yaml
    write→read cycle with kind and material intact.
    """
    col = Object(
        kind="column",
        anchor=Point3(x=1.0, y=0.0, z=1.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        material=MaterialLabel.WALL_CONCRETE,
    )
    room_with_obj = evolve_room_add_object(lab_room, col)
    assert len(room_with_obj.objects) == len(lab_room.objects) + 1
    assert room_with_obj.objects[-1].kind == "column"

    yaml_path = tmp_path / "room_with_col.yaml"
    write_room_yaml(room_with_obj, yaml_path)

    room_read = read_room_yaml(yaml_path)
    assert isinstance(room_read, RoomModel)
    assert len(room_read.objects) == len(lab_room.objects) + 1, (
        "Object count mismatch after YAML round-trip — evolve_room_add_object "
        "manual path has regressed."
    )
    assert room_read.objects[-1].kind == "column"
    assert room_read.objects[-1].material == MaterialLabel.WALL_CONCRETE
    assert abs(room_read.objects[-1].width_m - 0.3) < 1e-9


def test_evolve_room_remove_object_yaml_round_trip(
    lab_room: RoomModel, tmp_path: Path
) -> None:
    """evolve_room_remove_object → write → read preserves removal.

    Companion to the add test — ensures the remove half of the manual
    annotation path also survives the YAML round-trip.
    """
    col = Object(
        kind="door",
        anchor=Point3(x=0.0, y=0.0, z=0.0),
        width_m=0.9,
        height_m=2.1,
        depth_m=0.05,
        wall_index=0,
        material=MaterialLabel.WALL_PAINTED,
    )
    room_added = evolve_room_add_object(lab_room, col)
    assert len(room_added.objects) >= 1

    room_removed = evolve_room_remove_object(room_added, len(room_added.objects) - 1)
    assert len(room_removed.objects) == len(lab_room.objects)

    yaml_path = tmp_path / "room_removed.yaml"
    write_room_yaml(room_removed, yaml_path)
    room_read = read_room_yaml(yaml_path)

    assert len(room_read.objects) == len(lab_room.objects), (
        "Object count after remove+round-trip does not match baseline — "
        "evolve_room_remove_object manual path has regressed."
    )
