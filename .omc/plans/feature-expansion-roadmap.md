# roomestim Feature-Expansion Roadmap & Resume State

> **목적**: 2026-05-29 전체 스모크 분석 이후의 멀티-페이즈 자율 실행 추적 파일.
> 세션이 끊겨도 이 파일만 읽으면 정확히 어디서 재개할지 알 수 있다.
> **재개 규칙**: 아래 "현재 위치" 포인터 → 해당 Phase의 미완료 체크박스부터 이어간다.
> 각 Phase는 OMC 파이프라인(planner/architect → executor → code-reviewer/critic → verifier)을 따르고,
> verifier는 **전체 게이트**(default + web + ruff + mypy --strict + tense-lint)를 재실행한다.

---

## 현재 위치 (RESUME POINTER)

- **ACTIVE PHASE**: ✅ ALL DONE — Phase 1~6 완료 (2026-05-29). 설계 사이클 종료.
- **마지막 GREEN 게이트**: ADR 0043 + open-questions 갱신 후 tense-lint clean (EXIT=0). ADR 카운트 41. Phase 6 최종 게이트는 아래 §Phase 6 참조.
- **완료 산출물**: ADR 0040(B4 polygon ISM), 0041(B5 Ambisonics), 0042(B6 live-mesh), 0043(B7 흡음 가구) — 4개 모두 REVISED + critic 반영. README v0.22.1. open-questions §Feature-expansion 엔트리 4건 + 종합.

> 매 Phase 완료 시 이 블록을 갱신한다.

---

## 사용자 지시 (원문 의도)

1. 스모크 분석 결과 저장 ✅ (이 파일 + project memory + 아래 §분석 스냅샷)
2. README 갱신 (Phase 1)
3. B 항목(기능확장 4종)을 **차례로 하나씩 모두 설계** (Phase 2~5) — 산출물은 **설계 문서/ADR**
4. README 이후 기능확장 설계를 **차례로 자동(auto) 실행**
5. 모든 진행을 저장하여 중단되어도 재개 가능하게

---

## Phase 0 — 분석 저장 ✅ DONE (2026-05-29)

- [x] 전체 엔드투엔드 스모크 (CLI 5종 + 웹 전 산출물 + 음향 예측기 3종) 실행 → 전부 GREEN
- [x] 게이트 baseline 기록 (default 287p/5s, web 67p/4s, ruff/tense clean)
- [x] 분석 스냅샷을 이 파일 §아래에 보존
- [x] project memory에 스모크 결론 저장 (`feature_expansion_roadmap_2026_05_29.md`)

## Phase 1 — README 갱신 (ACTIVE)

목표: README의 stale 내용을 v0.22.1 실상태로 교정. **신규 기능 추가 아님, 문서 정직성 교정.**
교정 대상:
- [ ] 상단 "현재 상태" 테이블: v0.14 → v0.22.1 최신 행 추가/갱신
- [ ] RT60 예측기 절: "v0.14 default predictor는 Sabine" → "shoebox default predictor는 ISM" (실측 확인됨)
- [ ] ADR 카운트: "0001~0028 / 28개" → 실제 37개 반영
- [ ] decisions 카운트: D1~D35 → 실제 D73까지 반영 (요약만)
- [ ] CLI 입력 backend 설명: `--backend {roomplan,polycam}` 현실 반영 (polycam = MeshAdapter alias)
- [ ] export `--format {yaml,usdz,gltf,glb}` + `--with-acoustics-sidecar` + 엔진검증 토글 문서화
- [ ] edit 서브커맨드의 재질/오브젝트 편집(evolve_*) 능력 반영 (현 README는 스피커 nudge만 기술)
- [ ] 테스트 카운트 갱신 (default 152 → 287 등)
- [ ] honesty-leak lint 통과 유지 (한국어 본문 OK, 영문 present-tense 출시 framing 금지)
- [ ] **게이트 재실행 GREEN 확인** (verifier) — README는 lint scope 포함
- [ ] 커밋 (사용자가 명시 요청 시에만; 기본은 작업트리에 남김)

## Phase 2 — 설계: B4 Polygon / Non-rectilinear ISM ✅ DONE (2026-05-29)

