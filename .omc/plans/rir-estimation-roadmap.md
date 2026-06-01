# roomestim RIR-Estimation Research & Design Roadmap — Resume State

> **목적**: roomestim에 RIR(Room Impulse Response) estimation을 붙이는 연구+설계 사이클의 멀티-페이즈 추적 파일.
> 세션이 끊겨도 **이 파일만 읽으면** 정확히 어디서 재개할지 알 수 있다. (필수지침 2026-05-30)
> **재개 규칙**: 아래 "현재 위치(RESUME POINTER)" → 해당 Phase의 미완료 체크박스부터 이어간다.
> 매 Phase·중요 단계 완료 시 RESUME POINTER 블록을 **즉시** 갱신한다 (몰아서 아님).

---

## 현재 위치 (RESUME POINTER)

- **ACTIVE PHASE**: ✅ **Phase 3 (구현) 완료 — RIR auralization Phase A v0.23.0**. planner(gate해소)→executor(구현)→code-reviewer(MAJOR발견)→executor(fix)→verifier(독립 APPROVE, MAJOR fix load-bearing 증명). 커밋/푸시 진행. Phase B(neural late) / Phase C(differentiable fitting)는 여전히 out-of-scope deferred.
- **진행상태**: planner ✅ blocking gate 전부 해소 — §E spike 실측(compute_rir broadband-only + measure_rt60 ~6× 오차 → **image-source 직접조립** 확정, OQ-48 RESOLVED), §D 수용(OQ-47 verification-deferred), §A 5ms-window energy-continuity 규약. 플랜 `.omc/plans/rir-auralization-phase-a.md`(5 step, 12 accept test A1~A12, 버전→0.23.0). **executor 구현 中**.
- **plan 핸들**: planner agentId=a7c923cf108cb3b73. executor agentId=a22fe74da0c7e6df1. 편차3건(D1 8-band 슬라이스 damping[0:6], D2 compute_rir 기각, D3 rng default_rng(seed+band)).
- **executor ✅**: rir.py(222L)+late_reverb.py(152L)+binaural.synthesize_brir(additive, 데모경로 무변경) + 14 web 테스트(A1~A12+A11b). 버전 0.23.0, D79, ADR0044 §SU(Proposed→Accepted), OQ-48 CLOSED. 게이트 GREEN(default 300p/5s=core회귀0, web 82p/4s, ruff/mypy/tense EXIT0). **A11 deviation**: plan의 "broadband decay=max RT60±10%"는 비균일 RT60룸에서 물리적으로 거짓 → per-band contract(각 밴드 자기 RT60 ±10%)로 정정 + A11b 추가. → code-reviewer ✅(A11 deviation LEGITIMATE 확인). **MAJOR 1건**: Gate3 splice-continuity 가 real-HRTF BRIR 에서 위반(ch1 3.22dB>3dB), A12는 mono경로만 검증·BRIR테스트는 synthetic unit-impulse HRTF라 scale mismatch 가려짐. + MINOR(silent-band tail drop, dead import, ADR 문구, n_bands). → executor 수정 ✅(MAJOR: per-channel late-tail energy renorm, ch1 3.22dB→0.033dB; silent-band fallback; dead import 제거; ADR/D79 문구정정; n_bands drop; +2 load-bearing test). 게이트 GREEN(default 300p/5s, web 84p/4s, ruff/mypy/tense EXIT0). code-reviewer agentId=a74ea0316e7928b3b, fix executor agentId=a63f7a0a3af525c11. → verifier 최종검증 中.
- **마지막 GREEN 게이트**: v0.22.2 전체 GREEN(default 300p/5s, web 68p/4s, ruff/mypy/tense EXIT0), 커밋 `2eae5eb` 푸시됨.
- **완료 산출물**: Phase 1 리서치 + Phase 1.5 스파이크 + **ADR 0044 REVISED** + OQ-47~51 등록.
- **다음 행동**: planner 플랜 → executor(rir.py + late_reverb.py 신규, web-tier, 신규패키지0) → code-reviewer → verifier(전체 게이트) → green까지 반복. 커밋은 사용자 요청대로 진행.
- **확정 사실(재확인 불요)**: ADR=**0044 REVISED**. OQ=**47~51 등록완료**. tense-lint clean. 재질·ISM=6-band. 판정=GO-WITH-CAVEATS. critic agentId=aca25e5c9f10f7cce(이어쓰기 가능). 세션한도 리셋 6:50am Asia/Seoul.

