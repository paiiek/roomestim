# ADR 0048 — `auto` floor-reconstruction: convex-preserving disconnected-floater auto-select

- **Date**: 2026-06-12
- **Status**: Accepted (v0.37.0 — opt-in `"auto"` 모드가 구현되었다. 시제는 수행된 사실에 대해 과거형이다. clean 입력은 설계상 convex 와 byte-equal 로 남으며 default 는 여전히 `"convex"` 다.)
- **Deciders**: planner(설계), executor(구현), code-reviewer(honesty 리뷰), verifier(독립 검증)
- **Refs**: 플랜 `.omc/plans/c1-floater-robust-autoselect.md`; 소유 플랜 `.omc/plans/data-unblock-validation-cycle.md` Tier 2 C1; ADR 0042(occupancy/concave floor reconstruction — `auto` 가 재사용하는 추출기); 단일진실원천 disclosure `roomestim/reconstruct/floor_polygon.py::AUTO_FLOOR_RECON_NOTE`.

> **핵심요약**: convex footprint 는 disconnected RGB-D floater 를 통째로 감싸 footprint 를 과대(+~22–40 %)읽는다. `occupancy` 추출기가 이를 고치지만 n=1 증거의 비-default opt-in 이라 clean 입력을 그냥 켜면 byte-equal 회귀가 난다. 본 ADR 은 **convex-preserving auto-select** `"auto"` 를 추가한다: coarse-grid(0.25 m, min_count 1) convex-hull **면적-팽창 신호** φ 가 ≥ 1.10 일 때만 기존 occupancy 추출기로 전환하고, 그렇지 않으면 동일한 convex 경로를 탄다. clean 입력은 단일 coarse-component → φ = 1.0 *정확히* → 발화하지 않음 → `_convex_floor_polygon` 을 같은 vertices 로 호출 → **byte-equal by construction**. connected geometry(through-opening bleed, L-shape)는 단일 component 라 φ = 1.0 → 절대 발화하지 않으므로 **bleed/notch 회복 주장이 구조적으로 불가능**하다.

---

## Context

- convex footprint(default)는 floor-projected vertices 의 convex hull 이라, 방 밖으로 떨어진 **disconnected sparse floater**(RGB-D 재구성 노이즈)를 hull 안에 통째로 삼켜 footprint 를 과대읽는다(Redwood end-to-end 최악 +~22 %, 합성 fixture +~40 %).
- `occupancy` 모드(ADR 0042)는 density + connected-component 전처리로 그 floater 를 제거하지만 (a) n=1 Redwood 증거뿐이고 (b) 비-default opt-in 이며 (c) clean 입력에 켜면 convex 와 byte-equal 이 깨진다(약한 concave 침식).
- V1(3DSES) 검증은 occupancy 가 **DISCONNECTED** floater 는 제거하지만 doorway 등 **connected through-opening bleed** 는 제거하지 못함을 보였다(largest-CC 가 문간으로 연결된 영역을 유지).
- 필요한 것: clean 입력을 절대 회귀시키지 않고 bleed/notch 주장도 하지 않는 **convex-preserving auto-select**.

## Decision

opt-in `"auto"` 모드를 `FloorReconstruction` literal / arg / env / CLI choices 에 추가한다. mesh.py dispatch 는 추출기 블록 앞에서 `"auto"` 를 *effective* 모드로 해소한다:

- `disconnected_floater_phi(vertices)`(`floor_polygon.py`, 순수 함수): floor-projected cloud 를 coarse `_AUTO_DET_CELL_M = 0.25 m` / `_AUTO_DET_MIN_COUNT = 1` 그리드에 rasterize → 8-connected-component label → `φ = convex_hull_area(전체 occupied cell centres) / convex_hull_area(최대 CC cell centres)`. component ≤ 1 또는 임의의 degeneracy → **φ = 1.0**(early return / never-raise).
- `auto_should_use_occupancy(vertices)` = `φ >= _AUTO_FLOATER_PHI_THRESHOLD`(1.10). True → `occupancy` 추출기, False → 동일한 `_convex_floor_polygon(vertices)`.

## Drivers

- **byte-equal-by-construction**: clean 입력은 단일 coarse-component → φ = 1.0 *정확히* → false-fire 불가. 신호는 vertices 를 READ 만 하고(rasterize copy) convex 경로에 넘기는 배열을 변형하지 않는다.
- **harm-weighted single signal**: φ 는 고치려는 정확한 harm(convex-hull 면적 engulfment)을 측정한다. edge fragmentation / non-rect geometry 는 면적을 거의 안 늘리고(early return), distant floater 는 분리거리에 따라 φ 가 커진다(0.5 m → 1.11, 1.0 m → 1.23, 2.0 m → 1.45).
- **safe failure = false-negative**: under-fire(작은/가까운 floater <10 % 팽창)는 convex 유지 = 오늘 동작, 회귀 없음. 위험한 false-positive 는 single-component early return 으로 봉쇄.
- **bleed/non-rect 제외는 tuning 이 아니라 construction**: connected geometry 는 단일 coarse-component → φ = 1.0 → 발화 불가.

## Alternatives considered

- **(a) default 를 occupancy 로 전환** — 기각: clean byte-equal 회귀 + n=1 증거.
- **(b) 0.05 m 추출 그리드에서 면적비 계산** — 기각: clean L-room 이 edge component 로 쪼개져 φ=1.25, density-marginal clean room 이 speckle 로 φ=4661 → false-fire.
- **(c) fraction-of-cells-outside-largest-CC** — 기각: edge-fragment 오염(304 "outside" cells 중 실제 floater 는 ~16), distance/harm-weighted 아님.
- **(d) threshold auto-calibration** — 기각: 존재하지 않는 capability 를 가정하지 않는다.

## Why chosen

coarse single-component early-return 이 clean φ = 1.0 을 *정확히* 만들어 byte-equal 이 tuned 가 아니라 **structural** 이다. θ=1.10 은 합성 fixture 에서 two-sided margin 을 갖는다(clean exact 1.0; fixture 1.3375; @0.5 m boundary 1.1125).

## Consequences

- threshold 는 **합성 fixture 로만 validated**(Redwood 는 설계 근거로 인용, 재취득 아님). real-scan floater GT 가 repo 에 없다.
- scan gap 너머의 **실제 detached 구조물도 동일하게 drop** 된다(disclosed).
- occupancy default `min_count=3` 는 여전히 notch 를 FAIL 한다(re-entrant 회복 없음) — `auto` 도 이를 상속하며 다르게 주장하지 않는다.
- 면적 numbers(합성 fixture, 재현됨): convex floater-cloud **27.99 m² (+39.9 %)** → auto-fired occupancy **19.0075 m² (−5.0 %)**, true 20.0 m². cited Redwood +22 %→+5 % 를 미러링.

## Follow-ups

- real-scan threshold calibration(repo 내 floater GT 필요).
- connected through-opening bleed 는 여전히 미해결(`auto` 범위 밖, 설계상 발화 불가).
