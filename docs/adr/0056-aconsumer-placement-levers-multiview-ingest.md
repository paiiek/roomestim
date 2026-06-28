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

## Status-update — v0.50.1 (독립 code-review follow-up, 2026-06-26)

v0.50.0 는 위에서 "code-reviewer(예정)" 로 남겨둔 독립 리뷰 전에 출하됐다. 다른 세션의 독립
`code-reviewer` 패스가 **APPROVE-WITH-FIXES**(0 CRITICAL/HIGH, 1 MEDIUM, 4 LOW) 를 냈고,
아래 3건을 **additive PATCH**(v0.50.1) 로 반영했다(코어 동작·골든 byte-equal, 기존 backend 무영향):

- **(MEDIUM)** `evolve_room_ceiling_height` 의 floor_y 재앵커링이 **floor 평면≠0** 케이스에서 미검증
  (모든 기존 테스트가 floor=y0). mesh 추출은 벽을 `y=0` 부터, floor 는 detected 평면에 두므로
  offset floor 면 override 가 벽을 `[floor_y, floor_y+h]` 로 옮겨 일관성을 **복구**한다(의도된 동작).
  → docstring 에 의도 명시 + 회귀 테스트 `test_ceiling_override_offset_floor_consistency`(클라우드 +5 m
  리프트) 추가.
- **(LOW)** `MultiviewAdapter.__init__` 가 `ceiling_height_m` 의 `≤20 m` plausibility bound 를
  parse() 까지 지연 → 생성자에서 fail-fast 하도록 동일 bound(`edit._MAX_USER_CEILING_M`) 적용.
- **(LOW)** `_points_from_npz` 의 named-key 분기가 `(N,6)` xyzrgb 를 미슬라이스해 downstream `(N,3)`
  체크에서 거부 → `.xyz`/`.txt` 로더와 parity 로 `[:, :3]` 슬라이스.

나머지 2 LOW(`place`/`collection` 에 `--backend` 인자 부재로 disclosure source phrase 가 정직한
generic "a reconstruction" 으로 폴백 / `closest_point_on_surface` 의 퇴화-edge 과보수 fallback)는
정직·무해로 **수용**. 또한 v0.50.0 이 누락했던 **README 문서화**(backend 열거 + `multiview`/A-consumer
레버 섹션 + 릴리스 행)를 동반. 전체 게이트 **767 passed·7 skipped**, mypy strict(63)·ruff clean.

## Status-update — v0.53.0 (MultiviewAdapter metric scale_anchor, 2026-06-28, additive MINOR)

ADR 본문 §2 는 재구성 클라우드를 **metric-native 가정**으로 ingest 했다(`parse` 가
`scale_anchor` 를 `del` 로 무시). 그러나 VGGT-class frames→cloud 재구성은 metric-native 가
**아니다** — per-room scale 이 ~1–5x 드리프트한다([[project_multiview_fusion_a1]] OQ-53 scale
FAIL 맥락). 단일 user-measured scalar 로 이를 보정하는 cheap A-consumer 레버를 추가한다(additive,
no-anchor 경로 byte-equal).

- **메커니즘**: `parse(scale_anchor=...)` 가 supplied 되면 (1) 방을 한 번 추출, (2) footprint
  diameter(= `floor_polygon` 의 (x,z) 코너 최대 pairwise 거리, `_footprint_diameter`,
  scipy `pdist`) 측정, (3) 클라우드를 `length_m / diameter` 로 **등방 리스케일**, (4) 재추출.
  `length_m` = footprint **diameter = 코너-대-코너 대각**(임의 두 footprint 코너 사이 최대 직선거리,
  줄자/도면). **최장 벽이 아니다** — 비정방형 방에선 대각 > 최장벽이라 벽을 재면 aspect-ratio 만큼
  (4×3 에서 ~20%) silent mis-scale. 이후 `ceiling_height_m` override 는 재추출된 방에 적용.
- **scale-invariance**: anchor length 가 고정이라 입력 클라우드를 임의 `k` 로 mis-scale 해도
  anchored footprint 가 동일(테스트 `test_scale_anchor_removes_input_scale_dependence`, k=0.37/2.5
  → 면적 rel 1e-6 일치). 즉 결과는 입력 클라우드 scale 에 **무의존**. 단 이 *exact* 무의존은
  `convex`(default, 클라우드 hull 이 scale-equivariant)에서만 — robust/concave/occupancy 의
  절대-미터 양자화 하에선 근사(테스트는 convex 만 커버).
- **가드**: `type ∈ {known_distance, user_provided}` (그 외 거부), `length_m` finite & >0
  (0/음수/inf/nan 거부), degenerate footprint(diameter 0) 거부.
- **scope**: **library-only**. CLI `_scale_anchor_for` 는 `--backend image`(cam_height)에만
  anchor 를 만들고 multiview 엔 None 을 준다 → cli.py(동시세션 경합 hot-path) 무변경 유지. multiview
  CLI 노출(`--known-floor-len-m` 류)은 별도 follow-up. VGGT frames→cloud 재구성은 여전히 OUT OF
  SCOPE.
- **검증 한계(정직)**: `_footprint_diameter` 는 추출된 (가능하면 convex) footprint 의 코너
  대각에 의존 — under-captured 클라우드에서 convex-hull 이 diameter 를 과대/과소 추정하면 rescale 도
  같은 비율로 bias 된다. scale-invariance(입력 무의존)는 증명되나, **anchored 절대치의 정확도는
  footprint 추출 품질에 종속**이며 real-scan end-to-end GT 로 미검증.
- **검증**: `tests/test_aconsumer_multiview.py` +6 케이스(scale-invariance/metric 착지 ~12㎡
  /diameter 복원/type·length 거부/no-anchor 회귀가드). 전체 게이트 **791 passed·8 skipped**,
  web 95 passed·4 skipped, mypy strict·ruff clean.

## Status-update — v0.54.0 (multiview scale_anchor CLI 배선, 2026-06-28, additive MINOR)

v0.53.0 가 "별도 follow-up" 으로 남긴 multiview CLI 노출을 마감한다. `scale_anchor` 가 더는
library-only 가 아니다 — `ingest`/`run` 에 `--known-floor-len-m M` 플래그를 추가했다.

- **배선**: 공유 헬퍼 `_add_known_floor_len_arg`(ingest+run 양쪽 호출) + `_scale_anchor_for(args)` 를
  backend 별 분기로 재구성 — `image`→`--cam-height`(기존 그대로), `multiview`→`--known-floor-len-m`
  으로 `ScaleAnchor("known_distance", len)`, 그 외/미공급→`None`. **image·기존 backend 경로 무변경**
  (구 함수는 non-image 를 early-return None 했고, 신 함수도 동일 결과).
- **계약**: 플래그 help 는 `length_m` = footprint **diameter = 코너-대-코너 대각**(최장 벽 아님)임을
  명시. 잘못된 length 는 adapter 가 ValueError → CLI 가 rc 1 로 표면화(room.yaml 미기록), 별도
  CLI-side 검증 미중복.
- **검증**: 신규 `tests/test_cli_multiview_scale_anchor.py` +5(`main([...])` 하니스, 실 .npz
  클라우드): metric 착지 ~12㎡·CLI scale-invariance(2x mis-scale→동일 면적 rel 1e-6)·no-anchor
  회귀·`run` 출력(room+layout)·bad-length(`-1`)→rc≠0·room.yaml 미기록. ruff·mypy strict clean.
  남은 한계는 v0.53.0 항목과 동일(anchored 절대치 정확도 = footprint 추출 품질 종속, real-scan GT
  미검증).
