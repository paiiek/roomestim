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

## Status-update (2026-07-01, v0.60.0 — `dome` dispatch wiring)

**`dome` algorithm wired into `run_placement` (additive, geometry-only).** The
two-stacked-ring VBAP dome (`place_vbap_dome`, A6 — already shipped in
`roomestim/place/vbap.py`) was previously reachable only by direct function call;
`run_placement(room, "dome", n_speakers, layout_radius_m, el_deg, ...)` now
dispatches to it (mirrors how ADR 0041 §Status-update recorded the ambisonics
dispatch wiring; the CLI/web pass through `run_placement`).

- **n→rings split:** the single `n_speakers` is split `n_lower=(n+1)//2`,
  `n_upper=n//2` (lower ring gets the odd extra). Lower ring at `el_lower_deg=0.0`;
  upper ring at `el_upper_deg = el_deg if el_deg > 0 else 30.0` (the elevation knob
  tilts the upper ring; el_deg ≤ 0 → a sensible 30° default — a downward/flat
  upper ring is nonsensical for a dome). `radius_m = layout_radius_m`.
- **Guard:** each ring needs ≥3 → `n_speakers >= 6`. `run_placement` pre-validates
  with a clear message (`"dome requires n_speakers>=6 (two rings of >=3); got N"`)
  before `place_vbap_dome`'s own per-ring `kErrTooFewSpeakers`.
- **Honest framing (unchanged):** dome is geometry-blind like vbap (the room
  argument is unused), and is reported with the conservative `IRREGULAR`
  regularity hint — it is NOT a single planar ring nor a calibrated dome, just two
  stacked equal-angle rings. `target_algorithm == "VBAP"`. No acoustic/SPL claim.
- **Web exposure:** `roomestim_web` adds `dome` + `coverage` to the algorithm
  Radio, extends the speaker-count choices to 24/32/48/64 (vbap-ring + dbap verified
  to handle these; the prior 16 cap was purely the Radio choices), and adds a
  one-click "예시 룸 불러오기" loader that runs a bundled lab-room mesh through the
  same pipeline. Coverage greys out n/radius/elevation (it auto-computes the grid
  from room geometry and carries no SPL guarantee — see `COVERAGE_GRID_NOTE`).
- **Byte-equal:** existing dispatch branches and every prior call path are
  unchanged (additive branch only).
