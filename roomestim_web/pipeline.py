"""roomestim_web.pipeline — end-to-end pipeline runner for the web UI."""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from roomestim.adapters.base import CaptureAdapter


@dataclass(frozen=True)
class PipelineResult:
    """Holds outputs from a complete pipeline run."""

    room: object  # RoomModel — typed as object to avoid top-level import
    layout: object  # PlacementResult
    room_yaml_path: Path
    layout_yaml_path: Path


def run_pipeline(
    input_path: str | Path,
    *,
    algorithm: str,
    n_speakers: int,
    layout_radius_m: float,
    el_deg: float,
    octave_band: bool,
    out_dir: str | Path,
    wfs_f_max_hz: float = 8000.0,
    skip_engine_validation: bool = False,
    ceiling_height_m: float | None = None,
    snap_to_surfaces: bool = False,
) -> PipelineResult:
    """Run full parse → place → export pipeline.

    Args:
        input_path: Path to room scan (.usdz/.json/.obj/.gltf/.glb/.ply) or a
            reconstructed point cloud (.npz/.xyz/.txt, or a points-only .ply).
        algorithm: Placement algorithm name (e.g. "vbap").
        n_speakers: Number of speakers to place.
        layout_radius_m: Speaker layout circle radius in metres.
        el_deg: Speaker elevation angle in degrees.
        octave_band: Whether to use octave-band absorption coefficients.
        out_dir: Directory to write room.yaml and layout.yaml.
        ceiling_height_m: Optional user-supplied ceiling height (metres). Only
            applied on the point-cloud path (``MultiviewAdapter``) — rough
            consumer clouds never reconstruct the ceiling, so the user supplies
            it as one scalar (PLACEMENT_SENSITIVITY_VERDICT.md). Ignored for
            mesh/RoomPlan inputs, which carry a real ceiling.
        snap_to_surfaces: When True, snap every placed speaker onto the nearest
            real wall/ceiling surface after placement (install-time mitigation
            from PLACEMENT_SENSITIVITY_VERDICT.md — recovers coverage to within
            ~0.03 dB of the oracle on a rough room model).

    Returns:
        PipelineResult with room, layout, and output file paths.

    Raises:
        ValueError: If input_path has an unsupported suffix.
    """
    input_path = Path(input_path)
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    MESH_SUFFIXES = {".obj", ".gltf", ".glb"}
    # Reconstructed rough point clouds (no faces) → MultiviewAdapter, the
    # validated consumer "rough+" tier front-end (convex footprint default).
    CLOUD_SUFFIXES = {".npz", ".xyz", ".txt"}

    suffix = input_path.suffix.lower()
    if suffix in (".usdz", ".json"):
        from roomestim.adapters.roomplan import RoomPlanAdapter
        adapter: CaptureAdapter = RoomPlanAdapter()
        room = adapter.parse(input_path, scale_anchor=None, octave_band=octave_band)
    elif suffix in MESH_SUFFIXES:
        from roomestim.adapters.mesh import MeshAdapter
        adapter = MeshAdapter()
        room = adapter.parse(input_path, scale_anchor=None, octave_band=octave_band)
    elif suffix in CLOUD_SUFFIXES:
        from roomestim.adapters.multiview import MultiviewAdapter
        adapter = MultiviewAdapter(ceiling_height_m=ceiling_height_m)
        room = adapter.parse(input_path, scale_anchor=None, octave_band=octave_band)
    elif suffix == ".ply":
        # .ply is ambiguous: a mesh (with faces) or a points-only cloud. Try the
        # mesh path first; on rejection fall back to the point-cloud adapter,
        # closing the points-only .ply gap that MeshAdapter rejects.
        from roomestim.adapters.mesh import MeshAdapter
        try:
            adapter = MeshAdapter()
            room = adapter.parse(input_path, scale_anchor=None, octave_band=octave_band)
        except ValueError:
            from roomestim.adapters.multiview import MultiviewAdapter
            adapter = MultiviewAdapter(ceiling_height_m=ceiling_height_m)
            room = adapter.parse(input_path, scale_anchor=None, octave_band=octave_band)
    else:
        raise ValueError(
            f"Unsupported input format '{suffix}'."
            " Expected .usdz / .json / .obj / .gltf / .glb / .ply"
            " (mesh) or .npz / .xyz / .txt (point cloud)."
        )

    from roomestim.place.dispatch import run_placement
    layout = run_placement(room, algorithm, n_speakers, layout_radius_m, el_deg, wfs_f_max_hz=wfs_f_max_hz)

    if snap_to_surfaces:
        # Install-time snap-to-surface (PLACEMENT_SENSITIVITY_VERDICT.md): move
        # each planned speaker onto the nearest real wall/ceiling so the exported
        # layout is physically mountable. No-op when the room has no mount surface.
        from roomestim.edit import snap_layout_to_surfaces
        layout = snap_layout_to_surfaces(room, layout)

    room_yaml_path = out_dir / "room.yaml"
    layout_yaml_path = out_dir / "layout.yaml"

    from roomestim.export.room_yaml import write_room_yaml
    write_room_yaml(room, room_yaml_path)

    from roomestim.export.layout_yaml import write_layout_yaml
    write_layout_yaml(layout, layout_yaml_path, validate=not skip_engine_validation)

    return PipelineResult(
        room=room,
        layout=layout,
        room_yaml_path=room_yaml_path,
        layout_yaml_path=layout_yaml_path,
    )


def build_yaml_zip(result: PipelineResult, zip_path: str | Path) -> Path:
    """Bundle room.yaml + layout.yaml into a ZIP archive.

    Args:
        result: PipelineResult from run_pipeline().
        zip_path: Destination path for the ZIP file.

    Returns:
        Path to the created ZIP file.
    """
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(result.room_yaml_path, arcname="room.yaml")
        zf.write(result.layout_yaml_path, arcname="layout.yaml")
    return zip_path
