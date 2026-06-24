"""Measured (blind) RT60 from a recorded audio signal — `[audio]` extra (A3).

Unlike the geometric RT60 MODEL (Sabine / Eyring / ISM in
:mod:`roomestim.reconstruct.materials` / `image_source`), which depends on
ASSUMED surface materials, this estimates RT60 from an actual recording — a
MEASUREMENT of the real room. It wraps the `blind-rt60` package (Ratnam et al.
maximum-likelihood reverberation-decay model) and reads audio via `soundfile`.

The honest framing is the single-source-of-truth
:data:`roomestim.reconstruct._disclosure.MEASURED_RT60_NOTE`: the blind estimator
has its own (in-repo-UNVALIDATED) error, returns a single BROADBAND value (not
per-octave-band), and depends on the recording quality.

LAYERING: this module lazily imports `blind_rt60` + `soundfile` INSIDE the
functions, never at module import time, so importing it does not pull the
`[audio]` deps and the core / `import roomestim` boundary stays dependency-light.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from roomestim.reconstruct._disclosure import MEASURED_RT60_NOTE

if TYPE_CHECKING:  # numpy is a core dep, but keep the public types lazy-friendly
    import numpy as np

__all__ = [
    "MEASURED_RT60_NOTE",
    "MeasuredRT60",
    "measure_rt60_from_audio",
    "measure_rt60_from_signal",
]

_AUDIO_EXTRA_HINT = (
    "measured RT60 needs the optional 'audio' extra: pip install 'roomestim[audio]' "
    "(provides blind-rt60 + soundfile)."
)


@dataclass(frozen=True)
class MeasuredRT60:
    """A single broadband measured (blind) RT60 estimate. See ``note``."""

    rt60_s: float
    sample_rate_hz: int
    n_samples: int
    source: str          # file path or "<signal>" for an in-memory array
    method: str          # = "blind-rt60 (Ratnam et al. ML decay model)"
    note: str            # = MEASURED_RT60_NOTE


_METHOD = "blind-rt60 (Ratnam et al. ML decay model)"


def measure_rt60_from_signal(
    signal: "np.ndarray",
    sample_rate_hz: int,
    *,
    source: str = "<signal>",
    **blind_kwargs: object,
) -> MeasuredRT60:
    """Blind broadband RT60 (seconds) from an in-memory mono/multichannel signal.

    Multichannel input is averaged to mono. The estimator is run at the
    recording's NATIVE ``sample_rate_hz`` (the blind-rt60 default design point is
    8 kHz speech; resampling is left to the caller). ``blind_kwargs`` are
    forwarded to ``BlindRT60(...)`` (e.g. ``percentile``, ``max_itr``). Raises
    ``ImportError`` (with an install hint) when the ``[audio]`` extra is absent,
    and ``ValueError`` on an empty / non-finite signal or a non-positive sample
    rate.
    """
    import numpy as np

    if sample_rate_hz <= 0:
        raise ValueError(f"sample_rate_hz must be > 0, got {sample_rate_hz}")
    # Resolve the [audio] extra FIRST so a missing dependency surfaces the
    # friendly install hint before any signal-shape complaint.
    try:
        from blind_rt60 import BlindRT60
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(_AUDIO_EXTRA_HINT) from exc

    x = np.asarray(signal, dtype=np.float64)
    if x.ndim > 1:  # average channels to mono
        x = x.mean(axis=tuple(range(1, x.ndim)))
    if x.size == 0:
        raise ValueError("signal is empty")
    if not np.all(np.isfinite(x)):
        raise ValueError("signal contains non-finite samples")

    estimator = BlindRT60(fs=sample_rate_hz, **blind_kwargs)
    rt60 = float(estimator.estimate(x, sample_rate_hz))
    return MeasuredRT60(
        rt60_s=rt60,
        sample_rate_hz=int(sample_rate_hz),
        n_samples=int(x.size),
        source=source,
        method=_METHOD,
        note=MEASURED_RT60_NOTE,
    )


def measure_rt60_from_audio(
    audio_path: str | Path,
    **blind_kwargs: object,
) -> MeasuredRT60:
    """Blind broadband RT60 (seconds) from an audio file (wav/flac/ogg via soundfile).

    Reads the file, averages channels to mono, and runs the blind estimator.
    Raises ``FileNotFoundError`` if the path is missing, ``ImportError`` (with an
    install hint) when the ``[audio]`` extra is absent, and the same ``ValueError``
    conditions as :func:`measure_rt60_from_signal`.
    """
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"audio file not found: {path}")
    try:
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(_AUDIO_EXTRA_HINT) from exc

    data, fs = sf.read(str(path), dtype="float64", always_2d=False)
    return measure_rt60_from_signal(data, int(fs), source=str(path), **blind_kwargs)
