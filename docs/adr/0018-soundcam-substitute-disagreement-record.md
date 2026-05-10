# ADR 0018 — SoundCam substitute-disagreement record (paper-retrieved RT60 vs default-enum Sabine prediction)

- **Status**: Accepted (v0.10.0); supersedes ADR 0016 §Status-of-A11-substitute-claim
- **Date**: 2026-05-10
- **Predecessor**: ADR 0016 (Stage-2 schema flip via SoundCam substitute,
  v0.9.0); ADR 0017 (A10-layout deferred-with-classification);
  v0.9.0 critic verdict (4.4/10 — flagged honesty leak between
  `citation_pending: true` placeholders and "measured" framing in
  RELEASE_NOTES + perf doc + ADR 0016 §Consequences); paper retrieval
  agents 2026-05-10 (cross-checked).

## Decision

The substitute-vs-in-situ honesty contract codified in ADR 0016
§Reverse-criterion is **EXPLICITLY FIRED** at v0.10.0:

1. SoundCam paper-retrieved RT60 (Schroeder broadband, Table 7) for lab
   = 0.158 s and conference = 0.581 s.
2. Default 9-entry MaterialLabel enum + paper-faithful material map +
   Sabine 500 Hz prediction yields lab = 0.254 s (rel-err +60 %) and
   conference = 0.449 s (rel-err -22.7 %).
3. Both rel-errs exceed ±20 %; ADR 0016 §Reverse-criterion item (1)
   triggers (substitute disagrees with paper-honest reality on the same
   predictor / adapter path that v0.9.0 advertised as PASS).
4. Per ADR 0016 §Reverse-criterion item (2): schema marker reverts
   `"0.1"` → `"0.1-draft"` at v0.10.0.
5. Per ADR 0016 §Reverse-criterion item (3): cross-repo PR proposal
   pauses; `.omc/research/cross-repo-pr-v0.9-proposal.md` is annotated
   WITHDRAWN at v0.10.0.

The living_room fixture is **REMOVED** at v0.10.0: paper §A.2 explicitly
states "the room does not have specific walls delineating it from parts
of the rest of the house"; v0.9.0 used fabricated dimensions which
amount to a second honesty leak.

## Drivers

1. **v0.9.0 honesty leak (Critic 4.4/10)**: every SoundCam fixture file
   carried `citation_pending: true`, but RELEASE_NOTES_v0.9.0.md +
   `docs/perf_verification_a10a_soundcam_2026-05-09.md` + ADR 0016
   §Consequences advertised the values as "measured" without the
   placeholder qualifier. v0.10 must walk back the unqualified
   "PASS" framing.
2. **Paper-retrieved values disagree with placeholders by structural
   factors** (lab measured 0.158 s vs placeholder 0.35 s = 2.2× error).
   Living_room placeholder (0.45 s) is REMOVED at v0.10 with no
   paper-retrieved counterpart: paper §A.2 publishes no authoritative
   dims, and Table 7 row coverage was not independently verified for
   living_room during paper-retrieval (see §Status-update-2026-05-10b
   below). The placeholder had been chosen so the default-enum
   Sabine prediction silently passed ±20 %; the paper-retrieved value
   reveals the default-enum cannot reach treated-room (lab) absorption
   levels.
3. **ADR 0016 §Reverse-criterion was DESIGNED FOR THIS EVENT.** The
   ratchet-safe pattern (in-situ ALWAYS overrides substitute; substitute
   is "good enough until in-situ arrives") explicitly makes
   paper-retrieved data a partial in-situ override (the paper authors
   are the in-situ researchers; their reported values are the
   authoritative measurement, not v0.9 placeholders).
4. **Default 9-entry MaterialLabel enum systematically under-represents
   treated-room absorption** (max α_avg ≈ 0.46 vs paper NRC 1.26 / 1.0
   melamine + fiberglass treatment ≈ α_avg 1.10). v0.11+ candidate is
   add MELAMINE_FOAM + FIBERGLASS_CEILING; v0.10 records the
   disagreement-signature without the library-coefficient revision.

## Alternatives considered

- **(a) v0.9.1 patch — replace fixture with paper values, keep ±20 % gate.**
  Rejected. Forces either A11 mass-fail (lab +60 % outside ±20 %) or
  silent gate-weakening (new honesty leak Critic will flag). Not
  structurally reconcilable with the existing 9-entry enum.
