"""roomestim_web.binaural — Per-image-source binaural renderer.

Renders a mono source clip through a pyroomacoustics ISM simulation and
binauralizes each image source via HRTF convolution + time-align + sum.
Output: 48 kHz, 16-bit, stereo WAV peak-normalized to -1 dBFS.

pyroomacoustics and soundfile are required (not lazy); both are present in
the roomestim conda environment. pysofaconventions is only needed if a real
SOFA HRTF is requested (via load_default_hrtf / load_hutubs / load_kemar).
"""
from __future__ import annotations

import logging
import math
from math import gcd
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import numpy as np
import pyroomacoustics as pra  # type: ignore[import-untyped]
import soundfile as sf  # type: ignore[import-untyped]
from scipy.signal import fftconvolve, resample_poly  # type: ignore[import-untyped]

_LOG = logging.getLogger("roomestim_web.binaural")

# VBAP ring placement default puts speakers at y=0 (floor plane). The binaural
# renderer treats any speaker below this threshold as "no explicit elevation"
# and lifts to listener ear height for a perceptually sensible demo. This
# affects ONLY the rendered audio; layout.yaml exports the user-placed y.
_VBAP_FLOOR_SENTINEL_M: float = 0.01

if TYPE_CHECKING:
    from roomestim.model import PlacementResult, Point2, Point3, RoomModel, Surface
    from roomestim_web.hrtf_io import HrtfTable


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_pra_material(surf: "Surface") -> Any:
    """Convert a roomestim Surface to a pyroomacoustics Material."""
    if surf.absorption_bands is not None:
        return pra.Material(
            energy_absorption={
                "coeffs": list(surf.absorption_bands),
                "center_freqs": [125, 250, 500, 1000, 2000, 4000],
            }
        )
    return pra.Material(float(surf.absorption_500hz))


def _default_material(surfaces: Sequence["Surface"]) -> Any:
    """Pick the most common wall material from the surface list."""

    walls = [s for s in surfaces if s.kind == "wall"]
    if not walls:
        return pra.Material(0.10)
    from collections import Counter

    counts: Counter[float] = Counter(w.absorption_500hz for w in walls)
    common_alpha = counts.most_common(1)[0][0]
    for w in walls:
        if w.absorption_500hz == common_alpha:
            return _build_pra_material(w)
    return pra.Material(common_alpha)


def _image_inside_floor(
    image_xz: tuple[float, float], floor_polygon: Sequence["Point2"]
) -> bool:
    """True if image-source xz projection is inside the floor polygon."""
    from shapely.geometry import Point, Polygon

    poly = Polygon([(float(p.x), float(p.z)) for p in floor_polygon])
    return bool(poly.contains(Point(float(image_xz[0]), float(image_xz[1]))))


def _resolve_damping_scalar(damping: Any) -> Any:
    """Collapse multi-band damping array to a scalar-per-image.

    1-band → broadband; 6-band → 500 Hz reference (idx 2); arbitrary band count
    (e.g. pyroomacoustics 8-band default) → geometric mean across bands.
    """
    if damping.ndim == 1:
        return damping
    if damping.ndim == 2 and damping.shape[0] == 6:
        return damping[2]
    if damping.ndim == 2 and damping.shape[0] == 1:
        return damping[0]
    if damping.ndim == 2:
        return np.exp(np.mean(np.log(np.clip(damping, 1e-12, None)), axis=0))
    raise ValueError(f"unexpected damping shape {damping.shape}")


def _is_rectilinear_shoebox(floor_polygon: Sequence["Point2"]) -> bool:
    """Return True if the 4-point polygon is axis-aligned (shoebox)."""
    if len(floor_polygon) != 4:
        return False
    unique_x = len(set(round(p.x, 6) for p in floor_polygon))
    unique_z = len(set(round(p.z, 6) for p in floor_polygon))
    return unique_x == 2 and unique_z == 2


