"""ACE Challenge adapter geometry audit — gated E2E test.

Compares ``ACE_ROOM_GEOMETRY`` byte-for-byte against arXiv:1606.03365 Table 1
(TASLP supporting material; open access; transcribed 2026-05-06). Materials
are NOT yet cross-checked — TASLP final paper is paywalled; deferred to v0.6+.

Marked ``@pytest.mark.e2e`` so the default CI lane (``-m "not lab and not e2e"``)
ignores it. Runs unconditionally when collected (no env-var requirement) — the
fixture CSV is committed at ``tests/fixtures/ace_eaton_2016_table_i_arxiv.csv``.

On failure or success, emits a markdown delta report to
``docs/ace_geometry_audit_2026-05-07.md`` (idempotent overwrite). Mirrors the
regeneration pattern of ``docs/perf_verification_e2e_2026-05-06.md``.

L/W convention: roomestim keeps "longer dimension as L" so this test compares
the unordered ``{L, W}`` set as a multiset on the floor plane (allowing the
arXiv L/W swap on Office_1 / Office_2 / Building_Lobby). H must match exactly
within ±0.01 m.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from roomestim.adapters.ace_challenge import ACE_ROOM_GEOMETRY

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "ace_eaton_2016_table_i_arxiv.csv"
)
_REPORT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "ace_geometry_audit_2026-05-07.md"
)
_TOLERANCE_M = 0.01


def _load_arxiv_table() -> list[tuple[str, float, float, float]]:
    """Return [(room_id, L_m, W_m, H_m), ...] from the committed CSV.

    Skips lines beginning with ``#`` to keep the citation comment inline with
    the data without using a sidecar file.
    """
    rows: list[tuple[str, float, float, float]] = []
    with _FIXTURE_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header: list[str] | None = None
        for raw in reader:
            if not raw:
                continue
            if raw[0].lstrip().startswith("#"):
                continue
            if header is None:
                header = [h.strip() for h in raw]
                expected = ["room_id", "L_m", "W_m", "H_m"]
                if header != expected:
                    raise ValueError(
                        f"{_FIXTURE_PATH}: header {header!r} != expected {expected!r}"
                    )
                continue
            room_id = raw[0].strip()
            L_m = float(raw[1])
            W_m = float(raw[2])
            H_m = float(raw[3])
            rows.append((room_id, L_m, W_m, H_m))
    return rows


def _write_report(deltas: list[str], statuses: list[tuple[str, str]]) -> None:
    lines = [
        "# ACE Challenge adapter geometry audit",
        "",
        "- Generated: 2026-05-07 by `tests/test_ace_geometry_audit.py`",
        "- Source of truth: arXiv:1606.03365 Table 1 (TASLP supporting material; "
        "open access; transcribed 2026-05-06).",
        "- Fixture: `tests/fixtures/ace_eaton_2016_table_i_arxiv.csv`.",
        "- Caveat: **dimensions only.** Material assignments (`floor`, `walls`, "
        "`ceiling`) are NOT cross-checked — Eaton 2016 TASLP final paper is "
        "paywalled; materials deferred to v0.6+.",
        "- L/W convention: roomestim keeps \"longer dimension as L\". The audit "
        "compares unordered `{L, W}` set as a multiset on the floor plane "
        "(allowing arXiv L/W swap on Office_1 / Office_2 / Building_Lobby). "
        "H must match exactly within ±0.01 m.",
        f"- Tolerance: ±{_TOLERANCE_M:.2f} m.",
        "",
        "## Per-room status",
        "",
        "| Room | Status | Notes |",
        "| --- | --- | --- |",
    ]
    for room_id, status in statuses:
        lines.append(f"| {room_id} | {status} | dims-only; materials not checked |")
    lines.append("")
    lines.append("## Deltas")
    lines.append("")
    if deltas:
        lines.extend(deltas)
    else:
        lines.append("No dimensional deltas. All 7 rooms agree within tolerance.")
    lines.append("")
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.e2e
def test_ace_geometry_dims_match_arxiv_table_1() -> None:
    """All 7 ACE rooms agree with arXiv:1606.03365 Table 1 within ±0.01 m.

    Materials are NOT cross-checked — caveat written into the markdown header.
    """
    arxiv_rows = _load_arxiv_table()
    assert len(arxiv_rows) == 7, (
        f"expected 7 rows in {_FIXTURE_PATH}, got {len(arxiv_rows)}"
    )

    deltas: list[str] = []
    statuses: list[tuple[str, str]] = []
    failures: list[str] = []

    for room_id, arxiv_L, arxiv_W, arxiv_H in arxiv_rows:
        assert room_id in ACE_ROOM_GEOMETRY, (
            f"arXiv room_id {room_id!r} missing from ACE_ROOM_GEOMETRY"
        )
        geom = ACE_ROOM_GEOMETRY[room_id]
        rm_L = float(geom["L"])
        rm_W = float(geom["W"])
        rm_H = float(geom["H"])

        # Floor-plane multiset compare (allows L/W swap)
        rm_floor = sorted([rm_L, rm_W])
        arxiv_floor = sorted([arxiv_L, arxiv_W])
        floor_ok = all(
            abs(rm_floor[i] - arxiv_floor[i]) <= _TOLERANCE_M for i in range(2)
        )
        height_ok = abs(rm_H - arxiv_H) <= _TOLERANCE_M

        if floor_ok and height_ok:
            statuses.append((room_id, "OK"))
        else:
            statuses.append((room_id, "DELTA"))
            delta_line = (
                f"- **{room_id}**: roomestim (L={rm_L}, W={rm_W}, H={rm_H}) vs "
                f"arXiv (L={arxiv_L}, W={arxiv_W}, H={arxiv_H}); "
                f"floor_match={floor_ok}, height_match={height_ok}"
            )
            deltas.append(delta_line)
            failures.append(delta_line)

    _write_report(deltas, statuses)

    # Materials must remain unverified at v0.5 — sanity-assert the caveat is
    # in the regenerated report so downstream readers see it.
    report_text = _REPORT_PATH.read_text(encoding="utf-8")
    assert "Material assignments" in report_text
    assert "NOT cross-checked" in report_text

    if failures:
        raise AssertionError(
            "ACE_ROOM_GEOMETRY dimensional audit failed:\n" + "\n".join(failures)
        )
