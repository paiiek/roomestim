# ADR 0050 — Apple RoomPlan `CapturedStructure` → N-RoomModel splitter adapter

- **Date**: 2026-06-17
- **Status**: Accepted (S1+S2+S3 구현됨 v0.43.0 — `roomestim/adapters/roomplan_structure.py` 가 진짜 Apple `CapturedStructure`(MIT fixture)를 N개 단일방 `RoomModel` 로 분해해 ADR 0049 RoomCollection 합성 레이어에 공급. wall partition 보존(fixture 20 walls→5/6/3/6), objects 10 kept·doors/windows 8 wall_index 재계산, openings/degenerate/tie-break 처리. 단일방 코드 0 touch·golden byte-equal. membership 은 HEURISTIC RECONSTRUCTION 으로 disclosed(정확도 UNVALIDATED, multi-room GT 없음). code-review APPROVE-WITH-FIXES(ADR 사이드카 거짓주장 1건 수정). default 686p/7s. 진짜 RoomModel rewrite 는 본 splitter 경로로 우회되어 불필요.)
- **Deciders**: 사용자(빌드 방향 승인 예정), planner(설계), executor(구현 예정), code-reviewer(honesty + additive-only 리뷰 예정), verifier(full-gate)
- **Refs**: ADR 0047(multi-room DEFERRED — 본 ADR 가 그 re-open condition 의 *입력 경로* 절반을 충족), ADR 0049(additive RoomCollection composition layer — 본 ADR 가 그 합성 레이어에 N 개 `RoomModel` 을 **공급**), ADR 0046(provenance-at-boundary), ADR 0002(단일방 `RoomModel`), ADR 0034(object schema). 실 스키마 증거: `.omc/research/roomplan-real-export-acquisition.md`. 실 fixture: `tests/fixtures/roomplan_real/capturedstructure_{multiroom,single}.json` (+ `ATTRIBUTION.md`, MIT). 단일진실원천 disclosure: `roomestim/reconstruct/_disclosure.py` (신규 `ROOMPLAN_STRUCTURE_SPLIT_NOTE`). 플랜: `.omc/plans/multi-room-roomcollection.md` §"CapturedStructure splitter adapter (planner 2026-06-17)".

> **핵심요약**: Apple `CapturedStructure` 는 진짜 multi-room 캡처지만 **element→room membership 을 제공하지 않는다** — `sections`(=방)는 `label + story + center[x,y,z]` 만 갖고, `walls/doors/windows/openings/objects/floors` 는 방 외래키 없는 **flat 배열**이다. 따라서 splitter 는 각 element 를 **명시적·문서화된 HEURISTIC**(floor-plane nearest-section-center, story-matched)으로 section 에 배정한다. 결과 per-room split 은 **RECONSTRUCTED/heuristic 이지 Apple-authoritative 가 아니다** → provenance + 단일진실원천 disclosure 로 라벨링하고, 수출이 담지 않는 per-room geometry 를 **fabricate 하지 않는다**(특히 floors[] 는 빌딩 전체 단일 폴리곤 1개뿐이라 per-room footprint 는 **배정된 벽들의 floor-projected hull** 로 만든다). 집계 volume/RT60 **없음**. 이것은 ADR 0047 의 `RoomModel` rewrite 가 **아니다**: 새 어댑터 모듈이 N 개의 **기존 단일방 `RoomModel`** 을 만들어 ADR 0049 의 **이미 출시된** RoomCollection 합성 레이어에 그대로 먹인다 → 단일방 코드 0 touch, additive-only.

---

## Context

ADR 0047 은 진정한 multi-room 을 DEFER 했고 그 re-open 조건을 (1) 실 multi-room 입력 경로, (2) per-room placement/export 설계로 못박았다. ADR 0049 가 (2)를 **additive RoomCollection 합성 레이어**(N 개 단일방 입력 → per-room placement + 묶음 export, v0.40–0.42 출시)로 충족했다. 남은 것은 (1) — **진짜 Apple export 를 N 개 단일방 `RoomModel` 로 바꾸는 입력 경로**다.

2026-06-17, MIT 라이선스의 공개 GitHub repo(`theLodgeBots/open3dFloorplan`)에서 **진짜 device-scan `CapturedStructure` export 2건**(4-section multiroom + 1-section single)을 확보해 repo fixture 로 커밋했다(real-vs-synthetic 검증: UUID v4·proprietary `coreModel` 바이너리·7-decimal float·enum-as-dict 인코딩 — 손으로 못 만듦). 실 스키마(직접 `json.load` 로 재확인):

