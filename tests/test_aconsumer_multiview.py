"""A-consumer placement levers + multiview point-cloud ingest.

Covers the features wired from PLACEMENT_SENSITIVITY_VERDICT.md:
  - MultiviewAdapter: reconstructed point-cloud ingest (.ply/.npz/.xyz)
  - evolve_room_ceiling_height: user-supplied ceiling override
  - snap_layout_to_surfaces + closest_point_on_surface: install-time snap
"""

from __future__ import annotations

import numpy as np
import pytest

from roomestim.adapters.base import ScaleAnchor
from roomestim.adapters.multiview import MultiviewAdapter
from roomestim.edit import (
    evolve_room_ceiling_height,
    snap_layout_to_surfaces,
)
from roomestim.geom.surface_distance import closest_point_on_surface
from roomestim.model import PlacedSpeaker, PlacementResult, Point3
from roomestim.place.dbap import place_dbap


# --------------------------------------------------------------------------- #
# Fixtures: a synthetic Y-up "rough cloud" — 4 x 3 m room, floor + walls sampled
# up to 1.5 m only (ceiling deliberately NOT captured, mimicking rough capture).
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


@pytest.fixture
def cloud() -> np.ndarray:
    return _rough_cloud()


# --------------------------------------------------------------------------- #
# MultiviewAdapter — ingest formats
# --------------------------------------------------------------------------- #
def test_multiview_npz_pm_key(tmp_path, cloud):
    p = tmp_path / "c.npz"
    np.savez(p, P_m=cloud)  # spike cache convention
    room = MultiviewAdapter(up_axis="y", floor_reconstruction="convex").parse(p)
    assert room.provenance == "reconstructed"
    assert len(room.floor_polygon) >= 3
    assert room.ceiling_height_m > 0.0
    # A ceiling-less cloud cannot yield a confident ceiling.
    assert room.ceiling_confidence in ("low", "unknown")


def test_multiview_npz_generic_key_and_fallback(tmp_path, cloud):
    p = tmp_path / "c.npz"
    np.savez(p, points=cloud)
    room = MultiviewAdapter(up_axis="y").parse(p)
    assert len(room.floor_polygon) >= 3
    # Fallback: an archive with only a non-standard key still resolves via the
    # "first (N, 3) array" rule.
    p2 = tmp_path / "c2.npz"
    np.savez(p2, weird_name=cloud)
    room2 = MultiviewAdapter(up_axis="y").parse(p2)
    assert len(room2.floor_polygon) >= 3


def test_multiview_xyz_text(tmp_path, cloud):
    p = tmp_path / "c.xyz"
    np.savetxt(p, cloud)
    room = MultiviewAdapter(up_axis="y").parse(p)
    assert room.provenance == "reconstructed"
    assert len(room.floor_polygon) >= 3


def test_multiview_ply_points_only(tmp_path, cloud):
    trimesh = pytest.importorskip("trimesh")
    p = tmp_path / "c.ply"
    trimesh.PointCloud(cloud).export(p)
    room = MultiviewAdapter(up_axis="y").parse(p)
    assert room.provenance == "reconstructed"
    assert len(room.floor_polygon) >= 3


def test_multiview_ceiling_override_in_adapter(tmp_path, cloud):
    p = tmp_path / "c.npz"
    np.savez(p, P_m=cloud)
    room = MultiviewAdapter(up_axis="y", ceiling_height_m=2.7).parse(p)
    assert room.ceiling_height_m == pytest.approx(2.7)
    assert room.ceiling_confidence == "high"


def test_multiview_rejects_bad_extension(tmp_path):
    p = tmp_path / "c.obj"
    p.write_text("dummy")
    with pytest.raises(ValueError, match="unsupported extension"):
        MultiviewAdapter().parse(p)


def test_multiview_rejects_too_few_points(tmp_path):
    p = tmp_path / "c.npz"
    np.savez(p, P_m=np.zeros((2, 3)))
    with pytest.raises(ValueError, match=">=3 points"):
        MultiviewAdapter(up_axis="y").parse(p)


def test_multiview_bad_ceiling_arg():
    with pytest.raises(ValueError, match="ceiling_height_m must be > 0"):
        MultiviewAdapter(ceiling_height_m=-1.0)


# --------------------------------------------------------------------------- #
# MultiviewAdapter — scale_anchor (metric-scale anchor)
# --------------------------------------------------------------------------- #
def _footprint_area(room) -> float:
    from shapely.geometry import Polygon

    return float(Polygon([(p.x, p.z) for p in room.floor_polygon]).area)


def _parse_npz(tmp_path, points, *, scale_anchor=None, name="c"):
    p = tmp_path / f"{name}.npz"
    np.savez(p, P_m=points)
    return MultiviewAdapter(up_axis="y", floor_reconstruction="convex").parse(
        p, scale_anchor=scale_anchor
    )