def _build_shoebox_room(
    room: "RoomModel",
    fs: int,
    max_order: int,
) -> Any:
    """Build a pra.ShoeBox from a rectilinear RoomModel."""

    pts = room.floor_polygon
    xs = sorted(set(round(p.x, 6) for p in pts))
    zs = sorted(set(round(p.z, 6) for p in pts))
    width = abs(xs[1] - xs[0])
    depth = abs(zs[1] - zs[0])
    height = room.ceiling_height_m

    surfaces = room.surfaces
    floor_surf = next((s for s in surfaces if s.kind == "floor"), None)
    ceil_surf = next((s for s in surfaces if s.kind == "ceiling"), None)
    wall_mat = _default_material(surfaces)

    materials = {
        "floor": _build_pra_material(floor_surf) if floor_surf else pra.Material(0.10),
        "ceiling": _build_pra_material(ceil_surf) if ceil_surf else pra.Material(0.10),
        "east": wall_mat,
        "west": wall_mat,
        "north": wall_mat,
        "south": wall_mat,
    }

    return pra.ShoeBox(
        [width, height, depth],
        fs=fs,
        max_order=max_order,
        materials=materials,
        ray_tracing=False,
    )


def _build_extrusion_room(
    room: "RoomModel",
    fs: int,
    max_order: int,
) -> Any:
    """Build a pra.Room via from_corners + extrude for non-shoebox rooms."""

    # pra uses (x, z) floor corners (2D), then extrudes along y. FIX-2 cross-fix:
    # offset corners by the polygon min so they share the frame that `_to_pra`
    # (and the image-containment back-conversion at the call site) assume — the
    # prior un-offset corners placed every source outside the room polygon, so
    # `add_source` raised before any DOA could be computed.
    pts = room.floor_polygon
    min_x = min(p.x for p in pts)
    min_z = min(p.z for p in pts)
    corners = np.array(
        [[p.x - min_x, p.z - min_z] for p in pts],
        dtype=np.float64,
    ).T  # shape (2, N)

    wall_mat = _default_material(room.surfaces)
    room_pra = pra.Room.from_corners(
        corners,
        fs=fs,
        max_order=max_order,
        materials=wall_mat,
    )

    floor_surf = next((s for s in room.surfaces if s.kind == "floor"), None)
    ceil_surf = next((s for s in room.surfaces if s.kind == "ceiling"), None)
    floor_mat = _build_pra_material(floor_surf) if floor_surf else pra.Material(0.10)
    ceil_mat = _build_pra_material(ceil_surf) if ceil_surf else pra.Material(0.10)

    # pyroomacoustics >= 0.7 expects extrude(materials=...) as a dict keyed by
    # 'floor'/'ceiling' (a list raises TypeError on 0.10.x). FIX-2 cross-fix:
    # the prior list form left the whole extrusion (non-shoebox) renderer path
    # un-runnable, which is why the DOA axis swap below went unguarded.
    room_pra.extrude(
        room.ceiling_height_m,
        materials={"floor": floor_mat, "ceiling": ceil_mat},
    )
    return room_pra


def _doa_az_el_deg(rel: np.ndarray, is_shoebox_path: bool) -> tuple[float, float]:
    """Compute SOFA-convention (az_deg, el_deg) for a listener-relative pra-frame
    vector, ready to hand to :func:`nearest_hrir`.

    Shared DOA geometry extracted from ``render_binaural_demo`` (binaural.py
    DOA block, D75 axis logic) so ``synthesize_brir`` reuses the same math
    without duplicating it.

    Axis layout (D75):
        shoebox   → pra frame [x, height, depth] : up=rel[1], front=rel[2]
        extrusion → pra frame [x, depth, height] : up=rel[2], front=rel[1]
        side=rel[0] in both.

    D80: ``atan2(side, front)`` is *pipeline*-convention azimuth (RIGHT=+az),
    but ``nearest_hrir`` indexes HRIRs by *SOFA/AmbiX* azimuth (LEFT=+az). The
    single sign-flip authority ``roomestim.coords.pipeline_to_ambix`` (az→−az)
    bridges the two; bypassing it mirrors every lateral component L↔R. Elevation
    is convention-invariant. We route through the authority here so coords.py is
    the actual single source of truth for the frame conversion.
    """
    from roomestim.coords import pipeline_to_ambix

    side = float(rel[0])
    if is_shoebox_path:
        up = float(rel[1])
        front = float(rel[2])
    else:
        up = float(rel[2])
        front = float(rel[1])
    az_pipe = math.atan2(side, front)
    horiz = math.sqrt(side ** 2 + front ** 2)
    el = math.atan2(up, horiz)
    az_sofa, el_sofa = pipeline_to_ambix(az_pipe, el)
    return math.degrees(az_sofa), math.degrees(el_sofa)


