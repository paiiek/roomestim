"""tests/web/test_immersive_design_ui.py — immersive-layout P4 Immersive Design UI.

Covers the web surface of the shipped 4-axis trade-off report (ADR 0060):
- ``_on_evaluate`` composes ``tradeoff_to_dict`` ("note" first; nested axes).
- price injection sums the per-speaker price into the cost axis.
- measured RT60 injection flips ``rt60.source`` to "measured"; blank → "predicted".
- guard returns a friendly message + empty JSON + None state (never raises).
- ``_on_export_tradeoff`` writes the exact dict to a downloadable JSON file.
- ``build_demo`` exposes an "임머시브 설계" tab.

Handlers are called DIRECTLY (no live Gradio server).
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.web

pytest.importorskip("gradio")

from roomestim.place.vbap import place_vbap_ring  # noqa: E402
from roomestim_web.immersive_design import (  # noqa: E402
    _on_evaluate,
    _on_export_tradeoff,
)
from tests.fixtures.synthetic_rooms import shoebox  # noqa: E402


def test_on_evaluate_happy_path() -> None:
    room = shoebox()
    layout = place_vbap_ring(8, radius_m=2.0)
    json_dict, disclaimer, status, imm_state = _on_evaluate(
        room, layout, "generic_surround_compact", None, 10.0, 85.0, None
    )
    # "note" rides first.
    assert list(json_dict.keys())[0] == "note"
    # Nested axes present.
    for axis in ("spl", "angular", "interference", "cost", "rt60"):
        assert axis in json_dict
    assert json_dict["spl_provenance"] == "estimate"
    # imm_state is the SAME dict shown (no recompute drift).
    assert imm_state == json_dict
    assert disclaimer  # non-empty disclaimer surfaced
    # Honesty surfacing is load-bearing: the disclaimer must name the
    # self-describing provenance/source so a regression that drops them fails here.
    assert "spl_provenance" in disclaimer or "provenance" in disclaimer.lower()
    assert "rt60_source" in disclaimer or "RT60 source" in disclaimer
    assert "8 speakers" in status


def test_on_evaluate_price_injection() -> None:
    room = shoebox()
    layout = place_vbap_ring(8, radius_m=2.0)
    json_dict, _disclaimer, _status, _imm = _on_evaluate(
        room, layout, "generic_surround_compact", 125.0, 10.0, 85.0, None
    )
    assert json_dict["cost"]["total_price"] == 8 * 125.0
    assert json_dict["cost"]["complete"] is True


def test_on_evaluate_measured_rt60() -> None:
    room = shoebox()
    layout = place_vbap_ring(8, radius_m=2.0)
    json_dict, _d, _s, _i = _on_evaluate(
        room, layout, "generic_surround_compact", None, 10.0, 85.0, 0.42
    )
    assert json_dict["rt60"]["source"] == "measured"
    assert json_dict["rt60"]["effective_s"] == pytest.approx(0.42, abs=1e-3)

    # blank / 0 → predicted.
    for blank in (None, 0, 0.0):
        d2, _d, _s, _i = _on_evaluate(
            room, layout, "generic_surround_compact", None, 10.0, 85.0, blank
        )
        assert d2["rt60"]["source"] == "predicted"


def test_on_evaluate_guard_returns_friendly_message() -> None:
    room = shoebox()
    # No room AND no layout.
    json_dict, disclaimer, status, imm_state = _on_evaluate(
        None, None, "generic_surround_compact", None, 10.0, 85.0, None
    )
    assert json_dict == {}
    assert imm_state is None
    assert status  # friendly Korean message
    assert disclaimer == ""

    # Room present, layout missing → still guarded, no raise.
    json_dict2, _d, status2, imm2 = _on_evaluate(
        room, None, "generic_surround_compact", None, 10.0, 85.0, None
    )
    assert json_dict2 == {}
    assert imm2 is None
    assert status2


def test_on_evaluate_too_few_speakers_guarded() -> None:
    room = shoebox()
    layout = place_vbap_ring(8, radius_m=2.0)
    layout.speakers = layout.speakers[:1]  # 1 speaker → angular/interference need >=2
    json_dict, disclaimer, status, imm_state = _on_evaluate(
        room, layout, "generic_surround_compact", None, 10.0, 85.0, None
    )
    assert json_dict == {}
    assert imm_state is None
    assert status  # friendly message, no raise
    assert disclaimer == ""


def test_on_evaluate_invalid_model_key_falls_back() -> None:
    room = shoebox()
    layout = place_vbap_ring(8, radius_m=2.0)
    json_dict, _d, _s, imm = _on_evaluate(
        room, layout, "nonexistent_model", None, 10.0, 85.0, None
    )
    # Unknown key falls back to the default built-in spec; evaluation still succeeds.
    assert imm == json_dict
    assert list(json_dict.keys())[0] == "note"


def test_on_export_tradeoff_roundtrip() -> None:
    room = shoebox()
    layout = place_vbap_ring(8, radius_m=2.0)
    json_dict, _d, _s, _i = _on_evaluate(
        room, layout, "generic_surround_compact", None, 10.0, 85.0, None
    )
    path, _status = _on_export_tradeoff(json_dict)
    assert path is not None
    from pathlib import Path

    assert Path(path).exists()
    with open(path, encoding="utf-8") as fh:
        loaded = json.load(fh)
    assert "note" in loaded
    assert loaded == json_dict


def test_on_export_tradeoff_none_returns_friendly_no_file() -> None:
    path, status = _on_export_tradeoff(None)
    assert path is None
    # status is a gr.update; its value carries the friendly message.
    value = getattr(status, "get", lambda *_: None)("value") or getattr(
        status, "value", ""
    )
    assert "평가" in str(value)


def test_immersive_design_tab_present() -> None:
    import gradio as gr

    from roomestim_web.app import build_demo

    demo = build_demo()
    assert isinstance(demo, gr.Blocks)
    labels = [getattr(c, "label", None) for c in demo.blocks.values()]
    assert "임머시브 설계" in labels
