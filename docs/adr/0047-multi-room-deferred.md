# ADR 0047 — Multi-room (`RoomCollection`) DEFERRED; RoomPlan multi-floor-entry silent-loss 만 disclose

- **Date**: 2026-06-08
- **Status**: Accepted (bounded slice 구현됨 — RoomPlan sidecar 의 2번째 이상 floor 엔트리가 SILENTLY 버려지던 데이터 손실을 `UserWarning` disclosure 로 가시화했다. 시제는 수행된 사실에 대해 과거형이다. 진정한 multi-room `RoomCollection` 은 본 ADR 로 명시 DEFER 한다.)
- **Deciders**: 사용자(빌드 방향 승인), executor(구현), code-reviewer(honesty 리뷰 예정)
- **Refs**: 플랜 `.omc/plans/commercialization-followups-4candidates.md` §Candidate (B) (D99); ADR 0002(room representation — 단일방 `RoomModel`), ADR 0046(room-level provenance), ADR 0034(object schema); 단일진실원천 disclosure `roomestim/reconstruct/_disclosure.py::ROOMPLAN_MULTI_FLOOR_NOTE`.

> **핵심요약**: SWOT 의 "`roomplan.py` `floor_entries[0]` 가 다른 방을 버린다" 는 지적은 과장이었다. roomestim 이 받는 RoomPlan **sidecar 스키마는 구조상 단일방**(`"category":"room"`, 하나의 `dimensions`, flat `walls[]/floors[]/ceilings[]`)이고, Apple 의 진짜 multi-room(`CapturedStructure` = 다수 `CapturedRoom`)은 이 스키마에 **존재하지도 않는다**. 따라서 `floor_entries[0]` 가 버리는 것은 *방*이 아니라 한 방 안의 **추가 floor 폴리곤**(split-level / 분리된 바닥 패치)이며, 이는 경고 없이 SILENTLY 사라지고 있었다. 본 사이클은 그 **조용한 손실만** disclose(>1 경로에서 `UserWarning`)하고, model/스키마/export 는 일절 건드리지 않는다(순수 additive — 모든 단일방 golden/round-trip byte-equal). 진정한 multi-room 컨테이너는 blast radius 가 커서 DEFER 한다.

---

## Context

상용화 SWOT 은 `roomplan.py:262 floor_entries[0]` 를 "다른 방을 버린다(dropping other rooms)" 로 적었으나, 코드/스키마 확인 결과:

- RoomPlanAdapter sidecar 스키마(`roomplan.py:1-37` docstring)는 **단일방 전용**이다: `"category": "room"`, 단일 `dimensions`, flat `walls[]/floors[]/ceilings[]`.
- `RoomModel`(`model.py`)도 설계상 단일방이다: 하나의 `floor_polygon: list[Point2]`, scalar `ceiling_height_m`.
- Apple 의 multi-room 표현(`CapturedStructure` → 다수 `CapturedRoom`)은 이 sidecar 스키마에 **들어오지 않는다**.

실제 결함은 한 방 안에 floor 엔트리가 2개 이상일 때(split-level / 분리 바닥 패치) `floor_entries[1:]` 가 **경고 없이 버려진다**는 점이다(`[0]` 만 참조, `len()` 가드 없음 확인). `walls[]`/`ceilings[]` 는 이미 전부 순회하므로 truncation 이 없다 — **floors[] 에만** silent 손실이 있었다.

## Decision

