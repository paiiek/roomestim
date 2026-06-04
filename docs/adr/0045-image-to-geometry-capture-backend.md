# ADR 0045 — image/video → room geometry (`[vision]` capture backend) (draft)

- **Date**: 2026-06-01
- **Status**: Proposed (draft) — **부분 구현·출하**. rough tier(§B)의 단일-파노 image backend 는 v0.25.0 에서 구현·출하됐다(experimental `--backend image`; §Status-update-2026-06-04b / D86 / ADR 0046 참조). install-grade 1급 경로(§C)·multi-view 는 미구현/FALLBACK 으로 남아 제안/예정 시제다. §Phase-0/multi-view 스파이크의 사실은 수행되었으므로 과거 시제로 기술한다(ADR 0020/0044 honesty 규율). header 가 PROPOSED 인 것은 ADR 전체(특히 install-grade §C)가 미확정이기 때문이다.
- **Deciders**: architect (설계 제안), critic (리뷰 예정), planner (확정 예정), 사용자 (greenlight 예정)
- **Refs**: ADR 0001 (capture-backend priority — RoomPlan first-class, COLMAP `[colmap]`+`--experimental`, scale-anchor work = v0.3 scope; **본 ADR 은 ADR 0001 이 보류한 image/COLMAP 브랜치의 연속**), ADR 0002 (room representation — 2.5D polygon + scalar ceiling), ADR 0027/0042 (mesh adapter · hull→polygon · live-mesh corner extraction 선례), ADR 0020 (tense-lint honesty scope), ADR 0044 (RIR auralization — image-derived geometry 의 하류 소비자), D26 (forbidden-indefinite-deferral / YAGNI); 리서치 리포트 `.omc/research/image-to-geometry-feasibility-2026-06-01.md`; Phase-0 스파이크 아티팩트 `/home/seung/mmhoa/spike-image-geometry/` (`final_spike_summary.json`, `metric_s2d3d_results.json`); 결정 D81.

> **핵심요약 (권장안)**: 설치공간 사진/영상에서 `RoomModel` geometry 를 복원하는 `[vision]` capture backend 를 **정직성-우선 tiered** 아키텍처로 제안한다. 신규 `CaptureAdapter`(`adapters/image.py`)가 기존 `parse(path, *, scale_anchor, octave_band) → RoomModel` Protocol 을 roomplan/mesh 와 나란히 구현하고, 무거운 모델 의존은 optional extra(`[vision]` 신규 또는 `[colmap]` 확장) 뒤에 둔다 — core `roomestim/` 의존 0 불변. 출력 geometry 는 `provenance=reconstructed(image)` 로 태그하여 RoomPlan LiDAR 의 `measured` 와 **결코 동일한 install-grade 측정으로 제시하지 않는다**. Phase-0 스파이크는 single-pano(HorizonNet, out-of-domain st3d 체크포인트)가 ≤15 cm 게이트를 **신뢰성 있게 통과하지 못함**(verdict = **FALLBACK, conditional**)을 실증했으므로, single-pano 는 **rough-estimate / assisted-measure / pre-scan tier** 로 한정 제안하고(엔지니어 확인 후 layout/RIR 투입), **multi-view(MASt3R/VGGT)** 를 *better-than-rough* 정확도가 필요할 때의 1급 경로로 둔다. 본 ADR 은 ADR 0001 의 `--experimental` 게이트 선례를 상속한다. 재질은 manual/UNKNOWN 유지(시각→흡음은 install-grade 아님). provenance/confidence 정직성 메커니즘은 소규모 `RoomModel`/`Surface` 스키마 추가가 필요할 수 있으나 본 제안 시점에는 설계 작업으로 플래그만 했다(room-level provenance 는 이후 v0.25.0 에서 구현·출하됐다 — ADR 0046 / §Status-update-2026-06-04b; per-Surface 는 OPEN).

---

## Context

### 현 상태 (코드 확인 사실 — 2026-06-01)

**(1) 신규 아키텍처가 아니라 ADR 0001 의 연속이다.** ADR 0001(`docs/adr/0001-capture-backend-priority.md`)은 "RoomPlan first-class, Polycam secondary, COLMAP experimental behind `[colmap]` extra + `--experimental` flag" 를 이미 수락했고, "COLMAP scale-anchor work(ArUco / known-distance reference) = v0.3 scope"(같은 ADR §Follow-ups, line 45)로 image 브랜치를 명시 **보류**했다. 본 ADR 0045 는 그 보류된 image/COLMAP 브랜치의 **만기 연속**이며 새 방향이 아니다.

**(2) 캡처 계약과 ScaleAnchor 가 이미 pre-wired 되어 있다.** `roomestim/adapters/base.py:23` 의 `CaptureAdapter` Protocol 은 `parse(path, *, scale_anchor: ScaleAnchor | None, octave_band: bool) → RoomModel`(`base.py:25~31`)을 정의한다. `ScaleAnchor`(`base.py:12~20`)는 `type: "aruco" | "known_distance" | "user_provided"` 와 `length_m: float` 을 이미 갖는다 — image backend 의 metric-scale 해소(파노=카메라/삼각대 높이 = `known_distance`, multi-view=ArUco)에 신규 필드가 불필요하다.

