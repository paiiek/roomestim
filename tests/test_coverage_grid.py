"""Deterministic unit tests for the B1 ceiling coverage grid (geometry only).

Every expected coverage figure is computed in-test from the AVIXA formula with
``math.tan`` (no hardcoded rounded literals, no fake numbers). No randomness, no
I/O except the one tmp-path round-trip in the pipeline-reuse test.
"""

from __future__ import annotations

import math

import pytest

from roomestim.model import PlacementResult, Point2, Point3
from roomestim.place.coverage_grid import (
    COVERAGE_GRID_NOTE,
    EFFECTIVE_DISPERSION_FACTOR,
    OVERLAP_FRACTION,
    coverage_result_to_placement,
    coverage_to_dict,
    format_coverage_lines,
    place_coverage_grid,
    place_coverage_grid_for_room,
)

# --------------------------------------------------------------------------- #
# Analytic helpers (mirror the geometry; computed, never hardcoded)
# --------------------------------------------------------------------------- #


def _expected_radius(ceiling: float, ear: float, dispersion: float) -> float:
    eff = dispersion * EFFECTIVE_DISPERSION_FACTOR
    return (ceiling - ear) * math.tan(math.radians(eff / 2.0))


def _expected_spacing(ceiling: float, ear: float, dispersion: float, overlap: float) -> float:
    return 2.0 * _expected_radius(ceiling, ear, dispersion) * (1.0 - overlap)


def _rect(length_x: float, width_z: float) -> list[Point2]:
    return [
        Point2(0.0, 0.0),
        Point2(length_x, 0.0),
        Point2(length_x, width_z),
        Point2(0.0, width_z),
    ]


def _axis_count(span: float, spacing: float) -> int:
    """Closed form of the half-spacing-both-edges lattice node count on one axis."""
    return math.floor((span - spacing) / spacing) + 1


# --------------------------------------------------------------------------- #
# 1. Known rectangle -> known count & spacing (square)
# --------------------------------------------------------------------------- #


def test_square_known_rectangle_count_and_spacing() -> None:
    ceiling, ear, disp = 3.0, 1.0, 90.0
    result = place_coverage_grid(
        floor_polygon=_rect(10.0, 8.0),
        ceiling_height_m=ceiling,
        ear_height_m=ear,
        nominal_dispersion_deg=disp,
        overlap_mode="background",
        grid_type="square",
    )
    radius = _expected_radius(ceiling, ear, disp)
    spacing = _expected_spacing(ceiling, ear, disp, OVERLAP_FRACTION["background"])

    assert result.coverage_radius_m == pytest.approx(radius, abs=1e-12)
    assert result.coverage_diameter_m == pytest.approx(2.0 * radius, abs=1e-12)
    assert result.center_to_center_spacing_m == pytest.approx(spacing, abs=1e-12)

    nx = _axis_count(10.0, spacing)
    nz = _axis_count(8.0, spacing)
    assert result.n_speakers == nx * nz  # rectangle => all nodes inside

    # First node half a spacing from the edge; neighbour pitch == spacing.
    xs = sorted({sp.position.x for sp in result.speakers})
    assert xs[0] == pytest.approx(spacing / 2.0, abs=1e-9)
    assert xs[1] - xs[0] == pytest.approx(spacing, abs=1e-9)

    for sp in result.speakers:
        assert sp.position.y == ceiling
        assert sp.aim_direction == Point3(0.0, -1.0, 0.0)


# --------------------------------------------------------------------------- #
# 2. Hex grid on the same rectangle
# --------------------------------------------------------------------------- #