### 재개에 필요한 핸들 (워크플로우 복원용)
- deep-research Task ID: `wkw4jvy81`
- Run ID: `wf_4fd35c52-5db`
- scriptPath: `/home/seung/.claude/projects/-home-seung-mmhoa-roomestim/0c32d454-1b60-4be5-b81c-fc72a09a31ed/workflows/scripts/deep-research-wf_4fd35c52-5db.js`
- 재개 명령(중단 시): `Workflow({scriptPath: "<위 경로>", resumeFromRunId: "wf_4fd35c52-5db"})` — 완료 에이전트는 캐시 반환
- 워크플로우가 결과 없이 죽었으면: 같은 args로 deep-research 재실행 (args는 §스코프 참조)

> 매 Phase 완료 시 이 블록을 갱신한다.

---

## 스코프 (확정 — AskUserQuestion 2026-05-30)

- **접근 패러다임**: **Hybrid physics-neural** — 기하/파동 시뮬레이션(ISM/ray/FDTD)을 physics prior로, 신경망이 late-reverb·고차반사·잔차 보정. 순수 geometric / 순수 neural-field(NAF·INRAS)는 경계용으로만, hybrid 중간지대를 깊게.
- **목표 용도**: **Auralization / 청취** — convolvable, 지각적으로 충실한 RIR. perceptual + objective(RT60/EDT/C50/C80/DRR, EDC fit, log-spectral) 평가.
- **산출물**: 리서치 리포트 + **roomestim 통합 설계 ADR 0044** (PROPOSED; ADR 0040~0043 컨벤션 = Reverse-criterion + blocking gate + honesty).

### roomestim 보유 자산 (hybrid의 physics 절반)
- (a) 기하 복원: scanned mesh(RoomPlan/Polycam, .usdz/.obj/.gltf/.ply) → room polygon + walls
- (b) 재질: per-surface octave-band 흡음 (10-entry MaterialLabel)
- (c) RT60: Sabine / Eyring / shoebox ISM(default, 6-band); polygon ISM 확장 설계(ADR 0040, pyroomacoustics lazy-import)
- (d) 바이노럴: HUTUBS·KEMAR HRTF; B5 Ambisonics 배치 설계 중(ADR 0041)
- (e) 스피커 배치 최적화: VBAP/DBAP/WFS
- → "geometry→RIR"은 거의 공짜. 연구 질문 = **neural late-reverb 보정이 의존성·데이터 비용 대비 가치 있는가**.

---

## Phase 1 — Deep Research ✅ DONE (2026-05-30)

목표: hybrid physics-neural RIR(auralization 지향) SOTA·도구·sim-to-real gap·few-shot 보정을 인용기반으로 조사.
- [x] deep-research 워크플로우 5단계 완료 (Run wf_4fd35c52-5db; 105 agents, 23 sources, 25 verified→20 confirmed/5 refuted)
- [x] 결과 리포트를 `.omc/research/rir-estimation-2026-05-30.md` 로 저장
- [x] 핵심 발견 요약을 본 파일 §연구 발견 스냅샷에 보존
- [x] RESUME POINTER 갱신 → Phase 2

조사 5각도(예상): ① hybrid 방법론(DiffRIR/Hearing Anything Anywhere, differentiable ISM/ray, early-ISM+late-neural, FiNS/neural-FDN) ② auralization 평가지표 ③ 도구·데이터셋(pyroomacoustics/gpuRIR/Treble/Steam Audio; dEchorate/BUT/SoundSpaces) ④ sim-to-real gap ⑤ few-shot 보정 vs blind 합성.

## Phase 2 — 통합 설계 ADR 0044 (PENDING)

