"""4-axis immersive-layout trade-off report (immersive-layout-design P3).

This module is a THIN AGGREGATION layer: it composes the already-shipped
direct-field SPL field (P1, :mod:`roomestim.spec.speaker_spec`), the geometric
angular metrics (P2, :mod:`roomestim.place.immersive_quality`), an RT60 estimate
(model :func:`roomestim.reconstruct.predictor.predict_rt60_default` OR an
engineer-injected measured value), and a simple per-speaker price sum into a
single decision-support summary over four axes:

1. LEVEL — direct-field SPL field over the listener area + headroom vs a target;
2. PANNING — angular uniformity of the rig as seen from the listener;
3. SEPARATION — the geometric too-close-pairs interference proxy;
4. COST — the arithmetic sum of the per-speaker ``SpeakerSpec.price`` fields.

It re-derives NO physics — every numeric output is forwarded from the existing
frozen scores, so the report inherits each composed metric's caveats. None of the
four axes is a guaranteed in-room measurement; the whole report is RELATIVE
guidance for comparing candidate layouts. See :data:`TRADEOFF_REPORT_NOTE`.

numpy-free (stdlib only + the composed modules' deps); import-safe at
``import roomestim`` time (core / torch-free boundary).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from roomestim.geom.polygon import polygon_area_3d
from roomestim.model import (
    ListenerArea,
    MaterialLabel,
    PlacementResult,
    RoomModel,
    assert_finite,
)
from roomestim.place.immersive_quality import (
    DEFAULT_MIN_SEPARATION_DEG,
    AngularUniformityScore,
    InterferenceScore,
    angular_uniformity,
    angular_uniformity_to_dict,
    format_angular_uniformity_lines,
    format_interference_lines,
    interference_proxy,
    interference_to_dict,
)
from roomestim.reconstruct._disclosure import TRADEOFF_REPORT_NOTE
from roomestim.reconstruct.measured_rt60 import MeasuredRT60
from roomestim.reconstruct.predictor import predict_rt60_default
from roomestim.spec.speaker_spec import (
    DEFAULT_GRID_RESOLUTION_M,
    SpeakerSpec,
    SPLFieldScore,
    spl_field_over_area,
    spl_field_to_dict,
)

__all__ = [
    "TRADEOFF_REPORT_NOTE",
    "TradeoffCost",
    "TradeoffReport",
    "evaluate_layout",
    "tradeoff_to_dict",
    "format_tradeoff_lines",
]


@dataclass(frozen=True)
class TradeoffCost:
    """Cost axis: a simple arithmetic sum of the per-speaker ``price`` fields.

    NOT a quote. ``total_price`` is ``None`` (and ``complete`` False, ``n_priced``
    0) when NO speaker has a price; when some-but-not-all speakers are priced,
    ``total_price`` is the sum of the KNOWN prices and ``complete`` is False. See
    :data:`TRADEOFF_REPORT_NOTE`.
    """

    total_price: float | None
    n_speakers: int
    n_priced: int
    complete: bool  # True iff every speaker had a non-None price


@dataclass(frozen=True)
class TradeoffReport:
    """Aggregate 4-axis decision-support summary. NOT a guaranteed measurement.

    Composes the P1 SPL field, the P2 angular metrics, an RT60 context value, and
    the cost sum; every numeric field is forwarded from the underlying scores. See
    :data:`TRADEOFF_REPORT_NOTE`.
    """

    layout_name: str
    target_algorithm: str
    n_speakers: int

    # Axis 1 — level (direct-field SPL).
    spl: SPLFieldScore
    target_spl_db: float
    spl_headroom_db: float   # = spl.min_spl_db - target_spl_db
    meets_target_spl: bool   # = spl.min_spl_db >= target_spl_db
    # Provenance of the contributing specs' sensitivity: "datasheet" (the absolute
    # SPL / headroom is meaningful), "estimate" (placeholder previewing numbers,
    # NOT authoritative), or "mixed". Makes the absolute SPL claim self-describing
    # rather than relying on the reader having read TRADEOFF_REPORT_NOTE.
    spl_provenance: str

    # Axis 2 — panning (angular uniformity).
    angular: AngularUniformityScore

    # Axis 3 — separation (interference proxy).
    interference: InterferenceScore

    # Axis 4 — cost.
    cost: TradeoffCost

    # RT60 context.
    rt60_predicted_s: float
    rt60_predictor_name: str
    rt60_measured_s: float | None
    rt60_effective_s: float   # = measured if injected else predicted
    rt60_source: Literal["measured", "predicted"]

    note: str  # = TRADEOFF_REPORT_NOTE


# Intentional LOCAL copy of the RT60 surface-area-by-material aggregation also
# present in roomestim_web/report.py and the predictor: kept additive (this is a
# thin composer; refactoring the existing private copies is out of scope).
def _surface_areas_by_material(room: RoomModel) -> dict[MaterialLabel, float]:
    """Per-material surface-area sums, folding object-derived surfaces (D46)."""
    extra: list[Any] = []
    if room.objects:
        try:
            from roomestim.reconstruct.predictor import _objects_to_surfaces

            extra = _objects_to_surfaces(list(room.objects))
        except Exception:
            extra = []

    areas: dict[MaterialLabel, float] = defaultdict(float)
    for surf in room.surfaces:
        areas[surf.material] += polygon_area_3d(surf.polygon)
    for surf in extra:
        areas[surf.material] += polygon_area_3d(surf.polygon)
    return dict(areas)


def _spec_for_channel(
    specs: SpeakerSpec | dict[int, SpeakerSpec], channel: int
) -> SpeakerSpec:
    """Resolve the spec for one channel (single spec applies to all, or per-channel).

    Mirrors :func:`roomestim.spec.speaker_spec._spec_for_channel`: a missing
    channel key raises ``ValueError``.
    """
    if isinstance(specs, dict):
        try:
            return specs[channel]
        except KeyError as exc:
            raise ValueError(f"no SpeakerSpec for channel {channel}") from exc
    return specs


def _build_cost(specs: list[SpeakerSpec]) -> TradeoffCost:
    """Arithmetic per-speaker price sum (None when no speaker is priced)."""
    n = len(specs)
    priced = [s.price for s in specs if s.price is not None]
    n_priced = len(priced)
    if n_priced == 0:
        return TradeoffCost(
            total_price=None, n_speakers=n, n_priced=0, complete=False
        )
    return TradeoffCost(
        total_price=sum(priced),
        n_speakers=n,
        n_priced=n_priced,
        complete=n_priced == n,
    )


def _resolve_measured_rt60(
    measured_rt60: MeasuredRT60 | float | None,
) -> float | None:
    """Normalise the engineer RT60 injection to seconds (or None).

    Accepts a :class:`MeasuredRT60` (uses ``.rt60_s``), a raw float, or None. The
    seconds value is required to be finite and strictly positive REGARDLESS of the
    branch — ``MeasuredRT60`` is a plain frozen dataclass with no validating
    ``__post_init__``, so a hand-built negative / NaN ``rt60_s`` must be rejected
    here too. Raises ``ValueError`` on a non-finite / non-positive value.
    """
    if measured_rt60 is None:
        return None
    if isinstance(measured_rt60, MeasuredRT60):
        value = measured_rt60.rt60_s
    else:
        value = float(measured_rt60)
    assert_finite(value, field="measured_rt60")
    if value <= 0.0:
        raise ValueError(f"measured_rt60 must be > 0, got {value}")
    return value


def evaluate_layout(
    room: RoomModel,
    placement: PlacementResult,
    spec: SpeakerSpec | dict[int, SpeakerSpec],
    *,
    listener_area: ListenerArea,
    drive_w: float,
    target_spl_db: float,
    measured_rt60: MeasuredRT60 | float | None = None,
    grid_resolution_m: float = DEFAULT_GRID_RESOLUTION_M,
    min_separation_deg: float = DEFAULT_MIN_SEPARATION_DEG,
) -> TradeoffReport:
    """Compose the 4-axis trade-off report for one candidate layout.

    Forwards to the already-shipped metrics — :func:`spl_field_over_area`
    (level), :func:`angular_uniformity` (panning), :func:`interference_proxy`
    (separation), and :func:`predict_rt60_default` (RT60 context) — plus a per-
    speaker price sum (cost). NO physics is re-derived here.

    ``spec`` is a single :class:`SpeakerSpec` applied to every speaker, or a
    ``dict[channel -> SpeakerSpec]``. ``measured_rt60`` injects an engineer RT60:
    a :class:`MeasuredRT60` (its ``.rt60_s``), a raw float (seconds, must be
    finite > 0), or None to use the model estimate.

    Raises ``ValueError`` on ``drive_w <= 0``, a non-finite ``target_spl_db``, a
    non-positive injected ``measured_rt60``, or a missing per-channel spec. The
    composed metrics raise on their own degenerate inputs (e.g. fewer than 2
    speakers for the angular axes) and are NOT swallowed.
    """
    assert_finite(drive_w, field="drive_w")
    if drive_w <= 0.0:
        raise ValueError(f"drive_w must be > 0, got {drive_w}")
    assert_finite(target_spl_db, field="target_spl_db")

    speakers = placement.speakers
    measured_s = _resolve_measured_rt60(measured_rt60)

    # Axis 1 — level (direct-field SPL field over the listener area).
    spl = spl_field_over_area(
        spec,
        drive_w=drive_w,
        speakers=speakers,
        listener_area=listener_area,
        grid_resolution_m=grid_resolution_m,
    )
    spl_headroom_db = spl.min_spl_db - target_spl_db
    meets_target_spl = spl.min_spl_db >= target_spl_db

    # Axes 2 + 3 — panning + separation (geometric; raise on <2 speakers).
    angular = angular_uniformity(speakers)
    interference = interference_proxy(speakers, min_separation_deg=min_separation_deg)

    # Axis 4 — cost (arithmetic per-speaker price sum).
    resolved_specs = [_spec_for_channel(spec, sp.channel) for sp in speakers]
    cost = _build_cost(resolved_specs)

    # Surface the contributing specs' provenance so the ABSOLUTE SPL / headroom is
    # self-describing (only datasheet sensitivity makes it meaningful — see note).
    provs = {s.provenance for s in resolved_specs}
    spl_provenance = provs.pop() if len(provs) == 1 else "mixed"

    # RT60 context — model estimate, optionally overridden by the injection.
    areas = _surface_areas_by_material(room)
    prediction = predict_rt60_default(room, areas)
    rt60_predicted_s = prediction.rt60_s
    if measured_s is not None:
        rt60_effective_s = measured_s
        rt60_source: Literal["measured", "predicted"] = "measured"
    else:
        rt60_effective_s = rt60_predicted_s
        rt60_source = "predicted"

    return TradeoffReport(
        layout_name=placement.layout_name,
        target_algorithm=placement.target_algorithm,
        n_speakers=len(speakers),
        spl=spl,
        target_spl_db=target_spl_db,
        spl_headroom_db=spl_headroom_db,
        meets_target_spl=meets_target_spl,
        spl_provenance=spl_provenance,
        angular=angular,
        interference=interference,
        cost=cost,
        rt60_predicted_s=rt60_predicted_s,
        rt60_predictor_name=prediction.predictor_name,
        rt60_measured_s=measured_s,
        rt60_effective_s=rt60_effective_s,
        rt60_source=rt60_source,
        note=TRADEOFF_REPORT_NOTE,
    )


def tradeoff_to_dict(report: TradeoffReport) -> dict[str, object]:
    """Plain JSON-serialisable dict (``"note"`` first; mirrors the composed *_to_dict)."""
    return {
        "note": report.note,
        "layout_name": report.layout_name,
        "target_algorithm": report.target_algorithm,
        "n_speakers": report.n_speakers,
        "target_spl_db": round(report.target_spl_db, 2),
        "spl_headroom_db": round(report.spl_headroom_db, 2),
        "meets_target_spl": report.meets_target_spl,
        "spl_provenance": report.spl_provenance,
        "spl": spl_field_to_dict(report.spl),
        "angular": angular_uniformity_to_dict(report.angular),
        "interference": interference_to_dict(report.interference),
        "cost": {
            "total_price": (
                None
                if report.cost.total_price is None
                else round(report.cost.total_price, 2)
            ),
            "n_speakers": report.cost.n_speakers,
            "n_priced": report.cost.n_priced,
            "complete": report.cost.complete,
        },
        "rt60": {
            "predicted_s": round(report.rt60_predicted_s, 3),
            "measured_s": (
                None
                if report.rt60_measured_s is None
                else round(report.rt60_measured_s, 3)
            ),
            "effective_s": round(report.rt60_effective_s, 3),
            "source": report.rt60_source,
            "predictor_name": report.rt60_predictor_name,
        },
    }


def format_tradeoff_lines(report: TradeoffReport) -> list[str]:
    """Human-readable CLI summary lines (RELATIVE guidance; NO acoustic guarantee)."""
    lines = [
        f"immersive layout trade-off — '{report.layout_name}' "
        f"({report.target_algorithm}, {report.n_speakers} speakers); "
        "RELATIVE guidance only, NO acoustic guarantee (see note):",
    ]
    # Axis 1 — level.
    status = "meets" if report.meets_target_spl else "SHORT of"
    lines.append(
        f"  level: direct-field SPL min {report.spl.min_spl_db:.1f} / "
        f"mean {report.spl.mean_spl_db:.1f} / max {report.spl.max_spl_db:.1f} dB; "
        f"{report.spl_headroom_db:+.1f} dB headroom — {status} target "
        f"{report.target_spl_db:.1f} dB (direct-field only, specs={report.spl_provenance})"
    )
    # Axes 2 + 3 — reuse the composed formatters verbatim.
    lines.extend(f"  {ln}" for ln in format_angular_uniformity_lines(report.angular))
    lines.extend(f"  {ln}" for ln in format_interference_lines(report.interference))
    # Axis 4 — cost.
    if report.cost.total_price is None:
        lines.append(
            f"  cost: unpriced (0 / {report.cost.n_speakers} speakers have a price; "
            "NOT a quote)"
        )
    else:
        tag = "complete" if report.cost.complete else "PARTIAL"
        lines.append(
            f"  cost: {report.cost.total_price:.2f} ({tag}, "
            f"{report.cost.n_priced} / {report.cost.n_speakers} priced; NOT a quote)"
        )
    # RT60 context.
    lines.append(
        f"  rt60: {report.rt60_effective_s:.2f} s ({report.rt60_source}; "
        f"predictor {report.rt60_predictor_name})"
    )
    lines.append("  4-axis decision-support summary, not a measurement (see note)")
    return lines
