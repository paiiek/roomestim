"""roomestim_web.object_add — Object Add Mode for the web UI.

Purpose
-------
Object Add Mode — column / door / window 추가 UI per ADR 0034 §A + D39.
사용자가 phone-scan 결과 후 누락된 기둥·문·창문을 룸 모델에 추가하거나
제거할 수 있게 한다. core 측 ``roomestim.edit.evolve_room_add_object`` /
``evolve_room_remove_object`` 가 immutable evolve 를 책임지므로 본 모듈은
입력 폼 + 검증 + 호출만 담당.

Layering
--------
Imports: Gradio + ``roomestim`` (public APIs: ``Object``, ``ObjectKind``,
``DEFAULT_OBJECT_MATERIAL``, ``evolve_room_add_object``,
``evolve_room_remove_object``). 3D viewer 갱신은 caller (app.py) 가
``roomestim_web.viewer.build_room_figure`` 로 위임. D29 lane separation
(web → core, 단방향) 준수.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import gradio as gr

from roomestim import (
    DEFAULT_OBJECT_MATERIAL,
    Object,
    ObjectKind,
    evolve_room_add_object,
    evolve_room_remove_object,
)
from roomestim.model import MaterialLabel, Point3, RoomModel

_LOG = logging.getLogger("roomestim_web.object_add")

_MATERIAL_CHOICES: list[str] = [m.value for m in MaterialLabel]


def _build_add_object_form(kind: ObjectKind) -> dict[str, gr.components.Component]:
    """Build kind-specific input form components.

    - column: anchor (x, y, z) + width/height/depth + material dropdown.
    - door/window: wall_index (int) + anchor (wall-local x, z) + width/height +
      depth=0 (hidden constant) + material dropdown.
    """
    default_material = DEFAULT_OBJECT_MATERIAL[kind].value
    components: dict[str, gr.components.Component] = {}
    if kind == "column":
        components["anchor_x"] = gr.Number(label="anchor x (m)", value=0.0)
        components["anchor_y"] = gr.Number(label="anchor y (m, base z)", value=0.0)
        components["anchor_z"] = gr.Number(label="anchor z (m)", value=0.0)
        components["width_m"] = gr.Number(label="width (m)", value=0.4, minimum=0.01)
        components["height_m"] = gr.Number(label="height (m)", value=2.5, minimum=0.01)
        components["depth_m"] = gr.Number(label="depth (m)", value=0.4, minimum=0.01)
        components["wall_index"] = gr.Number(label="wall_index (column → 비어 둠)", value=None, visible=False)
    else:  # door / window
        components["wall_index"] = gr.Number(label="wall_index (정수)", value=0, precision=0, minimum=0)
        components["anchor_x"] = gr.Number(label="anchor x (wall-local, m)", value=0.0)
        components["anchor_y"] = gr.Number(label="anchor y (보통 0)", value=0.0, visible=False)
        components["anchor_z"] = gr.Number(label="anchor z (wall-local 높이, m)", value=0.0)
        components["width_m"] = gr.Number(label="width (m)", value=0.9 if kind == "door" else 1.2, minimum=0.01)
        components["height_m"] = gr.Number(label="height (m)", value=2.1 if kind == "door" else 1.2, minimum=0.01)
        components["depth_m"] = gr.Number(label="depth (door/window → 0)", value=0.0, visible=False)
    components["material"] = gr.Dropdown(
        choices=_MATERIAL_CHOICES,
        value=default_material,
        label="material",
    )
    return components


def _on_add_object(
    room: RoomModel | None,
    kind: ObjectKind,
    form_data: dict[str, Any],
) -> tuple[RoomModel | None, str]:
    """Parse form_data → Object → evolve_room_add_object → (new_room, status_md).

    Returns (room_unchanged, error_md) on failure.
    """
    if room is None:
        return room, "오류: 먼저 방 스캔 파일을 실행하세요."
    try:
        anchor = Point3(
            x=float(form_data.get("anchor_x", 0.0) or 0.0),
            y=float(form_data.get("anchor_y", 0.0) or 0.0),
            z=float(form_data.get("anchor_z", 0.0) or 0.0),
        )
        width_m = float(form_data.get("width_m", 0.0) or 0.0)
        height_m = float(form_data.get("height_m", 0.0) or 0.0)
        depth_m = float(form_data.get("depth_m", 0.0) or 0.0)
        raw_wall_index = form_data.get("wall_index", None)
        wall_index: int | None
        if kind == "column":
            wall_index = None
        else:
            if raw_wall_index is None or raw_wall_index == "":
                return room, f"오류: {kind} 추가 시 wall_index 가 필요합니다."
            wall_index = int(raw_wall_index)
        raw_material = form_data.get("material") or DEFAULT_OBJECT_MATERIAL[kind].value
        material = MaterialLabel(raw_material)
        obj = Object(
            kind=kind,
            anchor=anchor,
            width_m=width_m,
            height_m=height_m,
            depth_m=depth_m,
            wall_index=wall_index,
            material=material,
        )
        new_room = evolve_room_add_object(room, obj)
    except ValueError as exc:
        _LOG.warning("_on_add_object ValueError: %s", exc)
        return room, f"오류: 객체 추가 실패 — {exc}"
    except Exception as exc:
        _LOG.exception("_on_add_object failed")
        return room, f"오류: 예상치 못한 실패 — {exc}"
    return new_room, f"객체 추가됨: {kind} (총 objects={len(new_room.objects)})"


def _on_remove_object(
    room: RoomModel | None,
    object_index: int,
) -> tuple[RoomModel | None, str]:
    """Call evolve_room_remove_object; return updated room or error msg."""
    if room is None:
        return room, "오류: 먼저 방 스캔 파일을 실행하세요."
    try:
        idx = int(object_index)
    except (TypeError, ValueError):
        return room, f"오류: object_index 가 정수가 아닙니다 ({object_index!r})."
    try:
        new_room = evolve_room_remove_object(room, idx)
    except IndexError as exc:
        _LOG.warning("_on_remove_object IndexError: %s", exc)
        return room, f"오류: index 범위 초과 — {exc}"
    except Exception as exc:
        _LOG.exception("_on_remove_object failed")
        return room, f"오류: 예상치 못한 실패 — {exc}"
    return new_room, f"객체 제거됨 (index={idx}; 총 objects={len(new_room.objects)})"


def _objects_to_rows(room: RoomModel | None) -> list[list[str]]:
    """Return current objects as a Dataframe-compatible list of rows."""
    if room is None:
        return []
    rows: list[list[str]] = []
    for i, obj in enumerate(room.objects):
        anchor_str = f"({obj.anchor.x:.2f}, {obj.anchor.y:.2f}, {obj.anchor.z:.2f})"
        dims_str = f"{obj.width_m:.2f}×{obj.height_m:.2f}×{obj.depth_m:.2f}"
        wall_str = "—" if obj.wall_index is None else str(obj.wall_index)
        rows.append([str(i), str(obj.kind), obj.material.value, anchor_str, dims_str, wall_str])
    return rows


def build_object_add_tab(
    initial_room_state: gr.State,
    on_add: Callable[..., Any],
    on_remove: Callable[..., Any],
) -> dict[str, Any]:
    """Build the Object Add Tab with sub-mode radio + form + Add/Remove buttons.

    Caller (app.py) is responsible for wiring ``on_add`` / ``on_remove`` to the
    Add / Remove button .click() events, since component IDs depend on the host
    Blocks context.

    Returns a dict with component handles so the caller can wire callbacks:
        ``tab``           — gr.Tab context
        ``kind_radio``    — gr.Radio (column/door/window)
        ``form``          — dict[str, gr.components.Component] (current form fields)
        ``add_btn``       — gr.Button Add
        ``object_table``  — gr.Dataframe (current objects)
        ``remove_index``  — gr.Number (index to remove)
        ``remove_btn``    — gr.Button Remove
        ``status_md``     — gr.Markdown change-pending indicator
    """
    with gr.Tab("객체 추가") as tab:
        gr.Markdown(
            "### 객체 추가 (column / door / window)\n"
            "phone-scan 으로 누락된 기둥·문·창문을 추가하세요. column 은 독립적,"
            " door/window 는 벽에 부착 (wall_index 필수)."
        )
        kind_radio = gr.Radio(
            choices=["column", "door", "window"],
            value="column",
            label="객체 종류",
        )

        # Build all input fields once (column-form by default; visibility toggles
        # are simpler than fully dynamic rebuild given Gradio Blocks constraints).
        with gr.Row():
            anchor_x = gr.Number(label="anchor x (m)", value=0.0)
            anchor_y = gr.Number(label="anchor y (m)", value=0.0)
            anchor_z = gr.Number(label="anchor z (m)", value=0.0)
        with gr.Row():
            width_m = gr.Number(label="width (m)", value=0.4, minimum=0.01)
            height_m = gr.Number(label="height (m)", value=2.5, minimum=0.01)
            depth_m = gr.Number(label="depth (m, column only)", value=0.4, minimum=0.0)
        with gr.Row():
            wall_index = gr.Number(
                label="wall_index (door/window 필수, column 은 비어 둠)",
                value=None,
                precision=0,
                minimum=0,
            )
            material = gr.Dropdown(
                choices=_MATERIAL_CHOICES,
                value=DEFAULT_OBJECT_MATERIAL["column"].value,
                label="material",
            )
        add_btn = gr.Button("추가 (Add)", variant="primary")

        gr.Markdown("### 현재 객체 목록")
        object_table = gr.Dataframe(
            headers=["index", "kind", "material", "anchor", "dims (w×h×d)", "wall_index"],
            datatype=["str", "str", "str", "str", "str", "str"],
            col_count=(6, "fixed"),
            interactive=False,
            label="objects",
        )
        with gr.Row():
            remove_index = gr.Number(label="제거할 index", value=0, precision=0, minimum=0)
            remove_btn = gr.Button("제거 (Remove)", variant="secondary")
        status_md = gr.Markdown(value="", visible=False, label="상태")

        # Update material default when kind changes (cheap convenience wiring).
        def _on_kind_change(k: str) -> Any:
            try:
                return gr.update(value=DEFAULT_OBJECT_MATERIAL[k].value)  # type: ignore[index]
            except Exception:
                return gr.update()

        try:
            kind_radio.change(fn=_on_kind_change, inputs=[kind_radio], outputs=[material])
        except Exception:
            _LOG.warning("kind_radio.change wiring failed; material default will be static")

    return {
        "tab": tab,
        "kind_radio": kind_radio,
        "form": {
            "anchor_x": anchor_x,
            "anchor_y": anchor_y,
            "anchor_z": anchor_z,
            "width_m": width_m,
            "height_m": height_m,
            "depth_m": depth_m,
            "wall_index": wall_index,
            "material": material,
        },
        "add_btn": add_btn,
        "object_table": object_table,
        "remove_index": remove_index,
        "remove_btn": remove_btn,
        "status_md": status_md,
    }


__all__ = [
    "build_object_add_tab",
    "_build_add_object_form",
    "_on_add_object",
    "_on_remove_object",
    "_objects_to_rows",
]
