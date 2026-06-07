# roomestim 상용화 분석 + 다음-스텝 플랜 (2026-06-06)

냉정 분석. 3개 독립 read-only 탐색(roadmap inventory / measured-path+acoustics maturity / downstream+integration)
근거. 자화자찬 배제. 모든 주장 file:line 추적 가능(에이전트 리포트).

## BLUF (냉정 판정)
roomestim 은 **코드 품질은 install-grade(mypy --strict clean, DoS 하드닝, 결정론적 placement, provenance 정직성
체인, 깨끗한 스키마 round-trip)** 이나, **제품으로서는 세 개의 foundational 갭 때문에 아직 팔 수 없다**:
1. **실제 캡처로 단 한 번도 검증된 적 없음.** 모든 테스트 픽스처가 합성 shoebox. 유일한 real-scan acceptance
   게이트(`lab_real.usdz`)는 픽스처 미커밋으로 **영구 SKIP**. → "벽 ±10cm cm-grade" 주장은 **실데이터 미입증**.
2. **measured 경로가 실제 디바이스 출력을 못 먹는다.** RoomPlan 어댑터는 **JSON 사이드카만** 파싱; 실제 Apple
   RoomPlan 산출물인 `.usdz` 는 `NotImplementedError`(roomplan.py:204). 즉 아이폰/아이패드 LiDAR 원본을 현재
   ingest 불가. mesh 어댑터의 `.usdz` 도 NotImplementedError(mesh.py:124).
3. **acoustics 는 research/demo-grade.** RT60 오차 최대 ±1.4s(Lecture_2 −0.9s), accuracy 게이트 없음(테스트가
   크기 아닌 순서만 assert), 재질은 전부 추정/UNKNOWN/하드코딩. → "정확한 음향" 주장 불가.

이 세 가지는 **어떤 제품 프레이밍에서도 선결**이다(특히 1·2). 흔히 frontier 로 본 image 백엔드(rough-tier)는
정직하게 라벨돼 있어 *위험이 아니라 이미 관리됨* — 진짜 상용화 블로커가 아니다.

## 무엇이 진짜고 무엇이 아닌가 (commercialization SWOT)
| 영역 | 상태 | 근거 |
|---|---|---|
| 코어 지오메트리 plumbing(RoomModel·adapters·export·round-trip) | **install-grade 코드** | mypy strict clean, 438 test def, DoS caps |
| provenance 정직성(measured/reconstructed/assumed, layout 경계 전파) | **견고**(이번 세션 강화) | model.py:141, x_geometry_provenance |
| placement VBAP/DBAP/WFS | 결정론·정확하나 **VBAP는 방 무시**(원점 링), listener=하드코딩 1.5×1.5m 단일 sweet-spot | vbap.py:6,111; listener_area.py:33 |
| RoomPlan(LiDAR) 실 디바이스 ingest | **불가**(.usdz NotImplemented; JSON 사이드카만) | roomplan.py:204 |
| 실제 캡처 정확도 검증 | **0건**(real-scan 게이트 영구 SKIP, 픽스처 전부 합성) | test_acceptance_lab_room.py:32 |
| acoustics RT60 | **research/demo-grade**(±1.4s, no accuracy gate) | perf_verification_e2e_2026-05-08.md:13 |
| 재질 추론 | **없음**(UNKNOWN/하드코딩만; visual classifier 0) | image.py:152, mesh.py:229, OQ-55 OPEN |
| 가구/객체 검출 | **없음**(objects=[] 하드코딩; RoomPlan은 column/door/window만, 의자/책상/소파 무시) | mesh.py:271, roomplan.py:151 |
| 불확실성(per-corner) 표면화 | **없음**(코드에 confidence/uncertainty 전무; OQ-57 미정의) | OQ-57 OPEN |
| multi-room | **없음**(RoomModel 단일방; RoomPlan floor_entries[0]만) | roomplan.py:262 |
| image 백엔드 | rough-tier(per-room ≤15cm 3-8%), **정직 라벨·게이트됨** | README, cli.py:420 |
| spatial_engine 통합 | 계약은 loose(additionalProperties), **배포는 하드코딩 절대경로**라 타 머신 happy-path 실패 | layout_yaml.py:58 |
| 배포 | **PyPI 미배포**(ADR 0007 deferred), room.yaml 은 아직 -draft, requirements 드리프트 | pyproject; ADR 0007 |
| 미구현 설계(designed-not-built) | ADR 0040 polygon-ISM / 0041 ambisonics / 0042 live-mesh / 0043 furniture-absorption = PROPOSED 코드 0 | docs/adr |

## 제품 프레이밍 3안 (플랜이 갈리는 유일한 지점 — 비즈니스 결정)
- **(A) B2B AV-인스톨러 프로 툴**: 입력=iPhone/iPad Pro LiDAR(RoomPlan) → 스피커 레이아웃 + (정직) 음향 리포트
  + CAD/engine export. measured 경로 의존. 필요=실 .usdz ingest·real-scan 검증·재질(수동 UI 또는 추론)·불확실성.
  음향은 "guidance, 보증 아님"으로 포지셔닝. **북극성 정합 최상(정확 공간추론)**.
