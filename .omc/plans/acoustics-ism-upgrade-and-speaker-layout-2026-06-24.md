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

## ★RESUME POINTER (다음 세션) — 2026-06-24 갱신 #5 (B4 DONE, 성능평가 기반, 다음=A3)

- **v0.45(B1)·v0.46(A1)·v0.47(B2) 전부 PUSHED.** user: 성능평가 후 "B4→A3 순차".
- **★성능평가(현실 B2B 방 5종×grid×overlap)**: B1 nominal coverage grid 실측 바닥 커버리지 = **평균 69~75%·최저 53%**(1-D AVIXA spacing 의 2-D 대각 갭). A1 음향은 이미 검증(Spearman 0.90)·북극성 아님 → 북극성 출력(레이아웃) 약점부터 해결 결정.
- **B4 = DONE (v0.48.0, MINOR additive), 커밋 직전 code-review 대기.** B1 의 under-cover 를 측정 수렴으로 정직 해결.
  - (1) `place_coverage_grid` additive `spacing_scale`(default 1.0=byte-equal, `(0,1]`). (2) 신규 `place/coverage_complete.py` `place_coverage_grid_to_target`: B2 overlap 오라클을 목표(default 0.9)까지 spacing ×0.9 조밀화, 수렴/cap honest, `CoverageTargetResult`. (3) CLI `--coverage-target` + 미지정 시 <85% stderr 경고. ADR 0054.
  - 실증: meeting 6×5 54%(4spk)→97%(12spk) MET, retail 66%→95%. `COVERAGE_COMPLETE_NOTE`(SPL 무주장). 게이트 default **755p/7s**(+13), 내 모듈 ruff·mypy clean.
  - ⚠️ 워킹트리에 **다른 동시 세션의 untracked WIP**(`roomestim/adapters/multiview.py`·`roomestim/geom/surface_distance.py`·`tests/test_aconsumer_multiview.py`·`.omc/autopilot/spec-aconsumer-multiview.md`, "A-consumer multiview" 기능) 존재 — 그 파일에 mypy strict 2 에러(내 것 아님). 내 커밋은 내 파일만 스테이징, 그들 파일 무접촉.
- **A3 진행중 (blind-rt60 `[audio]` extra).** ★feasibility 1차출처 검증: `blind-rt60` PyPI v0.1.1 **License MIT 확인**(plan 주장 정확), 블라인드 RT60(Ratnam et al. ML), deps=scipy/numpy/matplotlib(전부 보유). soundfile 0.9.0 로컬有(web extra >=0.12).
  - **증분 1 = DONE (v0.49.0, library-only, code-review 대기→커밋예정)**: `[audio]` extra + `reconstruct/measured_rt60.py`(`measure_rt60_from_audio`/`_from_signal`→`MeasuredRT60`, lazy import, subprocess 로 core dep-light lock) + `MEASURED_RT60_NOTE` 단일진실원천 + mypy override + `tests/test_measured_rt60.py`(importorskip, 정확도 단언 X). 합성 0.5s→0.48s 스모크 OK. ★CLI 미배선(cli.py 동시세션 경합 회피). default 764p/7s, mypy(63)·ruff clean, ADR 0055.
  - **증분 2(defer)**: Acta Acustica 2025 closed-form 보정(geo prior→측정 RT60 제약 투영) + ACE corpus(CC-BY-ND, Zenodo 6257551) 정확도 벤치(외부 다운로드 의존).
- 베이스라인 **755p/7s @ v0.48.0**.

### (이전) 갱신 #4 (B1 PUSHED + A1 + B2 DONE, B3 정직 DEFER)

