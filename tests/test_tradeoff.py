"""Tests for the 4-axis immersive-layout trade-off report (P3).

The report is a THIN AGGREGATION of the already-tested P1 SPL field, P2 angular
metrics, and RT60 predictor — so these tests lock the COMPOSITION contract (all
four axes present, headroom / meets-target consistency, the exact cost-sum
arithmetic, the measured-RT60 injection branch, JSON round-trip, and the error
propagation) rather than re-deriving physics. Default gate — numpy-free, no torch
/ web deps.
"""

from __future__ import annotations

import json

import pytest

from roomestim.design.tradeoff import (
    TRADEOFF_REPORT_NOTE,
    TradeoffCost,
    TradeoffReport,
    evaluate_layout,
    format_tradeoff_lines,
    tradeoff_to_dict,
)
from roomestim.model import ListenerArea, PlacedSpeaker, Point2, Point3
from roomestim.place.vbap import place_vbap_ring
from roomestim.reconstruct.measured_rt60 import MeasuredRT60
from roomestim.reconstruct._disclosure import MEASURED_RT60_NOTE
from roomestim.spec.speaker_spec import SpeakerSpec
from tests.fixtures.synthetic_rooms import shoebox


def _spec(price: float | None = None, **kw: object) -> SpeakerSpec:
    base: dict[str, object] = dict(
        model="test",
        sensitivity_db_1w1m=90.0,
        max_spl_db=120.0,
        dispersion_deg=90.0,
        price=price,
    )
    base.update(kw)
    return SpeakerSpec(**base)  # type: ignore[arg-type]


def _square_area(half: float = 1.0) -> ListenerArea:
    poly = [Point2(-half, -half), Point2(half, -half), Point2(half, half), Point2(-half, half)]
    return ListenerArea(polygon=poly, centroid=Point2(0.0, 0.0), height_m=1.20)


def _evaluate(spec: SpeakerSpec | dict[int, SpeakerSpec], **kw: object) -> TradeoffReport:
    room = shoebox()
    placement = place_vbap_ring(8, radius_m=2.0)
    params: dict[str, object] = dict(
        listener_area=_square_area(),
        drive_w=10.0,
        target_spl_db=80.0,
    )
    params.update(kw)
    return evaluate_layout(room, placement, spec, **params)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Happy path: all four axes present + headroom / meets-target consistency
# --------------------------------------------------------------------------- #


def test_report_has_all_four_axes() -> None:
    report = _evaluate(_spec(price=100.0))
    assert report.layout_name == "vbap_ring"
    assert report.target_algorithm == "VBAP"
    assert report.n_speakers == 8
    # Axis 1 SPL, axis 2 angular, axis 3 interference, axis 4 cost.
    assert report.spl.n_samples > 0
    assert report.angular.n_speakers == 8
    assert report.interference.n_speakers == 8
    assert report.cost.n_speakers == 8
    assert report.note == TRADEOFF_REPORT_NOTE


