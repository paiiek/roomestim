"""roomestim_web.app — Gradio UI shell (v0.12-web.0).

Defines build_demo() returning a gr.Blocks app with sidebar knobs,
file upload, and output tabs. Pipeline logic is wired in P13c–P13f.
"""
from __future__ import annotations

import atexit
import logging
import shutil
import tempfile
import time
from collections import deque
from pathlib import Path
from typing import Any

import gradio as gr

import roomestim_web
from roomestim import __version__ as ROOMESTIM_CORE_VERSION

_LOG = logging.getLogger("roomestim_web")

class _EvictingDeque(deque[tempfile.TemporaryDirectory[str]]):
    """deque that calls .cleanup() on TemporaryDirectory entries evicted by maxlen."""

    def append(self, item: tempfile.TemporaryDirectory[str]) -> None:
        if len(self) == self.maxlen:
            evicted = self[0]
            try:
                evicted.cleanup()
            except Exception:
                _LOG.exception("Failed to clean up evicted TemporaryDirectory")
        super().append(item)


# Deque of TemporaryDirectory handles; eviction (maxlen=8) auto-cleans oldest.
_TEMP_REAPER: _EvictingDeque = _EvictingDeque(maxlen=8)


def _reap_stale_tempdirs(max_age_seconds: int = 4 * 3600) -> None:
    """Walk tempfile.gettempdir() for roomestim_* dirs older than max_age_seconds; remove."""
    root = Path(tempfile.gettempdir())
    now = time.time()
    for entry in root.glob("roomestim_*"):
        try:
            if entry.is_dir() and (now - entry.stat().st_mtime) > max_age_seconds:
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            continue


atexit.register(_reap_stale_tempdirs)


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

    td = tempfile.TemporaryDirectory(prefix="roomestim_")
    _TEMP_REAPER.append(td)  # deque eviction closes the oldest entry; cap=8
    out_dir = Path(td.name)

    try:
        result = run_pipeline(
            file.name if hasattr(file, "name") else file,
            algorithm=algorithm,
            n_speakers=int(n_speakers),
            layout_radius_m=radius,
            el_deg=elevation,
            octave_band=octave_band,
            out_dir=out_dir,
        )
    except Exception:
        _LOG.exception("run_pipeline failed; returning all-None tuple")
        try:
            _TEMP_REAPER.remove(td)
        except ValueError:
            pass  # already evicted by another submit
        td.cleanup()
        return (None,) * 6

    # Build 3D figure (requires plotly; returns None if unavailable)
    try:
        figure = build_room_figure(result.room, result.layout)  # type: ignore[arg-type]
    except Exception:
        _LOG.exception("build_room_figure failed")
        figure = None

    # Build acoustic report and RT60 chart
    try:
        from roomestim_web.report import build_acoustic_report, build_rt60_bar_chart

        report = build_acoustic_report(result.room)  # type: ignore[arg-type]
        rt60_chart = build_rt60_bar_chart(report)
        report_json: Any = report.to_json_dict()
    except Exception:
        _LOG.exception("build_acoustic_report failed")
        rt60_chart, report_json = None, None

    # Build setup PDF
    try:
        from roomestim_web.setup_pdf import build_setup_pdf

        pdf_path = build_setup_pdf(
            result.layout,
            result.room,  # type: ignore[arg-type]
            out_dir / "setup_card.pdf",
            input_filename=Path(file.name).name if hasattr(file, "name") else str(file),
            roomestim_version=roomestim_web.__version__,
        )
        pdf_str: Any = str(pdf_path)
    except Exception:
        _LOG.exception("build_setup_pdf failed")
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
                out_dir / "binaural_demo.wav",
                hrtf=load_default_hrtf(),
                max_order=10,
                duration_s=30.0,
            )
            binaural_str: Any = str(binaural_path)
        else:
            binaural_str = None
    except Exception:
        _LOG.exception("render_binaural_demo failed")
        binaural_str = None

    # Path A: wrap archive build in try/except — build_result_archive requires
    # room_yaml and layout_yaml to be non-None; build_provenance_readme may also
    # raise. A failure here must not crash the Gradio response.
    try:
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
        zip_path = build_result_archive(artefacts, readme, out_dir / "result_bundle.zip")
        archive_str: Any = str(zip_path)
    except Exception:
        _LOG.exception("archive build failed; returning None for archive tier")
        archive_str = None

    return (figure, rt60_chart, report_json, pdf_str, binaural_str, archive_str)