- **(B) B2C 컨슈머 앱**: 입력=폰 사진/파노 → rough 레이아웃 → 스피커 제안. image 경로 의존. 필요=per-corner
  uncertainty(OQ-57)·캡처 가이드·cam_h 자동추정·UX. **정확도 리스크 최고**(rough), 신뢰 표면화가 생사.
- **(C) B2B SDK / spatial_engine 프런트엔드**: roomestim=더 큰 오디오 제품의 지오메트리+레이아웃 모듈. 필요=스키마
  경로 디커플·PyPI·room.yaml 스키마 freeze·버전 협상·real-scan 검증. **엔지니어링 최소, 시장은 spatial_engine에 종속**.

추천: **(A) 우선**, (C)는 (A)의 부산물로 동반(레이아웃 계약 정리). 근거: 북극성=정확 공간추론, 유일한 정확
경로=measured, 그리고 (A)/(C) 공통 선결이 곧 foundational 갭 1·2·3 해소다.

## 단계 플랜 (프레이밍 무관 Phase 0/1 먼저)
- **Phase 0 — 현실 검증(필수, 모든 프레이밍 공통, 최우선)**
  - 실제 캡처 1건(RoomPlan .usdz 또는 dense mesh) + ground-truth 확보·커밋 → SKIP된 acceptance 게이트 GREEN화.
    → "±10cm" 주장을 입증 또는 반증(반증이면 정직 하향). **이게 모든 정확도 주장의 게이트.**
  - acoustics 정직 포지셔닝: RT60을 "상대/guidance" 라벨로 명시 또는 명시적 비-게이트로 고지(이미 일부 됨).
- **Phase 1 — 디바이스 입력 갭 + 통합 하드닝**
  - 실 `.usdz` ingest 구현(RoomPlan parametric + mesh USDZ). measured 경로의 실사용 잠금 해제.
  - spatial_engine 스키마 경로 디커플(절대경로 제거 → 번들 fallback/config). PyPI-ready 패키징(ADR 0007 재개).
  - room.yaml 0.2 스키마 freeze(다운스트림 의존 시).
- **Phase 2 — 최대 정확도/기능 갭(프레이밍 (A) 기준)**
  - **재질 추론**(음향+사실성의 단일 최대 레버): RoomPlan 표면 카테고리 활용 + (image) visual material classifier
    타당성(OQ-55). 최소 coarse 분류라도.
  - 객체/가구: RoomPlan이 주는 것 와이어링(의자·책상·소파 무시 중단) + OQ-33.
  - 불확실성 표면화(OQ-57) — 양 경로 신뢰의 선결.
- **Phase 3 — 차별화**
  - image 백엔드 하드닝(cam_h 자동추정=최대 오차원 제거, 캡처 가이드), multi-room, ambisonics(dead enum 해소
    +OQ-38 round-trip), polygon acoustics(ADR 0040).

## 다음 즉시 액션 후보(Phase 0)
1. real-scan 픽스처 확보 경로 결정(실제 iPhone/iPad 스캔 가능? 또는 공개 RoomPlan/mesh GT 데이터셋?).
2. `.usdz` ingest 구현(measured 경로 실사용 잠금 해제) — 명확·유계 엔지니어링.
3. acoustics 정직 포지셔닝 문서/라벨 패스(저비용, 즉시).

## 사용자 결정 (2026-06-06)
- **프레이밍 = (A) B2B AV-인스톨러 프로 툴** (measured/LiDAR 경로가 코어).
- **Phase 0 데이터 = 공개 데이터셋**.

## Phase 0 착수 — 데이터 조사 + 첫 실-스캔 실행 (2026-06-06)
- **데이터셋 평가(document-specialist)**: 실내 실-스캔 GT 데이터셋 대부분 non-commercial. **ARKitScenes 가 유일하게
  (a) 센서 정합(iPad ARKit LiDAR = RoomPlan 파이프라인), (b) Faro 레이저 GT, (c) `.ply` 직접 ingest, (d) 상업 허용
  라이선스(<700M MAU, Apple)** — B2B 최적. 차선=ScanNet++(sub-mm GT, 단 non-commercial). 비-cuboid 스트레스=Structured3D(합성).
- **로컬에 이미 ARKitScenes 10 scene(4.9G)** 존재: `/home/seung/mmhoa/spike-vggt-multiview/data/arkit/raw/Validation/*/`
  각 `<id>_3dod_mesh.ply`(ARKit recon mesh) + lowres_wide. (VGGT 스파이크 OQ-53/59 잔여물.)
- **주의(검증 독립성)**: 스파이크 `eval_scene.py` 의 "GT" floor ring 은 동일 mesh 에서 **roomestim 로직(concave hull)**으로
  추출됨 → roomestim 검증에 재사용 시 tautological(≈0 오차, 무의미). **±10cm 검증엔 독립 GT(Faro highres, 로컬 미보유) 필요.**

