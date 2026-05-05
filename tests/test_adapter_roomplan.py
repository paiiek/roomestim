"""A9 — RoomPlan adapter tests (sidecar a/b split per decisions.md D9)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
import yaml
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.adapters import RoomPlanAdapter
from roomestim.model import (
    ListenerArea,
    MaterialLabel,
    Point2,
    Point3,
    RoomModel,
    Surface,
    canonicalize_ccw,
)
from roomestim.reconstruct.listener_area import (
    default_listener_area,
    kWarnConcaveListenerCentroid,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SIDECAR_PATH = FIXTURE_DIR / "lab_room.json"
META_PATH = FIXTURE_DIR / "lab_room.meta.yaml"
USDZ_PATH = FIXTURE_DIR / "lab_room.usdz"


def _load_meta() -> dict[str, Any]:
    with META_PATH.open("r", encoding="utf-8") as fh:
        meta = yaml.safe_load(fh)
    assert isinstance(meta, dict)
    return meta


def _floor_polygon_area(room: RoomModel) -> float:
    coords = [(p.x, p.z) for p in room.floor_polygon]
    return float(ShapelyPolygon(coords).area)


# --------------------------------------------------------------------------- #
# A9a — sidecar parses against ground-truth metadata
# --------------------------------------------------------------------------- #


def test_a9a_sidecar_parses() -> None:
    """A9a — sidecar JSON parses; ceiling +-10cm, area +-5%, walls >=4."""
    adapter = RoomPlanAdapter()
    room = adapter.parse(SIDECAR_PATH)
    meta = _load_meta()

    # Ceiling height tolerance: +-10 cm.
    assert room.ceiling_height_m == pytest.approx(
        meta["ceiling_height_m"], abs=0.10
    ), f"ceiling_height_m={room.ceiling_height_m}, expected ~{meta['ceiling_height_m']}"

    # Floor area tolerance: +-5 %.
    floor_area = _floor_polygon_area(room)
    expected_area = float(meta["floor_area_m2"])
    assert floor_area == pytest.approx(expected_area, rel=0.05), (
        f"floor_area={floor_area}, expected ~{expected_area} (+-5%)"
    )

    # Wall count: >= meta['wall_count'].
    wall_count = sum(1 for s in room.surfaces if s.kind == "wall")
    assert wall_count >= int(meta["wall_count"]), (
        f"wall_count={wall_count}, expected >= {meta['wall_count']}"
    )

    # Listener centroid +- 10 cm tolerance when meta provides ground truth.
    if "listener_centroid" in meta:
        truth = meta["listener_centroid"]
        truth_x = float(truth["x"])
        truth_z = float(truth["z"])
        cx = room.listener_area.centroid.x
        cz = room.listener_area.centroid.z
        dx = cx - truth_x
        dz = cz - truth_z
        dist = math.hypot(dx, dz)
        assert dist <= 0.10, (
            f"listener centroid ({cx}, {cz}) far from truth "
            f"({truth_x}, {truth_z}); dist={dist:.3f} m > 0.10 m"
        )


def test_a9a_materials_mapped() -> None:
    """Walls -> WALL_PAINTED, floor -> WOOD_FLOOR, ceiling -> CEILING_ACOUSTIC_TILE."""
    adapter = RoomPlanAdapter()
    room = adapter.parse(SIDECAR_PATH)

    walls = [s for s in room.surfaces if s.kind == "wall"]
    assert walls, "expected at least one wall surface"
    for s in walls:
        assert s.material == MaterialLabel.WALL_PAINTED, (
            f"wall material={s.material}, expected WALL_PAINTED"
        )

    floors = [s for s in room.surfaces if s.kind == "floor"]
    assert len(floors) == 1
    assert floors[0].material == MaterialLabel.WOOD_FLOOR

    ceilings = [s for s in room.surfaces if s.kind == "ceiling"]
    assert len(ceilings) == 1
    assert ceilings[0].material == MaterialLabel.CEILING_ACOUSTIC_TILE


def test_a9a_floor_polygon_is_ccw() -> None:
    """Floor polygon emitted in CCW order on the (x, z) plane."""
    adapter = RoomPlanAdapter()
    room = adapter.parse(SIDECAR_PATH)
    coords = [(p.x, p.z) for p in room.floor_polygon]
    poly = ShapelyPolygon(coords)
    assert poly.exterior.is_ccw is True


# --------------------------------------------------------------------------- #
# A9b — gated USDZ path; SKIP cleanly when the file is absent
# --------------------------------------------------------------------------- #


def test_a9b_real_usdz_skip_when_absent() -> None:
    """A9b — real USDZ parses through same code path; SKIP when fixture missing."""
    adapter = RoomPlanAdapter()
    if not USDZ_PATH.exists():
        pytest.skip(
            f"A9b real USDZ fixture not present at {USDZ_PATH}; "
            "post-autopilot human-driven capture per D8."
        )
    try:
        adapter.parse(USDZ_PATH)
    except NotImplementedError as exc:
        pytest.skip(f"A9b USDZ parametric path not implemented in v0.1: {exc}")


# --------------------------------------------------------------------------- #
# Concave listener centroid warning
# --------------------------------------------------------------------------- #


def test_concave_listener_centroid_warning() -> None:
    """Concave floor polygon -> kWarnConcaveListenerCentroid emitted."""
    # An L-shape whose geometric centroid lies outside the polygon.
    # Use a thin L: the centroid of the union of two thin arms falls in the
    # missing corner.
    floor = [
        Point2(0.0, 0.0),
        Point2(10.0, 0.0),
        Point2(10.0, 1.0),
        Point2(1.0, 1.0),
        Point2(1.0, 10.0),
        Point2(0.0, 10.0),
    ]
    floor = canonicalize_ccw(floor)

    # Sanity: confirm the geometric centroid actually falls outside.
    shp = ShapelyPolygon([(p.x, p.z) for p in floor])
    assert not shp.contains(shp.centroid), (
        "test setup invariant: floor centroid must be outside the polygon"
    )

    with pytest.warns(kWarnConcaveListenerCentroid):
        listener = default_listener_area(floor)
    assert isinstance(listener, ListenerArea)


# --------------------------------------------------------------------------- #
# Smoke: parsed RoomModel surfaces are well-formed
# --------------------------------------------------------------------------- #


def test_a9a_surfaces_well_formed() -> None:
    adapter = RoomPlanAdapter()
    room = adapter.parse(SIDECAR_PATH)
    for s in room.surfaces:
        assert isinstance(s, Surface)
        assert len(s.polygon) >= 3
        for p in s.polygon:
            assert isinstance(p, Point3)
        assert 0.0 <= s.absorption_500hz <= 1.0
