"""Tests for roomestim_web.report — acoustic report builder (P13d)."""

from __future__ import annotations

import pytest

pytest.importorskip("plotly")

from roomestim.adapters.polycam import PolycamAdapter
from roomestim_web.report import build_acoustic_report


@pytest.fixture
def fixture_room() -> object:
    return PolycamAdapter().parse(
        "tests/fixtures/lab_room.obj", scale_anchor=None, octave_band=False
    )


@pytest.mark.web
def test_rt60_sabine_500hz_known_room(fixture_room: object) -> None:
    """For lab_room.obj fixture, Sabine-500Hz is a positive finite float."""
    report = build_acoustic_report(fixture_room)  # type: ignore[arg-type]
    assert report.sabine_rt60_500hz_s > 0.0
    assert report.sabine_rt60_500hz_s < 5.0


@pytest.mark.web
def test_rt60_octave_band_returns_6_values(fixture_room: object) -> None:
    report = build_acoustic_report(fixture_room)  # type: ignore[arg-type]
    assert len(report.sabine_rt60_per_band_s) == 6
    assert set(report.sabine_rt60_per_band_s.keys()) == {125, 250, 500, 1000, 2000, 4000}
    assert len(report.eyring_rt60_per_band_s) == 6


@pytest.mark.web
def test_eyring_lessthan_or_equal_sabine(fixture_room: object) -> None:
    """ADR 0009 D9 runtime invariant: Eyring ≤ Sabine for the same room."""
    report = build_acoustic_report(fixture_room)  # type: ignore[arg-type]
    assert report.eyring_rt60_500hz_s <= report.sabine_rt60_500hz_s + 1e-9
    for band in (125, 250, 500, 1000, 2000, 4000):
        assert (
            report.eyring_rt60_per_band_s[band]
            <= report.sabine_rt60_per_band_s[band] + 1e-9
        )


@pytest.mark.web
def test_report_geom_helpers_imported_from_core() -> None:
    """ADR 0029 §Cross-lane-geom-amendment regression lock (v0.15.2).

    Verifies that the three private geometry helpers were removed from
    roomestim_web.report and that polygon_area_3d / room_volume are now
    sourced directly from roomestim.geom.polygon (identity check).
    Fails if anyone re-introduces the duplicates.
    """
    import roomestim_web.report as wr
    from roomestim.geom.polygon import polygon_area_3d, room_volume

    assert not hasattr(wr, "_polygon_area_3d"), (
        "_polygon_area_3d duplicate must not exist in roomestim_web.report"
    )
    assert not hasattr(wr, "_shoelace_2d"), (
        "_shoelace_2d duplicate must not exist in roomestim_web.report"
    )
    assert not hasattr(wr, "_room_volume"), (
        "_room_volume duplicate must not exist in roomestim_web.report"
    )
    assert wr.polygon_area_3d is polygon_area_3d, (
        "roomestim_web.report.polygon_area_3d must be the same object as "
        "roomestim.geom.polygon.polygon_area_3d (import identity)"
    )
    assert wr.room_volume is room_volume, (
        "roomestim_web.report.room_volume must be the same object as "
        "roomestim.geom.polygon.room_volume (import identity)"
    )
