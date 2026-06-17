# ADR 0041 — Ambisonics 배치 알고리즘 설계 (B5, draft)

**Status**: Partially-Accepted — **PR1 SHIPPED** (v0.33.0, OQ-38
`x_target_algorithm` round-trip, D102; §Status-update-v0.33.0). **PR2+PR3 SHIPPED
EXPERIMENTAL** (v0.39.0, 2026-06-17, D104; §Status-update-2026-06-17) under the §D-3a
point-2 carve-out (roomestim-side rig COORDINATE generation only; end-to-end decode/route
UNCONFIRMED). **PR4 (t-design) DEFERRED**. The §D-3a point-1 end-to-end gate (engine
식별·라우팅 합의 or require.md ambisonics mandatory 승격) remains the trigger to remove the
"experimental" label. 원 draft(2026-05-29)는 설계 합의 선행 기록.
**REVISED 2026-05-29** — critic 리뷰(ACCEPT-WITH-RESERVATIONS; 0 CRITICAL, 3 MAJOR)
반영: require.md precondition 명시(§Pre-conditions), OQ-38 자기참조 트리거 → cadence+D26
재근거(§Context), engine 식별·라우팅 pre-implementation gate 신설(§D-3a), PR1에 collapse
계약 테스트 invert + golden fixture 명시(§PR 분할).
**Supersedes**: none. **Amends**: ADR 0003 (placement-algorithm-priority) Follow-up.
**Related**: ADR 0003, ADR 0036 (layout round-trip nudge), OQ-38, D50.

> **핵심요약 (권장안)**: Ambisonics를 "encoding format"이 아니라 **"디코더가 소비할 규칙적
> 스피커 리그를 배치하는 또 하나의 기하 알고리즘"**으로 정의한다((a)안). 실제 SH
> 디코딩/decoder 선택은 engine 책임으로 남긴다(`spatial_engine/proto/ipc_schema.md:21-22`
> 에서 `/sys/ambi_order`·`/sys/ambi_decoder_type` 확인됨). 리그 기하는 신규
> `place/ambisonics.py`에서 **t-design 우선·platonic 폴백**으로 구현하고, round-trip
> 결함(OQ-38)은 이 기회에 `x_target_algorithm` extension key로 함께 닫는다.

## Context

