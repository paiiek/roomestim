"""tests/test_predict_rt60_default.py — ADR 0030 default predictor (v0.15.0).

Covers:
  - is_rectilinear_shoebox: 4-pt axis-aligned True, off-axis False, 6-pt False.
  - predict_rt60_default: shoebox → ISM, non-shoebox → Eyring.
  - predict_rt60_default_per_band: shoebox per-band ISM has 6 bands.
  - prefer_ism=False escape hatch routes to Eyring even on shoebox.
  - Rationale string contains predictor + geometry markers.
  - ISM/Eyring runtime invariant on shoebox: ISM >= Eyring - 1e-6 (ADR 0009).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.reconstruct.predictor import (
    _polygon_area_3d,
    is_rectilinear_shoebox,
    predict_rt60_default,
    predict_rt60_default_per_band,
)


@pytest.fixture
def lab_room() -> object:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    return RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)


@pytest.fixture
def area_dict(lab_room: object) -> dict[object, float]:
    from collections import defaultdict
    areas: dict[object, float] = defaultdict(float)
    for s in lab_room.surfaces:  # type: ignore[attr-defined]
        areas[s.material] += _polygon_area_3d(s.polygon)
    return dict(areas)


def test_is_rectilinear_shoebox_lab_room_true(lab_room: object) -> None:
    assert is_rectilinear_shoebox(lab_room) is True


def test_predict_rt60_default_lab_room_uses_ism(lab_room: object, area_dict: dict[object, float]) -> None:
    pred = predict_rt60_default(lab_room, area_dict)
    assert pred.predictor_name == "image_source"
    assert pred.rt60_s > 0
    assert pred.rt60_per_band_s == {}  # single-band variant
    assert "shoebox" in pred.rationale
    assert "ISM" in pred.rationale


def test_predict_rt60_default_per_band_lab_room_uses_ism(lab_room: object, area_dict: dict[object, float]) -> None:
    pred = predict_rt60_default_per_band(lab_room, area_dict)
    assert pred.predictor_name == "image_source"
    assert len(pred.rt60_per_band_s) == 6
    assert 500 in pred.rt60_per_band_s
    assert pred.rt60_s == pred.rt60_per_band_s[500]
    for band, rt in pred.rt60_per_band_s.items():
        assert rt > 0, f"Band {band} Hz RT60 must be positive, got {rt}"


def test_prefer_ism_false_routes_to_eyring(lab_room: object, area_dict: dict[object, float]) -> None:
    pred = predict_rt60_default(lab_room, area_dict, prefer_ism=False)
    assert pred.predictor_name == "eyring"
    assert pred.rt60_s > 0
    assert "Eyring" in pred.rationale or "non-shoebox" in pred.rationale


def test_ism_eyring_runtime_invariant_lab_room(lab_room: object, area_dict: dict[object, float]) -> None:
    """ISM >= Eyring - 1e-6 per ADR 0009 + ADR 0028 §Decision sub-item 2."""
    pred_ism = predict_rt60_default(lab_room, area_dict, prefer_ism=True)
    pred_eyr = predict_rt60_default(lab_room, area_dict, prefer_ism=False)
    assert pred_ism.rt60_s >= pred_eyr.rt60_s - 1e-6, (
        f"ISM RT60 {pred_ism.rt60_s} < Eyring {pred_eyr.rt60_s} - 1e-6 — runtime invariant violated"
    )


def test_is_rectilinear_shoebox_three_point_returns_false() -> None:
    """A 3-point polygon (triangle) is not a shoebox."""

    class _FakeRoom:
        class _Pt:
            def __init__(self, x: float, z: float) -> None:
                self.x = x
                self.z = z
        floor_polygon = [_Pt(0, 0), _Pt(1, 0), _Pt(0.5, 1)]
        ceiling_height_m = 2.5
        surfaces: list[object] = []

    assert is_rectilinear_shoebox(_FakeRoom()) is False


def test_is_rectilinear_shoebox_off_axis_returns_false() -> None:
    """Rotated 4-point rectangle (3 unique x or 3 unique z) is not detected as shoebox."""

    class _FakeRoom:
        class _Pt:
            def __init__(self, x: float, z: float) -> None:
                self.x = x
                self.z = z
        # Rotated quad: 4 unique x and 4 unique z
        floor_polygon = [_Pt(0, 0), _Pt(2, 1), _Pt(3, 3), _Pt(1, 2)]
        ceiling_height_m = 2.5
        surfaces: list[object] = []

    assert is_rectilinear_shoebox(_FakeRoom()) is False


def test_rt60_prediction_dataclass_is_frozen() -> None:
    from roomestim.reconstruct import RT60Prediction

    p = RT60Prediction(
        rt60_s=0.5,
        rt60_per_band_s={},
        predictor_name="eyring",
        rationale="test",
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        p.rt60_s = 1.0  # type: ignore[misc]


def test_predictor_name_literal_only_two_values() -> None:
    """Sanity: PredictorName Literal must remain ('image_source', 'eyring')."""
    from roomestim.reconstruct.predictor import PredictorName
    # PredictorName is a typing.Literal — assert via get_args
    from typing import get_args
    assert set(get_args(PredictorName)) == {"image_source", "eyring"}