1. **Bounded slice — disclose only.** `roomplan.py::_room_model_from_sidecar` 에서 `len(floor_entries) > 1` 일 때 silent drop 을 멈추고 `UserWarning` 을 방출한다. 메시지 본문은 단일진실원천 `_disclosure.py::ROOMPLAN_MULTI_FLOOR_NOTE` 에서 가져온다(인라인 재타이핑 금지). N(발견된 floor 엔트리 수)은 경고 prefix 로 덧붙인다. `len == 1` 경로는 **무변경**(경고 없음).
2. **geometry number 불변.** disclose-only 를 택했다(플랜 옵션 (a)). 폴리곤 **merge(union) 는 채택하지 않는다** — merge 는 footprint/area 수치를 바꾸고 측정 GT 없이 그 값을 단언하면 가짜 숫자가 된다(가짜 숫자 금지). primary(첫) floor 는 오늘과 동일하게 쓰이고, 추가 엔트리는 modelled 되지 않는다.
3. **model / 스키마 / export 무변경.** `RoomModel`, room schema, 모든 export(room.yaml/gltf/usd)를 건드리지 않는다. 변경은 `>1` 경로의 경고 1개뿐인 **순수 additive** 라, 기존 단일방 golden/round-trip 테스트가 byte-equal 로 유지된다.
4. **진정한 multi-room `RoomCollection` DEFER.** 아래 blast radius 참조.

## 진정한 multi-room blast radius (DEFER 근거)

실제 `RoomCollection`/multi-room 컨테이너는 **모든** `RoomModel` 소비자를 건드린다:

- **5개 `RoomModel(` 생성 지점**: `adapters/{ace_challenge,image,mesh,roomplan}.py`, `io/room_yaml_reader.py`.
- **export**: `export/room_yaml.py`(`room_model_to_dict`), `export/gltf.py`, `export/usd.py`(+ 각 acoustics 사이드카).
- **placement**: `place/dispatch.py`(listener area, VBAP/DBAP/WFS 가 모두 단일방 가정).
- **CLI**: ingest/place flow(`_maybe_print_*` notice 들이 단일방 가정).
- **schema**: `proto/room_schema.v0_2.draft.json`(단일방 shape) + `io/room_yaml_reader.py`.
- **테스트**: 모든 단일방 golden 이 기존 것을 깨지 않고 multi-room sibling 을 요구.

이는 다중-PR core refactor 이며, 실제 multi-room sidecar fixture 도 없다. 부분 구현은 단일방 golden round-trip 을 깰 위험이 있어 auto-memory `feedback_verify_each_step` 에 위배된다. → **컨테이너는 DEFER.**

## Consequences

**Positive**
- 한 방 안 다중 floor 엔트리의 **조용한 geometry 손실 제거** — 이제 명시적으로 disclose 된다.
- model/스키마/export 무변경 → 단일방 golden/round-trip byte-equal, acoustics surface 무접촉.
- 단일진실원천 disclosure 패턴(`_disclosure.py`) 정합.

**Negative / risk**
- 제품은 여전히 **단일방**이다 — "roomestim 이 multi-room 을 지원한다" 고 주장할 수 없다(주장하지 않는다). 다중 floor 엔트리는 disclose 되지만 modelled 되지 않는다.

**Neutral**
- 향후 진정한 multi-room 은 별도 phased ADR + 실제 multi-room fixture + per-room placement/export 설계를 요구한다(아래 follow-up).

## Alternatives considered

- **지금 진짜 `RoomCollection` 구현** — 기각: 다중-PR core refactor(blast radius 상기), 실 fixture 부재, 단일방 golden 위험.
- **floor 폴리곤 merge(union)** — 기각(이번 사이클): coplanar 단순폴리곤일 때만 union 가능하나, 그 결과 area/footprint 수치를 측정 GT 없이 단언하면 가짜 숫자. disclose-only 가 least-claim.
- **`ValueError` 로 raise** — 기각: 부분 geometry 가 위험하다고 단정하긴 과함. RoomPlan 의 정상 단일방 캡처(대부분 단일 floor 엔트리)를 막지 않으면서 비정상만 경고하는 disclose 가 비례적.

## Follow-ups (re-open conditions)

- **진정한 multi-room `RoomCollection`**: 실제 multi-room sidecar/`CapturedStructure` fixture 확보 + per-room placement/export 설계가 준비되면 dedicated phased ADR 로 착수. (OQ: multi-room 컨테이너 — 본 ADR blast radius 가 그 범위 정의.)
- merge 경로는 측정 footprint GT 가 생기면 재검토 가능(현재 가짜 숫자 트랩).
