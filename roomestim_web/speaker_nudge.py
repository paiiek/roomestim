"""roomestim_web.speaker_nudge — Speaker Nudge Tab for the web UI.

Purpose
-------
Speaker Nudge panel — fine-tune one auto-placed speaker after the placement
algorithm runs (ADR 0036 §B). The user selects a channel, enters a spherical Δ
(az/el/dist) XOR a Cartesian Δ (xyz), and clicks Apply. The core mutation logic
is delegated to ``roomestim.edit.nudge_speaker`` and re-validation to
``roomestim.export.validate_placement``; this module only builds the form,
maps channel → speaker index, and renders the result.

Layering
--------
Imports: Gradio + ``roomestim.edit.nudge_speaker`` +
``roomestim.export.validate_placement``. The 3D viewer rebuild is delegated to
``roomestim_web.viewer.build_room_figure``. D29 lane separation (web → core,
single direction) preserved.

References: D49, D50, ADR 0036 §B/§D.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import gradio as gr

_LOG = logging.getLogger("roomestim_web.speaker_nudge")


def _channel_to_index(layout: Any, channel: Any) -> int | None:
    """Map a speaker ``channel`` to its zero-based index in ``layout.speakers``.

    Returns ``None`` when the channel is not found or ``layout`` is unusable.
    """
    if layout is None:
        return None
    try:
        target = int(channel)
    except (TypeError, ValueError):
        return None
    for i, sp in enumerate(layout.speakers):
        if int(sp.channel) == target:
            return i
    return None


def _on_nudge_speaker(
    room: Any,
    layout: Any,
    channel: Any,
    daz: float,
    del_deg: float,
    ddist: float,
    dx: float,
    dy: float,
    dz: float,
) -> tuple[Any, Any, str]:
    """Apply a single-speaker nudge and rebuild the 3D viewer.

    Returns ``(new_layout_or_unchanged, figure_or_None, status_markdown)``. On
    any failure the layout is returned unchanged so the caller's ``layout_state``
    keeps the last valid placement.
    """
    if layout is None:
        return layout, None, "오류: 먼저 방 스캔 파일을 실행하세요."

    idx = _channel_to_index(layout, channel)
    if idx is None:
        return layout, None, f"오류: 채널 {channel!r} 을(를) 찾을 수 없습니다."

    from roomestim.edit import nudge_speaker  # noqa: PLC0415
    from roomestim.export import validate_placement  # noqa: PLC0415

    try:
        new_layout = nudge_speaker(
            layout,
            idx,
            daz_deg=float(daz or 0.0),
            del_deg=float(del_deg or 0.0),
            ddist_m=float(ddist or 0.0),
            dx=float(dx or 0.0),
            dy=float(dy or 0.0),
            dz=float(dz or 0.0),
        )
    except (ValueError, IndexError) as exc:
        _LOG.warning("_on_nudge_speaker nudge failed: %s", exc)
        return layout, None, f"오류: nudge 실패 — {exc}"

    errs = validate_placement(new_layout)
    if errs:
        joined = "\n".join(f"• {e}" for e in errs)
        return layout, None, f"⚠ 엔진 검증 실패 (layout 미변경):\n{joined}"

    # Rebuild the 3D viewer with the new speaker positions (OQ-32 pattern).
    try:
        from roomestim_web.viewer import build_room_figure  # noqa: PLC0415

        figure = build_room_figure(room, new_layout) if room is not None else None
    except Exception:
        _LOG.exception("build_room_figure failed in _on_nudge_speaker")
        figure = None

    return new_layout, figure, f"스피커 조정 적용됨: 채널 {channel} (index {idx})"


def build_speaker_nudge_tab(
    initial_layout_state: gr.State,
    on_nudge: Callable[..., Any],
) -> dict[str, Any]:
    """Build the Speaker Nudge Tab (channel select + Δ inputs + Apply).

    Caller (app.py) wires ``on_nudge`` to the Apply button .click() event,
    since component IDs depend on the host Blocks context.

    Returns a dict with component handles:
        ``tab``        — gr.Tab context
        ``channel``    — gr.Number (speaker channel; 3D-click fallback)
        ``daz``        — gr.Number azimuth Δ (degrees, step 1)
        ``del_deg``    — gr.Number elevation Δ (degrees, step 1, [-90, 90])
        ``ddist``      — gr.Number distance Δ (m, step 0.05)
        ``dx``/``dy``/``dz`` — gr.Number Cartesian Δ (m, step 0.05)
        ``apply_btn``  — gr.Button Apply
        ``status_md``  — gr.Markdown status
    """
    with gr.Tab("스피커 조정") as tab:
        gr.Markdown(
            "### 스피커 미세 조정 (nudge)\n"
            "자동 배치된 스피커를 채널 단위로 미세 조정합니다. **구면 Δ** (az/el/dist)"
            " 또는 **직교 Δ** (x/y/z) 중 하나만 입력하세요 (동시 입력 시 오류).\n\n"
            "3D 뷰어에서 스피커를 클릭해 채널을 확인할 수 있습니다 (채널 입력이 우선)."
        )
        channel = gr.Number(label="채널 (channel)", value=1, precision=0, minimum=0)
        with gr.Row():
            daz = gr.Number(label="az Δ (도)", value=0.0, step=1.0)
            del_deg = gr.Number(
                label="el Δ (도)", value=0.0, step=1.0, minimum=-90.0, maximum=90.0
            )
            ddist = gr.Number(label="dist Δ (m)", value=0.0, step=0.05)
        with gr.Row():
            dx = gr.Number(label="x Δ (m)", value=0.0, step=0.05)
            dy = gr.Number(label="y Δ (m)", value=0.0, step=0.05)
            dz = gr.Number(label="z Δ (m)", value=0.0, step=0.05)
        apply_btn = gr.Button("적용 (Apply)", variant="primary")
        status_md = gr.Markdown(value="", visible=False, label="상태")

    return {
        "tab": tab,
        "channel": channel,
        "daz": daz,
        "del_deg": del_deg,
        "ddist": ddist,
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "apply_btn": apply_btn,
        "status_md": status_md,
    }


__all__ = [
    "build_speaker_nudge_tab",
    "_on_nudge_speaker",
    "_channel_to_index",
]
