# roomestim v0.25.0 — image→geometry capture backend (single-pano, experimental rough tier)

MINOR bump `0.24.0` → `0.25.0`. See ADR 0045 (`docs/adr/0045-image-to-geometry-capture-backend.md`,
§Status-update-2026-06-04b), ADR 0046 (`docs/adr/0046-room-provenance-schema.md`), D85/D86
(`.omc/plans/decisions.md`), and the build plan `.omc/plans/image-backend-single-pano-build.md`.

This cycle lands roomestim's **first image→geometry capture path**: a single
equirectangular **panorama → RoomModel** adapter, exposed on the CLI as an
**opt-in experimental** backend. It is the north-star "no clean scan available →
feed a photo → get geometry + a speaker layout" capability, shipped honestly as a
**rough-estimate tier** — explicitly **NOT install-grade**. The previously
clean-scan-only ingest (RoomPlan / mesh) now has an image front-door.

> **Honesty up front.** Image-reconstructed geometry is tagged
> `provenance="reconstructed"`, all surface materials are `UNKNOWN` (no visual
> material inference), metric scale comes from an **assumed camera height**, and
> the CLI prints an `ESTIMATED` notice. **Accuracy is rough — and the realistic
> number is worse than the oracle ceiling.** With a user-supplied (imperfect)
> camera height — the actual deployment case — the prior spike measured a
> **median wall error of 35–57 cm and only 11–17 % of rooms within ≤15 cm**
> (PanoContext residential: 35 cm / 17 %; Stanford2D3D office: 57 cm / 11 %). The
> often-quoted **~43–45 % ≤15 cm is the perfect-scale-anchor *oracle* ceiling**
> (assumes the exact camera height is known a priori) — not what you get at
> inference. Camera-height error dominates: ±10 cm of cam-height alone ≈ 32 cm
> median wall error, and even on clean synthetic input with the exact height a
> single room can come back ~20 % off on one dimension. The ≤15 cm install-grade
> claim stays reserved for LiDAR/RoomPlan capture. Two feasibility spikes (OQ-53 multi-view scale,
> OQ-59 floor front-end) concluded image→geometry is a rough tier, not
> install-grade — this release ships exactly that, labeled as such.

## ① Room-level provenance schema (ADR 0046 / D85)

`RoomModel` gains a room-level `provenance: Literal["measured","reconstructed","assumed"]`
field (default `"assumed"`, the honest least-claim). Real-scan adapters
(roomplan/mesh/ace) assert `"measured"`; the new image adapter emits
`"reconstructed"`. Emitted in YAML only on `0.2-draft` (legacy `0.1` output stays
byte-equal); the reader defaults an absent key to `"assumed"`. This closes
ADR 0045 Reverse-criterion #4 / blocking gate #3 (no path for reconstructed
geometry to masquerade as sensor-measured) — a precondition for exposing any
image-derived output.

## ② `[vision]` optional extra + vendored HorizonNet (D86 / build P2)