목표: shoebox 전용 ISM을 비직각 폴리곤 방 + coupled-space로 확장하는 **설계 문서** 작성.
- [x] architect: 현 `roomestim/reconstruct/image_source.py` (shoebox ISM) 구조 분석 + 확장 표면적 정의
- [x] 알고리즘 비교 (자체 mirror-ISM vs pyroomacoustics 재사용 vs hybrid) → 권장 pyroomacoustics(b)
- [x] coupled-space(Building_Lobby) 처리 방침 — critic가 marker 부재 + Building_Lobby=shoebox 사실 정정
- [x] OQ-15/OQ-13b 연결 + ADR 0030 reverse-criterion item 3 충족 경로
- [x] ADR 0040 draft 작성 (docs/adr/0040-polygon-ism-design.md)
- [x] critic 리뷰 (1 CRITICAL + 3 MAJOR) → 전부 반영 → REVISED 확정
- [x] open-questions.md §Feature-expansion 사이클에 OQ-23 재기재 + 파생 OQ 제안 기록
- 결론: 권장 = 선택지 b(pyroomacoustics) + C2(core lazy-import) + 3-티어 cascade. 구현 deferred(PR1-4).

## Phase 3 — 설계: B5 Ambisonics 배치 ✅ DONE (2026-05-29)

목표: 현 enum stub(`algorithm.py: AMBISONICS`)을 정식 4번째 배치 알고리즘으로 만드는 **설계 문서**.
- [x] architect: VBAP/DBAP/WFS dispatch 구조 + engine schema/ipc_schema 분석
- [x] order(1st/2nd/3rd) ↔ n_speakers((N+1)² 하한) ↔ t-design/platonic 레이아웃 매핑
- [x] target_algorithm=AMBISONICS round-trip(OQ-38) — x_target_algorithm extension key로 종결 제안
- [x] ADR 0041 작성 (docs/adr/0041-ambisonics-placement-design.md)
- [x] critic 리뷰 (ACCEPT-WITH-RESERVATIONS, 0 CRITICAL+3 MAJOR) → 전부 반영 → REVISED
- [x] open-questions.md §Feature-expansion 사이클에 B5 엔트리 + 파생 OQ 기록
- 결론: (a)안(디코더 리그 배치) + engine 디코딩 위임 + x_target_algorithm OQ-38 종결. PR2 전 engine 라우팅 gate.

## Phase 4 — 설계: B6 Live-mesh corner 추출 ✅ DONE (2026-05-29)

목표: synthesized-shoebox tautology 를 실제 메시 코너 추출로 대체하는 **설계 문서** (OQ-13e).
- [x] architect: floor_polygon.py(stub, 호출처 0) + mesh.py 인라인 convex hull + walls.py extrusion 분석
- [x] alpha-shape(권장) / RANSAC / Hough / convex 비교 + 비볼록은 추출단 문제임을 규명
- [x] corner err ≤ 10cm 검증 = 합성 L-shape 메시(SoundCam 불요), convex byte-equal 회귀
- [x] ADR 0042 작성 (docs/adr/0042-live-mesh-corner-extraction.md)
- [x] critic 리뷰 (2 CRITICAL: D6 mislabel + 메시생성기 부재; 3 MAJOR) → 전부 반영 → REVISED
- [x] open-questions.md §Feature-expansion 에 B6 엔트리 + OQ-13e 부분 resolution 기록
- 핵심 정정: convex-hull deferral 출처 = D6(오) → ADR 0027 + OQ-13e(ii)(정). D74 로 mislabel cleanup 제안.

## Phase 5 — 설계: B7 가구 자동 인식 / ObjectKind 확장 ✅ DONE (2026-05-29)

목표: ObjectKind(column/door/window) → 흡음 가구(sofa/bookshelf 등) 확장 + 자동 클러스터링 **설계 문서**.
- [x] architect: Object 모델 + DEFAULT_OBJECT_MATERIAL + ACE equivalent-absorption + roomplan _extract_objects + OQ-33 분석
- [x] 흡음 가구 모델 = ACE equivalent-absorption-area(ADR 0013), ISM 은 sabin 직접 누적(B-2)
- [x] B7-A(enum 수동) / B7-B(자동: RoomPlan sidecar 저비용, mesh 클러스터링 deferred) 경계 정의
- [x] ADR 0043 작성 (docs/adr/0043-absorptive-furniture-objectkind.md)
- [x] critic 리뷰 (1 CRITICAL: B-1 ISM α-희석 결함; 2 MAJOR) → 전부 반영 → REVISED
- [x] open-questions.md §Feature-expansion 에 B7 엔트리 + 종합 기록
- 핵심: D26-YAGNI → 검증(가구 RT60 영향)을 enum 확장보다 선행. ISM 은 B-2(sabin) 필수.

