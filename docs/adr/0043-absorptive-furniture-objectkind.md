# ADR 0043 — 흡음 가구 ObjectKind 확장 + 자동 인식 정책 (draft)

- **Date**: 2026-05-29
- **Status**: Proposed (draft — 미구현; 본 문서는 설계 제안이며 코드/테스트는 아직 존재하지 않는다. 시제는 모두 제안/예정이다.) **REVISED 2026-05-29** — critic 리뷰(REVISE; 1 CRITICAL + 2 MAJOR, citation 정확도 100%) 반영: (1) **B-1→B-2 정정** — ISM shoebox 경로는 area-weighted-α 라 합성-surface(B-1)가 α 를 희석할 뿐 sabin 을 주입 못함; ISM 은 sabin 직접 누적(B-2) 필수(§B), (2) §G double-count mischaracterization 정정 + ISM sabin-magnitude/단일-predictor identity/shoebox-경계 불연속 검증으로 재설계, (3) sofa/curtain A_500 provenance honesty-gap + surface-vs-Object double-count 경계 명시(§C).
- **Deciders**: architect (설계 제안), critic (리뷰 예정), planner (확정 예정)
- **Refs**: ADR 0011, ADR 0013 (equivalent-absorption-area 선례), ADR 0019 (enum 추가 선례), ADR 0030, ADR 0031, ADR 0034 §D (object schema scope), ADR 0037; D26 (forbidden-indefinite-deferral / YAGNI), D46, D54; OQ-33 (자동 인식 deferred)

> **핵심요약 (권장안)**: ObjectKind enum 확장(흡음 가구)과 자동 인식을 **분리**하고, enum 확장(B7-A)만 선행하되 가구를 column 5-face 도 door/window α-override 도 아닌 **ACE 의 `MISC_SOFT` equivalent-absorption-area 패턴(ADR 0013 선례)** 으로 모델링할 것을 제안한다. 자동 인식(B7-B)은 RoomPlan sidecar category 확장만 즉시 가치가 있고, mesh BoundingBox 클러스터링은 OQ-33 hard-wall 미충족이므로 deferred 유지. **단 D26-YAGNI 긴장(사용자 보고 0건)을 고려해 검증(PR4: 가구 흡음 미반영 vs 반영 RT60 차이 측정)을 enum 확장(PR1)보다 먼저 두어, 측정된 정확도 손실이 ±20% 예산을 잠식할 때만 enum 을 여는 안을 권한다(§Consensus Synthesis).**

---

## Context

### 현 상태 (코드 확인 사실)

`ObjectKind = Literal["column", "door", "window"]` (`roomestim/model.py:134`) 는 **건축 요소 3종만** 표현한다. `Object` dataclass (`model.py:224~243`) 는 `kind / anchor / width_m / height_m / depth_m / wall_index / material` 필드를 가지며, `DEFAULT_OBJECT_MATERIAL` (`model.py:248~252`) 은 `column→WALL_CONCRETE`, `door→WALL_PAINTED`, `window→GLASS` 로 매핑한다. `MaterialLabel` (`model.py:46~56`) 은 10-entry closed enum이고, 흡음 가구 근사로 사용 가능한 항목은 `MISC_SOFT` (α_500=0.40, `model.py:70`; bands `model.py:104`) 하나뿐이다.

객체→음향 경로는 두 가지로 **이미 작동**한다 (`reconstruct/predictor.py`):

1. **column** → `_objects_to_surfaces()` (`predictor.py:209~268`): 기둥당 5 surface (4 측면 `kind="wall"` + top `kind="ceiling"`) 를 생성, ISM/Eyring 의 area-weighted α 평균에 합산.
2. **door/window** → `_objects_to_wall_alpha_overrides()` (`predictor.py:271~310`): 새 surface가 아니라 부착 벽의 α를 면적가중 blend로 patch (D46 혼합 절충).

이 fold는 **ISM (shoebox) 분기에서만** 객체를 반영한다 (`predictor.py:453~507` / `:528~588`). 비-shoebox Eyring 분기 (`predictor.py:509`, `:590`) 는 caller가 전달한 `surface_areas_by_material` dict만 사용한다. web 경로에서 이 dict를 만드는 `roomestim_web/report.py:37~59` 의 `_surface_areas_by_material()` 는 column 5-face를 `_objects_to_surfaces()` 로 합산하지만, door/window α-override는 **의도적으로 제외**한다 (`report.py:42~44` 주석). 즉 비-shoebox 방의 door/window 흡음은 현재 음향에 반영되지 않는다 (확인된 현 동작; B7 설계 시 고려 대상).