def test_hex_grid_rows_offset_and_inside() -> None:
    ceiling, ear, disp = 3.0, 1.0, 90.0
    result = place_coverage_grid(
        floor_polygon=_rect(10.0, 8.0),
        ceiling_height_m=ceiling,
        ear_height_m=ear,
        nominal_dispersion_deg=disp,
        grid_type="hex",
    )
    assert result.grid_type == "hex"
    spacing = result.center_to_center_spacing_m

    rows: dict[float, list[float]] = {}
    for sp in result.speakers:
        rows.setdefault(round(sp.position.z, 9), []).append(sp.position.x)
    zlevels = sorted(rows)
    assert len(zlevels) >= 2

    # Row pitch dz = spacing * sqrt(3) / 2.
    dz = spacing * math.sqrt(3.0) / 2.0
    assert zlevels[1] - zlevels[0] == pytest.approx(dz, abs=1e-9)

    # Odd rows offset by spacing/2 relative to even rows.
    even_minx = min(rows[zlevels[0]])
    odd_minx = min(rows[zlevels[1]])
    assert odd_minx - even_minx == pytest.approx(spacing / 2.0, abs=1e-9)

    # All positions inside the rectangle [0,10] x [0,8].
    for sp in result.speakers:
        assert 0.0 <= sp.position.x <= 10.0
        assert 0.0 <= sp.position.z <= 8.0


# --------------------------------------------------------------------------- #
# 3. Overlap mode changes spacing & count
# --------------------------------------------------------------------------- #


def test_overlap_mode_speech_denser_than_background() -> None:
    rect = _rect(20.0, 16.0)
    bg = place_coverage_grid(
        floor_polygon=rect, ceiling_height_m=3.0, ear_height_m=1.0, overlap_mode="background"
    )
    speech = place_coverage_grid(
        floor_polygon=rect, ceiling_height_m=3.0, ear_height_m=1.0, overlap_mode="speech"
    )
    assert speech.center_to_center_spacing_m < bg.center_to_center_spacing_m
    assert speech.n_speakers > bg.n_speakers
    assert bg.overlap_fraction == OVERLAP_FRACTION["background"]
    assert speech.overlap_fraction == OVERLAP_FRACTION["speech"]


# --------------------------------------------------------------------------- #
# 4. Coverage-radius formula exactness
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("ceiling", "ear", "dispersion"),
    [(2.7, 1.2, 90.0), (3.5, 1.0, 110.0), (4.0, 1.2, 60.0), (2.5, 0.0, 120.0)],
)
def test_coverage_radius_formula_exact(ceiling: float, ear: float, dispersion: float) -> None:
    result = place_coverage_grid(
        floor_polygon=_rect(12.0, 12.0),
        ceiling_height_m=ceiling,
        ear_height_m=ear,
        nominal_dispersion_deg=dispersion,
    )
    expected = (ceiling - ear) * math.tan(math.radians(EFFECTIVE_DISPERSION_FACTOR * dispersion / 2.0))
    assert result.coverage_radius_m == pytest.approx(expected, abs=1e-12)
    assert result.effective_dispersion_deg == pytest.approx(
        dispersion * EFFECTIVE_DISPERSION_FACTOR, abs=1e-12
    )


# --------------------------------------------------------------------------- #
# 5. Tiny room -> exactly 1 speaker (fallback)
# --------------------------------------------------------------------------- #


def test_tiny_room_single_speaker_fallback() -> None:
    from shapely.geometry import Point as ShapelyPoint
    from shapely.geometry import Polygon as ShapelyPolygon

    poly_pts = _rect(1.2, 1.0)  # smaller than one spacing (~2.27 m)
    result = place_coverage_grid(
        floor_polygon=poly_pts, ceiling_height_m=3.0, ear_height_m=1.0
    )
    assert result.n_speakers == 1
    sp = result.speakers[0]
    shp = ShapelyPolygon([(p.x, p.z) for p in poly_pts])
    assert shp.covers(ShapelyPoint(sp.position.x, sp.position.z))

    placement = coverage_result_to_placement(result)
    assert placement.regularity_hint == "IRREGULAR"


# --------------------------------------------------------------------------- #
# 6. Concave (L-shaped) footprint
# --------------------------------------------------------------------------- #


