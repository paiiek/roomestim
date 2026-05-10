---
title: "v0.10 A10a SoundCam smoke-test + A11 disagreement-record (honesty correction)"
date: 2026-05-10
predecessor_perf_doc: docs/perf_verification_a10a_soundcam_2026-05-09.md
generated_by: tests/test_a10a_soundcam_corner.py + tests/test_a11_soundcam_rt60.py
scope: A10a smoke-test (revealed-tautology framing) + A11 disagreement-record — SoundCam 2 rooms (living_room REMOVED at v0.10)
dataset: SoundCam (Stanford 2024, MIT) — arXiv:2311.03517v2 — purl.stanford.edu/xq364hd5023
honesty_marker: paper-retrieved dims + RT60 from arXiv:2311.03517v2 Appendix A.1/A.3 + Table I + Table 7 (cross-checked by 2 retrieval agents 2026-05-10); A10a smoke-test is structurally tautological per ADR 0018 §Consequences; A11 is disagreement-record, not PASS-gate
supersedes: docs/perf_verification_a10a_soundcam_2026-05-09.md
---

# v0.10 A10a SoundCam smoke-test + A11 disagreement-record (honesty correction)

This perf doc supersedes
`docs/perf_verification_a10a_soundcam_2026-05-09.md`. The v0.9.0
"PASS" framing on A10a corner err (0.00 cm) and A11 RT60 (lab 0.28 % /
living_room 5.57 % / conference 15.92 %) was based on placeholder
fixture values; v0.9.0 critic verdict (4.4/10) flagged this as a
structural honesty leak. v0.10 walks the over-claims back using
paper-retrieved dims + RT60 from arXiv:2311.03517v2 (Appendix A.1, A.3 +
Table I + Table 7).

The two SoundCam rooms covered here are **lab** and **conference**.
The living_room fixture was REMOVED at v0.10 (paper §A.2 explicitly
publishes no authoritative dims — see ADR 0018).

Reproduction commands:

```bash
/home/seung/miniforge3/bin/python -m pytest \
    tests/test_a10a_soundcam_corner.py \
    tests/test_a11_soundcam_rt60.py \
    -v
```

---

## §1 A10a — Per-room smoke-test (revealed-tautology framing)

