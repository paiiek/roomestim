# ADR 0004 — `room.yaml` schema lock-in timing

- **Status**: Accepted (finalized 2026-05-04)
- **Date**: 2026-05-03
- **Cross-ref**: design plan §2.3 Q5, §6.0, decisions D2.

## Context

`room.yaml` is a NEW schema owned by roomestim. Locking it too early forces engine-team rework;
locking too late leaves downstream consumers without a contract.

## Decision

**Two-stage lock within v0.1.** Stage 1 ships immediately (`version: "0.1-draft"`,
`additionalProperties: true`). Stage 2 (`version: "0.1"`, `additionalProperties: false`) flips
only after the lab fixture (A10) has produced ≥1 real `room.yaml` reviewed and committed as
`tests/fixtures/lab_real_room.yaml`. Cross-repo PR proposing
`spatial_engine/proto/room_schema.json` lands in **roomestim v0.2** after ≥10 real `room.yaml`
files have been produced and reviewed.

## Drivers

1. Forces design discipline early — engineers on both sides see the contract.
2. `version` field gates breakage with strict-validation flag.
3. Engine integration deferred until the schema has been exercised.

## Alternatives

- **Lock in v0.1 + propose to engine simultaneously**: rejected. Asks engine team to accept an
  unexercised schema; cross-repo PR coordination tax.
- **Keep schema fully experimental until v0.2**: rejected. Downstream consumers have no contract;
  every change breaks them silently.

## Consequences

- (+) Two-stage lock is the explicit insurance against premature lock-in.
- (+) Both schema variants ship in `roomestim/proto/` (`room_schema.draft.json`, `room_schema.json`).
- (−) Two test fixtures must stay in sync.

## Falsifier

If after Stage 2 lock, ≥3 of the next 10 real-world `room.yaml` files require schema patches,
revert to Stage 1 (`additionalProperties: true`) and reopen the schema for v0.2.

## Follow-ups

- Cross-repo PR checklist in design plan §11.4.
- ADR for engine-side `RoomGeometry` loader in v0.2.
- Stage-2 flip checklist: lab fixture (`tests/fixtures/lab_real_room.yaml`) + reviewer sign-off per D8/D2; then flip `version` const and `additionalProperties` in `proto/room_schema.json`.
- Cross-repo PR proposing `spatial_engine/proto/room_schema.json` targets roomestim v0.2 (after ≥10 real `room.yaml` files exercised).
