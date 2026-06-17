"""CAND-3 — Ambisonics rig placement (ADR 0041 PR2+PR3).

Geometry-only, numpy-only tests for ``place_ambisonics``: angle precision,
symmetry, quasi-isotropy proxy (spherical-2-design second moment, NOT a scipy SH
condition number — scipy renamed ``sph_harm`` -> ``sph_harm_y`` in 1.15+, so the
SH path is version-fragile; the proxy is exact for these symmetric rigs), the
``n >= (N+1)**2`` lower bound, round-trip label preservation (PR1
``x_target_algorithm``), R10/R11 write pre-flight, error contracts, and the
load-bearing CLI disclosure (WARN + NOTE).
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pytest

from roomestim.cli import _maybe_print_ambisonics_notes
from roomestim.export.layout_yaml import write_layout_yaml
from roomestim.io.placement_yaml_reader import read_placement_yaml
from roomestim.place.ambisonics import (
    AMBISONICS_RIG_DISCLOSURE,
    place_ambisonics,
)
from roomestim.place.dispatch import run_placement

_PHI = (1.0 + math.sqrt(5.0)) / 2.0
_INV_PHI = 1.0 / _PHI

_GOLDEN_PATH = (
    Path(__file__).parent / "fixtures" / "golden" / "place_ambisonics_order1_octa.yaml"
)

# Order -> (expected n, independently-recomputed RAW vertices) per the closed-form
# formulas. Recomputed here independently of the production module so a typo in
# either the test or the module fails the angle-precision assertion.
_REFERENCE_RAW: dict[int, list[tuple[float, float, float]]] = {
    1: [
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
    ],
    2: [
        (0.0, s1, s2 * _PHI)
        for s1 in (1.0, -1.0)
        for s2 in (1.0, -1.0)
    ]
    + [
        (s1, s2 * _PHI, 0.0)
        for s1 in (1.0, -1.0)
        for s2 in (1.0, -1.0)
    ]
    + [
        (s1 * _PHI, 0.0, s2)
        for s1 in (1.0, -1.0)
        for s2 in (1.0, -1.0)
    ],
    3: [
        (sx, sy, sz)
        for sx in (1.0, -1.0)
        for sy in (1.0, -1.0)
        for sz in (1.0, -1.0)
    ]
    + [
        (0.0, s1 * _INV_PHI, s2 * _PHI)
        for s1 in (1.0, -1.0)
        for s2 in (1.0, -1.0)
    ]
    + [
        (s1 * _INV_PHI, s2 * _PHI, 0.0)
        for s1 in (1.0, -1.0)
        for s2 in (1.0, -1.0)
    ]
    + [
        (s1 * _PHI, 0.0, s2 * _INV_PHI)
        for s1 in (1.0, -1.0)
        for s2 in (1.0, -1.0)
    ],
}
_EXPECTED_N = {1: 6, 2: 12, 3: 20}
_EXPECTED_NAME = {1: "octahedron", 2: "icosahedron", 3: "dodecahedron"}


def _unit_reference(order: int) -> np.ndarray:
    raw = np.array(_REFERENCE_RAW[order], dtype=float)
    return raw / np.linalg.norm(raw, axis=1, keepdims=True)


def _produced_unit_dirs(order: int, radius_m: float = 2.0) -> np.ndarray:
    res = place_ambisonics(order, radius_m=radius_m)
    pos = np.array([[s.position.x, s.position.y, s.position.z] for s in res.speakers])
    return pos / radius_m


@pytest.mark.parametrize("order", [1, 2, 3])
def test_angle_precision_under_5deg(order: int) -> None:
    """Each produced direction matches a reference vertex within << 5 deg."""
    produced = _produced_unit_dirs(order)
    reference = _unit_reference(order)
    assert produced.shape == reference.shape
    # Best-match pairing: every produced dir must have a reference dir within tol.
    cos = produced @ reference.T  # (n, n) cosine of angle between unit vectors
    best = np.clip(cos.max(axis=1), -1.0, 1.0)
    max_ang_rad = float(np.max(np.arccos(best)))
    assert max_ang_rad < 1e-6, f"order {order}: max angle err {max_ang_rad} rad"
    assert math.degrees(max_ang_rad) <= 5.0
    # Pairing is a bijection (each reference matched exactly once).
    assert len(set(int(i) for i in cos.argmax(axis=1))) == len(reference)


@pytest.mark.parametrize("order", [1, 2, 3])
def test_symmetry_equal_radii_and_centroid(order: int) -> None:
    res = place_ambisonics(order, radius_m=2.0)
    assert len(res.speakers) == _EXPECTED_N[order]
    dists = [
        math.sqrt(s.position.x**2 + s.position.y**2 + s.position.z**2)
        for s in res.speakers
    ]
    assert max(dists) - min(dists) < 1e-9
    for d in dists:
        assert abs(d - 2.0) < 1e-9
    dirs = _produced_unit_dirs(order)
    centroid = dirs.mean(axis=0)
    assert float(np.max(np.abs(centroid))) < 1e-9


@pytest.mark.parametrize("order", [1, 2, 3])
def test_quasi_isotropy_proxy(order: int) -> None:
    """Order-1 isotropy / spherical-2-design NECESSARY condition: M = (1/3)I, cond ~ 1.

    This asserts only the order-1 second-moment (a necessary, not sufficient,
    condition for SH decode conditioning at N>=2). The substantive guarantee is
    that these solids are high designs (octa 3-, ico/dode 5-design; see module
    docstring); this test does NOT compute a full SH-matrix condition number.
    NOTE: numpy-only — NOT a scipy SH condition number (scipy renamed
    ``sph_harm`` -> ``sph_harm_y`` in 1.15+, version-fragile); the second-moment
    proxy is exact for these symmetric rigs and avoids the coupling.
    """
    dirs = _produced_unit_dirs(order)
    n = dirs.shape[0]
    moment = dirs.T @ dirs / n
    assert float(np.max(np.abs(moment - np.eye(3) / 3.0))) < 1e-9
    assert float(np.linalg.cond(moment)) < 1.01


@pytest.mark.parametrize("order,n", [(1, 6), (2, 12), (3, 20)])
def test_n_speakers_meets_design_lower_bound(order: int, n: int) -> None:
    res = place_ambisonics(order)
    assert len(res.speakers) == n
    assert n >= (order + 1) ** 2


@pytest.mark.parametrize("order", [1, 2, 3])
def test_round_trip_label_preserved(order: int, tmp_path: Path) -> None:
    res = place_ambisonics(order)
    assert res.target_algorithm == "AMBISONICS"
    assert res.regularity_hint == "IRREGULAR"
    p = tmp_path / "layout.yaml"
    write_layout_yaml(res, p, validate=False)
    back = read_placement_yaml(p)
    assert back.target_algorithm == "AMBISONICS"
    assert back.regularity_hint == "IRREGULAR"
    assert len(back.speakers) == len(res.speakers)
    # write -> read -> write fixed point: byte-identical re-emission (D50).
    p2 = tmp_path / "layout2.yaml"
    write_layout_yaml(back, p2, validate=False)
    assert p.read_bytes() == p2.read_bytes()
    for a, b in zip(res.speakers, back.speakers):
        assert b.position.x == pytest.approx(a.position.x, abs=1e-9)
        assert b.position.y == pytest.approx(a.position.y, abs=1e-9)
        assert b.position.z == pytest.approx(a.position.z, abs=1e-9)


@pytest.mark.parametrize("order", [1, 2, 3])
def test_write_preflight_succeeds(order: int, tmp_path: Path) -> None:
    """R10 (IRREGULAR min=1) + R11 finite-sweep pass for every order."""
    res = place_ambisonics(order)
    p = tmp_path / "layout.yaml"
    write_layout_yaml(res, p, validate=False)
    assert p.is_file()


def test_order1_golden_byte_equal(tmp_path: Path) -> None:
    """order 1 octahedron reproduces the frozen golden byte-for-byte."""
    res = place_ambisonics(1, radius_m=2.0)
    out = tmp_path / "place_ambisonics_order1_octa.yaml"
    write_layout_yaml(res, out, validate=False)
    assert _GOLDEN_PATH.is_file(), f"golden fixture missing: {_GOLDEN_PATH}"
    assert out.read_bytes() == _GOLDEN_PATH.read_bytes()


@pytest.mark.parametrize("bad", [0, 4, -1])
def test_invalid_order_raises(bad: int) -> None:
    with pytest.raises(ValueError, match="kErrTooFewSpeakers"):
        place_ambisonics(bad)


def test_dispatch_requires_order() -> None:
    from roomestim.model import (
        ListenerArea,
        Point2,
        RoomModel,
    )

    # ambisonics is geometry-blind; this minimal room is never consumed.
    room = RoomModel(
        name="t",
        floor_polygon=[
            Point2(0.0, 0.0),
            Point2(4.0, 0.0),
            Point2(4.0, 4.0),
            Point2(0.0, 4.0),
        ],
        ceiling_height_m=3.0,
        surfaces=[],
        listener_area=ListenerArea(
            polygon=[
                Point2(1.0, 1.0),
                Point2(3.0, 1.0),
                Point2(3.0, 3.0),
                Point2(1.0, 3.0),
            ],
            centroid=Point2(2.0, 2.0),
            height_m=1.2,
        ),
    )
    with pytest.raises(ValueError, match="--order"):
        run_placement(room, "ambisonics", 8, 2.0, 0.0, order=None)
    # With order it dispatches to place_ambisonics.
    res = run_placement(room, "ambisonics", 8, 2.0, 0.0, order=2)
    assert res.target_algorithm == "AMBISONICS"
    assert len(res.speakers) == 12


def test_cli_disclosure_always_printed(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(algorithm="ambisonics", order=2, el_deg=0.0, n_speakers=8)
    _maybe_print_ambisonics_notes(args)
    err = capsys.readouterr().err
    assert AMBISONICS_RIG_DISCLOSURE in err
    assert "UNCONFIRMED" in err
    assert "WARNING:" not in err  # no ignored knobs -> no warn


def test_cli_warns_on_ignored_knobs(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(algorithm="ambisonics", order=2, el_deg=30.0, n_speakers=8)
    _maybe_print_ambisonics_notes(args)
    err = capsys.readouterr().err
    assert "WARNING:" in err
    assert "ignored for ambisonics" in err
    assert AMBISONICS_RIG_DISCLOSURE in err


def test_cli_notes_silent_for_non_ambisonics(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(algorithm="vbap", order=None, el_deg=0.0, n_speakers=8)
    _maybe_print_ambisonics_notes(args)
    assert capsys.readouterr().err == ""
