# ADR 0030 §Status-update history — predictor-default-switch

**Companion file to**: [`0030-predictor-default-switch.md`](./0030-predictor-default-switch.md)
**Purpose**: chronological §Status-update blocks for ADR 0030, relocated
v0.22.1 per OQ-39 / D73 closure. Each block is byte-equal to its
pre-split content; D22 audit-trail-discipline is preserved (no retroactive
edits to block bodies).
**Block order convention**: blocks appear in their pre-split file order
(lines 133–477 of the HEAD `66d0f4b` file). The order is NOT strict
chronology — D22's append-on-top convention placed v0.18.4 above v0.18.3
above v0.18.2 in the original; that file order is preserved here verbatim
to keep `git blame` / future bisect across the split intact.

---

## §Status-update-v0.15.1

**Patch release** — v0.15.0 code-review unabsorbed follow-ups MEDIUM-1 + LOW-1
closed. No policy change, no new invariant, no web lane change.

**Item E (MEDIUM-1 closure) — Per-band fallback rationale append**
`_shoebox_per_band_alphas` now returns a third element `fallback_surfaces:
tuple[str, ...]` (sorted surface names where `absorption_bands is None` and
the 500 Hz scalar was broadcast). `predict_rt60_default_per_band` appends
`"; per-band α fallback used for surfaces: [<names>]"` to the rationale string
when the set is non-empty. The frozen `RT60Prediction` dataclass gains no new
field (backward-compat: external serialisers that inspect only existing fields
are unaffected). Single-band `predict_rt60_default` is unaffected (uses 500 Hz
scalars throughout; cannot trigger per-band fallback path).

**Item F (LOW-1 closure) — `roomestim/geom/polygon.py` shared util**
`roomestim/geom/__init__.py` NEW + `roomestim/geom/polygon.py` NEW (~80 LoC):
`polygon_area_3d`, `room_volume`, `shoelace_2d` extracted from the duplicate
definitions in `predictor.py` and `ace_challenge.py`.

- `predictor.py`: both internal callsites (`_polygon_area_3d`, `_room_volume`)
  migrated to `from roomestim.geom.polygon import polygon_area_3d, room_volume`;
  duplicate definitions deleted.
- `ace_challenge.py`: duplicate `_room_volume` definition deleted. The adapter
  itself never had an internal callsite (the helper was consumed only by tests
  via `from roomestim.adapters.ace_challenge import _room_volume`). The 3
  affected test modules (`tests/test_e2e_ace_challenge_rt60.py`,
  `tests/test_per_band_mae_ex_bl_snapshot.py`,
  `tests/test_lecture_2_ceiling_seat_bracket.py`) now import directly via
  `from roomestim.geom.polygon import room_volume`. No `room_volume` import is
  added to `ace_challenge.py` itself — it would be dead code.

D29 lane separation is web↔core; this extraction is core-internal and does not
touch `roomestim_web/` (D30 byte-equal confirmed — `git diff 63ae18a --
roomestim_web/` is empty). `roomestim_web/report.py` retains its own private
`_polygon_area_3d` / `_shoelace_2d` / `_room_volume` duplicates per D29 lane
separation; consolidating those would cross the lane boundary and is
intentionally out of scope for v0.15.1.

D22 audit-trail-discipline: this block follows the v0.10.1 precedent of
appending §Status-update without retroactively editing prior content.

## §Status-update-v0.15.2 (2026-05-18)

**Patch release** — v0.15.1 code-review LOW retention items closed (Item G +
Item H). No policy change to the predictor cascade (ADR 0030 §A–§E byte-equal).

**Item G — web report geom dedup land**
`roomestim_web/report.py` `_polygon_area_3d` / `_shoelace_2d` / `_room_volume`
three private duplicate functions removed (~24 LoC). Replaced with:

```python
from roomestim.geom.polygon import polygon_area_3d, room_volume
```

Callsites updated: `_surface_areas_by_material` inner loop, `build_acoustic_report`
volume calculation, and per-surface area loop. Decision basis: ADR 0029
§Cross-lane-geom-amendment (web → core stable public util import permitted;
core → web direction remains forbidden). `roomestim_web/__init__.py` bumped to
`0.12-web.7` (web lane touched per D30).

**Item H — LOW-2 clean-close (ace_challenge._room_volume deprecation shim)**
v0.15.1 removed `_room_volume` from `roomestim/adapters/ace_challenge.py`
without adding a deprecation shim. v0.15.2 records the **intentional decision
not to add a shim**:

