"""Blocker-(C) de-risk study — is RT60-from-decay-fit reliable on a SPARSE
first-order-only ISM RIR? (OUT-OF-GATE eval; NO external data, NO fake numbers.)

ADR 0040 (polygon-ISM RT60) records three blockers that keep the non-shoebox
RT60 cascade DEFERRED. Blocker (C) is the only one that needs ZERO external
data: pyroomacoustics' RT60-from-energy-decay fit (Schroeder integration via
``pyroomacoustics.experimental.rt60.measure_rt60``) has UNVERIFIED reliability
when fed a SPARSE first-order-image-source-only RIR (the kind
``polygon_image_source.first_order_image_sources`` would produce — direct path
+ one bounce per surface only).

This harness quantifies that reliability on SYNTHETIC shoebox rooms where the
ground truth is the ANALYTIC Sabine/Eyring RT60 formula (legitimate GT: a closed-
form physics formula, not an invented measurement). Method:

  1. For a sweep of room sizes x absorptions, generate the pyroomacoustics
     shoebox RIR at FIRST order (max_order=1, the sparse case the polygon
     enumerator mimics) and at HIGH order (max_order=DENSE_ORDER, a dense tail).
  2. Fit RT60 from each RIR via measure_rt60 (RT20 + RT30 extrapolation).
  3. Report the bias/error of the SPARSE (first-order) fit relative to BOTH the
     dense fit AND the analytic Sabine/Eyring RT60.

The point is NOT to validate pyroomacoustics' acoustics (the analytic formula is
the reference) — it is to answer: does a first-order-only ISM RIR carry enough
decay information for a trustworthy RT60 fit, or not? A clear answer de-risks (or
KILLS) blocker (C) without any external dataset.

This module is NOT collected by the default pytest gate (no ``test_`` functions;
``__main__`` entrypoint only). It modifies no shipped code. REQUIRES
pyroomacoustics (a web/optional extra) — if unavailable it exits with a clear
message and the DEFER doc records the study as pending.

Run:  python tests/eval/sparse_ism_rt60_fit_study.py
"""

from __future__ import annotations

import math
import statistics
import sys
from typing import Any

# --- pre-committed go/no-go thresholds (set BEFORE running) -------------------
# Blocker (C) is de-risked (GO = first-order RIR carries trustworthy decay info)
# only if BOTH hold on the median across the sweep:
GO_SPARSE_VS_ANALYTIC_MAX = 20.0   # median |sparse_fit - analytic| / analytic  (%)
GO_SPARSE_VS_DENSE_MAX = 20.0      # median |sparse_fit - dense_fit| / dense_fit (%)
# Blocker (C) is CONFIRMED (NO-GO = sparse fit is unreliable, cascade stays
# blocked on (C)) if EITHER median error is this large, OR the sparse fit fails
# to produce a finite RT60 on a large fraction of rooms:
NOGO_SPARSE_ERR = 35.0             # % median error (either reference)
NOGO_FAIL_FRAC = 0.25              # fraction of rooms with non-finite sparse fit
# Sanity floor: the DENSE fit must itself track the analytic GT, else the
# measurement method is the problem, not sparsity (study is then inconclusive):
DENSE_SANITY_MAX = 25.0            # median |dense_fit - analytic| / analytic (%)

FS = 16000                         # Hz; RIR sampling rate
DENSE_ORDER_CAP = 110              # safety cap on the calibrated dense max_order

# Sweep: shoebox dims (m) x target RT60 (s). The dense reflection order is NOT a
# fixed constant: a pure-ISM RIR only spans ~max_order bounces of path length, so
# a long RT60 needs a high order to capture the full -30 dB decay (e.g. RT60=1.0 s
# needs max_order~137 per inverse_sabine). We therefore CALIBRATE the dense order
# per room from the target RT60 via pyroomacoustics' own inverse_sabine, which
# also fixes the uniform energy-absorption alpha — so the analytic Sabine RT60 of
# that alpha equals the target by construction (a clean, consistent GT). Targets
# stay moderate so the calibrated order stays tractable.
ROOMS = [
    (4.0, 3.0, 2.7),
    (6.0, 4.5, 3.0),
    (8.0, 6.0, 3.2),
    (10.0, 7.0, 3.5),
    (5.0, 5.0, 2.8),
]
RT60_TARGETS = [0.3, 0.5, 0.7]


def _analytic_rt60(dims: tuple[float, float, float], alpha: float) -> tuple[float, float]:
    """Analytic Sabine & Eyring RT60 for a uniform-alpha shoebox (the GT)."""
    lx, ly, lz = dims
    volume = lx * ly * lz
    s_total = 2.0 * (lx * ly + ly * lz + lx * lz)
    sabine = 0.161 * volume / (s_total * alpha)
    eyring = 0.161 * volume / (-s_total * math.log(1.0 - alpha))
    return sabine, eyring


