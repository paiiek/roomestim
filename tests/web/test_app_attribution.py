"""tests/web/test_app_attribution.py — verify HRTF attribution footer in Gradio UI."""
from __future__ import annotations

import pytest

pytest.importorskip("gradio")

import gradio as gr

from roomestim_web.app import build_demo


@pytest.mark.web
def test_hrtf_attribution_footer_present() -> None:
    """build_demo() must contain a gr.Markdown with elem_id='hrtf-attribution-footer'."""
    demo = build_demo()

    # Walk all blocks looking for the attribution Markdown
    footer: gr.Markdown | None = None
    for block in demo.blocks.values():
        if isinstance(block, gr.Markdown) and getattr(block, "elem_id", None) == "hrtf-attribution-footer":
            footer = block
            break

    assert footer is not None, (
        "Could not find gr.Markdown with elem_id='hrtf-attribution-footer'. "
        f"elem_ids found: {[getattr(b, 'elem_id', None) for b in demo.blocks.values()]}"
    )

    value = footer.value or ""
    assert "HUTUBS" in value, f"Expected 'HUTUBS' in attribution text, got: {value!r}"
    assert "CC BY 4.0" in value, f"Expected 'CC BY 4.0' in attribution text, got: {value!r}"
    assert "MIT KEMAR" in value, f"Expected 'MIT KEMAR' in attribution text, got: {value!r}"