- `_room_volume` carried an underscore prefix (module-private convention).
- `ace_challenge.py` defines no `__all__`; underscore-prefixed symbols are
  excluded from wildcard imports by Python convention.
- External consumer search `grep -rn "ace_challenge.*_room_volume"` returns 0
  hits across the entire repo tree.
- PATCH-range removal of an internal (underscore-prefix, `__all__`-unexposed)
  symbol is within semver PATCH scope. A shim would permanently dead-code the
  alias and confuse future `grep` audits.

If an external fork reports an `ImportError`, the remediation is a one-line
shim: `from roomestim.geom.polygon import room_volume as _room_volume` in the
caller. This ADR block serves as the audit trail for that decision.

D22 audit-trail-discipline: this block follows the v0.10.1 / v0.15.1 precedent.

## §Status-update-v0.16 (2026-05-18)

v0.16.0 lands three new policy surfaces per the ADR 0030 audit-trail cadence.

**Item I — Material Override UI land (D39 + D40 + D43 + ADR 0031)**
`roomestim/edit.py` NEW: `evolve_room` / `evolve_surface` / `evolve_room_material` /
`evolve_room_materials_bulk` helpers. All mutations via `dataclasses.replace`
chain; `Surface` frozen invariant (ADR 0002) preserved throughout. Web Material
Override Tab + Apply button (D40 manual trigger) land in `roomestim_web/app.py`.
ADR 0009 ISM ≥ Eyring invariant verified on 50 evolved rooms (D43 regression
lock: `tests/test_edit_room.py::test_evolve_room_material_shuffle_adr_0009_invariant`).

**Item J — 2D Blueprint export land (D41 + ADR 0032)**
`roomestim/viz/blueprint.py` NEW: `render_blueprint()` PNG (300 dpi) + SVG
export. Coordinate convention: x=right, z=north-up per D41. Content layers:
floor outline, wall labels, listener area, speaker positions, dimension arrow,
north arrow, 1 m scale bar. Byte-equal PNG determinism lock under matplotlib
Agg backend (`tests/test_viz_blueprint.py::test_render_blueprint_determinism_png_byte_equal`).
Web Blueprint Tab added.

**Item K — Engine validation toggle land (D42 + ADR 0033)**
`write_layout_yaml` gains `validate: bool = True` + `schema_path_override`
kwargs (backward-compat default ON). CLI `export` subcommand: mutually exclusive
`--validate-engine PATH` / `--no-engine-validation` flags. Precedence: CLI >
ENV > default hardcoded path (D42 regression lock:
`tests/test_engine_toggle.py::test_cli_export_cli_overrides_env`). WARNING
header prepended to YAML when validation skipped (ADR 0033 §C audit trail).
Web sidebar Checkbox "Standalone YAML (skip engine schema check)" default OFF.

**Honesty note**: v0.16 provides "scan → material correction → blueprint"
workflow. The root-cause phone-scan material-estimation accuracy gap (RoomPlan
assigns `WALL_PAINTED` to all walls) remains an upstream limitation outside
roomestim's scope. v0.16 provides the correction path, not the estimation fix.

**Versions**: `roomestim.__version__` `0.15.2` → `0.16.0` (MINOR bump — 4 new
public API symbols + 1 new viz entry + 2 new CLI flags). `roomestim_web.__version__`
`0.12-web.7` → `0.13-web.0` (web MINOR bump — 2 new UI tabs + sidebar checkbox).

## §Status-update-v0.16.1 (2026-05-18)

D22 audit-trail-discipline pattern (v0.10.1 / v0.15.1 / v0.15.2 / v0.16 precedent).
Existing §Status-update-v0.16 本文 위에 append; retroactive 수정 X.

**Item L (MEDIUM-2 closure)** — `roomestim/viz/blueprint.py` module-level
`matplotlib.use("Agg", force=True)` guard 추가 (import 시점 backend lock-in).
기존 `render_blueprint` 함수 본체 내부 `matplotlib.use("Agg")` 제거 (중복).
`try/except ImportError: pass` 로 graceful degradation 보존 (`[viz]` extra 미설치
환경). 근거: PNG byte-equal 결정성 회귀 lock 강건성 — 다른 모듈이 non-Agg backend을
process 내 먼저 초기화해도 blueprint import 시 Agg 강제 보장.
테스트: `test_blueprint_module_locks_agg_backend` +1 케이스 (모듈 import 후
`matplotlib.get_backend().lower() == "agg"` 회귀 lock).

