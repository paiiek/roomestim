# roomestim v0.18.1 — CLI el-bound enforcement (Fix 7b closure)

PATCH bump `0.18.0` → `0.18.1`. See ADR 0036 §Status-update-v0.18.1 and ADR
0030 §Status-update-v0.18.1 Item W.

## What v0.18.0 missed

`roomestim edit --del-deg` (and the `nudge_speaker` API) allowed a spherical
elevation delta to push the resulting elevation outside `[-90, 90]°`. For
example, a speaker at `el=80°` nudged by `+20°` produced `el2=100°`, which
silently fed `cos(100°) < 0` into `yaml_speaker_to_cartesian` — flipping the
x/z hemisphere (mirror-reflected position, all-finite, so the existing
`assert_finite` guard passed without error). This is Fix 7b, explicitly deferred
in the v0.18.0 design as a known gap. The web UI was already safe via
`gr.Number(minimum=-90, maximum=90)` input restriction; the gap was CLI-facing.

## What v0.18.1 fixes

- `nudge_speaker` spherical branch now raises `ValueError` when
  `el2 = degrees(el_rad) + del_deg` falls outside `[-90, 90]` (inclusive — el=
  ±90 is physical zenith/nadir and is accepted). Error message:
  `"nudge_speaker: resulting elevation {el2}° outside [-90, 90] (non-physical);
  reduce del_deg or use a Cartesian Δ"`.
- CLI `roomestim edit --del-deg` propagates this `ValueError` through the
  existing `main()` exception handler → `error: ...` to stderr + exit 1. No
  output file is written on rejection.
- Cartesian branch (`--dx/--dy/--dz`) stays unguarded: any finite (x, y, z)
  implies `el = atan2(y, sqrt(x²+z²)) ∈ [-90, 90]` by atan2's range — a guard
  would be dead code (D53 §2.2).
- `--del-deg` help string updated to note the `[-90, 90]` constraint and exit-1
  behaviour.

**Decision (D53):** reject, not clamp. Mirrors the existing `dist <= 0` reject
in `nudge_speaker` (same frame, same class of non-physical input). Clamp
rejected: breaks `dist <= 0` symmetry, silently distorts user intent,
non-idempotent under repeated nudges, and semantically conflicts with the web
`gr.Number` input restriction.

## What stays the same

- ADR 0036 `§A/§D/§E/§F` body byte-equal; `§B/§C` nudge policy
  enforcement-tightened (no new policy surface).
- ADR 0030 `§A–§E` predictor cascade byte-equal (placement editing does not
  touch the RT60 prediction path).
- `PlacedSpeaker` / `PlacementResult` frozen-respecting (all edits via
  `dataclasses.replace`).
- `write_layout_yaml` 5-step order, typed raises, and byte output unchanged.
- `read_placement_yaml` aim-direction restoration (D50) unchanged.
- `__schema_version__ = "0.2-draft"` unchanged (D52).
- Web lane byte-equal: `roomestim_web.__version__` stays `0.15-web.0`; no web
  file is touched (`git diff 5e8c436 -- roomestim_web/` = 0 bytes). HF Spaces
  redeployment not triggered.

## Test count

| Lane | v0.18.0 | v0.18.1 | Δ |
|---|---|---|---|
| default (`-m "not lab and not web"`) | 260 passed | 264 passed | +4 |
| web (`tests/web/`) | 70 passed | 70 passed | 0 |

Counts are `passed` on the canonical interpreter (`/home/seung/miniforge3/bin/python`,
6 default-lane / 1 web-lane skips). Skip counts vary across environments by
optional-dep availability (gradio/fsspec, `pxr`, `SPATIAL_ENGINE_BUILD_DIR`,
E2E dataset), so collected totals differ from passed totals; the `+4` delta is
the new-test count and is environment-invariant.

New cases: `test_nudge_speaker_el_above_90_raises`,
`test_nudge_speaker_el_below_neg90_raises`,
`test_nudge_speaker_cartesian_no_el_guard` (all in
`tests/test_edit_placement.py`), plus `test_cli_edit_el_out_of_range_exit_1`
(in `tests/test_cli_edit.py`). Existing `test_nudge_speaker_spherical` extended
in-place with el=90 exact-boundary acceptance check (no new test function).

## Known gaps (v0.19+ pickup)

- **Candidate A** — web 3D speaker click accuracy (Plotly marker size + click→
  customdata cross-environment support). v0.18.1 DEFER → v0.19 cadence (D26 —
  not indefinite; next release is the hard re-evaluation point).
- **Candidate B** — `roomestim edit` diff warning-header filtering (cosmetic;
  v0.18.0 already mitigated via same-validate-mode comparison). v0.18.1 DEFER
  → v0.19 cadence.
- ADR 0030 has reached ~410 lines; v0.19 should evaluate splitting
  `§Status-update` history into a separate `docs/adr/0030-history.md`
  (triggered per v0.18 design §Risk table — 400-line threshold passed).
- OQ-36 (room.yaml schema downgrade flag), OQ-37 (notes round-trip), OQ-38
  (target_algorithm full round-trip / DBAP·AMBISONICS label), ADR 0036 §G
  reverse-criteria — all unchanged from v0.18.0.

## Tag

Local-only. The user tags/commits separately.
