"""tests/web/test_binaural_renderer.py — Binaural renderer tests (Phase P13e).

Synthetic-data tests (no bundled SOFA or source WAV required):
  - test_binaural_render_returns_stereo_wav
  - test_binaural_render_peak_at_minus_1_dbfs

Real-data test (skipped until HUTUBS + source.wav are populated):
  - test_binaural_render_byte_exact_golden
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pytest.importorskip("pyroomacoustics")
pytest.importorskip("soundfile")
# pysofaconventions skip is per-test (real-data path); synthetic-data tests bypass

import numpy as np
import soundfile as sf

from roomestim.adapters import MeshAdapter
from roomestim.place.dispatch import run_placement


# ── Synthetic HRTF fixture — replaces real SOFA when data is absent ──────


@pytest.fixture
def synthetic_hrtf() -> object:
    """A minimal HrtfTable: 6 directions × 64-sample identity HRIRs.

    Lets the renderer run without bundling HUTUBS data.
    """
    from roomestim_web.hrtf_io import HrtfTable

    dirs = np.array(
        [
            [0, 0],  # front
            [90, 0],  # right
            [180, 0],  # back
            [270, 0],  # left
            [0, 90],  # above
            [0, -90],  # below
        ],
        dtype=np.float64,
    )
    M = dirs.shape[0]
    hrir_l = np.zeros((M, 64), dtype=np.float64)
    hrir_l[:, 0] = 1.0
    hrir_r = hrir_l.copy()
    return HrtfTable(
        sample_rate_hz=48000,
        directions=dirs,
        hrirs_left=hrir_l,
        hrirs_right=hrir_r,
        attribution="synthetic-test-fixture",
    )


@pytest.fixture
def synthetic_source_wav(tmp_path: Path) -> Path:
    """Generate a 30s mono 48kHz 16-bit WAV in tmp."""
    sr = 48000
    n = int(30.0 * sr)
    t = np.arange(n) / sr
    np.random.seed(0)
    sig = 0.3 * np.sin(2 * np.pi * 440 * t) + 0.05 * np.random.randn(n)
    sig = sig.astype(np.float32)
    p = tmp_path / "synthetic_source.wav"
    sf.write(str(p), sig, sr, subtype="PCM_16")
    return p


@pytest.fixture
def fixture_room_and_layout() -> tuple[object, object]:
    room = MeshAdapter().parse(
        "tests/fixtures/lab_room.obj", scale_anchor=None, octave_band=False
    )
    layout = run_placement(room, "vbap", 8, 2.0, 0.0)
    return room, layout


@pytest.mark.web
def test_binaural_render_returns_stereo_wav(
    fixture_room_and_layout: tuple[object, object],
    synthetic_hrtf: object,
    synthetic_source_wav: Path,
    tmp_path: Path,
) -> None:
    from roomestim_web.binaural import render_binaural_demo

    room, layout = fixture_room_and_layout
    out = render_binaural_demo(
        room,  # type: ignore[arg-type]
        layout,  # type: ignore[arg-type]
        synthetic_source_wav,
        tmp_path / "out.wav",
        hrtf=synthetic_hrtf,  # type: ignore[arg-type]
        max_order=2,
        duration_s=2.0,
    )
    audio, sr = sf.read(str(out), dtype="float32")
    assert sr == 48000
    assert audio.ndim == 2 and audio.shape[1] == 2
    # duration (2 s) + up to 2 s reverb tail per §5.2 step 7
    assert 2.0 * 48000 <= audio.shape[0] <= 4.0 * 48000


@pytest.mark.web
def test_binaural_render_peak_at_minus_1_dbfs(
    fixture_room_and_layout: tuple[object, object],
    synthetic_hrtf: object,
    synthetic_source_wav: Path,
    tmp_path: Path,
) -> None:
    from roomestim_web.binaural import render_binaural_demo

    room, layout = fixture_room_and_layout
    out = render_binaural_demo(
        room,  # type: ignore[arg-type]
        layout,  # type: ignore[arg-type]
        synthetic_source_wav,
        tmp_path / "out.wav",
        hrtf=synthetic_hrtf,  # type: ignore[arg-type]
        max_order=2,
        duration_s=2.0,
    )
    audio, _ = sf.read(str(out), dtype="float32")
    peak_dbfs = 20 * np.log10(max(float(np.abs(audio).max()), 1e-10))
    assert -1.2 <= peak_dbfs <= -0.8


@pytest.mark.web
def test_binaural_doa_axis_mapping() -> None:
    """Guard the per-image-source DOA axis + frame convention via the REAL
    helper ``_doa_az_el_deg`` (no re-implementation of its formula).

    D80: the renderer hands azimuth to ``nearest_hrir`` in SOFA/AmbiX convention
    (LEFT=+az). A source 1 m to the listener's RIGHT (+x, shoebox path) is +90°
    in pipeline convention, which ``coords.pipeline_to_ambix`` negates to az≈270°
    in SOFA convention. Elevation is convention-invariant. A right source
    returning az≈+90° here would mean the pipeline→SOFA negation was bypassed
    (the pre-D80 L↔R swap). The energy-grounded proof lives in
    ``test_binaural_ild_right_source_sofa`` and ``..._render_path`` below.
    """
    from roomestim_web.binaural import _doa_az_el_deg

    # Source to the RIGHT (+x) at ear height, shoebox pra frame [x, height, depth].
    az_deg, el_deg = _doa_az_el_deg(np.array([1.0, 0.0, 0.0]), is_shoebox_path=True)
    assert abs((az_deg % 360.0) - 270.0) < 0.1, (
        "right source must map to SOFA az≈270° (pipeline +90° negated); "
        f"got {az_deg:.1f}° — pipeline→SOFA negation bypassed (D80 swap)."
    )
    assert abs(el_deg) < 0.1

    # Mirror: source to the LEFT (-x) → SOFA az≈+90°.
    az_left, _ = _doa_az_el_deg(np.array([-1.0, 0.0, 0.0]), is_shoebox_path=True)
    assert abs((az_left % 360.0) - 90.0) < 0.1

    # Source 1 m directly above (shoebox up=rel[1]) → el≈+90°.
    _, el_up = _doa_az_el_deg(np.array([0.0, 1.0, 0.0]), is_shoebox_path=True)
    assert el_up > 85.0


@pytest.mark.web
def test_binaural_ild_right_source_sofa() -> None:
    """D80 dataset-grounded ILD regression — asserts against the real HRIR data,
    not the renderer's own formula.

    A source to the listener's RIGHT (+x) must, after the pipeline→SOFA azimuth
    conversion, select an HRIR whose RIGHT-ear energy exceeds the LEFT-ear energy
    (and the mirror for -x). This FAILS on the pre-D80 swapped code (which fed
    SOFA-lookup a pipeline-convention azimuth, mirroring L↔R) and PASSES after.
    """
    from roomestim.coords import pipeline_to_ambix
    from roomestim_web.binaural import _doa_az_el_deg
    from roomestim_web.hrtf_io import load_default_hrtf, nearest_hrir

    try:
        hrtf = load_default_hrtf()
    except FileNotFoundError:
        pytest.skip("no default HRTF (HUTUBS/KEMAR) bundled in this checkout")

    # Right source (+x): real renderer DOA → real nearest_hrir on real data.
    az_r, el_r = _doa_az_el_deg(np.array([1.0, 0.0, 0.0]), is_shoebox_path=True)
    l_r, r_r = nearest_hrir(hrtf, az_r, el_r)
    eL_r = float(np.sum(l_r ** 2))
    eR_r = float(np.sum(r_r ** 2))
    assert eR_r > eL_r, (
        f"right (+x) source: RIGHT-ear energy must dominate; got L={eL_r:.4g} "
        f"R={eR_r:.4g} at SOFA az={az_r:.1f}°. R<L means the L↔R swap (D80)."
    )

    # Left source (-x): mirror — LEFT-ear energy dominates.
    az_l, el_l = _doa_az_el_deg(np.array([-1.0, 0.0, 0.0]), is_shoebox_path=True)
    l_l, r_l = nearest_hrir(hrtf, az_l, el_l)
    eL_l = float(np.sum(l_l ** 2))
    eR_l = float(np.sum(r_l ** 2))
    assert eL_l > eR_l, (
        f"left (-x) source: LEFT-ear energy must dominate; got L={eL_l:.4g} "
        f"R={eR_l:.4g} at SOFA az={az_l:.1f}°."
    )

    # The conversion authority itself: pipeline +90° (right) negates to 270°.
    az_sofa, _ = pipeline_to_ambix(np.pi / 2.0, 0.0)
    assert abs((np.degrees(az_sofa) % 360.0) - 270.0) < 1e-6


@pytest.mark.web
def test_binaural_ild_right_source_render_path() -> None:
    """D80 end-to-end ILD regression through ``render_binaural_demo``.

    Places a single speaker 1 m to the listener's RIGHT (+x) in a shoebox and
    runs the REAL render path with the REAL default HRTF. The direct sound is the
    dominant component, so the RIGHT output channel must carry more energy than
    the LEFT. Mirror for -x. Fails pre-D80 (swapped), passes after.
    """
    from roomestim.model import PlacedSpeaker, PlacementResult, Point3
    from roomestim_web.binaural import render_binaural_demo
    from roomestim_web.hrtf_io import load_default_hrtf
    from tests.fixtures.synthetic_rooms import shoebox

    try:
        hrtf = load_default_hrtf()
    except FileNotFoundError:
        pytest.skip("no default HRTF (HUTUBS/KEMAR) bundled in this checkout")

    import tempfile

    room = shoebox(width=6.0, depth=6.0, height=2.8)
    listener_h = room.listener_area.height_m

    def _render_channel_energy(dx: float) -> tuple[float, float]:
        spk = PlacedSpeaker(
            channel=0,
            position=Point3(dx, listener_h, 0.0),  # +x = right, same height/front
        )
        layout = PlacementResult(
            target_algorithm="VBAP",
            regularity_hint="REGULAR",
            speakers=[spk],
            layout_name="ild_single",
        )
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.wav"
            sr = 48000
            n = sr  # 1 s
            np.random.seed(0)
            sig = (0.3 * np.random.randn(n)).astype(np.float32)
            sf.write(str(src), sig, sr, subtype="PCM_16")
            out = render_binaural_demo(
                room,  # type: ignore[arg-type]
                layout,  # type: ignore[arg-type]
                src,
                Path(td) / "out.wav",
                hrtf=hrtf,
                max_order=0,  # direct sound only — isolate the DOA component
                duration_s=1.0,
            )
            audio, _ = sf.read(str(out), dtype="float64")
        return float(np.sum(audio[:, 0] ** 2)), float(np.sum(audio[:, 1] ** 2))

    eL_right, eR_right = _render_channel_energy(+2.0)
    assert eR_right > eL_right, (
        "right (+x) speaker: RIGHT channel must dominate the rendered output; "
        f"got L={eL_right:.4g} R={eR_right:.4g}. R<L means the L↔R swap (D80)."
    )

    eL_left, eR_left = _render_channel_energy(-2.0)
    assert eL_left > eR_left, (
        "left (-x) speaker: LEFT channel must dominate; "
        f"got L={eL_left:.4g} R={eR_left:.4g}."
    )


@pytest.mark.web
def test_binaural_doa_elevation_nonshoebox_real_path(
    synthetic_hrtf: object,
    synthetic_source_wav: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX-2 / D75: in a NON-shoebox (extrusion) room, a source placed directly
    above the listener must yield a positive DOA elevation.

    Runs the real renderer and spies on the actual ``nearest_hrir`` calls (no
    re-implementation of the DOA formula). The pre-fix code assumed the shoebox
    pra-axis layout unconditionally, mapping the extrusion height axis to the
    azimuth plane, so an overhead source rendered at el≈0 instead of el>0.
    """
    import roomestim_web.hrtf_io as hrtf_io

    from roomestim.model import PlacedSpeaker, PlacementResult, Point3
    from tests.fixtures.synthetic_rooms import l_shape_room

    room = l_shape_room()
    assert not _is_extrusion_shoebox(room), "L-shape fixture must be non-shoebox"

    # Single speaker placed ~0.8 m directly above the listener centroid.
    centroid = room.listener_area.centroid
    listener_h = room.listener_area.height_m
    overhead = PlacedSpeaker(
        channel=0,
        position=Point3(centroid.x, listener_h + 0.8, centroid.z),
    )
    layout = PlacementResult(
        target_algorithm="VBAP",
        regularity_hint="REGULAR",
        speakers=[overhead],
        layout_name="overhead_single",
    )

    captured: list[tuple[float, float]] = []
    real_nearest = hrtf_io.nearest_hrir

    def _spy(table: object, az_deg: float, el_deg: float) -> object:
        captured.append((az_deg, el_deg))
        return real_nearest(table, az_deg, el_deg)  # type: ignore[arg-type]

    monkeypatch.setattr(hrtf_io, "nearest_hrir", _spy)

    from roomestim_web.binaural import render_binaural_demo

    render_binaural_demo(
        room,  # type: ignore[arg-type]
        layout,  # type: ignore[arg-type]
        synthetic_source_wav,
        tmp_path / "out.wav",
        hrtf=synthetic_hrtf,  # type: ignore[arg-type]
        max_order=1,
        duration_s=1.0,
    )

    assert captured, "renderer must compute at least one DOA"
    max_el = max(el for _, el in captured)
    assert max_el > 45.0, (
        "overhead source in a non-shoebox room must produce a high positive "
        f"elevation DOA; got max el={max_el:.1f}° across {len(captured)} images. "
        "A near-zero max elevation indicates the az/el axis swap (FIX-2)."
    )


