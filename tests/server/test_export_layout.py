"""Headless tests for P5.7 Feature A — ``POST /api/export/layout``.

The endpoint delegates serialisation ENTIRELY to core
``roomestim.export.layout_yaml.write_layout_yaml`` (D29 — the server adds no
placement/geometry math); it only builds the ``PlacementResult`` from the request
placement, lets core write the layout.yaml to a temp file, and reads the text back.
These tests assert the JSON contract, the env-gated validation header, and the
generic-message error discipline (ADR 0038, no leaked internals).

NOTE: layout.yaml's R10 pre-flight requires a real engine ``regularity_hint``
(``LINEAR``/``CIRCULAR``/``PLANAR_GRID``/``IRREGULAR``) with enough speakers. The
viewer's fresh-load default hint is ``IRREGULAR`` (min 1) — the honest label for the
hand-placed 5.1 SEED — so a first-click export is valid (see
``test_export_layout_viewer_default_hint_200``). A non-engine hint like ``"ring"``
is still correctly rejected with a generic 400. The base valid case here uses
``LINEAR`` (min 2) to match the 2-speaker placement.

``pytest.importorskip("fastapi")`` keeps the suite portable to envs WITHOUT the
``[server]`` extra; in the canonical miniforge env fastapi is installed so these
run in the default gate.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from roomestim_server.app import create_app  # noqa: E402
from roomestim_server.rooms import BUILTIN_SHOEBOX_ID  # noqa: E402


def _client() -> TestClient:
    return TestClient(create_app())


def _valid_body() -> dict[str, object]:
    """A valid layout-export body: 2 speakers with a LINEAR hint (min 2)."""
    return {
        "room_id": BUILTIN_SHOEBOX_ID,
        "placement": {
            "target_algorithm": "vbap",
            "regularity_hint": "LINEAR",
            "layout_name": "live-edit",
            "speakers": [
                {"channel": 1, "position": {"x": 1.8, "y": 1.2, "z": 1.8},
                 "aim_direction": None},
                {"channel": 2, "position": {"x": -1.8, "y": 1.2, "z": 1.8},
                 "aim_direction": None},
            ],
        },
    }


def _assert_no_internals(text: str) -> None:
    for needle in ("Traceback", "ValueError(", "ValueError:", ".py", "/home/", 'File "'):
        assert needle not in text, f"leaked internals: {needle!r} in {text!r}"


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #


def test_export_layout_success_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Unset → validate=False → the honest "schema validation skipped" header.
    monkeypatch.delenv("SPATIAL_ENGINE_REPO_DIR", raising=False)
    resp = _client().post("/api/export/layout", json=_valid_body())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["filename"] == "layout.yaml"
    text = body["yaml"]
    assert isinstance(text, str) and text.strip()
    # Env unset → validation skipped → the writer prepends its WARNING header.
    assert "WARNING: schema validation skipped" in text
    # Expected layout.yaml keys (spherical per-speaker form).
    for key in ("version", "name", "speakers", "az_deg", "el_deg", "dist_m"):
        assert key in text, key


def test_export_layout_yaml_parses_and_has_two_speakers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SPATIAL_ENGINE_REPO_DIR", raising=False)
    text = _client().post("/api/export/layout", json=_valid_body()).json()["yaml"]
    import yaml  # noqa: PLC0415

    data = yaml.safe_load(text)
    assert data["name"] == "live-edit"
    assert data["regularity_hint"] == "LINEAR"
    assert len(data["speakers"]) == 2
    for sp in data["speakers"]:
        for key in ("id", "channel", "az_deg", "el_deg", "dist_m"):
            assert key in sp, key


# --------------------------------------------------------------------------- #
# Errors — generic body, no leaked internals
# --------------------------------------------------------------------------- #


def test_export_layout_too_few_speakers_400_generic() -> None:
    # 1 speaker with a CIRCULAR hint (min 3) → core R10 ValueError → generic 400.
    body = _valid_body()
    body["placement"] = {  # type: ignore[assignment]
        "target_algorithm": "vbap",
        "regularity_hint": "CIRCULAR",
        "layout_name": "live-edit",
        "speakers": [
            {"channel": 1, "position": {"x": 1.8, "y": 1.2, "z": 1.8},
             "aim_direction": None},
        ],
    }
    resp = _client().post("/api/export/layout", json=body)
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_REQUEST"
    assert payload["error"]["message"]
    _assert_no_internals(resp.text)


def test_export_layout_unknown_regularity_hint_400_generic() -> None:
    # A non-engine hint like "ring" (the old pre-fix placeholder) is correctly
    # rejected with a generic 400 — the writer only accepts real engine hints.
    body = _valid_body()
    body["placement"]["regularity_hint"] = "ring"  # type: ignore[index]
    resp = _client().post("/api/export/layout", json=body)
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_export_layout_viewer_default_hint_200() -> None:
    # Fresh-load regression: the viewer's DEFAULT layoutMeta (IRREGULAR hint, the
    # hand-placed 5.1 SEED of 6 speakers) must export a VALID layout.yaml on the
    # first click — no re-seed required. Locks the P5.7 first-click-400 fix.
    body = _valid_body()
    body["placement"]["regularity_hint"] = "IRREGULAR"  # type: ignore[index]
    body["placement"]["speakers"] = [  # type: ignore[index]
        {"channel": 1, "position": {"x": -1.5, "y": 1.2, "z": 1.8}, "aim_direction": None},
        {"channel": 2, "position": {"x": 1.5, "y": 1.2, "z": 1.8}, "aim_direction": None},
        {"channel": 3, "position": {"x": -2.0, "y": 1.2, "z": 0.0}, "aim_direction": None},
        {"channel": 4, "position": {"x": 2.0, "y": 1.2, "z": 0.0}, "aim_direction": None},
        {"channel": 5, "position": {"x": -1.5, "y": 1.2, "z": -1.8}, "aim_direction": None},
        {"channel": 6, "position": {"x": 1.5, "y": 1.2, "z": -1.8}, "aim_direction": None},
    ]
    resp = _client().post("/api/export/layout", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["filename"] == "layout.yaml"
    assert "speakers" in data["yaml"]


def test_export_layout_unknown_room_id_400_generic() -> None:
    body = _valid_body()
    body["room_id"] = "builtin:nope"
    resp = _client().post("/api/export/layout", json=body)
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_export_layout_malformed_body_missing_field_422() -> None:
    resp = _client().post("/api/export/layout", json={"room_id": BUILTIN_SHOEBOX_ID})
    assert resp.status_code == 422
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION"


# --------------------------------------------------------------------------- #
# Client-side wiring — string-grep over main.js (guards without executing JS)
# --------------------------------------------------------------------------- #


def test_main_js_references_export_layout_wiring() -> None:
    from pathlib import Path  # noqa: PLC0415

    main_js = (
        Path(__file__).resolve().parents[2]
        / "roomestim_server"
        / "static"
        / "main.js"
    ).read_text(encoding="utf-8")
    for needle in ("/api/export/layout", "exportLayout", "layout.yaml"):
        assert needle in main_js, f"main.js missing wiring reference: {needle!r}"