### ★ Phase 0 첫 실행 발견 (HIGH — 실데이터 첫 실행이 P0 버그 노출)
roomestim **MeshAdapter 를 10개 실 ARKit mesh 에 실행**(canonical env, trimesh 4.12):
- 10/10 크래시 없이 ingest(provenance=measured) — 그러나 **ceiling_height_m 가 물리적으로 불가능: 6.5–9.6 m**
  (실제 방 ~2.4–3 m). 근본원인 **확인**: `mesh.py:202 ceiling_height_m = y_max - y_min` 가 **Y-up 을 하드코딩**,
  up-axis/gravity 정규화 전무. 그러나 ARKit mesh 는 **Z-up(gravity-aligned)** — 예: scene 41069048 축별 extent
  X=4.68·Y=3.80·**Z=2.51**(Z 가 진짜 수직, ~2.5m 천장)인데 어댑터는 Y extent(3.80, 긴 방은 6.5–9.6)를 "천장"으로 보고
  floor polygon 도 틀린 평면(X-Z)에서 추출.
- **= "install-grade" measured 경로의 P0 정확성 버그.** 합성 Y-up shoebox 픽스처만 있어 여태 안 보였음. .obj/.gltf/.glb/.ply
  소스마다 up-축 다름(glTF Y-up, ARKit/많은 export Z-up) → 정규화 없으면 실데이터에서 조용히 garbage.

### Phase 0 정제 플랜 (이 발견 반영)
- **0a (CODE, 최우선) up-axis/gravity 정규화** — MeshAdapter 에 up-축 자동검출(floor=최대 수평 평면 클러스터의 법선 /
  gravity; 단순 "최소-extent 축"은 길쭉한 방서 취약 → 평면-피팅 기반) + **실 ARKit mesh 회귀 테스트**(천장 ~2.4–3 m 범위
  assert; lab marker, 로컬 데이터 게이트). RoomPlan/ARKit 양 convention 처리.
- **0b (검증) 독립 GT 로 ±10cm** — ARKitScenes Faro highres(또는 ScanNet++ sub-mm) 다운로드 → 독립 GT 로 floor/wall/
  ceiling 오차 측정 → "±10cm" 입증/반증. 0a 후행.
- **0c (정직성) acoustics 포지셔닝** — RT60 "guidance/상대" 라벨 명시(저비용).

## RESUME POINTER (2026-06-07, autopilot — Phase 0c + Phase 1 DONE & COMMITTED)
프레이밍=B2B installer 확정.
- **Phase 0a DONE & 커밋됨(v0.25.3, `5064a8b`, D91)**: MeshAdapter up-axis 자동 정규화.
- **Phase 0c + Phase 1 DONE & 커밋됨(v0.26.0, `16759a3`, D92·D93; ADR 0027 §Status-update-2026-06-07)**:
  - **0c (acoustics 정직성)**: `_disclosure.py` 단일 진실원천 `RT60_DISCLOSURE`/`RT60_MODEL_NAME` + `RT60Prediction.disclosure`
    + export usd/gltf 사이드카 `disclaimer`/`acoustics_model`/`materials_status` additive 필드 + README "정직 고지(모델 추정,
    측정 아님/guidance)" 블록 + `test_rt60_disclosure.py`. RT60 수치 byte-불변(라벨만).
  - **Phase 1 (.usdz mesh ingest)**: `mesh.py` `_room_model_from_usdz`/`_vertices_from_usdz` + 공유 `_extract_room_model`
    리팩터(0a 정규화 재사용); `[usd]`/`[mesh-export]` extra(usd-core); `scripts/gen_usdz_fixtures.py` + `shoebox_{yup,zup}.usdz`;
    `test_adapter_polycam.py` .usdz 가 NotImplementedError→MeshAdapter 정상 파싱.
  - **리뷰 2R 반영(이번 세션, 검증완료)**: round-2 **[HIGH] metersPerUnit→m 스케일**(cm-unit USDZ 0.01 의 100× silent
    과대치수 차단) + upAxis 교차검증 + instance-proxy 순회; round-3 **[HIGH] default-prim 스코프 순회**(concrete `def`-prototype
    이중계수→8.96 m 팬텀 천장 차단; 독립 재현·수정 입증) + 천장 절대상한 `ROOMESTIM_MAX_CEILING_M`(기본 20 m) fail-loud.
  - 게이트 GREEN: default 387p/3s, web 86p/3s, ruff/mypy(strict) EXIT0. 독립 code-review(REQUEST-CHANGES→해소) + verifier.

**다음 = Phase 0b (독립 GT 로 ±10 cm 절대정확도 입증/반증)** — 여전히 미입증(상용화 최우선 게이트).
**★ 0b BLOCKED — 로컬에 독립 GT 없음 (2026-06-07 read-only 정찰로 확정)**:
- 로컬 10 Validation scene 전부 `metadata.csv` `has_laser_scanner_point_clouds=False` → Faro 레이저 GT 미보유.
  보유 자산 = ARKit *recon* mesh(=우리가 ingest 하는 입력, GT 아님) + RGB + trajectory + intrinsics 뿐.
- 스파이크 `eval_scene.py:122-129` 의 "GT" 는 `floor_ring.py`(roomestim `floor_polygon_from_mesh` 로직 **복사**)로 **같은
  mesh** 에서 추출 → tautological(self-validation), 재사용 금지 확정.
