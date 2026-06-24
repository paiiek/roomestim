# ADR 0053 — B2 coverage-circle overlap verification (geometric, NO SPL)

- **Date**: 2026-06-24
- **Status**: Accepted (v0.47.0 — 구현 완료. MINOR additive / opt-in: 기존 `--algorithm coverage` 경로에 사이드카 `overlap` 블록과 새 모듈만 추가했고, 기존 vbap/dbap/wfs/ambisonics 및 coverage golden/round-trip 은 byte-equal 로 남는다. `coverage_to_dict` 무변경.)
- **Deciders**: main(설계+구현 `.omc/plans/acoustics-ism-upgrade-and-speaker-layout-2026-06-24.md` Track B), code-reviewer(예정)
- **Refs**: B1 ADR 0052(`COVERAGE_GRID_NOTE`, ±3 dB 를 B2 로 명시 보류); 코드 단일진실원천 `roomestim/place/coverage_overlap.py::COVERAGE_OVERLAP_NOTE`; 정직-NOTE 패턴 형제 ADR 0052 / D96. 표준: AVIXA Audio Coverage Uniformity (구 InfoComm 1M:2012).

> **핵심요약**: B1 이 명시적으로 보류한 "±3 dB 균일도 검증"을, **절대 SPL 을 발명하지 않고** B1 의 coverage-circle 기하 모델 그 자체를 검증하는 방향으로 닫는다. 청취평면 footprint 를 격자 샘플링하여 각 점이 몇 개의 coverage 원(반경 `coverage_radius_m`)에 들어가는지(overlap multiplicity)를 세고, `fraction_covered`(≥1 원, 갭 탐지)·`fraction_overlap_2plus`(≥2 원, 오버랩 목표)·`worst_point_xz`(최악 갭 위치)를 보고한다. SPL/음향 주장 0. 단일진실원천 `COVERAGE_OVERLAP_NOTE`.

---

## Context

B1(ADR 0052)은 AVIXA coverage-radius/spacing 공식으로 천장 격자를 **사이징**하지만, `COVERAGE_GRID_NOTE` 가 못박았듯 "±3 dB 균일도는 SPL/coverage 시뮬레이션이 필요 → B2 보류"였다. 이 보류를 정직하게 닫아야 했다.

설계 초안(plan Track B2)은 "direct-SPL 분산 스코어"였으나, 구현 중 **순수 direct-sound SPL 필드는 천장 스피커 바로 아래 근접장 피크(inverse-square)가 지배**하여 (ⓐ 기하가 다른 방 간 균일도 비교지표로 비견고, ⓑ 절대 SPL 은 스피커 감도·구동레벨 GT 부재로 불가)함을 실증했다(direct-only spread 가 모든 구성에서 19 dB 초과 → ±3 dB pass/fail boolean 은 항상-fail 의 오해를 부름). NO FAKE NUMBERS 원칙상 절대 SPL 은 발명 불가.

## Decision

### 신규 모듈 `roomestim/place/coverage_overlap.py` (기하 전용, SPL 무주장)

`score_coverage_overlap(result, floor_polygon, *, grid_resolution_m=0.5)` →
`CoverageOverlapScore`. 청취평면 footprint 를 `grid_resolution_m` 격자(셀-중심, 대칭 inset)로 샘플링하고, 각 샘플에서 **수평거리** 기준 화자 coverage 원(중심=화자 (x,z), 반경=`coverage_radius_m` — B1 이 사이징에 쓴 바로 그 값) 포함 개수를 센다. 결정론·numpy 불요(math+shapely, 기존 core). 보고:

- `fraction_covered` — ≥1 원에 든 footprint 비율(1.0=무갭, <1.0=실제 구멍).
- `fraction_overlap_2plus` — ≥2 원(AVIXA 오버랩 목표).
- `min_overlap` / `mean_overlap` — multiplicity 분포.
- `worst_point_xz` — 최소 커버 샘플(갭 위치 지시).

CLI `--algorithm coverage` 가 `room.floor_polygon` 으로 호출하여 `layout.coverage.json` 의 **신규 `overlap` 키**(말미 append)에 기록 + 요약 라인 출력. 새 플래그 `--coverage-grid-res-m`(기본 0.5). `coverage_to_dict` 는 무변경(byte-equal).

### 왜 overlap, SPL 아님 (load-bearing 정직)

`COVERAGE_OVERLAP_NOTE` 가 못박는다: 이것은 **기하 coverage-원 오버랩 검증이지 음향/SPL 예측이 아니다.** SPL·주파수응답·잔향장 무주장(절대 SPL=감도/구동레벨 부재, direct-sound=근접장 지배). coverage-원 오버랩은 B1 의 spacing 수학이 유도된 바로 그 양이므로, 음향 숫자를 발명하지 않고 B1 자신의 기하 약속을 검증한다.

## Consequences

- **(+) B1 의 보류(±3 dB) 정직하게 닫힘** — SPL 발명 없이, B1 이 사이징한 기하 그 자체를 검증.
- **(+) 실측 가치 있는 발견 표면화**: B1 의 1-D AVIXA spacing(`S=2R(1−overlap)`)은 **2-D 면적 커버리지에 대각 갭을 남긴다** — square/background 기본 격자는 8×6 m 방에서 바닥의 ~51% 만 커버(반경 1.20 m < 셀 반대각 1.44 m). hex·speech-overlap 가 이를 부분 개선. 인스톨러가 `fraction_covered`/`worst_point_xz` 로 갭을 보고 격자를 조정 가능.
- **(+) additive byte-equal**: `coverage_to_dict`·기존 5 알고리즘 golden/round-trip 불변. default 715→727p/7s(+12 `tests/test_coverage_overlap.py`), web 86p/3s, ruff·mypy(--strict, 59 files) clean.
- **(−) ±3 dB 절대 pass/fail boolean 미제공(의도적)** — direct-sound 필드는 ±3 dB 를 일상적으로 초과하며 그 윈도우는 잔향 보조 in-room 필드 대상이라, boolean 은 오해를 부른다. 상대 지표(`fraction_covered`/`overlap_2plus`/`worst_point_xz`)로 대체.

## Alternatives considered

- **(a) direct-sound SPL 분산 스코어(원안)** — REJECTED: 근접장 지배로 비견고 + 절대 SPL GT 부재(NO FAKE NUMBERS 위반). 구현·실증 후 기각.
- **(b) pyroomacoustics RIR 기반 SPL** — REJECTED(이번 스코프): web-extra 의존 + 잔향 confound + 재질/구동 GT 부재. 여전히 절대 SPL 불가.
- **(c) ±3 dB boolean 유지** — REJECTED: 항상-fail 오해.

## Reverse-criterion

- 실 스피커 감도(dB SPL/W@1m) + 구동레벨 + 측정 polar 가 입력으로 들어오면(외부 데이터), 절대 SPL coverage 맵을 별도 모듈로 추가하고 이 ADR 에 §Status-update.
- 잔향 보조 in-room ±3 dB 검증은 측정 RIR 또는 검증된 RT60(ADR 0028 A1 = NO-GO 절대) 의존 → 현재 DEFER.