- 최상위: `coreModel`(base64 proprietary), `referenceOriginTransform[16]`, `version`(2), `story`(int), `sections[]`, 그리고 **flat** `walls/doors/windows/openings/objects/floors[]`.
- `Section` = `{label, story, center[x,y,z]}` **만**. geometry 없음. 라벨: bedroom, bathroom, livingRoom, **unidentified**. (multiroom 파일: bedroom×2, bathroom, unidentified.)
- `Surface`(wall/door/window/opening/floor): `category`/`confidence` = **single-key dict**(`{"wall":{}}`, `{"door":{"isOpen":false}}`), `dimensions[w,h,0]`, `transform`=**flat 16-float column-major** simd_float4x4, `polygonCorners`(rect wall=`[]`; floor=4 corners), `story`, `identifier`/`parentIdentifier`(UUID|null).
- `Object`(가구): `category`(enum-dict), `transform[16]`, `dimensions[3]`, `attributes`, `parentIdentifier`.
- 단위 meters, ARKit world Y-up. **NO material_hint, NO ceilings, NO room dims, NO element→room FK.**

**검증된 결정적 사실 2가지(설계를 가른다):**
1. multiroom 파일의 `floors[]` 는 **단 1개**(빌딩 전체 6.43×7.43 m). 4개 section 의 per-room floor 폴리곤은 **export 에 존재하지 않는다.**
2. flat column-major `transform` 을 `np.asarray(flat).reshape(4,4).T` 하면 **col3 = origin, col0 = 단위 width-dir** 로, 기존 `roomplan.py::_wall_polygon_from_transform` 의 계약(`transform[:3,3]`=origin, `transform[:3,0]`=width axis)과 **정확히 일치**한다(실 wall[0] 로 검증: origin `[4.055,-0.265,-4.379]`, width-dir `[0.029,0,1.0]` norm 1.0).

## Decision

**ADR 0047 의 `RoomModel` rewrite 대신, `CapturedStructure` → N-`RoomModel` splitter 어댑터(신규 모듈)를 채택해 ADR 0049 RoomCollection 합성 레이어에 공급한다.**

1. **신규 모듈 (D-A).** `roomestim/adapters/roomplan_structure.py`. 기존 `roomplan.py` 는 **편집하지 않는다**(sidecar 단일방 경로 byte-equal 유지). 건전한 helper 만 **import 재사용**: `_wall_polygon_from_transform`, `_polygon_3d`, `_project_to_floor_polygon`, `_material_for_hint`, object kind 매핑 로직. 새 모듈은 `parse_structure(path) -> list[RoomModel]` 를 노출한다.

2. **Schema 파싱 (D-B).**
   - **transform**: flat16 → `np.asarray(flat, float).reshape(4,4).T` → 기존 `_wall_polygon_from_transform`/object anchor 계약과 일치(위 검증). 단일 helper `_mat4_from_flat()` 로 캡슐화.
   - **enum-as-dict**: `category`/`confidence` 는 `next(iter(d))` 로 첫 키 추출 → 문자열로 정규화 후 기존 substring kind 매핑에 투입(door `isOpen` 값은 geometry 에 무관, 무시).
   - meters/Y-up — 기존 frame 과 동일, 변환 없음.

3. **Room-assignment HEURISTIC (D-C, load-bearing honesty).** Apple 은 element→room 을 주지 않는다. 각 element 를 다음으로 배정한다:
   - **PRIMARY**: element origin(transform col3) 의 **floor-plane (x,z)** 와 각 section.center 의 (x,z) 사이 **유클리드 최근접**, 단 `story` 일치 section 만 후보. (section.center 의 y 는 전 section 동일한 구조 평균값 −0.254 라 수직 변별력 0 → x,z 만 사용.)
   - **door/window**: `parentIdentifier`(→부모 wall UUID)가 있으면 **부모 wall 이 배정된 방**으로 따라가고, 그 방의 walls-only 프레임에서 `wall_index` 를 **재계산**(ADR 0037 / `wall_surfaces` 프레임). parent 미해결 시 nearest-center 로 폴백하고 `wall_index=None`(predictor 가 무시).
   - **section 은 index 로 식별**(label 로 병합 금지) — 동일 라벨 두 `bedroom` 을 분리 보존(이름 충돌은 `bedroom`, `bedroom-2` 식 deterministic 접미사).
   - **`unidentified` section**: 삭제·병합하지 않고 `unidentified` 라는 이름의 방으로 그대로 보존(nearest-center 동일 적용); disclosure 가 low-confidence 임을 명시.
   - **타이브레이크**: 등거리 → 최소 section index(deterministic).
   - **결과 split 은 RECONSTRUCTED**. 단일진실원천 `_disclosure.py::ROOMPLAN_STRUCTURE_SPLIT_NOTE` 로 라벨링.

