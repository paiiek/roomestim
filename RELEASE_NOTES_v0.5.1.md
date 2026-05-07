# RELEASE NOTES — roomestim v0.5.1

v0.5.1 is a **bookkeeping-only audit-correction patch** on top of v0.5.0.
Zero code logic change. Default lane test count unchanged at 84.

## Why

The Eaton 2016 TASLP final paper (DOI 10.1109/TASLP.2016.2577502) was
obtained via SNU IEEE Xplore on 2026-05-07 — shortly after v0.5.0 shipped.
v0.4 / v0.5.0 audit framing assumed the paper contained a per-surface
material assignment table for the 7 ACE Challenge rooms. Reviewed cover-
to-cover, the paper does **not** contain such a table. v0.5.1 corrects the
framing so future audit cycles do not wait on a non-existent canonical
source.

## What changed (no code logic change)

### Adapter honesty caveats

- `roomestim/adapters/ace_challenge.py` module docstring + in-module
  honesty caveat + per-room `notes` string: updated to reflect "TASLP
  final reviewed; per-surface materials NOT in paper". Floor 4/7 BYTE-
  CONFIRMED at TASLP §II-C (carpet rooms only). Walls / ceiling remain
  best-guess.
- New Building_Lobby modelling caveat in the in-module honesty block:
  TASLP §II-C describes Building_Lobby as a "large irregular-shaped
  hard-floored room with coupled spaces". `ACE_ROOM_GEOMETRY` shoebox
  is the recording corner only — the room is not a shoebox.

### Audit ledger

- `.omc/plans/v0.4-audit-findings.md`: "Status update 2026-05-07
  (post-v0.5.0; framing correction at v0.5.1)" block appended. Original
  sections preserved for history.
- `.omc/plans/v0.5-audit-findings.md`: "Status update 2026-05-07
  (v0.5.1 — TASLP final reviewed)" block appended.

### Decisions log

- `.omc/plans/decisions.md`: D16 appended (D1–D15 bodies untouched).

### ADRs

- `docs/adr/0012-eaton-taslp-materials-not-in-paper.md` (NEW): full
  Decision / Drivers / Alternatives considered / Why chosen /
  Consequences / Reverse if / References. Closes the v0.4 Finding 1
  materials-half audit hunt with a "canonical-source exhausted" verdict.

### Version

- `pyproject.toml` and `roomestim/__init__.py`: 0.5.0 → 0.5.1.
- `__schema_version__` stays `"0.1-draft"`.

## What did NOT change

- All 84 default-lane tests pass byte-for-byte vs v0.5.0.
- `MaterialLabel` enum, `MaterialAbsorption`, `MaterialAbsorptionBands`:
  unchanged.
- `ACE_ROOM_GEOMETRY` numerical values: unchanged.
- Schema: unchanged.
- v0.5.0 perf doc at `docs/perf_verification_e2e_2026-05-07.md`:
  unchanged.
- v0.4 perf doc at `docs/perf_verification_e2e_2026-05-06.md`: unchanged.
- ADRs 0001–0011: unchanged.

## What v0.5.0 framing was vindicated

- Office_2 dimensional patch (W 3.50 → 3.22, H 3.00 → 2.94) and
  ADR 0010's "verified vs arXiv:1606.03365 Table 1" framing: TASLP
  Table I (p.1683) is byte-identical to arXiv 1606.03365 Table 1.
  v0.5.0 was correct.
- MISC_SOFT enum slot (ADR 0011): retroactively strengthened by TASLP
  §II-C explicit furniture counts (Office_2 "6 chairs + bookcase";
  Lecture_2 "~100 chairs + ~35 tables"; etc.). Per-room MISC_SOFT
  surface area is now derivable from canonical counts via Beranek 2004
  / Vorländer 2020 per-piece equivalent absorption — out-of-scope for
  v0.5.x; available for v0.6+.

## Tests

| Step | Command | Expected |
| --- | --- | --- |
| Default lane | `python3 -m pytest -m "not lab and not e2e" -q` | 84 passed, 3 skipped, 3 deselected (unchanged from v0.5.0) |
| Lint | `python3 -m ruff check` | All checks passed! |
| Version | `grep '^version\|__version__' pyproject.toml roomestim/__init__.py` | both 0.5.1 |

## Backwards compatibility

- `sabine_rt60`, `sabine_rt60_per_band`, `eyring_rt60`,
  `eyring_rt60_per_band`: byte-identical to v0.5.0.
- `MaterialAbsorption`, `MaterialAbsorptionBands` row values: unchanged.
- `ACE_ROOM_GEOMETRY` numerical values: unchanged.
- Schema unchanged.
- All 84 default-lane tests pass byte-for-byte.

## What stays DEFERRED

- Building_Lobby coupled-space modelling ADR (v0.6+ — needs design pass).
- Per-room MISC_SOFT surface area derived from TASLP §II-C furniture
  counts (v0.6+ — needs Beranek 2004 / Vorländer 2020 per-piece α
  table + adapter-level surface-budget pipeline + gated E2E re-run).
- Hard-floor subtype for Lecture_1 / Lecture_2 / Building_Lobby (needs
  non-canonical evidence: lab visit / author email / Imperial SAP
  internal report).
- Lecture_2 ceiling hypothesis (Finding 3) — canonical evidence path
  closed-with-no-result; non-canonical evidence required.
- Walls / ceiling assignments for all 7 rooms — INDETERMINATE (not
  TASLP-blocked); no canonical published source exists.
- Stage-2 schema flip / A10 lab capture (D8).
- Millington-Sette per-surface predictor (ADR 0009 alt-considered).
- 8 kHz octave band (ADR 0008 reverse criterion).
- PyPI / submodule (D11).

## Schema status

`__schema_version__ = "0.1-draft"` (Stage-1; `additionalProperties: true`).
Stage-2 flip remains deferred per D8.
