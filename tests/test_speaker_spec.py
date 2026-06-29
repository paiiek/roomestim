"""Tests for the SpeakerSpec data model + direct-field SPL engine (P1).

Direct-field only (no reverb / room gain); see SPL_DIRECT_FIELD_NOTE. NOT
web-marked — core / numpy-free path.
"""

from __future__ import annotations

import json
import math

import pytest

from roomestim.model import ListenerArea, PlacedSpeaker, Point2, Point3
from roomestim.reconstruct._disclosure import SPL_DIRECT_FIELD_NOTE
from roomestim.spec.speaker_spec import (
    BUILTIN_SPEAKER_CATALOG,
    SpeakerSpec,
    direct_field_spl_db,
    directivity_atten_db,
    format_spl_field_lines,
    load_speaker_catalog,
    load_speaker_spec,
    spl_field_over_area,
    spl_field_to_dict,
)


def _spec(**kw: object) -> SpeakerSpec:
    base: dict[str, object] = dict(
        model="test",
        sensitivity_db_1w1m=90.0,
        max_spl_db=115.0,
        dispersion_deg=90.0,
    )
    base.update(kw)
    return SpeakerSpec(**base)  # type: ignore[arg-type]


def _square_area(half: float = 1.0, height_m: float = 1.20) -> ListenerArea:
    poly = [Point2(-half, -half), Point2(half, -half), Point2(half, half), Point2(-half, half)]
    return ListenerArea(polygon=poly, centroid=Point2(0.0, 0.0), height_m=height_m)


# --------------------------------------------------------------------------- #
# direct_field_spl_db: distance + power laws
# --------------------------------------------------------------------------- #
def test_distance_doubling_drops_6_02_db() -> None:
    spec = _spec()
    a = direct_field_spl_db(spec, drive_w=1.0, distance_m=1.0)
    b = direct_field_spl_db(spec, drive_w=1.0, distance_m=2.0)
    assert a - b == pytest.approx(6.0206, abs=1e-3)


def test_distance_quadrupling_drops_12_04_db() -> None:
    spec = _spec()
    a = direct_field_spl_db(spec, drive_w=1.0, distance_m=1.0)
    b = direct_field_spl_db(spec, drive_w=1.0, distance_m=4.0)
    assert a - b == pytest.approx(12.0412, abs=1e-3)


def test_10x_drive_power_adds_10_db() -> None:
    spec = _spec()
    a = direct_field_spl_db(spec, drive_w=1.0, distance_m=1.0)
    b = direct_field_spl_db(spec, drive_w=10.0, distance_m=1.0)
    assert b - a == pytest.approx(10.0, abs=1e-9)


def test_sensitivity_is_spl_at_1w_1m_on_axis() -> None:
    spec = _spec(sensitivity_db_1w1m=87.5)
    assert direct_field_spl_db(spec, drive_w=1.0, distance_m=1.0) == pytest.approx(87.5)


def test_direct_field_spl_rejects_nonpositive() -> None:
    spec = _spec()
    with pytest.raises(ValueError):
        direct_field_spl_db(spec, drive_w=0.0, distance_m=1.0)
    with pytest.raises(ValueError):
        direct_field_spl_db(spec, drive_w=-1.0, distance_m=1.0)
    with pytest.raises(ValueError):
        direct_field_spl_db(spec, drive_w=1.0, distance_m=0.0)
    with pytest.raises(ValueError):
        direct_field_spl_db(spec, drive_w=1.0, distance_m=-2.0)


# --------------------------------------------------------------------------- #
# directivity_atten_db
# --------------------------------------------------------------------------- #
def test_directivity_on_axis_is_zero() -> None:
    assert directivity_atten_db(_spec(), 0.0) == pytest.approx(0.0)


def test_directivity_minus_6_at_half_angle() -> None:
    spec = _spec(dispersion_deg=90.0)
    assert directivity_atten_db(spec, 45.0) == pytest.approx(-6.0, abs=1e-9)


def test_directivity_minus_6_at_half_angle_other_dispersion() -> None:
    spec = _spec(dispersion_deg=120.0)
    assert directivity_atten_db(spec, 60.0) == pytest.approx(-6.0, abs=1e-9)