**Item M (MEDIUM-3 closure)** — `tests/test_engine_toggle.py`에
`test_cli_export_cli_overrides_env_positive_success` positive integration variant 추가
(기존 6 → 7 케이스). ENV = anti-permissive schema (required: `__MUST_NOT_EXIST_PROP__`)
/ CLI = permissive schema (`{"type": "object"}`) → exit 0 + layout.yaml 생성 + WARNING
부재 증명. 기존 negative variant (`test_cli_export_cli_overrides_env`) 유지 —
두 케이스가 다른 각도에서 D42 CLI > ENV precedence 회귀 lock.

**Item N (LOW-1 closure)** — `roomestim_web/app.py` inline `__import__("json")`
제거. module top-level `import json` 추가 + `_count_changes(changes_json: str) -> int`
module-level named helper 추출. helper는 empty/invalid/non-dict 입력 시 0 반환
(exception confinement: `JSONDecodeError`, `ValueError`, `TypeError`). 테스트:
`test_count_changes_helper` +1 케이스 (5 입력 → 0/0/1/0/0 회귀 lock).

**Item O (LOW-2 + LOW-3 묶음 closure)** — Material Override Tab Dataframe wiring 보강.
`build_material_override_tab()`: Dataframe `interactive=False` → `interactive=True` +
label 업데이트. `changes_textbox: gr.Textbox` 신규 추가 (JSON 직접 입력 fallback +
Dataframe 변경 시 자동 갱신 표시). `_dataframe_to_changes_json(rows, initial_room) -> str`
helper 신규 (~30 LoC): baseline material 비교 후 변경된 행만 JSON으로 반환. `app.py`:
Dataframe `change` 이벤트 → `_changes_textbox` → `changes_state` wiring 추가
(try/except fallback 포함). `_dataframe_to_changes_json` import 추가. 테스트:
`test_dataframe_changes_to_json_helper` + `test_dataframe_changes_to_json_no_change`
+2 케이스.

**Item P (OQ-32 CLOSED)** — 3D viewer Plotly Mesh3d color 갱신 on Apply.
`layout_state: gr.State = gr.State(value=None)` 신규 추가 (`room_state` 동일 패턴).
`_on_submit` 반환 11-tuple → 12-tuple 확장 (마지막 `result.layout` 추가); 4 반환
경로 모두 12-tuple 일관. `submit_btn.click outputs` 12요소로 확장 (`layout_state`
추가). `_on_apply_overrides_wrapper` 시그니처 2-인자 → 3-인자 (layout 추가);
반환 5-tuple → 6-tuple (`viewer_plot` 추가); 정상 분기에서 `build_room_figure(new_room,
layout)` 재호출 → Plotly figure with updated `MATERIAL_PALETTE[surface.material]` 색상.
`_apply_btn.click` inputs 3개 / outputs 6개로 확장. `roomestim_web/viewer.py` 본체
byte-equal. 테스트: `test_apply_returns_viewer_figure` +1 케이스 (6-tuple +
`result[1]` non-None 회귀 lock). OQ-32 CLOSED.

**Versions**: `roomestim.__version__` `0.16.0` → `0.16.1` (PATCH). `roomestim_web.__version__`
`0.13-web.0` → `0.13-web.1` (PATCH per D30 — wiring 보강 + viewer 색 갱신).
`__schema_version__` `"0.1-draft"` 불변. ADR 0030/0031/0032/0033 본문 byte-equal.

## §Status-update-v0.17 (2026-05-19)

D22 audit-trail-discipline 패턴 (v0.10.1 / v0.15.1 / v0.15.2 / v0.16.0 / v0.16.1 precedent).
기존 §Status-update-v0.16.1 본문 위에 append; retroactive 수정 X.

**Item Q — Object schema land (D44 + D46 + D47 + ADR 0034)**
`Object` frozen dataclass + `ObjectKind` Literal + `DEFAULT_OBJECT_MATERIAL` dict +
`evolve_room_add_object` / `evolve_room_remove_object` / `evolve_room(objects=)` 6개
공개 API v0.17.0에서 land. `RoomModel.objects: list[Object] = []` 추가.
schema_version `"0.1-draft"` → `"0.2-draft"` (D44 backward parse: 0.1 입력 → `objects=[]`
자동; 0.2 입력 → `objects` 키 파싱).

