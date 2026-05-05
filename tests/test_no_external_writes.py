"""A14 — No external writes: CLI only writes files under --out-dir."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


_FIXTURE_JSON = Path(__file__).parent / "fixtures" / "lab_room.json"
# Repo root — needed so the subprocess can import roomestim even when CWD differs.
_REPO_ROOT = str(Path(__file__).parent.parent)


def test_no_external_writes(tmp_path: Path) -> None:
    """Ensure `roomestim run` creates files only inside the specified --out-dir."""
    out_dir = tmp_path / "out"

    # Snapshot tmp_path tree before the run (excluding out_dir)
    def _tree(root: Path) -> set[Path]:
        return {p for p in root.rglob("*") if p.is_file()}

    before = _tree(tmp_path)

    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{_REPO_ROOT}:{existing_pp}" if existing_pp else _REPO_ROOT

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
        cwd=str(tmp_path),
        env=env,
    )
    assert result.returncode == 0, (
        f"roomestim run exited {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    after = _tree(tmp_path)
    new_files = after - before

    # Every new file must be inside out_dir
    for f in new_files:
        assert str(f).startswith(str(out_dir)), (
            f"CLI created a file outside --out-dir: {f}"
        )

    # Confirm the expected outputs are present
    assert (out_dir / "room.yaml").exists()
    assert (out_dir / "layout.yaml").exists()
