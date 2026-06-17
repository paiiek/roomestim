# ADR 0049 — Multi-room `RoomCollection` as an additive composition layer

- **Date**: 2026-06-17
- **Status**: Accepted (Phase 1 구현됨 — `RoomCollection` 합성 레이어 + `collection` CLI 서브커맨드 + `collection.yaml` manifest writer/reader + 신규 proto 스키마. 시제는 수행된 사실에 대해 과거형이다. 단일방 코드 경로 무접촉으로 모든 단일방 golden byte-equal; load-bearing 테스트(collection per-room layout == standalone `place` 바이트 동일) 통과. v0.40.0 (MINOR/additive) 출시. Phase 2(결합 3D export)·Phase 3(명시적 per-room offset)은 DEFER.)
- **Deciders**: 사용자(빌드 방향 승인), planner(설계), executor(Phase 1 구현), code-reviewer(honesty + additive-only 리뷰 → APPROVE), verifier/orchestrator(full-gate GREEN: default 650p/7s · web 86p/3s · ruff · mypy)
- **Refs**: ADR 0047(multi-room DEFERRED — 본 ADR 가 그 re-open condition 을 충족), ADR 0002(단일방 `RoomModel`), ADR 0007(in-package proto bundling), ADR 0033(engine schema validation), ADR 0046(provenance-at-boundary). 플랜 `.omc/plans/multi-room-roomcollection.md` §"Phased plan (planner 2026-06-17)".

> **핵심요약**: ADR 0047 이 DEFER 한 것은 `RoomModel` **rewrite**(모든 소비자를 건드리는 multi-PR core refactor)였다. 본 ADR 은 그것이 아니다. `RoomCollection` 은 **N 개의 명시적 단일방 입력**(각각 기존 어댑터가 만든 진짜 `RoomModel`/room.yaml)을 **순서 있는 컨테이너로 합치는 순수 additive 합성 레이어**다. roomestim 은 한 번의 캡처에서 여러 방을 **추론하지 않는다** — 합성은 사용자가 명시한 N 개의 단일방 캡처에서 온다(정직 framing). 새 컨테이너 + 새 CLI 서브커맨드 `collection` + 새 combined export(manifest) 만 **추가**하고, 단일방 ingest/place/export/run/edit 경로와 5개 `RoomModel` 생성 지점·기존 export 는 **한 바이트도 건드리지 않는다** → 단일방 golden/round-trip 은 **구조상(by construction) byte-equal**.

---

## Context

ADR 0047 은 진정한 multi-room `RoomCollection` 을 **3가지 이유**로 DEFER 했다:
1. **실 multi-room 입력 경로 없음** — RoomPlan sidecar 는 구조상 단일방이고 Apple `CapturedStructure` 는 ingest 되지 않는다.
2. **blast radius** — 진짜 컨테이너는 5개 `RoomModel` 생성 지점 + 모든 export + placement + CLI + schema + 모든 golden 을 건드리는 multi-PR core refactor.
3. **부분 구현이 단일방 golden round-trip 을 깰 위험** (auto-memory `feedback_verify_each_step` 위배).

B2B AV-인스톨러 워크플로(`project_commercialization_b2b`)는 multi-room venue 를 스캔한다 — 하지만 **방마다 따로** 스캔한다. 실제로 필요한 산출물은 "한 캡처에서 추론된 multi-room 모델"이 아니라 **per-room 스피커 레이아웃 + 하나로 묶인 모델**이다. 이건 ADR 0047 의 DEFER 이유 (1)(2)(3) 을 우회한다 — 입력이 이미 N 개의 진짜 단일방 `RoomModel` 이고, 합성은 단일방 코드를 재작성하지 않고 **그 위에 얇게 얹는다**.

## Decision

**ADR 0047 이 DEFER 한 RoomModel rewrite 대신, additive composition layer 를 채택한다.**

1. **컨테이너 (D-A).** 새 모듈 `roomestim/collection.py` 에 `RoomCollection` 데이터클래스: `name: str`, `rooms: list[RoomModel]`(순서 있음), `placements: list[PlacementResult | None]`(병렬 인덱스, optional). 방은 phase 1 에서 **서로 독립** — per-room transform/offset/pose **없음**. `model.py` 는 **편집하지 않는다**(새 모듈이 `model.py` 에서 import). offset 은 측정된 inter-room 정합 GT 가 없으므로(따로 스캔됨) phase 1 에서 **fabricate 하지 않고**, 사용자가 명시적으로 줄 때만(Phase 3, opt-in) 도입한다.
2. **CLI (D-B).** 새 서브커맨드 `collection` (`--in-rooms PATH [PATH ...]` + 기존 placement 플래그 재사용 + `--name` + `--out-dir`). 핸들러 `_cmd_collection` 은 방마다 `_cmd_place` 가 쓰는 **같은 라이브러리 함수**(`read_room_yaml` → `run_placement` → `write_layout_yaml`)를 호출한다 — `_cmd_place` 자체는 호출/편집하지 않는다. per-room `layout.<name>.yaml`(이름 충돌 시 index-suffix) + `collection.yaml` manifest 를 쓴다.
3. **Combined export (D-C).** phase 1 = `collection.yaml` **manifest 전용**(collection name/version + `rooms[]` = `{name, room_ref, layout_ref}` 상대경로). geometry merge·combined 3D 파일 **없음**. 스키마 = **별도 신규 파일** `roomestim/proto/collection_schema.v0_1.draft.json`(`additionalProperties:false`); 단일방 `room_schema.v0_2.draft.json` 은 **편집 안 함**. 신규 writer `export/collection_yaml.py` + reader `io/collection_yaml_reader.py`. combined glTF/USD 는 Phase 2(opt-in), explicit offset 은 Phase 3.
4. **Phasing (D-D).** 3 phase, 각 phase 는 독립적으로 full-gate GREEN + 단일방 golden byte-equal. Phase 1 = thinnest end-to-end vertical slice.
5. **NO FAKE CAPABILITY / NO FAKE NUMBERS.** "roomestim 이 multi-room 을 추론한다" 고 **주장하지 않는다**. 합성은 N 개의 명시적 단일방 입력에서 온다. 집계 footprint/volume/RT60 같은 **aggregate 음향 수치는 산출하지 않는다**(ADR 0047 의 merge=가짜숫자 트랩 회피); 음향은 per-room 에 머문다.

