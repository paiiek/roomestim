"""E2E RT60 characterisation test — ACE Challenge corpus.

Gated by:
  - @pytest.mark.e2e  (registered in pyproject.toml)
  - @pytest.mark.network  (registered in pyproject.toml; network not actually used at runtime)
  - ROOMESTIM_E2E_DATASET_DIR env var pointing at a populated local ACE corpus dir

Default CI: ``pytest -m "not lab and not e2e"`` does NOT collect this test.

To run with the sample fixture:
    ROOMESTIM_E2E_DATASET_DIR=tests/fixtures/ace_challenge_sample \
        pytest tests/test_e2e_ace_challenge_rt60.py::test_e2e_rt60_characterisation -m e2e -s

To run with the real ACE corpus (after download):
    ROOMESTIM_E2E_DATASET_DIR=/path/to/ace_corpus \
        pytest tests/test_e2e_ace_challenge_rt60.py::test_e2e_rt60_characterisation -m e2e -s
"""

from __future__ import annotations

import os
import statistics
from pathlib import Path

import pytest

from roomestim.adapters.ace_challenge import (
    _room_volume,
    _surface_areas_by_material,
    dataset_name,
    list_rooms,
    load_room,
)
from roomestim.model import OCTAVE_BANDS_HZ
from roomestim.reconstruct.materials import sabine_rt60, sabine_rt60_per_band

E2E_DIR_ENV = "ROOMESTIM_E2E_DATASET_DIR"
# Pin report path to repo root so the test is hermetic regardless of pytest CWD.
REPORT_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "perf_verification_e2e_2026-05-06.md"
)


# --------------------------------------------------------------------------- #
# Gated E2E characterisation test
# --------------------------------------------------------------------------- #


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_rt60_characterisation(capsys):
    """Characterisation: PRINT per-room RT60 errors. NO assert on magnitude.

    Framing: same as v0.1.1 DBAP-noise characterisation in
    tests/test_room_acoustics.py — Sabine is ±20% in real rooms by physics
    (non-diffuse fields, low-frequency resonances). Asserting a numeric bound
    on real-world data would fabricate a threshold (Critic M1 honesty principle).
    """
    dataset_dir_str = os.environ.get(E2E_DIR_ENV)
    if not dataset_dir_str:
        pytest.skip(
            f"E2E test gated; set {E2E_DIR_ENV} to a populated ACE Challenge directory."
        )
    dataset_dir = Path(dataset_dir_str)
    if not dataset_dir.is_dir():
        pytest.skip(
            f"{E2E_DIR_ENV}={dataset_dir_str} does not exist or is not a directory."
        )

    room_ids = list_rooms(dataset_dir)
    if not room_ids:
        pytest.skip(f"{dataset_dir} contains zero usable rooms.")

    rows_500hz: list[tuple[str, float, float, float]] = []  # (room_id, predicted, measured, err)
    rows_per_band: dict[int, list[tuple[str, float, float, float]]] = {
        b: [] for b in OCTAVE_BANDS_HZ
    }

    for room_id in room_ids:
        case = load_room(dataset_dir, room_id)
        areas = _surface_areas_by_material(case.room)
        volume = _room_volume(case.room)

        predicted_500hz = sabine_rt60(volume, areas)
        predicted_per_band = sabine_rt60_per_band(volume, areas)

        e500 = predicted_500hz - case.measured_rt60_500hz_s
        rows_500hz.append((room_id, predicted_500hz, case.measured_rt60_500hz_s, e500))

        for band, predicted in predicted_per_band.items():
            measured = case.measured_rt60_per_band_s.get(band)
            if measured is not None:
                rows_per_band[band].append(
                    (room_id, predicted, measured, predicted - measured)
                )

        print(
            f"[{room_id}] V={volume:.1f}m³ "
            f"500Hz: pred={predicted_500hz:.3f}s "
            f"meas={case.measured_rt60_500hz_s:.3f}s "
            f"err={e500:+.3f}s"
        )

    # Write characterisation report to docs/
    _write_report(REPORT_PATH, dataset_name(), rows_500hz, rows_per_band)

    # Invariants only — NO magnitude threshold
    assert len(rows_500hz) >= 1, "expected ≥1 room evaluated when env var is set"
    for room_id, pred, meas, _err in rows_500hz:
        assert pred > 0.0, f"{room_id}: predicted RT60 must be positive"
        assert meas > 0.0, f"{room_id}: measured RT60 must be positive"


