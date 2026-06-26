# ADR 0056 — A-consumer placement levers (ceiling override + snap-to-surface) + multiview point-cloud ingest

- **Date**: 2026-06-26
- **Status**: Accepted (v0.50.0 — MINOR additive: two new `edit.py` helpers + one new geom primitive + one new capture adapter + opt-in CLI flags/backend. Existing backends, default placement path, and `import roomestim` boundary unchanged.)
- **Deciders**: main(설계+구현, autopilot spec `.omc/autopilot/spec-aconsumer-multiview.md`), code-reviewer(예정). Source of scope: `spike-vggt-multiview/PLACEMENT_SENSITIVITY_VERDICT.md`.
- **Refs**: 코드 `roomestim/edit.py::evolve_room_ceiling_height` / `::snap_layout_to_surfaces`, `roomestim/geom/surface_distance.py::closest_point_on_surface`, `roomestim/adapters/multiview.py::MultiviewAdapter`, CLI `ingest --backend multiview` + `--ceiling-height-m` + `place --snap-to-surfaces`. 재사용: `MeshAdapter._extract_room_model`(ADR 0027/0051 footprint+robust planes), `edit.evolve_room`/`evolve_placement`.

> **핵심요약**: Placement-Sensitivity 측정(rough 기하로 immersive 배치 성립, 천장=복구불가 스칼라, 벽오차=install-time snap)이 도출한 (b) rough+ consumer-tier 를 코드로 착지시킨다. 세 레버를 additive 로 추가: (1a) 사용자 천장높이 override, (1b) 배치 결과를 실제 마운트면에 snap, (2) MeshAdapter 가 거부하던 points-only 클라우드를 직접 인제스트하는 MultiviewAdapter. 핵심 기하 추출은 MeshAdapter 경로 재사용 → footprint 모드/robust 평면 로직 무변경.

---

## Context

`PLACEMENT_SENSITIVITY_VERDICT.md`(spike-vggt-multiview)는 rough(영상→VGGT) 기하로도 immersive **B-coverage** 배치가 성립함을 측정으로 보였다(커버리지 균일도 손실 ~0.7 dB, 대칭 유지). 단 두 가지 cheap requirement 가 남았다:

1. **천장 높이는 rough 클라우드로 복구 불가** — 클라우드 z-범위 ~1–2 m vs 실제 천장 2.3–5.3 m. 그러나 사용자가 줄자로 잴 수 있는 **단일 스칼라**다(공급 시 천장-스피커 면오차 45 cm → 0).
2. **잔여 벽 마운트 오차(~35 cm)는 coverage 문제가 아니라 mounting 문제** — 설치 시 계획 위치를 실제 면에 **snap** 하면 oracle 대비 ~0.03 dB 로 회복.

성숙한 roomestim 코드베이스 점검 결과 인접 기능은 이미 존재했다: footprint front-ends(`--floor-reconstruction convex|concave|occupancy|auto|robust`), `place_dbap` 의 on-surface 마운트. **진짜 갭**은 (a) 사용자 천장 입력 경로 부재, (b) 임포트/편집/드리프트된 레이아웃의 install-time snap 부재, (c) `MeshAdapter` 가 points-only PLY 를 거부(`mesh.py`)하여 **재구성 클라우드(VGGT 등)** 를 받을 길이 없다는 점.

## Decision

### 1a. 사용자 천장높이 override — `edit.evolve_room_ceiling_height(room, height_m)`
floor footprint/surface 불변. 각 wall 을 자기 base edge 위 수직 사각형 `[floor_y, floor_y+height_m]` 으로 재구성(벽/바닥 edge 순서·개수 비의존 → 편집된 방에 robust), ceiling surface 를 `floor_y+height_m` 로 리프트. 재질·옥타브밴드 흡음 보존. 측정 천장은 authoritative → `ceiling_confidence="high"`, `ceiling_coverage=None`. 비양수/비유한 거부, `>20 m` plausibility bound 로 오타 거부. CLI `--ceiling-height-m FLOAT` 를 `ingest`/`run` 에 추가(adapter.parse 후 적용, **모든 backend** 적용 가능, multiview 권장).

### 1b. 면 스냅 — `edit.snap_layout_to_surfaces(room, result)`
각 `PlacedSpeaker.position` → 가장 가까운 wall/ceiling Surface 위 점(floor 는 마운트면 제외). `position` 만 변경, `aim_direction` 유지(스냅 변위 작음). 신규 primitive `geom/surface_distance.py::closest_point_on_surface(point, surface)`: 쿼리점을 면 평면에 투영 후 폴리곤에 clamp(내부면 그대로, 외부면 exterior 최근접) → 반환점은 항상 물리적 면 위. 퇴화면(꼭짓점<3, collinear, self-intersect)은 첫 꼭짓점/최근접 꼭짓점 fallback(never raises). CLI `place --snap-to-surfaces`.

### 2. MultiviewAdapter — `adapters/multiview.py`
재구성 **점군**(.ply points-only / .npz points·xyz·P_m·vertices / .xyz·.txt) 인제스트 → `MeshAdapter._extract_room_model(points, ...)` 재사용(동일 footprint/ceiling/walls/listener). `provenance="reconstructed"` 로 다운그레이드. 선택 `ceiling_height_m` 생성자 인자 → 1a 위임. DoS 가드(`ROOMESTIM_MAX_CLOUD_BYTES`, 기본 ~500 MB, ADR 0038 선례), (N,3)·비유한·`<3 pts` 검증. **VGGT frames→cloud 재구성은 OUT OF SCOPE**(GPU 의존) — 어댑터는 클라우드만 받는다. CLI `ingest --backend multiview`(+기존 `--floor-reconstruction`, 신규 `--ceiling-height-m`).

## Consequences

- **+** rough consumer-tier(폰/영상 점군 → immersive 배치) 가 실제 워크플로로 성립: `ingest --backend multiview --floor-reconstruction convex --ceiling-height-m H` → `place --snap-to-surfaces`. 측정이 정당화한 세 cheap 레버를 모두 코드로 제공.
- **+** 1a/1b 는 backend 무관(measured mesh 에도 적용) → 편집/임포트 레이아웃에도 유용.
- **+** 핵심 기하 추출 무변경(MeshAdapter 재사용) → robust/footprint 회귀 위험 낮음, 기존 게이트 유지.
- **−** MultiviewAdapter 가 `MeshAdapter._extract_room_model`(private)에 의존 → mesh 추출 시그니처 변경 시 동반 수정 필요(같은 모듈군이라 수용).
- **−** 천장 override 미공급 rough 클라우드의 자동 천장은 여전히 low-confidence — 문서/도움말에서 페어링 권장으로 완화.
- **검증**: `tests/test_aconsumer_multiview.py`(천장 override / snap / multiview .ply·.npz·.xyz 합성 클라우드). 전체 게이트 764 passed·7 skipped, mypy strict clean, ruff clean.

## Out of scope
VGGT frames→cloud 재구성(상류/GPU), real-acoustics sim, Web UI.
