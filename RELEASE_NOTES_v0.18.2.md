# roomestim v0.18.2 — OQ-33 D26 decision (doc-only re-defer + regression lock)

PATCH bump `0.18.1` → `0.18.2`. See ADR 0034 §Status-update-v0.18.2 and ADR
0030 §Status-update-v0.18.2 Item X.

## What v0.18.1 left open

OQ-33 ("Mesh / Polycam / ACEChallenge adapter object 자동 인식") was deferred
from v0.17 with a D26 forced-decision cadence of "v0.19 까지 결정 강제." The
manual-annotation resolution candidate (candidate 3) was described as a *future*
option in the original OQ text — but had in fact already shipped in v0.17
(`evolve_room_add_object`, web `object_add.py`, predictor fold). The out-of-date
premise needed a formal correction record and a D26-compliant decision on the two
remaining high-risk auto-detection candidates.

## What v0.18.2 does

### Decision D54 — OQ-33 re-defer (honest re-scoping)

- **Manual-annotation path declared DONE** (shipped v0.17): core
  `evolve_room_add_object` / `evolve_room_remove_object` (`roomestim/edit.py`) +
  web Object Add Mode (`roomestim_web/object_add.py`) + predictor
  `_objects_to_surfaces` / `_objects_to_wall_alpha_overrides` fold.
- **OQ-33 residual narrowed** to "non-RoomPlan adapter (Mesh/ACE) 무인 자동 추출"
  only. `MeshAdapter` and `ACEChallengeAdapter` retain `objects=[]` placeholder.
- **Auto-detection candidates re-deferred to v0.20 (hard wall)**:
  - Candidate 1 (Polycam Pro segmentation API): proprietary, Linux-CI-unbuildable,
    no fixture, 0 user reports → premature.
  - Candidate 2 (bbox clustering + geometric heuristic): greenfield "미안정", no
    ground-truth fixture → ships unvalidated heuristics, violates D26 YAGNI.
- **Both D26 triggers unmet**: non-RoomPlan auto-extraction requests = 0;
  mesh-only object-GT fixtures = 0.
- **v0.20 is a hard wall**: re-re-deferral forbidden. If no trigger fires by
  v0.20, OQ-33 remainder is formally closed as WONTFIX. Reverse-criterion (D54):
  (a) ≥1 auto-extraction user request, OR (b) mesh-only object-GT fixture
  introduced, OR (c) Polycam Linux-buildable segmentation export published.

### Decision D55 — CLI `add-object` deferred (OUT)

Optional CLI parity subcommand `roomestim add-object` (D55) is OUT for this
cycle — user did not confirm. Web manual-annotation is already available. No
CLI code added.

### OQ-39 — ADR 0030 §Status-update split deferred

ADR 0030 is ~430 lines with 8 §Status-update blocks. Splitting during a
doc-only re-defer cycle adds churn with no functional gain and risks the
append-only audit-trail discipline (D22). Deferred to v0.21+; trigger: file >
~600 lines OR documented navigation-pain report ≥ 1.

### Regression-lock test (Phase 2)

`tests/test_oq33_residual_lock.py` (NEW, 4 test cases) locks:
- `MeshAdapter().parse(<minimal.obj>).objects == []` — adapter placeholder
  invariant; fails immediately if auto-detection is silently added.
- `ACEChallengeAdapter` still returns `objects==[]`.
- `evolve_room_add_object(room, col)` → `write_room_yaml` → `read_room_yaml`
  preserves object (kind, material, width_m).
- `evolve_room_remove_object` round-trip also survives.

## What stays the same

- ADR 0030 `§A–§E` predictor cascade byte-equal — doc-only cycle; no
  acoustic/schema code touched.
- `RoomModel` frozen (all mutation via `dataclasses.replace`).
- `PlacedSpeaker` / `PlacementResult` unchanged.
- ADR 0009 invariant (`ism_rt60 ≥ eyring_rt60 − 1e-6`) — D47 regression lock
  (150 instances) GREEN; predictor untouched.
- `__schema_version__ = "0.2-draft"` unchanged (D52 — no new Object field).
- Web lane byte-equal: `roomestim_web.__version__` stays `0.15-web.0`; no web
  file touched.
- `MeshAdapter` / `ACEChallengeAdapter` `objects=[]` behavior unchanged (that
  IS the point — the test now locks it).

## Known gaps (v0.20 / v0.21+)

- **OQ-33 residual** — adapter auto-detection (candidate 1 Polycam Pro API /
  candidate 2 bbox clustering): v0.20 hard wall. Reverse-criterion in D54.
- **OQ-39** — ADR 0030 §Status-update split: v0.21+ (trigger: >600 lines or
  navigation-pain report ≥ 1).
- **OQ-34** — cylinder/arch column: v0.19+ polygonal approximation policy.
- **OQ-35** — USDZ/gLTF acoustic metadata standard: v0.19+ (Apple RoomPlan
  acoustic API).
- **OQ-36** — `room.yaml` downgrade export flag (`--schema 0.1`): triggered by
  external consumer fail report (currently 0).
- **OQ-37** — `PlacedSpeaker.notes` round-trip: v0.19+ (engine schema coordination).
- **OQ-38** — `target_algorithm` DBAP/AMBISONICS round-trip: v0.19+.
- **D55** — CLI `roomestim add-object`: user-gated OUT; revisit on explicit request.

## Test counts

| Lane | v0.18.1 baseline | v0.18.2 |
|------|-----------------|---------|
| default (`-m 'not lab and not web'`) | ~264 | ~264 + 4 new |
| web (`tests/web/`) | ~70 | ~70 (unchanged) |

(Exact counts may vary by ±3 due to optional-dep skip drift; see plan §5 baseline
note.)

## §Tag local-only

This release is tagged and released locally (no PyPI). Web lane byte-equal
confirmed: `git diff 2ad9ece -- roomestim_web/` = 0 bytes.
