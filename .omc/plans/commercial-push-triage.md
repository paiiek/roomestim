# roomestim — Commercial-Release Push: Backlog Triage (Track B)

- **Author**: architect (read-only analysis pass)
- **Date**: 2026-06-27
- **Baseline**: v0.51.0 (`7e43368`, origin/main SYNCED), default 770p/7s · web 86p/3s · ruff/mypy(--strict,63) clean
- **Truth sources reconciled**: `roomestim-backlog.md` (STALE — authored at v0.31.0), MEMORY.md + memory files (current to v0.51.0), `docs/adr/0001..0056`, README version table, ADR §Status-update blocks. (No CHANGELOG.md exists — README table is the de-facto changelog.)
- **Mandate**: execute autonomously EVERY candidate that needs NO user-action (creds / manual external download) and is NOT a fake-number trap (no GT → unverifiable). NO FAKE NUMBERS. Commercial-OK licenses only.

---

## Headline finding (root cause of a thin GREEN pool)

The backlog (`roomestim-backlog.md`) was written at v0.31.0 and is **stale**: every Tier-1/2/3
code-only item it lists (⑥ alpha-shape/concave/robust footprint, ⑦ ambisonics, ⑧ multi-room
RoomCollection, ② RT60 error bar) has since **SHIPPED** (v0.32.0 → v0.51.0). The repo's own
2026-06-22 reconciliation already concluded: *"no fresh-shippable, data-independent,
non-user-gated candidate exists"* among the original feature backlog.

What that conclusion **missed** is that the goal has now changed to **commercial release**. That
re-opens a small but real class of GREEN work that was previously parked as "downstream demand
not triggered" (ADR 0007): **PyPI/packaging-readiness items**. Two concrete, honest, code-only
gaps exist there (see GREEN-1, GREEN-2). They are not north-star geometry — they are
release-hygiene — but they are the only genuinely NEW-unblocked, honestly-verifiable, code-only
work on the board.

The true north-star lever (break the multi-view coverage wall for deployable ≤15cm geometry)
remains **research/large-gated**, not GREEN: A1 multi-view VGGT fusion reached 12.7cm median
but n=10 + convex-room artifact; A2 proper TSDF was a **decisive negative** (VGGT inter-chunk
pose inconsistency makes free-space carving destructive). The only credible path is VGGT+GTSAM
global bundle-adjustment (Apache+BSD, commercial-OK) — a multi-week spike with GPU + validation
data, i.e. AMBER/large, deferred to the parallel research-pull track (A).

---

## Master triage table (ALL items)

