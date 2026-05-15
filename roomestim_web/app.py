"""roomestim_web.app — Gradio UI shell (v0.12-web.0).

Defines build_demo() returning a gr.Blocks app with sidebar knobs,
file upload, and output tabs. Pipeline logic is wired in P13c–P13f.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import gradio as gr

import roomestim_web
from roomestim import __version__ as ROOMESTIM_CORE_VERSION


def _on_submit(
    file: Any,
    algorithm: str,
    n_speakers: str,
    radius: float,
    elevation: float,
    octave_band: bool,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """Submit handler — runs pipeline and builds 3D figure when a file is uploaded.

    Returns a 6-tuple matching the output component order:
        (viewer_plot, report_plot, report_json, pdf_file, binaural_audio, raw_file)
    """
    if file is None:
        return (None, None, None, None, None, None)

    from roomestim_web.archive import ArchiveArtefacts, build_result_archive
    from roomestim_web.pipeline import run_pipeline
    from roomestim_web.provenance import build_provenance_readme
    from roomestim_web.viewer import build_room_figure

    out_dir = tempfile.mkdtemp(prefix="roomestim_")

    result = run_pipeline(
        file.name if hasattr(file, "name") else file,
        algorithm=algorithm,
        n_speakers=int(n_speakers),
        layout_radius_m=radius,
        el_deg=elevation,
        octave_band=octave_band,
        out_dir=out_dir,
    )

    # Build 3D figure (requires plotly; returns None if unavailable)
    try:
        figure = build_room_figure(result.room, result.layout)  # type: ignore[arg-type]
    except ImportError:
        figure = None

    # Build acoustic report and RT60 chart
    try:
        from roomestim_web.report import build_acoustic_report, build_rt60_bar_chart

        report = build_acoustic_report(result.room)  # type: ignore[arg-type]
        rt60_chart = build_rt60_bar_chart(report)
        report_json: Any = report.to_json_dict()
    except ImportError:
        rt60_chart, report_json = None, None

    # Build setup PDF
    try:
        from roomestim_web.setup_pdf import build_setup_pdf

        pdf_path = build_setup_pdf(
            result.layout,
            result.room,  # type: ignore[arg-type]
            Path(out_dir) / "setup_card.pdf",
            input_filename=Path(file.name).name if hasattr(file, "name") else str(file),
            roomestim_version=roomestim_web.__version__,
        )
        pdf_str: Any = str(pdf_path)
    except ImportError:
        pdf_str = None

    # Build binaural demo
    try:
        from roomestim_web.binaural import render_binaural_demo
        from roomestim_web.hrtf_io import load_default_hrtf

        source_wav = Path("roomestim_web/data/audio/source.wav")
        if source_wav.exists():
            binaural_path = render_binaural_demo(
                result.room,  # type: ignore[arg-type]
                result.layout,  # type: ignore[arg-type]
                source_wav,
                Path(out_dir) / "binaural_demo.wav",
                hrtf=load_default_hrtf(),
                max_order=10,
                duration_s=30.0,
            )
            binaural_str: Any = str(binaural_path)
        else:
            binaural_str = None
    except (ImportError, FileNotFoundError):
        binaural_str = None

    readme = build_provenance_readme(
        input_path=(file.name if hasattr(file, "name") else str(file)),
        algorithm=algorithm,
        n_speakers=int(n_speakers),
        layout_radius_m=radius,
        el_deg=elevation,
        octave_band=octave_band,
        roomestim_version=ROOMESTIM_CORE_VERSION,
        roomestim_web_version=roomestim_web.__version__,
    )
    artefacts = ArchiveArtefacts(
        room_yaml=result.room_yaml_path,
        layout_yaml=result.layout_yaml_path,
        setup_pdf=Path(pdf_str) if pdf_str else None,
        binaural_wav=Path(binaural_str) if binaural_str else None,
        acoustic_report_json=report_json,
    )
    zip_path = build_result_archive(artefacts, readme, Path(out_dir) / "result_bundle.zip")

    return (figure, rt60_chart, report_json, pdf_str, binaural_str, str(zip_path))


def build_demo() -> gr.Blocks:
    """Build and return the Gradio Blocks app shell."""
    with gr.Blocks(title="roomestim — spatial audio configurator") as demo:
        gr.Markdown("## roomestim · spatial audio configurator")
        gr.Markdown(
            "Upload a room scan (`.usdz` or `.obj`), configure the sidebar, "
            "then press **Run**."
        )

        with gr.Row():
            # ── Sidebar ──────────────────────────────────────────────────────
            with gr.Column(scale=1, min_width=240):
                gr.Markdown("### Configuration")

                algorithm = gr.Radio(
                    ["vbap", "dbap", "wfs"],
                    label="Algorithm",
                    value="vbap",
                )
                n_speakers = gr.Radio(
                    ["4", "6", "8", "12", "16"],
                    label="N speakers",
                    value="8",
                )
                radius = gr.Slider(
                    minimum=0.5,
                    maximum=3.0,
                    value=2.0,
                    step=0.1,
                    label="Layout radius (m)",
                )
                elevation = gr.Slider(
                    minimum=-30.0,
                    maximum=60.0,
                    value=0.0,
                    step=1.0,
                    label="Elevation (deg)",
                )
                octave_band = gr.Checkbox(
                    value=True,
                    label="Octave-band absorption",
                )

                scan_file = gr.File(
                    file_types=[".usdz", ".obj"],
                    label="Room scan (.usdz or .obj)",
                )

                submit_btn = gr.Button("Run", variant="primary")

            # ── Output tabs ──────────────────────────────────────────────────
            with gr.Column(scale=3):
                with gr.Tabs():
                    with gr.Tab("3D viewer"):
                        viewer_plot = gr.Plot()

                    with gr.Tab("Acoustic report"):
                        report_plot = gr.Plot()
                        report_json = gr.JSON()

                    with gr.Tab("Setup PDF"):
                        pdf_file = gr.File()

                    with gr.Tab("Binaural demo"):
                        binaural_audio = gr.Audio()

                    with gr.Tab("Raw downloads"):
                        raw_file = gr.File(label="YAML zip")

        # Wire submit button — outputs mapped by component reference
        submit_btn.click(
            fn=_on_submit,
            inputs=[scan_file, algorithm, n_speakers, radius, elevation, octave_band],
            outputs=[viewer_plot, report_plot, report_json, pdf_file, binaural_audio, raw_file],
        )

    return demo


if __name__ == "__main__":
    build_demo().launch()
