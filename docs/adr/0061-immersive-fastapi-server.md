# ADR 0061 — 임머시브 레이아웃 FastAPI `/api/evaluate` 서버 (P5.1, 헤드리스 MVP)

- **Date**: 2026-07-01
- **Status**: Accepted (v0.61.0 — MINOR additive: 신규 top-level 패키지 `roomestim_server/` + `[server]` opt-in extra. core/web 무변경, byte-equal, 물리 재유도 0.)
- **Deciders**: main(설계+오케스트레이션, 재개 `.omc/plans/immersive-layout-p5-fastapi-threejs.md`), executor(구현+테스트), code-reviewer(예정, 독립 패스).
- **Refs**: 코드 `roomestim_server/{__init__,app,schemas,service,errors,rooms}.py`, 테스트 `tests/server/test_evaluate_api.py` + `tests/server/test_rooms_api.py`. 래핑 대상(frozen, 재유도 금지): ADR 0060 `roomestim/design/tradeoff.py::evaluate_layout`/`tradeoff_to_dict`, ADR 0058 `roomestim/spec/speaker_spec.py::BUILTIN_SPEAKER_CATALOG`. 정직성 패턴 mirror: `roomestim_web/immersive_design.py::_on_evaluate` (ADR 0038 / OQ-45). 플랜 = 임머시브 레이아웃 설계 도구 P5 (`.omc/plans/immersive-layout-p5-fastapi-threejs.md`).

> **핵심요약**: 이미 ship 된 P3 4축 trade-off 엔진을 HTTP JSON 으로 노출하는 얇은 stateless REST 레이어. 새 물리 0 — 모든 수치는 `evaluate_layout` → `tradeoff_to_dict` 를 그대로 forward (byte-equal 패리티 테스트로 증명). 신규 `roomestim_server` 패키지를 `[server]` opt-in extra(FastAPI=MIT, uvicorn=BSD-3, httpx=BSD-3) 뒤에 격리; `import roomestim`/`import roomestim_server` 는 fastapi-free 유지(create_app 호출 시에만 lazy import). 프런트엔드(Three.js)는 P5.2 로 연기.

---

## Context

임머시브 레이아웃 설계 도구의 4축 trade-off 엔진(ADR 0060)은 library + Gradio 탭(P4)으로만 노출돼 있다. AV 엔지니어가 브라우저에서 스피커를 드래그하며 리포트를 실시간으로 보는 도구(P5)를 만들려면 먼저 엔진을 HTTP API 로 노출해야 한다. P5.1 은 그 중 **완전 헤드리스·완전 테스트 가능한 MVP 슬라이스**(프런트엔드 없이 `/api/evaluate` + room 지오메트리 엔드포인트)다.

설계 제약: (1) NO FAKE NUMBERS — 모든 수치는 실제 `evaluate_layout` 계산으로 추적 가능, JS/서버 물리 0; (2) D29 web→core 단방향 — 서버는 serve/validate/call/serialise 만; (3) additive opt-in — core 게이트는 fastapi 불요; (4) 상용 OK 라이선스만; (5) 원시 예외 미노출(ADR 0038).

## Decision

### 1. 신규 top-level 패키지 `roomestim_server/` (`[server]` extra 뒤)
`roomestim_web`(Gradio, `[web]`)와 별개의 sibling 패키지. 두 ASGI 스택/extra 가 얽히지 않도록 분리. 레이아웃: `__init__`(lazy 가드) · `app`(FastAPI 팩토리) · `schemas`(pydantic v2 요청 모델) · `service`(thin 어댑터) · `errors`(generic 메시지+코드) · `rooms`(내장 룸 레지스트리+지오메트리 직렬화) · `static/`(P5.2 용 placeholder).

### 2. Lazy 경계 — core/패키지 import 는 fastapi-free
`roomestim_server/__init__.py` 는 top-level 에서 fastapi/app/schemas 를 import 하지 않는다. `create_app()` 호출 시에만 `roomestim_server.app` 을 lazy import; fastapi 부재 시 `ImportError("install roomestim[server]: pip install 'roomestim[server]'")` 로 친절히 실패. → `import roomestim`(core) 와 `import roomestim_server`(패키지) 둘 다 fastapi 를 sys.modules 에 로드하지 않음(게이트 검증).

### 3. Stateless REST MVP — WebSocket 미도입
- `POST /api/evaluate` — 엔진 계약 전체를 한 호출로. 요청 = room_id + placement(speakers[]) + spec(model_key, price?) + params(drive_w, target_spl_db, measured_rt60_s?, grid_resolution_m?, min_separation_deg?). 응답 성공 = `{"ok": true, "report": <tradeoff_to_dict>}` (inner report 는 note-first).
- `GET /api/rooms` / `GET /api/rooms/{id}` — 지오메트리 ONLY(floor_polygon, ceiling_height_m, listener_area, walls-from-surfaces). 물리/재질 미노출.
- `GET /healthz` — 부팅 스모크.
- WebSocket 은 드래그 latency 가 측정상 문제일 때만 후속 phase 에서 추가(현재 미도입 — stateless 가 테스트 가능성 유지).