A new **opt-in `[vision]` extra** (`torch`, `torchvision`, `Pillow`,
`huggingface_hub`, `gdown`, `scikit-learn`, `opencv-python`) gates all model
dependencies. **Core stays torch-free** (`import roomestim` /
`roomestim.adapters` / `roomestim.vision` pull no torch — ADR 0045 blocking
gate #4, the core/web boundary). HorizonNet's MIT inference code
(© 2019 Cheng Sun) is **vendored** under `roomestim/vision/horizonnet/`
(model + post-processing only; LICENSE + NOTICE included), with a Python-3.12
fix (`distutils` → `packaging`). **Model weights are never bundled** —
`roomestim/vision/checkpoints.py` resolves them download-on-first-use, keeping
roomestim's distribution MIT-clean.

## ③ Single-pano image adapter (`ImageAdapter`, build P3)

`roomestim/adapters/image.py` — `ImageAdapter` implements the `CaptureAdapter`
protocol. A gravity-aligned equirectangular panorama → HorizonNet corners →
metric floor polygon + ceiling height, with **metric scale from the camera
height** via the pre-wired `ScaleAnchor(type="known_distance", length_m=cam_h)`.
It reuses the existing `walls_from_floor_polygon` / `default_listener_area` /
mesh-style surface assembly (thin, consistent with other backends). Output:
`provenance="reconstructed"`, all surfaces `material=UNKNOWN` (§E — no visual
material guess), `objects=[]`. The torch-free geometry core (`_corners_to_room`)
is unit-tested in-gate against an analytically-inverted synthetic layout and
independently validated against the spike oracle (no mirror/sign error).

## ④ CLI exposure + `ESTIMATED` labeling (build P4)

`--backend image` is added to `ingest` and `run`, behind a **hard
`--experimental` gate** (without it: exit 1, before any torch import). New args:
`--cam-height M` (the scale anchor; omitted → adapter default + warning),
`--weights {st3d,zind}`, `--accept-zind-tou`. When the produced room is
`provenance="reconstructed"`, the CLI prints an honest **ESTIMATED** notice
(rough-estimate tier, approximate, not install-grade, ≤15 cm reserved for
LiDAR/RoomPlan). Measured backends (roomplan/polycam) are unchanged.

```bash
pip install -e ".[vision]"
python -m roomestim run --backend image --experimental \
    --cam-height 1.6 --input room_pano.jpg \
    --algorithm vbap --n-speakers 6 --out-dir /tmp/out
# → ESTIMATED notice; room.yaml (provenance=reconstructed) + layout.yaml
```

## Checkpoint licensing (code vs weights)

| Checkpoint | Domain | Code | Weights license | roomestim handling |
|---|---|---|---|---|
| `st3d` (default) | Structured3D (synthetic) | HorizonNet MIT | research dataset | download-on-first-use (HF `gum-tech/horizonnet-resnet50-rnn`) |
| `zind` (opt-in) | Zillow Indoor (real residential) | HorizonNet MIT | **ZInD ToU — non-commercial** | opt-in only (`--accept-zind-tou`); `gdown`; never bundled |

A genuinely better residential checkpoint (ZInD) exists but is non-commercial,
so the shipped default stays the permissively-usable (research) `st3d`. No
clearly-better *permissive* residential checkpoint is available — hence the
experimental rough-tier framing rather than an install-grade promotion.

## What stays the same

| Item | Value |
|---|---|
| Default `--backend` behavior | unchanged (`roomplan`/`polycam` measured; image is opt-in + experimental) |
| Core dependencies | unchanged — all model deps behind `[vision]` (core torch-free) |
| `roomestim_web` | untouched (web image upload deferred — see below) |
| `__schema_version__` | `0.2-draft` (provenance is an additive optional field) |
| Legacy `0.1` YAML output | byte-equal (provenance emitted only on `0.2-draft`) |
| ≤15 cm install-grade claim | reserved for LiDAR/RoomPlan (image is rough tier) |

## Deferred (honestly out of scope this cycle)

- **Web-tier image upload** — the CLI is the shipped surface; web upload UI is a
  follow-up (also: the canonical env's torchvision is broken, so the vision path
  is exercised out-of-gate).
- **Real per-corner uncertainty (OQ-57)** — converting the ~18 cm aggregate
  residual to calibrated per-corner confidence is an unsolved question; faking
  per-corner numbers would be dishonest. Disclosure for now = provenance +
  adapter warnings + the ESTIMATED label.
- **Per-Surface provenance** — room-level only this cycle (per-Surface needs
  schema `additionalProperties:false` edits; OQ-54 remainder OPEN).
- **In-domain accuracy (OQ-52)** — single-pano stays rough; an in-domain
  residential checkpoint to test install-grade promotion is inaccessible.

## Test / gate evidence

Canonical miniforge env (`/home/seung/miniforge3/bin/python -m pytest`):
- default (`-m "not lab and not web and not e2e"`): **345 passed / 5 skipped**
  (was 312 / 5 at v0.24.0 — +33 tests across provenance / vision-boundary /
  image-adapter / CLI-image).
- web (`-m web`): **86 passed / 4 skipped** (unchanged — web source untouched).
- ruff `roomestim`: clean. mypy strict (`roomestim`, vendored dir excluded):
  0 errors, 47 files. lint_tense: exit 0.
- **Boundary proof**: `import roomestim.cli` / `.adapters` / `.vision` are
  torch-free even though the canonical env's torchvision is broken.
- **End-to-end (out-of-gate, real HorizonNet, spike venv)**: `roomestim run
  --backend image --experimental --cam-height 1.6 --input roomA.png` →
  room.yaml (provenance=reconstructed) + layout.yaml + ESTIMATED notice, exit 0.
- Per-phase: executor → independent code-reviewer APPROVE (×4 phases) →
  independent verifier (this release). No self-approval.

## Versioning

- `roomestim`: `0.24.0` → `0.25.0` (MINOR — additive image backend + provenance
  field; no removed/altered default behavior). `pyproject.toml` + `roomestim/__init__.py`.
- `roomestim_web`: unchanged (web untouched).
- `__schema_version__`: `0.2-draft` (unchanged; provenance is additive optional).

## Tag note

Local-only MINOR tag (no PyPI release). Vendored HorizonNet under MIT
(`roomestim/vision/horizonnet/LICENSE` + `NOTICE`); model weights not redistributed.
