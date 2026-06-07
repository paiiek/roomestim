# ADR 0027 — Mesh-format generalisation via single MeshAdapter

- **Status**: Accepted (v0.12-web.1)
- **Date**: 2026-05-15b
- **Cross-ref**: D33 (MeshAdapter rename rationale), D6 (convex-hull-of-projection
  deferral), ADR 0024 (web demo separate package; parallel-track boundary),
  OQ-20 (glTF binary byte-equal reproducibility), OQ-21 (PLY no-faces degenerate
  case), `.omc/plans/v0.12-web.1-design.md` §6.

## Status

Accepted (v0.12-web.1).

## Context

v0.12-web.0 shipped a `PolycamAdapter` that accepted only `.obj` files — a name
and scope mismatch from day one, since the class parsed any OBJ mesh (not Polycam
exports exclusively) and HF Spaces users export room scans in a mix of formats:
Polycam (`.usdz` / `.obj`), Reality Capture (`.gltf`), Apple Object Capture (`.ply`),
and Sketchfab (`.glb`). Four new mesh formats were requested without requiring any new
core dependency because `trimesh>=4.0` (already pinned in `pyproject.toml`) natively
loads all four via `trimesh.load(force="mesh")`.

Two surfacing options were available: (i) rename `PolycamAdapter` → `MeshAdapter` and
retain the old name as a deprecated alias; (ii) keep `PolycamAdapter` as-is and add
a new sibling class. Option (i) was chosen (D33).

## Decision

Generalise the OBJ-only `PolycamAdapter` into a single mesh-format-agnostic
`MeshAdapter` (new module `roomestim/adapters/mesh.py`) accepting `.obj`, `.gltf`,
`.glb`, `.ply` via `trimesh.load(force="mesh")`. The convex-hull-of-vertex-projection
geometry, the default `MaterialLabel` triple (`WALL_PAINTED` + `WOOD_FLOOR` +
`CEILING_DRYWALL`), and `RoomModel.schema_version="0.1-draft"` were all preserved
byte-equal across the four mesh formats.

`PolycamAdapter` was retained as a `DeprecationWarning`-emitting subclass alias in
`roomestim/adapters/polycam.py` (D33). `.usdz` continued to raise
`NotImplementedError` (no `[usd]` extra in default CI). `.json` (RoomPlan sidecar)
continued to delegate to `RoomPlanAdapter` directly from `pipeline.py` — the `.json`
route was NOT handed to `MeshAdapter` in order to preserve the byte-equivalence claim
cleanly across the rename.

## Drivers

1. **HF Spaces on-ramp**: users export room scans from Polycam (`.usdz`/`.obj`),
   Reality Capture (`.gltf`), Apple Object Capture (`.ply`), and Sketchfab (`.glb`);
   accepting all four closed the v0.12-web.0 on-ramp gap.
2. **Zero new core dependency**: `trimesh>=4.0` was already pinned and natively loads
   all four formats.
3. **Rename over shim** (D33): the v0.1-era class name `PolycamAdapter` no longer
   matched its actual scope; renaming avoided freezing the misnomer as the canonical
   implementation.
4. **Backward compatibility**: `isinstance(PolycamAdapter(), MeshAdapter)` returned
   `True`; all duck-typing call sites continued to work byte-equal.

## Consequences

- **(+)** Users uploaded `.gltf`, `.glb`, and `.ply` room scans to the Gradio demo
  without any new install step.
- **(+)** `PolycamAdapter` deprecation surfaced in pytest only when a caller invoked
  `.parse()` (one `DeprecationWarning` per location); existing tests passed byte-equal
  because pytest's default capture mode deduped and did not fail on warnings.
- **(−) glTF axis-convention caveat**: `trimesh.load(force="mesh")` flattened
  scene-graph transforms but did NOT correct for source-tool axis conventions (Reality
  Capture: Z-up; Polycam OBJ: Y-up; Apple Object Capture: variable). `MeshAdapter`
  used the convex-hull-of-XY-projection (`vertices[:,0]` + `vertices[:,1]`) for the
  floor polygon and `vertices[:,2]` max−min for ceiling height. For glTF/glb files
  exported with a Z-up root transform, the result was geometrically valid but the
  "floor" and "ceiling" axes were swapped relative to the user's intent. Documented
  as a known caveat in `RELEASE_NOTES_v0.12-web.1.md` § "Known gaps"; OQ-20 broadened
  to cover this case.
