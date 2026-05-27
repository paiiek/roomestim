"""roomestim_web.viewer — Plotly 3D figure builder for room + speaker layout.

Design spec §9. Plotly is lazy-imported so this module loads without plotly
installed.

v0.14-web.0 (ADR 0034 §A): ``room.objects`` rendering added — column = 5 face
Mesh3d (4 side + 1 top); door/window = sub-quad on host wall plane with
opacity (door=1.0 opaque; window=0.3 semi-transparent).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import plotly.graph_objects as go

    from roomestim.model import Object, PlacementResult, RoomModel, Surface


def build_room_figure(
    room: "RoomModel",
    layout: "PlacementResult",
) -> "go.Figure":
    """Build a Plotly 3D figure from a RoomModel and PlacementResult.

    Args:
        room: Parsed room model with surfaces.
        layout: Speaker placement result.

    Returns:
        plotly.graph_objects.Figure ready for display.
    """
    import plotly.graph_objects as go  # lazy import

    from roomestim_web.material_palette import MATERIAL_PALETTE, speaker_color

    traces: list[Any] = []
    seen_materials: set[str] = set()

    # ── Room mesh — one Mesh3d per surface ───────────────────────────────────
    for surface in room.surfaces:
        polygon = surface.polygon
        n = len(polygon)

        xs = [p.x for p in polygon]
        ys = [p.y for p in polygon]
        zs = [p.z for p in polygon]

        # Fan triangulation from v0
        i_idx: list[int] = []
        j_idx: list[int] = []
        k_idx: list[int] = []
        for t in range(1, n - 1):
            i_idx.append(0)
            j_idx.append(t)
            k_idx.append(t + 1)

        mat_name = surface.material.value
        color = MATERIAL_PALETTE[surface.material]
        first_occurrence = mat_name not in seen_materials
        seen_materials.add(mat_name)

        traces.append(
            go.Mesh3d(
                x=xs,
                y=ys,
                z=zs,
                i=i_idx,
                j=j_idx,
                k=k_idx,
                color=color,
                opacity=0.7,
                flatshading=True,
                showscale=False,
                name=mat_name,
                showlegend=first_occurrence,
            )
        )

    # ── Objects (column/door/window) — ADR 0034 §A / v0.14-web.0 ─────────────
    try:
        for obj in getattr(room, "objects", []):
            obj_traces = _build_object_traces(obj, room, MATERIAL_PALETTE)
            traces.extend(obj_traces)
    except Exception:
        # Defensive: never block speaker/listener rendering on object failures.
        pass

    # ── Speakers — one Scatter3d with N markers ──────────────────────────────
    speakers = layout.speakers
    sx = [s.position.x for s in speakers]
    sy = [s.position.y for s in speakers]
    sz = [s.position.z for s in speakers]
    s_colors = [speaker_color(s.channel) for s in speakers]
    s_text = [f"Ch{s.channel}" for s in speakers]
    # v0.15-web.0 (ADR 0036 §B): customdata carries the channel so a 3D click
    # can identify the selected speaker (channel dropdown is the primary path).
    s_customdata = [[s.channel] for s in speakers]

    traces.append(
        go.Scatter3d(
            x=sx,
            y=sy,
            z=sz,
            mode="markers",
            marker=dict(size=8, symbol="diamond", color=s_colors),
            text=s_text,
            customdata=s_customdata,
            name="Speakers",
        )
    )

    # ── Listener — one Scatter3d at centroid ─────────────────────────────────
    # Listener-frame floor is at y=0 by adapter convention, so ListenerArea
    # head height (height_m) maps directly to the absolute y coordinate.
    centroid = room.listener_area.centroid
    height_m = room.listener_area.height_m

    traces.append(
        go.Scatter3d(
            x=[centroid.x],
            y=[height_m],
            z=[centroid.z],  # Point2.z maps to z-axis (front)
            mode="markers",
            marker=dict(size=12, symbol="cross", color="#000000"),
            name="Listener",
        )
    )

    # ── Aim direction lines — one Scatter3d with None separators ─────────────
    lx: list[float | None] = []
    ly: list[float | None] = []
    lz: list[float | None] = []

    for s in speakers:
        lx.extend([s.position.x, centroid.x, None])
        ly.extend([s.position.y, height_m, None])
        lz.extend([s.position.z, centroid.z, None])  # centroid.z → z-axis

    traces.append(
        go.Scatter3d(
            x=lx,
            y=ly,
            z=lz,
            mode="lines",
            line=dict(width=2, color="#888888", dash="dot"),
            name="Aim direction",
        )
    )

    fig = go.Figure(data=traces)
    fig.update_layout(
        scene=dict(
            camera=dict(
                eye=dict(x=1.5, y=1.2, z=1.5),
                center=dict(x=0.0, y=0.5, z=0.0),
                up=dict(x=0.0, y=1.0, z=0.0),
            ),
            aspectmode="data",
            xaxis_title="x (m, right)",
            yaxis_title="y (m, up)",
            zaxis_title="z (m, front)",
        ),
        legend=dict(orientation="v", x=1.02, y=1.0),
        margin=dict(l=0, r=0, t=30, b=0),
        title="Room geometry + speaker placement",
    )
    return fig


def _build_object_traces(
    obj: "Object",
    room: "RoomModel",
    palette: dict[Any, str],
) -> list[Any]:
    """Build Plotly Mesh3d traces for a single Object (column/door/window).

    column → 5 face (4 side + top) Mesh3d (10 triangles fan-tris); 8 vertices.
    door/window → sub-quad on host wall plane (2 triangles); door opacity=1.0,
    window opacity=0.3.

    Returns a list of go.Mesh3d traces (may be empty on geometry errors).
    """
    import plotly.graph_objects as go  # lazy import

    color = palette.get(obj.material, "#C0C0C0")
    if obj.kind == "column":
        return _column_traces(obj, color, go)
    if obj.kind in ("door", "window"):
        return _wall_attached_traces(obj, room, color, go)
    return []


def _column_traces(obj: "Object", color: str, go: Any) -> list[Any]:
    """5-face Mesh3d for a column: 4 side + top, fan-triangulated."""
    cx, cy, cz = obj.anchor.x, obj.anchor.y, obj.anchor.z
    w = obj.width_m
    d = obj.depth_m if obj.depth_m > 0 else obj.width_m
    h = obj.height_m
    # 8 vertices: bottom 4 (CCW from x-d corner) + top 4
    half_w, half_d = w / 2.0, d / 2.0
    base_y = cy
    top_y = cy + h
    xs = [
        cx - half_w, cx + half_w, cx + half_w, cx - half_w,  # base
        cx - half_w, cx + half_w, cx + half_w, cx - half_w,  # top
    ]
    ys = [base_y, base_y, base_y, base_y, top_y, top_y, top_y, top_y]
    zs = [
        cz - half_d, cz - half_d, cz + half_d, cz + half_d,  # base
        cz - half_d, cz - half_d, cz + half_d, cz + half_d,  # top
    ]
    # 10 triangles: 4 sides (2 tri each = 8) + top (2 tri); bottom skipped (floor).
    i_idx = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    j_idx = [1, 4, 2, 5, 3, 6, 0, 7, 5, 6]
    k_idx = [5, 5, 6, 6, 7, 7, 4, 4, 6, 7]
    return [
        go.Mesh3d(
            x=xs,
            y=ys,
            z=zs,
            i=i_idx,
            j=j_idx,
            k=k_idx,
            color=color,
            opacity=1.0,
            flatshading=True,
            showscale=False,
            name=f"column ({obj.material.value})",
            showlegend=False,
        )
    ]


def _wall_attached_traces(
    obj: "Object",
    room: "RoomModel",
    color: str,
    go: Any,
) -> list[Any]:
    """Sub-quad on the host wall plane for door/window.

    Maps wall-local (anchor.x, anchor.z) + (width, height) to absolute Point3 via
    the wall's polygon[0]→polygon[1] horizontal edge as the local x-axis and
    z as vertical.
    """
    if obj.wall_index is None:
        return []
    # wall_index is indexed against the WALLS-ONLY surface list (mirroring the
    # predictor's _objects_to_wall_alpha_overrides), NOT the full surfaces
    # array. See ADR 0037. Out-of-range still returns [] (robustness contract).
    walls = [s for s in room.surfaces if s.kind == "wall"]
    if not (0 <= obj.wall_index < len(walls)):
        return []
    wall: "Surface" = walls[obj.wall_index]
    if len(wall.polygon) < 4:
        return []
    p0 = wall.polygon[0]
    p1 = wall.polygon[1]
    # Local x-axis along p0→p1 (horizontal edge), local y is world +y.
    ex_x = p1.x - p0.x
    ex_z = p1.z - p0.z
    ex_len = (ex_x * ex_x + ex_z * ex_z) ** 0.5
    if ex_len <= 1e-9:
        return []
    ux_x = ex_x / ex_len
    ux_z = ex_z / ex_len
    ax = obj.anchor.x  # wall-local x offset along the edge
    az = obj.anchor.z  # wall-local vertical offset from the wall base
    w = obj.width_m
    h = obj.height_m
    # 4 corners (bottom-left, bottom-right, top-right, top-left) in world space
    base_x0 = p0.x + ux_x * ax
    base_z0 = p0.z + ux_z * ax
    base_y0 = p0.y + az
    xs = [
        base_x0,
        base_x0 + ux_x * w,
        base_x0 + ux_x * w,
        base_x0,
    ]
    ys = [base_y0, base_y0, base_y0 + h, base_y0 + h]
    zs = [
        base_z0,
        base_z0 + ux_z * w,
        base_z0 + ux_z * w,
        base_z0,
    ]
    opacity = 0.3 if obj.kind == "window" else 1.0
    return [
        go.Mesh3d(
            x=xs,
            y=ys,
            z=zs,
            i=[0, 0],
            j=[1, 2],
            k=[2, 3],
            color=color,
            opacity=opacity,
            flatshading=True,
            showscale=False,
            name=f"{obj.kind} ({obj.material.value})",
            showlegend=False,
        )
    ]
