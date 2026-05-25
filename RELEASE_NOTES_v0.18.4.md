# roomestim v0.18.4 — v0.19-cycle OQ 재검토 (doc-only PATCH)

PATCH bump `0.18.3` → `0.18.4`. See ADR 0034/0035/0036 §Status-update-v0.18.4
and ADR 0030 §Status-update-v0.18.4 Item Z.

## Summary

This is a **doc-only OQ re-examination** release. It builds no feature. The
v0.19-cycle cadence commitment required re-examining OQ-34/35/36/37/38 — five
open questions carrying a "v0.19 cycle 시작 시 재검토" cadence, one of which
(OQ-36) carried a D26 hard-wall forcing a real decision this cycle.

All five OQ triggers were independently verified against the live repo at
`c05c34e` (v0.18.3) — **all triggers are UNMET (0 reports)**. The correct,
honest disposition is therefore one forced WONTFIX (OQ-36) and four explicit
re-defers with concrete new cadences (OQ-34/35/37/38). No feature is built.

## What v0.18.4 decides (D57–D61)

### OQ-36 — CLOSED (WONTFIX) — D57

`room.yaml --schema 0.1` 다운그레이드 CLI flag: **D26 hard-wall forced
CLOSED (WONTFIX)**.

- Sole real consumer (`spatial_engine`) consumes only `layout.yaml`; never
  reads `room.yaml` (`docs/adr/0034-object-schema.md:142`). The trigger
  premise ("외부 consumer fail") has no applicable consumer.
- Trigger (외부 consumer fail 보고 ≥ 1건) = **0건** (full grep of git log /
  docs / artifacts).
- Library write-path already exists (`room_model_to_dict(schema_version=
  "0.1"|"0.1-draft")` + `write_room_yaml(schema_version=...)`); only CLI
  exposure is absent — programmatic callers can downgrade today.
- Adding a CLI `--schema` flag = YAGNI for a 0-consumer feature.

This is a formal close at the D26 hard-wall, not an indefinite re-defer.
**Reverse-criterion:** (a) `room.yaml` direct-consumer fails on unknown
`objects` field ≥ 1 report, OR (b) spatial_engine introduces `room.yaml`
consumption requiring 0.1-draft only → v0.20+ ADR 0034 §Status-update + CLI
flag.

ADR ref: ADR 0034 §Status-update-v0.18.4.

### OQ-37 — re-deferred to v0.20 — D60

`PlacedSpeaker.notes` round-trip via `x_notes` engine extension. Trigger
unmet (0 requests). ADR 0036 §C Level-1 explicit exclusion. Re-defer to
**v0.20 cycle** (grouped with OQ-38 for a single engine-schema consultation).

### OQ-38 — re-deferred to v0.20 — D61

`target_algorithm` full round-trip via `x_target_algorithm`. Trigger unmet
(DBAP/AMBISONICS label-loss 0 reports). D50 Level-1 explicit exclusion
(intentional design). Re-defer to **v0.20 cycle** (grouped with OQ-37).

### OQ-34 — re-deferred to v0.21 — D58

Cylinder/curved column support (`shape` field). Trigger unmet (0 user
requests; acoustic model still rectilinear shoebox ISM). Re-defer to
**v0.21 cycle** (avoids collision with v0.20 OQ-33 auto-detection hard wall).

### OQ-35 — re-deferred to v0.21 — D59

USDZ/gLTF acoustic metadata standard. Trigger unmet (Apple/Khronos standard
not published; 0 external-tool import requests). Sidecar stays
`"v0.1-internal"`. Re-defer to **v0.21 cycle** (grouped with OQ-34 —
both externally gated).

### Cadence summary

| OQ | Disposition | New cadence |
|---|---|---|
| OQ-36 | CLOSED (WONTFIX) — D26 hard-wall | n/a (closed) |
| OQ-37 | re-defer | v0.20 |
| OQ-38 | re-defer | v0.20 |
| OQ-34 | re-defer | v0.21 |
| OQ-35 | re-defer | v0.21 |

## What stays the same

| Item | Value |
|---|---|
| `roomestim_web.__version__` | `0.15-web.0` (web byte-equal — no web touch) |
| `__schema_version__` | `0.2-draft` (no new Object/RoomModel field) |
| `RoomModel` / `PlacedSpeaker` fields | Frozen (no additions) |
| `ObjectKind` | Closed `Literal["column","door","window"]` (no `shape`, no `cylinder`) |
| ADR 0009 ISM ≥ Eyring invariant | Unaffected |
| ADR 0030 predictor cascade §A–§E | Byte-equal |
| RT60 negative control | `1.9190766987173207` (acoustic path untouched) |
| D50 Level-1 ≤1e-9 structural contract | Preserved |
| `layout.yaml` format / engine schema | Unchanged (`version: '1.0'`; `geometry_schema.json` 불변) |
| All functional code | Byte-equal (doc-only cycle; `git diff -- roomestim/ roomestim_web/ tests/` shows ONLY the version line) |
| All prior §Status-update blocks (D22) | Byte-equal above the new §Status-update-v0.18.4 sections |

## Versioning note (PATCH rationale)

PATCH `0.18.4` per the project's de-facto SemVer cadence (D30): MINOR =
new user-facing feature/schema/API; PATCH = fix / doc / re-defer with no
new capability. This cycle ships zero new capability — one forced WONTFIX
and four re-defers. This is even more clearly PATCH than v0.18.2 (which
added one regression-lock test); this cycle adds no test. Precedent strictly
dominates.

"v0.19 cycle" is the cadence label (which OQs were due), not a version
mandate. The emitted version string is `0.18.4`, and all audit-trail
artifacts are version-named `v0.18.4`.

## Known gaps (unchanged from v0.18.3)

- OQ-30 per-wall α decomposition (v0.20+ or trigger-gated)
- OQ-23 polygon ISM non-shoebox
- OQ-37 `notes` round-trip (v0.20 re-exam)
- OQ-38 DBAP/AMBISONICS label collapse (v0.20 re-exam)
- OQ-34 cylinder column (v0.21 re-exam)
- OQ-35 acoustic metadata standard (v0.21 re-exam)
- OQ-39 ADR 0030 §Status-update split (deferred v0.21)
- OQ-33 non-RoomPlan auto object detection (v0.20 hard wall)
- D55 CLI `add-object` subcommand (OUT / user-gated)

## Tag note

Local-only PATCH tag (no PyPI release). `git diff c05c34e -- roomestim_web/`
= 0 bytes (web byte-equal confirmed). Default-lane test count: 271 passed /
6 skipped (byte-equal to v0.18.3 baseline — doc-only, zero new/removed tests).
Web lane: 70 passed / 1 skipped (unchanged).
