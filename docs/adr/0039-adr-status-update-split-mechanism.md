# ADR 0039 — ADR §Status-update split mechanism (v0.22.1)

**Date**: 2026-05-28
**Status**: ACCEPTED
**Deciders**: planner (this design), executor (this commit)
**Drivers**: OQ-39 closure for ADR 0030; D22 audit-trail-discipline operational
refinement; reusable pattern for any future ADR hitting the same growth
threshold.

---

## Context

D22 audit-trail-discipline (append-only §Status-update blocks; no retroactive
edits) is load-bearing for traceability. Side-effect: ADRs that land policy in
a long-cycle area accrete §Status-update blocks monotonically. ADR 0030
(predictor-default-switch) is the first to hit a navigability threshold (477
lines, 10 blocks); ADRs 0031 (per-band promotion), 0033 (engine validation
toggle), 0034 (object schema), 0036 (placement edit), 0037 (wall_index frame)
each carry 3–5 blocks now and are on the same trajectory.

## Decision

When an ADR reaches BOTH of the following AND a documented navigation-pain
report:

1. **Line count > 400**, AND
2. **§Status-update block count ≥ 6**

…relocate all §Status-update blocks to a sibling companion file named
`<adr-stem>-status-updates.md` in the same `docs/adr/` directory. The original
file retains §A–§E (or §Context + §Decision + §Consequences +
§Reverse-criterion + §References — whatever the ADR's structural top-level
sections are) and inserts a single forward-pointer block before its closing
`---`:

```markdown
## §Status-update history
All §Status-update blocks have been relocated to the companion file (OQ-39 /
D73 closure): → `<adr-stem>-status-updates.md`. Each block is byte-equal to
its pre-split content. Future §Status-update blocks land in the companion file.
```

The companion file gets a minimal header (companion-to pointer + purpose +
block-order note) and the §Status-update bodies copied byte-equal.

**Trigger combination is conjunctive** (lines AND blocks AND navigation-pain)
to prevent premature splits — a 600-line ADR with 2 blocks is probably just a
long ADR; a 200-line ADR with 8 blocks is probably mis-structured.

**lint_tense compatibility**: both files remain in `docs/adr/*.md` glob
scope; §Status-update header anchor exclusion continues to apply inside the
companion file. No `# noqa` needed.

**Cross-reference compatibility**: existing references to "ADR 0030" or
"ADR 0030 §A" resolve to the original file (preserved). References to "ADR
0030 §Status-update-v0.X" resolve via the forward-pointer + companion file.
No outgoing reference rewrite required.

## Consequences

- (+) ADR core decisions (§A–§E) become re-readable in audit cycles.
- (+) D22 audit-trail-discipline preserved (split = relocation, not retroactive
  edit; future status-updates append to companion file).
- (+) No incoming cross-reference rewrite — the canonical file name doesn't
  change.
- (−) Two files per long-lived ADR (mild file-count growth).
- (−) New readers must follow one pointer to find historical context.

## Reverse-criterion

1. **Companion file itself exceeds 800 lines** → split into per-version
   subdirectory (Option 2 from OQ-39 resolution candidates).
2. **A reviewer reports navigation-pain in the companion file** (e.g., cannot
   find a specific §Status-update block fast) → either index block at the top of
   the companion file, or per-version split.
3. **Future ADR is split prematurely** (before all 3 triggers are met) → tighten
   the rule with explicit examples.

## References

- ADR 0030 — first application of the split mechanism (v0.22.1).
- D22 — audit-trail-discipline (no retroactive edits to §Status-update blocks).
- D73 — ADR 0030 split + README schema-marker reconcile decision.
- OQ-39 — original deferral with trigger conditions.
- D26 — forbidden-indefinite-deferral clause (made OQ-39 forced-decision).
- D72 — honesty-re-review precedent.
