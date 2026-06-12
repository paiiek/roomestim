# ADR 0040 — Polygon / 비-직각(non-rectilinear) ISM RT60 예측 설계

- **Status**: PROPOSED (draft — 미구현; 본 문서는 설계 제안이며 코드/테스트는 아직 존재하지 않음). **REVISED 2026-05-29 — critic 리뷰(1 CRITICAL + 3 MAJOR) 반영: §F coupled-space marker 부재 정정, §G 순환검증 제거, §B per-band 매핑·pra-fit 신뢰성 명시, §I PR1 스파이크 게이트 + PR2 시그니처 불일치 + PR3 OQ-23 재기재.**
- **Date**: 2026-05-29
- **Deciders**: architect (설계), critic (리뷰 완료: REVISE→반영), planner (확정 예정)
- **Predecessor**: ADR 0028 (ISM 라이브러리 채택 — shoebox 전용 landing), ADR 0030 (predictor-default switch — shoebox=ISM / non-shoebox=Eyring cascade + §Reverse-criterion item 3 "polygon ISM landing → Eyring fallback 을 polygon ISM 으로 승격")
- **Cross-ref**: ADR 0014 (Building_Lobby coupled-space 제외), ADR 0024 (web-demo 별도 패키지), ADR 0037 (wall-index 단일 frame), D26 (forbidden-indefinite-deferral), D29 (parallel-track / web↔core 레인 분리), OQ-9 (Building_Lobby EXCLUDE), OQ-13b/OQ-15 (glass-heavy conference Sabine 발산), OQ-23 (Polygon ISM deferral), OQ-30 (per-wall α decomposition)

> **핵심요약 (권장안)**: pyroomacoustics 의 polygon ISM(`pra.Room.from_corners(...).extrude(...)` + RT60 추정)을
> core 로 끌어올려 비-shoebox 전용 `roomestim/reconstruct/polygon_image_source.py` sibling 모듈로 래핑하고,
> predictor cascade 의 중간 티어로 끼우는 방안(선택지 b)을 권장한다. 자체 polygon mirror-image bookkeeping
> 신규 구현(선택지 a)은 RT60 ±20% 목표 대비 ROI 가 낮다. 단 pyroomacoustics 가 현재 web-extra 이므로
> **D29 web↔core 레인 분리**를 어떻게 다룰지(§C)가 본 ADR 의 핵심 미결 결정이다.

---

## Context

### 현 상태 (검증된 사실)

ISM RT60 예측기는 **shoebox 전용**이다. `roomestim/reconstruct/image_source.py` (622 LoC) 의 핵심 함수 `_ism_rt60_core` (line 164) 는 image-source 격자를 정수 lattice index `(nx, ny, nz)` + parity `(qx, qy, qz)` 로 enumerate 하는데, 이 스킴은 **6 개 축정렬 평면의 직각 mirror** 에 hard-coded 되어 있다:

- 입력은 `(L, W, H)` 3-tuple 차원 + 6-tuple surface area/α (line 432-440); surface index convention 이 `(floor, ceiling, wall_xneg, wall_xpos, wall_yneg, wall_ypos)` 로 LOCKED (line 85-102).
- image 위치 계산 `img_x = (1-2qx)*sx + 2*nx*L` (line 316) 과 bounce-count `n_xneg=|nx-qx|` (line 317) 는 **벽이 x=0, x=L 에 평행하다는 가정에 전적으로 의존**한다. 비-직각 벽에는 적용 불가능하다.
- 즉 image_source.py 는 polygon 으로의 점진적 확장 여지가 거의 없다 — lattice 스킴 자체가 shoebox 가정의 산물이다.

비-shoebox 방은 `predict_rt60_default` (`predictor.py:453`) 에서 `is_rectilinear_shoebox(room)` (line 97) 이 False 를 반환하면 **Eyring 으로 silently route** 된다 (line 509, rationale `"non-shoebox or prefer_ism=False: Eyring fallback"`). `is_rectilinear_shoebox` 의 판정은 "floor_polygon 이 정확히 4 정점 + unique x 2개 + unique z 2개" 이며, 회전된 사각형·L자형·5각형 이상은 모두 탈락한다.

### Eyring fallback 이 부정확한 지점

ADR 0028 §Decision 2 가 기록한 발산 신호가 그대로 적용된다: glass-heavy 방에서 specular grazing reflection 이 late-decay tail 을 지배하는데, Eyring 의 diffuse-field 가정은 이를 평균해 없앤다. 측정 비율:
- Conference (glass 1면 + drywall 3면): ISM/Sabine = 5.05, ISM/Eyring = 5.70 (ADR 0028 line 120).
- Office_1: ISM/Sabine = 2.01 (line 132).

비-shoebox glass-heavy 방(예: 비직각 conference, 경사벽 atrium)은 **specular 발산 신호 + 비직각 geometry** 를 동시에 갖는다. 현재는 이런 방이 Eyring 으로 빠지므로 ADR 0028 이 식별한 5× 발산을 그대로 다시 떠안는다. OQ-23 의 트리거 조건("non-shoebox in-situ capture landing 또는 non-shoebox ACE room 재도입")이 충족되면 이 부정확성이 사용자에게 노출된다.

