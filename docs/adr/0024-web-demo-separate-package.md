# ADR 0024 — Web demo as separate `roomestim_web` package (parallel track)

- **Status**: Accepted (v0.12-web.0)
- **Date**: 2026-05-15
- **Cross-ref**: D29 (output-filename routing for parallel-track design plans),
  D30 (web-demo-as-parallel-track release versioning), ADR 0025 (binaural demo
  stack), ADR 0026 (HRTF dataset selection), `.omc/plans/v0.12-web-design.md`
  §0.0 Item A.

## Status

Accepted at v0.12-web.0. Parallel-track release versioning (`v0.12-web.N`)
governed by D30. Design plan at `.omc/plans/v0.12-web-design.md` (D29 filename
routing). Core `roomestim/` package version (`0.13.0`) stays unchanged.

## Context

roomestim's core acoustics package (`roomestim/`) operates on the
`v0.X.Y` SemVer track. A Gradio-based web demo for Hugging Face Spaces
deployment covers a distinct concern — browser-facing UI, optional heavy
dependencies (Plotly, pyroomacoustics, reportlab, pysofaconventions,
soundfile), and a cold-start-aware deployment contract — that does not belong
in the core package:

1. The core package targets Python library consumers (CLI, adapter scripting,
   pytest); the web demo targets end-users uploading a phone scan through a
   browser.
2. The `[web]` optional extras (`gradio>=4.0`, `plotly>=5.18`,
   `pyroomacoustics>=0.7`, `pysofaconventions>=0.1`, `reportlab>=4.0`,
   `soundfile>=0.12`) are 200–400 MB of transitive installs; they must not
   become mandatory for CI or library consumers.
3. Hugging Face Spaces expects a specific root layout (`app.py`,
   `requirements.txt`, front-matter YAML in `README.md`) that is orthogonal
   to the Python package structure.
4. Web-demo release cadence (`v0.12-web.0`, `v0.12-web.1`, …) differs from
   the acoustics-track cadence (`v0.12.0`, `v0.13.0`, …). Coupling them
   under a single SemVer forces lock-step releases (D30 reverse-criterion).

## Decision

Ship the Gradio web demo as a **sibling package** `roomestim_web/` in the same
git repository, under a parallel version string `v{core_at_branch}-web.N`
(here: `v0.12-web.0`). Core `pyproject.toml [project] version` remains at
the acoustics-track number (`0.13.0`); `roomestim_web/__init__.py::__version__`
carries the parallel string.

Concrete layout:

```
roomestim_web/          # sibling package — web demo only
    __init__.py         # __version__ = "0.12-web.0"
    app.py              # Gradio blocks definition
    views/              # 3D viewer, acoustic report, PDF, binaural, ZIP
    data/hrtf/          # bundled SOFA files (HUTUBS pp1 + MIT KEMAR)
app.py                  # repo-root shim — `from roomestim_web.app import demo`
requirements.txt        # Spaces pinned deps
```

Install the web extras via:

```bash
pip install -e ".[web]"
```

The `[web]` extras group in `pyproject.toml` lists all heavy dependencies;
the default `pip install -e .` (or `pip install -e ".[dev]"`) installs none
of them. The default CI lane (`pytest -m "not lab and not e2e and not web"`)
is therefore unaffected.

## Drivers

1. **Dependency isolation**: `[web]` extras must not pollute the core install
   or CI default lane (200–400 MB transitive; incompatible with `roomestim/`
   target of zero browser-stack dependencies).
2. **HF Spaces layout contract**: Spaces reads `app.py` + `requirements.txt`
   at repo root and the README front-matter YAML; these are incompatible with
   the core `pyproject.toml`-driven layout without a shim.
3. **Cadence independence**: web demo iteration speed (UI polish, HRTF
   bundle updates, Gradio version bumps) outpaces acoustics-track iteration
   (each acoustics release requires ADR + OQ + characterising study). D30
   codifies the cadence separation.
4. **D29 filename routing**: the parallel-track design plan lives at
   `.omc/plans/v0.12-web-design.md` (not `v0.12-design.md`) to avoid
   overwriting the acoustics-track plan and silently breaking six ADR/OQ
   cross-references (D29 reverse-criterion).

## Alternatives considered

- **(a) Merge web demo into `roomestim/` as an optional sub-module.**
  Rejected: `[web]` extras at 200–400 MB would become visibly attached to
  the core package; every `pip install roomestim` page would list them;
  version coupling becomes mandatory.
- **(b) Separate git repository for the web demo.**
  Rejected: duplicates the `roomestim/` source tree (import path changes,
  two-repo CI maintenance, ADR cross-reference rot). Sibling package in the
  same repo avoids all of these at zero coordination cost.
- **(c) Docker-only Spaces deployment (no Gradio SDK).**
  Rejected: Docker spaces have longer cold-start; Gradio SDK path keeps
  Spaces build time under the §0.4 S3 pre-mortem target (OQ-18).
- **(d) Couple web version to acoustics SemVer.**
  Rejected: forces lock-step releases — an acoustics-only bugfix would bump
  the web demo version (confusing for HF Spaces deployment history); a
  UI-only web polish would require a full acoustics-track ADR cycle.

