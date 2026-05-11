# ADR 0020 — CI lint policy for present-tense version-specific framing

- **Status**: Accepted (v0.11.0)
- **Date**: 2026-05-11
- **Cross-ref**: D22 (audit-trail-discipline pattern; §Status-update /
  §Honesty-correction block-exclusion precedent), D24 (NEW v0.11; CI
  lint policy codification), ADR 0019 (MELAMINE_FOAM enum; same v0.11
  release), OQ-13h (resolved at v0.11), `scripts/lint_tense.py`,
  `tests/test_lint_tense.py`, `.github/workflows/ci.yml`.

## Decision

v0.11 ships a **CI lint** flagging present-tense version-specific
framing in fixture README + ADR + past-version RELEASE_NOTES files.
The mechanism is a **standalone Python script** (`scripts/lint_tense.py`)
invoked from a **GitHub Actions step** in `.github/workflows/ci.yml`.

### Scope (3 file families)

- `tests/fixtures/**/README.md` — fixture context that contributors
  read alongside the data.
- `docs/adr/*.md` — architectural decision records (every ADR is
  written for posterity; past-tense framing keeps the audit trail
  readable as the project ages).
- `RELEASE_NOTES_v*.md` — every PAST-version release notes file.
  The **current-version** release notes (`RELEASE_NOTES_v0.11.0.md`
  at v0.11 ship time) are **EXCLUDED** from scope — current-version
  release notes are inherently in present tense ("v0.11.0 ships X",
  "v0.11.0 closes OQ-13a"), and forcing past tense at ship time
  is incoherent. The asymmetry is documented: future release-cycle
  scripts must rotate the exclusion as the current version moves
  forward (see §Reverse-criterion).

### Pattern (word-bounded)

```
\bwe ship\b | \bship in v0\.[0-9]+\b
```

Word-bounded to reduce false positives (e.g., "internship",
"craftmanship" do not match; "ship" inside "shipped" / "shipping"
does not match because the boundary regex requires the literal
word).

### Block exclusion (per D22)

Lines INSIDE a `## §Status-update-` or `## §Honesty-correction-`
markdown section are SKIPPED. These section headers are the
canonical audit-trail anchors per D22 (v0.10.1); their content
records WHY a past correction landed and is inherently in present
tense at the time of recording. The block extends from the
matching header to the next `## ` or `# ` header at the same depth,
or end of file.

### Per-line escape

A line containing the case-insensitive marker `# noqa: lint-tense`
is excluded even outside any block. Rationale comment recommended
(e.g., `# noqa: lint-tense — intentional doc example`).

### False-positive policy

**ZERO blocking false-positives at v0.11 ship time.** Any
false-positive must be either (a) rewritten in past tense; or
(b) suppressed via `# noqa: lint-tense` with rationale; or (c)
escalated for scope adjustment. At v0.11 ship time, the live-repo
run flagged **0 files** (well under the §0.4 STOP rule #7
threshold of > 3 files).

## Drivers

1. **OQ-13h** (v0.10.1) — fixture README body carried v0.9-tense framing beneath the v0.10 §Honesty-correction prepend; v0.10.1 fixed lines in place but did not prevent recurrence. v0.11 adds the CI lint to prevent the class of issue.
2. **D22 audit-trail-discipline** at v0.10.1 established `## §Status-update-` / `## §Honesty-correction-` blocks as canonical past-tense anchors; the lint must EXCLUDE those blocks or it punishes the very pattern D22 prescribes.
3. **Procedural complement to ADR 0019** — alongside MELAMINE_FOAM (substantive remediation), the lint is the v0.11 honesty-discipline procedural cap.

## Alternatives considered

- **(a) Pre-commit hook.** Rejected: requires user installation; bypassable with `--no-verify`. Acceptable as v0.12+ warn-only fallback if the GH Actions step proves flaky.
- **(b) Pytest-collection-time check.** Rejected: lint is not a test; flaky lint would block test execution.
- **(c) GH Actions step + standalone script.** ACCEPTED — matches existing ruff/mypy pattern; reproducible locally; smoke test exercises seeded-fixture branches (mitigates §5.3 pre-mortem).
- **(d) `git grep` one-liner without a script.** Rejected: D22 block-exclusion is not expressible as a single grep pattern.
- **(e) Allow-list-based per-file suppression.** Rejected for v0.11 (zero false-positives at ship); reversible if rate exceeds 1 per 10 files at v0.12+.

## Why chosen

