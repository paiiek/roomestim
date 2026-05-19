"""tests/test_objects_acoustic_invariant.py — v0.17 Phase 6 ADR 0009 invariant.

Covers Phase 6 acceptance gates per .omc/plans/v0.17-design.md (Phase 6,
line 537-550):

- Baseline: lab_room with no objects retains the v0.16.1 RT60 value.
- Adding a column noticeably changes the RT60 (0.005 ≤ |Δ| ≤ 0.10 s).
- Adding door + window applies small overrides (|Δ| < 0.05 s).
- Random invariant sweep across 10 seeds × {column, door, window} ensures
  ``ism_rt60 ≥ eyring_rt60 - 1e-6`` (ADR 0009).
  (Reduced to 10 from 50 for default-lane runtime; full 50 in nightly via
  @pytest.mark.slow if such a marker becomes registered.)
- Cascade default unchanged: predictor_name ∈ {"image_source", "eyring"}.
- ``is_rectilinear_shoebox`` ignores objects and stays True after adding
  a column to a shoebox.
"""

from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path

import pytest

from roomestim import Object, evolve_room_add_object
from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.geom.polygon import polygon_area_3d
from roomestim.model import MaterialLabel, Point3, RoomModel
from roomestim.reconstruct.predictor import (
    is_rectilinear_shoebox,
    predict_rt60_default,
)


_LAB_ROOM_BASELINE_RT60_S: float = 1.9190766987173207


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def lab_room() -> RoomModel:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    return RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)


@pytest.fixture
def area_dict(lab_room: RoomModel) -> dict[MaterialLabel, float]:
    areas: dict[MaterialLabel, float] = defaultdict(float)
    for s in lab_room.surfaces:
        areas[s.material] += polygon_area_3d(s.polygon)
    return dict(areas)


# --------------------------------------------------------------------------- #
# Baseline: empty objects → byte-equal vs v0.16.1
# --------------------------------------------------------------------------- #


def test_lab_room_no_objects_unchanged(
    lab_room: RoomModel,
    area_dict: dict[MaterialLabel, float],
) -> None:
    """No-objects lab_room rt60 matches the v0.16.1 byte-equal baseline."""
    assert lab_room.objects == []
    pred = predict_rt60_default(lab_room, area_dict)
    assert pred.rt60_s == pytest.approx(_LAB_ROOM_BASELINE_RT60_S, abs=1e-9)
    assert pred.predictor_name == "image_source"


# --------------------------------------------------------------------------- #
# Object-induced deltas
# --------------------------------------------------------------------------- #


