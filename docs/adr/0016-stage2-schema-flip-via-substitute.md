# ADR 0016 — Stage-2 schema flip via SoundCam public-dataset substitute

- **Status**: Accepted (v0.9.0)
- **Date**: 2026-05-09
- **Predecessor**: v0.8.0 (`5cd5be3` — Lecture_2 ceiling/seat bracketing
  null verdict + per-band MAE snapshot; ADR 0015; D19; OQ-11);
  ADRs 0001..0015; D1..D19; OQ-4 (Stage-2 schema flip predicate from
  v0.5-design); v0.8 strategic-position report
  `.omc/plans/v0.8-strategic-position-2026-05-09.md`.

## Decision

`__schema_version__` flips `"0.1-draft"` → `"0.1"` at v0.9.0;
`RoomModel.schema_version` default flips `"0.1-draft"` → `"0.1"`;
`proto/room_schema.json` (already authored as Stage 2 strict at v0.1.1
P3 — `additionalProperties: false`, `version: const "0.1"`) becomes the
canonical schema. The flip is **substitute-driven** (SoundCam 3 rooms ×
A10a synthesised corners ≤ 10 cm + A11 ±20 % Sabine RT60 boost) and
**NOT in-situ-driven** (A10b user lab unchanged; ADR 0017 partner ADR
records A10-layout non-substitutability).

> **Honesty marker (required)**: GT corners + RT60 derived from
> SoundCam paper-published dimensions; live-mesh corner extraction is
> v0.10+ upgrade path.

## Drivers

1. **8-release Stage-2 inertia.** v0.1.1 P3 already authored
   `proto/room_schema.json` as Stage 2 strict
   (`additionalProperties: false`, `version: const "0.1"`); the only
   missing piece for 8 releases (v0.1..v0.8) has been the
   `__schema_version__` marker flip + `RoomModel.schema_version`
   default flip. v0.5-design OQ-4 explicitly bound the marker to A10
   lab capture (D8); the v0.8 strategic-position report identified
   "wait for capture" as the 0%-progress deadlock blocking
   spatial_engine integration + the v0.2.0 cross-repo PR that has been
   draft-frozen for 7 releases.
2. **Substitute is bounded validation, not zero validation.** SoundCam
   (Stanford 2024, MIT license) ships 3 rooms with Azure Kinect
   textured meshes + measured Schroeder RT60 traces + paper-published
   dimensions. v0.9 ships the *paper-derived* substitute: synthesised
   rectangular shoeboxes from the published dimensions (no mesh
   redistribution; no live extraction). This is an audit-honest
   intermediate: "good enough until in-situ arrives", not "the new
   ground truth".
3. **Cross-repo PR unblock.** Stage-2 flip is the prerequisite for the
   v0.2.0 cross-repo PR to spatial_engine
   (`spatial_engine/proto/room_schema.json` proposal). v0.9 ships the
   proposal-stage text at
   `.omc/research/cross-repo-pr-v0.9-proposal.md`; merge remains
   spatial_engine team responsibility, not v0.9.
4. **Honesty preservation via reverse criterion.** The marker flip is
   reversible — if A10b in-situ lab capture eventually disagrees with
   the substitute findings (corner > 10 cm OR RT60 > 20 % on the same
   predictor / adapter path), the schema may revert to `"0.1-draft"`,
   the cross-repo PR pauses, and a successor ADR (0018+) records the
   disagreement. **In-situ ALWAYS overrides substitute.**

## Alternatives considered

- **(a) Wait for A10b indefinitely.** Rejected. 8-release deadlock
  pattern explicitly identified as drift in the v0.8 strategic
  report; the project pivots from "wait for capture" to "use clean
  public substitute" as the v0.9 minimum-leverage move. Without a
  user-volunteer calendar slot, A10b is structurally unfundable from
  the executor side.
- **(b) Use ARKitScenes substitute instead.** Rejected. Apple
  non-commercial license risks spatial_engine future commercial
  integration path; ~hundreds-of-GB scope is out of v0.9 scope; the
  minimum-leverage move is 3 SoundCam rooms first. ARKitScenes
  remains a v0.10+ DEFERRED-not-rejected candidate (OQ-12c).
- **(c) Live SoundCam mesh download + extraction.** Rejected for
  v0.9. Several-GB download + alpha-shape / RANSAC corner extraction
  on noisy upstream meshes is out of v0.9 scope; the executor
  deliberately stops at "synthesise from published dimensions" so
  default-lane CI does not depend on a multi-GB external download.
  v0.10+ upgrade path explicitly named in §References.
- **(d) Motus single-room substitute.** Rejected. Motus ships 1 room
  only with HOA RIR + OBJ CAD; phone-scan path completely
  uninvolved; adapter not exercised; D2 reverse rule asks for ≥3
  captures.
