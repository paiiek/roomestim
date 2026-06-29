"""Tests for the immersive-layout angular-quality metrics (P2).

Pure geometry (geodesic angles between speaker direction unit vectors) => default
gate, no torch / web deps. These lock the geometric invariants: an equal-angle
ring is perfectly uniform with no too-close pairs, a clustered layout is
non-uniform and flags its tight pair, dome elevation is NOT ignored, degenerate
inputs raise, and the honesty note disclaims any acoustic claim.
"""

from __future__ import annotations

import json
import math

import pytest

from roomestim.model import PlacedSpeaker, Point3
from roomestim.place.immersive_quality import (
    IMMERSIVE_QUALITY_NOTE,
    AngularUniformityScore,
    InterferenceScore,
    angular_uniformity,
    angular_uniformity_to_dict,
    format_angular_uniformity_lines,
    format_interference_lines,
    interference_proxy,
    interference_to_dict,
)
from roomestim.place.vbap import place_vbap_dome, place_vbap_ring


def _spk(channel: int, x: float, y: float, z: float) -> PlacedSpeaker:
    return PlacedSpeaker(channel=channel, position=Point3(x=x, y=y, z=z))


# --------------------------------------------------------------------------- #
# Equal-angle ring: perfectly uniform, no too-close pairs
# --------------------------------------------------------------------------- #


def test_equal_angle_ring_is_perfectly_uniform() -> None:
    ring = place_vbap_ring(8, radius_m=2.0)
    score = angular_uniformity(ring.speakers)
    assert score.n_speakers == 8
    # 8 equal-angle speakers on the horizontal great circle => every
    # nearest-neighbour gap is 360/8 = 45 deg.
    assert score.min_nn_gap_deg == pytest.approx(45.0, abs=1e-6)
    assert score.max_nn_gap_deg == pytest.approx(45.0, abs=1e-6)
    assert score.mean_nn_gap_deg == pytest.approx(45.0, abs=1e-6)
    assert score.uniformity == pytest.approx(1.0, abs=1e-9)


def test_equal_angle_ring_no_close_pairs_at_10deg() -> None:
    ring = place_vbap_ring(8, radius_m=2.0)
    score = interference_proxy(ring.speakers)  # default 10 deg
    assert score.n_close_pairs == 0
    assert score.close_pairs == []
    assert not score.close_pairs_truncated
    assert score.min_pair_separation_deg == pytest.approx(45.0, abs=1e-6)


# --------------------------------------------------------------------------- #
# Irregular layout: one tight cluster
# --------------------------------------------------------------------------- #


def test_irregular_layout_is_non_uniform_and_flags_cluster() -> None:
    # Three well-separated directions plus channel 4 placed 5 deg from channel 3
    # in the horizontal plane => a tight 3&4 cluster.
    speakers = [
        _spk(1, 0.0, 0.0, 2.0),    # front  (az 0)
        _spk(2, 2.0, 0.0, 0.0),    # right  (az 90)
        _spk(3, 0.0, 0.0, -2.0),   # back   (az 180)
        _spk(4, 2.0 * math.sin(math.radians(185.0)), 0.0,
             2.0 * math.cos(math.radians(185.0))),  # az 185 -> 5 deg from ch3
    ]
    uni = angular_uniformity(speakers)
    assert uni.uniformity < 1.0
    # The tightest pair is the 3&4 cluster (5 deg apart).
    assert uni.worst_pair == (3, 4)
    assert uni.min_nn_gap_deg == pytest.approx(5.0, abs=1e-6)

    inter = interference_proxy(speakers, min_separation_deg=10.0)
    assert inter.n_close_pairs >= 1
    assert (3, 4) in inter.close_pairs
    assert inter.min_pair_separation_deg == pytest.approx(5.0, abs=1e-6)


# --------------------------------------------------------------------------- #
# Dome: elevation is NOT ignored (geodesic, not azimuth-only)
# --------------------------------------------------------------------------- #