목표: 리포트 기반으로 roomestim 통합 경로 ADR 작성 (OMC: architect→draft→critic→verifier).
- [ ] architect: 현 ISM/pyroomacoustics early-reflection + HRTF 렌더 위에 RIR auralization 얹는 표면적 정의
- [ ] build-vs-borrow: neural late-reverb 부분 (자체 vs 기존 모델), 의존성·학습데이터 현실성
- [ ] few-shot 보정 = 실측 RIR 필요 여부 명시
- [ ] ADR 0044 draft (docs/adr/0044-...): Status=PROPOSED + **Reverse-criterion**(어떤 증거면 neural 절반 버리고 pure-physics RIR로 가는가) + blocking gate
- [ ] critic 리뷰 → REVISE
- [ ] open-questions.md 에 RIR 엔트리 + 파생 OQ
- [ ] 게이트: 코드 무변경이면 tense-lint clean(EXIT=0) 확인. canonical python `/home/seung/miniforge3/bin/python`
- [ ] 커밋 (사용자 명시 요청 시에만)

## Phase 3 — (조건부) 구현 착수

ADR 0044가 implement now로 결론 + 사용자 승인 시에만. 그 전까지 설계-only.

---

## 스파이크 결과 (Phase 1.5, 2026-05-30, architect read-only)

**판정: GO-WITH-CAVEATS** — Phase A는 core-engine 리팩터가 아니라 *대체로 깨끗한 graft*. web-tier 한정, 신규 패키지 0.

### 정정 2건 (이전 가정 틀림)
- ❌ **"6-band ISM ↔ 10-band 재질 mismatch"는 거짓.** 재질·ISM 모두 균일 6-band octave (`model.py:75/86/154` = 125/250/500/1k/2k/4k). 10→6 손실투영 없음. (오히려 demo 렌더가 `_resolve_damping_scalar` binaural.py:80-94 에서 6밴드를 500Hz 스칼라로 *축소* 중 — Phase A는 이걸 멈추고 6밴드 유지.)
- ⚠️ **core ISM(`image_source.py`)은 RT60 스칼라/per-band dict만 반환** (image list/RIR 없음, Q1=옵션c). 단 **web `binaural.py`가 자체 pyroomacoustics ISM을 live 실행**하며 `pra_source.images`(시간) + `pra_source.damping`(per-band 감쇠)를 이미 접근(binaural.py:292,308-309). 즉 early-reflection 데이터는 web-tier에 살아있음.

### A. 이미 가진 것
- early reflections(per-image time+per-band atten): binaural.py:308-309 (live)
- per-band T60: `predict_rt60_default_per_band` → `RT60Prediction.rt60_per_band_s` 6-band dict (predictor.py:87,525)
- HRTF: `nearest_hrir` 방향 인덱스 룩업, 48kHz (hrtf_io.py:217)
- pyroomacoustics 0.10.1 설치됨, `Room.compute_rir()` 존재하나 **미호출**(design-only, ADR 0040)

### B. Phase A까지 gap (sized)
| 조각 | 크기 | 위치 |
|---|---|---|
| mono early-RIR builder (image→impulse train, 또는 compute_rir()) | S | new `roomestim_web/rir.py` |
| **FDN/filtered-noise late tail** (어떤 dep도 FDN 미제공, 직접 작성) | L(FDN)/M(filtered-noise) | new `roomestim_web/late_reverb.py` |
| per-band T60→decay-gain handoff | S | late_reverb.py |
| mixing-time 추정 (echo density 부재 — analytic √V 1차) | S/M | rir.py |
| early+late splice (truncate@t_mix) | S | rir.py |
| **mono-RIR→BRIR convolver** (현 HRTF는 discrete-direction만) | M | binaural 확장 |

### C/D. 최대 결정요인
**diffuse late-tail → BRIR** (B 마지막 항). FDN tail은 DOA 없음 → 현 `nearest_hrir`(방향 인덱스)에 안 맞음 → diffuse-field binaural(2-HRIR decorrelation / IC-shaped noise) 신규 필요. 나머지는 재사용/소형. 팀이 2-HRIR decorrelation 근사 수용 시 near-clean GO.