- **v0.45.0(B1) PUSHED `a12d64c`. v0.46.0(A1) PUSHED `670a304`.**
- **B2 = DONE (v0.47.0, MINOR additive).** B1 이 보류한 "±3 dB 균일도 검증"을 **절대 SPL 발명 없이** B1 의 coverage-원 기하 검증으로 닫음.
  - 신규 `roomestim/place/coverage_overlap.py` `score_coverage_overlap`: 청취평면 footprint 격자 샘플링 → 각 점 coverage-원(반경=B1 `coverage_radius_m`) 포함 개수 → `fraction_covered`(≥1, 갭)·`fraction_overlap_2plus`(≥2)·`worst_point_xz`. `--algorithm coverage` 가 `layout.coverage.json` 의 신규 `overlap` 키 + `--coverage-grid-res-m`(기본 0.5). `coverage_to_dict` byte-equal.
  - ★설계 pivot 실증: 원안 direct-SPL 분산은 **근접장 피크 지배로 비견고 + 절대 SPL GT 부재**(구현 후 기각) → coverage-원 오버랩(B1 spacing 이 유도된 양)으로 정직 전환. ★실측 발견: B1 의 1-D AVIXA spacing 은 **2-D 에 대각 갭**(square/background 기본 8×6 m 방 ~51% 만 커버, r 1.20<셀반대각 1.44 m). 단일진실원천 `COVERAGE_OVERLAP_NOTE`(SPL 무주장). ADR 0053.
  - 게이트 GREEN: default **727p/7s**(715→+12 `tests/test_coverage_overlap.py`), web 86p/3s, ruff·mypy(--strict 59) clean, CLI E2E OK. 독립 code-review APPROVE(3 LOW non-blocking 반영: 문구완화 "AVIXA target"→"≥2-circle share", perf/worst_point docstring 노트).
- **B3 = 정직한 scoped DEFER (구현 안 함).** B3(spaudiopy/DBAP decode matrix for proposed coords)는 **roomestim 아키텍처 경계 위반**: roomestim 은 layout 기하만 방출하고 **decode/gain matrix·SH 인코딩은 엔진 책임**(ambisonics 모듈이 명시: "does NOT compute decode matrix... 엔진 책임, end-to-end contract UNCONFIRMED" — ADR 0041 §D-3a). B3 를 지으면 동일 UNCONFIRMED 계약을 요구 + 엔진 책임 중복. DBAP placement(v0.39.0)·coverage grid 좌표는 이미 layout.yaml 로 엔진에 흐름. ⇒ 가짜 계약으로 out-of-scope 기능 짓지 않음(NO FAKE CONTRACT). 재오픈 조건=엔진 라우팅 계약 확정 시.
- **다음 후보**: (Track A) A3 blind-rt60 [audio] extra(측정 RT60 백엔드, GT 덜 필요) / A2 polygon RT60(FLAIR 라이선스 확인 선행, GT-gated). (Track B 소진: B1✓ B2✓ B3=scoped DEFER). 또는 북극성 frontier(VGGT+GTSAM, 별도 스파이크).
- 베이스라인 **727p/7s @ v0.47.0**. 게이트=`/home/seung/miniforge3/bin/python -m pytest`.

### (이전) 2026-06-24 갱신 #3 (B1 PUSHED + A1 DONE)

- **v0.45.0 (B1) = PUSHED** to origin/main (`a12d64c`, user 승인).
- **A1 = DONE & COMMITTED (v0.46.0, MINOR additive).** dEchorate(Zenodo 5562386, CC-BY-4.0 둘다 검증) 측정 GT로 shipped shoebox RT60 엔진 2차 독립검증.
  - 하니스 `tests/eval/rt60_validation.py`(out-of-gate, no `test_` funcs) + committable GT `tests/eval/data/dechorate_gt.yaml`(transcribed+cited, 500/1000Hz 체크섬 일치). 전체 provenance+results = `.omc/research/_data/`(gitignored). 엔진 코드 BYTE-EQUAL.
  - **결과(n=40)**: diffuse-field Sabine/Eyring가 측정 RT60 ORDERING 강하게 추적(Spearman ρ≈0.90, Pearson 0.97, 0.14–0.81s). 절대정확도 미확립: ISM 반사방 과대예측(MAPE~103%, DR~11× 과대), Sabine 과소예측(MAPE~28%). 사전확정 go/no-go(§3.5) = **NO-GO 절대band / GO trend**. 근본원인=alpha-input gap(dEchorate 재질명만, alpha無; 반사α 0.10까지 올려도 ISM 58%). ARNI/polygon DEFER 유지.
  - disclosure(`_disclosure.py` RT60_DISCLOSURE 단일진실원천)에 측정기반 dEchorate 문장블록 추가(trend-valid+absolute-DEFER+named uncertainty), substring 계약 보존. ADR 0028 §Status-update(2026-06-24) 기록.
  - 게이트 GREEN: default **715p/7s**, web 86p/3s, ruff/mypy clean. 독립 code-review APPROVE(2 LOW 해소: 하니스 mypy 정리 + Zenodo ID 검증).
