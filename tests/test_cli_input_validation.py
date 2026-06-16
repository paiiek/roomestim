"""v0.22.2 audit fixes — CLI input-validation + engine-toggle regressions.

Covers:
  - FIX-3 / D76: schema-violating or malformed room.yaml fed to `place` exits 1
    with an `error:` message and NO Python traceback (ValidationError / YAMLError
    are wrapped as ValueError at the read boundary so the CLI handler catches
    them and the reader docstring "Raises ValueError" is true).
  - FIX-4 / D77: `run` accepts the `--validate-engine` / `--no-engine-validation`
    mutually-exclusive toggle (at parity with export / edit).
  - FIX-5 / D78: a self-intersecting (bow-tie) floor_polygon is rejected at the
    read boundary with a ValueError (would otherwise produce garbage volume).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from roomestim.cli import main
from roomestim.export.room_yaml import write_room_yaml
from roomestim.io.room_yaml_reader import read_room_yaml

from tests.fixtures.synthetic_rooms import shoebox

_FIXTURE_JSON = Path(__file__).parent / "fixtures" / "lab_room.json"


def _write_valid_room_yaml(path: Path) -> dict:
    write_room_yaml(shoebox(), path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# FIX-3 / D76 — CLI catches schema / YAML errors, no traceback escapes
# --------------------------------------------------------------------------- #


def test_place_on_schema_violating_room_exits_one_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    room_yaml = tmp_path / "room.yaml"
    data = _write_valid_room_yaml(room_yaml)
    del data["ceiling_height_m"]  # drop a schema-required property
    room_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")

    rc = main(
        ["place", "--in-room", str(room_yaml), "--algorithm", "vbap",
         "--out-dir", str(tmp_path / "out")]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_place_on_malformed_yaml_exits_one_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    room_yaml = tmp_path / "room.yaml"
    room_yaml.write_text("name: [unterminated\n  : :", encoding="utf-8")

    rc = main(
        ["place", "--in-room", str(room_yaml), "--algorithm", "vbap",
         "--out-dir", str(tmp_path / "out")]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err


def test_read_room_yaml_schema_error_is_value_error(tmp_path: Path) -> None:
    """The wrapped exception is a true ValueError (docstring contract)."""
    room_yaml = tmp_path / "room.yaml"
    data = _write_valid_room_yaml(room_yaml)
    del data["name"]
    room_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError):
        read_room_yaml(room_yaml)


# --------------------------------------------------------------------------- #
# MINOR (reviewer) / D76 addendum — empty / non-mapping YAML guard
# --------------------------------------------------------------------------- #
# An empty file parses to None; a top-level list parses to list. Both caused
# AttributeError / TypeError (not ValueError) before the isinstance guard was
# added, so they escaped the CLI handler as a raw traceback.


def test_place_on_empty_room_yaml_exits_one_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    room_yaml = tmp_path / "room.yaml"
    room_yaml.write_text("", encoding="utf-8")  # safe_load → None

    rc = main(
        ["place", "--in-room", str(room_yaml), "--algorithm", "vbap",
         "--out-dir", str(tmp_path / "out")]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_place_on_list_room_yaml_exits_one_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    room_yaml = tmp_path / "room.yaml"
    room_yaml.write_text("- item1\n- item2\n", encoding="utf-8")  # safe_load → list

    rc = main(
        ["place", "--in-room", str(room_yaml), "--algorithm", "vbap",
         "--out-dir", str(tmp_path / "out")]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err


def test_read_room_yaml_empty_file_is_value_error(tmp_path: Path) -> None:
    """Empty room.yaml raises ValueError (not AttributeError) — guard contract."""
    room_yaml = tmp_path / "room.yaml"
    room_yaml.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a YAML mapping"):
        read_room_yaml(room_yaml)


def test_read_room_yaml_list_is_value_error(tmp_path: Path) -> None:
    """Top-level-list room.yaml raises ValueError (not TypeError) — guard contract."""
    room_yaml = tmp_path / "room.yaml"
    room_yaml.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a YAML mapping"):
        read_room_yaml(room_yaml)


# --------------------------------------------------------------------------- #
# FIX-4 / D77 — `run` engine-validation toggle parity
# --------------------------------------------------------------------------- #


def test_run_accepts_no_engine_validation(tmp_path: Path) -> None:
    rc = main(
        ["run", "--backend", "roomplan", "--input", str(_FIXTURE_JSON),
         "--algorithm", "vbap", "--n-speakers", "8", "--out-dir", str(tmp_path),
         "--no-engine-validation"]
    )
    assert rc == 0
    assert (tmp_path / "layout.yaml").exists()


def test_run_validate_engine_and_no_validation_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        main(
            ["run", "--backend", "roomplan", "--input", str(_FIXTURE_JSON),
             "--algorithm", "vbap", "--validate-engine", "/tmp/x",
             "--no-engine-validation"]
        )


# --------------------------------------------------------------------------- #
# FIX-5 / D78 — self-intersecting floor rejected
# --------------------------------------------------------------------------- #


def test_bowtie_floor_polygon_rejected(tmp_path: Path) -> None:
    room_yaml = tmp_path / "room.yaml"
    data = _write_valid_room_yaml(room_yaml)
    fp = data["floor_polygon"]
    # Swap the last two vertices of the rectangle → self-intersecting bow-tie.
    fp[2], fp[3] = fp[3], fp[2]
    room_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="self-intersecting"):
        read_room_yaml(room_yaml)


def test_simple_floor_polygon_accepted(tmp_path: Path) -> None:
    """Negative control: the unmodified (simple) shoebox floor still loads."""
    room_yaml = tmp_path / "room.yaml"
    _write_valid_room_yaml(room_yaml)
    room = read_room_yaml(room_yaml)
    assert room.name == "synthetic_shoebox"


# --------------------------------------------------------------------------- #
# PR3 / ADR 0042 — `--floor-reconstruction` CLI flag (v0.32.0)
# --------------------------------------------------------------------------- #


def _write_l_prism_obj(path: Path) -> None:
    """Watertight L-shaped prism (6x6 minus a 3x3 notch), extruded 2.5 m tall."""
    import numpy as np
    import trimesh

    foot = [(0.0, 0.0), (6.0, 0.0), (6.0, 3.0), (3.0, 3.0), (3.0, 6.0), (0.0, 6.0)]
    h = 2.5
    n = len(foot)
    bottom = [(x, 0.0, z) for (x, z) in foot]
    top = [(x, h, z) for (x, z) in foot]
    verts = np.array(bottom + top, dtype=float)
    faces: list[list[int]] = []
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, j + n])
        faces.append([i, j + n, i + n])
    for i in range(1, n - 1):
        faces.append([0, i + 1, i])
    for i in range(1, n - 1):
        faces.append([n, n + i, n + i + 1])
    mesh = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=False)
    mesh.export(path)


def test_cli_floor_reconstruction_concave_ingests_l_mesh(tmp_path: Path) -> None:
    """`--floor-reconstruction concave` on a mesh backend recovers the notch."""
    obj_path = tmp_path / "l_room.obj"
    _write_l_prism_obj(obj_path)

    rc = main(
        ["ingest", "--backend", "polycam", "--input", str(obj_path),
         "--out-dir", str(tmp_path), "--floor-reconstruction", "concave"]
    )
    assert rc == 0
    room = read_room_yaml(tmp_path / "room.yaml")
    # Concave keeps the re-entrant corner → >=6 vertices (an L has 6 corners).
    assert len(room.floor_polygon) >= 6


def test_cli_floor_reconstruction_default_convex_collapses_notch(
    tmp_path: Path,
) -> None:
    """Default (convex) erases the notch → a 5-vertex pentagon hull."""
    obj_path = tmp_path / "l_room.obj"
    _write_l_prism_obj(obj_path)

    rc = main(
        ["ingest", "--backend", "polycam", "--input", str(obj_path),
         "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    room = read_room_yaml(tmp_path / "room.yaml")
    assert len(room.floor_polygon) == 5


def test_cli_concave_notice_fires_for_non_mesh_backend(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Concave with a non-mesh backend (roomplan) emits an honest 'ignored' NOTE."""
    rc = main(
        ["ingest", "--backend", "roomplan", "--input", str(_FIXTURE_JSON),
         "--out-dir", str(tmp_path), "--floor-reconstruction", "concave"]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "ignored for --backend roomplan" in captured.err


def test_cli_concave_structural_notice_for_mesh_backend(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Concave on a mesh backend emits the UNVALIDATED structural-estimate NOTE."""
    obj_path = tmp_path / "l_room.obj"
    _write_l_prism_obj(obj_path)

    rc = main(
        ["ingest", "--backend", "polycam", "--input", str(obj_path),
         "--out-dir", str(tmp_path), "--floor-reconstruction", "concave"]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "STRUCTURAL estimate" in captured.err
    assert "UNVALIDATED" in captured.err


def _write_dense_l_prism_obj(path: Path) -> None:
    """Dense (subdivided) L-prism for the occupancy footprint mode.

    The sparse 12-vertex L-prism puts ~1 vertex per 5 cm occupancy cell and
    would fail ``min_count``; subdividing below 4 cm packs it densely enough for
    the occupancy path to recover the L footprint.
    """
    import numpy as np
    import trimesh

    foot = [(0.0, 0.0), (6.0, 0.0), (6.0, 3.0), (3.0, 3.0), (3.0, 6.0), (0.0, 6.0)]
    h = 2.5
    n = len(foot)
    bottom = [(x, 0.0, z) for (x, z) in foot]
    top = [(x, h, z) for (x, z) in foot]
    verts = np.array(bottom + top, dtype=float)
    faces: list[list[int]] = []
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, j + n])
        faces.append([i, j + n, i + n])
    for i in range(1, n - 1):
        faces.append([0, i + 1, i])
    for i in range(1, n - 1):
        faces.append([n, n + i, n + i + 1])
    dense_v, dense_f = trimesh.remesh.subdivide_to_size(
        verts, np.array(faces), max_edge=0.04
    )
    trimesh.Trimesh(vertices=dense_v, faces=dense_f, process=False).export(path)


def test_cli_floor_reconstruction_occupancy_ingests_mesh(tmp_path: Path) -> None:
    """`--floor-reconstruction occupancy` on a mesh backend recovers the notch."""
    obj_path = tmp_path / "dense_l.obj"
    _write_dense_l_prism_obj(obj_path)

    rc = main(
        ["ingest", "--backend", "polycam", "--input", str(obj_path),
         "--out-dir", str(tmp_path), "--floor-reconstruction", "occupancy"]
    )
    assert rc == 0
    room = read_room_yaml(tmp_path / "room.yaml")
    # Occupancy keeps the re-entrant corner → >=6 vertices (an L has 6 corners).
    assert len(room.floor_polygon) >= 6


def test_cli_occupancy_notice_for_mesh_backend(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Occupancy on a mesh backend emits the ROBUSTNESS / n=1 / NOT-guarantee NOTE."""
    obj_path = tmp_path / "dense_l.obj"
    _write_dense_l_prism_obj(obj_path)

    rc = main(
        ["ingest", "--backend", "polycam", "--input", str(obj_path),
         "--out-dir", str(tmp_path), "--floor-reconstruction", "occupancy"]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "ROBUSTNESS lever" in captured.err
    assert "UNVALIDATED" in captured.err
    assert "n=1" in captured.err


def test_cli_occupancy_notice_ignored_for_non_mesh_backend(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Occupancy with a non-mesh backend (roomplan) emits an honest 'ignored' NOTE."""
    rc = main(
        ["ingest", "--backend", "roomplan", "--input", str(_FIXTURE_JSON),
         "--out-dir", str(tmp_path), "--floor-reconstruction", "occupancy"]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "occupancy is ignored for --backend roomplan" in captured.err


def test_cli_env_var_honored_when_flag_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HIGH regression guard: omitting --floor-reconstruction still honors env var.

    Pre-0.32.0 behaviour: ``ROOMESTIM_MESH_FLOOR_RECON=concave`` with no CLI
    flag → concave mode (env var respected). The fix (default=None) preserves
    this; a default="convex" would silently defeat the env var.
    """
    obj_path = tmp_path / "l_room.obj"
    _write_l_prism_obj(obj_path)

    monkeypatch.setenv("ROOMESTIM_MESH_FLOOR_RECON", "concave")
    rc = main(
        ["ingest", "--backend", "polycam", "--input", str(obj_path),
         "--out-dir", str(tmp_path)]  # NO --floor-reconstruction flag
    )
    assert rc == 0
    room = read_room_yaml(tmp_path / "room.yaml")
    # Env var honored → concave mode → notch preserved (>=6 vertices).
    assert len(room.floor_polygon) >= 6


# --------------------------------------------------------------------------- #
# D103 — `--algorithm` default = vbap (v0.38.0; user-approved 2026-06-16)
# --------------------------------------------------------------------------- #
# Omitting --algorithm used to be a parser error (required=True). It now
# defaults to vbap (always-works fixed-radius ring; geometry-blind). dbap was
# NOT chosen as default because place/dispatch.py requires a wall/ceiling
# surface and would crash on geometry-less inputs.


def test_place_algorithm_defaults_to_vbap_in_parser(tmp_path: Path) -> None:
    """Parser default: omitting --algorithm resolves to vbap (not a parse error)."""
    from roomestim.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(
        ["place", "--in-room", str(tmp_path / "room.yaml"),
         "--out-dir", str(tmp_path / "out")]  # NO --algorithm flag
    )
    assert args.algorithm == "vbap"


def test_run_algorithm_defaults_to_vbap_in_parser() -> None:
    """The composite `run` subparser also defaults --algorithm to vbap."""
    from roomestim.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(
        ["run", "--backend", "roomplan", "--input", str(_FIXTURE_JSON),
         "--out-dir", "/tmp/out"]  # NO --algorithm flag
    )
    assert args.algorithm == "vbap"


def test_place_without_algorithm_produces_vbap_layout(tmp_path: Path) -> None:
    """End-to-end: `place` with no --algorithm == explicit `--algorithm vbap`."""
    room_yaml = tmp_path / "room.yaml"
    _write_valid_room_yaml(room_yaml)

    out_default = tmp_path / "out_default"
    out_explicit = tmp_path / "out_explicit"

    rc_default = main(
        ["place", "--in-room", str(room_yaml), "--out-dir", str(out_default)]
    )  # NO --algorithm flag
    rc_explicit = main(
        ["place", "--in-room", str(room_yaml), "--algorithm", "vbap",
         "--out-dir", str(out_explicit)]
    )

    assert rc_default == 0
    assert rc_explicit == 0
    layout_default = (out_default / "layout.yaml").read_text(encoding="utf-8")
    layout_explicit = (out_explicit / "layout.yaml").read_text(encoding="utf-8")
    # Default resolves to vbap → byte-identical to the explicit-vbap layout.
    assert layout_default == layout_explicit
