# RELEASE NOTES — roomestim v0.6.0

v0.6.0 wires the v0.5.0 `MaterialLabel.MISC_SOFT` schema slot to the
ACE Challenge adapter using TASLP §II-C explicit per-room furniture counts
(Eaton 2016) and per-piece equivalent-absorption rows from textbook tables
(Vorländer 2020 §11 / Appx A primary; Beranek 2004 Ch.3 cross-check). Six
of the 7 ACE rooms gain one synthesised `Surface(material=MISC_SOFT)`
each; Building_Lobby is excluded by default per its coupled-space caveat
(ADR 0012). Two LOW retrospective fixes from v0.5.1 are folded in.

A12 byte-equality of every v0.5.1 default-lane test is preserved (84 →
100; +16 new MISC_SOFT-budget tests; nothing existing is modified).
`__schema_version__` stays `"0.1-draft"`. No new enum entry.

---

## Highlights

- **TASLP-derived per-room MISC_SOFT surface budget**:
  `roomestim/adapters/ace_challenge.py` gains `_PIECE_EQUIVALENT_ABSORPTION_*`
  per-piece α tables, `_FURNITURE_BY_ROOM` per-room counts (factual data
  from TASLP §II-C; not copyrightable), `_furniture_to_misc_soft_area`,
  and `_misc_soft_surface_from_furniture(room_id, room_dimensions)`.
  `_build_room_model` appends the synthesised surface iff the helper
  returns non-None. Surface count goes 6 → 7 for the 6 furniture-tracked
  rooms; Building_Lobby stays at 6 (coupled-space exclusion).
- **Empirical validation of v0.4 Finding 4 hypothesis**: Lecture_1
  Sabine 500 Hz error collapses from +1.201 s to +0.125 s post-v0.6.
  Office_1 / Office_2 over-prediction drops by 0.16 – 0.23 s. The v0.6
  perf doc at `docs/perf_verification_e2e_2026-05-08.md` records the
  full per-room per-band envelope.
- **LOW-RETRO docstring softening**: code-reviewer (LOW-RETRO-1) and
  security-reviewer (LOW-RETRO-2) findings from v0.5.1 are addressed in
  the adapter module docstring + in-module honesty caveat + ADR 0012
  References.

---

## What changed

### ACE adapter — TASLP-MISC plumbing

- `roomestim/adapters/ace_challenge.py`:
  - +`_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2` (5 rows: office_chair 0.50,
    stacking_chair 0.15, lecture_seat 0.45, table 0.10, bookcase 0.30 m²
    Sabines per piece).
  - +`_PIECE_EQUIVALENT_ABSORPTION_BANDS_M2` (per-piece per-band tuples;
    band-2 ↔ legacy-scalar invariant preserved by construction).
  - +`_FURNITURE_BY_ROOM` (6 rooms; Building_Lobby intentionally absent).
  - +`_furniture_to_misc_soft_area(furniture)` — integrand-preserving
    formula.
  - +`_misc_soft_surface_from_furniture(room_id, room_dimensions)` —
    builds synthetic Surface or returns None; includes strip-clip path
    for the Lecture_2 case where `√area > min(L, W)`.
  - `_build_room_model(room_id, geom)` appends the synthesised surface
    iff helper returns non-None.
  - `load_room(...)` `notes` string updated per room (MISC_SOFT
    synthesised vs intentionally NOT synthesised).
  - Module docstring + in-module honesty caveat softened
    (LOW-RETRO-1, LOW-RETRO-2).

### Tests

- `tests/test_misc_soft_furniture_budget.py` (NEW; +16 default-lane
  tests):
  - Per-piece band-2 ↔ scalar invariant.
  - Per-room exact-area assertions for Office_1, Office_2, Meeting_1,
    Meeting_2, Lecture_1, Lecture_2 (closed-form values from
    integrand-preserving formula).
  - `KeyError` on unknown piece.
  - `Building_Lobby` exclusion; unknown room → None.
  - Lecture_2 strip-clip path with Newell-area assertion + footprint-fit
    check (R-3 risk mitigation).
  - RoomModel surface-count wiring (6→7 for Lecture_2; 6 unchanged for
    Building_Lobby).
  - Per-band band-2 ↔ legacy-scalar invariant for the synthesised
    Surface object.

### Documentation

- `docs/adr/0013-taslp-misc-soft-surface-budget.md` (NEW): full Decision
  / Drivers / Alternatives considered / Why chosen / Consequences /
  Reverse if / References. Cites Vorländer 2020 §11 / Appendix A
  (primary) and Beranek 2004 Ch.3 Table 3.1 (cross-check) per OQ-6 lock.
- `docs/adr/0012-eaton-taslp-materials-not-in-paper.md`: References
  cross-ref appended (ADR 0013, v0.6 audit-findings, v0.6 honesty
  caveats); LOW-RETRO-2 softening in DOI line. ADR 0012 body (Decision
  / Drivers / Alternatives considered / Why chosen / Consequences /
  Reverse if) is byte-identical to v0.5.1.

### Bookkeeping

- `.omc/plans/decisions.md`: D17 appended (D14, D15, D16 bodies
  untouched).
- `.omc/plans/v0.6-audit-findings.md` (NEW): per-finding status post-
  v0.6.
- `.omc/plans/open-questions.md`: OQ-6..OQ-10 marked `[x]` with
  executor confirmation note.