스모크 확인(사용자 보고): shoebox 방에 glass window 추가 시 RT60 1.594→1.599s — door/window α-override 경로가 shoebox에서 살아있음을 입증.

### 자동 인식 현황

- **RoomPlan adapter** (`adapters/roomplan.py:130~182`): `_extract_objects()` 가 sidecar `objects[]` 의 `category` 문자열에 대해 case-insensitive substring match로 column/pillar/door/window만 추출하고, 그 외 (chair, table, …) 는 `continue` 로 무시 (`roomplan.py:151~152`). 가구 category는 데이터에 존재해도 버려진다.
- **Mesh adapter** (`adapters/mesh.py:192`) 와 **ACE adapter** (`ace_challenge.py:721`): `objects=[]` placeholder. 라벨 정보 부재.
- OQ-33 (`open-questions.md`): 자동 인식의 manual-annotation 부분은 v0.17에서 충족(D54)되었고, **adapter 무인 자동 추출**만 잔여로 v0.20 hard-wall에 재연기. D26 trigger 2종 ((a) non-RoomPlan 자동추출 요청 ≥1건, (b) mesh-only object-GT fixture 도입) 은 **여전히 미충족**. bbox 클러스터링은 "미안정 + GT fixture 부재로 검증 불가" 로 명시 (decisions.md D54).

### TASLP 가구 선례 (ADR 0013 / 메모리)

ACE adapter는 가구를 **개별 Object/Surface로 모델링하지 않는다**. `_furniture_to_misc_soft_area()` (`ace_challenge.py:265~311`) 가 per-piece equivalent absorption A_i (m² Sabines/item; `ace_challenge.py:209~227`) 의 합을 `area = ΣA_i / α_MISC_SOFT` 로 환산해 **단일 합성 MISC_SOFT surface** 하나를 생성한다 (`ace_challenge.py:314~388`). 폴리곤 좌표는 음향적으로 무의미하고 **면적만** Sabine/Eyring integrand에 기여한다. 메모리 정합: TASLP §II-C는 furniture **counts만** 제공(재질 assignment 없음) — 이 패턴은 가구를 "장비 흡음 예산"으로 추상화한 것이다.

### 문제

카펫·소파·커튼·서가가 많은 거실/회의실에서 흡음 가구가 ObjectKind에 없어 RT60 정확도 손실이 발생할 수 있다(특히 흡음 dominant 룸). 정밀도 목표는 Sabine RT60 ±20%이며 캡처 노이즈가 dominant이므로, 가구 흡음의 누락은 체계적 편향(systematic bias)으로 ±20% 예산을 잠식할 수 있다 — 단, 이 손실의 정량적 크기는 **현재 측정된 바 없다** (가구 있는 ACE/SoundCam 룸 대조 검증이 본 ADR의 입증 항목).

---

## Decision

### §A — 두 갈래 분리 및 우선순위

B7을 두 독립 작업으로 분리한다:

- **B7-A (ObjectKind enum 확장 + per-kind 흡음 모델)** — 수동 add 경로(`evolve_room_add_object`, `object_add.py`)로 **즉시 가치**. 자동 인식에 의존하지 않음. **우선 구현 제안** (단 §Consensus 의 선검증 조건부).
- **B7-B (자동 인식)** — RoomPlan sidecar category 확장(저비용)과 mesh BoundingBox 클러스터링(고비용·미검증)으로 다시 분리.

B7-A는 B7-B의 선행조건이다(자동 인식이 산출할 객체의 데이터 모델·음향 경로가 먼저 존재해야 함). 따라서 **B7-A 선행, B7-B는 OQ-33 trigger 충족 시점까지 deferred 유지**를 제안한다.

### §B — per-kind 흡음 모델 (핵심 설계 결정)

신규 흡음 가구 kind(예: `sofa`, `bookshelf`, `curtain`, `table`)는 **column의 5-face surface 패턴도, door/window의 wall-α-override 패턴도 적합하지 않다**:

