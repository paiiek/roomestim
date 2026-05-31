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
