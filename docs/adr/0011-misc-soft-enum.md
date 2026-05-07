# ADR 0011 — MaterialLabel `MISC_SOFT` extension for adapter-emitted furnishings absorption

- **Status**: Accepted (v0.5.0)
- **Date**: 2026-05-07
- **Cross-ref**: D3, D5, D7, D12, D14, ADR 0008,
  `.omc/plans/v0.5-design.md` §0a,
  `.omc/plans/v0.4-audit-findings.md` Finding 4b,
  `roomestim/model.py` (`MaterialLabel`, `MaterialAbsorption`,
  `MaterialAbsorptionBands`),
  `tests/test_room_acoustics_octave.py` (4 new MISC_SOFT tests).

## Decision

Extend the closed `MaterialLabel` enum (D3) with one new entry `MISC_SOFT`
("misc_soft"), and add the corresponding rows to the absorption tables:

- `MaterialAbsorption[MaterialLabel.MISC_SOFT] = 0.40` (legacy 500 Hz scalar).
- `MaterialAbsorptionBands[MaterialLabel.MISC_SOFT] = (0.20, 0.30, 0.40, 0.50, 0.60, 0.65)`
  (representative-not-verbatim; rising upholstered-furniture-class profile).

The band-index-2 ↔ legacy-scalar invariant
(`MaterialAbsorptionBands[m][2] == MaterialAbsorption[m]`) is preserved by
construction and continues to be enforced by
`tests/test_room_acoustics_octave.py::test_band_a500_matches_legacy_scalar`,
which iterates over `MaterialLabel` and so picks up `MISC_SOFT` automatically.

`MISC_SOFT` is a **schema slot reserved for adapter-emitted furnishings /
occupants absorption budget** (curtains, fabric panels, books, light
upholstery, seated occupants). It is **not a per-furnishing-item physics
model**. No adapter currently emits `MISC_SOFT` surfaces; adapter wiring
follows consumer demand, mirroring the D5 precedent for `x_aim_*` extension
keys (reserved before consumer wiring).

## Drivers

- v0.4 audit-findings Finding 4b (`.omc/plans/v0.4-audit-findings.md`)
  documented that the bare-walls 6-surface model under-counts the absorption
  budget for `Building_Lobby`, `Lecture_1`, `Office_1`, and `Office_2`
  (over-predicting RT60 at 500 Hz by +0.435 to +1.425 s). Soft furnishings
  and occupants are the most likely missing absorption term.
- D3's closed-enum policy was deliberately chosen to keep the absorption
  table authoritative; the v0.4 finding is the closed-enum reverse-trigger
  firing empirically.
- F4b is structurally independent of F1 (geometry / materials byte-audit) and
  ships cleanly under v0.5 SHORT-mode regardless of whether the TASLP
  materials-half landed (it didn't — see ADR 0010 and `.omc/plans/v0.5-design.md`
  §0a).
- D14 reverse-if explicitly listed "consider `MISC_SOFT` MaterialLabel enum
  extension for furnishings" as the v0.5 follow-up.

## Alternatives considered

- **Free-form `custom_label` per D3 reverse-trigger.** Rejected. D3's
  reverse-trigger fired empirically (the v0.4 audit found a missing
  absorption term), but the trigger only justifies "extend the enum coverage"
  — it does not justify opening the schema to arbitrary strings. An opt-in
  named slot is a smaller, reversible step; if `MISC_SOFT` proves
  insufficient, `custom_label` remains on the table for v0.6+.
- **Per-furnishing-item sub-enum** (`CHAIR`, `CURTAIN`, `BOOKS`, `OCCUPANT`).
  Rejected. Larger schema, larger ADR, no current consumer asking for it,
  and per-item physics would need verbatim Vorländer Appx A or measured
  rows — neither is in scope for v0.5 (D14 reaffirmed honesty-marker policy).
- **Defer F4b to v0.6.** Rejected. F4b is structurally independent of F1
  (the F1 dimensional half landed at v0.5; F1 materials and F3/F4a remain
  DEFERRED). Slipping F4b past v0.5 would force v0.6 to gain a "schema
  cleanup" headline, which is less useful per release than landing it now.

## Why chosen

