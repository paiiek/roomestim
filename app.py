"""Hugging Face Spaces entrypoint. Imports the Gradio Blocks app from roomestim_web."""
from __future__ import annotations

from roomestim_web.app import _MAX_UPLOAD_BYTES, build_demo

# ADR 0038 / OQ-45 (Gap 2): build_demo() binds the upload cap onto the Blocks
# object (``demo.max_file_size``), which gradio's server honors regardless of
# launch path — so the HF-served ``demo`` already carries the cap. The explicit
# launch kwarg below re-affirms it for the local-run path.
demo = build_demo()

if __name__ == "__main__":
    demo.launch(max_file_size=_MAX_UPLOAD_BYTES)
