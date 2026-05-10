# roomestim v0.10.1 — Release Notes

**Date**: 2026-05-10b (drafted) / 2026-05-10b (shipped)
**Predecessor**: v0.10.0 (`90aa6f1`) — honesty correction; ADR 0016 reverse-criterion fired; ADR 0018; living_room removed; D21.
**Patch nature**: factual-integrity-only. NO library code changes; NO test logic changes; NO test count change (stays 116); NO library-default-state mutation (`__schema_version__` stays `"0.1-draft"`).

## What we got wrong in v0.10.0

1. **ADR 0018 §Drivers item 2 line 46 contained a fabricated quote**: `living_room measured 1.121 s vs placeholder 0.45 s = 2.5× error`. The `1.121 s` measurement is uncited and contradicts v0.10's own §A.2 claim that paper publishes no authoritative living_room data. v0.10 critic flagged this as a MED honesty-leak (composite verdict 7.6/10).
2. **`tests/fixtures/soundcam_synthesized/README.md` body lines 27/31/41-43 still described v0.9 placeholder regime in present tense** beneath the v0.10 §Honesty-correction prepend block. Tense mismatch reads as if v0.9 placeholder shipping is current behaviour.
3. **`.omc/plans/v0.10-design.md` line 702 contained the same fabricated `1.121 s` quote** as ADR 0018 line 46 (drafting residue from the same source).

## What v0.10.1 fixes

1. **ADR 0018 line 46 in-line redaction**: `1.121 s` quote and `vaulted-ceiling open-layout (living_room) targets` extrapolation REMOVED. Lab quote (`0.158 s vs placeholder 0.35 s`) preserved (independent Table 7 citation in §Decision item 1 + §References).
2. **ADR 0018 §Status-update-2026-05-10b appended**: records the WHY of the redaction for audit-trail discipline (mirrors v0.10's RELEASE_NOTES_v0.9.0 prepend pattern).
3. **`tests/fixtures/soundcam_synthesized/README.md` tense + framing fix** on body lines 27/31/41-43. NO content removal; only past-tense rewrites + `[v0.9-historical, superseded by §Honesty-correction-2026-05-10]` marker prepend.
4. **`.omc/plans/v0.10-design.md` line 702 same redaction** as ADR 0018 line 46. Implementation-note block at top of plan gains 1-line addendum bullet referencing v0.10.1.
5. **D22 codifies the hybrid audit-trail-discipline pattern** for same-week-old ADR corrections (factual errors → in-line redaction + §Status-update; structural errors → ADR supersedure). Mirrors OQ-13g resolution candidate.
6. **OQ-13f/g/h/i recorded as NEW open questions** in `.omc/plans/open-questions.md`:
   - OQ-13f: disagreement-band asymmetry (DEFERRED to v0.11).
   - OQ-13g: audit-trail discipline for same-week-old ADRs (codified in D22).
   - OQ-13h: README-body-still-in-old-tense audit (DEFERRED to v0.11 CI lint).
   - OQ-13i: mypy strict project commitment (DEFERRED to v0.12+).
7. **OQ-13a amended** to specify Vorländer 2020 §11 / Appx A as PRIMARY for MELAMINE_FOAM α₅₀₀ (matching ADR 0011 / OQ-2 / OQ-6 precedent).
8. **OQ-12a status-update marker** records v0.11 will ship in-situ protocol DOC only (no capture commitment).
9. **OQ-13d marked `[x]` resolved** (Critic verdict received 2026-05-10).
10. **Version bump** `0.10.0` → `0.10.1` in `pyproject.toml` + `roomestim/__init__.py` (`__version__` only; `__schema_version__` stays `"0.1-draft"`).

## What stays the same

- Library code (`roomestim/**/*.py` except `__init__.py:__version__`) byte-equal to v0.10.0.
- All test files (`tests/**/*.py`) byte-equal to v0.10.0.
- All fixture data files (`tests/fixtures/soundcam_synthesized/{lab,conference}/{dims.yaml,rt60.csv,GT_corners.json}` + `LICENSE_MIT.txt`) byte-equal.
- ADRs 0001..0017 byte-equal.
- ADR 0018 §Decision + §Alternatives + §Why-chosen + §Consequences + §Reverse-criterion + §References byte-equal (only §Drivers item 2 line 46 + new appended §Status-update changed).
- `RELEASE_NOTES_v0.9.0.md`, `RELEASE_NOTES_v0.10.0.md`, all perf docs, all cross-repo PR research notes byte-equal.
- `__schema_version__` stays `"0.1-draft"` (Stage-2 schema state preserved from v0.10).
- Cross-repo PR proposal at `.omc/research/cross-repo-pr-v0.10-deferred.md` byte-equal (status remains WITHDRAWN per v0.10 ADR 0016 §Reverse-criterion).
- `MaterialLabel` 9 entries; `MaterialAbsorption{,Bands}` rows; `_FURNITURE_BY_ROOM` sum=276; `_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2['lecture_seat']`=0.45.
- A10a corner test count: 2 (lab + conference smoke); A11 substitute test count: 2 (lab + conference disagreement-record); schema test invariant: 1.

## Default-lane test count

**116 tests collected; 116 passed.** UNCHANGED from v0.10.0.

## What stays deferred

- v0.11 hybrid scope: MELAMINE_FOAM enum (OQ-13a); disagreement-band tightening (OQ-13f); README-tense CI lint (OQ-13h); in-situ protocol DOC (OQ-12a).
- v0.12+ scope: mypy strict project commitment (OQ-13i).
- A10b in-situ user-lab capture: user-volunteer-only (OQ-12a unchanged on capture commitment).
- Live-mesh extraction (OQ-13e): unchanged.
- Cross-repo PR re-submission (OQ-13c + `.omc/research/cross-repo-pr-v0.10-deferred.md`): unchanged.

## Tag policy

Local tag `v0.10.1` per D11 (tag-local-only). NOT pushed to remote.

## References

- v0.10.1 design plan: `.omc/plans/v0.10.1-patch.md`
- v0.10.0 commit: `90aa6f1`
- v0.10 critic verdict (2026-05-10; 7.6/10 composite)
- v0.10 architect verdict (2026-05-10; §Categorisation table)
- ADR 0018 §Status-update-2026-05-10b (NEW, v0.10.1)
- D22 (NEW, v0.10.1) — `.omc/plans/decisions.md`
- OQ-13f/g/h/i (NEW, v0.10.1) — `.omc/plans/open-questions.md`