def test_headroom_is_exact_and_meets_target_consistent() -> None:
    report = _evaluate(_spec(), target_spl_db=80.0)
    # Headroom is exactly min_spl - target (analytic identity).
    assert report.spl_headroom_db == report.spl.min_spl_db - 80.0
    # A low target is met; a target above the achieved min SPL is not.
    assert report.meets_target_spl is (report.spl.min_spl_db >= 80.0)
    assert report.meets_target_spl is True

    high = _evaluate(_spec(), target_spl_db=report.spl.min_spl_db + 50.0)
    assert high.meets_target_spl is False
    assert high.spl_headroom_db == pytest.approx(-50.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# SPL provenance surfacing (the absolute-claim honesty self-describes)
# --------------------------------------------------------------------------- #


def test_spl_provenance_estimate_by_default() -> None:
    # SpeakerSpec defaults provenance="estimate"; the report surfaces it.
    report = _evaluate(_spec())
    assert report.spl_provenance == "estimate"
    assert tradeoff_to_dict(report)["spl_provenance"] == "estimate"
    assert any("specs=estimate" in ln for ln in format_tradeoff_lines(report))


def test_spl_provenance_datasheet_when_all_datasheet() -> None:
    report = _evaluate(_spec(provenance="datasheet"))
    assert report.spl_provenance == "datasheet"


def test_spl_provenance_mixed_when_specs_differ() -> None:
    specs: dict[int, SpeakerSpec] = {}
    for ch in range(1, 9):
        specs[ch] = _spec(provenance="datasheet" if ch <= 4 else "estimate")
    report = _evaluate(specs)
    assert report.spl_provenance == "mixed"


# --------------------------------------------------------------------------- #
# Cost axis: all / some / none priced
# --------------------------------------------------------------------------- #


def test_cost_all_priced_is_complete_and_exact_sum() -> None:
    report = _evaluate(_spec(price=125.0))
    assert report.cost.complete is True
    assert report.cost.n_priced == 8
    assert report.cost.n_speakers == 8
    assert report.cost.total_price == pytest.approx(8 * 125.0)  # exact = 1000.0


def test_cost_some_priced_is_partial_sum() -> None:
    # Per-channel specs: channels 1-3 priced (10/20/30), 4-8 unpriced.
    specs: dict[int, SpeakerSpec] = {}
    for ch in range(1, 9):
        specs[ch] = _spec(price=float(ch * 10) if ch <= 3 else None)
    report = _evaluate(specs)
    assert report.cost.complete is False
    assert report.cost.n_priced == 3
    assert report.cost.total_price == pytest.approx(10.0 + 20.0 + 30.0)  # 60.0


def test_cost_none_priced_is_none() -> None:
    report = _evaluate(_spec(price=None))
    assert report.cost.total_price is None
    assert report.cost.complete is False
    assert report.cost.n_priced == 0


# --------------------------------------------------------------------------- #
# RT60 injection: float / MeasuredRT60 / None
# --------------------------------------------------------------------------- #


def test_rt60_none_uses_predicted() -> None:
    report = _evaluate(_spec(), measured_rt60=None)
    assert report.rt60_source == "predicted"
    assert report.rt60_measured_s is None
    assert report.rt60_effective_s == report.rt60_predicted_s
    assert report.rt60_predicted_s > 0.0


def test_rt60_float_injection_overrides() -> None:
    report = _evaluate(_spec(), measured_rt60=0.42)
    assert report.rt60_source == "measured"
    assert report.rt60_measured_s == pytest.approx(0.42)
    assert report.rt60_effective_s == pytest.approx(0.42)
    # The model estimate is still computed + carried for comparison.
    assert report.rt60_predicted_s > 0.0


def test_rt60_measured_dataclass_nonpositive_rejected() -> None:
    # MeasuredRT60 has no validating __post_init__, so a hand-built non-positive
    # rt60_s must be rejected by the composer, symmetric with the float branch.
    bad = MeasuredRT60(
        rt60_s=-1.0,
        sample_rate_hz=48000,
        n_samples=48000,
        source="<test>",
        method="test",
        note=MEASURED_RT60_NOTE,
    )
    with pytest.raises(ValueError, match="measured_rt60"):
        _evaluate(_spec(), measured_rt60=bad)


def test_rt60_measured_dataclass_injection_overrides() -> None:
    measured = MeasuredRT60(
        rt60_s=0.55,
        sample_rate_hz=48000,
        n_samples=48000,
        source="<test>",
        method="test",
        note=MEASURED_RT60_NOTE,
    )
    report = _evaluate(_spec(), measured_rt60=measured)
    assert report.rt60_source == "measured"
    assert report.rt60_effective_s == pytest.approx(0.55)
    assert report.rt60_measured_s == pytest.approx(0.55)


# --------------------------------------------------------------------------- #
# Serialisation + formatting
# --------------------------------------------------------------------------- #


def test_tradeoff_to_dict_is_json_serialisable_note_first() -> None:
    report = _evaluate(_spec(price=100.0), measured_rt60=0.42)
    d = tradeoff_to_dict(report)
    assert list(d)[0] == "note"  # note is the FIRST key
    # Nested composed dicts present.
    assert "spl" in d and isinstance(d["spl"], dict)
    assert "angular" in d and isinstance(d["angular"], dict)
    assert "interference" in d and isinstance(d["interference"], dict)
    assert "cost" in d and isinstance(d["cost"], dict)
    assert "rt60" in d and isinstance(d["rt60"], dict)
    cost = d["cost"]
    assert isinstance(cost, dict)
    assert cost["total_price"] == pytest.approx(800.0)
    rt60 = d["rt60"]
    assert isinstance(rt60, dict)
    assert rt60["source"] == "measured"
    assert rt60["effective_s"] == pytest.approx(0.42)
    # Round-trips through JSON.
    assert json.loads(json.dumps(d))["note"] == TRADEOFF_REPORT_NOTE


def test_tradeoff_to_dict_unpriced_cost_is_null() -> None:
    d = tradeoff_to_dict(_evaluate(_spec(price=None)))
    cost = d["cost"]
    assert isinstance(cost, dict)
    assert cost["total_price"] is None
    assert cost["complete"] is False


def test_format_lines_smoke() -> None:
    lines = format_tradeoff_lines(_evaluate(_spec(price=100.0)))
    assert any("trade-off" in ln for ln in lines)
    assert any("cost:" in ln for ln in lines)
    assert any("rt60:" in ln for ln in lines)
    # No acoustic guarantee in the header.
    assert any("NO acoustic guarantee" in ln for ln in lines)


def test_format_lines_unpriced_says_unpriced() -> None:
    lines = format_tradeoff_lines(_evaluate(_spec(price=None)))
    assert any("cost: unpriced" in ln for ln in lines)


# --------------------------------------------------------------------------- #
# Error paths
# --------------------------------------------------------------------------- #


def test_nonpositive_drive_w_raises() -> None:
    with pytest.raises(ValueError, match="drive_w"):
        _evaluate(_spec(), drive_w=0.0)


def test_nonpositive_measured_rt60_raises() -> None:
    with pytest.raises(ValueError, match="measured_rt60"):
        _evaluate(_spec(), measured_rt60=-1.0)


def test_too_few_speakers_propagates() -> None:
    room = shoebox()
    one = place_vbap_ring(8, radius_m=2.0)
    # Single speaker => angular_uniformity / interference_proxy raise.
    one.speakers = [PlacedSpeaker(channel=1, position=Point3(x=0.0, y=0.0, z=2.0))]
    with pytest.raises(ValueError, match="kErrTooFewSpeakers"):
        evaluate_layout(
            room,
            one,
            _spec(),
            listener_area=_square_area(),
            drive_w=10.0,
            target_spl_db=80.0,
        )


def test_missing_per_channel_spec_raises() -> None:
    # dict spec missing some channels => _spec_for_channel raises.
    specs = {1: _spec(price=10.0)}  # channels 2-8 absent
    with pytest.raises(ValueError, match="no SpeakerSpec for channel"):
        _evaluate(specs)


# --------------------------------------------------------------------------- #
# Cost dataclass direct unit (exact arithmetic, no physics)
# --------------------------------------------------------------------------- #


def test_tradeoff_cost_dataclass_fields() -> None:
    cost = TradeoffCost(total_price=300.0, n_speakers=4, n_priced=4, complete=True)
    assert cost.total_price == 300.0
    assert cost.complete is True