- **(−) glTF scene-graph semantic material labels NOT extracted**: `trimesh.load(force="mesh")`
  flattened to a single mesh; only vertex coordinates were used — same caveat as `.obj`
  (D6).
- **(−) Alpha-shape reconstruction (D6) deferred to v0.3**: v0.12-web.1 inherited the
  convex-hull caveat byte-equal across all four mesh formats.
- **(−) PLY no-faces degenerate case (OQ-21)**: if a user uploaded a points-only PLY
  (no triangular faces), `trimesh.load(force="mesh")` returned a `Trimesh` with 0
  faces; the existing `vertices.shape[1] != 3` guard did NOT catch this. Documented
  as a known gap; resolution deferred to v0.12-web.2 on user report.

## §Status-update-v0.18.5 (2026-05-27)

**D62 — internal test-caller migration (D33 intended end-state).** The four
`tests/web/*.py` files that used the deprecated `PolycamAdapter` alias purely
as a generic mesh parser were migrated to the canonical `MeshAdapter`:
`tests/web/test_setup_pdf.py` (import :12, parse :19),
`tests/web/test_acoustic_report.py` (import :9, parse :15),
`tests/web/test_binaural_renderer.py` (import :24, parse :79),
`tests/web/test_3d_viewer.py` (import :11, construct :19). Each parse target
is `tests/fixtures/lab_room.obj` (a `.obj` mesh); the swap is
behavior-preserving (`PolycamAdapter(MeshAdapter)` only adds the
`DeprecationWarning` + a `.json`-delegation branch, neither of which applies
to a `.obj` input). Effect: the four files emit zero `PolycamAdapter`
`DeprecationWarning`s; the alias's intentional warning now fires only from the
contract test `tests/test_adapter_polycam.py` (the desired single canonical
trigger).

The alias is **NOT removed** (D33 reverse-criterion still gates full removal —
full removal is a BREAKING change requiring a successor D-decision and a
"Breaking changes" RELEASE_NOTES callout). The shim docstring's "removal at
v0.14 or later" is noted as stale (we are at v0.18.x); editing it would imply
a removal commitment not made this cycle; it remains as-is pending a future
removal decision. `cli.py` `_get_adapter("polycam")` and the contract test
`tests/test_adapter_polycam.py` are byte-equal (DO-NOT-TOUCH invariants —
see D62 for rationale). New OQ filed: OQ-40 (gradio `col_count` deprecation
noise — a separate, deferred web-lane source). PATCH bump `0.18.4 → 0.18.5`.

## §Status-update-v0.20.0 (2026-05-28)

**D66 — PLY no-faces guard (OQ-21 CLOSED).** A points-only PLY (vertices but no
triangular faces — a degenerate point-cloud export) loads via
`trimesh.load(force="mesh")` as a `Trimesh` with `len(faces)==0`. The existing
`(N, 3)` vertex-shape check does NOT catch this (the array is still 2-D with 3
columns, or `(0, 3)` after trimesh drops unreferenced vertices), so the input
slipped through to the convex-hull-of-projection path, which is undefined for a
point cloud. `MeshAdapter._room_model_from_mesh` now adds a guard right after the
vertex-shape check: `faces = np.asarray(getattr(loaded, "faces", []))` →
`if len(faces) == 0: raise ValueError("MeshAdapter: mesh has 0 faces
(points-only PLY); a surface mesh with triangular faces is required.")`. New
fixture `tests/fixtures/points_only.ply` (vertices only, `element face 0`) +
`tests/test_adapter_mesh.py::test_mesh_adapter_points_only_ply_raises` lock it;
the existing 4-format parse test and the vertex-color PLY test (faces present)
are unaffected. This resolves the v0.12-web.1 "known degenerate case" without
vendoring. The mesh output contract (convex-hull floor, D6) is otherwise
byte-equal. MINOR bump `0.19.0 → 0.20.0` (the no-faces guard adds a new
validation error path for a previously-undefined input).

## Follow-ups

- **OQ-20** — glTF binary (`.glb`) byte-equal reproducibility across trimesh versions.
- **OQ-21** — PLY files with vertex colour but no faces (points-only degenerate case).
  CLOSED v0.20.0 (no-faces guard; D66 / ADR 0027 §Status-update-v0.20.0).

## References

- D33 — `.omc/plans/decisions.md` (MeshAdapter rename rationale; PolycamAdapter
  deprecated subclass alias).
- D6 — `.omc/plans/decisions.md` (convex-hull-of-vertex-projection deferral; floor
  polygon geometry unchanged across all four mesh formats).
