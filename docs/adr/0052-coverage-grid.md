# ADR 0052 — B1 room-aware AVIXA ceiling-speaker coverage-grid (geometric-only)

- **Date**: 2026-06-24
- **Status**: Accepted (v0.45.0 — 구현 완료. 시제는 수행된 사실에 대해 과거형이다. MINOR additive / opt-in: 새 `--algorithm coverage` 선택지와 새 모듈만 추가했고, 기존 vbap/dbap/wfs/ambisonics 경로 및 golden/round-trip 은 byte-equal 로 남는다.)
- **Deciders**: planner(설계 `.omc/plans/b1-coverage-grid-design-2026-06-24.md`), executor(구현), code-reviewer(예정), verifier(예정)
- **Refs**: 설계 단일진실원천 `.omc/plans/b1-coverage-grid-design-2026-06-24.md`; 리서치 `.omc/research/usable-tech-facet5-speaker-layout-2026-06-23.md` §1A/§1C; 코드 단일진실원천 `roomestim/place/coverage_grid.py::COVERAGE_GRID_NOTE`; 정직-NOTE 패턴 형제 ADR 0041(B5 `LAYOUT_ANGLE_CHECK_NOTE`)·D96(`CEILING_CONFIDENCE_HEURISTIC_NOTE`). 표준: AVIXA Audio Coverage Uniformity (구 InfoComm 1M:2012).

> **핵심요약**: 청취자-중심 VBAP/DBAP/WFS/ambisonics 렌더 리그와 별개로, **방의 floor polygon + 천장고 + 귀높이 + 공칭 분산각**으로부터 천장면에 사각/육각 격자 스피커 위치를 결정론적으로 계산하고 footprint 폴리곤에 클립하는 **room-aware 분산-천장 coverage grid** 를 추가한다. **기하 AVIXA 공식 기반 전용** — SPL/음향성능 주장 없음(그건 B2, 보류). 단일진실원천 `COVERAGE_GRID_NOTE` 가 그 경계를 못박는다.

---

## Context

roomestim 의 기존 배치 5종은 모두 **청취자-중심**이다: vbap/wfs/ambisonics 는 고정 리그(by construction 방-blind)이고, dbap 만 mount surface + listener_area 를 쓴다. 그러나 상용 B2B AV-인스톨러의 가장 흔한 실무 — **분산 천장 스피커의 균일 coverage 격자** (회의실/리테일/BGM) — 를 내는 경로가 없었다. 이 격자는 청취자 한 점을 겨냥하는 ring 이 아니라, 방 전체를 덮는 하향 발사 천장 캔의 정칙 배열이다.

AVIXA Audio Coverage Uniformity (구 InfoComm 1M:2012) 의 coverage-radius 공식은 기하적이고 비-encumbered 이다. 단, **AVIXA 표준은 ±3 dB 균일도 MEASUREMENT 절차를 정의한다 — B1 은 SPL 도 ±3 dB 도 계산하지 않는다(그건 B2).**

## Decision

### 신규 모듈 `roomestim/place/coverage_grid.py` (기하 전용)
공식(리서치 §1A/§1C)::

    effective_dispersion = nominal_dispersion * 0.75   (EFFECTIVE_DISPERSION_FACTOR)
    coverage_radius      = (ceiling_height - ear_height) * tan(effective/2)
    spacing (S)          = 2 * coverage_radius * (1 - overlap_fraction)
    overlap              = background 0.15 / speech 0.23 (20–25% 밴드 중점)

- **Lattice (half-spacing 양변 inset)**: 스피커 중심은 footprint AABB 의 `[minx+S/2, maxx-S/2] × [minz+S/2, maxz-S/2]` 폐구간에 놓인다 — 첫/마지막 스피커가 각 축에서 벽으로부터 반-spacing `S/2`. 사각 격자는 양축 `S` 보; 육각 격자는 x 방향 `S`, z 방향 `S·√3/2`, 홀수 행 `S/2` offset. row-major(z 다음 x) 결정론적 방출(RNG 없음).
- **Inclusion (EXACT, 문서화)**: 격자점 `(x,z)` 는 그 floor-투영 coverage **centroid** 가 폴리곤 내부 또는 `edge_inclusion_tol_m` 이내일 때만 유지 — `poly.covers(pt) or poly.buffer(tol).covers(pt)` (dbap 의 `inset.buffer(1e-9).contains` 관용구 미러). **centroid-in-polygon**(원-면적 overlap 아님): concave notch 근처 유지 스피커의 coverage 원은 벽을 넘칠 수 있고 NOTE 가 이를 정직히 명시(음향 주장 아님).
- **Tiny-room fallback (≥1 보장)**: footprint 가 한 spacing 보다 작거나 모든 격자점이 concave footprint 밖이면 `poly.representative_point()`(shapely 가 내부 보장)에 정확히 1개.
- **Aim**: 천장 스피커는 정-하향 `Point3(0,-1,0)`(하향 발사 캔, listener-aimed ring 아님).
- numpy 불필요 — bounded 격자를 stdlib `math` 결정론 루프로 생성, shapely 만 사용(둘 다 기존 core dep). core/torch-free import-safe.

