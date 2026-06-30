# ADR 0060 — 임머시브 레이아웃 4축 trade-off 리포트 (decision-support aggregation)

- **Date**: 2026-07-01
- **Status**: Accepted (v0.58.0 — MINOR additive: 신규 `roomestim/design/` 패키지(`tradeoff.py` + `__init__.py`) + 단일진실원천 `TRADEOFF_REPORT_NOTE`. 기존 placement/CLI/web/spec/place/default import 경계·골든 무변경, byte-equal. 물리 재유도 0 — 기존 frozen score 합성만.)
- **Deciders**: main(설계+오케스트레이션, 재개 `.omc/plans/immersive-layout-design-tool.md`), executor(구현+테스트), code-reviewer(예정, 독립 패스).
- **Refs**: 코드 `roomestim/design/tradeoff.py` + 단일진실원천 `roomestim/reconstruct/_disclosure.py::TRADEOFF_REPORT_NOTE`. 재사용(재유도 금지): Phase 1 `spec/speaker_spec.py`(`spl_field_over_area`/`SPLFieldScore`/`spl_field_to_dict`, ADR 0058), Phase 2 `place/immersive_quality.py`(`angular_uniformity`/`interference_proxy` + `*_to_dict`/`format_*_lines`, ADR 0059), `reconstruct/predictor.py::predict_rt60_default`, `reconstruct/measured_rt60.py::MeasuredRT60`, `geom/polygon.py::polygon_area_3d`, `roomestim_web/report.py::_surface_areas_by_material`(패턴 로컬 복제). 인터랙티브 임머시브 레이아웃 설계 도구 Phase 3(Phase 1 = ADR 0058, Phase 2 = ADR 0059).

> **핵심요약**: 임머시브 레이아웃 4축 trade-off 의 최종 합성기. 이미 ship 된 (1) 직접음장 SPL field(level) + (2) 각도 균일도(panning) + (3) interference proxy(separation) + (4) per-speaker price 합(cost) + RT60 컨텍스트(모델 OR 엔지니어 주입 measured)를 단일 `TradeoffReport` frozen dataclass 로 묶는다. **물리 재유도 0** — 기존 frozen score 를 그대로 forward, 각 메트릭의 caveat 를 그대로 상속. 4축 어느 것도 보장된 in-room 측정 아님 → 후보 레이아웃 **상대 비교** guidance 로만 사용.

---

## Context

임머시브 레이아웃 설계 도구([[project_immersive_layout_design_tool]])의 4축 trade-off 가 세 Phase 에 걸쳐 부품이 갖춰졌다: Phase 1(ADR 0058)이 LEVEL(직접음장 SPL), Phase 2(ADR 0059)가 PANNING(각도 균일도)+SEPARATION(interference). 남은 작업은 이들을 RT60 컨텍스트·COST 와 함께 **하나의 결정-지원 리포트**로 합성하는 것이다. 핵심 설계 제약: 이 레이어는 새 물리를 도입하면 안 된다(메트릭은 이미 검증·고지됨) — 순수 aggregation 이어야 하고, 각 부품의 정직성 caveat 가 합성 결과까지 손실 없이 전파돼야 한다.

## Decision

### 1. `evaluate_layout(room, placement, spec, *, listener_area, drive_w, target_spl_db, measured_rt60=None, grid_resolution_m=..., min_separation_deg=...) -> TradeoffReport`
얇은 합성기. 각 축을 기존 함수에 forward: LEVEL=`spl_field_over_area`, PANNING=`angular_uniformity`, SEPARATION=`interference_proxy`, RT60=`predict_rt60_default`. COST=resolved spec 들의 `.price` 산술 합. `spec`은 단일 SpeakerSpec(전체 적용) 또는 `dict[channel]`(로컬 `_spec_for_channel` resolver, 누락 키→ValueError, Phase 1 과 동일 계약). `drive_w<=0`·비유한 `target_spl_db`·비양수 주입 RT60→ValueError. <2 스피커 등 degenerate 는 하부 함수가 raise(삼키지 않음).

### 2. RT60 컨텍스트 — 모델 OR 엔지니어 주입
`measured_rt60`는 `MeasuredRT60`(그 `.rt60_s`) / raw float(초, 유한·>0) / None 수용. 주입 시 `rt60_effective_s=measured`·`rt60_source="measured"`, 부재 시 predicted·`"predicted"`. 모델 추정치(`rt60_predicted_s`)는 주입 여부와 무관하게 항상 계산·보존(비교용). surface-area-by-material 집계는 `roomestim_web/report.py`의 `_surface_areas_by_material` 패턴을 **로컬 private 복제**(object-derived surface fold 포함; 기존 두 private 복제는 리팩터링 안 함 — additive 유지).