- **(b) v0.10.0 substantive — fixture replacement + reverse-criterion
  firing + ADR 0018 + A11 disagreement-record framing + living_room
  removal + schema revert.** ACCEPTED. Honest and minimum-leverage:
  no library coefficient revision, no enum addition, no predictor
  change. Walks back exactly what v0.9.0 over-claimed.
- **(c) v0.10.0 hybrid — same as (b) plus add MELAMINE_FOAM /
  FIBERGLASS_CEILING / TILE_FLOOR enums so A11 PASS is recoverable.**
  Rejected for v0.10. Library-coefficient revision chains into
  MaterialAbsorption + MaterialAbsorptionBands + many test files;
  scope explosion. Deferred to v0.11+ (OQ-13a).
- **(d) v0.10.0 minimal — fixture replacement only; keep schema flip.**
  Rejected. ADR 0016 §Reverse-criterion explicitly says marker reverts
  if substitute disagrees on the same adapter path. Skipping the revert
  silently breaks the ratchet-safe contract.
- **(e) Widen A11 ±20 % gate to ±60 % to accommodate lab + conference.**
  Rejected. Gate-widening is the paradigmatic honesty leak v0.7 critic
  flagged; ±20 % gate is invariant per A11 acceptance from v0.1; widening
  it for substitute purposes invalidates the comparison with ACE
  corpus (which DOES pass ±20 %).
- **(f) Keep living_room fixture with Figure 2 plot-axes-derived dims
  (~4×5 m bounding box) + honesty marker.** Rejected. Plot-axes-derived
  is itself a fabrication not authored by the paper; the open-layout +
  vaulted-ceiling + kitchen+stairway exposure breaks the shoebox
  approximation regardless of which dims you pick. Removal is honest;
  retention is dishonest.

## Why chosen

- Honest enforcement of ADR 0016 §Reverse-criterion that v0.9.0 designed
  for exactly this event.
- Minimum-leverage: 0 library-coefficient changes, 0 predictor changes,
  0 adapter changes, 0 enum changes; only fixture data + ADR + schema
  marker + 1 file rename in the test suite.
- Directly addresses the v0.9.0 critic verdict (4.4/10 honesty leak).
- Preserves audit trail: ADR 0016 amended (not deleted); RELEASE_NOTES
  v0.9.0.md amended (not deleted); old perf doc preserved with
  superseded-by header (not deleted); cross-repo PR proposal annotated
  WITHDRAWN (not deleted).

## Consequences

- `__schema_version__` becomes `"0.1-draft"` again; `RoomModel.schema_version`
  default becomes `"0.1-draft"`.
- New writes via `roomestim.export.room_yaml.write_room_yaml` emit
  `version: "0.1-draft"` by virtue of the changed default.
- `proto/room_schema.json` (Stage-2 strict file) preserved for v0.11+
  re-flip; not deleted.
- Cross-repo PR proposal at
  `.omc/research/cross-repo-pr-v0.9-proposal.md` annotated WITHDRAWN.
  New `.omc/research/cross-repo-pr-v0.10-deferred.md` records the
  withdrawal + restart criteria (paper-faithful material maps + A11 PASS
  on ≥ 2 SoundCam rooms with ±20 % gate intact).
- A10a corner test count: 3 → 2 (living_room removed); both remaining
  tests reframed as "smoke-tests" (revealed-tautology disclosure).
- A11 substitute test count: 3 → 2 (living_room removed); both remaining
  tests reframed as "disagreement-record" (no PASS-gate claim).
- Default-lane test count: 118 → 116 (-2 from living_room removals; 0
  from any other change since A10a smoke + A11 disagreement-record tests
  preserve the same per-room test count for lab + conference; schema
  test invariant count preserved).
- A11 disagreement signatures recorded:
  - **lab**: predicted 0.254 s vs measured 0.158 s; rel-err +60 %;
    signature: `default_enum_underrepresents_treated_room_absorption`.
  - **conference**: predicted 0.449 s vs measured 0.581 s; rel-err -22.7 %;
    signature: `sabine_shoebox_underestimates_glass_wall_specular`.
