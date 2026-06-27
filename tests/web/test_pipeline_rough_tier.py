"""tests/web/test_pipeline_rough_tier.py — consumer "rough+" tier wiring.

Covers the three PLACEMENT_SENSITIVITY_VERDICT.md product requirements wired
into the web ``run_pipeline``:
  1. point-cloud ingest (.npz/.xyz/.txt, points-only .ply) → MultiviewAdapter
  2. user-supplied ceiling height (one scalar) → ceiling override
  3. install-time snap-to-surface after placement
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from roomestim_web.pipeline import run_pipeline


def _rough_cloud(seed: int = 0, n: int = 4000) -> np.ndarray:
    """Y-up rough cloud: 4 x 3 m room, floor + walls sampled to 1.5 m only
    (ceiling deliberately NOT captured, mimicking a rough phone/video scan)."""
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


@pytest.fixture
def cloud_npz(tmp_path: Path) -> Path:
    p = tmp_path / "rough.npz"
    np.savez(p, P_m=_rough_cloud())
    return p


@pytest.mark.web
def test_pipeline_pointcloud_npz_produces_yamls(cloud_npz: Path, tmp_path: Path) -> None:
    """A rough .npz point cloud routes to MultiviewAdapter and places speakers."""
    result = run_pipeline(
        cloud_npz,
        algorithm="dbap",
        n_speakers=8,
        layout_radius_m=2.0,
        el_deg=0.0,
        octave_band=False,
        out_dir=tmp_path,
        ceiling_height_m=2.7,
    )
    assert result.room_yaml_path.exists()
    assert result.layout_yaml_path.exists()
    assert len(result.layout.speakers) == 8
    # provenance downgraded for a reconstruction
    assert result.room.provenance == "reconstructed"  # type: ignore[attr-defined]


@pytest.mark.web
def test_pipeline_user_ceiling_override(cloud_npz: Path, tmp_path: Path) -> None:
    """User ceiling scalar overrides the (unrecoverable) cloud ceiling."""
    result = run_pipeline(
        cloud_npz,
        algorithm="dbap",
        n_speakers=8,
        layout_radius_m=2.0,
        el_deg=0.0,
        octave_band=False,
        out_dir=tmp_path,
        ceiling_height_m=2.7,
    )
    assert result.room.ceiling_height_m == pytest.approx(2.7)  # type: ignore[attr-defined]


@pytest.mark.web
def test_pipeline_snap_moves_speakers_onto_surfaces(
    cloud_npz: Path, tmp_path: Path
) -> None:
    """snap_to_surfaces=True pulls placed speakers onto real mount surfaces."""
    from roomestim.geom.surface_distance import closest_point_on_surface

    common = dict(
        algorithm="dbap",
        n_speakers=8,
        layout_radius_m=2.0,
        el_deg=0.0,
        octave_band=False,
        ceiling_height_m=2.7,
    )
    no_snap = run_pipeline(cloud_npz, out_dir=tmp_path / "a", snap_to_surfaces=False, **common)
    snapped = run_pipeline(cloud_npz, out_dir=tmp_path / "b", snap_to_surfaces=True, **common)

    room = snapped.room
    mounts = [s for s in room.surfaces if s.kind in ("wall", "ceiling")]  # type: ignore[attr-defined]
    assert mounts, "rough room must expose wall/ceiling mount surfaces"

    def min_surface_dist(layout) -> float:  # type: ignore[no-untyped-def]
        worst = 0.0
        for sp in layout.speakers:
            d = min(closest_point_on_surface(sp.position, s)[0] for s in mounts)
            worst = max(worst, d)
        return worst

    # Snapping must not increase any speaker's distance to the nearest surface,
    # and should drive the worst-case essentially to zero (on-surface).
    assert min_surface_dist(snapped.layout) <= min_surface_dist(no_snap.layout)
    assert min_surface_dist(snapped.layout) < 1e-6


@pytest.mark.web
def test_pipeline_xyz_text_cloud(tmp_path: Path) -> None:
    """A .xyz text cloud is accepted via the point-cloud path."""
    p = tmp_path / "rough.xyz"
    np.savetxt(p, _rough_cloud())
    result = run_pipeline(
        p,
        algorithm="dbap",
        n_speakers=8,
        layout_radius_m=2.0,
        el_deg=0.0,
        octave_band=False,
        out_dir=tmp_path / "out",
        ceiling_height_m=2.7,
    )
    assert result.layout_yaml_path.exists()
    assert len(result.layout.speakers) == 8


@pytest.mark.web
def test_pipeline_ply_points_only_falls_back_to_cloud(tmp_path: Path) -> None:
    """A points-only .ply (no faces) falls back from MeshAdapter to MultiviewAdapter."""
    trimesh = pytest.importorskip("trimesh")
    p = tmp_path / "rough.ply"
    trimesh.PointCloud(_rough_cloud()).export(p)
    result = run_pipeline(
        p,
        algorithm="dbap",
        n_speakers=8,
        layout_radius_m=2.0,
        el_deg=0.0,
        octave_band=False,
        out_dir=tmp_path / "out",
        ceiling_height_m=2.7,
    )
    assert result.room.provenance == "reconstructed"  # type: ignore[attr-defined]
    assert len(result.layout.speakers) == 8
