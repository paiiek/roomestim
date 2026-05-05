# ADR 0001 — Capture backend priority

- **Status**: Accepted (finalized 2026-05-04)
- **Date**: 2026-05-03
- **Cross-ref**: design plan §2.3 Q1, decisions D6.

## Context

roomestim must consume a phone room-scan and produce a metric-scale `RoomModel`. Three viable
backends exist: Apple RoomPlan (USDZ + JSON sidecar, parametric walls, LiDAR-scaled), Polycam
(USDZ/OBJ mesh, cross-platform), COLMAP (any video, scale-ambiguous).

## Decision

**RoomPlan first-class, Polycam supported secondary, COLMAP experimental** behind `[colmap]`
extra and `--experimental` flag.

## Drivers

1. RoomPlan emits parametric walls — dramatically reduces v0.1 CV scope.
2. LiDAR scale is metric out of the box; no ArUco / known-distance anchor required.
3. Polycam fills the device-availability gap (Android, non-Pro iPhones).

## Alternatives

- **Polycam-first**: rejected. Mesh-only output forces wall re-detection in v0.1 (more CV).
- **COLMAP-only**: rejected. Scale ambiguity is a research problem, not v0.1 scope.

## Consequences

- (+) v0.1 CV work is bounded.
- (+) Cross-platform fallback exists via Polycam (P5).
- (−) iOS Pro device required for first-class path. Mitigated by D6 (test fixture flexes to
  whichever device captures).

## Falsifier

If P5 (Polycam adapter) ships before P4 (RoomPlan adapter) due to capture-device unavailability,
reverse this ADR; Polycam becomes first-class de facto.

## Follow-ups

- Document iOS Pro device requirement in README (done — architecture.md capture matrix).
- Polycam-first reversal trigger: if P5 ships before P4 due to device unavailability, update this ADR (cross-ref D6).
- COLMAP scale-anchor work (ArUco / known-distance reference) is v0.3 scope (cross-ref D6 reversal criteria).
