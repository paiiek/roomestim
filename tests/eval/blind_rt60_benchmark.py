"""A3 increment 2a — blind-rt60 accuracy benchmark (OUT-OF-GATE, controlled sim).

Quantifies the in-repo-previously-UNVALIDATED accuracy of the `[audio]` measured
RT60 path (:func:`roomestim.reconstruct.measured_rt60.measure_rt60_from_signal`,
which wraps `blind-rt60`) against a CONTROLLED pyroomacoustics simulation whose
RT60 ground truth is the Schroeder integration of the synthesised RIR.

This is a SIMULATION benchmark, NOT a measured-room corpus: the GT is an
idealised image-source RIR (specular, shoebox), so it bounds the blind
ESTIMATOR's decay-fit accuracy under ideal conditions, not the end-to-end
real-room error. A measured-corpus (ACE, CC-BY-ND) benchmark remains deferred.

It also records the load-bearing usage caveat: the Ratnam blind estimator needs a
signal with DECAY events (impulsive claps separated by silence — the recommended
capture). Continuous stationary excitation (steady noise) has no observable decay
tail and the estimate diverges badly; that negative control is reported too.

Run:  python tests/eval/blind_rt60_benchmark.py   (needs [web] pyroomacoustics + [audio] blind-rt60)
Not collected by the default gate (no test_ functions; __main__ entrypoint only).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

FS = 16000
RESULTS_PATH = (
    Path(__file__).resolve().parents[2]
    / ".omc" / "research" / "_data" / "blind_rt60_benchmark_results.md"
)

# (target RT60 s, room dims m) matrix — small/medium/large rooms across the range.
CASES: list[tuple[float, list[float]]] = [
    (0.3, [5.0, 4.0, 3.0]),
    (0.5, [5.0, 4.0, 3.0]),
    (0.7, [8.0, 6.0, 3.5]),
    (1.0, [10.0, 8.0, 4.0]),
    (1.5, [12.0, 10.0, 4.5]),
]


def _impulsive_claps(rir: np.ndarray, n_claps: int = 4, gap_s: float = 0.9) -> np.ndarray:
    """Convolve N short broadband bursts (claps, separated by silence) with the RIR.

    This is the recommended capture: each clap excites the room and decays in the
    following silence, giving the blind estimator the decay tails it models.
    """
    rng = np.random.default_rng(0)
    dur = int((n_claps * gap_s + 1.0) * FS)
    sig = np.zeros(dur)
    burst_len = int(0.02 * FS)
    for k in range(n_claps):
        burst = rng.standard_normal(burst_len)
        p = int(k * gap_s * FS)
        sig[p:p + burst_len] += burst
    return np.convolve(sig, rir)[:dur]


def run() -> dict[str, Any]:
    import pyroomacoustics as pra

    from roomestim.reconstruct.measured_rt60 import measure_rt60_from_signal

    rows: list[dict[str, Any]] = []
    noise_rows: list[dict[str, Any]] = []
    for idx, (target, dims) in enumerate(CASES):
        e_abs, max_order = pra.inverse_sabine(target, dims)
        room = pra.ShoeBox(dims, fs=FS, materials=pra.Material(e_abs), max_order=max_order)
        room.add_source([1.0, 1.0, 1.5])
        room.add_microphone([dims[0] - 2.0, dims[1] - 1.0, 1.5])
        room.compute_rir()
        rir = np.asarray(room.rir[0][0], dtype=np.float64)
        gt = float(pra.experimental.measure_rt60(rir, fs=FS))

        claps = _impulsive_claps(rir)
        est = measure_rt60_from_signal(claps, FS).rt60_s
        rows.append({
            "target": target, "dims": dims, "gt": gt, "est": est,
            "err_s": est - gt, "pct": 100.0 * (est - gt) / gt,
        })

        # negative control (ONE representative case): stationary 2 s noise has no
        # decay tail, so the estimate is expected to diverge badly.
        if idx == 0:
            rng = np.random.default_rng(1)
            rev_noise = np.convolve(rng.standard_normal(FS * 2), rir)[: FS * 2]
            est_noise = measure_rt60_from_signal(rev_noise, FS).rt60_s
            noise_rows.append({"target": target, "gt": gt, "est": est_noise})

    mae = sum(abs(r["err_s"]) for r in rows) / len(rows)
    mape = sum(abs(r["pct"]) for r in rows) / len(rows)
    bias = sum(r["pct"] for r in rows) / len(rows)
    max_abs_pct = max(abs(r["pct"]) for r in rows)
    return {
        "rows": rows, "noise_rows": noise_rows,
        "MAE_ms": mae * 1000.0, "MAPE_pct": mape, "bias_pct": bias,
        "max_abs_pct": max_abs_pct, "n": len(rows),
    }


def _format(res: dict[str, Any]) -> str:
    L = ["# blind-rt60 accuracy benchmark — controlled pyroomacoustics simulation", ""]
    L.append(f"n={res['n']} cases (impulsive-clap excitation). GT = Schroeder RT60 of "
             "the simulated shoebox RIR.")
    L.append("")
    L.append(f"**MAPE = {res['MAPE_pct']:.1f}%**, bias {res['bias_pct']:+.1f}%, "
             f"MAE {res['MAE_ms']:.0f} ms, max |error| {res['max_abs_pct']:.1f}%.")
    L.append("")
    L.append("| target s | room | GT (Schroeder) | blind est | err % |")
    L.append("|---|---|---|---|---|")
    for r in res["rows"]:
        dims = "x".join(str(d) for d in r["dims"])
        L.append(f"| {r['target']} | {dims} | {r['gt']:.3f} | {r['est']:.3f} | {r['pct']:+.1f} |")
    L.append("")
    L.append("## Negative control — stationary noise excitation (no decay tail)")
    L.append("The Ratnam blind estimator needs decay events; continuous noise diverges:")
    L.append("| target s | GT | blind est (noise) |")
    L.append("|---|---|---|")
    for r in res["noise_rows"]:
        L.append(f"| {r['target']} | {r['gt']:.3f} | {r['est']:.1f} |")
    L.append("")
    L.append("## Caveats")
    L.append("- SIMULATION, not a measured corpus: idealised specular shoebox RIR (no air "
             "absorption / diffusion), so this bounds the estimator's decay-fit accuracy, "
             "NOT end-to-end real-room error. Measured-corpus (ACE) validation deferred.")
    L.append("- Accuracy holds ONLY for impulsive excitation (claps + silence); steady "
             "noise fails (see negative control).")
    L.append("- Broadband single value; per-octave-band not assessed.")
    return "\n".join(L)


if __name__ == "__main__":
    res = run()
    report = _format(res)
    print(report)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(report + "\n")
    print(f"\n[written] {RESULTS_PATH}")
