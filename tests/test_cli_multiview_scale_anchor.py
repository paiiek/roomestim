"""tests/test_cli_multiview_scale_anchor.py — multiview metric scale-anchor CLI wiring.

Covers the ``--known-floor-len-m`` flag that exposes the v0.53.0
``MultiviewAdapter`` metric scale anchor (ADR 0056) on the ``ingest`` and ``run``
CLI commands. Unlike the image backend, multiview parses a REAL synthetic
``.npz`` cloud, so no monkeypatch is needed.

The flag carries the KNOWN footprint diameter (corner-to-corner floor diagonal),
which rescales the reconstructed cloud isotropically so the extracted footprint
diagonal matches it — making a non-metric (VGGT-class) cloud metric.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from roomestim.cli import main
from roomestim.io.room_yaml_reader import read_room_yaml


# --------------------------------------------------------------------------- #
# Fixture: a synthetic Y-up "rough cloud" — 4 x 3 m room (footprint diagonal
# 5.0 m), floor + walls sampled up to 1.5 m only (ceiling deliberately omitted).
# Mirrors tests/test_aconsumer_multiview.py::_rough_cloud.
# --------------------------------------------------------------------------- #
def _rough_cloud(seed: int = 0, n: int = 4000) -> np.ndarray:
    rng = np.random.default_rng(seed)
    pts = []
    for _ in range(n):
        pts.append([rng.uniform(0, 4), 0.0, rng.uniform(0, 3)])  # floor
    for _ in range(n):
        y = rng.uniform(0, 1.5)
        e = int(rng.integers(0, 4))
        if e == 0:
            pts.append([rng.uniform(0, 4), y, 0.0])
        elif e == 1:
            pts.append([rng.uniform(0, 4), y, 3.0])
        elif e == 2:
            pts.append([0.0, y, rng.uniform(0, 3)])
        else:
            pts.append([4.0, y, rng.uniform(0, 3)])
    return np.asarray(pts, dtype=float)


def _write_cloud(path: Path, points: np.ndarray) -> Path:
    np.savez(path, P_m=points)
    return path


def _footprint_area_from_yaml(room_yaml: Path) -> float:
    """Read back room.yaml and compute the floor-polygon area via shapely."""
    from shapely.geometry import Polygon

    room = read_room_yaml(room_yaml)
    return float(Polygon([(p.x, p.z) for p in room.floor_polygon]).area)


# --------------------------------------------------------------------------- #
# ingest --backend multiview --known-floor-len-m
# --------------------------------------------------------------------------- #
def test_ingest_multiview_known_floor_len_lands_metric_area(tmp_path: Path) -> None:
    cloud = _write_cloud(tmp_path / "c.npz", _rough_cloud())
    rc = main(
        ["ingest", "--backend", "multiview", "--known-floor-len-m", "5.0",
         "--input", str(cloud), "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    room_yaml = tmp_path / "room.yaml"
    assert room_yaml.exists()
    assert _footprint_area_from_yaml(room_yaml) == pytest.approx(12.0, rel=0.15)


def test_ingest_multiview_anchor_is_scale_invariant(tmp_path: Path) -> None:
    # A 2x mis-scaled cloud anchored to the SAME 5.0 m footprint diameter lands
    # the SAME ~12 m^2 metric footprint (scale-invariance through the CLI).
    base_cloud = _write_cloud(tmp_path / "base.npz", _rough_cloud())
    rc_base = main(
        ["ingest", "--backend", "multiview", "--known-floor-len-m", "5.0",
         "--input", str(base_cloud), "--out-dir", str(tmp_path / "base_out")]
    )
    assert rc_base == 0
    base_area = _footprint_area_from_yaml(tmp_path / "base_out" / "room.yaml")

    mis_cloud = _write_cloud(tmp_path / "mis.npz", _rough_cloud() * 2.0)
    rc_mis = main(
        ["ingest", "--backend", "multiview", "--known-floor-len-m", "5.0",
         "--input", str(mis_cloud), "--out-dir", str(tmp_path / "mis_out")]
    )
    assert rc_mis == 0
    mis_area = _footprint_area_from_yaml(tmp_path / "mis_out" / "room.yaml")

    assert mis_area == pytest.approx(base_area, rel=1e-6)
    assert mis_area == pytest.approx(12.0, rel=0.15)


def test_ingest_multiview_without_anchor_still_metric(tmp_path: Path) -> None:
    # Regression guard: omitting --known-floor-len-m leaves the metric-native
    # cloud untouched (passes scale_anchor=None) — ~12 m^2 footprint, rc==0.
    cloud = _write_cloud(tmp_path / "c.npz", _rough_cloud())
    rc = main(
        ["ingest", "--backend", "multiview",
         "--input", str(cloud), "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    assert _footprint_area_from_yaml(tmp_path / "room.yaml") == pytest.approx(
        12.0, rel=0.05
    )


# --------------------------------------------------------------------------- #
# run --backend multiview --known-floor-len-m
# --------------------------------------------------------------------------- #
def test_run_multiview_known_floor_len_writes_outputs(tmp_path: Path) -> None:
    cloud = _write_cloud(tmp_path / "c.npz", _rough_cloud())
    rc = main(
        ["run", "--backend", "multiview", "--known-floor-len-m", "5.0",
         "--input", str(cloud), "--algorithm", "vbap", "--n-speakers", "6",
         "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    assert (tmp_path / "room.yaml").exists()
    assert (tmp_path / "layout.yaml").exists()
    assert _footprint_area_from_yaml(tmp_path / "room.yaml") == pytest.approx(
        12.0, rel=0.15
    )


# --------------------------------------------------------------------------- #
# Bad length is surfaced by the CLI (adapter raises ValueError → main() → rc 1)
# --------------------------------------------------------------------------- #
def test_ingest_multiview_rejects_bad_length(tmp_path: Path) -> None:
    cloud = _write_cloud(tmp_path / "c.npz", _rough_cloud())
    rc = main(
        ["ingest", "--backend", "multiview", "--known-floor-len-m", "-1",
         "--input", str(cloud), "--out-dir", str(tmp_path)]
    )
    assert rc != 0
    assert not (tmp_path / "room.yaml").exists()
