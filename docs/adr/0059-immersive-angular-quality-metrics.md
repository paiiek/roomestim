# ADR 0059 — 임머시브 레이아웃 각도 품질 메트릭 (angular uniformity + interference proxy)

- **Date**: 2026-06-29
- **Status**: Accepted (v0.57.0 — MINOR additive: 신규 `roomestim/place/immersive_quality.py` + 단일진실원천 `IMMERSIVE_QUALITY_NOTE`. 기존 placement/CLI/web/default import 경계·골든 무변경, byte-equal.)
- **Deciders**: main(설계+오케스트레이션, 풀플랜 `~/.claude/plans/glowing-booping-hopcroft.md`, 재개 `.omc/plans/immersive-layout-design-tool.md`), executor(구현+polish), code-reviewer(opus, 독립 = **APPROVE**, 0 CRIT/HIGH·2 MEDIUM·4 LOW → 전부 반영).
- **Refs**: 코드 `roomestim/place/immersive_quality.py` + 단일진실원천 `roomestim/reconstruct/_disclosure.py::IMMERSIVE_QUALITY_NOTE`. 재사용: `model.py`(PlacedSpeaker/Point3/assert_finite/kErrTooFewSpeakers), `place/coverage_overlap.py`(frozen-score + note-first to_dict + format_lines 스타일). 인터랙티브 임머시브 레이아웃 설계 도구 Phase 2(Phase 1 = ADR 0058).

> **핵심요약**: 임머시브 레이아웃 4축 trade-off 중 "coverage 균일도"와 "overlap/간섭"의 토대. listener 중심 임머시브 리그에서 "균일도"는 **청취자가 본 스피커 방향들의 각도 규칙성** = 구면 위 방향 단위벡터 간 **측지각(great-circle)**. `angular_uniformity`(최근접 측지 gap의 min/max 비율, dome elevation 완전 반영) + `interference_proxy`(기하 최소분리 임계 below 쌍 플래그). **순수 기하 — 음향 측정 아님**: VBAP/DBAP 패닝 매끄러움 근사일 뿐 radius/level/지향성/room 무시, interference는 comb-filter/심리음향 예측 아닌 RISK proxy, 10° 임계와 uniformity-ratio는 미보정 rule-of-thumb.

---

## Context

임머시브 레이아웃 설계 도구([[project_immersive_layout_design_tool]])의 4축 trade-off 중 SPL 충분성은 Phase 1(ADR 0058)이 다뤘다. 나머지 "coverage 균일도"와 "overlap/간섭"을 임머시브(listener-centric) 맥락에서 정의해야 한다. 분산 천장 BGM의 floor-coverage 원(coverage_overlap.py)과 달리, 임머시브 리그는 청취자가 원점에 있고 스피커가 둘러싼다 — 품질 신호는 **청취자가 본 방향들의 각도 규칙성**이다(고른 각간격 = 매끄러운 VBAP/DBAP 패닝, 큰 홀 없음). 단순 azimuth gap은 dome(고도차)을 놓치므로 **구면 측지각**이 올바른 primitive.

## Decision

### 1. `angular_uniformity(speakers) -> AngularUniformityScore`
각 스피커의 `position`을 원점→스피커 단위벡터로 변환. 쌍별 측지각 `acos(clamp(dot(u_i,u_j),-1,1))`(deg). 스피커별 최근접 이웃 gap 집합 → `min/max/mean_nn_gap_deg`, `uniformity = min_nn/max_nn ∈ [0,1]`(1.0=완전 균일), `worst_pair`(최소각 쌍 채널, sorted 정규화). `max_nn<=0`(전부 동일방향 degenerate)→uniformity 1.0 가드. `<2` 스피커 또는 원점 스피커→ValueError.

### 2. `interference_proxy(speakers, min_separation_deg=10.0) -> InterferenceScore`
방향 측지 분리가 임계 below인 쌍을 플래그(너무 가까움=comb-filter/중복 coverage RISK). `n_close_pairs`(정확 카운트, 항상 보존)·`close_pairs`(채널 각 sorted, `MAX_REPORTED_CLOSE_PAIRS=20` 캡)·`close_pairs_truncated` 플래그(**무성 드롭 금지** — 캡 초과 시 카운트는 정확·리스트만 절단·플래그 True). 기하 proxy, 심리음향 아님 명시.

### 3. 단일진실원천 `IMMERSIVE_QUALITY_NOTE` (`reconstruct/_disclosure.py`)
GEOMETRIC only, 측지각(azimuth-only 아님, dome 반영), uniformity가 VBAP/DBAP 매끄러움 근사이나 radius/level/지향성/room 무시, interference가 comb-filter/phase/심리음향 예측 아님, 10°+ratio는 미보정 rule-of-thumb. 모든 출력 참조. plumbing은 coverage_overlap.py 스타일(note-first to_dict + format_lines).

## Consequences

- **(+)** 임머시브 4축 중 균일도·간섭 축의 기하 토대 확보(Phase 3 tradeoff가 소비). dome elevation 정확 반영(측지각).
- **(+)** core 무변경 byte-equal(신규 모듈, numpy-free `math`만, `import roomestim` torch-free). default 736→751p(+15 신규 테스트만, polish 후 +α), web 95p 불변, mypy 67 clean.
- **(+)** NO FAKE NUMBERS: 순수 기하 명시, 캡 무성드롭 금지(카운트 보존+플래그), 측지각 REPL 검증(8-ring 45°·uniformity 1.0·90°/0°/180° exact).
- **(−)** 음향 측정 아님(고지됨): radius/level/지향성/room/주파수 무시. 실제 패닝 품질의 근사 guidance.
- **(−)** 10° 임계·uniformity-ratio는 미보정 휴리스틱(고지됨). 보정엔 측정 comb-filter/패닝 데이터 필요(현재 부재).

## Status-update (2026-06-29)
독립 code-review(opus) = **APPROVE**(0 CRIT/HIGH, 2 MEDIUM + 4 LOW, 비차단). 전부 반영: ① close-pairs truncation/flag 불변식 테스트 추가(honesty-critical), ② `worst_pair` uniform-rig 표현 reword(균일 시 outlier 쌍 미표기)+sorted 채널 정규화(close_pairs와 일관), ③ non-finite position 테스트, ④ antipodal(180°) 측지 테스트, ⑤ O(n²) 비용 docstring 명시. 테스트 15→18. 게이트 재검증 GREEN.