@pytest.mark.parametrize("k", [0.37, 2.5])
def test_scale_anchor_removes_input_scale_dependence(tmp_path, k):
    # Property the spike _validate_scale_anchor.py asserts: mis-scaling the WHOLE
    # cloud by any k yields an IDENTICAL anchored footprint area. The anchor
    # length is fixed, so the rescale undoes whatever input scale was present.
    fixed_len = 5.0
    base = _parse_npz(
        tmp_path, _rough_cloud(), scale_anchor=ScaleAnchor("user_provided", fixed_len),
        name="base",
    )
    mis = _parse_npz(
        tmp_path,
        _rough_cloud() * k,
        scale_anchor=ScaleAnchor("user_provided", fixed_len),
        name=f"k{k}",
    )
    base_area = _footprint_area(base)
    mis_area = _footprint_area(mis)
    assert mis_area == pytest.approx(base_area, rel=1e-6)


def test_scale_anchor_lands_metric_area(tmp_path):
    # Metric sanity: the 4x3 m rough cloud has true footprint diameter 5.0 m
    # (diagonal of 4x3). Anchoring to 5.0 m should leave the convex footprint at
    # ~12 m^2 (area of a 4x3 rect).
    room = _parse_npz(
        tmp_path, _rough_cloud(), scale_anchor=ScaleAnchor("user_provided", 5.0)
    )
    assert _footprint_area(room) == pytest.approx(12.0, rel=0.15)


def test_scale_anchor_rescales_diameter(tmp_path):
    # Anchoring a 2x mis-scaled cloud to 5.0 m brings the footprint diameter back
    # to ~5.0 m (the convex 4x3 diagonal).
    room = _parse_npz(
        tmp_path, _rough_cloud() * 2.0, scale_anchor=ScaleAnchor("user_provided", 5.0)
    )
    assert MultiviewAdapter._footprint_diameter(room) == pytest.approx(5.0, rel=0.05)


def test_scale_anchor_rejects_unsupported_type(tmp_path, cloud):
    with pytest.raises(ValueError, match="scale_anchor.type"):
        _parse_npz(tmp_path, cloud, scale_anchor=ScaleAnchor("aruco", 1.0))


@pytest.mark.parametrize("bad", [0.0, -1.0, float("inf"), float("nan")])
def test_scale_anchor_rejects_bad_length(tmp_path, cloud, bad):
    with pytest.raises(ValueError, match="length_m"):
        _parse_npz(tmp_path, cloud, scale_anchor=ScaleAnchor("user_provided", bad))


def test_no_scale_anchor_footprint_unchanged(tmp_path, cloud):
    # Snapshot: parsing the 4x3 rough cloud WITHOUT an anchor gives the metric-
    # native ~12 m^2 footprint (regression guard — anchor path must not alter the
    # no-anchor behavior).
    room = _parse_npz(tmp_path, cloud, scale_anchor=None)
    assert _footprint_area(room) == pytest.approx(12.0, rel=0.05)


# --------------------------------------------------------------------------- #
# evolve_room_ceiling_height
# --------------------------------------------------------------------------- #
def test_ceiling_override_rebuilds_geometry(tmp_path, cloud):
    p = tmp_path / "c.npz"
    np.savez(p, P_m=cloud)
    room = MultiviewAdapter(up_axis="y").parse(p)
    out = evolve_room_ceiling_height(room, 2.5)
    assert out.ceiling_height_m == pytest.approx(2.5)
    assert out.ceiling_confidence == "high"
    assert out.ceiling_coverage is None
    # floor unchanged
    assert len(out.floor_polygon) == len(room.floor_polygon)
    # ceiling surface lifted to floor_y + 2.5
    floor_y = next(s for s in out.surfaces if s.kind == "floor").polygon[0].y
    ceil = next(s for s in out.surfaces if s.kind == "ceiling")
    assert all(v.y == pytest.approx(floor_y + 2.5) for v in ceil.polygon)
    # walls span [floor_y, floor_y + 2.5]
    for w in (s for s in out.surfaces if s.kind == "wall"):
        ys = sorted(v.y for v in w.polygon)
        assert ys[0] == pytest.approx(floor_y)
        assert ys[-1] == pytest.approx(floor_y + 2.5)
    # input not mutated (frozen-evolve invariant)
    assert room.ceiling_height_m != pytest.approx(2.5)


def test_ceiling_override_offset_floor_consistency(tmp_path):
    # Regression (code-review MEDIUM): when the detected floor plane is NOT at
    # y=0, the override must re-anchor walls/ceiling to the floor surface's y so
    # the box stays vertically consistent (mesh extraction builds walls from
    # y=0 while placing the floor at its detected plane).
    offset = _rough_cloud() + np.array([0.0, 5.0, 0.0])  # lift cloud +5 m in y
    p = tmp_path / "c.npz"
    np.savez(p, P_m=offset)
    room = MultiviewAdapter(up_axis="y").parse(p)
    out = evolve_room_ceiling_height(room, 2.4)
    floor_y = next(s for s in out.surfaces if s.kind == "floor").polygon[0].y
    assert floor_y == pytest.approx(5.0, abs=0.2)
    ceil = next(s for s in out.surfaces if s.kind == "ceiling")
    assert all(v.y == pytest.approx(floor_y + 2.4) for v in ceil.polygon)
    for w in (s for s in out.surfaces if s.kind == "wall"):
        ys = sorted(v.y for v in w.polygon)
        assert ys[0] == pytest.approx(floor_y)
        assert ys[-1] == pytest.approx(floor_y + 2.4)


