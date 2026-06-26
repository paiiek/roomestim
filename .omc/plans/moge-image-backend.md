# Work Plan — MoGe metric single-image geometry backend (additive, opt-in)

- **Plan id**: `moge-image-backend`
- **Mode**: direct (no interview)
- **Target version**: **v0.52.0** (MINOR, additive)
- **New ADR**: **0057** (`docs/adr/0057-moge-metric-image-backend.md` — next free; 0056 is the highest existing)
- **Executor env**: `/home/seung/mmhoa/spike-vggt-multiview/venv/bin/python` (torch 2.5.1+cu121, CUDA True, RTX 2080 Ti). The canonical miniforge env has a **broken torchvision** and CANNOT run MoGe — the MoGe path is `[moge]`-marked and SKIPPED there, exactly like the existing `[vision]` path.
- **Default gate env (unchanged, byte-equal target)**: `/home/seung/miniforge3/bin/python -m pytest` — current baseline **770p / 7s**.
- **Feasibility source**: `.omc/research/env-feasibility-moge-acoustix-2026-06-27.md` (read before starting).

---

## Context

roomestim's only image backend today is `ImageAdapter` (`roomestim/adapters/image.py`): a single **equirectangular** panorama → vendored HorizonNet layout → a TORCH-FREE trig core that needs a **camera-height anchor** to fix metric scale. A single pano is provably scale-ambiguous (`r = cam_h / tan(-v_floor)`, see `IMAGE_CAM_H_SCALE_NOTE`), so the **dominant error lever is the cam_h assumption** (±10 cm → ±25–40 cm dimension error). Measured cold-eval on 244 real PanoContext panos: per-DIM median **39 cm (res) / 50 cm (office)**; per-room both-dims ≤15 cm only **8% / 3%**.

