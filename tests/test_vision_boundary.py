"""Core/web boundary guard for the optional ``[vision]`` extra (ADR 0045 gate #4).

These tests run in the canonical (torch-free) gate. They assert that importing
roomestim, its adapters, and the torch-free parts of ``roomestim.vision`` never
pulls in torch — even though the canonical env ships a BROKEN torchvision. The
torch-backed vendored model (``roomestim.vision.horizonnet.model``) is NOT
imported here; it is smoke-tested out-of-gate against a working torch env.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Modules that MUST import without dragging torch into sys.modules.
_TORCH_FREE_MODULES = [
    "roomestim",
    "roomestim.adapters",
    "roomestim.vision",
    "roomestim.vision.checkpoints",
]


def test_torch_free_imports_do_not_load_torch() -> None:
    """A fresh interpreter importing the core modules must have no `torch`.

    Run in a subprocess so prior test imports (or torch loaded elsewhere) cannot
    contaminate the sys.modules check.
    """
    imports = "; ".join(f"import {m}" for m in _TORCH_FREE_MODULES)
    code = (
        f"{imports}; import sys; "
        "assert 'torch' not in sys.modules, "
        "'torch leaked into sys.modules via a core import'; "
        "print('OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"torch-free import check failed.\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "OK" in result.stdout


def test_checkpoints_imports_despite_broken_torchvision() -> None:
    """`roomestim.vision.checkpoints` imports even with broken/absent torchvision."""
    mod = importlib.import_module("roomestim.vision.checkpoints")
    assert hasattr(mod, "resolve_checkpoint")


def test_zind_requires_tou_acceptance() -> None:
    """resolve_checkpoint('zind') without acceptance raises a ToU error."""
    from roomestim.vision.checkpoints import resolve_checkpoint

    with pytest.raises(ValueError, match="(?i)terms of use|non-commercial|ZInD"):
        resolve_checkpoint("zind")


def test_local_override_returns_path_without_download(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ROOMESTIM_HORIZONNET_CKPT short-circuits resolution (no download)."""
    from roomestim.vision.checkpoints import resolve_checkpoint

    fake = tmp_path / "ckpt.pth"
    fake.write_bytes(b"")
    monkeypatch.setenv("ROOMESTIM_HORIZONNET_CKPT", str(fake))
    # Even for the gated 'zind' name the local override wins (no acceptance).
    assert resolve_checkpoint("zind") == fake
    assert resolve_checkpoint("st3d") == fake


def test_vision_extra_declared_in_pyproject() -> None:
    """The `[vision]` optional-dependency group is declared with torch deps."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        data = tomllib.load(fh)
    extras = data["project"]["optional-dependencies"]
    assert "vision" in extras, "[vision] extra missing from pyproject"
    names = " ".join(extras["vision"]).lower()
    for dep in ("torch", "torchvision"):
        assert dep in names, f"{dep} missing from [vision] extra"
