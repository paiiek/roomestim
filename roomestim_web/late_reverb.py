"""roomestim_web.late_reverb — Per-band exponential filtered-noise late tail.

Phase A auralization (ADR 0044 §B/§C). Synthesizes the statistical diffuse
reverberation tail as per-band exponentially-decaying shaped Gaussian noise,
driven by the per-band RT60 from ``predict_rt60_default_per_band`` (the single
RT60 truth source). Bands are split/recombined through a power-complementary
octave filterbank so the summed-band power is flat across band edges (no naive
summation). v1 model is filtered-noise; FDN is deferred to Phase B.

Determinism (project-mandated byte-equal): each band uses
``np.random.default_rng(seed + band_index)`` (NOT the legacy process-global
``np.random.seed`` of the demo path, which is order-fragile). A fixed
``seed=0`` default makes two runs byte-identical. The filterbank coefficients
are deterministic (computed from fixed band edges). No wall-clock, no unseeded
RNG anywhere in the late path (deviation D3).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt  # type: ignore[import-untyped]

from roomestim.model import OCTAVE_BANDS_HZ

# Local mirror of the 6 roomestim octave centers (imported source of truth).
OCTAVE_BANDS_HZ_LOCAL: tuple[int, ...] = tuple(OCTAVE_BANDS_HZ)

# Butterworth order for each octave bandpass/shelf section. Order 4 gives a
# ~ -3 dB crossover at the geometric band edges (power-complementary pairing).
_FILTER_ORDER: int = 4


def per_band_decay_envelope(rt60_s: float, n_samples: int, fs: int) -> np.ndarray:
    """Exponential 60-dB decay envelope ``decay(t) = 10 ** (-3 * t / rt60_s)``.

    ``t = arange(n_samples) / fs``. At ``t = rt60_s`` the envelope is exactly
    ``10 ** -3`` (-60 dB). Pure deterministic (no RNG).
    """
    if rt60_s <= 0.0:
        raise ValueError(f"rt60_s must be positive; got {rt60_s}")
    t = np.arange(n_samples, dtype=np.float64) / float(fs)
    return np.power(10.0, -3.0 * t / rt60_s)


def _band_edges_hz() -> list[tuple[float, float]]:
    """Geometric crossover edges for the 6 octave bands.

    Returns a per-band ``(lo, hi)`` edge pair where ``lo``/``hi`` are the
    geometric means between adjacent octave centers; the lowest band has
    ``lo = 0`` (lowpass) and the highest has ``hi = inf`` (highpass).
    """
    centers = [float(c) for c in OCTAVE_BANDS_HZ_LOCAL]
    edges: list[float] = []
    for i in range(len(centers) - 1):
        edges.append(float(np.sqrt(centers[i] * centers[i + 1])))
    band_edges: list[tuple[float, float]] = []
    for i in range(len(centers)):
        lo = 0.0 if i == 0 else edges[i - 1]
        hi = float("inf") if i == len(centers) - 1 else edges[i]
        band_edges.append((lo, hi))
    return band_edges


def _band_sos(band_index: int, fs: int) -> np.ndarray:
    """Second-order-section coefficients for the octave band's filter.

    Band 0 → lowpass; last band → highpass; interior bands → bandpass.
    Deterministic for fixed ``fs`` and ``OCTAVE_BANDS_HZ_LOCAL``.
    """
    nyq = fs / 2.0
    lo, hi = _band_edges_hz()[band_index]
    n_bands = len(OCTAVE_BANDS_HZ_LOCAL)
    if band_index == 0:
        sos = butter(_FILTER_ORDER, hi / nyq, btype="lowpass", output="sos")
    elif band_index == n_bands - 1:
        sos = butter(_FILTER_ORDER, lo / nyq, btype="highpass", output="sos")
    else:
        sos = butter(
            _FILTER_ORDER,
            [lo / nyq, hi / nyq],
            btype="bandpass",
            output="sos",
        )
    return np.asarray(sos, dtype=np.float64)


def synthesize_late_tail_per_band(
    rt60_per_band_s: dict[int, float],
    n_samples: int,
    *,
    sample_rate_hz: int = 48000,
    seed: int = 0,
) -> np.ndarray:
    """Return ``(6, n_samples)`` per-band late tail (band-limited, decaying).

    For each band: seeded Gaussian noise
    (``np.random.default_rng(seed + band_index)`` for byte-equal determinism)
    multiplied by :func:`per_band_decay_envelope` for that band's RT60, then
    band-limited with the power-complementary octave filterbank. Returns
    per-band (the caller normalizes for splice continuity, then recombines via
    :func:`recombine_bands`).
    """
    bands = list(OCTAVE_BANDS_HZ_LOCAL)
    if set(rt60_per_band_s.keys()) != set(bands):
        raise ValueError(
            f"rt60_per_band_s keys {sorted(rt60_per_band_s)} must equal the "
            f"6 roomestim octave bands {bands}"
        )
    n = max(int(n_samples), 0)
    out = np.zeros((len(bands), n), dtype=np.float64)
    if n == 0:
        return out
    for b_idx, band_hz in enumerate(bands):
        rng = np.random.default_rng(seed + b_idx)
        noise = rng.standard_normal(n)
        # Band-limit the (white) noise FIRST, then apply the decay envelope.
        # Filtering-then-decaying keeps the envelope in full control of the
        # decay slope; decaying-then-filtering would let the band filter's
        # impulse response smear the decay and corrupt the per-band RT60
        # (narrow low bands decay far too fast otherwise).
        # Single-pass IIR: Butterworth bands crossing at their -3 dB geometric
        # edges sum to flat power (|H|^2 power-complementary). Phase distortion
        # is irrelevant for a decaying-noise diffuse tail; single-pass keeps the
        # power-complementary property that filtfilt's double-pass would break.
        sos = _band_sos(b_idx, sample_rate_hz)
        band_noise: np.ndarray = sosfilt(sos, noise)
        envelope = per_band_decay_envelope(rt60_per_band_s[band_hz], n, sample_rate_hz)
        out[b_idx] = band_noise * envelope
    return out


def recombine_bands(per_band: np.ndarray) -> np.ndarray:
    """Power-complementary recombination of ``(6, N)`` → ``(N,)`` broadband.

    Used after splice-continuity normalization. The per-band streams are
    already band-limited by the power-complementary filterbank, so summation
    preserves flat power across band edges.
    """
    arr = np.asarray(per_band, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError(f"per_band must be 2-D (bands, samples); got {arr.shape}")
    result: np.ndarray = np.sum(arr, axis=0)
    return result
