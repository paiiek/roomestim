"""Headless tests for P5.6 — bundled example loader (``/api/examples``).

``GET /api/examples`` lists the bundled example-capture manifest; ``POST
/api/examples/{id}/load`` reads a shipped file and parses it via the SAME
server-side path as an upload (D29 — no client physics): a ``roomplan``-format
example returns ``{"room": ...}``, a ``structure``-format example returns
``{"rooms": [...]}``. These tests assert the manifest, that EVERY shipped example
loads (guarding against shipping a broken example), that returned ids are
retrievable, and that an unknown id → generic 404 (ADR 0038, no leaked internals).

``pytest.importorskip("fastapi")`` keeps the suite portable to envs WITHOUT the
``[server]`` extra; in the canonical miniforge env fastapi is installed so these
run in the default gate.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from roomestim_server.app import create_app  # noqa: E402


def _client() -> TestClient:
    return TestClient(create_app())


def _assert_no_internals(text: str) -> None:
    for needle in ("Traceback", "ValueError(", "ValueError:", ".py", "/home/", 'File "'):
        assert needle not in text, f"leaked internals: {needle!r} in {text!r}"


# --------------------------------------------------------------------------- #
# GET /api/examples — manifest
# --------------------------------------------------------------------------- #


def test_list_examples_manifest() -> None:
    resp = _client().get("/api/examples")
    assert resp.status_code == 200
    examples = resp.json()["examples"]
    assert isinstance(examples, list)
    assert len(examples) >= 3
    for ex in examples:
        assert ex["id"]
        assert ex["name"]
        assert ex["format"] in ("roomplan", "structure")
    # The three known ids ship.
    ids = {ex["id"] for ex in examples}
    assert {
        "lab_room_synthetic",
        "capturedstructure_single",
        "capturedstructure_multiroom",
    } <= ids


# --------------------------------------------------------------------------- #
# POST /api/examples/{id}/load — correct shape per format
# --------------------------------------------------------------------------- #


def test_load_roomplan_example_returns_single_room() -> None:
    client = _client()
    resp = client.post("/api/examples/lab_room_synthetic/load")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "room" in body and "rooms" not in body
    room_id = body["room"]["id"]
    assert room_id.startswith("uploaded:")
    assert client.get(f"/api/rooms/{room_id}").status_code == 200


def test_load_structure_example_returns_multiple_rooms() -> None:
    client = _client()
    resp = client.post("/api/examples/capturedstructure_multiroom/load")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "rooms" in body and "room" not in body
    rooms = body["rooms"]
    assert len(rooms) == 4
    for room in rooms:
        assert client.get(f"/api/rooms/{room['id']}").status_code == 200


def test_every_shipped_example_loads() -> None:
    # Guard against shipping a broken example: iterate the live manifest and assert
    # each bundled file actually parses to the shape its declared format promises.
    client = _client()
    examples = client.get("/api/examples").json()["examples"]
    assert examples
    for ex in examples:
        resp = client.post(f"/api/examples/{ex['id']}/load")
        assert resp.status_code == 200, f"example {ex['id']} failed to load"
        body = resp.json()
        assert body["ok"] is True
        if ex["format"] == "structure":
            assert isinstance(body["rooms"], list) and body["rooms"]
        else:
            assert body["room"]["id"].startswith("uploaded:")


# --------------------------------------------------------------------------- #
# P6.B — the bundled column example loads and exposes a renderable column box
# --------------------------------------------------------------------------- #


def test_column_example_loads_with_column_object() -> None:
    client = _client()
    resp = client.post("/api/examples/lab_room_with_column/load")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "room" in body and "rooms" not in body
    room_id = body["room"]["id"]
    assert room_id.startswith("uploaded:")

    geom = client.get(f"/api/rooms/{room_id}").json()
    # Ceiling exposed for the enclosed-room render.
    assert isinstance(geom["ceiling"], list) and geom["ceiling"]
    # At least one column with the box fields the viewer needs.
    columns = [o for o in geom["objects"] if o["kind"] == "column"]
    assert len(columns) >= 1
    col = columns[0]
    assert {"x", "y", "z"} <= set(col["anchor"])
    for field in ("width_m", "depth_m", "height_m"):
        assert isinstance(col[field], (int, float)) and col[field] > 0


# --------------------------------------------------------------------------- #
# ★ Frame normalisation — a captured room is recentred to the canonical Frame A
#   (floor at y=0, listener centroid at the horizontal origin) at registration
# --------------------------------------------------------------------------- #


def test_captured_room_recentred_to_listener_origin() -> None:
    """A real captured room (own world frame) comes back centred on Frame A.

    The bundled ``capturedstructure_single`` living-room is authored near
    ``x≈1.22, z≈0.04`` with the floor at ``y≈−1.02``; registration recentres it so
    the listener centroid sits at the horizontal origin and the floor sits at y=0.
    """
    client = _client()
    room = client.post("/api/examples/capturedstructure_single/load").json()["rooms"][0]

    c = room["listener_area"]["centroid"]
    assert c["x"] == pytest.approx(0.0, abs=1e-6)
    assert c["z"] == pytest.approx(0.0, abs=1e-6)

    wall_ys = [p["y"] for w in room["walls"] for p in w["polygon"]]
    assert wall_ys
    assert min(wall_ys) == pytest.approx(0.0, abs=1e-6)  # floor at y=0
    # ceiling_height_m is floor-relative and unchanged by the rigid translation.
    assert max(wall_ys) == pytest.approx(room["ceiling_height_m"], abs=1e-3)


# --------------------------------------------------------------------------- #
# Errors — unknown id → generic 404, no leaked internals
# --------------------------------------------------------------------------- #


def test_load_unknown_example_404_generic() -> None:
    resp = _client().post("/api/examples/does_not_exist/load")
    assert resp.status_code == 404
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "EXAMPLE_NOT_FOUND"
    assert payload["error"]["message"]
    _assert_no_internals(resp.text)
