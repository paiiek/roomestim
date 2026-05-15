"""roomestim_web.binaural — Per-image-source binaural renderer.

Renders a mono source clip through a pyroomacoustics ISM simulation and
binauralizes each image source via HRTF convolution + time-align + sum.
Output: 48 kHz, 16-bit, stereo WAV peak-normalized to -1 dBFS.

pyroomacoustics and soundfile are required (not lazy); both are present in
the roomestim conda environment. pysofaconventions is only needed if a real
SOFA HRTF is requested (via load_default_hrtf / load_hutubs / load_kemar).
"""
from __future__ import annotations

import math
from math import gcd
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import numpy as np
import pyroomacoustics as pra  # type: ignore[import-untyped]
import soundfile as sf  # type: ignore[import-untyped]
from scipy.signal import fftconvolve, resample_poly  # type: ignore[import-untyped]

# VBAP ring placement default puts speakers at y=0 (floor plane). The binaural
# renderer treats any speaker below this threshold as "no explicit elevation"
# and lifts to listener ear height for a perceptually sensible demo. This
# affects ONLY the rendered audio; layout.yaml exports the user-placed y.
_VBAP_FLOOR_SENTINEL_M: float = 0.01

if TYPE_CHECKING:
    from roomestim.model import PlacementResult, Point2, RoomModel, Surface
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

    # pra uses (x, z) floor corners (2D), then extrudes along y
    corners = np.array(
        [[p.x, p.z] for p in room.floor_polygon],
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

    room_pra.extrude(room.ceiling_height_m, materials=[floor_mat, ceil_mat])
    return room_pra


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
    for s_idx, pra_source in enumerate(room_pra.sources):
        images = pra_source.images  # shape (3, N_images)
        damping = pra_source.damping  # shape (n_bands, N_images) or (N_images,)
        n_images = images.shape[1]

        # Collapse multi-band damping to the 500 Hz reference band for
        # consistency with the rest of roomestim (Sabine 500 Hz, ADR 0021).
        # pra.Material(scalar) produces 1 band; band dict produces 6 bands
        # at center_freqs=[125, 250, 500, 1000, 2000, 4000] → band index 2.
        if damping.ndim == 2:
            damp_scalar = damping[2] if damping.shape[0] >= 6 else damping[0]
        else:
            damp_scalar = damping  # shape (N_images,)

        for i in range(n_images):
            img_pos = images[:, i]  # (x, y, z) in pra frame
            rel = img_pos - listener_pos

            dist = float(np.linalg.norm(rel))
            if dist < 1e-6:
                continue

            # Azimuth: atan2(x, z) → front=0, right=+90
            az_deg = math.degrees(math.atan2(float(rel[0]), float(rel[2])))
            # Elevation: atan2(y, sqrt(x²+z²))
            horiz = math.sqrt(float(rel[0]) ** 2 + float(rel[2]) ** 2)
            el_deg = math.degrees(math.atan2(float(rel[1]), horiz))

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