- 5-face(column) 패턴: 가구를 직육면체 외피로 모델링하면 표면적이 과대평가되고(소파는 외피가 아니라 흡음체), top면이 ceiling α에 잘못 합산된다.
- wall-α-override(door/window) 패턴: 가구는 벽 부착물이 아니라 자립형(free-standing)이므로 부착 벽이 없다.

대신 **ACE의 equivalent-absorption-area 패턴(ADR 0013)을 재사용**할 것을 제안한다: 각 흡음 가구 kind에 per-piece equivalent absorption A_500(m² Sabines/item)을 부여하고, 단일 합성 흡음 surface로 환산하거나(ACE식) 또는 predictor 단계에서 직접 sabin을 누적한다. 두 하위안:

- **B-1 (합성 surface 환산식, ACE 선례)**: `area = A_500/α_furniture` 인 단일 합성 surface 를 emit. **ACE identity (`ace_challenge.py:273~283`)는 Sabine/Eyring 의 *additive* integrand(`area × α` 합산, materials.py:83~85)에서만 sabin 을 보존한다.**
- **B-2 (predictor 에 sabin 누적 경로 신설)**: 가구를 area 가 아닌 absorption sabin 으로 ISM/Eyring 분자에 직접 더하는 신규 helper.

> **⚠️ 권장안 정정 (critic CRITICAL)**: 초안은 B-1 을 "양 predictor 분기 무수정 재사용"으로 권했으나 이는 **ISM 경로에서 물리적으로 틀렸다**. ISM shoebox 분기는 면(face) 면적을 **고정**(`predictor.py:155` `areas=(L*W, L*W, L*H, ...)`)하고 면별 α 를 **area-weighted-average**(`predictor.py:180`)로 blend 한다. 여기에 큰 면적의 합성 가구 surface 를 extras 로 넣으면, 그 면적은 floor α 를 misc_soft 쪽으로 **희석(dilute)** 할 뿐 의도한 `A_500` sabin 을 주입하지 못한다 — floor 기여는 여전히 `(L*W) × α_blended` 이지 `합성면적 × α_misc_soft` 가 아니다. shoebox(가장 흔한 방)에서 가구의 RT60 효과가 거의 0 또는 wrong-signed 로 **silently** 나온다.
>
> **정정된 권장**: **ISM(shoebox) 경로는 B-2(sabin 직접 누적)**, **Sabine/Eyring(additive) 경로만 B-1**. 즉 `_objects_to_surfaces()` 의 가구 emit 에 명시적 `absorption_area_m2`(sabin) 항을 실어 ISM `image_source_rt60` 가 면적-α-blend 가 아니라 별도 sabin term 으로 합산하게 한다. 이러면 shoebox/비-shoebox 양쪽에서 가구 흡음이 일관되게 반영된다(아래 §G shoebox-경계 불연속 항 참조).

### §C — MaterialLabel 신규 필요 여부

흡음 가구용 신규 MaterialLabel은 **불필요할 수 있다**: per-piece A_500을 가구 kind별 상수 dict(ACE `_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2` `:209~215` 와 동형)로 두면, surface의 α는 기존 `MISC_SOFT`(0.40) 를 reference로 쓰고 area로 sabin을 맞추는 ACE식 환산이 그대로 성립한다(`ace_challenge.py:273~283` 의 integrand 보존 identity). 단 커튼/카펫처럼 α 프로파일이 MISC_SOFT와 유의하게 다른 경우(커튼은 고주파 흡음 강함) 별도 band-tuple이 필요할 수 있으므로, ADR 0019(MELAMINE_FOAM enum 추가) 선례에 따라 **신규 kind ≥1종이 MISC_SOFT band 프로파일로 >30% 오차를 보이면 신규 MaterialLabel 추가**를 reverse-trigger로 둘 것을 제안한다.

`DEFAULT_OBJECT_MATERIAL` (`model.py:248`) 에 신규 kind별 기본 재질 entry 추가가 필요하며, `ObjectKind` Literal 확장 시 이 dict가 모든 kind를 cover해야 한다(현재 `object_add.py:47` 와 `roomplan.py:168` 가 `DEFAULT_OBJECT_MATERIAL[kind]` 를 KeyError 없이 인덱싱하는 것에 의존).

