---
title: "ADR 0035 — Mesh export 정책 (USDZ via usd-core; gLTF via trimesh)"
status: Accepted
date: 2026-05-19
deciders: planner (v0.17-design.md), executor
supersedes: null
refs:
  - ADR 0002
  - ADR 0024
  - ADR 0027
  - ADR 0034
  - D45
  - D29
---

# ADR 0035 — Mesh export 정책 (USDZ via usd-core; gLTF via trimesh)

**Date**: 2026-05-19
**Status**: Accepted
**Deciders**: planner (v0.17-design.md), executor

---

## Context

v0.16.1까지 `roomestim`의 export는 `layout.yaml` (engine schema) + `room.yaml`
(직렬화) 두 형식만 지원한다. 3D mesh format 부재로 인해:

- Vision Pro / Reality Composer 사용자가 USDZ 변환 스크립트를 직접 작성해야 한다.
- Blender / three.js / Unity 사용자가 gLTF 변환을 별도 수행해야 한다.
- phone-scan → 음향 예측 → 3D 시각화 워크플로우에서 roomestim이 중간 링크로 기능하지
  못하고 변환 부담이 사용자에게 전가된다.

사용자 4-제안 ③(나머지)이 이 결정을 촉발했다.

---

## Decision

### §A — USDZ backend: `usd-core` (D45)

USDZ 포맷은 `usd-core` PyPI wheel을 통해 구현한다.

```toml
# pyproject.toml
[project.optional-dependencies]
usd = ["usd-core>=24.0; python_version >= '3.10'"]
```

Python 3.10 미만 환경에는 wheel이 제공되지 않으므로 `python_version >= '3.10'`
marker를 명시한다. Import-time graceful degradation:

```python
# roomestim/export/usd.py (module top-level)
try:
    from pxr import Usd, UsdGeom, Sdf
except ImportError as e:
    raise ImportError(
        "USDZ export requires `pip install roomestim[usd]`"
    ) from e
```

CLI가 다른 포맷을 사용할 때 `usd.py`가 import되지 않으므로 lazy import 패턴이 유효하다.

**채택 근거**: `pyusd`는 마지막 PyPI release 2019년이며 GitHub archived (deprecated).
`usd-core`는 현행 Pixar OpenUSD의 공식 PyPI 배포 (`from pxr import Usd, UsdGeom, Sdf`
동일 API). Linux/macOS wheel 제공, Python 3.10+ 호환 검증. Vision Pro /
Reality Composer / Apple Preview.app 모두 USDZ 표준 호환.

### §B — gLTF backend: `trimesh` (core dep)

gLTF/GLB 포맷은 이미 core dependency인 `trimesh>=4.0`을 통해 구현한다.
추가 extras 불필요. 지원 포맷:

- `glb` (binary, default) — 단일 파일, 배포 편의.
- `gltf` (ASCII JSON + `.bin` sidecar) — 사람이 읽을 수 있는 형식.

### §C — 씬 계층 구조 표준

USDZ 및 gLTF 모두 동일한 논리적 계층을 따른다:

| USD namespace | gLTF node | 내용 |
|---------------|-----------|------|
| `/Room/Surfaces` | `Scene/Surfaces` | wall/floor/ceiling mesh face |
| `/Room/Objects` | `Scene/Objects` | column/door/window mesh |
| `/Room/Listener` | `Scene/Listener` | listener_area semi-transparent |
| `/Room/Speakers/Channel_N` | `Scene/Speakers/Channel_N` | 스피커 sphere (r=0.05 m) |

사용자가 sub-prim 단위로 visibility hide 가능 (USD `visibility` attr /
gLTF `node.extras.visible`).

### §D — 재질 바인딩

`MaterialLabel` → PBR baseColor 매핑은 `roomestim_web/viewer.py:31`에서
이미 정의된 `MATERIAL_PALETTE`를 재사용한다 (viewer와 색상 일치 → 사용자
mental model 일관).

- **USD**: `UsdShade.Material` + `UsdShade.Shader` (surface) PBR `baseColor` 설정.
- **gLTF**: `material.pbrMetallicRoughness.baseColorFactor` 설정.

acoustic α 정보 (500 Hz + 6-band)는 mesh 자체에 미포함. 옵션 sidecar로 분리 (§E).

### §E — Optional acoustic sidecar

`--with-acoustics-sidecar` 플래그 사용 시 `<basename>.acoustics.json` 생성:

```json
{
  "schema": "roomestim-acoustics-sidecar-v0.1-internal",
  "surfaces": [
    {
      "id": "wall_0",
      "material": "GLASS",
      "alpha_500hz": 0.04,
      "alpha_bands": {"125": 0.03, "250": 0.03, "500": 0.04, "1000": 0.04, "2000": 0.05, "4000": 0.05}
    }
  ]
}
```

v0.17.0 sidecar format은 internal (스키마 `"v0.1-internal"`). OQ-35에서
v0.19+ 표준화 검토 (Vision Pro / Apple RoomPlan API 표준화 연동).

### §F — CLI 인터페이스

```
roomestim export [--format yaml|usdz|gltf|glb] [--with-acoustics-sidecar] <room.yaml>
```

