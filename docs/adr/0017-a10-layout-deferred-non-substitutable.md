# ADR 0017 — A10-layout deferred (non-substitutable)

- **Status**: Accepted (v0.9.0) — **Deferred-with-classification**
- **Date**: 2026-05-09
- **Predecessor**: v0.8.0 (`5cd5be3`); ADR 0016 (partner ADR — Stage-2
  schema flip via SoundCam substitute);
  v0.8 strategic-position report `§3` acceptance scorecard A10
  decomposition; D8 (original A10 lab-capture predicate).

## Decision

A10-layout (VBAP-N speakers ±5° azimuth + ±10 cm radial vs PHYSICAL
speakers in a real captured room) is **explicitly classified as not
substitutable by any public dataset known to v0.9**. v0.9 ships A10a
(corner geometry substitute) and A11-boost (RT60 substitute);
A10-layout remains DEFERRED to user in-situ work and is NOT advertised
as part of A10a closure.

> **Honesty marker (required)**: GT corners + RT60 derived from
> SoundCam paper-published dimensions; live-mesh corner extraction is
> v0.10+ upgrade path. A10-layout is a separate concern entirely —
> physical-speaker placement vs algorithm prediction — and no public
> dataset provides that ground truth.

## Drivers

1. **No public VBAP layout GT.** No public dataset known to v0.9
   ships VBAP-N layout GT against scan corners. SoundCam ships
   measurement-mic positions, not VBAP speaker positions. ARKitScenes
   ships scene meshes, not speaker GT. Motus ships HOA RIR + OBJ CAD,
   not VBAP layout GT. dEchorate ships room IRs at fixed mic
   positions, not VBAP speakers.
2. **Mic positions are not analogous to speaker placements.** The
   A10-layout gate is "did roomestim's `place_vbap(...)` recommend
   coordinates that the user can physically install with ±5° / ±10 cm
   tolerance?". Reverse-engineering this from public-dataset
   measurement-mic positions would compare two different things.
3. **Procedurally-generated GT does not substitute for physical
   placement.** A5 / A6 / A16 already exercise the placement
   algorithm against synthetic / procedural rooms. A10-layout is
   uniquely about physical-world placement vs algorithm prediction;
   it requires a real captured room AND physically installed
   speakers measured by tape (D4-style).
4. **Honest classification > silent goal-shifting.** Pretending the
   A10a substitute closes A10-layout would dishonestly claim
   acceptance for a verification path that was not exercised. ADR
   0017 formalises the strategic-position report's A10 three-way
   decomposition (geometry / RT60 / layout) so the scorecard reflects
   what was actually established at v0.9.

## Alternatives considered

- **(a) Synthesise speaker positions on SoundCam rooms (place 8
  virtual VBAP speakers + check the *coordinates* against geometric
  correctness).** Rejected. This is unit-test-level placement-
  algorithm verification (already covered by A5 / A6 / A7), NOT
  A10-layout. A10-layout requires real-world physical placement vs
  the algorithm's prediction.
- **(b) Reverse-engineer speaker placement from SoundCam mic
  positions.** Rejected. SoundCam mic positions are measurement-rig
  positions, not speaker-installation positions; comparing them to
  VBAP-recommended coordinates is meaningless. This would be
  "fake-substitutability".
- **(c) Defer A10-layout silently and retroactively redefine A10 as
  geometry-only.** Rejected. The v0.8 strategic-position report
  scorecard would flag this as goal-post-moving; the appropriate
  posture is the explicit three-way decomposition recorded by ADR
  0017.
- **(d) Close A10-layout by cite-only (claim "covered by future
  work").** Rejected. Cite-only closure for an unmet acceptance gate
  is dishonest under the project's honesty-marker policy (D12 / D16
  / ADR 0011 / ADR 0012 precedent).

## Why chosen

- Honest classification > silent goal-shifting. v0.9 ships the A10
  three-way decomposition explicitly: A10a substitute PASS, A10b
  in-situ DEFERRED-no-closure, A10-layout DEFERRED-with-classification
  (this ADR).
- Future v0.10+ A10b in-situ work continues to carry both A10a
  (geometry) and A10-layout responsibility under the same
  user-volunteer activation barrier — no scope drift introduced.
- ADR 0017 is the citable decision-handle for the strategic-position
  scorecard's A10 row; future audit cycles can refer to it without
  re-litigating non-substitutability.

## Consequences

- The strategic-position scorecard (§3 row A10) henceforth reads
  **A10a PASS (substitute, ADR 0016), A10b DEFERRED (no closure;
  user-volunteer-only), A10-layout DEFERRED-with-classification (ADR
  0017)**.
- v0.9 release notes (`RELEASE_NOTES_v0.9.0.md`) explicitly carry
  the three-way decomposition.
- Future v0.10+ A10b in-situ session — when one materialises — must
  exercise both geometry + layout sub-gates simultaneously (the gate
  is unified at the in-situ level even though substitute work split
  it).
- No code change. No predictor change. No schema change. No new
  MaterialLabel enum entry.
- v0.8 invariants byte-equal (same as ADR 0016
  §Consequences final bullet).

## Reverse-trigger

- If a public dataset eventually ships VBAP-N speaker GT against
  scan corners (unlikely but possible — e.g., a follow-up paper to
  SoundCam adds physical speaker positions, OR an immersive-audio
  community dataset emerges with installed-speaker coordinates), ADR
  0017 is reverted and an A10a-layout substitute is added in v0.10+.
- If the project's audio-rendering scope contracts to a layout-
  agnostic mode (e.g., HRTF-only synthesis) where A10-layout becomes
  vestigial, ADR 0017 is superseded by a posture-update ADR.

## References

- v0.8 strategic-position report —
  `.omc/plans/v0.8-strategic-position-2026-05-09.md`.
- ADR 0016 (partner ADR; Stage-2 schema flip via SoundCam
  substitute).
- v0 design Q9 / A10 — original A10 acceptance specification.
- D4 — A10 place-then-mount interpretation; A10-layout gate inherits
  this framing.
- D8 — original A10 lab-capture predicate; A10-layout is the
  layout-half of the gate.
- v0.9 design `.omc/plans/v0.9-design.md` §2.6 (this ADR's plan
  parent).
