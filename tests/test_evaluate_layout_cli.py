"""Tests for the `evaluate-layout` CLI subcommand (ADR 0060 §Status-update, P3).

The handler is a THIN WRAPPER over the already-tested
``roomestim.design.tradeoff.evaluate_layout`` (see ``tests/test_tradeoff.py`` for
the composition / physics contract). These tests lock the CLI plumbing +
honesty: exit codes, the stdout/stderr surfaces, the note-first JSON shape, the
spec-source resolution (built-in vs unknown key), the price injection arithmetic,
the measured-RT60 branch, and the error propagation. Core / torch-free (numpy-
free), no optional extra — default gate.
"""

from __future__ import annotations

import json
from pathlib import Path

from roomestim.cli import main
from roomestim.export.layout_yaml import write_layout_yaml
from roomestim.export.room_yaml import write_room_yaml
from roomestim.place.vbap import place_vbap_ring
from tests.fixtures.synthetic_rooms import shoebox


def _fixture_yamls(tmp_path: Path) -> tuple[str, str]:
    """Write a shoebox room.yaml + an 8-speaker VBAP ring layout.yaml on disk."""
    room_path = tmp_path / "room.yaml"
    layout_path = tmp_path / "layout.yaml"
    write_room_yaml(shoebox(), room_path, schema_version="0.1-draft")
    # validate=False: skip the engine-schema round-trip (no engine repo needed).
    write_layout_yaml(place_vbap_ring(8, radius_m=2.0), layout_path, validate=False)
    return str(room_path), str(layout_path)


def test_cli_json_happy_path(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    room_yaml, layout_yaml = _fixture_yamls(tmp_path)
    rc = main(
        ["evaluate-layout", "--in-room", room_yaml, "--in-placement", layout_yaml, "--json"]
    )
    assert rc == 0
    out = capsys.readouterr()
    payload = json.loads(out.out)
    # note first (insertion order preserved in the dict / JSON object).
    assert next(iter(payload)) == "note"
    # all four axes present.
    assert "spl" in payload  # level
    assert "angular" in payload  # panning
    assert "interference" in payload  # separation
    assert "cost" in payload  # cost
    assert payload["n_speakers"] == 8


def test_cli_spec_model_price_populates_cost(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    room_yaml, layout_yaml = _fixture_yamls(tmp_path)
    rc = main(
        [
            "evaluate-layout",
            "--in-room", room_yaml,
            "--in-placement", layout_yaml,
            "--spec-model", "generic_surround_compact",
            "--price", "125",
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    cost = payload["cost"]
    assert cost["n_speakers"] == 8
    assert cost["n_priced"] == 8
    assert cost["complete"] is True
    assert cost["total_price"] == 8 * 125  # exact arithmetic sum


def test_cli_measured_rt60_injection(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    room_yaml, layout_yaml = _fixture_yamls(tmp_path)

    rc = main(
        [
            "evaluate-layout",
            "--in-room", room_yaml,
            "--in-placement", layout_yaml,
            "--measured-rt60", "0.4",
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rt60"]["source"] == "measured"
    assert payload["rt60"]["measured_s"] == 0.4

    # omitted → model-predicted
    rc = main(
        ["evaluate-layout", "--in-room", room_yaml, "--in-placement", layout_yaml, "--json"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rt60"]["source"] == "predicted"
    assert payload["rt60"]["measured_s"] is None

    # non-positive --measured-rt60 is NOT an error: it silently falls back to the
    # model-predicted RT60 (rc 0), matching the --measured-rt60 help text and the
    # P4 web _is_finite_positive semantics. Locks the doc-accuracy fix.
    rc = main(
        [
            "evaluate-layout",
            "--in-room", room_yaml,
            "--in-placement", layout_yaml,
            "--measured-rt60", "-1",
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rt60"]["source"] == "predicted"
    assert payload["rt60"]["measured_s"] is None


def test_cli_human_output(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    room_yaml, layout_yaml = _fixture_yamls(tmp_path)
    rc = main(["evaluate-layout", "--in-room", room_yaml, "--in-placement", layout_yaml])
    assert rc == 0
    out = capsys.readouterr()
    assert "trade-off" in out.out
    # honesty NOTE goes to stderr.
    assert "NOTE:" in out.err


def test_cli_unknown_spec_model_exits_1(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    room_yaml, layout_yaml = _fixture_yamls(tmp_path)
    rc = main(
        [
            "evaluate-layout",
            "--in-room", room_yaml,
            "--in-placement", layout_yaml,
            "--spec-model", "nope",
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "error:" in err
    assert "nope" in err
    assert "generic_surround_compact" in err  # lists the valid keys


def test_cli_missing_room_file_exits_1(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    _room_yaml, layout_yaml = _fixture_yamls(tmp_path)
    rc = main(
        [
            "evaluate-layout",
            "--in-room", "/no/such/room.yaml",
            "--in-placement", layout_yaml,
        ]
    )
    assert rc == 1
    assert "error:" in capsys.readouterr().err
