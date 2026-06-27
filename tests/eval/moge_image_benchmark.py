"""MoGe metric single-image backend — honest accuracy benchmark (OUT-OF-GATE).

Scores the MoGe backend (:class:`roomestim.adapters.moge.MoGeAdapter`) against
the HorizonNet ``[vision]`` baseline (:class:`roomestim.adapters.image.ImageAdapter`)
on the PanoContext / Stanford2D3D pano set, using the IDENTICAL scorer for GT,
MoGe and HorizonNet so the comparison is apples-to-apples.

Ground truth (HONEST LIMITS, recorded in the results file):
  * GT is the LayoutNet ``label_cor`` corner annotation — 100% CUBOID, so ONLY
    cuboid accuracy can be measured.
  * GT metric scale is DERIVED from a NOMINAL camera height (1.6 m office-class
    ``camera_*`` Stanford2D3D, 1.4 m residential ``pano_*`` PanoContext), so the
    absolute-metric comparison is itself anchored to an assumed cam_h. A metric
    MoGe that disagrees is NOT necessarily wrong — a SCALE-INVARIANT shape error
    (global per-room scale removed) is reported alongside the absolute error.

Metrics (match the existing baseline): per-DIM error (sorted dims, azimuth-
invariant) median + per-room both-dims <=15 cm rate, per room class. MoGe is
scored with BOTH the ``convex`` and ``robust`` footprint extractors (from the
SAME fused cloud — MoGe runs once per pano). Per-crop metric-scale dispersion
(CV) is reported as the honesty metric.

Run (spike-vggt venv, GPU):
    ROOMESTIM_HORIZONNET_CKPT=/home/seung/mmhoa/spike-image-geometry/ckpt/resnet50_rnn__st3d.pth \
    PYTHONPATH=/home/seung/mmhoa/roomestim \
    /home/seung/mmhoa/spike-vggt-multiview/venv/bin/python tests/eval/moge_image_benchmark.py [N]

Not collected by the default gate (no ``test_`` functions; ``__main__`` only).
"""

from __future__ import annotations

import math
import os
import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np

DATA_ROOT = Path(
    "/home/seung/mmhoa/spike-image-geometry/panocontext_data/pano_s2d3d"
)
DEFAULT_CKPT = Path(
    "/home/seung/mmhoa/spike-image-geometry/ckpt/resnet50_rnn__st3d.pth"
)
RESULTS_PATH = (
    Path(__file__).resolve().parents[2]
    / ".omc" / "research" / "_data" / "moge_image_benchmark_results.md"
)
PANO_W, PANO_H = 1024, 512
LE15_M = 0.15  # <=15 cm per-room success threshold

# Nominal camera height per room class (matches the prior HorizonNet eval):
# Stanford2D3D office-class panos are named ``camera_*``; PanoContext
# residential panos are named ``pano_*``.
NOMINAL_CAM_H = {"office": 1.6, "residential": 1.4}


def _room_class(name: str) -> str:
    return "office" if name.startswith("camera_") else "residential"


def _gt_dims(label_path: Path, cam_h: float) -> tuple[list[float], float] | None:
    """LayoutNet ``label_cor`` corners -> (sorted floor dims [m], ceiling [m]).

    Same corner->metric projection roomestim's image core uses
    (``r = cam_h / tan(-v_floor)``), with the nominal class camera height.
    """
    cor = np.loadtxt(label_path)
    if cor.ndim != 2 or cor.shape[0] < 6 or cor.shape[0] % 2 != 0:
        return None
    ceil_pts = cor[0::2]
    floor_pts = cor[1::2]
    xs: list[float] = []
    zs: list[float] = []
    hts: list[float] = []
    for (uc, vc), (uf, vf) in zip(ceil_pts, floor_pts):
        u = ((uf + 0.5) / PANO_W - 0.5) * 2.0 * math.pi
        v_floor = -((vf + 0.5) / PANO_H - 0.5) * math.pi
        v_ceil = -((vc + 0.5) / PANO_H - 0.5) * math.pi
        tan_floor = math.tan(-v_floor)
        if tan_floor <= 1e-6:
            continue
        r = cam_h / tan_floor
        xs.append(r * math.sin(u))
        zs.append(-r * math.cos(u))
        hts.append(cam_h + r * math.tan(v_ceil))
    if len(xs) < 3:
        return None
    w = max(xs) - min(xs)
    d = max(zs) - min(zs)
    return sorted([float(w), float(d)]), float(np.median(hts))


def _bbox_dims(floor_polygon: Any) -> list[float]:
    xs = [p.x for p in floor_polygon]
    zs = [p.z for p in floor_polygon]
    return sorted([max(xs) - min(xs), max(zs) - min(zs)])


