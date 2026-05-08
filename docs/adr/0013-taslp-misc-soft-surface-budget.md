# ADR 0013 — TASLP-derived MISC_SOFT surface budget per room (v0.6)

- **Status**: Accepted (v0.6.0)
- **Date**: 2026-05-08
- **Predecessor**: v0.5.1 (`4bfa862`); ADRs 0008 (octave-band), 0011
  (MISC_SOFT enum), 0012 (TASLP materials closure); D14, D15, D16.

## Decision

Wire the v0.5.0 `MaterialLabel.MISC_SOFT` schema slot (ADR 0011) to the ACE
Challenge adapter using TASLP §II-C "Rooms" (p.1683) explicit per-room
furniture counts, and per-piece equivalent-absorption rows transcribed
from textbook tables (Vorländer 2020 *Auralization* §11 / Appendix A
primary; Beranek 2004 *Concert Halls and Opera Houses* Ch.3 Table 3.1
cross-check for the lecture-seat row). The adapter synthesises one
additional `Surface(material=MISC_SOFT, kind="floor")` per furniture-tracked
room whose Newell-area is integrand-preserving:

```
area_misc_soft = Σ_pieces count_i * A_500_i / a_misc_soft_500
```

with `a_misc_soft_500 = MaterialAbsorption[MISC_SOFT] = 0.40` (v0.5.0 row).

Six of the 7 ACE rooms gain a MISC_SOFT surface (surface count 6 → 7);
Building_Lobby is excluded by default (§3 OQ-9; coupled-space caveat
already documented in ADR 0012).

Per-piece α₅₀₀ values (m² Sabines per item):

| Piece | α₅₀₀ | Source |
| --- | ---: | --- |
| `office_chair` | 0.50 | Vorländer 2020 §11 / Appx A "upholstered seating, empty"; Beranek 2004 Ch.3 Tab 3.1 cross-check |
| `stacking_chair` | 0.15 | Vorländer 2020 §11 / Appx A "wooden chair" representative |
| `lecture_seat` | 0.45 | Beranek 2004 Ch.3 Tab 3.1 "unoccupied theatre/lecture seats"; Vorländer 2020 §11 / Appx A theatre-seating cross-check |
| `table` | 0.10 | Vorländer 2020 §11 / Appx A "large hard table" representative |
| `bookcase` | 0.30 | Vorländer 2020 §11 / Appx A "books on shelf" |

Per-band tuples mirror the MISC_SOFT band-tuple shape `(0.5×, 0.75×, 1.0×,
1.25×, 1.5×, 1.625×)` of α₅₀₀, scaled to the per-piece reference. The
band-2 ↔ legacy-scalar invariant
(`_PIECE_EQUIVALENT_ABSORPTION_BANDS_M2[p][2] ==
_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2[p]`) holds by construction and is
test-enforced.

Per-room TASLP §II-C furniture counts:

| Room | Furniture |
| --- | --- |
| `Office_1` | 4 office_chair |
| `Office_2` | 6 office_chair, 1 bookcase |
| `Meeting_1` | 14 office_chair |
| `Meeting_2` | 30 office_chair, 6 table |
| `Lecture_1` | 60 lecture_seat, 20 table |
| `Lecture_2` | 100 lecture_seat, 35 table |
| `Building_Lobby` | (intentionally excluded — coupled space) |

Plumbing:
- New private helper `_furniture_to_misc_soft_area(furniture: dict[str, int]) -> float`
  computes the integrand-preserving area at 500 Hz.
- New private helper
  `_misc_soft_surface_from_furniture(room_id: str, room_dimensions: tuple) -> Surface | None`
  builds the synthetic Surface (or returns `None` for Building_Lobby /
  unknown rooms). The polygon is laid out as a square inside the floor
  footprint when `√area ≤ min(L, W)`; otherwise as a strip along the
  longer edge (R-3 strip-clip; triggers on Lecture_1 and Lecture_2).
- `_build_room_model` appends the synthesised surface iff the helper
  returns non-None.

## Drivers