def test_directivity_monotonic_decreasing() -> None:
    spec = _spec(dispersion_deg=90.0)
    prev = 1.0
    for deg in (0.0, 10.0, 20.0, 30.0, 45.0, 60.0, 80.0):
        val = directivity_atten_db(spec, deg)
        assert val <= prev
        prev = val


def test_directivity_floor_clamped() -> None:
    spec = _spec(dispersion_deg=10.0)
    # far off-axis -> would be very negative -> clamped to floor
    assert directivity_atten_db(spec, 179.0) == pytest.approx(-60.0)


# --------------------------------------------------------------------------- #
# Spec validation
# --------------------------------------------------------------------------- #
def test_spec_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        _spec(sensitivity_db_1w1m=math.nan)
    with pytest.raises(ValueError):
        _spec(max_spl_db=math.inf)
    with pytest.raises(ValueError):
        _spec(dispersion_deg=math.nan)


def test_spec_rejects_bad_dispersion() -> None:
    with pytest.raises(ValueError):
        _spec(dispersion_deg=0.0)
    with pytest.raises(ValueError):
        _spec(dispersion_deg=-30.0)
    with pytest.raises(ValueError):
        _spec(dispersion_deg=360.1)


def test_spec_allows_dispersion_360_and_optional_price() -> None:
    s = _spec(dispersion_deg=360.0, price=499.0)
    assert s.dispersion_deg == 360.0
    assert s.price == 499.0


# --------------------------------------------------------------------------- #
# spl_field_over_area
# --------------------------------------------------------------------------- #
def test_spl_field_single_speaker_finite() -> None:
    spec = _spec()
    spk = PlacedSpeaker(channel=0, position=Point3(0.0, 2.5, 0.0))
    area = _square_area(half=1.0)
    score = spl_field_over_area(spec, drive_w=1.0, speakers=[spk], listener_area=area)
    assert score.n_samples >= 1
    assert math.isfinite(score.min_spl_db)
    assert math.isfinite(score.mean_spl_db)
    assert math.isfinite(score.max_spl_db)
    assert score.uniformity_db >= 0.0
    assert score.min_spl_db <= score.mean_spl_db <= score.max_spl_db
    assert score.note == SPL_DIRECT_FIELD_NOTE
    # worst point lies inside the polygon bounds
    wx, wz = score.worst_point_xz
    assert -1.0 <= wx <= 1.0 and -1.0 <= wz <= 1.0


def test_spl_field_two_speakers_raise_min_spl() -> None:
    spec = _spec()
    area = _square_area(half=1.0)
    one = [PlacedSpeaker(channel=0, position=Point3(0.0, 2.5, 0.0))]
    two = [
        PlacedSpeaker(channel=0, position=Point3(0.0, 2.5, 0.0)),
        PlacedSpeaker(channel=1, position=Point3(0.0, 2.5, 0.0)),
    ]
    s1 = spl_field_over_area(spec, drive_w=1.0, speakers=one, listener_area=area)
    s2 = spl_field_over_area(spec, drive_w=1.0, speakers=two, listener_area=area)
    # energy sum of two identical sources adds ~3 dB everywhere
    assert s2.min_spl_db > s1.min_spl_db
    assert s2.min_spl_db - s1.min_spl_db == pytest.approx(10.0 * math.log10(2.0), abs=1e-6)


def test_spl_field_per_channel_specs() -> None:
    area = _square_area(half=1.0)
    specs = {0: _spec(sensitivity_db_1w1m=90.0), 1: _spec(sensitivity_db_1w1m=80.0)}
    spks = [
        PlacedSpeaker(channel=0, position=Point3(0.0, 2.5, 0.0)),
        PlacedSpeaker(channel=1, position=Point3(0.0, 2.5, 0.0)),
    ]
    score = spl_field_over_area(specs, drive_w=1.0, speakers=spks, listener_area=area)
    assert math.isfinite(score.mean_spl_db)


