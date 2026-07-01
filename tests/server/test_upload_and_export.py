"""Headless tests for P5.4 — ``GET /api/specs``, ``POST /api/rooms/upload``,
and the client-side export/upload wiring (immersive-layout P5.4 / ADR 0061).

The upload endpoint delegates parsing ENTIRELY to the torch-free core reader
``roomestim.io.room_yaml_reader.read_room_yaml`` (D29 — the server adds no
geometry math); ``/api/specs`` just lists ``BUILTIN_SPEAKER_CATALOG`` metadata.
These tests assert the JSON contract, an end-to-end upload → geometry → evaluate →
place round-trip, the generic-message error discipline (ADR 0038, no leaked
internals), registry isolation, and a string-grep over ``main.js`` that guards the
export/upload wiring without executing JS.

NOTE: the actual file DOWNLOAD ("Export trade-off JSON") and the 3-D WebGL render
are HUMAN-verified in a browser — they cannot run headlessly. Capture-file
(roomplan/usdz/image) upload via the heavy adapter dispatch remains DEFERRED (NOT
in P5.4 — room.yaml only, parsed by the torch-free reader).

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
from roomestim_server import rooms as _rooms  # noqa: E402
from roomestim_server.rooms import (  # noqa: E402
    BUILTIN_SHOEBOX_ID,
    get_room,
    register_uploaded_room,
    room_geometry_to_dict,
)


def _client() -> TestClient:
    return TestClient(create_app())


def _valid_room_yaml_text(tmp_path: Path) -> str:
    """A valid room.yaml, generated IN-TEST from the built-in shoebox."""
    out = tmp_path / "room.yaml"
    write_room_yaml(get_room(BUILTIN_SHOEBOX_ID), out)
    return out.read_text(encoding="utf-8")


def _assert_no_internals(text: str) -> None:
    for needle in ("Traceback", "ValueError(", "ValueError:", ".py", "/home/", 'File "'):
        assert needle not in text, f"leaked internals: {needle!r} in {text!r}"


# --------------------------------------------------------------------------- #
# GET /api/specs
# --------------------------------------------------------------------------- #


def test_specs_lists_catalog() -> None:
    resp = _client().get("/api/specs")
    assert resp.status_code == 200
    specs = resp.json()["specs"]
    keys = {s["model_key"] for s in specs}
    assert keys == {
        "generic_ceiling_4in",
        "generic_surround_compact",
        "generic_pa_box_mid",
    }
    for s in specs:
        assert set(s) == {"model_key", "price", "provenance"}
        assert s["provenance"] in ("datasheet", "estimate")


# --------------------------------------------------------------------------- #
# POST /api/rooms/upload — round-trip
# --------------------------------------------------------------------------- #


def test_upload_round_trip_and_usable_end_to_end(tmp_path: Path) -> None:
    client = _client()
    text = _valid_room_yaml_text(tmp_path)

    resp = client.post("/api/rooms/upload", json={"room_yaml": text})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    room = body["room"]
    room_id = room["id"]
    assert room_id.startswith("uploaded:")

    # The returned floor_polygon matches the shoebox's (allow float rounding).
    expected = room_geometry_to_dict(get_room(BUILTIN_SHOEBOX_ID), room_id)
    assert len(room["floor_polygon"]) == len(expected["floor_polygon"])
    for got, exp in zip(room["floor_polygon"], expected["floor_polygon"]):
        assert got["x"] == pytest.approx(exp["x"])
        assert got["z"] == pytest.approx(exp["z"])

    # The uploaded room is usable end-to-end: geometry, evaluate, and place.
    assert client.get(f"/api/rooms/{room_id}").status_code == 200

    eval_body = {
        "room_id": room_id,
        "placement": {
            "speakers": [
                {"channel": 1, "position": {"x": -1.5, "y": 1.2, "z": 1.8}},
                {"channel": 2, "position": {"x": 1.5, "y": 1.2, "z": 1.8}},
            ]
        },
    }
    eval_resp = client.post("/api/evaluate", json=eval_body)
    assert eval_resp.status_code == 200
    assert eval_resp.json()["ok"] is True

    place_resp = client.post(
        "/api/place",
        json={"room_id": room_id, "algorithm": "vbap", "n_speakers": 6},
    )
    assert place_resp.status_code == 200
    assert place_resp.json()["ok"] is True


# --------------------------------------------------------------------------- #
# Errors — generic body, no leaked internals
# --------------------------------------------------------------------------- #


def test_upload_bad_yaml_400_generic() -> None:
    resp = _client().post(
        "/api/rooms/upload", json={"room_yaml": "not: [valid yaml"}
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["message"]
    _assert_no_internals(resp.text)


def test_upload_valid_yaml_but_not_a_room_400_generic() -> None:
    # Well-formed YAML that is NOT a valid room (schema/validation failure) → 400.
    resp = _client().post(
        "/api/rooms/upload", json={"room_yaml": "name: nope\nfoo: 1\n"}
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_upload_malformed_body_missing_field_422() -> None:
    resp = _client().post("/api/rooms/upload", json={})
    assert resp.status_code == 422
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION"


# --------------------------------------------------------------------------- #
# Registry isolation
# --------------------------------------------------------------------------- #


def test_two_uploads_get_distinct_ids(tmp_path: Path) -> None:
    client = _client()
    text = _valid_room_yaml_text(tmp_path)
    id1 = client.post("/api/rooms/upload", json={"room_yaml": text}).json()["room"]["id"]
    id2 = client.post("/api/rooms/upload", json={"room_yaml": text}).json()["room"]["id"]
    assert id1 != id2
    assert id1.startswith("uploaded:")
    assert id2.startswith("uploaded:")


def test_unknown_uploaded_id_404_geometry_and_400_evaluate() -> None:
    client = _client()
    assert client.get("/api/rooms/uploaded:999").status_code == 404

    eval_body = {
        "room_id": "uploaded:999",
        "placement": {
            "speakers": [
                {"channel": 1, "position": {"x": -1.5, "y": 1.2, "z": 1.8}},
                {"channel": 2, "position": {"x": 1.5, "y": 1.2, "z": 1.8}},
            ]
        },
    }
    resp = client.post("/api/evaluate", json=eval_body)
    assert resp.status_code == 400
    assert resp.json()["ok"] is False


# --------------------------------------------------------------------------- #
# Client-side wiring — string-grep over main.js (guards without executing JS)
# --------------------------------------------------------------------------- #


def test_main_js_references_p54_wiring() -> None:
    main_js = (
        Path(__file__).resolve().parents[2]
        / "roomestim_server"
        / "static"
        / "main.js"
    ).read_text(encoding="utf-8")
    for needle in (
        "/api/specs",
        "/api/rooms/upload",
        "trade-off.json",
        "room_yaml",
        "_lastReport",  # the verbatim last-report store
        "exportTradeoff",  # the export handler (no recompute)
    ):
        assert needle in main_js, f"main.js missing wiring reference: {needle!r}"


# --------------------------------------------------------------------------- #
# Registry invariants (bounded eviction, deepcopy isolation) + size cap
# --------------------------------------------------------------------------- #


def test_uploaded_registry_evicts_oldest_past_cap() -> None:
    # Registering CAP+1 rooms evicts the FIRST id (oldest-first, memory-bounded).
    room = get_room(BUILTIN_SHOEBOX_ID)
    ids = [register_uploaded_room(room) for _ in range(_rooms._UPLOADED_CAP + 1)]
    with pytest.raises(KeyError):
        get_room(ids[0])  # the oldest was evicted
    # a recent one still resolves
    assert get_room(ids[-1]) is not None


def test_get_room_deepcopy_isolates_stored_upload() -> None:
    # get_room returns a deepcopy, so mutating the returned room must NOT leak
    # into the stored copy (preserves the built-ins' no-shared-state invariant).
    room = get_room(BUILTIN_SHOEBOX_ID)
    rid = register_uploaded_room(room)
    got = get_room(rid)
    got.name = "MUTATED"
    again = get_room(rid)
    assert again.name != "MUTATED"


def test_upload_oversize_yaml_422() -> None:
    # The ~2 MB room_yaml cap rejects an oversize body at the schema (422),
    # before it is written to a temp file / parsed.
    huge = "a: 1\n" + ("#" * 2_000_001)
    resp = _client().post("/api/rooms/upload", json={"room_yaml": huge})
    assert resp.status_code == 422
    assert resp.json()["ok"] is False
    assert resp.json()["error"]["code"] == "VALIDATION"