**MoGe** (Microsoft, github.com/microsoft/MoGe, MIT/Apache — commercially clean, UNLIKE HorizonNet's non-commercial *weights*) outputs **metric** geometry (metric point map + depth + FoV) from a single **perspective** RGB image, with **no cam_h assumption**. 

**Honest hypothesis (to be tested, NO FAKE NUMBERS)**: removing the cam_h lever could let MoGe beat HorizonNet on the existing cuboid eval. If it does NOT beat baseline, we ship MoGe as an **experimental / unvalidated alternative** (not default) — that is an acceptable, explicitly-allowed outcome.

### The central technical problem: modality + coverage mismatch

MoGe consumes a **perspective** image; the existing eval is **equirectangular** panos; and a *single* perspective view sees only a FRACTION of a room (one or two walls), so it cannot by itself produce a complete floor polygon. The plan resolves this with a **pano → multi-perspective-crop → fuse** path (below) so MoGe operates in its native modality while remaining benchmarkable against the pano cuboid GT. If a true apples-to-apples pano comparison proves infeasible at eval time, the fallback is to report MoGe as a different-input-modality backend on its own appropriate GT (documented, not faked).

---

## Work Objectives

1. Additive, opt-in **`MoGeAdapter`** (`roomestim/adapters/moge.py`) implementing the existing `CaptureAdapter` Protocol, torch-guarded (lazy import), emitting a `RoomModel` with `provenance="reconstructed"`, materials UNKNOWN, `objects=[]`, and an honest disclosure note.
2. The **core depth→RoomModel algorithm**: metric point cloud → gravity/floor-plane fit → ceiling plane → footprint polygon, with the multi-crop pano-fusion front-end.
3. **Packaging**: new `[moge]` extra + license note + mypy `ignore_missing_imports` + ruff guard, mirroring the `[vision]`/`pxr`/`blind_rt60` patterns.
4. **CLI**: `--backend moge` registered in `ingest` and `run`, behind the existing `--experimental` hard gate.
5. **Tests**: a `moge`-marked, skip-guarded adapter-contract + smoke test (NOT in default gate); plus an **out-of-gate honest eval script** that runs MoGe on the appropriate dataset and reports REAL per-room error vs HorizonNet baseline, writing results to `.omc/research/_data/`.
6. **Honest eval protocol + go/no-go decision rule** (ship default vs experimental).
7. **Release**: ADR 0057, README row + backend enumeration, single-source disclosure note, default gate byte-equal.

---

## Guardrails

### Must Have
- `import roomestim` and `import roomestim.adapters.moge` stay **torch-free** (torch / MoGe imported lazily inside the parse-time helper only). Verify with a subprocess test (mirror the `measured_rt60` `[audio]` subprocess lock pattern).
- Default gate (canonical broken-torch env) **byte-equal / unaffected**: 770p/7s, ruff clean, `mypy --strict` clean. The `moge` test path is marker-skipped there.
- **NO FAKE NUMBERS**: every accuracy figure comes from a real MoGe run on real data, produced by the eval script and written to `.omc/research/_data/`. No number invented in code, ADR, README, or this plan.
- Provenance on emitted `RoomModel` = `"reconstructed"`; materials = `MaterialLabel.UNKNOWN`; `objects=[]`; honest disclosure for metric-but-unvalidated-vs-real-metric-GT status AND the cuboid-only eval limit.
- Commercial license recorded in a pyproject comment (MIT/Apache), like the HorizonNet license note. Call out that MoGe **weights are MIT/Apache** (a commercial advantage over HorizonNet's non-commercial weights).

### Must NOT Have
- No vendoring of large MoGe weights into the repo; no weights committed. Resolve/download at runtime into a per-user cache (reuse the `roomestim/vision/checkpoints.py` philosophy: code is torch-free path-resolution; heavy deps lazy).
- No change to existing backends' behaviour or goldens (image/roomplan/polycam/multiview byte-equal).
- No new hard dependency in core `[project].dependencies`. MoGe lives ONLY in `[moge]`.
- No claim of install-grade (≤15 cm) accuracy. MoGe ships at the experimental rough-estimate tier until the eval proves otherwise.
- No `--cam-height` requirement for `moge` (it is metric); if `--cam-height` is passed with `--backend moge`, print an "ignored (metric backend)" NOTE rather than using it.

---

## Core algorithm sketch (depth/point-map → RoomModel)

All of this lives behind the lazy torch boundary in `roomestim/adapters/moge.py`. Torch-free helpers (plane math on plain numpy arrays) may live in a small `roomestim/vision/moge/` package; **numpy is already a core dep** so pure-geometry helpers can be import-safe, but keep the MoGe model import lazy.

**Input handling (modality bridge):**
- `parse(path)` inspects the image. **Equirectangular** (aspect ≈ 2:1) → multi-crop+fuse path. Otherwise → **single perspective** path (loud warning: partial-room coverage, footprint is the visible extent only).

**(A) Pano → perspective crops (known rotations).** Render N gnomonic/perspective crops from the equirectangular pano at fixed yaw angles (e.g. 8 × 45° yaw, ~90° FoV, plus optionally a down-pitched crop for floor coverage). Because WE generate the crops, the per-crop camera rotation `R_i` and intrinsics are **known exactly** — no pose estimation needed. (Implementation: standard equirect→perspective sampling; a small numpy/PIL helper, no torch.)

**(B) Per-crop MoGe inference.** For each crop, MoGe returns a metric point map `P_i` (H×W×3, camera frame) + validity mask (+ FoV/intrinsics; since we control the crop FoV we can also pass it). Lazy torch.

**(C) Fuse into one metric cloud.** Rotate each crop's points into the common pano frame by the known `R_i`: `P = ∪_i R_i · P_i[mask_i]`. Optional light per-crop scale reconciliation on overlapping regions if MoGe's per-crop metric scale drifts (measure overlap-consistency; if within a few %, trust as-is and RECORD the dispersion as an honesty metric — do not silently rescale without logging). Result: a single metric point cloud, **no cam_h used anywhere** — scale comes from MoGe.

**(D) Gravity / floor plane.** MoGe does not output gravity. Estimate the **floor plane** by RANSAC over the lowest band of points (or the dominant near-horizontal plane); its normal defines the up-axis, and the floor sets `y = 0`. (Reuse `roomestim/adapters/mesh.py` density-plane / up-axis utilities where they apply — `MeshAdapter` already has robust floor/ceiling density-plane extraction and `UpAxis` handling; prefer reuse over re-implementation.)

**(E) Ceiling plane.** The dominant near-horizontal plane ABOVE the floor → `ceiling_height_m = signed distance(ceiling_plane, floor_plane)`. Compute `ceiling_coverage` / `ceiling_confidence` via the existing heuristic (`CEILING_CONFIDENCE_HEURISTIC_NOTE`) if the mesh utilities expose it for a bare cloud; otherwise set `ceiling_confidence="unknown"` (honest: image-reconstructed).

**(F) Footprint.** Gravity-align the cloud, project the wall/vertical points onto the floor plane → 2D, and derive the footprint polygon by reusing `MeshAdapter`'s footprint extraction (`floor_reconstruction` convex/robust). `MultiviewAdapter` is the precedent: it feeds a bare point cloud into `MeshAdapter._extract_room_model`. **Strongly prefer routing the fused MoGe cloud through the same `MeshAdapter` extraction** so footprint/walls/listener-area/ceiling logic is shared, not duplicated. This makes `MoGeAdapter` largely a *front-end* that produces a metric, gravity-aligned cloud and delegates room extraction — minimal new geometry code, maximum reuse.

**(G) Emit `RoomModel`** exactly like `_corners_to_room` does: floor `Surface`, ceiling `Surface`, `walls_from_floor_polygon`, `default_listener_area`, `provenance="reconstructed"`, materials UNKNOWN, `objects=[]`, `schema_version` matching current adapters.

**Single-perspective path** (non-pano input): run MoGe once, do (D)–(G) on the partial cloud, but emit a LOUD warning that the footprint is the *visible extent only* (a single perspective cannot see a closed room) and is not a complete floor polygon. This is the honest CLI use for a single photo.

> Design note for the executor: the cleanest architecture is `MoGeAdapter.parse → fused metric cloud → MeshAdapter._extract_room_model(...)`. Confirm `MeshAdapter`/`MultiviewAdapter` expose a usable cloud-ingest entry point and reuse it; only add MoGe-specific code for crop generation, inference, fusion, and floor-plane gravity alignment.

---

## Honest eval protocol

- **Dataset**: 244 PanoContext panos at `/home/seung/mmhoa/spike-image-geometry/panocontext_data/pano_s2d3d/`. **GT is 100% CUBOID** — the benchmark can ONLY measure cuboid accuracy; this LIMIT must be labeled in the results file, ADR, and README.
- **Metric** (match the existing baseline): per-DIM error (median) and **per-room both-dims ≤15 cm rate**.
- **Baseline (from memory, recompute if HorizonNet eval is rerunnable)**: HorizonNet per-DIM median **39 cm (res) / 50 cm (office)**; per-room ≤15 cm **8% / 3%**. If feasible, re-run HorizonNet through the same harness so MoGe and baseline use identical scoring; otherwise cite the memory numbers and label them as prior-run.
- **MoGe scale honesty caveat (record in results)**: the PanoContext GT metric scale may itself be derived from an assumed camera height in the dataset annotations. If so, a metric MoGe that disagrees with GT is not necessarily wrong — note this explicitly so "beats cam_h" is not overclaimed. Where possible, report scale-invariant shape error (aspect ratios / angles) alongside absolute dimension error.
- **Output**: write `.omc/research/_data/moge_image_benchmark_results.md` (mirror `tests/eval/blind_rt60_benchmark.py` → `.omc/research/_data/blind_rt60_benchmark_results.md`). Include n, per-DIM distribution, ≤15 cm rate, per-crop scale dispersion, failures, and the cuboid-only + scale caveats.
- **Run env**: spike-vggt venv (GPU). Out-of-gate (no `test_` functions; `__main__` entrypoint), exactly like the blind-rt60 benchmark.

### Go / No-Go decision rule (pre-committed)
- **GO-as-candidate-default**: MoGe per-room ≤15 cm rate **strictly beats** HorizonNet on BOTH room classes (>8% res AND >3% office) AND per-DIM median is **lower** on both. → ship as a candidate primary image backend (still `--experimental` until a measured-metric-GT validation exists; record as a follow-up).
- **SHIP-EXPERIMENTAL**: MoGe does not clearly beat baseline (mixed or worse). → ship `--backend moge` as an experimental, unvalidated alternative; HorizonNet `image` stays the documented rough-tier; README/ADR state the eval outcome honestly with the real numbers.
- Either way the code ships (additive). The decision only sets default vs experimental framing and the README/ADR wording — fed by REAL numbers from the eval script.

---

## Task Flow (phased)

### Phase 0 — Install probe + license decision (executor, spike-vggt venv)
- `… /spike-vggt-multiview/venv/bin/pip install git+https://github.com/microsoft/MoGe.git` (or the PyPI package if one resolves — probe `pip index versions` for a published `moge`/`moge-*`). First weight download ~1–2 GB via `huggingface_hub`, cached.
- **License/packaging decision**: prefer a PyPI-published MoGe for the `[moge]` extra (keeps roomestim PyPI-publishable per ADR 0007). If MoGe is **git-only**, the `[moge]` extra uses a `git+https` direct reference and the pyproject comment MUST note this extra is not PyPI-wheel-installable (git install required) — same honesty bar as other notes. Alternatively load weights via `huggingface_hub` + a thin inference wrapper to avoid a direct git dep. Executor picks the cleanest of these AND records the rationale in the ADR.
- Confirm: MoGe runs on one sample image; capture the output keys (point map / depth / mask / intrinsics) to pin the adapter against the REAL API surface (do not code against assumed field names).

**Acceptance**: MoGe imports and runs in the spike venv; one inference produces a metric point map; the exact API (function/class names, return fields) is written into the ADR/plan notes; the extra/license approach is decided and justified.

### Phase 1 — `[moge]` packaging guards (pyproject)
- Add `[project.optional-dependencies].moge = [ … ]` with a license comment block (MIT/Apache; weights MIT/Apache = commercial advantage vs HorizonNet's NC weights; never-imported-at-core-time note; broken-canonical-torchvision skip note) modeled on the existing `vision`/`audio` extras.
- Add a `pytest` marker `moge: requires the [moge] extra (torch + MoGe weights); excluded from default CI`.
- Add mypy `ignore_missing_imports` override for the MoGe module(s) (mirror the `pxr.*` / `blind_rt60.*`/`soundfile.*` blocks). If a `roomestim/vision/moge/` vendored shim exists, add a ruff/mypy stance for it consistent with how `roomestim/vision/` (non-horizonnet) code is treated (our own vision code is NOT excluded and must pass strict).

**Acceptance**: `pip install 'roomestim[moge]'` resolves in the spike venv; `mypy --strict` and `ruff` still pass in the canonical env (the moge module type-checks or is overridden exactly like the existing patterns); default gate untouched.

### Phase 2 — Adapter `roomestim/adapters/moge.py`
- Implement `MoGeAdapter` with `parse(path, *, scale_anchor=None, octave_band=False) -> RoomModel` satisfying the `CaptureAdapter` Protocol (`roomestim/adapters/base.py`).
- Torch/MoGe imported lazily inside the inference helper (clear `ImportError` → `pip install 'roomestim[moge]'`, mirror `_infer_corners`). Module import stays torch-free.
- Implement the algorithm (A)–(G): pano-crop generator (torch-free numpy/PIL), per-crop MoGe inference (lazy), known-rotation fusion, floor/gravity RANSAC, and **delegate footprint/ceiling/walls to `MeshAdapter` cloud extraction** (reuse `MultiviewAdapter`'s path). Single-perspective fallback with loud partial-coverage warning.
- Emit `provenance="reconstructed"`, materials UNKNOWN, `objects=[]`, ceiling_confidence per heuristic-or-unknown. `scale_anchor` is accepted but ignored (metric backend) — warn if supplied.
- Add a `MOGE_METRIC_NOTE` to `roomestim/reconstruct/_disclosure.py` (single source of truth, add to `__all__`): metric single-image geometry, no cam_h assumption; metric scale UNVALIDATED against real metric GT; cuboid-only eval limit; single perspective sees partial room; experimental rough tier. Reference it (don't retype) from the adapter warnings, CLI disclosure, and README.

**Acceptance**: `import roomestim.adapters.moge` is torch-free (subprocess test); in the spike venv, `MoGeAdapter().parse(sample_pano)` returns a valid `RoomModel` (floor_polygon CCW, positive ceiling_height_m, provenance reconstructed, materials UNKNOWN, objects []).

### Phase 3 — CLI `--backend moge`
- Add `"moge"` to the `--backend` choices in BOTH the `ingest` (~line 129) and `run` (~line 365) subparsers; update the help text enumerations.
- Add a `moge` branch in `_get_adapter` (`roomestim/cli.py` ~line 808): behind the existing `_ExperimentalGate` (`--experimental` required, fires before any torch import); if `--floor-reconstruction` is passed it APPLIES (mesh-cloud extraction, like multiview — no "ignored" NOTE) — confirm against the delegation; if `--cam-height` is passed, print an "ignored (MoGe is metric)" NOTE.
- Extend the provenance disclosure phrase map (`roomestim/cli.py` ~line 973, the `{roomplan: …, image: …}.get(backend)` dict) with `"moge": "a single-image metric reconstruction (MoGe)"`.
- `_scale_anchor_for` stays image-only (returns None for moge) — no change needed beyond confirming moge isn't routed a cam_h anchor.

**Acceptance**: `roomestim ingest --backend moge --input <pano> --experimental` runs in the spike venv and writes a `room.yaml`; without `--experimental` it exits 1 with the gate message (torch-free path); canonical env help text lists `moge` without importing torch.

### Phase 4 — Tests (out-of-gate)
- `tests/test_moge_adapter.py`: `@pytest.mark.moge`, `importorskip` MoGe, a contract test (parse returns valid RoomModel with the honest fields) + a small smoke test on one sample image. Add the torch-free-import subprocess test (mirror `test_measured_rt60` import lock).
- `tests/eval/moge_image_benchmark.py`: out-of-gate `__main__` script (NO `test_` functions, not collected by default gate) modeled on `tests/eval/blind_rt60_benchmark.py`. Runs MoGe across the 244-pano dataset, scores per-DIM + per-room ≤15 cm vs HorizonNet baseline, writes `.omc/research/_data/moge_image_benchmark_results.md` with all real numbers + caveats.

**Acceptance**: default gate (canonical env) collects/passes **770p/7s byte-equal** (moge tests skipped); the moge-marked tests pass in the spike venv; the eval script produces a results file with REAL numbers.

### Phase 5 — Eval run + decision
- Run `tests/eval/moge_image_benchmark.py` in the spike venv. Apply the pre-committed go/no-go rule from the REAL numbers. Record the verdict (candidate-default vs experimental) in the ADR and README with the actual figures.

**Acceptance**: results file populated; verdict chosen strictly from real numbers; no fabricated values anywhere.

### Phase 6 — Docs + ADR + release (v0.52.0)
- **ADR 0057** `docs/adr/0057-moge-metric-image-backend.md` (Korean-header style like 0055/0056), with the full **ADR block**:
  - **Decision**: add additive opt-in MoGe metric image backend; default-vs-experimental per the eval verdict.
  - **Decision Drivers**: cam_h is the dominant image-backend error lever; MoGe is metric + commercially-licensed (MIT/Apache weights); additive/torch-free boundary preserved.
  - **Alternatives considered**: (a) keep HorizonNet-only; (b) vendor MoGe weights; (c) other metric depth models (Depth Anything / Metric3D / UniDepth) — note why MoGe (single-image metric point map + FoV, permissive license) was chosen; (d) single-perspective-only (rejected: can't close a room) vs multi-crop fusion (chosen).
  - **Why chosen**: removes the scale-ambiguity lever with a commercially-clean model, reusing existing cloud→RoomModel extraction.
  - **Consequences**: + metric, no cam_h; + commercial weights; − metric scale still unvalidated vs real metric GT; − GPU/env divergence (eval in spike venv, gate in canonical); − cuboid-only eval limit.
  - **Follow-ups**: real measured-metric-GT validation; PyPI-publishability of the `[moge]` extra if git-only; perspective-image GT benchmark.
  - **Status**: Accepted (v0.52.0, MINOR additive). Cite the REAL eval numbers.
- **README**: add the version row to the changelog table; extend the `--backend {roomplan,polycam,image,multiview}` enumeration (line ~70) to include `moge`; add a short MoGe paragraph (metric, no cam_h, MIT/Apache weights, experimental, cuboid-only eval limit, real numbers); add `[moge]` to the extras list (line ~698 area); add the MoGe license line near the HorizonNet license note (line ~735).
- **Single-source disclosure**: `MOGE_METRIC_NOTE` is the only place the honesty text lives; all surfaces reference it.

**Acceptance**: ADR 0057 complete with all fields + real numbers; README updated; disclosure single-sourced; default gate still 770p/7s byte-equal, ruff + mypy --strict clean.

### Phase 7 — Review + verify + commit
- `code-reviewer` pass (opus): torch-free boundary, no fake numbers, additivity/byte-equal, license correctness, reuse vs duplication of `MeshAdapter` extraction.
- `verifier` pass: canonical default gate 770p/7s byte-equal + ruff + mypy --strict; spike-venv moge tests pass; eval results file present with real numbers; subprocess torch-free import lock green.
- Commit per repo protocol (release-style message: `roomestim v0.52.0 — MoGe metric single-image backend (ADR 0057, MINOR additive)`), do NOT push unless the user asks.

**Acceptance**: reviewer APPROVE (fixes applied), verifier VERIFIED with evidence, working tree matches the plan.

---

## Success Criteria
- `roomestim/adapters/moge.py` exists, torch-free on import, satisfies `CaptureAdapter`, emits honest `RoomModel` (reconstructed / UNKNOWN / objects=[]).
- `[moge]` extra + marker + mypy/ruff guards in place; license recorded; MoGe weights MIT/Apache called out as a commercial advantage.
- `--backend moge` wired in `ingest` + `run`, `--experimental`-gated, cam-height ignored-with-NOTE.
- moge-marked + smoke + torch-free-import tests pass in spike venv; default canonical gate **770p/7s byte-equal**, ruff + mypy --strict clean.
- Eval script ran on real data; `.omc/research/_data/moge_image_benchmark_results.md` has REAL per-DIM + ≤15 cm numbers vs HorizonNet; go/no-go verdict applied.
- ADR 0057 (full ADR fields + real numbers), README row + enumeration + license line, `MOGE_METRIC_NOTE` single-sourced.
- NO fabricated numbers anywhere.

---

## Risks (ordered by severity)
1. **Pano-vs-perspective modality mismatch (biggest)** — resolved by the multi-crop fusion front-end (known rotations, no pose estimation). Residual risk: per-crop metric-scale drift across crops degrading the fused cloud → mitigate by measuring/reporting overlap scale dispersion; if large, document and fall back to perspective-GT benchmark rather than faking a pano comparison.
2. **MoGe metric-scale accuracy unvalidated vs real metric GT** — PanoContext GT scale may itself be cam_h-derived; report scale-invariant shape error alongside absolute, and label the unvalidated status (`MOGE_METRIC_NOTE`). Real metric-GT validation is a follow-up.
3. **Weights download / network** — 1–2 GB on first use; cache it; the eval/tests are out-of-gate so a flaky network never touches the default gate.
4. **GPU env divergence** — eval/tests run in the spike-vggt venv; the default gate runs in the broken-torchvision canonical env where the moge path is marker-skipped (same posture as `[vision]`). Verifier must run BOTH envs.
5. **Packaging / PyPI-publishability** — if MoGe is git-only, the `[moge]` extra's direct git ref blocks PyPI wheel install of that extra; document honestly (Phase 0 decision) and keep core publishable.

---

## Ordered task list (for the executor)
1. **Phase 0** — In the spike-vggt venv, install MoGe; run one inference; record the exact API surface + return fields; decide `[moge]` packaging (PyPI vs git vs hf_hub) and license note; verify weights are MIT/Apache.
2. **Phase 1** — Add `[moge]` extra (+license comment), `moge` pytest marker, mypy `ignore_missing_imports` override, ruff stance. Confirm canonical `mypy --strict` + `ruff` still clean and default gate untouched.
3. **Phase 2** — Write `roomestim/adapters/moge.py` (lazy torch; pano-crop generator; per-crop inference; known-rotation fusion; floor/gravity RANSAC; **delegate footprint/ceiling/walls to `MeshAdapter` cloud extraction** like `MultiviewAdapter`; single-perspective fallback). Add `MOGE_METRIC_NOTE` to `_disclosure.py` (`__all__`). Subprocess torch-free import test.
4. **Phase 3** — Wire `--backend moge` in `ingest` + `run`, `_get_adapter` branch behind `_ExperimentalGate`, cam-height ignored-NOTE, provenance phrase map entry.
5. **Phase 4** — `tests/test_moge_adapter.py` (`@pytest.mark.moge`, importorskip, contract + smoke + import-lock); `tests/eval/moge_image_benchmark.py` (out-of-gate `__main__`).
6. **Phase 5** — Run the eval on the 244-pano dataset in the spike venv; write `.omc/research/_data/moge_image_benchmark_results.md`; apply the go/no-go rule.
7. **Phase 6** — ADR 0057 (full fields + real numbers), README (row + enumeration + MoGe paragraph + extras + license line), single-sourced disclosure.
8. **Phase 7** — `code-reviewer` (opus) → apply fixes; `verifier` (canonical gate byte-equal 770p/7s + ruff + mypy; spike-venv moge tests; eval file present); commit `roomestim v0.52.0 …` (no push unless asked).

---

## Key file paths (reference)
- New: `roomestim/adapters/moge.py`; optional `roomestim/vision/moge/` (torch-free helpers); `tests/test_moge_adapter.py`; `tests/eval/moge_image_benchmark.py`; `docs/adr/0057-moge-metric-image-backend.md`; `.omc/research/_data/moge_image_benchmark_results.md` (eval output).
- Edit: `pyproject.toml` (`[moge]` extra, marker, mypy override); `roomestim/cli.py` (`_get_adapter` ~808, backend choices ~129/~365, provenance phrase map ~973); `roomestim/reconstruct/_disclosure.py` (`MOGE_METRIC_NOTE` + `__all__`); `README.md` (changelog row, backend enumeration ~70, extras ~698, license ~735).
- Reuse (do not duplicate): `roomestim/adapters/base.py` (`CaptureAdapter`, `ScaleAnchor`); `roomestim/adapters/mesh.py` (`MeshAdapter` cloud extraction, `FloorReconstruction`, `UpAxis`, density-plane floor/ceiling, ceiling_confidence); `roomestim/adapters/multiview.py` (bare-cloud → `MeshAdapter` precedent); `roomestim/adapters/image.py` (`_corners_to_room` emission pattern, lazy-import pattern); `roomestim/vision/checkpoints.py` (torch-free runtime weight resolution philosophy).
- Env: build/eval in `/home/seung/mmhoa/spike-vggt-multiview/venv/bin/python`; default gate in `/home/seung/miniforge3/bin/python -m pytest`.