def _resample_audio(
    audio: np.ndarray, src_sr: int, dst_sr: int
) -> np.ndarray:
    """Resample mono float64 audio using scipy.signal.resample_poly."""
    if src_sr == dst_sr:
        return audio
    g = gcd(src_sr, dst_sr)
    return resample_poly(audio, dst_sr // g, src_sr // g)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_binaural_demo(
    room: "RoomModel",
    layout: "PlacementResult",
    source_wav_path: str | Path,
    out_path: str | Path,
    *,
    hrtf: "HrtfTable | None" = None,
    max_order: int = 10,
    sample_rate_hz: int = 48000,
    duration_s: float = 30.0,
    seed: int = 0,
) -> Path:
    """Render the source clip through the room (pyroomacoustics ISM) and
    binauralize via HRTF convolution per-image-source.

    Writes 48 kHz, 16-bit, stereo, peak-normalized to -1 dBFS WAV.
    Returns out_path as a Path.
    """

    np.random.seed(seed)

    # -- Load HRTF ----------------------------------------------------------
    if hrtf is None:
        from roomestim_web.hrtf_io import load_default_hrtf

        hrtf = load_default_hrtf()

    from roomestim_web.hrtf_io import nearest_hrir

    # -- Load source audio --------------------------------------------------
    source_raw, src_sr = sf.read(str(source_wav_path), dtype="float64", always_2d=False)
    if source_raw.ndim > 1:
        source_raw = source_raw[:, 0]  # force mono
    source_audio = _resample_audio(source_raw, src_sr, sample_rate_hz)

    duration_samples = int(round(duration_s * sample_rate_hz))
    if len(source_audio) > duration_samples:
        source_audio = source_audio[:duration_samples]
    elif len(source_audio) < duration_samples:
        source_audio = np.pad(source_audio, (0, duration_samples - len(source_audio)))

    # -- Build pyroomacoustics room -----------------------------------------
    if _is_rectilinear_shoebox(room.floor_polygon):
        room_pra = _build_shoebox_room(room, sample_rate_hz, max_order)
    else:
        room_pra = _build_extrusion_room(room, sample_rate_hz, max_order)

    # -- Coordinate offset: roomestim world → pra room frame ---------------
    # pra ShoeBox origin is at one corner; roomestim polygon may be centred at 0.
    # Offset all positions so the polygon min corner maps to (0,0,0) in pra.
    pts = room.floor_polygon
    min_x = min(p.x for p in pts)
    min_z = min(p.z for p in pts)
    is_shoebox_path = _is_rectilinear_shoebox(room.floor_polygon)

    def _to_pra(rx: float, ry: float, rz: float) -> list[float]:
        """Translate roomestim (x,y,z) → pra room coordinates.

        ShoeBox path: pra dims are [width, height, depth] → positions [x, y, z].
        Extrusion path: pra.Room.from_corners(corners_xz) + extrude(h) places
        height as the THIRD coordinate, so positions are [x, z, height]. The
        axis swap is required for non-shoebox rooms.
        """
        if is_shoebox_path:
            return [rx - min_x, ry, rz - min_z]
        return [rx - min_x, rz - min_z, ry]

    # -- Listener position: centroid at listener height ---------------------
    cx = room.listener_area.centroid.x
    cz = room.listener_area.centroid.z
    listener_height = room.listener_area.height_m
    listener_pos_pra = np.array(_to_pra(cx, listener_height, cz), dtype=np.float64)
    # Keep world-frame listener for DOA computation (relative positions are the same)
    listener_pos = listener_pos_pra  # DOA uses relative vectors; offset cancels out

    # Add single mono microphone at listener centroid
    room_pra.add_microphone(listener_pos_pra.reshape(3, 1))

    # -- Add all speakers as sources ----------------------------------------
    width = max(p.x for p in pts) - min_x
    depth = max(p.z for p in pts) - min_z
    # Per-axis bounds for clamping inside pra room. ShoeBox: [w, h, d];
    # extrusion: [w, d, h] (see _to_pra). Build dim list to match.
    if is_shoebox_path:
        pra_dim_bounds = (width, room.ceiling_height_m, depth)
    else:
        pra_dim_bounds = (width, depth, room.ceiling_height_m)
    for spk in layout.speakers:
        sx = spk.position.x
        # VBAP ring places y=0 (floor plane) — lift to ear height so the demo
        # renders a perceptually sensible elevation. See _VBAP_FLOOR_SENTINEL_M
        # comment at module top.
        sy_raw = spk.position.y
        sy = sy_raw if sy_raw > _VBAP_FLOOR_SENTINEL_M else listener_height
        sz = spk.position.z
        pra_pos = _to_pra(sx, sy, sz)
        # Clamp strictly inside room bounds to avoid boundary rejection
        for axis in range(3):
            pra_pos[axis] = float(
                np.clip(pra_pos[axis], 0.01, pra_dim_bounds[axis] - 0.01)
            )
        room_pra.add_source(pra_pos, signal=source_audio)

    # -- Compute image sources ----------------------------------------------
    room_pra.image_source_model()

    # -- Pre-allocate output buffer -----------------------------------------
    max_hrir_len = hrtf.hrirs_left.shape[1]
    # Generous buffer: duration + HRIR tail + maximum possible delay
    # Max delay: room diagonal × max_order / speed of sound
    max_dim = math.sqrt(width ** 2 + room.ceiling_height_m ** 2 + depth ** 2) * max_order
    max_delay = int(max_dim / 343.0 * sample_rate_hz) + 1
    buf_len = duration_samples + max_hrir_len + max_delay + 1024

    out_left = np.zeros(buf_len, dtype=np.float64)
    out_right = np.zeros(buf_len, dtype=np.float64)

    # -- Per-image-source binaural accumulation ----------------------------
    total_dropped_images = 0
    for s_idx, pra_source in enumerate(room_pra.sources):
        images = pra_source.images  # shape (3, N_images)
        damping = pra_source.damping  # shape (n_bands, N_images) or (N_images,)
        n_images = images.shape[1]

        # Collapse multi-band damping to the 500 Hz reference band for
        # consistency with the rest of roomestim (Sabine 500 Hz, ADR 0021).
        # pra.Material(scalar) produces 1 band; band dict produces 6 bands
        # at center_freqs=[125, 250, 500, 1000, 2000, 4000] → band index 2.
        damp_scalar = _resolve_damping_scalar(damping)

        for i in range(n_images):
            img_pos = images[:, i]  # (x, y, z) in pra frame

            # For non-shoebox (extrusion) rooms, drop image sources whose xz
            # projection falls outside the floor polygon. The extrusion path
            # uses pra coordinates (x, z, height), so xz is img_pos[0], img_pos[1].
            if not is_shoebox_path:
                # Convert pra coords back to roomestim world frame for containment
                img_x_world = float(img_pos[0]) + min_x
                img_z_world = float(img_pos[1]) + min_z
                if not _image_inside_floor((img_x_world, img_z_world), room.floor_polygon):
                    total_dropped_images += 1
                    continue

            rel = img_pos - listener_pos

            dist = float(np.linalg.norm(rel))
            if dist < 1e-6:
                continue

            # FIX-2 / D75: DOA axes are geometry-path dependent (see
            # _doa_az_el_deg). D80: that helper also routes the azimuth through
            # coords.pipeline_to_ambix so the SOFA lookup gets SOFA-convention
            # azimuth (RIGHT=+az pipeline → LEFT=+az SOFA). The demo path now
            # shares the helper instead of re-deriving the geometry, making the
            # frame conversion single-sourced for both render paths.
            az_deg, el_deg = _doa_az_el_deg(rel, is_shoebox_path)

            hrir_l, hrir_r = nearest_hrir(hrtf, az_deg, el_deg)

            # Delay in samples (integer, causal)
            n_delay = int(round(dist / 343.0 * sample_rate_hz))

            # Gain: damping / distance (1/r geometric spreading)
            g = float(damp_scalar[i]) / max(dist, 0.1)

            # Convolve + scale
            conv_l = fftconvolve(source_audio, hrir_l, mode="full") * g
            conv_r = fftconvolve(source_audio, hrir_r, mode="full") * g

            end_l = n_delay + len(conv_l)
            end_r = n_delay + len(conv_r)

            if n_delay < buf_len:
                actual_end_l = min(end_l, buf_len)
                actual_end_r = min(end_r, buf_len)
                out_left[n_delay:actual_end_l] += conv_l[: actual_end_l - n_delay]
                out_right[n_delay:actual_end_r] += conv_r[: actual_end_r - n_delay]

    if total_dropped_images >= 1:
        _LOG.warning(
            "render_binaural_demo: dropped %d image source(s) outside floor polygon"
            " (non-rectilinear extrusion room).",
            total_dropped_images,
        )

    # -- Trim to duration + reverb tail -------------------------------------
    # Spec §5.2 step 7: keep up to 2 s of late-arriving reflection tail so
    # the room's reverberation is audible past the dry-source duration.
    tail_samples = 2 * sample_rate_hz
    output_len = min(duration_samples + tail_samples, buf_len)
    out_left = out_left[:output_len]
    out_right = out_right[:output_len]

    # -- Peak-normalize to -1 dBFS -----------------------------------------
    target_peak = 10 ** (-1.0 / 20)  # ≈ 0.8913
    peak = max(float(np.abs(out_left).max()), float(np.abs(out_right).max()), 1e-10)
    out_left = out_left * (target_peak / peak)
    out_right = out_right * (target_peak / peak)

    # -- Write stereo WAV ---------------------------------------------------
    stereo = np.stack([out_left, out_right], axis=1)  # (N, 2)
    out_path = Path(out_path)
    sf.write(str(out_path), stereo, sample_rate_hz, subtype="PCM_16")

    return out_path