- `--format yaml` (default) — 기존 동작 backward-compat.
- `--format usdz` — `write_usdz(room, path)` 호출.
- `--format gltf` — `write_gltf(room, path, binary=False)` 호출.
- `--format glb` — `write_gltf(room, path, binary=True)` 호출.

신규 공개 API 2개: `write_usdz`, `write_gltf`.
신규 CLI flag 2개: `--format`, `--with-acoustics-sidecar`.

### §G — 좌표 규약

`RoomModel.Point3` (x=right, y=up, z=forward)는 USDZ/gLTF 표준 좌표계
(y-up right-handed)와 동일 — 좌표 변환 불필요.

- USDZ stage: `upAxis="Y"`, `metersPerUnit=1.0` 명시.
- gLTF: Khronos 표준 y-up right-handed — 추가 설정 불필요.

### §H — 결정론 정책

mesh vertex/face round-trip equality를 1차 회귀 lock으로 사용한다:
write → read → vertex/face equal. byte-equal lock은 v0.17.1 patch 후속
(usd-core zip timestamp 의존 + gLTF JSON 직렬화 순서 확인 후).

---

## Consequences

- (+) Vision Pro / Reality Composer 사용자에게 직접 USDZ 제공.
- (+) Blender / three.js / Unity / Unreal 사용자에게 gLTF/GLB 제공.
- (+) HF Spaces re-deploy 트리거 없음 — `usd-core`는 optional extra이고
  시스템 의존성 변경 없음.
- (+) `trimesh` 기존 core dep 재사용 — gLTF 추가 의존성 0.
- (−) `usd-core`는 Python 3.10+ only — 3.9 이하 환경에서 USDZ export 불가.
  CLI `--format usdz` 호출 시 `ImportError` with 안내 메시지.
- (−) USDZ acoustic metadata extension은 v0.19+ (OQ-35) — 현재 sidecar로 분리.

---

## Reverse-criterion

1. **`usd-core` wheel 미제공 or numpy 버전 충돌 발견** — USDZ scope drop +
   v0.17.1 patch. USDZ self-writer (~300 LoC; USDZ = uncompressed zip + USD binary
   spec 공개) 또는 USDZ 포맷 제거.
2. **mesh inside-out 방향 회귀** (winding order CCW vs CW 불일치) — ADR 0002
   CCW polygon convention 기준으로 winding 수정.
3. **사용자가 다른 mesh format 요청** (`.fbx`, `.obj`, `.dae`) — 별도 export 모듈
   추가 (`roomestim/export/fbx.py` 등). 이 ADR 본문 수정 없이 ADR 0035
   §Status-update 추가.
4. **USDZ acoustic metadata extension 표준 등장** — §E 확장 (OQ-35 closure).

---

## References

- **D45** — USDZ backend = `usd-core` PyPI wheel (`pyusd` deprecated → rejected).
- **ADR 0002** — RoomModel shape + CCW polygon convention (winding order source).
- **ADR 0024** — web 분리 (D29 lane separation: export 모듈은 core lane).
- **ADR 0027** — mesh format generalisation precedent.
- **ADR 0034** — Object schema (Column/Door/Window) — objects to mesh 매핑.
- **D29** — lane separation (export 모듈은 `roomestim/export/` core; web은 download만).
- `roomestim/export/usd.py` — USDZ writer 구현.
- `roomestim/export/gltf.py` — gLTF/GLB writer 구현.
- `roomestim_web/viewer.py:31` — `MATERIAL_PALETTE` 재사용 색상 팔레트.
- `tests/test_export_usdz.py` — round-trip equality 회귀 lock.
- `tests/test_export_gltf.py` — GLB/gLTF format 회귀 lock.
- `README.md §USDZ` — 설치 및 사용법.

---

## §Status-update-v0.18.4 (2026-05-25)

ADR 0035 최초 §Status-update 블록. D22 audit-trail-discipline: append only,
no retroactive edits to prior body.

**OQ-35 재연기 (D59) — USDZ/gLTF acoustic metadata 표준: v0.21 cycle 시작 시 재검토.**

두 trigger 모두 미충족: (1) Apple/Khronos acoustic-metadata 표준 **미공개** (Vision
Pro/RoomPlan acoustic extension 도 미확정); (2) Unreal/SPARTA 등 외부 도구 import
요청 0건. sidecar 는 `"v0.1-internal"` 로 동작 중이며 외부 표준이 없는 상태에서
roomestim 자체 spec 을 동결하는 것은 premature — 표준 등장 시 재작업 비용 발생.

**신규 cadence: v0.21 cycle 시작 시 재검토** (외부 표준 의존 — OQ-34 와 동일 사이클
묶음으로 재검토 효율화). §G reverse-criterion (iv) = OQ-35 closure 경로 (표준 공개
시 §E 확장).

Reverse if (조기 escalate): Vision Pro/Apple RoomPlan acoustic metadata 표준 공개
OR 외부 도구 (Unreal/SPARTA 등) acoustic import 요청 ≥ 1건 → ADR 0035 §E 확장
(KHR extension key / Apple sidecar spec 채택). **ADR ref**: D59.

Predictor cascade / ObjectKind / schema: 불변. web: byte-equal (`0.15-web.0`).
`roomestim.__version__` `0.18.3` → `0.18.4` (PATCH). 신규 ADR: none. 신규 OQ: none.