- **(e) Flip Stage-2 with NO substitute (declare schema "good enough
  on author judgement").** Rejected. Would break OQ-4 / D8 / D2
  conditions that Stage-2 lock requires real-world fixture exercise
  (≥3 captures per D2 reverse rule). SoundCam provides exactly that
  (≥3 rooms) under MIT license.

## Why chosen

- Minimum-leverage answer to the v0.8 strategic-position report:
  "진짜 다음 스텝 — 코드를 한 줄도 쓰지 않고 lab capture를 잡거나, 공개
  데이터로 substitute한다". User chose substitute path; v0.9 ships
  exactly that.
- Preserves the 8-release schema-file infrastructure investment
  (`proto/room_schema.json` Stage 2 strict authored at v0.1.1 P3 is
  byte-equal under v0.9; only the marker flips).
- Unblocks cross-repo PR finalisation-prep (proposal-stage at
  `.omc/research/`).
- Substitute-vs-in-situ honesty preserved via the §Reverse-criterion
  below — **ratchet-safe**: in-situ evidence ALWAYS overrides
  substitute.

## Consequences

- `__schema_version__` becomes `"0.1"`;
  `RoomModel.schema_version` default becomes `"0.1"`.
- New writes via `roomestim.export.room_yaml.write_room_yaml` emit
  `version: "0.1"` by virtue of the changed default; the call-site
  remains a no-API-change.
- Old reads (`version: "0.1-draft"`) continue to validate against
  `proto/room_schema.draft.json` (backward-compat retained via the
  existing `_load_schema` switch at
  `roomestim/io/room_yaml_reader.py:32`). A regression test asserts
  this in `tests/test_schema_stage2_validates.py`.
- `additionalProperties: false` is now in force on Stage-2 reads;
  consumers writing extensions must use Stage-2 explicit slots
  (`mount_surfaces`, `wfs_baseline_edge`, optional `absorption`
  block) or future namespaced extensions added in a v0.9+ schema
  patch.
- A10a substitute corner errors per room (cached-mode default lane)
  are 0.00 cm / 0.00 cm / 0.00 cm (lab / living_room / conference);
  the synthesised shoebox is exact by construction.
- A11 RT60 substitute errors per room at 500 Hz Sabine: lab 0.28 %
  (predicted 0.351 s vs measured 0.350 s); living_room 5.57 %
  (predicted 0.425 s vs measured 0.450 s); conference 15.92 %
  (predicted 0.462 s vs measured 0.550 s). All three within ±20 %
  per the A11 boost gate; defensible material maps recorded inline
  in each `tests/fixtures/soundcam_synthesized/<room>/dims.yaml`
  rationale block.
- Cross-repo PR draft (v0.2.0) becomes finalisation-ready; v0.9 emits
  the proposal text at `.omc/research/cross-repo-pr-v0.9-proposal.md`
  but does NOT execute the PR submission (spatial_engine team review
  responsibility).
- v0.8 invariants byte-equal: MaterialLabel 9 entries,
  `MaterialAbsorption{,Bands}` byte-equal, `_FURNITURE_BY_ROOM` sum
  = 276, `_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2['lecture_seat']` =
  0.45, MISC_SOFT α₅₀₀ = 0.40, `roomestim/place/wfs.py` byte-equal,
  `roomestim/cli.py` byte-equal, `roomestim/adapters/ace_challenge.py`
  byte-equal, `roomestim/adapters/polycam.py` byte-equal,
  `roomestim/reconstruct/floor_polygon.py` byte-equal. ADRs 0001..0015
  byte-equal.

## Reverse-criterion (CRITICAL — ratchet-safe)

If A10b (user lab capture) ever ships and ITS corner reconstruction
err > 10 cm OR ITS measured RT60 deviates from predicted by > 20 % on
the same predictor / adapter path that the A10a / A11 substitutes
passed, the Stage-2 flip is RE-EVALUATED:

1. ADR 0018+ records the disagreement (substitute-vs-in-situ
   discrepancy log).
2. Schema may be reverted to `"0.1-draft"` while the disagreement is
   investigated (the reader `_load_schema` switch at
   `roomestim/io/room_yaml_reader.py:32` already supports both
   variants, so the revert is non-breaking for consumers).
3. The cross-repo PR (`.omc/research/cross-repo-pr-v0.9-proposal.md`)
   is paused if not yet merged, OR a follow-up PR adjusts the schema
   if already merged.

This is **ratchet-safe**: in-situ evidence ALWAYS overrides
substitute evidence. Substitute is "good enough until in-situ
arrives", not "the new ground truth".

> **Honesty marker (repeated for completeness)**: GT corners + RT60
> derived from SoundCam paper-published dimensions; live-mesh corner
> extraction is v0.10+ upgrade path.

## References

- SoundCam (Stanford, 2024). NeurIPS 2024 D&B track.
  arXiv:2311.03517; Stanford Digital Repository
  purl.stanford.edu/xq364hd5023; license MIT (verbatim copy at
  `tests/fixtures/soundcam_synthesized/LICENSE_MIT.txt`).
- ADR 0001..0015 (predecessor architecture decisions).
- ADR 0017 (partner ADR; A10-layout non-substitutable
  classification).
- D2 (`.omc/plans/decisions.md`) — ≥3 captures requirement for
  Stage-2 lock.
- D8 (`.omc/plans/decisions.md`) — original A10 lab-capture predicate;
  v0.9 substitute path inherits D8 reverse-trigger via
  §Reverse-criterion above.
- D11 — distribution model; cross-repo PR remains proposal-stage.
- D19 — v0.8 ratification framing; v0.9 does NOT ratify any
  Lecture_2 bracketing variant (OQ-11 unchanged).
- OQ-4 — Stage-2 schema flip predicate from v0.5-design.
- OQ-12a/b/c — v0.9-design open questions (A10b timeline / AnyRIR
  watchlist trigger / ARKitScenes v0.10+ scoping).
- v0.8 strategic-position report —
  `.omc/plans/v0.8-strategic-position-2026-05-09.md`.
- v0.9 design — `.omc/plans/v0.9-design.md`.
- Cross-repo PR proposal text —
  `.omc/research/cross-repo-pr-v0.9-proposal.md`.
- Tests — `tests/test_a10a_soundcam_corner.py`,
  `tests/test_a11_soundcam_rt60.py`,
  `tests/test_schema_stage2_validates.py`.