음향 통합 (D46): column → 5 추가 surface (`predictor._objects_to_surfaces`); door/window
→ wall α override (`predictor._objects_to_wall_alpha_overrides`; effective α =
`α_wall × (1 − Σfrac) + Σ(α_obj × frac)`).

ADR 0009 invariant (`ism_rt60 ≥ eyring_rt60 − 1e-6`) 유지 확인 (D47 회귀 lock:
`tests/test_objects_acoustic_invariant.py` 6 케이스, 50 seeds × 3 kind = 150 instance).
ADR 0030 cascade `default_predictor_name ∈ {"image_source", "eyring"}` 보존 (D38).

**정직성 노트**: `MeshAdapter` (Polycam 등)와 `ACEChallengeAdapter`는 `objects=[]`
placeholder — 자동 인식은 OQ-33 (v0.18+) deferral.

**Item R — USDZ + gLTF export land (D45 + ADR 0035)**
`write_usdz` + `write_gltf` 신규 공개 API 2개. CLI `--format yaml|usdz|gltf|glb`
(default `yaml` backward-compat). optional `--with-acoustics-sidecar` flag →
`<basename>.acoustics.json`.

USDZ backend: `usd-core>=24.0` optional extra (`pip install roomestim[usd]`).
gLTF backend: 기존 core dep `trimesh>=4.0` 재사용 (추가 의존성 0).
HF Spaces re-deploy 트리거 없음 (시스템 의존성 변경 없음).

**정직성 노트**: v0.17.0 1차 release는 mesh geometry + PBR color만 포함.
acoustic α 메타데이터는 sidecar (internal schema `v0.1-internal`); USD `<material binding>`
acoustic extension은 v0.19+ (OQ-35 deferral).

**Item S — Schema bump 0.1-draft → 0.2-draft (D44)**
외부 consumer (`spatial_engine`)는 `room.yaml` 미사용 (`layout.yaml`만 소비) →
schema bump 영향 격리. `room.yaml` 소비자: roomestim 자체 (round-trip) + 사용자 도구
(드물게). 0.1-draft YAML 외부 consumer가 0.2-draft unknown field로 fail 시 OQ-36
(v0.17.1 patch 후속).

**Versions**: `roomestim.__version__` `0.16.1` → `0.17.0` (MINOR bump — 6 신규 공개
API + 2 export + 2 CLI flag). `roomestim_web.__version__` `0.13-web.1` → `0.14-web.0`
(web MINOR — download 버튼 USDZ/GLB 추가). `__schema_version__` `"0.1-draft"` →
`"0.2-draft"` (ADR 0034 §B).

## §Status-update-v0.18 (2026-05-22)

D22 audit-trail-discipline 패턴 (v0.10.1 / v0.15.1 / v0.15.2 / v0.16.0 / v0.16.1 /
v0.17 precedent). 위 §Status-update-v0.17 본문 위에 append; retroactive 수정 없음.

**Item T — `evolve_placement` + `nudge_speaker` land (D48 + D49 + ADR 0036)**
`roomestim/edit.py` 에 frozen-respecting `evolve_placement(...)` + `nudge_speaker(...)`
신규 공개 API 2개. nudge 는 spherical Δ (az/el/dist) XOR Cartesian Δ (xyz) — 동시
지정 시 ValueError; 모든 frame 변환은 `roomestim.coords` 단일 권위 경유.
round-trip 은 신규 모듈 없이 기존 reader + `write_layout_yaml` + 신규 edit helper
조합 (D48 — 스켈레톤 `load_layout.py` 가정은 기존 reader/writer 중복으로 reject).
정직성 노트: round-trip 충실도는 Level 1 (구조 동치) 만; byte-equal 은 비-목표
(D51 — `yaml.safe_dump` 단일 직렬화 권위 유지).

