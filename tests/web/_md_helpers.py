"""tests/web/_md_helpers.py — shared test helper for gr.update payload extraction.

Decouples web tests from the internal Gradio `gr.update(...)` representation
(`{"value": ..., "__type__": "update", "visible": ...}`) so a Gradio internal
restructure won't silently degrade the test contract. (v0.12-web.6 / MEDIUM-1
follow-up, code-review 2026-05-17 PM.)
"""
from __future__ import annotations

from typing import Any


def get_md_payload(maybe_update: Any) -> tuple[Any, Any]:
    """Return (value, visible) from a gr.update payload or dict fallback.

    Accepts:
      - dict-like: `{"value": str, "visible": bool, ...}` (unit-test fallback,
        or Gradio's internal update dict).
      - Object with `.value` / `.visible` attributes.

    Returns:
      (value_or_None, visible_or_None) tuple — both fields are optional so
      callers can assert on either side independently.
    """
    if isinstance(maybe_update, dict):
        return maybe_update.get("value"), maybe_update.get("visible")
    return getattr(maybe_update, "value", None), getattr(maybe_update, "visible", None)