- ADR 0024 — `docs/adr/0024-web-demo-separate-package.md` (parallel-track package
  boundary; `roomestim_web/` sibling; preserved byte-equal at v0.12-web.1).
- OQ-20 / OQ-21 — `.omc/plans/open-questions.md` (follow-up open questions).
- `roomestim/adapters/mesh.py` — `MeshAdapter` implementation.
- `roomestim/adapters/polycam.py` — deprecated subclass alias shim.
- `roomestim/adapters/__init__.py` — `MeshAdapter` + `PolycamAdapter` exports.
- `roomestim_web/pipeline.py` — format dispatch (`MESH_SUFFIXES` set; `.json` →
  `RoomPlanAdapter` direct path preserved).
- `tests/test_adapter_mesh.py` — parametrised 4-format + 1-usdz-negative acceptance
  tests.
- `RELEASE_NOTES_v0.12-web.1.md` — v0.12-web.1 release notes (§ "Known gaps").
- `.omc/plans/v0.12-web.1-design.md` §6 — ADR sketch source.

## §Status-update-2026-06-07 (v0.25.3) — up-axis(gravity) 자동 정규화 (measured 경로 P0 정확성 수정; D91)

상용화(B2B AV-인스톨러) 분석 중 measured 경로가 **실 캡처로 미검증**(픽스처 전부 합성 Y-up shoebox)임을 확인,
실 ARKitScenes(iPad LiDAR=RoomPlan 센서 정합) 10 scene 으로 MeshAdapter 를 처음 실행 → **천장 6.5–9.6 m**(실제 ~2.5 m).
근본원인: 어댑터가 **Y-up 하드코딩**(`ceiling = y_max - y_min`)·gravity/up-축 정규화 전무. ARKit/RoomPlan·다수 `.ply`/
`.obj` export 는 **Z-up(gravity-aligned)** → 가로 치수를 천장으로 오인, floor polygon 도 틀린 평면 추출.

**수정**: `MeshAdapter` 가 ingest 시 up-축을 **planar-density 판별자**(축별 1-D 히스토그램의 floor/ceiling 평면 집중도;
종횡비 무관)로 검출 후 모델 Y-up 프레임으로 정규화 → 기존 추출 로직 불변. density 동률 시 floor-area tiebreaker
(clear-floor 1.50× 마진). density·area 둘 다 모호(완전 cube / sparse+narrow)면 조용히 추측 않고 `ValueError`(진단+
`up_axis=` 권고)로 **fail-loud**. `up_axis` override 추가(기본 auto). 합성 Y-up 입력은 정규화 identity → **byte-equal**.

**검증**: 실 ARKit 10 scene up-축 전부 Z·천장 2.49–3.69 m(다중층 1개 5.76 m 별도)·`@pytest.mark.lab` 회귀로 고정.
default 368p/6s, ruff/mypy(strict)/tense EXIT0. 독립 code-review 2R(HIGH narrow-room→해소, MEDIUM sparse-narrow→fail-loud)
+ 독립 verifier VERIFIED-GREEN. **한계**: gravity-aligned-to-principal-axis 가정(기울어진 mesh 는 `up_axis=` 필요);
센서 vs 실측 ±10 cm 절대정확도는 독립 GT 필요(Phase 0b 후속, 미입증).
**Cross-refs**: D91, `.omc/plans/commercialization-analysis.md`(B2B 프레이밍·Phase 0), ADR 0001(RoomPlan/mesh measured 경로),
ADR 0042(live-mesh corner extraction, 관련 PROPOSED).

## §Status-update-2026-06-07 (v0.26.0) — .usdz mesh ingest (Phase 1; D93)

ARKit RoomPlan 의 1차 export 포맷인 **`.usdz`(USDZ)** 지오메트리 ingest 를 `MeshAdapter` 에 추가 — measured 경로의
"RoomPlan .usdz ingest 불가" 블로커(상용화 Phase 1) 해소. `[usd]`/`[mesh-export]` extra(usd-core) 로 게이트, `pxr` 경유.
공유 `_extract_room_model` 헬퍼로 리팩터해 v0.25.3 up-축(gravity) 정규화를 USDZ 경로에서도 재사용.

