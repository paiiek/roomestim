# Plan — ① Acoustics ISM upgrade + 동반 추천 기법 (2026-06-24)

RESUME POINTER. 진실원천 = `.omc/research/usable-tech-SYNTHESIS-2026-06-23.md` + facet6 addendum.
요청: "① 음향 ISM 업그레이드 + 리서치한 쓸 수 있는 기법 중 뭘 하면 좋을지 플랜."

## 0. 냉정한 프레이밍 (먼저 읽을 것)
- **핵심 진단**: 현 코드는 이미 정직하다. `materials.py`에 Sabine/Eyring **단일+per-octave-band 둘 다 존재**(`MaterialAbsorptionBands`). `image_source.py`=shoebox ISM RT60(단일+per-band). `polygon_image_source.py`=비-shoebox **geometry-only, RT60 의도적 DEFER**(사유=비-shoebox **측정 RT60 GT 부재**, ADR 0040 §G).
- ⇒ **"ISM 업그레이드"의 진짜 블로커는 코드가 아니라 검증 GT.** 단순히 polygon RT60 magnitude를 emit하면 NO-FAKE-NUMBERS 원칙 위반. 이 플랜은 **GT로 엔진을 먼저 검증**한 뒤에만 새 수치를 노출한다.
- **북극성 정렬**: roomestim 북극성 = 공간추론 강건성 + **스피커 레이아웃**. RT60은 수단(청취충실도 아님, Phase B/C 저우선). ⇒ 동반 추천 기법은 북극성에 더 직접 정렬되는 **스피커 레이아웃**으로 제안. 음향은 "demo-grade→정량수치" 정직성 업그레이드로서 가치.
- 모든 단계: OMC(planner→executor→code-review→verifier), 풀 게이트 재실행, additive/MINOR, NO FAKE NUMBERS, 합성픽스처 byte-equal 보존.
- 베이스라인: 695p/7s @ v0.44.0(`2a07832`). canonical 게이트 = `/home/seung/miniforge3/bin/python -m pytest`.

---

## TRACK A — 음향 ISM 업그레이드 (① 본체)

### A1. RT60 엔진 검증 하니스 (★keystone, 低위험, 외부데이터 CC-BY)
- **무엇**: ARNI(Zenodo 6985104, CC-BY) + dEchorate(Zenodo 5562386, CC-BY) 다운로드 → 기존 `sabine_rt60_per_band`/`eyring_rt60_per_band`/`image_source_rt60_per_band`(shoebox)를 **측정 RT60 vs 예측** 으로 정량 평가. ARNI=단일 rect, 5342 흡음패널 구성(흡음→RT60 민감도 gold). dEchorate=cuboid 6 흡음구성.
- **출력**: README/disclosure의 "ESTIMATE / demo-grade"를 **측정 기반 정량 오차범위**(예: "shoebox, 알려진 흡음 → ±N% T30")로 교체. 이건 새 추정수치가 아니라 **측정 GT 대비 검증수치** → NO-FAKE-NUMBERS 준수.
- **왜 keystone**: 이후 모든 음향 작업(polygon RT60, calibration)이 "엔진이 known-material에서 얼마나 맞나"를 먼저 알아야 정직하게 쌓인다.
- **산출물**: 검증 스크립트(.omc/research 또는 tests/eval, gitignored 데이터), 결과 표, disclosure 문구 패치. 코드코어 무변경 가능.
- **위험**: 낮음. 데이터 다운로드(수 GB) + 파싱. 라이선스 CC-BY 확정.
- **게이트**: 검증은 out-of-gate eval(데이터 의존). disclosure 문구 변경은 default 게이트 byte-equal 확인.

### A2. Polygon RT60 (pyroomacoustics) — ★GT-gated, 中위험
- **무엇**: `polygon_image_source.py`의 DEFERRED RT60을 pyroomacoustics `Room.from_corners()+extrude()`(v0.10.1, MIT, `RoomModel.footprint`에 직접매핑)로 비-shoebox RT60 emit. 다대역 흡음(pyroomacoustics materials MIT) + hybrid ISM+ray.
- **★게이트 조건(반드시)**: 비-shoebox **측정 RT60 GT가 있을 때만** 수치 노출. 후보:
  - MP-RIR(보유, CC-BY, 비-shoebox polygon 측정 RIR) — 단 **재질/천장 GT 부재** → RT60 magnitude 검증 부분적. geometry(TOA/visibility)는 이미 검증됨.
  - FLAIR(Zenodo 17037517, mm laser+270 RIR) — **라이선스 확인이 선행 액션**. CC-BY면 최강 비-shoebox geo+RIR GT.
- **honest fallback**: GT가 magnitude를 못 잡으면 → RT60은 계속 DEFER 유지하되, **엔진 코드는 들여놓고 "unverified, gated behind measured GT" 라벨**로 둔다(ADR 0040 §G 연장). A1에서 shoebox 엔진오차는 정량화돼 있으므로 "shoebox 검증 ±N%, 비-shoebox는 미검증" 정직고지.
- **위험**: 중. 핵심 리스크 = 비-shoebox magnitude GT 부족 → 부분 DEFER 가능성. 코드는 들어가도 노출은 보수적.
- **결정 필요**: FLAIR 라이선스 확인 결과 + MP-RIR 재질 배정 가능성에 따라 "노출 vs 계속 DEFER" 갈림.