def build_demo() -> gr.Blocks:
    """Build and return the Gradio Blocks app shell."""
    with gr.Blocks(title="roomestim — 공간 음향 구성기") as demo:
        gr.Markdown("## roomestim · 공간 음향 구성기")
        gr.Markdown(
            "방 스캔 파일 (`.usdz`, `.obj`, `.gltf`, `.glb`, `.ply`)을 업로드하고"
            " 좌측 사이드바에서 알고리즘·스피커·반경·고도각을 설정한 뒤 **실행** 버튼을 누르세요.\n\n"
            "결과는 우측 탭에서 3D 뷰어, 음향 리포트, 설치 안내 PDF, 바이노럴 데모,"
            " 원본 YAML 압축 파일로 제공됩니다."
        )

        with gr.Row():
            # ── Sidebar ──────────────────────────────────────────────────────
            with gr.Column(scale=1, min_width=240):
                gr.Markdown("### 설정")

                algorithm = gr.Radio(
                    ["vbap", "dbap", "wfs"],
                    label="알고리즘",
                    value="vbap",
                    info=(
                        "VBAP: 3-스피커 vector-based amplitude panning, 가장 표준."
                        " DBAP: distance-based, 비대칭 배치 허용."
                        " WFS: wave field synthesis, 직선·곡선 어레이용."
                    ),
                )
                n_speakers = gr.Radio(
                    ["4", "6", "8", "12", "16"],
                    label="스피커 개수",
                    value="8",
                    info="레이아웃에 사용할 스피커 개수. VBAP/DBAP는 4–16, WFS는 8–16 권장.",
                )
                radius = gr.Slider(
                    minimum=0.5,
                    maximum=3.0,
                    value=2.0,
                    step=0.1,
                    label="레이아웃 반경 (m)",
                    info="청취자 중심에서 스피커까지 거리 (미터). 일반 거실 1.5–2.5m, 스튜디오 0.5–1.5m.",
                )
                elevation = gr.Slider(
                    minimum=-30.0,
                    maximum=60.0,
                    value=0.0,
                    step=1.0,
                    label="고도각 (도)",
                    info="스피커 고도각 (도). 0=귀 높이, +30=천장 방향, –20=바닥 방향. 대부분 0 또는 ±15.",
                )
                octave_band = gr.Checkbox(
                    value=True,
                    label="옥타브 밴드 흡음",
                    info="6-밴드 (125/250/500/1k/2k/4k Hz) 옥타브 흡음 계산. 끄면 단일-밴드 500 Hz Sabine만 사용.",
                )

                scan_file = gr.File(
                    file_types=[".usdz", ".obj", ".gltf", ".glb", ".ply"],
                    label="방 스캔 (.usdz / .obj / .gltf / .glb / .ply)",
                )

                submit_btn = gr.Button("실행", variant="primary")

            # ── Output tabs ──────────────────────────────────────────────────
            with gr.Column(scale=3):
                with gr.Tabs():
                    with gr.Tab("3D 뷰어"):
                        viewer_plot = gr.Plot()

                    with gr.Tab("음향 리포트"):
                        report_plot = gr.Plot()
                        report_json = gr.JSON()

                    with gr.Tab("설치 안내 PDF"):
                        pdf_file = gr.File()

                    with gr.Tab("바이노럴 데모"):
                        binaural_audio = gr.Audio()

                    with gr.Tab("원본 다운로드"):
                        raw_file = gr.File(label="YAML 압축 파일")

        gr.Markdown(
            "**HRTF 및 음원 출처.** 기본 바이노럴 렌더링은"
            " [HUTUBS HRTF Dataset](https://depositonce.tu-berlin.de/items/dc8c5bff-3a6a-471e-9d6c-bce4ed7d9ae6)"
            " (Brinkmann et al., TU Berlin, CC BY 4.0)을 사용합니다."
            " fallback HRTF는 MIT KEMAR Head-Related Impulse Response Database"
            " (퍼블릭 도메인)이며, 샘플 모노 음성은 [LibriVox](https://librivox.org/)"
            " (퍼블릭 도메인)입니다. 라이선스 조건과 인용 의무 텍스트는"
            " `docs/adr/0025` 및 `docs/adr/0026` §\"Attribution\"을 참고하세요.",
            elem_id="hrtf-attribution-footer",
        )

        # Wire submit button — outputs mapped by component reference
        submit_btn.click(
            fn=_on_submit,
            inputs=[scan_file, algorithm, n_speakers, radius, elevation, octave_band],
            outputs=[viewer_plot, report_plot, report_json, pdf_file, binaural_audio, raw_file],
        )

    return demo


if __name__ == "__main__":
    build_demo().launch()