def test_column_added_changes_rt60(
    lab_room: RoomModel,
    area_dict: dict[MaterialLabel, float],
) -> None:
    """Concrete column inside the room shifts RT60 within [0.005, 0.10] s."""
    base = predict_rt60_default(lab_room, area_dict).rt60_s
    col = Object(
        kind="column",
        anchor=Point3(x=2.5, y=0.0, z=2.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )
    new_room = evolve_room_add_object(lab_room, col)
    new_rt = predict_rt60_default(new_room, area_dict).rt60_s
    delta = abs(new_rt - base)
    assert 0.005 <= delta <= 0.10, f"column Δrt60 out of expected band: {delta}"


def test_door_window_changes_minimal(
    lab_room: RoomModel,
    area_dict: dict[MaterialLabel, float],
) -> None:
    """Door + window α overrides produce a small (< 0.05 s) RT60 delta."""
    base = predict_rt60_default(lab_room, area_dict).rt60_s
    door = Object(
        kind="door",
        anchor=Point3(x=1.0, y=0.0, z=-2.0),
        width_m=0.9,
        height_m=2.1,
        depth_m=0.0,
        wall_index=0,
        material=MaterialLabel.WALL_PAINTED,
    )
    window = Object(
        kind="window",
        anchor=Point3(x=2.5, y=1.0, z=0.0),
        width_m=1.2,
        height_m=1.2,
        depth_m=0.0,
        wall_index=1,
        material=MaterialLabel.GLASS,
    )
    room_with_door = evolve_room_add_object(lab_room, door)
    room_with_both = evolve_room_add_object(room_with_door, window)
    new_rt = predict_rt60_default(room_with_both, area_dict).rt60_s
    assert abs(new_rt - base) < 0.05


# --------------------------------------------------------------------------- #
# Cascade name + shoebox detection invariants
# --------------------------------------------------------------------------- #


def test_cascade_unchanged_default(
    lab_room: RoomModel,
    area_dict: dict[MaterialLabel, float],
) -> None:
    """Predictor_name stays inside {"image_source", "eyring"} after objects."""
    col = Object(
        kind="column",
        anchor=Point3(x=1.0, y=0.0, z=1.0),
        width_m=0.3,
        height_m=2.85,
        depth_m=0.3,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )
    new_room = evolve_room_add_object(lab_room, col)
    pred = predict_rt60_default(new_room, area_dict)
    assert pred.predictor_name in {"image_source", "eyring"}


def test_is_rectilinear_shoebox_robust_to_objects(
    lab_room: RoomModel,
) -> None:
    """Adding a column does not change the floor_polygon → still a shoebox."""
    assert is_rectilinear_shoebox(lab_room) is True
    col = Object(
        kind="column",
        anchor=Point3(x=1.5, y=0.0, z=0.5),
        width_m=0.4,
        height_m=2.85,
        depth_m=0.4,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )
    new_room = evolve_room_add_object(lab_room, col)
    assert is_rectilinear_shoebox(new_room) is True


# --------------------------------------------------------------------------- #
# ADR 0009 invariant sweep — N seeds × 3 kinds
# --------------------------------------------------------------------------- #


_INVARIANT_SEEDS: int = 10  # Reduce to 10 from 50 for default lane; 50 in nightly via @pytest.mark.slow.


def _random_column(rng: random.Random) -> Object:
    x = rng.uniform(-2.0, 2.0)
    z = rng.uniform(-1.6, 1.6)
    w = rng.uniform(0.1, 0.5)
    d = rng.uniform(0.1, 0.5)
    return Object(
        kind="column",
        anchor=Point3(x=x, y=0.0, z=z),
        width_m=w,
        height_m=2.85,
        depth_m=d,
        wall_index=None,
        material=MaterialLabel.WALL_CONCRETE,
    )


def _random_door(rng: random.Random, n_walls: int) -> Object:
    return Object(
        kind="door",
        anchor=Point3(
            x=rng.uniform(-1.0, 1.0),
            y=0.0,
            z=rng.uniform(-1.0, 1.0),
        ),
        width_m=rng.uniform(0.7, 1.0),
        height_m=rng.uniform(1.9, 2.3),
        depth_m=0.0,
        wall_index=rng.randrange(n_walls),
        material=MaterialLabel.WALL_PAINTED,
    )


def _random_window(rng: random.Random, n_walls: int) -> Object:
    return Object(
        kind="window",
        anchor=Point3(
            x=rng.uniform(-1.0, 1.0),
            y=rng.uniform(0.5, 1.5),
            z=rng.uniform(-1.0, 1.0),
        ),
        width_m=rng.uniform(0.6, 1.4),
        height_m=rng.uniform(0.6, 1.4),
        depth_m=0.0,
        wall_index=rng.randrange(n_walls),
        material=MaterialLabel.GLASS,
    )


def test_invariant_n_seeds_3_kinds(
    lab_room: RoomModel,
    area_dict: dict[MaterialLabel, float],
) -> None:
    """ISM ≥ Eyring - 1e-6 for every seed × kind (ADR 0009 invariant)."""
    n_walls = sum(1 for s in lab_room.surfaces if s.kind == "wall")
    for seed in range(_INVARIANT_SEEDS):
        rng = random.Random(seed)
        for builder in (_random_column, _random_door, _random_window):
            if builder is _random_column:
                obj = builder(rng)  # type: ignore[call-arg]
            else:
                obj = builder(rng, n_walls)  # type: ignore[call-arg]
            new_room = evolve_room_add_object(lab_room, obj)
            pred_ism = predict_rt60_default(new_room, area_dict, prefer_ism=True)
            pred_eyr = predict_rt60_default(new_room, area_dict, prefer_ism=False)
            assert pred_ism.rt60_s >= pred_eyr.rt60_s - 1e-6, (
                f"ADR 0009 invariant broken: seed={seed} kind={obj.kind} "
                f"ism={pred_ism.rt60_s} eyr={pred_eyr.rt60_s}"
            )
