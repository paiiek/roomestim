# ADR 0007 — Distribution model for roomestim (DEFERRED)

- **Status**: Accepted (v0.2; recorded as DEFERRAL)
- **Date**: 2026-05-06
- **Cross-ref**: design plan §11.3, decisions D1, D11; v0.1.1 closeout §7 (a)/(c).

## Context

D1 (`.omc/plans/decisions.md`) deferred the submodule-vs-PyPI choice to v0.2 ADR.
v0.2 ships ~1 day after v0.1.1 (cd78c0d, 2026-05-05). Neither D1 reverse criterion has fired:

- (i) Engine team has not requested vendoring.
- (ii) CI maintenance cost since v0.1 is < 1 day/month (no incidents in the 1-day window).

Three viable distribution paths remain:

- (a) Standalone git repo — current state since v0.1
- (b) Git submodule under `spatial_engine/third_party/roomestim/`
- (c) PyPI publish under name `roomestim`

## Decision

**DEFER** the choice. v0.2 ships as standalone (option (a)), unchanged from v0.1.
ADR 0007 records the decision context and re-evaluation criteria.

## Drivers (evidence as of 2026-05-06)

1. **Time elapsed since v0.1.1**: ~1 day. No reverse-criterion signal possible.
2. **Cross-repo PR rounds since v0.1.1**: 0 (the cross-repo PR for room_schema.json is drafted
   in `.omc/autopilot/cross-repo-pr-room-schema.md` but NOT yet opened against spatial_engine).
3. **Real-world room.yaml count produced since v0.1.1**: 0 (D2/D8 lab capture is post-autopilot).
4. **CI maintenance hours since v0.1.1**: ~0 (no incidents in 1-day window).
5. **Sibling-repo precedent**: vid2spatial, claude_text2traj are standalone — consistent with (a).

## Alternatives considered

- **(b) Submodule**: rejected for now — requires engine-team coordination AND a tested branch
  hygiene process. No evidence yet that the cross-repo coordination tax is high enough to justify it.
- **(c) PyPI**: rejected for now — adds release-process complexity (semver discipline, name claim,
  packaging-test CI) for no measured benefit in the 1-day window.

## Why chosen (defer)

The decision space is fundamentally evidence-limited at v0.2. Forcing a choice would either
fabricate rationale or pre-commit to a structure that the next 30 days of usage may invalidate.
Mirrors v0.1.1 closeout Critic M1 honesty principle: "do not promote audit/deferral to closure."

## Consequences

- (+) No migration cost at v0.2.
- (−) Ambiguity remains for downstream consumers; resolved at v0.3 or sooner if a reverse trigger fires.
- Migration plan if reverted to (b) or (c): a future ADR 0007a will spec the migration mechanics.

## Reverse criteria (per D1)

- Engine team explicitly requests vendoring → flip to (b).
- CI maintenance cost > 1 day/month over a 30-day window → flip to (b).
- ≥1 external consumer requests `pip install roomestim` → consider (c) — but only if (b) is also evaluated and rejected.

## Follow-ups

- Cross-repo PR for room_schema.json: `.omc/autopilot/cross-repo-pr-room-schema.md`. Engine-team review of the schema is INDEPENDENT of this distribution decision.
- Re-evaluate at v0.3 ship or after first cross-repo PR exchange, whichever comes first.
- D11 entry in decisions.md records this deferral.
