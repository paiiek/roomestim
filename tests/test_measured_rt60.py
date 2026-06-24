"""Tests for the [audio] extra: measured (blind) RT60 from a recording.

Skip-guarded via importorskip — they run where the `audio` extra is installed
and skip otherwise (matching the usd/vision extra convention). They lock the
WRAPPER plumbing + honesty, NOT blind-estimator accuracy (no ground truth in
repo; ACE-corpus benchmark deferred), so RT60 assertions are deliberately loose.
"""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest

pytest.importorskip("blind_rt60")
pytest.importorskip("soundfile")

from roomestim.reconstruct._disclosure import MEASURED_RT60_NOTE
from roomestim.reconstruct.measured_rt60 import (
    MeasuredRT60,
    measure_rt60_from_audio,
    measure_rt60_from_signal,
)


def _synth_decay(rt60_s: float = 0.5, fs: int = 16000, dur_s: float = 3.0) -> np.ndarray:
    """White noise with an exponential energy decay of the requested RT60."""
    n = int(fs * dur_s)
    t = np.arange(n) / fs
    rng = np.random.default_rng(0)
    tau = rt60_s / 6.907755  # -60 dB == exp(-t/tau) reaching 1e-3 amplitude
    return rng.standard_normal(n) * np.exp(-t / tau)


def test_measure_from_signal_returns_plausible_rt60() -> None:
    res = measure_rt60_from_signal(_synth_decay(0.5), 16000)
    assert isinstance(res, MeasuredRT60)
    assert 0.1 < res.rt60_s < 1.5  # loose: wrapper plumbing, not accuracy
    assert res.sample_rate_hz == 16000
    assert res.n_samples == 16000 * 3
    assert res.method.startswith("blind-rt60")
    assert res.note == MEASURED_RT60_NOTE


def test_multichannel_averaged_to_mono() -> None:
    mono = _synth_decay(0.5)
    stereo = np.stack([mono, mono], axis=1)  # (n, 2)
    a = measure_rt60_from_signal(mono, 16000)
    b = measure_rt60_from_signal(stereo, 16000)
    assert b.n_samples == a.n_samples  # collapsed to mono length
    assert b.rt60_s == pytest.approx(a.rt60_s, rel=1e-6)


@pytest.mark.parametrize(
    "sig, fs",
    [
        (np.array([]), 16000),
        (np.array([1.0, np.nan, 0.5]), 16000),
    ],
)
def test_bad_signal_raises(sig: np.ndarray, fs: int) -> None:
    with pytest.raises(ValueError):
        measure_rt60_from_signal(sig, fs)


def test_non_positive_fs_raises() -> None:
    with pytest.raises(ValueError):
        measure_rt60_from_signal(_synth_decay(), 0)


def test_audio_file_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import soundfile as sf

    p = tmp_path / "clap.wav"
    sf.write(str(p), _synth_decay(0.5), 16000)
    res = measure_rt60_from_audio(p)
    assert 0.1 < res.rt60_s < 1.5
    assert res.source == str(p)
    assert res.sample_rate_hz == 16000


def test_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        measure_rt60_from_audio("/no/such/file.wav")


def test_note_honesty_invariants() -> None:
    low = MEASURED_RT60_NOTE.lower()
    assert "measurement" in low
    assert "not the geometric" in low or "not a calibrated" in low
    assert "blind" in low
    assert "broadband" in low
    assert "roomestim[audio]" in low


def test_core_import_does_not_pull_audio_deps() -> None:
    """`import roomestim` (and even the measured_rt60 module) must NOT import
    blind_rt60/soundfile — the deps are lazy, keeping the core boundary light."""
    code = (
        "import sys; import roomestim; import roomestim.reconstruct.measured_rt60; "
        "assert 'blind_rt60' not in sys.modules, 'blind_rt60 eagerly imported'; "
        "assert 'soundfile' not in sys.modules, 'soundfile eagerly imported'; "
        "print('ok')"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout
