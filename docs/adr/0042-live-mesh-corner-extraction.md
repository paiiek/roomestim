# ADR 0042 — Live-mesh corner 추출 (B6): alpha-shape floor polygon + 비볼록 지원

- **Status**: PROPOSED (draft — 미구현; 본 문서는 설계 제안이며 코드/테스트는 아직 존재하지 않는다. 아래 시제는 모두 제안/예정이다.) **REVISED 2026-05-29** — critic 리뷰(ACCEPT-WITH-RESERVATIONS; 2 CRITICAL + 3 MAJOR) 반영: (1) convex-hull deferral 의 출처를 **D6 → ADR 0027 + OQ-13e(ii)** 로 정정(D6 은 capture-device 결정으로 polygon 과 무관 — repo 전반 mislabel 확인), (2) §F 검증의 비-tautological 메시 생성기를 PR2 deliverable 로 명시, (3) §B byte-equal 을 hard short-circuit 계약으로, (4) α 휴리스틱을 jitter variant 게이트로, (5) MultiPolygon silent-discard 가드 추가.
- **Date**: 2026-05-29
- **Deciders**: architect (설계 제안), critic (리뷰 완료: ACCEPT-WITH-RESERVATIONS → 반영), planner (확정 예정)
- **Predecessor / Related**:
  - ADR 0016 (Stage-2 schema flip via SoundCam substitute — A10a corner gate 도입), ADR 0017 (A10 layout deferred / non-substitutable), ADR 0018 (SoundCam substitute disagreement-record — revealed-tautology 명문화)
  - ADR 0027 (mesh-format generalisation — 단일 MeshAdapter; convex-hull-of-projection 채택), ADR 0038 (input resource bounds — 메시 입력 상한)
  - ADR 0040 (Polygon/non-rectilinear ISM RT60 — 비-shoebox RT60 예측; 본 ADR 의 geometry 짝)
  - ADR 0027 (convex-hull-of-projection **채택 출처**) + OQ-13e(ii) (비볼록 alpha-shape 연기). **주의**: repo 전반(ADR 0027:5 cross-ref, `mesh.py:7` docstring, decisions.md:1257/1848)이 이 deferral 을 "D6" 으로 mislabel 해 왔으나, D6(decisions.md:79)은 "Capture device availability — RoomPlan-first" 결정으로 polygon 과 무관하다. 본 ADR 은 이 mislabel 을 정정한다. D29 (web↔core 레인 분리)
  - OQ-13e (live-mesh extraction), OQ-21 (PLY no-faces; CLOSED), OQ-23 (Polygon ISM deferral)

> **핵심요약 (권장안)**: floor polygon 추출 알고리즘을 **alpha-shape(concave hull)** 로 채택할 것을 제안한다(선택지 a). MeshAdapter 의 현 `MultiPoint(...).convex_hull` (`roomestim/adapters/mesh.py:135`) 은 비볼록 footprint(L자형·notch)를 소실시키므로, 이를 신규 core 함수 `floor_polygon_from_mesh` 의 alpha-shape 구현으로 대체하되 **현 convex 경로를 default 로 보존**하고 alpha-shape 는 opt-in(α 파라미터/플래그)으로 진입시킨다(회귀 0). 벽은 현 `walls_from_floor_polygon` (floor 외곽 + ceiling extrusion)을 **그대로 재사용**하며 RANSAC vertical-plane 은 ±10cm 목표 대비 ROI 미달로 채택하지 않는다. "비볼록 지원"(OQ-13e(ii))은 `geom/polygon.py` 가 아니라 **추출단(adapter)** 의 문제임이 코드 확인으로 드러났다(downstream RoomModel/listener/Sabine 는 이미 simple non-convex 를 수용한다). 검증은 **SoundCam mesh download access 없이도** 합성 L-shape 메시(`tests/fixtures/synthetic_rooms.py:175 l_shape_room`)로 비-tautological 입증이 가능하다.

---

## Context

### 현 상태 (검증된 사실)

#### (1) floor polygon 재구성은 "예약된 죽은 stub" + "인라인 convex hull" 의 이중 구조다

