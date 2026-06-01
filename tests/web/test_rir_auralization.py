"""tests/web/test_rir_auralization.py — Phase A auralization acceptance tests.

Load-bearing acceptance tests A1–A12 for the RIR auralization Phase A
implementation (ADR 0044): ``roomestim_web.rir``, ``roomestim_web.late_reverb``,
and ``roomestim_web.binaural.synthesize_brir``. Each test fails without the
implementation (no tautologies). web-marked (run in the web gate, not core).
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

pytest.importorskip("pyroomacoustics")
pytest.importorskip("scipy")

from roomestim.model import OCTAVE_BANDS_HZ, MaterialAbsorptionBands
from roomestim.reconstruct.predictor import predict_rt60_default_per_band
from roomestim_web.binaural import _build_shoebox_room, synthesize_brir
from roomestim_web.late_reverb import (
    per_band_decay_envelope,
    recombine_bands,
    synthesize_late_tail_per_band,
)
from roomestim_web.report import _surface_areas_by_material
from roomestim_web.rir import (
    assemble_early_rir_per_band,
    assemble_mono_rir_per_band,
    mixing_time_s,
    total_rir_length_samples,
)
from tests.fixtures.synthetic_rooms import shoebox

FS = 48000


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def band_room() -> object:
    """A small shoebox with every surface promoted to 6-band absorption.

    Mirrors what ``synthesize_brir`` does internally so the pra room build
    yields per-band damping (the §E spike showed scalar materials → 1-band).
    """
    room = shoebox(width=5.0, depth=4.0, height=2.8)
    new_surfaces = [
        dataclasses.replace(
            s, absorption_bands=MaterialAbsorptionBands.get(s.material, (s.absorption_500hz,) * 6)
        )
        for s in room.surfaces
    ]
    return dataclasses.replace(room, surfaces=new_surfaces)


@pytest.fixture
def synthetic_hrtf() -> object:
    from roomestim_web.hrtf_io import HrtfTable

    dirs = np.array(
        [[0, 0], [90, 0], [180, 0], [270, 0], [0, 90], [0, -90]], dtype=np.float64
    )
    hrir_l = np.zeros((6, 64), dtype=np.float64)
    hrir_l[:, 0] = 1.0
    hrir_r = hrir_l.copy()
    return HrtfTable(
        sample_rate_hz=48000,
        directions=dirs,
        hrirs_left=hrir_l,
        hrirs_right=hrir_r,
        attribution="synthetic-test-fixture",
    )


def _build_pra_with_source(room: object) -> tuple[object, np.ndarray]:
    """Build a pra shoebox + mic at listener + source 1 m front; run ISM."""
    rp = _build_shoebox_room(room, FS, 5)  # type: ignore[arg-type]
    cx = room.listener_area.centroid.x  # type: ignore[attr-defined]
    cz = room.listener_area.centroid.z  # type: ignore[attr-defined]
    ly = room.listener_area.height_m  # type: ignore[attr-defined]
    min_x = min(p.x for p in room.floor_polygon)  # type: ignore[attr-defined]
    min_z = min(p.z for p in room.floor_polygon)  # type: ignore[attr-defined]
    lp = np.array([cx - min_x, ly, cz - min_z], dtype=np.float64)
    rp.add_microphone(lp.reshape(3, 1))
    rp.add_source([cx - min_x, ly, cz - min_z + 1.0], signal=np.array([1.0]))
    rp.image_source_model()
    return rp, lp


def _rt60(room: object) -> dict[int, float]:
    pred = predict_rt60_default_per_band(room, _surface_areas_by_material(room))  # type: ignore[arg-type]
    return dict(pred.rt60_per_band_s)


# ── Step 1: rir.py ──────────────────────────────────────────────────────────


@pytest.mark.web
def test_a1_early_rir_shape_and_first_arrival(band_room: object) -> None:
    """A1: (6, L) shape; direct-path sample index = round(dist/343*fs) ±1."""
    rp, lp = _build_pra_with_source(band_room)
    early = assemble_early_rir_per_band(rp, lp, sample_rate_hz=FS)
    assert early.shape[0] == 6
    assert early.ndim == 2 and early.shape[1] > 1
    # Direct path: source is 1 m in front of the listener.
    expected = int(round(1.0 / 343.0 * FS))
    # The first nonzero column across all bands is the direct path.
    nonzero_cols = np.where(np.any(early != 0.0, axis=0))[0]
    assert nonzero_cols.size > 0
    first = int(nonzero_cols[0])
    assert abs(first - expected) <= 1


@pytest.mark.web
def test_a2_band_grid_guard_raises() -> None:
    """A2: band-grid guard raises ValueError on <6 bands."""
    from roomestim_web.rir import _band_grid_guard

    with pytest.raises(ValueError):
        _band_grid_guard(np.ones((1, 10)))  # 1-band (scalar material)
    with pytest.raises(ValueError):
        _band_grid_guard(np.ones(10))  # 1-D
    # 8-band pra grid: leading 6 are recovered, no raise.
    ok = _band_grid_guard(np.arange(80, dtype=float).reshape(8, 10))
    assert ok.shape == (6, 10)


@pytest.mark.web
def test_a3_mixing_time_analytic_exact(band_room: object) -> None:
    """A3: t_mix == 1e-3 * sqrt(room_volume(room)) exactly."""
    from roomestim.geom.polygon import room_volume

    expected = 1e-3 * float(np.sqrt(room_volume(band_room)))  # type: ignore[arg-type]
    assert mixing_time_s(band_room) == expected  # type: ignore[arg-type]


@pytest.mark.web
def test_a4_total_length_reaches_slowest_band() -> None:
    """A4: total length >= max(RT60_band) * fs (slowest band -60 dB reach)."""
    rt = {b: 0.4 for b in OCTAVE_BANDS_HZ}
    rt[125] = 1.5
    n = total_rir_length_samples(rt, FS)
    assert n >= int(np.ceil(1.5 * FS))
    # Demo 2 s constant is NOT inherited: shorter RT60 → shorter RIR.
    rt_short = {b: 0.3 for b in OCTAVE_BANDS_HZ}
    assert total_rir_length_samples(rt_short, FS) < 2 * FS


# ── Step 2: late_reverb.py ──────────────────────────────────────────────────


@pytest.mark.web
def test_a5_decay_envelope_minus_60db_at_rt60() -> None:
    """A5: envelope at t = rt60_s equals 10**-3 (-60 dB) exactly."""
    rt60 = 0.8
    n = int(round(rt60 * FS)) + 1
    env = per_band_decay_envelope(rt60, n, FS)
    # Sample exactly at t = rt60_s (index round(rt60*fs)).
    idx = int(round(rt60 * FS))
    assert env[idx] == pytest.approx(10.0**-3, rel=1e-9)


@pytest.mark.web
def test_a6_late_tail_byte_equal() -> None:
    """A6: two calls with identical args are byte-equal."""
    rt = {b: 0.5 for b in OCTAVE_BANDS_HZ}
    n = FS // 2
    a = synthesize_late_tail_per_band(rt, n, sample_rate_hz=FS, seed=0)
    b = synthesize_late_tail_per_band(rt, n, sample_rate_hz=FS, seed=0)
    assert np.array_equal(a, b)


@pytest.mark.web
def test_a7_filterbank_power_complementary() -> None:
    """A7: summed-band power has no >3 dB notch/peak at the 5 crossovers."""
    from scipy.signal import sosfreqz  # type: ignore[import-untyped]

    from roomestim_web.late_reverb import _band_edges_hz, _band_sos

    w = np.linspace(1e-3, np.pi, 8000)
    freqs = w / np.pi * (FS / 2.0)
    total = np.zeros_like(w)
    for b in range(6):
        sos = _band_sos(b, FS)
        _, h = sosfreqz(sos, worN=w)
        # Single-pass IIR (sosfilt): output power = |H|^2. Butterworth bands
        # crossing at their -3 dB edges sum to flat power (power-complementary).
        total += np.abs(h) ** 2
    crossovers = sorted(
        {e for lo, hi in _band_edges_hz() for e in (lo, hi) if 0 < e < np.inf}
    )
    assert len(crossovers) == 5
    for f in crossovers:
        idx = int(np.argmin(np.abs(freqs - f)))
        dev_db = abs(10.0 * np.log10(total[idx]))
        assert dev_db <= 3.0, f"crossover {f:.0f} Hz deviates {dev_db:.2f} dB"


@pytest.mark.web
def test_a8_six_bands_distinct_no_collapse() -> None:
    """A8: 6 bands present and distinct (no 500 Hz scalar collapse)."""
    rt = {125: 1.5, 250: 1.2, 500: 0.9, 1000: 0.7, 2000: 0.5, 4000: 0.4}
    n = FS // 2
    pb = synthesize_late_tail_per_band(rt, n, sample_rate_hz=FS, seed=0)
    assert pb.shape[0] == 6
    # Bands are not all equal (distinct RNG streams + distinct decay slopes).
    for i in range(1, 6):
        assert not np.array_equal(pb[0], pb[i])


# ── Step 3: synthesize_brir ─────────────────────────────────────────────────


@pytest.mark.web
def test_a9_brir_two_channel_convolvable(
    band_room: object, synthetic_hrtf: object
) -> None:
    """A9: (2, L) shape; fftconvolve-able, finite output."""
    from scipy.signal import fftconvolve  # type: ignore[import-untyped]

    brir = synthesize_brir(band_room, hrtf=synthetic_hrtf, max_order=3, seed=0)  # type: ignore[arg-type]
    assert brir.ndim == 2 and brir.shape[0] == 2
    assert np.all(np.isfinite(brir))
    y = fftconvolve(np.random.RandomState(0).randn(2000), brir[0])
    assert np.all(np.isfinite(y))


@pytest.mark.web
def test_a10_brir_deterministic_byte_equal(
    band_room: object, synthetic_hrtf: object
) -> None:
    """A10: two synthesize_brir calls with identical args are byte-equal."""
    b1 = synthesize_brir(band_room, hrtf=synthetic_hrtf, max_order=3, seed=0)  # type: ignore[arg-type]
    b2 = synthesize_brir(band_room, hrtf=synthetic_hrtf, max_order=3, seed=0)  # type: ignore[arg-type]
    assert np.array_equal(b1, b2)


@pytest.mark.web
def test_a11_tail_decay_matches_rt60_per_band(band_room: object) -> None:
    """A11: each per-band late-tail decay matches THAT band's RT60 within ±10%.

    Fit the Schroeder EDC of each band of the late tail — the §C handoff product
    (``synthesize_late_tail_per_band``) whose per-band decay is, by construction,
    governed by ``predict_rt60_default_per_band`` (the single RT60 truth source).
    The total RIR length spans the slowest band's -60 dB reach (A4), so each
    band's EDC is well-defined over -15..-45 dB.

    This is the load-bearing decay invariant and STRONGER than a single
    broadband fit: a non-uniform-RT60 room (the painted shoebox spans
    ~1.1..1.9 s across bands) has a recombined broadband decay that is an
    energy-weighted MIX (the wide high band dominates), so it does NOT equal
    max(RT60); only the per-band contract holds. Any break in the RT60→envelope
    wiring (wrong band index, wrong slope, scalar collapse to one band) moves a
    band's fitted RT60 outside tolerance. Loose tolerance: sanity invariant, not
    a perceptual claim (OQ-47).
    """
    rt = _rt60(band_room)
    n = total_rir_length_samples(rt, FS)
    per_band = synthesize_late_tail_per_band(rt, n, sample_rate_hz=FS, seed=0)
    assert per_band.shape[0] == 6
    for b_idx, band_hz in enumerate(OCTAVE_BANDS_HZ):
        band = per_band[b_idx]
        edc = np.cumsum((band**2)[::-1])[::-1]
        edc = edc / edc[0]
        edc_db = 10.0 * np.log10(np.maximum(edc, 1e-20))
        t = np.arange(len(edc_db)) / FS
        mask = (edc_db <= -15.0) & (edc_db >= -45.0)
        assert mask.sum() > 10, f"band {band_hz} Hz: insufficient EDC range"
        slope = np.polyfit(t[mask], edc_db[mask], 1)[0]  # dB/s
        rt60_fit = -60.0 / slope
        target = rt[band_hz]
        assert abs(rt60_fit - target) / target <= 0.10, (
            f"band {band_hz} Hz: fit RT60 {rt60_fit:.3f}s vs target {target:.3f}s "
            f"({100 * abs(rt60_fit - target) / target:.1f}% off)"
        )


@pytest.mark.web
def test_a11b_brir_tail_decays(band_room: object, synthetic_hrtf: object) -> None:
    """A11b: the spliced BRIR late tail is decaying (smoothed energy late << early).

    Complements A11: the per-band energy-continuity splice (A12) re-weights the
    BRIR tail bands, so its broadband RT60 is not asserted; instead verify the
    tail genuinely decays (block energy at the end is far below the start), so
    the BRIR carries an audible, finite, decaying reverberation tail.
    """
    brir = synthesize_brir(band_room, hrtf=synthetic_hrtf, max_order=4, seed=0)  # type: ignore[arg-type]
    t_mix = int(round(mixing_time_s(band_room) * FS))  # type: ignore[arg-type]
    tail = brir[0, t_mix:]
    blk = int(0.05 * FS)
    n_blocks = len(tail) // blk
    assert n_blocks >= 4
    e_first = float(np.mean(tail[:blk] ** 2))
    e_last = float(np.mean(tail[(n_blocks - 1) * blk : n_blocks * blk] ** 2))
    assert e_first > 0.0
    # Last block at least 20 dB below the first (monotone decay sanity).
    assert 10.0 * np.log10(max(e_last, 1e-20) / e_first) <= -20.0


@pytest.mark.web
def test_a12_splice_per_band_continuity(band_room: object) -> None:
    """A12 (Gate 3): per-band discontinuity at t_mix <= 3 dB for all 6 bands."""
    rp, lp = _build_pra_with_source(band_room)
    rt = _rt60(band_room)
    mono = assemble_mono_rir_per_band(rp, lp, band_room, rt, sample_rate_hz=FS, seed=0)  # type: ignore[arg-type]
    t_mix = int(round(mixing_time_s(band_room) * FS))  # type: ignore[arg-type]
    window = int(round(0.005 * FS))
    for b in range(6):
        pre = float(np.sum(mono[b, t_mix - window : t_mix] ** 2))
        post = float(np.sum(mono[b, t_mix : t_mix + window] ** 2))
        if pre <= 0.0 or post <= 0.0:
            continue  # silent band on both sides — no discontinuity to test
        disc_db = abs(10.0 * np.log10(post / pre))
        assert disc_db <= 3.0, f"band {b} splice discontinuity {disc_db:.2f} dB"


@pytest.mark.web
def test_a12_real_hrtf_brir_splice_continuity(band_room: object) -> None:
    """A12 (Gate 3, REAL HRTF): BRIR splice discontinuity <= 3 dB on BOTH channels.

    The mono per-band splice (A12) is normalized against the HRIR-FREE early mono
    RIR, but each BRIR channel's early level carries direction-dependent HRIR
    energy the mono reference never sees. With the production ``load_default_hrtf``
    on the standard 5x4x2.8 fixture, channel 1's discontinuity was ~3.22 dB
    (> the 3 dB limit) before the per-channel tail renormalization; the synthetic
    unit-impulse HRTF (A9/A10/A11b) masks it. This test is load-bearing: it FAILS
    against the pre-fix code and PASSES after the per-channel splice fix.
    """
    from roomestim_web.hrtf_io import load_default_hrtf

    hrtf = load_default_hrtf()
    brir = synthesize_brir(band_room, hrtf=hrtf, max_order=10, seed=0)  # type: ignore[arg-type]
    t_mix = int(round(mixing_time_s(band_room) * FS))  # type: ignore[arg-type]
    window = int(round(0.005 * FS))
    for ch in range(2):
        x = brir[ch]
        pre = float(np.sum(x[t_mix - window : t_mix] ** 2))
        post = float(np.sum(x[t_mix : t_mix + window] ** 2))
        assert pre > 0.0 and post > 0.0
        disc_db = abs(10.0 * np.log10(post / pre))
        assert disc_db <= 3.0, f"channel {ch} splice discontinuity {disc_db:.2f} dB"


@pytest.mark.web
def test_a12_silent_window_band_retains_tail() -> None:
    """All 6 mono late-tail bands keep nonzero energy even with a sparse early RIR.

    If a band has zero energy inside the 5 ms pre-t_mix window (no reflection
    landed there), referencing only that window would zero the band's ENTIRE late
    tail (silent-band drop). The fallback references the band's overall early
    energy instead, so the tail is retained. Constructed sparse early RIR: a
    single direct-path impulse per band far before t_mix, empty pre-window.
    """
    from unittest.mock import patch

    rt = {b: 0.6 for b in OCTAVE_BANDS_HZ}
    fs = FS
    room = shoebox(width=5.0, depth=4.0, height=2.8)
    t_mix = int(round(mixing_time_s(room) * fs))  # type: ignore[arg-type]
    window = int(round(0.005 * fs))
    # Sparse early: one impulse per band well before the pre-t_mix window so the
    # 5 ms window straddling t_mix is empty for every band.
    early = np.zeros((6, t_mix + 10), dtype=np.float64)
    direct = max(t_mix - 2 * window, 1)
    early[:, direct] = np.array([1.0, 0.9, 0.8, 0.7, 0.6, 0.5])
    with patch("roomestim_web.rir.assemble_early_rir_per_band", return_value=early):
        mono = assemble_mono_rir_per_band(
            object(), np.zeros(3), room, rt, sample_rate_hz=fs, seed=0  # type: ignore[arg-type]
        )
    for b in range(6):
        tail_energy = float(np.sum(mono[b, t_mix:] ** 2))
        assert tail_energy > 0.0, f"band {b} late tail was silently dropped"


@pytest.mark.web
def test_recombine_broadband_shape() -> None:
    """recombine_bands collapses (6, N) → (N,) by power-complementary sum."""
    pb = np.ones((6, 100), dtype=np.float64)
    out = recombine_bands(pb)
    assert out.shape == (100,)
    np.testing.assert_array_equal(out, np.full(100, 6.0))
