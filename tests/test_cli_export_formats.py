"""tests/test_cli_export_formats.py — v0.17 Phase 6 CLI --format dispatch.

Covers Phase 6 acceptance gates per .omc/plans/v0.17-design.md (Phase 6,
line 706-713):

- ``roomestim export`` defaults to ``--format yaml`` (backward-compat).
- ``--format usdz`` writes a ``.usdz`` file (skipped if ``pxr`` absent).
- ``--format gltf`` / ``--format glb`` writes the appropriate file.
- ``--format obj`` (unknown choice) → argparse exit code 2.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from roomestim.export.layout_yaml import write_layout_yaml
from roomestim.export.room_yaml import write_room_yaml
from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.model import (
    PlacedSpeaker,
    PlacementResult,
    Point3,
    RoomModel,
)


_REPO_ROOT = str(Path(__file__).resolve().parent.parent)


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{_REPO_ROOT}:{existing_pp}" if existing_pp else _REPO_ROOT
    return env


@pytest.fixture
def lab_room() -> RoomModel:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    return RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)


@pytest.fixture
def io_paths(lab_room: RoomModel, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build room.yaml + layout.yaml in tmp_path; return (room_path, layout_path, out_dir)."""
    room_path = tmp_path / "room.yaml"
    layout_path = tmp_path / "layout.yaml"
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Persist a 0.1-draft room.yaml (no objects key) so the CLI's read_room_yaml
    # path stays portable across schema branches.
    write_room_yaml(lab_room, room_path, schema_version="0.1-draft")

    placement = PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="IRREGULAR",
        speakers=[
            PlacedSpeaker(channel=1, position=Point3(x=1.0, y=1.2, z=1.0)),
            PlacedSpeaker(channel=2, position=Point3(x=-1.0, y=1.2, z=1.0)),
        ],
        layout_name="cli-test",
    )
    write_layout_yaml(placement, layout_path)
    return room_path, layout_path, out_dir


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "roomestim", *args],
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_cli_export_yaml_default(io_paths: tuple[Path, Path, Path]) -> None:
    """No --format → yaml branch fires; room.yaml + layout.yaml emitted."""
    room_path, layout_path, out_dir = io_paths
    result = _run_cli(
        [
            "export",
            "--in-room", str(room_path),
            "--in-placement", str(layout_path),
            "--out-dir", str(out_dir),
            "--no-engine-validation",
        ]
    )
    assert result.returncode == 0, (
        f"yaml-default export failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert (out_dir / "room.yaml").exists()
    assert (out_dir / "layout.yaml").exists()


def test_cli_export_usdz(io_paths: tuple[Path, Path, Path]) -> None:
    """``--format usdz`` writes a ``.usdz`` file (skipped if ``pxr`` absent)."""
    if importlib.util.find_spec("pxr") is None:
        pytest.skip("pxr (usd-core) not installed")
    room_path, layout_path, out_dir = io_paths
    result = _run_cli(
        [
            "export",
            "--in-room", str(room_path),
            "--in-placement", str(layout_path),
            "--out-dir", str(out_dir),
            "--format", "usdz",
        ]
    )
    assert result.returncode == 0, (
        f"usdz export failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert (out_dir / "room.usdz").exists()


def test_cli_export_gltf(io_paths: tuple[Path, Path, Path]) -> None:
    """``--format glb`` writes a ``.glb`` file using trimesh (core dep)."""
    room_path, layout_path, out_dir = io_paths
    result = _run_cli(
        [
            "export",
            "--in-room", str(room_path),
            "--in-placement", str(layout_path),
            "--out-dir", str(out_dir),
            "--format", "glb",
        ]
    )
    assert result.returncode == 0, (
        f"glb export failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert (out_dir / "room.glb").exists()


def test_cli_export_invalid_format(io_paths: tuple[Path, Path, Path]) -> None:
    """``--format obj`` → argparse rejects with exit code 2."""
    room_path, layout_path, out_dir = io_paths
    result = _run_cli(
        [
            "export",
            "--in-room", str(room_path),
            "--in-placement", str(layout_path),
            "--out-dir", str(out_dir),
            "--format", "obj",
        ]
    )
    assert result.returncode == 2, (
        f"Expected argparse exit code 2, got {result.returncode}; stderr={result.stderr!r}"
    )
