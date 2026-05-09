# RELEASE NOTES — roomestim v0.8.0

v0.8.0 is a **substantive numerical-experiment release**. v0.7's critic
verdict labelled v0.7 as borderline ADR-theatre and demanded that v0.8 ship
a residual-shrinking experiment rather than another bookkeeping-only
release. v0.8 ships exactly that: a Lecture_2 ceiling/seat bracketing
harness whose verdict — positive or null — is the deliverable, plus a
per-band ex-Building_Lobby MAE snapshot test that freezes the v0.6/v0.7
residual signature so future PRs editing predictor / adapter / per-band
tables that shift any MAE force a one-line golden update + PR justification.

The v0.8 SemVer minor bump is justified on substantive numerical-experiment
grounds, addressing the v0.7 critic SemVer-loose finding ("v0.6 / v0.7
should have been patches"): v0.8 ships a falsifiable experiment whose
result re-orients the v0.9+ work plan, plus a snapshot infrastructure that
auto-evaluates future PRs against residual coverage.

A12 byte-equality of every v0.7.0 default-lane test is preserved
(104 → 111; +5 bracketing tests + +2 MAE snapshot tests; nothing existing
is modified). `__schema_version__` stays `"0.1-draft"`. No new enum entry.
No predictor change. No coefficient revision. No adapter-data mutation.
v0.6/v0.7 numerical baseline preserved (overrides default-equivalent path
is byte-equal).

---

## Highlights

- **Lecture_2 ceiling/seat sensitivity bracketing — published null result**:
  Four committed variants (V0 baseline / V1 ceiling=`ceiling_drywall` / V2
  lecture_seat α split unoccupied profile / V3 V1+V2) and one optional
  bounding case (V4 ceiling=`wall_concrete`; env-gated by
  `ROOMESTIM_BRACKET_V4=1`) are evaluated against the in-tree measured-T60
  fixture. The verdict at v0.8 ship is **NULL**: V3 closes Lecture_2 |err|
  from −0.908 s to −0.879 s @500 Hz Sabine (within bracket; not below the
  ±0.5 s acceptance envelope) and regresses Meeting_1 / Meeting_2 by
  +0.108 s / +0.142 s @500 Hz Sabine vs V0. **Single-coefficient
  ceiling/seat swap is insufficient** to close the Lecture_2 residual
  without external regression. v0.9 considers the broader F4a per-band
  sensitivity sweep + coupled-space modelling per ADR 0015
  §Reverse-trigger. This null result is itself a publishable v0.8 finding:
  it rules out F3 + lecture_seat single-coefficient explanations for the
  Lecture_2 under-prediction.
- **Per-band ex-BL MAE snapshot — frozen golden**: `tests/fixtures/golden/
  per_band_mae_ex_bl_2026-05-09.json` records the v0.6 perf doc per-band-
  per-predictor MAE figures (mean of |err| over the 6 ex-BL rooms; ±0.001 s
  tolerance). Future PRs editing the predictor / adapter / per-band tables
  that shift any MAE trip the snapshot test; intentional updates are a
  one-line golden change + PR justification.
- **Library defaults UNCHANGED**: `_build_room_model(...)` gains an
  additive `overrides=` kwarg (default `None` ⇒ byte-equal to v0.7).
  `MaterialLabel`, `MaterialAbsorption{,Bands}`, `_FURNITURE_BY_ROOM`,
  `_PIECE_EQUIVALENT_ABSORPTION_*`, `roomestim/place/wfs.py`,
  `roomestim/cli.py`, `roomestim/model.py` byte-equal to v0.7.

---

## What changed

### Adapter — Scope A bracketing hook

- `roomestim/adapters/ace_challenge.py`:
  - + `_RoomBuildOverrides` frozen dataclass (`ceiling_label`,
    `seat_alpha_500`, `seat_alpha_bands`).
  - `_build_room_model(...)` gains `overrides: _RoomBuildOverrides | None
    = None` keyword arg. When `overrides is None` the output is
    byte-equal to v0.7 (no surface added/removed/reordered; absorption
    values per surface unchanged).
  - + sibling helper `_misc_soft_surface_from_furniture_with_alpha(...)`
    that takes 500 Hz scalar α and 6-band tuple as args (used only when
    `overrides.seat_alpha_500 is not None`). The original
    `_misc_soft_surface_from_furniture(...)` keeps its current signature
    and is byte-equal.
  - **NO** mutation of `MaterialAbsorption{,Bands}`, `_FURNITURE_BY_ROOM`,
    `_PIECE_EQUIVALENT_ABSORPTION_*`. Module-level dicts byte-equal to
    v0.7.

### Tests — Scope A bracketing harness

- `tests/test_lecture_2_ceiling_seat_bracket.py` (NEW; +5 default-lane
  tests):
  - `test_bracket_v0_baseline_matches_v07_perf_doc_500hz` — pin V0 baseline
    500 Hz Sabine values against `docs/perf_verification_e2e_2026-05-08.md`
    within ±0.001 s. Pre-condition for V1..V4: if this fails, the
    override hook leaked into the default code path or a coefficient
    drifted.
  - `test_bracket_v1_ceiling_drywall_lecture2_500hz` — Lecture_2 V1
    override path executes and produces a finite Sabine 500 Hz prediction
    that differs from V0.
  - `test_bracket_v2_lecture_seat_unoccupied_lecture2_500hz` — Lecture_2
    V2 override path executes and produces a finite Sabine 500 Hz
    prediction that differs from V0.
  - `test_bracket_v3_combined_lecture2_500hz` — V3 acceptance OR null
    verdict (passes either way; verdict recorded in the appendix doc + ADR
    0015 + this release notes file).
  - `test_bracket_emits_perf_doc_appendix` — recompute V0..V3 (+V4 if env-
    gated) for all 6 furniture-tracked rooms × 6 octave bands × 2
    predictors and write
    `docs/perf_verification_lecture2_bracket_2026-05-09.md` with
    deterministic byte-content (re-running yields identical md5sum).

### Tests — Scope B per-band ex-BL MAE snapshot

- `tests/test_per_band_mae_ex_bl_snapshot.py` (NEW; +2 default-lane tests):
  - `test_per_band_mae_ex_bl_matches_golden` — recompute per-band-per-
    predictor MAE in-process from the in-tree fixture; assert against
    frozen golden within ±0.001 s.
  - `test_per_band_mae_golden_schema_invariant` — schema-validate the
    golden JSON (keys, lengths, Building_Lobby in exclusion list, bands
    match `OCTAVE_BANDS_HZ`, both predictors present).

### Fixtures

- `tests/fixtures/ace_eaton_2016_table_i_measured_rt60.csv` (NEW): factual
  reproduction of the v0.6/v0.7-preserved
  `docs/perf_verification_e2e_2026-05-08.md` measured-T60 column. Used by
  both Scope A and Scope B; default-lane (no env gating).
- `tests/fixtures/golden/per_band_mae_ex_bl_2026-05-09.json` (NEW): frozen
  per-band ex-BL MAE figures rounded to 3 decimal places matching the v0.6
  perf-doc display precision.

### Documentation

- `docs/adr/0015-lecture-2-ceiling-seat-bracketing.md` (NEW): full
  Status / Date / Predecessor / Decision / Drivers / Alternatives
  considered (5; (a)..(e)) / Why chosen / Consequences / Reverse-trigger /
  References sections. Records the v0.8 null verdict explicitly.
- `docs/adr/0014-building-lobby-coupled-space-exclusion.md`: References
  cross-ref appended (one line) pointing forward to ADR 0015. Body
  byte-equal to v0.7.
- `docs/perf_verification_lecture2_bracket_2026-05-09.md` (NEW;
  auto-generated by the Scope-A test #5; checked in deterministic).
- `docs/perf_verification_e2e_2026-05-08.md`: byte-equal to v0.7
  (preserved as the v0.6/v0.7 numerical-baseline reference).

### Bookkeeping

- `.omc/plans/decisions.md`: D19 appended (D14..D18 bodies untouched).
- `.omc/plans/open-questions.md`: new "v0.8-design — 2026-05-09" section
  with OQ-11 (v0.9 ratification prerequisites + V4 bounding-case reading).
  D14..D18 invariants reaffirmed.
- `pyproject.toml`, `roomestim/__init__.py`: 0.7.0 → 0.8.0.
  `__schema_version__` stays `"0.1-draft"` (D8 not satisfied; A10 lab
  capture has not shipped).

---

## v0.8 numerical verdict — null

Per `docs/perf_verification_lecture2_bracket_2026-05-09.md` §1 + §2 (per
500 Hz Sabine):

| Variant | Sabine (s) | Eyring (s) | Measured (s) | Err Sabine (s) | Err Eyring (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| V0 | 0.435 | 0.374 | 1.343 | -0.908 | -0.969 |
| V1 | 0.743 | 0.682 | 1.343 | -0.600 | -0.661 |
| V2 | 0.322 | 0.272 | 1.343 | -1.021 | -1.071 |
| V3 | 0.464 | 0.414 | 1.343 | -0.879 | -0.929 |

V3 acceptance verdict — **NULL**:

- Lecture_2 V3 |err| @500 Hz: 0.879 s (threshold 0.500 s) — fails (1).
- Non-Lecture_2 rooms regressing > +0.100 s @500 Hz vs V0 (Sabine):
  Meeting_1 +0.108 s; Meeting_2 +0.142 s — fails (2).

**Single-coefficient ceiling/seat swap is insufficient** to close the
Lecture_2 residual without external regression. v0.9 considers the
broader F4a per-band sensitivity sweep + coupled-space modelling per
ADR 0015 §Reverse-trigger.

---

## Bracketing variant set — methodology summary

- **V0** baseline — library default; byte-equal to v0.7.
- **V1** ceiling swap — Lecture_2 ceiling material → `ceiling_drywall`
  (replacing default `ceiling_acoustic_tile`). Tests F3 hypothesis.
- **V2** lecture_seat α split — unoccupied seat profile (`α₅₀₀ = 0.20`;
  per-band `(0.10, 0.16, 0.20, 0.24, 0.26, 0.26)`) per Beranek 2004 Ch.3
  Table 3.1 / Vorländer 2020 §11. Tests "default seat α₅₀₀ = 0.45 is too
  high" hypothesis.
- **V3** combined V1 + V2.
- **V4** bounding case — ceiling = `wall_concrete` (very low absorption);
  characterising "what would close the gap entirely?". **Env-gated**
  (`ROOMESTIM_BRACKET_V4=1`). Not in default appendix doc.

---

## What stays deferred

- **F4a constrained sensitivity sweep at 2 kHz / 4 kHz**
  (`MaterialAbsorptionBands[wall_painted]` + `[ceiling_drywall]`) — was
  v0.8 candidate #2; deferred to v0.9 with the v0.8 null result as
  sharpened prior.
- **Ratification of any bracketing variant as new default** — requires
  all three of ADR 0015 §Reverse-trigger conditions (acceptance envelope
  + non-regression + independent evidence). v0.8 verdict already fails
  the first two for V3.
- **Coupled-space predictor (Cremer / Müller two-room formula;
  Vorländer 2020 §4.4)** — ADR 0014 §Alternatives considered (b); needs
  per-sub-volume geometry the ACE adapter does not have.
- **F1 walls / ceiling materials**: INDETERMINATE per ADR 0012 (canonical
  evidence path closed).
- **Hard-floor subtype**: needs lab visit / author email.
- **Stage-2 schema flip / A10 lab capture** (D8).
- **Millington-Sette predictor** (ADR 0009 alt-considered).
- **8 kHz octave band** (ADR 0008 reverse criterion unmet).
- **PyPI / submodule** (D11 unchanged).
- **ADR 0016+** — only spawn when a real new commitment ships. v0.8 has
  exactly one (the bracketing methodology, ADR 0015).

---

## Tests

| File | Count | Markers |
| --- | ---: | --- |
| `tests/test_lecture_2_ceiling_seat_bracket.py` | +5 | (none — default lane 104 → 109) |
| `tests/test_per_band_mae_ex_bl_snapshot.py` | +2 | (none — default lane 109 → 111) |
| All other test files | unchanged | — |

Default-lane collected: **111** tests (104 v0.7.0 + 5 v0.8 bracketing + 2
v0.8 snapshot). `ruff check` clean. Gated e2e deselected: 3 (unchanged).

| Step | Command | Expected |
| --- | --- | --- |
| Default lane | `python -m pytest -m "not lab and not e2e" -q` | 111 passed, 3 skipped, 3 deselected |
| Lint | `python -m ruff check` | All checks passed! |
| Bracketing | `python -m pytest tests/test_lecture_2_ceiling_seat_bracket.py -q` | 5 passed |
| Snapshot | `python -m pytest tests/test_per_band_mae_ex_bl_snapshot.py -q` | 2 passed |
| Idempotent perf doc | `python -m pytest tests/test_lecture_2_ceiling_seat_bracket.py::test_bracket_emits_perf_doc_appendix -q && md5sum docs/perf_verification_lecture2_bracket_2026-05-09.md` (run twice) | identical hashes |
| E2E (gated) | `ROOMESTIM_E2E_DATASET_DIR=/tmp/ace_corpus python -m pytest -m e2e -s tests/test_e2e_ace_challenge_rt60.py` | passes; v0.7 numerical baseline byte-equal (overrides=None default path) |

---

## Backwards compatibility

- `_build_room_model(room_id, geom)` — no positional-arg drift; the new
  `overrides=` keyword is additive with default `None`. All v0.7 callers
  (`load_room`, the gated E2E test, the Scope-B snapshot recomputation)
  pass `overrides=None` implicitly and see byte-equal output.
- `_misc_soft_surface_from_furniture(room_id, room_dimensions)` —
  signature + behaviour byte-equal to v0.7. The new sibling
  `_misc_soft_surface_from_furniture_with_alpha(...)` is opt-in only via
  the bracketing override path.
- `MaterialAbsorption`, `MaterialAbsorptionBands`, `MaterialLabel`
  (9 entries), `_FURNITURE_BY_ROOM`, `_PIECE_EQUIVALENT_ABSORPTION_*`
  byte-equal to v0.7.
- `__schema_version__`: `"0.1-draft"` unchanged.
- `sabine_rt60`, `sabine_rt60_per_band`, `eyring_rt60`,
  `eyring_rt60_per_band`: byte-equal to v0.7.
- `roomestim/cli.py` and `roomestim/place/wfs.py`: byte-equal to v0.7.
- All 104 v0.7.0 default-lane tests pass byte-for-byte. v0.6 perf doc at
  `docs/perf_verification_e2e_2026-05-08.md` remains the v0.6/v0.7
  numerical-baseline reference (no v0.8 regeneration).

---

## Schema status

`__schema_version__ = "0.1-draft"` (Stage-1; `additionalProperties: true`).
Stage-2 flip remains deferred per D8. v0.8 is sensitivity-experiment +
snapshot-infrastructure + bookkeeping; no schema change.

---

## SemVer rationale (addressing v0.7 critic)

The v0.7 critic flagged v0.6 / v0.7 as SemVer-loose ("should have been
patches"). v0.8 is a substantive minor bump on the following grounds:

- **New publishable empirical result**: a falsifiable bracketing
  experiment with a documented null verdict, recorded in a deterministic
  appendix doc + ADR 0015 + RELEASE_NOTES (this file). v0.8 ships a
  finding, not just bookkeeping.
- **New residual-coverage infrastructure**: the per-band ex-BL MAE
  snapshot test changes how *future* PRs are evaluated. PRs editing
  predictor / adapter / per-band tables that shift any MAE now require a
  one-line golden update + justification — a behavioural commitment to
  residual coverage, not just test-count growth.
- **New library hook**: `_build_room_model(..., overrides=)` is an
  additive API surface. Default-equivalent path is byte-equal, but the
  channel is now public-private: external sensitivity work can use it
  the same way the v0.8 bracketing harness does.

A patch release (v0.7.1) would not have signaled the new infrastructure +
empirical-experiment commitments to downstream consumers reviewing the
release feed.