def test_concave_l_shape_drops_notch_nodes() -> None:
    from shapely.geometry import Point as ShapelyPoint
    from shapely.geometry import Polygon as ShapelyPolygon

    # L-shape: full 10x10 minus the top-right quadrant (x>4 and z>4 is the notch).
    l_pts = [
        Point2(0.0, 0.0),
        Point2(10.0, 0.0),
        Point2(10.0, 4.0),
        Point2(4.0, 4.0),
        Point2(4.0, 10.0),
        Point2(0.0, 10.0),
    ]
    result = place_coverage_grid(
        floor_polygon=l_pts, ceiling_height_m=3.0, ear_height_m=1.0
    )
    assert result.n_speakers >= 1
    shp = ShapelyPolygon([(p.x, p.z) for p in l_pts])
    buffered = shp.buffer(1e-9)
    for sp in result.speakers:
        pt = ShapelyPoint(sp.position.x, sp.position.z)
        assert shp.covers(pt) or buffered.covers(pt)
        # No kept node in the excluded notch.
        assert not (sp.position.x > 4.0 and sp.position.z > 4.0)


# --------------------------------------------------------------------------- #
# 7. Edge-case errors
# --------------------------------------------------------------------------- #


def test_ceiling_not_above_ear_raises() -> None:
    with pytest.raises(ValueError, match="ceiling_height_m <= ear_height_m"):
        place_coverage_grid(
            floor_polygon=_rect(10.0, 8.0), ceiling_height_m=1.0, ear_height_m=1.0
        )
    with pytest.raises(ValueError, match="ceiling_height_m <= ear_height_m"):
        place_coverage_grid(
            floor_polygon=_rect(10.0, 8.0), ceiling_height_m=0.0, ear_height_m=1.2
        )


def test_too_few_vertices_raises() -> None:
    with pytest.raises(ValueError, match=">=3 vertices"):
        place_coverage_grid(
            floor_polygon=[Point2(0.0, 0.0), Point2(1.0, 0.0)],
            ceiling_height_m=3.0,
            ear_height_m=1.0,
        )


def test_self_intersecting_polygon_raises() -> None:
    # Bow-tie (self-intersecting) quad.
    bowtie = [Point2(0.0, 0.0), Point2(2.0, 2.0), Point2(2.0, 0.0), Point2(0.0, 2.0)]
    with pytest.raises(ValueError, match="degenerate floor polygon"):
        place_coverage_grid(
            floor_polygon=bowtie, ceiling_height_m=3.0, ear_height_m=1.0
        )


def test_non_finite_ceiling_raises() -> None:
    with pytest.raises(ValueError, match="kErrNonFiniteValue"):
        place_coverage_grid(
            floor_polygon=_rect(10.0, 8.0),
            ceiling_height_m=float("nan"),
            ear_height_m=1.0,
        )


@pytest.mark.parametrize("disp", [0.0, 180.0, 200.0])
def test_dispersion_out_of_range_raises(disp: float) -> None:
    with pytest.raises(ValueError, match="nominal_dispersion_deg"):
        place_coverage_grid(
            floor_polygon=_rect(10.0, 8.0),
            ceiling_height_m=3.0,
            ear_height_m=1.0,
            nominal_dispersion_deg=disp,
        )


# --------------------------------------------------------------------------- #
# 8. Room wrapper + ceiling_confidence == "low" (no raise)
# --------------------------------------------------------------------------- #


def _make_room(ceiling: float = 3.0, ear: float = 1.3, *, confidence: str = "unknown"):
    from roomestim.model import ListenerArea, RoomModel, Surface

    floor = _rect(8.0, 6.0)
    centroid = Point2(4.0, 3.0)
    listener = ListenerArea(polygon=_rect(8.0, 6.0), centroid=centroid, height_m=ear)
    floor_surface = Surface(
        kind="floor",
        polygon=[Point3(p.x, 0.0, p.z) for p in floor],
        material=__import__("roomestim.model", fromlist=["MaterialLabel"]).MaterialLabel.WOOD_FLOOR,
        absorption_500hz=0.10,
    )
    return RoomModel(
        name="t",
        floor_polygon=floor,
        ceiling_height_m=ceiling,
        surfaces=[floor_surface],
        listener_area=listener,
        ceiling_confidence=confidence,  # type: ignore[arg-type]
    )


