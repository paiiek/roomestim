"""v0.18 — evolve_placement + nudge_speaker (ADR 0036 §A/§B; D48 + D49).

Frozen-respecting placement edit helpers: the input PlacementResult is never
mutated, speakers list is shallow-copied, spherical Δ XOR Cartesian Δ.
"""

from __future__ import annotations

import math

import pytest

from roomestim.coords import yaml_speaker_to_cartesian
from roomestim.edit import evolve_placement, nudge_speaker
from roomestim.model import PlacedSpeaker, PlacementResult, Point3


def _ring_result(radius_m: float = 2.0) -> PlacementResult:
    """3 speakers on a horizontal ring at azimuths {0, 120, 240}°."""
    speakers: list[PlacedSpeaker] = []
    for i, az_deg in enumerate((0.0, 120.0, 240.0)):
        az = math.radians(az_deg)
        speakers.append(
            PlacedSpeaker(
                channel=i + 1,
                position=Point3(
                    x=radius_m * math.sin(az),
                    y=0.0,
                    z=radius_m * math.cos(az),
                ),
            )
        )
    return PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="CIRCULAR",
        speakers=speakers,
        layout_name="ring",
    )


def test_evolve_placement_returns_new_instance() -> None:
    r = _ring_result()
    r2 = evolve_placement(r, layout_name="renamed")
    assert r2 is not r
    assert r2.layout_name == "renamed"
    assert r.layout_name == "ring"  # original untouched


def test_evolve_placement_speakers_shallow_copy() -> None:
    r = _ring_result()
    r2 = evolve_placement(r)
    assert r2.speakers is not r.speakers
    # mutating the new list does not affect the original
    r2.speakers.append(r2.speakers[0])
    assert len(r.speakers) == 3


def test_nudge_speaker_spherical() -> None:
    r = _ring_result()
    # speaker 0 is at az=0 (front, +z); daz=90 → az=90 (right, +x)
    r2 = nudge_speaker(r, 0, daz_deg=90.0)
    ex, ey, ez = yaml_speaker_to_cartesian(90.0, 0.0, 2.0)
    p = r2.speakers[0].position
    assert p.x == pytest.approx(ex, abs=1e-9)
    assert p.y == pytest.approx(ey, abs=1e-9)
    assert p.z == pytest.approx(ez, abs=1e-9)
    # el boundary case: el=0 + del_deg=89 → finite (no NaN/inf)
    r3 = nudge_speaker(r, 0, del_deg=89.0)
    q = r3.speakers[0].position
    assert math.isfinite(q.x) and math.isfinite(q.y) and math.isfinite(q.z)
    # el=90 exact boundary is physical (zenith) → accepted
    r4 = nudge_speaker(r, 0, del_deg=90.0)
    assert math.isfinite(r4.speakers[0].position.y)


def test_nudge_speaker_el_above_90_raises() -> None:
    r = _ring_result()  # speaker 0 at el=0
    with pytest.raises(ValueError, match="outside \\[-90, 90\\]"):
        nudge_speaker(r, 0, del_deg=91.0)


def test_nudge_speaker_el_below_neg90_raises() -> None:
    r = _ring_result()
    with pytest.raises(ValueError, match="outside \\[-90, 90\\]"):
        nudge_speaker(r, 0, del_deg=-91.0)


def test_nudge_speaker_cartesian_no_el_guard() -> None:
    # Cartesian Δ can place a speaker far above the listener; the implied el
    # is always physical (atan2 ∈ [-90,90]) so no guard fires — large dy OK.
    r = _ring_result()
    r2 = nudge_speaker(r, 0, dz=0.0, dy=100.0)
    p = r2.speakers[0].position
    assert p.y == pytest.approx(100.0, abs=1e-9)  # no rejection


def test_nudge_speaker_cartesian() -> None:
    r = _ring_result()
    before = r.speakers[0].position
    r2 = nudge_speaker(r, 0, dx=0.5)
    after = r2.speakers[0].position
    assert after.x == pytest.approx(before.x + 0.5, abs=1e-12)
    assert after.y == pytest.approx(before.y, abs=1e-12)
    assert after.z == pytest.approx(before.z, abs=1e-12)


def test_nudge_speaker_mixing_raises() -> None:
    r = _ring_result()
    with pytest.raises(ValueError, match="mutually exclusive"):
        nudge_speaker(r, 0, daz_deg=5.0, dx=0.5)


def test_nudge_speaker_dist_nonpositive_raises() -> None:
    r = _ring_result()
    with pytest.raises(ValueError, match="must be > 0"):
        nudge_speaker(r, 0, ddist_m=-10.0)


def test_nudge_speaker_index_out_of_range() -> None:
    r = _ring_result()
    with pytest.raises(IndexError, match="valid range"):
        nudge_speaker(r, 99, daz_deg=5.0)


def test_nudge_speaker_preserves_aim() -> None:
    r = _ring_result()
    aim = Point3(x=0.0, y=0.0, z=-1.0)
    r = evolve_placement(
        r,
        speakers=[
            PlacedSpeaker(channel=s.channel, position=s.position, aim_direction=aim)
            for s in r.speakers
        ],
    )
    r2 = nudge_speaker(r, 0, daz_deg=5.0)
    # nudging position must not drop the aim direction
    assert r2.speakers[0].aim_direction == aim
