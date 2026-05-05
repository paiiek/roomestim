# RELEASE NOTES — roomestim v0.2.0 + v0.3.0

v0.2 records the distribution-model deferral and proposes room_schema.json cross-repo.
v0.3 adds opt-in octave-band absorption (6 bands, Vorländer-class typical coefficients)
and an ACE Challenge E2E adapter for RT60 characterisation. Stage-2 schema flip and
physical lab capture remain post-autopilot human-gated per D8.

---

## v0.2 (distribution + cross-repo)

- **ADR 0007** (`docs/adr/0007-distribution-model.md`): records the D1 distribution-model
  decision as DEFERRED. roomestim remains a standalone git repo at v0.2. Neither D1 reverse
  criterion (engine team vendoring request; CI cost > 1 day/month) has fired in the 1-day
  window since v0.1.1. Re-evaluate at v0.3 or after first cross-repo PR exchange.

- **Cross-repo PR draft** (`.omc/autopilot/cross-repo-pr-room-schema.md`): markdown-only
  proposal to adopt `proto/room_schema.json` verbatim as `spatial_engine/proto/room_schema.json`.
  Opening the actual PR against spatial_engine is human-gated (OD-10). The draft inlines the
  full v0.3 schema and pins its SHA256.

- **D11** added to `.omc/plans/decisions.md` (distribution-model deferral rationale).

- No production code changes. All 63 v0.1.1 default-lane tests pass byte-for-byte.

---

## v0.3 (octave-band absorption)

- **Schema extension** (`proto/room_schema.json`, `proto/room_schema.draft.json`): OPTIONAL
  `absorption` block per surface with 6 octave-band coefficients (a125, a250, a500, a1000,
  a2000, a4000). `absorption_500hz` remains REQUIRED. Backwards-compatible: v0.1.1 YAML
  files validate cleanly against v0.3 schema.

- **MaterialAbsorptionBands** (`roomestim/model.py`): 6-band absorption table for all 8
  MaterialLabel values. Representative Vorländer-class coefficients. Band index 2 (a500) equals
  the legacy MaterialAbsorption scalar (enforced by `test_band_a500_matches_legacy_scalar`).

- **OCTAVE_BANDS_HZ** (`roomestim/model.py`): `(125, 250, 500, 1000, 2000, 4000)`.

- **sabine_rt60_per_band()** (`roomestim/reconstruct/materials.py`): per-band Sabine RT60
  estimate. Same ValueError raise on zero absorption per band. `sabine_rt60()` unchanged
  byte-for-byte (legacy golden preserved).

- **SABINE_REFERENCE_SHOEBOX_RT60_PER_BAND_S**: analytical per-band reference constant
  for the 5×4×2.8 m synthetic shoebox.

- **Reader/writer** (`roomestim/io/room_yaml_reader.py`, `roomestim/export/room_yaml.py`):
  reader accepts optional `absorption` block (absorption_bands=None when absent); writer
  emits block only when `surface.absorption_bands is not None`. Default: None → byte-identical
  to v0.1.1 (A12 preserved).

- **CLI** (`roomestim/cli.py`): `--octave-band` flag on `ingest`/`run` subcommands. Default OFF.

- **Adapters** (`roomestim/adapters/roomplan.py`, `polycam.py`, `roomestim/reconstruct/walls.py`):
  accept `octave_band: bool = False`; when True, populate `absorption_bands`.

- **ADR 0008** (`docs/adr/0008-octave-band-absorption.md`): rationale for 6-band extension.

- **D12** added to `.omc/plans/decisions.md` (octave-band schema extension).

---

## E2E verification (ACE Challenge adapter, gated)

- **Adapter** (`roomestim/adapters/ace_challenge.py`): reads per-band T60 from user-supplied
  CSVs (`ace_corpus_t60.csv`, `ace_corpus_t60_500hz.csv`) and constructs synthetic RoomModel
  objects from published ACE Challenge room geometry (7 rooms, Imperial College London).
  Raises FileNotFoundError with explicit message if CSVs are missing — no hardcoded T60 values
  (honesty principle, Risk R-C).

- **Gated E2E test** (`tests/test_e2e_ace_challenge_rt60.py`): markers `@pytest.mark.e2e` +
  `@pytest.mark.network`, gated by `ROOMESTIM_E2E_DATASET_DIR` env var. Characterisation only —
  no magnitude threshold asserted (same framing as v0.1.1 DBAP-noise test).

- **Sample fixture** (`tests/fixtures/ace_challenge_sample/`): PLACEHOLDER CSV values for
  Office_1 and Meeting_1. NOT real ACE measurements. Used by default-lane unit tests.

- **Report**: `docs/perf_verification_e2e_2026-05-06.md` written by the gated test run.

---

## Tests added

| File | Count | Markers |
| --- | ---: | --- |
| `tests/test_room_acoustics_octave.py` | 6 | (none — default lane) |
| `tests/test_schema_octave_band_compat.py` | 4 | (none — default lane) |
| `tests/test_e2e_ace_challenge_rt60.py` | 1 gated + 2 unit | `e2e`, `network` (gated); none (unit) |

Default-lane collected: **75** tests (63 v0.1.1 + 10 v0.3 + 2 adapter unit tests).

---

## Backwards compatibility

- `absorption_500hz` remains REQUIRED in schema — no v0.1.1 YAML file breaks.
- `sabine_rt60()` signature and return value unchanged (frozen golden test).
- `--octave-band` flag default OFF → `roomestim ingest/run` output byte-identical to v0.1.1 (A12).
- All 63 v0.1.1 default-lane tests pass with zero changes.

---

## What stays deferred

- **D2 Stage-2 schema flip**: `__schema_version__` stays `"0.1-draft"` until A10 lab capture (D8).
- **A10 physical lab capture**: post-autopilot human session.
- **A2/A15 C++ harness re-enable**: D10 — engine v0.2 work.
- **PyPI publish / submodule migration**: ADR 0007 DEFERRED; re-evaluate at v0.3 or first cross-repo PR round.
- **8 kHz octave band**: v0.4 if engine reverb integration demands it.
- **RT60 model upgrade** (Eyring, Fitzroy, Arau-Puchades): v0.4+.

---

## Known limitations

- `MaterialAbsorptionBands` values are representative Vorländer-class coefficients, not verbatim
  Appx A rows. Each row carries an honesty marker in the source; UNKNOWN is flat at 0.10 (synthetic).
- ACE Challenge Building Lobby has coupled spaces (café/stairwell) — Sabine model underperforms
  in non-diffuse coupled geometries. Treat as a stress test, not a validation data point.
- Per-octave-band Sabine assumes a diffuse field; real rooms violate this at low frequencies
  and in heavily-absorbed rooms (Vorländer 2020 §4).