def test_multiview_adapter_rejects_implausible_ceiling():
    # Fail-fast at construction (code-review LOW): the 20 m plausibility bound
    # is enforced in __init__, not deferred to parse().
    with pytest.raises(ValueError, match="plausibility bound"):
        MultiviewAdapter(ceiling_height_m=999.0)


def test_multiview_npz_xyzrgb_key_sliced(tmp_path, cloud):
    # code-review LOW: a named point key carrying extra columns (xyzrgb) is
    # sliced to xyz for parity with the .xyz/.txt loader, not rejected.
    rgb = np.random.default_rng(1).uniform(0, 1, size=(cloud.shape[0], 3))
    p = tmp_path / "c.npz"
    np.savez(p, points=np.hstack([cloud, rgb]))  # (N, 6)
    room = MultiviewAdapter(up_axis="y").parse(p)
    assert len(room.floor_polygon) >= 3


@pytest.mark.parametrize("bad", [0.0, -1.0, 999.0])
def test_ceiling_override_rejects_implausible(tmp_path, cloud, bad):
    p = tmp_path / "c.npz"
    np.savez(p, P_m=cloud)
    room = MultiviewAdapter(up_axis="y").parse(p)
    with pytest.raises(ValueError):
        evolve_room_ceiling_height(room, bad)


# --------------------------------------------------------------------------- #
# closest_point_on_surface + snap_layout_to_surfaces
# --------------------------------------------------------------------------- #
def test_closest_point_on_wall_clamps_to_polygon(tmp_path, cloud):
    p = tmp_path / "c.npz"
    np.savez(p, P_m=cloud)
    room = MultiviewAdapter(up_axis="y", ceiling_height_m=2.5).parse(p)
    wall = next(s for s in room.surfaces if s.kind == "wall")
    # A point pushed off the wall along its normal snaps back onto the wall plane.
    v = wall.polygon[0]
    probe = Point3(v.x + 0.5, v.y, v.z + 0.5)
    dist, closest = closest_point_on_surface(probe, wall)
    assert dist >= 0.0
    # Re-snapping the returned closest point gives ~0 distance (it lies on it).
    dist2, _ = closest_point_on_surface(closest, wall)
    assert dist2 == pytest.approx(0.0, abs=1e-6)


def test_snap_layout_moves_speakers_onto_surfaces(tmp_path, cloud):
    p = tmp_path / "c.npz"
    np.savez(p, P_m=cloud)
    room = MultiviewAdapter(up_axis="y", ceiling_height_m=2.5).parse(p)
    mounts = [s for s in room.surfaces if s.kind in ("wall", "ceiling")]
    lay = place_dbap(mount_surfaces=mounts, n_speakers=8, listener_area=room.listener_area)

    from dataclasses import replace

    perturbed = replace(
        lay,
        speakers=[
            replace(s, position=Point3(s.position.x + 0.3, s.position.y, s.position.z + 0.3))
            for s in lay.speakers
        ],
    )
    snapped = snap_layout_to_surfaces(room, perturbed)

    def max_off(layout: PlacementResult) -> float:
        return max(
            min(closest_point_on_surface(s.position, m)[0] for m in mounts)
            for s in layout.speakers
        )

    assert max_off(perturbed) > 0.1  # perturbation took them off-surface
    assert max_off(snapped) == pytest.approx(0.0, abs=1e-6)
    assert len(snapped.speakers) == len(lay.speakers)


def test_snap_no_mount_surfaces_is_noop():
    # A result whose room has no wall/ceiling surfaces is returned unchanged.
    from roomestim.model import ListenerArea, Point2, RoomModel, Surface

    floor = Surface(
        kind="floor",
        polygon=[Point3(0, 0, 0), Point3(2, 0, 0), Point3(2, 0, 2), Point3(0, 0, 2)],
        material=__import__(
            "roomestim.model", fromlist=["MaterialLabel"]
        ).MaterialLabel.WOOD_FLOOR,
        absorption_500hz=0.1,
    )
    room = RoomModel(
        name="floor_only",
        floor_polygon=[Point2(0, 0), Point2(2, 0), Point2(2, 2), Point2(0, 2)],
        ceiling_height_m=2.5,
        surfaces=[floor],
        listener_area=ListenerArea(
            polygon=[Point2(0.5, 0.5), Point2(1.5, 0.5), Point2(1.5, 1.5), Point2(0.5, 1.5)],
            centroid=Point2(1.0, 1.0),
        ),
    )
    res = PlacementResult(
        target_algorithm="DBAP",
        regularity_hint="IRREGULAR",
        speakers=[PlacedSpeaker(channel=1, position=Point3(1, 1, 1))],
        layout_name="x",
    )
    out = snap_layout_to_surfaces(room, res)
    assert out.speakers[0].position == Point3(1, 1, 1)
