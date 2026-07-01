"""Headless tests for the geometry-only room endpoints (immersive-layout P5.1).

``GET /api/rooms`` lists the built-ins; ``GET /api/rooms/{id}`` returns geometry
ONLY (no physics); unknown ids 404 with a generic body.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from roomestim_server.app import create_app  # noqa: E402
from roomestim_server.rooms import BUILTIN_SHOEBOX_ID  # noqa: E402


def _client() -> TestClient:
    return TestClient(create_app())


def test_list_rooms_includes_builtin() -> None:
    body = _client().get("/api/rooms").json()
    ids = [r["id"] for r in body["rooms"]]
    assert BUILTIN_SHOEBOX_ID in ids
    entry = next(r for r in body["rooms"] if r["id"] == BUILTIN_SHOEBOX_ID)
    assert entry["name"]
    assert "footprint" in entry


def test_get_room_geometry_valid() -> None:
    resp = _client().get(f"/api/rooms/{BUILTIN_SHOEBOX_ID}")
    assert resp.status_code == 200
    geom = resp.json()
    assert geom["id"] == BUILTIN_SHOEBOX_ID
    assert geom["floor_polygon"]  # non-empty
    assert all({"x", "z"} <= set(p) for p in geom["floor_polygon"])
    assert geom["ceiling_height_m"] > 0
    la = geom["listener_area"]
    assert la["polygon"]
    assert {"x", "z"} <= set(la["centroid"])
    assert geom["walls"]  # walls present
    # geometry only: no physics / material keys leaked.
    assert "rt60" not in geom
    assert "material" not in geom


def test_get_room_unknown_404_generic() -> None:
    resp = _client().get("/api/rooms/builtin:does_not_exist")
    assert resp.status_code == 404
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "ROOM_NOT_FOUND"
    assert "Traceback" not in resp.text