def _scale_invariant_err(est: list[float], gt: list[float]) -> list[float]:
    """Per-dim error after removing the optimal global scale (shape-only)."""
    e = np.asarray(est)
    g = np.asarray(gt)
    denom = float((e * e).sum())
    s = float((e * g).sum() / denom) if denom > 0 else 1.0
    return [abs(float(s * e[i] - g[i])) for i in range(len(est))]


def _collect_panos(n_target: int) -> list[tuple[Path, Path, str]]:
    """Balanced, deterministic sample of (img, label, class) across all splits."""
    office: list[tuple[Path, Path, str]] = []
    resid: list[tuple[Path, Path, str]] = []
    for split in ("train", "valid", "test"):
        img_dir = DATA_ROOT / split / "img"
        lbl_dir = DATA_ROOT / split / "label_cor"
        if not img_dir.is_dir():
            continue
        for img in sorted(img_dir.glob("*.png")):
            lbl = lbl_dir / (img.stem + ".txt")
            if not lbl.exists():
                continue
            cls = _room_class(img.stem)
            (office if cls == "office" else resid).append((img, lbl, cls))
    rng = np.random.default_rng(0)
    half = n_target // 2

    def _sample(pool: list[tuple[Path, Path, str]], k: int) -> list[Any]:
        if len(pool) <= k:
            return pool
        idx = rng.choice(len(pool), size=k, replace=False)
        return [pool[i] for i in sorted(idx)]

    return _sample(office, half) + _sample(resid, n_target - half)


def run(n_target: int) -> dict[str, Any]:
    from PIL import Image

    from roomestim.adapters.base import ScaleAnchor
    from roomestim.adapters.image import ImageAdapter
    from roomestim.adapters.mesh import MeshAdapter
    from roomestim.adapters.moge import MoGeAdapter

    if "ROOMESTIM_HORIZONNET_CKPT" not in os.environ and DEFAULT_CKPT.exists():
        os.environ["ROOMESTIM_HORIZONNET_CKPT"] = str(DEFAULT_CKPT)

    # Eval-only speedup (does NOT change results): ImageAdapter reloads the
    # 326 MB HorizonNet checkpoint on EVERY parse() (the per-pano bottleneck).
    # Memoise the load — the net is identical and used read-only (eval/no_grad),
    # so the forward pass + scorer are byte-for-byte unchanged. image.py imports
    # this name lazily inside _infer_corners, so patching the module attribute is
    # picked up at call time.
    import roomestim.vision.horizonnet.misc.utils as _hutils

    _orig_load = _hutils.load_trained_model
    _net_cache: dict[str, Any] = {}

    def _cached_load(net_cls: Any, path: str, *a: Any, **k: Any) -> Any:
        if path not in _net_cache:
            _net_cache[path] = _orig_load(net_cls, path, *a, **k)
        return _net_cache[path]

    _hutils.load_trained_model = _cached_load

    panos = _collect_panos(n_target)
    moge = MoGeAdapter()  # model cached across panos
    image = ImageAdapter()

    rows: list[dict[str, Any]] = []
    for img, lbl, cls in panos:
        cam_h = NOMINAL_CAM_H[cls]
        gt = _gt_dims(lbl, cam_h)
        if gt is None:
            continue
        gt_dims, gt_ceil = gt
        row: dict[str, Any] = {"stem": img.stem, "cls": cls, "gt_dims": gt_dims,
                               "gt_ceil": gt_ceil}

        # MoGe once -> shared fused cloud -> convex + robust footprints.
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pano = np.asarray(Image.open(img).convert("RGB"))
                cloud = moge._reconstruct_cloud(pano, is_pano=True)
                row["scale_cv"] = moge.last_diagnostics.get("scale_cv")
                for mode in ("convex", "robust"):
                    mesh = MeshAdapter(floor_reconstruction=mode, up_axis="y")
                    rm = mesh._extract_room_model(cloud, name=img.stem,
                                                  up_axis_hint="y")
                    row[f"moge_{mode}"] = _bbox_dims(rm.floor_polygon)
                    row[f"moge_{mode}_ceil"] = float(rm.ceiling_height_m)
        except Exception as exc:  # noqa: BLE001 - record failures honestly
            row["moge_error"] = repr(exc)

        # HorizonNet baseline via roomestim's own vendored path (same scorer).
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                rh = image.parse(img, scale_anchor=ScaleAnchor("known_distance", cam_h))
            row["hnet"] = _bbox_dims(rh.floor_polygon)
            row["hnet_ceil"] = float(rh.ceiling_height_m)
        except Exception as exc:  # noqa: BLE001
            row["hnet_error"] = repr(exc)

        rows.append(row)
    return {"rows": rows, "n": len(rows)}


