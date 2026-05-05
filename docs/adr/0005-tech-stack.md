# ADR 0005 — Tech stack

- **Status**: Accepted (finalized 2026-05-04)
- **Date**: 2026-05-03
- **Cross-ref**: design plan §2.3 Q8, §9.

## Context

roomestim is Python-only at v0.1 (no pybind11 to spatial_engine yet). Stack must mirror
`claude_text2traj` discipline so the team can context-switch cheaply.

## Decision

**Python ≥3.10, setuptools build, optional-dependency groups, pyproject.toml.** Locked deps:

- Core: `numpy>=1.24`, `pyyaml>=6`, `jsonschema>=4`, `shapely>=2.0`, `scipy>=1.10`,
  `trimesh>=4.0`.
- USDZ parametric (optional): `pyusd` under `[usd]` extra.
- COLMAP (optional, experimental): `pycolmap>=0.6` under `[colmap]` extra.
- Visualization (optional): `matplotlib>=3.7` under `[viz]` extra.
- Dev: `pytest>=7`, `pytest-mock`, `hypothesis>=6`, `ruff>=0.5`, `mypy>=1.8`.

CI: GitHub Actions on Ubuntu 22.04, Python 3.10/3.11/3.12.

## Drivers

1. `shapely` is the de-facto polygon library; avoids reimplementing wall-segment intersection.
2. `trimesh` parses OBJ + GLB out of the box; USDZ via optional `pyusd`.
3. `jsonschema` already used by `claude_text2traj` for the trajectory schema.

## Alternatives

- **Pydantic for validation instead of jsonschema**: rejected. Cross-language schema reuse
  (engine-side C++ loader will validate against the same JSON Schema) is the v0.2 win.
- **`uv` build / lock instead of setuptools**: deferred. Not yet adopted in sibling repos.

## Consequences

- (+) Mirrors `claude_text2traj` — context-switch cost is low.
- (+) Optional-dep groups keep base install cheap.
- (−) USDZ parametric requires `[usd]` extra; CI must cover both `[usd]` installed and not.

## Falsifier

If `pyusd` install friction blocks more than one developer-day in v0.1, switch to a hand-rolled
USDZ parametric parser (USDZ is just a zipped USDA — hand-parsing the JSON sidecar is feasible).

## Follow-ups

- CI workflow at `.github/workflows/ci.yml` (done — P6).
- Evaluate `uv` build / lock for v0.2 once adopted in a sibling repo (deferred per Alternatives above).
- Octave-band absorption coefficients (125 Hz – 8 kHz) for v0.3 reverb integration (cross-ref decisions D7 reversal criteria).