**Item U — reader aim 복원 (D50)**
`read_placement_yaml` 이 `x_aim_az_deg`/`x_aim_el_deg` 존재 시 `aim_direction` 복원
(시그니처 불변; 반환 PlacementResult 의 aim 이 None→복원으로 채워짐). 정직성 노트:
aim 복원은 **shipped `roomestim export` 의 기존 aim silent-corruption 버그도 수리**
(명시 `x_aim_az_deg: 0.0` 이 export 재실행 시 toward-origin 으로 변형되던 문제;
export byte-gate 로 회귀-lock). `notes` 와 per-speaker `id` 는 engine schema 충실
슬롯 부재로 round-trip 제외 (notes = OQ-37; id = channel 재생성). `target_algorithm`
은 {VBAP, WFS} 에서만 보존 — DBAP/AMBISONICS 는 read 시 "VBAP" 로 붕괴 (OQ-38
deferral). 부분 aim 키 (한 축만 존재) → treat-as-missing (양쪽 키 필요). 수치 노트:
position `dist_m` 은 비축-정렬 azimuth (예: 120°) 에서 cartesian↔spherical cycle 당
~1 ULP drift → byte-equal idempotency 게이트는 축-정렬 fixture (az ∈ {0,90,180,270}°,
el=0, 정수 반경; 단일 write→read→write 고정점) 로 lock. aim az/el 은 atan2 scale-
invariant 이라 unit-벡터 복원으로 byte-equal.

**Item V — CLI `roomestim edit` + web 스피커 nudge (web 0.14→0.15-web.0)**
신규 CLI subcommand `roomestim edit` (read → nudge → 재검증 collector → write +
unified diff; flag `--daz`/`--del-deg`/`--ddist`/`--dx`/`--dy`/`--dz`; D42
precedence 재사용). web "스피커 조정" 탭 (channel 입력 + 6 Δ Number + Apply →
`nudge_speaker` → `validate_placement` → 3D 뷰어 재렌더). 검증 collector
`validate_placement(...)` 는 `write_layout_yaml` 의 5-step·typed raise 를 건드리지
않는 별도 비-raising 헬퍼 (MED-1); schema path-join 은 `_resolve_schema_file` 로
중복 제거 (3번째 복제 consolidation). 정직성 노트: web 3D 스피커 클릭 정확도는
Plotly customdata 의존 (작은 marker 클릭 미스 가능 → channel 입력 fallback 병행).
CLI elevation Δ 의 el>90 비물리 clamp 는 v0.18.1 deferral (finite 검사만; web 은
`gr.Number minimum/maximum` 제한).

**Versions**: `roomestim.__version__` `0.17.0` → `0.18.0` (MINOR bump — 3 신규 공개
API `evolve_placement`/`nudge_speaker`/`validate_placement` + reader 충실도 보강 +
CLI subcommand 1개 + web UI surface 1개). `roomestim_web.__version__` `0.14-web.0`
→ `0.15-web.0` (web MINOR — 스피커 조정 탭 + 3D customdata + nudge Apply→재렌더).
`__schema_version__` `"0.2-draft"` **불변** (D52 — layout 편집 ⊥ RoomModel schema).

## §Status-update-v0.18.1 (2026-05-22)

**Item W — Fix 7b closure (CLI el-bound enforcement)**

`nudge_speaker` spherical 분기에 el ∉ [-90, 90] → `ValueError` reject 추가
(D53). v0.18.0 에서 known-gap (Fix 7b deferral) 으로 명시된 단일 correctness
버그 closure. clamp/warn-clamp/silent-accept 세 대안 모두 거부 (D53 근거: 기존
`dist <= 0` reject 와 대칭, 사용자 의도 보존, 멱등성 유지, web `gr.Number`
min/max 와 정합). Cartesian 분기 unguarded 유지 (atan2 산출 el 은 항상 물리적).

predictor cascade (ADR 0030 §A–§E) byte-equal — placement 편집은 RT60 경로
미접촉. `roomestim_web.__version__` `0.15-web.0` 불변 (web byte-equal, D30).
`__schema_version__` `0.2-draft` 불변. ADR 0036 §Status-update-v0.18.1 병행
append. D22 audit-trail-discipline (v0.10.1 / v0.15.1 / v0.15.2 / v0.16.1 /
v0.17 / v0.18 precedent): 이 블록 append, 기존 §Status-update 본문 retroactive
수정 없음.

## §Status-update-v0.18.4 (2026-05-25)

D22 audit-trail-discipline pattern (v0.10.1 / v0.15.1 / v0.15.2 / v0.16.0 /
v0.16.1 / v0.17 / v0.18 / v0.18.1 / v0.18.2 / v0.18.3 precedent). 위
§Status-update-v0.18.3 본문 위에 append; retroactive 수정 없음.

