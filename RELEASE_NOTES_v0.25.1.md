# roomestim v0.25.1 — image-backend honesty hardening (layout-boundary provenance + real-model golden)

PATCH bump `0.25.0` → `0.25.1`. See ADR 0046 (`docs/adr/0046-room-provenance-schema.md`,
§Status-update-2026-06-05), D87/D88 (`.omc/plans/decisions.md`), and the follow-up
plan `.omc/plans/image-backend-honesty-followups.md` (T1/T2).

This is an **honesty / robustness hardening** of the v0.25.0 image→geometry rough
tier — it carries the reconstructed-geometry marker further down the pipeline and
adds a regression lock on the real inference path. It is **NOT an accuracy
improvement**: single-pano image→geometry is still a **rough-estimate tier**,
explicitly **NOT install-grade** (≤15 cm stays reserved for LiDAR/RoomPlan).

> **Honesty up front.** Nothing about the estimate's accuracy changed. v0.25.0's
> rough-tier framing (`provenance="reconstructed"`, `UNKNOWN` materials, assumed
> camera-height scale, ~35–57 cm median wall error at inference) stands. This
> release only makes that rough-tier provenance *more durable and more testable*.

## ① layout.yaml now carries the `x_geometry_provenance` honesty marker (D87)

v0.25.0 persisted room-level `provenance` into `room.yaml` (on `0.2-draft`), but the
**placement artifact** (`layout.yaml`) did not record it — at that boundary the
rough-tier marker existed only as a **volatile CLI stderr** notice
(`_maybe_print_estimated_notice`). That gap is now closed:

- `PlacementResult` gains `geometry_provenance` (default the honest least-claim
  `"assumed"`). The CLI threads `room.provenance` onto the result at a single
  point (`_run_placement`), so a layout built from image-derived geometry keeps
  its origin.
- `export/layout_yaml.py` emits a top-level extension key `x_geometry_provenance`
  **only when the value `!= "assumed"`**. Every existing layout (all default
  `assumed`) therefore stays **byte-equal**; only `reconstructed` (rough marker)
  and `measured` (positive claim) are written. The geometry schema's
  `additionalProperties: true` root validates the key.
- `io/placement_yaml_reader.py` defaults a missing key to least-claim `"assumed"`
  and validates the value via the shared `_parse_provenance` (same path as the
  room reader), rejecting out-of-enum values with a consistent `ValueError`.
  write→read→write is idempotent (a stable fixed point).

Downstream consumers now see the rough-tier provenance at the artifact boundary,
not only via the room.yaml or the transient stderr notice.

## ② `place` subcommand now prints the ESTIMATED notice

`place` now emits the honest **ESTIMATED** stderr notice for reconstructed rooms,
consistent with `run` / `ingest` (it was previously omitted). The persistent,
machine-readable marker is ① above; this stderr line is the human-facing
secondary channel.

## ③ Real-model golden regression test (`vision`-marked) (D88)

Every other in-gate image test is **torch-free** (synthetic `cor_id`), leaving the
real torch path (`adapters/image._infer_corners` → vendored HorizonNet) otherwise
unguarded. A new `vision`-marked test (`tests/test_image_backend_golden.py`) runs
that real path on a **vendored procedural pano**
(`tests/fixtures/image/roomA_synth_pano.png`, our own MIT-clean render; GT
W=4.0 D=3.0 H=2.7 m) and locks the output:

- **exact** asserts on the honesty invariants — `provenance="reconstructed"`, all
  surfaces `material=UNKNOWN`, `objects==[]`, `n_surfaces==6` (4 walls);
- a dimensional regression lock at `abs=0.2 m` — a deliberate **cross-machine
  jitter bound** (CPU / torchvision build variation), **not** an accuracy bar
  (the estimate is rough, err ≈ 45–96 cm vs GT).

It **skips off-stack**: the canonical miniforge env has torch but a **broken
torchvision** (`operator torchvision::nms does not exist` — a `RuntimeError`, not
`ImportError`), so the guard probes the stack in a subprocess and catches broad
failures. It runs green only in the `[vision]` extra venv with the HorizonNet
checkpoint reachable.

## What stays the same

| Item | Value |
|---|---|
| Estimate accuracy | unchanged — still rough tier, NOT install-grade |
| `__schema_version__` | `0.2-draft` (unchanged; `x_geometry_provenance` is an additive extension key) |
| Existing `layout.yaml` output | byte-equal (key emitted only when `!= "assumed"`) |
| Core dependencies | unchanged — all model deps behind `[vision]` (core torch-free) |
| `roomestim_web` | untouched (web image upload still deferred — OQ-57) |
| ≤15 cm install-grade claim | reserved for LiDAR/RoomPlan |

## Test / gate evidence

Canonical miniforge env (`/home/seung/miniforge3/bin/python -m pytest`):
- default (`-m "not web and not lab and not e2e"`): **351 passed / 6 skipped**
  (the `vision` golden skips here — broken torchvision).
- web (`-m web`): **86 passed / 4 skipped** (unchanged — web source untouched).
- ruff `roomestim`: clean. mypy strict baseline + lint_tense: green (in default gate).
- **Out-of-gate (real HorizonNet, `[vision]` venv)**: the new golden runs green on
  the vendored synthetic pano.
- executor → independent code-reviewer APPROVE → independent verifier. No self-approval.

## Versioning

- `roomestim`: `0.25.0` → `0.25.1` (PATCH — additive, backward-compat honesty
  marker; no removed/altered default behavior). `pyproject.toml` +
  `roomestim/__init__.py`.
- `roomestim_web`: unchanged. `__schema_version__`: `0.2-draft` (unchanged).

## Tag note

Local-only PATCH tag (no PyPI release). Vendored HorizonNet under MIT; model
weights not redistributed. The vendored synthetic pano fixture is our own
procedural render (MIT-clean).