**(3) 출력 계약이 저차원이다.** `RoomModel`(`model.py:275`)은 `floor_polygon: list[Point2]`(`model.py:279`) + scalar `ceiling_height_m`(`model.py:280`) + planar wall `Surface` 리스트(`model.py:281`; `Surface.material: MaterialLabel`, `model.py:152`) + `schema_version: str = "0.2-draft"`(`model.py:284`)로 구성된 2.5D extruded prism 이다. `canonicalize_ccw`(`model.py:326`)가 floor polygon 정규화를 제공한다. 즉 dense mesh/NeRF 가 아니라 ~4–12 wall plane + metric floor ring 만 복원하면 되며, 이는 room-layout-estimation 계열이 full photogrammetry 보다 적합함을 뜻한다.

**(4) optional-extra 선례가 이미 둘 존재한다.** `pyproject.toml:20` `[project.optional-dependencies]` 아래 `web = [...]`(`pyproject.toml:28~43`)와 `colmap = ["pycolmap>=0.6"]`(`pyproject.toml:47`)가 선언되어 있다. `[web]` 패턴(무거운 audio/ML 의존을 extra 뒤로 격리, core 의존 0)이 image backend 의 모델 의존 격리에 그대로 적용된다.

**(5) 어댑터 재사용 seam 이 존재한다.** `adapters/roomplan.py`(metric-native 선례)와 `adapters/mesh.py`(hull→floor polygon degenerate path; ADR 0027/0042)가 `parse(...)→RoomModel` 을 구현한다. mesh adapter 의 `hull` + `walls_from_floor_polygon` 류 헬퍼는 multi-view planar fit 의 floor-ring→wall 조립에서 재사용 seam 이 된다.

### 문제

roomestim 의 캡처 계약은 backend-agnostic 이며 ScaleAnchor 까지 pre-wired 되어 있으나, 현재 metric geometry 를 산출하는 backend 는 RoomPlan(LiDAR, `measured`)과 mesh 뿐이다. iOS Pro 디바이스가 없거나(ADR 0001 §Consequences 의 device-availability gap), 사전 스캔 없이 일반 사진/영상/360 파노라마만 보유한 사용자는 진입 경로가 없다. ADR 0001 이 v0.3 로 보류한 image/COLMAP 브랜치가 만기되었고, 본 ADR 은 그 브랜치를 **정직성-우선**으로 다시 연다.

### Phase-0 스파이크 (수행됨; 사실 기술 — 과거 시제)

목표: "360 파노 1장 + 카메라높이 1개 → floor_polygon + ceiling_height 가 GT 대비 허용오차(≲10–15 cm) 내인가" 라는 make-or-break 1질문 (`.omc/research/image-to-geometry-feasibility-2026-06-01.md` §Phase-0).

수행한 것 (아티팩트 `/home/seung/mmhoa/spike-image-geometry/`):
- HorizonNet(single-pano room-layout net, HF-미러 `resnet50_rnn__st3d` 가중치, **Structured3D 학습**)을 166 실측 GT 방에 forward 했다 — PanoContext(53, residential, roomestim 에 가장 관련) + Stanford2D3D(113, offices/conference/hallway). **두 데이터셋 모두 해당 체크포인트에 out-of-domain** 이다.
- **Standard layout metric**: S2D3D 5.09% Corner-Err / 62.6% 3D-IoU; PanoContext 8.46% CE / 61.5% IoU (vs in-domain README 보고 ~0.76% CE / ~83% IoU).
- **Metric cm 오차** (카메라높이 ScaleAnchor 적용 후): nominal cam_h → median wall 35–57 cm; **PERFECT ScaleAnchor → median wall 18 cm, 단 43–45% 방만 ≤15 cm**; ±10 cm cam_h 불확실성 → median 32–38 cm. 오차는 ~34–40 cm **SCALE 성분**(ScaleAnchor 로 해소 가능)과 ~18 cm **SHAPE 성분**(축소 불가한 corner 오차)으로 분해된다.
- **기준선**: RoomPlan LiDAR ~8.5 cm avg. 결정 게이트는 ≲10–15 cm 였다.

엔지니어링 경로는 de-risk 되었다: GPU 에서 ~0.25 s/img 로 동작했고, net 출력이 `RoomModel`(polygon + per-wall height)에 1:1 매핑되며, metric scaling 이 카메라높이 스칼라 1개(기존 ScaleAnchor `known_distance`)였다. **계약 caveat**: HorizonNet 은 Manhattan + 단일 평면 천장을 가정하므로, non-Manhattan/multi-height 방은 AtlantaNet-class 가 필요하거나 silently 사각화된다.

**VERDICT = FALLBACK (conditional)**: single-pano(st3d, out-of-domain)는 ≤15 cm 게이트를 **신뢰성 있게 통과하지 못했다**. 이 gap 은 (a) out-of-domain 체크포인트, (b) cam_h scale 민감도, (c) floor-boundary elevation 오차에 귀속되며, **원리적 기각이 아니다** — 접근 불가한 in-domain 체크포인트라면 borderline 일 개연성이 있다. (출처: `final_spike_summary.json`, `metric_s2d3d_results.json`.)

### 연구 근거 (요약; 전문 `.omc/research/image-to-geometry-feasibility-2026-06-01.md`)