- 독립 GT 경로 3택(전부 외부 작업 필요): (A) ARKitScenes **laser-scan highres(Faro)** subset 다운로드(현 10 scene 과
  다른 scene ID, 진짜 ±10cm GT) — 다운로드+eval 셋업 필요; (B) ARKitScenes **3DOD annotation JSON**(`*_3dod_annotation.json`)
  다운로드 — 소용량이나 주로 가구 박스, room walls/ceiling 인코딩 여부 불확실(부분 GT 가능성); (C) **다른 벤치마크**(독립 GT
  보유)로 피벗. → **사용자 결정 대기**(다운로드 권한·용량·우선순위 vs Phase 2 선행).
그 다음(또는 0b 피벗 시) Phase 2(재질 추론·가구 와이어링·불확실성 OQ-57) — 외부데이터 없이 즉시 코딩 가능하나
플랜상 0b 가 "정확도 주장의 게이트"라 우선순위 충돌.

### Phase 0b 착수 (2026-06-07, 사용자 결정 = (A) Faro laser GT 다운로드)
- **데이터 발견 정정**: metadata.csv(5072행 전수)에서 `visit_id` 기준 **threedod ∩ laser = 1001 visit**, laser+3dod 행 3044개,
  Validation laser+3dod 365행 존재 → 로컬 10 scene 만 laser=False 였을 뿐, **둘 다 가진 scene 다수 존재**. (직전 awk 의 CR
  line-ending 버그로 0 으로 오판했던 것 교정.)
- **다운로드 경로 확보**: `apple/ARKitScenes` repo clone(`/tmp/ARKitScenes`), `download_data.py raw --split Validation
  --video_id <id> --raw_dataset_assets mesh annotation --download_laser_scanner_point_cloud`. base=docs-assets.developer.apple.com
  /ml-research/datasets/arkitscenes/v1. 후보(distinct-visit Validation): 42444946/421337, 42444966/421383, 42445021/421380,
  42445028/421378, 42445429/421372, 42445966/422022. 다운로드 위치=`.../data/arkit/phase0b/`.
- **독립성 보증(핵심)**: GT=**Faro 레이저 스캔**, 추정=roomestim MeshAdapter(**ARKit RGB-D recon mesh**) — **서로 다른 센서**
  (직전 스파이크의 same-mesh tautology 와 근본적으로 다름). GT 추출기는 roomestim 로직 미사용 독립 스크립트(수직 히스토그램
  peak=floor/ceiling, oriented-bbox=footprint). 비교지표: ceiling height(scalar, frame-free), floor OBB extent(회전불변),
  area. end-to-end(ARKit→roomestim vs laser-GT) 오차 = 실사용자 체감 오차 → ±10cm 게이트에 적합.
- **진행상태**: 1-scene(42444946) 다운로드 백그라운드 실행 중 → 파이프라인 검증 후 3+ scene 확장 예정.

### ★★ Phase 0b 결과 (2026-06-07) — ±10cm 주장 **반증(DISPROVEN)** + 2번째 measured 경로 P0 발견
**핵심 발견(독립 laser GT 앵커)**: scene 42444946 에서 roomestim 천장=4.370 m, **robust floor/ceiling 평면 peak-to-peak
=3.035 m**, **독립 Faro laser GT=3.034 m**(robust 와 1 mm 일치) → roomestim 이 **+1.335 m(44%) 과대**. laser 와
robust-mesh 가 1mm 일치 = 방은 실제 ~3.03 m, ARKit mesh 도 정확, **버그는 roomestim 추출**.
**5-scene 체계성 확인(robust 는 laser 앵커된 proxy GT)**:
| scene | roomestim천장 | robust/GT | 오차 |
|---|---|---|---|
| 42444946 | 4.370 | 3.035 | +1.335 |
| 42444966 | 3.039 | 2.309 | +0.729 |
| 42445021 | 2.760 | 2.331 | +0.429 |
| 42445028 | 2.614 | 2.340 | +0.274 |
| 42445429 | 2.610 | 2.276 | +0.334 |
→ **0/5 가 ±10cm 이내**. 평균 +0.62 m, median +0.43 m, max +1.34 m, **항상 양수(inflation)**.
**근본원인**: `mesh.py` `_extract_room_model` 의 `ceiling_height_m = y_max - y_min`(전체 수직 extent)가 floor/ceiling
**평면**이 아니라 scan outlier(가구·바닥아래·천장위 점, 관측 ~1-3%)를 천장으로 집계. **합성 shoebox 픽스처엔 outlier 0 이라
full-extent==robust → 여태 안 보임**(0a up-axis 와 동일 패턴: 실데이터 첫 노출). floor footprint(convex hull)도 outlier
inflation 가능성(2차 — 진짜 GT 엔 registration 필요, 후속).
**도구**(durable): `.../data/arkit/phase0b/gt_extract.py`(독립 GT 추출기, roomestim 미임포트), `mesh/<vid>/*.ply`(5 scene),
`laser_scanner_point_clouds/421337/*.ply`(Faro GT, 3 sub-scan).
**P0 fix DONE & 커밋됨 (v0.26.1 `29b9edf`, D94; ADR 0027 §Status-update-2026-06-07)**:
- full-extent→robust floor/ceiling **density-plane** 추출(`_robust_floor_ceiling_y`); floor/ceiling Surface lift 도 robust
  평면 사용(self-consistent). 합성 픽스처 byte-equal(outlier 0 → robust==full-extent). 잔여리스크(중간평면/under-sampled
  ceiling mis-pick) 정직 주석.
