---
title: "ADR 0034 — Object schema (Column/Door/Window)"
status: Accepted
date: 2026-05-19
deciders: planner (v0.17-design.md), executor
supersedes: null
refs:
  - ADR 0002
  - ADR 0008
  - ADR 0009
  - ADR 0019
  - ADR 0030
  - ADR 0031
  - D44
  - D46
  - D47
---

# ADR 0034 — Object schema (Column/Door/Window)

**Date**: 2026-05-19
**Status**: Accepted
**Deciders**: planner (v0.17-design.md), executor

---

## Context

v0.16.1까지 `RoomModel`은 `surfaces` (floor/ceiling/wall)와 `listener_area`만 보유한다.
column/pillar/door/window 같은 obstacle 객체는 표현 수단이 없고, 그 결과:

- 기둥은 벽으로 흡수되어 ISM α 계산에서 완전히 누락된다.
- 도어/창문의 흡음 계수가 벽 전체 α의 area-weighted average 안에 희석된다.
- Eaton 2016 TASLP `Building_Lobby` 같은 irregular 룸 (coupled-space + 기둥 구조)은
  shoebox 근사 자체가 부적합하지만, obstacle 부재로 인해 편향이 더 크다.

사용자 4-제안 ①(나머지)이 이 결정을 촉발했다. ACEChallenge `conference` fixture의
ISM/Sabine ratio 5.05는 glass-heavy 재질 외에도 도어/창문의 α 미반영이 기여 원인으로
지목된다.

---

## Decision

### §A — Object dataclass 명세

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal
from roomestim.model import MaterialLabel, Point3

ObjectKind = Literal["column", "door", "window"]

@dataclass(frozen=True)
class Object:
    kind: ObjectKind
    anchor: Point3          # column = base center (floor level)
                            # door/window = bottom-left (wall-local coords)
    width_m: float
    height_m: float
    depth_m: float          # column 전용; door/window = 0.0
    wall_index: int | None  # column = None (standalone); door/window 필수
    material: MaterialLabel
```

`anchor` 의미론:
- `column`: 기둥 바닥면 중심점 (floor level). `wall_index=None` — 룸 내부 어디에나
  배치 가능.
- `door` / `window`: 벽 로컬 좌표계에서 bottom-left 코너. `wall_index` 는 해당 벽의
  `surfaces` 리스트 인덱스 (kind="wall" 필터 후).

`DEFAULT_OBJECT_MATERIAL` 상수:

```python
DEFAULT_OBJECT_MATERIAL: dict[ObjectKind, MaterialLabel] = {
    "column":  "WALL_CONCRETE",
    "door":    "WALL_PAINTED",
    "window":  "GLASS",
}
```

### §B — RoomModel 통합 및 schema bump

`RoomModel`에 `objects: list[Object] = field(default_factory=list)` 필드 추가.
schema_version `"0.1-draft"` → `"0.2-draft"` (D44).

backward parse 정책 (`room_yaml_reader.py`):

```python
schema_version = data.get("schema_version", "0.1-draft")
if schema_version == "0.1-draft":
    objects = []  # 0.1-draft에는 objects 필드 부재 — 자동 빈 리스트
elif schema_version == "0.2-draft":
    objects = [_parse_object(o) for o in data.get("objects", [])]
else:
    raise ValueError(f"Unsupported schema_version: {schema_version}")
