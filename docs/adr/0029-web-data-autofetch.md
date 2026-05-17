# ADR 0029 — Web Data Auto-Fetch Policy (v0.12-web.4)

**Date**: 2026-05-17
**Status**: ACCEPTED
**Deciders**: planner (v0.12-web.4-design.md), executor (2026-05-17)
**Drivers**: D36 (data-bundle prohibition), ADR 0026 §Reverse-criterion (>10 MB → fetch-on-first-use), HF Spaces cold-boot budget (<60 s)

---

## Context

v0.12-web.0–3 shipped with a print-only `scripts/fetch_web_data.py` that listed manual steps
to populate HRTF and audio data. As a result:

1. **Binaural tab was always empty** on HF Spaces (no data shipped; no auto-fetch).
2. **WFS aliasing errors were swallowed** silently — `_on_submit` returned `(None,)*6` for
   any `ValueError`, hiding the actionable remediation message from `dispatch.py:80-90`.

ADR 0026 §Reverse-criterion explicitly deferred to "download-on-first-use via
`scripts/fetch_web_data.py`" once the combined SOFA bundle exceeded 10 MB.
HUTUBS (1.36 GB zip) exceeds the HF Spaces cold-boot budget; KEMAR (2.5 MB) and
LibriVox MP3 (12.9 MB → trimmed WAV ≈ 5 MB) do not.

---

## Decision

### A. Auto-fetch scope

- **Auto-download**: KEMAR SOFA (CC BY 4.0, 2.5 MB) + LibriVox MP3 → 30 s WAV (Public Domain).
- **NOT auto-downloaded**: HUTUBS (1.36 GB zip) — manual guide only via
  `scripts/fetch_web_data.py --extract-hutubs`.
- **SHA-256 integrity gate (Status-update-2026-05-17)**: `_download_file()` accepts an
  optional `expected_sha256` parameter and verifies the digest after download, but
  `fetch_kemar` / `fetch_librivox` do NOT pin a digest in v0.12-web.4 — they pass
  `expected_sha256=None`, which emits a WARNING log (`fetch_web_data.py:86-89`) and
  proceeds. Honest status: **infrastructure landed, pin deferred to v0.12-web.5 per
  OQ-27**. Per ADR 0018 honesty discipline + D35, this gap is recorded here rather
  than papered over. A compromised upstream or MITM-capable network could deliver
  modified bytes; mitigations are HTTPS transport (system CA trust) + OQ-27 follow-up.
- **SHA-256 integrity gate (Status-update-v0.12-web.5 / 2026-05-17 PM)**: real KEMAR +
  LibriVox digests computed from upstream downloads and pinned as
  `KEMAR_SOFA_SHA256 = "2c531e26b225435aabec05024c125ed96d55ced0a63d16b89f34e249d0dc4fd9"` and
  `LIBRIVOX_MP3_SHA256 = "b3053bbc683f76b676e1c2233479e7254c701af95a42e4a614d68756f4fffa72"`
  in `scripts/fetch_web_data.py`; both `fetch_kemar` and `fetch_librivox` now forward
  `expected_sha256=`. Mismatch raises `RuntimeError` and unlinks the partial download.
  OQ-27 closed at v0.12-web.5. The WARNING-only branch in `_download_file:86-89`
  remains for callers that intentionally skip verification (only `extract_hutubs` path).
- **System deps + boot-time UX (Status-update-v0.12-web.6 / 2026-05-17 evening)**:
  `packages.txt` NEW at repo root declares `ffmpeg` for HF Spaces auto-detection
  (system-level dep required by `fetch_librivox`). `_ensure_web_data()` now returns
  `bool` so `build_demo()` can set the binaural-status Markdown's INITIAL value to
  "데이터 다운로드 중" (fetch started) or "데이터 미준비" (auto-fetch disabled / data
  absent) at boot, eliminating the "empty tab before first click" gap. DRY helper
  `scripts.fetch_web_data.auto_fetch_enabled()` centralises the env-gate
  interpretation. `_progress_quiet()` + `ROOMESTIM_WEB_QUIET_FETCH=1` suppresses
  per-block stdout progress in daemon mode (auto-set by the background thread).
  URL availability monitoring (separate from SHA pin) deferred to OQ-28 NEW.