- **검증(독립 Faro laser GT)**: scene 42444946 fixed=3.02 m vs GT 3.03 m(~1 cm); 5-scene 천장 2.27–3.02 m(종전 2.61–4.37
  full-extent). 0a lab 회귀 bound 갱신(종전 full-extent 값은 inflated 였음) + 신규 synthetic outlier 회귀.
- 게이트 GREEN: default 388p/3s, lab 11p/3s, web 86p/3s, ruff/mypy EXIT0. code-review APPROVE-WITH-FIXES(MEDIUM/LOW 반영).
- **정직 하향(README)**: "정밀도 목표" 표에 독립 GT 검증 현황 — **천장 높이만 ±10 cm 실증, 벽/footprint 미검증**(registration
  후속), 종전 lab A11 GT 가 tautological 이었음 명시.
- **durable 도구**: `.../arkit/phase0b/gt_extract.py`(독립 GT 추출기), `mesh/<vid>/*.ply`(5 scene), `laser_scanner_point_clouds/
  421337/*.ply`(Faro GT). `/tmp/ARKitScenes`(다운로드 tooling, 휘발). 다운로드법=download_data.py raw --download_laser_scanner_point_cloud.

### ★ Phase 0b 후속 #1 결과 (2026-06-07) — footprint/wall 독립검증 = **NEGATIVE (ill-posed, 미검증 유지)**
**시도**: 단일 방 ARKit recon mesh(scene 42444946)의 footprint 를 독립 Faro 레이저 GT 와 비교하려 함. **핵심 발견**:
- **frame-free 단축경로 불가**: 천장 높이는 scalar(회전·평행이동 불변)라 frame-free 비교됐지만, footprint 는 그렇지 않음.
  레이저 GT 는 단일 방이 아니라 **건물 한 층 전체**(≈72×102 m, ~7000 m², 벽 ~856 m, 수직 ~24.6 m multi-floor)이고 ARKit mesh 는 그 안의 한 방
  (≈5.86×10.49 m, 둘레 ~31 m = venue 벽의 ~3.6%). 두 클라우드 좌표계 완전 비정합(ARKit 원점 근처, 레이저 Z≈455).
- **ARKitScenes 변환 없음**(확인): `_pose.txt` 는 레이저↔레이저 정합만(`raw/README.md`·`DATA.md:94`). ARKit↔레이저 변환 미제공
  → 방을 venue 좌표계로 **registration** 해야 footprint 비교 가능.
- **3가지 정합 방법 모두 신뢰 임계 미달**(robust negative, 단일 버그 아님): open3d **FPFH+RANSAC** 전역정합 ×2
  (floor 검출 버그 수정 후에도 ICP fitness 0.18~0.22), 중력제약 **2D yaw-sweep FFT** 정합(피크 margin ≈1.00× = 완전 모호).
  대형 multi-room 공간에 비슷한 직사각형 방 다수 → 초기추정 없는 단일-방→venue 배치는 ill-posed. 천장이 검증된 건
  height 가 floor↔ceiling **수평위치-불변 scalar** 라 floor+ceiling 평면 담은 임의 국소 sub-scan 으로 복원되기 때문
  (3.03 m GT = 전체 multi-floor venue[수직 ~24.6 m, full-venue robust peak-to-peak ≈6.1 m] 가 아니라 방과 같은 층 국소
  영역 값); footprint 는 수평 localization 필수 → 차이.
- **결정(정직)**: 잘못된 정합으로 *허위* ±cm 수치를 만들지 않음. footprint/walls = **미검증 유지**. README 정밀도-목표 §
  업데이트(시도·이유·종결경로 명시). 추가 구조적 한계 명시: roomestim footprint = **convex hull** → 비-convex 방 과대추정.
- **종결 경로**: (a) 방 단위 크롭 레이저/알려진 대응 seed, (b) 작은 단독공간 레이저 scene, (c) 근사위치 seed→ICP(seed 독립
  정당화 필수, 아니면 cherry-pick). 추가 레이저 scene 다운로드(후보 visit 6개)로 multi-scene 화도 가능하나 동일 ill-posed.
- **durable 도구**(spike 디렉터리, roomestim repo 밖): `…/arkit/phase0b/footprint_validate.py`(Tier1 frame-free, OBB),
  `footprint_register.py`(open3d FPFH+RANSAC+ICP, 신뢰게이트), `footprint_register2d.py`(중력제약 2D FFT). 격리 venv
  `/tmp/o3d-venv`(open3d 0.19, 휘발). roomestim 코어 코드 **무변경**(README+plan doc-only).

