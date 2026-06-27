"""roomestim_web.app — Gradio UI shell (v0.12-web.0).

Defines build_demo() returning a gr.Blocks app with sidebar knobs,
file upload, and output tabs. Pipeline logic is wired in P13c–P13f.
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import shutil
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import gradio as gr

import roomestim_web
from roomestim import __version__ as ROOMESTIM_CORE_VERSION
from roomestim_web.material_override import (
    _dataframe_to_changes_json,
    build_material_override_tab,
    on_apply_overrides,
)
from roomestim_web.object_add import (
    _objects_to_rows,
    _on_add_object,
    _on_remove_object,
    build_object_add_tab,
)
from roomestim_web.speaker_nudge import (
    _on_nudge_speaker,
    build_speaker_nudge_tab,
)

_LOG = logging.getLogger("roomestim_web")

# ADR 0038: web upload boundary cap (defense-in-depth). Mirrors the MeshAdapter
# byte bound so gradio's own server-side size check rejects an oversized upload
# at the request boundary. NOTE: gradio still streams the upload to a temp file
# before handlers run, so this is gradio's size rejection — not a "before bytes
# hit disk" guard. The MeshAdapter pre-stat() byte-cap (env-overridable) is the
# load-bearing parse-memory chokepoint that also protects the CLI/library path.
_MAX_UPLOAD_BYTES = int(os.environ.get("ROOMESTIM_MAX_MESH_BYTES", 200 * 1024 * 1024))  # ~200 MB

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
    """Walk tempfile.gettempdir() for this PID's roomestim_<pid>_* dirs older than max_age; remove.

    OQ-45 / ADR 0038: the glob is namespaced per-PID so the reaper can never
    delete another process's tempdirs on a shared host. It still reaps this
    process's own stale dirs at ``atexit``.
    """
    root = Path(tempfile.gettempdir())
    now = time.time()
    for entry in root.glob(f"roomestim_{os.getpid()}_*"):
        try:
            if entry.is_dir() and (now - entry.stat().st_mtime) > max_age_seconds:
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            continue


atexit.register(_reap_stale_tempdirs)


# ---------------------------------------------------------------------------
# Background auto-fetch for binaural demo data (Phase 3 / ADR 0029)
# ---------------------------------------------------------------------------

_BINAURAL_DATA_ROOT = Path(
    os.environ.get("ROOMESTIM_WEB_DATA_ROOT") or (Path(__file__).parent / "data")
)
_BINAURAL_FETCH_STARTED = False
_BINAURAL_FETCH_LOCK = threading.Lock()


def _cleanup_stale_download_tmps() -> None:
    """Remove leftover ``.tmp`` files from prior interrupted downloads.

    Daemon thread may be killed mid-`urlretrieve` at process shutdown, leaving
    `<name>.tmp` files in the data dirs. Clear them before starting a new fetch
    so retries don't accumulate. (MAJOR-1 follow-up, code-review 2026-05-17.)
    """
    for sub in ("hrtf", "audio"):
        d = _BINAURAL_DATA_ROOT / sub
        if not d.exists():
            continue
        for tmp in d.glob("*.tmp"):
            try:
                tmp.unlink()
            except OSError:
                continue


def _binaural_data_present() -> bool:
    """True iff (KEMAR or HUTUBS) AND source.wav both exist on disk."""
    hrtf_dir = _BINAURAL_DATA_ROOT / "hrtf"
    audio_dir = _BINAURAL_DATA_ROOT / "audio"
    kemar_ok = (hrtf_dir / "kemar.sofa").exists()
    hutubs_ok = (hrtf_dir / "hutubs_pp1.sofa").exists()
    wav_ok = (audio_dir / "source.wav").exists()
    return (kemar_ok or hutubs_ok) and wav_ok


def _ensure_web_data() -> bool:
    """Start a background daemon thread to fetch KEMAR + LibriVox if missing.

    Respects ROOMESTIM_WEB_AUTO_FETCH=0 env opt-out (ADR 0029).
    Safe to call multiple times — only one fetch thread is ever started.

    Race-safety: file-existence checks AND the `_BINAURAL_FETCH_STARTED` flag
    update happen inside `_BINAURAL_FETCH_LOCK` so two concurrent callers cannot
    both decide to spawn a fetch thread when data is half-present.

    Returns:
        True if a background fetch was started (data missing + auto-fetch enabled),
        False otherwise. v0.12-web.6 (MINOR-3 /code-review 2026-05-17): used by
        `build_demo()` to set the initial binaural-status Markdown message.
    """
    global _BINAURAL_FETCH_STARTED
    from scripts.fetch_web_data import auto_fetch_enabled

    if not auto_fetch_enabled():
        return False

    with _BINAURAL_FETCH_LOCK:
        if _BINAURAL_FETCH_STARTED:
            return False
        if _binaural_data_present():
            return False  # all data present; nothing to do
        _BINAURAL_FETCH_STARTED = True

    _cleanup_stale_download_tmps()
    # Suppress per-block stdout progress in daemon mode to avoid log noise.
    # Set BEFORE thread start so the contract is explicit (LOW-1 / code-review web.6).
    os.environ.setdefault("ROOMESTIM_WEB_QUIET_FETCH", "1")

    def _bg_fetch() -> None:
        try:
            from scripts.fetch_web_data import auto_fetch
            auto_fetch(data_root=_BINAURAL_DATA_ROOT)
        except Exception:
            _LOG.exception("Background auto-fetch failed; binaural demo will use fallback.")

    t = threading.Thread(target=_bg_fetch, daemon=True, name="roomestim-web-data-fetch")
    t.start()
    _LOG.info("Background data fetch started (daemon thread).")
    return True


def _binaural_status_update(msg: str | None) -> Any:
    """Build a `gr.update(...)` for the binaural-status Markdown component.

    Returns visible=False / value="" when *msg* is None, else visible=True with the
    Korean message. Wraps in a try/except so unit tests that import this without
    Gradio still work — those receive a plain dict fallback.
    """
    try:
        return gr.update(value=msg or "", visible=msg is not None)
    except Exception:
        return {"value": msg or "", "visible": msg is not None}


def _on_submit(
    file: Any,
    algorithm: str,
    n_speakers: str,
    radius: float,
    elevation: float,
    octave_band: bool,
    wfs_f_max_hz: float,
    skip_engine_validation: bool = False,
    ceiling_height_m: float | None = None,
    snap_to_surfaces: bool = False,
) -> tuple[Any, Any, Any, Any, Any, Any, Any, Any, Any, Any, Any, Any]:
    """Submit handler — runs pipeline and builds 3D figure when a file is uploaded.

    Returns a 12-tuple matching the output component order:
        (viewer_plot, report_plot, report_json, pdf_file, binaural_audio,
         binaural_status_md, raw_file, material_table, blueprint_png,
         blueprint_svg, room_state, layout_state)
    """
    if file is None:
        return (None, None, None, None, None, _binaural_status_update(None), None, None, None, None, None, None)

    from roomestim_web.archive import ArchiveArtefacts, build_result_archive
    from roomestim_web.pipeline import run_pipeline
    from roomestim_web.provenance import build_provenance_readme
    from roomestim_web.viewer import build_room_figure

    td = tempfile.TemporaryDirectory(prefix=f"roomestim_{os.getpid()}_")
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
            wfs_f_max_hz=wfs_f_max_hz,
            skip_engine_validation=skip_engine_validation,
            # Rough+ consumer tier (PLACEMENT_SENSITIVITY_VERDICT.md): a user
            # ceiling scalar (only used on the point-cloud path) and install-time
            # snap. Treat 0/blank ceiling as "auto-estimate" (None).
            ceiling_height_m=(
                float(ceiling_height_m)
                if ceiling_height_m and float(ceiling_height_m) > 0.0
                else None
            ),
            snap_to_surfaces=bool(snap_to_surfaces),
        )
    except ValueError as exc:
        _LOG.warning("run_pipeline ValueError (WFS or validation): %s", exc)
        try:
            _TEMP_REAPER.remove(td)
        except ValueError:
            pass
        td.cleanup()
        # ADR 0038 / OQ-45: do NOT echo str(exc) to the web user — WFS/validation
        # messages can embed the resolved engine schema path (SPATIAL_ENGINE_REPO_DIR).
        # Full detail is logged above; the user gets a generic message.
        error_report: Any = {
            "error": "처리 중 오류가 발생했습니다. 서버 로그를 확인하세요.",
            "algorithm": algorithm,
        }
        return (None, None, error_report, None, None, _binaural_status_update(None), None, None, None, None, None, None)
    except Exception:
        _LOG.exception("run_pipeline failed; returning all-None tuple")
        try:
            _TEMP_REAPER.remove(td)
        except ValueError:
            pass  # already evicted by another submit
        td.cleanup()
        return (None, None, None, None, None, _binaural_status_update(None), None, None, None, None, None, None)

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
    _binaural_status: str | None = None
    try:
        from roomestim_web.binaural import render_binaural_demo
        from roomestim_web.hrtf_io import load_default_hrtf

        source_wav = _BINAURAL_DATA_ROOT / "audio" / "source.wav"
        hrtf_dir = _BINAURAL_DATA_ROOT / "hrtf"
        hrtf_present = (hrtf_dir / "hutubs_pp1.sofa").exists() or (hrtf_dir / "kemar.sofa").exists()

        if source_wav.exists() and hrtf_present:
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
            _binaural_status = (
                "바이노럴 데모 미준비 — 데이터 파일이 없습니다. "
                "`python scripts/fetch_web_data.py --auto` 를 실행하거나 "
                "잠시 후 다시 시도하세요 (자동 다운로드 진행 중일 수 있습니다)."
            )
    except Exception:
        _LOG.exception("render_binaural_demo failed")
        binaural_str = None
        _binaural_status = "바이노럴 렌더링 중 오류가 발생했습니다. 로그를 확인하세요."

    # Expose binaural status in report_json if available
    if _binaural_status is not None and isinstance(report_json, dict):
        report_json["binaural_status"] = _binaural_status
    elif _binaural_status is not None:
        report_json = {"binaural_status": _binaural_status}

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

    # Build material surface table
    try:
        from roomestim_web.material_override import _build_surface_table
        material_table: Any = _build_surface_table(result.room)  # type: ignore[arg-type]
    except Exception:
        _LOG.exception("_build_surface_table failed")
        material_table = None

    # Build blueprint PNG + SVG
    blueprint_png_str: Any = None
    blueprint_svg_str: Any = None
    try:
        from roomestim.viz.blueprint import render_blueprint
        bp_png = out_dir / "blueprint.png"
        bp_svg = out_dir / "blueprint.svg"
        render_blueprint(result.room, result.layout, bp_png, fmt="png", dpi=300)  # type: ignore[arg-type]
        render_blueprint(result.room, result.layout, bp_svg, fmt="svg")  # type: ignore[arg-type]
        blueprint_png_str = str(bp_png)
        blueprint_svg_str = str(bp_svg)
    except Exception:
        _LOG.exception("render_blueprint failed")

    return (
        figure, rt60_chart, report_json, pdf_str, binaural_str,
        _binaural_status_update(_binaural_status), archive_str,
        material_table, blueprint_png_str, blueprint_svg_str,
        result.room,    # room_state — feeds Material Override Tab Apply button
        result.layout,  # layout_state — feeds OQ-32 viewer rebuild on Apply (v0.16.1)
    )


def _on_apply_overrides_wrapper(
    room: Any,
    layout: Any,
    changes_json: Any,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """Apply material overrides and return updated Gradio component values.

    Returns (room_state, viewer_plot, report_plot, report_json,
             override_status_md, changes_state_reset).

    Factored to module-level for testability (v0.16.1 verifier fix).
    v0.16.1: layout arg added for OQ-32 viewer rebuild.
    """
    if room is None:
        status = gr.update(value="오류: 먼저 방 스캔 파일을 실행하세요.", visible=True)
        return room, None, None, None, status, "{}"
    try:
        from roomestim_web.report import build_rt60_bar_chart  # noqa: PLC0415
        changes_str = changes_json if isinstance(changes_json, str) else "{}"
        new_room, new_report, errors = on_apply_overrides(room, changes_str)
        new_rt60_chart = build_rt60_bar_chart(new_report)
        new_report_json: Any = new_report.to_json_dict()
        if errors:
            msg = "⚠ 일부 재질 값 오류:\n" + "\n".join(f"• {e}" for e in errors)
        else:
            n = _count_changes(changes_str)
            msg = f"정정 적용됨: {n} surface(s)"
        status_update = gr.update(value=msg, visible=True)
        # OQ-32: rebuild 3D viewer with new room colors.
        try:
            from roomestim_web.viewer import build_room_figure  # noqa: PLC0415
            new_figure = build_room_figure(new_room, layout) if layout is not None else None
        except Exception:
            _LOG.exception("build_room_figure failed in _on_apply_overrides_wrapper")
            new_figure = None
        return new_room, new_figure, new_rt60_chart, new_report_json, status_update, "{}"
    except Exception:
        # ADR 0038 / OQ-45: full detail logged server-side; user sees a generic
        # message (no raw exception text in the web-facing string).
        _LOG.exception("_on_apply_overrides_wrapper failed")
        status_update = gr.update(
            value="오류: 재질 정정에 실패했습니다. 서버 로그를 확인하세요.", visible=True
        )
        return room, None, None, None, status_update, "{}"


def _count_changes(changes_json: str) -> int:
    """Return number of entries in a JSON-encoded {idx: material} mapping; 0 on parse error.

    v0.16.1 LOW-1: extracted from inline __import__("json") in _on_apply_overrides_wrapper.
    """
    if not changes_json.strip():
        return 0
    try:
        parsed = json.loads(changes_json)
    except (json.JSONDecodeError, ValueError, TypeError):
        return 0
    return len(parsed) if isinstance(parsed, dict) else 0


def build_demo() -> gr.Blocks:
    """Build and return the Gradio Blocks app shell."""
    fetch_started = _ensure_web_data()  # kick off background fetch if data is missing (ADR 0029)
    # Initial binaural-status message: tell the user data is being prepared so the
    # binaural tab is never blank at boot (v0.12-web.6 / HF Spaces cold-boot UX).
    if fetch_started:
        initial_binaural_status = (
            "바이노럴 데모 데이터 다운로드 중 — 약 30 초 후 첫 실행 시 사용 가능합니다."
        )
        initial_binaural_visible = True
    elif not _binaural_data_present():
        initial_binaural_status = (
            "바이노럴 데모 데이터 미준비 — `python scripts/fetch_web_data.py --auto` 를 실행하세요."
        )
        initial_binaural_visible = True
    else:
        initial_binaural_status = ""
        initial_binaural_visible = False
    with gr.Blocks(title="roomestim — 공간 음향 구성기") as demo:
        gr.Markdown("## roomestim · 공간 음향 구성기")
        gr.Markdown(
            "방 스캔 파일 (`.usdz`, `.obj`, `.gltf`, `.glb`, `.ply`) 또는 폰/영상 포인트 "
            "클라우드 (`.npz`, `.xyz`, `.txt`)를 업로드하고 좌측 사이드바에서 알고리즘·스피커·"
            "반경·고도각을 설정한 뒤 **실행** 버튼을 누르세요. 거친 포인트 클라우드는 천장 높이를 "
            "직접 입력하고 ‘설치 시 표면에 스냅’을 켜는 것을 권장합니다.\n\n"
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
                # Slider default 1500 Hz differs from dispatch.run_placement default
                # (8000 Hz). When algorithm != "wfs" this value is still passed but
                # ignored by VBAP/DBAP; only the WFS dispatch branch reads it.
                wfs_f_max_hz = gr.Slider(
                    minimum=500,
                    maximum=8000,
                    value=1500,
                    step=100,
                    label="WFS f_max (Hz)",
                    info="WFS 공간 앨리어싱 상한 주파수. 스피커 간격이 좁을수록 높은 값 허용.",
                    visible=False,
                    interactive=True,
                )

                scan_file = gr.File(
                    file_types=[
                        ".usdz", ".obj", ".gltf", ".glb", ".ply",
                        ".npz", ".xyz", ".txt",
                    ],
                    label="방 스캔 / 포인트 클라우드 (.usdz / .obj / .gltf / .glb / .ply / .npz / .xyz / .txt)",
                )

                # ── Rough+ consumer tier (PLACEMENT_SENSITIVITY_VERDICT.md) ──
                # Point-cloud (phone/video) captures never reconstruct the
                # ceiling, so the user supplies it as one scalar; install-time
                # snap then mounts the planned speakers on real surfaces.
                ceiling_height_m = gr.Number(
                    value=None,
                    label="천장 높이 (m) — 선택",
                    info=(
                        "포인트 클라우드(.npz/.xyz/.txt 또는 점-전용 .ply) 입력 시 천장 높이를 "
                        "직접 지정합니다. 거친 캡처는 천장을 복원하지 못하므로 한 숫자만 입력하면 "
                        "높이 레이어가 정확해집니다. 비우면(0) 클라우드에서 자동 추정. "
                        "메쉬/RoomPlan 입력에서는 무시됩니다."
                    ),
                )
                snap_to_surfaces = gr.Checkbox(
                    value=False,
                    label="설치 시 표면에 스냅",
                    info=(
                        "배치된 스피커를 가장 가까운 실제 벽/천장 표면으로 이동시켜 물리적으로 "
                        "설치 가능하게 만듭니다. 거친 방 모델에서 커버리지를 오라클 대비 ~0.03 dB "
                        "이내로 회복합니다 (PLACEMENT_SENSITIVITY_VERDICT.md)."
                    ),
                )

                # Engine validation toggle (D42 / ADR 0033).
                # Unchecked (default) = validation ON (backward-compat).
                # Checked = standalone YAML mode, schema check skipped.
                skip_engine_validation = gr.Checkbox(
                    value=False,
                    label="Standalone YAML (skip engine schema check)",
                    info=(
                        "체크하면 spatial_engine 스키마 검증을 건너뜁니다. "
                        "출력 YAML에 WARNING 코멘트가 추가됩니다 (ADR 0033 §C)."
                    ),
                )

                submit_btn = gr.Button("실행", variant="primary")

                # ── Export format Radio (Phase 5 / ADR 0035) ────────────────
                export_format = gr.Radio(
                    choices=["yaml", "usdz", "gltf"],
                    value="yaml",
                    label="Export 포맷",
                    info=(
                        "yaml = 기존 room/layout YAML 압축 (backward-compat). "
                        "usdz = AR 호환 USDZ (extras 필요). "
                        "gltf = GLB 바이너리 (trimesh 사용)."
                    ),
                )
                export_btn = gr.Button("Export", variant="secondary")
                export_file = gr.File(label="Export 결과 다운로드", interactive=False)
                export_status_md = gr.Markdown(value="", visible=False)

            # ── Output tabs ──────────────────────────────────────────────────
            with gr.Column(scale=3):
                # State holding the current RoomModel for the Material Override
                # Tab Apply button. Populated by _on_submit (index 10 in the
                # 12-tuple; layout_state index 11 — v0.16.1 OQ-32 closure).
                # None before first submit.
                room_state: gr.State = gr.State(value=None)
                # layout_state: holds PlacementResult for OQ-32 viewer rebuild on Apply (v0.16.1).
                layout_state: gr.State = gr.State(value=None)
                # State holding pending material changes as a JSON string
                # {"surface_index": "material_value", ...}. Reset to "{}" on
                # each new submit so stale changes don't carry over.
                changes_state: gr.State = gr.State(value="{}")

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
                        # Value is cleared on every successful submit via
                        # `_binaural_status_update(None)`. Do not optimize the
                        # helper to skip the None branch — a stale failure
                        # message must not persist after a successful retry.
                        # (v0.12-web.5 MINOR-2 follow-up.)
                        binaural_status_md = gr.Markdown(
                            value=initial_binaural_status,
                            visible=initial_binaural_visible,
                            elem_id="binaural-status",
                        )

                    with gr.Tab("원본 다운로드"):
                        raw_file = gr.File(label="YAML 압축 파일")

                    # Material Override Tab — built by helper (HIGH-1 fix).
                    _mat_comps = build_material_override_tab()
                    material_table = _mat_comps.get("dataframe") if _mat_comps else None
                    _apply_btn = _mat_comps.get("apply_btn") if _mat_comps else None
                    _override_status_md = _mat_comps.get("status_md") if _mat_comps else None
                    _changes_textbox = _mat_comps.get("changes_textbox") if _mat_comps else None

                    # Object Add Tab — v0.14-web.0 (ADR 0034 §A / D39).
                    _obj_comps = build_object_add_tab(room_state, _on_add_object, _on_remove_object)
                    _obj_form = _obj_comps.get("form", {})
                    _obj_kind_radio = _obj_comps.get("kind_radio")
                    _obj_add_btn = _obj_comps.get("add_btn")
                    _obj_table = _obj_comps.get("object_table")
                    _obj_remove_index = _obj_comps.get("remove_index")
                    _obj_remove_btn = _obj_comps.get("remove_btn")
                    _obj_status_md = _obj_comps.get("status_md")

                    # Speaker Nudge Tab — v0.15-web.0 (ADR 0036 §B / D49).
                    _nudge_comps = build_speaker_nudge_tab(layout_state, _on_nudge_speaker)
                    _nudge_channel = _nudge_comps.get("channel")
                    _nudge_daz = _nudge_comps.get("daz")
                    _nudge_del = _nudge_comps.get("del_deg")
                    _nudge_ddist = _nudge_comps.get("ddist")
                    _nudge_dx = _nudge_comps.get("dx")
                    _nudge_dy = _nudge_comps.get("dy")
                    _nudge_dz = _nudge_comps.get("dz")
                    _nudge_apply_btn = _nudge_comps.get("apply_btn")
                    _nudge_status_md = _nudge_comps.get("status_md")

                    with gr.Tab("2D 블루프린트"):
                        gr.Markdown(
                            "### 2D 블루프린트\n"
                            "룸 평면도 (top-down view). **실행** 후 자동 생성됩니다.\n\n"
                            "좌표계: x = 우측 (m), z = 전방/북쪽 (m) per D41."
                        )
                        blueprint_image = gr.Image(label="PNG (300 dpi)")
                        blueprint_file = gr.File(label="SVG 벡터 다운로드")

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

        # Toggle WFS f_max slider visibility based on algorithm selection
        algorithm.change(
            fn=lambda alg: gr.update(visible=(alg == "wfs")),
            inputs=[algorithm],
            outputs=[wfs_f_max_hz],
        )

        # Wire submit button — outputs mapped by component reference
        submit_btn.click(
            fn=_on_submit,
            inputs=[
                scan_file, algorithm, n_speakers, radius, elevation,
                octave_band, wfs_f_max_hz, skip_engine_validation,
                ceiling_height_m, snap_to_surfaces,
            ],
            outputs=[
                viewer_plot, report_plot, report_json, pdf_file,
                binaural_audio, binaural_status_md, raw_file,
                material_table, blueprint_image, blueprint_file,
                room_state,    # index 10 — feeds Material Override Apply button
                layout_state,  # index 11 — feeds OQ-32 viewer rebuild on Apply (v0.16.1)
            ],
        )

        # Wire Material Override Apply button (HIGH-1 fix).
        # _apply_btn is None if build_material_override_tab() returned {} (no Gradio).
        # Wire Dataframe change event → changes_textbox → changes_state (LOW-2 + LOW-3).
        if material_table is not None and _changes_textbox is not None:
            try:
                material_table.change(
                    fn=lambda rows, room: (
                        _dataframe_to_changes_json(rows, room)
                        if room is not None else "{}"
                    ),
                    inputs=[material_table, room_state],
                    outputs=[_changes_textbox],
                )
                _changes_textbox.change(
                    fn=lambda s: s,  # mirror textbox value into changes_state
                    inputs=[_changes_textbox],
                    outputs=[changes_state],
                )
            except Exception:
                _LOG.warning("Dataframe change event wiring failed; fallback to manual JSON input")

        if _apply_btn is not None:
            _apply_btn.click(
                fn=_on_apply_overrides_wrapper,
                inputs=[room_state, layout_state, changes_state],
                outputs=[room_state, viewer_plot, report_plot, report_json, _override_status_md, changes_state],
            )

        # ── Object Add wiring (v0.14-web.0) ──────────────────────────────────
        if (
            _obj_add_btn is not None
            and _obj_kind_radio is not None
            and _obj_table is not None
            and _obj_status_md is not None
        ):
            _form_keys = ["anchor_x", "anchor_y", "anchor_z", "width_m", "height_m", "depth_m", "wall_index", "material"]
            _form_inputs = [_obj_form[k] for k in _form_keys]

            def _add_wrapper(
                room: Any,
                layout: Any,
                kind: str,
                *form_values: Any,
            ) -> tuple[Any, Any, Any, Any, Any]:
                form_data = dict(zip(_form_keys, form_values, strict=False))
                new_room, status = _on_add_object(room, kind, form_data)  # type: ignore[arg-type]
                rows = _objects_to_rows(new_room)
                try:
                    from roomestim_web.viewer import build_room_figure  # noqa: PLC0415
                    new_fig = build_room_figure(new_room, layout) if (new_room is not None and layout is not None) else None
                except Exception:
                    _LOG.exception("build_room_figure failed after object add")
                    new_fig = None
                # Recompute acoustic report (objects may affect ISM via predictor).
                try:
                    from roomestim_web.report import build_acoustic_report, build_rt60_bar_chart  # noqa: PLC0415
                    rep = build_acoustic_report(new_room) if new_room is not None else None
                    chart = build_rt60_bar_chart(rep) if rep is not None else None
                    rep_json = rep.to_json_dict() if rep is not None else None
                except Exception:
                    _LOG.exception("acoustic report rebuild failed after object add")
                    chart, rep_json = None, None
                _ = chart
                _ = rep_json
                return new_room, new_fig, rows, gr.update(value=status, visible=True), gr.update()

            _obj_add_btn.click(
                fn=_add_wrapper,
                inputs=[room_state, layout_state, _obj_kind_radio, *_form_inputs],
                outputs=[room_state, viewer_plot, _obj_table, _obj_status_md, report_plot],
            )

        if (
            _obj_remove_btn is not None
            and _obj_remove_index is not None
            and _obj_table is not None
            and _obj_status_md is not None
        ):
            def _remove_wrapper(
                room: Any,
                layout: Any,
                idx: Any,
            ) -> tuple[Any, Any, Any, Any]:
                new_room, status = _on_remove_object(room, int(idx) if idx is not None else 0)
                rows = _objects_to_rows(new_room)
                try:
                    from roomestim_web.viewer import build_room_figure  # noqa: PLC0415
                    new_fig = build_room_figure(new_room, layout) if (new_room is not None and layout is not None) else None
                except Exception:
                    _LOG.exception("build_room_figure failed after object remove")
                    new_fig = None
                return new_room, new_fig, rows, gr.update(value=status, visible=True)

            _obj_remove_btn.click(
                fn=_remove_wrapper,
                inputs=[room_state, layout_state, _obj_remove_index],
                outputs=[room_state, viewer_plot, _obj_table, _obj_status_md],
            )

        # ── Speaker Nudge wiring (v0.15-web.0 / ADR 0036 §B) ─────────────────
        if _nudge_apply_btn is not None and _nudge_status_md is not None:
            def _nudge_wrapper(
                room: Any,
                layout: Any,
                channel: Any,
                daz: Any,
                del_deg: Any,
                ddist: Any,
                dx: Any,
                dy: Any,
                dz: Any,
            ) -> tuple[Any, Any, Any]:
                new_layout, fig, status = _on_nudge_speaker(
                    room, layout, channel, daz, del_deg, ddist, dx, dy, dz
                )
                # layout_state only advances on success (handler returns the
                # unchanged layout on error, so a failed nudge keeps the prior
                # placement). viewer_plot stays as-is when fig is None.
                fig_update = fig if fig is not None else gr.update()
                return new_layout, fig_update, gr.update(value=status, visible=True)

            _nudge_apply_btn.click(
                fn=_nudge_wrapper,
                inputs=[
                    room_state, layout_state, _nudge_channel,
                    _nudge_daz, _nudge_del, _nudge_ddist,
                    _nudge_dx, _nudge_dy, _nudge_dz,
                ],
                outputs=[layout_state, viewer_plot, _nudge_status_md],
            )

        # ── Export format dispatch (Phase 5 / ADR 0035) ──────────────────────
        export_btn.click(
            fn=_on_export,
            inputs=[room_state, layout_state, export_format],
            outputs=[export_file, export_status_md],
        )

    # ADR 0038 / OQ-45 (Gap 2): bind the upload cap on the Blocks object itself
    # so gradio's server honors it regardless of how the app is launched. The
    # gradio 6.14.0 upload route reads ``app.get_blocks().max_file_size`` at
    # request time (gradio.Blocks does NOT accept max_file_size as a ctor kwarg;
    # only launch() does, and HF Spaces' ``demo = build_demo(); demo.launch()``
    # never runs roomestim_web's ``__main__`` guard). Setting the attribute here
    # makes the cap effective at the HF entrypoint and any importer; a later
    # launch(max_file_size=...) simply re-affirms the same value.
    demo.max_file_size = _MAX_UPLOAD_BYTES

    return demo


def _on_export(
    room: Any,
    layout: Any,
    fmt: str,
) -> tuple[Any, Any]:
    """Dispatch Export button click by selected format.

    - ``yaml``: re-use existing layout_yaml writer.
    - ``usdz``: lazy import ``roomestim.export.write_usdz``; ImportError if
      ``[usd]`` extras 미설치.
    - ``gltf``: lazy import ``roomestim.export.write_gltf`` (format=``glb``).

    Returns (file_path_or_None, gr.update for status_md).
    """
    if room is None or layout is None:
        return None, gr.update(value="오류: 먼저 방 스캔 파일을 실행하세요.", visible=True)
    td = tempfile.TemporaryDirectory(prefix=f"roomestim_{os.getpid()}_export_")
    _TEMP_REAPER.append(td)
    out_dir = Path(td.name)
    try:
        if fmt == "yaml":
            from roomestim.export import write_layout_yaml  # noqa: PLC0415
            out_path = out_dir / "layout.yaml"
            write_layout_yaml(layout, out_path)
            return str(out_path), gr.update(value=f"YAML export 완료: {out_path.name}", visible=True)
        if fmt == "usdz":
            try:
                from roomestim.export import write_usdz  # type: ignore[attr-defined]  # noqa: PLC0415
            except ImportError as exc:
                _LOG.warning("usdz export ImportError: %s", exc)
                return None, gr.update(
                    value="오류: USDZ extras 미설치 — `pip install roomestim[usd]` 후 다시 시도하세요.",
                    visible=True,
                )
            out_path = out_dir / "room.usdz"
            write_usdz(room, layout, out_path)
            return str(out_path), gr.update(value=f"USDZ export 완료: {out_path.name}", visible=True)
        if fmt == "gltf":
            try:
                from roomestim.export import write_gltf  # type: ignore[attr-defined]  # noqa: PLC0415
            except ImportError as exc:
                _LOG.warning("gltf export ImportError: %s", exc)
                return None, gr.update(
                    value="오류: gLTF export 의존성 미설치 (trimesh 필요).",
                    visible=True,
                )
            out_path = out_dir / "room.glb"
            write_gltf(room, layout, out_path, format="glb")
            return str(out_path), gr.update(value=f"gLTF export 완료: {out_path.name}", visible=True)
        return None, gr.update(value=f"오류: 알 수 없는 포맷 {fmt!r}", visible=True)
    except Exception:
        # ADR 0038 / OQ-45: full detail logged server-side; user sees a generic
        # message (no raw exception text in the web-facing string).
        _LOG.exception("_on_export failed for fmt=%s", fmt)
        return None, gr.update(
            value="오류: export에 실패했습니다. 서버 로그를 확인하세요.", visible=True
        )


if __name__ == "__main__":
    # ADR 0038: build_demo() already binds the cap on the Blocks object; the
    # explicit launch kwarg re-affirms it for the local-run path (harmless).
    build_demo().launch(max_file_size=_MAX_UPLOAD_BYTES)
