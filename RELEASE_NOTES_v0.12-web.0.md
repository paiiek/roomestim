# roomestim v0.12-web.0 — Release Notes

**Date**: 2026-05-15
**Predecessor**: v0.13.0 (`2046681`) — Vorländer α₅₀₀ SECOND re-deferral (ADR 0019
§Status-update-2026-05-12-2) + D28 NEW + mypy --strict baseline + lint scope expansion-2.
**Release nature**: Parallel-track web demo release. Version string `v0.12-web.0` per D30
(acoustics-track `pyproject.toml` version stays `0.13.0`; `roomestim_web/__version__`
carries the parallel string). Core `roomestim/` library byte-equal to v0.13.0 EXCEPT
`roomestim/place/dispatch.py` (NEW) + `roomestim/cli.py` (refactor). Default-lane
128-pass CI gate verified by `tests/test_cli_idempotent.py` + unchanged 128-pass count.

## What v0.12-web.0 ships

A **Hugging Face Spaces-deployable Gradio web demo** at `roomestim_web/` — a sibling
package in the same git repository (ADR 0024). The user uploads a phone room scan
(`.usdz` or `.obj`), configures speaker placement, and receives five output views:

### Five output views

1. **3D interactive viewer** (Plotly) — room geometry + speaker positions rendered in
   the browser; azimuth/elevation DOA arcs overlaid.
2. **Acoustic report** — Sabine + Eyring RT60 predictions for all 6 octave bands
   (125–4000 Hz) displayed as a table + band plot; ±20 % precision disclaimer shown.
3. **Per-speaker setup PDF** (8 pages A4, reportlab) — one page per speaker: position
   (x, y, z metres), azimuth, elevation, distance; printable tape-measure reference.
4. **Binaural demo WAV** (30 s stereo, 48 kHz) — HUTUBS pp1 HRTF (TU Berlin, CC BY 4.0)
   convolved with pyroomacoustics ISM RIRs (`max_order=10`, `ray_tracing=False`,
   `fs=48000`) inside the user's own room. Lets the user hear their speaker layout
   through headphones (ADR 0025 + ADR 0026).
5. **ZIP archive** — all four artefacts above bundled as a single download.

### HF Spaces deploy

The repo-root `app.py` + `requirements.txt` + the front-matter YAML block at the top of
`README.md` constitute the canonical Spaces layout. The user pushes the repo to a
Hugging Face Space when ready; no additional configuration is required.

```bash
# Local install
pip install -e ".[web]"
python -m roomestim_web        # or: gradio app.py for hot-reload
```

### New optional extras `[web]`

| Package | Min version | Purpose |
|---|---|---|
| `gradio` | ≥ 4.0 | Blocks UI + file upload |
| `plotly` | ≥ 5.18 | 3D viewer |
| `pyroomacoustics` | ≥ 0.7 | ISM RIR synthesis |
| `pysofaconventions` | ≥ 0.1 | SOFA HRTF file loading |
| `reportlab` | ≥ 4.0 | PDF generation |
| `soundfile` | ≥ 0.12 | WAV write |

Install: `pip install -e ".[web]"`. Default `pip install -e .` and `pip install -e ".[dev]"`
install none of these.

## New ADRs

| ADR | Title | Key decision |
|---|---|---|
| ADR 0024 | Web demo as separate `roomestim_web` package (parallel track) | Sibling package in same repo; `[web]` extras; D29 filename routing; D30 versioning. |
| ADR 0025 | Binaural demo stack (pyroomacoustics ISM + HUTUBS HRTF) | ISM `max_order=10`, `ray_tracing=False`, `fs=48000`; scipy fftconvolve; HUTUBS PRIMARY. |
| ADR 0026 | HRTF dataset selection (HUTUBS PRIMARY + MIT KEMAR FALLBACK) | HUTUBS pp1 CC BY 4.0; MIT KEMAR Public Domain; both bundled under `roomestim_web/data/hrtf/`; 44.1 → 48 kHz resample at load. |

## New tests under `@pytest.mark.web`

22 tests selected under `pytest -m web` with `[web]` extras installed; 21 pass + 1
skipped (binaural byte-exact golden test skipped pending SOFA data files — OQ-19):

