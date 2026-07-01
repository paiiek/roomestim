"""Headless contract + physics-parity + error tests for ``POST /api/place``.

``/api/place`` (immersive-layout P5.3) seeds an initial layout by delegating
ENTIRELY to core ``roomestim.place.dispatch.run_placement`` — the server adds NO
placement math (D29). These tests assert the JSON contract, prove parity against a
direct in-process ``run_placement`` call, verify the generic-message error
discipline (ADR 0038, no leaked internals), and smoke a place → evaluate
round-trip.

NOTE: the drag interaction itself is JS/WebGL (raycaster onto a horizontal plane)
and is HUMAN-verified — it cannot be exercised headlessly. These tests cover the
``/api/place`` backend; the moved-speaker evaluate parity is covered by
``test_evaluate_api.py::test_evaluate_moved_speaker_changes_report_and_stays_parity``.

``pytest.importorskip("fastapi")`` keeps the suite portable to envs WITHOUT the
``[server]`` extra; in the canonical miniforge env fastapi is installed so these
run in the default gate.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from roomestim.place.dispatch import run_placement  # noqa: E402
from roomestim_server.app import create_app  # noqa: E402
from roomestim_server.rooms import BUILTIN_SHOEBOX_ID, get_room  # noqa: E402


def _client() -> TestClient:
    return TestClient(create_app())


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #


def test_place_success_contract() -> None:
    resp = _client().post(
        "/api/place",
        json={"room_id": BUILTIN_SHOEBOX_ID, "algorithm": "vbap", "n_speakers": 6},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    placement = body["placement"]
    assert len(placement["speakers"]) == 6
    for s in placement["speakers"]:
        assert "channel" in s
        pos = s["position"]
        assert set(pos) == {"x", "y", "z"}
    # layout metadata forwarded for the evaluate placement block.
    for key in ("target_algorithm", "regularity_hint", "layout_name"):
        assert key in placement


def test_place_defaults_apply() -> None:
    """Only ``room_id`` is required; algorithm/n_speakers default (vbap, 6)."""
    resp = _client().post("/api/place", json={"room_id": BUILTIN_SHOEBOX_ID})
    assert resp.status_code == 200
    assert len(resp.json()["placement"]["speakers"]) == 6


# --------------------------------------------------------------------------- #
# ★ Physics parity — the server adds NO placement math
# --------------------------------------------------------------------------- #


def test_place_physics_parity() -> None:
    """API speaker positions == a direct ``run_placement`` call, lifted to ear height.

    ``vbap`` is listener-ear-centric (el=0 ring on the ``y=0`` plane); the server
    lifts it by ``listener_area.height_m`` into the canonical Frame A (floor at 0,
    ear plane at ``height_m``) as a client-facing view adjustment. So x/z round-trip
    verbatim (no invented placement math) and y == the core value + ``height_m``.
    """
    resp = _client().post(
        "/api/place",
        json={"room_id": BUILTIN_SHOEBOX_ID, "algorithm": "vbap", "n_speakers": 6},
    )
    api_speakers = resp.json()["placement"]["speakers"]

    room = get_room(BUILTIN_SHOEBOX_ID)
    lift = room.listener_area.height_m
    direct = run_placement(room, "vbap", 6, 1.8, 0.0)
    direct_positions = [
        {"x": s.position.x, "y": s.position.y + lift, "z": s.position.z}
        for s in direct.speakers
    ]
    api_positions = [s["position"] for s in api_speakers]
    assert api_positions == direct_positions
    assert [s["channel"] for s in api_speakers] == [
        s.channel for s in direct.speakers
    ]
    # aim_direction must round-trip verbatim too (no drift / no invented aim).
    direct_aims = [
        None
        if s.aim_direction is None
        else {"x": s.aim_direction.x, "y": s.aim_direction.y, "z": s.aim_direction.z}
        for s in direct.speakers
    ]
    assert [s["aim_direction"] for s in api_speakers] == direct_aims


# --------------------------------------------------------------------------- #
# ★ Frame consistency — ear-origin algorithms lifted to ear height; room-absolute
#   algorithms left untouched (Frame A: floor at y=0, ear plane at height_m)
# --------------------------------------------------------------------------- #


def test_place_ear_origin_lifted_to_ear_height() -> None:
    """vbap (listener-ear-centric, el=0) seeds at ear height y ≈ height_m, centred."""
    height_m = get_room(BUILTIN_SHOEBOX_ID).listener_area.height_m
    resp = _client().post(
        "/api/place",
        json={"room_id": BUILTIN_SHOEBOX_ID, "algorithm": "vbap", "n_speakers": 6},
    )
    speakers = resp.json()["placement"]["speakers"]
    for s in speakers:
        assert s["position"]["y"] == pytest.approx(height_m)
    # ring centred on the horizontal origin (listener centroid)
    assert sum(s["position"]["x"] for s in speakers) == pytest.approx(0.0, abs=1e-9)
    assert sum(s["position"]["z"] for s in speakers) == pytest.approx(0.0, abs=1e-9)


def test_place_coverage_not_lifted_stays_on_ceiling() -> None:
    """coverage is room-absolute (ceiling plane) — it must NOT be lifted to y≈4.2.

    Lifting a ceiling/wall placement by height_m would float it above the room and
    re-introduce the very bug this fix removes; only ear-origin algorithms lift.
    """
    ceiling = get_room(BUILTIN_SHOEBOX_ID).ceiling_height_m
    resp = _client().post(
        "/api/place",
        json={"room_id": BUILTIN_SHOEBOX_ID, "algorithm": "coverage", "n_speakers": 4},
    )
    assert resp.status_code == 200
    speakers = resp.json()["placement"]["speakers"]
    assert speakers
    for s in speakers:
        assert s["position"]["y"] == pytest.approx(ceiling)


# --------------------------------------------------------------------------- #
# Errors — generic body, no leaked internals
# --------------------------------------------------------------------------- #


def _assert_no_internals(text: str) -> None:
    for needle in ("Traceback", "ValueError(", "ValueError:", ".py", "/home/", 'File "'):
        assert needle not in text, f"leaked internals: {needle!r} in {text!r}"


def test_place_unknown_algorithm_400_generic() -> None:
    resp = _client().post(
        "/api/place",
        json={"room_id": BUILTIN_SHOEBOX_ID, "algorithm": "nope", "n_speakers": 6},
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["message"]
    _assert_no_internals(resp.text)


def test_place_too_few_speakers_400_generic() -> None:
    """vbap requires >= 3 speakers; below the engine minimum → generic 400."""
    resp = _client().post(
        "/api/place",
        json={"room_id": BUILTIN_SHOEBOX_ID, "algorithm": "vbap", "n_speakers": 2},
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_place_unknown_room_id_400_generic() -> None:
    resp = _client().post(
        "/api/place",
        json={"room_id": "builtin:nope", "algorithm": "vbap", "n_speakers": 6},
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    _assert_no_internals(resp.text)


def test_place_malformed_body_missing_room_id_422() -> None:
    resp = _client().post("/api/place", json={"algorithm": "vbap"})
    assert resp.status_code == 422
    assert resp.json()["ok"] is False
    assert resp.json()["error"]["code"] == "VALIDATION"


def test_place_malformed_body_wrong_type_422() -> None:
    resp = _client().post(
        "/api/place",
        json={"room_id": BUILTIN_SHOEBOX_ID, "n_speakers": "not-a-number"},
    )
    assert resp.status_code == 422
    assert resp.json()["ok"] is False
    assert resp.json()["error"]["code"] == "VALIDATION"


def test_place_n_speakers_out_of_bounds_422() -> None:
    # The sanity bound (1..128) rejects absurd counts at the schema (422), before
    # they reach run_placement — distinct from the per-algorithm minimum (400).
    for n in (0, -3, 500):
        resp = _client().post(
            "/api/place",
            json={"room_id": BUILTIN_SHOEBOX_ID, "algorithm": "vbap", "n_speakers": n},
        )
        assert resp.status_code == 422, n
        assert resp.json()["ok"] is False


# --------------------------------------------------------------------------- #
# Round-trip: /api/place output feeds straight into /api/evaluate
# --------------------------------------------------------------------------- #


def test_place_coverage_avoid_ok() -> None:
    """coverage_avoid (P7.1) dispatches through run_placement with default clearance.

    PlaceRequest.algorithm is a free string forwarded to core; the request-field
    wiring for ``clearance_m`` is P7.3, so the core default (0.30 m) applies here.
    The built-in shoebox has no obstacles, so the filter is a pass-through and the
    room-absolute placement is returned un-lifted (coverage_avoid ∉ ear-origin set).
    """
    resp = _client().post(
        "/api/place",
        json={
            "room_id": BUILTIN_SHOEBOX_ID,
            "algorithm": "coverage_avoid",
            "n_speakers": 8,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    placement = body["placement"]
    assert placement["target_algorithm"] == "COVERAGE_AVOID"
    assert len(placement["speakers"]) == 8


def test_place_then_evaluate_round_trip() -> None:
    client = _client()
    placement = client.post(
        "/api/place",
        json={"room_id": BUILTIN_SHOEBOX_ID, "algorithm": "vbap", "n_speakers": 6},
    ).json()["placement"]

    eval_body = {
        "room_id": BUILTIN_SHOEBOX_ID,
        "placement": {
            "target_algorithm": placement["target_algorithm"],
            "regularity_hint": placement["regularity_hint"],
            "layout_name": placement["layout_name"],
            "speakers": placement["speakers"],
        },
        "spec": {"model_key": "generic_surround_compact", "price": None},
        "params": {"drive_w": 10.0, "target_spl_db": 85.0, "measured_rt60_s": None},
    }
    resp = client.post("/api/evaluate", json=eval_body)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