GT corners are synthesised analytically from paper-published room
dimensions (axis-aligned shoebox centred at the floor-plane origin —
matching the `shoebox(L, W, H)` factory the test uses). The predicted
shoebox built from the same dims yields the same corners by
construction. The 0 cm result is therefore a **smoke-test for
fixture-integrity**, NOT a corner-extraction validation. Per ADR 0018
§Consequences this is now formally disclosed (v0.9 advertised "A10a
PASS — corner err 0.00 cm" without acknowledging the tautology).

| Room | Corners | Corner err (cm) | ≤ 10 cm gate | v0.10 framing |
| --- | ---: | ---: | --- | --- |
| lab | 4 | 0.00 | smoke-PASS | revealed-tautology (synthesised-vs-synthesised) |
| conference | 4 | 0.00 | smoke-PASS | revealed-tautology (synthesised-vs-synthesised) |
| living_room | — | — | — | REMOVED per ADR 0018 (no authoritative paper dims) |

The substantive corner-extraction gate is therefore **A10b in-situ
user-lab capture** (ADR 0016 §Reverse-criterion + ADR 0017 + ADR 0018);
A10a substitute is now formally a smoke-test, not a verification gate.
Live-mesh extraction (alpha-shape / RANSAC / Hough on actual SoundCam
PLY meshes) is the v0.11+ upgrade path that re-introduces a
non-tautological comparison (OQ-13e).

---

## §2 A11 — Per-room RT60 disagreement-record (paper-retrieved measured; default-enum Sabine predicted)

RT60 ground truth is the paper Table 7 Schroeder broadband mean (paper
does NOT publish per-octave-band numerical values; Figure 10 octave-band
graph is not numerically tabulated). The Sabine prediction is at
500 Hz using the default 9-entry MaterialLabel enum + paper-faithful
material maps. The unit mismatch (Sabine 500 Hz prediction vs Schroeder
broadband measurement) is recorded as part of the disagreement
signature; v0.11+ may sharpen via per-band reconciliation (OQ-13b).

v0.10 framing: this is a **disagreement-record table**, NOT a PASS-gate
table. Both rooms exceed ±20 %; the gap is recorded with a remediation
candidate per ADR 0018.

| Room | Predicted (s) | Measured (s) | Rel-err | ±20 % gate | Disagreement signature |
| --- | ---: | ---: | ---: | --- | --- |
| lab | 0.254 | 0.158 | +60 % | OUT (recorded) | default_enum_underrepresents_treated_room_absorption |
| conference | 0.449 | 0.581 | -22.7 % | OUT (recorded) | sabine_shoebox_underestimates_glass_wall_specular |
| living_room | — | — | — | — | REMOVED per ADR 0018 |

**Lab interpretation**: paper §A.1 describes treated room with NRC 1.26
melamine foam walls + NRC 1.0 fiberglass ceiling + office carpet floor.
Default 9-entry MaterialLabel enum max α_avg ≈ 0.46 (with `misc_soft`
walls + `ceiling_acoustic_tile` + `carpet`); paper α_avg ≈ 1.10. Default
enum systematically OVER-PREDICTS treated-room RT60. v0.11+ candidate:
add `MELAMINE_FOAM` (NRC 1.26) + `FIBERGLASS_CEILING` (NRC 1.0) +
`TILE_FLOOR` enums with paper-faithful coefficient sourcing (OQ-13a).

**Conference interpretation**: paper §A.3 confirms 3 drywall walls + 1
glass wall + ceiling tiles + office carpet. Default enum REPRESENTS the
paper materials adequately (`wall_painted` for drywall + `glass` +
`ceiling_acoustic_tile` + `carpet`). The −22.7 % residual is a
Sabine-shoebox-approximation effect (single glass wall specular
reflections under-counted by Sabine). v0.11+ candidate: glass-heavy-room
residual study with mirror-image source method or ray tracing
cross-check (OQ-13b).

ACE corpus A11 (gated E2E) byte-equal under v0.10 — substitute
disagreement does NOT invalidate ACE evidence; it bounds the
SUBSTITUTE's reach.

---

## §3 A10 three-way acceptance scorecard (v0.10)

Per ADR 0017 + ADR 0018:

| Sub-gate | v0.10 verdict | Citable ADR |
| --- | --- | --- |
| A10a corner geometry (substitute, smoke-test) | smoke-PASS — 0 cm by construction (revealed tautology) | ADR 0016 + ADR 0018 |
| A10b in-situ user lab | DEFERRED — no closure (priority ELEVATED under §Reverse-criterion firing) | ADR 0016 §Reverse-criterion + ADR 0018 |
| A10-layout VBAP-N vs physical | DEFERRED-with-classification — non-substitutable | ADR 0017 |
| A11 substitute (RT60) | disagreement-record (lab +60 %, conference −22.7 %) | ADR 0018 |

---

## §4 Dataset reference

- **SoundCam** — Schissler et al. (2024). *SoundCam: A Dataset for
  Finding Humans Using Room Acoustics.* NeurIPS 2024 Datasets and
  Benchmarks track. arXiv:2311.03517v2.
- **Stanford Digital Repository**: purl.stanford.edu/xq364hd5023.
- **License**: MIT (verbatim copy at
  `tests/fixtures/soundcam_synthesized/LICENSE_MIT.txt`).
- Two rooms used at v0.10 (down from 3 in v0.9): lab, conference. The
  living_room fixture was REMOVED at v0.10 per ADR 0018 (paper §A.2
  publishes no authoritative dims).
- Paper retrieval cross-checked by 2 independent retrieval agents on
  2026-05-10.

---

## §5 ADR 0016 §Reverse-criterion firing — note

This perf doc records the substantive evidence for ADR 0016
§Reverse-criterion item (1) firing at v0.10:

- substitute predicted-vs-measured rel-err > 20 % on lab + conference;
- both rooms run on the same predictor / adapter path that v0.9
  advertised as PASS;
- living_room removed per paper §A.2 honesty constraint.

Per item (2): schema marker REVERTED `"0.1"` → `"0.1-draft"` at
v0.10.0. Per item (3): cross-repo PR proposal WITHDRAWN at v0.10.0.

In-situ evidence ALWAYS overrides substitute. Paper-retrieved data is a
partial in-situ override (the paper authors are the in-situ
researchers); v0.10 honours that ratchet-safe contract.

The v0.11+ upgrade path that may re-flip the schema marker requires
ALL of: (i) MELAMINE_FOAM + FIBERGLASS_CEILING + TILE_FLOOR enums
(OQ-13a); (ii) A11 substitute returns to ±20 % on lab + conference under
paper-faithful material maps; (iii) successor ADR 0019+ ratifies the
re-flip. Until then, marker stays `"0.1-draft"`.