| Module | Test count | Notes |
|---|---|---|
| `tests/web/test_3d_viewer.py` | 3 | `test_room_figure_trace_count`, `test_room_figure_camera_default`, `test_room_figure_material_color_mapping` |
| `tests/web/test_acoustic_report.py` | 3 | `test_rt60_sabine_500hz_known_room`, `test_rt60_octave_band_returns_6_values`, `test_eyring_lessthan_or_equal_sabine` |
| `tests/web/test_archive.py` | 3 | `test_archive_contains_6_files`, `test_archive_readme_lists_provenance`, `test_archive_optional_files_excluded` |
| `tests/web/test_binaural_renderer.py` | 4 | `test_binaural_render_returns_stereo_wav`, `test_binaural_render_peak_at_minus_1_dbfs`, `test_binaural_doa_axis_mapping`; `test_binaural_render_byte_exact_golden` **skip** (SOFA absent — OQ-19) |
| `tests/web/test_pipeline_integration.py` | 2 | `test_pipeline_end_to_end_obj_produces_yamls`, `test_pipeline_end_to_end_with_archive` |
| `tests/web/test_setup_pdf.py` | 7 | `test_setup_pdf_generates_valid_pdf`, `test_setup_pdf_one_page_per_speaker`, `test_setup_pdf_no_exception_on_typical_layouts` (×4: vbap-4/8/16, dbap-8), `test_setup_pdf_wfs_with_valid_spacing` |

Without `[web]` extras the suite collects 9 tests via module-level
`pytest.importorskip` (3 modules skipped); the default-lane count stays
**unchanged at 128 passed** (`pytest -m "not lab and not e2e and not web"`).

## License + attribution

| Asset | Licence | Attribution required |
|---|---|---|
| HUTUBS pp1 SOFA (TU Berlin) | CC BY 4.0 | Yes — `HRTF_ATTRIBUTION.md` + `README.md` `## License` + web UI footer |
| MIT KEMAR SOFA (MIT Media Lab) | Public Domain | No (included in `HRTF_ATTRIBUTION.md` for completeness) |
| LibriVox source audio | Public Domain | No |
| roomestim core + web | MIT | Yes |

## What stays the same

- Core `roomestim/` package **`__schema_version__` stays `"0.1-draft"`** (Stage-2 flip
  still bound to A10b in-situ capture + ≥ 3 captures per ADR 0016 + D2).
- `MaterialLabel` enum stays at 10 entries; `MELAMINE_FOAM` α₅₀₀ = 0.85 byte-equal
  (D27 SECOND-AND-LAST re-deferral at v0.13.0; v0.14 hard wall unchanged).
- All 128 default-lane tests byte-equal pass; no test logic changed by the web track.
- Conference disagreement-record byte-equal; ADR 0018 + ADR 0021 byte-equal.
- Cross-repo PR stays WITHDRAWN (D11; ≥ 3 captures requirement unmet).
- `proto/*` byte-equal; predecessor RELEASE_NOTES byte-equal (v0.1.1 through v0.13.0).

## Known gaps / pending work

- **HUTUBS pp1 SOFA + MIT KEMAR SOFA + LibriVox source WAV NOT bundled in this commit**
  (file-size + licence-clarity gate). Run `scripts/fetch_web_data.py` to download and
  SHA-256-verify. Until data files land, the binaural view raises `HRTFDataMissingError`
  and the byte-exact golden test remains skipped.
- **OQ-17 OPEN** — HUTUBS pp1 subject-id stability across TU Berlin dataset re-issues.
- **OQ-18 OPEN** — HF Spaces cold-start wall time not yet measured (first deploy pending).
- **OQ-19 OPEN** — binaural WAV byte-exact reproducibility across pyroomacoustics versions
  and CPU architectures (x86_64 vs ARM64) unverified until data bundle lands.
- **D27 hard wall at v0.14** (Vorländer α₅₀₀ verbatim citation) — orthogonal to this
  parallel track; acoustics-track schedule unchanged.

## Verification gate

20-check gate per `.omc/plans/v0.12-web-design.md` §14:

- Default-lane 128-pass CI: `pytest -m "not lab and not e2e and not web" -q` → 128 passed.
- Web-lane CI with `[web]` extras: `pytest -m web -q` → 21 passed, 1 skipped (binaural golden, OQ-19).
- Tense-lint clean: `python scripts/lint_tense.py` → 0 flagged lines.
- 3 new ADR files present in `docs/adr/` (ADR 0024, 0025, 0026).
- D29 / D30 / D31 appended to `.omc/plans/decisions.md`.
- OQ-17 / OQ-18 / OQ-19 appended to `.omc/plans/open-questions.md`.

## References

- Design plan: `.omc/plans/v0.12-web-design.md` (parallel-track; D29 filename routing).
- ADR 0024: `docs/adr/0024-web-demo-separate-package.md`.
- ADR 0025: `docs/adr/0025-binaural-demo-stack.md`.
- ADR 0026: `docs/adr/0026-hrtf-dataset-selection.md`.
- D29 / D30 / D31: `.omc/plans/decisions.md`.
- OQ-17 / OQ-18 / OQ-19: `.omc/plans/open-questions.md`.
- Predecessor: `RELEASE_NOTES_v0.13.0.md` (acoustics track; byte-equal under web track).
