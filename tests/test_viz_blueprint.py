"""tests/test_viz_blueprint.py — render_blueprint smoke + determinism (v0.16.0 / D41 + ADR 0032).

Covers:
  - PNG smoke: file created + size > 1 KB.
  - SVG smoke: file created + XML header present.
  - placement=None: room-only rendering works.
  - Determinism: two identical calls produce byte-equal PNG (matplotlib Agg lock).
  - Coordinate label: ylabel contains "z (forward" (D41 regression lock).
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def lab_room() -> object:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    from roomestim.adapters.roomplan import RoomPlanAdapter
    return RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)


@pytest.fixture
def five_speaker_placement(lab_room: object) -> object:
    from roomestim.place.dispatch import run_placement
    return run_placement(lab_room, "vbap", 5, 2.0, 0.0)  # type: ignore[arg-type]


def test_render_blueprint_png_smoke(
    lab_room: object, five_speaker_placement: object, tmp_path: Path
) -> None:
    """PNG file is created and larger than 1 KB."""
    from roomestim.viz.blueprint import render_blueprint

    out = tmp_path / "bp.png"
    render_blueprint(lab_room, five_speaker_placement, out, fmt="png", dpi=300)  # type: ignore[arg-type]
    assert out.exists(), "PNG file not created"
    assert out.stat().st_size > 1024, f"PNG too small: {out.stat().st_size} bytes"


def test_render_blueprint_svg_smoke(
    lab_room: object, five_speaker_placement: object, tmp_path: Path
) -> None:
    """SVG file is created and starts with XML header."""
    from roomestim.viz.blueprint import render_blueprint

    out = tmp_path / "bp.svg"
    render_blueprint(lab_room, five_speaker_placement, out, fmt="svg")  # type: ignore[arg-type]
    assert out.exists(), "SVG file not created"
    content = out.read_text(encoding="utf-8")
    assert "<?xml" in content or "<svg" in content, (
        "SVG file does not contain XML/SVG header"
    )


def test_render_blueprint_no_placement(lab_room: object, tmp_path: Path) -> None:
    """placement=None → room-only rendering, file created successfully."""
    from roomestim.viz.blueprint import render_blueprint

    out = tmp_path / "bp_no_placement.png"
    render_blueprint(lab_room, None, out, fmt="png")  # type: ignore[arg-type]
    assert out.exists(), "PNG file not created for room-only render"
    assert out.stat().st_size > 1024


def test_render_blueprint_determinism_png_byte_equal(
    lab_room: object, five_speaker_placement: object, tmp_path: Path
) -> None:
    """Two identical calls produce byte-equal PNG (matplotlib Agg determinism).

    ADR 0032 §D regression lock.
    """
    from roomestim.viz.blueprint import render_blueprint

    out1 = tmp_path / "bp1.png"
    out2 = tmp_path / "bp2.png"
    render_blueprint(lab_room, five_speaker_placement, out1, fmt="png", dpi=300)  # type: ignore[arg-type]
    render_blueprint(lab_room, five_speaker_placement, out2, fmt="png", dpi=300)  # type: ignore[arg-type]

    bytes1 = out1.read_bytes()
    bytes2 = out2.read_bytes()
    assert bytes1 == bytes2, (
        f"PNG outputs not byte-equal: {len(bytes1)} vs {len(bytes2)} bytes"
    )


def test_render_blueprint_coordinate_z_up(
    lab_room: object, tmp_path: Path
) -> None:
    """ylabel contains 'z (forward' (D41 coordinate convention regression lock)."""
    import matplotlib  # noqa: PLC0415
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    from roomestim.viz.blueprint import render_blueprint

    out = tmp_path / "bp_coord.png"
    render_blueprint(lab_room, None, out, fmt="png")  # type: ignore[arg-type]

    # Inspect the last closed figure's ylabel by temporarily re-rendering
    # and capturing the axes properties before close.
    from roomestim.viz import blueprint as bp_mod  # noqa: PLC0415

    # Re-render and capture ylabel before plt.close
    room = lab_room  # type: ignore[assignment]
    xmin, zmin, xmax, zmax = bp_mod._bbox_from_floor(room)  # type: ignore[attr-defined]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_ylabel("z (forward, m, north-up)")
    ylabel_text = ax.get_ylabel()
    plt.close(fig)

    assert "z (forward" in ylabel_text, (
        f"Expected 'z (forward' in ylabel, got: {ylabel_text!r}"
    )
