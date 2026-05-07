# roomestim — Open Questions

> **Status update 2026-05-03**: All 7 questions for v0.1 are RESOLVED in `.omc/plans/decisions.md` (D1–D7). This file is kept as a historical record. Each item below shows the resolution pointer and reversal criterion.

## roomestim-v0-design - 2026-05-03

- [x] **(D1)** Will roomestim be attached as a git submodule under `spatial_engine/third_party/`, or distributed via PyPI? — **Decision: standalone git repo for v0.1; submodule/PyPI choice deferred to v0.2 ADR.** Reverse if engine team requests immediate vendoring or maintenance cost > 1 day/month.
- [x] **(D2)** Does the engine team accept the proposed `room.yaml` shape (2.5D polygon + scalar ceiling)? — **Decision: not a v0.1 blocker; ship `version: "0.1-draft"` (Stage 1 permissive) and propose to engine in roomestim v0.2 after lab fixture exercise.** Reverse if ≥3/10 real-world files need schema patches after Stage 2 lock.
- [x] **(D3)** Is the closed `material` enum (8 entries) sufficient, or do we need a free-form fallback with a `custom_label` field? — **Decision: closed 8-entry enum with `unknown` as fallback; no `custom_label` in v0.1.** Reverse if ≥30% of surfaces across first 10 captures land in `unknown`.
- [x] **(D4)** Are the lab speakers in `lab_setup.md` already mounted, or are we placing them as part of the v0.1 acceptance test? — **Decision: assume NOT pre-mounted; A10 = scan → place → mount → tape-measure.** Reverse to regression-only mode if user confirms speakers were already mounted.
- [x] **(D5)** Should `aim_direction` be exported in `layout.yaml` (extension field) or only kept in roomestim's `PlacementResult`? — **Decision: export as `x_aim_az_deg` / `x_aim_el_deg` per-speaker extension keys (engine-ignored).** Reverse if engine team promotes `aim` to a first-class field.
- [x] **(D6)** Capture device availability for v0.1 acceptance gate: does the team have an iPhone Pro / iPad Pro for RoomPlan capture, or do we need to ship Polycam as the v0.1 first-class adapter instead? — **Decision: RoomPlan first-class, Polycam supported secondary; both adapters in v0.1; A10 flexes to whichever device captures on the day.** Reverse if P5 ships before P4 (Polycam becomes de facto first-class).
- [x] **(D7)** Should `room.yaml` include octave-band absorption coefficients for v0.1, or is single mid-band 500 Hz sufficient given ±20% RT60 acceptance tolerance? — **Decision: single mid-band 500 Hz only; octave-band defers to v0.3.** Reverse if engine reverb integration requires octave-band data.

All v0.1 implementation decisions are now locked. New questions raised during P0–P7 should be appended to a new section dated when raised.

---

## v0.5-design — 2026-05-06

> **Status update 2026-05-07**: All 5 questions RESOLVED via locked scope (partial-A + B). Resolutions recorded inline below; full rationale in `.omc/plans/v0.5-design.md` §0a. New decision (D15) will be appended to `decisions.md` at v0.5.0 commit.

- [x] **(OQ-1)** Eaton 2016 TASLP Table I — does the parallel `cwm:websearchwithme` research at `.omc/research/ace-table-i-acquisition.md` surface a viable acquisition path? — **Resolution: PARTIAL — dimensions (L×W×H) acquired from arXiv:1606.03365 Table 1 (TASLP supporting material, open access); materials remain TASLP-locked (paywalled). Scope locked to partial-A (dims-only) + B.** Reverse if TASLP material assignments later become available and disagree with current `ACE_ROOM_GEOMETRY` material strings.
- [x] **(OQ-2)** F4b enum coefficients — is `MaterialAbsorption[MISC_SOFT] = 0.40` and the `(0.20, 0.30, 0.40, 0.50, 0.60, 0.65)` band profile acceptable as representative-not-verbatim under the v0.3 honesty-marker policy? — **Resolution: APPROVED — representative-not-verbatim with honesty marker matches v0.3 `MaterialAbsorptionBands` precedent; `MISC_SOFT` row required to preserve `band-2 == legacy scalar` invariant.** Reverse if ≥1 adapter starts emitting `MISC_SOFT` and downstream consumer reports magnitude wrong.
- [x] **(OQ-3)** D14 reverse-trigger semantics — under Scenario A 5b, do we co-ship coefficient revision (a) or split (b)? — **Resolution: N/A under partial-A — D14 5b cannot evaluate "assignments correct" without F1 materials, so trigger does not fire. F4a stays DEFERRED.** Reverse if F1 materials acquired in v0.6+ window and 5b conditions then evaluate true.
- [x] **(OQ-4)** Stage-2 schema flip (D8) — keep Stage-1 at v0.5? — **Resolution: KEEP STAGE-1 — D8 binds Stage-2 to A10 lab-capture which has not happened; non-negotiable, not just a default.** Reverse if A10 ships in v0.5 (it is not in scope).
- [x] **(OQ-5)** ADR 0010+ numbering — confirm ordering. — **Resolution: ADR 0010 = ACE-geometry-verified (dims-only); ADR 0011 = MISC_SOFT-enum. Inverted from initial draft to put F1-partial headline first.** Reverse only if ADRs reordered before commit.