def test_spl_field_missing_channel_spec_raises() -> None:
    area = _square_area()
    specs = {0: _spec()}
    spks = [PlacedSpeaker(channel=5, position=Point3(0.0, 2.5, 0.0))]
    with pytest.raises(ValueError):
        spl_field_over_area(specs, drive_w=1.0, speakers=spks, listener_area=area)


def test_spl_field_guards() -> None:
    spec = _spec()
    area = _square_area()
    spk = PlacedSpeaker(channel=0, position=Point3(0.0, 2.5, 0.0))
    with pytest.raises(ValueError):
        spl_field_over_area(spec, drive_w=1.0, speakers=[], listener_area=area)
    with pytest.raises(ValueError):
        spl_field_over_area(spec, drive_w=0.0, speakers=[spk], listener_area=area)
    with pytest.raises(ValueError):
        spl_field_over_area(spec, drive_w=1.0, speakers=[spk], listener_area=area, grid_resolution_m=0.0)
    bad_area = ListenerArea(
        polygon=[Point2(0.0, 0.0), Point2(1.0, 0.0)], centroid=Point2(0.0, 0.0)
    )
    with pytest.raises(ValueError):
        spl_field_over_area(spec, drive_w=1.0, speakers=[spk], listener_area=bad_area)


def test_spl_field_to_dict_and_lines() -> None:
    spec = _spec()
    spk = PlacedSpeaker(channel=0, position=Point3(0.0, 2.5, 0.0))
    area = _square_area()
    score = spl_field_over_area(spec, drive_w=1.0, speakers=[spk], listener_area=area)
    d = spl_field_to_dict(score)
    assert list(d)[0] == "note"
    assert d["note"] == SPL_DIRECT_FIELD_NOTE
    lines = format_spl_field_lines(score)
    assert any("direct-field" in ln.lower() for ln in lines)


# --------------------------------------------------------------------------- #
# Round-trip load + catalog honesty
# --------------------------------------------------------------------------- #
def test_load_speaker_spec_roundtrip_yaml(tmp_path) -> None:  # type: ignore[no-untyped-def]
    src = _spec(model="real_box", sensitivity_db_1w1m=92.5, max_spl_db=121.0, dispersion_deg=100.0)
    p = tmp_path / "spec.yaml"
    p.write_text(
        "model: real_box\n"
        "sensitivity_db_1w1m: 92.5\n"
        "max_spl_db: 121.0\n"
        "dispersion_deg: 100.0\n",
        encoding="utf-8",
    )
    loaded = load_speaker_spec(p)
    assert loaded.model == src.model
    assert loaded.sensitivity_db_1w1m == src.sensitivity_db_1w1m
    assert loaded.max_spl_db == src.max_spl_db
    assert loaded.dispersion_deg == src.dispersion_deg
    # loaded specs default to datasheet provenance
    assert loaded.provenance == "datasheet"