def _summarize(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    """Per-class + overall stats for a method key (e.g. 'moge_robust', 'hnet')."""
    out: dict[str, Any] = {}
    for cls in ("office", "residential", "all"):
        sel = [r for r in rows if (cls == "all" or r["cls"] == cls) and key in r]
        if not sel:
            out[cls] = None
            continue
        dim_errs: list[float] = []
        n_le15 = 0
        for r in sel:
            est, gt = r[key], r["gt_dims"]
            e = [abs(est[i] - gt[i]) for i in range(2)]
            dim_errs.extend(e)
            if max(e) <= LE15_M:
                n_le15 += 1
        out[cls] = {
            "n": len(sel),
            "median_dim_cm": float(np.median(dim_errs)) * 100.0,
            "pct_le15": 100.0 * n_le15 / len(sel),
        }
    return out


def _summarize_shape(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Scale-invariant (shape-only) per-class median dim error for a MoGe key."""
    out: dict[str, Any] = {}
    for cls in ("office", "residential", "all"):
        sel = [r for r in rows if (cls == "all" or r["cls"] == cls) and key in r]
        if not sel:
            out[cls] = None
            continue
        errs: list[float] = []
        for r in sel:
            errs.extend(_scale_invariant_err(r[key], r["gt_dims"]))
        out[cls] = {"n": len(sel), "median_shape_cm": float(np.median(errs)) * 100.0}
    return out


def _ceil_median_cm(rows: list[dict[str, Any]], key: str) -> float | None:
    errs = [abs(r[key] - r["gt_ceil"]) for r in rows if key in r]
    return float(np.median(errs)) * 100.0 if errs else None


def _fmt_method(label: str, s: dict[str, Any] | None) -> list[str]:
    if s is None:
        return [f"| {label} | — | — | — | — | — | — |"]
    def cell(c: str, k: str) -> str:
        return f"{s[c][k]:.1f}" if s.get(c) else "—"
    return [
        f"| {label} "
        f"| {cell('office','median_dim_cm')} | {cell('office','pct_le15')} "
        f"| {cell('residential','median_dim_cm')} | {cell('residential','pct_le15')} "
        f"| {cell('all','median_dim_cm')} | {cell('all','pct_le15')} |"
    ]


def _format(res: dict[str, Any]) -> str:
    rows = res["rows"]
    moge_c = _summarize(rows, "moge_convex")
    moge_r = _summarize(rows, "moge_robust")
    hnet = _summarize(rows, "hnet")
    n_off = sum(1 for r in rows if r["cls"] == "office")
    n_res = sum(1 for r in rows if r["cls"] == "residential")
    cvs = [r["scale_cv"] for r in rows if r.get("scale_cv") is not None
           and math.isfinite(r["scale_cv"])]
    moge_fail = sum(1 for r in rows if "moge_error" in r)
    hnet_fail = sum(1 for r in rows if "hnet_error" in r)

    L = ["# MoGe metric single-image backend — accuracy benchmark", ""]
    L.append(f"n = {res['n']} panos ({n_off} office-class `camera_*` Stanford2D3D, "
             f"{n_res} residential `pano_*` PanoContext), sampled deterministically "
             "across train/valid/test.")
    L.append("")
    L.append("GT = LayoutNet `label_cor` corners (100% CUBOID) projected to metric "
             "with a NOMINAL camera height (1.6 m office / 1.4 m residential). "
             "Per-DIM error = |sorted-dim - GT| (azimuth-invariant); per-room = both "
             "dims <=15 cm. HorizonNet baseline run through roomestim's OWN "
             "`ImageAdapter` (vendored, same scorer).")
    L.append("")
    L.append("## Per-DIM median error (cm) + per-room <=15 cm rate (%)")
    L.append("")
    L.append("| method | office med cm | office <=15% | resid med cm | resid <=15% "
             "| all med cm | all <=15% |")
    L.append("|---|---|---|---|---|---|---|")
    L += _fmt_method("HorizonNet (baseline)", hnet)
    L += _fmt_method("MoGe convex", moge_c)
    L += _fmt_method("MoGe robust", moge_r)
    L.append("")

    # Scale-invariant (shape-only) MoGe error.
    sc = _summarize_shape(rows, "moge_convex")
    sr = _summarize_shape(rows, "moge_robust")
    L.append("## MoGe scale-invariant (shape-only) median per-DIM error (cm)")
    L.append("Global per-room scale removed, isolating SHAPE from the cam_h-derived "
             "GT metric scale (the absolute metric caveat).")
    L.append("")
    L.append("| method | office | resid | all |")
    L.append("|---|---|---|---|")
    for lbl, s in (("MoGe convex", sc), ("MoGe robust", sr)):
        def c(k: str, s: dict[str, Any] = s) -> str:
            return f"{s[k]['median_shape_cm']:.1f}" if s.get(k) else "—"
        L.append(f"| {lbl} | {c('office')} | {c('residential')} | {c('all')} |")
    L.append("")

    L.append("## Ceiling height median error (cm)")
    L.append(f"- HorizonNet: {_ceil_median_cm(rows, 'hnet_ceil')!r}")
    L.append(f"- MoGe (convex/robust share the cloud, same ceiling): "
             f"{_ceil_median_cm(rows, 'moge_convex_ceil')!r}")
    L.append("")

    L.append("## Honesty metrics")
    if cvs:
        L.append(f"- Per-crop metric-scale dispersion CV: median {np.median(cvs):.1%}, "
                 f"p90 {np.percentile(cvs, 90):.1%}, max {max(cvs):.1%} (n={len(cvs)}). "
                 "High dispersion => MoGe's per-crop metric scale drifts across the "
                 "fused crops.")
    L.append(f"- MoGe failures: {moge_fail}; HorizonNet failures: {hnet_fail} "
             "(counted, excluded from medians).")
    L.append("")
    L.append("## Caveats (load-bearing)")
    L.append("- CUBOID-ONLY GT: the benchmark can only measure cuboid accuracy; "
             "non-shoebox generalisation is NOT tested.")
    L.append("- GT metric scale is cam_h-derived: the absolute per-DIM comparison "
             "penalises a metric MoGe that disagrees with the assumed-cam_h GT scale; "
             "see the scale-invariant shape error.")
    L.append("- MoGe sees TRUE depth THROUGH openings/windows/glass that a cuboid GT "
             "closes off at the nearest wall, so the MoGe footprint OVER-reads on "
             "rooms with openings (a real modality difference, not a fusable error).")
    L.append("- Per-crop metric-scale dispersion is a genuine MoGe-fusion limitation "
             "(no cam_h is used anywhere; scale is MoGe's).")
    return "\n".join(L)


def _verdict(res: dict[str, Any]) -> str:
    """Apply the pre-committed go/no-go rule from the real numbers."""
    rows = res["rows"]
    hnet = _summarize(rows, "hnet")
    # Best MoGe variant per class on the <=15 cm rate.
    moge_c = _summarize(rows, "moge_convex")
    moge_r = _summarize(rows, "moge_robust")

    # A SINGLE MoGe variant must win BOTH metrics — do not let one variant supply
    # the <=15cm rate and the other the median (that would bias the bar toward GO).
    def best_variant(cls: str) -> tuple[str, float, float] | None:
        cands = [(n, m) for n, m in (("convex", moge_c), ("robust", moge_r))
                 if m and m.get(cls)]
        if not cands:
            return None
        # pick the variant with the higher <=15cm rate (tie-break: lower median).
        name, m = max(cands, key=lambda nm: (nm[1][cls]["pct_le15"],
                                             -nm[1][cls]["median_dim_cm"]))
        return name, m[cls]["pct_le15"], m[cls]["median_dim_cm"]

    lines = ["", "## Go / No-Go verdict (pre-committed rule)"]
    if not (hnet and hnet.get("office") and hnet.get("residential")):
        lines.append("- Inconclusive: HorizonNet baseline incomplete.")
        return "\n".join(lines)
    go = True
    for cls in ("office", "residential"):
        h15 = hnet[cls]["pct_le15"]
        hmed = hnet[cls]["median_dim_cm"]
        bv = best_variant(cls)
        if bv is None:
            go = False
            lines.append(f"- {cls}: no MoGe variant available -> does NOT beat baseline.")
            continue
        vname, m15, mmed = bv
        beats = (m15 > h15 and mmed < hmed)
        go = go and beats
        lines.append(
            f"- {cls}: MoGe best variant ({vname}) <=15% = {m15} vs HorizonNet {h15}; "
            f"median = {mmed} cm vs HorizonNet {hmed:.1f} cm "
            f"-> {'beats' if beats else 'does NOT beat'} baseline (single variant must win both).")
    if go:
        lines.append("\n**VERDICT: GO-as-candidate-default** — MoGe strictly beats "
                     "HorizonNet on both classes (still --experimental until a "
                     "measured-metric-GT validation exists).")
    else:
        lines.append("\n**VERDICT: SHIP-EXPERIMENTAL** — MoGe does not clearly beat "
                     "the HorizonNet baseline; ship `--backend moge` as an "
                     "experimental, unvalidated alternative (HorizonNet `image` "
                     "stays the documented rough tier).")
    return "\n".join(lines)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    result = run(n)
    report = _format(result) + "\n" + _verdict(result)
    print(report)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(report + "\n")
    print(f"\n[written] {RESULTS_PATH}")