- Empirically tests v0.4 audit Finding 4 hypothesis ("bare-walls model
  under-counts absorption budget — soft furnishings/occupants") — see
  v0.4-audit-findings.md and the v0.6 perf doc at
  `docs/perf_verification_e2e_2026-05-08.md`.
- Uses the canonical TASLP §II-C furniture counts (factual data; not
  copyrightable), recorded durably in project memory
  `project_taslp_2016_content.md` at v0.5.1.
- Vindicates the v0.5.0 MISC_SOFT slot (ADR 0011) by making it a live
  surface-emitting consumer, exercising the schema's reserved coverage
  for furnishings/occupants absorption.
- Additive change: adapter-data + helper + private wiring; no schema
  flip, no enum extension, no MaterialAbsorptionBands revision, no
  predictor change. Default-lane byte-equality of v0.5.1's 84 tests is
  preserved by construction (no existing test imports the helper).
- Preserves Sabine integrand exactly at 500 Hz reference by construction.

## Alternatives considered

- **(a) Public API `furniture_to_misc_soft_area(...)`.** Rejected. No
  external consumer asks today. Reverse-trigger to public if and when
  another adapter wants to share the formula.
- **(b) Per-furnishing Surface objects** (one Surface per chair / table).
  Rejected. Explodes the surface count without changing the Sabine
  integrand; obscures the "synthetic budget" framing; no acoustic
  benefit at the diffuse-field assumption used by Sabine/Eyring.
- **(c) Add new `MaterialLabel.FLOOR_HARD` enum entry** (§3 OQ-10).
  Rejected. Schema-impacting; no per-band data justifies splitting
  WOOD_FLOOR; orthogonal to MISC_SOFT; honesty caveat in adapter
  already documents the wood/concrete/tile/linoleum indeterminacy
  (v0.5.1 D16). Reverse-trigger if hard-floor subtype is later
  confirmed and is not already in the enum.
- **(d) Building_Lobby per-area MISC_SOFT density approximation.**
  Rejected. ACE_ROOM_GEOMETRY shoebox of 72.9 m³ describes the recording
  corner only — not the full coupled space. Adding furniture absorption
  to a room whose modelling-assumption is already violated compounds
  error rather than reducing it. ADR 0012 covers the structural caveat;
  a future ADR (v0.7+) re-evaluates Building_Lobby coupled-space
  modelling on its own terms.
- **(e) Co-ship per-band coefficient revision (Finding 4a).** Rejected.
  D14 5b reverse-trigger requires "assignments correct AND errors
  persist"; F1 walls/ceiling are INDETERMINATE per ADR 0012 — the
  pre-condition cannot evaluate. Stays DEFERRED with the same explicit
  rationale as v0.5.x.

## Why chosen

This is the smallest correct additive move that empirically tests an
open hypothesis (v0.4 F4) using a canonical source (TASLP §II-C). It:

- Makes the v0.5.0 MISC_SOFT slot a live surface-emitting consumer
  rather than a schema-only reservation.
- Keeps `_build_room_model` signature stable; the helper is unit-testable
  in isolation.
- Reuses the v0.3 honesty-marker policy (representative-not-verbatim)
  and the v0.5.0 band-2 ↔ legacy-scalar invariant.
- Imposes zero changes to: model.py (no enum / no table edits),
  reconstruct/materials.py (no predictor edits), io / export / cli.

## Consequences

- **Adapter** (`roomestim/adapters/ace_challenge.py`):
  - +`_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2`, `_PIECE_EQUIVALENT_ABSORPTION_BANDS_M2`,
    `_FURNITURE_BY_ROOM`.
  - +`_furniture_to_misc_soft_area(...)`, `_misc_soft_surface_from_furniture(...)`.
  - `_build_room_model` appends synthesised MISC_SOFT surface iff helper
    returns non-None (6→7 surfaces for furniture-tracked rooms; 6
    unchanged for Building_Lobby).
  - `load_room` `notes` string updated to declare MISC_SOFT presence /
    absence per room.
  - LOW-RETRO docstring softening (v0.5.1 follow-up; consistent with
    ADR 0012).
- **Tests**:
  - New file `tests/test_misc_soft_furniture_budget.py` (+16 default-lane
    tests). v0.5.1 84 → 100.
  - Existing `test_ace_adapter_with_sample_fixture` continues to pass
    byte-for-byte (assertions are `len(areas) > 0` / `volume > 0` /
    `predicted_500hz > 0`; surface-count 6→7 for furniture rooms is
    absorbed).
- **Schema**: `__schema_version__` stays `"0.1-draft"` (Stage-1 absorbs
  MISC_SOFT surface emission gracefully via `additionalProperties: true`).
- **Perf doc**:
  - `docs/perf_verification_e2e_2026-05-08.md` regenerated post-v0.6.
  - High-furniture rooms drop sharply: Lecture_1 Sabine 1.762→0.686 s
    (err +1.201 → +0.125 s); Office_1 0.864→0.704 s; Office_2
    0.862→0.631 s. Lecture_2 strip-clip path triggers; under-prediction
    deepens (Lecture_2 ceiling hypothesis ADR 0012 — separate v0.7+
    work). Building_Lobby unchanged.
  - Eyring monotonicity (`eyring ≤ sabine + 1e-9`) preserved per-room
    per-band — runtime-asserted in the gated E2E.
- **Decisions log**: D17 appended; D14, D15, D16 bodies untouched.
- **Open questions**: OQ-6..OQ-10 marked `[x]` with this plan's locked
  defaults.
- **Version**: `pyproject.toml` and `roomestim/__init__.py` 0.5.1 →
  0.6.0; local-only tag `v0.6.0` (D11 precedent).

## Reverse if

- A textbook re-read or author lookup surfaces a per-piece value that
  differs by > 30% on any band → patch
  `_PIECE_EQUIVALENT_ABSORPTION_*` and re-run gated E2E.
- An external adapter consumer reports the synthesised MISC_SOFT
  surface area is wrong for their use case → revisit the helper's
  formula and the per-piece table.
- A lab visit produces a measured furnishings-class absorption per-room
  delta that disagrees with the synthesised area by > 30% → revisit.
- An author email / ACE Challenge consortium follow-up paper publishes
  a per-room measured furnishings absorption table → patch and re-cite.
- Building_Lobby coupled-space ADR (v0.7+) ships first → re-evaluate
  whether B-L should be included with a coupled-space-aware budget.

## References

- Eaton, J., Gaubitch, N. D., Moore, A. H., & Naylor, P. A. (2016).
  *Estimation of room acoustic parameters: The ACE Challenge.* IEEE/ACM
  TASLP 24(10), 1681–1693. DOI: 10.1109/TASLP.2016.2577502
  (institutional access).
  - **§II-C "Rooms" (p.1683)**: per-room prose with floor type +
    furniture counts. Source for `_FURNITURE_BY_ROOM`.
- Vorländer, M. (2020). *Auralization: Fundamentals of Acoustics,
  Modelling, Simulation, Algorithms and Acoustic Virtual Reality* (2nd
  ed.). Springer. §11 + Appendix A absorption coefficient tables.
  - "Upholstered seating, empty" row → `office_chair` α₅₀₀ ≈ 0.50.
  - "Wooden chair" representative → `stacking_chair` α₅₀₀ ≈ 0.15.
  - Theatre-seating row → `lecture_seat` cross-check.
  - "Large hard table" representative → `table` α₅₀₀ ≈ 0.10.
  - "Books on shelf" → `bookcase` α₅₀₀ ≈ 0.30.
- Beranek, L. (2004). *Concert Halls and Opera Houses* (2nd ed.).
  Springer. Ch.3 Table 3.1.
  - "Unoccupied theatre/lecture seats" row → `lecture_seat` α₅₀₀ ≈ 0.45.
- ADR 0008 — octave-band absorption schema extension (v0.3).
- ADR 0011 — MISC_SOFT MaterialLabel extension (v0.5.0).
- ADR 0012 — Eaton 2016 TASLP final reviewed; per-surface materials NOT
  in paper (v0.5.1).
- ADR 0014 — Building_Lobby coupled-space exclusion from aggregate
  metrics (v0.7; formalises the v0.6 §Alternatives-considered-(d)
  exclusion).
- D14 — Eyring shipped; ACE byte-audit deferred.
- D15 — v0.5.0 partial-A (dims) + B (MISC_SOFT) shipped.
- D16 — v0.5.1 framing correction; TASLP §II-C furniture counts
  identified as MISC_SOFT retroactive justification.
- `.omc/plans/v0.6-design.md` (this release's locked plan).
- `.omc/plans/v0.6-audit-findings.md` (per-finding status).
- Project memory: `project_taslp_2016_content.md` (paper content map).
