"""roomestim_web.pipeline — end-to-end pipeline runner for the web UI."""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path


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
) -> PipelineResult:
    """Run full parse → place → export pipeline.

    Args:
        input_path: Path to room scan (.usdz or .obj).
        algorithm: Placement algorithm name (e.g. "vbap").
        n_speakers: Number of speakers to place.
        layout_radius_m: Speaker layout circle radius in metres.
        el_deg: Speaker elevation angle in degrees.
        octave_band: Whether to use octave-band absorption coefficients.
        out_dir: Directory to write room.yaml and layout.yaml.

    Returns:
        PipelineResult with room, layout, and output file paths.

    Raises:
        ValueError: If input_path has an unsupported suffix.
    """
    input_path = Path(input_path)
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    MESH_SUFFIXES = {".obj", ".gltf", ".glb", ".ply"}

    suffix = input_path.suffix.lower()
    if suffix == ".usdz":
        from roomestim.adapters.roomplan import RoomPlanAdapter
        adapter: object = RoomPlanAdapter()
    elif suffix == ".json":
        from roomestim.adapters.roomplan import RoomPlanAdapter
        adapter = RoomPlanAdapter()
    elif suffix in MESH_SUFFIXES:
        from roomestim.adapters.mesh import MeshAdapter
        adapter = MeshAdapter()
    else:
        raise ValueError(
            f"Unsupported input format '{suffix}'."
            " Expected .usdz / .obj / .gltf / .glb / .ply."
        )

    # parse() is defined on both adapter types
    room = adapter.parse(  # type: ignore[union-attr]
        input_path, scale_anchor=None, octave_band=octave_band
    )

    from roomestim.place.dispatch import run_placement
    layout = run_placement(room, algorithm, n_speakers, layout_radius_m, el_deg)

    room_yaml_path = out_dir / "room.yaml"
    layout_yaml_path = out_dir / "layout.yaml"

    from roomestim.export.room_yaml import write_room_yaml
    write_room_yaml(room, room_yaml_path)

    from roomestim.export.layout_yaml import write_layout_yaml
    write_layout_yaml(layout, layout_yaml_path)

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