### E. 권장 ADR 0044 scope
- web-tier, **신규 패키지 0** (scipy+numpy로 충분), 2개 소형 모듈: `rir.py`(early 조립+√V mixing-time+splice) + `late_reverb.py`(per-band T60 구동 tail).
- **v1 late = filtered-noise** 권장 (M, deterministic, byte-equal 테스트 친화, FDN 튜닝/coloration 리스크 회피). FDN은 follow-on.
- **6밴드 전부 유지** (스칼라 축소 명시적 배제), `predict_rt60_default_per_band`를 T60 단일 진실원천으로 재사용(리포트 RT60과 auralization tail 일관).
- gating OQ: **diffuse-tail binauralization 전략** (early=per-DOA `nearest_hrir`, late=2-HRIR decorrelation; perceptual 검증을 신규 OQ로). `image_source_model()` vs `compute_rir()` 결정 — compute_rir() 권장하되 RT60 일관성 spike 선결(ADR 0040:67 sparse-RIR measure_rt60 미검증 플래그).
- scope는 Phase A 엄수 (학습데이터 0, 측정 0). neural late는 Phase B로 out-of-scope.

---

## 연구 발견 스냅샷 (2026-05-30, 전문 = .omc/research/rir-estimation-2026-05-30.md)

### 두 dominant 패턴 (둘 다 roomestim 적용 가능)
- **A. Differentiable inverse-rendering**: physics 렌더러 파라미터를 backprop로 소수 실측 피팅. DiffRIR(CVPR2024)=방당 **~12 monaural RIR** + planar 복원 → monaural+binaural 렌더. AV-DAR(2025)=multi-view 시각 prior, 10× 적은 데이터로 pure-neural 필적(C50/T60 위주).
- **B. early(ISM/RT)+late(FDN/filtered-noise) 분해**: RAZR(2014)=geometry+material만, 측정 0, ISM+FDN binaural = **pure-physics baseline**. neural late = DecayFitNet+VFM-FDN(DAFx2025, scattering 보완), differentiable FDN(EURASIP2024).

### roomestim 핵심 인사이트
- roomestim은 이미 hybrid의 **physics 절반** 보유(기하+**6밴드** 재질+ISM+HRTF). → "geometry→RIR"은 거의 공짜. [스파이크 정정: 재질·ISM 모두 6-band, 10-band 아님]
- sim-to-real gap의 핵심 = **late tail diffuseness + scattering** (ISM specular-only). DAFx2025 VFM이 이걸 타겟.

### 권고 단계 (ADR 0044 시드)
1. **Phase A (최저비용·신규데이터 0·측정 0)**: 기존 ISM/pyroomacoustics early + per-band T60(Sabine/Eyring/ISM)로 **RAZR식 FDN late tail** + HUTUBS/KEMAR HRTF → convolvable binaural RIR.
2. **Phase B (중간)**: DecayFitNet식 neural late / VFM-FDN scattering 보정 graft (specular tail gap 보완).
3. **Phase C (고비용)**: DiffRIR식 differentiable fitting — **대상 방 ~12 측정 RIR 확보 시에만**.
4. **Reverse-criterion (neural 절반 하지 말 것)**: 캘리브용 실측 RIR 확보 불가 / 용도가 청취 아닌 파라미터 추정 / FDN-physics tail이 이미 perceptual·JND 통과 시. 근거: RAZR는 학습데이터 0, **EDC-neural의 perceptual 등가 주장은 검증서 반박됨**.

### ⚠️ 반박된 주장 (채택 금지)
- EDC-neural 재구성 RIR의 MUSHRA 지각 등가 (0-3 폐기 ×2), DAFx2025 2AFC 실녹음 구별불가(1-2), AV-DAR 16.6–50.9% 향상(1-2). → "perceptually faithful"은 방법 역량이지 검증된 등가 아님.

### ADR 전 코드 확인 필요 (Open Questions)
1. (Q2) 지각품질 best-correlate metric + 잔향 JND 임계 — 미해결, 추가 조사/문헌 필요.
2. (Q3) pyroomacoustics/Treble/Steam Audio + dEchorate/BUT/SoundSpaces head-to-head — 미해결.
3. (Q5) roomestim이 방당 ~12 RIR 실측 가능? 아니면 blind-only → RAZR pure-physics tail 지각충분?
4. (Q4) 현 **6-band ISM** 출력이 10-band 재질 라벨 + DecayFitNet-VFM-FDN(mixing-time truncation, no-crossfade splice, per-band T60 handoff)과 통합되나? → 코드 확인 항목.