- **파이프라인 순위** (accuracy × metric-scale ÷ effort): (1) 360° 파노라마 → room-layout net(HorizonNet/HoHoNet/AtlantaNet) → metric, net 출력이 곧 계약 + 스케일 = 카메라높이 스칼라 1개; (2) multi-view 사진/영상 → MASt3R(metric pointmap)/VGGT(CVPR'25) → RANSAC/Manhattan plane fit → floor-ring, 스케일 = ArUco/측정 reference; (3) (fallback) single 일반 사진 → monocular metric depth → plane fit, rough tier 만.
- **재질 honesty**: 시각→흡음은 install-grade 가 아니다(SAP-Net = topology-image 기반, CRNN material = measured IR 기반 — 둘 다 설치공간 사진이 아니다). 저신뢰 visual material *제안*만 가능하고 auto-commit 은 금지다.

---

## Decision

### §A — tiered, honesty-first capture backend

image/video → geometry 를 **provenance 태그를 동반한 tiered backend** 로 제안한다.

- 신규 `CaptureAdapter`(`adapters/image.py`)가 roomplan/mesh 와 나란히 기존 `parse(path, *, scale_anchor, octave_band) → RoomModel` Protocol 을 구현한다(`base.py:23~31`). geometry 재구성 핸드오프(pretrained 모델 호출) → ScaleAnchor 소비(metric 해소) → planar/Manhattan fit → 계약(`canonicalize_ccw` floor polygon + `ceiling_height_m` + vertical-rect walls)의 3단계를 예정한다.
- 출력 geometry 는 **`provenance = reconstructed(image)`** 로 태그할 것을 예정한다(§F 의 스키마 설계 후). 장차 RoomPlan LiDAR 의 `measured` 및 default 의 `assumed` 와 구분되도록 할 예정이며(현재 `model.py` 에는 provenance 필드가 없다 — §F 참조), image-derived geometry 는 **install-grade 측정으로 제시하지 않을 것을 규약화** 한다 — CLI/web 에서 "estimated" 로 가시 라벨하고, layout/RIR 투입 전 엔지니어 확인을 거치도록 제안한다(ADR 0044 가 image-derived geometry 의 하류 소비자이므로 특히 중요).

### §B — single-pano = rough-estimate / assisted-measure / pre-scan tier

Phase-0 스파이크 verdict(FALLBACK, conditional)에 근거하여, single-pano(HorizonNet-class) 경로를 **install-grade 가 아니라 빠른 rough tier** 로 한정 제안한다. 이 tier 의 출력은 다음을 동반할 것을 예정한다:
- **per-corner 불확실성** (스파이크의 ~18 cm SHAPE 성분이 corner-level 잔차임을 반영),
- **Manhattan-assumption flag** (non-Manhattan/multi-height 방의 silent 사각화 방지),
- **scale-source disclosure** (어떤 ScaleAnchor 가 어떤 입력값으로 metric 을 해소했는지 — 치수가 silently "metric" 으로 둔갑하지 않게).

엔지니어가 layout/RIR 에 투입하기 전 확인하는 것을 default 로 둔다.

### §C — multi-view(MASt3R/VGGT) = first-class accuracy path

*better-than-rough* geometry 가 필요할 때의 1급 정확도 경로로 multi-view(MASt3R metric pointmap / VGGT feed-forward)를 예정한다. 근거: multi-point anchor(ArUco/측정 reference)로 scale 을 해소하므로 single-pano 의 단일 cam_h 스칼라보다 scale 민감도가 낮고(스파이크가 노출한 ~34–40 cm SCALE 성분 / ±10 cm cam_h 민감도를 완화), non-Manhattan/clutter 방을 더 잘 다룬다. 비용: point cloud → RANSAC/Manhattan plane fit + floor-ring 추출이 진짜 BUILD 작업이며(mesh adapter seam 재사용), multi-view metric-scale 실현가능성은 별도 스파이크가 선행한다(OQ-53). **라이선싱 주의**: MASt3R 및 VGGT 공개 가중치는 non-commercial 라이선스를 포함할 수 있으므로, 스파이크(OQ-53) 착수 전 라이선스 조건을 확인해야 한다 — 상업적 배포가 필요한 경우 후보 목록에서 제외하거나 대안을 탐색해야 할 수 있다(OQ-53 의 선행조건으로 포함).

> **스파이크 결과 (2026-06-02, §Status-update-2026-06-02 / D83 참조)**: VGGT-1B multi-view 스파이크가 scale 하위질문을 PASS(median scale error 1.6%, 6/10 ≤5%)로 닫아 §C 의 핵심 risk(scale 민감도)를 해소했다. 단 ≤15 cm floor-geometry 는 out-of-the-box FALLBACK(median 22.4 cm; periphery under-coverage 가 root cause, scale 아님)이므로, multi-view 를 *조건부* 1급 경로로 두되 install-grade ship 전에 집중된 floor-extraction front-end 스파이크(OQ-59)를 선행한다. 그 후속으로 OQ-59 가 front-end 레버 질문을 **NO** 로 닫았다(§Status-update-2026-06-04 / D84): 배포가능 front-end 그 어느 것도 ≤15 cm 를 close 하지 못했고(최고 배포가능 `convex_band` 17.13 cm / 4-of-10 도 FAIL), root cause 가 corner-fitting 아닌 coverage 임이 재확인됐다. 따라서 multi-view 는 first-class ≤15 cm 경로로 **승격되지 않고 rough-tier 에 머문다**; 다음 레버는 front-end 가 아니라 coverage(coverage-aware capture / TSDF / VGGT-Omega — 별도 스파이크)다.

### §D — 의존성 격리 (core 게이트 불오염)

무거운 모델 의존(HorizonNet/MASt3R/VGGT 런타임)은 optional extra 뒤에 둔다 — `[vision]` 신규 선언 또는 기존 `[colmap]` 확장(`pyproject.toml:47`) 중 택일을 예정한다. core `roomestim/` 의 의존 0 을 불변으로 유지하여(`[web]`/`[colmap]` 선례, §Context (4)), 기본 게이트를 오염시키지 않는다. ADR 0001 의 `--experimental` 게이트를 상속하여 experimental 경로로 노출한다.

### §E — 재질은 manual/UNKNOWN 유지

image backend 가 복원하는 `Surface.material`(`model.py:152`, required field — `Surface` dataclass 에 implicit default 없음) 은 어댑터가 **명시적으로** `MaterialLabel.UNKNOWN`(`model.py:54`, `= "unknown"`)을 설정해야 한다. `Surface.material` 에는 암묵적 default 가 존재하지 않는다(`model.py:152` 가 required 필드임; `material: MaterialLabel = MaterialLabel.UNKNOWN` default 는 다른 dataclass 인 `Object`(`model.py:243`)에 존재하므로 혼동하지 않는다). 따라서 구현 시 image adapter 는 `Surface(material=MaterialLabel.UNKNOWN, ...)` 를 명시 지정해야 한다. 시각→흡음 분류는 install-grade 가 아니므로(§Context 연구 근거), 도입한다면 **저신뢰 visual *제안*에 한정**하고 auto-commit 을 금지한다. 시각 재질 분류 viability 는 OQ-55 로 분리한다.

### §F — provenance/confidence 스키마 = 설계 작업 (지금 구현하지 않음)

`measured | reconstructed | assumed` 정직성 태그를 per-`RoomModel`/per-`Surface` 로 표현하려면 소규모 스키마 추가가 필요할 개연성이 있다. `schema_version: str = "0.2-draft"`(`model.py:284`) 와 `MaterialLabel.UNKNOWN`(`model.py:54`) 선례가 존재하므로 자연스러우나, **현재 `model.py` 에는 provenance 필드가 없다** — 본 ADR 은 이를 **설계 작업으로 플래그만 하고 지금 구현하지 않는다**. 스키마 형태·하위호환·honesty 리뷰는 OQ-54 및 blocking gate #3 의 선행조건으로 둔다.

### §G — 비목표 (non-goal, 스코프 경계)

본 ADR 의 scope 는 **단독·정적·빈 방(single, empty, static room)** 의 geometry 복원에 한정한다 — 가구/사람이 있는 occupied/dynamic scene, 복수 공간을 이어붙인 multi-room stitching, 외부 공간, 정밀 텍스처·재질 포인트클라우드는 모두 out-of-scope 이다. 이 경계는 프로젝트의 bounded-scope ethos(D26)를 상속하며, scope 확장은 별도 ADR 로 다룬다.

---

## Consequences

**Positive**
- ADR 0001 의 만기 보류 브랜치 closure — device-availability gap(non-Pro 디바이스·사전 스캔 부재)에 진입 경로 제공.
- 계약 재사용: 신규 `parse(...)→RoomModel` adapter 하나, ScaleAnchor pre-wired(`base.py`), mesh adapter floor-ring seam 재사용 → roomestim-side BUILD 최소화.
- core 게이트 불오염: 모델 의존을 optional extra 뒤로 격리(§D) → core 회귀 0, `[web]`/`[colmap]` 경계 보존.
- 정직성-우선: provenance 태그 + per-corner 불확실성 + scale-source disclosure 로 image-derived 치수가 measured 로 둔갑하지 않음 — 프로젝트 ethos(measured/assumed honesty marker 선례) 정합.
- single-pano 엔지니어링 경로는 스파이크로 이미 de-risk(~0.25 s/img, 1:1 RoomModel 매핑, 스칼라 1개 스케일).

**Negative / risk**
- single-pano 정확도가 install-grade 게이트(≤15 cm)를 신뢰성 있게 통과하지 못한다(스파이크 verdict) — rough tier 한정이 이 risk 의 정직한 수용이며, install-grade 승격은 blocking gate 통과 전까지 금지.
- multi-view 1급 경로는 RANSAC/Manhattan plane fit + floor-ring 추출이 진짜 BUILD(가장 무거움)이고 metric-scale 실현가능성이 미검증(OQ-53).
- non-Manhattan/multi-height 방의 silent 사각화 risk(HorizonNet 계약 caveat) — Manhattan-assumption flag 로 완화하되 AtlantaNet-class 도입은 미결(OQ-56).
- provenance 스키마 추가(§F)가 `RoomModel`/`Surface` 하위호환과 하류 소비자(ADR 0044 auralization)에 영향 — 설계·리뷰 선행 필요.

**Neutral**
- 기존 roomplan/mesh adapter 와 데모 경로는 불변(별도 adapter 추가, 기존 경로 무수정).
- in-domain 체크포인트는 접근 불가하여 스파이크가 borderline-여부를 직접 확인하지 못함 — 원리적 기각이 아니라 미검증으로 남김(OQ-52).

---

## Reverse-criterion (image backend 를 하지 말 것 / rough tier 로 충분할 때 / RoomPlan+mesh 에서 멈출 때)

다음 증거 중 하나라도 성립하면 image backend(또는 그 일부 tier)를 **하지 않고** RoomPlan+mesh 에 머문다:

1. 대상 사용자가 사실상 전원 iOS Pro/LiDAR 디바이스를 보유한다 → RoomPlan `measured`(~8.5 cm) 가 항상 우월, image backend 의 한계효용이 의존성·복잡도 비용을 정당화하지 못함.
2. 용도가 *rough/pre-scan* 으로 충분하고 install-grade 정밀이 불필요하다 → single-pano rough tier 까지만 구현하고 multi-view 1급 경로(§C, BUILD 최대)는 착수하지 않음(YAGNI, D26).
3. multi-view metric-scale 스파이크(OQ-53)가 single-pano 대비 의미 있는 정확도 개선을 보이지 못한다 → 1급 경로 미착수, rough tier 한정 유지.
4. provenance honesty 스키마 합의(OQ-54)에 도달하지 못한다 → image backend 출력을 measured 와 구분 불가하므로 **착수 금지**(정직성 우선 — 구분 불가한 reconstructed 치수는 위험).
5. in-domain 체크포인트 검증(OQ-52)에서도 ≲15 cm median 에 도달하지 못한다 → single-pano 의 install-grade 승격을 영구 포기, rough tier 로 고정.

> 근거: Phase-0 스파이크가 single-pano(out-of-domain)의 ≤15 cm 미달을 실증했고(verdict FALLBACK), RoomPlan LiDAR(~8.5 cm)가 가용할 때의 우위는 명확하다.

## Blocking gate (구현 착수 전 충족)

1. **in-domain 체크포인트 검증** — single-pano 를 rough tier 에서 install-grade 로 **승격하기 전**, in-domain(residential) 체크포인트가 calibrated cam_h 로 residential 방에서 ≲15 cm median 에 도달함을 검증(OQ-52). 미달 시 single-pano 는 rough tier 영구 고정.
2. **multi-view metric-scale 스파이크** — 1급 정확도 경로(§C) 착수 전 MASt3R/VGGT 의 metric-scale 실현가능성 + floor-ring 추출을 spike 로 GREEN 확인(OQ-53).
3. **provenance-tag 스키마 설계 + honesty 리뷰** — `measured | reconstructed | assumed` 태그의 `RoomModel`/`Surface` 스키마 형태·하위호환·CLI/web 라벨링을 설계·리뷰 합의(OQ-54). 합의 전 image backend 출력 노출 금지(Reverse-criterion #4).
4. **core/web 경계 보존** — 모델 의존이 `[vision]`/`[colmap]` extra 뒤에만 존재(core 의존 0), 기본 + web 게이트 회귀 0(canonical `/home/seung/miniforge3/bin/python -m pytest`), tense-lint EXIT=0 재확인.

## Alternatives considered

- **single-pano 를 install-grade 1급 backend 로 즉시 승격**: 스파이크 verdict(43–45% 방만 ≤15 cm, ±10 cm cam_h → 32–38 cm)가 신뢰성을 반박 → 기각, rough tier 한정.
- **multi-view 1급 경로를 먼저 BUILD**: 가장 무거운 작업(RANSAC/Manhattan plane fit)이고 metric-scale 미검증 → spike(OQ-53) 선행 전 착수 기각, rough tier(낮은 effort)부터.
- **full photogrammetry / dense mesh / NeRF**: 출력 계약이 저차원(floor ring + ~4–12 plane)이므로 과잉 → 기각, room-layout-estimation 계열 채택.
- **시각 재질 자동 분류 install-grade 도입**: 시각→흡음이 install-grade 아님(SAP-Net/CRNN 도메인 불일치) → 기각, manual/UNKNOWN 유지 + 저신뢰 제안만(OQ-55).
- **image backend 미착수(RoomPlan+mesh 고정)**: device-availability gap 을 닫지 못함, ADR 0001 보류 브랜치 무기한 미해소(D26 forbidden-indefinite-deferral 긴장) → 본 ADR 이 정직성-우선 tiered 로 재개.

## Open Questions (신규)

- **OQ-52**: in-domain(residential, Structured3D-domain) 체크포인트로 single-pano 가 calibrated cam_h 에서 residential 방 ≲15 cm median 에 도달하는가 — 스파이크가 사용한 out-of-domain st3d 가중치의 정확도 gap 이 체크포인트 귀속인지 확인. install-grade 승격 gate(blocking gate #1).
- **OQ-53**: multi-view(MASt3R/VGGT) metric-scale 실현가능성 — multi-point anchor 로 scale 을 single-pano cam_h 보다 안정적으로 해소하는가 + floor-ring/Manhattan plane fit 이 계약을 산출하는가. 1급 경로 gate(blocking gate #2).
- **OQ-54**: provenance/confidence 태그 스키마 — `measured | reconstructed | assumed` 를 `RoomModel`/`Surface` 에 추가하는 형태·하위호환·CLI/web 라벨링·하류 소비자(ADR 0044) 영향. honesty 리뷰 gate(blocking gate #3, Reverse-criterion #4).
- **OQ-55**: 시각 재질 분류 viability — 설치공간 사진에서 저신뢰 visual material *제안*이 의미 있는 신호를 주는가(auto-commit 금지 전제). 미충족 시 §E manual/UNKNOWN 만 유지.
- **OQ-56**: non-Manhattan / multi-height 방 처리 — Manhattan-assumption flag(rough tier)로 충분한가, AtlantaNet-class 또는 multi-view(§C)가 필요한가. silent 사각화 방지 정책.
- **OQ-57**: per-corner 불확실성 도출·교정 방법 — §B 는 rough tier 출력에 per-corner 불확실성을 동반할 것을 예정하나, 스파이크가 산출한 aggregate ~18 cm SHAPE 잔차를 per-corner confidence 로 변환하는 방법이 미정이다(모델 출력에서 직접 얻는가, 경험적 분포에서 얻는가, 별도 교정 셋이 필요한가). blocking gate 또는 rough-tier 수용기준과 연동해야 한다.
- **OQ-58**: cam_h 현장 측정 신뢰성 — 전체 tier-1 스케일 경로가 카메라/삼각대 높이 스칼라 1개에 의존하고, 스파이크는 ±10 cm cam_h 불확실성이 median 오차를 18 cm → 32–38 cm 로 두 배 이상 키움을 보였다(단일-pano 의 지배적 실세계 오차원). 현장 사용자가 필요한 정밀도로 cam_h 를 측정하는 방법, cam_h 를 잘못 추정했을 때의 실패 모드·경고 경로가 미정의이다. rough tier 의 scale-source disclosure(§B) 설계 전에 다뤄야 한다.

---

## §Status-update-2026-06-02 (multi-view 스파이크 → blocking gate #2 부분 충족; header PROPOSED 유지)

**Blocking gate #2(multi-view metric-scale 스파이크, OQ-53)의 scale 하위질문이 PASS 로 닫혔고, ≤15 cm floor-geometry 정확도 하위질문은 FALLBACK 으로 OPEN 유지된다 — 따라서 §C 의 multi-view 1급 경로는 *조건부* 로 진행하되, ADR header 는 PROPOSED 에 머문다(gate #2 의 정확도 절반 미충족 + OQ-52/OQ-54 미해소).** 본 스파이크는 결정 D83 으로 기록되고, repo 밖 throwaway 아티팩트(`/home/seung/mmhoa/spike-vggt-multiview/` — `VERDICT.md`, `vggt_spike_verdict.json`)로 수행되어 repo 는 byte-for-byte 무변경이다.

**스파이크 (수행됨; 사실 기술 — 과거 시제).** VGGT-1B(`facebook/VGGT-1B`, 비상업 research 체크포인트 — feasibility VERDICT 용; 별도의 gated VGGT-1B-Commercial 폼이 존재하나 본 verdict 에 불필요)를 feed-forward 로 돌려 dense pointmap + camera extrinsics(similarity scale)를 얻고, camera-baseline anchor 로 metric scale 을 복원한 뒤 floor-band → concave-hull footprint 를 추출해 GT 와 비교했다. 데이터는 ARKitScenes `raw` Validation split(Apple ML research 라이선스 — research VERDICT 용도)의 **10 개 별개 물리 방, 48 view** 로, 실제 handheld parallax 가 있는 posed RGB + ARKit metric trajectory + 등록된 3DOD room mesh(=floor GT)를 갖춘 **genuine multi-view + metric GT**(semi-synthetic 아님)이다.

**VERDICT = FALLBACK.** 두 하위질문의 결과가 갈린다:

- **Scale 하위질문 (gate #2 의 핵심 risk) = PASS.** Multi-view 는 single-pano 의 단일 cam_h 스칼라가 전체 metric scale 을 좌우하던 single-point-of-failure 를 제거했다(prior 스파이크: ±10 cm cam_h → median corner 18 cm → 32–38 cm). Parallax 로부터 scale 을 직접 복원하여 **median scale error 1.6%, 10 방 중 6 방이 best-fit similarity 대비 5% 이내** 를 순수 camera-baseline anchor 만으로 달성했다. OQ-53 의 scale 하위질문은 이로써 **해소(YES)** 된다.
- **≤15 cm install-grade floor-geometry gate = out-of-the-box FAIL.** Median corner error **22.4 cm**(nv48) / 24.7 cm(nv32); **10 방 중 2 방만 ≤15 cm**, 8/10 ≤30 cm; RoomPlan LiDAR ~8.5 cm baseline 대비 ~2.6×. Median floor-area error 는 **43% undershoot**(방 periphery 의 체계적 under-coverage). 2/10 방(long-thin / low-parallax sweep)은 VGGT pose/baseline degeneracy 를 겪어 1 방이 96.5 cm outlier 였다.

**Root cause = scale 가 아니라 periphery under-coverage.** 지배적 오차원은 sparse handheld sweep 이 far wall/corner 를 under-reconstruct 하는 coverage 문제이며, 스파이크의 naive concave-hull front-end 도 일부 기여한다 — 둘 다 tractable 한 front-end 문제로, **VGGT 의 scale·geometry 능력에 대한 원리적 기각이 아니다**(예: scene 41142278 은 scale error 0.4% / pose RMSE 4 cm 로 거의 완벽하나 4.9×6.9 m floor 중 3.1×5.8 m 만 cover).

**권장 (§C 갱신).**

1. **Gate #2 scale-stability = met** → OQ-53 의 scale 하위질문 RESOLVED 로 표기.
2. **≤15 cm floor-geometry gate = FALLBACK(out-of-the-box)** → VGGT 를 **as-is drop-in install-grade 경로로 ship 하지 않는다**. 동시에 "VGGT 가 불가능하다" 는 결론도 내리지 않는다 — 실패는 coverage/front-end 이지 모델의 scale·geometry 능력이 아니다.
3. **최고가치 다음 실험 = 집중된 floor-extraction front-end 스파이크**(OQ-59 신규): raw concave hull 대신 RANSAC wall-plane corner 추출, coverage-aware capture guidance, multi-view TSDF fusion, 또는 fuller coverage 를 위한 VGGT-Omega 체크포인트.
4. **실용 product call**: image/video → geometry 를 **HONEST metric scale + 가시적 per-corner uncertainty 를 동반한 rough-estimate tier** 로 둔다(single-pano 보다 엄격히 우월 — scale honest, cam_h 추측 불요). ≤15 cm 주장은 LiDAR/RoomPlan 에 유보한다. 이는 본 ADR 의 provenance/honesty framing(measured vs reconstructed vs assumed) 및 OQ-54 와 정합한다.

**Header PROPOSED 유지 근거.** gate #2 의 정확도 절반(≤15 cm)이 미충족이고 blocking gate #1(OQ-52 in-domain 검증)·#3(OQ-54 provenance 스키마)이 미해소이므로, header 를 Accepted 로 전환하지 않는다.

---

## §Status-update-2026-06-04 (OQ-59 front-end 스파이크 → ≤15 cm deployable FALLBACK; header PROPOSED 유지)

**OQ-53/D83 이 최고가치 다음 레버로 지목한 floor-extraction front-end 를 집중 검증한 결과, 배포가능 front-end 그 어느 것도 ≤15 cm install-grade 게이트를 close 하지 못했다 — D83 의 FALLBACK 이 hardens 되며 multi-view 는 first-class ≤15 cm 경로로 승격되지 않고 rough-tier 에 머문다. PRIMARY 가설(RANSAC wall-plane corner)은 기각되고, 다음 레버는 front-end 가 아니라 coverage 임이 확정된다 — 따라서 header 는 PROPOSED 에 머문다(gate #2 정확도 절반 미충족 + OQ-52/OQ-54 미해소).** 본 스파이크는 결정 D84 로 기록되고, repo 밖 throwaway 아티팩트(`/home/seung/mmhoa/spike-vggt-multiview/` — `OQ59_VERDICT.md`, `out/oq59_verdict.json`, `logs/eval_rerun.log`, `scripts/frontends.py`)로 수행되어 repo 는 byte-for-byte 무변경이다.

**스파이크 (수행됨; 사실 기술 — 과거 시제).** OQ-53 과 동일한 캐시 nv48 VGGT 포인트클라우드(ARKitScenes raw Validation 10 방, 48 view, Umeyama-metric, z-up) 위에서 front-end 만 바꿔 동일 `best_fit_2d` metric 으로 재평가했다. Step-1 reproduction gate(캐시가 OQ-53 nv48 baseline 을 재현하는가)는 **PASS — 10 방 전부 delta 0.00 cm**(캐시 byte-faithful, 스파이크 간 silent drift 없음). OQ-53 에서 10/10 OOM-크래시했던 RANSAC 은 repo 밖 `frontends.py` 에서 수정됐다(inlier SVD refit `full_matrices=False` + line-fit 전 ≤100 k pts seeded uniform subsample) — 10 방 전부 ~1–2 s 에 실제 polygon 을 산출했고, 따라서 아래 RANSAC 수치는 진짜 데이터다.

**VERDICT = FALLBACK (hardened).** front-end 레버 질문은 **NO** 로 답해진다(median corner cm / area err% / ≤15 cm):

- `baseline_concave`(control): 22.41 cm / 43.4% / 2-of-10.
- **`convex_band`(최고 배포가능, fixed-param): 17.13 cm / 30.0% / 4-of-10** — 현 concave baseline 대비 실질·무비용 개선(−5 cm median, +2 방)이나 여전히 install-grade FAIL.
- `ransac_walls`(**PRIMARY, fixed-param**): 19.30 cm(no-degen 8 방 18.72) / 26.4% / 2-of-10 — **기각**: trivial convex hull 보다 나쁘고 high-variance(41069048 3.4 cm win / 41159519 105 cm blow-up). per-room bimodal — 단일 고정 파라미터로 두 regime(잘 재구성된 벽 vs partial/parallel 벽)을 straddle 할 수 없어 median 이 parameter-free convex hull 뒤로 처진다.
- `sweep_best`(**ORACLE, 배포 불가**): 11.60 cm / 35.7% / 7-of-10 — concave-hull family 자체에 ≤15 cm 여지가 있음을 증명하나 inference 시점에 없는 per-room GT-tuned 파라미터를 쓰므로 ship 불가(method 아닌 ceiling). degeneracy 방 = 41159503(scale 63% off, front-end 불가복), 41125756(scale 14% off).

**Root cause = corner-fitting 아니라 periphery under-coverage**(OQ-53 에서 이미 isolated). hull family 는 존재하는 점의 경계만 다시 그릴 뿐 missing periphery 를 만들어내지 못하므로, 아무리 영리한 corner geometry 도 ≤15 cm 에 닿지 못한다. 남은 OQ-53 레버(coverage-aware capture / TSDF fusion / VGGT-Omega denser frames)는 모두 *coverage* 를 공략하며 고정 cloud 위 front-end-only 변경이 아니다 — OQ-59 scope 밖, 각각 별도 capture/compute 스파이크다.

**권장 (§C 갱신, D83 FALLBACK 을 hardens).**

1. **OQ-59 front-end 레버 = resolved NO** → multi-view 를 first-class ≤15 cm 경로로 **승격하지 않는다**. image/video → geometry 를 **HONEST metric scale + 가시적 per-corner uncertainty 를 동반한 rough-estimate tier** 로 고정한다. ≤15 cm 주장은 LiDAR/RoomPlan 에 유보.
2. **무비용 in-tier upgrade(게이트 승급 아님)**: 이 경로가 ship 된다면 floor footprint 에 concave baseline 대신 `convex_band` 를 선호하되, **median win 이지 per-room dominance 아님**(3/10 방에서 regress, best-baseline 2 방 포함)이므로 rough-estimate 라벨을 유지한다.
3. **다음 레버 = coverage, corner 아님** → coverage-aware capture / TSDF·VGGT-Omega denser fusion 이 최고가치 잔여 실험이며 각각 별도 스파이크다. install-grade floor 주장이 재우선화되지 않는 한 defer.

**Header PROPOSED 유지 근거.** gate #2 의 정확도 절반(≤15 cm)이 여전히 미충족이고 blocking gate #1(OQ-52 in-domain 검증)·#3(OQ-54 provenance 스키마)이 미해소이므로, header 를 Accepted 로 전환하지 않는다.

---

## §Status-update-2026-06-04b (rough-tier 단일-파노 image backend **구현·출하** v0.25.0; header PROPOSED 유지)

**rough tier(§B)가 in-repo 코드로 구현·출하되었다 — 더 이상 throwaway 스파이크가 아니다.** 단일 equirectangular 파노라마 → RoomModel 캡처 어댑터(`roomestim/adapters/image.py::ImageAdapter`)가 CLI `--backend image`(experimental 하드 게이트) 로 노출되어, v0.25.0 MINOR 로 출하됐다(D86, 빌드 플랜 `.omc/plans/image-backend-single-pano-build.md`). 이는 **rough-estimate tier 한정**이며 install-grade 가 아니다.

**blocking gate 현황 (이 출하 시점):**
- **gate #3 (provenance honesty 스키마, OQ-54) = MET** — room-level `provenance(measured|reconstructed|assumed)` 구현(ADR 0046 / D85). image 출력은 `reconstructed`, 재질 `UNKNOWN`(§E), masquerade 경로 0. Reverse-criterion #4 충족 → image 출력 노출 차단 해제(이 출하의 선결).
- **gate #4 (core/web 경계) = MET** — 모델 의존은 `[vision]` opt-in extra 뒤에만, core torch-free 입증(깨진 canonical torchvision 로 검증). vendored HorizonNet(MIT)·weights 미번들(download-on-first-use).
- **gate #2 (≤15 cm 정확도) = FALLBACK** — multi-view(OQ-53)·front-end(OQ-59) 둘 다 install-grade 미달. 단일-파노 st3d 는 out-of-domain — **현실(사용자 cam_h) median 벽 35–57 cm·≤15 cm 11–17%**(43–45% 는 perfect-scale-anchor 오라클 천장, 추론 시점 불가). cam_h ±10 cm → 32 cm. → rough tier 로 출하, install-grade 승격 안 함.
- **gate #1 (OQ-52 in-domain ckpt) = 미해소** — residential ckpt 접근 불가(ZInD 는 비상업 라이선스, opt-in `--weights zind` 로만). 단일-파노 install-grade 승격 보류.

**Header PROPOSED 유지 근거.** rough tier 는 출하됐으나 ADR 의 install-grade(§C 1급 경로) 절반은 FALLBACK 이고 gate #1·#2 가 미충족이므로, ADR 전체를 Accepted 로 전환하지 않는다. 대신 본 ADR 은 "rough tier = 구현·출하(experimental), install-grade = 미달·보류" 상태다.

**Deferred (정직 기록):** web-tier 이미지 업로드, 실제 per-corner uncertainty(OQ-57 미해결 calibration — 가짜 숫자 금지), per-Surface provenance(OQ-54 잔여), coverage 레버(OQ-59 b/c/d).

---

*본 ADR 의 **rough tier(§B)는 v0.25.0 에서 구현·출하됐다**(experimental `--backend image`, D86/ADR 0046). install-grade 1급 경로(§C)와 multi-view 는 여전히 미구현/FALLBACK 이다(throwaway 스파이크로만 검증). install-grade 승급은 blocking gate #1(OQ-52)·#2(≤15 cm) 충족 후 별도 진행한다.*
