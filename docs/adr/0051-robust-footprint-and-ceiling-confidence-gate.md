# ADR 0051 — `robust` floor-reconstruction (density-percentile boundary trim) + `ceiling_confidence` plane-plausibility gate

- **Date**: 2026-06-23
- **Status**: Accepted (v0.44.0 — 두 변경 모두 구현되었다. 시제는 수행된 사실에 대해 과거형이다. ⓐ `"robust"` 는 비-default opt-in 모드이며 기존 모드/golden 은 byte-equal 로 남는다. ⓑ 는 annotation-only 로 `ceiling_height_m` 을 절대 변경하지 않고 "high"→"low" 강등만 한다.)
- **Deciders**: planner(설계), executor(구현), code-reviewer(honesty 리뷰 APPROVE), 메인(독립 게이트 검증)
- **Refs**: 플랜 `.omc/plans/robust-footprint-and-ceiling-confidence-fix.md`; ADR 0048(`auto` floater select — 동일 footprint 계보), ADR 0042(occupancy/concave 추출기 — `robust` 가 재사용), D96(ceiling_coverage/ceiling_confidence HEURISTIC 도입); 단일진실원천 `roomestim/reconstruct/floor_polygon.py::floor_polygon_robust`, `roomestim/adapters/mesh.py::_CEILING_PLAUSIBLE_MIN_M`. 검증 근거: `scrream-gt/` n=1 SCRREAM noise-sweep(on-disk, [[project_a1_tsdf_negative_scrream_validation]]).

> **핵심요약**: SCRREAM known-extrinsic 완전-방 GT 에 vertex noise 를 주입한 n=1 스윕에서 두 결함이 드러났다. (ⓐ) concave-hull footprint 가 noise 에 단조 과대(+19.4 %@5 cm, +39 %@10 cm)이고, (ⓑ) 극단 noise 에서 ceiling height 가 implausible 하게 collapse(1.34 m vs true 2.58 m)하는데도 `ceiling_confidence` 가 `ceiling_coverage>=0.50` 에만 키잉되어 "high" 를 거짓 보고했다. 본 ADR 은 두 개의 **독립·additive** MeshAdapter 변경을 추가한다.

---

## Context

`scrream-gt/scrream_seg_frontend_proto.py` 의 검증된 n=1 noise-sweep 가 두 가지 측정된 결함을 노출했다(허위수치 아님, on-disk SCRREAM GT 로 end-to-end 측정):

- **footprint over-estimate**: vertex noise 가 concave-hull 경계 면적을 단조 팽창시킨다 — +19.4 %@σ=5 cm, +39 %@σ=10 cm. 경계 "flyer" 는 floor band 의 다른 점들보다 kNN 밀도가 희박하다.
- **ceiling collapse + false-high**: 극단 noise 에서 robust ceiling plane 이 1.34 m(true 2.58 m)로 collapse 하지만, wrong-but-dense 한 저평면이 footprint 를 채워 `ceiling_coverage` 는 여전히 높다 → coverage 단독 키잉인 `ceiling_confidence` 가 "high" 를 거짓 보고한다.

## Decision

### ⓐ `floor_reconstruction="robust"` — density-percentile boundary trim (Primitive-A)
`floor_polygon_robust()` 를 추가한다: floor band(하단 ~15 cm)에서 kNN 평균거리(`cKDTree`, k=12)가 큰 상위 `drop_pct`(=8 %) 희박-경계 flyer 를 concave hull 이전에 제거한다. 검증 스윕에서 과대추정을 대략 반감(+19.4 %→+8.3 %@5 cm, +39 %→+12 %@10 cm)했고 **clean 입력에서는 불변**이다. 제거 후 점들은 기존 concave 경로(`floor_polygon_from_mesh`, synth-(N,3) 트릭, ADR 0042 occupancy 와 동일)로 흘려 모든 guard/`simplify`/`is_simple_polygon`/`canonicalize_ccw` 를 상속한다. **결정론적**(RNG 없음, `cKDTree.query`/`np.percentile` 순서무관, `<=` tie 결정론). scipy 는 이미 hard dep(`scipy.spatial.cKDTree`) — 신규 의존성 없음.

`auto` 는 절대 `robust` 로 해석되지 않는다(occupancy/convex 만). `robust` 는 생성자 인자 / `--floor-reconstruction robust` / `ROOMESTIM_MESH_FLOOR_RECON=robust` 로만 도달 가능하다. dispatch 는 `{"concave":…, "occupancy":…, "robust":…}[recon]` dict 로 리팩터되었고 concave/occupancy 매핑은 이전과 동일 → **byte-equal by construction**. ValueError → convex 폴백 + `UserWarning` 은 동일 경로 유지.

### ⓑ `ceiling_confidence` plane-plausibility gate (annotation-only)
`_classify_ceiling_confidence(coverage, ceiling_height_m=None)` 가 선택적 height 인자를 받는다. `"high"` 는 이제 `coverage >= _CEILING_COVERAGE_MIN` **AND** plausible height(`ceiling_height_m is None` — gate 스킵, back-compat — 또는 `_CEILING_PLAUSIBLE_MIN_M(1.8 m) <= h <= _MAX_CEILING_HEIGHT_M`)를 모두 요구한다. "high" 출력 집합이 기존(coverage 단독)의 **strict subset** 이므로 gate 는 오직 high→low 강등만 하고 절대 승격하지 않는다. `ceiling_height_m` 은 **read-only — 추출 height 를 절대 변경하지 않는다**. 1.8 m 는 보수적 HEURISTIC(미보정): shoebox 2.5 m·실 ARKit robust ceiling ~2.24 m 아래, 검증된 1.34 m collapse 위 — `CEILING_CONFIDENCE_HEURISTIC_NOTE` 와 일관.

## Consequences

- **Positive**: noise-robust footprint opt-in 확보(검증된 과대추정 반감); collapsed-ceiling 의 false-high 가 정직히 강등됨. 둘 다 honesty-디스클로즈(n=1 SCRREAM, "UNVALIDATED on real room scans", "NOT an accuracy guarantee", "HEURISTIC, NOT calibrated").
- **Neutral/byte-equal**: default(`convex`) 및 기존 모든 모드/golden byte-identical(green 695p/7s, 0 regression 으로 확증); schema_version 불변; 신규 의존성 0.
- **Negative/한계**: `robust` 정확도는 n=1 SCRREAM 으로만 검증 — 실 room scan 미검증. Primitive-B(through-opening/room-segmentation leakage)는 design-only 미선적(GT 부재). 1.8 m 미만 실제 저층고 방은 보수적으로 "low" 강등(under-claim, 절대 false-high 아님 — 안전한 실패 방향).

## Verification
default 695p/7s(686→+9 신규 테스트, 0 regression), web 86p/3s, ruff clean, mypy clean. code-review APPROVE(CRITICAL/HIGH 0, LOW 3 non-blocking). 신규 테스트는 방향/부등식만 단언(n=1 퍼센트 하드코딩 없음).