### 결정적 발견 — polygon ISM 경로가 이미 web 에 존재한다

`roomestim_web/binaural.py:143-170` `_build_extrusion_room` 은 비-shoebox 방을 `pra.Room.from_corners(corners_xz).extrude(height)` 로 구성하고, binaural 렌더용 ISM RIR 을 이미 산출하고 있다 (line 230-233: shoebox→`_build_shoebox_room`, else→`_build_extrusion_room`). 즉 **임의 prismatic polygon 방에 대한 ISM 반사 bookkeeping·visibility test·image pruning 은 pyroomacoustics 가 이미 검증된 형태로 제공**하며, 이 repo 안에서 이미 호출되고 있다. 다만:
- 이 경로는 RIR(오디오)을 만들 뿐 **RT60 숫자를 predictor 로 환류시키지 않는다**.
- `pyroomacoustics` 는 **web optional-extra** (`pyproject.toml:39`) 이고, `predictor.py` 는 **core 모듈**(docstring line 20: "this module is core (no web dependency)") 이다. 이것이 통합의 핵심 제약이다.
- `is_rectilinear_shoebox` 판정이 core(`predictor.py:97`)와 web(`binaural.py:97`)에 **중복** 정의돼 있다.

---

## Decision (제안)

### A. 알고리즘 선택지 비교

| 선택지 | 구현복잡도 | 정확도 (±20% 대비) | shoebox 경로 통합성 | core-순수성(no web dep) |
|--------|-----------|-------------------|--------------------|------------------------|
| (a) 자체 polygon mirror-ISM 신규 구현 — 각 벽 평면 mirror + visibility/validity test + image pruning + EDC 적분 | 높음 (~400-600 LoC + 검증부담; 비볼록·visibility 버그 위험) | 충분하나 새 버그 표면; ±20% 달성에 과잉 | 신규 코드라 통합부담 큼 | 유지 (numpy-only 가능) |
| (b) pyroomacoustics 재사용 (`from_corners`+`extrude`+RT60 추정 또는 EDC 직접 fit) | 낮음 (~80-150 LoC wrapper; binaural.py 패턴 재사용) | 충분 (검증된 라이브러리; web 에서 이미 가동 중) | sibling 모듈로 깔끔히 분리 | **위반 위험** (pyroomacoustics 는 현재 web-extra) |
| (c) hybrid ISM(저차) + ray(고차) | 매우 높음 | ±20% 목표에 과잉 (BIM precision 아님) | 복잡 | pyroomacoustics ray 또는 자체구현 |

근거: 정밀도 목표가 RT60 ±20% 이고 "캡처 노이즈가 dominant error" 이므로, 물리정확도 최대화(선택지 c)나 신규 검증부담(선택지 a)은 ROI 미달이다. 선택지 (b)는 이미 repo 안에서 동일 알고리즘이 비-shoebox 방에 가동 중이라는 점에서 위험이 가장 낮다.

### B. 권장안 — 선택지 (b), core 로 끌어올린 pyroomacoustics wrapper

신규 sibling 모듈 `roomestim/reconstruct/polygon_image_source.py` (제안) 를 추가한다:

- 공개 API 제안 (image_source.py 와 parity):
  - `polygon_image_source_rt60(floor_polygon_xz, ceiling_height_m, surfaces, *, max_order, sound_speed_m_s) -> float`
  - `polygon_image_source_rt60_per_band(...) -> dict[int, float]`
- 내부 구현: `pra.Room.from_corners(...).extrude(...)` → image-source 모델 실행 → `pra.experimental.measure_rt60` 또는 EDC Schroeder fit (image_source.py 의 T30→T20→T10 cascade 와 동일 정책 재현).
- **per-band 매핑 규약 (critic MAJOR 반영)**: pyroomacoustics 는 8-band damping 을 기본으로 쓸 수 있다(binaural.py:84 주석이 명시; binaural.py:48 center_freqs `[125,250,500,1000,2000,4000]`). polygon per-band RT60 은 반드시 roomestim 의 **6-band octave 규약(125/250/500/1k/2k/4k)** 으로 정렬해 반환해야 한다 — 그렇지 않으면 기존 6-band 소비자(report/chart)와 깨진다. `binaural.py:80-94 _resolve_damping_scalar` 의 8→scalar collapse 로직을 참조하되, RT60 경로는 collapse 가 아니라 **band-격자 정렬(pra band → roomestim 6-band)** 이 필요하다. 일부 band 만 fit 실패 시의 부분-실패 처리도 PR1 에서 규약화. 단일밴드/per-band 가 같은 band 격자를 쓰도록 강제.
- **pra RT60 fit 신뢰성은 미검증 (critic MAJOR)**: `measure_rt60` 는 RIR 에 Schroeder 적분을 적용하는데, ISM-only RIR 은 late tail 이 sparse/discrete 해 EDC 가 계단형이 되고 T30 fit 이 불안정할 수 있다. binaural.py 의 기존 polygon 경로는 **오디오 렌더용**이라 RT60 fit 정확도는 검증된 적이 없다. 따라서 §I PR1 의 degenerate-shoebox 일치 스파이크를 통과하기 전엔 cascade(PR3) 연결을 금지한다.
- **image_source.py 는 손대지 않는다** (shoebox 경로 byte-equal 회귀 0 보장). lattice 스킴은 shoebox 가정 산물이므로 확장이 아닌 sibling 분리가 올바른 경계.

