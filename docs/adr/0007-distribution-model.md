# ADR 0007 — Distribution model for roomestim (DEFERRED)

- **Status**: Accepted (v0.2; recorded as DEFERRAL)
- **Date**: 2026-05-06
- **Cross-ref**: design plan §11.3, decisions D1, D11; v0.1.1 closeout §7 (a)/(c).

## Context

D1 (`.omc/plans/decisions.md`) deferred the submodule-vs-PyPI choice to v0.2 ADR.
v0.2 ships ~1 day after v0.1.1 (cd78c0d, 2026-05-05). Neither D1 reverse criterion has fired:

- (i) Engine team has not requested vendoring.
- (ii) CI maintenance cost since v0.1 is < 1 day/month (no incidents in the 1-day window).

Three viable distribution paths remain:

- (a) Standalone git repo — current state since v0.1
- (b) Git submodule under `spatial_engine/third_party/roomestim/`
- (c) PyPI publish under name `roomestim`

## Decision

**DEFER** the choice. v0.2 ships as standalone (option (a)), unchanged from v0.1.
ADR 0007 records the decision context and re-evaluation criteria.

## Drivers (evidence as of 2026-05-06)

1. **Time elapsed since v0.1.1**: ~1 day. No reverse-criterion signal possible.
2. **Cross-repo PR rounds since v0.1.1**: 0 (the cross-repo PR for room_schema.json is drafted
   in `.omc/autopilot/cross-repo-pr-room-schema.md` but NOT yet opened against spatial_engine).
3. **Real-world room.yaml count produced since v0.1.1**: 0 (D2/D8 lab capture is post-autopilot).
4. **CI maintenance hours since v0.1.1**: ~0 (no incidents in 1-day window).
5. **Sibling-repo precedent**: vid2spatial, claude_text2traj are standalone — consistent with (a).

## Alternatives considered

- **(b) Submodule**: rejected for now — requires engine-team coordination AND a tested branch
  hygiene process. No evidence yet that the cross-repo coordination tax is high enough to justify it.
- **(c) PyPI**: rejected for now — adds release-process complexity (semver discipline, name claim,
  packaging-test CI) for no measured benefit in the 1-day window.

## Why chosen (defer)

The decision space is fundamentally evidence-limited at v0.2. Forcing a choice would either
fabricate rationale or pre-commit to a structure that the next 30 days of usage may invalidate.
Mirrors v0.1.1 closeout Critic M1 honesty principle: "do not promote audit/deferral to closure."

## Consequences

- (+) No migration cost at v0.2.
- (−) Ambiguity remains for downstream consumers; resolved at v0.3 or sooner if a reverse trigger fires.
- Migration plan if reverted to (b) or (c): a future ADR 0007a will spec the migration mechanics.

## Reverse criteria (per D1)

- Engine team explicitly requests vendoring → flip to (b).
- CI maintenance cost > 1 day/month over a 30-day window → flip to (b).
- ≥1 external consumer requests `pip install roomestim` → consider (c) — but only if (b) is also evaluated and rejected.

## Follow-ups

- Cross-repo PR for room_schema.json: `.omc/autopilot/cross-repo-pr-room-schema.md`. Engine-team review of the schema is INDEPENDENT of this distribution decision.
- Re-evaluate at v0.3 ship or after first cross-repo PR exchange, whichever comes first.
- D11 entry in decisions.md records this deferral.

## Status-update — packaging is now PyPI-*ready* (NOT published) — Candidate A / D98 (2026-06-08)

The standalone-vs-submodule-vs-PyPI **decision is unchanged**: still DEFERRED to option (a)
standalone. None of the reverse criteria above has fired (no engine-team vendoring request, no
external `pip install roomestim` request, CI cost unchanged). This update records only that the
*packaging* is now machine-independent and install-verified — it does **NOT** record a publish.

**What changed (machine-independence fix).** `roomestim/export/layout_yaml.py` previously hardcoded
a machine-specific default engine-schema path (`/home/.../spatial_engine/proto/geometry_schema.json`),
which made "engine validation with no env and no CLI flag" silently succeed only on the original dev
machine and fail/mislead everywhere else. That literal is **removed**. `_engine_schema_path()` now
resolves the engine geometry schema from `SPATIAL_ENGINE_REPO_DIR` only (the engine schema is read at
write time, **never vendored** — see `layout_yaml.py` module docstring), and with no env + no
`--validate-engine` it returns `None` so the existing descriptive `FileNotFoundError` fires (naming
`SPATIAL_ENGINE_REPO_DIR`, `--validate-engine`, `--no-engine-validation`). Engine validation is opt-in
(ADR 0033 §C: `--no-engine-validation` skips cleanly), and the `CLI > ENV` precedence is preserved.
Output is byte-equal to before when env/CLI points at a real schema (verified in-gate). This is a
cross-machine **bug fix**, not a behavior regression.

**Packaging-readiness PROOF (isolated venv, captured 2026-06-08).** `python -m build --wheel` →
`pip install dist/roomestim-0.29.0-py3-none-any.whl` into a fresh venv → from a neutral cwd:
`roomestim --help` prints usage; `import roomestim` succeeds, is **torch-free**
(`'torch' not in sys.modules`), and resolves to the installed `site-packages/roomestim`, reporting
`__version__ == 0.29.0`. The `[vision]` torch deps stay behind their opt-in extra (core import is
torch-free). This is what "PyPI-ready" means here: **builds + installs cleanly + console-script runs +
machine-independent** — NOT a registry upload.

**Honest limitation (known follow-up, NOT claimed fixed).** The room.yaml validation schemas live at
the **repo-root** `proto/*.json` and are resolved at runtime via `_proto_dir()` =
`Path(__file__).parents[2] / "proto"` (room_yaml.py / room_yaml_reader.py). In an installed wheel this
resolves to a nonexistent `site-packages/proto`, and the wheel currently ships **zero** `proto/*.json`
(the `[tool.setuptools.package-data] roomestim = ["proto/*.json", ...]` glob targets a nonexistent
in-package `roomestim/proto/`). Therefore an installed copy can build + run `--help` + emit a
layout.yaml with `--no-engine-validation`, but **cannot yet self-validate/emit room.yaml** unless run
from a repo checkout. The honest fix is a small bundling refactor (relocate `proto/` into
`roomestim/proto/` and point `_proto_dir()` at the in-package location so the existing package-data
glob ships them), which touches runtime + golden round-trip surface and is therefore **out of
Candidate A's scope** (this cycle's bound was the engine-path decouple + a pyproject-only packaging
fix). Recorded here so "PyPI-ready" is not overclaimed: the wheel builds/installs/runs, but full
room.yaml self-validation in an installed copy is a tracked follow-up.

**Reverse criteria for an actual PyPI publish remain UNCHANGED** (see above). Stay packaging-ready; do
not upload.
