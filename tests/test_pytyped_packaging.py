"""Regression guard: roomestim/py.typed PEP 561 marker is bundled IN-PACKAGE (ADR 0007).

The marker file must ship alongside the package so that downstream consumers
(e.g. spatial_engine) can discover that roomestim exports typed stubs when they
run mypy.  This test is the substitute for an actual wheel-build check (``build``
is not assumed installed in CI): it proves ``py.typed`` resolves inside the
installed package tree, which is exactly what PEP 561 requires.

Design mirrors ``tests/test_proto_packaging.py``.
"""

from __future__ import annotations

from pathlib import Path

import roomestim


def test_pytyped_is_inside_package() -> None:
    """``py.typed`` must live at the package root (PEP 561)."""
    pkg_root = Path(roomestim.__file__).resolve().parent
    marker = pkg_root / "py.typed"
    assert marker.exists(), (
        f"py.typed not found at {marker}; "
        "ensure [tool.setuptools.package-data] includes 'py.typed'"
    )


def test_pytyped_is_a_file() -> None:
    """``py.typed`` must be a regular file (not a directory)."""
    pkg_root = Path(roomestim.__file__).resolve().parent
    marker = pkg_root / "py.typed"
    assert marker.is_file(), f"py.typed exists but is not a regular file: {marker}"
