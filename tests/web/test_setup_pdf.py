"""Tests for roomestim_web.setup_pdf — speaker setup card PDF (P13d)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytest.importorskip("reportlab")

from roomestim.adapters.polycam import PolycamAdapter
from roomestim.place.dispatch import run_placement
from roomestim_web.setup_pdf import build_setup_pdf


@pytest.fixture
def fixture_room_and_layout() -> tuple[object, object]:
    room = PolycamAdapter().parse(
        "tests/fixtures/lab_room.obj", scale_anchor=None, octave_band=False
    )
    layout = run_placement(room, "vbap", 8, 2.0, 0.0)
    return room, layout


@pytest.mark.web
def test_setup_pdf_generates_valid_pdf(fixture_room_and_layout: tuple[object, object]) -> None:
    room, layout = fixture_room_and_layout
    with tempfile.TemporaryDirectory() as tmp:
        out = build_setup_pdf(layout, room, Path(tmp) / "setup.pdf")
        assert out.exists()
        head = out.read_bytes()[:4]
        assert head == b"%PDF"


@pytest.mark.web
def test_setup_pdf_one_page_per_speaker(fixture_room_and_layout: tuple[object, object]) -> None:
    room, layout = fixture_room_and_layout
    with tempfile.TemporaryDirectory() as tmp:
        out = build_setup_pdf(layout, room, Path(tmp) / "setup.pdf")
        text = out.read_bytes()
        page_count = (
            text.count(b"/Type /Page\n")
            + text.count(b"/Type /Page ")
            + text.count(b"/Type/Page")
        )
        assert page_count == len(layout.speakers)


@pytest.mark.web
@pytest.mark.parametrize(
    "algorithm,n",
    [("vbap", 4), ("vbap", 8), ("vbap", 16), ("dbap", 8)],
)
def test_setup_pdf_no_exception_on_typical_layouts(
    fixture_room_and_layout: tuple[object, object],
    algorithm: str,
    n: int,
) -> None:
    room, _ = fixture_room_and_layout
    layout = run_placement(room, algorithm, n, 2.0, 0.0)
    with tempfile.TemporaryDirectory() as tmp:
        build_setup_pdf(layout, room, Path(tmp) / f"setup_{algorithm}_{n}.pdf")


@pytest.mark.web
def test_setup_pdf_wfs_with_valid_spacing(
    fixture_room_and_layout: tuple[object, object],
) -> None:
    """WFS layout exercises PDF generation; n=200 keeps spacing below aliasing bound."""
    room, _ = fixture_room_and_layout
    layout = run_placement(room, "wfs", 200, 2.0, 0.0)
    with tempfile.TemporaryDirectory() as tmp:
        build_setup_pdf(layout, room, Path(tmp) / "setup_wfs_200.pdf")