def _write_report(
    path: Path,
    ds_name: str,
    rows_500hz: list[tuple[str, float, float, float]],
    rows_per_band: dict[int, list[tuple[str, float, float, float]]],
) -> None:
    """Emit a markdown characterisation report. NO accuracy threshold."""
    lines = [
        f"# E2E RT60 verification — {ds_name}",
        "",
        "- Generated: 2026-05-06 by `tests/test_e2e_ace_challenge_rt60.py`",
        "- Predictor: roomestim v0.3 Sabine RT60 (mid-band 500 Hz) + sabine_rt60_per_band (octave bands)",
        "- Reference: ACE Challenge corpus tabulated T60 (per dataset_dir CSV)",
        "- Framing: characterisation, NOT a pass/fail gate. Per-room error in seconds.",
        "",
        "## Per-room 500 Hz error",
        "",
        "| Room | Predicted (s) | Measured (s) | Error (s) |",
        "| --- | ---: | ---: | ---: |",
    ]
    for r, p, m, e in rows_500hz:
        lines.append(f"| {r} | {p:.3f} | {m:.3f} | {e:+.3f} |")

    if rows_500hz:
        errs = [e for _, _, _, e in rows_500hz]
        mean_err = statistics.mean(errs)
        max_err = max(errs, key=abs)
        lines.append("")
        lines.append(f"- mean error: {mean_err:+.3f} s")
        lines.append(f"- max abs error: {max_err:+.3f} s")

    lines.append("")
    lines.append("## Per-band errors")
    lines.append("")

    for band, rows in rows_per_band.items():
        if not rows:
            continue
        lines.append(f"### {band} Hz")
        lines.append("")
        lines.append("| Room | Predicted (s) | Measured (s) | Error (s) |")
        lines.append("| --- | ---: | ---: | ---: |")
        for r, p, m, e in rows:
            lines.append(f"| {r} | {p:.3f} | {m:.3f} | {e:+.3f} |")
        errs = [e for _, _, _, e in rows]
        lines.append("")
        lines.append(f"- mean error: {statistics.mean(errs):+.3f} s")
        lines.append(f"- max abs error: {max(errs, key=abs):+.3f} s")
        lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "This report is a CHARACTERISATION, not a pass/fail acceptance gate. "
        "Sabine assumes a diffuse field; real rooms violate this at low frequencies "
        "and in heavily-absorbed spaces (Vorländer 2020 §4). Material labels are "
        "inferred from ACE corpus informal descriptions (carpet/hard floor); mapping "
        "to roomestim's closed MaterialLabel enum involves judgment calls."
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Unit tests (NOT marked e2e — run in default CI)
# --------------------------------------------------------------------------- #


def test_ace_adapter_skips_cleanly_when_env_var_unset(monkeypatch):
    """Ensure the gating works: with no env var, the adapter module imports cleanly."""
    monkeypatch.delenv(E2E_DIR_ENV, raising=False)
    # Import must succeed — no side-effects at import time
    from roomestim.adapters.ace_challenge import dataset_name, list_rooms, load_room  # noqa: F401

    assert callable(list_rooms)
    assert callable(load_room)
    assert dataset_name() == "ACE Challenge (Imperial College, 2015)"


def test_ace_adapter_with_sample_fixture():
    """Smoke test using tests/fixtures/ace_challenge_sample/ as the dataset_dir."""
    fixture_dir = Path(__file__).parent / "fixtures" / "ace_challenge_sample"
    assert fixture_dir.is_dir(), f"missing sample fixture at {fixture_dir}"

    rooms = list_rooms(fixture_dir)
    assert len(rooms) >= 1, "expected at least one room in sample fixture"

    case = load_room(fixture_dir, rooms[0])
    assert case.room_id == rooms[0]
    assert case.measured_rt60_500hz_s > 0.0
    assert len(case.measured_rt60_per_band_s) >= 1

    # Verify roomestim can compute predicted RT60 from this synthesised room
    areas = _surface_areas_by_material(case.room)
    volume = _room_volume(case.room)
    assert volume > 0.0, "room volume must be positive"
    assert len(areas) > 0, "must have ≥1 material"

    predicted_500hz = sabine_rt60(volume, areas)
    assert predicted_500hz > 0.0, "predicted RT60 must be positive"

    predicted_per_band = sabine_rt60_per_band(volume, areas)
    assert set(predicted_per_band.keys()) == set(OCTAVE_BANDS_HZ)
    for band, rt60 in predicted_per_band.items():
        assert rt60 > 0.0, f"per-band RT60 must be positive at {band} Hz"
