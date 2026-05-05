"""Top-down floor-plan PNG renderer.

matplotlib is imported lazily so the package stays importable without the
``[viz]`` extra installed.
"""

from __future__ import annotations

from pathlib import Path

from roomestim.model import PlacementResult, RoomModel


def render_floorplan_png(
    room: RoomModel,
    placement: PlacementResult | None,
    out_path: Path | str,
) -> None:
    """Render a top-down floor-plan PNG.

    Draws:
    * The floor polygon (walls) as a closed outline.
    * The listener area polygon (filled, semi-transparent).
    * Speaker positions as markers with channel labels (when ``placement`` is
      not None).

    Parameters
    ----------
    room:
        Room geometry to draw.
    placement:
        Speaker placement result. Pass ``None`` to draw room-only.
    out_path:
        Destination file path. Parent directories must exist.
    """
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.patches as mpatches  # noqa: PLC0415
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from matplotlib.patches import Polygon as MplPolygon  # noqa: PLC0415

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_aspect("equal")
    ax.set_xlabel("x (right, m)")
    ax.set_ylabel("z (front, m)")
    ax.set_title(f"Floor plan: {room.name}")

    # -- Floor polygon (walls outline) --
    floor_pts = [(p.x, p.z) for p in room.floor_polygon]
    if floor_pts:
        floor_patch = MplPolygon(
            floor_pts,
            closed=True,
            fill=False,
            edgecolor="black",
            linewidth=2,
        )
        ax.add_patch(floor_patch)

    # -- Listener area (filled) --
    la_pts = [(p.x, p.z) for p in room.listener_area.polygon]
    if la_pts:
        la_patch = MplPolygon(
            la_pts,
            closed=True,
            facecolor="steelblue",
            alpha=0.25,
            edgecolor="steelblue",
            linewidth=1,
            label="listener area",
        )
        ax.add_patch(la_patch)

    # -- Centroid marker --
    cx, cz = room.listener_area.centroid.x, room.listener_area.centroid.z
    ax.plot(cx, cz, "b+", markersize=10, label="centroid")

    # -- Speakers --
    if placement is not None:
        for sp in placement.speakers:
            sx, sz = sp.position.x, sp.position.z
            ax.plot(sx, sz, "r^", markersize=8)
            ax.annotate(
                str(sp.channel),
                (sx, sz),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=8,
                color="darkred",
            )
        # dummy handle for legend
        speaker_handle = mpatches.Patch(color="red", label="speakers")
        ax.legend(handles=[speaker_handle])

    # Auto-scale with a small margin
    all_x = [p.x for p in room.floor_polygon]
    all_z = [p.z for p in room.floor_polygon]
    if all_x and all_z:
        margin = 0.5
        ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
        ax.set_ylim(min(all_z) - margin, max(all_z) + margin)

    fig.tight_layout()
    fig.savefig(str(out_path), dpi=150)
    plt.close(fig)


__all__ = ["render_floorplan_png"]