### C. pyroomacoustics 의 core vs web 레인 결정 (D29 — 미결정, planner 확정 필요)

본 ADR 의 **가장 중요한 미결 결정**이다. 세 옵션:

- **C1. pyroomacoustics 를 core 의존성으로 승격** — `predict_rt60_default` 가 직접 호출. 가장 단순하나 D29 web↔core 레인 분리와 정면 충돌하고, core install 무게가 늘어난다.
- **C2. lazy import + graceful fallback (권장 후보)** — `polygon_image_source.py` 가 pyroomacoustics 를 함수 내부에서 lazy import; `ImportError` 시 predictor 는 Eyring 으로 fallback (rationale 에 "pyroomacoustics 미설치 → Eyring" 기록). pyroomacoustics 는 web-extra 로 유지. core 순수성 보존 + polygon ISM 은 web/extra 환경에서만 활성. 단 동일 방이 환경에 따라 다른 숫자를 내는 **재현성 비대칭**이 tradeoff.
- **C3. polygon ISM 을 web 레인에 두고 core 는 영구히 Eyring** — D29 가장 충실하나 ADR 0030 §Reverse-criterion item 3 ("polygon ISM landing → predict_rt60_default 승격")을 충족하지 못한다.

권장: **C2**. ADR 0030 reverse-criterion 충족(predictor cascade 가 polygon ISM 을 사용)과 D29 레인 분리(pyroomacoustics 가 core 강제 의존이 되지 않음)를 동시에 만족하는 유일한 옵션.

### D. predictor cascade 통합 (제안)

`predict_rt60_default` / `_per_band` 의 분기 (현 `predictor.py:453` / `:528`) 를 3-티어로 확장:

1. `is_rectilinear_shoebox(room)` 이면 → 기존 custom shoebox ISM (현행 유지, byte-equal).
2. else if `is_prismatic_polygon(room)` (신규 predicate 제안: floor_polygon 이 simple non-self-intersecting + ceiling_height 일정 + coupled-space 아님) 이면 → `polygon_image_source_rt60(...)` (lazy-import; 실패 시 3 으로 fallback).
3. else (coupled-space 또는 polygon ISM 사용 불가/예외) → Eyring (현행 유지).

분기점 추가 위치: `predictor.py:453` 의 `if prefer_ism and is_rectilinear_shoebox(room):` 직후 `elif prefer_ism and is_prismatic_polygon(room):` 블록. `RT60Prediction.predictor_name` Literal 에 `"polygon_image_source"` 추가, `PredictorName` 타입(line 56) 확장 제안.

**`is_rectilinear_shoebox` 중복 제거 제안**: core(`predictor.py:97`)와 web(`binaural.py:97`)의 중복 판정을 core 단일 authority 로 통합하고 web 이 import (ADR 0037 의 wall-index 단일-frame 정신과 정합). web→core import 만 허용하는 현 레이어링과 일치한다.

### E. ADR 0030 §Reverse-criterion item 3 충족 방식

item 3 은 "polygon ISM lands → `predict_rt60_default` §A item 2(Eyring fallback)를 polygon ISM fallback 으로 승격 + §Status-update append" 를 요구한다. 본 설계의 §D 3-티어 cascade 가 정확히 이를 구현한다: 비-shoebox prismatic 방의 1차 예측기가 Eyring 에서 polygon ISM 으로 승격되고, Eyring 은 coupled-space/예외 시의 최종 fallback 으로 강등된다. 구현 PR 착수 시 ADR 0030 에 §Status-update 블록 append 예정.

### F. coupled-space (Building_Lobby) 처리

> **정정 (critic CRITICAL 반영)**: 초안은 "`is_prismatic_polygon` 이 coupled-space 마커로 Building_Lobby 를 티어 3(Eyring)으로 보낸다"고 적었으나 이는 **사실과 다르다**. (1) `RoomModel` 에는 coupled-space 마커 필드가 **존재하지 않는다** (`grep coupled roomestim/model.py` = 0건; 마커는 `ace_challenge.py` 주석/`_FURNITURE_BY_ROOM` 에만 있고 predictor 는 이를 참조하지 않음). (2) `ACE_ROOM_GEOMETRY["Building_Lobby"]` 는 `L=5.13, W=4.47, H=3.18` 의 **4정점 축정렬 shoebox 로 저장**되어(ace_challenge.py:149-156) `is_rectilinear_shoebox==True` → **티어 1(shoebox ISM)** 으로 라우팅된다. 즉 현재 Building_Lobby 는 polygon 경로를 애초에 거치지 않는다.

