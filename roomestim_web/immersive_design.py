"""roomestim_web.immersive_design — Immersive Layout Trade-off Tab (P4).

Purpose
-------
Immersive design panel — evaluate the already-placed layout against the shipped
4-axis trade-off report (immersive-layout-design P3) and export it as JSON. The
user picks a built-in speaker spec, an optional price, drive power, a target SPL,
and an optional measured RT60, then clicks 평가; the JSON report + an honesty
disclaimer render. A second button exports the last-evaluated dict verbatim.

Layering (D29 — web → core, single direction)
---------------------------------------------
ALL physics is delegated to ``roomestim.design.tradeoff.evaluate_layout`` /
``tradeoff_to_dict``; the built-in specs come from
``roomestim.spec.speaker_spec.BUILTIN_SPEAKER_CATALOG``. This module only builds
the form, normalises the inputs, renders the report, and serialises the export.
NO core mutation, NO physics re-derivation.

Honesty (ADR 0038 / OQ-45)
--------------------------
The real exception text is logged server-side; the web user only ever sees a
GENERIC Korean message. The report's own ``note`` / ``spl_provenance`` /
``rt60_source`` are surfaced in a Markdown disclaimer ABOVE the JSON so the
relative-guidance caveat is visible without expanding the report.

References: ADR 0060 (P3 trade-off), immersive-layout-design Phase 4.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

import gradio as gr

_LOG = logging.getLogger("roomestim_web.immersive_design")

# Default model key (must exist in BUILTIN_SPEAKER_CATALOG).
_DEFAULT_MODEL_KEY = "generic_surround_compact"


def _is_finite_positive(value: Any) -> bool:
    """True iff *value* coerces to a finite float strictly greater than 0."""
    if value is None:
        return False
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f) and f > 0.0


def _build_disclaimer(note: str, spl_provenance: str, rt60_source: str) -> str:
    """Render the honesty disclaimer Markdown (note + self-describing provenance)."""
    return (
        "**임머시브 트레이드오프 — 상대 비교용 가이드 (측정 보장 아님).**\n\n"
        f"- SPL provenance: `{spl_provenance}` "
        "(절대 SPL/헤드룸은 `datasheet` 일 때만 의미 있음; `estimate` 는 미리보기용)\n"
        f"- RT60 source: `{rt60_source}` (`measured` = 엔지니어 주입값, `predicted` = 모델 추정)\n\n"
        f"{note}"
    )


def _on_evaluate(
    room: Any,
    layout: Any,
    model_key: Any,
    price: Any,
    drive_w: Any,
    target_spl_db: Any,
    measured_rt60_raw: Any,
) -> tuple[Any, str, str, Any]:
    """Evaluate the live layout and return ``(json_dict, disclaimer_md, status_md, imm_state)``.

    Delegates ALL physics to ``roomestim.design.tradeoff.evaluate_layout``. The
    4th value (``imm_state``) is the SAME dict rendered in the JSON component so
    the export serialises exactly what was shown (no recompute drift).

    On a guard miss (no room / no layout / <2 speakers) returns a friendly Korean
    status, empty JSON ``{}``, empty disclaimer, and ``None`` state — never raises.
    On a physics failure the real error is logged server-side and the user gets a
    GENERIC message (ADR 0038 / OQ-45).
    """
    if room is None or layout is None:
        return {}, "", "먼저 좌측에서 룸을 제출/배치하세요.", None
    speakers = getattr(layout, "speakers", None)
    if not speakers or len(speakers) < 2:
        return {}, "", "스피커가 2개 이상 배치된 레이아웃이 필요합니다.", None

    from roomestim.design.tradeoff import (  # noqa: PLC0415
        evaluate_layout,
        tradeoff_to_dict,
    )
    from roomestim.spec.speaker_spec import BUILTIN_SPEAKER_CATALOG  # noqa: PLC0415

    key = model_key if model_key in BUILTIN_SPEAKER_CATALOG else _DEFAULT_MODEL_KEY
    spec = BUILTIN_SPEAKER_CATALOG[key]
    if _is_finite_positive(price):
        spec = dataclasses.replace(spec, price=float(price))

    # blank / None / <=0 → use the model-predicted RT60 (rt60_source="predicted").
    measured = float(measured_rt60_raw) if _is_finite_positive(measured_rt60_raw) else None

    try:
        report = evaluate_layout(
            room,
            layout,
            spec,
            listener_area=room.listener_area,
            drive_w=float(drive_w),
            target_spl_db=float(target_spl_db),
            measured_rt60=measured,
        )
    except Exception:
        # ADR 0038 / OQ-45: full detail logged server-side; user sees a generic
        # message (no raw exception text in the web-facing string).
        _LOG.exception("_on_evaluate evaluate_layout failed")
        return {}, "", "오류: 평가에 실패했습니다. 서버 로그를 확인하세요.", None

    dict_result = tradeoff_to_dict(report)
    disclaimer = _build_disclaimer(
        report.note, report.spl_provenance, report.rt60_source
    )
    status = (
        f"평가 완료: '{report.layout_name}' "
        f"({report.target_algorithm}, {report.n_speakers} speakers)"
    )
    return dict_result, disclaimer, status, dict_result


def _on_export_tradeoff(imm_dict: Any) -> tuple[Any, Any]:
    """Export the last-evaluated trade-off dict to a JSON file for download.

    Returns ``(file_path_or_None, gr.update status)``. Writes exactly what was
    shown (``imm_dict``) — no recompute. Mirrors ``app._on_export`` temp/reaper
    mechanics: a ``TemporaryDirectory`` is appended to the app's ``_TEMP_REAPER``
    (cap-8 eviction auto-cleans) so the file lives long enough to download
    without leaking. The reaper is imported lazily to avoid a circular import
    (app.py imports this module at build time).
    """
    if not imm_dict:
        return None, gr.update(value="먼저 평가를 실행하세요.", visible=True)
    from roomestim_web.app import _TEMP_REAPER  # noqa: PLC0415

    td = tempfile.TemporaryDirectory(prefix=f"roomestim_{os.getpid()}_tradeoff_")
    _TEMP_REAPER.append(td)
    out_path = Path(td.name) / "tradeoff.json"
    try:
        out_path.write_text(
            json.dumps(imm_dict, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        _LOG.exception("_on_export_tradeoff write failed")
        # Symmetric with app._on_run failure paths: drop the dir from the reaper
        # and clean it up now rather than leaving an empty temp dir to evict.
        try:
            _TEMP_REAPER.remove(td)
        except ValueError:
            pass
        td.cleanup()
        return None, gr.update(
            value="오류: 내보내기에 실패했습니다. 서버 로그를 확인하세요.", visible=True
        )
    return str(out_path), gr.update(
        value=f"트레이드오프 JSON export 완료: {out_path.name}", visible=True
    )


def build_immersive_design_tab(
    room_state: gr.State,
    layout_state: gr.State,
    on_evaluate: Callable[..., Any],
    on_export: Callable[..., Any],
) -> dict[str, Any]:
    """Build the Immersive Design Tab (spec/drive/target inputs + evaluate/export).

    ``room_state`` / ``layout_state`` are the host Blocks' live ``gr.State``
    holding the current ``RoomModel`` / ``PlacementResult`` (reused, NOT
    re-placed). ``on_evaluate`` / ``on_export`` are wired to the buttons by the
    caller (app.py) since component IDs depend on the host Blocks context.

    Returns a dict of component handles for the caller to wire.
    """
    from roomestim.spec.speaker_spec import BUILTIN_SPEAKER_CATALOG  # noqa: PLC0415

    with gr.Tab("임머시브 설계") as tab:
        gr.Markdown(
            "### 임머시브 레이아웃 4축 트레이드오프\n"
            "이미 배치된 레이아웃을 4축(레벨·패닝·분리·비용 + RT60 컨텍스트)으로 평가합니다. "
            "**먼저 좌측에서 룸을 제출/배치**한 뒤 아래 값을 설정하고 **평가**를 누르세요.\n\n"
            "이 리포트는 후보 레이아웃 비교용 **상대 가이드**이며, 보장된 실내 측정값이 아닙니다 "
            "(자세한 caveat 은 결과 위 면책 문구 참고)."
        )
        model_dd = gr.Dropdown(
            choices=sorted(BUILTIN_SPEAKER_CATALOG),
            value=_DEFAULT_MODEL_KEY,
            label="스피커 모델 (built-in spec)",
            info="내장 대표 추정(estimate-provenance) 스펙. 절대 SPL 은 미리보기용입니다.",
        )
        with gr.Row():
            price_num = gr.Number(
                value=None,
                label="대당 가격 (선택)",
                info="비우면 비용 축이 unpriced(None) 로 표시됩니다 (견적 아님).",
            )
            drive_slider = gr.Slider(
                minimum=1.0,
                maximum=100.0,
                value=10.0,
                step=1.0,
                label="구동 전력 drive_w (W)",
            )
        with gr.Row():
            target_slider = gr.Slider(
                minimum=70.0,
                maximum=105.0,
                value=85.0,
                step=1.0,
                label="목표 SPL (dB)",
            )
            rt60_num = gr.Number(
                value=None,
                label="측정 RT60 (s) — 선택",
                info="양수 → 주입(measured). 비우면/0 → 모델 추정(predicted) 사용.",
            )
        with gr.Row():
            evaluate_btn = gr.Button("평가", variant="primary")
            export_btn = gr.Button("트레이드오프 JSON 내보내기", variant="secondary")

        # imm_state holds the LAST tradeoff_to_dict result so export serialises
        # exactly what was shown (no recompute drift).
        imm_state: gr.State = gr.State(value=None)

        status_md = gr.Markdown(value="")
        disclaimer_md = gr.Markdown(value="")
        json_comp = gr.JSON(label="4축 트레이드오프 리포트")
        export_status_md = gr.Markdown(value="", visible=False)
        file_comp = gr.File(label="트레이드오프 JSON 다운로드", interactive=False)

    return {
        "tab": tab,
        "model_dd": model_dd,
        "price_num": price_num,
        "drive_slider": drive_slider,
        "target_slider": target_slider,
        "rt60_num": rt60_num,
        "evaluate_btn": evaluate_btn,
        "export_btn": export_btn,
        "imm_state": imm_state,
        "status_md": status_md,
        "disclaimer_md": disclaimer_md,
        "json_comp": json_comp,
        "export_status_md": export_status_md,
        "file_comp": file_comp,
    }


__all__ = [
    "build_immersive_design_tab",
    "_on_evaluate",
    "_on_export_tradeoff",
]