## Phase 6 — 종합 마무리 ✅ DONE (2026-05-29)

- [x] 4개 설계 문서 cross-link 정합성 확인:
  - **B6(0042) → B4(0040)**: live-mesh 가 비볼록 floor 추출 시 RT60 은 B4 polygon ISM/Eyring 트랙으로 (상호 cross-ref 기재).
  - **B5(0041)**: OQ-38 round-trip(x_target_algorithm)으로 독립; engine 디코딩 위임.
  - **B7(0043)**: Object→음향 경로가 B4 predictor cascade(ISM/Eyring) 위에서 동작 — B7 의 sabin 누적이 B4 shoebox/polygon ISM 양쪽과 정합.
- [x] 공통 패턴: 4개 모두 (i) 기존 추상화 무수정/회귀-0 우선, (ii) critic 가 사실 오류·물리 결함 적발→REVISE, (iii) honesty(미구현=PROPOSED, 미확인="확인 불가").
- [x] 최종 게이트: 코드 무변경 → default/web pytest 불변; 문서 tense-lint clean(EXIT=0) 전 ADR 확인.
- [x] 사용자 보고.

### 구현 우선순위 권고 (다음 단계)
1. **B7-A 검증-선행** (저렴·즉시 가치, D26 게이트): ACE 룸 가구 흡음 RT60 영향 측정 → ±20% 잠식 입증 시 enum 개방. ISM 은 B-2(sabin) 필수.
2. **B5 PR1 (x_target_algorithm)**: OQ-38 종결 — ambisonics 와 독립 가치, engine 라우팅 합의 gate.
3. **B6 alpha-shape**: 신규 의존 0, convex default 보존(회귀 0). 비-tautological 메시 생성기 선결.
4. **B4 polygon ISM**: 최대 작업(pyroomacoustics core lazy-import, D29 레인 결정 planner 필요).
> 4개 모두 Status=PROPOSED. 구현 착수 전 각 ADR §Reverse-criterion + blocking gate 확인.

---

## 분석 스냅샷 (2026-05-29 스모크 결론)

### 게이트 baseline
- default: 287 passed, 5 skipped (`pytest -m "not lab and not web and not e2e"`)
- web: 67 passed, 4 skipped (`pytest -m web`)
- ruff: clean / tense-lint: clean
- canonical python: `/home/seung/miniforge3/bin/python`

### 현 기능 (검증됨)
- CLI 5종: ingest / place / export / run / edit
- 입력 5포맷: .usdz / .obj / .gltf / .glb / .ply (point-only 비메싱)
- 배치 3종: vbap / dbap / wfs (+ AMBISONICS enum stub)
- RT60 예측 3종 + 6밴드: Sabine / Eyring / **ISM (shoebox default)**
- 재질: 10-entry MaterialLabel + octave band
- 편집: 스피커 nudge + 재질교체 + 오브젝트 add/remove + surface edit (immutable evolve)
- 웹: Gradio + HF Spaces — 3D viewer / 음향리포트 / 바이노럴(HUTUBS·KEMAR) / setup PDF / ZIP
- 공개 코퍼스: ACE Challenge / SoundCam

### lab_room.obj 실측 (V=40 m³, shoebox)
- default(ISM) RT60 @500Hz = 1.594 s
- Sabine = 1.238 s, Eyring = 1.193 s
- default predictor rationale: "shoebox L=4.00 W=4.00 H=2.50: per-band ISM (max_order=50)"

### 확인된 유일 실질 이슈
- README.md stale: v0.14 / Sabine-default 표기 (실제 v0.22.1 / ISM-default). → Phase 1 교정 대상.

### B 항목 설계 대상 (우선순위순)
- B4 Polygon/non-rectilinear ISM (shoebox 한계 확장 — 최대 물리정확도 이득)
- B5 Ambisonics 배치 (4번째 알고리즘, enum stub 정식화)
- B6 Live-mesh corner 추출 (OQ-13e — synthesized tautology 대체)
- B7 가구 자동인식 / ObjectKind 확장 (흡음 가구 → RT60 정확도)

### 관련 OQ (open)
- OQ-46 (web pip-audit + lockfile), OQ-40 (gradio col_count), OQ-35 (USDZ/glTF 음향메타), OQ-37/38 (edit round-trip 충실도), OQ-13e (live-mesh), OQ-13b/OQ-15 (glass-heavy predictor)