**per-piece A_500 provenance (critic 지적 — honesty gap)**: ACE `_PIECE_EQUIVALENT_ABSORPTION_500HZ_M2`(`:209~215`)는 chair/table/bookcase 만 cover 하고 **sofa/curtain 상수는 존재하지 않는다**. 신규 가구 kind 의 A_500 은 representative source(Vorländer 2020 / Bies & Hansen / Beranek 등)에서 honesty-marked 로 도입해야 하며, source 미확보 시 해당 kind 는 enum 에 넣지 않는다(ADR 0011/0013 honesty-marker 정책 동일 적용). PR1 은 source 가 확보된 kind 만 land.

**surface-vs-Object 경계 (critic ambiguity 해소)**: 가구는 **`room.surfaces` 에 append 하지 않고 `Object`-derived extra(`_objects_to_surfaces()` 산출물)로만** 다룬다. ACE 처럼 real `Surface` 로 append 하면 `report.py:55`(surfaces 루프) + `report.py:57`(extras) 에서 double-count 된다. Object-derived 단일 경로로 고정.

### §D — 자동 인식 설계

- **RoomPlan sidecar 확장 (저비용, 즉시 가능)**: `_extract_objects()` (`roomplan.py:130`) 의 substring match에 가구 category(sofa/couch/table/chair/bookshelf 등)를 추가. sidecar는 이미 category를 제공하므로 GT fixture 없이도 결정론적 매핑이 가능(검증은 fixture sidecar에 가구 entry 추가로 단위테스트 가능). 단 RoomPlan이 가구 dimensions를 제공해도 **재질은 제공하지 않으므로** `DEFAULT_OBJECT_MATERIAL` fallback에 의존 — 재질 추정 불확실성이 가장 큰 리스크.
- **Mesh BoundingBox 클러스터링 (deferred 유지 제안)**: 메시(.obj 등)는 라벨이 없어 bbox 클러스터링 + geometric heuristic이 필요. OQ-33 가 "미안정 + GT fixture 부재로 검증 불가" 로 명시했고 D26 trigger 미충족이므로, B7로 이 항목을 끌어올리지 말고 OQ-33의 v0.20 hard-wall 평가에 위임할 것을 제안한다. **대안**(미안정 클러스터링 대신): (1) Polycam Pro segmentation API 소비(비공개·Linux-CI 불가), (2) 사용자 수동 annotation(이미 `object_add.py` 로 가능 — 가구 kind만 추가하면 즉시 작동).

**자동 vs 수동 경계**: B7-A 구현 시 수동 경로(web UI)는 즉시 가구를 지원한다. 자동 경로는 RoomPlan sidecar만 저비용으로 확장하고, mesh는 수동 fallback에 의존.

### §E — Scope / Non-goals

**Scope (B7-A 제안 범위)**:
- `ObjectKind` Literal에 흡음 가구 kind 추가(구체적 enum 멤버는 planner 결정 — sofa/bookshelf/curtain/table 후보).
- per-kind equivalent absorption dict + `_objects_to_surfaces()` 가구 분기(B-1).
- `DEFAULT_OBJECT_MATERIAL` entry 추가, `object_add.py` UI에 가구 kind radio 추가.
- RoomPlan sidecar category 확장(B7-B 일부, 저비용).

**Non-goals**:
- Mesh BoundingBox 클러스터링(OQ-33 deferred 유지).
- 가구의 기하학적 외피 모델링(소파의 정확한 형상) — equivalent absorption 추상화로 충분.
- 곡선 가구(OQ-34 cylinder 정책과 별개).
- 비-shoebox Eyring 경로의 door/window α-override 통합(별도 OQ — 현 `report.py:42` 제외 동작은 본 ADR 범위 밖).

### §F — PR 분할 제안

1. **PR1** — `ObjectKind` enum 확장 + per-kind absorption dict + `_objects_to_surfaces()` 가구 분기(B-1) + `DEFAULT_OBJECT_MATERIAL` entry. 회귀 lock: 기존 column/door/window 경로 byte-equal(D47 invariant 유지).
2. **PR2** — `object_add.py` web UI 가구 kind 지원 + viewer(`viewer.py:189~292`) 렌더 분기.
3. **PR3** — RoomPlan sidecar category 확장 + fixture sidecar에 가구 entry 추가 + 단위테스트.
4. **PR4 (조건부 — §Consensus 에 따라 PR1 보다 먼저 권장)** — 가구 있는 ACE/SoundCam 룸 대조 검증 harness(가구 흡음 미반영 vs 반영 RT60 차이 측정; ±20% 영향 입증).

