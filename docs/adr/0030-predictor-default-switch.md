# ADR 0030 — Predictor-default switch: Sabine → ISM-preferred (v0.15.0)

**Date**: 2026-05-17 evening
**Status**: ACCEPTED
**Deciders**: planner (v0.15-design.md), executor (this commit)
**Drivers**: ADR 0028 §Reverse-criterion item 2 (Office_1 + conference ISM/Sabine
both > 1.15 signature robustness confirmed), D26 forbidden-indefinite-deferral
clause, D27 hard-wall cadence (Item D switch decision was DEFERRED at v0.14.0
WITH a v0.15+ MUST-land trigger).

---

## Context

ADR 0028 (v0.14.0, "Hard-wall closure + ISM adoption") landed the ISM library
(`roomestim/reconstruct/image_source.py`) and characterised the Item B (e+)
disagreement signature:

- **Conference (glass-heavy)**: ISM/Sabine = 5.0537 → Sabine under-estimates by 5×.
- **Office_1 (glass-heavy)**: ISM/Sabine = 2.0059 → Sabine under-estimates by 2×.

Both ratios > 1.15 across ≥ 2 rooms → the predictor-default switch decision
(Item D) was DEFERRED at v0.14.0 but with a hard v0.15+ trigger per D26
forbidden-indefinite-deferral clause. Failing to land it at v0.15+ would have
turned D26 into a dead letter.

The default predictor in v0.14.0 surfaces through the web `AcousticReport` /
`build_rt60_bar_chart` annotation, which reads "Sabine 500 Hz = X.XX s" as the
headline number. End users perceive this as the recommended estimate.

---

## Decision

### A. Cascade order at v0.15.0

`roomestim.reconstruct.predict_rt60_default(room, surface_areas_by_material)`:

1. **ISM branch** — if `is_rectilinear_shoebox(room)` AND `prefer_ism=True`
   (default): call `image_source_rt60(...)` on the inferred shoebox
   `(L, W, H)` + 6-tuple `surface_areas` + 6-tuple `absorption_coeffs`
   (wall α is area-weighted average across `kind == "wall"` surfaces; per-wall
   α decomposition is OQ-30 NEW).
2. **Eyring fallback** — else (non-shoebox OR `prefer_ism=False`): call
   `eyring_rt60(volume_m3, surface_areas_by_material)`.
3. **Sabine** is no longer the default; it remains available as a side-by-side
   bar (chart) and JSON field (`sabine_*`) for backwards compatibility and
   comparison.

### B. AcousticReport surface

`roomestim_web.report.AcousticReport` v0.15.0 adds 4 fields:

- `default_rt60_500hz_s: float` — headline number.
- `default_rt60_per_band_s: dict[int, float]` — per-band variant.
- `default_predictor_name: Literal["image_source", "eyring"]` — which branch fired.
- `default_predictor_rationale: str` — human-readable reason.

`to_json_dict()` exposes all 4 under the same keys (string-keyed `per_band` dict
per existing convention).

### C. Chart annotation

`build_rt60_bar_chart`:

- Headline horizontal reference line uses `default_rt60_500hz_s` and annotates
  either "ISM (default) 500 Hz = X.XX s" or "Eyring (default fallback) 500 Hz =
  X.XX s" depending on which branch fired.
- When ISM fired (shoebox), an additional green bar series ("ISM (default)") is
  added per band alongside the existing Sabine + Eyring bars.

### D. Backwards compatibility

- `sabine_rt60` / `eyring_rt60` core API: byte-equal, unchanged.
- `AcousticReport.sabine_*` / `eyring_*` fields: byte-equal, unchanged.
- Callers that depended on the v0.14.0 Sabine-headline behavior should now
  query `default_rt60_500hz_s` instead of `sabine_rt60_500hz_s`.

### E. Error handling

`compute_acoustic_report()` wraps the `predict_rt60_default*` calls in
`try/except` and falls back to the Eyring 500 Hz value (already computed) on
any exception, recording the failure in the `default_predictor_rationale`. This
prevents a degenerate ISM input (e.g., zero-absorption shoebox) from breaking
the whole acoustic report tab.

---

## Consequences

- (+) Glass-heavy rooms (offices, conference rooms) now show a default RT60
  consistent with measured-room characterisation per ADR 0028.
- (+) D26 forbidden-indefinite-deferral clause SATISFIED (predictor-default
  switch landed within the v0.15+ trigger window).
- (+) Sabine + Eyring still visible side-by-side — users can see the
  disagreement when ISM > Sabine.
- (−) Non-shoebox rooms (≠4 floor vertices or off-axis) silently route to
  Eyring without ISM treatment. Polygon ISM is OQ-23 (deferred at v0.14.0).
- (−) Wall-α area-weighting is a simplification when walls have heterogeneous
  materials (e.g., one glass wall + three painted walls). OQ-30 NEW tracks
  per-wall-α decomposition (would require ISM API change to accept full
  area+α list, not just 6-tuple).

## Reverse-criterion

1. **ISM produces inflated RT60 on a low-α shoebox vs Sabine reference** —
   tighten the Sabine/Eyring ≤ ISM invariant check (ADR 0009) and bisect.
   Successor ADR 0031.
2. **User feedback flags "ISM default is too high"** — add a UI toggle
   exposing `prefer_ism` (currently API-only). If feedback persists across
   ≥ 3 rooms, supersede ADR 0030 with ADR 0031.
3. **Polygon ISM lands (OQ-23 closure)** — extend `predict_rt60_default` to
   use polygon ISM for non-shoebox rooms; promote ADR 0030 §A item 2
   ("Eyring fallback") to "polygon ISM fallback". Append §Status-update.

## References

- ADR 0009 — D9 Eyring parallel predictor (runtime invariant pattern source).
- ADR 0018 — substitute-disagreement record / honesty discipline.
- ADR 0021 — Sabine-shoebox residual study (v0.12.0) + §Status-update-2026-05-16
  conference + Office_1 ISM ratio characterisation.
- ADR 0028 — D27 hard-wall closure + ISM adoption (v0.14.0); §Reverse-criterion
  item 2 is the trigger for ADR 0030.
- D26 — forbidden-indefinite-deferral clause.
- D27 — hard-wall cadence (cycle 3 of D27/D28-P2 schedule).
- D38 NEW — predictor-default cascade policy.
- OQ-30 NEW — per-wall-α decomposition for ISM (mixed-material walls).
- `roomestim/reconstruct/predictor.py` — implementation.
- `roomestim_web/report.py` — surface + chart wiring.
- `tests/test_predict_rt60_default.py` — 9 NEW tests.
- `RELEASE_NOTES_v0.15.0.md` — release notes.

---

## §Status-update history

All 10 §Status-update blocks (in original file order: v0.15.1, v0.15.2,
v0.16, v0.16.1, v0.17, v0.18, v0.18.1, v0.18.4, v0.18.3, v0.18.2 — note the
D22 append-on-top convention put v0.18.4/v0.18.3/v0.18.2 in non-chronological
order) have been relocated to the companion file for navigability (OQ-39 /
D73 closure):

→ [`0030-predictor-default-switch-status-updates.md`](./0030-predictor-default-switch-status-updates.md)

Each block is byte-equal to its pre-split content (no retroactive edits per
D22 audit-trail-discipline). Future §Status-update blocks land in the
companion file, not here.