### ★ Phase 2 착수: 가구 음향 배선 완료 (v0.27.0, D95; 2026-06-07 autopilot)
**스코프 결정(정직)**: Phase 2 3항목 중 **재질 추론**(measured mesh 는 외형데이터 부재 → 기하만으론 불가; RoomPlan
material_hint 는 이미 배선; 진짜 추론은 visual classifier=OQ-55, 저신뢰 제안만)과 **OQ-57 per-corner 수치**(‘가짜 숫자 금지’
계류, calibration 미정)는 정직하게 빌드 불가로 판정. **가구 음향 배선**만 honest·bounded 로 구현(사용자 승인).
**구현**: `ObjectKind` += `sofa`/`bed`/`table`/`storage`. 가구 = column 과 동일 **free-standing box**(`_objects_to_surfaces`
5-face)로 RT60 흡음 예산에 반영; RoomPlan sidecar `_extract_objects` 가 카테고리 매핑(sofa/couch·bed·table/desk·
storage/cabinet/shelf/wardrobe/refrigerator; chair·toilet 제외). 단일 진실원천 `FREESTANDING_OBJECT_KINDS`/
`WALL_ATTACHED_OBJECT_KINDS`(model.py) 를 predictor·gltf·usd·room.yaml reader·`proto/room_schema.v0_2.draft.json` 공유.
재질=대표 추정(soft→MISC_SOFT 0.40, hard wood→WOOD_FLOOR 0.10), bbox-solid ESTIMATE 정직 라벨(open-frame table 과대계수
honesty note 포함). **기존 픽스처 RT60 byte-equal**(어떤 adapter 도 가구 미방출 → 순수 additive).
**검증**: default **396p/3s**(388→+8 furniture), web 86p/3s, ruff/mypy EXIT0. 독립 **code-review APPROVE-WITH-FIXES**:
HIGH(room schema 가구 enum+oneOf 미확장 → 직렬화 round-trip 깨짐) 독립 발견·수정(schema-validated write↔read 테스트 추가);
MEDIUM(table solid-box 과대계수) honesty-note 반영; LOW×2(rationale 문자열·zero-depth degeneration=schema 가드됨) skip.
**남은 Phase 2 (정직 defer)**: 재질 추론(OQ-55 visual classifier 필요), per-corner uncertainty(OQ-57 calibration).

### ★ Phase 2 후속: 천장 confidence flag 완료 (v0.28.0 `6f7bd1f`, D96; 2026-06-07 autopilot)
**구현**: `mesh.py:_robust_floor_ceiling_y` 가 docstring 으로 명시했던 deferred 개선 — 잔여 mis-pick failure
mode(topmost-dense bin 이 tabletop/mezzanine/under-sampled 천장이면 height UNDER-report)를 **annotate(보정
아님)**. `RoomModel.ceiling_coverage`(float|None, honest 기하측도=검출 천장밴드 ±10cm 가 floor footprint 25cm
그리드 셀 덮는 vertex-occupancy 비율) + `ceiling_confidence`(high/low/unknown, **0.50 보수 임계 HEURISTIC, NOT
calibrated**·합성픽스처만 검증). 단일진실원천 `CEILING_CONFIDENCE_HEURISTIC_NOTE`(`_disclosure.py`). threading=
RoomModel 2필드(least-claim None/"unknown")·usd/gltf sidecar 3키·room.yaml **conditional emit**(coverage is not
None=measured 일 때만→비-mesh golden byte-equal)+reader coupling+schema optional props·CLI stderr NOTE(3 사이트,
low 일 때만). **ceiling_height_m·RT60 무변경.** 측도는 deliberately CONSERVATIVE(false 'low' never false 'high').
**검증**: 클린 픽스처 7/7 coverage 1.000/high 실측(과대주장 방지 empirical), mis-pick 합성 0.176/low. default
**408p/3s**(396→+12), web 86p/3s, ruff/mypy EXIT0. 독립 code-review(opus) **APPROVE — 0 CRIT/HIGH/MED, 3 LOW
전부 커밋 전 수정·재게이트**: LOW-1 docstring 과대주장(occupancy 측도라 low-poly 천장도 low) 정정·LOW-2
writer/reader 비대칭(hand-authored confidence-without-coverage rewrite drop) reader coupling+회귀테스트·LOW-3
finite-check XZ→XYZ. 세부=`.omc/plans/ceiling-confidence-flag.md`.

**다음 후보**: (1) ~~footprint/wall 독립검증~~ → NEGATIVE(데이터 한계, 종결경로 (a)/(c) 필요).
(2) ~~가구 음향 배선~~ → 완료(v0.27.0). (3) ~~ceiling mis-pick confidence flag~~ → 완료(v0.28.0).
(4) 실제 .usdz RoomPlan parametric furniture ingest(현재 sidecar JSON 만; .usdz=geometry mesh 만; parametric
CapturedRoom USD 픽스처 부재로 검증난이도↑). (5) OQ-55 visual material 제안 스파이크(저신뢰, auto-commit 금지).
(6) image cam_h 자동추정(최대오차원 제거, Phase 3).
캐노니컬 게이트 = `/home/seung/miniforge3/bin/python -m pytest -m "not web and not vision and not lab and not e2e"`
(PATH pytest 아님; **408p/3s** 가 default 베이스라인(v0.28.0), web 86p/3s).

