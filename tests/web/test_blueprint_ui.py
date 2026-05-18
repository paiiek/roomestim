"""tests/web/test_blueprint_ui.py — Blueprint Tab + engine validation checkbox (v0.16.0).

Covers:
  - build_demo() includes "2D 블루프린트" tab.
  - build_demo() sidebar has Checkbox with "Standalone YAML" label + default False.
"""
from __future__ import annotations

import pytest


@pytest.mark.web
def test_blueprint_tab_components() -> None:
    """build_demo() contains '2D 블루프린트' tab."""
    from roomestim_web.app import build_demo

    demo = build_demo()
    found = False
    for block in demo.blocks.values():
        label = getattr(block, "label", None)
        if label and "블루프린트" in str(label):
            found = True
            break
    assert found, "Tab '2D 블루프린트' not found in build_demo() components"


@pytest.mark.web
def test_blueprint_engine_validation_checkbox() -> None:
    """Sidebar contains Checkbox with 'Standalone YAML' in label + default value=False."""
    import gradio as gr
    from roomestim_web.app import build_demo

    demo = build_demo()
    found_checkbox = False
    for block in demo.blocks.values():
        if isinstance(block, gr.Checkbox):
            label = getattr(block, "label", "") or ""
            if "Standalone YAML" in label:
                found_checkbox = True
                assert block.value is False, (
                    f"Checkbox default value should be False (validation ON), got {block.value}"
                )
                break
    assert found_checkbox, (
        "Checkbox with 'Standalone YAML' not found in build_demo() sidebar"
    )
