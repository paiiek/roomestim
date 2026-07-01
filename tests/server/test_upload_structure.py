"""Headless tests for P5.6 — ``POST /api/rooms/upload/structure``.

The CapturedStructure (multi-room) upload endpoint delegates parsing ENTIRELY to
the torch-free core adapter ``roomestim.adapters.roomplan_structure.parse_structure``
(json+numpy+shapely — D29, the server adds no geometry math), splitting a real Apple
export into one ``RoomModel`` per section. These tests assert the multi-room JSON
contract (``{"rooms": [...]}``), that EACH returned id is retrievable + evaluable,
the single-section case, the generic-message error discipline (ADR 0038, no leaked
internals), the size cap, and that the existing single-room upload paths are
unchanged (additive regression guard).

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

_REAL_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "roomplan_real"
)
_MULTIROOM = _REAL_DIR / "capturedstructure_multiroom.json"
_SINGLE = _REAL_DIR / "capturedstructure_single.json"
_LAB_ROOM_JSON = (
    Path(__file__).resolve().parents[1] / "fixtures" / "lab_room.json"
)


def _client() -> TestClient:
    return TestClient(create_app())


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
# Happy path — multi-room split, each room retrievable + evaluable
# --------------------------------------------------------------------------- #


def test_upload_structure_multiroom_four_rooms() -> None:
    text = _MULTIROOM.read_text(encoding="utf-8")
    resp = _client().post("/api/rooms/upload/structure", json={"structure_json": text})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    rooms = body["rooms"]
    assert isinstance(rooms, list)
    assert len(rooms) == 4  # bedroom, bedroom-2, bathroom, unidentified
    ids = [r["id"] for r in rooms]
    assert all(rid.startswith("uploaded:") for rid in ids)
    assert len(set(ids)) == 4  # each room gets its own registered id
    for room in rooms:
        assert room["floor_polygon"]  # geometry-only render fields present


def test_upload_structure_each_id_usable_end_to_end() -> None:
    client = _client()
    text = _MULTIROOM.read_text(encoding="utf-8")
    up = client.post("/api/rooms/upload/structure", json={"structure_json": text})
    rooms = up.json()["rooms"]
    assert len(rooms) == 4

    for room in rooms:
        room_id = room["id"]
        # Retrievable as geometry.
        geo = client.get(f"/api/rooms/{room_id}")
        assert geo.status_code == 200
        assert geo.json()["id"] == room_id
        # Usable as room_id in /api/evaluate (the whole point of the upload).
        eval_resp = client.post("/api/evaluate", json=_valid_eval_body(room_id))
        assert eval_resp.status_code == 200
        assert eval_resp.json()["ok"] is True


def test_upload_structure_single_section_one_room() -> None:
    text = _SINGLE.read_text(encoding="utf-8")
    resp = _client().post("/api/rooms/upload/structure", json={"structure_json": text})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert len(body["rooms"]) == 1
    assert body["rooms"][0]["id"].startswith("uploaded:")


# --------------------------------------------------------------------------- #
# Errors — generic body, no leaked internals
# --------------------------------------------------------------------------- #


def test_upload_structure_malformed_json_400_generic() -> None:
    resp = _client().post(
        "/api/rooms/upload/structure", json={"structure_json": "{not valid"}
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["message"]
    _assert_no_internals(resp.text)


def test_upload_structure_no_sections_400_generic() -> None:
    # Well-formed JSON that is NOT a CapturedStructure (no sections[]) → 400.
    resp = _client().post(
        "/api/rooms/upload/structure", json={"structure_json": '{"label": "nope"}'}
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_upload_structure_non_object_payload_400_generic() -> None:
    resp = _client().post(
        "/api/rooms/upload/structure", json={"structure_json": "[1, 2, 3]"}
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_upload_structure_missing_field_422() -> None:
    resp = _client().post("/api/rooms/upload/structure", json={})
    assert resp.status_code == 422
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION"


def test_upload_structure_oversize_422() -> None:
    # The ~10 MB structure_json cap rejects an oversize body at the schema (422),
    # before it is written to a temp file / parsed.
    huge = "a" * 10_000_001
    resp = _client().post("/api/rooms/upload/structure", json={"structure_json": huge})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION"


# --------------------------------------------------------------------------- #
# Regression guard — the existing single-room upload paths are unchanged
# --------------------------------------------------------------------------- #


def test_room_yaml_upload_still_works(tmp_path: Path) -> None:
    out = tmp_path / "room.yaml"
    write_room_yaml(get_room(BUILTIN_SHOEBOX_ID), out)
    resp = _client().post(
        "/api/rooms/upload", json={"room_yaml": out.read_text(encoding="utf-8")}
    )
    assert resp.status_code == 200
    assert resp.json()["room"]["id"].startswith("uploaded:")


def test_roomplan_single_upload_still_works() -> None:
    text = _LAB_ROOM_JSON.read_text(encoding="utf-8")
    resp = _client().post("/api/rooms/upload/roomplan", json={"roomplan_json": text})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["room"]["id"].startswith("uploaded:")  # single-room shape unchanged
