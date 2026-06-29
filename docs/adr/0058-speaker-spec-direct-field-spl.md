# ADR 0058 — SpeakerSpec 데이터 모델 + 직접음장(direct-field) SPL 엔진

- **Date**: 2026-06-29
- **Status**: Accepted (v0.56.0 — MINOR additive: 신규 `roomestim/spec/` 패키지 + 단일진실원천 `SPL_DIRECT_FIELD_NOTE`. 기존 백엔드·placement·default import 경계·골든 무변경, byte-equal.)
- **Deciders**: main(설계+오케스트레이션, 풀플랜 `~/.claude/plans/glowing-booping-hopcroft.md`, 재개 `.omc/plans/immersive-layout-design-tool.md`), executor(구현), code-reviewer(opus, 독립 = APPROVE-WITH-FIXES → 3 MEDIUM 반영).
- **Refs**: 코드 `roomestim/spec/speaker_spec.py` + 단일진실원천 `roomestim/reconstruct/_disclosure.py::SPL_DIRECT_FIELD_NOTE`. 재사용: `model.py`(ListenerArea/PlacedSpeaker/Point3/assert_finite), `place/coverage_overlap.py`(ear-plane 샘플링 패턴 동일). 인터랙티브 임머시브 레이아웃 설계 도구 Phase 1.

> **핵심요약**: 임머시브 레이아웃 trade-off 4축 중 "SPL 충분성"의 토대를 만든다. roomestim은 그간 "SPL은 발명하지 않는다"(스피커 감도/드라이브 데이터 부재)고 명시 거부해 왔다. 이를 **실제 datasheet 스펙을 입력받는** `SpeakerSpec` + **직접음장-only** SPL 엔진으로 해소한다. 절대수치는 `provenance="datasheet"` 일 때만 유의미하고, 내장 카탈로그는 전부 `estimate` 라벨. **반사음장/room-gain 미모델(과소추정 방향) + max_spl_db 미캡/근거리 미모델(과대추정 방향) 둘 다 정직 고지** — upper/lower bound 아닌 free-field direct 추정.

---

## Context

임머시브 레이아웃 설계 도구([[project_immersive_layout_design_tool]])는 엔지니어에게 4축 trade-off(coverage 균일도·**SPL 충분성**·스피커 수/비용·overlap/간섭)를 제시한다. 이 중 coverage/overlap/count는 기존 기하 토대가 있으나, **SPL 충분성은 토대가 0**이었다 — `coverage_overlap.py`가 명시하듯 "absolute SPL needs speaker sensitivity + drive level that roomestim does not have." 사용자 결정: 충실도를 **실제 제품 스펙**으로 올리고(SpeakerSpec 신규), SPL 경계는 **직접음장만**(반사음장은 RT60 demo-grade 불확실성 상속을 피해 제외).

## Decision

### 1. `SpeakerSpec` (frozen dataclass, `roomestim/spec/speaker_spec.py`)
datasheet 최소 필드: `model`, `sensitivity_db_1w1m`, `max_spl_db`, `dispersion_deg`(축대칭 −6 dB 총 coverage 각), `provenance: Literal["datasheet","estimate"]="estimate"`, `price: float|None`. `assert_finite` + `dispersion_deg ∈ (0,360]` 검증.

### 2. 직접음장 SPL (`direct_field_spl_db`)
`sensitivity + 10·log10(W) − 20·log10(d) + directivity`. 지향성 = **단순화 축대칭** quadratic roll-off `−6·(θ/(disp/2))²` (on-axis 0 dB, half-angle 정확히 −6 dB; AVIXA coverage-angle 관례), −60 dB 플로어. **측정 polar pattern 아님.** 다중 스피커 = **비간섭 에너지 합** `10·log10 Σ 10^(SPL_i/10)`.

### 3. listener-area SPL 필드 (`spl_field_over_area`)
ListenerArea 폴리곤을 ear-plane(`height_m`)에서 `coverage_overlap.py`와 **문자-동일** 샘플링(cell-centred inset, `poly.covers`). 샘플별 3D 거리 + aim 대비 off-axis 각 → 에너지 합. `SPLFieldScore`(min/mean/max/uniformity/worst_point + `exceeds_max_spl` 가시화 플래그 + note).

### 4. 카탈로그 + 로더
`BUILTIN_SPEAKER_CATALOG`(generic 3종, **전부 estimate**); `load_speaker_spec`/`load_speaker_catalog`(yaml/json, 로드 시 default `datasheet`) — 엔지니어가 **실 datasheet 주입**.

### 5. 단일진실원천 `SPL_DIRECT_FIELD_NOTE` (`reconstruct/_disclosure.py`)
직접음장-only(반사음장/room-gain/boundary 미모델 → **과소추정**), 단순화 지향성(측정 polar 아님), 비간섭 에너지 합, estimate-vs-datasheet provenance, **그리고 max_spl_db 미캡 + 근거리 미모델 → 과대추정 가능** = neither upper nor lower bound. 모든 출력이 참조.

## Consequences

- **(+)** 임머시브 4축 중 SPL 충분성 축의 물리적 토대 확보(Phase 3 tradeoff에서 소비). 엔지니어가 실 datasheet 주입 시 절대 SPL 유의미.
- **(+)** core 무변경 byte-equal(신규 패키지, numpy-free, `import roomestim` torch-free 경계 유지). default 게이트 701→736p(+35 신규 테스트만), web 95p 불변.
- **(+)** NO FAKE NUMBERS 정렬: 양방향(과소·과대) 정직 고지, 카탈로그 estimate 라벨, REPL로 물리 항등식 검증(거리2배 −6.02 dB·10×W +10 dB·half-angle −6 dB exact).
- **(−)** 직접음장-only는 실내 절대 SPL의 upper/lower bound 아님(고지됨). 반사음장은 측정 RT60 주입 경로(Phase 3)에서 별도 고려.
- **(−)** 지향성은 스칼라 축대칭 단순화 — 실측 polar/주파수 의존 미반영(고지됨). 실측 polar ingest는 비범위(deferred).

## Status-update (2026-06-29)
독립 code-review(opus) = **APPROVE-WITH-FIXES**(0 CRIT/HIGH, 3 MEDIUM). 반영: ① NaN/degenerate aim이 무성으로 on-axis화되던 결함 → aim 유한성 `assert_finite` + acos 전 `cos_off` 가드(fake-number 누수 차단), ② `max_spl_db` 과대추정 방향을 NOTE에 추가 + `exceeds_max_spl` 플래그로 가시화, ③ off-axis 기하/카탈로그 로더/에러경로 테스트 보강(23→35). 게이트 재검증 GREEN.
