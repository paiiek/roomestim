# ADR 0012 — Eaton 2016 TASLP final reviewed; per-surface materials NOT in paper (audit closure for v0.4 Finding 1 materials half)

- **Status**: Accepted (v0.5.1)
- **Date**: 2026-05-07
- **Predecessor**: v0.5.0 (`9aea762`); ADRs 0010 (ACE-geometry-verified-arXiv) and
  0011 (MISC_SOFT-enum); D14, D15.

## Decision

Close the v0.4 Finding 1 materials-half audit hunt with a **canonical-source
exhausted** verdict. The Eaton 2016 TASLP final paper (DOI
10.1109/TASLP.2016.2577502) was reviewed cover-to-cover at v0.5.1 and does
**not** contain a per-surface material assignment table for the 7 ACE
Challenge rooms.

Future audit cycles must not propose "wait for TASLP" as the resolution
path for walls or ceiling material assignments. The framing in
`.omc/plans/v0.4-audit-findings.md` (Finding 1, "the canonical published
source is Eaton 2016 TASLP Table I") and in
`.omc/research/ace-table-i-acquisition.md` (TL;DR, "재질 배치 ... TASLP 본문에만
존재하는 것으로 판단") is corrected at v0.5.1.

Floors are partially confirmed against TASLP §II-C "Rooms" (p.1683):
- Office_1, Office_2, Meeting_1, Meeting_2 — TASLP says "carpeted" → roomestim
  `floor: carpet` BYTE-CONFIRMED.
- Lecture_1, Lecture_2, Building_Lobby — TASLP says "hard-floored" → roomestim
  `floor: wood_floor` is HARD-FLOOR-COMPATIBLE but the specific subtype
  (wood vs. concrete vs. tile vs. linoleum) is not in the paper.

Walls and ceiling are NOT in the canonical paper for any of the 7 rooms.
Existing roomestim `walls` / `ceiling` strings remain best-guess.

Building_Lobby gains a structural caveat documented in the adapter (and
mirrored to the audit-findings file): TASLP §II-C describes it as "large
irregular-shaped hard-floored room with coupled spaces including a café,
stairwell and staircase. Measurements in Table I correspond to the corner
area where the recordings were made whereas the total volume of the lobby is
many times larger." `ACE_ROOM_GEOMETRY["Building_Lobby"]` shoebox is the
recording corner, not the room. Sabine RT60 prediction on a non-shoebox
coupled space is not expected to match measurement.

## Drivers

- Honest audit ledger: shipping with "TASLP-blocked" markers after the paper
  is in hand and confirmed silent on materials would be a known-false marker.
- Process hygiene: the v0.4 → v0.5 → v0.5.1 chain should reflect what was
  actually established at each step. v0.5.1 corrects v0.4's optimistic
  framing.
- Permanent project memory: future audit cycles in v0.6+ must not repeat the
  "wait for TASLP" loop. The fact that TASLP is silent on walls/ceiling is
  durable and worth durable storage.

## Alternatives considered

- **(a) Do nothing — leave v0.5 framing as-is.** Rejected. The framing in v0.4
  audit-findings explicitly names TASLP as the canonical material source.
  Now-known to be wrong; leaving stale silently rots audit credibility.
- **(b) Edit the v0.4 / v0.5 audit-findings files in place to remove the
  "TASLP-blocked" framing.** Rejected. Erasing prior framing breaks the
  audit chain. Instead append a "Status update 2026-05-07" block that
  preserves history and records the correction.
- **(c) Author a v0.6 ADR with a full materials-from-canonical search across
  IEEE / ACM / Imperial College / arXiv / Zenodo / author email.** Out of
  scope for v0.5.1 (which is bookkeeping-only, no code changes besides
  adapter caveat). Captured as future v0.6 work item under "Reverse if".
- **(d) Add a new MaterialLabel enum entry like `WALL_UNVERIFIED` /
  `CEILING_UNVERIFIED`.** Rejected. Schema-impacting change; closed-enum
  reverse-trigger is not warranted by current evidence. The honesty caveat
  in the adapter docstring + per-room `notes` string is sufficient.
- **(e) Promote Lecture_2 ceiling Finding 3 from HYPOTHESIS to REJECTED
  because the canonical evidence path is closed.** Rejected. The hypothesis
  is neither supported nor refuted by the canonical paper; promoting to
  REJECTED requires positive evidence (lab visit, author email). Status
  stays HYPOTHESIS with the upstream evidence path documented as
  closed-with-no-result.
- **(f) Use TASLP §II-C furniture counts to derive per-room MISC_SOFT
  surface area now (in v0.5.1).** Rejected for v0.5.x. This is a real
  v0.6+ work item but requires Beranek 2004 / Vorländer 2020 per-piece
  equivalent absorption tables, an adapter-level surface-budget pipeline,
  and gated E2E re-runs. Out of scope for the audit-correction patch.

## Why chosen

Closing the materials hunt with an honest "canonical source exhausted"
verdict is the smallest correct move. It:
- Preserves the v0.5.0 dimensional patch and ADR 0010 framing (both
  vindicated by the now-in-hand TASLP Table I — byte-identical to arXiv).
- Strengthens v0.5.0 ADR 0011 (MISC_SOFT) with retroactive justification
  from TASLP furniture counts, without changing v0.5.x scope.
- Removes the ghost "TASLP-blocked" gate that future audit cycles would
  otherwise wait on indefinitely.
- Ships with zero code logic change — adapter caveat update + audit ledger
  appends + ADR + D16 + version bump only. Default-lane test count and
  byte-equality of every existing test are preserved.

## Consequences

- **Adapter (`roomestim/adapters/ace_challenge.py`)**: module docstring +
  in-module honesty caveat + per-room `notes` string updated to reflect
  TASLP-reviewed status. Building_Lobby coupled-space caveat added to the
  in-module honesty block. No data change.
- **Audit ledger** (`.omc/plans/v0.4-audit-findings.md`,
  `.omc/plans/v0.5-audit-findings.md`): "Status update 2026-05-07" blocks
  appended; original sections preserved for history.
- **Decisions log**: D16 appended; D14 and D15 bodies untouched.
- **Project memory**: `project_taslp_2016_content.md` records the paper's
  actual content map for permanent recall across sessions.
- **Tests**: zero change. Default lane stays 84; gated audit unchanged.
- **Schema**: zero change. `__schema_version__` stays `"0.1-draft"`.
- **Version**: `pyproject.toml` and `roomestim/__init__.py` bump 0.5.0 →
  0.5.1. Local-only tag `v0.5.1` (not pushed; D11 precedent).
- **v0.6 v0.6+ work item set updated**:
  - Per-room MISC_SOFT surface area derived from TASLP §II-C furniture
    counts (Beranek 2004 / Vorländer 2020 per-piece α).
  - Building_Lobby coupled-space modelling: explicit ADR for non-shoebox
    rooms; consider removing Building_Lobby from the v0.5 perf-doc
    Sabine/Eyring comparison or adding a `geometry_kind: shoebox|coupled`
    annotation to `ACE_ROOM_GEOMETRY`.
  - Hard-floor subtype confirmation for Lecture_1 / Lecture_2 /
    Building_Lobby — needs lab visit / author email / Imperial SAP report.
  - Lecture_2 ceiling hypothesis (Finding 3): same path — non-canonical
    sources only.

## Reverse if

- An author-provided supplementary material (Imperial College SAP internal
  report, lab visit photos, author email response) surfaces a real per-
  surface material assignment table for any of the 7 rooms → revisit in
  v0.6+ ADR; do not necessarily reverse D16, but supplement.
- A re-read of TASLP turns up materials in an appendix, figure caption, or
  supplementary-online file that this review missed → revert D16.
- ACE Challenge consortium publishes a follow-up dataset paper with
  materials → re-open Finding 1 materials half against the new source.

## References

- Eaton, J., Gaubitch, N. D., Moore, A. H., & Naylor, P. A. (2016).
  *Estimation of room acoustic parameters: The ACE Challenge.* IEEE/ACM
  Transactions on Audio, Speech, and Language Processing, 24(10), 1681–1693.
  DOI: 10.1109/TASLP.2016.2577502 (institutional access).
  - **Table I (p.1683)**: per-room L, W, H, V, mean FB T60. Byte-identical
    to arXiv:1606.03365 Table 1. **No material columns.**
  - **§II-C "Rooms" (p.1683)**: prose room descriptions — floor type +
    furniture counts only. **No walls, no ceiling.**
- Eaton, J., Gaubitch, N. D., Moore, A. H., & Naylor, P. A. (2016).
  *ACE Challenge Results Technical Report.* arXiv:1606.03365 (open access;
  Table 1 used as the dimensional source-of-truth at v0.5.0; ADR 0010).
- D14 — Eyring shipped; ACE byte-audit deferred (now partial-resolved).
- D15 — v0.5.0 partial-A (dims) + B (MISC_SOFT) shipped.
- D16 — v0.5.1 framing correction (this ADR's decisions-log mirror).
- ADR 0010 — ACE geometry verified vs arXiv:1606.03365 Table 1 (dims only).
- ADR 0011 — MISC_SOFT MaterialLabel extension.
- ADR 0013 — TASLP-derived MISC_SOFT surface budget per room (v0.6;
  consumes the §II-C furniture counts noted under "v0.6 v0.6+ work item
  set updated" above).
- ADR 0014 — Building_Lobby coupled-space exclusion from aggregate
  metrics (v0.7; formalises the structural caveat documented above).
- `.omc/plans/v0.4-audit-findings.md` "Status update 2026-05-07".
- `.omc/plans/v0.5-audit-findings.md` "Status update 2026-05-07 (v0.5.1)".
- `.omc/plans/v0.6-audit-findings.md` (TASLP-MISC ship summary).
- `roomestim/adapters/ace_challenge.py` honesty caveats (v0.5.1, v0.6).
- Project memory: `project_taslp_2016_content.md` (paper content map).
