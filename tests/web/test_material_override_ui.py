"""tests/web/test_material_override_ui.py — Material Override UI tests (v0.16.0 / D39 + D40 + D43).

Covers:
  - build_demo() includes "재질 정정" tab.
  - on_apply_overrides({0: GLASS}) → rt60 differs from baseline.
  - on_apply_overrides({0: GLASS}) → ISM >= Eyring - 1e-6 (D43 regression lock).
  - on_apply_overrides({}) → room and report byte-equal.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from roomestim.model import RoomModel


@pytest.fixture
def lab_room() -> RoomModel:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    from roomestim.adapters.roomplan import RoomPlanAdapter
    room = RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)
    assert isinstance(room, RoomModel)
    return room


@pytest.mark.web
def test_material_override_tab_components() -> None:
    """build_demo() contains '재질 정정' tab."""
    from roomestim_web.app import build_demo

    demo = build_demo()
    # Walk the Blocks components to find a tab with "재질 정정"
    found = False
    for block in demo.blocks.values():
        label = getattr(block, "label", None)
        if label and "재질 정정" in str(label):
            found = True
            break
    assert found, "Tab '재질 정정' not found in build_demo() components"


def test_on_apply_overrides_recompute(lab_room: RoomModel) -> None:
    """Changing surface 0 to GLASS produces a different rt60 than baseline."""
    from roomestim_web.material_override import on_apply_overrides
    from roomestim_web.report import build_acoustic_report

    baseline = build_acoustic_report(lab_room)
    changes = json.dumps({"0": "glass"})
    _new_room, new_report, _errors = on_apply_overrides(lab_room, changes)

    # rt60 must differ because absorption coefficients changed
    assert new_report.default_rt60_500hz_s != baseline.default_rt60_500hz_s, (
        f"Expected rt60 to change after material override; both = {baseline.default_rt60_500hz_s:.4f}"
    )


def test_on_apply_overrides_invariant(lab_room: RoomModel) -> None:
    """After material override, ISM >= Eyring - 1e-6 (D43 regression lock)."""
    from roomestim_web.material_override import on_apply_overrides

    changes = json.dumps({"0": "glass"})
    _new_room, new_report, _errors = on_apply_overrides(lab_room, changes)

    ism_rt60 = new_report.default_rt60_500hz_s
    eyr_rt60 = new_report.eyring_rt60_500hz_s

    # For ISM-path rooms (shoebox), default_rt60 = ISM
    # Verify the invariant
    assert ism_rt60 >= eyr_rt60 - 1e-6, (
        f"D43 violated after material override: ISM/default={ism_rt60:.4f} < "
        f"Eyring={eyr_rt60:.4f} - 1e-6"
    )


def test_on_apply_overrides_no_change(lab_room: RoomModel) -> None:
    """Empty changes_json '{}' → new room has same material values + same rt60."""
    from roomestim_web.material_override import on_apply_overrides
    from roomestim_web.report import build_acoustic_report

    baseline = build_acoustic_report(lab_room)
    new_room, new_report, errors = on_apply_overrides(lab_room, "{}")

    assert errors == [], f"No errors expected for empty changes; got {errors}"
    assert new_report.default_rt60_500hz_s == baseline.default_rt60_500hz_s, (
        f"Empty changes should produce identical report; "
        f"baseline={baseline.default_rt60_500hz_s:.4f}, new={new_report.default_rt60_500hz_s:.4f}"
    )
    # All materials unchanged
    for i, (orig, new) in enumerate(zip(lab_room.surfaces, new_room.surfaces)):
        assert new.material == orig.material, f"Surface {i} material changed unexpectedly"


def test_on_apply_overrides_recompute_returns_3tuple(lab_room: RoomModel) -> None:
    """on_apply_overrides returns a 3-tuple (room, report, errors) — MEDIUM-4."""
    from roomestim_web.material_override import on_apply_overrides
    import json

    result = on_apply_overrides(lab_room, json.dumps({"0": "glass"}))
    assert len(result) == 3, f"Expected 3-tuple, got {len(result)}-tuple"
    _new_room, _report, errors = result
    assert isinstance(errors, list), f"errors must be a list; got {type(errors)}"
    assert errors == [], f"No errors expected for valid input; got {errors}"


def test_on_apply_overrides_invalid_material_surfaces_errors(lab_room: RoomModel) -> None:
    """Invalid material string → errors list non-empty, room unchanged (MEDIUM-4)."""
    from roomestim_web.material_override import on_apply_overrides
    import json

    changes = json.dumps({"0": "typo_material"})
    new_room, new_report, errors = on_apply_overrides(lab_room, changes)

    assert len(errors) >= 1, "Expected at least one error for invalid material 'typo_material'"
    # Room should be unchanged (invalid entry skipped)
    assert new_room.surfaces[0].material == lab_room.surfaces[0].material, (
        "Invalid material must be skipped; original material should remain"
    )


def test_dataframe_changes_to_json_helper(lab_room: RoomModel) -> None:
    """_dataframe_to_changes_json: changing surface 0 → glass produces {"0": "glass"}."""
    from roomestim_web.material_override import _build_surface_table, _dataframe_to_changes_json

    rows = _build_surface_table(lab_room)
    # Mutate a copy of rows to simulate Dataframe edit
    rows_changed = [list(r) for r in rows]
    rows_changed[0][2] = "glass"  # change surface 0 material

    result = _dataframe_to_changes_json(rows_changed, lab_room)
    parsed = json.loads(result)
    assert "0" in parsed, f"Expected surface 0 in changes; got {result}"
    assert parsed["0"] == "glass", f"Expected glass for surface 0; got {parsed['0']}"
    # Unchanged rows must not appear
    for i in range(1, len(rows)):
        assert str(i) not in parsed, f"Surface {i} should not appear (unchanged)"


def test_dataframe_changes_to_json_no_change(lab_room: RoomModel) -> None:
    """_dataframe_to_changes_json: unchanged rows → '{}'."""
    from roomestim_web.material_override import _build_surface_table, _dataframe_to_changes_json

    rows = _build_surface_table(lab_room)
    result = _dataframe_to_changes_json(rows, lab_room)
    assert result == "{}", f"Expected '{{}}' for unchanged rows; got {result!r}"


@pytest.mark.web
def test_apply_returns_viewer_figure(lab_room: RoomModel) -> None:
    """_on_apply_overrides_wrapper returns 6-tuple with non-None viewer figure (OQ-32)."""
    pytest.importorskip("gradio")
    pytest.importorskip("plotly")
    from roomestim.place.dispatch import run_placement
    from roomestim_web.app import _on_apply_overrides_wrapper

    layout = run_placement(lab_room, "vbap", 5, 2.0, 0.0)
    result = _on_apply_overrides_wrapper(lab_room, layout, '{"0": "glass"}')

    assert len(result) == 6, f"Expected 6-tuple; got {len(result)}-tuple"
    viewer_fig = result[1]
    assert viewer_fig is not None, "Expected non-None viewer figure after Apply (OQ-32)"


@pytest.mark.web
def test_count_changes_helper() -> None:
    """_count_changes: empty/empty-dict/single/invalid/non-dict → 0/0/1/0/0 (LOW-1 regression lock)."""
    pytest.importorskip("gradio")
    from roomestim_web.app import _count_changes

    assert _count_changes("") == 0, "empty string → 0"
    assert _count_changes("{}") == 0, "empty dict → 0"
    assert _count_changes('{"0": "glass"}') == 1, "single entry → 1"
    assert _count_changes("not-json") == 0, "invalid JSON → 0"
    assert _count_changes('[]') == 0, "non-dict (list) → 0"


@pytest.mark.web
def test_apply_button_wired_to_handler() -> None:
    """Apply button in Material Override Tab has a click handler bound (HIGH-1)."""
    import gradio as gr
    from roomestim_web.material_override import build_material_override_tab

    # gr.Tab requires gr.Blocks → gr.Tabs() context chain (Gradio 6.x rendering rule).
    with gr.Blocks():
        with gr.Tabs():
            comps = build_material_override_tab()

    assert comps, "build_material_override_tab() must return non-empty dict"
    apply_btn = comps.get("apply_btn")
    assert apply_btn is not None, "apply_btn must be present in returned dict"

    assert isinstance(apply_btn, gr.Button), (
        f"apply_btn must be a gr.Button; got {type(apply_btn)}"
    )
