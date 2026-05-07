# ACE Challenge adapter geometry audit

- Generated: 2026-05-07 by `tests/test_ace_geometry_audit.py`
- Source of truth: arXiv:1606.03365 Table 1 (TASLP supporting material; open access; transcribed 2026-05-06).
- Fixture: `tests/fixtures/ace_eaton_2016_table_i_arxiv.csv`.
- Caveat: **dimensions only.** Material assignments (`floor`, `walls`, `ceiling`) are NOT cross-checked — Eaton 2016 TASLP final paper is paywalled; materials deferred to v0.6+.
- L/W convention: roomestim keeps "longer dimension as L". The audit compares unordered `{L, W}` set as a multiset on the floor plane (allowing arXiv L/W swap on Office_1 / Office_2 / Building_Lobby). H must match exactly within ±0.01 m.
- Tolerance: ±0.01 m.

## Per-room status

| Room | Status | Notes |
| --- | --- | --- |
| Office_1 | OK | dims-only; materials not checked |
| Office_2 | OK | dims-only; materials not checked |
| Meeting_1 | OK | dims-only; materials not checked |
| Meeting_2 | OK | dims-only; materials not checked |
| Lecture_1 | OK | dims-only; materials not checked |
| Lecture_2 | OK | dims-only; materials not checked |
| Building_Lobby | OK | dims-only; materials not checked |

## Deltas

No dimensional deltas. All 7 rooms agree within tolerance.