# ---------------------------------------------------------------------------
# Phase A auralization — BRIR synthesis (ADR 0044 §D)
# ---------------------------------------------------------------------------


def _diffuse_decorrelation_filters(
    n_taps: int,
    interaural_distance_m: float,
    fs: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Two short FIR filters whose cross-correlation targets the diffuse-field
    interaural coherence ``IC(f) = sinc(2*pi*f*d/c)`` (ADR 0044 §D, Gate 1).

    Deterministic given ``seed``. This is a NAMED design parameter, not a
    verified perceptual claim (OQ-47 verification-deferred). The two filters
    are built from a shared white sequence whose left/right copies are mixed to
    realise the target magnitude-squared coherence per frequency bin.
    """
    rng = np.random.default_rng(seed)
    n = max(int(n_taps), 1)
    # Frequency grid for an n-point real FFT.
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    c = 343.0
    ic = np.sinc(2.0 * freqs * interaural_distance_m / c)  # np.sinc(x)=sin(pi x)/(pi x)
    ic = np.clip(ic, -1.0, 1.0)
    # Coherence-mixing weights: shared component sqrt(|IC|), independent sqrt(1-|IC|).
    w_shared = np.sqrt(np.abs(ic))
    w_indep = np.sqrt(np.clip(1.0 - np.abs(ic), 0.0, 1.0))
    sign = np.sign(ic)
    sign[sign == 0] = 1.0

    shared = rng.standard_normal(len(freqs)) + 1j * rng.standard_normal(len(freqs))
    indep_l = rng.standard_normal(len(freqs)) + 1j * rng.standard_normal(len(freqs))
    indep_r = rng.standard_normal(len(freqs)) + 1j * rng.standard_normal(len(freqs))

    spec_l = w_shared * shared + w_indep * indep_l
    spec_r = w_shared * sign * shared + w_indep * indep_r

    fir_l = np.fft.irfft(spec_l, n=n)
    fir_r = np.fft.irfft(spec_r, n=n)
    # Normalize each to unit energy so the decorrelator does not change level.
    fir_l = fir_l / max(float(np.sqrt(np.sum(fir_l ** 2))), 1e-12)
    fir_r = fir_r / max(float(np.sqrt(np.sum(fir_r ** 2))), 1e-12)
    return fir_l, fir_r


def synthesize_brir(
    room: "RoomModel",
    listener_pos_world: "Point3 | tuple[float, float, float] | None" = None,
    *,
    hrtf: "HrtfTable | None" = None,
    rt60_per_band_s: dict[int, float] | None = None,
    max_order: int = 10,
    sample_rate_hz: int = 48000,
    interaural_distance_m: float = 0.18,
    seed: int = 0,
) -> np.ndarray:
    """Synthesize a 2-channel convolvable BRIR, shape ``(2, L_total)``.

    Phase A hybrid path (ADR 0044): ISM early (per-image DOA → ``nearest_hrir``,
    6-band weighted) + filtered-noise late (per-band, ``rir.assemble_mono_rir_per_band``
    energy-continuity splice) → diffuse 2-HRIR decorrelation tail
    (``IC(f) = sinc(2*pi*f*d/c)``). The 6 octave bands are preserved end-to-end;
    RT60 truth is ``predict_rt60_default_per_band`` (the single source). The
    diffuse tail is *plausible*, not a verified perceptual claim (OQ-47).

    Args:
        room: roomestim room model.
        listener_pos_world: world (x, y, z) listener point. Defaults to the
            listener-area centroid at ``listener_area.height_m``.
        hrtf: HRTF table; defaults to ``load_default_hrtf()``.
        rt60_per_band_s: per-band RT60; if ``None``, computed via
            ``predict_rt60_default_per_band`` (falls back to a uniform per-band
            map only if that predictor returns an empty per-band dict).
        max_order: ISM reflection order.
        sample_rate_hz: output sample rate.
        interaural_distance_m: head width for the diffuse IC target curve.
        seed: deterministic seed (byte-equal reproducible).
    """
    import dataclasses

    from roomestim.model import MaterialAbsorptionBands
    from roomestim_web.hrtf_io import nearest_hrir
    from roomestim_web.late_reverb import recombine_bands
    from roomestim_web.rir import (
        _SPLICE_WINDOW_S,
        assemble_mono_rir_per_band,
        mixing_time_s,
    )

    # Phase A requires per-band pra damping (the spike showed scalar materials
    # yield a 1-band damping array). Promote every surface to 6-band absorption
    # (from MaterialAbsorptionBands, falling back to a flat a500 row) so the
    # band-grid guard in rir.py is satisfied. Additive; the demo path is untouched.
    def _ensure_band_materials(r: "RoomModel") -> "RoomModel":
        new_surfaces = []
        for surf in r.surfaces:
            if surf.absorption_bands is not None:
                new_surfaces.append(surf)
                continue
            bands = MaterialAbsorptionBands.get(
                surf.material, (surf.absorption_500hz,) * 6
            )
            new_surfaces.append(dataclasses.replace(surf, absorption_bands=bands))
        return dataclasses.replace(r, surfaces=new_surfaces)

    room = _ensure_band_materials(room)

    if hrtf is None:
        from roomestim_web.hrtf_io import load_default_hrtf

        hrtf = load_default_hrtf()

    # -- Resolve per-band RT60 (single truth source) ------------------------
    if rt60_per_band_s is None:
        from roomestim.reconstruct.predictor import predict_rt60_default_per_band
        from roomestim_web.report import _surface_areas_by_material

        pred = predict_rt60_default_per_band(room, _surface_areas_by_material(room))
        rt60_per_band_s = dict(pred.rt60_per_band_s)
        if not rt60_per_band_s:
            # Non-shoebox Eyring fallback returns an empty per-band dict; map the
            # broadband RT60 onto all 6 octave bands so the per-band tail is
            # well-defined (keeps the 6-band invariant, no scalar collapse downstream).
            from roomestim.model import OCTAVE_BANDS_HZ

            rt60_per_band_s = {b: float(pred.rt60_s) for b in OCTAVE_BANDS_HZ}

    # -- Build pra room (reuse demo builders; do not duplicate) -------------
    is_shoebox_path = _is_rectilinear_shoebox(room.floor_polygon)
    if is_shoebox_path:
        room_pra = _build_shoebox_room(room, sample_rate_hz, max_order)
    else:
        room_pra = _build_extrusion_room(room, sample_rate_hz, max_order)

    pts = room.floor_polygon
    min_x = min(p.x for p in pts)
    min_z = min(p.z for p in pts)

    def _to_pra(rx: float, ry: float, rz: float) -> list[float]:
        if is_shoebox_path:
            return [rx - min_x, ry, rz - min_z]
        return [rx - min_x, rz - min_z, ry]

    # Listener position.
    if listener_pos_world is None:
        cx = room.listener_area.centroid.x
        cz = room.listener_area.centroid.z
        ly = room.listener_area.height_m
    elif hasattr(listener_pos_world, "x"):
        cx = float(listener_pos_world.x)  # type: ignore[union-attr]
        ly = float(listener_pos_world.y)  # type: ignore[union-attr]
        cz = float(listener_pos_world.z)  # type: ignore[union-attr]
    else:
        cx = float(listener_pos_world[0])
        ly = float(listener_pos_world[1])
        cz = float(listener_pos_world[2])
    listener_pos = np.array(_to_pra(cx, ly, cz), dtype=np.float64)
    room_pra.add_microphone(listener_pos.reshape(3, 1))

    # Single deterministic source: 1 m in front of the listener (+z world),
    # clamped strictly inside the room bounds.
    width = max(p.x for p in pts) - min_x
    depth = max(p.z for p in pts) - min_z
    if is_shoebox_path:
        pra_dim_bounds = (width, room.ceiling_height_m, depth)
    else:
        pra_dim_bounds = (width, depth, room.ceiling_height_m)
    src_world = (cx, ly, cz + 1.0)
    src_pra = _to_pra(*src_world)
    for axis in range(3):
        src_pra[axis] = float(np.clip(src_pra[axis], 0.01, pra_dim_bounds[axis] - 0.01))
    room_pra.add_source(src_pra, signal=np.array([1.0], dtype=np.float64))

    room_pra.image_source_model()

    # -- Per-band mono RIR (truth for length + splice continuity) -----------
    mono_per_band = assemble_mono_rir_per_band(
        room_pra,
        listener_pos,
        room,
        rt60_per_band_s,
        sample_rate_hz=sample_rate_hz,
        seed=seed,
    )  # (6, L_total)
    total_len = mono_per_band.shape[1]
    t_mix = int(round(mixing_time_s(room) * sample_rate_hz))
    t_mix = min(max(t_mix, 0), total_len)

    max_hrir_len = int(hrtf.hrirs_left.shape[1])
    out_len = total_len + max_hrir_len
    brir_l = np.zeros(out_len, dtype=np.float64)
    brir_r = np.zeros(out_len, dtype=np.float64)

    # -- EARLY (pre t_mix): per-image DOA → HRIR, 6-band weighted -----------
    from roomestim_web.rir import _band_grid_guard

    for pra_source in room_pra.sources:
        images = pra_source.images
        damping = _band_grid_guard(np.asarray(pra_source.damping, dtype=np.float64))
        n_images = images.shape[1]
        for i in range(n_images):
            rel = images[:, i] - listener_pos
            dist = float(np.linalg.norm(rel))
            if dist < 1e-6:
                continue
            n_delay = int(round(dist / 343.0 * sample_rate_hz))
            if n_delay >= t_mix:
                continue  # late part handled by the diffuse tail
            az_deg, el_deg = _doa_az_el_deg(rel, is_shoebox_path)
            hrir_l, hrir_r = nearest_hrir(hrtf, az_deg, el_deg)
            # Broadband gain = mean of the 6-band damping / distance.
            g = float(np.mean(damping[:, i])) / max(dist, 0.1)
            end = n_delay + len(hrir_l)
            if n_delay < out_len:
                actual_end = min(end, out_len)
                seg = actual_end - n_delay
                brir_l[n_delay:actual_end] += hrir_l[:seg] * g
                brir_r[n_delay:actual_end] += hrir_r[:seg] * g

    # -- LATE (post t_mix): recombine bands → diffuse 2-HRIR decorrelation --
    late_mono = recombine_bands(mono_per_band[:, t_mix:total_len])  # (L_late,)
    n_late = late_mono.shape[0]
    if n_late > 0:
        fir_l, fir_r = _diffuse_decorrelation_filters(
            min(256, n_late), interaural_distance_m, sample_rate_hz, seed
        )
        tail_l = fftconvolve(late_mono, fir_l, mode="full")
        tail_r = fftconvolve(late_mono, fir_r, mode="full")
        # Gate-3 splice continuity for the REAL BRIR (per channel). The per-band
        # mono splice (assemble_mono_rir_per_band) is normalized against the
        # HRIR-FREE early mono RIR, but each BRIR channel's early level carries
        # direction-dependent HRIR energy the mono reference never sees. Rescale
        # each channel's tail so its energy in the 5 ms window straddling t_mix
        # matches that channel's early BRIR energy in the 5 ms pre-t_mix window.
        window = max(int(round(_SPLICE_WINDOW_S * sample_rate_hz)), 1)
        for tail, brir_ch in ((tail_l, brir_l), (tail_r, brir_r)):
            lo = max(t_mix - window, 0)
            e_early = float(np.sum(brir_ch[lo:t_mix] ** 2))
            e_tail = float(np.sum(tail[:window] ** 2))
            if e_tail > 0.0 and e_early > 0.0:
                tail *= np.sqrt(e_early / e_tail)
        end = t_mix + len(tail_l)
        actual_end = min(end, out_len)
        seg = actual_end - t_mix
        brir_l[t_mix:actual_end] += tail_l[:seg]
        brir_r[t_mix:actual_end] += tail_r[:seg]

    return np.stack([brir_l, brir_r], axis=0)  # (2, L)