## Consequences

- **(+) Core default-lane CI unchanged**: `pytest -m "not lab and not e2e
  and not web"` runs 128 passed with zero web dependencies installed.
- **(+) 9 web tests** under `@pytest.mark.web` verifiable via
  `pip install -e ".[web]" && pytest -m web`.
- **(+) HF Spaces deploy** requires only: user pushes repo root → Spaces
  reads `app.py` + `requirements.txt` + README front-matter. No additional
  configuration file.
- **(+) Cadence independence**: `roomestim_web/__version__` advances
  independently of `roomestim/__version__`.
- **(−) Two `__version__` strings in the repo**: consumers must know to
  check `roomestim.__version__` for acoustics and
  `roomestim_web.__version__` for the web demo. Documented in README
  `## Web demo` section.
- **(−) HUTUBS + KEMAR SOFA + LibriVox source WAV files NOT bundled in
  this commit** (file-size + license-clarity gate; see
  `scripts/fetch_web_data.py` for protocol). Binaural byte-exact golden
  test skipped until data files land (OQ-17, OQ-19).

## Reverse-criterion

- If `[web]` combined install size exceeds 10 MB (§0.4 STOP threshold S3)
  → switch to Docker-based Space or trim deps (OQ-18 reverse-criterion fires).
- If web demo becomes mandatory for core install (e.g., engine team requires
  browser-based room-config UI as default) → collapse `roomestim_web/` into
  `roomestim/` under a single SemVer (D30 reverse-criterion fires).
- If HF Spaces cold-start exceeds 90 s → switch to Docker-based Space or
  trim deps (OQ-18 resolution candidate).

## §Status-update-v0.22.0 (2026-05-28)

**OQ-45 web public-deployment hardening (D71, ADR 0038).** Cycle B of the v0.21
post-audit fix program lands four web-source changes on the `roomestim_web`
track plus a declaration-only dependency reconcile:

- **Error-string scrub.** The three `app.py` echo sites (`_on_submit` ValueError
  branch, `_on_apply_overrides_wrapper`, `_on_export`) no longer place
  `str(exc)`/`{exc}` in the user-visible string — full detail stays in `_LOG`
  server-side, the user gets a generic "서버 로그를 확인하세요" message. This closes
  the residual OQ-42 echo-leak (the dev `_DEFAULT_ENGINE_SCHEMA_PATH` could
  surface via a validation message); see ADR 0033 §Status-update-v0.22.0.
- **Tempdir reaper per-PID.** `_reap_stale_tempdirs` globs `roomestim_{pid}_*`
  and the creation prefixes embed the PID → no cross-session deletion on a shared
  host (R-3: a crashed process's dirs are no longer reaped by a fresh process;
  accepted — HF Spaces containers cycle ≤ 24 h, OQ-22).
- **Upload `max_file_size` cap** at the `launch()` boundary (ADR 0038),
  mirroring the `MeshAdapter` byte bound.
- **`material_override.on_apply_overrides` list-input guard** (non-dict JSON
  payload → user-facing error + no crash).
- **Dependency reconcile (declaration-only).** `pyproject.toml` web extra
  `gradio>=4.0` → `>=4.44` (≤ installed 6.14.0; widens-forward, no downgrade);
  README front-matter `sdk_version` `"4.0.0"` → `"6.14.0"` (installed reality).
  The installed canonical env is unaffected. CI `pip-audit` + lockfile deferred
  to OQ-46.

`roomestim_web` `0.17-web.0` → `0.18-web.0` (web source changes; D30). Core
`roomestim` advances `0.21.0` → `0.22.0` (the `MeshAdapter` bound is the
SemVer-MINOR driver; ADR 0038). All gates green; RT60 byte-equal
`1.9190766987173207`.

## References

- D29 — `.omc/plans/decisions.md` (output-filename routing for parallel-track
  design plans; D29 prevents silent overwrite of acoustics-track `v0.12-design.md`).
- D30 — `.omc/plans/decisions.md` (web-demo-as-parallel-track release
  versioning; `v0.12-web.0` parallel string; `roomestim_web/__init__.py`).
- ADR 0025 — `docs/adr/0025-binaural-demo-stack.md` (pyroomacoustics ISM +
  HUTUBS HRTF stack for the binaural view).
- ADR 0026 — `docs/adr/0026-hrtf-dataset-selection.md` (HUTUBS pp1 PRIMARY
  + MIT KEMAR FALLBACK; bundling policy).
- OQ-17 — `.omc/plans/open-questions.md` (HUTUBS subject-id stability).
- OQ-18 — `.omc/plans/open-questions.md` (HF Spaces cold-start budget).
- OQ-19 — `.omc/plans/open-questions.md` (binaural WAV byte-exact
  reproducibility across pyroomacoustics versions).
- `.omc/plans/v0.12-web-design.md` §0.0 Item A, §3 P13g.
- `RELEASE_NOTES_v0.12-web.0.md` — parallel-track release notes.