- `roomestim/reconstruct/floor_polygon.py` 의 `floor_polygon_from_mesh` 는 **순수 stub** 이다: `del mesh_vertices` (line 38) 후 `raise NotImplementedError` (line 39-42). 프로덕션 호출처는 **0개** — `grep floor_polygon_from_mesh` 결과 정의/`__all__` 외에는 어디서도 import 되지 않는다.
- 실제로 메시에서 코너를 뽑는 코드는 `roomestim/adapters/mesh.py:131-146` 에 **인라인** 으로 존재한다: XZ 평면 투영(line 134) → `MultiPoint(xz_points).convex_hull` (line 135) → exterior 좌표(line 143) → `canonicalize_ccw` (line 144). 주석(mesh.py:7-8, 132-133)이 "convex hull of XY-projected vertices (D6 — alpha-shape deferred)" 를 명시한다(이 주석은 ① deferral 을 "D6" 으로 mislabel 하고 ② 코드가 XZ(`v[0],v[2]`)를 쓰는데 "XY" 라 적은 두 stale 표기를 갖는다 — PR1 에서 cleanup 권장).
- 즉 `floor_polygon_from_mesh` stub 과 mesh.py 의 인라인 hull 은 **연결돼 있지 않다**. B6 의 자연스러운 1차 작업은 이 둘을 **단일 함수로 통합**하는 것이다.

#### (2) 벽 추출은 floor-edge extrusion stub 이다

- `roomestim/reconstruct/walls.py:25-68` `walls_from_floor_polygon` 은 각 CCW floor edge 를 `(p_i,0),(p_{i+1},0),(p_{i+1},h),(p_i,h)` 수직 사각형으로 extrude 한다. RANSAC·평면 fit 은 없다.
- ceiling height 는 `y_max - y_min` (mesh.py:122-124) 로 단순 산출된다. mesh.py:169-174 가 이 함수를 호출한다.

#### (3) synthesized-shoebox revealed-tautology 의 실제 위치 — 프로덕션이 아니라 테스트/fixture 다

OQ-13e 가 지목하는 tautology 는 **프로덕션 코드 경로가 아니다.** 위치는:

- `tests/fixtures/soundcam_synthesized/<room>/GT_corners.json` — GT corners 가 paper-published dims 에서 `[(-L/2,-W/2),(+L/2,-W/2),(+L/2,+W/2),(-L/2,+W/2)]` 로 **합성**된다(`lab/GT_corners.json` 의 `method` 필드 + README §Synthesis methodology step 3).
- `tests/test_a10a_soundcam_corner.py:71-103` `_corner_errors` — 같은 dims 로 `shoebox(width=L, depth=W, height=H)` (synthetic_rooms.py:37) 를 지어 GT 와 비교한다. **같은 dims → 같은 shoebox → 0cm by construction.** 테스트 docstring(line 9-25)이 "STRUCTURALLY TAUTOLOGICAL", "predicted corners equal the GT corners to machine epsilon BY CONSTRUCTION" 을 자인하며, 10cm tolerance 는 "forward-compatibility ONLY" (line 17-21)라고 명시한다.

**tautology 가 회피하는 것**: 실제 SoundCam Azure Kinect PLY 메시에서 (스캔 노이즈·텍스처가 섞인 vertex cloud 로부터) 코너를 추출하는 단계를 건너뛰고, paper 의 깔끔한 직사각 dims 로 shoebox 를 합성해 자기 자신과 비교한다. 그 결과 **"코너 추출 알고리즘의 정확도"는 한 번도 측정된 적이 없다** — A10a 는 fixture-integrity smoke-test 일 뿐이다(README §"Why synthesised instead of live mesh"; ADR 0018 §Consequences). 신뢰성 gap 은: 우리는 "노이즈 있는 실측 메시 → ±10cm 코너"를 입증한 적이 없다는 점이다.

#### (4) 비볼록은 downstream 에서 이미 지원되며, 제약은 추출단에만 있다 — OQ-13e(ii) 전제의 핵심 정정

