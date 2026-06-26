"""Tests for the `measure-rt60` CLI subcommand (ADR 0055, A3 increment 2a).

Skip-guarded via importorskip — they run where the `audio` extra is installed
and skip otherwise (matching the usd/vision/audio extra convention). They lock
the CLI WRAPPER plumbing + honesty (exit codes, stdout/stderr surfaces, JSON
shape), NOT blind-estimator accuracy (no ground truth in repo; ACE-corpus
benchmark deferred), so there are deliberately NO accuracy assertions.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

pytest.importorskip("blind_rt60")
pytest.importorskip("soundfile")

from roomestim.cli import main


def _synth_decay(rt60_s: float = 0.5, fs: int = 16000, dur_s: float = 3.0) -> np.ndarray:
    """White noise with an exponential energy decay of the requested RT60."""
    n = int(fs * dur_s)
    t = np.arange(n) / fs
    rng = np.random.default_rng(0)
    tau = rt60_s / 6.907755  # -60 dB == exp(-t/tau) reaching 1e-3 amplitude
    return rng.standard_normal(n) * np.exp(-t / tau)


def _write_wav(tmp_path) -> str:  # type: ignore[no-untyped-def]
    import soundfile as sf

    p = tmp_path / "clap.wav"
    sf.write(str(p), _synth_decay(0.5), 16000)
    return str(p)


def test_cli_human_output(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    wav = _write_wav(tmp_path)
    rc = main(["measure-rt60", "--audio", wav])
    assert rc == 0
    out = capsys.readouterr()
    assert "RT60" in out.out
    assert wav in out.out
    # honesty NOTE goes to stderr
    assert "NOTE:" in out.err


def test_cli_json_output(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    wav = _write_wav(tmp_path)
    rc = main(["measure-rt60", "--audio", wav, "--json"])
    assert rc == 0
    out = capsys.readouterr()
    payload = json.loads(out.out)
    # lock the full payload shape (the JSON contract downstream may consume)
    assert set(payload) == {
        "rt60_s", "sample_rate_hz", "n_samples", "source", "method", "note",
    }
    assert payload["rt60_s"] > 0
    assert payload["source"] == wav
    assert payload["sample_rate_hz"] == 16000
    assert "blind-rt60" in payload["method"]


def test_cli_missing_file_exits_1(capsys) -> None:  # type: ignore[no-untyped-def]
    rc = main(["measure-rt60", "--audio", "/no/such/file.wav"])
    assert rc == 1
    out = capsys.readouterr()
    assert "error:" in out.err