def _fit_rt60(rir: Any, fs: int) -> dict[str, float]:
    """Fit RT60 from an RIR via RT20 and RT30 extrapolation (measure_rt60)."""
    from pyroomacoustics.experimental.rt60 import measure_rt60

    out: dict[str, float] = {}
    for tag, decay in (("rt20", 20), ("rt30", 30)):
        try:
            val = float(measure_rt60(rir, fs=fs, decay_db=decay))
        except Exception:  # noqa: BLE001 - a failed fit is a real data point
            val = float("nan")
        out[tag] = val
    return out


def _make_rir(dims: tuple[float, float, float], alpha: float, max_order: int) -> Any:
    """Build a pyroomacoustics shoebox RIR at the given reflection order."""
    import numpy as np
    import pyroomacoustics as pra

    room = pra.ShoeBox(
        list(dims), fs=FS, materials=pra.Material(alpha), max_order=max_order
    )
    # source + mic on the room diagonal, away from walls/symmetry planes
    lx, ly, lz = dims
    src = np.array([lx * 0.35, ly * 0.35, lz * 0.45])
    mic = np.array([lx * 0.62, ly * 0.68, lz * 0.55])
    room.add_source(src.tolist())
    room.add_microphone(mic.reshape(3, 1))
    room.compute_rir()
    return room.rir[0][0]


def run() -> dict[str, Any]:
    import pyroomacoustics as pra

    rows: list[dict[str, Any]] = []
    for dims in ROOMS:
        for rt60_tgt in RT60_TARGETS:
            # inverse_sabine fixes alpha (so analytic Sabine == target) AND the
            # max_order needed to capture the full decay (the dense control).
            alpha, dense_order = pra.inverse_sabine(rt60_tgt, list(dims))
            dense_order = min(int(dense_order), DENSE_ORDER_CAP)
            sabine, eyring = _analytic_rt60(dims, alpha)
            sparse_rir = _make_rir(dims, alpha, max_order=1)
            dense_rir = _make_rir(dims, alpha, max_order=dense_order)
            sparse = _fit_rt60(sparse_rir, FS)
            dense = _fit_rt60(dense_rir, FS)
            # Primary metric = the RT60 ESTIMATE from the 30 dB-slope method
            # (RT30 window extrapolated to a 60 dB decay), the standard. The
            # "rt30"/"rt20" tags name the decay WINDOW; the stored value is an
            # RT60 estimate (hence the *_rt60_est* key names).
            rows.append({
                "dims": dims, "alpha": alpha, "rt60_tgt": rt60_tgt,
                "dense_order": dense_order,
                "sabine": sabine, "eyring": eyring,
                "sparse_rt60_est": sparse["rt30"], "sparse_rt60_est_20db": sparse["rt20"],
                "dense_rt60_est": dense["rt30"], "dense_rt60_est_20db": dense["rt20"],
                "n_sparse_taps": int((abs(sparse_rir) > 1e-9).sum()),
                "n_dense_taps": int((abs(dense_rir) > 1e-9).sum()),
            })
    return {"rows": rows}


def _pct_err(a: float, ref: float) -> float:
    if not (math.isfinite(a) and math.isfinite(ref)) or ref == 0:
        return float("nan")
    return 100.0 * abs(a - ref) / ref


def _median_finite(vals: list[float]) -> float:
    fin = [v for v in vals if math.isfinite(v)]
    return statistics.median(fin) if fin else float("nan")


def analyze(res: dict[str, Any]) -> dict[str, Any]:
    rows = res["rows"]
    n = len(rows)
    # Reference = analytic SABINE: pyroomacoustics' inverse_sabine + ShoeBox use
    # the Sabine energy-absorption model, and the dense ISM fit empirically lands
    # on Sabine (verified: dense RT30 ~ sabine to a few %). Eyring runs ~15-20%
    # below Sabine here; it is reported per-room but is the wrong analytic anchor
    # for this simulator. The conclusion (sparse fit collapses) is reference-robust.
    sparse_vs_analytic = [_pct_err(r["sparse_rt60_est"], r["sabine"]) for r in rows]
    sparse_vs_dense = [_pct_err(r["sparse_rt60_est"], r["dense_rt60_est"]) for r in rows]
    dense_vs_analytic = [_pct_err(r["dense_rt60_est"], r["sabine"]) for r in rows]

    n_sparse_fail = sum(1 for r in rows if not math.isfinite(r["sparse_rt60_est"]))
    fail_frac = n_sparse_fail / n if n else 1.0

    med_sva = _median_finite(sparse_vs_analytic)
    med_svd = _median_finite(sparse_vs_dense)
    med_dva = _median_finite(dense_vs_analytic)

    # signed median bias of the sparse fit (does first-order over- or under-shoot?)
    signed_sva = _median_finite([
        100.0 * (r["sparse_rt60_est"] - r["sabine"]) / r["sabine"]
        for r in rows if math.isfinite(r["sparse_rt60_est"])
    ])

    dense_sane = math.isfinite(med_dva) and med_dva <= DENSE_SANITY_MAX
    go = (
        dense_sane
        and fail_frac < NOGO_FAIL_FRAC
        and math.isfinite(med_sva) and med_sva <= GO_SPARSE_VS_ANALYTIC_MAX
        and math.isfinite(med_svd) and med_svd <= GO_SPARSE_VS_DENSE_MAX
    )
    nogo = (
        (math.isfinite(med_sva) and med_sva >= NOGO_SPARSE_ERR)
        or (math.isfinite(med_svd) and med_svd >= NOGO_SPARSE_ERR)
        or fail_frac >= NOGO_FAIL_FRAC
    )
    if not dense_sane:
        verdict = "INCONCLUSIVE (dense fit does not track analytic GT)"
    elif go:
        verdict = "GO (first-order RIR carries trustworthy decay info)"
    elif nogo:
        verdict = "NO-GO (blocker C confirmed: sparse fit unreliable)"
    else:
        verdict = "GREY"

    return {
        "n_rooms": n,
        "median_sparse_vs_analytic_pct": med_sva,
        "median_sparse_vs_dense_pct": med_svd,
        "median_dense_vs_analytic_pct": med_dva,
        "signed_median_sparse_bias_pct": signed_sva,
        "sparse_fail_frac": fail_frac,
        "n_sparse_fail": n_sparse_fail,
        "dense_sane": dense_sane,
        "go": go, "nogo": nogo, "verdict": verdict,
    }