### §G — 검증 전략

- **ISM sabin-magnitude 입증 (critic CRITICAL/MAJOR 반영 — 최우선)**: shoebox 방에서 `ISM_RT60(가구有) ≠ ISM_RT60(가구無)` 가 **올바른 sabin 크기**만큼 차이나는지 검증한다. 구체적으로 ISM 경로가 가구를 흡수한 sabin 총량 == `Σ A_500`(직접 손계산) 인지 확인 — 단순히 "두 adapter 결과 일치"가 아니라 sabin 크기를 falsifiable 하게 고정한다(α-dilution 결함이 재발하면 이 게이트가 잡는다).
- **additive identity 교차검증 (단일 predictor 강제)**: ObjectKind 가구 RT60 vs ACE 합성 MISC_SOFT surface RT60 비교는 **반드시 `prefer_ism=False` 로 양쪽을 강제**해 동일 additive integrand 에서 수행한다. (초안은 ACE→Eyring vs web→ISM 을 비교해 서로 다른 integrand 라 unfalsifiable 했다 — critic MAJOR.)
- **shoebox-경계 불연속 방지**: B-2(sabin 누적)를 ISM·Eyring 양쪽에 동일 적용하므로, 같은 방이 `is_rectilinear_shoebox` 경계에서 ISM↔Eyring 으로 라우팅이 바뀌어도 가구 흡음 효과가 **불연속적으로 변하지 않아야** 함을 테스트로 고정(B-1 을 ISM 에 썼다면 발생했을 user-visible 불일치 — critic What's Missing).
- **기존 Object 경로 회귀 0**: column/door/window 의 ISM 결과가 enum 확장 후에도 byte-equal(D47 회귀 lock 확장).
- **double-count 주의 (초안 mischaracterization 정정)**: critic 확인 결과 `predict_rt60_default` 의 ISM/Eyring 분기는 **상호배타**(ISM 은 `agg_areas` 무시, Eyring 만 사용)이므로 default cascade 에 double-count 는 없다. 단 B-1 을 합성 surface 로 쓸 경우 `report.py:55`(room.surfaces 루프) + `report.py:57`(extras) 양쪽 합산 시 **진짜 double-count** 가능 — 그래서 §B 가 "room.surfaces 에 append 하지 말고 Object-derived extra 로만" 경계를 명시(아래 ambiguity 해소).
- **SoundCam 룸**: 별도 fixture 필요(**SoundCam fixture 가용성: 확인 불가**).

---

## Consequences

- (+) 흡음 가구를 수동 경로로 즉시 모델링 가능 — 거실/회의실 RT60 편향 감소(정량은 검증 후 확정).
- (+) ACE equivalent-absorption-area 패턴 재사용으로 신규 음향 코드 최소화, 양 predictor 분기 무수정.
- (+) RoomPlan sidecar는 category를 이미 제공 → 자동 인식 일부 저비용 확보.
- (−) `ObjectKind` closed Literal 개방 — ADR 0034 §D "신규 kind ≥3건 시 enum 확장" 정책과의 정합 필요(흡음 가구는 단일 클래스이므로 1회 확장으로 충족 논변 가능 — §Consensus 참조).
- (−) 가구 재질/흡음량 추정 불확실성 — A_500 상수는 representative-not-verbatim(ADR 0011/0013 honesty marker 동일 적용 필요).
- (−) mesh 자동 인식은 여전히 미해결(OQ-33 잔여) — 수동 fallback 의존.

---

## Reverse-criterion

1. **가구 경로 RT60 기여 < 측정 노이즈 floor AND 사용자 피드백 부재** — B7-A deprecate 검토(= §Consensus 선검증이 WONTFIX 로 귀결).
2. **신규 가구 kind ≥1종이 MISC_SOFT band 프로파일 대비 >30% 오차** — 전용 MaterialLabel 추가(ADR 0019 선례).
3. **ADR 0009 invariant 위반**(ism_rt60 < eyring_rt60) — 가구 fold 분기 비활성 fallback.
4. **OQ-33 D26 trigger 충족** ((a) non-RoomPlan 자동추출 요청, (b) mesh-only object-GT fixture) — B7-B mesh 클러스터링 재평가.

---

## References

- `roomestim/model.py:134` — `ObjectKind` Literal (현 3종).
- `roomestim/model.py:224~252` — `Object` dataclass + `DEFAULT_OBJECT_MATERIAL`.
- `roomestim/model.py:46~107` — `MaterialLabel` enum + `MaterialAbsorption`/`Bands` (MISC_SOFT α=0.40).
- `roomestim/reconstruct/predictor.py:209~310` — `_objects_to_surfaces` (column 5-face) + `_objects_to_wall_alpha_overrides` (door/window).
- `roomestim/reconstruct/predictor.py:453~596` — ISM fold (shoebox) vs Eyring fallback (비-shoebox, caller dict).
- `roomestim/reconstruct/materials.py:49~236` — Sabine/Eyring integrand (area × α 합산).
- `roomestim/adapters/roomplan.py:130~182` — `_extract_objects` (가구 category `continue` 폐기 지점 `:151`).
- `roomestim/adapters/ace_challenge.py:209~388` — equivalent-absorption-area 패턴(per-piece A_i → 합성 MISC_SOFT surface; ADR 0013 선례).
- `roomestim/adapters/mesh.py:192` — `objects=[]` placeholder.
- `roomestim_web/object_add.py:40~131` — 수동 add UI(kind radio + 검증).
- `roomestim_web/report.py:37~59` — `_surface_areas_by_material` (column fold, door/window 제외 `:42~44`).
- `.omc/plans/open-questions.md` — OQ-33 deferred + D26 trigger.
- `docs/adr/0034-object-schema.md:122~131` — §D Scope OUT("일반 가구 chair/table/sofa → OQ-33").
- `docs/adr/0013-taslp-misc-soft-surface-budget.md` — equivalent-absorption-area 패턴 선례.

---

## Consensus Addendum (검토 참고)

- **Antithesis (steelman)**: "B7-A를 굳이 신규 ObjectKind로 할 필요가 없다 — 이미 web Material Override Tab으로 surface α를 직접 바꿀 수 있고(`evolve_room_material`), ACE식 합성 MISC_SOFT surface를 수동으로 추가할 수도 있다. 새 enum 멤버 + UI + adapter 확장은 surface-area 증가이며, 사용자 가구 인식 요청이 0건(OQ-33 trigger 미충족)인 상황에서 D26 YAGNI에 정면으로 걸린다. B7은 **수요 증거 없는 기능 추가**일 수 있다."
- **Tradeoff tension**: 즉시 가치(흡음 가구 수동 모델링)와 D26 YAGNI(사용자 보고 0건) 사이의 긴장. B7-A는 자동 인식(B7-B, 명백히 deferred)과 달리 "수동 경로 즉시 가치"를 내세우지만, 그 수동 경로의 수요 자체가 입증되지 않았다. enum 확장의 비가역성(closed Literal을 한번 열면 OQ-34 cylinder 등 추가 압력)도 비용.
- **Synthesis (권장)**: B7-A를 enum 확장 없이 **선검증**한다 — 가구 있는 ACE 룸에서 "가구 흡음 미반영 vs 반영" RT60 차이를 먼저 측정(검증 PR4를 PR1보다 먼저)해 ±20% 예산 잠식이 실재하면 enum을 열고, 차이가 노이즈 floor 이하면 WONTFIX. 이렇게 하면 D26 trigger를 "측정된 정확도 손실 ≥ 임계"로 구체화해 honesty를 유지한다.
- **Principle 정합 (검토 필요)**: ADR 0034 §D는 "신규 kind 요청 ≥3건 시 enum 확장"을 명시(`0034-object-schema.md:129`). 흡음 가구를 단일 클래스로 1회 확장하는 것이 이 정책 위반인지, 아니면 "가구 클래스 = 1 요청"으로 해석할지 명시적 판단이 필요(severity: medium — 정책 정합 미해결 시 critic 반려 가능).

> **미확인 사항(honesty)**: SoundCam 룸 fixture의 존재 여부는 확인하지 못했다(검증 PR4의 SoundCam 부분은 fixture 가용성에 의존). ADR 0013 본문은 직접 읽지 않고 `ace_challenge.py` 구현으로 패턴을 역추적했다. door/window α-override가 비-shoebox에서 제외되는 동작(`report.py:42`)이 의도된 설계인지 미해결 결함인지는 본 분석 범위 밖이며 별도 추적이 필요하다. 본 ADR 의 모든 구현 서술은 제안/예정이며 코드는 존재하지 않는다.