- `pyproject.toml`, `roomestim/__init__.py`: 0.5.1 → 0.6.0.
- `tests/test_e2e_ace_challenge_rt60.py`: REPORT_PATH bumped from
  `2026-05-07.md` to `2026-05-08.md`; "Generated" date and "v0.5" →
  "v0.6" version line bumped accordingly. v0.5 / v0.4 perf docs
  preserved byte-identical.

---

## Perf doc — v0.5 vs v0.6 deltas

The gated E2E test at `tests/test_e2e_ace_challenge_rt60.py` writes its
report to `docs/perf_verification_e2e_2026-05-08.md`. v0.5 doc at
`2026-05-07.md` and v0.4 doc at `2026-05-06.md` are preserved.

500 Hz Sabine error envelope (s):

| Room | v0.5 err | v0.6 err | Δ |
| --- | ---: | ---: | ---: |
| Building_Lobby | +1.425 | +1.425 | 0.000 (excluded) |
| Lecture_1 | +1.201 | +0.125 | −1.076 |
| Lecture_2 | −0.670 | −0.908 | −0.238 |
| Meeting_1 | +0.072 | −0.017 | −0.089 |
| Meeting_2 | +0.061 | −0.012 | −0.073 |
| Office_1 | +0.486 | +0.327 | −0.160 |
| Office_2 | +0.410 | +0.179 | −0.231 |

Eyring monotonicity (`eyring_500hz <= sabine_500hz + 1e-9`) preserved
per room and per band; runtime-asserted in the gated E2E.

---

## What stays deferred

- **F1 walls / ceiling materials**: INDETERMINATE (not TASLP-blocked;
  no canonical source). Unchanged from v0.5.1 (ADR 0012 / D16).
- **F3 — Lecture_2 ceiling hypothesis**: canonical evidence path
  closed-with-no-result. v0.6 numbers are consistent with the
  hypothesis (Lecture_2 under-prediction deepens after MISC_SOFT
  added); confirmation still requires non-canonical evidence (lab
  visit / author email).
- **`lecture_seat` α₅₀₀ revision (v0.7+ candidate)**: Lecture_2 fires
  the empirical reverse-trigger condition flagged in retrospective
  review — |err| = 0.908 s = 67.6% of measured 1.343 s, exceeding both
  common heuristics (|err|/measured > 50%; |err| > 0.50 s absolute).
  100 lecture_seat × α=0.45 on an empty hall over-corrects; the
  textbook-cited 0.45 may be the occupied-row rather than empty. v0.7
  ADR should split occupied vs unoccupied rows OR revise the locked
  α downward (toward 0.20–0.25 effective) and re-cite. Also
  entangled with F3 (ceiling material uncertain) — disentangling
  requires either a non-canonical evidence channel for ceiling OR
  per-piece α empirical fit on Lecture_1 (which is correctly predicted
  at v0.6, suggesting the seat α is ok but ceiling/seats interact).
- **F4a — `MaterialAbsorptionBands` coefficient revision**: D14 5b
  pre-condition unchanged.
- **Hard-floor subtype**: needs lab visit / author email.
- **Building_Lobby coupled-space ADR**: separate v0.7+ work item.
- **Stage-2 schema flip / A10 lab capture** (D8).
- **Millington-Sette predictor** (ADR 0009 alt-considered).
- **8 kHz octave band** (ADR 0008 reverse criterion).
- **PyPI / submodule** (D11).

---

## Tests

| File | Count | Markers |
| --- | ---: | --- |
| `tests/test_misc_soft_furniture_budget.py` | +16 | (none — default lane 84 → 100) |
| All other test files | unchanged | — |

Default-lane collected: **100** tests (84 v0.5.1 + 16 v0.6 MISC_SOFT
budget). `ruff check` clean. Gated e2e deselected: 3 (unchanged).

| Step | Command | Expected |
| --- | --- | --- |
| Default lane | `python3 -m pytest -m "not lab and not e2e" -q` | 100 passed, 3 skipped, 3 deselected |
| Lint | `python3 -m ruff check` | All checks passed! |
| Version | `grep '^version\|__version__' pyproject.toml roomestim/__init__.py` | both 0.6.0 |

---

## Backwards compatibility

- `sabine_rt60`, `sabine_rt60_per_band`, `eyring_rt60`,
  `eyring_rt60_per_band`: byte-identical to v0.5.1.
- `MaterialAbsorption`, `MaterialAbsorptionBands` row values: unchanged.
- `MaterialLabel` enum entries: unchanged (9 members; no new entry).
- `__schema_version__`: `"0.1-draft"` unchanged.
- All 84 v0.5.1 default-lane tests pass byte-for-byte.
- No CLI flag added; no public adapter signature changed.
- `ACE_ROOM_GEOMETRY` numerical values: unchanged.
- The 6 furniture-tracked rooms now emit one additional synthesised
  `Surface(material=MISC_SOFT)` each (surface count 6→7). The existing
  `tests/test_ace_adapter_with_sample_fixture` smoke test asserts
  `len(areas) > 0`, `volume > 0`, and `predicted_500hz > 0` — all
  continue to hold (a new MISC_SOFT material adds a new key but does
  not invalidate the smoke assertions).

---

## Schema status

`__schema_version__ = "0.1-draft"` (Stage-1; `additionalProperties: true`).
Stage-2 flip remains deferred per D8. The v0.6 MISC_SOFT surface
emission is absorbed by Stage-1 schema gracefully. No cross-repo schema
PR needed at v0.6.
