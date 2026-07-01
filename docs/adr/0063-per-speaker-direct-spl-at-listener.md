# ADR 0063 — 스피커별 개별 직접음장 SPL (청취 지점) — 설치 가이드용

- **Date**: 2026-07-01
- **Status**: Accepted (v0.63.0 — MINOR additive: 신규 public 함수
  `per_speaker_direct_spl_at_listener`. 기존 SPL 엔진·placement·default import
  경계·골든 무변경, byte-equal.)
- **Deciders**: main(설계+오케스트레이션, 재개 `.omc/plans/immersive-installer-ux-p6.md`
  Phase P6.D), executor(구현), code-reviewer(opus, 독립).
- **Refs**: 코드 `roomestim/spec/speaker_spec.py::per_speaker_direct_spl_at_listener`.
  재사용: `direct_field_spl_db`(L122)·`_aim_unit_vector`(L186)·`_spec_for_channel`·
  `spl_field_over_area`(per-point 계산의 단일-점 특수화). 단일진실원천
  `SPL_DIRECT_FIELD_NOTE`. server `roomestim_server/service.py` install 블록
  + viewer 테이블. 임머시브 레이아웃 설치자-대면 UX Phase P6.D. 토대 = ADR 0058.

> **핵심요약**: 설치자가 스피커를 하나 옮길 때 "이 스피커가 청취 지점에 단독으로
> 얼마의 SPL 을 기여하는가"를 보여준다. 새 음향은 발명하지 않는다 — ADR 0058 의
> `spl_field_over_area` 가 그리드 위에서 하던 per-point 계산(거리 + off-axis +
> `direct_field_spl_db`)을 **한 점(청취자 귀)에서만** 평가한 것. 직접음장-only,
> 측정값 아님(`SPL_DIRECT_FIELD_NOTE` 계승).

---

## Context

P6.D 이전에는 `/api/evaluate` 가 **집계** SPL(청취영역의 min/mean/max/uniformity,
`spl_field_over_area`)만 냈다. 설치자가 스피커 하나를 드래그하면 집계 지표만
갱신될 뿐, **그 스피커의 개별 기여**는 화면에 없었다 — "이 스피커를 옮기면 뭐가
변하나"를 직접 보여주지 못했다. 개별 스피커 SPL 은 엔진에 없던 값이라 core 에
작은 추가가 필요했다(P6.C 의 geometry-only install 블록으로는 불가).

## Decision

### 1. `per_speaker_direct_spl_at_listener` (core, additive)
`(specs, *, drive_w, speakers, listener_area) -> list[tuple[int, float]]`. 각
스피커에 대해:

- `ear = (centroid.x, listener_area.height_m, centroid.z)`;
  `(dx,dy,dz) = ear − speaker.position`; `dist = ||(dx,dy,dz)||`.
- `off_axis` = `_aim_unit_vector(speaker, listener_area)` 와 `(dx,dy,dz)` 사이 각
  — `spl_field_over_area` 의 sample-point off-axis 유도를 **문자-동일** 미러
  (동일 `cos_off = clamp(dot/dist, −1, 1)` 클램프, degenerate `dist<=0 → 1e-6`/
  on-axis fallback, `acos` 전 `assert_finite(cos_off)` 가드).
- `spl = direct_field_spl_db(spec, drive_w, distance_m=dist, off_axis_deg)`.

채널별 스펙은 기존 `_spec_for_channel` 로 resolve(단일 스펙 → 전 채널 공유,
`dict[channel→spec]` → 채널별). `drive_w` 가드는 `direct_field_spl_db` 와 동일
(비유한/비양수 → `ValueError`). `__all__` 에 추가. `SPL_DIRECT_FIELD_NOTE` 계승.

### 2. server (`service.py`)
`evaluate_request` 가 P6.C install 블록의 각 speaker 에 `spl_at_listener_db` 를
추가(위 core 함수 위임, 채널 매칭). SPL 계산은 별도 guard 로 감싸 실패 시 **그
필드만** null 로 degrade(geometry 는 불변); install 빌드 전체도 guard 유지 →
어떤 실패도 evaluate 를 깨지 않고 원시 예외를 누출하지 않음(ADR 0038). `report`
는 verbatim engine dict 그대로.

### 3. viewer (`main.js` + `index.html`)
설치 테이블에 "SPL @listener (dB)" 열; 방금 옮긴 스피커의 채널을 드래그-엔드에
기록해 재렌더 후 그 행을 하이라이트(재시드 시 해제). D29 — JS 물리 0, 모든
수치는 서버 계산.

## Consequences

- **(+)** 설치자가 스피커별 개별 SPL 기여를 실시간(드래그-엔드)으로 확인 — "무엇이
  변했는지"가 명시적. 임머시브 설치 UX(P6) 완성.
- **(+)** core 기존 SPL 엔진·골든 byte-equal(순수 additive; numpy-free,
  `import roomestim` torch-free 경계 유지). off-axis 유도가 `spl_field_over_area`
  와 문자-동일이라 단일 스피커·단일 샘플에서 두 경로가 정확히 일치(테스트로 실증).
- **(+)** NO FAKE NUMBERS: `SPL_DIRECT_FIELD_NOTE` 계승(직접음장-only, 반사음장/
  room-gain 미모델·과소추정 방향 + max_spl_db 미캡·과대추정 방향 둘 다 고지),
  카탈로그 estimate 라벨, D29(JS 물리 0).
- **(−)** 직접음장-only 는 실내 절대 SPL 의 upper/lower bound 아님(고지됨; ADR
  0058 와 동일 한계). 절대수치는 `provenance="datasheet"` 일 때만 유의미.