- **다음 = B2/B3 스피커 레이아웃 확장**(Track B 권고순서 B1→B3→B2; B1 SHIPPED). B2=SPL 커버리지 스코어링(pyroomacoustics direct-SPL grid, AVIXA ±3dB), B3=비정형 렌더(spaudiopy/DBAP, 기존 v0.39.0 리그 재사용). 둘 다 additive/MINOR, 기존 방 polygon+B1 그리드 소비.

### (이전) 2026-06-24 갱신 #2 (B1 SHIPPED)
- **B1 = DONE & SHIPPED v0.45.0** (local commit `a12d64c`, ★NOT pushed — push를 auto-mode classifier가 차단, user 명시승인 필요). 이전 세션 design agent(af29.../a903...)는 cross-session 회수 불가 → fresh 재dispatch(디스크 Write 계약)로 복구.
  - 스펙: `.omc/plans/b1-coverage-grid-design-2026-06-24.md`. 구현: `roomestim/place/coverage_grid.py`(shapely+math, numpy조차 불요) + `--algorithm coverage` (place/run) + `layout.coverage.json` 사이드카 + ADR `docs/adr/0052-coverage-grid.md`.
  - room-aware AVIXA 천장 커버리지 그리드(square/hex, half-spacing 인셋, centroid-in-polygon 클립, tiny-room representative_point 폴백). COVERAGE_GRID_NOTE 단일진실원천, SPL/±3dB 무주장(B2 defer), NO FAKE NUMBERS. 기존 VBAP/DBAP/WFS/ambisonics 리그(room-independent)와 별개. additive byte-equal.
  - 게이트 GREEN: default **715p/7s**(695→+20), web 86p/3s, mypy --strict clean(58), ruff clean, CLI E2E OK. planner→executor(opus)→code-review(opus) APPROVE×2 + main 독립 게이트/코드리드/E2E.
- **A1 = 설계완료, 미실행.** 스카우팅 리포트 `.omc/research/a1-rt60-validation-harness-design-2026-06-24.md`. 권고: dEchorate(Zenodo 5562386, CC-BY) FIRST — make-or-break PASS(RT60 Table 5 in-paper, 6x6x2.4 shoebox, bands=roomestim 1:1, 84GB 다운로드 불요), ROUTE-RAW on `image_source_rt60_per_band`. ARNI(6985104) 2nd=sensitivity(per-panel alpha 부재·50GB). go/no-go 사전확정(§3.5): 현실 likely=GREY tier(trend/relative validity, 절대정확도 DEFER). 최대리스크=alpha-input gap(둘 다 per-surface alpha 미동봉).
- **즉시 다음 액션 후보**: (1) user가 push 승인 → origin/main; (2) A1 실행(dEchorate harness, out-of-gate eval, 셔링엔진 무변경, 디스클로저 문구만 측정기반 교체); (3) A3 blind-rt60 [audio] extra; (4) A2 polygon RT60=FLAIR(17037517) 라이선스 확인 의존.
- 베이스라인 **715p/7s @ v0.45.0**. 게이트=`/home/seung/miniforge3/bin/python -m pytest`.
