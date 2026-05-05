# ADR 0003 — Placement algorithm priority

- **Status**: Accepted (finalized 2026-05-04)
- **Date**: 2026-05-03
- **Cross-ref**: design plan §2.3 Q3.

## Context

`spatial_engine/require.md` §2 mandates WFS / VBAP / DBAP (object-based). Each algorithm has
distinct geometric constraints; "place 8 speakers in this room" is meaningless without specifying
the target algorithm.

## Decision

Order: **VBAP → DBAP → WFS → Ambisonics (deferred to v0.3)**.

## Drivers

1. VBAP equal-angle ring is the simplest deterministic placement; fastest path to a working
   end-to-end pipeline.
2. DBAP is robust to irregular venues — required for exhibition-space realism.
3. WFS has the strictest constraint (λ/2 spacing); ships last so the placement engine can
   absorb the irregularity lessons from DBAP first.

## Alternatives

- **WFS-first**: rejected. λ/2 at f_max=8 kHz means ~2 cm spacing — incompatible with any real lab.
- **Ambisonics-first**: rejected. Not yet in `require.md` mandatory list.

## Consequences

- (+) v0.1 ships a usable VBAP placement on day one of P3.
- (+) WFS aliasing-frequency surfacing (extension key `x_wfs_f_alias_hz`) is a clean
  observability win once WFS lands in P5.
- (−) Ambisonics customers wait until v0.3.

## Falsifier

If `require.md` adds Ambisonics to mandatory before v0.3, reorder.

## Follow-ups

- Per-algorithm placement modules in `roomestim/place/` (done — P3/P5).
- Ambisonics placement in v0.3: add `ambisonics.py` once `require.md` lists it mandatory (cross-ref design §10 deferral table).
