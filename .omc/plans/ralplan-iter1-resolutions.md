# roomestim — RALPLAN-DR Iter 1 Resolutions (2026-05-03)

> Consensus loop record between Planner / Architect / Critic on whether to proceed to autopilot
> of P1–P6. Iter 1 verdicts and the 5 resolutions applied before iter 2 re-review.

## Verdict chain

| Reviewer | Verdict | Summary |
|---|---|---|
| Planner | `READY-WITH-MINOR-ADJUSTMENTS` | 3 Gs proposed: G1 fixture strategy, G3 RT60 reference, G4 Stage-2 sign-off |
| Architect | `ARCHITECT-REVISE` | G1→commit JSON-sidecar, G3→pre-computed Sabine only, drop G4 (redundant), add G5 (autopilot exit boundary) |
| Critic | `ITERATE` (5 fixes) | G5 reframe; A9 split a/b; A11 synthetic-shoebox fallback + Sabine unit test; G1 artifact paths locked; §8 per-phase command list |

## Five resolutions applied

### Fix 1 — G5 reframe (Critic) — `decisions.md` D8 added

Autopilot exits with Stage-1 `room.yaml` shipped + A10 `@pytest.mark.lab` SKIP. Stage-2 flip
and A10 capture stay inside v0.1 but are human-gated post-autopilot. `RELEASE_NOTES_v0.1.md`
will document this. A11 falls back to a synthetic shoebox so RT60 testability does not
depend on A10.

Rejected alternative: "promote A10 to v0.2" — gutted v0.1 identity. D8 documents both options.

### Fix 2 — A9 split into A9a + A9b — `decisions.md` D9 added

A9 splits to:
- **A9a (default CI)**: `tests/fixtures/lab_room.json` (RoomPlan JSON-sidecar mock) + `tests/fixtures/lab_room.meta.yaml` (ground-truth metadata). Runs unconditionally.
- **A9b (gated)**: real `tests/fixtures/lab_room.usdz` parses via the same `roomplan_adapter.parse(...)` path. SKIP if absent.

Same fixture and metadata files are P4-task-1 deliverables; commit before any P4 implementation.

### Fix 3 — A11 fallback (Critic fix #3)

When A10 SKIPs (default autopilot lane), A11 cannot reference the real lab room's RT60.
Replacement: A11 references a **synthetic shoebox of known volume + Vorländer 2020 Appx A
absorption coefficients** as the RT60 source-of-truth. New unit test
`test_sabine_constant_matches_vorlander_appendix_a` asserts the precomputed RT60 ∈
`[textbook_sabine ± 10%]` for a fixed shoebox (e.g., 5×4×2.8 m, walls=painted, floor=wood,
ceiling=acoustic_tile). This guards against silent absorption-table bugs without requiring
the lab fixture.

When A10 is performed (post-autopilot), A11 reverts to the lab-room reference.

### Fix 4 — G1 artifact paths (Critic fix #4) — `decisions.md` D9

Sidecar fixture is named explicitly:
- `tests/fixtures/lab_room.json` — RoomPlan-format JSON sidecar
- `tests/fixtures/lab_room.meta.yaml` — ceiling height, floor area, wall count, listener-area centroid (ground truth for A9a tolerance check)

Both files are P4-task-1 deliverables, committed before any reconstruct/adapter code lands.

### Fix 5 — §8 per-phase gate commands (Critic fix #5)

Added below as the autopilot per-phase boundary commands. Autopilot prompt prefixes this list.

