"""A1 — RT60 prediction-engine validation harness (OUT-OF-GATE eval).

Quantitatively compares roomestim's SHIPPED shoebox RT60 predictors against the
MEASURED dEchorate dataset (Di Carlo et al. 2021, CC-BY-4.0) so the README /
disclosure can replace vague "ESTIMATE / demo-grade" wording with a real,
measurement-backed verdict — OR record an explicit honest DEFER.

This module is NOT collected by the default pytest gate (no ``test_`` functions;
``__main__`` entrypoint only). It does not modify the shipped engine. It reads a
tiny committed GT file (tests/eval/data/dechorate_gt.yaml) whose every number is
transcribed-and-cited from the paper / standard absorption tables. NO FAKE
NUMBERS: this script only *computes* predictions and *reports* errors against
that measured GT.

Run:  python tests/eval/rt60_validation.py
Design + go/no-go gate: .omc/research/a1-rt60-validation-harness-design-2026-06-24.md §3.5

Method (ROUTE-RAW): the dEchorate per-facet binary config (reflective/absorbent)
is mapped to literature absorption analogs and fed DIRECTLY to
``image_source_rt60_per_band`` (which takes raw per-surface alpha, bypassing the
material catalog). Sabine/Eyring are reimplemented inline with the SAME 0.161
constant the shipped funcs use, also driven by raw alpha — isolating formula
error from catalog-mapping error. The biggest caveat (recorded in every output)
is the alpha-input gap: dEchorate ships material names, not measured alpha.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from roomestim.reconstruct.image_source import image_source_rt60_per_band

# --- pre-committed go/no-go thresholds (design §3.5; set BEFORE running) -------
GO_MAPE_MAX = 25.0          # %
GO_RHO_MIN = 0.85           # Spearman
GO_DRANGE_LO, GO_DRANGE_HI = 0.5, 2.0   # predicted/measured dynamic-range ratio band
NOGO_MAPE = 40.0            # %
NOGO_RHO = 0.70
JND_PCT = 5.0              # RT60 JND ~5% (ISO 3382-1)

GT_PATH = Path(__file__).parent / "data" / "dechorate_gt.yaml"
RESULTS_PATH = (
    Path(__file__).resolve().parents[2]
    / ".omc" / "research" / "_data" / "rt60_validation_results.md"
)


# --- helpers ------------------------------------------------------------------
def _load_gt() -> dict[str, Any]:
    with GT_PATH.open() as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
        return data


def _alpha_vec(analog: dict[str, Any], scale: float, bands: list[int]) -> dict[int, float]:
    """Scaled, clamped alpha vector for the requested bands (clamp to <1)."""
    return {b: min(0.999, max(0.0, analog["alpha"][b] * scale)) for b in bands}


def _facet_states(code: str) -> list[int]:
    """6-bit string -> list of ints (0=absorbent, 1=reflective), bit0 leftmost."""
    return [int(c) for c in code]


def _build_absorption_per_band(
    gt: dict[str, Any], code: str, bands: list[int],
    abs_scale: float, refl_alpha_floor: float = 0.0,
) -> dict[int, tuple[float, ...]]:
    """Per-band 6-tuple of raw alpha in roomestim LOCKED surface order.

    Surface order: (floor, ceiling, wall_x_neg, wall_x_pos, wall_y_neg, wall_y_pos).
    dEchorate facet order: (floor, ceiling, west, south, east, north).
    surface_index_map in the GT names which facet fills each surface slot.
    abs_scale scales ONLY absorbent/floor analogs (alpha-sensitivity sweep);
    refl_alpha_floor raises reflective-surface alpha to at least this value
    (the reflective analog is the most uncertain input and dominates ISM).
    """
    states = _facet_states(code)
    facet_names = gt["facet_order"]                  # index -> facet name
    state_by_facet = dict(zip(facet_names, states))
    rule = gt["facet_material_rule"]
    analogs = gt["absorption_analogs"]

    per_surface_alpha: list[dict[int, float]] = []
    for surface_facet in gt["surface_index_map"]:
        if surface_facet == "floor":
            kind = "floor"
        elif surface_facet == "ceiling":
            kind = "ceiling"
        else:
            kind = "wall"
        reflective = state_by_facet[surface_facet] == 1
        analog_name = rule[kind]["reflective" if reflective else "absorbent"]
        analog = analogs[analog_name]
        # scale only the absorbing materials; leave hard reflectors at x1.0
        scale = abs_scale if analog["role"] in ("absorbent", "floor") else 1.0
        vec = _alpha_vec(analog, scale, bands)
        if analog["role"] == "reflective" and refl_alpha_floor > 0.0:
            vec = {b: max(vec[b], refl_alpha_floor) for b in bands}
        per_surface_alpha.append(vec)

    return {
        b: tuple(per_surface_alpha[s][b] for s in range(6)) for b in bands
    }


def _sabine_raw(volume: float, areas: tuple[float, ...], alpha: tuple[float, ...]) -> float:
    total = sum(a * al for a, al in zip(areas, alpha))
    return 0.161 * volume / total


def _eyring_raw(volume: float, areas: tuple[float, ...], alpha: tuple[float, ...]) -> float:
    s_total = sum(areas)
    alpha_bar = sum(a * al for a, al in zip(areas, alpha)) / s_total
    return 0.161 * volume / (-s_total * math.log(1.0 - alpha_bar))


def _spearman(xs: list[float], ys: list[float]) -> float:
    """Spearman rho = Pearson on ranks (average ranks for ties)."""
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return num / (dx * dy) if dx and dy else float("nan")


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return num / (dx * dy) if dx and dy else float("nan")


# --- main eval ----------------------------------------------------------------
def run() -> dict[str, Any]:
    gt = _load_gt()
    geom = gt["geometry"]
    L, W, H = geom["length_m"], geom["width_m"], geom["height_m"]
    c = geom["speed_of_sound_m_s"]
    volume = L * W * H
    areas = (L * W, L * W, W * H, W * H, L * H, L * H)  # floor,ceil,xneg,xpos,yneg,ypos
    bands = gt["bands_measured_hz"]

    rows: list[dict[str, Any]] = []          # per (config, band) at center alpha
    pred_all: dict[str, list[float]] = {"image_source": [], "sabine": [], "eyring": []}
    meas_all: list[float] = []

    for cfg in gt["configs"]:
        code = cfg["code"]
        absorption = _build_absorption_per_band(gt, code, bands, abs_scale=1.0)
        ism = image_source_rt60_per_band(volume, (L, W, H), areas, absorption, sound_speed_m_s=c)
        for b in bands:
            meas = cfg["rt60"][b]
            alpha_b = absorption[b]
            preds = {
                "image_source": ism[b],
                "sabine": _sabine_raw(volume, areas, alpha_b),
                "eyring": _eyring_raw(volume, areas, alpha_b),
            }
            for name, p in preds.items():
                pred_all[name].append(p)
                rows.append({
                    "code": code, "band": b, "predictor": name,
                    "measured": meas, "predicted": p,
                    "err_s": p - meas, "pct": 100.0 * (p - meas) / meas,
                    "jnd": abs(100.0 * (p - meas) / meas) <= JND_PCT,
                })
            meas_all.append(meas)

    # aggregate metrics per predictor
    summary: dict[str, Any] = {}
    n_pts = len(meas_all)
    for name in pred_all:
        prs = [r for r in rows if r["predictor"] == name]
        mae = sum(abs(r["err_s"]) for r in prs) / len(prs)
        mape = sum(abs(r["pct"]) for r in prs) / len(prs)
        bias = sum(r["pct"] for r in prs) / len(prs)
        jnd_frac = sum(1 for r in prs if r["jnd"]) / len(prs)
        rho = _spearman(pred_all[name], meas_all)
        r_p = _pearson(pred_all[name], meas_all)
        summary[name] = {
            "MAE_ms": mae * 1000.0, "MAPE_pct": mape, "bias_pct": bias,
            "jnd_frac": jnd_frac, "spearman": rho, "pearson": r_p,
        }

    # monotonicity + dynamic range on the incremental series (image_source, per band)
    series = gt["monotonic_series"]
    series_meas = {b: [next(cf["rt60"][b] for cf in gt["configs"] if cf["code"] == cd)
                       for cd in series] for b in bands}
    series_pred: dict[int, list[float]] = {}
    for cd in series:
        ab = _build_absorption_per_band(gt, cd, bands, 1.0)
        ism = image_source_rt60_per_band(volume, (L, W, H), areas, ab, sound_speed_m_s=c)
        for b in bands:
            series_pred.setdefault(b, []).append(ism[b])

    def _monotonic(seq: list[float]) -> bool:
        return all(seq[i + 1] >= seq[i] - 1e-9 for i in range(len(seq) - 1))

    mono = {b: {"measured": _monotonic(series_meas[b]), "predicted": _monotonic(series_pred[b])}
            for b in bands}
    drange = {b: {"measured": series_meas[b][-1] / series_meas[b][0],
                  "predicted": series_pred[b][-1] / series_pred[b][0]} for b in bands}

    # alpha-sensitivity sweep (image_source MAPE at abs_scale 0.8/1.0/1.2)
    sens: dict[float, float] = {}
    for scale in (0.8, 1.0, 1.2):
        errs = []
        for cfg in gt["configs"]:
            ab = _build_absorption_per_band(gt, cfg["code"], bands, scale)
            ism = image_source_rt60_per_band(volume, (L, W, H), areas, ab, sound_speed_m_s=c)
            for b in bands:
                m = cfg["rt60"][b]
                errs.append(abs(100.0 * (ism[b] - m) / m))
        sens[scale] = sum(errs) / len(errs)
    sens_spread = sens[1.2] - sens[0.8]  # MAPE swing across alpha x[0.8,1.2]

    # reflective-alpha sensitivity: the reflective analog (~0.01) is the single
    # most uncertain input and dominates the ISM. Raise its floor and re-measure
    # image_source MAPE to show how much of the error is the reflective-alpha guess.
    refl_sens: dict[float, float] = {}
    for floor_a in (0.01, 0.03, 0.05, 0.10):
        errs = []
        for cfg in gt["configs"]:
            ab = _build_absorption_per_band(gt, cfg["code"], bands, 1.0, refl_alpha_floor=floor_a)
            ism = image_source_rt60_per_band(volume, (L, W, H), areas, ab, sound_speed_m_s=c)
            for b in bands:
                m = cfg["rt60"][b]
                errs.append(abs(100.0 * (ism[b] - m) / m))
        refl_sens[floor_a] = sum(errs) / len(errs)

    # go/no-go on the BEST shipped predictor = image_source
    best = summary["image_source"]
    median_dr_ratio = sorted(drange[b]["predicted"] / drange[b]["measured"] for b in bands)[len(bands) // 2]
    mono_ok = all(mono[b]["predicted"] == mono[b]["measured"] for b in bands)
    dr_ok = GO_DRANGE_LO <= median_dr_ratio <= GO_DRANGE_HI
    formula_dominates = sens_spread < best["MAPE_pct"]

    go = (best["MAPE_pct"] <= GO_MAPE_MAX and best["spearman"] >= GO_RHO_MIN
          and mono_ok and dr_ok and formula_dominates)
    nogo = (best["MAPE_pct"] > NOGO_MAPE or best["spearman"] < NOGO_RHO
            or sens_spread >= best["MAPE_pct"])
    verdict = "GO" if go else ("NO-GO" if nogo else "GREY")

    return {
        "n_points": n_pts, "bands": bands, "summary": summary, "rows": rows,
        "monotonicity": mono, "dynamic_range": drange,
        "alpha_sensitivity_MAPE": sens, "alpha_sens_spread_pct": sens_spread,
        "reflective_alpha_sensitivity_MAPE": refl_sens,
        "median_dynamic_range_ratio": median_dr_ratio,
        "verdict": verdict, "go": go, "nogo": nogo,
    }


def _format_report(res: dict[str, Any]) -> str:
    L = []
    L.append("# A1 RT60 validation — dEchorate measured GT (image-source ROUTE-RAW)")
    L.append("")
    L.append(f"VERDICT: **{res['verdict']}**  (n={res['n_points']} config×band points, "
             f"bands={res['bands']} Hz)")
    L.append("")
    L.append("## Aggregate metrics (raw-alpha ROUTE-RAW)")
    L.append("| predictor | MAPE % | MAE ms | bias % | within-JND | Spearman ρ | Pearson r |")
    L.append("|---|---|---|---|---|---|---|")
    for name, s in res["summary"].items():
        L.append(f"| {name} | {s['MAPE_pct']:.1f} | {s['MAE_ms']:.0f} | {s['bias_pct']:+.1f} "
                 f"| {s['jnd_frac']*100:.0f}% | {s['spearman']:.3f} | {s['pearson']:.3f} |")
    L.append("")
    L.append("## Monotonicity & dynamic range (incremental series, image-source)")
    L.append("| band Hz | mono meas | mono pred | DR meas | DR pred |")
    L.append("|---|---|---|---|---|")
    for b in res["bands"]:
        m, d = res["monotonicity"][b], res["dynamic_range"][b]
        L.append(f"| {b} | {m['measured']} | {m['predicted']} | "
                 f"{d['measured']:.2f}× | {d['predicted']:.2f}× |")
    L.append(f"\nmedian predicted/measured dynamic-range ratio = {res['median_dynamic_range_ratio']:.2f}")
    L.append("")
    L.append("## Alpha-input sensitivity (image-source MAPE vs absorbent-alpha scale)")
    for sc, mp in res["alpha_sensitivity_MAPE"].items():
        L.append(f"- α×{sc}: MAPE {mp:.1f}%")
    L.append(f"- spread (α×1.2 − α×0.8) = {res['alpha_sens_spread_pct']:.1f} pct-points")
    L.append("")
    L.append("## Reflective-alpha sensitivity (image-source MAPE vs reflective-α floor)")
    L.append("The reflective analog (Formica→marble ≈0.01) is the most uncertain input; "
             "raising its floor collapses the ISM over-prediction:")
    for fa, mp in res["reflective_alpha_sensitivity_MAPE"].items():
        L.append(f"- reflective α≥{fa}: MAPE {mp:.1f}%")
    L.append("")
    L.append("## Caveats (load-bearing)")
    L.append("- dEchorate ships material NAMES, not per-band alpha → absorption is literature "
             "ANALOG; predicted RT60 carries alpha-input uncertainty confounded with formula error.")
    L.append("- Table 5 reports only 500/1000/2000/4000 Hz (no 125/250 Hz) → 4-band validation.")
    L.append("- image_source uses a fixed single src/recv diagonal pair; measured RT60 is a "
             "spatial median → a few-% model-form difference expected.")
    L.append("- Shoebox-only regime. Non-shoebox (polygon) RT60 remains separately DEFERRED.")
    return "\n".join(L)


if __name__ == "__main__":
    res = run()
    report = _format_report(res)
    print(report)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(report + "\n")
    print(f"\n[written] {RESULTS_PATH}")
