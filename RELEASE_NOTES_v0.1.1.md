# roomestim v0.1.1 — Release Notes

**Date**: 2026-05-05
**Predecessor**: v0.1 (18/18 perf checks, all P0–P7 phases)
**Plan**: `.omc/plans/v0.1.1-closeout.md` (RALPLAN-DR iter-2 consensus)

---

## Summary

v0.1.1 closes 2/4 addressable v0.1 limitations (phase offset; DBAP
characterisation), defers 1/4 with documented decision (A2/A15 → spatial_engine
v0.2 per D10), and audits 1/4 (A10 fixture path → template + single-source
schema). Stage-2 schema flip and physical lab capture remain post-autopilot
human-gated per D8. RT60-vs-real-rooms model accuracy remains open (octave-band
extension deferred to v0.3 per D7).

Stage-2 flip and A10 capture pending human session.

---

## Closed (2/4)

### Phase offset gap — CLOSED

`place_vbap_ring` now accepts an optional `phase_offset_deg: float = 0.0`.
`place_vbap_dome` now accepts an optional `phase_offsets_deg: list[float] | None = None`
(default `None` ≡ `[0.0, 0.0]`; length-2 list, one offset per ring).

Default values reproduce v0.1 output byte-for-byte. The default branch is
guarded by a frozen pre-edit golden fixture
(`tests/fixtures/golden/place_vbap_ring_n8_default.yaml`) and asserted by
`tests/test_placement_vbap_phase.py::test_place_vbap_ring_phase_offset_default_byte_equal_to_golden`.

Lab-fixture position-subset match (`spatial_engine/configs/lab_8ch_aligned.yaml`)
verified by `tests/test_placement_vbap_phase.py::test_lab_8ch_aligned_position_subset_match`
on `version`, `name`, and per-speaker `id`/`channel`/`az_deg`/`el_deg`/`dist_m`.
Excluded fields (`regularity_hint`, `delay_ms`, `x_aim_*`) are documented in
the test docstring with reasons.

**Cross-repo note (regularity_hint divergence)**: position fields match
exactly between the lab fixture and the v0.1.1-generated dome, but
`regularity_hint` differs (lab=`CIRCULAR`, generated=`IRREGULAR`). The
engine's VBAP weighting selects different code paths on these two values
(`SpeakerLayout.h:38`), so position-subset match does NOT imply runtime
behavioural equivalence at the engine. roomestim follows the conservative
`IRREGULAR` downgrade for stacked rings (`vbap.py:9–11`); the lab fixture's
`CIRCULAR`-on-stacked-rings annotation is a deliberate engine-side choice.
Cross-repo reconciliation is v0.2 work — the engine's stacked-ring
classification rule and roomestim's classification rule must agree before
the runtime weighting question can be closed.

### DBAP geometry-dependence — CHARACTERISED

`tests/test_placement_dbap_under_noise.py` runs `place_dbap` over σ ∈ {0, 1, 2, 5} cm
× 100 trials of uniform floor-vertex perturbation (helper:
`perturb_room_with_walls(room, sigma_m, seed)` in `tests/fixtures/synthetic_rooms.py`).

Asserts **invariants only** (a-priori derivable):
- **Non-divergence**: every position component is finite.
- **On-surface**: ≤1 cm slack to the closest perturbed wall (DBAP places by surface projection by construction).
- **Count preservation**: `len(speakers) == 6` for every trial.

Drift histogram (mean / p50 / p95 / max) is **printed**, not asserted. The
2026-05-05 snapshot is committed in the test's leading docstring; reviewers
detect drift regressions visually in PR review. Greedy argmax tie-break is
structurally non-smooth (m-scale drift at sub-cm vertex noise on a 5×4 m
shoebox); no a-priori smooth bound is asserted because none exists.

## Deferred (1/4)

### A2 / A15 C++ harness binaries — DEFERRED to spatial_engine v0.2

The named binaries (`layout_loader_smoke`, `coords_parity_harness`) are not
part of the engine's v0.1 build. Authoring them inside roomestim was rejected
(smuggles C++ build complexity into a Python-first repo; a consumer-side
reimplementation of the engine's loader logic would invalidate the parity
claim).

