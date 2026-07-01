"""Headless contract + physics-parity + error tests for ``POST /api/evaluate``.

The FastAPI layer (immersive-layout P5.1) is a thin serve/validate/call/serialise
wrapper over the frozen P3 trade-off engine. These tests assert the JSON contract,
prove the server adds ZERO physics (byte-equal to a direct in-process
``evaluate_layout`` call), and verify the honesty/error discipline (generic
messages, no leaked internals).

``pytest.importorskip("fastapi")`` keeps the suite portable to envs WITHOUT the
``[server]`` extra; in the canonical miniforge env fastapi is installed so these
run in the default gate.
"""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from roomestim.design.tradeoff import evaluate_layout, tradeoff_to_dict  # noqa: E402
from roomestim.model import (  # noqa: E402
    PlacedSpeaker,
    PlacementResult,
    Point3,
)
from roomestim.spec.speaker_spec import BUILTIN_SPEAKER_CATALOG  # noqa: E402
from roomestim_server.app import create_app  # noqa: E402
from roomestim_server.rooms import BUILTIN_SHOEBOX_ID, get_room  # noqa: E402


def _client() -> TestClient:
    return TestClient(create_app())


def _valid_body() -> dict[str, object]:
    return {
        "room_id": BUILTIN_SHOEBOX_ID,
        "placement": {
            "target_algorithm": "vbap",
            "regularity_hint": "ring",
            "layout_name": "live-edit",
            "speakers": [
                {"channel": 1, "position": {"x": 1.8, "y": 1.2, "z": 1.8},
                 "aim_direction": None},
                {"channel": 2, "position": {"x": -1.8, "y": 1.2, "z": 1.8},
                 "aim_direction": None},
            ],
        },
        "spec": {"model_key": "generic_surround_compact", "price": None},
        "params": {"drive_w": 10.0, "target_spl_db": 85.0, "measured_rt60_s": None},
    }


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #


def test_evaluate_success_contract() -> None:
    resp = _client().post("/api/evaluate", json=_valid_body())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    report = body["report"]
    # note-first (mirrors tradeoff_to_dict).
    assert next(iter(report)) == "note"
    # all four axes + RT60 context present.
    for key in ("spl", "angular", "interference", "cost", "rt60"):
        assert key in report, key
    # honesty fields surfaced.
    assert report["spl_provenance"] in ("datasheet", "estimate", "mixed")
    assert report["rt60"]["source"] in ("measured", "predicted")


def test_evaluate_measured_rt60_injection() -> None:
    body = _valid_body()
    body["params"] = {"drive_w": 10.0, "target_spl_db": 85.0, "measured_rt60_s": 0.55}
    report = _client().post("/api/evaluate", json=body).json()["report"]
    assert report["rt60"]["source"] == "measured"
    assert report["rt60"]["measured_s"] == 0.55


def test_evaluate_non_positive_rt60_falls_back_to_predicted() -> None:
    """measured_rt60_s <= 0 → model prediction is used (no error)."""
    body = _valid_body()
    body["params"] = {"drive_w": 10.0, "target_spl_db": 85.0, "measured_rt60_s": 0.0}
    report = _client().post("/api/evaluate", json=body).json()["report"]
    assert report["rt60"]["source"] == "predicted"
    assert report["rt60"]["measured_s"] is None


# --------------------------------------------------------------------------- #
# ★ Physics parity — the NO-FAKE-NUMBERS guard
# --------------------------------------------------------------------------- #


def test_evaluate_physics_parity_byte_equal() -> None:
    """API report == tradeoff_to_dict(evaluate_layout(<same inputs, in-process>)).

    Proves the server adds zero physics and zero drift (D29 / no fake numbers).
    """
    body = _valid_body()
    api_report = _client().post("/api/evaluate", json=body).json()["report"]

    # Build the identical inputs directly and call the core engine in-process.
    room = get_room(BUILTIN_SHOEBOX_ID)
    spec = BUILTIN_SPEAKER_CATALOG["generic_surround_compact"]
    placement = PlacementResult(
        target_algorithm="vbap",
        regularity_hint="ring",
        layout_name="live-edit",
        speakers=[
            PlacedSpeaker(channel=1, position=Point3(1.8, 1.2, 1.8)),
            PlacedSpeaker(channel=2, position=Point3(-1.8, 1.2, 1.8)),
        ],
    )
    direct = tradeoff_to_dict(
        evaluate_layout(
            room,
            placement,
            spec,
            listener_area=room.listener_area,
            drive_w=10.0,
            target_spl_db=85.0,
        )
    )
    assert api_report == direct


