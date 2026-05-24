# roomestim v0.18.3 — writer float normalization (D56; dogfood edit-churn fix)

PATCH bump `0.18.2` → `0.18.3`. See ADR 0036 §Status-update-v0.18.3 and ADR
0030 §Status-update-v0.18.3 Item Y.

## What v0.18.0 overclaimed

`RELEASE_NOTES_v0.18.0.md` lines 57–58 stated:

> "The float drift (e.g. `az_deg: -90.00000000000001`) does not affect editing
> UX, which relies on Level 1 structural equivalence."

**This was an overclaim.** Dogfooding at HEAD `aae5514` (v0.18.2) disproved it:
a no-op `edit --speaker 0 --daz 0` on the n8 VBAP ring produced a non-empty
unified diff touching an UNRELATED speaker:

```diff
-  x_aim_az_deg: 44.99999999999999      ← speaker 6, NOT speaker 0
+  x_aim_az_deg: 45.0
```

The spurious diff IS visible editing UX. Per D22 audit-trail-discipline, the
shipped v0.18.0 release notes are NOT retroactively edited; the correction is
recorded here and in ADR 0036 §Status-update-v0.18.3.

## What v0.18.2 left open

The float drift issue was known at v0.18.0 but incorrectly assessed as
UX-invisible. The v0.18.0 text claimed structural equivalence was sufficient;
dogfooding showed the unified diff shown to the user was the headline UX and
dirty floats contaminated it.

## What v0.18.3 fixes

### D56 — writer float normalization (`roomestim/export/layout_yaml.py`)

`_placed_speaker_to_dict` now wraps every emitted numeric degree/distance field
in `_round9(x) = round(x, 9)` as the **last step at emit time**:

- Per-speaker: `az_deg`, `el_deg`, `dist_m`, `x_aim_az_deg`, `x_aim_el_deg`
- Top-level (WFS only): `x_wfs_f_alias_hz`

Because place-write and edit-write traverse the same `placement_to_dict` path,
identical structural input → byte-identical output → a zero-magnitude edit now
produces an **empty diff** (the defect is gone).

**Precision (N=9):** position error injected ≤ `2·sin(5e-10°)` ≈ **1.7e-11 m**
for dist ≤ 2 m — two orders of magnitude inside the D50 Level-1 ≤1e-9 structural
contract. `round(-0.0, 9) == -0.0` is preserved (no spurious churn on
`x_aim_el_deg: -0.0` lines).

Specific dirty-float collapses confirmed at N=9:
`-135.00000000000003` → `-135.0`, `-90.00000000000001` → `-90.0`,
`-45.000000000000014` → `-45.0`, `44.99999999999999` → `45.0`,
`89.99999999999999` → `90.0`, `-7.016709298534876e-15` → `-0.0`.

### Golden fixture regenerated

`tests/fixtures/golden/place_vbap_ring_n8_default.yaml` — dirty floats replaced
with clean values. SHA256: `2caea92b…` → `3b9b0dc760b9b417c8daa5cbf4ef895bee214364af93d18cb57f36e94fcc35ac`.
`.PROVENANCE` updated with new `golden_sha256` and provenance note. The
`pre_edit_source_sha256` is unchanged (placement code path unchanged; only
serialization rounds).

### 3 fix-lock regression gates added

Added to `tests/test_layout_round_trip.py`:

- **G10** `test_noop_edit_empty_diff_non_axis_aligned` — the dogfood defect as
  a permanent guard: `edit --daz 0` on n8 ring → `in_path.read_bytes() ==
  out_path.read_bytes()`.
- **G11** `test_place_output_has_no_dirty_floats` — every emitted float leaf in
  the n8 ring YAML `== round(v, 9)` (non-vacuous: parses the written YAML).
- **G12** `test_idempotent_non_axis_aligned_rewrite_byte_equal` — write→read→write
  is a single-iteration byte-equal fixed point on the n8 ring (was NOT before D56).

## What stays the same

| Item | Value |
|---|---|
| `roomestim_web.__version__` | `0.15-web.0` (web byte-equal — core-only change) |
| `__schema_version__` | `0.2-draft` (no new Object/RoomModel field) |
| RT60 negative control | `1.9190766987173207` (acoustic path untouched) |
| ADR 0009 ISM ≥ Eyring invariant | Unaffected |
| ADR 0030 predictor cascade §A–§E | Byte-equal |
| D50 Level-1 ≤1e-9 structural contract | Preserved (N=9 error ≪ 1e-9) |
| `layout.yaml` format / engine schema | Unchanged (`version: '1.0'`; `geometry_schema.json` 불변) |
| All prior §Status-update blocks (D22) | Byte-equal above the new §Status-update-v0.18.3 sections |

## Known gaps (unchanged from v0.18.2)

- OQ-30 per-wall α decomposition (v0.20+ or trigger-gated)
- OQ-23 polygon ISM non-shoebox
- OQ-37 `notes` round-trip (requires engine `x_notes` extension)
- OQ-38 DBAP/AMBISONICS label collapse (Level 1 design decision)
- OQ-39 ADR 0030 §Status-update split (deferred v0.21)
- OQ-33 non-RoomPlan auto object detection (v0.20 hard wall)
- D55 CLI `add-object` subcommand (OUT / user-gated)

## Migration note

No migration required. The only user-visible change is that `roomestim place`
and `roomestim edit` now emit clean floats in `layout.yaml`. Existing dirty-float
`layout.yaml` files from v0.18.x can still be read by `read_placement_yaml` —
the reader is unchanged; the fix is write-only. On first re-write the floats
will normalize (the clean values are within Level-1 tolerance of the originals).

## Tag note

Local-only PATCH tag (no PyPI release). `git diff aae5514 -- roomestim_web/`
= 0 bytes (web byte-equal confirmed). Default-lane test count: 268 → 271
(+3 fix-lock gates G10/G11/G12). Web lane: 70 passed / 1 skipped (unchanged).