### PlacementResult 재사용 (스키마 변경 0)
B1 은 layout.yaml 경계에 대해 `PlacedSpeaker`/`PlacementResult` 를 **재사용**하고, coverage 전용 수치(radius/spacing/n/grid/overlap)는 새 `CoverageGridResult` 가 담아 새 `layout.coverage.json` 사이드카(`layout.angles.json` 패럴)로 방출한다. `coverage_result_to_placement` 가 `regularity_hint = "PLANAR_GRID"(n≥4) / "IRREGULAR"(n<4)` (R10 min_speaker_count 통과)·`target_algorithm="COVERAGE_GRID"` 로 래핑한다.

### 새 `TargetAlgorithm.COVERAGE_GRID` (additive enum)
writer 는 `x_target_algorithm` 을 non-VBAP 에만 방출하므로 VBAP layout 은 byte-equal. placement-yaml READER 가 닫힌 라벨 집합 `_TARGET_ALGORITHM_VALUES` 를 검증하므로 거기에 `"COVERAGE_GRID"` 를 **additive 로** 추가했다(round-trip 보존).

### CLI (additive)
`place`·`run` 의 `--algorithm` 에 `coverage` 선택지 추가(기본 `vbap` 불변) + 4 플래그(`--ceiling-dispersion-deg`/`--ear-height-m`/`--overlap-mode`/`--grid`). coverage 분기는 `place_coverage_grid_for_room` 를 직접 호출해 사이드카용 `CoverageGridResult` 를 얻고(이중계산 회피), `layout.yaml` + `layout.coverage.json` 을 쓰고 coverage 라인 + NOTE 를 출력. `dispatch.run_placement` 도 coverage 분기 + 4 optional defaulted kwarg 를 얻어 기존 호출자(web/test) byte-equal.

### 정직 NOTE 단일진실원천 `COVERAGE_GRID_NOTE`
`LAYOUT_ANGLE_CHECK_NOTE` 스타일 module-level `str` 상수, `__all__` export, docstring·`coverage_to_dict`·`format_coverage_lines`·CLI 가 retype 없이 참조. NOTE 가 못박는 것: 기하 전용·SPL 무계산·±3 dB 미검증(B2 보류)·이상화 원뿔·실 스피커 polar 무주장·공칭 분산각은 user-supplied datasheet(방에서 추론 안 함).

## Consequences

- **Positive**: 첫 room-aware 분산-천장 격자(B2B 인스톨러 핵심 실무) 확보 — dbap 에 이은 2번째 기하-인지 경로. AVIXA 공식 기반·결정론·새 의존성 0·core import-safe.
- **Neutral/byte-equal**: 기본 `vbap` 및 dbap/wfs/ambisonics 경로 무변경, golden/round-trip byte-equal(게이트로 확증), geometry_schema.json·room 스키마 무변경. enum/reader 추가는 순수 additive.
- **Negative/한계**: **B2 — SPL / ±3 dB AVIXA 균일도 채점은 보류**(direct-sound SPL 모델 + listener grid 필요). B1 은 위치만, B2 가 채점. centroid-in-polygon 규칙은 concave notch 에서 coverage 원이 벽을 넘칠 수 있음(NOTE 명시). 공칭 분산각은 단일 user scalar — GLL/CLF datasheet polar 파싱은 out of scope. optimization-based 배치(scipy DE)도 후순위 레버.

## Verification
default 게이트 695p/7s(v0.44.0) → +신규 `tests/test_coverage_grid.py`(11 케이스, 모두 결정론·`math.tan` in-test 계산, 하드코딩 round 리터럴 없음), 0 regression. ruff clean, mypy --strict clean(58 source files, Any leak 0). CLI smoke: `place --algorithm coverage` 가 layout.yaml(engine-validated) + layout.coverage.json 을 쓰고 NOTE 출력 확인. NO FAKE NUMBERS — 모든 coverage 수치는 공식 유도뿐.
