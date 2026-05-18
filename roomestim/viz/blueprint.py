"""roomestim.viz.blueprint — 2D top-down blueprint renderer (D41 + ADR 0032).

Purpose
-------
Renders a top-down architectural blueprint of a RoomModel as PNG (300 dpi
raster) or SVG (vector, scalable for CAD import). Used by the web Blueprint
Tab and Setup PDF page 2.

Coordinate convention (D41)
---------------------------
RoomModel internal frame: x=right, y=up, z=front (right-handed).
Blueprint projection: (x, z) plane — x → screen x, z → screen y (north-up).
Result: room entrance (z=0) appears at the *bottom* of the figure; +z (forward)
points upward, matching architectural drawing convention where north is up.
``ax.set_ylabel("z (forward, m, north-up)")`` makes this explicit per D41.

Determinism (ADR 0032 §D)
--------------------------
matplotlib Agg backend + DejaVu Sans (ships with matplotlib) + no random
seeds → PNG output is byte-equal across identical inputs. This enables a
byte-equal regression lock in ``tests/test_viz_blueprint.py``.

Layering
--------
matplotlib is lazy-imported (``[viz]`` extra). The module is importable
without matplotlib installed. ``roomestim.model`` is the only roomestim dep.

References: D41, ADR 0032.
"""

from __future__ import annotations

# ADR 0032 §D + v0.16.1 MEDIUM-2 closure: force Agg backend at IMPORT time
# so that even import-only consumers cannot break PNG byte-equal determinism.
# `force=True` is required when another module has already initialised a
# non-Agg backend in the same process (e.g., test runners with `--mpl`).
try:
    import matplotlib  # noqa: PLC0415
    if matplotlib.get_backend().lower() != "agg":
        matplotlib.use("Agg", force=True)
except ImportError:
    pass  # matplotlib is a [viz] extra; render_blueprint() will surface later

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from roomestim.model import PlacementResult, RoomModel

if TYPE_CHECKING:
    import matplotlib.axes


# --------------------------------------------------------------------------- #
# Internal geometry helpers
# --------------------------------------------------------------------------- #


def _bbox_from_floor(
    room: RoomModel,
) -> tuple[float, float, float, float]:
    """Return (xmin, zmin, xmax, zmax) bounding box with 1 m padding.

    Padding provides space for north-arrow + scale-bar annotations that live
    outside the floor outline.
    """
    xs = [p.x for p in room.floor_polygon]
    zs = [p.z for p in room.floor_polygon]
    if not xs:
        return (-1.0, -1.0, 1.0, 1.0)
    pad = 1.0
    return (min(xs) - pad, min(zs) - pad, max(xs) + pad, max(zs) + pad)


# --------------------------------------------------------------------------- #
# Drawing layers (ADR 0032 §C)
# --------------------------------------------------------------------------- #


def _draw_walls(ax: "matplotlib.axes.Axes", room: RoomModel) -> None:
    """Layer 1+2: floor polygon outline (black 1.5 pt) + wall labels at midpoints."""
    from matplotlib.patches import Polygon as MplPolygon  # noqa: PLC0415

    floor_pts = [(p.x, p.z) for p in room.floor_polygon]
    if not floor_pts:
        return

    floor_patch = MplPolygon(
        floor_pts,
        closed=True,
        fill=False,
        edgecolor="black",
        linewidth=1.5,
    )
    ax.add_patch(floor_patch)

    # Wall labels: W0, W1, … at midpoints of consecutive floor edges
    n = len(floor_pts)
    for i in range(n):
        x0, z0 = floor_pts[i]
        x1, z1 = floor_pts[(i + 1) % n]
        mx, mz = (x0 + x1) / 2.0, (z0 + z1) / 2.0
        ax.annotate(
            f"W{i}",
            (mx, mz),
            fontsize=7,
            ha="center",
            va="center",
            color="dimgray",
            fontfamily="DejaVu Sans",
        )


def _draw_listener(ax: "matplotlib.axes.Axes", room: RoomModel) -> None:
    """Layer 3: listener area polygon (semi-transparent green α=0.3) + centroid cross."""
    from matplotlib.patches import Polygon as MplPolygon  # noqa: PLC0415

    la_pts = [(p.x, p.z) for p in room.listener_area.polygon]
    if la_pts:
        la_patch = MplPolygon(
            la_pts,
            closed=True,
            facecolor="green",
            alpha=0.3,
            edgecolor="green",
            linewidth=1.0,
            label="listener area",
        )
        ax.add_patch(la_patch)

    # Centroid cross
    cx = room.listener_area.centroid.x
    cz = room.listener_area.centroid.z
    ax.plot(cx, cz, "+", color="darkgreen", markersize=10, markeredgewidth=1.5)


def _draw_speakers(
    ax: "matplotlib.axes.Axes",
    placement: PlacementResult | None,
) -> None:
    """Layer 4: red dots + channel labels for each placed speaker."""
    if placement is None:
        return

    channel_names = ["L", "R", "C", "LS", "RS", "LB", "RB", "LF", "RF"]

    for sp in placement.speakers:
        sx, sz = sp.position.x, sp.position.z
        ax.plot(sx, sz, "o", color="red", markersize=6, zorder=5)
        ch_idx = sp.channel - 1
        label = channel_names[ch_idx] if 0 <= ch_idx < len(channel_names) else str(sp.channel)
        ax.annotate(
            label,
            (sx, sz),
            textcoords="offset points",
            xytext=(5, 4),
            fontsize=7,
            color="darkred",
            fontfamily="DejaVu Sans",
            zorder=6,
        )