### B. Background thread strategy (ADR 0029 §B)

`roomestim_web.app.build_demo()` calls `_ensure_web_data()` once at app construction.
`_ensure_web_data()`:
- Checks if KEMAR/HUTUBS SOFA and source.wav already exist.
- If data is missing AND `ROOMESTIM_WEB_AUTO_FETCH != "0"`, starts a **daemon thread**
  (`threading.Thread(daemon=True)`) that calls `scripts.fetch_web_data.auto_fetch()`.
- Uses a module-level lock to ensure only one fetch thread is ever started.
- Errors in the background thread are logged at WARNING level; they never crash the UI.

### C. UI fallback (ADR 0029 §C)

When `_on_submit` finds `source.wav` or HRTF SOFA absent:
- `binaural_str = None` (no audio returned to Gradio `gr.Audio`).
- `report_json["binaural_status"]` is set to a Korean user-facing message explaining the
  missing data and directing the user to run `--auto` or retry after the background fetch.

### D. WFS error surface (ADR 0029 §D)

`_on_submit` now catches `ValueError` separately before the broad `except Exception`:
- Returns `(None, None, {"error": str(exc), "algorithm": algorithm}, None, None, None)`.
- The `report_json` tab surface the aliasing message from `dispatch.py:80-90` including
  remediation steps (`--wfs-f-max-hz` / `--n-speakers` guidance).

### E. Env opt-out

`ROOMESTIM_WEB_AUTO_FETCH=0` disables all auto-fetch (background thread + `--auto` CLI flag).
Used in CI / air-gapped environments.

### F. ADR 0026 §Status-update-2026-05-17 (KEMAR fallback policy)

`hrtf_io.load_default_hrtf()` priority order unchanged: hutubs_pp1.sofa → kemar.sofa.
Auto-fetch only fetches KEMAR (not HUTUBS). In demo environments where HUTUBS is absent,
KEMAR serves as the binaural HRTF. Lab environments continue to prefer HUTUBS.
This is a clarification of ADR 0026 §Reverse-criterion, not a structural source switch.

---

## Consequences

- (+) Binaural demo works out-of-the-box on HF Spaces after a ~30 s background fetch.
- (+) WFS aliasing errors are visible to the user in the report JSON tab.
- (+) HUTUBS 1.36 GB download is never forced on cold-boot.
- (−) First binaural render may be unavailable if container boots before fetch completes.
  B3 fallback message handles this gracefully.
- (−) Background thread adds a small (<<1 MB RSS) daemon thread for the app lifetime.

## Reverse-criterion

- If cold-boot timeout (<60 s) is exceeded due to KEMAR download: switch to pre-bundled
  stub HRTF or accept no binaural demo on first boot. Successor ADR 0030.
- If ROOMESTIM_WEB_AUTO_FETCH=0 becomes the CI standard: remove background thread at v0.12-web.5.

## References

- ADR 0018 — honesty discipline (D35).
- ADR 0025 — binaural demo stack.
- ADR 0026 — HRTF dataset selection + attribution; §Reverse-criterion (>10 MB fetch-on-use).
- D36 — data-bundle prohibition + fetch-script + opt-out background.
- OQ-26 — HUTUBS URL long-term stability + GitHub mirror backup.
- OQ-27 — auto-fetch SHA-256 pin missing (deferred to v0.12-web.5).
- `scripts/fetch_web_data.py` — download implementation.
- `roomestim_web/app.py:_ensure_web_data()` — background thread entry point.
- `RELEASE_NOTES_v0.12-web.4.md` — release notes.
