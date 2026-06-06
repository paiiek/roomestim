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

## RESUME POINTER (2026-06-07)
프레이밍=B2B installer 확정. **Phase 0a DONE & 커밋예정(v0.25.3, D91)**: MeshAdapter up-axis(gravity) 자동 정규화
(planar-density 판별자 + fail-loud 모호성 가드 + `up_axis` override) — 실 ARKit 10 scene 천장 6.5–9.6 m→2.49–3.69 m 수정.
독립 code-review 2R(HIGH narrow-room→해소, MEDIUM sparse-narrow→fail-loud) + verifier VERIFIED-GREEN. default 368p/6s.
**다음 = Phase 0b(독립 GT 로 ±10 cm 절대정확도 입증/반증)**: ARKitScenes Faro highres 또는 ScanNet++(sub-mm, non-commercial)
다운로드 → 독립 GT 로 floor/wall/ceiling 오차 측정. (주의: 스파이크 `eval_scene.py` GT 는 roomestim 로직 파생이라 재사용 금지.)
그 다음 Phase 0c(acoustics "guidance" 정직 라벨), Phase 1(실 `.usdz` ingest + 스키마 절대경로 디커플 + PyPI), Phase 2(재질 추론
·가구 와이어링·불확실성 OQ-57).
