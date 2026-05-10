# SoundCam — synthesized fixture (roomestim v0.9..v0.10 A10a substitute)

> **§Honesty-correction-2026-05-10 (v0.10)**: v0.9.0 fixture values were
> placeholders (`citation_pending: true`); RELEASE_NOTES_v0.9.0.md +
> docs/perf_verification_a10a_soundcam_2026-05-09.md + ADR 0016
> §Consequences nonetheless advertised the values as "measured", which
> Critic flagged as a structural honesty leak (verdict 4.4/10).
> v0.10 retrieves paper-retrieved dims + RT60 from arXiv:2311.03517v2
> Appendix A.1-A.3 + Table I + Table 7. Living-room is REMOVED from the
> fixture (paper §A.2 explicitly: "the room does not have specific walls
> delineating it from parts of the rest of the house" — no authoritative
> dims). Lab + conference values are paper-confirmed; A11 PASS-gate is
> replaced by disagreement-record framing per ADR 0018. See v0.10
> RELEASE_NOTES + ADR 0018.

## Honesty marker (required)

> **GT corners + RT60 derived from SoundCam paper-published dimensions;
> live-mesh corner extraction is v0.10+ upgrade path.**

## Provenance

- **Upstream dataset**: SoundCam (Stanford, 2024). NeurIPS 2024 D&B track.
  - Paper: arXiv:2311.03517
  - Stanford Digital Repository: purl.stanford.edu/xq364hd5023
  - License: MIT (full text at `./LICENSE_MIT.txt`)
- **What we ship in v0.9**: rectangular shoebox **synthesised** ground-truth
  derived from the room dimensions reported in the upstream paper. The actual
  Azure Kinect 3D textured meshes + measured Schroeder RT60 traces are NOT
  redistributed here — see "Synthesis methodology" below.
- **What we DO NOT ship in v0.9**: live-mesh extraction from upstream PLY/CSV
  files. That is the v0.10+ upgrade path; ADR 0016 §Reverse-criterion records
  the substitute-vs-in-situ honesty boundary.

## Synthesis methodology

For each of the 2 SoundCam rooms (lab / conference; living_room REMOVED at v0.10 per ADR 0018):

1. Take published room dimensions (L × W × H, metres) from the SoundCam
   paper / repo metadata. If the executor was unable to access the
   canonical published values (paywall / repo offline), placeholder
   estimates from the v0.9 implementation prompt were used and are
   flagged here as `citation_pending: true` in the per-room `dims.yaml`.
2. Place the room as an axis-aligned rectangular shoebox centred at the
   floor-plane origin. Floor at `y = 0.0`, ceiling at `y = H`.
3. Synthesise the 4 corner xz coordinates as
   `[(-L/2, -W/2), (+L/2, -W/2), (+L/2, +W/2), (-L/2, +W/2)]` — CCW from
   the minimum-x,minimum-z corner.
4. Record measured RT60 at the 500 Hz mid-band per the paper / repo. If
   the executor used a placeholder estimate (paper paywalled / repo
   offline), the per-room `rt60.csv` carries `citation_pending: true` in
   its header comment and the value is a 0.30..0.60 s estimate consistent
   with the room class (lab / living_room / conference).

These three files per room — `dims.yaml`, `GT_corners.json`, `rt60.csv` —
form the cached default-lane GT used by `tests/test_a10a_soundcam_corner.py`
and `tests/test_a11_soundcam_rt60.py`.

## Why "synthesised" instead of "live mesh"

The upstream SoundCam meshes ship as Azure Kinect PLY plus per-room CSV
RT60 measurements. v0.9 deliberately stops short of redistributing those
files (they are several GB total) and stops short of live-deriving corners
from a downloaded mesh (the room corners under upstream-textured noise
require alpha-shape / RANSAC tooling out of v0.9 scope).

What v0.9 ships is the **substitute that the paper alone is sufficient to
construct**: a rectangular shoebox derived from the published dimensions.
The A10a corner test compares the roomestim Polycam-adapter-equivalent
construction (a shoebox built from the same dimensions) against the
synthesised corners — so the test is a fixture-integrity + path-execution
check, NOT a mesh-extraction validation. The A10b in-situ user-lab test
remains the authoritative corner-error gate (ADR 0016 §Reverse-criterion).

## Files

| Path | Purpose |
| --- | --- |
| `LICENSE_MIT.txt` | Verbatim upstream MIT license |
| `README.md` | This file |
| `lab/dims.yaml` | Lab room dimensions (treated/empty room) |
| `lab/GT_corners.json` | Synthesised 4 xz corners + ceiling height |
| `lab/rt60.csv` | Measured RT60 (paper Table 7 broadband Schroeder mean) |
| `conference/dims.yaml` | Conference room dimensions |
| `conference/GT_corners.json` | Synthesised corners |
| `conference/rt60.csv` | Measured RT60 (paper Table 7 broadband Schroeder mean) |

(`living_room/` was REMOVED at v0.10 — paper publishes no authoritative dims. See ADR 0018.)

## References

- SoundCam paper: arXiv:2311.03517
- SoundCam repository: purl.stanford.edu/xq364hd5023
- ADR 0016: `docs/adr/0016-stage2-schema-flip-via-substitute.md`
- ADR 0017: `docs/adr/0017-a10-layout-deferred-non-substitutable.md`
- v0.9 design: `.omc/plans/v0.9-design.md`