Compensating coverage in v0.1.1 (note: this is COMPENSATING, not equivalent —
schema validation does not exercise the C++ loader, and the Python roundtrip
does not exercise the engine's coords code path):
- **A2 compensating coverage**: schema validation S5 (already passing) checks
  that emitted `layout.yaml` is shape-conformant per `geometry_schema.json`.
  It does NOT prove the engine's loader accepts that YAML at runtime.
- **A15 compensating coverage**: the 10 804-point Python coords roundtrip sweep
  at machine epsilon (`tests/test_coords_roundtrip.py`) exercises every code
  path the C++ harness would exercise on the Python side. It does NOT prove
  the C++ implementation matches; that proof lives in spatial_engine v0.2.

The skip-reason text in `tests/test_engine_roundtrip.py` and
`tests/test_coords_engine_parity.py` now distinguishes "build dir absent" from
"build dir present but harness binary not built" and points at
`.omc/plans/decisions.md` D10.

## Audited (1/4)

### A10 lab fixture path — AUDITED

`tests/fixtures/lab_real_groundtruth.yaml.template` is the new single source
of truth for the GT YAML schema. It contains every field
`tests/test_acceptance_lab_room.py` consumes, with `# TODO: replace with
tape-measured value` markers for human follow-up.

The acceptance test's inline schema docstring (previously lines 9–27) was
trimmed to a one-line pointer at the template — eliminating the duplicated
schema definition that was at risk of drifting from the test code.

`tests/fixtures/__init__.py` documents the human handoff: drop `lab_real.usdz`
from the iPad scan, rename `.yaml.template` → `.yaml`, run `pytest -m lab`.

---

## Known limitations (post-closeout, OPEN)

- **RT60 accuracy vs real rooms**: Sabine ±20% at best in real rooms
  (non-diffuse fields, low-frequency resonances). Octave-band absorption +
  reference-room comparison would close this but is deferred to v0.3 per D7.
- **A10 physical capture**: post-autopilot human-gated per D8 — fixture path
  audited (above), capture session itself awaits.

## R5 mitigation — best-effort note

Plan §5 R5 specified that `tests/fixtures/golden/place_vbap_ring_n8_default.yaml`
must be committed *before* `roomestim/place/vbap.py` is edited, providing a
git-history ordering proof that the golden encodes pre-edit state. roomestim
was not under git version control at the time of the v0.1.1 closeout, so this
ordering proof is **downgraded to best-effort**:

- **Within-session ordering**: file mtime shows golden generated at
  1777968131 < vbap.py edit at 1777968214 (Step 0 ran before Step 2). mtime
  is auditable but mutable.
- **Hash-based proof of pre-edit-ness**:
  `tests/fixtures/golden/.PROVENANCE` records the SHA256 of the golden YAML
  and the SHA256 of the verbatim pre-edit `_equal_angle_ring` function body.
  Anyone can revert that function to the recorded text, re-run the generator
  snippet, and check the output YAML hash matches. A future drift between the
  test path and the recorded pre-edit code is detectable as a hash mismatch.

This downgrade is documented per Critic ACCEPT-WITH-RESERVATIONS Major #1
(R5 mitigation structurally non-functional given untracked state).

## Files changed in v0.1.1

- `roomestim/place/vbap.py` — +`phase_offset_deg` on ring, +`phase_offsets_deg` on dome (additive; default behaviour byte-equal to v0.1).
- `tests/test_placement_vbap_phase.py` (NEW) — 6 tests covering phase offset on ring/dome + golden byte-equality + lab fixture position-subset match.
- `tests/test_placement_dbap_under_noise.py` (NEW) — DBAP characterisation under σ ∈ {0, 1, 2, 5} cm.
- `tests/fixtures/golden/place_vbap_ring_n8_default.yaml` (NEW, frozen pre-edit) — byte ground truth for the default-kwargs golden test.
- `tests/fixtures/synthetic_rooms.py` — +`perturb_room_with_walls(room, sigma_m, seed)` helper.
- `tests/fixtures/lab_real_groundtruth.yaml.template` (NEW) — A10 GT schema single source of truth.
- `tests/fixtures/__init__.py` — package docstring documents the A10 handoff.
- `tests/test_acceptance_lab_room.py` — schema docstring trimmed to template pointer.
- `tests/test_engine_roundtrip.py` — skip reason names D10.
- `tests/test_coords_engine_parity.py` — skip reason names D10.
- `.omc/plans/decisions.md` — +D10 (A2/A15 deferral rationale).
- `docs/perf_verification_2026-05-04.md` — Limitations section recategorised (CLOSED / CHARACTERISED / DEFERRED / AUDITED / OPEN).

## Test summary

- Default lane (`pytest -m "not lab"`): baseline 18 + 6 new (phase) + 4 new (dbap-noise parametric) = **28 collected, 28 passed**.
- Lab lane (`pytest -m lab`): SKIPs cleanly until `lab_real.usdz` and `lab_real_groundtruth.yaml` are dropped.
- A2/A15: SKIP with new skip-reason naming D10.
- Idempotency (A12): byte equality preserved (default `phase_offset_deg=0.0` reproduces pre-edit golden).