**Item Z — v0.19-cycle OQ 재검토 (doc-only PATCH)**

v0.19-cycle cadence 의 5 OQ 재검토 (OQ-34/35/36/37/38) 가 PATCH `0.18.4` 로
landing. OQ-36 은 D26 hard-wall 에서의 정식 WONTFIX close (D57); OQ-34/35 는
v0.21 명시-cadence 재연기 (D58/D59); OQ-37/38 은 v0.20 명시-cadence 재연기
(D60/D61). 모든 trigger 검증됨 (0건). 신규 ADR: none. 신규 OQ: none.

Predictor cascade §A–§E: **byte-equal** (doc-only — acoustic / schema 코드 미접촉).
web: **byte-equal** `0.15-web.0` (D30). `__schema_version__` `0.2-draft` 불변.
`roomestim.__version__` `0.18.3` → `0.18.4` (PATCH).
ADR 0034/0035/0036 §Status-update-v0.18.4 병행 append.

---

## §Status-update-v0.18.3 (2026-05-24)

D22 audit-trail-discipline pattern (v0.10.1 / v0.15.1 / v0.15.2 / v0.16.0 /
v0.16.1 / v0.17 / v0.18 / v0.18.1 / v0.18.2 precedent). 위
§Status-update-v0.18.2 본문 위에 append; retroactive 수정 없음.

**Item Y — D56 writer float normalization PATCH (placement serialization only)**

`roomestim/export/layout_yaml.py` `_round9` helper + 6 call-site wraps (D56):
per-speaker `az_deg`, `el_deg`, `dist_m`, `x_aim_az_deg`, `x_aim_el_deg` +
top-level `x_wfs_f_alias_hz` all normalized to 9 decimal places at emit time.
Fixes dogfood-reproduced no-op-edit diff churn. Predictor cascade (§A–§E)
byte-equal — placement serialization is not on the acoustic code path; RT60
negative control `1.9190766987173207` unchanged. `roomestim_web.__version__`
`0.15-web.0` 불변 (web byte-equal). `__schema_version__` `0.2-draft` 불변.
`roomestim.__version__` `0.18.2` → `0.18.3` (PATCH). New ADR: none (writer
precision tightening recorded via §Status-update appends per v0.18.1 precedent).
ADR 0036 §Status-update-v0.18.3 병행 append. 신규 OQ: none.

## §Status-update-v0.18.2 (2026-05-24)

D22 audit-trail-discipline 패턴 (v0.10.1 / v0.15.1 / v0.15.2 / v0.16.0 /
v0.16.1 / v0.17 / v0.18 / v0.18.1 precedent). 위 §Status-update-v0.18.1 본문 위에
append; retroactive 수정 없음.

**Item X — OQ-33 re-defer + D54 (doc-only PATCH)**

OQ-33 ("Mesh/ACE adapter 객체 자동 인식") 의 D26 forced-decision 사이클 (v0.19
cadence). 결론: manual-annotation 부분은 v0.17 에서 이미 충족 (`evolve_room_add_object`
+ web `object_add.py` Object Add Mode + predictor `_objects_to_surfaces` fold).
미해결 잔여는 "non-RoomPlan adapter 무인 자동 추출" 으로 범위 축소 → v0.20 hard
wall 재연기 (D54). 두 D26 trigger 모두 미충족 (0 user reports; 0 mesh-only GT
fixtures). 두 자동-추출 후보(Polycam Pro API / bbox clustering) 모두 0 user report
상태에서 highest-risk — D26 YAGNI 규율 정합. v0.20 이 hard wall (재-재연기 금지;
trigger 미충족 시 WONTFIX). CLI `add-object` (D55) = OUT (사용자 미확인 — web으로
이미 가능). 신규 OQ-39 (ADR 0030 §Status-update split) allocate — defer to v0.21.

predictor cascade (ADR 0030 §A–§E) byte-equal — doc-only 사이클; acoustic/schema
코드 미접촉. `roomestim_web.__version__` `0.15-web.0` 불변 (web byte-equal, D30).
`__schema_version__` `0.2-draft` 불변. `roomestim.__version__` `0.18.1` → `0.18.2`
(PATCH — executable regression-lock tests 추가).

regression lock: `tests/test_oq33_residual_lock.py` NEW (MeshAdapter + ACEChallenge
adapter `objects==[]` invariant + `evolve_room_add_object` YAML round-trip).