### 3. COST 축 — `TradeoffCost`
per-speaker `SpeakerSpec.price` 의 단순 산술 합. 전부 None→`total_price=None`·`complete=False`·`n_priced=0`. 일부만 priced→알려진 price 합·`complete=False`. 전부 priced→`complete=True`. **견적 아님**(고지). 

### 4. 단일진실원천 `TRADEOFF_REPORT_NOTE` (`reconstruct/_disclosure.py`)
리포트가 AGGREGATE decision-support 임을 명시: (a) LEVEL=직접음장 SPL(SPL_DIRECT_FIELD_NOTE 참조 — in-room 과소추정·단순 지향성·target headroom 도 동일 caveat 상속), (b)(c) PANNING/SEPARATION=GEOMETRIC 각도(IMMERSIVE_QUALITY_NOTE 참조 — 음향 측정 아님), (d) RT60=모델(RT60_DISCLOSURE) OR 주입 measured(MEASURED_RT60_NOTE), (e) COST=공급된 price 산술 합(부재 시 None, 견적 아님). 4축 어느 것도 보장된 in-room 측정 아님 → 상대 비교 guidance. 모든 출력 참조(재타이핑 금지).

### 5. Plumbing — Phase 1/2 스타일 재사용
`tradeoff_to_dict`(note-first JSON-serialisable; `spl`/`angular`/`interference` 는 기존 `*_to_dict` 중첩, `cost`/`rt60` dict 추가, rounding 스타일 일치) + `format_tradeoff_lines`(헤더 NO acoustic guarantee + 기존 `format_angular_uniformity_lines`/`format_interference_lines` 재사용 + level/cost/rt60 라인). `roomestim/design/__init__.py` 는 `spec/__init__.py` 스타일 re-export.

## Consequences

- **(+)** 임머시브 4축 trade-off 완성: 세 Phase 부품이 단일 리포트로 합성됨. 엔지니어 measured RT60 주입으로 모델 추정의 정직성 갭을 우회 가능(주입 시 source 라벨로 출처 추적).
- **(+)** core 무변경 byte-equal(신규 패키지, numpy-free, `import roomestim` torch-free). **물리 재유도 0** — 모든 수치는 기존 frozen score forward. default 754→775p(+21 신규 테스트만, review fix 포함), web 95p 불변, mypy 67→69 clean, ruff clean.
- **(+)** NO FAKE NUMBERS: cost=산술 합(견적 아님)·headroom=`min_spl - target` exact 항등·각 축 caveat 단일진실원천 전파. REPL EXACT 검증(cost 8×125=1000.0, headroom=min_spl-target).
- **(−)** 합성 리포트는 각 부품의 caveat 를 모두 상속(고지됨): LEVEL 은 in-room 과소추정·datasheet provenance 의존, PANNING/SEPARATION 은 음향 측정 아님, 모델 RT60 은 재질 가정. 절대 성능 보장 아닌 상대 guidance.
- **(−)** CLI/web 미배선(library-only). 동시세션 cli.py 경합 회피 + scope 최소화 — 배선은 후속.

## Status-update (2026-07-01)
구현 완료, 게이트 GREEN. 독립 code-review(opus) **APPROVE-WITH-FIXES**(0 CRIT/HIGH, 1 MEDIUM + 4 LOW). 2건 반영:
- **(MEDIUM)** `spl_provenance`(datasheet/estimate/mixed) 를 `TradeoffReport`·`tradeoff_to_dict`·`format_tradeoff_lines` 에 노출 — 절대 `meets_target_spl`/`spl_headroom_db` 주장이 `TRADEOFF_REPORT_NOTE` 를 읽지 않아도 self-describing(`SPLFieldScore.exceeds_max_spl` 가 over-claim 을 가시화하는 것과 동일 정신).
- **(LOW)** `_resolve_measured_rt60` 가 float 분기뿐 아니라 `MeasuredRT60` 분기도 finite/>0 검증(`MeasuredRT60` 는 검증 `__post_init__` 부재 → 손수 만든 음수/NaN `rt60_s` 차단).
- 나머지 LOW 3건(중복 `_spec_for_channel` dead branch, `report.py` 미러 bare-except, room-only RT60 per-call 재계산)은 record-only/optional 로 미적용.
게이트 재실행 GREEN: default 775p(+21)·web 95p/4s·mypy(--strict, 69)·ruff clean.
