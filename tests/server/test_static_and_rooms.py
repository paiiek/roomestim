"""Headless tests for the P5.2 static viewer wiring (immersive-layout P5.2).

Covers the ``GET /`` index shell, the ``/static`` StaticFiles mount, and a
string-grep contract test that ``main.js`` consumes the REAL /api/evaluate +
/api/rooms response keys (guards D29 / the JSON contract WITHOUT executing JS —
the 3-D render itself is human-verified, not headless-verifiable). The deeper
geometry asserts live in ``test_rooms_api.py``; the room check here stays light.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from roomestim_server.app import create_app  # noqa: E402
from roomestim_server.rooms import BUILTIN_SHOEBOX_ID  # noqa: E402

_STATIC_DIR = Path(__file__).resolve().parents[2] / "roomestim_server" / "static"


def _client() -> TestClient:
    return TestClient(create_app())


def test_index_serves_html() -> None:
    resp = _client().get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    # A stable marker string from index.html's <title>/<h1>.
    assert "immersive layout viewer" in resp.text


def test_static_main_js_served() -> None:
    resp = _client().get("/static/main.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"].lower()


def test_static_index_html_served() -> None:
    resp = _client().get("/static/index.html")
    assert resp.status_code == 200


def test_vendored_three_served_and_no_cdn() -> None:
    # Three.js is VENDORED + served locally (no external CDN) so the viewer works
    # offline / air-gapped and closes the supply-chain fetch-at-load surface.
    resp = _client().get("/static/vendor/three/three.module.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"].lower()
    ctrl = _client().get("/static/vendor/three/addons/controls/OrbitControls.js")
    assert ctrl.status_code == 200
    # index.html must reference the LOCAL vendor path, not a CDN, in its importmap.
    html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert "/static/vendor/three/three.module.js" in html
    assert "cdn.jsdelivr.net" not in html
    assert "http://" not in html and "https://cdn" not in html


def test_room_geometry_light() -> None:
    # Light re-assert only — the deep geometry checks live in test_rooms_api.py.
    resp = _client().get(f"/api/rooms/{BUILTIN_SHOEBOX_ID}")
    assert resp.status_code == 200
    geom = resp.json()
    assert geom["id"] == BUILTIN_SHOEBOX_ID
    assert geom["floor_polygon"]
    assert geom["walls"]


def test_main_js_references_real_contract() -> None:
    # Guards D29 / the JSON contract without executing JS: the frontend must
    # consume the documented API endpoints + response/request keys verbatim.
    text = (_STATIC_DIR / "main.js").read_text(encoding="utf-8")
    for token in (
        "/api/evaluate",
        "/api/rooms",
        "spl_provenance",
        "rt60",
        "note",
        "room_id",
        "speakers",
        # ★ nested per-axis keys — a rename in a tradeoff sub-serialiser would make
        # the viewer silently render "—"; these tokens catch that (one per axis).
        "min_spl_db",
        "min_nn_gap_deg",
        "min_pair_separation_deg",
        "total_price",
        "effective_s",
    ):
        assert token in text, f"main.js missing contract identifier: {token}"


def test_p6e_viewer_wiring_present() -> None:
    # P6.E viewer-only additions (string-grep, no JS execution): the honest algo
    # option VALUES + dome, the auto-reseed checkbox, and the drag pick-sphere +
    # on-scene label helpers. Guards against an accidental rename/removal.
    html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for token in (
        'value="vbap"',
        'value="dome"',  # NEW option (already works via /api/place)
        'value="dbap"',
        'value="coverage"',
        'id="auto-reseed"',
        "room-blind",  # honesty label on the algorithm options
    ):
        assert token in html, f"index.html missing P6.E marker: {token}"
    js = (_STATIC_DIR / "main.js").read_text(encoding="utf-8")
    for token in (
        "auto-reseed",       # item 2: auto re-place on room change
        "_pickMeshes",       # item 4: enlarged invisible pick target
        "_makeLabelSprite",  # item 3: on-scene channel/kind labels
        "disc-summary",      # item 1: collapsible disclaimer summary
    ):
        assert token in js, f"main.js missing P6.E marker: {token}"


def test_evaluate_still_routes_after_mount() -> None:
    # The /static mount must NOT shadow the POST /api/evaluate route either.
    body = {
        "room_id": BUILTIN_SHOEBOX_ID,
        "placement": {
            "speakers": [
                {"channel": 1, "position": {"x": 1.8, "y": 1.2, "z": 1.8}},
                {"channel": 2, "position": {"x": -1.8, "y": 1.2, "z": 1.8}},
            ]
        },
    }
    resp = _client().post("/api/evaluate", json=body)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_healthz_not_shadowed_by_mount() -> None:
    # The /static mount must NOT shadow the existing API/health routes.
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