따라서 본 ADR 의 정확한 입장:
- 현재 Building_Lobby 는 shoebox 저장형이라 티어 1 로 가며 polygon ISM 경로와 무관하다 (OQ-9 EXCLUDE 는 furniture-budget 차원 결정이지 geometry 차원이 아님).
- **coupled-space 를 안전하게 배제하는 predicate 는 현재 존재하지 않는다.** 진짜 coupled-space 가 non-shoebox geometry(예: in-situ capture 된 L자 lobby)로 들어오면 §D 티어 2(polygon ISM)로 직행하며, 본 설계는 그것을 막지 못한다 (이전 R4 가 막겠다던 시나리오가 실제로는 무방비).
- 이를 실제로 보장하려면 **별도 작업이 필요**하다: `RoomModel` 에 `coupled_space: bool` (또는 유사) 마커 필드 추가 + adapter 가 set + `is_prismatic_polygon` 이 이를 False 조건으로 사용. 이 marker 도입은 본 ADR scope 밖이며 신규 OQ(§OQ 갱신)로 추적한다. marker 도입 전까지는 "non-shoebox coupled-space 입력은 현재 미보호"임을 솔직히 명시한다.

### G. 검증 전략 (제안 — critic MAJOR 반영, 순환 검증 제거)

> **검증 정직성 재정의**: ACE GT T60(`_load_t60_per_band`, ace_challenge.py:730)는 **실제 shoebox 방의 측정값**이다. 그 방을 "벽 1면 회전/5각형 합성 변형"하면 더 이상 GT 와 같은 방이 아니므로 GT 비교가 무의미해진다. 따라서 합성-변형 fixture 의 "측정 GT ±20%" 주장은 **공허하며 폐기**한다. polygon ISM 의 절대정확도(vs 현실 ±20%)는 진짜 non-shoebox 측정 코퍼스가 확보되기 전엔 입증 불가임을 명시하고, 별도 OQ 로 분리한다.

검증은 입증 가능한 것만 게이트로 삼는다:

1. **(1차 게이트) degenerate-consistency**: shoebox 방을 `from_corners` 의 4정점 사각형 polygon 으로 표현해 polygon ISM 경로로 돌린 RT60 이, 동일 방의 custom shoebox ISM(`image_source_rt60`) RT60 과 ±X%(목표 ±10%) 이내로 수렴하는지. 두 경로(닫힌형 EDC 적분 vs pra RIR→Schroeder fit)는 알고리즘 클래스가 다르므로 이 일치는 자명하지 않다 — pra 경로의 RT60 추정 신뢰성을 처음으로 입증하는 핵심 게이트. (§I PR1 스파이크와 동일.)
2. **(상대비교) glass-heavy 방향성**: OQ-13b conference(shoebox, ISM/Sabine=5.05)에서 ISM 이 이미 측정에 근접함이 ADR 0028 에 기록됨. 비-shoebox 변형에서 polygon ISM 이 Eyring 보다 shoebox-ISM baseline 에 가까운 방향인지를 **방향성 신호(절대 ±20% 아님)** 로만 확인. vanity metric 으로 오인하지 않도록 "절대정확도 미입증" 라벨을 결과에 부착.
3. **shoebox 회귀 0 보장**: image_source.py 미변경 → `tests/test_image_source.py` 전체 PASS. `is_rectilinear_shoebox=True` 방의 `predict_rt60_default` 출력이 비트단위 불변임을 회귀 테스트로 고정.
4. **runtime invariant**: `polygon_ism_rt60 ≥ eyring_rt60 - 1e-6` 가 pra 결과에도 성립하는지 PR1 스파이크에서 **실측 확인 후** 게이트화(미성립 시 invariant 를 polygon 경로엔 적용 안 함으로 후퇴).
5. **lazy-import fallback**: pyroomacoustics 부재(default CI lane)에서 비-shoebox 방이 Eyring 으로 graceful fallback + rationale 문자열 정확 기록.
6. **non-convex 처리**: `from_corners` 가 비볼록 polygon 도 받지만 ISM visibility test 가 spurious/missing image 를 낼 수 있다. binaural.py:70-77 `_image_inside_floor`(shapely `contains` 수동 visibility 보강)가 이미 존재한다 — polygon RT60 경로가 이 보강을 재사용해야 하는지 PR1 에서 결정 + 비볼록 fixture 로 회귀 고정.

진짜 non-shoebox 측정 GT 코퍼스 확보는 신규 OQ 로 추적(§OQ).

### H. Scope / Non-goals

- **In scope**: 단일 prismatic(extruded-polygon) 방의 RT60 ISM 예측; predictor cascade 통합; lazy-import fallback.
- **Non-goals**: coupled-space ISM (OQ-9 EXCLUDE 유지); 비-prismatic(경사 천장/다층) geometry; per-wall α 정밀 decomposition (OQ-30 별도); ray-tracing 고차 hybrid (선택지 c, ROI 미달); 자체 polygon mirror-ISM 구현 (선택지 a).

