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
from roomestim.reconstruct.materials import (
    eyring_rt60,
    eyring_rt60_per_band,
    sabine_rt60,
    sabine_rt60_per_band,
)

E2E_DIR_ENV = "ROOMESTIM_E2E_DATASET_DIR"
# Pin report path to repo root so the test is hermetic regardless of pytest CWD.
REPORT_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "perf_verification_e2e_2026-05-08.md"
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

    # Row tuples: (room_id, sabine, eyring, measured, err_sabine, err_eyring)
    rows_500hz: list[tuple[str, float, float, float, float, float]] = []
    rows_per_band: dict[int, list[tuple[str, float, float, float, float, float]]] = {
        b: [] for b in OCTAVE_BANDS_HZ
    }

    for room_id in room_ids:
        case = load_room(dataset_dir, room_id)
        areas = _surface_areas_by_material(case.room)
        volume = _room_volume(case.room)

        sabine_500hz = sabine_rt60(volume, areas)
        eyring_500hz = eyring_rt60(volume, areas)
        sabine_per_band = sabine_rt60_per_band(volume, areas)
        eyring_per_band = eyring_rt60_per_band(volume, areas)

        # Vorländer 2020 §4.2 monotonicity: Eyring ≤ Sabine per room and per band.
        assert eyring_500hz <= sabine_500hz + 1e-9, (
            f"{room_id}: Eyring {eyring_500hz:.6f} > Sabine {sabine_500hz:.6f} "
            "violates Vorländer 2020 §4.2 monotonicity invariant"
        )
        for band in OCTAVE_BANDS_HZ:
            sb = sabine_per_band[band]
            eb = eyring_per_band[band]
            assert eb <= sb + 1e-9, (
                f"{room_id} @ {band} Hz: Eyring {eb:.6f} > Sabine {sb:.6f} "
                "violates Vorländer 2020 §4.2 monotonicity invariant"
            )

        err_sab_500 = sabine_500hz - case.measured_rt60_500hz_s
        err_eyr_500 = eyring_500hz - case.measured_rt60_500hz_s
        rows_500hz.append(
            (
                room_id,
                sabine_500hz,
                eyring_500hz,
                case.measured_rt60_500hz_s,
                err_sab_500,
                err_eyr_500,
            )
        )

        for band in OCTAVE_BANDS_HZ:
            measured = case.measured_rt60_per_band_s.get(band)
            if measured is not None:
                sb = sabine_per_band[band]
                eb = eyring_per_band[band]
                rows_per_band[band].append(
                    (room_id, sb, eb, measured, sb - measured, eb - measured)
                )

        print(
            f"[{room_id}] V={volume:.1f}m³ "
            f"500Hz: sabine={sabine_500hz:.3f}s eyring={eyring_500hz:.3f}s "
            f"meas={case.measured_rt60_500hz_s:.3f}s "
            f"err_sab={err_sab_500:+.3f}s "
            f"err_eyr={err_eyr_500:+.3f}s"
        )

    # Write characterisation report to docs/
    _write_report(REPORT_PATH, dataset_name(), rows_500hz, rows_per_band)

    # Invariants only — NO magnitude threshold
    assert len(rows_500hz) >= 1, "expected ≥1 room evaluated when env var is set"
    for room_id, sab, eyr, meas, _es, _ee in rows_500hz:
        assert sab > 0.0, f"{room_id}: Sabine RT60 must be positive"
        assert eyr > 0.0, f"{room_id}: Eyring RT60 must be positive"
        assert meas > 0.0, f"{room_id}: measured RT60 must be positive"


def _write_report(
    path: Path,
    ds_name: str,
    rows_500hz: list[tuple[str, float, float, float, float, float]],
    rows_per_band: dict[int, list[tuple[str, float, float, float, float, float]]],
) -> None:
    """Emit a markdown characterisation report. NO accuracy threshold."""
    lines = [
        f"# E2E RT60 verification — {ds_name}",
        "",
        "- Generated: 2026-05-08 by `tests/test_e2e_ace_challenge_rt60.py`",
        "- Predictor: roomestim v0.6 Sabine + Eyring RT60 (mid-band 500 Hz + octave bands)",
        "- Reference: ACE Challenge corpus tabulated T60 (per dataset_dir CSV)",
        "- Framing: characterisation, NOT a pass/fail gate. Per-room error in seconds.",
        "",
        "## Per-room 500 Hz error",
        "",
        "| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r, sab, eyr, m, es, ee in rows_500hz:
        lines.append(
            f"| {r} | {sab:.3f} | {eyr:.3f} | {m:.3f} | {es:+.3f} | {ee:+.3f} |"
        )

    if rows_500hz:
        errs_sab = [es for _, _, _, _, es, _ in rows_500hz]
        errs_eyr = [ee for _, _, _, _, _, ee in rows_500hz]
        mean_err_sab = statistics.mean(errs_sab)
        max_err_sab = max(errs_sab, key=abs)
        mean_err_eyr = statistics.mean(errs_eyr)
        max_err_eyr = max(errs_eyr, key=abs)
        lines.append("")
        lines.append(f"- mean error Sabine: {mean_err_sab:+.3f} s")
        lines.append(f"- max abs error Sabine: {max_err_sab:+.3f} s")
        lines.append(f"- mean error Eyring: {mean_err_eyr:+.3f} s")
        lines.append(f"- max abs error Eyring: {max_err_eyr:+.3f} s")

    lines.append("")
    lines.append("## Per-band errors")
    lines.append("")

    for band, rows in rows_per_band.items():
        if not rows:
            continue
        lines.append(f"### {band} Hz")
        lines.append("")
        lines.append(
            "| Room | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for r, sab, eyr, m, es, ee in rows:
            lines.append(
                f"| {r} | {sab:.3f} | {eyr:.3f} | {m:.3f} | {es:+.3f} | {ee:+.3f} |"
            )
        errs_sab = [es for _, _, _, _, es, _ in rows]
        errs_eyr = [ee for _, _, _, _, _, ee in rows]
        lines.append("")
        lines.append(f"- mean error Sabine: {statistics.mean(errs_sab):+.3f} s")
        lines.append(f"- max abs error Sabine: {max(errs_sab, key=abs):+.3f} s")
        lines.append(f"- mean error Eyring: {statistics.mean(errs_eyr):+.3f} s")
        lines.append(f"- max abs error Eyring: {max(errs_eyr, key=abs):+.3f} s")
        lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "This report is a CHARACTERISATION, not a pass/fail acceptance gate. "
        "Sabine assumes a diffuse field; real rooms violate this at low frequencies "
        "and in heavily-absorbed spaces (Vorländer 2020 §4). Material labels are "
        "inferred from ACE corpus informal descriptions (carpet/hard floor); mapping "
        "to roomestim's closed MaterialLabel enum involves judgment calls. "
        "Per-room and per-band `eyring ≤ sabine + 1e-9` is asserted at runtime "
        "(Vorländer 2020 §4.2)."
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
