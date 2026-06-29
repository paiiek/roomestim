"""SpeakerSpec data model + a DIRECT-FIELD-ONLY SPL engine (immersive-layout P1).

A :class:`SpeakerSpec` carries the few datasheet numbers needed to turn a placed
speaker into an absolute sound-pressure-level (SPL) prediction: the 1 W / 1 m
sensitivity, the maximum SPL, and a nominal coverage (dispersion) angle. From
those, :func:`direct_field_spl_db` evaluates the free-field inverse-square law
plus a SIMPLIFIED axisymmetric directivity roll-off, and
:func:`spl_field_over_area` energy-sums every speaker's direct-field contribution
over the listener area on an ear-plane lattice.

Honesty (load-bearing — :data:`SPL_DIRECT_FIELD_NOTE`)
------------------------------------------------------
This is a DIRECT-FIELD-ONLY model: NO reverberant field, NO room gain, NO
boundary reinforcement (so it under-estimates the real in-room SPL), and the
directivity is the AVIXA coverage-angle convention (0 dB on-axis, exactly -6 dB
at the coverage half-angle), NOT a measured polar pattern. Absolute SPL is only
meaningful when ``sensitivity_db_1w1m`` comes from a REAL datasheet
(``provenance="datasheet"``). The built-in :data:`BUILTIN_SPEAKER_CATALOG`
entries are representative ESTIMATEs (``provenance="estimate"``) for previewing
layouts only — they are NOT authoritative specifications.

numpy-free (stdlib ``math`` + shapely + yaml, all core deps); import-safe at
``import roomestim`` time (core / torch-free boundary).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

from roomestim.model import ListenerArea, PlacedSpeaker, Point3, assert_finite
from roomestim.reconstruct._disclosure import SPL_DIRECT_FIELD_NOTE

__all__ = [
    "SPL_DIRECT_FIELD_NOTE",
    "DEFAULT_GRID_RESOLUTION_M",
    "DIRECTIVITY_ATTEN_FLOOR_DB",
    "SpeakerProvenance",
    "SpeakerSpec",
    "SPLFieldScore",
    "BUILTIN_SPEAKER_CATALOG",
    "directivity_atten_db",
    "direct_field_spl_db",
    "spl_field_over_area",
    "spl_field_to_dict",
    "format_spl_field_lines",
    "load_speaker_spec",
    "load_speaker_catalog",
]

#: Default ear-plane sampling resolution (m) — mirrors coverage_overlap.
DEFAULT_GRID_RESOLUTION_M: float = 0.5

#: Floor on the directivity attenuation (dB) to avoid pathological values far
#: outside the coverage angle. -60 dB is already inaudible against the on-axis.
DIRECTIVITY_ATTEN_FLOOR_DB: float = -60.0

#: Provenance of a spec's numbers: ``"datasheet"`` (a real published spec) or
#: ``"estimate"`` (representative / placeholder, NOT authoritative).
SpeakerProvenance = Literal["datasheet", "estimate"]


@dataclass(frozen=True)
class SpeakerSpec:
    """The datasheet numbers needed to predict a speaker's direct-field SPL.

    Honesty: an absolute SPL is only meaningful when ``sensitivity_db_1w1m``
    comes from a REAL datasheet (``provenance="datasheet"``). ``"estimate"``
    values are representative placeholders for previewing only. See
    :data:`SPL_DIRECT_FIELD_NOTE`.
    """

    model: str
    sensitivity_db_1w1m: float  # dB SPL @ 1 W / 1 m (datasheet "sensitivity")
    max_spl_db: float           # max continuous / peak SPL @ 1 m (datasheet)
    dispersion_deg: float       # nominal -6 dB total coverage angle (axisymmetric)
    provenance: SpeakerProvenance = "estimate"
    price: float | None = None  # optional, for the cost trade-off axis (Phase 3)

    def __post_init__(self) -> None:
        assert_finite(self.sensitivity_db_1w1m, field="sensitivity_db_1w1m")
        assert_finite(self.max_spl_db, field="max_spl_db")
        assert_finite(self.dispersion_deg, field="dispersion_deg")
        if not (0.0 < self.dispersion_deg <= 360.0):
            raise ValueError(
                f"dispersion_deg must be in (0, 360], got {self.dispersion_deg}"
            )
        if self.price is not None:
            assert_finite(self.price, field="price")


def directivity_atten_db(spec: SpeakerSpec, off_axis_deg: float) -> float:
    """SIMPLIFIED axisymmetric directivity attenuation (dB) at ``off_axis_deg``.

    This is NOT a measured polar pattern. It is a smooth quadratic roll-off that
    follows the AVIXA coverage-angle convention: 0 dB on-axis and exactly -6 dB
    at the coverage half-angle (``dispersion_deg / 2``), i.e. the -6 dB total
    beamwidth equals ``dispersion_deg``::

        atten = -6.0 * (off_axis_deg / (dispersion_deg / 2)) ** 2

    The roll-off continues past the coverage edge (a real driver's lobing is not
    modelled) and is clamped to :data:`DIRECTIVITY_ATTEN_FLOOR_DB`. Symmetric in
    the sign of ``off_axis_deg``. See :data:`SPL_DIRECT_FIELD_NOTE`.
    """
    assert_finite(off_axis_deg, field="off_axis_deg")
    half_angle = spec.dispersion_deg / 2.0
    ratio = off_axis_deg / half_angle
    atten = -6.0 * ratio * ratio
    if atten < DIRECTIVITY_ATTEN_FLOOR_DB:
        return DIRECTIVITY_ATTEN_FLOOR_DB
    return atten


def direct_field_spl_db(
    spec: SpeakerSpec,
    *,
    drive_w: float,
    distance_m: float,
    off_axis_deg: float = 0.0,
) -> float:
    """Direct-field SPL (dB) of one speaker at ``distance_m`` and ``off_axis_deg``.

    Free-field inverse-square law plus the simplified directivity::

        spl = sensitivity_db_1w1m
              + 10*log10(drive_w)        # power: +10 dB per 10x watts
              - 20*log10(distance_m)     # distance: -6.02 dB per doubling
              + directivity_atten_db(spec, off_axis_deg)

    DIRECT FIELD ONLY — no reverberant field, room gain, or boundary
    reinforcement (see :data:`SPL_DIRECT_FIELD_NOTE`). Raises ``ValueError`` if
    ``drive_w`` or ``distance_m`` is non-finite or non-positive.
    """
    assert_finite(drive_w, field="drive_w")
    assert_finite(distance_m, field="distance_m")
    if drive_w <= 0.0:
        raise ValueError(f"drive_w must be > 0, got {drive_w}")
    if distance_m <= 0.0:
        raise ValueError(f"distance_m must be > 0, got {distance_m}")
    return (
        spec.sensitivity_db_1w1m
        + 10.0 * math.log10(drive_w)
        - 20.0 * math.log10(distance_m)
        + directivity_atten_db(spec, off_axis_deg)
    )


@dataclass(frozen=True)
class SPLFieldScore:
    """Direct-field SPL statistics over the listener area. NOT a measurement.

    See :data:`SPL_DIRECT_FIELD_NOTE`: direct-field only, simplified directivity,
    energy-summed assuming incoherent direct sound.
    """

    n_samples: int
    min_spl_db: float
    mean_spl_db: float
    max_spl_db: float
    uniformity_db: float            # = max_spl_db - min_spl_db
    worst_point_xz: tuple[float, float]  # lowest-SPL sample (x, z)
    exceeds_max_spl: bool  # peak area SPL > smallest contributing spec's max_spl_db
    note: str  # = SPL_DIRECT_FIELD_NOTE


def _spec_for_channel(
    specs: SpeakerSpec | dict[int, SpeakerSpec], channel: int
) -> SpeakerSpec:
    """Resolve the spec for one channel (single spec applies to all, or per-channel)."""
    if isinstance(specs, dict):
        try:
            return specs[channel]
        except KeyError as exc:
            raise ValueError(f"no SpeakerSpec for channel {channel}") from exc
    return specs


def _aim_unit_vector(
    speaker: PlacedSpeaker, listener_area: ListenerArea
) -> tuple[float, float, float]:
    """Unit aim vector: the speaker's ``aim_direction`` or, if absent, toward the
    listener-area centroid at ear height. Falls back to straight down if degenerate."""
    if speaker.aim_direction is not None:
        ax, ay, az = speaker.aim_direction.x, speaker.aim_direction.y, speaker.aim_direction.z
    else:
        ax = listener_area.centroid.x - speaker.position.x
        ay = listener_area.height_m - speaker.position.y
        az = listener_area.centroid.z - speaker.position.z
    # Reject a non-finite aim BEFORE normalising: a NaN/inf component would make
    # ``norm`` non-finite, slip past the ``norm <= 0.0`` guard, and downstream
    # collapse cos_off to a fake perfect-on-axis 1.0. Fail loudly instead.
    assert_finite(ax, field="aim_direction.x")
    assert_finite(ay, field="aim_direction.y")
    assert_finite(az, field="aim_direction.z")
    norm = math.sqrt(ax * ax + ay * ay + az * az)
    if norm <= 0.0:
        return (0.0, -1.0, 0.0)
    return (ax / norm, ay / norm, az / norm)


def spl_field_over_area(
    specs: SpeakerSpec | dict[int, SpeakerSpec],
    *,
    drive_w: float,
    speakers: list[PlacedSpeaker],
    listener_area: ListenerArea,
    grid_resolution_m: float = DEFAULT_GRID_RESOLUTION_M,
) -> SPLFieldScore:
    """Direct-field SPL field over the listener area on an ear-plane lattice.

    ``specs`` is a single :class:`SpeakerSpec` applied to every speaker, or a
    ``dict[channel -> SpeakerSpec]``. The listener polygon is sampled on a
    ``grid_resolution_m`` lattice (cell-centred symmetric inset, ``poly.covers``)
    at ``z = listener_area.height_m`` ear height — the SAME sampling as
    :func:`roomestim.place.coverage_overlap.score_coverage_overlap`. At each
    sample the total SPL is the ENERGY sum of every speaker's
    :func:`direct_field_spl_db` (3D distance; off-axis angle between the speaker's
    aim and the sample direction). Returns min / mean / max / uniformity over the
    covered samples and the lowest-SPL (worst) point.

    DIRECT FIELD ONLY (:data:`SPL_DIRECT_FIELD_NOTE`). Raises ``ValueError`` on no
    speakers, a degenerate polygon, or a non-positive resolution / drive power.
    """
    if not speakers:
        raise ValueError("spl_field_over_area requires >= 1 placed speaker")
    assert_finite(drive_w, field="drive_w")
    if drive_w <= 0.0:
        raise ValueError(f"drive_w must be > 0, got {drive_w}")
    assert_finite(grid_resolution_m, field="grid_resolution_m")
    if grid_resolution_m <= 0.0:
        raise ValueError(f"grid_resolution_m must be > 0, got {grid_resolution_m}")
    if len(listener_area.polygon) < 3:
        raise ValueError("spl field requires a listener polygon with >=3 vertices")
    poly = ShapelyPolygon([(p.x, p.z) for p in listener_area.polygon])
    if not poly.is_valid or poly.is_empty or poly.area <= 0.0:
        raise ValueError("degenerate listener polygon (zero area / self-intersecting)")

    ear_y = listener_area.height_m
    # Pre-resolve per-speaker (spec, position, unit aim vector).
    speaker_terms: list[tuple[SpeakerSpec, Point3, tuple[float, float, float]]] = []
    for sp in speakers:
        spec = _spec_for_channel(specs, sp.channel)
        speaker_terms.append((spec, sp.position, _aim_unit_vector(sp, listener_area)))

    # --- footprint sampling grid (cell-centred, symmetric inset) ----------- #
    minx, minz, maxx, maxz = poly.bounds
    nx = max(1, int(math.floor((maxx - minx) / grid_resolution_m)))
    nz = max(1, int(math.floor((maxz - minz) / grid_resolution_m)))
    x0 = minx + (maxx - minx - (nx - 1) * grid_resolution_m) / 2.0
    z0 = minz + (maxz - minz - (nz - 1) * grid_resolution_m) / 2.0
    samples: list[tuple[float, float]] = []
    for ix in range(nx):
        for iz in range(nz):
            x = x0 + ix * grid_resolution_m
            z = z0 + iz * grid_resolution_m
            if poly.covers(ShapelyPoint(x, z)):
                samples.append((x, z))
    if not samples:  # footprint smaller than one cell
        rep = poly.representative_point()
        samples.append((float(rep.x), float(rep.y)))

    results: list[tuple[float, float, float]] = []  # (x, z, spl_total)
    for x, z in samples:
        energy = 0.0
        for spec, pos, aim in speaker_terms:
            dx = x - pos.x
            dy = ear_y - pos.y
            dz = z - pos.z
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist <= 0.0:
                # Sample coincides with the speaker; clamp to a tiny radius so the
                # inverse-square term stays finite rather than blowing up.
                dist = 1e-6
                cos_off = 1.0
            else:
                # off-axis angle = angle between aim and (sample - speaker).
                dot = aim[0] * dx + aim[1] * dy + aim[2] * dz
                cos_off = max(-1.0, min(1.0, dot / dist))
            # Belt-and-suspenders: a non-finite cos_off would slip through the
            # clamp (NaN compares False) and feed acos a fake value.
            assert_finite(cos_off, field="cos_off")
            off_axis_deg = math.degrees(math.acos(cos_off))
            spl_i = direct_field_spl_db(
                spec, drive_w=drive_w, distance_m=dist, off_axis_deg=off_axis_deg
            )
            energy += 10.0 ** (spl_i / 10.0)
        spl_total = 10.0 * math.log10(energy) if energy > 0.0 else DIRECTIVITY_ATTEN_FLOOR_DB
        results.append((x, z, spl_total))

    n = len(results)
    spls = [r[2] for r in results]
    worst = min(results, key=lambda r: r[2])
    min_spl = min(spls)
    max_spl = max(spls)
    # Make the over-claim VISIBLE: flag when the predicted peak area SPL exceeds
    # the smallest contributing driver's max_spl_db rating (the model never caps
    # at it — see SPL_DIRECT_FIELD_NOTE over-estimate disclosure).
    min_spec_max_spl = min(spec.max_spl_db for spec, _pos, _aim in speaker_terms)
    return SPLFieldScore(
        n_samples=n,
        min_spl_db=min_spl,
        mean_spl_db=sum(spls) / n,
        max_spl_db=max_spl,
        uniformity_db=max_spl - min_spl,
        worst_point_xz=(worst[0], worst[1]),
        exceeds_max_spl=max_spl > min_spec_max_spl,
        note=SPL_DIRECT_FIELD_NOTE,
    )


def spl_field_to_dict(score: SPLFieldScore) -> dict[str, object]:
    """Plain JSON-serialisable dict (``"note"`` first; mirrors coverage_overlap)."""
    return {
        "note": score.note,
        "n_samples": score.n_samples,
        "min_spl_db": round(score.min_spl_db, 2),
        "mean_spl_db": round(score.mean_spl_db, 2),
        "max_spl_db": round(score.max_spl_db, 2),
        "uniformity_db": round(score.uniformity_db, 2),
        "worst_point_xz": [round(score.worst_point_xz[0], 3), round(score.worst_point_xz[1], 3)],
        "exceeds_max_spl": score.exceeds_max_spl,
    }


def format_spl_field_lines(score: SPLFieldScore) -> list[str]:
    """Human-readable CLI summary lines (direct-field only; NO acoustic guarantee)."""
    wx, wz = score.worst_point_xz
    lines = [
        "direct-field SPL over listener area (NO reverb / room gain — see note):",
        f"  sampled {score.n_samples} ear-plane pts; "
        f"min {score.min_spl_db:.1f} / mean {score.mean_spl_db:.1f} / "
        f"max {score.max_spl_db:.1f} dB",
        f"  uniformity {score.uniformity_db:.1f} dB (max-min); "
        f"worst near (x={wx:.1f}, z={wz:.1f})",
    ]
    if score.exceeds_max_spl:
        lines.append(
            "  WARNING: peak SPL exceeds a contributing driver's max_spl_db rating "
            "(model does NOT cap at it — likely OVER-stated; see note)"
        )
    lines.append("  direct-field GUIDANCE only, not a measured SPL (see note)")
    return lines


# --------------------------------------------------------------------------- #
# Built-in catalog — ALL representative ESTIMATEs, for previewing only.
# These numbers are plausible generic placeholders, NOT real datasheet specs.
# Inject real datasheet specs via load_speaker_spec / load_speaker_catalog.
# --------------------------------------------------------------------------- #
BUILTIN_SPEAKER_CATALOG: dict[str, SpeakerSpec] = {
    "generic_ceiling_4in": SpeakerSpec(
        model="generic_ceiling_4in",
        sensitivity_db_1w1m=86.0,
        max_spl_db=104.0,
        dispersion_deg=110.0,
        provenance="estimate",
    ),
    "generic_surround_compact": SpeakerSpec(
        model="generic_surround_compact",
        sensitivity_db_1w1m=88.0,
        max_spl_db=108.0,
        dispersion_deg=90.0,
        provenance="estimate",
    ),
    "generic_pa_box_mid": SpeakerSpec(
        model="generic_pa_box_mid",
        sensitivity_db_1w1m=96.0,
        max_spl_db=126.0,
        dispersion_deg=75.0,
        provenance="estimate",
    ),
}


def _spec_from_mapping(data: dict[str, object]) -> SpeakerSpec:
    """Build a :class:`SpeakerSpec` from a parsed mapping.

    Loaded specs default ``provenance="datasheet"`` (the caller is injecting real
    numbers) unless the mapping says otherwise. Raises ``ValueError`` on missing
    or malformed fields.
    """
    if not isinstance(data, dict):
        raise ValueError(f"speaker spec must be a mapping, got {type(data).__name__}")
    price_raw = data.get("price")
    try:
        model = str(data["model"])
        sensitivity = float(data["sensitivity_db_1w1m"])  # type: ignore[arg-type]
        max_spl = float(data["max_spl_db"])  # type: ignore[arg-type]
        dispersion = float(data["dispersion_deg"])  # type: ignore[arg-type]
        price = None if price_raw is None else float(price_raw)  # type: ignore[arg-type]
    except KeyError as exc:
        raise ValueError(f"speaker spec missing required field {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"speaker spec has a malformed numeric field: {exc}") from exc
    provenance_raw = data.get("provenance", "datasheet")
    if provenance_raw not in ("datasheet", "estimate"):
        raise ValueError(
            f"provenance must be 'datasheet' or 'estimate', got {provenance_raw!r}"
        )
    provenance: SpeakerProvenance = provenance_raw
    return SpeakerSpec(
        model=model,
        sensitivity_db_1w1m=sensitivity,
        max_spl_db=max_spl,
        dispersion_deg=dispersion,
        provenance=provenance,
        price=price,
    )


def _load_mapping(path: Path | str) -> object:
    """Parse a ``.json`` / ``.yaml`` / ``.yml`` file (yaml.safe_load handles JSON too)."""
    p = Path(path)
    try:
        with p.open("r", encoding="utf-8") as fh:
            if p.suffix.lower() == ".json":
                return json.load(fh)
            return yaml.safe_load(fh)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ValueError(f"speaker spec '{p}': invalid file — {exc}") from exc


def load_speaker_spec(path: Path | str) -> SpeakerSpec:
    """Load a single :class:`SpeakerSpec` from a yaml / json file.

    Loaded specs default ``provenance="datasheet"`` unless the file says
    otherwise, so engineers can inject REAL datasheet specs. Raises ``ValueError``
    on a malformed file or spec.
    """
    data = _load_mapping(path)
    if not isinstance(data, dict):
        raise ValueError(f"speaker spec '{path}': top-level must be a mapping")
    return _spec_from_mapping(data)


def load_speaker_catalog(path: Path | str) -> dict[str, SpeakerSpec]:
    """Load a ``{model_key -> SpeakerSpec}`` catalog from a yaml / json file.

    Accepts either a top-level mapping ``{key: spec_mapping}`` or a list of spec
    mappings (keyed by each spec's ``model``). Loaded specs default
    ``provenance="datasheet"``. Raises ``ValueError`` on a malformed file.
    """
    data = _load_mapping(path)
    catalog: dict[str, SpeakerSpec] = {}
    if isinstance(data, dict):
        for key, raw in data.items():
            spec = _spec_from_mapping(raw)
            catalog[str(key)] = spec
    elif isinstance(data, list):
        for raw in data:
            spec = _spec_from_mapping(raw)
            catalog[spec.model] = spec
    else:
        raise ValueError(
            f"speaker catalog '{path}': top-level must be a mapping or a list"
        )
    if not catalog:
        raise ValueError(f"speaker catalog '{path}': no specs found")
    return catalog
