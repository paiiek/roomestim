# roomestim v0.22.1 — ADR 0030 split + README schema-marker reconcile

PATCH bump `0.22.0` → `0.22.1`. Doc-only patch + 1-line README fix. No acoustic
path touched (`git diff 66d0f4b -- roomestim/reconstruct/` empty); no schema
change (`__schema_version__` stays `0.2-draft`); no web source touched
(`git diff 66d0f4b -- roomestim_web/` empty; `roomestim_web.__version__` stays
`0.18-web.0`). See ADR 0030 (companion file split landing), ADR 0039
(`docs/adr/0039-adr-status-update-split-mechanism.md`, NEW), D73
(`.omc/plans/decisions.md`), and OQ-39 (CLOSED) (`.omc/plans/open-questions.md`).

## ① ADR 0030 §Status-update split (OQ-39 closure)

`docs/adr/0030-predictor-default-switch.md` had grown to 477 lines with 10
§Status-update blocks (in file order: v0.15.1, v0.15.2, v0.16, v0.16.1, v0.17,
v0.18, v0.18.1, v0.18.4, v0.18.3, v0.18.2 — D22 append-on-top placed v0.18.4
above v0.18.3/v0.18.2) — making §A–§E predictor-cascade decision text hard
to locate during the v0.22.0 security-audit pass. OQ-39 had deferred this
split with explicit triggers (file > ~600 lines OR documented navigation-pain);
trigger (b) fired during v0.22.0; v0.22.1 closes it.

**Mechanism (D73, codified as ADR 0039)**: split-by-section.
- `docs/adr/0030-predictor-default-switch.md` retains §A–§E + §Consequences +
  §Reverse-criterion + §References + a forward-pointer block (~147 lines).
- `docs/adr/0030-predictor-default-switch-status-updates.md` (NEW) holds all
  10 §Status-update blocks, byte-equal to pre-split content (D22 audit-trail-
  discipline preserved — relocation, not retroactive edit).

Outgoing cross-references in other ADRs, decisions.md, source comments, and
RELEASE_NOTES v0.15.0–v0.22.0 continue to resolve correctly (the canonical
filename did not change).

## ② README schema-marker reconcile (D72 honesty-re-review extension)

`README.md:399` was stale since v0.17.0 (`0.1-draft` while ground truth in
`roomestim/__init__.py:4` and `roomestim/model.py:284` had moved to
`0.2-draft` per ADR 0034 §B). v0.22.0 D72 reconciled `sdk_version` in the same
README front-matter but missed this sibling line. v0.22.1 closes the
partial-reconcile gap.

## ③ ADR 0039 NEW — split mechanism meta-ADR

`docs/adr/0039-adr-status-update-split-mechanism.md` codifies the split rule
as a reusable pattern for any future ADR hitting (line > 400) AND (blocks ≥ 6)
AND (documented navigation-pain). Companion-file naming convention,
lint_tense compatibility note, cross-reference compatibility note, and
reverse-criterion (escalate to per-version subdirectory at companion > 800
lines) all captured.

## Verification

Run under canonical miniforge env (`/home/seung/miniforge3/bin/python -m pytest`):

- default: 288 passed / 6 skipped (unchanged — no test added or removed)
- web (`tests/web/`): 82 passed / 1 skipped (unchanged — no web source touched; verifier independently measured 82/1 at HEAD `66d0f4b`, which differs from the v0.22.0 plan / commit-message claim of 79/1 — v0.22.0's D72 honesty re-review added load-bearing tests not reflected in the post-land baseline statement; v0.22.1's verifier corrects the notational drift)
- mypy --strict: 0 errors across 38 files
- ruff: clean
- lint_tense: exit 0 (both ADR 0030 files + ADR 0039 NEW + README in scope)
- RT60 sentinel byte-equal: `1.9190766987173207`

## Versions

- `roomestim.__version__`: `0.22.0` → `0.22.1` (PATCH)
- `roomestim_web.__version__`: `0.18-web.0` (unchanged — D30 byte-equal)
- `__schema_version__`: `0.2-draft` (unchanged)
- `pyproject.toml` version: `0.22.0` → `0.22.1`