### I. 단계적 구현 순서 (제안 PR 분할)

- **PR1**: `polygon_image_source.py` sibling 모듈 + lazy-import wrapper + 단위 테스트 (predictor 미연결; pyroomacoustics extra 환경에서만 활성). image_source.py·predictor.py 무변경 → 회귀 0. **반드시 포함하는 게이트 스파이크**: (i) degenerate-shoebox 일치 — 4정점 사각형 polygon RT60 ≈ custom shoebox ISM RT60(±10%); (ii) per-band band-격자 정렬 검증; (iii) `polygon_ism ≥ eyring` invariant 실측; (iv) 비볼록 polygon visibility 처리(`_image_inside_floor` 재사용 여부) 결정. **이 스파이크 통과 전 PR3 금지.**
- **PR2**: `is_prismatic_polygon` predicate (core) + `is_rectilinear_shoebox` 중복 제거(web→core import). 순수 predicate, predictor 분기 미변경. **주의 (critic 지적)**: web `_is_rectilinear_shoebox`(binaural.py:97)는 `Sequence[Point2]` 를, core(predictor.py:97)는 `RoomModel` 을 받는다 — 시그니처 불일치라 단순 import 치환 불가. adapter 함수 또는 시그니처 정렬을 PR2 에 명시 포함.
- **PR3**: `predict_rt60_default` / `_per_band` 3-티어 cascade 연결 + `PredictorName` 확장 + ADR 0030 §Status-update append + OQ-23 상태 갱신. **주의**: OQ-23 은 v0.14.0 NEW 로 실재하나 현재 `open-questions.md` 에는 부재(curated subset; OQ-23/OQ-41 등 누락)다 — PR3 는 OQ-23 entry 를 open-questions.md 에 먼저 재기재한 뒤 상태 갱신.
- **PR4**: §G 검증(degenerate-consistency 게이트 + glass-heavy 방향성 비교 + shoebox 회귀 lock + lazy-import fallback). 절대 ±20% 주장 금지(미입증 라벨 유지).

### J. 리스크

- **R1 (D29 레인 위반)**: pyroomacoustics 의존이 core 로 새어들 위험. → §C2 lazy-import 로 완화; core 강제 의존 금지.
- **R2 (재현성 비대칭)**: web-extra 유무에 따라 동일 방이 polygon ISM vs Eyring 으로 갈림. → rationale 에 명시 기록 + default CI 는 Eyring 경로를 게이트로 고정.
- **R3 (pyroomacoustics 버전 드리프트)**: OQ-19(binaural WAV byte-exact reproducibility) 와 동일 클래스 리스크. → RT60 은 ±20% 목표라 byte-exact 불요; 버전 floor `>=0.7` 유지.
- **R4 (coupled-space 오분류)**: prismatic predicate 가 coupled-space 를 polygon ISM 으로 잘못 보낼 위험. → **현재 무방비** (§F 정정 참조: coupled-space 마커가 존재하지 않음). 현 Building_Lobby 는 shoebox 저장형이라 티어 1 로 빠져 우연히 안전하나, non-shoebox coupled capture 가 landing 하면 보호 없음. mitigation 은 `RoomModel` 에 coupled-space 마커 도입(본 ADR scope 밖, 신규 OQ) 이며 그 전까지는 "미보호"를 솔직히 명시.

---

## Consequences (제안 시점 예측)

- (+) 비-shoebox glass-heavy 방이 Eyring(발산)대신 polygon ISM 으로 1차 예측 → ADR 0028 이 식별한 5× 발산 완화 예상.
- (+) ADR 0030 §Reverse-criterion item 3 충족 → OQ-23 closure 경로 확보.
- (+) image_source.py 무변경 → shoebox 경로 byte-equal 회귀 0.
- (+) 이미 web 에서 검증·가동 중인 pyroomacoustics 경로 재사용 → 신규 검증부담 최소.
- (−) core 가 polygon ISM 을 web-extra(pyroomacoustics) 존재 여부에 의존 → 환경별 재현성 비대칭 (lazy-import fallback 으로 완화하나 잔존).
- (−) D29 레인 분리에 압력 — pyroomacoustics 가 core 코드 경로에서 호출됨(설치는 web-extra 유지하더라도 import 지점이 core 로 이동). planner/critic 의 명시 승인 필요.
- (−) coupled-space 는 여전히 EXCLUDE — Building_Lobby 류는 개선 없음.

## Reverse-criterion (제안)

1. **pyroomacoustics 의 core lazy-import 가 default CI 무게/안정성을 해친다** — §C2 를 §C3(web 전용 polygon ISM)로 후퇴; predictor 는 비-shoebox 에서 Eyring 유지. 후속 ADR 로 기록.
2. **polygon ISM RT60 이 측정 GT 대비 ±20% 를 못 맞춘다 (특히 비볼록/coupled 근접)** — fixture 검증에서 발견 시 해당 geometry class 를 prismatic predicate 에서 제외(티어 3 fallback) + 신규 OQ 로 추적.
3. **자체 polygon mirror-ISM 구현 요구가 등장 (의존성 제거·라이선스·재현성 사유)** — 선택지 (a)로 전환; 본 ADR 을 후속 ADR 로 supersede + image_source.py 의 EDC fit 정책 재사용.
4. **coupled-space in-situ capture 가 landing** — coupled-space ISM 별도 ADR 착수 (OQ-9 EXCLUDE 재평가); 본 ADR 의 prismatic-only scope 유지.