def _is_extrusion_shoebox(room: object) -> bool:
    from roomestim_web.binaural import _is_rectilinear_shoebox

    return _is_rectilinear_shoebox(room.floor_polygon)  # type: ignore[attr-defined]


@pytest.mark.web
@pytest.mark.skipif(
    not (
        Path("roomestim_web/data/hrtf/hutubs_pp1.sofa").exists()
        and Path("roomestim_web/data/audio/source.wav").exists()
    ),
    reason=(
        "HUTUBS/source data not bundled in this checkout "
        "(P13e data-bundle step pending)."
    ),
)
def test_binaural_render_byte_exact_golden(
    fixture_room_and_layout: tuple[object, object], tmp_path: Path
) -> None:
    """Golden-file regression — pinned SHA-256 once real data is bundled.

    Skipped until the SOFA + source WAV are populated and the hash is recorded.
    """
    from roomestim_web.binaural import render_binaural_demo
    from roomestim_web.hrtf_io import load_default_hrtf

    room, layout = fixture_room_and_layout
    out = render_binaural_demo(
        room,  # type: ignore[arg-type]
        layout,  # type: ignore[arg-type]
        Path("roomestim_web/data/audio/source.wav"),
        tmp_path / "out.wav",
        hrtf=load_default_hrtf(),
        max_order=10,
        duration_s=30.0,
        seed=0,
    )
    golden_path = Path("tests/web/golden/binaural_pp1_shoebox.sha256")
    actual_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    if not golden_path.exists():
        pytest.skip(f"golden hash not yet recorded; actual SHA-256 = {actual_sha}")
    golden_sha = golden_path.read_text().strip()
    assert actual_sha == golden_sha