| # | Item | ADR / ref | Bucket | Why this bucket |
|---|------|-----------|--------|-----------------|
| 1 | `py.typed` PEP 561 marker for installed wheel | ADR 0007 | **GREEN** | mypy --strict clean (63 files) but ships NO PEP 561 marker → installed wheel exposes 0 types to the named consumer `spatial_engine`. Honest, additive, S. |
| 2 | `CHANGELOG.md` from README version table | — / ADR 0007 | **GREEN** | No CHANGELOG exists. PyPI/commercial standard. 100% honest doc reorg of committed history (no new numbers). S. |
| 3 | RIR auralization Phase B/C (web-tier) | ADR 0044 | **GREEN (low/off-north-star)** | Code-only, honest "plausible-not-perceptually-validated" path exists (= Phase A pattern). But OQ-47/49 perceptual metric unresolved → cannot claim fidelity; explicitly LOW per north star. M. |
| 4 | Ambisonics PR4-lite: order-1 cube-8 alt rig | ADR 0041 | **GREEN (near-zero value)** | Pure closed-form verifiable math (isotropy proxy established). But whole ambisonics path is end-to-end UNCONFIRMED (engine routing gate unmet) → polishing an unrouted experimental feature. S. |
| 5 | Ambisonics PR4 full t-design (order 3) | ADR 0041 | **AMBER** | Needs external t-design coordinate TABLE with license/source (open OQ). dodecahedron-20 already "sufficient for experimental slice". Low value. |
| 6 | A3 increment 2b — ACE measured-corpus blind-RT60 end-to-end bench | ADR 0055 §Reverse | **AMBER** | External download (Zenodo 6257551). License = **CC-BY-ND** (No-Derivatives → caution even for an out-of-gate benchmark). Would give the first measured-room end-to-end RT60 error band. Reachable by an agent IF license cleared. |
| 7 | A2 polygon-ISM RT60 via FLAIR measured GT | ADR 0040 | **AMBER** | External download (Zenodo 17037517); license unverified (must check 1st-source — prior license hallucinations burned this project twice). |
| 8 | VGGT+GTSAM global-BA multi-view fusion (north-star frontier) | — / `project_multiview_fusion_a1` | **AMBER (large/research)** | Apache+BSD commercial-OK, but multi-week GPU spike + validation data. A2 TSDF already a decisive negative; needs global pose-graph. Highest north-star ROI *if* it pans out → research-pull track A. |
| 9 | `floor_reconstruction` auto→robust routing | ADR 0051 | **RED (weak-gate)** | Code-only but robust mode is n=1 SCRREAM-validated; changing `auto` routing risks silent regression with no broad GT. Honest path = keep opt-in (already is). |
| 10 | ① footprint/wall geometry validation | ADR 0042/0051 | **RED** | No known-extrinsic / single-room GT (ARKit Faro = whole-floor; SCRREAM capture object-centric). Already an HONEST NEGATIVE. |
| 11 | ③ polygon-ISM RT60 cascade (acoustic magnitude) | ADR 0040 | **RED** | Non-shoebox measured RT60 GT lacks material + ceiling-height → magnitude is a material-confound fake-number trap (reconfirmed 4×). Geometry/TOA portion already landed. |
| 12 | ④ RoomPlan parametric `.usdz` ingest | ADR 0047 | **RED** | Needs a real-device CapturedRoom export sample (user-gated). Geometry-only `.usdz` already ingested; splitter path already ships. |
| 13 | ⑤ furniture absorption validation | ADR 0043 | **RED** | Absorption GT = 0 → unverifiable. |
| 14 | cam_h known-size prior | ADR 0045 §D | **RED** | Detector + verifiable prior absent. |
| 15 | material inference (OQ-55) | ADR 0027 | **RED** | Material/absorption GT = 0. |
| 16 | per-corner uncertainty (OQ-57) | — | **RED** | Calibration data absent. |
| 17 | ⑩ PyPI publish (actual `twine upload`) | ADR 0007 | **RED (user-gated)** | Needs creds + user approval. Install-grade DONE; py.typed (GREEN-1) is the last pre-publish code gap. |
| 18 | OQ-37 (`x_notes` per-speaker) / OQ-34 (curved columns) | ADR 0036/0034 | **RED (no trigger)** | Reverse-trigger demand = 0 reports; engine-schema negotiation gated. |
| 19 | Ambisonics PR2-4 end-to-end de-experimental | ADR 0041 §D-3a | **RED (engine-gated)** | `require.md` ambisonics-mandatory promotion OR engine-team routing agreement — neither met (grep ambison = 0 hits, re-checked). |

---

## GREEN items — detail (ranked by commercial-release ROI)

### GREEN-1 — `py.typed` PEP 561 marker  ⭐ TOP
- **ADR**: 0007 (distribution) — directly advances the only pre-publish code gap.
- **Scope**: add `roomestim/py.typed` (empty marker) + extend `[tool.setuptools.package-data]`
  (`pyproject.toml:106-107` already declares a package-data glob) so the installed wheel ships it.
- **Why honest-verifiable**: roomestim is already mypy `--strict` clean across 63 files; the
  marker only *advertises* types that demonstrably pass. Verify by `pip install` into a clean
  venv and confirming `mypy` on a tiny consumer importing `roomestim` resolves types (currently
  it sees `Any`). No numbers invented.
- **Why #1 ROI**: it is the single concrete thing standing between "PyPI-ready" and "PyPI-typed
  for the named consumer `spatial_engine`", and ADR 0007's own reverse-criterion ("publish the
  moment a consumer appears") is now active. Pure release-hygiene, zero north-star risk.
- **Size**: S. **Ships as**: v0.51.1 PATCH (packaging-correctness, no checkout behavior change —
  same class as v0.37.1 proto-bundling fix).

### GREEN-2 — `CHANGELOG.md`
- **ADR**: none (release hygiene; supports ADR 0007).
- **Scope**: generate `CHANGELOG.md` (Keep-a-Changelog style) by transcribing the existing
  README version table (v0.1 → v0.51.0). All facts already committed; no new claims.