## Why NOT the ADR 0047-deferred refactor

| ADR 0047 DEFER 이유 | 본 additive 접근의 회피 방식 |
|---|---|
| (1) 실 multi-room 입력 경로 없음 | 입력 = N 개의 **이미 존재하는 진짜 단일방** `RoomModel`/room.yaml. 한 캡처에서 multi-room 을 추론하지 않음. |
| (2) blast radius(5 생성지점·export·placement·CLI·schema·golden) | **0 touch** of 단일방 코드. 새 모듈·새 서브커맨드·새 proto·새 export 만 **추가**. |
| (3) 부분 구현이 단일방 golden 을 깸 | golden byte-equality 가 **by construction** (단일방 코드 미변경) + 명시 회귀 테스트로 잠금. |

## Blast radius (목표: 단일방에 대해 near-zero)

- **단일방 `RoomModel` 생성 5개 지점** (`adapters/{ace_challenge,image,mesh,roomplan}.py`, `io/room_yaml_reader.py`): **TOUCH 0**.
- **export** (`export/{room_yaml,layout_yaml,gltf,usd}.py`): **TOUCH 0** (combined export 는 기존 writer 를 per-room 호출만).
- **placement** (`place/dispatch.py::run_placement`): **TOUCH 0** (재사용).
- **CLI** (`cli.py`): **additive only** — 신규 `_add_collection_parser` + `_cmd_collection` + `main()`/`_build_parser` 디스패치 1 분기. 기존 5개 서브커맨드 파서/핸들러 byte-unchanged.
- **schema** (`proto/room_schema.v0_2.draft.json`): **TOUCH 0**; 신규 `collection_schema.v0_1.draft.json` 만 추가.
- **신규 파일**: `roomestim/collection.py`, `export/collection_yaml.py`, `io/collection_yaml_reader.py`, `proto/collection_schema.v0_1.draft.json`, `tests/test_collection_*.py`, `tests/fixtures/collection/`.
- `roomestim/__init__.py`: `RoomCollection` export (additive append) — optional.

## Consequences

**Positive**
- 제품이 정직하게 만들 수 있는 산출물(per-room 레이아웃 + 묶음 manifest)을 실제로 출력 → ADR 0047 re-open condition("per-room placement/export 설계") 충족.
- 단일방 golden/round-trip byte-equal, acoustics surface 무접촉 → `feedback_verify_each_step` 준수.
- ADR 0007 in-package proto 패턴·기존 writer/reader 패턴 재사용.

**Negative / risk**
- 여전히 **단일방 추론** 제품이다 — multi-room 추론을 주장할 수 없다(주장하지 않음). collection 은 명시 입력의 묶음.
- per-room layout byte-equality 가 깨지면 "additive·no cross-talk" 주장이 무너진다 → load-bearing 회귀 테스트로 직접 검증 필수.
- Phase 1 manifest 는 inter-room pose 가 없어 combined 3D 에서 방들이 로컬 원점에 겹친다(문서화된 정직 한계; Phase 3 의 명시 offset 으로 해소).

**Neutral**
- aggregate 음향(집계 RT60/volume)은 의도적으로 범위 밖(가짜숫자 트랩). 측정 GT 가 생기기 전엔 재오픈 안 함.

## Alternatives considered

- **ADR 0047 의 진짜 `RoomModel` rewrite 지금 구현** — 기각: blast radius·golden 위험 그대로(0047 근거 불변). additive layer 가 같은 제품 가치를 near-zero 위험으로 제공.
- **`model.py` 에 `RoomCollection` 추가** — 기각(약): 기존 심볼은 byte-equal 이나 파일을 건드림. 신규 `collection.py` 가 "단일방 코드 0 touch" 를 더 깨끗이 보장.
- **`room_schema` 를 multi-room 으로 확장** — 기각: 단일방 스키마/golden 회귀 위험. 별도 `collection_schema` 가 분리·additive.
- **Phase 1 에서 footprint union / combined volume·RT60** — 기각: 측정 inter-room 정합·집계 GT 부재 → 가짜숫자(ADR 0047 와 동일 트랩). per-room 에 한정.
- **Phase 1 에서 inferred inter-room offset(자동 정합)** — 기각: 정합 GT 없음 → fabricated registration. offset 은 사용자 명시(Phase 3)만.

## Follow-ups

- Phase 2: opt-in combined glTF/USD(기존 per-room writer 재사용, offset 없으면 로컬 원점).
- Phase 3: 사용자 명시 per-room offset(shared building frame); absent ⇒ Phase 1/2 byte-equal.
- aggregate 음향/footprint merge: 측정 multi-room GT 가 생기면 별도 ADR 로 재검토(현재 가짜숫자 트랩).
