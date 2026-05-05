"""Step 3 of v0.1.1 closeout — phase_offset_deg / phase_offsets_deg coverage.

These tests cover the new optional kwargs added in v0.1.1:
- ``place_vbap_ring(phase_offset_deg=…)``
- ``place_vbap_dome(phase_offsets_deg=[lower, upper])``

Default values must reproduce v0.1 behaviour byte-for-byte (test #2 below
asserts that against a frozen pre-edit golden fixture).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml

from roomestim.export.layout_yaml import write_layout_yaml
from roomestim.place.vbap import place_vbap_dome, place_vbap_ring


_GOLDEN_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "golden"
    / "place_vbap_ring_n8_default.yaml"
)
_LAB_FIXTURE_PATH = Path(
    "/home/seung/mmhoa/spatial_engine/configs/lab_8ch_aligned.yaml"
)


# --------------------------------------------------------------------------- #
# Test 1 — basic offset
# --------------------------------------------------------------------------- #


def test_place_vbap_ring_phase_offset_basic() -> None:
    """n=4, phase_offset_deg=-135 → first speaker at az=-135°, 90° spacing."""
    result = place_vbap_ring(n=4, radius_m=2.0, el_deg=0.0, phase_offset_deg=-135.0)
    assert len(result.speakers) == 4

    # Compute az from each speaker's listener-frame position to verify.
    expected_az_deg = [-135.0, -45.0, 45.0, 135.0]
    for sp, exp_az in zip(result.speakers, expected_az_deg):
        actual_az_deg = math.degrees(math.atan2(sp.position.x, sp.position.z))
        # tolerate ±1e-9 numeric noise; equal-angle math is exact otherwise.
        assert abs(actual_az_deg - exp_az) < 1e-9, (
            f"channel {sp.channel}: expected az={exp_az}°, got {actual_az_deg}°"
        )


# --------------------------------------------------------------------------- #
# Test 2 — default kwargs are byte-equal to frozen pre-edit golden
# --------------------------------------------------------------------------- #


def test_place_vbap_ring_phase_offset_default_byte_equal_to_golden(
    tmp_path: Path,
) -> None:
    """Default phase_offset_deg=0.0 reproduces v0.1 output byte-for-byte.

    The golden fixture was generated from the pre-edit HEAD (Step 0 of the
    v0.1.1-closeout plan) before the phase_offset_deg parameter existed. Any
    typo in the new default branch (e.g., shifting az by a non-zero constant)
    will fail this assertion.
    """
    out = tmp_path / "place_vbap_ring_n8_default.yaml"
    result = place_vbap_ring(n=8, radius_m=2.0, el_deg=0.0)
    write_layout_yaml(result, out)

    assert _GOLDEN_PATH.is_file(), (
        f"golden fixture missing: {_GOLDEN_PATH} — re-freeze before Step 2 edits"
    )
    assert out.read_bytes() == _GOLDEN_PATH.read_bytes(), (
        "default place_vbap_ring(n=8, radius_m=2.0, el_deg=0.0) output drifted "
        f"from frozen golden {_GOLDEN_PATH}"
    )


# --------------------------------------------------------------------------- #
# Test 3 — phase wraps mod 360°
# --------------------------------------------------------------------------- #


def test_place_vbap_ring_phase_offset_wraps() -> None:
    """phase_offset_deg=720 produces the same listener-frame positions as 0.0."""
    base = place_vbap_ring(n=4, radius_m=2.0, el_deg=0.0, phase_offset_deg=0.0)
    wrapped = place_vbap_ring(n=4, radius_m=2.0, el_deg=0.0, phase_offset_deg=720.0)

    assert len(base.speakers) == len(wrapped.speakers) == 4
    for a, b in zip(base.speakers, wrapped.speakers):
        # 720° = 2 full revolutions — Cartesian positions must coincide to
        # numeric noise (1e-9 m on a 2 m radius).
        assert abs(a.position.x - b.position.x) < 1e-9, (
            f"x mismatch ch{a.channel}: {a.position.x} vs {b.position.x}"
        )
        assert abs(a.position.y - b.position.y) < 1e-9
        assert abs(a.position.z - b.position.z) < 1e-9


# --------------------------------------------------------------------------- #
# Test 4 — dome rings rotate independently
# --------------------------------------------------------------------------- #


def test_place_vbap_dome_phase_offsets_independent() -> None:
    """phase_offsets_deg=[-135, 0] rotates lower ring -135°, upper ring stays."""
    result = place_vbap_dome(
        n_lower=4,
        n_upper=4,
        el_lower_deg=0.0,
        el_upper_deg=30.0,
        radius_m=2.0,
        phase_offsets_deg=[-135.0, 0.0],
    )
    assert len(result.speakers) == 8

    lower = result.speakers[:4]
    upper = result.speakers[4:]

    expected_lower_az = [-135.0, -45.0, 45.0, 135.0]
    for sp, exp_az in zip(lower, expected_lower_az):
        actual_az = math.degrees(math.atan2(sp.position.x, sp.position.z))
        assert abs(actual_az - exp_az) < 1e-9, (
            f"lower ch{sp.channel}: az {actual_az}° != {exp_az}°"
        )

    expected_upper_az = [0.0, 90.0, 180.0, -90.0]  # 0, 90, 180, 270 mod 360
    for sp, exp_az in zip(upper, expected_upper_az):
        actual_az = math.degrees(math.atan2(sp.position.x, sp.position.z))
        # Compare on the unit circle (atan2 wraps to [-180, 180]).
        diff = (actual_az - exp_az + 540.0) % 360.0 - 180.0
        assert abs(diff) < 1e-9, (
            f"upper ch{sp.channel}: az {actual_az}° != {exp_az}° (diff={diff})"
        )


# --------------------------------------------------------------------------- #
# Test 5 — wrong-length phase_offsets_deg raises
# --------------------------------------------------------------------------- #


def test_place_vbap_dome_phase_offsets_wrong_length_raises() -> None:
    """phase_offsets_deg of length != 2 raises ValueError naming kErrTooFewSpeakers."""
    with pytest.raises(ValueError, match=r"kErrTooFewSpeakers.*phase_offsets_deg length 1"):
        place_vbap_dome(
            n_lower=4,
            n_upper=4,
            phase_offsets_deg=[0.0],
        )

    with pytest.raises(ValueError, match=r"kErrTooFewSpeakers.*phase_offsets_deg length 3"):
        place_vbap_dome(
            n_lower=4,
            n_upper=4,
            phase_offsets_deg=[0.0, 0.0, 0.0],
        )


# --------------------------------------------------------------------------- #
# Test 6 — lab_8ch_aligned position-subset match
# --------------------------------------------------------------------------- #


def test_lab_8ch_aligned_position_subset_match(tmp_path: Path) -> None:
    """Generated dome matches lab_8ch_aligned.yaml on the comparable field set.

    EXCLUDED with documented reason:
      - regularity_hint: lab fixture annotates "CIRCULAR" but place_vbap_dome
        emits "IRREGULAR" (vbap.py:9–11 conservative downgrade for stacked
        rings). Both are valid; we don't introduce an override parameter just
        to make this test pass — see Critic B1 resolution in
        .omc/plans/v0.1.1-closeout.md §3 / Step 3 docstring.
      - delay_ms: lab fixture has 10.0ms on channel 1 only — a per-speaker
        test override; LayoutLoader.cpp:84 makes the field optional default 0.
        Not a placement output.
      - x_aim_az_deg / x_aim_el_deg: D5 extension keys roomestim emits but the
        lab fixture pre-dates them.

    INCLUDED: top-level version, name; per-speaker id, channel, az_deg, el_deg,
    dist_m. All compared with 1e-9 absolute tolerance for numeric fields.
    """
    if not _LAB_FIXTURE_PATH.is_file():
        pytest.skip(
            f"lab fixture missing: {_LAB_FIXTURE_PATH} — engine repo not "
            "present in this checkout"
        )

    result = place_vbap_dome(
        n_lower=4,
        n_upper=4,
        el_lower_deg=0.0,
        el_upper_deg=30.0,
        radius_m=1.0,
        phase_offsets_deg=[-135.0, -135.0],
        layout_name="lab_8ch_aligned",
    )
    out = tmp_path / "generated_lab_8ch_aligned.yaml"
    write_layout_yaml(result, out)

    with out.open() as fh:
        gen = yaml.safe_load(fh)
    with _LAB_FIXTURE_PATH.open() as fh:
        lab = yaml.safe_load(fh)

    # Top-level included fields.
    assert gen["version"] == lab["version"], (
        f"version mismatch: gen={gen['version']!r} lab={lab['version']!r}"
    )
    assert gen["name"] == lab["name"], (
        f"name mismatch: gen={gen['name']!r} lab={lab['name']!r}"
    )

    # Per-speaker included fields. Compare in channel order; both lists are
    # 1..8 monotonic by construction.
    assert len(gen["speakers"]) == len(lab["speakers"]) == 8
    for gen_sp, lab_sp in zip(gen["speakers"], lab["speakers"]):
        assert gen_sp["id"] == lab_sp["id"], (
            f"id mismatch: gen={gen_sp['id']} lab={lab_sp['id']}"
        )
        assert gen_sp["channel"] == lab_sp["channel"]
        for key in ("az_deg", "el_deg", "dist_m"):
            assert abs(gen_sp[key] - lab_sp[key]) < 1e-9, (
                f"channel {gen_sp['channel']} {key}: "
                f"gen={gen_sp[key]} lab={lab_sp[key]} "
                f"diff={gen_sp[key] - lab_sp[key]}"
            )