- **Why honest-verifiable**: it restates already-shipped, already-reviewed history — there is
  nothing to fabricate. Verify by diffing entries against the README table + git tags.
- **Size**: S. **Ships as**: bundle into v0.51.1 PATCH (with GREEN-1) or standalone doc commit.
- **Caveat**: lower ROI than GREEN-1 (README table already serves the function); do it only if
  bundling cost is ~0.

### GREEN-3 — RIR auralization Phase B/C
- **ADR**: 0044. **Scope**: extend web-tier `roomestim_web/rir.py` / `late_reverb.py` late-field
  model. **Honest path**: ship as "plausible, NOT perceptually validated" (exact Phase-A framing)
  because OQ-47/49 perceptual metric is unresolved.
- **Why ranked low**: explicitly LOWEST priority per north star (RIR is a *means*, not the
  product); off-geometry; any fidelity claim would be a fake-number trap, so value is capped at
  "more plausible plumbing." **Size**: M. **Ships as**: MINOR (web-tier only).

### GREEN-4 — Ambisonics PR4-lite (order-1 cube-8 alternative rig)
- **ADR**: 0041. **Scope**: add the documented cube-8 order-1 alternative (`ambisonics.py:110`
  already notes the cube vertices). Pure closed-form, verified by the existing isotropy proxy.
- **Why ranked lowest**: the entire ambisonics path is end-to-end UNCONFIRMED (engine routing
  gate unmet) and labelled experimental — adding a second order-1 rig polishes a feature with no
  contracted consumer. **Size**: S. **Ships as**: MINOR experimental. **Recommend: SKIP** unless
  trivially bundled.

---

## Newly-unblocked since backlog (v0.31.0 → v0.51.0)?

- **Code-only / data-on-disk**: NONE of the original feature backlog — they all shipped. The
  ONLY newly-relevant code-only items are the **packaging GREENs (py.typed, CHANGELOG)**, newly
  in-scope purely because the *goal* moved to commercial release (not because new data arrived).
- **New data on disk**: none that unblocks a GREEN. SCRREAM (deleted; object-centric capture =
  end-to-end footprint validation impossible), ARKit Faro (whole-floor, no per-room extrinsic),
  dEchorate (already consumed for ② / A1) — all remain RED/AMBER as before.
- **Feature-enabled follow-ups**: measured-RT60 (v0.49/0.51) enables **A3 2b (ACE)** — but that
  is AMBER (external CC-BY-ND download), not GREEN. multiview backend (v0.50) enables nothing new
  without new cloud GT.

---

## Recommendation (Track B → Phase 1 synthesis)

The honest state: **the code-only north-star (geometry-robustness) queue is exhausted**; the only
GREEN work is release-hygiene. Do NOT manufacture low-value off-north-star code (RIR B/C,
ambisonics cube-8) to look busy — that violates the compass.

**Execute this autopilot run, in order:**
1. **GREEN-1 `py.typed`** (S, v0.51.1 PATCH) — real commercial-release value, zero risk, closes
   ADR 0007's last code gap before a publish decision.
2. **GREEN-2 `CHANGELOG.md`** (S) — bundle with #1 in the same v0.51.1 PATCH.
3. **HOLD everything else for the parallel research-pull (Track A)**: the genuinely high-ROI
   north-star lever is whatever commercially-licensed ML technique Track A surfaces (e.g. a
   learned footprint/layout refiner, or a blind-RT60 improvement that lets A3 2b become
   GT-light). Re-triage once Track A reports.

Route GREEN-1/2 through OMC: planner (optional, trivial) → executor → code-reviewer → verifier
(full canonical gate `/home/seung/miniforge3/bin/python -m pytest`, default 770p/7s must hold
byte-equal + new packaging regression guard like v0.37.1's `test_proto_packaging.py`).

**AMBER candidates worth a user/agent decision** (in ROI order): VGGT+GTSAM frontier (north-star,
large) > A3 2b ACE (acoustics, license-cautious CC-BY-ND) > FLAIR polygon-RT60 (license-unverified).
**RED = do not touch** without the named unblock (creds / known-extrinsic GT / engine contract).