```

export 정책 (`room_yaml.py`): 항상 `schema_version: "0.2-draft"` write +
`objects:` 키 무조건 emit (빈 list라도) — round-trip determinism 보장.

evolve helper 신규 공개 API (6개):

| 심볼 | 설명 |
|------|------|
| `Object` | frozen dataclass |
| `ObjectKind` | `Literal["column", "door", "window"]` |
| `DEFAULT_OBJECT_MATERIAL` | kind별 기본 재질 dict |
| `evolve_room_add_object(room, obj)` | object 추가 후 새 RoomModel 반환 |
| `evolve_room_remove_object(room, idx)` | index 위치 object 제거 |
| `evolve_room(objects=...)` | keyword 인자로 objects 리스트 교체 |

### §C — DEFAULT_OBJECT_MATERIAL 근거

- `column → WALL_CONCRETE`: 구조용 기둥은 콘크리트/벽돌이 지배적. α_500Hz = 0.02
  (낮은 흡음, 높은 반사 — ISM RT60 증가 방향).
- `door → WALL_PAINTED`: 도어는 페인트칠 목재/금속. α_500Hz ≈ wall_painted (≈0.05)
  — wall α 대비 영향 미미.
- `window → GLASS`: 창문은 plate glass. α_500Hz = 0.04 — wall_painted보다 약간 낮음.

### §D — Scope OUT

다음 항목은 v0.17.0 범위 밖이며 별도 ADR/OQ로 추적한다:

- **곡선/원형 객체** (cylinder column, arch): OQ-34 — v0.19+ polygonal 근사 정책 검토.
- **일반 가구** (chair/table/sofa): OQ-33 — v0.18+ mesh adapter BoundingBox 클러스터링.
- **USDZ acoustic metadata**: OQ-35 — v0.19+ Vision Pro / Apple RoomPlan API 표준화 후.
- `kind` enum 개방: closed Literal 유지. 신규 kind 요청 ≥ 3건 발생 시 ADR 0034
  §Status-update 추가 후 enum 확장.

---

## Consequences

- (+) phone-scan → RoomModel 워크플로우에서 기둥/도어/창문의 음향 영향을 명시적으로
  표현할 수 있다.
- (+) `evolve_room_add_object` / `evolve_room_remove_object`로 UI에서 객체를 추가·제거하고
  즉시 RT60 재계산 가능.
- (+) `schema_version` `"0.2-draft"` backward parse 자동 → 기존 `0.1-draft` YAML 소비자
  영향 0.
- (+) 외부 `spatial_engine`은 `layout.yaml`만 소비 (`room.yaml` 미사용) → schema bump
  영향 격리.
- (−) `RoomModel.frozen` 상태 유지 (모든 변이는 `dataclasses.replace` 체인) — 대규모
  object list 수정 시 객체 생성 비용 선형 증가. OQ 후보로 남음.
- (−) `MeshAdapter` (Polycam 등)와 `ACEChallengeAdapter`는 `objects=[]` placeholder —
  자동 인식은 OQ-33 (v0.18+).

---

## Reverse-criterion

1. **column 면적 < 1% of total wall α 기여 AND 사용자 피드백 부재** — v0.18+ 재검토.
   기준: lab_room 중앙 0.3×0.3×2.85 column 면적 3.42 m² / 전체 표면적 ~80 m² = 4.3%.
   임계치 미만 케이스가 통계적으로 지배적이면 column API deprecate 검토.
2. **ADR 0009 invariant 위반** (`ism_rt60 < eyring_rt60 - 1e-6`) — ISM 분기 비활성 fallback.
   D47 회귀 lock (50 seeds × 3 kind = 150 instance)이 GREEN인 동안 trigger 없음.
3. **외부 consumer가 0.2-draft YAML unknown field로 fail** — `roomestim export --schema 0.1`
   flag 도입 또는 OQ-36 (v0.17.1 patch).

---

## References

- **D44** — schema bump `"0.1-draft"` → `"0.2-draft"` + backward parse 보장.
- **D46** — column = 5 추가 surface; door/window = wall α override (혼합 절충).
- **D47** — ADR 0009 invariant + cascade 회귀 lock (50 seeds × 3 kind).
- **ADR 0002** — RoomModel shape + CCW polygon convention.
- **ADR 0008** — octave-band α 정책.
- **ADR 0009** — ISM ≥ Eyring runtime invariant.
- **ADR 0019** — enum extension cadence precedent (MELAMINE_FOAM).
- **ADR 0030** — predictor-default cascade.
- **ADR 0031** — material override policy (door/window default material 결정과 일관).
- `roomestim/model.py` — `Object`, `ObjectKind`, `DEFAULT_OBJECT_MATERIAL`.
- `roomestim/edit.py` — `evolve_room_add_object`, `evolve_room_remove_object`.
- `roomestim/io/room_yaml_reader.py` — backward parse 구현.
- `roomestim/export/room_yaml.py` — 0.2-draft export.
- `tests/test_objects.py` — Object schema 단위 테스트.
- `tests/test_objects_acoustic_invariant.py` — D47 회귀 lock 150 instance.