## References

- `roomestim/reconstruct/image_source.py:85-102, 164, 316-326, 432-440` — shoebox lattice 스킴이 6 축정렬 평면에 hard-coded; polygon 확장 불가 근거.
- `roomestim/reconstruct/predictor.py:97, 453, 509, 528` — `is_rectilinear_shoebox` predicate + cascade 분기점 + non-shoebox→Eyring silent route.
- `roomestim_web/binaural.py:97, 143-170, 230-233` — 이미 존재하는 polygon-ISM 경로(`pra.Room.from_corners().extrude()`) + 중복된 `_is_rectilinear_shoebox`.
- `roomestim/geom/polygon.py:66-86` — `room_volume`(prismatic 가정) + simple-polygon 제약(self-intersecting 미지원).
- `roomestim/model.py:142-154, 274-284` — Surface/RoomModel/floor_polygon 표현(임의 polygon floor 이미 가능; 벽은 vertical rectangle).
- `roomestim/adapters/ace_challenge.py:89-91, 238-240, 730` — Building_Lobby coupled-space 기술 + ACE GT T60 로더.
- `pyproject.toml:39` — pyroomacoustics 는 web optional-extra (core 의존 아님) — §C 레인 결정의 핵심 제약.
- ADR 0028 §Decision 2 — glass-heavy ISM/Sabine 발산 측정값.
- ADR 0030 §Reverse-criterion item 3 — 충족 대상 criterion.
- OQ-9, OQ-13b, OQ-15, OQ-23, OQ-30 (`.omc/plans/open-questions.md`).

---

## §OQ / decisions 갱신 제안

- **OQ-23 (Polygon ISM)**: deferred → 본 ADR 0040 확정 시 "설계 완료, 구현 deferred (PR1-4 제안)" 로 갱신; 구현 PR3 landing 시 CLOSED. **단 OQ-23 은 현재 open-questions.md 에 부재(curated subset)** 이므로 갱신 전 entry 재기재 필요(§I PR3).
- **OQ-13b/OQ-15 연결**: polygon ISM 검증이 비-shoebox glass-heavy 방에서 방향성 개선을 확인하면 OQ-13b 가설에 비-shoebox 데이터포인트 추가(절대정확도 아닌 방향성). OQ-15 는 이미 CLOSED(ADR 0028) → status-update 만.
- **신규 OQ 제안 #1 (coupled-space marker)**: `RoomModel` 에 coupled-space 마커 필드 도입 — §F 정정이 드러낸 무방비 해소용. coupled-space in-situ capture landing 시 트리거.
- **신규 OQ 제안 #2 (non-shoebox 측정 GT 코퍼스)**: polygon ISM 의 절대 ±20% 정확도 입증용 비-shoebox 측정 RIR 코퍼스 확보 — §G 가 합성-변형 GT 의 공허함을 인정한 후속.
- **신규 OQ 제안 #3 (pra RT60 fit 신뢰성)**: sparse ISM-only RIR 에서 `measure_rt60` Schroeder fit 의 결정성/안정성 — §I PR1 스파이크로 1차 답하되 광범위 검증은 OQ 로.
- **신규 OQ 제안 #4 (lazy-import 재현성 비대칭)**: §C2 채택 시 web-extra 유무에 따른 환경별 예측기 분기 추적.
- **신규 D 제안**: "polygon ISM 은 pyroomacoustics 재사용(선택지 b) + core lazy-import(§C2); 자체 mirror-ISM(선택지 a)은 §Reverse item 3 까지 미구현" 결정 기록.

---

> **honesty note (REVISED 2026-06-08, §Status-update 참조)**: 본 문서의 RT60 cascade·`is_prismatic_polygon`·predictor 통합 항목은 여전히 **제안/예정(DEFERRED)**이다. 단 §Status-update 가 기록하듯 **geometry-only 부분(image-source POSITION + visibility enumerator)은 v0.31.0 에서 LANDED** 되었다. `roomestim_web/binaural.py` 의 `_build_extrusion_room` polygon 경로(binaural RIR 용)는 변함없이 별개다.

---

## Status-update (2026-06-08, v0.31.0 — D100)

**Geometry-only enumerator LANDED; RT60 cascade DEFERRED.**

