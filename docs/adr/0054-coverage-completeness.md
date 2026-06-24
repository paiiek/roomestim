# ADR 0054 — B4 coverage-completeness densify-to-target (measured)

- **Date**: 2026-06-24
- **Status**: Accepted (v0.48.0 — MINOR additive / opt-in: new `--coverage-target` flag + new module + additive `spacing_scale` param (default 1.0 = byte-equal). Default `--algorithm coverage` (no target) unchanged except a stderr low-coverage NOTE.)
- **Deciders**: main(설계+구현, plan Track B 후속), code-reviewer(예정). user 결정: 성능평가 후 "B4→A3 순차".
- **Refs**: B1 ADR 0052(coverage grid), B2 ADR 0053(overlap oracle); 코드 `roomestim/place/coverage_complete.py::COVERAGE_COMPLETE_NOTE`. 성능 동기 = 현실 방 매트릭스 평가에서 B1 nominal grid 가 바닥 평균 69~75%(min 53%)만 커버.

> **핵심요약**: B2 가 측정으로 드러낸 "B1 의 1-D AVIXA spacing 이 2-D 대각 갭을 남겨 바닥 ~54-77% 만 커버" 문제를, **측정 커버리지(B2 overlap 오라클)를 목표치까지 격자를 조밀화**하여 정직하게 해결한다. closed-form 상수 추정 대신 실측 수렴(NO FAKE NUMBERS). SPL 무주장.

---

## Context

성능 평가(현실 B2B 방 5종 × grid 2 × overlap 2)에서 B1 nominal coverage grid 의 실제 바닥 커버리지가 **평균 69~75%, 최저 53%**로 측정됐다. 근본 원인: B1 의 overlap(15%/23%)은 **1-D 인접-원 겹침** 기준이라 square 격자의 **2-D 전면 커버리지(필요 overlap ≥29%, S ≤ R√2)** 엔 대각 갭을 남긴다. B2B 인스톨러 도구로서 "기본 레이아웃이 바닥을 덜 덮는다"는 surface + 해결되어야 했다.

## Decision

### 1. `place_coverage_grid` 에 additive `spacing_scale` (default 1.0)
center-to-center spacing 에 곱하는 lever(`(0,1]`, densify-only). 1.0 = AVIXA nominal = **byte-equal**. <1.0 = 격자 조밀화(2-D 갭 축소). 검증 가드(finite·범위) 추가.

### 2. 신규 모듈 `roomestim/place/coverage_complete.py`
`place_coverage_grid_to_target(..., target_coverage=0.90, max_speakers=200)`:
`spacing_scale` 을 1.0 에서 ×0.9 씩 내리며 매 스텝 재배치+재채점(B2 `score_coverage_overlap`), **측정 `fraction_covered ≥ target` 첫 격자에서 수렴**(converged=True) 반환. 스피커 cap/스케일 floor 먼저 도달 시 가장 조밀한 시도 격자를 converged=False 로 정직 반환(절대 sparse 격자 silent 아님). `CoverageTargetResult`(grid/score/target/achieved/spacing_scale/converged/iters/note).

### 3. CLI `--coverage-target FRAC`
지정 시 densifier 사용 → `layout.yaml` 은 조밀화된 격자, `layout.coverage.json` `overlap.target` 블록(requested/achieved/converged) + "target MET/NOT MET" 라인. **미지정 시**(기본): 기존 경로 + 실제 커버리지 < 0.85 이면 stderr NOTE 로 `--coverage-target`/hex/speech 안내(silent 아님).

### 4. 정직성
`COVERAGE_COMPLETE_NOTE`: achieved_coverage 는 **기하 −6 dB coverage-원 커버리지(B2 오라클), SPL/음향 무주장**. converged=false = cap 내 목표 미달(densest 반환). spacing_scale<1 = nominal 초과 조밀화.

## Consequences

- **(+) 성능 결함 정직 해결**: meeting 6×5 방 54%(4 spk) → **97%(12 spk) MET**, retail 12×10 66% → 95%. 측정 수렴이라 방마다 적응적(고정 공식 아님).
- **(+) silent under-cover 제거**: 기본 경로도 낮은 커버리지를 stderr 로 경고.
- **(+) additive byte-equal**: spacing_scale=1.0 기본 → `place_coverage_grid` 결과/coverage_to_dict/5 알고리즘 golden 불변. `overlap.target` 는 `--coverage-target` 지정 시에만 사이드카에 추가.
- **(−) 절대 SPL/±3 dB 균일도 여전히 무주장** — 기하 커버리지(≥1 원)만. 음향 균일도는 측정 RIR/검증 RT60 의존(A1=NO-GO 절대).
- 게이트: default **755p/7s**(+13 `tests/test_coverage_complete.py`), ruff·mypy(--strict, 내 모듈) clean, CLI E2E(densify+warning) 검증.

## Alternatives considered

- **(a) closed-form 2-D 커버리지 spacing 공식**(square S≤R√2, hex S≤R√3) — REJECTED 단독: 벽 inset·클립·오목 footprint 에서 정확도 미보장 → 측정 수렴이 더 정직·강건(hand-derived 상수 미신뢰).
- **(b) 기본값을 speech/hex 로 변경** — REJECTED: 여전히 75% 평균(불충분) + B1 기본 byte-equal 깨짐.
- **(c) 경고만, 자동수정 없음** — REJECTED 단독: 인스톨러에게 해결책 미제공. 경고는 기본 경로에 유지하되 densifier 도 제공.

## Reverse-criterion

- 절대 SPL coverage(스피커 감도+구동레벨 입력 시) 또는 측정-RIR 균일도 검증이 들어오면 별도 모듈 + 이 ADR §Status-update.
