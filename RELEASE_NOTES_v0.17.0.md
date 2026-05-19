# roomestim v0.17.0 — Release Notes

**Date**: 2026-05-19
**Version**: `roomestim` 0.17.0 / `roomestim_web` 0.14-web.0
**Schema version**: `"0.2-draft"` (upgraded from `"0.1-draft"`)

---

## §What v0.16.1 missed

v0.16.1까지 세 가지 공백이 남아 있었다.

1. **Column/Door/Window object 추상화 부재** — `RoomModel`은 6 surface (4 wall +
   floor + ceiling) shoebox만 표현. 기둥/도어/창문은 벽으로 흡수되어 ISM α 계산에서
   누락 또는 희석. ACEChallenge `conference` fixture ISM/Sabine ratio 5.05의 기여
   원인 중 하나로 지목.

2. **USDZ/gLTF export 부재** — export는 `layout.yaml` + `room.yaml`만. Vision Pro /
   Blender / Unity 사용자가 매번 변환 스크립트를 직접 작성해야 했다.

3. **Engine 통합 mesh 형식 부재** — phone-scan → 음향 예측 → 3D 시각화 워크플로우에서
   roomestim이 3D export 링크 역할을 하지 못했다.

---

## §What v0.17.0 lands

### 1. Object schema (D44 + ADR 0034)

`Object` frozen dataclass + `ObjectKind` Literal + `DEFAULT_OBJECT_MATERIAL` dict가
`roomestim.model`에 추가되었다.

```python
from roomestim.model import Object, ObjectKind, DEFAULT_OBJECT_MATERIAL

col = Object(
    kind="column",
    anchor=Point3(x=2.5, y=0.0, z=2.0),
    width_m=0.3, height_m=2.85, depth_m=0.3,
    wall_index=None,
    material="WALL_CONCRETE",
)
room = evolve_room_add_object(room, col)
```

신규 공개 API 6개:

| 심볼 | 위치 |
|------|------|
| `Object` | `roomestim.model` |
| `ObjectKind` | `roomestim.model` |
| `DEFAULT_OBJECT_MATERIAL` | `roomestim.model` |
| `evolve_room_add_object` | `roomestim.edit` |
| `evolve_room_remove_object` | `roomestim.edit` |
| `evolve_room(objects=...)` | `roomestim.edit` |

`schema_version` `"0.1-draft"` → `"0.2-draft"` (D44). backward parse 자동:
기존 `"0.1-draft"` YAML 읽기 시 `objects=[]` 자동 설정 — 기존 소비자 영향 없음.

### 2. 음향 통합 (D46 + D47)

column/door/window 객체가 RT60 예측에 반영된다.

- **column**: `predictor._objects_to_surfaces(objects)` → 4 측면 + 1 top = 5개
  추가 surface로 변환 후 `_shoebox_surface_areas_and_alphas`에 머지. lab_room 중앙
  0.3×0.3×2.85 column 기준 RT60 영향 < 0.05 s 예측.

- **door/window**: `predictor._objects_to_wall_alpha_overrides(objects)` → 해당 벽의
  effective α를 면적 비례로 재계산.
  `α_eff = α_wall × (1 − Σfrac) + Σ(α_obj × frac)`

ADR 0009 invariant (`ism_rt60 ≥ eyring_rt60 − 1e-6`) 유지 검증:
`tests/test_objects_acoustic_invariant.py` 6 케이스, 50 random seeds × 3 kind =
150 instance × `predict_rt60_default` 호출.

ADR 0030 cascade `default_predictor_name ∈ {"image_source", "eyring"}` 보존 (D38).

### 3. Mesh export (ADR 0035)

```bash
# USDZ (Vision Pro / Reality Composer)
pip install "roomestim[usd]"
roomestim export --format usdz room.yaml

# gLTF / GLB (Blender / three.js / Unity)
roomestim export --format glb room.yaml

# acoustic sidecar 포함
roomestim export --format usdz --with-acoustics-sidecar room.yaml
```

신규 공개 API 2개: `write_usdz(room, path)`, `write_gltf(room, path, binary=True)`.

씬 계층: `/Room/Surfaces` + `/Room/Objects` + `/Room/Listener` + `/Room/Speakers/Channel_N`.
재질 색상: `MATERIAL_PALETTE` (viewer와 동일 → mental model 일관).

`--with-acoustics-sidecar`: `<basename>.acoustics.json` 생성 (per-surface material +
α_500hz + 6-band; schema `"v0.1-internal"` — OQ-35 v0.19+ 표준화 예정).

---

## §What stays the same

- `RoomModel` surfaces frozen, `dataclasses.replace` 체인 변이 패턴 불변.
- ADR 0009 `ism_rt60 ≥ eyring_rt60 − 1e-6` invariant 보존.
- ADR 0030 cascade (`image_source` → `eyring` fallback) 정책 불변.
- `surface` kind enum (`"wall"`, `"floor"`, `"ceiling"`) closed — 변경 없음.
- `sabine_*` / `eyring_*` API byte-equal (backward-compat).
- ADR 0031 / 0032 / 0033 본문 byte-equal.