def test_load_speaker_spec_roundtrip_json(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "spec.json"
    p.write_text(
        json.dumps(
            {
                "model": "real_json",
                "sensitivity_db_1w1m": 88.0,
                "max_spl_db": 110.0,
                "dispersion_deg": 80.0,
                "price": 250.0,
            }
        ),
        encoding="utf-8",
    )
    loaded = load_speaker_spec(p)
    assert loaded.model == "real_json"
    assert loaded.provenance == "datasheet"
    assert loaded.price == 250.0


def test_load_speaker_spec_respects_explicit_provenance(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "spec.yaml"
    p.write_text(
        "model: guess\nsensitivity_db_1w1m: 85.0\nmax_spl_db: 100.0\n"
        "dispersion_deg: 90.0\nprovenance: estimate\n",
        encoding="utf-8",
    )
    assert load_speaker_spec(p).provenance == "estimate"


def test_builtin_catalog_all_estimates_and_valid() -> None:
    assert BUILTIN_SPEAKER_CATALOG
    for key, spec in BUILTIN_SPEAKER_CATALOG.items():
        assert spec.provenance == "estimate"
        assert spec.model == key
        assert math.isfinite(spec.sensitivity_db_1w1m)
        assert math.isfinite(spec.max_spl_db)
        assert 0.0 < spec.dispersion_deg <= 360.0


# --------------------------------------------------------------------------- #
# Off-axis geometry: aim_direction actually steers the field
# --------------------------------------------------------------------------- #
def test_spl_field_aim_direction_steers_and_is_symmetric() -> None:
    spec = _spec(dispersion_deg=90.0)
    h = 1.20
    # Speaker at ear height aimed along +x.
    spk = PlacedSpeaker(
        channel=0, position=Point3(0.0, h, 0.0), aim_direction=Point3(1.0, 0.0, 0.0)
    )
    # Narrow strip at x≈2.0 whose grid yields exactly TWO samples at z=±0.25,
    # symmetric about the +x aim axis (single x column at x=2.0).
    poly = [Point2(1.9, -0.5), Point2(2.1, -0.5), Point2(2.1, 0.5), Point2(1.9, 0.5)]
    area = ListenerArea(polygon=poly, centroid=Point2(2.0, 0.0), height_m=h)
    score = spl_field_over_area(spec, drive_w=1.0, speakers=[spk], listener_area=area)
    assert score.n_samples == 2
    # Symmetric about the aim axis -> identical SPL -> zero spread (proves the
    # off-axis angle, hence aim_direction, is applied symmetrically).
    assert score.uniformity_db == pytest.approx(0.0, abs=1e-9)
    assert score.min_spl_db == pytest.approx(score.max_spl_db, abs=1e-9)
    # Both off-axis samples are quieter than a hypothetical on-axis listener at
    # the same x (z=0) -> the directivity actually rolls off off-axis.
    on_axis = direct_field_spl_db(spec, drive_w=1.0, distance_m=2.0, off_axis_deg=0.0)
    assert score.max_spl_db <= on_axis + 1e-9


def test_spl_field_aim_away_is_quieter_than_aim_toward() -> None:
    spec = _spec(dispersion_deg=90.0)
    h = 1.20
    area = _square_area(half=1.0, height_m=h)
    # Same geometry, opposite aim: toward the area (-? centroid at origin) vs away.
    pos = Point3(0.0, 2.5, 3.0)
    toward = [PlacedSpeaker(channel=0, position=pos, aim_direction=Point3(0.0, -1.0, -1.0))]
    away = [PlacedSpeaker(channel=0, position=pos, aim_direction=Point3(0.0, 1.0, 1.0))]
    s_toward = spl_field_over_area(spec, drive_w=1.0, speakers=toward, listener_area=area)
    s_away = spl_field_over_area(spec, drive_w=1.0, speakers=away, listener_area=area)
    assert s_toward.max_spl_db > s_away.max_spl_db


# --------------------------------------------------------------------------- #
# exceeds_max_spl flag (over-claim made visible)
# --------------------------------------------------------------------------- #
def test_exceeds_max_spl_flag_and_dict_and_lines() -> None:
    # Tiny max_spl_db rating + high drive -> predicted SPL exceeds the rating.
    spec = _spec(max_spl_db=80.0)
    spk = PlacedSpeaker(channel=0, position=Point3(0.0, 1.30, 0.0))
    area = _square_area(half=1.0)
    score = spl_field_over_area(spec, drive_w=100.0, speakers=[spk], listener_area=area)
    assert score.exceeds_max_spl is True
    d = spl_field_to_dict(score)
    assert d["exceeds_max_spl"] is True
    assert any("exceeds" in ln.lower() for ln in format_spl_field_lines(score))
    # A generous rating is not exceeded.
    spec2 = _spec(max_spl_db=140.0)
    score2 = spl_field_over_area(spec2, drive_w=1.0, speakers=[spk], listener_area=area)
    assert score2.exceeds_max_spl is False
    assert spl_field_to_dict(score2)["exceeds_max_spl"] is False


def test_exceeds_max_spl_uses_smallest_contributing_rating() -> None:
    area = _square_area(half=1.0)
    # Channel 1 has a tiny rating -> the min over contributing specs governs.
    specs = {0: _spec(max_spl_db=140.0), 1: _spec(max_spl_db=70.0)}
    spks = [
        PlacedSpeaker(channel=0, position=Point3(0.0, 1.30, 0.0)),
        PlacedSpeaker(channel=1, position=Point3(0.0, 1.30, 0.0)),
    ]
    score = spl_field_over_area(specs, drive_w=1.0, speakers=spks, listener_area=area)
    assert score.exceeds_max_spl is True


# --------------------------------------------------------------------------- #
# NaN aim_direction must raise, NOT collapse to fake on-axis
# --------------------------------------------------------------------------- #
def test_spl_field_nonfinite_aim_raises() -> None:
    spec = _spec()
    area = _square_area(half=1.0)
    nan_spk = [
        PlacedSpeaker(
            channel=0, position=Point3(0.0, 2.5, 0.0),
            aim_direction=Point3(math.nan, 0.0, 0.0),
        )
    ]
    with pytest.raises(ValueError):
        spl_field_over_area(spec, drive_w=1.0, speakers=nan_spk, listener_area=area)
    inf_spk = [
        PlacedSpeaker(
            channel=0, position=Point3(0.0, 2.5, 0.0),
            aim_direction=Point3(0.0, math.inf, 0.0),
        )
    ]
    with pytest.raises(ValueError):
        spl_field_over_area(spec, drive_w=1.0, speakers=inf_spk, listener_area=area)


# --------------------------------------------------------------------------- #
# load_speaker_catalog round-trip (dict + list forms) + empty -> error
# --------------------------------------------------------------------------- #
def test_load_speaker_catalog_dict_form(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "catalog.yaml"
    p.write_text(
        "box_a:\n"
        "  model: box_a\n"
        "  sensitivity_db_1w1m: 90.0\n"
        "  max_spl_db: 118.0\n"
        "  dispersion_deg: 90.0\n"
        "box_b:\n"
        "  model: box_b\n"
        "  sensitivity_db_1w1m: 95.0\n"
        "  max_spl_db: 124.0\n"
        "  dispersion_deg: 75.0\n",
        encoding="utf-8",
    )
    cat = load_speaker_catalog(p)
    assert set(cat) == {"box_a", "box_b"}
    assert cat["box_a"].sensitivity_db_1w1m == 90.0
    assert cat["box_b"].dispersion_deg == 75.0
    assert cat["box_a"].provenance == "datasheet"


def test_load_speaker_catalog_list_form(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "catalog.json"
    p.write_text(
        json.dumps(
            [
                {"model": "box_a", "sensitivity_db_1w1m": 90.0, "max_spl_db": 118.0, "dispersion_deg": 90.0},
                {"model": "box_b", "sensitivity_db_1w1m": 95.0, "max_spl_db": 124.0, "dispersion_deg": 75.0},
            ]
        ),
        encoding="utf-8",
    )
    cat = load_speaker_catalog(p)
    assert set(cat) == {"box_a", "box_b"}  # keyed by each spec's model
    assert cat["box_b"].max_spl_db == 124.0


def test_load_speaker_catalog_empty_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "empty.yaml"
    p.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_speaker_catalog(p)


# --------------------------------------------------------------------------- #
# Loader error paths
# --------------------------------------------------------------------------- #
def test_load_speaker_spec_malformed_file_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_speaker_spec(p)


def test_load_speaker_spec_missing_required_field_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "spec.yaml"
    p.write_text("model: x\nsensitivity_db_1w1m: 90.0\nmax_spl_db: 110.0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_speaker_spec(p)  # dispersion_deg missing


def test_load_speaker_spec_bad_provenance_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "spec.yaml"
    p.write_text(
        "model: x\nsensitivity_db_1w1m: 90.0\nmax_spl_db: 110.0\n"
        "dispersion_deg: 90.0\nprovenance: guessed\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_speaker_spec(p)


def test_load_speaker_spec_malformed_price_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "spec.yaml"
    p.write_text(
        "model: x\nsensitivity_db_1w1m: 90.0\nmax_spl_db: 110.0\n"
        "dispersion_deg: 90.0\nprice: not_a_number\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_speaker_spec(p)