### LANDED (geometry only, in-gate verified)
- 신규 core 모듈 `roomestim/reconstruct/polygon_image_source.py` (numpy/shapely-only, **pyroomacoustics import 없음** → default gate lane 에서 실행). 공개 API:
  `first_order_image_sources(floor_polygon, ceiling_height_m, source, *, include_floor_ceiling=True, tol_m=1e-9) -> list[ImageSource]`.
  extruded simple polygon (floor_polygon=xz 평면 + ceiling_height_m=수직 extrude) 에 대해 source 를 각 벽 평면(+옵션 floor/ceiling 평면)에 mirror 한 **1차 image-source POSITION** 을 enumerate 하고, 각 image 에 shapely 기반 visibility flag(`valid`)·생성 surface(`wall_index`)·`reflection_point` 를 부착해 반환한다. 이것이 §A 선택지 (a)를 **geometry 로만 엄격히 축소**한 것(±400-600 LoC RT60 mirror-ISM 전체가 아닌 positions+visibility 만).
- visibility test (결정적, shapely): 벽 image 는 source 에서 벽 supporting line 으로 내린 수선의 발(specular reflection point)이 **유한 벽 segment 위**에 있어야 valid. §G item 6 가 물은 "`_image_inside_floor` 재사용 여부"는 — 그 아이디어(shapely `contains`/거리)를 core 로 재구현하되 web 의존 없이 사용하는 것으로 결정. 볼록 방은 모든 벽 image 보존, **비볼록(L자) 방은 supporting-line 발이 segment 밖이면 prune**(convex 가정이 잘못 보존할 image 제거).
- 검증(in-gate, default lane, `tests/test_polygon_image_source.py`): (i) 4정점 polygon 으로 표현한 **알려진 shoebox** 의 1차 image POSITION 이 analytic mirror(x=0,x=L,z=0,z=W + floor/ceiling 평면)와 **~1e-9 일치**; (ii) **비볼록 L자** fixture 가 off-segment reflection 을 정확히 prune; (iii) determinism·input-validation. acoustic-accuracy 주장 없음.