### A3. blind-rt60 측정 백엔드 + Acta Acustica 보정 (`roomestim[audio]`, 低~中위험)
- **무엇**: `[audio]` extra 신설(`blind_rt60` MIT + soundfile). 폰 녹음(박수/소음 5–10s) → 측정 RT60. + **Acta Acustica 2025 closed-form 보정**(constrained LS/MLE, ~50줄): 기하 흡음 prior를 측정 RT60 제약에 투영(≤1 JND). geo추정 옆에 측정치 표시 + 불일치 플래그 + 보정.
- **왜 좋은가**: 측정 기반이라 정직(추정 아님). off-the-shelf 라이브러리 부재 = roomestim 차별화. 재질 systematic bias(±40–60% soft 표면)를 측정으로 제거.
- **검증**: ACE corpus(CC-BY-ND, Zenodo 6257551)로 blind_rt60 정확도 벤치(±200–350ms 실측 기대). clap+`measure_rt60()`는 ±50–100ms.
- **위험**: 낮음(옵셔널 extra, core 무변경). blind_rt60 정확도가 낮으면 "calibration sanity-check"으로 포지셔닝(replacement 아님).

**Track A 권고 순서**: A1(keystone) → A3(독립가치 높음, GT 덜 필요) → A2(GT-gated, FLAIR 라이선스 확인 후).

---

## TRACK B — ★동반 추천: 스피커 레이아웃 (북극성 직접정렬, 低위험)

리서치한 기법 중 **가장 추천**. 이유: roomestim 북극성의 명시적 출력("정확한 공간추론 + **스피커 레이아웃**"). 음향보다 북극성 정렬도 높고, 동일하게 低위험·코드-only·commercial-OK·기존 방 polygon 소비. OSS turnkey 부재(=차별화 여지). 음향(SPL/RT60)과 자연스럽게 연결.

### B1. Geometric grid 옵티마이저 (AVIXA 공식, 低위험)
- **무엇**: 방 polygon + 천장고 + 스피커 분산각 → 커버리지 그리드 좌표. `Coverage = (H_ceil−H_ear)·tan(θ/2)`, spacing≈1.5×H, 오버랩 background 15%/speech 20–25%. shapely+numpy ~수십줄. square/hex 그리드.
- **출력**: `SpeakerLayout`(좌표 리스트 + 커버리지 메타) RoomModel 부가. CLI 노출.
- **위험**: 낮음. 결정론적·설명가능(AV 인스톨러 친화).

### B2. SPL 커버리지 스코어링 + 옵셔널 최적화 (中위험)
- **무엇**: 리스너 그리드에서 direct-SPL 분산 스코어 → 선택적 `scipy.differential_evolution`(비정형 방). pyroomacoustics(이미 [web] dep)를 SPL 오라클로. AVIXA ±3dB 균일도 타겟.
- **위험**: 중. 목적함수 구축. 기하 direct-sound로 충분(반사 무시 초기).

### B3. 비정형 레이아웃 렌더 (spaudiopy MIT / DBAP, 低위험)
- **무엇**: `[spatial]` extra(spaudiopy MIT). 제안 좌표 `(x,y,z)` → VBAP/AllRAD 디코딩 행렬. 설치환경(sweet-spot 없음)엔 **DBAP**(~50줄 자작)가 ceiling-only 그리드에 강건. roomestim 이미 ambisonics/DBAP 보유(v0.39.0) → 재사용/확장.
- **위험**: 낮음. 옵셔널.

**Track B 권고 순서**: B1 → B3 → B2.

---

## 제외/연기 (이 사이클 밖)
- **기하 frontier (VGGT+GTSAM global BA)**: 북극성 진짜 레버이나 **research spike·中~高위험**(video-only ≤15cm는 문헌 미해결, 팀이 TSDF/coverage 벽 반복 경험). **별도 스코프 스파이크**로, **先 AMB3R LICENSE 확인**(Apache면 drop-in 평가). 이 저위험 사이클과 분리.
- **RoomFormer measured non-convex**: 中위험, density-image 컴포넌트+검증 필요. Track A/B 후.
- **영상→흡음(AV-RIR)**: 시뮬only·hard표면만 신뢰·회귀모델 부재 → DEFER.

---

## ★RESUME POINTER (다음 세션) — 2026-06-24 갱신
- **user 승인: A1 + B1 부터 실행** (AskUserQuestion 응답 "A1 + B1 부터(추천)"). 실행은 OMC.
- **현재 phase: A1·B1 설계/스카우팅 에이전트 dispatch 완료, 산출물 회수 중.** 아직 코드 무변경.
  - B1 planner(opus) agentId=`af29d8f212b5bd88e` — 스피커 grid 구현스펙. **결정 D-1~D-4 대기 상태로 종료**(스펙 본문 미회수 → SendMessage로 회수 필요).
  - A1 scientist(opus) agentId=`a9039cb43e5bd621d` — 검증하니스 타당성+설계. "complete"로 종료(리포트 본문 미회수 → SendMessage로 회수 필요).
- **즉시 다음 액션**: 두 agentId에 SendMessage로 ① B1 스펙 + D-1~D-4 결정사항 ② A1 dEchorate/ARNI 다운로드 go/no-go + 엔진 API맵 + 하니스 설계 회수 → executor 착수.
- 결정 갈림 잔존: A2 polygon RT60 노출 = FLAIR(Zenodo 17037517) 라이선스 확인 의존(아직 미확인).
- 베이스라인 695p/7s @ v0.44.0. 게이트=`/home/seung/miniforge3/bin/python -m pytest`.