### ★ RESUME POINTER (2026-06-07 autopilot — 3-candidate 후속 완료) — 세부 = `.omc/plans/commercialization-followups-3candidates.md`
프레이밍=B2B installer. planner(opus)→executor(opus)→독립 code-review(opus)→full-gate 검증. 3개 후보 = 1 ship + 2 정직 DEFER.
- **(6) image cam_h = SHIPPED**: 단일 파노는 원리적 scale-ambiguous(cam_h=global scale, `r=cam_h/tan(-v_floor)` 정확
  선형) → 절대 cam_h 복원은 빌드 불가. 대신 **검증가능한 scale-honesty 기구**만 추가: `image.py::_cam_h_sensitivity`
  (torch-free·정확가역; max_radius_coeff/plausible cam_h window/scale_pct_per_10cm) + anchor-미공급시 ASSUMED 경고를
  `IMAGE_CAM_H_SCALE_NOTE`(`_disclosure.py` 단일진실원천)+민감도 인용으로 확장. **user/anchor cam_h silent override 0**,
  provenance="reconstructed" 불변. plan item(3) floor-plane cross-estimate 는 floor 폴리곤이 cam_h 에 **scale-invariant**
  (직각제약 포함 over-determine 안 함)임을 증명하고 **DEFER**(가짜숫자 방지). 검증갭(244 GT 100% cuboid→non-Manhattan
  정확도 주장 금지) ADR 0045 §honesty 명문화. **테스트 6 추가(default 408→414p/3s, torch-free, vision 마커 불요)**,
  web 86p/3s, ruff/mypy EXIT0, code-review APPROVE.
- **(4) parametric .usdz ingest = DEFER**: 리서치(인용) 결론 — RoomPlan parametric **시맨틱은 USD 에 없음**(CapturedRoom
  JSON + iOS17 String→UUID 매핑파일로 out-of-band). `.usdz`=geometry-only(이미 MeshAdapter ingest), 시맨틱=sidecar 가
  이미 커버 → 후보 자체가 moot/정직빌드불가. `roomplan.py:225` NotImplementedError 메시지를 정직·정보형으로 개선(테스트는
  NotImplementedError catch→skip 이라 안전). 재오픈=실 export `.usdz`+매핑JSON 확보 시. 근거=`.omc/research/oq4-roomplan-parametric-usd-defer.md`.
- **(5) OQ-55 visual material = DEFER(no-commit spike)**: 리포트 `.omc/research/oq55-visual-material-feasibility.md`.
  블로커=in-repo material/absorption GT 0 → 정확도 검증불가 → 주장금지. 트랩=material→absorption→RT60 직결 numeric
  파이프라인(오라벨=가짜 음향수치). 향후 빌드시 계약=opt-in·ESTIMATE·RT60-neutral-unless-accepted·image-only, **별도 태스크**.
- **side-fix**: 오토메모리 `reference_canonical_test_env.md` 에 캐노니컬 게이트 = **marker-scoped** 명문화(plain `pytest -q`
  =over-collect 오측정). 베이스라인 체인 275/6→388/3→396/3→408/3(→이번 414/3).

### ★ RESUME POINTER (2026-06-08 autopilot — 4-candidate A/B/C/D) — 세부 = `.omc/plans/commercialization-followups-4candidates.md`
사용자 지시 = 4개 코드-only 후보 전부 진행. planner(opus) 정직 스코핑 → A/B/D 완료, C 미착수(세션 한도).
- **(A) spatial_engine 절대경로 디커플 + PyPI-ready = DONE**(`d3457c5` v0.30.0 D98): `layout_yaml.py` 머신-특정 하드코딩
  기본경로 제거→`SPATIAL_ENGINE_REPO_DIR` env-only, 미설정 시 fail-loud(기존 3 escape-hatch). 격리 venv wheel build+install+
  콘솔스크립트+torch-free import 검증(PyPI-*ready*, publish 는 ADR 0007 여전히 deferred). conftest 머신-독립 sibling 상대탐색.
  grep `/home/` in roomestim/ = 0. code-review APPROVE-WITH-FIXES(stale 주석 2건 수정). default 414→416p/3s.
- **(B) multi-room 유계 슬라이스 = DONE**(`3a02d7e` v0.30.1 D99): RoomPlan `floor_entries[1:]` silent drop→`ROOMPLAN_MULTI_FLOOR_NOTE`
  (단일진실원천) UserWarning 로 고지(primary 만 사용, merge 안 함=기하수치 미생성). 순수 additive(len==1 무경고, `-W error` 검증).
  RoomModel/schema/export 무변경. 진짜 RoomCollection 은 ADR 0047 에 blast-radius 와 함께 DEFER(제품은 single-room). default 416→418p/3s.
  **독립 code-review 는 세션 한도로 차단→다음 세션 검토 예정**(커밋은 -W error 가법성증명+test추적+guard추적 자체검증).
- **(D) cam_h known-size-reference prior = DEFER(doc-only)**(`66e0953` D101): auto=detector+verifiable prior 부재+cuboid-GT 검증불가;
  manual=기존 `--cam-height` 와 동일 prior 를 마찰만 늘려 재생산·정확도 이득 0. ADR 0045 §honesty (D) 기록. 코드 0줄.
