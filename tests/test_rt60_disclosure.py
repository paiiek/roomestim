"""tests/test_rt60_disclosure.py — Phase 0c honest RT60/acoustics labeling.

Locks the honesty surface (labeling only; no numeric or schema-breaking change):

- ``RT60_DISCLOSURE`` constant exists, is non-trivial, and carries the
  model-vs-measurement framing.
- :attr:`RT60Prediction.disclosure` returns that same constant.
- The export ``.acoustics.json`` sidecar (gltf + usd builders) carries the
  ``disclaimer`` / ``acoustics_model`` / ``materials_status`` fields, while the
  pre-existing fields stay byte-stable.

These all live in the default lane (no web / lab / e2e marker).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from roomestim.adapters.roomplan import RoomPlanAdapter
from roomestim.export.gltf import _build_acoustics_sidecar as gltf_sidecar
from roomestim.model import RoomModel
from roomestim.reconstruct._disclosure import RT60_DISCLOSURE, RT60_MODEL_NAME
from roomestim.reconstruct.predictor import RT60Prediction

# Pre-existing sidecar keys that MUST remain byte-stable (no value change).
_LEGACY_SIDECAR_KEYS = {
    "version",
    "room_name",
    "schema_version",
    "surfaces",
    "objects",
}
_NEW_SIDECAR_KEYS = {"acoustics_model", "disclaimer", "materials_status"}


@pytest.fixture
def lab_room() -> RoomModel:
    fixture = Path("tests/fixtures/lab_room.json")
    if not fixture.exists():
        pytest.skip("lab_room.json fixture not found")
    return RoomPlanAdapter().parse(fixture, scale_anchor=None, octave_band=True)


def test_disclosure_constant_is_honest_and_nontrivial() -> None:
    assert isinstance(RT60_DISCLOSURE, str)
    assert len(RT60_DISCLOSURE) >= 80
    lowered = RT60_DISCLOSURE.lower()
    # Honesty framing: model (not measurement) + the observed error magnitude.
    assert "model" in lowered
    assert "not a validated acoustic measurement" in lowered
    assert "1.4" in RT60_DISCLOSURE  # cited observed error magnitude
    assert "guidance" in lowered
    assert isinstance(RT60_MODEL_NAME, str) and RT60_MODEL_NAME


def test_prediction_exposes_disclosure_constant() -> None:
    pred = RT60Prediction(
        rt60_s=0.5,
        rt60_per_band_s={},
        predictor_name="eyring",
        rationale="test",
    )
    assert pred.disclosure == RT60_DISCLOSURE


def test_gltf_sidecar_carries_disclaimer(lab_room: RoomModel) -> None:
    payload = gltf_sidecar(lab_room)
    # New honesty fields present and correct.
    assert payload["disclaimer"] == RT60_DISCLOSURE
    assert payload["acoustics_model"] == RT60_MODEL_NAME
    assert payload["materials_status"] in {"UNKNOWN/assumed", "assigned"}
    # Pre-existing fields untouched (byte-stable: only additive keys allowed).
    assert set(payload) == _LEGACY_SIDECAR_KEYS | _NEW_SIDECAR_KEYS
    assert payload["version"] == "0.17"
    assert len(payload["surfaces"]) == len(lab_room.surfaces)
    assert len(payload["objects"]) == len(lab_room.objects)


def test_usd_sidecar_matches_gltf_disclaimer(lab_room: RoomModel) -> None:
    # The usd builder imports pxr lazily at write time; the sidecar builder
    # itself is import-safe, so compare it against the gltf builder directly.
    from roomestim.export.usd import _build_acoustics_sidecar as usd_sidecar

    payload = usd_sidecar(lab_room)
    assert payload["disclaimer"] == RT60_DISCLOSURE
    assert payload["acoustics_model"] == RT60_MODEL_NAME
    assert set(payload) == _LEGACY_SIDECAR_KEYS | _NEW_SIDECAR_KEYS
