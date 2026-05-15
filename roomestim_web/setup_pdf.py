"""roomestim_web.setup_pdf — Speaker setup card PDF generator (v0.12-web P13d).

Generates a single PDF with one page per placed speaker. Uses reportlab,
which is lazy-imported inside build_setup_pdf so the module is importable
without reportlab installed.

Layout per design §8.1; ASCII mini-map per §8.2.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # no top-level heavy imports

__all__ = ["build_setup_pdf"]


# --------------------------------------------------------------------------- #
# ASCII mini-map helpers
# --------------------------------------------------------------------------- #

_MAP_COLS = 24
_MAP_ROWS = 10


def _ascii_minimap(
    floor_polygon: list[object],
    speakers: list[object],
    active_idx: int,
    listener_xz: tuple[float, float],
) -> list[str]:
    """Return _MAP_ROWS lines of _MAP_COLS chars representing the floor plan.

    Cells:
      * = this speaker
      o = other speakers
      L = listener centroid
      + = floor polygon corner
      . = interior / empty
      ' ' = exterior
    """
    # Extract (x, z) from floor polygon Points
    corners = [(float(p.x), float(p.z)) for p in floor_polygon]  # type: ignore[attr-defined]
    if not corners:
        return [" " * _MAP_COLS] * _MAP_ROWS

    xs = [c[0] for c in corners]
    zs = [c[1] for c in corners]
    x_min, x_max = min(xs), max(xs)
    z_min, z_max = min(zs), max(zs)
    x_span = x_max - x_min or 1.0
    z_span = z_max - z_min or 1.0

    def to_cell(wx: float, wz: float) -> tuple[int, int]:
        col = int((wx - x_min) / x_span * (_MAP_COLS - 1))
        row = int((wz - z_min) / z_span * (_MAP_ROWS - 1))
        return max(0, min(_MAP_COLS - 1, col)), max(0, min(_MAP_ROWS - 1, row))

    grid = [[" " for _ in range(_MAP_COLS)] for _ in range(_MAP_ROWS)]

    # Mark corners
    for cx, cz in corners:
        col, row = to_cell(cx, cz)
        grid[row][col] = "+"

    # Mark listener
    lx, lz = listener_xz
    lc, lr = to_cell(lx, lz)
    grid[lr][lc] = "L"

    # Mark speakers
    for i, spk in enumerate(speakers):
        sx = float(spk.position.x)  # type: ignore[attr-defined]
        sz = float(spk.position.z)  # type: ignore[attr-defined]
        sc, sr = to_cell(sx, sz)
        if i == active_idx:
            grid[sr][sc] = "*"
        else:
            if grid[sr][sc] == " ":
                grid[sr][sc] = "o"

    return ["".join(row) for row in grid]


# --------------------------------------------------------------------------- #
# Per-speaker geometry computations
# --------------------------------------------------------------------------- #


def _speaker_geometry(
    position: object,
    listener_xz: tuple[float, float],
    listener_height_m: float,
    floor_polygon: list[object],
) -> dict[str, float]:
    """Return listener-relative az_deg, el_deg, dist_m, nearest_corner_m.

    Origin = listener centroid (x = ``listener_xz[0]``, z = ``listener_xz[1]``,
    y = ``listener_height_m``); axes match listener-frame convention (z=front,
    x=right, y=up).
    """
    px = float(position.x)  # type: ignore[attr-defined]
    py = float(position.y)  # type: ignore[attr-defined]
    pz = float(position.z)  # type: ignore[attr-defined]
    lx, lz = listener_xz
    dx = px - lx
    dy = py - listener_height_m
    dz = pz - lz

    az_deg = math.degrees(math.atan2(dx, dz))
    horiz = math.sqrt(dx * dx + dz * dz)
    el_deg = math.degrees(math.atan2(dy, horiz)) if horiz > 0 else (
        90.0 if dy > 0 else -90.0
    )
    dist_m = math.sqrt(dx * dx + dy * dy + dz * dz)

    nearest = float("inf")
    for p in floor_polygon:
        ndx = px - float(p.x)  # type: ignore[attr-defined]
        ndz = pz - float(p.z)  # type: ignore[attr-defined]
        d = math.sqrt(ndx * ndx + ndz * ndz)
        if d < nearest:
            nearest = d

    return {
        "az_deg": az_deg,
        "el_deg": el_deg,
        "dist_m": dist_m,
        "nearest_corner_m": nearest if math.isfinite(nearest) else 0.0,
    }


def _aim_str(aim: object) -> str:
    """Return human-readable aim direction string.

    ``aim`` is a direction vector (NOT an absolute target point), so az/el are
    derived directly from its components without listener offset.
    """
    if aim is None:
        return "(towards listener)"
    ax = float(aim.x)  # type: ignore[attr-defined]
    ay = float(aim.y)  # type: ignore[attr-defined]
    az = float(aim.z)  # type: ignore[attr-defined]
    aim_az = math.degrees(math.atan2(ax, az))
    horiz = math.sqrt(ax * ax + az * az)
    aim_el = math.degrees(math.atan2(ay, horiz)) if horiz > 0 else 0.0
    return f"az {aim_az:.1f}° / el {aim_el:.1f}°"


# --------------------------------------------------------------------------- #
# Main PDF builder
# --------------------------------------------------------------------------- #


def build_setup_pdf(
    layout: object,
    room: object,
    out_path: str | Path,
    *,
    input_filename: str = "",
    roomestim_version: str = "",
) -> Path:
    """Write a reportlab PDF: 1 page per speaker, A4, 20 mm margins.

    Returns out_path as a Path.
    """
    # Lazy imports
    from reportlab.lib.pagesizes import A4  # type: ignore[import]
    from reportlab.lib.units import mm  # type: ignore[import]
    from reportlab.pdfgen.canvas import Canvas  # type: ignore[import]

    out_path = Path(out_path)
    page_w, page_h = A4  # 210×297 mm in points
    margin = 20 * mm

    # Access room/layout fields
    floor_polygon = room.floor_polygon  # type: ignore[attr-defined]
    ceiling_h = float(room.ceiling_height_m)  # type: ignore[attr-defined]
    listener_height_m = float(room.listener_area.height_m)  # type: ignore[attr-defined]
    listener_xz = (
        float(room.listener_area.centroid.x),  # type: ignore[attr-defined]
        float(room.listener_area.centroid.z),  # type: ignore[attr-defined]
    )
    speakers = layout.speakers  # type: ignore[attr-defined]
    algorithm = layout.target_algorithm  # type: ignore[attr-defined]

    canvas = Canvas(str(out_path), pagesize=A4)

    for i, spk in enumerate(speakers):
        geom = _speaker_geometry(spk.position, listener_xz, listener_height_m, floor_polygon)
        aim_txt = _aim_str(spk.aim_direction)
        map_lines = _ascii_minimap(floor_polygon, speakers, i, listener_xz)

        # ── Header ────────────────────────────────────────────────────────────
        y = page_h - margin
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawString(margin, y, f"Speaker Setup Card — Channel {spk.channel}")
        y -= 18

        canvas.setFont("Helvetica", 9)
        meta_parts = []
        if input_filename:
            meta_parts.append(f"Source: {input_filename}")
        meta_parts.append(f"Algorithm: {algorithm}")
        if roomestim_version:
            meta_parts.append(f"roomestim v{roomestim_version}")
        canvas.drawString(margin, y, "  |  ".join(meta_parts))
        y -= 6

        # Horizontal rule
        canvas.setLineWidth(0.5)
        canvas.line(margin, y, page_w - margin, y)
        y -= 16

        # ── Position fields ────────────────────────────────────────────────────
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(margin, y, "Position")
        y -= 14

        canvas.setFont("Helvetica", 10)
        fields = [
            ("Azimuth",        f"{geom['az_deg']:.1f}°"),
            ("Elevation",      f"{geom['el_deg']:.1f}°"),
            ("Distance",       f"{geom['dist_m']:.2f} m"),
            ("Nearest corner", f"{geom['nearest_corner_m']:.2f} m"),
            ("Aim direction",  aim_txt),
            ("Ceiling height", f"{ceiling_h:.2f} m"),
            ("Listener height",f"{listener_height_m:.2f} m"),
            ("X / Y / Z",      f"{spk.position.x:.2f} / {spk.position.y:.2f} / {spk.position.z:.2f} m"),
        ]
        col_w = (page_w - 2 * margin) / 2
        for label, value in fields:
            canvas.setFont("Helvetica-Bold", 9)
            canvas.drawString(margin, y, f"{label}:")
            canvas.setFont("Helvetica", 9)
            canvas.drawString(margin + col_w * 0.4, y, value)
            y -= 13

        y -= 8
        # Horizontal rule
        canvas.line(margin, y, page_w - margin, y)
        y -= 14

        # ── ASCII mini-map ─────────────────────────────────────────────────────
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(margin, y, "Floor plan (top view, z=front)")
        y -= 12

        canvas.setFont("Courier", 8)
        for line in map_lines:
            canvas.drawString(margin, y, line)
            y -= 10

        y -= 6
        canvas.setFont("Helvetica", 7)
        canvas.drawString(margin, y, "* this speaker   o other speakers   L listener   + corner")

        # ── Footer ─────────────────────────────────────────────────────────────
        canvas.setFont("Helvetica", 7)
        canvas.drawString(
            margin,
            margin,
            f"Speaker {i + 1} of {len(speakers)}  —  roomestim setup card",
        )
        canvas.drawRightString(
            page_w - margin,
            margin,
            f"ch{spk.channel}",
        )

        canvas.showPage()

    canvas.save()
    return out_path