OQ-13e(ii)는 "`floor_polygon_from_mesh` 의 비볼록 지원" 과 "`geom/polygon.py` 의 비볼록 미지원" 을 묶어서 적었으나, 코드 확인 결과 **둘은 별개이며 후자는 사실상 이미 충족**된다:

- `roomestim/geom/polygon.py` 의 `shoelace_2d` (line 22-39)·`room_volume` (line 66-86) 은 simple non-convex polygon 에서 정상 동작한다. 미지원 케이스는 **self-intersecting(bow-tie)** 뿐이며(line 79-83 주석: "Self-intersecting floor polygons are not a supported input shape"), 이는 비볼록(L-shape) 과 다른 부류다.
- `roomestim/reconstruct/listener_area.py:54-63` 은 concave 폴리곤의 centroid 가 바깥에 떨어질 때 `representative_point()` fallback + `kWarnConcaveListenerCentroid` 경고를 **이미 구현**한다.
- `roomestim/adapters/roomplan.py:263-274` 는 RoomPlan sidecar 의 **임의 floor polygon** 을 `canonicalize_ccw` 만 거쳐 그대로 RoomModel 에 싣는다(L자형 RoomPlan scan 이 이미 통과한다). 즉 RoomModel·placement·Sabine 경로는 비볼록 simple polygon 을 수용한다.
- 단 **ISM RT60 예측은 shoebox 전용**(image_source.py:164 lattice; ADR 0040 §Context)이며, non-shoebox 는 `predictor.py:509` 에서 Eyring 으로 silently route 된다. 따라서 비볼록 floor 가 들어와도 RT60 은 깨지지 않고 정확도만 Eyring 수준으로 떨어진다(ADR 0040 이 다루는 별개 트랙).

**결론**: B6 의 비볼록 작업은 `geom/polygon.py` 확장이 아니라 (i) **추출 알고리즘을 convex hull → alpha-shape 로 교체**, (ii) **self-intersection 검출 가드 1개 추가**, (iii) downstream 의 기존 concave-경로(listener fallback)가 새 입력에서도 동작함을 회귀 테스트로 확인 — 세 가지다.

#### (5) 포인트클라우드 정책 + 의존성

- `points_only.ply` 는 `trimesh.load(force="mesh")` 에서 **0 vertices** 로 로드된다(faces 없으면 trimesh 가 vertex array 를 버림). mesh.py:115-120 의 0-faces 가드(OQ-21, CLOSED)가 `ValueError` 로 reject 한다. 즉 현 정책은 "surface mesh 필수, point cloud 거부".
- 의존성: `shapely>=2.0` + `scipy>=1.10` + `trimesh>=4.0` 모두 **이미 core** (pyproject.toml:11-18). alpha-shape 는 `scipy.spatial.Delaunay` + `shapely.ops.unary_union`/`polygonize` 로 **신규 의존 없이** 구현 가능하다.

### 정밀도 목표

벽 위치 ±10cm. 캡처 노이즈가 dominant error 이므로 sub-cm 정밀도는 reverse goal(과잉 최적화)이다. 알고리즘 선택은 "노이즈 강건성"과 "비볼록 복원"을 ±10cm 안에서 만족하면 충분하다.

---

## Decision (제안)

### A. floor polygon 추출 알고리즘 선택지 비교

| 선택지 | 비볼록 지원 | ±10cm 달성 | 캡처노이즈 강건성 | 신규 의존 | 구현복잡도 |
|--------|-----------|-----------|------------------|----------|-----------|
| **(a) alpha-shape (concave hull)** | **예** (α 로 오목 정도 제어) | 예 (α·후처리로 도달) | 중 (α 튜닝 필요; 작은 α 는 노이즈 포착, 큰 α→convex 로 수렴) | **0** (scipy.spatial.Delaunay + shapely) | 중 (~120-200 LoC + α 선택 휴리스틱) |
| (b) RANSAC plane fit + 벽면 교선 | 예 (수직면 검출 후 교선) | 예 | 중상 (평면 다수일 때 노이즈 강건) | 0 (직접 구현) 또는 pyroomacoustics(web) | 높음 (~300-500 LoC; 평면 군집·교선·정렬 버그 표면 큼) |
| (c) Hough / projection histogram (축정렬 벽 검출) | **제한적** (축정렬 가정; 사선벽·곡선 실패) | 직각방에 한해 예 | 중 (bin 해상도 의존) | 0 | 중 |
| (d) convex hull + 축정렬 (현 상태) | **아니오** (오목 소실) | 볼록방만 | 상 (hull 은 노이즈에 둔감) | 0 (현 코드) | 0 (이미 존재, mesh.py:135) |

