"""roomestim_web.report — Acoustic report builder (v0.12-web P13d).

Computes RT60 (Sabine + Eyring, single-band and per-octave) from a RoomModel
and builds Plotly charts for the Gradio UI. Plotly is lazy-imported inside
chart-building functions so the module is importable without plotly installed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from roomestim.model import MaterialLabel, RoomModel

if TYPE_CHECKING:
    import plotly.graph_objects as go  # type: ignore[import-not-found]

__all__ = [
    "AcousticReport",
    "build_acoustic_report",
    "build_absorption_distribution_chart",
    "build_rt60_bar_chart",
]

# --------------------------------------------------------------------------- #
# Helpers — volume and per-surface areas (no external deps beyond shapely)
# --------------------------------------------------------------------------- #

_OCTAVE_BANDS = (125, 250, 500, 1000, 2000, 4000)


def _polygon_area_3d(pts: list[Any]) -> float:
    """Newell's method: area of a planar polygon in 3D."""
    n = len(pts)
    nx = ny = nz = 0.0
    for i in range(n):
        j = (i + 1) % n
        nx += (pts[i].y - pts[j].y) * (pts[i].z + pts[j].z)
        ny += (pts[i].z - pts[j].z) * (pts[i].x + pts[j].x)
        nz += (pts[i].x - pts[j].x) * (pts[i].y + pts[j].y)
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def _shoelace_2d(coords: list[tuple[float, float]]) -> float:
    """Signed shoelace area for 2D polygon; returns absolute value."""
    n = len(coords)
    acc = 0.0
    for i in range(n):
        j = (i + 1) % n
        acc += coords[i][0] * coords[j][1]
        acc -= coords[j][0] * coords[i][1]
    return abs(acc) * 0.5


def _room_volume(room: RoomModel) -> float:
    floor_coords = [(p.x, p.z) for p in room.floor_polygon]
    floor_area = _shoelace_2d(floor_coords)
    return floor_area * room.ceiling_height_m


def _surface_areas_by_material(room: RoomModel) -> dict[MaterialLabel, float]:
    from collections import defaultdict

    areas: dict[MaterialLabel, float] = defaultdict(float)
    for surf in room.surfaces:
        areas[surf.material] += _polygon_area_3d(surf.polygon)
    return dict(areas)


