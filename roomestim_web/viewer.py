"""roomestim_web.viewer — Plotly 3D figure builder for room + speaker layout.

Design spec §9. Plotly is lazy-imported so this module loads without plotly
installed.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import plotly.graph_objects as go

    from roomestim.model import PlacementResult, RoomModel


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

    # ── Speakers — one Scatter3d with N markers ──────────────────────────────
    speakers = layout.speakers
    sx = [s.position.x for s in speakers]
    sy = [s.position.y for s in speakers]
    sz = [s.position.z for s in speakers]
    s_colors = [speaker_color(s.channel) for s in speakers]
    s_text = [f"Ch{s.channel}" for s in speakers]

    traces.append(
        go.Scatter3d(
            x=sx,
            y=sy,
            z=sz,
            mode="markers",
            marker=dict(size=8, symbol="diamond", color=s_colors),
            text=s_text,
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
