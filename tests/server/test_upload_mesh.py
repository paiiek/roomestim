"""Headless tests for P5.7 Feature B — ``POST /api/rooms/upload/mesh``.

A BINARY mesh file (``.obj``/``.gltf``/``.glb``/``.ply``/``.usdz``) is uploaded as
base64 in a JSON string field (NOT multipart — the server needs NO python-multipart
dep) and parsed ENTIRELY by core ``roomestim.adapters.mesh.MeshAdapter().parse``
(D29 — the server adds no geometry math). These tests assert the round-trip
(upload → geometry → evaluate), the generic-message error discipline (ADR 0038, no
leaked internals), and that the existing text uploads still work (regression).

``.usdz`` needs the optional ``[usd]`` extra (pxr); the usdz test is written so it
PASSES whether pxr is installed (→ 200) or absent (→ 400) — never a 500/leak.

``pytest.importorskip("fastapi")`` keeps the suite portable to envs WITHOUT the
``[server]`` extra; in the canonical miniforge env fastapi is installed so these
run in the default gate.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from roomestim.export.room_yaml import write_room_yaml  # noqa: E402
from roomestim_server.app import create_app  # noqa: E402
from roomestim_server.rooms import (  # noqa: E402
    BUILTIN_SHOEBOX_ID,
    get_room,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _client() -> TestClient:
    return TestClient(create_app())


def _b64_of(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _assert_no_internals(text: str) -> None:
    for needle in ("Traceback", "ValueError(", "ValueError:", ".py", "/home/", 'File "'):
        assert needle not in text, f"leaked internals: {needle!r} in {text!r}"


# --------------------------------------------------------------------------- #
# Round-trip — upload → geometry → evaluate
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("fixture", ["lab_room.gltf", "lab_room.obj", "lab_room.ply"])
def test_upload_mesh_round_trip_and_usable(fixture: str) -> None:
    client = _client()
    path = _FIXTURES / fixture
    resp = client.post(
        "/api/rooms/upload/mesh",
        json={"filename": fixture, "content_b64": _b64_of(path)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    room = body["room"]
    room_id = room["id"]
    assert room_id.startswith("uploaded:")
    assert room["floor_polygon"]  # non-empty geometry

    # Retrievable via GET.
    assert client.get(f"/api/rooms/{room_id}").status_code == 200

    # Usable end-to-end in /api/evaluate.
    eval_body = {
        "room_id": room_id,
        "placement": {
            "speakers": [
                {"channel": 1, "position": {"x": -0.5, "y": 1.0, "z": 0.5}},
                {"channel": 2, "position": {"x": 0.5, "y": 1.0, "z": 0.5}},
            ]
        },
    }
    eval_resp = client.post("/api/evaluate", json=eval_body)
    assert eval_resp.status_code == 200, eval_resp.text
    assert eval_resp.json()["ok"] is True


def test_upload_mesh_usdz_installed_or_not_but_never_leaks() -> None:
    """`.usdz` → 200 when the [usd] extra (pxr) is installed, else generic 400."""
    client = _client()
    path = _FIXTURES / "shoebox_zup.usdz"
    resp = client.post(
        "/api/rooms/upload/mesh",
        json={"filename": "shoebox_zup.usdz", "content_b64": _b64_of(path)},
    )
    assert resp.status_code in (200, 400), resp.text
    if resp.status_code == 200:
        assert resp.json()["ok"] is True
        assert resp.json()["room"]["id"].startswith("uploaded:")
    else:
        assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


# --------------------------------------------------------------------------- #
# Errors — generic body, no leaked internals
# --------------------------------------------------------------------------- #


def test_upload_mesh_bad_base64_400_generic() -> None:
    resp = _client().post(
        "/api/rooms/upload/mesh",
        json={"filename": "lab_room.gltf", "content_b64": "!!!notb64"},
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["message"]
    _assert_no_internals(resp.text)


def test_upload_mesh_unsupported_suffix_400_generic() -> None:
    # Valid base64 but an unsupported suffix → rejected BEFORE any parse.
    resp = _client().post(
        "/api/rooms/upload/mesh",
        json={"filename": "x.txt", "content_b64": base64.b64encode(b"hello").decode()},
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_upload_mesh_garbage_bytes_for_valid_suffix_400_generic() -> None:
    # A supported suffix but the bytes are not a real mesh → adapter ValueError → 400.
    resp = _client().post(
        "/api/rooms/upload/mesh",
        json={"filename": "junk.ply", "content_b64": base64.b64encode(b"not a mesh").decode()},
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_upload_mesh_oversize_body_422() -> None:
    # A base64 payload beyond the ~90 MB transport cap is rejected at the schema.
    huge = "A" * 90_000_001
    resp = _client().post(
        "/api/rooms/upload/mesh",
        json={"filename": "big.ply", "content_b64": huge},
    )
    assert resp.status_code == 422
    assert resp.json()["ok"] is False
    assert resp.json()["error"]["code"] == "VALIDATION"


def test_upload_mesh_malformed_body_missing_field_422() -> None:
    resp = _client().post("/api/rooms/upload/mesh", json={"filename": "x.ply"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION"


# --------------------------------------------------------------------------- #
# Regression — the existing text uploads still work alongside the mesh path
# --------------------------------------------------------------------------- #


def test_existing_room_yaml_upload_still_works(tmp_path: Path) -> None:
    out = tmp_path / "room.yaml"
    write_room_yaml(get_room(BUILTIN_SHOEBOX_ID), out)
    resp = _client().post(
        "/api/rooms/upload", json={"room_yaml": out.read_text(encoding="utf-8")}
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_main_js_references_mesh_upload_wiring() -> None:
    main_js = (
        Path(__file__).resolve().parents[2]
        / "roomestim_server"
        / "static"
        / "main.js"
    ).read_text(encoding="utf-8")
    for needle in ("/api/rooms/upload/mesh", "uploadMesh", "content_b64", "arrayBuffer"):
        assert needle in main_js, f"main.js missing wiring reference: {needle!r}"