- v0.8/v0.9 invariants byte-equal: MaterialLabel 9 entries,
  `MaterialAbsorption{,Bands}` byte-equal, `_FURNITURE_BY_ROOM` sum=276,
  `_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2['lecture_seat']`=0.45,
  MISC_SOFT α₅₀₀=0.40, `roomestim/place/wfs.py` byte-equal,
  `roomestim/cli.py` byte-equal, `roomestim/adapters/ace_challenge.py`
  byte-equal, `roomestim/adapters/polycam.py` byte-equal,
  `roomestim/reconstruct/floor_polygon.py` byte-equal. ADRs 0001..0017
  byte-equal except ADR 0016 (§Status-update-2026-05-10 amendment
  appended).
- ACE corpus A11 (gated E2E) byte-equal — substitute disagreement does
  NOT invalidate ACE evidence; it bounds the SUBSTITUTE's reach.

## Reverse-criterion (CRITICAL — ratchet-safe)

If v0.11+ adds MELAMINE_FOAM + FIBERGLASS_CEILING + TILE_FLOOR enums
with paper-faithful coefficient sourcing AND the resulting A11
prediction returns to ±20 % on lab + conference (recovered substitute
PASS), the schema marker MAY re-flip `"0.1-draft"` → `"0.1"` per ADR
0019+ (TBD). Until then, marker stays `"0.1-draft"` and cross-repo PR
stays withdrawn.

If a future paper retrieval (or re-read of arXiv:2311.03517v2) surfaces
authoritative living_room dimensions (which we currently believe do not
exist per §A.2), the living_room fixture MAY be re-introduced under a
successor ADR.

## References

- arXiv:2311.03517v2 (NeurIPS 2024 D&B, SoundCam) — Appendix A.1, A.2,
  A.3 + Table I + Table 7 + Figure 10. Cross-checked by 2 independent
  retrieval agents on 2026-05-10.
- ADR 0016 (Stage-2 schema flip via SoundCam substitute) —
  §Reverse-criterion item (1)/(2)/(3) all firing at v0.10.
- ADR 0017 (A10-layout deferred-with-classification) — unchanged.
- v0.9.0 critic verdict (4.4/10) — flagged honesty leak that v0.10
  walks back.
- D2 (`.omc/plans/decisions.md`) — ≥3 captures requirement for
  Stage-2 lock; v0.10 substitute coverage drops to 2 rooms (lab,
  conference), tightening the D2 reverse condition for Stage-2 re-flip.
- D8 (original A10 lab-capture predicate) — unchanged.
- D11 (cross-repo PR remains proposal-stage; v0.10 elevates to WITHDRAWN).
- D14..D20 (v0.5..v0.9 decisions) — byte-equal under v0.10.
- D21 (NEW v0.10) — appended to `decisions.md` with v0.10 honesty
  correction summary.
- OQ-12a/b/c (v0.9-design open questions) — status reaffirmed; OQ-12a
  (A10b in-situ) elevated importance under §Reverse-criterion firing.
- OQ-13a/b/c/d/e (NEW v0.10) — open questions covering enum candidates
  for treated rooms, Sabine-residual study, cross-repo PR re-submission
  criteria, v0.10 critic verdict, live-mesh extraction.
- v0.10 design — `.omc/plans/v0.10-design.md`.
- v0.10 release notes — `RELEASE_NOTES_v0.10.0.md`.
- v0.10 perf doc — `docs/perf_verification_a10_soundcam_2026-05-10.md`.
- Cross-repo PR withdrawal — `.omc/research/cross-repo-pr-v0.10-deferred.md`.

---

## §Status-update-2026-05-10b (added at v0.10.1 — fabricated-quote redaction)

**Issue**: v0.10 critic verdict (7.6/10, 2026-05-10) flagged §Drivers
item 2 line 46 quoting `living_room measured 1.121 s` without
citation. v0.10 elsewhere asserts paper §A.2 publishes no authoritative
living_room data, so the quoted measurement is either uncited Table 7
row content (in which case ADR should cite Table 7 position) or
drafting residue (in which case it should be redacted).

**Action**: v0.10.1 redacts the `1.121 s` quote and the
`vaulted-ceiling open-layout (living_room) targets` extrapolation
from §Drivers item 2 (line 46). The line preserves the lab quote
(`0.158 s vs placeholder 0.35 s`) which has independent Table 7
citation in §Decision item 1 + §References. The redaction is in-line
to keep the ADR readable; this §Status-update records the WHY for
audit-trail discipline.

**Cross-references**: v0.10 critic verdict (§Honesty-leak audit MED);
v0.11 architect verdict §Categorisation table (categorised as
v0.10.1 patch); .omc/plans/v0.10.1-patch.md (this plan).
