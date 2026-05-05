"""A12 — CLI idempotency: running `roomestim run` twice produces byte-identical output."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


_FIXTURE_JSON = Path(__file__).parent / "fixtures" / "lab_room.json"
_REPO_ROOT = str(Path(__file__).parent.parent)


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{_REPO_ROOT}:{existing_pp}" if existing_pp else _REPO_ROOT
    return env


def _run_once(out_dir: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "roomestim",
            "run",
            "--backend", "roomplan",
            "--input", str(_FIXTURE_JSON),
            "--algorithm", "vbap",
            "--n-speakers", "8",
            "--layout-radius", "2.0",
            "--out-dir", str(out_dir),
        ],
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )
    assert result.returncode == 0, (
        f"roomestim run exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_cli_run_idempotent(tmp_path: Path) -> None:
    """Running `roomestim run` twice in the same out-dir produces byte-identical files."""
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    _run_once(out1)
    _run_once(out2)

    for fname in ("room.yaml", "layout.yaml"):
        f1 = out1 / fname
        f2 = out2 / fname
        assert f1.exists(), f"First run did not produce {fname}"
        assert f2.exists(), f"Second run did not produce {fname}"
        assert f1.read_bytes() == f2.read_bytes(), (
            f"{fname} differs between runs:\n"
            f"  run1: {f1.read_text()}\n"
            f"  run2: {f2.read_text()}"
        )
