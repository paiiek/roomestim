"""roomestim_web.material_override — Material Override Tab for the web UI.

Purpose
-------
Provides the Gradio Material Override Tab allowing users to correct per-surface
material assignments after a phone-scan. The core mutation logic is delegated to
``roomestim.edit`` helpers (D39), recompute is triggered by an explicit Apply
button (D40), and ADR 0009 ISM ≥ Eyring invariant is preserved on all evolved
rooms (D43).

Layering
--------
Imports: Gradio + ``roomestim.edit`` + ``roomestim_web.report``. No reconstruct
or model import beyond what is needed for the surface table builder. D29 lane
separation is preserved (web → core single direction).

References: D39, D40, D43, ADR 0031.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from roomestim.model import MaterialLabel, RoomModel

if TYPE_CHECKING:
    from roomestim_web.report import AcousticReport

_LOG = logging.getLogger("roomestim_web.material_override")

# All valid material labels for dropdown choices.
_MATERIAL_CHOICES: list[str] = [m.value for m in MaterialLabel]


# --------------------------------------------------------------------------- #
# Surface table builder
# --------------------------------------------------------------------------- #


def _polygon_area_approx(polygon: list[Any]) -> float:
    """Approximate polygon area via Newell's method (z-projection for walls)."""
    try:
        from roomestim.geom.polygon import polygon_area_3d
        return polygon_area_3d(polygon)
    except Exception:
        return 0.0


def _build_surface_table(room: RoomModel) -> list[list[str]]:
    """Return a list-of-rows for the Gradio Dataframe surface table.

    Columns: [index, kind, material, polygon_summary]
    """
    rows: list[list[str]] = []
    for i, surf in enumerate(room.surfaces):
        area = _polygon_area_approx(surf.polygon)
        n_verts = len(surf.polygon)
        poly_summary = f"{n_verts} vertices, area={area:.2f} m²"
        rows.append([str(i), surf.kind, surf.material.value, poly_summary])
    return rows


# --------------------------------------------------------------------------- #
# Apply handler
# --------------------------------------------------------------------------- #


def on_apply_overrides(
    room: RoomModel,
    changes_json: str,
) -> tuple[RoomModel, "AcousticReport", list[str]]:
    """Apply material overrides and recompute the acoustic report.

    Parameters
    ----------
    room:
        Current RoomModel (not mutated).
    changes_json:
        JSON string mapping surface index strings to MaterialLabel values,
        e.g. ``'{"0": "glass", "3": "carpet"}'``. Empty ``"{}"`` is a no-op.

    Returns
    -------
    tuple[RoomModel, AcousticReport, list[str]]
        New evolved room, freshly-computed acoustic report, and list of
        error messages for invalid entries (empty list = all OK).
    """
    from roomestim.edit import evolve_room_materials_bulk
    from roomestim_web.report import build_acoustic_report

    errors: list[str] = []

    try:
        raw: dict[str, str] = json.loads(changes_json) if changes_json.strip() else {}
    except json.JSONDecodeError as exc:
        msg = f"잘못된 JSON 입력: {exc}"
        _LOG.warning("on_apply_overrides: invalid changes_json %r — %s", changes_json, exc)
        errors.append(msg)
        raw = {}

    valid_values = {m.value for m in MaterialLabel}
    changes: dict[int, MaterialLabel] = {}
    for k, v in raw.items():
        try:
            idx = int(k)
        except ValueError:
            msg = f"surface index {k!r} 는 정수여야 합니다."
            _LOG.warning("on_apply_overrides: non-integer index %r — skipping", k)
            errors.append(msg)
            continue
        if v not in valid_values:
            msg = f"재질 값 {v!r} 이 유효하지 않습니다. 유효한 값: {sorted(valid_values)}"
            _LOG.warning("on_apply_overrides: invalid material %r — skipping", v)
            errors.append(msg)
            continue
        try:
            mat = MaterialLabel(v)
            changes[idx] = mat
        except (ValueError, KeyError) as exc:
            msg = f"항목 {k!r}={v!r} 처리 오류: {exc}"
            _LOG.warning("on_apply_overrides: skipping invalid entry %r=%r — %s", k, v, exc)
            errors.append(msg)

    new_room = evolve_room_materials_bulk(room, changes)
    report = build_acoustic_report(new_room)
    return new_room, report, errors


# --------------------------------------------------------------------------- #
# Dataframe → JSON helper
# --------------------------------------------------------------------------- #


def _dataframe_to_changes_json(rows: list[list[str]], initial_room: RoomModel) -> str:
    """Convert Dataframe rows to a JSON changes string, including only changed materials.

    Parameters
    ----------
    rows:
        Current Dataframe rows as returned by Gradio (list of [index, kind, material, poly_summary]).
    initial_room:
        Baseline RoomModel; surfaces whose material matches baseline are excluded from output.

    Returns
    -------
    str
        JSON string ``{"idx": "material_value", ...}`` for changed surfaces only.
        Returns ``"{}"`` when no changes are detected or rows is empty.
    """
    if not rows:
        return "{}"
    changes: dict[str, str] = {}
    for i, row in enumerate(rows):
        if len(row) < 3:
            continue
        new_mat = str(row[2])
        if i < len(initial_room.surfaces):
            baseline_mat = initial_room.surfaces[i].material.value
            if new_mat != baseline_mat:
                changes[str(i)] = new_mat
    return json.dumps(changes) if changes else "{}"


# --------------------------------------------------------------------------- #
# Gradio tab builder
# --------------------------------------------------------------------------- #


def build_material_override_tab(  # type: ignore[return]
) -> Any:
    """Build and return the Material Override Tab Gradio components.

    Returns a dict with keys:
        ``tab``        — the gr.Tab context object
        ``dataframe``  — gr.Dataframe surface table
        ``apply_btn``  — gr.Button Apply button
        ``status_md``  — gr.Markdown change-pending indicator

    The tab is constructed inside the caller's ``gr.Tabs()`` context.
    """
    try:
        import gradio as gr  # noqa: PLC0415
    except ImportError:
        return {}

    with gr.Tab("재질 정정") as tab:
        gr.Markdown(
            "### 표면 재질 정정\n"
            "아래 표에서 재질을 선택한 뒤 **적용** 버튼을 누르면 음향 리포트가 재계산됩니다."
        )
        dataframe = gr.Dataframe(
            headers=["index", "kind", "material", "polygon_summary"],
            datatype=["str", "str", "str", "str"],
            col_count=(4, "fixed"),
            interactive=True,
            label="표면 목록 (material 열 클릭하여 재질 정정)",
        )
        changes_textbox = gr.Textbox(
            label="변경 사항 (JSON)",
            value="{}",
            lines=2,
            info=(
                'surface index → material 매핑. 예: `{"0": "glass", "3": "carpet"}`. '
                '재질 열에서 값 변경 시 자동 갱신됩니다.'
            ),
        )
        apply_btn = gr.Button("적용 (Apply)", variant="primary")
        status_md = gr.Markdown(
            value="",
            visible=False,
            label="변경 상태",
        )

    return {
        "tab": tab,
        "dataframe": dataframe,
        "apply_btn": apply_btn,
        "status_md": status_md,
        "changes_textbox": changes_textbox,
    }


__all__ = [
    "build_material_override_tab",
    "on_apply_overrides",
    "_build_surface_table",
    "_dataframe_to_changes_json",
    "_MATERIAL_CHOICES",
]
