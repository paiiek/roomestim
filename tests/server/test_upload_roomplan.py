"""Headless tests for P5.5 — ``POST /api/rooms/upload/roomplan``.

The RoomPlan-JSON upload endpoint delegates parsing ENTIRELY to the torch-free
core adapter ``roomestim.adapters.roomplan.RoomPlanAdapter`` (json+numpy only —
D29, the server adds no geometry math). These tests assert the JSON contract, an
end-to-end upload → geometry → evaluate round-trip, the generic-message error
discipline (ADR 0038, no leaked internals), the size cap, and that the existing
room.yaml upload path is unchanged (additive regression guard).

``pytest.importorskip("fastapi")`` keeps the suite portable to envs WITHOUT the
``[server]`` extra; in the canonical miniforge env fastapi is installed so these
run in the default gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from roomestim.export.room_yaml import write_room_yaml  # noqa: E402
from roomestim_server.app import create_app  # noqa: E402
from roomestim_server.rooms import BUILTIN_SHOEBOX_ID, get_room  # noqa: E402

_LAB_ROOM_JSON = (
    Path(__file__).resolve().parents[1] / "fixtures" / "lab_room.json"
)


def _client() -> TestClient:
    return TestClient(create_app())


def _roomplan_text() -> str:
    return _LAB_ROOM_JSON.read_text(encoding="utf-8")


def _assert_no_internals(text: str) -> None:
    for needle in ("Traceback", "ValueError(", "ValueError:", ".py", "/home/", 'File "'):
        assert needle not in text, f"leaked internals: {needle!r} in {text!r}"


def _valid_eval_body(room_id: str) -> dict[str, object]:
    return {
        "room_id": room_id,
        "placement": {
            "speakers": [
                {"channel": 1, "position": {"x": -1.5, "y": 1.2, "z": 1.8}},
                {"channel": 2, "position": {"x": 1.5, "y": 1.2, "z": 1.8}},
            ]
        },
    }


# --------------------------------------------------------------------------- #
# Happy path — parse + geometry
# --------------------------------------------------------------------------- #


def test_upload_roomplan_happy_path() -> None:
    resp = _client().post(
        "/api/rooms/upload/roomplan", json={"roomplan_json": _roomplan_text()}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    room = body["room"]
    assert room["id"].startswith("uploaded:")
    # Geometry-only fields the viewer renders (from RoomPlanAdapter).
    assert room["floor_polygon"]
    assert room["walls"]


# --------------------------------------------------------------------------- #
# End-to-end — registered id retrievable + usable in /api/evaluate
# --------------------------------------------------------------------------- #


def test_upload_roomplan_id_usable_end_to_end() -> None:
    client = _client()
    up = client.post(
        "/api/rooms/upload/roomplan", json={"roomplan_json": _roomplan_text()}
    )
    room_id = up.json()["room"]["id"]

    # Retrievable as geometry.
    geo = client.get(f"/api/rooms/{room_id}")
    assert geo.status_code == 200
    assert geo.json()["id"] == room_id

    # Usable as room_id in /api/evaluate (the whole point of the upload).
    eval_resp = client.post("/api/evaluate", json=_valid_eval_body(room_id))
    assert eval_resp.status_code == 200
    assert eval_resp.json()["ok"] is True


# --------------------------------------------------------------------------- #
# Errors — generic body, no leaked internals
# --------------------------------------------------------------------------- #


def test_upload_roomplan_malformed_json_400_generic() -> None:
    resp = _client().post(
        "/api/rooms/upload/roomplan", json={"roomplan_json": "{not valid"}
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["message"]
    _assert_no_internals(resp.text)


def test_upload_roomplan_valid_json_but_not_a_room_400_generic() -> None:
    # Well-formed JSON that is NOT a valid RoomPlan sidecar (no floors[]) → 400.
    resp = _client().post(
        "/api/rooms/upload/roomplan", json={"roomplan_json": '{"label": "nope"}'}
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_upload_roomplan_non_object_payload_400_generic() -> None:
    # Well-formed JSON that is NOT an object (a JSON array) — the adapter's
    # dict-based sidecar parse rejects it → generic 400 (never a raw 500). Same
    # generic path a ``.usdz``-semantics payload would take (the adapter raises;
    # the helper maps ANY parse failure to a client-attributable 400).
    resp = _client().post(
        "/api/rooms/upload/roomplan", json={"roomplan_json": "[1, 2, 3]"}
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_upload_roomplan_missing_field_422() -> None:
    resp = _client().post("/api/rooms/upload/roomplan", json={})
    assert resp.status_code == 422
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION"


def test_upload_roomplan_oversize_422() -> None:
    # The ~5 MB roomplan_json cap rejects an oversize body at the schema (422),
    # before it is written to a temp file / parsed.
    huge = "a" * 5_000_001
    resp = _client().post("/api/rooms/upload/roomplan", json={"roomplan_json": huge})
    assert resp.status_code == 422
    assert resp.json()["ok"] is False
    assert resp.json()["error"]["code"] == "VALIDATION"


# --------------------------------------------------------------------------- #
# Regression guard — the existing room.yaml upload path is unchanged
# --------------------------------------------------------------------------- #


def test_room_yaml_upload_still_works(tmp_path: Path) -> None:
    out = tmp_path / "room.yaml"
    write_room_yaml(get_room(BUILTIN_SHOEBOX_ID), out)
    text = out.read_text(encoding="utf-8")

    resp = _client().post("/api/rooms/upload", json={"room_yaml": text})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["room"]["id"].startswith("uploaded:")
