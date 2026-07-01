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
# ★ P6.C — per-speaker install guide (server geometry; D29 parity)
# --------------------------------------------------------------------------- #


def test_evaluate_install_block_shape() -> None:
    """The response carries an ``install`` block with one entry per speaker."""
    body = _valid_body()
    resp = _client().post("/api/evaluate", json=body)
    assert resp.status_code == 200
    data = resp.json()
    install = data["install"]
    assert install is not None
    speakers = install["speakers"]
    assert len(speakers) == len(body["placement"]["speakers"])  # type: ignore[index]
    for entry, sent in zip(speakers, body["placement"]["speakers"]):  # type: ignore[arg-type]
        # position is verbatim from the placement.
        assert entry["position"] == sent["position"]
        assert entry["height_m"] == sent["position"]["y"]
        assert entry["channel"] == sent["channel"]
        # geometry fields present + sane types.
        assert entry["dist_m"] > 0.0
        assert isinstance(entry["az_deg"], float)
        assert isinstance(entry["el_deg"], float)
        # mounting hints (shoebox has walls + corners → non-null here).
        assert isinstance(entry["nearest_wall_index"], int)
        assert entry["wall_offset_m"] >= 0.0
        assert isinstance(entry["nearest_corner"], int)
        assert entry["corner_dist_m"] >= 0.0


def test_evaluate_install_az_el_dist_parity() -> None:
    """install az/el/dist == a direct ``cartesian_to_pipeline`` for the same layout.

    Proves the server does not re-derive the trig by hand and that no client/server
    drift can creep in — the SAME sign-flip authority the engine/layout.yaml use.
    """
    import math

    from roomestim.coords import cartesian_to_pipeline

    body = _valid_body()
    install = _client().post("/api/evaluate", json=body).json()["install"]

    room = get_room(BUILTIN_SHOEBOX_ID)
    ear_x = room.listener_area.centroid.x
    ear_y = room.listener_area.height_m
    ear_z = room.listener_area.centroid.z

    sent = body["placement"]["speakers"]  # type: ignore[index]
    for entry, s in zip(install["speakers"], sent):  # type: ignore[arg-type]
        p = s["position"]
        az, el, dist = cartesian_to_pipeline(
            p["x"] - ear_x, p["y"] - ear_y, p["z"] - ear_z
        )
        assert entry["az_deg"] == math.degrees(az)
        assert entry["el_deg"] == math.degrees(el)
        assert entry["dist_m"] == dist


def test_evaluate_report_block_unchanged_by_install() -> None:
    """``install`` is purely additive — ``report`` is byte-identical to core.

    (Same assertion as the physics-parity test, re-stated to lock that adding the
    install block did NOT perturb the verbatim engine report.)
    """
    body = _valid_body()
    api_report = _client().post("/api/evaluate", json=body).json()["report"]

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
            room, placement, spec, listener_area=room.listener_area,
            drive_w=10.0, target_spl_db=85.0,
        )
    )
    assert api_report == direct


# --------------------------------------------------------------------------- #
# ★ P6.D — per-speaker direct-field SPL at the listener (core parity)
# --------------------------------------------------------------------------- #


def test_evaluate_install_spl_present() -> None:
    """Every install entry carries a finite ``spl_at_listener_db`` on the shoebox."""
    import math

    body = _valid_body()
    install = _client().post("/api/evaluate", json=body).json()["install"]
    for entry in install["speakers"]:
        spl = entry["spl_at_listener_db"]
        assert isinstance(spl, float)
        assert math.isfinite(spl)


def test_evaluate_install_spl_parity() -> None:
    """install ``spl_at_listener_db`` == a direct core call for the same layout.

    Proves the server delegates the SPL to core
    ``per_speaker_direct_spl_at_listener`` (D29 — no acoustics re-derived) and that
    no client/server drift can creep in, matched by channel.
    """
    from roomestim.spec.speaker_spec import per_speaker_direct_spl_at_listener

    body = _valid_body()
    install = _client().post("/api/evaluate", json=body).json()["install"]

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
    expected = dict(
        per_speaker_direct_spl_at_listener(
            spec,
            drive_w=10.0,
            speakers=placement.speakers,
            listener_area=room.listener_area,
        )
    )
    for entry in install["speakers"]:
        assert entry["spl_at_listener_db"] == expected[entry["channel"]]


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


def test_grid_resolution_too_fine_rejected_422() -> None:
    """A sub-floor ``grid_resolution_m`` is rejected at the schema (DoS guard).

    Without the ``ge=0.05`` bound a tiny positive (1e-6) would blow the SPL grid
    to ~1e6 x 1e6 cells and hang/OOM the worker. It must be refused BEFORE the
    engine runs — a 422, never a 200 or a long-running request.
    """
    body = _valid_body()
    body["params"] = {
        "drive_w": 10.0,
        "target_spl_db": 85.0,
        "grid_resolution_m": 1e-6,
    }
    resp = _client().post("/api/evaluate", json=body)
    assert resp.status_code == 422
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_grid_resolution_reasonable_value_accepted() -> None:
    """A sane ``grid_resolution_m`` (above the floor) passes and evaluates."""
    body = _valid_body()
    body["params"] = {
        "drive_w": 10.0,
        "target_spl_db": 85.0,
        "grid_resolution_m": 0.25,
    }
    resp = _client().post("/api/evaluate", json=body)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


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