Minimal-LoC schema slot mirroring D5 precedent (`x_aim_*` extension keys
reserved before consumer wiring). The same honesty-marker policy that
governs the v0.3 `MaterialAbsorptionBands` rows (representative typical
room-acoustics coefficients consistent with Vorländer 2020 Appx A class;
NOT verbatim Appx A rows) governs this row: an inline comment in
`roomestim/model.py` declares "representative mid-band profile for mixed
soft furnishings; not a verbatim Vorländer Appx A row" and lists the
reverse-trigger.

## Consequences

- (+) `MaterialLabel` gains one entry (8 → 9). The Stage-1 schema
  (`additionalProperties: true` per D2/D8) absorbs this gracefully; no
  `__schema_version__` flip needed.
- (+) The band-2 ↔ legacy-scalar invariant test extends automatically over
  the new enum entry; three new explicit MISC_SOFT tests
  (`test_misc_soft_in_material_label_enum`,
  `test_misc_soft_absorption_500hz_present_and_finite`,
  `test_misc_soft_in_sabine_rt60_smoke`) plus a fourth standalone
  invariant test (`test_misc_soft_band500_matches_legacy_scalar`) provide
  belt-and-braces coverage. Default-lane test count 80 → 84.
- (+) When the Stage-2 schema flip eventually happens (D8 reverse-if A10
  lab capture), `MISC_SOFT` is already a permanent member of the closed
  enum — the schema flip needs no additional ADR for this row.
- (+) Adapters that wish to opt in to a furnishings absorption line (a
  future v0.6+ ACE adapter; or an external adapter consumer) have a named,
  test-covered, ADR-documented slot to emit. No further roomestim changes
  needed for adapter wiring.
- (−) `0.40` and the `(0.20, 0.30, 0.40, 0.50, 0.60, 0.65)` band tuple are
  representative-not-verbatim. If the first adapter to emit `MISC_SOFT`
  finds the magnitude wrong for their use case, the reverse-trigger fires
  and the row is revisited.
- (−) The schema slot exists without any internal consumer at v0.5 ("feature
  dead-on-arrival" critique noted in `.omc/plans/v0.5-design.md` §6 R-II).
  Mitigated by the explicit "schema slot reserved; adapter wiring follows
  consumer demand" framing in the inline comment, the release notes, and
  this ADR — same precedent as D5's `x_aim_*` extension keys.
- (−) No verbatim citation source was acquired before shipping the row;
  this is the same trade-off accepted at v0.3 for the existing
  `MaterialAbsorptionBands` rows (D12 honesty marker).

## Reverse if

- ≥1 adapter starts emitting `MISC_SOFT` AND a downstream consumer reports
  the `0.40` / `(0.20, 0.30, 0.40, 0.50, 0.60, 0.65)` magnitude is wrong
  for their use case → revisit the coefficients with the empirical
  evidence from that consumer.
- A verbatim citation source (Vorländer 2020 Appx A "audience seated"
  row, Beranek 2004 Concert Halls Ch. 3 furnishings table, or similar) is
  later acquired and the numbers shift → patch and emit a v0.5.x release
  with the verbatim values.
- An adapter consumer requests a per-furnishing-item sub-enum (`CHAIR`,
  `CURTAIN`, `BOOKS`, `OCCUPANT`) → that is a larger ADR but does not
  conflict with `MISC_SOFT` continuing as the umbrella slot.

## References

- D3 — closed `material` enum (8 entries originally; `unknown` fallback).
- D5 — `aim_direction` exported as `x_aim_*` extension keys (precedent for
  reserving slots before consumer wiring).
- D7 / ADR 0008 — octave-band absorption schema extension (v0.3).
- D12 — D12 reverse-trigger fired empirically; honesty-marker policy.
- D14 — Eyring shipped; F4b explicitly listed as v0.5 follow-up.
- `.omc/plans/v0.5-design.md` §0a — locked scope (partial-A + B).
- `.omc/plans/v0.4-audit-findings.md` Finding 4b — original DEFERRED entry.
- Beranek, L. (2004). *Concert Halls and Opera Houses*, Ch. 3. Springer.
- Vorländer, M. (2020). *Auralization*, Appx A. Springer.