- **Smallest mechanism that respects D22**: standalone script + 5 invariants (scope, pattern, block-exclusion, noqa, current-version-RN exclusion).
- **Reproducible locally**: `python scripts/lint_tense.py`; no Docker / env-var setup.
- **Mitigates §5.3 pre-mortem**: seeded-fixture branches exercise both excluded + flagged paths.
- **Matches existing CI step style** (ruff + mypy in the same workflow).

## Consequences

- **(+) CI gate prevents recurrence** of the OQ-13h pattern.
- **(+) Default-lane test count +1**.
- **(+) Block-exclusion respects D22**.
- **(+) Per-line `# noqa: lint-tense` escape** keeps the lint reversible.
- **(−) Asymmetric scope** on current-version release notes (constant must rotate at each release).
- **(−) +~5 s CI**.

## Reverse-criterion

- GH Actions step flaky at v0.12+ → switch to pre-commit advisory (warn-only).
- False-positive rate > 1 per 10 files at v0.12+ → allow-list-based suppression.
- Scope too narrow (leak in `docs/perf_verification_*.md` / `architecture.md`) → expand scope under successor ADR, not silently.
- Current-version exclusion forgotten at v0.12+ → smoke test catches it in CI of release commit.

## References

- D22 (block-exclusion precedent), D24 NEW (codification) — `.omc/plans/decisions.md`.
- ADR 0019 NEW (same v0.11 release).
- OQ-13h (resolved v0.11) — `.omc/plans/open-questions.md`.
- `scripts/lint_tense.py`, `tests/test_lint_tense.py`, `.github/workflows/ci.yml`.
- `.omc/plans/v0.11-design.md` §5.3 pre-mortem (lint-honesty-leak mitigation).
- `RELEASE_NOTES_v0.11.0.md`.
- `tests/fixtures/soundcam_synthesized/README.md` — OQ-13h triggering case (fixed v0.10.1; protected by this lint).

## §Status-update-2026-05-12 (v0.12.0) — lint scope expansion

**Expansion outcome (D22 hybrid pattern, operational refinement: scope
list grows)**: v0.12 fires the OQ-13h reverse-criterion "scope expansion
if a leak lands outside current scope" preemptively (no leak landed at
v0.11 ship time, but the README.md rewrite that accompanied v0.11.0
shipping (`8ab5d54` weekly progress + README sync) is the most likely
future-leak surface for v0.12+). Per `.omc/plans/v0.12-design.md` §2.4
+ §10.7-§10.8, the scope expansion adds **3 new file families** to
`scripts/lint_tense.py::_scoped_files()`:

- `docs/perf_verification_*.md` (7 files at v0.12 ship: `_2026-05-04`,
  `_a10a_soundcam_2026-05-09`, `_a10_soundcam_2026-05-10`,
  `_e2e_2026-05-06/07/08`, `_lecture2_bracket_2026-05-09`).
- `docs/architecture.md` (1 file).
- `README.md` (1 file — the top-level project landing page).

Pattern + block-exclusion + per-line escape semantics are **UNCHANGED**;
this is an additive scope-list extension, NOT a mechanism revision.
Current-version `RELEASE_NOTES_v*.md` exclusion constant rotates from
`RELEASE_NOTES_v0.11.0.md` → `RELEASE_NOTES_v0.12.0.md` (asymmetry
documented at v0.11; rotation per v0.11 §Reverse-criterion item 4).

**v0.12 first-run flag count**: **0 files flagged** on the expanded
5-family scope (well under v0.12 §0.4 STOP rule #6 threshold of > 5
files; below the v0.11 STOP rule #7 threshold of > 3 files too).
README.md `8ab5d54` body, all 7 perf docs, and `docs/architecture.md`
all use past-tense version-specific framing already — the live-repo
sweep found no present-tense leaks. No `# noqa: lint-tense` markers
were required at v0.12 ship time.

**New test** `tests/test_lint_tense.py::test_lint_tense_scope_includes_expanded_files`
asserts that the `_scoped_files()` discovery hits at least one file
from each of the 3 newly-added families (preemptive guard against
silent scope contraction in future refactors).

**Reverse-criterion (unchanged)**: pre-commit advisory fallback,
allow-list-based suppression, and scope re-expansion remain available
at v0.13+ per the original §Reverse-criterion block above.

**Cross-references**: D22 (block-exclusion pattern; preserved
byte-equal at v0.12), D24 NEW (CI tense lint policy; v0.11 codification
covers the v0.12 expansion as an operational refinement, NOT a new
ADR — STOP rule #14 prevents a second lint-related ADR), OQ-13h
(already `[x]` at v0.11; v0.12 reverse-criterion firing annotation
appended), `.omc/plans/v0.12-design.md` §2.4 + §10.7-§10.8 +
§14.K, `scripts/lint_tense.py::_scoped_files()` (modified to add 3
new file families).