def _draw_dimensions(ax: "matplotlib.axes.Axes", room: RoomModel) -> None:
    """Layer 5: dimension arrow for the longest wall edge."""
    floor_pts = [(p.x, p.z) for p in room.floor_polygon]
    if len(floor_pts) < 2:
        return

    # Find longest edge
    n = len(floor_pts)
    best_len = -1.0
    best_i = 0
    for i in range(n):
        x0, z0 = floor_pts[i]
        x1, z1 = floor_pts[(i + 1) % n]
        length = ((x1 - x0) ** 2 + (z1 - z0) ** 2) ** 0.5
        if length > best_len:
            best_len = length
            best_i = i

    x0, z0 = floor_pts[best_i]
    x1, z1 = floor_pts[(best_i + 1) % n]
    mx, mz = (x0 + x1) / 2.0, (z0 + z1) / 2.0

    ax.annotate(
        "",
        xy=(x1, z1),
        xytext=(x0, z0),
        arrowprops=dict(arrowstyle="<->", color="navy", lw=1.0),
    )
    ax.text(
        mx,
        mz,
        f"{best_len:.2f} m",
        ha="center",
        va="bottom",
        fontsize=7,
        color="navy",
        fontfamily="DejaVu Sans",
    )


def _draw_north_arrow(
    ax: "matplotlib.axes.Axes",
    xmin: float,
    xmax: float,
    zmax: float,
) -> None:
    """Layer 6a: north arrow in top-left corner.

    +z is north (forward) per D41 coordinate convention.
    """
    nx = xmin + (xmax - xmin) * 0.08
    nz = zmax - 0.3
    ax.annotate(
        "",
        xy=(nx, nz + 0.5),
        xytext=(nx, nz),
        arrowprops=dict(arrowstyle="->", color="black", lw=1.2),
    )
    ax.text(
        nx,
        nz + 0.6,
        "N",
        ha="center",
        va="bottom",
        fontsize=8,
        fontweight="bold",
        color="black",
        fontfamily="DejaVu Sans",
    )


def _draw_scale_bar(
    ax: "matplotlib.axes.Axes",
    xmax: float,
    zmin: float,
) -> None:
    """Layer 6b: 1 m scale bar in bottom-right corner."""
    sx0 = xmax - 1.3
    sx1 = sx0 + 1.0
    sz = zmin + 0.2
    ax.plot([sx0, sx1], [sz, sz], "-", color="black", lw=2.0)
    ax.plot([sx0, sx0], [sz - 0.05, sz + 0.05], "-", color="black", lw=1.5)
    ax.plot([sx1, sx1], [sz - 0.05, sz + 0.05], "-", color="black", lw=1.5)
    ax.text(
        (sx0 + sx1) / 2.0,
        sz + 0.1,
        "1 m",
        ha="center",
        va="bottom",
        fontsize=7,
        color="black",
        fontfamily="DejaVu Sans",
    )


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def render_blueprint(
    room: RoomModel,
    placement: PlacementResult | None,
    out_path: Path | str,
    *,
    fmt: Literal["png", "svg"] = "png",
    dpi: int = 300,
    show_dimensions: bool = True,
    show_north_arrow: bool = True,
    show_scale_bar: bool = True,
) -> None:
    """Render a 2D top-down blueprint and save to *out_path*.

    Content layers (ADR 0032 §C):
    1. Floor polygon outline (black 1.5 pt)
    2. Wall labels W0/W1/… at edge midpoints
    3. Listener area (semi-transparent green fill α=0.3)
    4. Speaker positions (red dots + L/R/C/LS/RS channel labels)
    5. Dimension arrow on the longest wall edge
    6. North arrow (top-left) + 1 m scale bar (bottom-right)

    Coordinate convention (D41): blueprint x = RoomModel x (right),
    blueprint y = RoomModel z (forward, north-up).

    Parameters
    ----------
    room:
        Room geometry.
    placement:
        Speaker placement. Pass ``None`` for room-only rendering.
    out_path:
        Destination file. Parent directory must exist.
    fmt:
        ``"png"`` (300 dpi raster) or ``"svg"`` (vector).
    dpi:
        Resolution for raster output (ignored for SVG).
    show_dimensions:
        Draw longest-wall dimension arrow.
    show_north_arrow:
        Draw north arrow (+z direction) in top-left corner.
    show_scale_bar:
        Draw 1 m scale bar in bottom-right corner.
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415

    xmin, zmin, xmax, zmax = _bbox_from_floor(room)

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_aspect("equal")
    ax.set_xlabel("x (right, m)", fontfamily="DejaVu Sans")
    ax.set_ylabel("z (forward, m, north-up)", fontfamily="DejaVu Sans")
    ax.set_title(f"Blueprint: {room.name}", fontfamily="DejaVu Sans")

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(zmin, zmax)

    _draw_walls(ax, room)
    _draw_listener(ax, room)
    _draw_speakers(ax, placement)

    if show_dimensions:
        _draw_dimensions(ax, room)
    if show_north_arrow:
        _draw_north_arrow(ax, xmin, xmax, zmax)
    if show_scale_bar:
        _draw_scale_bar(ax, xmax, zmin)

    fig.tight_layout()
    fig.savefig(str(out_path), format=fmt, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


__all__ = ["render_blueprint"]