def test_dome_metrics_are_finite() -> None:
    dome = place_vbap_dome(n_lower=6, n_upper=4, radius_m=2.0)
    uni = angular_uniformity(dome.speakers)
    inter = interference_proxy(dome.speakers)
    assert uni.n_speakers == 10
    assert math.isfinite(uni.uniformity)
    assert 0.0 <= uni.uniformity <= 1.0
    assert math.isfinite(inter.min_pair_separation_deg)


def test_elevation_not_ignored_same_azimuth_different_elevation() -> None:
    # Two speakers at the SAME azimuth (front) but different elevation: an
    # azimuth-only metric would call this 0 deg; the geodesic angle must be > 0.
    el_deg = 30.0
    low = _spk(1, 0.0, 0.0, 2.0)  # az 0, el 0
    high = _spk(
        2,
        0.0,
        2.0 * math.sin(math.radians(el_deg)),
        2.0 * math.cos(math.radians(el_deg)),
    )  # az 0, el 30
    score = angular_uniformity([low, high])
    assert score.min_nn_gap_deg == pytest.approx(30.0, abs=1e-6)
    assert score.min_nn_gap_deg > 0.0


# --------------------------------------------------------------------------- #
# Geodesic-angle correctness
# --------------------------------------------------------------------------- #


def test_geodesic_90_degrees() -> None:
    front = _spk(1, 0.0, 0.0, 2.0)
    right = _spk(2, 2.0, 0.0, 0.0)
    score = angular_uniformity([front, right])
    assert score.min_nn_gap_deg == pytest.approx(90.0, abs=1e-6)
    assert score.max_nn_gap_deg == pytest.approx(90.0, abs=1e-6)


def test_geodesic_identical_directions_zero() -> None:
    # Same direction, different radius => 0 deg geodesic gap.
    a = _spk(1, 0.0, 0.0, 2.0)
    b = _spk(2, 0.0, 0.0, 5.0)
    score = angular_uniformity([a, b])
    assert score.min_nn_gap_deg == pytest.approx(0.0, abs=1e-9)
    # max_gap is 0 => degenerate; uniformity reports 1.0 rather than 0/0.
    assert score.uniformity == pytest.approx(1.0)


def test_geodesic_antipodal_directions_180() -> None:
    # Exactly opposite directions => 180 deg geodesic gap (pins the clamp(-1)
    # lower bound; complements the 0 deg / 90 deg cases).
    front = _spk(1, 0.0, 0.0, 2.0)
    back = _spk(2, 0.0, 0.0, -2.0)
    score = angular_uniformity([front, back])
    assert score.min_nn_gap_deg == pytest.approx(180.0, abs=1e-6)
    assert score.max_nn_gap_deg == pytest.approx(180.0, abs=1e-6)


# --------------------------------------------------------------------------- #
# Degenerate inputs raise
# --------------------------------------------------------------------------- #


def test_fewer_than_two_speakers_raises() -> None:
    with pytest.raises(ValueError):
        angular_uniformity([_spk(1, 0.0, 0.0, 2.0)])
    with pytest.raises(ValueError):
        interference_proxy([_spk(1, 0.0, 0.0, 2.0)])


def test_speaker_at_origin_raises() -> None:
    speakers = [_spk(1, 0.0, 0.0, 0.0), _spk(2, 2.0, 0.0, 0.0)]
    with pytest.raises(ValueError):
        angular_uniformity(speakers)
    with pytest.raises(ValueError):
        interference_proxy(speakers)


def test_nonpositive_threshold_raises() -> None:
    ring = place_vbap_ring(4, radius_m=2.0)
    with pytest.raises(ValueError):
        interference_proxy(ring.speakers, min_separation_deg=0.0)


