"""WFS CLI ergonomics (v0.7) — constructive error message + override flags.

Default-lane tests. Verifies that:
  - The default `roomestim run --algorithm wfs --n-speakers 8 --layout-radius 2.0`
    invocation no longer raises a raw kErrWfsSpacingTooLarge but instead emits a
    constructive remediation message naming both --wfs-f-max-hz and --n-speakers
    safe values.
  - The new --wfs-f-max-hz flag actually relaxes the spatial-aliasing bound and
    lets the default n=8 / radius=2.0 invocation succeed.
  - The new --wfs-spacing-m flag overrides the derived spacing.
  - --wfs-spacing-m takes precedence over the derived spacing (verified through
    the resulting x_wfs_f_alias_hz which is c/(2*spacing)).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml


_FIXTURE_JSON = Path(__file__).parent / "fixtures" / "lab_room.json"
_REPO_ROOT = str(Path(__file__).parent.parent)


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{_REPO_ROOT}:{existing_pp}" if existing_pp else _REPO_ROOT
    return env


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "roomestim", *args],
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )


def test_run_wfs_default_n8_emits_constructive_error(tmp_path: Path) -> None:
    """Default WFS invocation fails with a message naming both remediation paths."""
    out_dir = tmp_path / "out"
    result = _run_cli(
        [
            "run",
            "--backend", "polycam",
            "--input", str(_FIXTURE_JSON),
            "--algorithm", "wfs",
            "--n-speakers", "8",
            "--layout-radius", "2.0",
            "--out-dir", str(out_dir),
        ]
    )
    assert result.returncode != 0, (
        f"expected non-zero exit, got 0\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "max safe --wfs-f-max-hz" in combined, (
        f"missing 'max safe --wfs-f-max-hz' clause:\n{combined}"
    )
    assert "minimum safe --n-speakers" in combined, (
        f"missing 'minimum safe --n-speakers' clause:\n{combined}"
    )


def test_run_wfs_with_low_fmax_succeeds(tmp_path: Path) -> None:
    """--wfs-f-max-hz 300 unblocks the default n=8 / radius=2.0 invocation."""
    out_dir = tmp_path / "out"
    result = _run_cli(
        [
            "run",
            "--backend", "polycam",
            "--input", str(_FIXTURE_JSON),
            "--algorithm", "wfs",
            "--n-speakers", "8",
            "--layout-radius", "2.0",
            "--wfs-f-max-hz", "300",
            "--out-dir", str(out_dir),
        ]
    )
    assert result.returncode == 0, (
        f"expected zero exit, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert (out_dir / "room.yaml").exists()
    assert (out_dir / "layout.yaml").exists()


def test_run_wfs_with_explicit_spacing_succeeds(tmp_path: Path) -> None:
    """--wfs-spacing-m 0.02 satisfies the bound at f_max=8000 even with high n."""
    out_dir = tmp_path / "out"
    result = _run_cli(
        [
            "run",
            "--backend", "polycam",
            "--input", str(_FIXTURE_JSON),
            "--algorithm", "wfs",
            "--n-speakers", "200",
            "--layout-radius", "2.0",
            "--wfs-spacing-m", "0.02",
            "--wfs-f-max-hz", "8000",
            "--out-dir", str(out_dir),
        ]
    )
    assert result.returncode == 0, (
        f"expected zero exit, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert (out_dir / "room.yaml").exists()
    assert (out_dir / "layout.yaml").exists()


def test_run_wfs_explicit_spacing_overrides_derived(tmp_path: Path) -> None:
    """--wfs-spacing-m wins over the (n_speakers, layout_radius)-derived spacing.

    With n=8 / radius=2.0, derived spacing would be 4.0/7 ≈ 0.5714 m. Passing
    --wfs-spacing-m 0.10 instead produces f_alias = c/(2*0.10) = 1715.0 Hz,
    not c/(2*0.5714) ≈ 300.12 Hz.
    """
    out_dir = tmp_path / "out"
    explicit_spacing = 0.10  # m
    result = _run_cli(
        [
            "run",
            "--backend", "polycam",
            "--input", str(_FIXTURE_JSON),
            "--algorithm", "wfs",
            "--n-speakers", "8",
            "--layout-radius", "2.0",
            "--wfs-spacing-m", str(explicit_spacing),
            "--wfs-f-max-hz", "1500",
            "--out-dir", str(out_dir),
        ]
    )
    assert result.returncode == 0, (
        f"expected zero exit, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    layout_path = out_dir / "layout.yaml"
    assert layout_path.exists()
    layout = yaml.safe_load(layout_path.read_text())
    assert "x_wfs_f_alias_hz" in layout
    expected_f_alias = 343.0 / (2.0 * explicit_spacing)  # 1715.0 Hz
    assert abs(layout["x_wfs_f_alias_hz"] - expected_f_alias) < 1e-6, (
        f"f_alias {layout['x_wfs_f_alias_hz']} does not reflect explicit spacing "
        f"{explicit_spacing} (expected ~{expected_f_alias})"
    )
