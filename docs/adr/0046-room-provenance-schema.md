# ADR 0046 — Room-level capture provenance 스키마 (`measured | reconstructed | assumed`)

- **Date**: 2026-06-04
- **Status**: Accepted (구현됨 — `RoomModel.provenance` room-level 필드 + 0.2-draft YAML round-trip 가 본 사이클에서 추가·게이트 GREEN·독립 code-review APPROVE 되었다. 시제는 수행된 사실에 대해 과거형이다.)
- **Deciders**: 사용자(빌드 방향 승인), executor(구현), code-reviewer(§F honesty 리뷰 APPROVE)
- **Refs**: ADR 0045(image→geometry capture backend; §F provenance 스키마 deferred·Reverse-criterion #4·blocking gate #3), ADR 0004(room.yaml 스키마 lock — 0.1 2단계; 본 변경은 0.2-draft permissive root 라 그 범위 밖), OQ-54(본 ADR 이 부분 해소), D85; 빌드 플랜 `.omc/plans/image-backend-single-pano-build.md`(P1).

> **핵심요약**: image-derived geometry 가 sensor-measured 치수로 둔갑하는 것을 막기 위해, `RoomModel` 에 **room-level** capture provenance 필드(`measured | reconstructed | assumed`)를 추가했다. 기본값은 정직한 least-claim `"assumed"` 이고, 실측 어댑터(roomplan/mesh/ace)만 명시적으로 `"measured"` 를 단언한다. YAML 에는 `0.2-draft` 에서만 방출되어(`objects[]` 선례) legacy `0.1` 출력은 byte-equal 로 유지된다. **per-Surface provenance 는 의도적으로 범위 밖**(스키마의 3개 `additionalProperties:false` sub-object 편집이 필요 — follow-up). 본 ADR 은 ADR 0045 §F / blocking gate #3 / Reverse-criterion #4 의 honesty 전제를 충족하여, 향후 image backend 출력 노출의 차단을 해제한다.

---

## Context

ADR 0045(image→geometry capture backend, PROPOSED)는 §F 에서 provenance 태그 스키마를 OQ-54 로 deferred 하고, **Reverse-criterion #4**(provenance honesty 스키마 합의 전 image backend 출력 노출 **금지** — 구분 불가한 reconstructed 치수가 measured 로 둔갑하면 위험)와 **blocking gate #3**(노출 전 `measured | reconstructed | assumed` 스키마 합의)을 두었다. 두 feasibility 사이클(OQ-53 scale, OQ-59 front-end, D83/D84)은 image→geometry 를 **rough-estimate tier** 로 확정했고, 단일-파노 in-repo 어댑터 빌드가 시작됐다(플랜 P1). 그 어댑터가 출력을 노출하려면 provenance 게이트가 선결되어야 한다.

기존 `RoomModel`(`model.py`)은 capture 출처를 표기하지 않았다 — RoomPlan LiDAR 스캔과 손으로 만든 모델이 동일하게 보였다. 모든 현존 어댑터(roomplan/mesh/ace/polycam)는 실측 센서/스캔에서 파생되지만, 그 사실이 데이터에 기록되지 않았다.

## Decision

1. **Room-level 필드.** `RoomModel` 에 `provenance: Provenance = "assumed"` 를 추가했다(`Provenance = Literal["measured","reconstructed","assumed"]`). 의미: `measured`=실측 depth 센서/스캔(LiDAR/mesh), `reconstructed`=depth 없이 이미지에서 추론(image backend), `assumed`=미상/손작성.
2. **정직한 least-claim 기본값.** 기본값은 `"assumed"` — 태그되지 않은 모델은 measured 를 **주장하지 않는다**. `"measured"` 는 실측 어댑터(roomplan/mesh/ace)가 명시적으로 단언할 때만 부여된다. polycam 은 roomplan/mesh 에 위임하여 상속한다. 따라서 image-derived 또는 untagged 모델이 measured 로 읽히는 경로는 **존재하지 않는다**(code-review §B masquerade 질문 CLOSED).
3. **0.2-draft 한정 방출.** YAML 직렬화는 `schema_version == "0.2-draft"` 에서만 `provenance` 를 방출한다(`objects[]` 선례). legacy `0.1-draft`/`0.1` 출력은 byte-equal 로 유지된다. reader 는 키 부재 시 `"assumed"` 로 기본화하여, provenance 이전에 쓰인 0.2-draft 파일도 정상 read 된다.
4. **스키마는 additive.** `proto/room_schema.v0_2.draft.json` 에 optional `provenance` property(enum 3값)를 추가했다 — `required` 에 넣지 않았고 root `additionalProperties: true` 를 보존했다. 0.1 스키마는 무변경. ADR 0004 의 2단계 lock 은 0.1 을 규율하며, 현 active 0.2-draft 는 permissive root 라 additive 진화가 그 범위 밖이다.
5. **per-Surface 는 deferred.** OQ-54 원문은 `RoomModel`/`Surface` 양쪽을 지목하나, per-Surface provenance 는 스키마의 3개 `additionalProperties:false` sub-object(surfaces/listener_area/objects item) 편집을 요구하므로 본 사이클에서 제외하고 follow-up 으로 둔다.

## Consequences

**Positive**
- ADR 0045 Reverse-criterion #4 / blocking gate #3 honesty 전제 충족 → image backend 출력 노출 차단 해제(후속 phase 가 `provenance=reconstructed` 를 방출).
- 정직성-우선 ethos(measured/assumed 마커 선례) 정합 — 둔갑 경로 0.
- additive·backward-compat — 기존 소비자(placement/RT60/export)는 provenance 를 읽지 않는 불활성 메타데이터로 무영향.

**Negative / risk**
- 0.2-draft YAML 출력에 키 1개 추가 — draft 스키마(permissive root)이고 released 소비자가 정확 byte 에 의존하지 않으므로 수용. 별도 version bump 은 image backend 기능 완성(플랜 P5) 시점으로 deferred(불활성 필드 — 단독 user-facing 가치 없음).
- per-Surface provenance 미구현 → 혼합-출처 방(일부 surface measured + 일부 reconstructed)의 표기 불가. 현 단일-출처 어댑터에서는 무문제. follow-up.

**Neutral**
- 향후 image adapter(플랜 P3)가 `provenance="reconstructed"` + Manhattan-flag + scale-source disclosure 를 방출할 자리를 마련한다.

## Alternatives considered

- **per-Surface provenance 즉시 구현**: §F/OQ-54 원문 충족이나 3개 strict sub-object 편집 + reader/writer round-trip + 테스트로 사이클 확대 → 단일-출처 어댑터에 불필요(YAGNI), room-level 선행·per-Surface follow-up 으로 분할.
- **기본값 `"measured"`**: 현 어댑터 동작 보존처럼 보이나, 손작성/legacy 모델을 measured 로 **둔갑**시켜 정직성 전제 위배 → 기각, least-claim `"assumed"`.
- **0.1 포함 전 스키마에 방출**: legacy byte-equality 파괴 → 기각, 0.2-draft 한정(objects[] 선례).
- **enum 대신 자유 문자열/신뢰도 스칼라**: 검증 불가·둔갑 표면 증가 → 기각, 닫힌 3-값 enum + schema enum + reader 방어 검증.

## Status / 후속

room-level provenance = 구현·게이트 GREEN(default 320p/5s, web 86p/4s, ruff/mypy/tense EXIT0)·독립 code-review APPROVE(masquerade CLOSED). OQ-54 는 room-level 부분에서 RESOLVED, per-Surface 는 OPEN(follow-up). 본 ADR 은 image backend 빌드(플랜 P2~P5: `[vision]` extra → `adapters/image.py` 단일-파노 → CLI/web rough-tier 라벨 → full gate+리뷰)의 선결 게이트를 닫는다.

## Status-update-2026-06-05 (v0.25.1) — provenance at the layout artifact boundary

- **Date**: 2026-06-05
- **Status**: Accepted (구현됨 — image-backend honesty follow-up T1+T2 가 본 사이클에서 추가·게이트 GREEN·독립 code-review APPROVE 되었다. 시제는 과거형이다.)
- **Refs**: ADR 0045(image→geometry capture backend), OQ-54(layout-boundary 부분 추가 해소), D87(layout-boundary propagation), D88(real-model golden test); follow-up 플랜 `.omc/plans/image-backend-honesty-followups.md`(T1/T2).

room-level provenance(위 Decision)는 `RoomModel.provenance` + room.yaml(0.2-draft) round-trip 까지만 영속했다 — placement 산출물 경계(layout.yaml)에는 기록되지 않았고, image backend 의 rough-tier 마커는 CLI 의 휘발성 stderr(`_maybe_print_estimated_notice`)로만 노출됐다. 이 사이클(D87)이 그 gap 을 닫는다.

1. **PlacementResult 전파.** `PlacementResult` 에 `geometry_provenance: Provenance = "assumed"` 를 추가했다. CLI 는 `room.provenance` 를 단일 지점(`_run_placement`)에서 result 에 실어, image-derived geometry 로부터 만든 layout 이 그 출처를 잃지 않게 한다.
2. **layout.yaml 방출(조건부).** `export/layout_yaml.py` 는 top-level extension key `x_geometry_provenance` 를 값이 `!= "assumed"` 일 때만 방출한다. 따라서 모든 기존 layout(전부 default `assumed`)은 **byte-equal** 로 유지되고, `reconstructed`(rough 마커)와 `measured`(positive claim) 만 경계에 실린다. geometry_schema root 가 `additionalProperties:true` 라 검증을 통과한다.
3. **reader 방어 read.** `io/placement_yaml_reader.py` 는 키 부재 시 least-claim `"assumed"` 로 기본화하고, 값은 공유 `_parse_provenance`(room reader 와 동일)로 검증하여 out-of-enum 을 일관되게 `ValueError` 로 기각한다. write→read→write 는 idempotent(고정점).
4. **stderr 휘발성 보완.** `place` 서브커맨드도 이제 `run`/`ingest` 와 동일하게 ESTIMATED stderr 고지를 출력한다(이전엔 누락). stderr 고지는 보조 채널이고, 영속·기계가독 마커는 (2)의 `x_geometry_provenance` 다.

이로써 직전 ADR 노트의 gap("provenance was room-level only / placement 경계에서는 휘발성 stderr 뿐")이 닫힌다. OQ-54 의 layout-boundary 측면은 RESOLVED, per-Surface 는 여전히 OPEN(follow-up).

**T2 — real-model golden regression(D88).** in-gate image 테스트는 전부 torch-free(synthetic `cor_id`)라, 실제 torch 경로(`adapters/image._infer_corners` → vendored HorizonNet)는 무방비였다. 새 `vision`-마크 테스트(`tests/test_image_backend_golden.py`)가 vendored 합성 파노(`tests/fixtures/image/roomA_synth_pano.png`, MIT-clean 자체 렌더, GT W=4.0 D=3.0 H=2.7)에서 그 실 경로를 돌려 출력을 잠근다. honesty invariant(provenance=reconstructed / 전 surface UNKNOWN / objects=[] / n_surfaces=6·벽 4)는 exact assert, 치수는 cross-machine jitter 흡수용 abs=0.2 m 회귀 락(정확도 주장 아님 — est err ≈ 45–96 cm, ROUGH). 캐노니컬 default 게이트는 torchvision 깨짐으로 SKIP, `[vision]` venv 에서만 실행된다(off-stack 자동 skip).

honesty/robustness 하드닝 — 정확도 개선 아님, 여전히 install-grade 아님.