4. **Per-room `RoomModel` 구성 (D-D).**
   - **floor_polygon**: `floors[]` 에서 가져오지 **않는다**(빌딩 전체 1개뿐, 검증됨). 배정된 벽들의 **floor-projected endpoint(p0,p1 in x,z)들의 convex hull** → `canonicalize_ccw`. hull 은 concave 방을 과대추정한다(기존 footprint convex-hull 정직고지와 동일 caveat). 벽 < 3 → 닫힌 폴리곤 불가 → footprint 를 **low-confidence** 로 표기하고 배정된 벽 bbox + section center 로 최소 폴리곤(또는 그 방 skip + warning). Voronoi 로 빌딩 floor 를 분할하는 안은 **기각**(Apple 이 안 잡은 per-room 경계를 fabricate = 가짜 숫자).
   - **ceiling_height_m**: RoomPlan 은 ceiling 무캡처 → 배정된 **wall heights(dimensions[1])의 median**(robust; 2.44 다수 + 2.99 outlier). `ceiling_coverage=None`, `ceiling_confidence="unknown"`(측정 안 됨). synthesized 임을 문서화.
   - **surfaces**: 배정된 walls → reshape+기존 helper; per-room hull floor surface; **ceiling surface 없음**(synthesized 스칼라 높이만 — 명시 ceiling entry 없음, 기존 동작과 일치).
   - **objects**: 배정된 objects 를 enum-dict→기존 kind 매핑(sofa/table/bed/storage 유지; chair/sink/toilet 무시 — 기존 `_extract_objects` 와 동일 정직 기준). material 은 `_MATERIAL_HINT_MAP` 에 hint 없음 → per-kind 기본(ESTIMATE).
   - **listener_area**: per-room footprint 에 기존 `default_listener_area`.
   - **provenance**: geometry 출처는 LiDAR depth = `"measured"`(코덱 literal 의미상 정확). **room MEMBERSHIP 의 heuristic 성격은 provenance literal 을 오버로드하지 않고** `ROOMPLAN_STRUCTURE_SPLIT_NOTE` + `UserWarning` 으로 담는다(이 분리가 D-C 의 명시 설계 판단). (대안: provenance="reconstructed" 로 강등 — 본 codebase 에서 "reconstructed"=depth 없는 image 추론을 의미하므로 부정확 → 채택 안 함.)

5. **CLI (D-E).** 신규 서브커맨드 `roomestim structure --in-structure PATH.json [placement flags] --name N --out-dir D`. 핸들러 `_cmd_structure` 는 `parse_structure()` → N `RoomModel` → 방마다 기존 `_run_placement` → `write_room_yaml`/`write_layout_yaml` → `RoomCollection` → `write_collection_yaml`(+ 옵션 combined glTF/USD 재사용), `_cmd_collection` 패턴 그대로. 기존 `collection`(N 개 명시 room.yaml 입력) 서브커맨드는 **무변경**(계약 오염 방지). `ingest`(단일 RoomModel 출력)에는 안 얹는다(N-출력 부적합). additive: 신규 `_add_structure_parser` + `_cmd_structure` + dispatch 1 분기.

6. **NO FAKE CAPABILITY / NO FAKE NUMBERS.** "roomestim 이 한 캡처에서 multi-room geometry 를 정확히 복원한다" 고 **주장하지 않는다**. split 은 heuristic·disclosed. per-room footprint 는 hull 추정(과대추정 고지). **집계 footprint/volume/RT60 없음**(ADR 0047 가짜숫자 트랩; 음향은 per-room). fixture 는 독립 GT 가 없으므로 검증은 **구조/sanity + provenance** 만, **정확도 주장 금지**.

## Why NOT the ADR 0047-deferred refactor

| ADR 0047 DEFER 이유 | 본 splitter 의 회피 |
|---|---|
| (1) 실 multi-room 입력 경로 없음 | **본 ADR 가 바로 그 경로** — 진짜 `CapturedStructure` → N 단일방 `RoomModel`. |
| (2) blast radius(5 생성지점·export·placement·CLI·schema·golden) | **단일방 0 touch.** 신규 어댑터 모듈 1개 + 신규 CLI 서브커맨드 1개. 출력은 **기존** `RoomModel`/`RoomCollection`(ADR 0049)·기존 export·기존 placement 재사용. |
| (3) 부분 구현이 단일방 golden 깸 | golden byte-equality **by construction**(단일방·sidecar `roomplan.py` 미변경) + 회귀 테스트로 잠금. |

## Honesty framing (the load-bearing point)

