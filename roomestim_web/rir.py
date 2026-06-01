"""roomestim_web.rir — Per-band early mono-RIR assembly + mixing-time + splice.

Phase A auralization (ADR 0044). Builds a per-band early mono room impulse
response directly from pyroomacoustics image-source data (``pra_source.images``
arrival times + ``pra_source.damping`` per-band attenuation), computes the
analytic Lindau (2012) mixing time, and splices a statistical late tail
(``roomestim_web.late_reverb``) with a per-band energy-continuity rule.

This module is HRTF-free and deterministic: the early assembly is pure
geometry (no RNG); ``seed`` is threaded only into the late path. ``compute_rir``
and ``measure_rt60`` are NOT used (image-source direct assembly per the §E spike,
OQ-48). The 6 roomestim octave bands are preserved end-to-end (no 500 Hz scalar
collapse); ``pra_source.damping`` is sliced ``[0:6]`` with a band-grid guard
because pyroomacoustics emits an 8-band octave grid at fs=48000 (deviation D1).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from roomestim.model import OCTAVE_BANDS_HZ

if TYPE_CHECKING:
    from roomestim.model import RoomModel

# Speed of sound (m/s) — matches binaural.py geometric-spreading constant.
_SPEED_OF_SOUND_M_S: float = 343.0

# Minimum distance for the 1/r geometric-spreading gain (binaural.py:377 parity).
_MIN_DIST_M: float = 0.1

# Energy-continuity splice window (Gate 3): fixed 5 ms for determinism.
_SPLICE_WINDOW_S: float = 0.005


def _band_grid_guard(damping: np.ndarray) -> np.ndarray:
    """Slice ``damping`` to the leading 6 roomestim octave bands.

    pyroomacoustics emits an 8-band octave grid
    ``[125, 250, 500, 1000, 2000, 4000, 8000, 16000]`` at fs=48000; the first
    6 rows align exactly with :data:`roomestim.model.OCTAVE_BANDS_HZ`
    (deviation D1). Raises ``ValueError`` if fewer than 6 bands are present
    (fail loud, not silent). 1-D damping (single broadband band) is rejected —
    Phase A requires per-band data.
    """
    if damping.ndim != 2 or damping.shape[0] < 6:
        raise ValueError(
            f"damping must be 2-D with >= 6 bands (roomestim octave grid); "
            f"got shape {damping.shape}. Phase A requires per-band damping "
            "(build the pra room with a 6-band pra.Material)."
        )
    return damping[0:6]


def assemble_early_rir_per_band(
    room_pra: Any,
    listener_pos: np.ndarray,
    *,
    sample_rate_hz: int = 48000,
) -> np.ndarray:
    """Return ``(6, L_early)`` per-band early mono-RIR (amplitude impulse train).

    Iterates ``pra_source.images`` (arrival time = dist / c) and
    ``pra_source.damping`` (per-band attenuation, sliced ``[0:6]`` via the
    band-grid guard). Gain per image is ``damping[b, i] / max(dist, 0.1)``
    placed at the integer sample ``round(dist / c * fs)``. No HRIR (mono).
    Deterministic: pure geometry, no RNG. Always emits the 6 roomestim octave
    bands (``len(OCTAVE_BANDS_HZ)``), enforced by the band-grid guard.

    Args:
        room_pra: a pyroomacoustics ``Room`` AFTER ``image_source_model()``.
        listener_pos: ``(3,)`` mic position in the pra room frame.
        sample_rate_hz: output sample rate.
    """
    n_bands = len(OCTAVE_BANDS_HZ)

    listener = np.asarray(listener_pos, dtype=np.float64).reshape(3)

    # First pass: per-image delay + per-band gain; track max delay for length.
    entries: list[tuple[int, np.ndarray]] = []
    max_delay = 0
    for pra_source in room_pra.sources:
        images = pra_source.images  # (3, N_images)
        damping = _band_grid_guard(np.asarray(pra_source.damping, dtype=np.float64))
        n_images = images.shape[1]
        for i in range(n_images):
            rel = images[:, i] - listener
            dist = float(np.linalg.norm(rel))
            if dist < 1e-6:
                continue
            n_delay = int(round(dist / _SPEED_OF_SOUND_M_S * sample_rate_hz))
            gain = damping[:, i] / max(dist, _MIN_DIST_M)  # (6,)
            entries.append((n_delay, gain))
            if n_delay > max_delay:
                max_delay = n_delay

    length = max_delay + 1
    rir = np.zeros((n_bands, length), dtype=np.float64)
    for n_delay, gain in entries:
        rir[:, n_delay] += gain
    return rir


def mixing_time_s(room: "RoomModel") -> float:
    """Analytic Lindau (2012) mixing time: ``t_mix[s] = 1e-3 * sqrt(V[m^3])``.

    ``V`` is the room volume from
    :func:`roomestim.geom.polygon.room_volume` (existing core helper;
    read-only core use, no core change).
    """
    from roomestim.geom.polygon import room_volume

    volume_m3 = room_volume(room)
    return 1e-3 * float(np.sqrt(volume_m3))


def total_rir_length_samples(rt60_per_band_s: dict[int, float], fs: int) -> int:
    """Total convolvable RIR length = -60 dB reach of the SLOWEST band.

    ``max(rt60_per_band_s.values())`` seconds * fs. Does NOT inherit the demo's
    2 s constant (binaural.py:402). Returns at least 1 sample.
    """
    if not rt60_per_band_s:
        raise ValueError("rt60_per_band_s must be non-empty")
    slowest_s = max(rt60_per_band_s.values())
    return max(int(np.ceil(slowest_s * fs)), 1)


def assemble_mono_rir_per_band(
    room_pra: Any,
    listener_pos: np.ndarray,
    room: "RoomModel",
    rt60_per_band_s: dict[int, float],
    *,
    sample_rate_hz: int = 48000,
    seed: int = 0,
) -> np.ndarray:
    """Full per-band mono RIR ``(6, L_total)``.

    Early (this module) truncated at ``t_mix``; late tail
    (:mod:`roomestim_web.late_reverb`) pasted with per-band energy-continuity
    normalization (Gate 3). Returns the 6-band array; recombination to broadband
    is the caller's job via the power-complementary filterbank in
    ``late_reverb.recombine_bands``.

    Truncate-and-paste splice, no crossfade (DAFx 2025 policy). The late tail
    band envelope start amplitude is scaled so per-band energy in the 5 ms
    window straddling ``t_mix`` is continuous.
    """
    from roomestim_web.late_reverb import synthesize_late_tail_per_band

    n_bands = len(OCTAVE_BANDS_HZ)
    early = assemble_early_rir_per_band(
        room_pra, listener_pos, sample_rate_hz=sample_rate_hz
    )

    t_mix_s = mixing_time_s(room)
    t_mix = int(round(t_mix_s * sample_rate_hz))
    total_len = total_rir_length_samples(rt60_per_band_s, sample_rate_hz)
    # Total length must at least span the splice point plus a usable tail.
    total_len = max(total_len, t_mix + 1)

    window = max(int(round(_SPLICE_WINDOW_S * sample_rate_hz)), 1)

    # Late tail spans [t_mix, total_len). Synthesize a unit-amplitude tail.
    n_late = total_len - t_mix
    late = synthesize_late_tail_per_band(
        rt60_per_band_s,
        n_late,
        sample_rate_hz=sample_rate_hz,
        seed=seed,
    )  # (6, n_late)

    out = np.zeros((n_bands, total_len), dtype=np.float64)

    # Paste the early RIR truncated at t_mix.
    early_keep = min(t_mix, early.shape[1])
    if early_keep > 0:
        out[:, :early_keep] = early[:, :early_keep]

    # Per-band energy-continuity normalization (Gate 3).
    for b in range(n_bands):
        # Early energy in the window ending at t_mix.
        e_lo = max(t_mix - window, 0)
        e_hi = min(t_mix, early.shape[1])
        if e_hi > e_lo:
            e_early = float(np.sum(early[b, e_lo:e_hi] ** 2))
        else:
            e_early = 0.0
        # Sparse-ISM fallback: a band can have zero energy inside the 5 ms
        # pre-t_mix window (no reflection landed there) yet still carry early
        # energy elsewhere. Referencing only the window would zero the band's
        # ENTIRE late tail (silent-band drop). Fall back to the band's mean
        # per-sample early energy across the kept early region so the tail is
        # retained at a level consistent with that band's overall early decay.
        if e_early <= 0.0 and early_keep > 0:
            band_total = float(np.sum(early[b, :early_keep] ** 2))
            if band_total > 0.0:
                e_early = band_total / float(early_keep) * float(window)
        # Late unit-window energy (first `window` samples of the unit tail).
        late_win = late[b, :window]
        e_late_unit = float(np.sum(late_win ** 2))
        if e_late_unit > 0.0 and e_early > 0.0:
            a0 = float(np.sqrt(e_early / e_late_unit))
        else:
            a0 = 0.0
        out[b, t_mix:total_len] = a0 * late[b, : total_len - t_mix]

    return out