- **(C) polygon-ISM geometry-only = DONE**(`c6eb9fd` v0.31.0 D100): core `polygon_image_source.py`(numpy/shapely-only,
  pyroomacoustics import 0) `first_order_image_sources(...) -> list[ImageSource]` — 벽/floor/ceiling 미러링 1차 이미지 POSITION +
  shapely on-segment 가시성. **POSITION 만, RT60 0**, predictor/image_source 무변경(shoebox byte-equal). `POLYGON_ISM_GEOMETRY_NOTE`
  단일진실원천. 검증=known shoebox→해석적 mirror ~1e-9 + L-shape non-convex pruning. 전체 RT60 cascade 는 non-shoebox 측정 GT 부재로
  ADR 0040 §Status-update DEFER. code-review APPROVE-WITH-FIXES 4 LOW 반영(docstring 과대주장·denom/is_valid fail-loud 가드+테스트).
- **(B 후속) 독립 code-review = DONE**(`ed9fae2` v0.30.2): 보류됐던 B 리뷰 실행 APPROVE, 2 LOW 반영(stacklevel=3 귀속·parse()-path warns 테스트).
- **새 default 베이스라인 = 433p/3s @v0.31.0**(414→+19: A+2, B+2, B후속+1, C+14). web 86p/3s 불변. **origin/main 푸시 완료.**

### ★ 외부 데이터 수집·검증 (2026-06-08 autopilot) — commercial-OK 데이터로 2건 실측 검증
사용자 지시="외부 데이터 최대한 긁어모아서 해봐". document-specialist 데이터 인벤토리(commercial-OK 우선) →
실행 2건(둘 다 가짜숫자 금지·실측·정직 caveat). 데이터셋 인벤토리 핵심: 음향 GT 는 **dEchorate·BUT ReverbDB·
MeshRIR(전부 CC-BY)**·ACE(CC-BY-ND, 이미 배선)·Motus(가구 RT60) 가 commercial-OK; geometry 독립 laser 는
ARKitScenes 가 사실상 유일 commercial-OK(Matterport/ScanNet/ScanNet++/InLUT3D=non-commercial); 비-cuboid
image GT(Structured3D/ZInD)=대개 research-only.
- **(검증 1) C polygon image-source ↔ dEchorate 실측 echo (commit `8b0b074`, doc; ADR 0040 §실측검증)**: v0.31.0 C
  enumerator 의 1차 image-source **geometry** 를 실 측정 cuboid 방의 annotated echo TOA 로 검증 → median per-wall
  **5.60 cm**(south 1면 제외 3.88 cm), 데이터셋 noise floor(direct 2.8 cm) 수준. 벽/floor/ceiling mirror path-length
  실측 일치. 비볼록 visibility·RT60 미검증(geometry-only). 근거 `.omc/research/dechorate-polygon-ism-validation.md`.
- **(검증 2) measured(mesh) 천장높이 ↔ ARKit 5-scene 독립 Faro laser GT**: phase0b 5 scene 의 laser GT 를 4 proxy→
  **5 true-laser** 로 업그레이드(다운로드 ~56GB). 결과(정직): **2/5 = GT-ambiguous**(Faro 가 multi-floor 건물 전체라
  naive robust peak 가 6.1/6.7 m 건물밴드 반환 → 헤드라인서 제외, 날조 안 함); **clean 3 scene: median |err| 3.6 cm,
  2/3 ≤±10 cm**, 가장 깨끗한 2개 1.0/3.6 cm(phase0b ~1cm 와 일치). v0.28.0 `ceiling_confidence` 는 5/5 high — 오작동
  아님(roomestim 자체 추정 3.02/2.41 m 가 plausible single-room, 불일치는 laser-GT multi-floor 추출 artifact).
  **결론: clean GT 에선 천장 ~1–4 cm 로 견고하나, N-scene laser 확장은 footprint 와 동일한 multi-floor localization
  한계로 막힘**(room-local laser crop 필요). 근거 `.omc/research/arkit-5scene-ceiling-laser-validation.md`.
- **다음 데이터 레버(미착수)**: BUT ReverbDB(CC-BY 8.7GB, 9방 측정 RIR+박스치수→RT60 predictor 정직 오차한계),
  Motus(가구 config RT60→v0.27.0 흡음 검증), MeshRIR. 전부 commercial-OK. RT60 정확도 주장은 이 데이터로만 가능.

**★ 4-candidate 사이클 종료 — A/B/C/D 모두 정직하게 해소(2 ship-feature + 1 ship-geometry + 1 doc-defer + B후속).**
**다음 후보(전부 외부데이터 또는 대형 refactor 의존)**: PyPI publish(ADR 0007 reverse-criteria 미발동), 진짜 multi-room RoomCollection(ADR 0047
phased+픽스처), polygon-ISM RT60 cascade(non-shoebox 측정 GT 필요·ADR 0040 §G/OQ#2), cam_h known-size prior(non-cuboid GT+detector·ADR 0045 §D).
즉시 코드-only 후보는 소진됨 — 다음 레버는 데이터 확보(real-scan/측정 RT60 GT)가 게이트. 우선순위 사용자 결정.

---

**(구) 다음 후보 (위 A/B/D 로 진행, C 잔여)**: (4)/(5) 재오픈은 외부데이터 의존(실 RoomPlan export+mapping / material GT). 코드-only =
image cam_h known-size prior(→D DEFER), multi-room(→B 유계+ADR 0047 DEFER), spatial_engine 디커플+PyPI(→A DONE), polygon-ISM(→C 잔여).
