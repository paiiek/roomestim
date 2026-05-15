"""Hugging Face Spaces entrypoint. Imports the Gradio Blocks app from roomestim_web."""
from __future__ import annotations

from roomestim_web.app import build_demo

demo = build_demo()

if __name__ == "__main__":
    demo.launch()