### 4. 성공/에러 봉투(envelope) — uniform `ok` 플래그
성공 `{"ok": true, "report": {...}}`; 에러 `{"ok": false, "error": {"code", "message"}}`. (OQ-P5-3 = wrapped 채택 — 클라이언트 success/error 파싱 일관.) HTTP 상태: 200 성공 / 400 client-attributable core `ValueError`(코드 `INVALID_REQUEST`) / 404 미지 room_id(`GET` 경로, 코드 `ROOM_NOT_FOUND`) / 422 pydantic 스키마 위반(FastAPI 기본) / 500 예기치 못한(전역 핸들러, 코드 `INTERNAL`).

### 5. 물리 패리티 보장 (NO FAKE NUMBERS 의 핵심 가드)
`service.evaluate_request` 는 검증된 요청을 core 객체(`PlacementResult`/`SpeakerSpec`/`RoomModel`)로 정규화 → `evaluate_layout(...)` → `tradeoff_to_dict` 만 한다. 물리 재유도 0. 테스트 `test_evaluate_physics_parity_byte_equal` 가 고정 입력에 대해 API report `==` in-process `tradeoff_to_dict(evaluate_layout(...))` 를 **dict 완전 일치**로 단언 → 서버가 어떤 물리/drift 도 추가 안 함을 증명. measured_rt60_s 는 web 패널과 동일하게 null/≤0 → predicted(주입 안 함).

### 6. 정직성 — 원시 예외 미노출 (ADR 0038 / OQ-45 mirror)
core `ValueError`(drive_w≤0, <2 스피커, 미지 spec key, 비양수 주입 RT60)·미지 room_id 는 서버측에서 `_LOG.warning` 으로 실제 텍스트 로깅 후 generic `EvaluateError`(→400 KR+EN generic 메시지)로 재발생. 예기치 못한 모든 예외는 전역 `Exception` 핸들러가 `_LOG.exception` 로깅 후 generic 500. 클라이언트 응답 본문에 stack/path/`ValueError(` 텍스트 누출 0 (테스트 `_assert_no_internals` 단언).

### 7. 내장 합성 룸 — `builtin:shoebox`
`rooms.py` 가 `tests/fixtures/synthetic_rooms.py::shoebox` 를 production 측에 로컬 복제(테스트 트리 의존 회피)한 결정적 5×4×3 m shoebox 1개를 빌더 레지스트리로 제공. 유효 `listener_area` 보유(엔진이 그 위에서 SPL field 평가). 업로드→adapter 는 P5.4 로 연기.

## License confirmation (HARD CONSTRAINT #4)

- **FastAPI** — MIT.
- **uvicorn** — BSD-3-Clause.
- **Starlette**(fastapi 전이 의존) — BSD-3-Clause.
- **Pydantic** v2 (fastapi 전이 의존) — MIT.
- **httpx**(TestClient 전송, in-gate 테스트 필수) — BSD-3-Clause.
모두 permissive·pure-Python·commercial-OK. GPL/AGPL/NC 전이 의존 없음. Three.js(MIT)는 P5.2 에서 벤더링 시 별도 헤더로 기록.

## Consequences

- **(+)** 프로그래매틱 4축 trade-off API 단독으로 shippable·유용. 헤드리스 100% 테스트(계약 shape + 물리 패리티 byte-equal + 에러 봉투 no-leak + boundary 가드). 신규 서버 테스트 16개(default 게이트에 in-gate 합류, `pytest.importorskip("fastapi")` 로 extra 부재 env 포터블).
- **(+)** core/web 무변경 byte-equal. `import roomestim` torch-free·fastapi-free 유지(게이트 검증). 물리 재유도 0 — 모든 수치 forward.
- **(+)** `[server]` opt-in 격리. fastapi 는 `create_app()` 호출 시에만 lazy 로드; 부재 시 친절한 ImportError. core mypy 69 불변, 신규 `roomestim_server` 6파일 mypy --strict clean.
- **(−)** 프런트엔드(Three.js 렌더+드래그)는 P5.2/P5.3 로 연기 — 가장 사용자-가시적인 부분은 헤드리스로 검증 불가(WebGL). MVP 는 자동화 가능한 proxy(계약+패리티+부팅 스모크)를 최대화하고 시각 검증은 후속 phase 의 명시적 human 단계로 남김.
- **(−)** 단일 내장 룸만(`builtin:shoebox`). 실 캡처 업로드/export 는 P5.4.