def _format(res: dict[str, Any], agg: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("# Sparse first-order ISM RT60-fit reliability study (ADR 0040 blocker C)")
    L.append("")
    L.append(f"VERDICT: **{agg['verdict']}**")
    L.append("")
    L.append(f"- rooms swept: {agg['n_rooms']}  (max_order: sparse=1, dense=inverse_sabine-"
             f"calibrated, cap={DENSE_ORDER_CAP}; fs={FS} Hz)")
    L.append(f"- GT reference: analytic Sabine RT60 (closed form; the model this "
             f"simulator is calibrated to — dense ISM fit lands on it)")
    L.append("")
    L.append("## Pre-committed thresholds")
    L.append(f"- GO if median(|sparse-analytic|/analytic) <= {GO_SPARSE_VS_ANALYTIC_MAX:.0f}% "
             f"AND median(|sparse-dense|/dense) <= {GO_SPARSE_VS_DENSE_MAX:.0f}% "
             f"AND dense fit sane.")
    L.append(f"- NO-GO if either median >= {NOGO_SPARSE_ERR:.0f}% OR sparse non-finite frac "
             f">= {NOGO_FAIL_FRAC*100:.0f}%.")
    L.append(f"- dense sanity: median(|dense-analytic|/analytic) <= {DENSE_SANITY_MAX:.0f}%.")
    L.append("")
    L.append("## Aggregate results (RT60 estimate via the RT30-slope method)")
    L.append(f"- median |sparse - analytic| / analytic = **{agg['median_sparse_vs_analytic_pct']:.1f}%**")
    L.append(f"- median |sparse - dense|    / dense    = **{agg['median_sparse_vs_dense_pct']:.1f}%**")
    L.append(f"- median |dense  - analytic| / analytic = {agg['median_dense_vs_analytic_pct']:.1f}%  "
             f"(sanity, dense_sane={agg['dense_sane']})")
    L.append(f"- signed median sparse bias            = {agg['signed_median_sparse_bias_pct']:+.1f}%")
    L.append(f"- sparse non-finite fits               = {agg['n_sparse_fail']}/{agg['n_rooms']} "
             f"({agg['sparse_fail_frac']*100:.0f}%)")
    L.append("")
    L.append("## Per-room detail")
    L.append("| dims (m) | rt60_tgt | alpha | dense_ord | eyring s | sabine s | "
             "sparse RT60est | dense RT60est | sparse taps | dense taps |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in res["rows"]:
        d = "x".join(f"{v:g}" for v in r["dims"])
        def _f(v: float) -> str:
            return f"{v:.2f}" if math.isfinite(v) else "nan"
        L.append(f"| {d} | {r['rt60_tgt']:.1f} | {r['alpha']:.3f} | {r['dense_order']} | "
                 f"{r['eyring']:.2f} | {r['sabine']:.2f} | "
                 f"{_f(r['sparse_rt60_est'])} | {_f(r['dense_rt60_est'])} | "
                 f"{r['n_sparse_taps']} | {r['n_dense_taps']} |")
    L.append("")
    L.append("## Interpretation")
    L.append("A first-order-only ISM RIR (direct + one bounce per surface) has very few taps "
             "and essentially no late reverberant tail. RT60-from-Schroeder fitting needs a "
             "sustained exponential energy decay; if the sparse fit deviates far from BOTH the "
             "analytic GT and the dense fit, blocker (C) is real and the polygon-ISM RT60 "
             "cascade cannot rest on a first-order RIR. This study uses synthetic shoeboxes only "
             "(analytic GT); it is NOT a measured-room accuracy claim and does NOT lift the other "
             "two blockers (no non-shoebox measured RT60 GT; material-confound).")
    return "\n".join(L)


if __name__ == "__main__":
    try:
        import pyroomacoustics  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        print(f"SKIP: pyroomacoustics unavailable ({exc!r}). "
              "Blocker-C study is recorded as pending in ADR 0040.")
        sys.exit(0)

    res = run()
    agg = analyze(res)
    print(_format(res, agg))
