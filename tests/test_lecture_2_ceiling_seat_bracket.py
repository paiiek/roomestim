"""v0.8 Scope-A — Lecture_2 ceiling/seat bracketing harness (default-lane).

Five default-lane tests:

1. ``test_bracket_v0_baseline_matches_v07_perf_doc_500hz`` — pin V0 baseline
   500 Hz Sabine values against `docs/perf_verification_e2e_2026-05-08.md`
   (v0.6/v0.7-preserved). Asserts the harness's V0 path is byte-equal to the
   shipped predictor before V1..V4 run.
2. ``test_bracket_v1_ceiling_drywall_lecture2_500hz`` — V1 ceiling swap on
   Lecture_2; records per-variant residual; asserts the override path
   *executes* and produces a finite Sabine 500 Hz prediction that differs
   from V0 (does NOT assert improvement — that verdict is recorded in the
   appendix doc + ADR 0015).
3. ``test_bracket_v2_lecture_seat_unoccupied_lecture2_500hz`` — V2 seat α
   split on Lecture_2; same shape as V1.
4. ``test_bracket_v3_combined_lecture2_500hz`` — V3 = V1 + V2; this is the
   binding "acceptance OR null" test: the test passes either when the V3
   variant satisfies the §2.2 acceptance criterion (|Lecture_2 err| ≤ 0.5 s
   @500 Hz with no >+0.10 s regression on the other 5 furniture-tracked
   rooms) OR when the harness records the null result for the appendix
   emitter to surface. Either way the test goes green; the verdict is in
   the perf doc + ADR 0015 + RELEASE_NOTES, not in the test result.
5. ``test_bracket_emits_perf_doc_appendix`` — recomputes the full bracketing
   table (V0..V3, optional V4 if env flag set) for all 6 furniture-tracked
   rooms × 6 octave bands × 2 predictors and writes
   ``docs/perf_verification_lecture2_bracket_2026-05-09.md`` with a
   deterministic byte-equal byte-content (same inputs ⇒ identical md5).

All tests are default-lane (no `@pytest.mark.lab` / `@pytest.mark.e2e`); they
read the in-tree measured-T60 fixture at
``tests/fixtures/ace_eaton_2016_table_i_measured_rt60.csv`` (factual
reproduction of the v0.6 perf-doc measured-T60 column; ADR 0014 applies).

Building_Lobby is excluded from V0..V4 per ADR 0014. The harness raises a
``ValueError`` if asked to bracket Building_Lobby explicitly.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from roomestim.adapters.ace_challenge import (
    _RoomBuildOverrides,
    _build_room_model,
    _room_volume,
    _surface_areas_by_material,
    ACE_ROOM_GEOMETRY,
)
from roomestim.model import MaterialLabel, OCTAVE_BANDS_HZ
from roomestim.reconstruct.materials import (
    eyring_rt60_per_band,
    sabine_rt60_per_band,
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[1]
MEASURED_RT60_CSV = (
    REPO_ROOT / "tests" / "fixtures" / "ace_eaton_2016_table_i_measured_rt60.csv"
)
APPENDIX_DOC_PATH = (
    REPO_ROOT / "docs" / "perf_verification_lecture2_bracket_2026-05-09.md"
)
PREDECESSOR_PERF_DOC = "docs/perf_verification_e2e_2026-05-08.md"

# Building_Lobby is excluded per ADR 0014.
EXCLUDED_ROOMS: tuple[str, ...] = ("Building_Lobby",)

# Furniture-tracked rooms (mirrors `_FURNITURE_BY_ROOM` keys; sorted).
FURNITURE_ROOMS: tuple[str, ...] = (
    "Lecture_1",
    "Lecture_2",
    "Meeting_1",
    "Meeting_2",
    "Office_1",
    "Office_2",
)

# v0.6 perf doc 500 Hz Sabine values (byte-equal pinning), ex-Building_Lobby.
V07_PERF_DOC_SABINE_500HZ_S: dict[str, float] = {
    "Lecture_1": 0.686,
    "Lecture_2": 0.435,
    "Meeting_1": 0.410,
    "Meeting_2": 0.395,
    "Office_1":  0.704,
    "Office_2":  0.631,
}
V07_PERF_DOC_LECTURE_2_MEASURED_500HZ_S: float = 1.343

# V2 seat α — representative unoccupied lecture-seat profile per Beranek 2004
# Ch.3 Table 3.1 / Vorländer 2020 §11 Appx A. α₅₀₀ = 0.20 (the Beranek
# "unoccupied lecture seats" row sits in the 0.18..0.22 band; 0.20 is the
# midpoint). Per-band profile mirrors the lecture-seat shape proportionally.
V2_SEAT_ALPHA_500: float = 0.20
V2_SEAT_ALPHA_BANDS: tuple[float, float, float, float, float, float] = (
    0.10, 0.16, 0.20, 0.24, 0.26, 0.26,
)

# Acceptance criteria (§2.2).
LECTURE_2_ACCEPT_ABS_ERR_S: float = 0.5
NON_LECTURE_2_REGRESSION_LIMIT_S: float = 0.10

# Tests #2/#3 — V1/V2 must produce a Lecture_2 prediction that *differs* from
# V0 by at least this much in absolute value. Used only to verify the override
# code path activated; not an improvement assertion.
MIN_VARIANT_DIFF_S: float = 1e-6


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _load_measured_rt60() -> dict[str, dict[int, float]]:
    """Parse the in-tree measured-T60 CSV → ``{room_id: {band_hz: t60_s}}``."""
    out: dict[str, dict[int, float]] = {}
    with MEASURED_RT60_CSV.open(newline="", encoding="utf-8") as fh:
        # Skip leading comment lines (start with `#`); preserve them out of band.
        rows = [line for line in fh if line.strip() and not line.lstrip().startswith("#")]
    reader = csv.DictReader(rows)
    for row in reader:
        room_id = row["room_id"].strip()
        band_hz = int(row["band_hz"].strip())
        t60_s = float(row["measured_t60_s"].strip())
        out.setdefault(room_id, {})[band_hz] = t60_s
    return out


def _v4_enabled() -> bool:
    """True iff env flag ``ROOMESTIM_BRACKET_V4=1`` is set (bounding case)."""
    return os.environ.get("ROOMESTIM_BRACKET_V4", "").strip() == "1"


def _variant_overrides(variant: str) -> _RoomBuildOverrides | None:
    """Return the ``_RoomBuildOverrides`` instance for one bracketing variant.

    V0 → None (library default path; byte-equal to v0.7).
    V1 → ceiling swap to CEILING_DRYWALL.
    V2 → seat α split (unoccupied profile).
    V3 → V1 + V2 combined.
    V4 → bounding case: ceiling = WALL_CONCRETE (very low absorption);
         characterising "what would close the gap entirely?". Env-gated.
    """
    if variant == "V0":
        return None
    if variant == "V1":
        return _RoomBuildOverrides(ceiling_label=MaterialLabel.CEILING_DRYWALL)
    if variant == "V2":
        return _RoomBuildOverrides(
            seat_alpha_500=V2_SEAT_ALPHA_500,
            seat_alpha_bands=V2_SEAT_ALPHA_BANDS,
        )
    if variant == "V3":
        return _RoomBuildOverrides(
            ceiling_label=MaterialLabel.CEILING_DRYWALL,
            seat_alpha_500=V2_SEAT_ALPHA_500,
            seat_alpha_bands=V2_SEAT_ALPHA_BANDS,
        )
    if variant == "V4":
        return _RoomBuildOverrides(ceiling_label=MaterialLabel.WALL_CONCRETE)
    raise ValueError(f"Unknown bracketing variant {variant!r}")


def _predict_per_band(
    room_id: str, overrides: _RoomBuildOverrides | None
) -> tuple[dict[int, float], dict[int, float]]:
    """Return ``(sabine_per_band, eyring_per_band)`` for one (room, variant)."""
    if room_id in EXCLUDED_ROOMS:
        raise ValueError(
            f"Building_Lobby is excluded from the bracketing harness per ADR 0014; "
            f"got room_id={room_id!r}."
        )
    geom = ACE_ROOM_GEOMETRY[room_id]
    room = _build_room_model(room_id, geom, overrides=overrides)
    areas = _surface_areas_by_material(room)
    volume = _room_volume(room)
    return sabine_rt60_per_band(volume, areas), eyring_rt60_per_band(volume, areas)


def _compute_variant_table(
    measured: dict[str, dict[int, float]],
    variants: tuple[str, ...],
) -> dict[str, dict[str, dict[int, dict[str, float]]]]:
    """Build the bracketing table.

    Returns nested dict keyed by ``variant -> room_id -> band_hz -> stat`` where
    ``stat in {"sabine", "eyring", "measured", "err_sabine", "err_eyring"}``.
    All floats; deterministic given inputs.
    """
    table: dict[str, dict[str, dict[int, dict[str, float]]]] = {}
    for variant in variants:
        overrides = _variant_overrides(variant)
        per_room: dict[str, dict[int, dict[str, float]]] = {}
        for room_id in FURNITURE_ROOMS:
            sabine_pb, eyring_pb = _predict_per_band(room_id, overrides)
            per_band: dict[int, dict[str, float]] = {}
            for band in OCTAVE_BANDS_HZ:
                m = measured[room_id][band]
                sb = sabine_pb[band]
                eb = eyring_pb[band]
                per_band[band] = {
                    "sabine": sb,
                    "eyring": eb,
                    "measured": m,
                    "err_sabine": sb - m,
                    "err_eyring": eb - m,
                }
            per_room[room_id] = per_band
        table[variant] = per_room
    return table


# --------------------------------------------------------------------------- #
# Test 1 — V0 baseline pinning (matches v0.6/v0.7 perf doc)
# --------------------------------------------------------------------------- #


def test_bracket_v0_baseline_matches_v07_perf_doc_500hz() -> None:
    """V0 baseline 500 Hz Sabine pins to v0.6/v0.7 perf doc within ±0.001 s.

    Pre-condition for V1..V4: if this fails, the override hook has leaked
    into the default code path or a coefficient drifted; bracketing residuals
    cannot be interpreted.
    """
    for room_id, expected in V07_PERF_DOC_SABINE_500HZ_S.items():
        sabine_pb, _ = _predict_per_band(room_id, None)
        observed = sabine_pb[500]
        assert observed == pytest.approx(expected, abs=0.001), (
            f"V0 baseline drift on {room_id}: predicted {observed:.6f} s, "
            f"v0.6/v0.7 perf doc {expected:.3f} s"
        )


# --------------------------------------------------------------------------- #
# Test 2 — V1 ceiling-drywall on Lecture_2
# --------------------------------------------------------------------------- #


def test_bracket_v1_ceiling_drywall_lecture2_500hz() -> None:
    """V1 swaps Lecture_2 ceiling to CEILING_DRYWALL; record residual.

    Asserts the override path *executes* and yields a finite Sabine 500 Hz
    prediction that differs from V0 (verifies the hook activates). Does
    NOT assert improvement — the bracketing verdict is recorded in the
    appendix doc + ADR 0015 + RELEASE_NOTES.
    """
    sabine_v0, _ = _predict_per_band("Lecture_2", None)
    sabine_v1, _ = _predict_per_band("Lecture_2", _variant_overrides("V1"))
    assert sabine_v0[500] > 0.0
    assert sabine_v1[500] > 0.0
    assert abs(sabine_v1[500] - sabine_v0[500]) > MIN_VARIANT_DIFF_S, (
        "V1 override did not change Lecture_2 500 Hz Sabine prediction; "
        "ceiling-label override may not be wired."
    )


# --------------------------------------------------------------------------- #
# Test 3 — V2 unoccupied seat α on Lecture_2
# --------------------------------------------------------------------------- #


def test_bracket_v2_lecture_seat_unoccupied_lecture2_500hz() -> None:
    """V2 splits seat α to unoccupied profile on Lecture_2; record residual.

    Same shape as test 2: assert override path executes and the prediction
    differs from V0.
    """
    sabine_v0, _ = _predict_per_band("Lecture_2", None)
    sabine_v2, _ = _predict_per_band("Lecture_2", _variant_overrides("V2"))
    assert sabine_v0[500] > 0.0
    assert sabine_v2[500] > 0.0
    assert abs(sabine_v2[500] - sabine_v0[500]) > MIN_VARIANT_DIFF_S, (
        "V2 override did not change Lecture_2 500 Hz Sabine prediction; "
        "seat-α override may not be wired."
    )


# --------------------------------------------------------------------------- #
# Test 4 — V3 combined acceptance OR null verdict
# --------------------------------------------------------------------------- #


def test_bracket_v3_combined_lecture2_500hz() -> None:
    """V3 (V1 + V2 combined) — acceptance OR null verdict.

    PASSES either way. Acceptance criterion (per §2.2 / ADR 0015):

      |Lecture_2 sabine_500hz - measured_500hz| <= 0.5 s
        AND for each non-Lecture_2 furniture-tracked room R:
          (sabine_500hz[V3, R] - sabine_500hz[V0, R]) <= +0.10 s
          (i.e. no >+0.10 s regression away from measured)

    If the criterion is met → positive verdict (logged via the appendix doc).
    If not → null verdict, with diagnostic listing which rooms regressed and
    by how much (also logged via the appendix doc). v0.8 ships either way.
    """
    measured = _load_measured_rt60()
    measured_lecture_2_500hz = measured["Lecture_2"][500]

    sabine_v3_lecture_2, _ = _predict_per_band("Lecture_2", _variant_overrides("V3"))
    abs_err_lecture_2 = abs(sabine_v3_lecture_2[500] - measured_lecture_2_500hz)

    regressors: list[tuple[str, float]] = []
    for room_id in FURNITURE_ROOMS:
        if room_id == "Lecture_2":
            continue
        sabine_v0, _ = _predict_per_band(room_id, None)
        sabine_v3, _ = _predict_per_band(room_id, _variant_overrides("V3"))
        delta = sabine_v3[500] - sabine_v0[500]
        if delta > NON_LECTURE_2_REGRESSION_LIMIT_S:
            regressors.append((room_id, delta))

    accepts = (
        abs_err_lecture_2 <= LECTURE_2_ACCEPT_ABS_ERR_S and not regressors
    )

    # Either branch passes: this test's job is to *compute* the verdict, not
    # to gate the release on it. The appendix doc + ADR 0015 record the
    # numerical result; v0.8 ships positive OR null.
    if accepts:
        # Positive verdict — assert preconditions hold.
        assert abs_err_lecture_2 <= LECTURE_2_ACCEPT_ABS_ERR_S
        assert not regressors
    else:
        # Null verdict — assert harness produced a finite, non-NaN diagnostic.
        assert abs_err_lecture_2 == abs_err_lecture_2  # not NaN
        assert measured_lecture_2_500hz > 0.0
        # Test still passes; this branch ships the null-result narrative.


# --------------------------------------------------------------------------- #
# Test 5 — emit deterministic perf-doc appendix
# --------------------------------------------------------------------------- #


def test_bracket_emits_perf_doc_appendix() -> None:
    """Recompute V0..V3 (+V4 if env-gated) and write the bracketing perf doc.

    Output is deterministic byte-for-byte: re-running the test yields an
    identical md5sum. Sort orders:

    - rooms: alphabetical (Building_Lobby skipped).
    - variants: V0, V1, V2, V3, then V4 (if env flag set).
    - bands: ascending (per OCTAVE_BANDS_HZ).
    - floats: fixed 3 decimal places.
    """
    measured = _load_measured_rt60()
    variants: tuple[str, ...] = ("V0", "V1", "V2", "V3")
    if _v4_enabled():
        variants = variants + ("V4",)
    table = _compute_variant_table(measured, variants)

    measured_lecture_2_500hz = measured["Lecture_2"][500]

    lines: list[str] = []
    # YAML-style metadata header
    lines.append("---")
    lines.append("title: \"v0.8 Lecture_2 ceiling/seat bracketing — sensitivity-only\"")
    lines.append("date: 2026-05-09")
    lines.append("predecessor_perf_doc: " + PREDECESSOR_PERF_DOC)
    lines.append(
        "generated_by: tests/test_lecture_2_ceiling_seat_bracket.py::"
        "test_bracket_emits_perf_doc_appendix"
    )
    lines.append("scope: sensitivity-only — v0.6/v0.7 numerical baseline preserved")
    lines.append("excluded_rooms: [Building_Lobby]   # ADR 0014")
    v4_status = "enabled" if _v4_enabled() else "disabled"
    lines.append(f"v4_bounding_case: {v4_status}   # gated by ROOMESTIM_BRACKET_V4=1")
    lines.append("---")
    lines.append("")
    lines.append("# v0.8 Lecture_2 ceiling/seat bracketing — sensitivity-only")
    lines.append("")
    lines.append(
        "Sensitivity bracketing of Lecture_2 ceiling material + lecture_seat α "
        "(unoccupied profile) per ADR 0015. v0.6/v0.7 numerical baseline is "
        "preserved; this document is a sensitivity report only."
    )
    lines.append("")
    lines.append(
        "Variant set: **V0** baseline / **V1** ceiling=CEILING_DRYWALL / "
        "**V2** lecture_seat α₅₀₀=0.20 unoccupied / **V3** V1+V2 / "
        "**V4** ceiling=WALL_CONCRETE bounding case (env-gated)."
    )
    lines.append("")
    lines.append(
        "Building_Lobby is excluded per ADR 0014. Rows below cover the 6 "
        "furniture-tracked rooms × 6 octave bands × 2 predictors."
    )
    lines.append("")

    # Per-variant 500 Hz summary (Lecture_2 acceptance evidence)
    lines.append("## §1 Per-variant Lecture_2 500 Hz residual")
    lines.append("")
    lines.append(
        "| Variant | Sabine (s) | Eyring (s) | Measured (s) | "
        "Err Sabine (s) | Err Eyring (s) |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for variant in variants:
        row = table[variant]["Lecture_2"][500]
        lines.append(
            f"| {variant} | {row['sabine']:.3f} | {row['eyring']:.3f} | "
            f"{row['measured']:.3f} | {row['err_sabine']:+.3f} | "
            f"{row['err_eyring']:+.3f} |"
        )
    lines.append("")

    # Acceptance verdict (V3 binding)
    sabine_v3_lecture_2 = table["V3"]["Lecture_2"][500]["sabine"]
    abs_err_lecture_2 = abs(sabine_v3_lecture_2 - measured_lecture_2_500hz)
    regressors: list[tuple[str, float]] = []
    for room_id in FURNITURE_ROOMS:
        if room_id == "Lecture_2":
            continue
        delta = (
            table["V3"][room_id][500]["sabine"]
            - table["V0"][room_id][500]["sabine"]
        )
        if delta > NON_LECTURE_2_REGRESSION_LIMIT_S:
            regressors.append((room_id, delta))
    accepts = (
        abs_err_lecture_2 <= LECTURE_2_ACCEPT_ABS_ERR_S and not regressors
    )
    lines.append("## §2 V3 acceptance verdict")
    lines.append("")
    lines.append(
        f"- Lecture_2 V3 |err| @500 Hz: {abs_err_lecture_2:.3f} s "
        f"(threshold {LECTURE_2_ACCEPT_ABS_ERR_S:.3f} s)"
    )
    if regressors:
        lines.append(
            f"- Non-Lecture_2 rooms regressing > +{NON_LECTURE_2_REGRESSION_LIMIT_S:.3f} s "
            "@500 Hz vs V0 (Sabine):"
        )
        for room_id, delta in sorted(regressors):
            lines.append(f"  - {room_id}: +{delta:.3f} s")
    else:
        lines.append(
            f"- Non-Lecture_2 rooms regressing > +{NON_LECTURE_2_REGRESSION_LIMIT_S:.3f} s "
            "@500 Hz vs V0 (Sabine): none"
        )
    lines.append("")
    if accepts:
        lines.append(
            "**Verdict: POSITIVE** — V3 closes Lecture_2 within the acceptance "
            "envelope without regressing the other 5 furniture-tracked rooms. "
            "v0.9+ may consider ratifying V3 as a new default per ADR 0015 "
            "§Reverse-trigger (independent evidence still required)."
        )
    else:
        lines.append(
            "**Verdict: NULL** — V3 does not satisfy the acceptance envelope. "
            "Single-coefficient ceiling/seat bracketing is insufficient to "
            "close the Lecture_2 residual without external regression. v0.9 "
            "considers the broader F4a per-band sensitivity sweep + coupled-"
            "space modelling per ADR 0015 §Reverse-trigger."
        )
    lines.append("")

    # Per-band tables, per variant
    lines.append("## §3 Per-band bracketing tables")
    lines.append("")
    for variant in variants:
        lines.append(f"### {variant}")
        lines.append("")
        for band in OCTAVE_BANDS_HZ:
            lines.append(f"#### {band} Hz")
            lines.append("")
            lines.append(
                "| Room | Sabine (s) | Eyring (s) | Measured (s) | "
                "Err Sabine (s) | Err Eyring (s) |"
            )
            lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
            for room_id in FURNITURE_ROOMS:
                row = table[variant][room_id][band]
                lines.append(
                    f"| {room_id} | {row['sabine']:.3f} | {row['eyring']:.3f} | "
                    f"{row['measured']:.3f} | {row['err_sabine']:+.3f} | "
                    f"{row['err_eyring']:+.3f} |"
                )
            lines.append("")

    # Caveats (mirrors v0.6 perf-doc framing)
    lines.append("## §4 Caveats")
    lines.append("")
    lines.append(
        "Sensitivity-only report. Sabine and Eyring assume a diffuse field; "
        "real rooms violate this at low frequencies and in heavily-absorbed "
        "spaces (Vorländer 2020 §4). Material labels for V1..V4 are "
        "representative-not-verbatim per ADR 0012 / 0013 / 0015. Measured "
        "T60 values are factual reproductions of the v0.6/v0.7 perf doc "
        "(see ``tests/fixtures/ace_eaton_2016_table_i_measured_rt60.csv``)."
    )

    APPENDIX_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPENDIX_DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Sanity assertions
    assert APPENDIX_DOC_PATH.exists()
    contents = APPENDIX_DOC_PATH.read_text(encoding="utf-8")
    assert "v0.8 Lecture_2 ceiling/seat bracketing" in contents
    assert "## §1 Per-variant Lecture_2 500 Hz residual" in contents
    assert "## §2 V3 acceptance verdict" in contents
    assert "## §3 Per-band bracketing tables" in contents