**권장: (a) alpha-shape.** 근거:
1. **비볼록이 1차 목표**인데 (d) 는 원리적으로 불가, (c) 는 축정렬 비볼록만, (b) 는 가능하나 ±10cm 목표 대비 과잉 복잡(평면 군집·교선·코너 정렬의 신규 버그 표면).
2. alpha-shape 는 α→∞ 에서 convex hull 로 **연속적으로 수렴**하므로, 현 convex 경로(d)를 alpha-shape 의 특수해로 포섭한다 → **default 보존 + opt-in 전환**이 자연스럽다.
3. 신규 의존 0. scipy Delaunay 의 simplex circumradius 가 α 보다 큰 엣지를 제거하고 `shapely.ops.polygonize`/`unary_union` 로 외곽을 닫는 표준 레시피.

**(b) RANSAC 의 부분 채택 — 벽 추출에서는 불필요**: 아래 §C 참고. floor polygon 만 정확하면 벽은 extrusion 으로 충분하다.

### B. 신규 `floor_polygon_from_mesh` 구현 제안 (alpha-shape)

`roomestim/reconstruct/floor_polygon.py` 의 stub 을 다음 시그니처로 **구현 제안**한다(현재는 미구현):

```
def floor_polygon_from_mesh(
    mesh_vertices: np.ndarray,       # (N,3) listener-frame metres
    *,
    alpha: float | None = None,      # None → convex hull (현 동작 보존)
    floor_band_m: float | None = None,  # 바닥 근처 vertex 만 사용(선택)
) -> list[Point2]:
```