### DEFERRED (RT60 cascade 전체 — 가짜 숫자 금지)
- **Polygon-ISM RT60 + predictor cascade (§D, PR3)**: DEFER — 비-shoebox **측정 GT 부재**(§G/제안 OQ #2)로 magnitude 입증 불가; sparse ISM-only RIR 의 pyroomacoustics RT60-fit 신뢰성 미검증(§B/제안 OQ #3); pyroomacoustics 가 **web-extra** 라 default-lane 재현성 비대칭(§C2). 지금 RT60 를 내보내면 음향 숫자를 날조하는 셈.
- **pyroomacoustics core lazy-import (§C2)** 및 **coupled-space marker (§F/R4)**: cascade 와 함께 DEFER.
- **byte-equal 보장**: `predictor.py` / `image_source.py` 는 **손대지 않음** → shoebox RT60 회귀 0. `PredictorName` 미변경, `predict_rt60_default` 미연결. 신규 모듈은 sibling 로만 존재.
- disclosure 단일진실원천: `roomestim/reconstruct/_disclosure.py::POLYGON_ISM_GEOMETRY_NOTE`.

### 실측 데이터 검증 (2026-06-08, dEchorate CC-BY 4.0 — geometry only)
합성 shoebox(~1e-9) 외에 **물리적으로 측정된 실제 cuboid 방**(dEchorate 데이터셋)의 annotated early-echo
arrival time 으로 1차 image-source **geometry** 를 독립 검증했다. dEchorate 의 calibrated recipe(`data_rooge.mat`:
c=345.844 m/s@24℃, fs=48k, 단일 calibrated source + 12 mic, 6 surface × 12 mic = 72 reflection TOA)를 사용.
roomestim 좌표(Point3 x·수직 y·z, floor y=0)로 명시 매핑(dEchorate 수직축 z→roomestim y; direct-path 자기일관성
2.8 cm median 으로 매핑 독립 확인). 각 1차 image→mic 거리를 측정 echo TOA(=path/c)와 비교:
- **median per-wall 오차 5.60 cm(0.162 ms); "south" 1면 제외 시 3.88 cm(0.112 ms), max 21 cm.**
- 참조 **noise floor = direct-path 자기일관성 2.8 cm(0.082 ms)** — mirror geometry 가 데이터셋 자체 calibration
  한계에 근접. 5/6 면이 ~3–4 cm(noise floor 수준).
- "south" 1면만 전 12 mic 에서 일관된 부호의 ~42 cm offset → dEchorate 의 **가동형 패널이 nominal bound 보다
  ~21 cm 바깥**에 놓인 **실 GT 기하 caveat**(mirror-math 결함 아님; path-length 수준 비교라 surface 라벨은 고정
  permutation).
- **검증된 것**: 벽 mirror(edge supporting line 반사)·floor(y→−y)·ceiling(y→2H−y) path-length 가 실측 cuboid 와
  일치. **검증 안 된 것**: 비볼록 visibility pruning(방이 cuboid 라 미발동), RT60·흡음 등 음향량(여전히 geometry-only),
  2차+ image, 다중 source. 즉 본 검증은 C 의 **geometry 정확성**을 실측으로 뒷받침할 뿐 acoustic 주장과 무관.
- 근거(gitignored durable note): `.omc/research/dechorate-polygon-ism-validation.md`; throwaway 스크립트 `/tmp/dechorate_ism_validate.py`. roomestim 프로덕션/테스트/버전 무변경(doc-only).

---

## Status-update (2026-06-12, C2 — evidence-backed DEFER, doc-only, NO predictor change)

**RT60 cascade + shoebox diffuse-field cap/blend (Option H): reconfirmed DEFERRED, now WITH a
multi-room MEASURED corpus (previously BUT-403-blocked).** Predictor / ISM / Eyring / materials /
`_disclosure.py::RT60_DISCLOSURE` stay **byte-equal**; no version bump.

### What was measured (live, v0.37.0; evidence note `.omc/research/c2-polygon-ism-rt60-cascade-evaluation.md`)
The candidate diffuse-field caps — hard cap `min(ISM,Eyring)` and β-blends `β·ISM+(1−β)·Eyring`,
β∈{0.25,0.5,0.75} — were evaluated against measured RT60 from **U-Rochester** (figshare 48711175,
**CC-BY 4.0**, n=10 shoebox-feedable, default materials) and **dEchorate** (Zenodo 5562386/4626589,
**CC-BY 4.0**, 11 configs, per-config KNOWN materials, 500 Hz). U-Rochester dims/measured reused
from `urochester-rt60-validation.md`; dEchorate measured T30 prior-recorded from
`but-reverbdb-rt60-validation.md`; all predictions computed live by the shipped predictor.

### Decisive findings
1. **The hard cap `min(ISM,Eyring)` is byte-identical to the already-shipping `prefer_ism=False`.**
   The predictor enforces `ISM ≥ Eyring − 1e-6` (FIX-1/D74), so `min(ISM,Eyring) = Eyring` for every
   shoebox (verified: max |min−Eyring| = 0 across all 21 rooms/configs). The hard cap adds NO
   capability — it is the existing diffuse escape hatch.
2. **The U-Rochester "improvement" of the cap is a MATERIAL-confound coincidence, not geometry.**
   On U-Rochester the cap (=Eyring) drops median abs error 2.904 s → 0.090 s — but only because the
   default `CEILING_ACOUSTIC_TILE` (α=0.55) makes the diffuse average coincidentally land near these
   acoustically-treated rooms' (unknown) true RT60. The bias sign **FLIPS** on dEchorate where
   materials are KNOWN (Eyring median signed −0.131, and Eyring/cap is WORSE than plain ISM on
   aggregate: median abs 0.131 vs 0.100). A cap "validated" by U-Rochester error reduction would be
   fitting the material gap — a soft fake number.
3. **The only material-confound-FREE benefit is the n=1 rigid `011111` specular case** (ISM 2.49 s
   vs measured 0.525 s → cap 0.33 s), which `prefer_ism=False` already exposes.
4. **No geometry-blind β-blend dominates:** the aggregate-optimal β is contradictory between corpora
   (U-Rochester→β=0, dEchorate-known→β=1) — any fixed β is overfit to one corpus.

### Decision rule (all four required to ship a cap) — NOT jointly met
- (i) opt-in default byte-equal — achievable but MOOT (hard cap ≡ shipped `prefer_ism=False`).
- (ii) guards pass default-OFF — achievable but MOOT (same reason).
- (iii) improves a material-confound-FREE metric — MARGINAL: helps only n=1 `011111`; HURTS the
  dEchorate-known aggregate (0.100→0.131); the U-Rochester win is the confounded metric.
- (iv) generalizes beyond n=1–2 cuboids (≥3 independent rigid geometries OR any non-shoebox measured
  RT60 GT) — **NO**, no such corpus exists on disk → decisive gate.
→ **Option B (doc-only DEFER).** No new predictor API surface (`diffuse_cap`/blend NOT added).

### Decision
- **Literal polygon-ISM → RT60 cascade (§D / §A option a) stays DEFERRED:** every measured-RT60
  corpus on disk (U-Rochester, dEchorate, BUT-ReverbDB) is shoebox/cuboid → non-shoebox magnitude
  unverifiable → fake numbers. Reconfirms the 2026-06-08 status-update, now backed by the
  newly-acquired multi-room measured corpus.
- **Shoebox diffuse-field cap/blend (Option H) is NOT validatable as general accuracy.** The hard
  cap is redundant with `prefer_ism=False`; the β-blend has no dataset-independent optimum and
  cannot be shown to generalize (criterion iv). `prefer_ism=False` already provides the rigid-room
  diffuse worst-case mitigation; the already-widened `RT60_DISCLOSURE` (A3 `66babfb`, one-sided
  +160~826% default-regime bias) already states the honest envelope. No new cap API is warranted.
- **Cross-ref ADR 0030 Reverse-criterion item 3:** the geometry foundation is satisfied (geometry-
  only enumerator LANDED v0.31.0; image-source POSITIONS validated to ~cm against the dEchorate
  cuboid); the **acoustic magnitude stays DEFERRED**.
- **Follow-ups (OQ):** non-shoebox measured RT60 GT corpus (still unfound); per-material α GT (would
  dissolve the U-Rochester confound); pyroomacoustics/EDC RT60-fit reliability on sparse ISM RIR.