```bash
# After P1 (RoomModel + room.yaml export + CaptureAdapter Protocol):
pytest tests/test_export_room_yaml.py tests/test_adapter_protocol.py -v && mypy --strict roomestim/
# Gates: A3 (room.yaml schema-validates AND finite), Protocol type-checks.

# After P2 (layout.yaml export + engine round-trip):
pytest tests/test_export_layout_yaml.py tests/test_engine_roundtrip.py tests/test_coords_engine_parity.py -v && mypy --strict roomestim/
# Gates: A1 (layout.yaml validates AND finite); A2/A15 SKIP-or-pass per env var.

# After P3 (VBAP + DBAP placement):
pytest tests/test_placement_vbap.py tests/test_placement_dbap.py tests/test_placement_under_noise.py -v && mypy --strict roomestim/
# Gates: A5/A6 (VBAP ring/dome <1°), A7 (DBAP coverage), A16 (noisy degradation <2× clean).

# After P4 (RoomPlan adapter via sidecar + reconstruction):
pytest tests/test_adapter_roomplan.py tests/test_room_acoustics.py -v && mypy --strict roomestim/
# Gates: A9a (sidecar fixture parses; ceiling ±10cm, area ±5%, walls ≥4, listener centroid emitted),
#        A11 (Sabine RT60 within 10% of Vorländer reference for synthetic shoebox).

# After P5 (WFS placement + Polycam adapter):
pytest tests/test_placement_wfs.py tests/test_adapter_polycam.py -v && mypy --strict roomestim/
# Gates: A8 (WFS λ/2 spacing + alias-freq surfacing), Polycam fixture parses.

# Before tagging v0.1 (P6 ship gate):
pytest -m "not lab" -v
pytest tests/test_cli_idempotent.py tests/test_no_external_writes.py -v
mypy --strict roomestim/
# Gates: A12 (idempotent CLI), A13 (headless CI), A14 (no external writes); full default lane green.
# A10 (@pytest.mark.lab) explicitly SKIPped — see D8 (post-autopilot human gate).
```

**A9a listener-centroid tolerance** (Architect iter-2 rec): `lab_room.meta.yaml` carries
`listener_centroid: {x: <float>, z: <float>}` as ground truth. A9a asserts the parsed
`RoomModel.listener_area.centroid` matches within ±10 cm (matches A10's wall-corner
tolerance). If the YAML omits the field, the centroid is "emitted, not gated" (A9a only
checks ceiling/area/walls). This keeps the field optional in the meta YAML while gating
when present.

## Open items not blocking iter 2

- Verify `spatial_engine/docs/lab_setup.md` documents the lab room's volume numerically. If
  absent, the synthetic-shoebox fallback (fix 3) makes Sabine reference computable
  independently of `lab_setup.md`. If present, A10 (post-autopilot) gains an extra check.
- Sidecar fixture writes commit cleanly under autopilot — no human handoff needed (the file
  is hand-authored YAML/JSON, not a real device capture).

## Iter 2 outcome (2026-05-03)

| Reviewer | Iter 1 | Iter 2 | Notes |
|---|---|---|---|
| Planner | READY-WITH-MINOR-ADJUSTMENTS | (deltas applied as D8/D9 + this addendum) | — |
| Architect | ARCHITECT-REVISE | **ARCHITECT-APPROVE** | 2 non-blocking recs (mypy P2-P5, centroid tolerance) — folded into §5 above and A9a note. |
| Critic | ITERATE (5 fixes) | **APPROVE** | All 6 RALPLAN-DR criteria pass; D8/D9 resolve P5 violation, A9 split prevents regression, synthetic-shoebox closes A11 fallback. |

**Final RALPLAN-DR verdict: APPROVED for autopilot kickoff of P1–P6.** Autopilot exits with:
- Stage-1 schema (`version: "0.1-draft"`) shipped.
- `pytest -m "not lab"` default lane green at every phase boundary (commands listed in §5).
- A10 SKIP-pending-human-capture; Stage-2 flip + cross-repo PR are post-autopilot work per D8.

ADR transition: `roomestim-v0-design.md` §12 ADR moves from `PROPOSED` to `Accepted` upon autopilot kickoff (this file is the consensus record satisfying §12's "after their reviews, this document is updated in place" clause for v0.1 execution gating).