**구현 핵심**: (1) `UsdGeom.Mesh` 지오메트리를 **default prim 스코프** instance-proxy 순회로 수집 — concrete `def`-prototype
가 instance-proxy 양쪽으로 이중계수되던 결함(독립 review round-3 HIGH) 차단; (2) `metersPerUnit` 을 읽어 m 로 스케일 —
cm-unit USDZ(metersPerUnit=0.01) 가 100× 과대 치수로 ingest 되던 결함(round-2 HIGH) 정합; (3) stage `upAxis` 메타데이터를
density 기반 검출과 **교차검증**(힌트만, 권위는 geometry); (4) 천장 타당성 **절대상한** `ROOMESTIM_MAX_CEILING_M`(기본 20 m)
초과 시 fail-loud — near-horizon 가드(D89)·v0.25.3 fail-loud 철학과 일관. usd.py 의 `pxr` 명시 서브모듈 import 버그도 동반 수정.

**검증**: 합성 Y-up/Z-up USDZ 픽스처(`scripts/gen_usdz_fixtures.py` 생성) + round-2/3 회귀 테스트, `PolycamAdapter`
`.usdz` 경로가 `NotImplementedError`→정상 파싱. default 387p/3s, web 86p/3s, ruff/mypy(strict) EXIT0. 독립 code-review
round-3 + verifier VERIFIED-GREEN. **한계**: 절대 ±10 cm 검증은 독립 GT 대기(Phase 0b, 미입증) — v0.25.3 한계 승계.
**Cross-refs**: D92(Phase 0c acoustics honesty), D93(Phase 1 USDZ ingest), `.omc/plans/commercialization-analysis.md`(B2B Phase 0c/1).

## §Status-update-2026-06-07 (v0.26.1) — robust ceiling extraction (Phase 0b P0; D94)

상용화 Phase 0b(독립 GT ±10 cm 검증)에서 measured 경로의 천장 높이 추출 P0 결함을 확인·수정. 종전
`MeshAdapter` 는 `ceiling_height_m = y_max − y_min`(전체 수직 extent)로 천장을 구했는데, 이는 floor 평면 아래/
ceiling 평면 위로 새는 1~3% 의 스캔 outlier(가구, sub-floor/above-ceiling 노이즈)를 floor/ceiling **평면** 대신
잡아 실 ARKitScenes 스캔에서 천장을 **+0.27~1.34 m 과대평가**(median +0.43 m, 항상 양수)했다. 핵심은 이 GT 가
roomestim 로직과 무관한 **별도 센서(ARKitScenes Faro 레이저 스캔)** 라는 점 — 종전 lab A11 게이트 GT 는 roomestim
파생이라 tautological 이었던 것과 대비된다.

**수정**: gravity-aligned 스캔은 floor/ceiling 를 두 개의 sharp dense layer 로 packing 하므로, Y 좌표를 3 cm
bin 히스토그램으로 만들고 midpoint 로 split 한 뒤 floor=하단 half 의 **최하단** still-dense bin, ceiling=상단 half 의
**최상단** still-dense bin(`_robust_floor_ceiling_y`)으로 평면을 복원. *최외곽* dense 평면 anchoring 이 hardening 핵심
— desk/가구 층이 진짜 천장보다 dense 할 수 있어(ARKit 41069042: y=−0.62 desk 가 y=+1.03 천장보다 우세) plain
argmax 는 높이를 0.63 m 로 붕괴시키나, 최상단 still-dense bin 은 실제 2.27 m 천장을 복원한다.

**증거(5-scene, full-extent → robust)**: 수정 전 0/5 가 ±10 cm 이내. scene 42444946 = full-extent **4.37 m →
robust 3.02 m vs Faro GT 3.03 m (~1 cm)**. 합성 클린 메시는 outlier 가 없어 robust == full-extent(회귀 0).

**한계(미해결, 정직 고지)**: 이 독립 GT 검증은 **천장 높이만** 커버한다. **벽 위치/footprint ±10 cm 는 아직 독립 GT
미검증**(레이저↔메시 registration 필요; 후속 과제). 또한 robust 추출의 residual: 상단 half 의 dense 중간 평면(큰
테이블/mezzanine/dense 선반) 또는 심히 under-sampled 된 진짜 천장이 원리상 천장으로 오선택돼 높이를 과소보고할 수
있음 — 레이저 GT 검증 케이스(가구 있는 거실)에선 무해했으나 known residual 이며, 향후 plane-area/coverage 체크 또는
confidence flag 가 개선책. PATCH(정확성 수정, 정확도 개선 아님). **Cross-refs**: D94, ADR 0001(measured 경로),
`.omc/plans/commercialization-analysis.md`(B2B Phase 0b).