Apple 의 `sections` 는 방을 **셋만** 알려준다: label, story, center. 어느 벽이 어느 방인지 **모른다**. 따라서 splitter 의 per-room 분할 전체가 roomestim 의 **추론**이다. 이를 정직하게 다루는 4가지 장치:
1. **단일진실원천 disclosure** `ROOMPLAN_STRUCTURE_SPLIT_NOTE`(adapter docstring·CLI stderr·`UserWarning`·README 가 동일 문자열 참조). **주의: 영속 room.yaml 사이드카는 이 membership-heuristic disclosure 를 담지 않는다** — 단일방 room.yaml 스키마/golden 을 byte-equal 로 유지하려고(ADR 0049 additive 원칙) schema 를 의도적으로 건드리지 않았고, membership 고지는 런타임 채널(CLI stderr + `UserWarning`)로만 전달된다.
2. **partition invariant 테스트**: 모든 wall 이 정확히 한 방에 배정(합 == 총 wall 수) — 누락/중복 0.
3. **degenerate-section warning**: 벽 <3 인 section 은 footprint low-confidence + `UserWarning`.
4. **정확도 무주장**: fixture 에 독립 GT 없음 → sanity(면적 finite·>0·빌딩 bbox 내, 높이 [2.0,3.5]) 만 검사, "이 분할이 맞다" 는 단언 금지.

알려진 실패 모드(문서화, 해결 안 함): **nested room**(bathroom-inside-bedroom — nearest-center 가 큰 방으로 빨아들임), **동일 라벨 인접 방**(두 bedroom 중 하나가 0벽 받는 경우 관측됨 → degenerate 처리), **두 방 경계의 등거리 벽**(tie-break index). 이들은 GT 없이 튜닝 불가 → least-claim.

## Consequences

**Positive**
- ADR 0047 re-open 조건 (1) 충족: 진짜 Apple multi-room export 를 실제로 ingest → per-room 레이아웃 + 묶음 manifest 산출(ADR 0049 합성 레이어 재사용).
- 단일방·sidecar 경로 byte-equal(0 touch) → `feedback_verify_each_step` 준수.
- 기존 helper(transform/poly/material/object-kind)·기존 export·placement·`RoomCollection` 최대 재사용.

**Negative / risk**
- per-room split 이 heuristic — nested/인접/동일라벨 방에서 **틀릴 수 있고 GT 로 측정 불가**. disclosure·warning·partition 테스트로 정직하게 한정하되, 정확도는 보증 못 함(최상위 리스크).
- per-room footprint 는 wall-hull 추정(concave 과대추정) — 측정 floor 폴리곤이 아니다.
- ceiling height 는 wall-height median 으로 synthesized(측정 ceiling 아님).

**Neutral**
- 집계 음향/footprint merge 는 의도적 범위 밖(가짜숫자 트랩; 측정 multi-room GT 생기면 별도 ADR).
- `coreModel`(proprietary 바이너리), `referenceOriginTransform`, `completedEdges`, `curve` 는 geometry 에 불필요 → 의도적 drop(문서화).

## Alternatives considered

- **Voronoi/section-cell 로 빌딩 floor 분할** — 기각: Apple 이 안 잡은 per-room 경계 fabricate(seam = 가짜 숫자). wall-hull 이 least-claim.
- **provenance="reconstructed" 로 방 강등** — 기각: 본 codebase 에서 "reconstructed"=depth 없는 image 추론. 여기 geometry 는 LiDAR(measured); membership heuristic 은 disclosure 로 분리.
- **`roomplan.py` 를 확장해 multi-section 처리** — 기각: sidecar 단일방 경로 오염·golden 회귀 위험. 신규 모듈이 0-touch 보장.
- **`collection` 서브커맨드에 `--in-structure` 플래그 추가** — 기각: `collection` 의 "N 개 명시 room.yaml" 계약을 흐림. 전용 `structure` 서브커맨드가 분리·명료.
- **`ingest` 에 structure 백엔드 추가** — 기각: `ingest` 는 단일 RoomModel/room.yaml 출력 계약 — N-출력에 부적합.
- **지금 ADR 0047 `RoomModel` rewrite** — 기각: blast radius·golden 위험 불변; additive splitter 가 동일 가치를 near-zero 위험으로 제공.

## Follow-ups

- 측정 multi-room GT(per-room footprint/벽 위치)가 생기면 assignment heuristic 정확도 평가 + 집계 음향 재오픈(현재 가짜숫자 트랩).
- `openings` 배열 처리(현재 multiroom fixture 는 openings=0) — Phase S3 에서 wall 과 동일 경로로 추가.
- nested/인접 방 오배정 완화(예: floor-polygon containment 보조 신호) — GT 확보 후.
