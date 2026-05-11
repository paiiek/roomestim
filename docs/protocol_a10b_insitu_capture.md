# A10b in-situ capture protocol (v0.11 minimal stub)

> **Scope note (v0.11)**: this DOC is **protocol-only**; no capture
> commitment ships with v0.11. A10b actual capture remained
> user-volunteer-only at v0.11 ship time. The protocol records the
> operational invariants that future user-volunteer captures must
> satisfy. See ADR 0016 §Reverse-criterion (in-situ ALWAYS overrides
> substitute) and OQ-12a (resolution-candidate unchanged on capture
> commitment).

## §1 Scope

A10b is the in-situ corner-extraction + RT60 measurement protocol
that supersedes A10a substitute fixtures (per ADR 0016
§Reverse-criterion). v0.11 shipped this protocol DOC ahead of any
specific user-volunteer capture, codifying the doc-ahead-of-impl
pattern recorded in D25.

This DOC was protocol-only. No capture commitment landed at v0.11.

## §2 Corner GT acceptance criteria

- **4 floor corners**, tape-measured, CCW order starting from the
  `min-x, min-z` corner (matches `canonicalize_ccw` invariant in
  `roomestim/model.py`).
- **1 ceiling height**, tape-measured at room centre.
- **Precision target**: **cm-precision** required; mm-precision
  tolerated; decimeter-precision (≥ 10 cm error) is a FAIL.
- Record measurements in `corners.json` alongside the upstream
  scan PLY/USDZ. The corner-error gate is satisfied when the
  tape-measured corners and the corner-extraction algorithm's
  output agree to within ≤ 10 cm Euclidean per corner.

## §3 Scan device list

- **PRIMARY**: RoomPlan iOS app (LiDAR-equipped iPad / iPhone Pro
  models). USDZ export expected.
- **SECONDARY**: Polycam iOS app (photogrammetry fallback when
  LiDAR is unavailable). PLY/USDZ export expected.
- **TERTIARY**: any calibrated scanner producing PLY/CSV upstream
  IF the device's internal calibration is published or
  independently verifiable. Live-mesh corner extraction from raw
  PLY/CSV is OUT OF SCOPE for v0.11; that gate is OQ-13e.

## §4 Minimum scan completeness

A valid A10b ingest requires ALL three:

1. **4 corners** extracted (corner-extraction algorithm reports
   ≥ 4 distinct corners agreeing with tape measurements per §2).
2. **1 ceiling height** extracted (flat-plane match against the
   scan upper surface).
3. **≥ 1 RT60 measurement** at the listening position (Schroeder
   broadband or per-band; sweep + impulse-response acceptable).

If ANY of (1)/(2)/(3) is missing → ABORT and re-scan. Do NOT
silently substitute or interpolate.

## §5 ABORT criteria

ABORT the capture and re-scan when ANY of the following fires:

- (a) Corner-extraction algorithm reports < 4 corners (likely
  partial scan, occlusion, or non-shoebox room outside v0.11
  scope).
- (b) Ceiling-height extraction fails (no flat-plane match within
  the room's upper 30 cm; likely vaulted ceiling, drop ceiling,
  or partial coverage).
- (c) RT60 trace shows obvious clipping, noise-floor near the
  measurement floor, or fewer than 30 dB of decay range.
- (d) Device calibration is unknown / unpublished and corner
  agreement with tape-measured GT exceeds 10 cm.

ABORT means STOP the capture and re-scan from a different
viewpoint / device / time of day. ABORT does NOT mean "fall back
to A10a substitute"; the substitute path was sealed at v0.10
under ADR 0018, and A10b is the only non-tautological gate (per
ADR 0016 §Reverse-criterion firing).

## §6 Cross-references

- ADR 0016 §Reverse-criterion — in-situ ALWAYS overrides
  substitute (Stage-2 schema flip predicate).
- ADR 0018 — substitute-disagreement record at v0.10; v0.11
  shipped this protocol DOC anticipating future v0.12+ closure.
- OQ-12a — A10b in-situ user-lab timeline; resolution-candidate
  unchanged on capture commitment at v0.11.
- OQ-13e — live-mesh extraction (PLY/CSV); deferred to v0.12+.
- D25 (v0.11) — doc-ahead-of-implementation pattern
  (`.omc/plans/decisions.md`).
