"""tests/web/test_immersive_algorithms_ui.py — UI exposure of dome/coverage,
higher speaker counts, and the one-click example-room loader (v0.60.0).

Asserts ``build_demo()`` exposes the new algorithm choices (dome, coverage) and
the higher speaker counts, that the "예시 룸 불러오기" button is present, and that
``_on_load_example`` populates the layout_state through the real pipeline.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("gradio")

import gradio as gr  # noqa: E402

from roomestim_web.app import (  # noqa: E402
    _EXAMPLE_ROOM_PATH,
    _on_algorithm_change,
    _on_load_example,
    build_demo,
)


def _upd_field(update: object, key: str) -> object:
    """Read a field from a gr.update result (dict-like or object) robustly."""
    if isinstance(update, dict):
        return update.get(key)
    return getattr(update, key, None)


def _build() -> gr.Blocks:
    with patch("roomestim_web.app._ensure_web_data", return_value=False):
        with patch("roomestim_web.app._binaural_data_present", return_value=True):
            return build_demo()


def _radio_choice_values(demo: gr.Blocks) -> list[list[str]]:
    """Collect the value-side of every gr.Radio's choices in the built app."""
    out: list[list[str]] = []
    for comp in demo.blocks.values():
        if isinstance(comp, gr.Radio):
            vals: list[str] = []
            for ch in comp.choices:
                # gradio normalises choices to (label, value) tuples.
                vals.append(str(ch[1]) if isinstance(ch, tuple) else str(ch))
            out.append(vals)
    return out


@pytest.mark.web
def test_algorithm_radio_exposes_dome_and_coverage() -> None:
    demo = _build()
    radios = _radio_choice_values(demo)
    algo = next((r for r in radios if "vbap" in r), None)
    assert algo is not None, "algorithm Radio not found"
    assert "dome" in algo
    assert "coverage" in algo


@pytest.mark.web
def test_n_speakers_radio_exposes_high_counts() -> None:
    demo = _build()
    radios = _radio_choice_values(demo)
    n_radio = next((r for r in radios if "64" in r), None)
    assert n_radio is not None, "n_speakers Radio with 64 not found"
    for c in ("24", "32", "48", "64"):
        assert c in n_radio


@pytest.mark.web
def test_algorithm_change_toggles_wfs_and_coverage_greying() -> None:
    """Lifted handler: WFS slider visible only for wfs; coverage greys n/radius/elev."""
    # returns 4 updates: [wfs_f_max_hz(visible), n_speakers, radius, elevation]
    wfs_u, n_u, r_u, el_u = _on_algorithm_change("wfs")
    assert _upd_field(wfs_u, "visible") is True
    # wfs does NOT grey the geometry knobs.
    for u in (n_u, r_u, el_u):
        assert _upd_field(u, "interactive") is True

    wfs_u, n_u, r_u, el_u = _on_algorithm_change("coverage")
    assert _upd_field(wfs_u, "visible") is False
    # coverage auto-computes count from room geometry → grey out n/radius/elev.
    for u in (n_u, r_u, el_u):
        assert _upd_field(u, "interactive") is False

    wfs_u, n_u, r_u, el_u = _on_algorithm_change("vbap")
    assert _upd_field(wfs_u, "visible") is False
    for u in (n_u, r_u, el_u):
        assert _upd_field(u, "interactive") is True


@pytest.mark.web
def test_example_button_label_present() -> None:
    demo = _build()
    labels = [
        c.value for c in demo.blocks.values()
        if isinstance(c, gr.Button) and getattr(c, "value", None)
    ]
    assert "예시 룸 불러오기" in labels


@pytest.mark.web
def test_example_room_bundled_on_disk() -> None:
    assert _EXAMPLE_ROOM_PATH.is_file(), f"bundled example missing: {_EXAMPLE_ROOM_PATH}"


@pytest.mark.web
def test_on_load_example_populates_layout_state(tmp_path: object) -> None:
    """One click runs the real pipeline and populates layout_state (index 11).

    The binaural data root is redirected to an empty dir so the heavy order-10
    30 s binaural render is skipped (the placement/parse path is what we assert).
    """
    pytest.importorskip("trimesh")
    # Point _BINAURAL_DATA_ROOT at an empty dir → source.wav/HRTF absent →
    # _on_submit takes the "binaural data not ready" branch (fast, no render).
    with patch("roomestim_web.app._BINAURAL_DATA_ROOT", tmp_path):
        result = _on_load_example("vbap", "8", 2.0, 0.0, True, 8000.0)
    assert isinstance(result, tuple)
    assert len(result) == 12
    layout_state = result[11]
    room_state = result[10]
    assert layout_state is not None, "layout_state should be populated by example load"
    assert room_state is not None
    assert len(layout_state.speakers) == 8