def test_evaluate_moved_speaker_changes_report_and_stays_parity() -> None:
    """A moved-speaker payload yields a different report, still byte-equal to core."""
    base = _valid_body()
    seed_report = _client().post("/api/evaluate", json=base).json()["report"]

    moved = _valid_body()
    moved["placement"]["speakers"][0]["position"] = {"x": 0.6, "y": 1.2, "z": 0.6}
    api_report = _client().post("/api/evaluate", json=moved).json()["report"]
    assert api_report != seed_report

    room = get_room(BUILTIN_SHOEBOX_ID)
    spec = BUILTIN_SPEAKER_CATALOG["generic_surround_compact"]
    placement = PlacementResult(
        target_algorithm="vbap",
        regularity_hint="ring",
        layout_name="live-edit",
        speakers=[
            PlacedSpeaker(channel=1, position=Point3(0.6, 1.2, 0.6)),
            PlacedSpeaker(channel=2, position=Point3(-1.8, 1.2, 1.8)),
        ],
    )
    direct = tradeoff_to_dict(
        evaluate_layout(
            room, placement, spec, listener_area=room.listener_area,
            drive_w=10.0, target_spl_db=85.0,
        )
    )
    assert api_report == direct


# --------------------------------------------------------------------------- #
# Errors — generic body, no leaked internals
# --------------------------------------------------------------------------- #


def _assert_no_internals(text: str) -> None:
    for needle in ("Traceback", "ValueError(", "ValueError:", ".py", "/home/", "File \""):
        assert needle not in text, f"leaked internals: {needle!r} in {text!r}"


def test_too_few_speakers_400_generic() -> None:
    body = _valid_body()
    body["placement"]["speakers"] = body["placement"]["speakers"][:1]  # type: ignore[index]
    resp = _client().post("/api/evaluate", json=body)
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_REQUEST"
    assert payload["error"]["message"]
    _assert_no_internals(resp.text)


def test_drive_w_non_positive_400() -> None:
    body = _valid_body()
    body["params"] = {"drive_w": 0.0, "target_spl_db": 85.0}
    resp = _client().post("/api/evaluate", json=body)
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_unknown_spec_key_400_generic() -> None:
    body = _valid_body()
    body["spec"] = {"model_key": "does_not_exist"}
    resp = _client().post("/api/evaluate", json=body)
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_unknown_room_id_400_generic() -> None:
    body = _valid_body()
    body["room_id"] = "builtin:nope"
    resp = _client().post("/api/evaluate", json=body)
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_internal_error_500_generic_no_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-ValueError from the service hits the global handler → 500, no leak.

    app.py does ``from roomestim_server.service import evaluate_request``, so the
    route closed over ``roomestim_server.app.evaluate_request`` — patch THAT name.
    ``raise_server_exceptions=False`` lets the app's handler run (vs re-raising).
    """
    import roomestim_server.app as app_module

    def _boom(_request: object) -> dict[str, object]:
        raise RuntimeError("boom /home/secret/x.py")

    monkeypatch.setattr(app_module, "evaluate_request", _boom)
    client = TestClient(create_app(), raise_server_exceptions=False)
    resp = client.post("/api/evaluate", json=_valid_body())
    assert resp.status_code == 500
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "INTERNAL"
    _assert_no_internals(resp.text)


def test_malformed_body_missing_field_422() -> None:
    resp = _client().post("/api/evaluate", json={"room_id": BUILTIN_SHOEBOX_ID})
    assert resp.status_code == 422
    assert resp.json()["ok"] is False
    assert resp.json()["error"]["code"] == "VALIDATION"


def test_malformed_body_wrong_type_422() -> None:
    body = _valid_body()
    body["params"] = {"drive_w": "not-a-number", "target_spl_db": 85.0}
    resp = _client().post("/api/evaluate", json=body)
    assert resp.status_code == 422
    assert resp.json()["ok"] is False
    assert resp.json()["error"]["code"] == "VALIDATION"


# --------------------------------------------------------------------------- #
# /healthz
# --------------------------------------------------------------------------- #


def test_healthz() -> None:
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --------------------------------------------------------------------------- #
# Core boundary — import roomestim is fastapi-free; guard error when fastapi absent
# --------------------------------------------------------------------------- #


def test_import_roomestim_in_subprocess_does_not_load_fastapi() -> None:
    """``import roomestim`` must NOT pull fastapi as a side effect.

    Asserted in a CLEAN subprocess so an in-process fastapi import by sibling
    tests cannot mask a real core leak (the authoritative isolated check).
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import roomestim, sys; "
            "assert 'fastapi' not in sys.modules, 'core leaked fastapi'; "
            "print('ok')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_create_app_friendly_error_when_fastapi_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``roomestim_server.create_app`` raises the install-hint ImportError if fastapi absent.

    Simulated by poisoning ``sys.modules['fastapi'] = None`` and dropping the
    cached ``roomestim_server`` modules so the lazy ``app`` import re-runs and the
    ``from fastapi import ...`` inside it fails — exercising the guard path.
    """
    monkeypatch.setitem(sys.modules, "fastapi", None)
    for name in list(sys.modules):
        if name == "roomestim_server" or name.startswith("roomestim_server."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    rs = importlib.import_module("roomestim_server")
    with pytest.raises(ImportError, match=r"roomestim\[server\]"):
        rs.create_app()