def test_nonfinite_position_raises() -> None:
    # A NaN / inf position component must raise (locks the assert_finite branch
    # in _direction_unit_vector), not silently produce a bogus direction.
    nan_spk = [_spk(1, float("nan"), 0.0, 2.0), _spk(2, 2.0, 0.0, 0.0)]
    with pytest.raises(ValueError):
        angular_uniformity(nan_spk)
    inf_spk = [_spk(1, float("inf"), 0.0, 2.0), _spk(2, 2.0, 0.0, 0.0)]
    with pytest.raises(ValueError):
        angular_uniformity(inf_spk)


# --------------------------------------------------------------------------- #
# Close-pairs truncation invariant: exact count preserved, list capped, flagged
# --------------------------------------------------------------------------- #


def test_close_pairs_truncation_preserves_exact_count_and_flags() -> None:
    # 8 speakers spread over a 7 deg arc in the horizontal plane => every
    # pairwise separation is <= 7 deg < the 10 deg threshold, so all
    # C(8, 2) = 28 pairs are close — more than the MAX_REPORTED_CLOSE_PAIRS=20
    # cap. The exact count must be preserved, the list capped, the flag set.
    from roomestim.place.immersive_quality import MAX_REPORTED_CLOSE_PAIRS

    speakers = [
        _spk(
            ch,
            2.0 * math.sin(math.radians(float(ch))),
            0.0,
            2.0 * math.cos(math.radians(float(ch))),
        )
        for ch in range(8)
    ]
    score = interference_proxy(speakers, min_separation_deg=10.0)
    assert score.n_close_pairs == 28  # exact FULL count, not capped
    assert len(score.close_pairs) == MAX_REPORTED_CLOSE_PAIRS == 20  # list capped
    assert score.close_pairs_truncated is True


# --------------------------------------------------------------------------- #
# Plumbing: to_dict round-trips, format_* nonempty, honesty note
# --------------------------------------------------------------------------- #


def test_angular_uniformity_to_dict_round_trips() -> None:
    ring = place_vbap_ring(6, radius_m=2.0)
    score = angular_uniformity(ring.speakers)
    d = angular_uniformity_to_dict(score)
    assert list(d)[0] == "note"  # note first
    assert d["note"] == IMMERSIVE_QUALITY_NOTE
    restored = json.loads(json.dumps(d))  # JSON-serialisable round-trip
    assert restored["n_speakers"] == 6
    assert restored["worst_pair"] == [score.worst_pair[0], score.worst_pair[1]]


def test_interference_to_dict_round_trips() -> None:
    ring = place_vbap_ring(6, radius_m=2.0)
    score = interference_proxy(ring.speakers)
    d = interference_to_dict(score)
    assert list(d)[0] == "note"
    assert d["note"] == IMMERSIVE_QUALITY_NOTE
    restored = json.loads(json.dumps(d))
    assert restored["n_close_pairs"] == score.n_close_pairs
    assert restored["close_pairs_truncated"] is False


def test_format_lines_nonempty() -> None:
    ring = place_vbap_ring(8, radius_m=2.0)
    uni = angular_uniformity(ring.speakers)
    inter = interference_proxy(ring.speakers)
    uni_lines = format_angular_uniformity_lines(uni)
    inter_lines = format_interference_lines(inter)
    assert uni_lines and all(isinstance(s, str) and s for s in uni_lines)
    assert inter_lines and all(isinstance(s, str) and s for s in inter_lines)


def test_note_is_honest_and_geometric() -> None:
    assert "GEOMETRIC" in IMMERSIVE_QUALITY_NOTE
    assert "NOT" in IMMERSIVE_QUALITY_NOTE
    assert "GEODESIC" in IMMERSIVE_QUALITY_NOTE


def test_score_types() -> None:
    ring = place_vbap_ring(4, radius_m=2.0)
    assert isinstance(angular_uniformity(ring.speakers), AngularUniformityScore)
    assert isinstance(interference_proxy(ring.speakers), InterferenceScore)