# --------------------------------------------------------------------------- #
# AcousticReport dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AcousticReport:
    """Frozen dataclass carrying all acoustic analysis results."""

    sabine_rt60_500hz_s: float
    sabine_rt60_per_band_s: dict[int, float]
    eyring_rt60_500hz_s: float
    eyring_rt60_per_band_s: dict[int, float]
    surface_absorption_500hz: list[tuple[int, MaterialLabel, float, float]]
    volume_m3: float
    total_surface_area_m2: float

    def to_json_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for gr.JSON."""
        return {
            "sabine_rt60_500hz_s": self.sabine_rt60_500hz_s,
            "sabine_rt60_per_band_s": {
                str(k): v for k, v in self.sabine_rt60_per_band_s.items()
            },
            "eyring_rt60_500hz_s": self.eyring_rt60_500hz_s,
            "eyring_rt60_per_band_s": {
                str(k): v for k, v in self.eyring_rt60_per_band_s.items()
            },
            "volume_m3": self.volume_m3,
            "total_surface_area_m2": self.total_surface_area_m2,
            "surface_absorption_500hz": [
                {
                    "surface_idx": idx,
                    "material": mat.value,
                    "area_m2": area,
                    "absorption_contribution_sabins": sabins,
                }
                for idx, mat, area, sabins in self.surface_absorption_500hz
            ],
        }


# --------------------------------------------------------------------------- #
# build_acoustic_report
# --------------------------------------------------------------------------- #


def build_acoustic_report(room: RoomModel) -> AcousticReport:
    """Compute RT60 (Sabine + Eyring, single + octave) from a RoomModel.

    Derives volume via shoelace floor-polygon area × ceiling_height_m.
    Surface areas aggregated via Newell's method on each polygon.
    """
    from roomestim.reconstruct.materials import (
        eyring_rt60,
        eyring_rt60_per_band,
        sabine_rt60,
        sabine_rt60_per_band,
    )

    volume_m3 = _room_volume(room)
    agg_areas = _surface_areas_by_material(room)
    total_surface_area_m2 = sum(agg_areas.values())

    sab_500 = sabine_rt60(volume_m3, agg_areas)
    sab_bands = sabine_rt60_per_band(volume_m3, agg_areas)
    eyr_500 = eyring_rt60(volume_m3, agg_areas)
    eyr_bands = eyring_rt60_per_band(volume_m3, agg_areas)

    # Per-surface absorption at 500 Hz.
    # Use Surface.absorption_500hz to honour adapter-emitted per-surface overrides
    # (e.g., ace_challenge MISC_SOFT live-alpha synthesis). The aggregate Sabine /
    # Eyring values above still go through MaterialAbsorption table because the
    # core predictors are keyed by MaterialLabel; per-surface overrides only
    # affect this chart-input list, not the aggregate RT60.
    surface_absorption: list[tuple[int, MaterialLabel, float, float]] = []
    for idx, surf in enumerate(room.surfaces):
        area = _polygon_area_3d(surf.polygon)
        sabins = area * surf.absorption_500hz
        surface_absorption.append((idx, surf.material, area, sabins))

    return AcousticReport(
        sabine_rt60_500hz_s=sab_500,
        sabine_rt60_per_band_s=sab_bands,
        eyring_rt60_500hz_s=eyr_500,
        eyring_rt60_per_band_s=eyr_bands,
        surface_absorption_500hz=surface_absorption,
        volume_m3=volume_m3,
        total_surface_area_m2=total_surface_area_m2,
    )


# --------------------------------------------------------------------------- #
# Chart builders
# --------------------------------------------------------------------------- #


def build_rt60_bar_chart(report: AcousticReport) -> "go.Figure":
    """Plotly grouped bar chart: octave bands × Sabine/Eyring.

    Adds a horizontal reference line for the Sabine 500 Hz single-band value.
    Lazy-imports plotly; call site should catch ImportError.
    """
    import plotly.graph_objects as go  # type: ignore[import]

    bands = sorted(report.sabine_rt60_per_band_s.keys())
    labels = [str(b) for b in bands]
    sabine_vals = [report.sabine_rt60_per_band_s[b] for b in bands]
    eyring_vals = [report.eyring_rt60_per_band_s[b] for b in bands]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(name="Sabine", x=labels, y=sabine_vals, marker_color="#4C72B0")
    )
    fig.add_trace(
        go.Bar(name="Eyring", x=labels, y=eyring_vals, marker_color="#DD8452")
    )
    fig.add_hline(
        y=report.sabine_rt60_500hz_s,
        line_dash="dot",
        line_color="gray",
        annotation_text=f"Sabine 500 Hz = {report.sabine_rt60_500hz_s:.2f} s",
        annotation_position="top right",
    )
    fig.update_layout(
        barmode="group",
        title="RT60 per octave band",
        xaxis_title="Octave band (Hz)",
        yaxis_title="RT60 (s)",
        legend_title="Predictor",
    )
    return fig


def build_absorption_distribution_chart(report: AcousticReport) -> "go.Figure":
    """Plotly stacked bar: per-surface fraction of total 500 Hz Sabine absorption.

    Color-codes by MaterialLabel using MATERIAL_PALETTE.
    Lazy-imports plotly; call site should catch ImportError.
    """
    import plotly.graph_objects as go  # type: ignore[import]

    from roomestim_web.material_palette import MATERIAL_PALETTE

    total_sabins = sum(s for _, _, _, s in report.surface_absorption_500hz)
    if total_sabins <= 0.0:
        total_sabins = 1.0  # avoid division-by-zero; all fractions will be 0

    # Group bars by material for consistent colouring
    from collections import defaultdict

    by_material: dict[MaterialLabel, list[tuple[int, float]]] = defaultdict(list)
    for idx, mat, _area, sabins in report.surface_absorption_500hz:
        by_material[mat].append((idx, sabins / total_sabins))

    x_labels = [str(idx) for idx, _, _, _ in report.surface_absorption_500hz]

    fig = go.Figure()
    for mat, entries in by_material.items():
        fractions = [0.0] * len(report.surface_absorption_500hz)
        for idx, frac in entries:
            fractions[idx] = frac
        fig.add_trace(
            go.Bar(
                name=mat.value,
                x=x_labels,
                y=fractions,
                marker_color=MATERIAL_PALETTE.get(mat, "#AAAAAA"),
            )
        )

    fig.update_layout(
        barmode="stack",
        title="Absorption distribution at 500 Hz (fraction of total Sabine absorption)",
        xaxis_title="Surface index",
        yaxis_title="Fraction",
        legend_title="Material",
    )
    return fig