def test_room_wrapper_uses_listener_height_and_low_confidence_ok() -> None:
    room = _make_room(ceiling=3.0, ear=1.3, confidence="low")
    result = place_coverage_grid_for_room(room)
    assert result.n_speakers >= 1
    assert result.ear_height_m == 1.3  # defaulted from listener_area.height_m

    # Explicit ear override wins.
    override = place_coverage_grid_for_room(room, ear_height_m=1.0)
    assert override.ear_height_m == 1.0
    assert override.coverage_radius_m > result.coverage_radius_m  # lower ear => bigger cone


# --------------------------------------------------------------------------- #
# 9. NOTE / honesty invariants
# --------------------------------------------------------------------------- #


def test_note_honesty_invariants() -> None:
    result = place_coverage_grid(
        floor_polygon=_rect(10.0, 8.0), ceiling_height_m=3.0, ear_height_m=1.0
    )
    assert result.note is COVERAGE_GRID_NOTE
    assert coverage_to_dict(result)["note"] == COVERAGE_GRID_NOTE
    assert format_coverage_lines(result)[-1].startswith("  NOTE:")

    # Geometric-only, explicit non-claim language; cites AVIXA; defers B2.
    note = COVERAGE_GRID_NOTE
    assert "NO acoustic-performance or SPL claim" in note
    assert "does NOT compute sound pressure level" in note
    assert "AVIXA Audio Coverage Uniformity" in note
    assert "deferred to B2" in note


# --------------------------------------------------------------------------- #
# 10. Pipeline reuse (write_layout_yaml + B5/B6 surfaces + round-trip)
# --------------------------------------------------------------------------- #


def test_pipeline_reuse_layout_and_surfaces(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from roomestim.export.layout_yaml import write_layout_yaml
    from roomestim.io.placement_yaml_reader import read_placement_yaml
    from roomestim.place.standards import check_layout_angles, compute_layout_metrics

    result = place_coverage_grid(
        floor_polygon=_rect(10.0, 8.0), ceiling_height_m=3.0, ear_height_m=1.0
    )
    placement = coverage_result_to_placement(result)
    assert isinstance(placement, PlacementResult)
    assert placement.target_algorithm == "COVERAGE_GRID"
    assert placement.regularity_hint == "PLANAR_GRID"

    out_path = tmp_path / "layout.yaml"
    write_layout_yaml(placement, out_path, validate=False)
    assert out_path.is_file()

    # Reader accepts the new label (closed-set validation extended additively).
    restored = read_placement_yaml(out_path)
    assert restored.target_algorithm == "COVERAGE_GRID"
    assert len(restored.speakers) == len(placement.speakers)

    # B5/B6 geometric surfaces accept any PlacementResult without error.
    report = check_layout_angles(placement)
    assert len(report.speakers) == len(placement.speakers)
    metrics = compute_layout_metrics(placement)
    assert metrics.note  # populated, no exception


# --------------------------------------------------------------------------- #
# 11. dict shape + speaker serialization
# --------------------------------------------------------------------------- #


def test_coverage_to_dict_shape() -> None:
    result = place_coverage_grid(
        floor_polygon=_rect(10.0, 8.0), ceiling_height_m=3.0, ear_height_m=1.0
    )
    d = coverage_to_dict(result)
    assert list(d)[0] == "note"  # note first
    assert d["n_speakers"] == result.n_speakers
    speakers = d["speakers"]
    assert isinstance(speakers, list)
    assert len(speakers) == result.n_speakers
    first = speakers[0]
    assert set(first) == {"channel", "x", "y", "z", "aim_x", "aim_y", "aim_z"}
    assert first["aim_y"] == -1.0
