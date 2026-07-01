"""Headless tests for the P5.9 per-kind material editing (curated rule-base).

Covers the catalog endpoint ``GET /api/materials`` and the optional
``materials`` override on ``POST /api/evaluate``. The override is LABEL-BASED
(a :class:`roomestim.model.MaterialLabel` name per kind) and drives the curated
rule-base coefficients; custom numeric α is intentionally NOT exposed here.

``pytest.importorskip("fastapi")`` keeps the suite portable to envs WITHOUT the
``[server]`` extra (mirrors the sibling server tests).
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from roomestim.model import MaterialAbsorption, MaterialLabel  # noqa: E402
from roomestim_server.app import create_app  # noqa: E402
from roomestim_server.rooms import BUILTIN_SHOEBOX_ID  # noqa: E402


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


def _assert_no_internals(text: str) -> None:
    for needle in ("Traceback", "ValueError(", "ValueError:", ".py", "/home/", "File \""):
        assert needle not in text, f"leaked internals: {needle!r} in {text!r}"


# --------------------------------------------------------------------------- #
# GET /api/materials — catalog
# --------------------------------------------------------------------------- #


def test_materials_catalog_lists_all_ten() -> None:
    resp = _client().get("/api/materials")
    assert resp.status_code == 200
    materials = resp.json()["materials"]
    # All 10 curated MaterialLabel members present, once each.
    labels = [m["label"] for m in materials]
    assert sorted(labels) == sorted(m.name for m in MaterialLabel)
    assert len(labels) == 10
    for m in materials:
        assert isinstance(m["absorption_500hz"], (int, float))
        assert m["name"]  # human label present
        # The advertised α is the REAL rule-base coefficient (no fake numbers).
        assert m["absorption_500hz"] == MaterialAbsorption[MaterialLabel[m["label"]]]


# --------------------------------------------------------------------------- #
# Override — RT60 responds to the chosen materials, in the expected direction
# --------------------------------------------------------------------------- #


def _predicted_rt60(client: TestClient, materials: dict[str, str]) -> float:
    body = _valid_body()
    body["materials"] = materials
    report = client.post("/api/evaluate", json=body).json()["report"]
    return float(report["rt60"]["predicted_s"])


def test_floor_material_carpet_vs_glass_changes_rt60() -> None:
    """A floor-material override REACHES the engine → the predicted RT60 changes.

    Carpet (α₅₀₀ 0.30) vs glass (α₅₀₀ 0.04) yield DIFFERENT predicted RT60 on the
    built-in shoebox, proving the override is applied to the floor surfaces before
    evaluate. (A monotone α₅₀₀→RT60 direction is NOT asserted here: this room uses
    the per-BAND ISM predictor, where glass's high low-frequency absorption — 125 Hz
    0.18 vs carpet 0.05 — plus the floor being a minor surface make the broadband
    direction band-dependent, not α₅₀₀-ordered. The unambiguous direction is asserted
    on the dominant wall surfaces below.)
    """
    client = _client()
    rt60_carpet = _predicted_rt60(client, {"floor": "CARPET"})
    rt60_glass = _predicted_rt60(client, {"floor": "GLASS"})
    assert rt60_carpet != rt60_glass


def test_absorptive_walls_shorten_rt60_vs_reflective() -> None:
    """More wall absorption → SHORTER predicted RT60 (physically-correct direction).

    Walls dominate this shoebox's decay, so an all-band absorptive material
    (melamine foam, bands 0.35–0.93) gives a much SHORTER RT60 than an all-band
    reflective one (concrete, bands 0.01–0.03). This is the honest "more absorption
    → shorter reverberation" guarantee, on the surface that actually drives it.
    """
    client = _client()
    rt60_absorptive = _predicted_rt60(client, {"walls": "MELAMINE_FOAM"})
    rt60_reflective = _predicted_rt60(client, {"walls": "WALL_CONCRETE"})
    assert rt60_absorptive < rt60_reflective


def test_unknown_material_name_400_generic() -> None:
    body = _valid_body()
    body["materials"] = {"floor": "NOT_A_MATERIAL"}
    resp = _client().post("/api/evaluate", json=body)
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_REQUEST"
    _assert_no_internals(resp.text)


# --------------------------------------------------------------------------- #
# Additive guard — omitted / all-null materials is byte-equal to today
# --------------------------------------------------------------------------- #


def test_materials_omitted_is_unchanged() -> None:
    """No ``materials`` key → identical report to a body that omits it (regression)."""
    client = _client()
    base = client.post("/api/evaluate", json=_valid_body()).json()["report"]

    explicit_none = _valid_body()
    explicit_none["materials"] = None
    with_none = client.post("/api/evaluate", json=explicit_none).json()["report"]
    assert with_none == base

    all_null = _valid_body()
    all_null["materials"] = {"floor": None, "walls": None, "ceiling": None}
    with_nulls = client.post("/api/evaluate", json=all_null).json()["report"]
    assert with_nulls == base