- `alpha is None` → **현 `MultiPoint(xz_points).convex_hull` 코드를 그대로 호출하는 literal
  short-circuit** (Delaunay-with-large-α 경로 아님). byte-equality 는 수치 수렴이 아니라
  **code-path 동일성**으로 보장된다 (critic MAJOR #1). §A 의 "α→∞ 수렴" 은 개념적 설명일 뿐
  회귀 메커니즘이 아니다 — 회귀 게이트는 이 short-circuit 의 hard 계약에 의존한다.
- `alpha is not None` → XZ 투영점에 Delaunay → circumradius > 1/alpha 인 simplex 제거 → 경계 엣지 `polygonize` → ring 선택 → `canonicalize_ccw`.
- **MultiPolygon silent-discard 가드 (critic MAJOR #3)**: `polygonize` 가 >1 polygon 을 내면
  단순히 "최대 면적 ring" 을 고르지 않는다 — 최대 조각이 전체 복원 면적의 **< 95%** 면
  footprint 가 잘못 분해된 것이므로 `ValueError`(또는 경고 + convex fallback)로 처리한다.
  그냥 최대 조각을 고르면 L-shape 의 한 leg 를 silently 버린 valid simple polygon 을 반환해
  downstream 을 조용히 오염시킨다(self-intersection 가드로 못 잡음).
- `floor_band_m` 지정 시 `y_min ≤ y ≤ y_min + floor_band_m` vertex 만 투영(천장·가구 vertex 가 footprint 를 부풀리는 것 방지) — 선택적 노이즈 완화.
- mesh.py:131-146 의 인라인 hull 을 이 함수 호출로 **교체**하여 stub/인라인 이중구조를 해소한다(§I PR1).

α 선택 휴리스틱(제안): vertex 간 평균 최근접거리(scipy cKDTree) 의 k배(예 2~3배)를 1/alpha 로 사용하는 자동 α. 사용자 override 가능. ±10cm 목표이므로 정밀 자동튜닝은 불필요.

### C. 벽 추출 — extrusion 유지, RANSAC vertical plane 미채택

- **권장: 현 `walls_from_floor_polygon` (floor 외곽 + ceiling height extrusion) 재사용.** alpha-shape 가 floor polygon 을 비볼록으로 복원하면, 각 엣지를 extrude 한 벽은 그대로 비볼록방 벽이 된다(walls.py:50-67 의 `range(n)` 루프가 정점 수에 무관하게 동작).
- **RANSAC vertical-plane fit 미채택 근거**: (i) extrusion 이 이미 ±10cm 를 만족(벽 오차 = floor polygon 오차 + 천장높이 오차이며 둘 다 alpha-shape/`y_max-y_min` 로 bound); (ii) RANSAC 평면군집은 floor polygon 과 **독립적으로** 벽을 추정해 둘이 불일치할 위험(코너에서 벽이 안 만남); (iii) ±10cm 목표 대비 과잉. RANSAC 은 reverse-criterion(아래)로 남긴다.

### D. 비볼록 폴리곤(OQ-13e(ii)) — geom/polygon.py 확장 범위

OQ-13e(ii) 전제의 정정(§Context (4)): geom 레이어 확장은 거의 불필요하다. 제안 작업:

1. **검출 가드 추가(권장)**: `floor_polygon_from_mesh` 출력에 `shapely.geometry.Polygon(coords).is_simple` / `.is_valid` 체크를 넣어, alpha-shape 가 self-intersecting ring 을 낼 경우 `ValueError` 로 reject(또는 convex hull fallback + 경고). 이는 polygon.py:79-83 이 명시한 미지원 케이스(bow-tie)를 추출단에서 차단한다.
2. **geom/polygon.py 자체는 변경 불요**: shoelace/Newell 면적은 simple non-convex 에서 이미 정확. 단 docstring(line 79-83)에 "추출단이 self-intersection 을 거른다" cross-ref 추가 권장(문서만).
3. **downstream 회귀 확인**: listener_area.py 의 concave fallback(line 56-63)이 새 alpha-shape 출력에서도 경고/`representative_point` 로 동작함을 테스트로 고정.

### E. 메시 vs 포인트클라우드

- **현 정책 유지**: surface mesh(faces≥1) 필수, point cloud(`points_only.ply` 류) 는 mesh.py:115-120 가 reject(OQ-21 CLOSED). B6 는 이 정책을 **바꾸지 않는다** — alpha-shape 는 vertex 만 쓰지만, "자동 메싱 안 함" 정책상 진입점은 surface mesh 로 유지한다.
- **단, alpha-shape 는 face 가 없어도 동작 가능**하므로, 향후 point-cloud 입력을 허용하려면 0-faces 가드 완화가 별도 결정사항이 된다 → 신규 OQ 로 분리(§OQ).
- **스캔 노이즈 처리**: (i) `floor_band_m` 으로 바닥 근처 vertex 만 사용; (ii) alpha 를 vertex 밀도에 맞춰 자동 설정; (iii) 출력 polygon 에 선택적 Douglas-Peucker 단순화(±10cm tolerance 내 정점 병합)로 노이즈 톱니 제거. 단순화는 over-engineering 방지를 위해 옵션으로.

### F. 검증 전략 — SoundCam access 없이도 비-tautological 입증 가능

**SoundCam mesh download access: 확인 불가.** 본 분석 시점에 SoundCam Azure Kinect PLY(수 GB)의 download/redistribution 가능 여부는 확인되지 않았다(README: "NOT redistributed here"; OQ-13e(i) 가 access 를 조건으로 명시). 따라서 검증을 SoundCam 에 의존시키지 않는다.

제안 검증 레이어(우선순위):

1. **합성 L-shape 메시 round-trip (SoundCam 불요, 권장 1차 게이트)**: `tests/fixtures/synthetic_rooms.py:175 l_shape_room` 의 6-vertex 비볼록 floor(정확히 알려진 GT corners)에서 → 해당 footprint 의 surface mesh(PLY) 를 생성 → `floor_polygon_from_mesh(alpha=...)` → 복원 polygon 의 정점이 GT 6코너에 ≤10cm.
   - **⚠️ CRITICAL 전제 (critic #1)**: 이 메시 생성기는 **현재 존재하지 않는다** — `synthetic_rooms.py` 는 `l_shape_room` 을 hand-coded `RoomModel`(literal 6-vertex floor_polygon)로 반환할 뿐 mesh/PLY export helper 가 없다(`grep mesh/trimesh/\.ply` = 0). 따라서 **PR2 의 명시 deliverable 로 `l_shape_mesh_ply(jitter_sigma=...)` 신규 생성기**를 만든다.
   - **비-tautological 조건 (핵심)**: 생성 메시는 floor 6코너만 삼각화하면 안 되고 **벽·천장·바닥 내부(interior) vertex 를 포함**해야 한다 — 그래야 "전체 vertex 의 convex hull" 은 **틀린 답**이 되고(L-shape 의 오목부를 메움), alpha-shape 만이 GT 를 복원함을 증명할 수 있다. GT 6코너는 `l_shape_room` 의 독립 정의 vertex 다. 단순히 6점 convex hull 을 되돌리는 것은 near-tautological 이며 금지.
   - **노이즈 게이트 (MAJOR #2, PR2 필수 acceptance)**: vertex 에 σ=1~3cm jitter 주입 후에도(`perturb_room_with_walls`(synthetic_rooms.py:110) 패턴) **자동-α 가 ≤10cm 를 달성**해야 한다. clean vertex 만 통과시키는 것으로는 ±10cm 휴리스틱이 입증되지 않는다.
2. **convex 회귀(필수)**: `alpha=None` 경로가 현 mesh.py convex hull 출력과 **byte-equal** — 기존 `lab_room.{ply,obj,gltf,glb}` fixture 로 회귀 0 입증.
3. **A10a tautology 의 비-tautological 승격(조건부)**: SoundCam mesh access 가 **확보되면**(OQ-13e(i)), `test_a10a_soundcam_corner.py` 의 `shoebox()` 합성을 `floor_polygon_from_mesh(downloaded_ply)` 로 교체 → 같은 10cm tolerance 가 그제서야 substantive gate 가 된다(테스트 docstring line 17-21 이 예고한 경로). access 미확보 시 이 단계는 deferred 로 남고 ①②로 ship.
4. **기존 stub 경로 회귀 0**: `floor_polygon_from_mesh` 가 더 이상 `NotImplementedError` 를 raise 하지 않으므로, 이를 기대하던 테스트(있다면)를 갱신. mesh.py 의 default(`alpha=None`) 동작 불변.

### G. Scope / Non-goals

- **In-scope**: alpha-shape floor polygon(비볼록 simple polygon), extrusion 벽, self-intersection 검출 가드, 합성 L-shape 검증.
- **Non-goals(명시적 제외)**:
  - **다층(multi-floor) 메시**: 단일 floor band 가정. 계단·복층은 제외(coupled-space; ADR 0014/0040 §Building_Lobby 선례).
  - **곡면 벽(curved walls)**: alpha-shape 가 다각형 근사는 하나, 곡면을 곡면으로 모델링하지 않음.
  - **사선/경사벽 RT60 정확도**: 비-shoebox RT60 은 ADR 0040(Polygon ISM)의 트랙이며 본 ADR 은 **geometry 추출만** 다룬다(RT60 은 Eyring fallback 유지).
  - **point-cloud 직접 입력**: 현 surface-mesh 정책 유지(별도 OQ).
  - **self-intersecting footprint**: 거부(미지원, polygon.py:79-83).

### H. 리스크

- **R-1 (메시 품질 의존)**: 실측 스캔의 구멍·노이즈·천장 vertex 혼입 → footprint 부풀림. 완화: `floor_band_m` + α 자동튜닝 + 단순화. 잔존 리스크: 매우 노이지한 스캔은 ±10cm 초과 가능 → reverse-criterion 으로 모니터.
- **R-2 (비볼록 edge case)**: alpha 가 너무 작으면 footprint 가 여러 조각(MultiPolygon)으로 분해 → "최대 면적 ring 선택" 정책으로 단일화하되, 분해가 심하면 `ValueError`. self-intersection 은 §D 가드로 차단.
- **R-3 (α 선택 민감도)**: 잘못된 α → over-/under-carve. 완화: 자동 α + 사용자 override + convex fallback. ±10cm 목표라 정밀 튜닝 불요.
- **R-4 (SoundCam access 확인 불가)**: substantive A10a 승격이 access 에 묶임 → ①②(합성 L-shape + convex 회귀)로 ship 하고 ③은 deferred. **honesty**: A10a 가 tautological 인 상태는 access 확보 전까지 ADR 0018 framing 그대로 유지(거짓 "live-mesh 입증" 주장 금지).

### I. 단계적 PR 분할 (제안)

- **PR1 — 알고리즘 + 통합**: `floor_polygon_from_mesh` 에 alpha-shape 구현(`alpha=None` 시 convex byte-equal). mesh.py:131-146 인라인 hull 을 이 함수 호출로 교체. self-intersection 가드. 회귀: 기존 mesh fixture byte-equal.
- **PR2 — 비볼록 검증 fixture**: 합성 L-shape PLY fixture + `floor_polygon_from_mesh(alpha)` round-trip 테스트(≤10cm) + 노이즈 주입 variant. listener concave-fallback 회귀.
- **PR3 — opt-in 노출**: MeshAdapter `parse(..., alpha=...)` / CLI 플래그 노출 + 문서. default 는 convex(회귀 0). **PR2(검증) 가 PR3 를 gate** 한다 — 미검증 alpha-shape 경로를 사용자에게 노출하지 않는다. **ADR 0038 상호작용**: Delaunay 는 O(N log N)이며 ADR 0038 이 허용하는 대형 메시(수백만 vertex)에서 시간·메모리가 급증한다(convex-hull default 경로는 저렴). opt-in alpha-shape 의 vertex-count 상한/`floor_band_m` 다운샘플링을 PR3 에서 ADR 0038 cap 과 정합시킨다.
- **PR4 (조건부, deferred) — A10a 비-tautological 승격**: SoundCam mesh access 확보 시에만. access 미확보면 OQ-13e 부분-resolution 으로 닫고 PR4 deferred.

---

## Consequences

- `floor_polygon_from_mesh` 가 `NotImplementedError` 를 더 이상 raise 하지 않고 실제 polygon 을 반환 → **죽은 stub 의 활성화**. `mesh.py` 의 인라인 hull 이 이 함수로 단일화되어 추출 로직 중복 제거.
- `MeshAdapter` 가 비볼록 footprint 를 보존 가능 → L자형·notch 방의 RoomModel 이 처음으로 정확해진다(단 RT60 은 Eyring 유지; ADR 0040 트랙).
- default(`alpha=None`)가 convex byte-equal 이므로 **기존 사용자 영향 0** → 추가 API(`alpha`)는 additive → SemVer-**MINOR**.
- A10a corner 테스트의 tautology 는 PR4(조건부)까지 **그대로 유지** — 본 ADR 은 추출 알고리즘을 제공할 뿐 SoundCam 입증을 주장하지 않는다(honesty 경계).
- 신규 의존 0 (scipy/shapely/trimesh 모두 기존 core).

## Reverse-criterion

- 합성 L-shape 검증에서 alpha-shape 가 ≤10cm 를 **재현적으로 달성하지 못하면**(α 튜닝으로도) → alpha-shape 채택을 철회하고 (b) RANSAC plane-fit 으로 재검토.
- 실측 스캔에서 alpha-shape footprint 가 routine 하게 ±10cm 초과로 부풀면 → `floor_band_m`/단순화 기본값 강화 또는 RANSAC 승격.
- SoundCam(또는 다른 authoritative) mesh access 가 확보되고 ③ 승격 시 corner err > 10cm 면 → R-2(SoundCam 메시가 실제로 비볼록/비-shoebox-floor)가 사실로 확인된 것이므로 OQ-13e 의 v0.9 risk-register R-2 가 firing → 알고리즘 재평가.
- point-cloud 입력 수요가 확인되면 → 0-faces 가드 완화를 별도 OQ 로 재오픈.

## OQ / decisions 갱신 (제안)

- **OQ-13e (live-mesh extraction)**: 상태를 OPEN → **부분 resolution** 으로 갱신. 조건 (ii)"비볼록 지원"은 본 ADR 이 alpha-shape + downstream 확인으로 해소 경로 제시; (iii)"±10cm 입증"은 **합성 L-shape 로 SoundCam 무관하게 입증 가능**함을 명문화. 조건 (i)"SoundCam mesh access"는 **확인 불가** → A10a 비-tautological 승격(PR4)만 이 조건에 잔류. resolution-candidate 를 "alpha-shape 추출 + 합성 비볼록 검증으로 ship; SoundCam-기반 A10a 승격은 access 확보 시 별도" 로 개정.
- **convex-hull deferral (출처: ADR 0027 + OQ-13e(ii); repo 전반 "D6" mislabel)**: 본 ADR 로
  **해소 경로 확정**. "비볼록=geom/polygon.py 미지원" 전제를 정정(simple non-convex 는 이미 OK;
  self-intersecting 만 미지원). 신규 결정 **D74** 로 (i) "추출단 alpha-shape + self-intersection
  가드" 채택, (ii) deferral 의 정확한 출처가 ADR 0027(+OQ-13e(ii))이며 D6(capture-device)이
  아님을 기록하고 mesh.py:7 / decisions.md:1257,1848 의 mislabel cleanup 을 함께 명시(차기 D
  번호; 현 최고 D73).
- **신규 OQ (제안, 차기 OQ 번호; 현 최고 OQ-46 → OQ-47)**: "Point-cloud 직접 입력 허용 여부 — alpha-shape 는 face 불요이나 현 0-faces 가드(OQ-21)가 reject; point-cloud 수요·노이즈 정책 정의 필요." deferred.
- **ADR 0040 cross-ref**: 본 ADR(geometry 추출)과 0040(non-shoebox RT60)이 짝임을 양방향 기재 — 비볼록 floor 가 추출돼도 RT60 은 0040 의 Eyring/polygon-ISM 트랙에서 처리.

## References

- `roomestim/reconstruct/floor_polygon.py:17-42` — floor polygon stub(`NotImplementedError`; 호출처 0).
- `roomestim/adapters/mesh.py:131-146` — 현 인라인 convex-hull-of-projection(교체 대상).
- `roomestim/adapters/mesh.py:115-120` — 0-faces(point-cloud) 거부 가드(OQ-21 CLOSED).
- `roomestim/reconstruct/walls.py:25-68` — floor-edge extrusion 벽(재사용 대상).
- `roomestim/geom/polygon.py:22-39, 79-83` — shoelace(simple non-convex OK) + self-intersecting 미지원 명시.
- `roomestim/reconstruct/listener_area.py:54-63` — concave centroid fallback(downstream 비볼록 지원 증거).
- `roomestim/adapters/roomplan.py:263-274` — 임의 floor polygon 통과(downstream 비볼록 수용 증거).
- `roomestim/reconstruct/image_source.py:164` + `predictor.py:509` — ISM shoebox 전용 / non-shoebox→Eyring(ADR 0040 트랙).
- `tests/test_a10a_soundcam_corner.py:9-25, 71-103` — revealed-tautology 자인 + 합성 비교 로직.
- `tests/fixtures/soundcam_synthesized/lab/GT_corners.json` + `README.md` — paper-dims 합성 GT; "live-mesh 는 upgrade path".
- `tests/fixtures/synthetic_rooms.py:37(shoebox), 110(perturb), 175(l_shape_room)` — 검증 fixture 후보.
- `pyproject.toml:11-18` — scipy/shapely/trimesh 모두 core(신규 의존 불요).
- ADR 0016/0017/0018 — A10a substitute + tautology framing. ADR 0027 — convex-hull-of-projection 채택. ADR 0038 — 메시 입력 상한. ADR 0040 — non-shoebox RT60.
- `.omc/plans/open-questions.md` — OQ-13e 본문(3조건). `.omc/plans/decisions.md:79` — D6(=capture-device, polygon 무관). `docs/adr/0027` + `decisions.md:1257,1848` + `mesh.py:7` — convex-hull deferral 실제 출처 + "D6" mislabel 위치.
