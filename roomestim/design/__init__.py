"""Immersive-layout decision-support composition (immersive-layout-design P3).

Additive, opt-in, numpy-free, import-safe at ``import roomestim`` time. The
:func:`evaluate_layout` composer is a THIN AGGREGATION of the already-shipped P1
direct-field SPL field, the P2 geometric angular metrics, an RT60 estimate, and a
per-speaker price sum — it re-derives no physics and inherits every composed
metric's caveats. See
:data:`roomestim.reconstruct._disclosure.TRADEOFF_REPORT_NOTE`.
"""

from __future__ import annotations

from roomestim.design.tradeoff import (
    TRADEOFF_REPORT_NOTE,
    TradeoffCost,
    TradeoffReport,
    evaluate_layout,
    format_tradeoff_lines,
    tradeoff_to_dict,
)

__all__ = [
    "TRADEOFF_REPORT_NOTE",
    "TradeoffCost",
    "TradeoffReport",
    "evaluate_layout",
    "format_tradeoff_lines",
    "tradeoff_to_dict",
]
