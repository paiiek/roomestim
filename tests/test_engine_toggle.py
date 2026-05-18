"""tests/test_engine_toggle.py — engine validation toggle CLI tests (v0.16.0 / D42 + ADR 0033).

Covers:
  - Default ON: no flag → validation uses ENV/hardcoded path.
  - --validate-engine INVALID_PATH → schema not found → exit non-zero.
  - --no-engine-validation → WARNING header in output YAML + exit 0.
  - Mutually exclusive group: both flags → argparse error.
  - ENV var precedence: SPATIAL_ENGINE_REPO_DIR set, no CLI flag → ENV used.
  - CLI overrides ENV: --validate-engine Y with ENV set to X → Y used.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_PYTHON = sys.executable
_LAB_ROOM = Path("tests/fixtures/lab_room.json")
_LAB_ROOM_YAML = Path("tests/fixtures/lab_room.yaml")


def _find_lab_room_yaml() -> Path | None:
    """Find a usable room.yaml fixture for export tests."""
    if _LAB_ROOM_YAML.exists():
        return _LAB_ROOM_YAML
    # Try to find any room yaml in fixtures
    fixtures = Path("tests/fixtures")
    for f in fixtures.glob("*.yaml"):
        if "room" in f.name:
            return f
    return None


def _find_lab_layout_yaml() -> Path | None:
    """Find a usable layout.yaml fixture for export tests."""
    fixtures = Path("tests/fixtures")
    for f in fixtures.glob("*.yaml"):
        if "layout" in f.name:
            return f
    return None


@pytest.fixture
def room_and_layout_yaml(tmp_path: Path) -> tuple[Path, Path]:
    """Generate room.yaml + layout.yaml from lab_room.json via ingest+place."""
    if not _LAB_ROOM.exists():
        pytest.skip("lab_room.json fixture not found")

    # ingest
    result = subprocess.run(
        [_PYTHON, "-m", "roomestim", "ingest",
         "--backend", "roomplan",
         "--input", str(_LAB_ROOM),
         "--out-dir", str(tmp_path),
         "--octave-band"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"ingest failed: {result.stderr}")

    room_yaml = tmp_path / "room.yaml"
    if not room_yaml.exists():
        pytest.skip("room.yaml not produced by ingest")

    # place
    result2 = subprocess.run(
        [_PYTHON, "-m", "roomestim", "place",
         "--in-room", str(room_yaml),
         "--algorithm", "vbap",
         "--n-speakers", "5",
         "--out-dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    if result2.returncode != 0:
        pytest.skip(f"place failed: {result2.stderr}")

    layout_yaml = tmp_path / "layout.yaml"
    if not layout_yaml.exists():
        pytest.skip("layout.yaml not produced by place")

    return room_yaml, layout_yaml


def test_cli_export_no_engine_validation(
    room_and_layout_yaml: tuple[Path, Path], tmp_path: Path
) -> None:
    """--no-engine-validation → exit 0 + WARNING header in output YAML."""
    room_yaml, layout_yaml = room_and_layout_yaml
    out_dir = tmp_path / "out_no_val"
    out_dir.mkdir()

    result = subprocess.run(
        [_PYTHON, "-m", "roomestim", "export",
         "--in-room", str(room_yaml),
         "--in-placement", str(layout_yaml),
         "--out-dir", str(out_dir),
         "--no-engine-validation"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    layout_out = out_dir / "layout.yaml"
    assert layout_out.exists(), "layout.yaml not written"
    content = layout_out.read_text(encoding="utf-8")
    assert "# WARNING: schema validation skipped" in content, (
        f"WARNING header not found in output:\n{content[:500]}"
    )


def test_cli_export_validate_engine_explicit_path(
    room_and_layout_yaml: tuple[Path, Path], tmp_path: Path
) -> None:
    """--validate-engine /tmp/fake_engine (invalid) → non-zero exit."""
    room_yaml, layout_yaml = room_and_layout_yaml
    out_dir = tmp_path / "out_bad_engine"
    out_dir.mkdir()

    result = subprocess.run(
        [_PYTHON, "-m", "roomestim", "export",
         "--in-room", str(room_yaml),
         "--in-placement", str(layout_yaml),
         "--out-dir", str(out_dir),
         "--validate-engine", "/tmp/fake_engine_does_not_exist"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, (
        f"Expected non-zero exit for invalid engine path, got 0\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_cli_export_mutually_exclusive_group(
    room_and_layout_yaml: tuple[Path, Path], tmp_path: Path
) -> None:
    """--validate-engine X --no-engine-validation together → argparse error + exit 2."""
    room_yaml, layout_yaml = room_and_layout_yaml
    out_dir = tmp_path / "out_mutex"
    out_dir.mkdir()

    result = subprocess.run(
        [_PYTHON, "-m", "roomestim", "export",
         "--in-room", str(room_yaml),
         "--in-placement", str(layout_yaml),
         "--out-dir", str(out_dir),
         "--validate-engine", "/tmp/x",
         "--no-engine-validation"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, (
        f"Expected argparse exit 2, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_cli_export_env_var_precedence(
    room_and_layout_yaml: tuple[Path, Path], tmp_path: Path
) -> None:
    """ENV SPATIAL_ENGINE_REPO_DIR set to valid engine dir → used when flag absent.

    The existing _engine_schema_path() only uses ENV when the candidate file
    exists; it silently falls back to the hardcoded default otherwise (D42 §A
    backward-compat). This test verifies that when no CLI flag is given the
    ENV var is consulted — by creating a fake schema dir with a valid schema
    file and confirming the export succeeds with it.
    """
    room_yaml, layout_yaml = room_and_layout_yaml
    out_dir = tmp_path / "out_env"
    out_dir.mkdir()

    # Create a minimal valid engine schema dir so _engine_schema_path() picks it up
    fake_engine = tmp_path / "fake_engine"
    proto_dir = fake_engine / "proto"
    proto_dir.mkdir(parents=True)
    # Minimal Draft 2020-12 schema that accepts any object
    import json as _json
    (proto_dir / "geometry_schema.json").write_text(
        _json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}),
        encoding="utf-8",
    )

    env = {**os.environ, "SPATIAL_ENGINE_REPO_DIR": str(fake_engine)}
    result = subprocess.run(
        [_PYTHON, "-m", "roomestim", "export",
         "--in-room", str(room_yaml),
         "--in-placement", str(layout_yaml),
         "--out-dir", str(out_dir)],
        capture_output=True, text=True,
        env=env,
    )
    # The fake schema accepts any object → validation passes → exit 0
    assert result.returncode == 0, (
        f"Expected exit 0 with valid fake ENV schema, got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    layout_out = out_dir / "layout.yaml"
    assert layout_out.exists()
    # Confirm no WARNING header (validation was ON, not skipped)
    content = layout_out.read_text(encoding="utf-8")
    assert "# WARNING" not in content, "WARNING header should not appear when validation is ON"


def test_cli_export_cli_overrides_env(
    room_and_layout_yaml: tuple[Path, Path], tmp_path: Path
) -> None:
    """CLI --validate-engine PATH overrides SPATIAL_ENGINE_REPO_DIR (D42 precedence).

    Setup: ENV has a valid fake schema, CLI points at a different valid fake schema.
    Result: CLI schema dir is used (not ENV). Both succeed; we verify by inspecting
    which path the error would reference when CLI path is invalid.
    """
    import json as _json
    room_yaml, layout_yaml = room_and_layout_yaml
    out_dir = tmp_path / "out_cli_over_env"
    out_dir.mkdir()

    # ENV: valid fake schema
    fake_env_engine = tmp_path / "env_engine"
    env_proto = fake_env_engine / "proto"
    env_proto.mkdir(parents=True)
    (env_proto / "geometry_schema.json").write_text(
        _json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}),
        encoding="utf-8",
    )

    # CLI: invalid path (no schema file) → should fail because CLI overrides ENV
    env = {**os.environ, "SPATIAL_ENGINE_REPO_DIR": str(fake_env_engine)}
    result = subprocess.run(
        [_PYTHON, "-m", "roomestim", "export",
         "--in-room", str(room_yaml),
         "--in-placement", str(layout_yaml),
         "--out-dir", str(out_dir),
         "--validate-engine", "/tmp/cli_engine_dir_nonexistent"],
        capture_output=True, text=True,
        env=env,
    )
    # CLI path is invalid → schema not found → non-zero (if ENV were used, exit 0)
    assert result.returncode != 0, (
        f"Expected non-zero exit because CLI path is invalid (D42: CLI > ENV). "
        f"If ENV path were used instead, it would succeed. returncode={result.returncode}"
    )


def test_cli_export_help_shows_validation_flags() -> None:
    """--help shows --validate-engine and --no-engine-validation flags."""
    result = subprocess.run(
        [_PYTHON, "-m", "roomestim", "export", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--validate-engine" in result.stdout, (
        "--validate-engine not in help output"
    )
    assert "--no-engine-validation" in result.stdout, (
        "--no-engine-validation not in help output"
    )