---

## §Migration note

| 항목 | 변경 내용 | 조치 필요 |
|------|----------|----------|
| `schema_version` | `"0.1-draft"` → `"0.2-draft"` | 없음 — reader 자동 backward parse |
| export `room.yaml` | 항상 `"0.2-draft"` + `objects:` 키 emit | 없음 — 기존 소비자 unknown field는 무시 |
| CLI `--format` | 신규 flag; default `yaml` | 없음 — 기존 호출 영향 0 |
| `--with-acoustics-sidecar` | 신규 flag | 없음 — opt-in only |
| USDZ 설치 | `pip install "roomestim[usd]"` | USDZ export 사용 시만 필요 |

외부 `spatial_engine`은 `layout.yaml`만 소비 (`room.yaml` 미사용) → schema bump
영향 완전 격리. 0.2-draft `room.yaml`을 소비하는 외부 도구가 unknown field로 fail
보고 시 OQ-36 (v0.17.1 patch 검토).

---

## §Default-lane test count

| 버전 | default lane | web lane | mypy sources | 비고 |
|------|-------------|----------|-------------|------|
| v0.16.1 | 192 passed + 4 skipped | 62 passed + 1 skipped | 37 files | — |
| v0.17.0 | ≥ 215 passed + ≥ 4 skipped | ≥ 65 passed + 1 skipped | ≥ 39 files | +28 신규; usdz skip 환경 따라 −4 가능 |

신규 테스트 분포 (예상):
- `tests/test_objects.py` — Object schema 단위 (~8 케이스)
- `tests/test_objects_acoustic_invariant.py` — D47 회귀 lock (~6 케이스)
- `tests/test_export_usdz.py` — round-trip equality (~4 케이스; usd-core 미설치 시 skip)
- `tests/test_export_gltf.py` — GLB/gLTF format (~6 케이스)
- `tests/test_schema_stage2_validates.py` — 0.2-draft schema 검증 (~4 케이스)

---

## §Tag local-only

v0.17.0 태그는 로컬 repo에만 존재. HF Spaces 배포 및 PyPI publish는 별도 절차.
`roomestim_web.__version__` `0.13-web.1` → `0.14-web.0` (web MINOR — download 버튼
USDZ/GLB 추가; D30 lane 분리 유지).

---

## §Known gaps v0.17.x+

- **OQ-33** (v0.18+): `MeshAdapter` / `ACEChallengeAdapter` object 자동 인식 —
  현재 `objects=[]` placeholder. BoundingBox 클러스터링 알고리즘 안정화 또는 사용자
  보고 1건 발생 시 v0.18 cycle에서 결정.
- **OQ-34** (v0.19+): 곡선/원형 객체 (cylinder column) — polygonal 근사 정책
  미정. 사용자 요청 1건 발생 시 trigger.
- **OQ-35** (v0.19+): USDZ/gLTF acoustic metadata 표준 — sidecar `"v0.1-internal"`
  비표준 유지. Vision Pro / Apple RoomPlan API 표준화 또는 사용자 외부 도구 통합
  요청 발생 시 trigger.
- **v0.17.1 후속**: USDZ extras 환경 검증 patch (Python 3.10+ wheel 재확인 +
  numpy 버전 호환성 명시 + byte-equal 회귀 lock 가능성 탐색). v0.17.0
  code-review 결과 누적된 MEDIUM 4건 일괄 closure:
  - **MEDIUM-1**: `_objects_to_surfaces` column 5-surface CCW 방향 시각적 정정
    (현재 ISM area-only 소비이므로 rt60 영향 없음; USDZ/gLTF back-face culling 시
    column 표면 invisible 가능성). Fix = vertex order 반전 또는 docstring 정정.
  - **MEDIUM-2**: `read_room_yaml` `_parse_object` 단계에서 door/window
    `wall_index < len(walls)` 추가 검증 (현재 predictor.py에서 늦게 raise; defense-
    in-depth).
  - **MEDIUM-3**: `roomestim/export/{usd,gltf}.py` 의 `except Exception:
    column_surfaces = []` broad-catch → `(ValueError, IndexError)` 으로 좁히고
    `logging.warning` 추가.
  - **MEDIUM-4**: door/window quad가 USDZ/gLTF에서 axis-aligned visual stand-in으로
    렌더 (non-x-aligned wall 정확도 손실) → wall-local axes 유도 (polygon[0]→[1]
    edge basis). ADR 0035 §Known-limitations에 명시 권장.
- **OQ-31** (v0.18+): multi-engine schema target — v0.17 cycle 종료 시 재검토 (D26
  hard wall v0.18까지 결정 강제).
