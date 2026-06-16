"""Regression guard: room.yaml JSON schemas are bundled IN-PACKAGE (ADR 0007).

Prior to v0.37.1 the schemas lived at repo-root ``proto/`` and ``_proto_dir()``
resolved ``Path(__file__).parents[2] / "proto"`` — which in an installed wheel
pointed at a nonexistent ``site-packages/proto`` (the wheel also shipped zero
schema files). v0.37.1 relocated them into ``roomestim/proto/`` so the existing
``[tool.setuptools.package-data]`` glob both ships and resolves them.

These tests are the substitute for an actual wheel-build check (``build`` is not
assumed installed in CI): they prove ``_proto_dir()`` resolves inside the
package and that the three schema files exist there, which is exactly what makes
an installed copy self-validate/emit room.yaml.
"""

from __future__ import annotations

from pathlib import Path

import roomestim
from roomestim.export.room_yaml import _proto_dir as _proto_dir_export
from roomestim.io.room_yaml_reader import _proto_dir as _proto_dir_reader

_SCHEMA_FILES = (
    "room_schema.draft.json",
    "room_schema.json",
    "room_schema.v0_2.draft.json",
)


def test_proto_dir_is_inside_package() -> None:
    """``_proto_dir()`` must resolve inside the ``roomestim`` package."""
    pkg_root = Path(roomestim.__file__).resolve().parent
    for proto_dir in (_proto_dir_export(), _proto_dir_reader()):
        assert "roomestim" in str(proto_dir)
        assert proto_dir == pkg_root / "proto"


def test_export_and_reader_agree() -> None:
    """Writer and reader must resolve the same schema directory."""
    assert _proto_dir_export() == _proto_dir_reader()


def test_schema_files_exist_in_package() -> None:
    """All three schema files must ship at the in-package location."""
    proto_dir = _proto_dir_export()
    for name in _SCHEMA_FILES:
        assert (proto_dir / name).is_file(), f"missing in-package schema: {name}"


def test_no_repo_root_proto_dir() -> None:
    """The old repo-root ``proto/`` schema location must no longer be where the
    runtime resolves (guards against a regression that re-points outside the
    package). ``_proto_dir()`` resolves to ``roomestim/proto``, never its parent.
    """
    pkg_parent = Path(roomestim.__file__).resolve().parent.parent
    assert _proto_dir_export() != pkg_parent / "proto"