`roomestim/place/`의 배치 3종(VBAP/DBAP/WFS)은 모두 "물리 스피커 좌표를 배치하는
순수 기하 알고리즘"이다. 산출물 `PlacedSpeaker`는 `(channel, position: Point3,
aim_direction)`을 가지며(`roomestim/model.py:292-299`), 채널 = 물리 스피커 인덱스를
전제한다. layout.yaml은 speaker마다 `id, channel` + spherical(`az_deg/el_deg/dist_m`)
형식을 emit한다(`roomestim/export/layout_yaml.py:195-209`).

Ambisonics는 현재 enum stub만 존재한다:
- `roomestim/place/algorithm.py:13-19` — `TargetAlgorithm.AMBISONICS = "AMBISONICS"`,
  docstring(`:3-5`)에 "deferred to v0.3 but listed for forward compatibility".
- `roomestim/place/dispatch.py:24-93` — `run_placement`은 vbap/dbap/wfs만 분기,
  미지원 알고리즘은 `:93`에서 raise. ambisonics 배치 함수 부재.
- `roomestim/cli.py:58-62, 169-172` — place/run 모두 `choices=["vbap","dbap","wfs"]`.
- ADR 0003 §Decision(`:15`)/Follow-ups(`:44`) — "VBAP→DBAP→WFS→Ambisonics(v0.3
  deferred); require.md가 mandatory로 올리면 `ambisonics.py` 추가".

**핵심 개념 간극**: Ambisonics의 채널은 물리 스피커 위치가 아니라 구면조화(SH)
계수다 (order N → (N+1)² 채널: 1st=4, 2nd=9, 3rd=16). 따라서 "ambisonic 채널을
PlacedSpeaker로 그대로 방출"하면 `position`/`az_deg`/`dist_m`/`aim_direction` 필드
의미가 붕괴하고, engine schema(`geometry_schema.json:27-83`)의 speaker 위치 요구와도
충돌한다. v0.3 보류의 표면 사유는 "require.md 미포함"이었으나, 실제 설계 장애물은 이
타입 불일치다.

**engine 책임 경계 (확인됨)**: 실제 SH 디코딩은 engine 런타임 소관이다.
`spatial_engine/proto/ipc_schema.md:21`은 `/sys/ambi_order`("Set Ambisonics decode
order (clamped 1..3)"), `:22`는 `/sys/ambi_decoder_type`
(0=PINV,1=MAX_RE,2=ALLRAD,3=EPAD,4=IN_PHASE)를 정의한다. 디코딩 행렬·decoder
선택은 engine이 이미 소유한다. roomestim의 좌표 인프라도 ambisonics-aware다 —
`roomestim/coords.py:28-35`에 `pipeline_to_ambix`/`ambix_to_pipeline`(az 부호
반전) 존재.

**engine schema 확인 결과**:
- `geometry_schema.json:18-22` — `regularity_hint` enum = `LINEAR/CIRCULAR/
  PLANAR_GRID/IRREGULAR`. **AMBISONICS/SPHERICAL/DOME 값 없음** → ambisonics
  리그는 schema 수정 없이는 기존 4개 enum 중 하나로 매핑해야 한다.
- `geometry_schema.json:8, 30` — 루트·per-speaker 모두 `additionalProperties:
  true` → `x_target_algorithm` 등 extension key는 schema 수정 없이 추가 가능
  (`x_wfs_f_alias_hz` 선례, `layout_yaml.py:231-238`).

**round-trip 결함(OQ-38)과 직결**: `placement_yaml_reader.py:67-76`은
`target_algorithm`을 저장하지 않고 `regularity_hint`+`x_wfs_f_alias_hz`로만 추론 →
DBAP/AMBISONICS layout은 read 시 "VBAP"로 붕괴(D50 Level-1 의도적 제외). 이 붕괴는
`tests/test_layout_round_trip.py:149-167`의 `test_dbap_target_algorithm_collapses_to_vbap`
/ `test_ambisonics_target_algorithm_collapses_to_vbap`에 **의도된 계약으로 codify**되어
있다.

**OQ-38 closure 정당화 (critic MAJOR 반영, 자기참조 트리거 제거)**: 초안은
"ambisonics 도입 자체가 OQ-38 reverse 조건을 발화시킨다"고 적었으나 이는 **자기참조
(순환)** 다 — 결함을 유발할 기능을 도입해 결함 수정을 정당화하는 구조. reverse 조건
원문(D61, `open-questions.md:665-675`)은 "DBAP/AMBISONICS 라벨 손실 보고 ≥1건 OR
engine algorithm-aware 검증 도입"이며, "미래에 손실이 예상됨"은 이를 충족하지 않는다.
정당한(더 강한) 근거는 따로 있다: OQ-38 평가 cadence가 **v0.20으로 재유예**(D61)됐는데
레포는 현재 **v0.22.x** 로 cadence가 이미 초과됐고, D26(`decisions.md`)은 **무기한
유예를 금지**한다. 따라서 OQ-38 종결은 "cadence 초과 + D26 forced-decision" 위에서
정당화한다(ambisonics 도입은 종결의 트리거가 아니라 동반 수혜자).

## Pre-conditions (critic MAJOR #1 반영)

- **require.md gating 상태**: `spatial_engine/require.md`는 현재 "WFS, VBAP, DBAP 등"만
  열거하며 **Ambisonics를 mandatory로 올리지 않았다** (`grep -ni ambison require.md` = 0건).
  ADR 0003 §Falsifier/Follow-up는 Ambisonics 빌드를 "require.md가 mandatory로 명시"에
  gate했다. 본 ADR은 그 precondition이 **여전히 미충족**임을 명시하며, 다음 독립 근거로
  진행을 정당화한다: (i) OQ-38 cadence 초과(v0.20 재유예 → 현 v0.22.x) + D26 무기한-유예
  금지, (ii) 본 ADR이 ADR 0003 Follow-up을 amend하여 "require.md mandatory" gate를
  "설계 선행 기록 + round-trip 결함 동반 종결"로 완화. **단 실제 구현 착수(PR2~)는
  require.md 갱신 또는 engine 팀 합의를 권장 gate로 둔다** (설계 문서화 PR1은 무관하게 진행 가능).

## Decision (제안)

### D-1: 개념 화해 — Ambisonics = "디코더용 규칙적 리그 배치" ((a)안 채택 제안)

Ambisonics 배치를 **"Ambisonics 디코딩에 적합한 규칙적 스피커 리그의 물리 좌표를
생성하는 또 하나의 기하 알고리즘"**으로 정의한다. roomestim은 리그 좌표만 산출하고,
SH 인코딩/디코딩 행렬·decoder 선택은 engine(`ipc_schema.md:21-22`)에 위임한다.

근거:
- 기존 `PlacedSpeaker`/`geometry_schema.json` 추상화를 무수정 재사용 — 타입 불일치
  회피.
- engine이 이미 디코딩을 소유(`/sys/ambi_order`, `/sys/ambi_decoder_type`)하므로
  roomestim이 SH 행렬을 재구현하면 책임 중복.
- "±2-5° 스피커 각도" 정밀도 목표는 물리 리그에만 의미가 있다 — (b)안(SH 채널 방출)
  에서는 무의미.

(b)안(ambisonic 채널 자체 방출)은 **기각 제안**: `position`/`az_deg`/`dist_m` 의미
붕괴 + schema 위반 + engine 책임 중복.

### D-2: order ↔ n_speakers ↔ 디코더 레이아웃 매핑

| order | SH 채널 수 (N+1)² | 권장 n_speakers (디코더 리그) | 권장 기하 |
|-------|------------------|------------------------------|-----------|
| 1     | 4                | 6 (octahedron) 또는 8 (cube)  | platonic  |
| 2     | 9                | 12 (icosahedron)             | platonic / t-design |
| 3     | 16               | 20 (dodecahedron) ~ 24       | t-design  |

원칙: 디코더 안정(역행렬 조건수)을 위해 **n_speakers ≥ (N+1)²**, 실무상
n_speakers ≈ 1.3–1.5 × (N+1)²를 권장. CLI는 `--order`를 1차 입력으로 받고
`--n-speakers`는 (a) 미지정 시 order에서 권장값 추론, (b) 지정 시 `n_speakers ≥
(N+1)²` 검증 후 가장 가까운 규칙적 리그로 라운딩하는 방식을 제안. (정확한 추론
규칙은 OQ-신규로 분리 — 아래.)

### D-3: 레이아웃 기하 — t-design 우선, platonic 폴백

- **1순위 t-design** (spherical t-design): 정해진 차수 t에 대해 구 위 점들이 SH를
  차수 t까지 정확 적분 → 디코더 조건수 최적, 준-등방. order N 디코딩엔 t ≥ 2N
  설계 사용.
- **소수 order의 platonic 폴백**: order 1=octahedron(6)/cube(8),
  order 2=icosahedron(12), order 3=dodecahedron(20). 좌표가 닫힌 형태라 테이블
  의존 없음.
- **기존 VBAP dome 재사용은 기각 제안**: `place_vbap_dome`(`vbap.py:129-212`)은
  2개 stacked equal-angle ring이라 천정/바닥을 비우고 두 위도에 집중 → 구 전체
  미커버, SH 직교성 열화, ±2-5° 정밀도와 디코더 안정성 보장 불가.
- **재사용 가능 헬퍼**: ring 기반 폴백 리그에 한해 `_equal_angle_ring`
  (`vbap.py:47-74`)·`_unit_aim_to_listener`(`vbap.py:33-44`)는 재사용 가능.

`regularity_hint`는 schema enum 제약(`geometry_schema.json:18-22`)상 신규 값 불가.
구형 준-등방 리그는 단일 평면 ring이 아니므로 **`IRREGULAR`로 매핑 제안**
(R10 min_speaker=1, 통과 — `layout_yaml.py:135-140`). 단일 ring 폴백 시에만
`CIRCULAR`(min 3).

### D-3a: engine 식별·라우팅 gate (critic "What's Missing" 반영 — pre-implementation 차단)

(a)안의 load-bearing 가정은 **"engine이 이 리그를 ambisonics 디코더로 라우팅한다"**
이다. 그러나 `regularity_hint=IRREGULAR`만으로는 engine이 ambisonics 리그를 일반
IRREGULAR 멀티스피커 layout과 구분할 수 없다 — engine이 IRREGULAR를 VBAP-weighting
경로로 보내면(엔진 측 regularity 분기) roomestim이 만든 좌표가 **잘못된 알고리즘으로
렌더**된다. 따라서 다음을 **PR2 착수 전 필수 해소(gate)**로 둔다:
1. engine이 layout.yaml에서 ambisonics 리그를 식별하는 메커니즘 확정 — `x_target_algorithm
   == "AMBISONICS"` (+ `x_ambisonics_order`)를 engine이 실제 읽어 디코더로 라우팅하는지,
   아니면 별도 신호가 필요한지 engine 팀과 합의.
2. 합의 전에는 본 ADR의 Consequences "(+) 4번째 알고리즘 합류"는 **roomestim 측 좌표
   생성에 한정**되며, end-to-end 디코딩 경로는 미확정임을 명시. (Reverse-criterion (a)가
   이를 post-hoc fallback으로 다뤘으나, 본 항목은 이를 pre-implementation gate로 승격.)

### D-4: engine 계약 — layout.yaml 표현 + OQ-38 동시 종결 제안

- 리그 좌표는 기존 spherical 형식으로 그대로 emit(`layout_yaml.py:195-209`) —
  schema 무수정.
- **`x_target_algorithm` top-level extension key 신설 제안** (OQ-38 후보 (1)):
  - writer `placement_to_dict`(`layout_yaml.py:217-239`)가 모든 알고리즘에 대해
    `x_target_algorithm = result.target_algorithm`을 emit (WFS의
    `x_wfs_f_alias_hz` 선례와 동일, `additionalProperties: true` 활용).
  - reader `read_placement_yaml`(`placement_yaml_reader.py:67-76`)가 이 키를
    추론보다 **우선** 복원; 부재 시 기존 추론 폴백(하위호환).
  - → DBAP/AMBISONICS round-trip 라벨 손실 종결. ambisonics 도입이 OQ-38 reverse
    조건을 발화시키므로 묶어 닫는 것이 합리적.
- ambisonics order는 `x_ambisonics_order` extension key로 함께 emit 제안(engine이
  `/sys/ambi_order`로 소비 가능; engine 소비 여부는 협의 대상).

### D-5: dispatch / CLI 통합

- `dispatch.run_placement`(`dispatch.py:24-93`)에 `algorithm == "ambisonics"` 분기
  추가, 신규 `roomestim/place/ambisonics.py::place_ambisonics(order, ...)` 호출.
- `cli.py`의 place/run choices(`:59, :170`)에 `"ambisonics"` 추가.
- `--order` (1|2|3) 인자 신설; `--n-speakers`는 ambisonics에서 선택적(미지정 시
  order 추론). VBAP 전용 `--layout-radius`/`--el-deg`는 ambisonics에선 radius만
  의미(리그 반경), elevation은 기하가 결정.

## Scope / Non-goals

- **In scope**: 규칙적 디코더 리그의 물리 좌표 생성, layout.yaml emit,
  CLI/dispatch 통합, round-trip 라벨 보존(OQ-38).
- **Non-goals (engine 책임)**: SH 인코딩/디코딩 행렬 산출, decoder type 선택
  (PINV/MAX_RE/ALLRAD/EPAD/IN_PHASE), 실제 오디오 렌더 — 모두
  `spatial_engine`(`ipc_schema.md:21-22`) 소관. roomestim은 리그 배치만.

## 검증 전략 (제안)

1. **각도 정밀도 ±2-5°**: 생성 리그의 각 스피커 (az,el)을 platonic/t-design
   기준 좌표와 비교, 최대 각도 오차 ≤ 5° assert.
2. **리그 대칭성**: 모든 스피커가 반경 동일(±tol), 중심(centroid)이 원점 근방,
   인접 각 분포의 균질성(준-등방) 점검. order N → SH 모드 행렬 조건수가 임계 이하임을
   검증(디코더 안정 대리 지표).
3. **round-trip 충실도**: write→read→write 후 `target_algorithm == "AMBISONICS"`
   보존(현재는 "VBAP" 붕괴) + 좌표 D50 fixed-point(≤1e-9) 유지.
4. **R10/R11 게이트**: `write_layout_yaml` pre-flight 통과
   (`IRREGULAR` min=1), finite-sweep 통과.

## PR 분할 (제안)

- PR1: `x_target_algorithm` writer/reader + golden 갱신 (OQ-38 종결, ambisonics와
  독립적으로 가치 있음). **반드시 포함(critic MAJOR #3)**: (i) 기존 collapse 계약
  테스트 `test_dbap_target_algorithm_collapses_to_vbap` / `test_ambisonics_target_algorithm_collapses_to_vbap`
  (`tests/test_layout_round_trip.py:149-167`)를 **라벨 보존 expect로 invert**, (ii)
  해당 모듈 docstring(현재 collapse를 계약으로 기술) 갱신, (iii) golden 재생성 —
  단일 fixture `tests/fixtures/golden/place_vbap_ring_n8_default.yaml`에
  `x_target_algorithm: VBAP` 추가(blast radius 작음). emit-for-all vs non-VBAP-only는
  PR1에서 결정(WFS의 `x_wfs_f_alias_hz`는 non-WFS엔 미방출 선례 — golden churn 최소화
  관점에선 non-VBAP-only가 유리). **본 ADR은 "emit-for-all"을 1안으로 제안하되 PR1
  실측 golden churn 보고 후 확정.**
- PR2: `place/ambisonics.py` 코어(platonic 우선) + 단위테스트(대칭/각도). **D-3a engine
  라우팅 gate 해소 후 착수.** scipy(`>=1.10`, 기존 의존)로 platonic 좌표 생성 + 조건수
  검증 가능 — 신규 의존 불요.
- PR3: dispatch/CLI 통합 + `--order`. **신규 OQ(n_speakers 라운딩 규칙) 해소 후 착수.**
  `--el-deg`/`--layout-radius`는 ambisonics에서 radius만 의미; `--el-deg`를 ambisonics와
  함께 주면 **경고 후 무시**(silent ignore 아님)로 제안.
- PR4: t-design 테이블 + order 3 고품질 리그 (선택). t-design **점좌표 테이블만** 외부
  의존(출처/라이선스는 신규 OQ); 조건수 검증은 scipy로 자체 가능.

## Consequences

- (+) 4번째 배치 알고리즘이 기존 추상화 무수정으로 합류; ADR 0003 Follow-up 이행.
- (+) OQ-38 라벨 붕괴가 부수적으로 종결(PR1).
- (+) engine 책임 경계(디코딩=engine, 리그=roomestim) 문서화.
- (−) `x_target_algorithm` 도입은 기존 golden layout.yaml 재생성 필요(byte-equal
  깨짐) — D56 round9 경로는 유지되나 키 추가로 파일 변동.
- (−) `--order`/`--n-speakers` 이중 입력은 검증·문서 부담 추가.
- (−) t-design 점좌표는 외부 테이블 의존(소수 order는 platonic 닫힌형으로 회피).

## Reverse-criterion (재개/철회 조건)

- (a) engine이 layout.yaml에서 `x_target_algorithm`/`x_ambisonics_order`를 실제
  소비하지 않음이 확인되면 → extension key emit를 보류하고 리그 좌표만 유지.
- (b) require.md/engine이 "리그가 아닌 SH 채널 자체"를 layout으로 요구하면 →
  (b)안 재검토 + schema 협상(현 `geometry_schema.json`은 위치 필수라 불가).
- (c) ±2-5° 정밀도가 platonic으로 미달하면 → t-design을 1순위로 승격.

## OQ / decisions 갱신 제안

- **OQ-38**: 본 ADR PR1로 **CLOSE 제안** (`x_target_algorithm` 후보 (1) 채택). reverse
  조건(라벨 손실)이 ambisonics 도입으로 발화됨을 명시. **→ v0.33.0 (D102)에서 CLOSED**
  (§Status-update-v0.33.0 참조).
- **신규 OQ (ambisonics order↔n_speakers 추론 규칙)**: `--n-speakers`
  미지정 시 order→권장값 추론 정확 규칙, 사용자가 비표준 n을 줄 때 가장 가까운
  규칙 리그로 라운딩할지/거부할지. evaluation cadence는 PR3 착수 시.
- **신규 OQ (t-design 좌표 출처/검증)**: order 3 t-design 테이블의
  출처(문헌)와 라이선스, fixture 검증 방법. PR4 착수 시.
- **decisions.md**: D-1~D-5에 대응하는 신규 D 항목(현재 최신 D73 → D74~) 등록 제안.

## References

- `roomestim/place/algorithm.py:13-19` — TargetAlgorithm enum, AMBISONICS stub.
- `roomestim/place/dispatch.py:24-93` — run_placement 분기 (ambisonics 미지원).
- `roomestim/place/vbap.py:33-74, 129-212` — 재사용 가능 헬퍼 + dome(재사용 부적합).
- `roomestim/model.py:292-319` — PlacedSpeaker / PlacementResult 필드.
- `roomestim/export/layout_yaml.py:135-140, 195-239` — R10 min_speaker, writer,
  x_wfs_f_alias_hz extension 선례.
- `roomestim/io/placement_yaml_reader.py:67-76` — target_algorithm 추론(붕괴 지점).
- `roomestim/coords.py:28-35` — pipeline↔ambix 변환 인프라(기존).
- `roomestim/cli.py:58-62, 169-172` — place/run choices(ambisonics 미노출).
- `spatial_engine/proto/geometry_schema.json:8, 18-22, 27-83` — regularity enum
  (ambisonics 값 없음 확인), additionalProperties:true.
- `spatial_engine/proto/ipc_schema.md:21-22` — /sys/ambi_order, ambi_decoder_type
  (디코딩 = engine 책임 확인).
- `docs/adr/0003-placement-algorithm-priority.md:15, 44` — 알고리즘 우선순위 +
  ambisonics Follow-up.
- `.omc/plans/open-questions.md:524-535, 665-675` — OQ-38 상세 + reverse 조건.

---

## Consensus Addendum (핵심 antithesis)

- **Antithesis(steelman) against (a)안**: 사용자가 "Ambisonics 지원"을 들으면 SH 인코딩
  출력을 기대할 수 있는데, (a)안은 "디코더용 스피커 리그"만 준다. 향후 engine이
  layout.yaml 대신 AmbiX B-format을 직접 받는 파이프라인을 추가하면 (a)안은 그
  needs를 못 채운다. 다만 현 시점 `ipc_schema.md:21-22` 증거는 engine이 디코딩을
  소유함을 명확히 보이므로, (a)안이 현 아키텍처와 정합한다.
- **Tradeoff tension**: OQ-38을 이 ADR에 묶으면(범위 ↑, golden 재생성) vs 분리하면
  (ambisonics 신기능이 출시 즉시 round-trip 결함 보유). 권고는 PR1로 분리하되 같은
  ADR 하에 종결 — 결함 동반 출시를 피하면서 PR 단위는 독립.

---

## Status-update-v0.33.0 (2026-06-08, Phase 4, D102)

**PR1 SHIPPED — OQ-38 CLOSED.** `x_target_algorithm` top-level extension key
(후보 (1)) 채택·구현. writer(`export/layout_yaml.py:placement_to_dict`)는
non-VBAP(DBAP/WFS/AMBISONICS)에만 키 방출(VBAP=reader 자연 기본값 → golden
`place_vbap_ring_n8_default.yaml` **byte-equal**; ADR §PR 분할에서 제안된
"emit-for-all" 대신 **non-VBAP-only**를 PR1에서 채택 — `x_wfs_f_alias_hz`/
`x_geometry_provenance` 의 "emit only when non-default" 선례와 golden churn 0).
reader(`io/placement_yaml_reader.py`)는 restore-first/infer-fallback: 키 있으면
복원하되 enum `{VBAP,DBAP,WFS,AMBISONICS}` 검증(out-of-enum → `ValueError`,
`_parse_provenance` 가드 미러), 없으면 기존 추론(pre-v0.32 key-less backward-compat).
collapse 계약 테스트 2건 invert(→ preservation) + 5건 신규. schema 무변경
(`additionalProperties:true`). default 452→457p, web 86p 무변, ruff/mypy(strict) EXIT0.

**정직성**: PR1은 round-trip **라벨**만 종결 — roomestim 은 여전히 ambisonics rig 을
**생산하지 않는다**(placement producer 부재). "roomestim supports ambisonics" 주장 금지.
AMBISONICS enum 멤버는 ADR 0003 forward-compat 로 유지(삭제 안 함).

**PR2-4 DEFERRED.** `place/ambisonics.py` producer + dispatch branch + CLI `--order`
는 미착수 유지. **Trigger(gate) = §D-3a engine 식별·라우팅 gate**: engine 이
`x_target_algorithm=="AMBISONICS"` 를 읽어 SH 디코더(`ipc_schema.md:21-22`
`/sys/ambi_order`)로 라우팅함을 확인(engine 팀 합의) **또는** `spatial_engine/require.md`
가 Ambisonics 를 mandatory 로 승격(§Pre-conditions). 둘 다 현재 미충족 → decoder 없이
rig 방출 시 end-to-end 검증 불가한 fake-completeness trap(§5)이므로 DEFER 유지.

---

## Status-update (2026-06-12, C3 — DEFER reconfirmed)

**Gate re-checked 2026-06-12.** Both require.md variants searched:
- `grep -ni ambison /home/seung/mmhoa/spatial_engine/require.md` → **0 hits**
- `grep -ni ambison /home/seung/mmhoa/spatial_engine-convergence/require.md` → **0 hits**

The §Pre-conditions gate (require.md mandatory promotion OR engine-team agreement) remains
**unmet**. Engine IPC capability exists (`proto/ipc_schema.md:21-22` `/sys/ambi_order` +
`/sys/ambi_decoder_type`) but capability ≠ requirement promotion — emitting an ambisonics
rig with no contracted consumer is the fake-completeness trap §D-3a was written to prevent.

**PR1 status**: SHIPPED v0.33.0 commit `15e4b8a` (D102) — `x_target_algorithm` round-trip
label preservation. This was the only roomestim-internal, data-free slice of ADR 0041; no
further data-free slice remains.

**PR2-4 status**: DEFERRED, unchanged. Trigger remains: `spatial_engine/require.md`
promotes Ambisonics to mandatory, OR engine-team agreement that `x_target_algorithm ==
"AMBISONICS"` routes to the SH decoder (`/sys/ambi_order`). Neither condition is met as of
this date.

**North-star note**: Ambisonics rig geometry is product-peripheral (acoustics/placement
lowest priority per roomestim north star). This DEFER is not a gap — it is the correct
outcome until the engine-side contract is established.

---

## Status-update (2026-06-17, CAND-3 — PR2+PR3 SHIPPED experimental)

**v0.39.0 (D104).** PR2 (platonic rig geometry) + PR3 (dispatch/CLI wiring) ship as an
EXPERIMENTAL, opt-in, honestly-disclosed COORDINATE-generation slice. PR4 (t-design)
stays DEFERRED.

**Why §D-3a point-2 legitimately applies (gate-respecting).** §D-3a has two points.
Point 1 (engine identifies/routes the rig to the SH decoder) is the END-TO-END gate and
remains UNMET — `grep -ni ambison spatial_engine/require.md` still returns 0 hits and there
is no engine-team routing agreement. Point 2 EXPLICITLY permits roomestim-side rig
**coordinate generation** to proceed provided the end-to-end decoding uncertainty is
disclosed. We shipped ONLY coordinate generation (pure, closed-form, exactly verifiable
math) and made the "decode/route is engine-gated and UNCONFIRMED" statement load-bearing and
unavoidable: a single-source-of-truth constant `AMBISONICS_RIG_DISCLOSURE`
(`roomestim/place/ambisonics.py`) printed to stderr on every `place`/`run --algorithm
ambisonics` invocation, plus README + this ADR. No fake capability: roomestim emits rig
COORDINATES; it does NOT SH-encode/decode, does NOT compute the decode matrix, does NOT
select a decoder type, and does NOT assert the engine will consume the rig.

**Design choices recorded.**
- **order → rig (closed-form, no external table):** 1 → octahedron (n=6, n≥4), 2 →
  icosahedron (n=12, n≥9), 3 → dodecahedron (n=20, n≥16); each n ≥ (N+1)². Cube-8 is a
  documented future alternative for order 1; v1 ships octahedron-6 only (deterministic n,
  sidesteps the n_speakers-inference OQ).
- **regularity_hint = IRREGULAR** (R10 min 1). Risk: an engine that branches IRREGULAR to
  VBAP-weighting would render the rig with the WRONG algorithm — exactly why the disclosure
  is load-bearing and the slice is labelled experimental.
- **Verification = numpy-only second-moment isotropy proxy**, NOT a scipy SH condition
  number. scipy renamed `sph_harm` → `sph_harm_y` in 1.15+, making the SH-matrix
  `np.linalg.cond` path version-fragile; the second-moment matrix M = VᵀV/n = (1/3)·I (a
  spherical-2-design property, verified exact: max|M−I/3| ≤ 5.6e-17, cond ≈ 1.0) is an
  equivalent decoder-stability proxy for these symmetric rigs with zero new dependency.
  **New-dep count = 0** (numpy is already core).

**Promotion trigger to remove "experimental"** (unchanged, = §D-3a point 1):
`spatial_engine/require.md` promotes Ambisonics to mandatory, OR engine-team agreement that
`x_target_algorithm == "AMBISONICS"` routes to the SH decoder (`/sys/ambi_order`). Until
then the experimental label and the UNCONFIRMED disclosure stand. PR4 t-design remains
DEFERRED (external coordinate table + license/source = new OQ; order-3 dodecahedron-20 is
sufficient for the experimental slice).
