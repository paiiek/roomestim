# RELEASE NOTES — roomestim v0.10.0 (Honesty Correction)

v0.10.0 is a **honesty-correction release**. It walks back the substitute
claims advertised in v0.9.0 RELEASE_NOTES + perf doc + ADR 0016
§Consequences, after the v0.9.0 critic verdict (4.4/10) flagged a
structural honesty leak between `citation_pending: true` placeholder
fixture values and "measured" framing in user-visible release artefacts.

The v0.10 SemVer minor bump is justified on three grounds:
(1) the substitute claims that defined v0.9 are walked back; (2) the
Stage-2 schema marker REVERTS `"0.1"` → `"0.1-draft"` per ADR 0016
§Reverse-criterion firing; (3) the v0.9.0 cross-repo PR proposal that
v0.9 advertised as "proposal-stage finalised" is annotated WITHDRAWN.
All library defaults, coefficients, predictors, and v0.8/v0.9 byte-equal
invariants on `MaterialLabel`/`MaterialAbsorption{,Bands}`/
`_FURNITURE_BY_ROOM` are preserved.

## What we got wrong in v0.9.0

1. **Fixture values were placeholders, not measurements.** Every SoundCam
   fixture file carried `citation_pending: true`. v0.9 placeholder values
   were chosen so the default-enum Sabine prediction silently passed
   ±20 % (lab 0.35 s; living_room 0.45 s; conference 0.55 s). Paper-
   retrieved values (Table 7 Schroeder broadband mean) are lab 0.158 s
   and conference 0.581 s; living_room dims are not in the paper.
2. **Living-room fixture used fabricated dims.** Paper §A.2 explicitly
   states "the room does not have specific walls delineating it from
   parts of the rest of the house". v0.9 used a synthesised 6.0 × 4.5 ×
   2.5 m shoebox with no paper authority.
3. **The "PASS" framing was structurally tautological.** v0.9 advertised
   "A10a PASS — corner err 0.00 cm by construction" without disclosing
   that GT corners + predicted corners were both synthesised from the
   same paper-published dimensions; the comparison was 0 cm by
   construction with no extraction-algorithm validation.
4. **ADR 0016 §Reverse-criterion was not fired when it should have been.**
   ADR 0016 explicitly designed a reverse path for substitute-vs-in-situ
   disagreement; paper-retrieved values are a partial in-situ override
   (the paper authors are the in-situ researchers); v0.9 did not check.

## What v0.10 fixes

- Lab + conference fixtures replaced with paper-retrieved dims + RT60
  (`citation_pending: false`; Table I + Table 7 cited).
- Living-room fixture REMOVED (3 rooms → 2; ADR 0018 records the rationale).
- A10a corner tests reframed as smoke-tests (revealed-tautology disclosure).
- A11 substitute reframed as disagreement-record (no PASS claim).
- Stage-2 schema marker REVERTED `"0.1"` → `"0.1-draft"` per ADR 0016
  §Reverse-criterion item (2).
- Cross-repo PR proposal WITHDRAWN per ADR 0016 §Reverse-criterion item (3).
- ADR 0018 NEW (substitute-disagreement record + remediation plan).
- ADR 0016 amended in place (§Status-update-2026-05-10 appended).
- RELEASE_NOTES_v0.9.0.md prepended with v0.10 honesty-correction notice;
  v0.9 body preserved verbatim for audit trail.
- `docs/perf_verification_a10a_soundcam_2026-05-09.md` superseded by new
  `docs/perf_verification_a10_soundcam_2026-05-10.md`; old file gets
  one-line superseded-by header but body byte-equal otherwise.

## Disagreement-record table (per ADR 0018)

| Room | Predicted (s) | Measured (s) | Rel-err | Signature |
| --- | ---: | ---: | ---: | --- |
| lab | 0.254 | 0.158 | +60 % | default_enum_underrepresents_treated_room_absorption |
| conference | 0.449 | 0.581 | -22.7 % | sabine_shoebox_underestimates_glass_wall_specular |

(living_room: REMOVED; no authoritative paper dims.)

## What stays the same

- All v0.8/v0.9 invariants byte-equal: `MaterialLabel` 9 entries,
  `MaterialAbsorption{,Bands}` byte-equal, `_FURNITURE_BY_ROOM` sum=276,
  `lecture_seat` α₅₀₀=0.45, MISC_SOFT α₅₀₀=0.40.
- `roomestim/place/wfs.py`, `roomestim/cli.py`,
  `roomestim/adapters/ace_challenge.py`, `roomestim/adapters/polycam.py`,
  `roomestim/reconstruct/floor_polygon.py` byte-equal to v0.9.
- ADRs 0001..0015 + 0017 byte-equal.
- ADR 0016 amended in place (§Status-update-2026-05-10 appended).
- ACE corpus A11 (gated E2E) byte-equal — substitute disagreement does
  NOT invalidate ACE evidence; it bounds the SUBSTITUTE's reach.
- `proto/room_schema.json` (Stage-2 strict file) preserved for v0.11+ re-flip.
- v0.9 audit trail preserved in full.

## What stays deferred

- **A10b in-situ user-lab capture** — unchanged; user-volunteer-only.
  ADR 0016 + ADR 0018 reverse-criteria keep this gate alive.
- **A10-layout VBAP-N vs physical** — non-substitutable per ADR 0017.
- **`MELAMINE_FOAM` / `FIBERGLASS_CEILING` / `TILE_FLOOR` MaterialLabel
  enum entries** — v0.11+ candidate (OQ-13a); library-coefficient revision
  out of v0.10 minimum-leverage scope.
- **Stage-2 schema RE-flip** — only after v0.11+ adds the new enums AND
  A11 substitute returns to ±20 % on ≥ 2 rooms with paper-faithful
  material maps.
- **Cross-repo PR re-submission** — only after Stage-2 RE-flip.
- **F4a 2k/4k sensitivity sweep** — ADR 0015 reverse-trigger; v0.11+ candidate.
- **Coupled-space predictor** — ADR 0014 alt-considered (b).
- **ARKitScenes / AnyRIR integration** — OQ-12b/c unchanged.

## Default-lane test count

v0.9: 118 → v0.10: 116 (-2 from living_room test removal; lab + conference
test bodies restructured but per-room test counts preserved).

| Test file | v0.9 count | v0.10 count | Delta |
| --- | ---: | ---: | ---: |
| `tests/test_a10a_soundcam_corner.py` | 3 | 2 | -1 |
| `tests/test_a11_soundcam_rt60.py` | 3 | 2 | -1 |
| `tests/test_schema_stage2_validates.py` | 1 | 1 | 0 |
| All others (ACE corpus, MISC_SOFT, etc) | 111 | 111 | 0 |

## Tag

Local-only `v0.10.0` per D11; v0.9.0 tag preserved.

## Reading order

1. ADR 0018 (substitute-disagreement record + remediation plan).
2. ADR 0016 §Status-update-2026-05-10 amendment (reverse-criterion firing record).
3. `docs/perf_verification_a10_soundcam_2026-05-10.md` (disagreement-record table + reproduction).
4. `.omc/research/cross-repo-pr-v0.10-deferred.md` (PR withdrawal + restart criteria).
5. RELEASE_NOTES_v0.9.0.md prepended notice (audit trail).
