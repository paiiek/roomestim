# roomestim v0.12-web.1 — Release Notes

**Date**: 2026-05-15b
**Predecessor**: v0.12-web.0 (`cfea9cb`)
**Release nature**: Parallel-track patch — acoustics-track core byte-equal to v0.13.0
EXCEPT `roomestim/adapters/{polycam.py,mesh.py}` (rename per D33 + ADR 0027).
Default-lane 128 → 134 passed + 4 skipped (134 = 128 + 4 mesh-format parametric tests +
2 new web-app tests; the 4 skipped = 3 SPATIAL_ENGINE_BUILD_DIR skips + 1 mypy-availability
skip in non-`[dev]` environments).
Web-lane 21 → 37 passed + 3 skipped (see "Web-lane skip-count clarification" below).

## What v0.12-web.1 ships

A mesh-format generalisation + 8-check verifier/reviewer cleanup that bundled
into a single patch on top of v0.12-web.0.

### Mesh-format generalisation (NEW)

Upload `.obj`, `.gltf`, `.glb`, or `.ply` room scans to the Gradio web demo —
all four were loaded via `trimesh>=4.0` (already a core dep) and converted
to a `RoomModel` via the convex-hull-of-vertex-projection geometry that
v0.1 shipped for `.obj`. glTF scene-graph semantic material labels were NOT
extracted; vertex coordinates only (see ADR 0027 + D6 caveat).
`PolycamAdapter` was retained as a deprecated subclass alias (D33).

### Verifier findings closed (4)

1. **mypy availability** — `tests/test_mypy_strict_baseline.py` now skips
   gracefully when mypy was not importable (PEP-668 system-Python case).
   CI lane installed `[dev]` so the gate stayed active in CI; the README
   documented `pip install --user --break-system-packages -e ".[dev,web]"`
   as the canonical dev-install command.
2. **Web-lane skip count** — investigation confirmed the v0.12-web.0
   release-notes claim of "21 pass + 1 skip" was a release-notes drift, NOT
   a regression: the "1 skip" referred to the web-lane binaural golden test
   (`test_binaural_render_byte_exact_golden`; OQ-19). The default lane also
   carried 2 additional skips that were never counted in the web-lane figure:

   ```
   SKIPPED tests/test_coords_engine_parity.py:59 — SPATIAL_ENGINE_BUILD_DIR unset (D10)
   SKIPPED tests/test_engine_roundtrip.py:46 — SPATIAL_ENGINE_BUILD_DIR unset (D10)
   SKIPPED tests/web/test_binaural_renderer.py:161 — HUTUBS/source data not bundled (P13e pending)
   ```

   At v0.12-web.0 the web lane had 21 pass + 1 skip (binaural golden only).
   At v0.12-web.1 the web lane had 37 pass + 3 skipped: the binaural golden
   (OQ-19 unchanged) + 2 pysofaconventions/SOFA-data `pytest.importorskip` triggers
   that surface when HUTUBS/KEMAR SOFA files are not bundled. No code change
   was needed; this entry is a release-notes correction only.
3. **3D viewer trace count** — invariant was `traces == len(surfaces) + 3`
   (NOT `traces >= len(speakers) + 3` as the v0.12-web.0 verifier
   heuristic had it). Docstring updated; assertion was already correct.
4. **Broadened `_on_submit` exception handling** — see code-reviewer
   findings below.

### Code-reviewer findings closed (4)

- **HIGH-1: HRTF attribution in UI footer.** New `gr.Markdown` with
  `elem_id="hrtf-attribution-footer"` enumerated HUTUBS (CC BY 4.0)
  + MIT KEMAR + LibriVox; the wording satisfied the CC BY 4.0
  attribution clause required by ADR 0026 + D31.
- **HIGH-2: `_to_pra` non-rectilinear AABB clamp gap.** New
  `_image_inside_floor()` helper using `shapely.Polygon.contains()`;
  out-of-polygon image-sources were dropped from the extrusion-path
  convolution sum with one aggregate `_LOG.warning(...)` per render.
- **MED-1: Widened `_on_submit` try/except.** All four output tiers
  caught `Exception`, logged via `logging.exception(...)` on the
  `roomestim_web` logger, and returned `None` for THAT tier only.
  A top-level guard (critic CRITICAL #1) wrapped the `run_pipeline()`
  call itself, returning `(None,) * 6` on any unhandled exception.
- **MED-2: Tempdir lifecycle.** D32 NEW — bounded `deque(maxlen=8)`
  of `TemporaryDirectory` instances + `atexit` reaper for
  `roomestim_*` dirs > 4 h old.
- **MED-3: Damping shape guard.** Explicit
  `if damping.ndim == 1 ... elif damping.shape[0] in (1, 6) ... else
  raise ValueError(...)` ladder replaced the `>= 6 else 0` heuristic.

## New ADR

| ADR | Title | Key decision |
|---|---|---|
| ADR 0027 | Mesh-format generalisation via single MeshAdapter | rename (NOT shim); 4 mesh formats; PolycamAdapter deprecated alias; D33. |

## New decisions

| D | Title | Reverse-criterion |
|---|---|---|
| D32 | Tempdir lifecycle: bounded deque + atexit reaper | OQ-18 / OQ-22 — tighten window to 30 min if container cycles < 1 h. |
| D33 | MeshAdapter rename (NOT shim) | If `DeprecationWarning` noise complaints land, downgrade to `PendingDeprecationWarning` at v0.13-web.0. |

## New open questions

- **OQ-20** — glTF binary (`.glb`) byte-equal reproducibility across trimesh versions
  (also covers glTF axis-convention caveat: Z-up root transform produces axis-swapped
  floor/ceiling projections).
- **OQ-21** — `.ply` files with vertex colour but no faces (points-only degenerate case).
- **OQ-22** — `_TEMP_REAPER` TTL window tightening if HF Spaces containers cycle < 1 h.

## What stays the same

- Core `roomestim/` package `__schema_version__` stayed `"0.1-draft"`.
- `MaterialLabel` enum stayed at 10 entries; `MELAMINE_FOAM` α₅₀₀ = 0.85
  byte-equal; D27 SECOND-AND-LAST re-deferral preserved; v0.14 hard wall
  unchanged.
- All 128 original default-lane tests passed byte-equal; the 134 count was
  128 + 4 NEW mesh-format parametric tests + 2 new web-app test stubs
  migrated to default lane; no existing test logic changed.
- Conference disagreement-record byte-equal; ADR 0018 + ADR 0021 byte-equal.
- Cross-repo PR stayed WITHDRAWN.
- Acoustics-track `pyproject.toml` version stayed `0.13.0`.

## Known gaps / pending work (unchanged from v0.12-web.0 unless noted)

- HUTUBS pp1 SOFA + MIT KEMAR SOFA + LibriVox source WAV still NOT bundled
  (file-size + licence gate); run `scripts/fetch_web_data.py`.
- OQ-17 / OQ-18 / OQ-19 from v0.12-web.0 stayed OPEN.
- D27 hard wall at v0.14 (Vorländer α₅₀₀) unchanged.
- **glTF axis-convention caveat (NEW at v0.12-web.1)**: `.gltf`/`.glb` files
  exported with a Z-up root transform produced geometrically valid but
  axis-swapped floor/ceiling projections (see ADR 0027 § "Consequences";
  OQ-20 broadened to cover this).
- **PLY no-faces degenerate case (NEW at v0.12-web.1, OQ-21)**: a points-only
  `.ply` upload (no triangular faces) was not caught by the existing vertex-shape
  guard; deferred to v0.12-web.2 on user report.

## Verification gate

18-check gate per `.omc/plans/v0.12-web.1-design.md` §7. All 18 PASS at ship.

Final test counts:

- Default lane: `pytest -m "not lab and not e2e and not web" -q` → **134 passed + 4 skipped**
  (was 134 passed + 1 mypy fail + 3 skipped at v0.12-web.0 in non-`[dev]` envs).
- Web lane: `pytest -m web -q` → **37 passed + 3 skipped**
  (was 21 passed + 1 skipped at v0.12-web.0; see skip-count clarification above).

## References

- Design plan: `.omc/plans/v0.12-web.1-design.md`.
- ADR 0027: `docs/adr/0027-mesh-format-generalisation.md`.
- D32 + D33: `.omc/plans/decisions.md`.
- OQ-20 + OQ-21 + OQ-22: `.omc/plans/open-questions.md`.
- Predecessor: `RELEASE_NOTES_v0.12-web.0.md`.
