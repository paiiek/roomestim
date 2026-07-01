# Changelog

All notable changes to roomestim are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.61.0] — 2026-07-01

**임머시브 레이아웃 FastAPI `/api/evaluate` 서버 (P5.1, 헤드리스 MVP)** (MINOR,
additive, core/web byte-equal). ADR 0061. 이미 ship 된 P3 4축 trade-off 엔진
(`roomestim.design.tradeoff.evaluate_layout` → `tradeoff_to_dict`, ADR 0060)을
HTTP JSON 으로 노출하는 얇은 stateless REST 레이어. **물리 재유도 0** — 모든
수치는 엔진을 그대로 forward (byte-equal 패리티 테스트로 증명).

### Server (앱-티어, 신규 `[server]` opt-in extra)

신규 top-level 패키지 `roomestim_server/` (`roomestim_web` 와 별개 sibling).
`create_app()` FastAPI 팩토리 + 엔드포인트: `POST /api/evaluate`
(`{"ok": true, "report": <note-first tradeoff_to_dict>}`), `GET /api/rooms` +
`GET /api/rooms/{id}` (지오메트리 ONLY — floor_polygon/ceiling_height/listener_area/
walls, 물리·재질 미노출), `GET /healthz`. 내장 결정적 합성 룸 `builtin:shoebox`
(5×4×3 m) 1개. 요청은 pydantic v2 로 검증(스키마 위반 → FastAPI 기본 422).

- **정직성 (ADR 0038 / OQ-45 mirror)**: client-attributable core `ValueError`
  (drive_w≤0, <2 스피커, 미지 spec key, 비양수 주입 RT60)·미지 room_id 는
  서버측 `_LOG.warning`/`_LOG.exception` 로 실제 텍스트 로깅 후 generic 봉투로
  변환 — 400 `{"ok": false, "error": {"code": "INVALID_REQUEST", ...}}` /
  404 `ROOM_NOT_FOUND` / 전역 핸들러 500 `INTERNAL`. 응답 본문에 stack/path/
  raw 예외 텍스트 누출 0.
- **물리 패리티 (NO FAKE NUMBERS)**: 고정 입력에 대해 API report `==` in-process
  `tradeoff_to_dict(evaluate_layout(...))` dict 완전 일치 단언 → 서버가 어떤
  물리/drift 도 추가 안 함을 증명 (D29 web→core 단방향).
- **경계 (additive opt-in)**: `[server]` extra = FastAPI(MIT) + uvicorn(BSD-3) +
  httpx(BSD-3, TestClient 전송); Starlette(BSD-3)·Pydantic(MIT) 전이. fastapi 는
  `create_app()` 호출 시에만 lazy import — `import roomestim`(core) 와
  `import roomestim_server`(패키지) 둘 다 fastapi-free 유지(게이트 검증).
  extra 부재 시 `create_app()` 은 친절한 `ImportError("install roomestim[server]")`.
- 헤드리스 서버 테스트 16개(`tests/server/`, `pytest.importorskip("fastapi")` 로
  extra 부재 env 포터블; 카논 miniforge env 에는 fastapi 설치돼 default 게이트
  in-gate 합류). 프런트엔드(Three.js 렌더+드래그)는 P5.2/P5.3 로 연기.

### Server — 프런트엔드 뷰어 (P5.2, static Three.js, core/버전 무변경)

`roomestim_server` 에 정적 3-D 뷰어 추가 (드래그는 P5.3 로 연기 — orbit 카메라만).
`GET /` = `index.html` 셸, `/static` StaticFiles 마운트(기존 `/api/*`·`/healthz`
라우트 미잠식). 로드 시 `GET /api/rooms/{id}` 로 룸 지오메트리(바닥/벽/청취영역)
+ 리터럴 seed 스피커 6개를 렌더하고, `POST /api/evaluate` 를 1회 호출해 4축 리포트
+ **상시 면책 배너**(`note`·`spl_provenance`·`rt60.source`)를 그린다.

- **D29 — JS 물리 0**: 뷰어는 SPL/각도/RT60 수식을 전혀 계산하지 않는다. 모든 수치는
  `/api/evaluate` 응답에서 verbatim 으로 읽고, seed 위치는 리터럴 UI 데이터(트리그
  계산 없음). 리포트 렌더는 전부 `textContent`(XSS-safe), 에러 봉투(`{"ok": false}`)
  graceful 처리. 독립 리뷰가 모든 중첩 계약 키를 `tradeoff_to_dict` 산출과 대조 검증.
- **Three.js 벤더링(오프라인/공급망)**: `three@0.160.0`(MIT) `three.module.js` +
  `OrbitControls.js` 를 `static/vendor/` 에 로컬 벤더링, ES-module importmap 로 로컬
  서빙 — 빌드 스텝·npm·외부 CDN·로드-시 페치 0. 현장(air-gapped) AV 설치서도 동작.
- 헤드리스 테스트(`tests/server/test_static_and_rooms.py`): `GET /` HTML·`/static`
  서빙·마운트가 `/healthz`·`/api/evaluate` 미잠식·벤더 three 로컬 서빙(CDN URL 부재)·
  main.js 가 실 계약 키(중첩 per-axis 포함) 참조. **3-D 렌더 자체는 human 육안 검증**
  (headless WebGL 불가 — 플랜 §7 명시).

### Server — 드래그 + live 재평가 (P5.3, core/버전 무변경)

뷰어에 스피커 **드래그** + 실시간 재평가 + 레이아웃 **재시드**(`POST /api/place`) 추가.

- **드래그**(`static/main.js`): raycaster 를 수평(+Y) 평면에 투영해 스피커 스피어의
  x,z 만 이동(y 고정 — 순수 UI 지오메트리). 드래그 중 OrbitControls 비활성(포인터
  경합 방지)·pointer capture; 드래그-종료 시 debounce(120 ms) 후 `/api/evaluate`
  재호출→메트릭 리페인트. 단조 증가 `_evalSeq` 가드로 느린 옛 응답이 새 렌더를
  덮어쓰지 못하게 함(경쟁 안전).
- **`POST /api/place`**(신규): `{room_id, algorithm, n_speakers, layout_radius_m,
  el_deg}` → core `run_placement` 위임 후 speakers 직렬화 반환. **D29** — 배치 물리
  전량 core, 서버/JS 재유도 0(`service.place_request` 는 evaluate 와 동일한 얇은
  resolve→call→serialise 어댑터; 물리-패리티 테스트로 위치·aim_direction verbatim
  증명). 미지 room_id·미지 algorithm·per-algorithm 최소 미달(예: VBAP ring n≥3) =
  core `ValueError` → generic 400 봉투(누출 0); `n_speakers` 는 스키마서 1..128 로
  sanity-bound(초과 → 422, DoS 가드).
- **재시드 UI**: algorithm(vbap/dbap/coverage) select + n 입력 + 버튼 → `/api/place`
  결과로 마커·layoutMeta 교체 후 재평가.
- 헤드리스 테스트(`tests/server/test_place_api.py`, 10개): 계약·물리 패리티(위치+aim)·
  에러 봉투(미지 algo/room·too-few·malformed·out-of-bounds)·place→evaluate 라운드트립.
  **드래그 UX 자체는 human 육안 검증**(WebGL, headless 불가).

### Server — specs·room.yaml 업로드·폼 컨트롤·export (P5.4, 최종 슬라이스, core/버전 무변경)

P5 마지막 슬라이스: 스피커 카탈로그 노출·실 room.yaml 업로드·파라미터 폼·리포트 export.

- **`GET /api/specs`**: `BUILTIN_SPEAKER_CATALOG`(model_key·price·provenance) 나열
  → 프런트 spec 드롭다운. 물리 0.
- **`POST /api/rooms/upload`**: room.yaml 을 **텍스트(JSON 본문 `{room_yaml}`)**로 받아
  torch-free 코어 `read_room_yaml` 로 파싱(멀티파트 미사용 → `[server]` 의존 무변경).
  파싱된 룸은 **bounded in-memory 레지스트리**(`uploaded:<n>`, cap 32 oldest-evict,
  `threading.Lock` 보호, `get_room` 은 deepcopy 반환)에 저장 — 무상태 서버의 의도적·
  경계-제한 예외(프로세스-로컬·비영속·워커 간 비공유, 정직 고지). **D29** 지오메트리
  재유도 0. 잘못된 업로드(malformed YAML·룸 아님·스키마 위반) = 전부 client-attributable
  → `read_room_yaml` 이 `ValueError` 로 래핑 → generic 400(누출 0, 4개 malformed 클래스
  실증); `room_yaml` 은 ~2 MB max_length(초과 → 422 DoS 가드). 캡처파일(roomplan/usdz/
  image) adapter 업로드는 DEFERRED(무거운 의존, room.yaml 만).
- **폼 컨트롤**(`static/`): spec 드롭다운 + target_spl_db·drive_w·measured_rt60_s 입력
  → `/api/evaluate` 로 공급(공백 RT60 → null → predicted), 변경 시 debounce 재평가.
  스피커-수 selector 는 P5.3 재시드로 이미 존재.
- **Export trade-off JSON**: 마지막 `/api/evaluate` 리포트를 **verbatim** 다운로드
  (`_lastReport` Blob, 재계산 0 → drift 없음, `_on_export_tradeoff` 규칙 mirror).
- **Upload UI**: `<input type=file>` → FileReader.readAsText → 업로드 → 현재 룸 교체·
  재렌더·재평가(`currentRoomId` mutable).
- 헤드리스 테스트(`tests/server/test_upload_and_export.py`, 11개): specs·업로드
  라운드트립(write_room_yaml→upload→evaluate/place)·bad-yaml/not-a-room 400·malformed
  422·distinct id·unknown-id 404/400·eviction cap·deepcopy 격리·oversize 422·main.js
  wiring grep. **파일 다운로드+WebGL 렌더는 human 육안**.

### Server — RoomPlan JSON 캡처 업로드 (P5.5, core/버전 무변경)

P5.4 가 DEFER 했던 캡처파일 업로드를 실제 Apple **RoomPlan JSON 사이드카**로 확장
(measured/LiDAR 캡처 = 제품 북극성). glTF/USD(바이너리+trimesh/pxr)와 달리 RoomPlan
JSON 은 텍스트 기반 + torch-free(`roomestim.adapters.roomplan` = json+numpy, 둘 다
이미 core 의존) → 멀티파트/무거운 의존 없이 `[server]` 경계 유지.

- **`POST /api/rooms/upload/roomplan`**: RoomPlan JSON 을 **텍스트(JSON 본문
  `{roomplan_json}`)**로 받아 torch-free 코어 `RoomPlanAdapter().parse` 로 파싱
  (멀티파트 미사용). exact POST 경로 → GET `/api/rooms/{room_id:path}` 미충돌. 파싱된
  룸은 room.yaml 업로드와 **동일** bounded 레지스트리(`uploaded:<n>`)에 저장·evaluate/
  place 에서 재사용. **D29** 지오메트리 재유도 0; RoomPlan 은 metric-native 라
  `scale_anchor` 미사용.
- **공유 헬퍼 `_parse_and_register(text, suffix, parse_fn)`**: temp-file→parse→generic-
  `EvaluateError`-on-any-exc→`finally` unlink→register→serialise 로직을 추출 →
  `upload_room`(room.yaml) 은 **byte-equal** 유지, `upload_roomplan` 이 재사용.
- **정직성 (ADR 0038)**: malformed JSON·룸 아님(floors[] 부재)·비-객체 페이로드·
  `.usdz` 시맨틱 = 전부 client-attributable → adapter 가 `ValueError`/
  `NotImplementedError` raise → generic 400(raw 예외/traceback 누출 0, 서버측만 로깅).
  `roomplan_json` 은 ~5 MB max_length(room.yaml 캡의 ~2.5× — 사이드카가 벽/바닥/천장
  transform + per-object 를 verbose JSON 으로 열거하기 때문; 초과 → 422 DoS 가드).
- **Upload UI**(`static/`): "RoomPlan JSON (.json)" `<input type=file>` 을 기존
  room.yaml 업로드 옆에 추가, 동일 업로드→룸교체→재렌더→재평가 흐름 공유(JS 물리 0).
- 헤드리스 테스트(`tests/server/test_upload_roomplan.py`, 8개): 해피패스(`lab_room.json`
  fixture)·id 라운드트립(GET + `/api/evaluate`)·malformed/not-a-room/비-객체 400·missing
  422·oversize 422·room.yaml 업로드 회귀 가드. core & 버전 무변경(server-only, P5.2~5.4 미러).

### Server — RoomPlan 멀티룸(CapturedStructure) 업로드 + 예시 로더 + room-picker (P5.6, core/버전 무변경)

P5.5(단일룸)를 실제 Apple **`CapturedStructure`(멀티룸)** ingest 로 확장 + 사용자가
자기 파일 없이도 브라우저에서 클릭 테스트할 수 있게 **예시 캡처 3종을 번들**. torch-free
코어 `roomestim.adapters.roomplan_structure.parse_structure`(json+numpy+shapely, 셋 다
이미 core 의존)가 export 를 섹션당 1개 `RoomModel`(멀티룸 fixture → 4룸, 단일 → 1룸)로
분해 — 멀티파트/새 의존 없음.

- **`POST /api/rooms/upload/structure`**: CapturedStructure 를 **텍스트(JSON 본문
  `{structure_json}`)**로 받아 `parse_structure` 로 분해, 각 `RoomModel` 을 room.yaml/
  RoomPlan 업로드와 **동일** bounded 레지스트리(`uploaded:<n>`)에 등록, `{"rooms": [...]}`
  (섹션 순서 보존)를 반환 — 각 룸 id 는 `/api/evaluate`·`/api/place` 에서 그대로 사용 가능.
  **D29** 지오메트리 재유도 0.
- **`GET /api/examples`** + **`POST /api/examples/{id}/load`**: 번들 예시 매니페스트(id/
  name/format/description)를 나열하고, 선택 시 서버가 파일을 읽어 **업로드와 동일한 파싱
  경로**로 dispatch — `roomplan` 포맷 → `{"room": ...}`(단일), `structure` 포맷 →
  `{"rooms": [...]}`(멀티). 미지 id → generic 404 `EXAMPLE_NOT_FOUND`(누출 0).
- **번들 예시(`roomestim_server/examples/`)**: `lab_room_synthetic.json`(자체 합성 RoomPlan
  사이드카) + `capturedstructure_single.json`·`capturedstructure_multiroom.json`(**실제 Apple
  export, MIT** — theLodgeBots/open3dFloorplan, `examples/ATTRIBUTION.md` 동봉). pyproject
  `package-data` 에 `roomestim_server = ["examples/*.json", "examples/*.md"]` 추가로 휠 동봉.
- **공유 헬퍼 리팩터**: temp-file 쓰기 + `finally` unlink + generic-`EvaluateError`-on-any-exc
  규율을 `_with_temp_file(text, suffix, fn)` 단일 지점으로 추출 → 단일룸 `_parse_and_register`
  는 **byte-equal** 유지, 신규 멀티룸 `_parse_and_register_many` 가 동일 규율 재사용.
- **정직성 (ADR 0038)**: malformed JSON·sections[] 부재·비-객체·잘못된 확장자 = 전부
  client-attributable → `ValueError` → generic 400(raw 예외/traceback 누출 0). 깨진 번들
  예시(shipped-broken)도 서버 버그이나 generic 400 으로만 노출(내부 미노출; 테스트가 모든
  번들 예시 파싱을 가드). `structure_json` 은 ~10 MB max_length(멀티룸 fixture ~252 KB →
  넉넉하지만 bounded; 초과 → 422 DoS 가드).
- **UI**(`static/`): CapturedStructure(.json) 업로드 인풋 + "예시 불러오기" 드롭다운(GET
  `/api/examples`) + **room-picker**(멀티룸 결과 시 표시, 이미 파싱·등록된 룸 중 재선택 —
  JS 물리 0, D29). 단일룸 결과는 기존과 동일 동작.
- 헤드리스 테스트(`tests/server/test_upload_structure.py` + `test_examples.py`): 멀티룸→4룸
  각 retrievable+evaluable·단일→1룸·malformed/no-sections/비-객체 400·missing 422·oversize
  422·단일룸 업로드 회귀 가드; 예시 매니페스트 나열·포맷별 shape·모든 번들 예시 로드 가드·
  미지 id 404. **core & 버전 0.61.0 무변경**(server-only, P5.2~5.5 미러); 번들 실 예시는
  MIT-attributed.

### Server — captured-room 좌표프레임 정합 FIX (P5.8, core/버전 무변경)

업로드/캡처 룸(RoomPlan·CapturedStructure·mesh)이 자기 world 프레임(임의 원점·floor y≠0)
으로 들어와, listener-centric SEED/placement(원점 기준)과 어긋나 **뷰어 렌더가 어긋나고
evaluate 메트릭도 프레임 불일치로 잘못** 계산되던 버그 수정. 추가로 `/api/place`가 스피커를
y=0(귀-원점)로 반환해 **재시드 시 스피커가 바닥으로 떨어지던** 2차 불일치도 해소.

- `rooms.py::_recenter_to_listener_origin`: 업로드 룸을 canonical Frame A(floor y=0,
  listener centroid 수평원점)로 **순수 강체 평행이동**(회전·스케일·재유도 0 → 물리 불변).
  모든 지오메트리(floor_polygon·surfaces·listener_area·free-standing object anchor)
  이동, 벽부착(문/창) anchor·상대 extent·height_m 불변. `register_uploaded_room` 단일
  choke point에 적용(built-in shoebox는 이미 canonical→no-op, idempotent).
- `service.py::place_request`: ear-origin 알고리즘(vbap/dome/ambisonics) 시드를
  `listener_area.height_m`만큼 상향(귀 높이)해 SEED·evaluate와 정합 — client-facing
  view 조정, evaluate는 speaker y를 절대좌표로 샘플(ear plane=height_m)하므로 round-trip
  이중계산 없음. room-absolute(dbap/coverage/wfs=벽/천장/절대 mount)은 미상향.
  업로드 응답은 STORED(recentered) 룸을 직렬화 → 렌더=place=evaluate 일치.
- 독립 opus review=APPROVE(0 blocker, 3 LOW informational). server tests +3(recenter·
  ear-height 회귀). **core & 버전 0.61.0 무변경.**

### Server — layout.yaml export + glTF/USD 메시 업로드 (P5.7, core/버전 무변경)

두 독립 서버-only additive 기능을 한 증분으로. **설계→엔진 루프 폐합**(브라우저가
엔진이 소비하는 `layout.yaml` 을 직접 emit) + **캡처 커버리지 확장**(RoomPlan 을
넘어 Polycam/포토그래메트리/일반 스캔 메시). 코어/버전 `0.61.0` 무변경, 물리 재유도 0.

- **`POST /api/export/layout`** (Feature A): `{room_id, placement}` 를 받아 코어
  `roomestim.export.layout_yaml.write_layout_yaml` 로 `layout.yaml`(placement-only
  엔진 계약)을 temp OUTPUT 파일에 쓴 뒤 텍스트를 읽어 `{"filename": "layout.yaml",
  "yaml": <text>}` 반환 — D29 placement 재유도 0. **검증 env-gate**:
  `validate = bool(SPATIAL_ENGINE_REPO_DIR)`(엔진 repo 있을 때만 full 스키마 검증;
  없으면 코어가 `# WARNING: schema validation skipped` 헤더를 붙여 정직 고지 — 유지).
  R10 too-few-speakers / WFS-without-alias / 미지 room_id → generic 400. `room_id`
  는 대칭/forward-compat 용(존재 확인만).
- **`POST /api/rooms/upload/mesh`** (Feature B): BINARY 메시(`.obj/.gltf/.glb/.ply`
  = trimesh 코어 의존, `.usdz` = `[usd]` extra)를 **base64 문자열 필드**(JSON,
  **멀티파트 아님** → python-multipart 무의존 유지)로 받아 코어
  `roomestim.adapters.mesh.MeshAdapter().parse` 로 파싱, 기존 bounded 레지스트리
  (`uploaded:<n>`)에 등록, `{"room": geom}` 반환 — D29 지오메트리 재유도 0. 미지원
  확장자는 파싱 전에 거부, 잘못된 base64/oversize/degenerate 메시/`.usdz`-without-
  `[usd]`(adapter `ImportError`) → 전부 generic 400. 디코드 바이트의 authoritative
  상한은 MeshAdapter 자체 `_MAX_MESH_FILE_BYTES`(~200 MB); `content_b64` 는 ~90 MB
  transport 상한(초과 → 422 DoS 가드).
- **temp-file 헬퍼 확장**: 기존 텍스트-입력 `_with_temp_file` 옆에 바이트-입력
  `_with_temp_bytes_file`(메시)와 출력-then-read `_export_to_temp_file`(layout)
  추가 — 셋 다 동일한 `finally` unlink + generic-`EvaluateError`-on-any-exc 규율.
- **정직성 (ADR 0038)**: 모든 실패는 client-attributable → 서버측 로깅 후 generic
  봉투(raw 예외/traceback/경로 누출 0).
- **UI**(`static/`): 메시 파일 인풋(`.obj,.gltf,.glb,.ply,.usdz` + `.usdz` extra
  주석) → ArrayBuffer→base64→POST(JS 파싱 0, D29) + "Export layout.yaml" 버튼
  (현재 room_id+live placement → 반환 yaml 을 브라우저 다운로드).
- 헤드리스 테스트(`tests/server/test_export_layout.py` + `test_upload_mesh.py`):
  export 성공 계약·WARNING 헤더(env unset)·yaml 파싱·too-few/미지-hint/미지-room
  400·missing 422; 메시 gltf/obj/ply 라운드트립+evaluate·`.usdz`(pxr 유무 모두
  200|400, never 500/leak)·bad base64/미지원 확장자/garbage bytes 400·oversize 422·
  room.yaml 업로드 회귀. **core & 버전 0.61.0 무변경**(server-only).

### Server — per-kind 재질 편집 (P5.9, curated rule-base, core/버전 무변경)

사용자가 바닥/벽/천장 재질을 curated 10-재질 목록에서 선택하면 룸의 예측 RT60
(trade-off 리포트의 `rt60`)이 그에 맞춰 갱신된다. **label 기반만** — 커스텀 수치 α
입력은 별도 결정까지 연기(label-only). 코어(`roomestim/`) 무변경, 버전 `0.61.0`
유지, 물리 재유도 0(모든 계수는 코어 룰베이스에서 읽음).

- **`GET /api/materials`** (`/api/specs` 패턴 미러): `roomestim.model.MaterialLabel`
  10개 각각 `{"label": <NAME>, "name": <human>, "absorption_500hz": <500 Hz α>}`
  반환 — α 는 `MaterialAbsorption`(Vorländer 2020)의 REAL 계수. UI 드롭다운 구동.
- **evaluate 재질 override**: `EvaluateRequest` 에 OPTIONAL `materials`
  (`MaterialsOverrideIn`: `floor`/`walls`/`ceiling`, 각 MaterialLabel NAME 또는
  null) 추가. 설정 시 `get_room` 이 돌려준 **복사본**(built-in=fresh build,
  uploaded=deepcopy — 공유 상태 아님)에서 해당 kind 의 모든 `Surface` 의
  `material`/`absorption_500hz`/`absorption_bands` 를 코어 테이블
  (`MaterialAbsorption`/`MaterialAbsorptionBands`)로 IN-PLACE 재설정(`Surface` 는
  frozen → `dataclasses.replace`) 후 evaluate → 예측 RT60 반영. 미지 라벨 이름 →
  서버측 로깅 후 generic 400(누출 0). `materials` 부재/all-null → **byte-equal**
  (순수 additive, 기존 테스트 무회귀).
- **UI**(`static/`): floor/walls/ceiling `<select>` 3개(`GET /api/materials` 로
  채움, `이름 (α=<계수>)` 표시, 첫 옵션 `— (keep)` = override 없음) → `change` 시
  기존 debounced 재평가에 배선, 요청 body 에 `materials:{floor,walls,ceiling}` 포함.
  D29 — JS 물리 0(서버/코어가 RT60 계산, JS 는 라벨만 전송).
- 헤드리스 테스트(`tests/server/test_materials.py`): 카탈로그 10개+실 α·바닥 carpet
  vs glass → 예측 RT60 **변화(방향 무단언)**(★멀티밴드 ISM 예측기라 500 Hz α 만으로는
  단조 아님 — carpet 은 저역 흡수가 wood/glass 보다 낮아 바닥-단독 교체 시 오히려 근소
  LONGER; 방향 단언은 all-surface MELAMINE_FOAM 0.07 s ≪ WALL_CONCRETE 5.6 s 같은 대신호
  로만)·미지 라벨 400 no-leak·omitted/all-null byte-equal 회귀. **core & 버전 0.61.0
  무변경**(server-only).

---

## [0.60.0] — 2026-07-01

**`dome` placement dispatch wiring** (MINOR, additive, core byte-equal). ADR 0003
§Status-update. The two-stacked-ring VBAP dome (`place_vbap_dome`, A6 — already in
`roomestim/place/vbap.py`) is now reachable through the public dispatcher:
`run_placement(room, "dome", n_speakers, layout_radius_m, el_deg, ...)` splits the
single `n_speakers` into `n_lower=(n+1)//2` / `n_upper=n//2` (lower ring at 0°,
upper ring tilted by `el_deg`; el_deg ≤ 0 → 30° default), `radius_m = layout_radius_m`. Guard:
`n_speakers >= 6` (two rings of ≥3) with a clear `ValueError` message before the
per-ring `kErrTooFewSpeakers`. Geometry-blind (room argument unused), reported with
the conservative `IRREGULAR` hint and `target_algorithm == "VBAP"` — NOT a calibrated
dome, just two stacked equal-angle rings; no SPL/acoustic claim. All existing dispatch
branches byte-equal (additive branch only).

### Web (앱-티어, roomestim 버전 무관)

dome + coverage 알고리즘과 고-스피커 개수, 원클릭 예시 룸 로더를 웹(Gradio) UI 에 노출
(`roomestim_web/app.py`, additive). 알고리즘 Radio 에 `dome`(2단 스택 링, 높이 레이어,
IRREGULAR, 개수 ≥6) + `coverage`(AVIXA 천장 격자, 방 기하로 개수 자동산출·n/반경/고도각
무시·SPL 보장 없음) 추가; 스피커 개수 Radio 를 `4–16` → `4/6/8/12/16/24/32/48/64` 로 확장
(vbap-ring + dbap 가 24–64 처리 검증됨, 기존 16 상한은 순전히 Radio 선택지 제약이었음).
`algorithm.change` 핸들러가 coverage 선택 시 n/반경/고도각을 `interactive=False` 로 비활성화
(자동 격자라 무시됨을 UX 로 표면화). **"예시 룸 불러오기"** 버튼 추가 — 번들된 실제 lab-room
메쉬(`roomestim_web/data/examples/lab_room.obj`, `tests/fixtures/lab_room.obj` 의 COPY,
web→core 레이어링 유지)를 현재 사이드바 설정으로 `_on_submit` 과 동일 파이프라인에 통과시켜
3D 뷰어·음향 리포트·임머시브 설계 탭을 한 번에 채움. raw exception 미노출(ADR 0038) —
번들 부재/실패 시 generic 한국어 메시지. 시각(육안) 확인은 사람 몫(headless Gradio 렌더 불가).

## [Unreleased]

### Web (앱-티어, roomestim 버전 무관)

rough+ 컨슈머 티어를 웹(Gradio) 경로에 노출 (`roomestim_web`, additive). 코어 패키지가 이미
구현한 rough-tier 워크플로(`MultiviewAdapter` 점군 ingest + 천장 override + snap-to-surfaces)를
consumer-facing `run_pipeline`/UI 에 배선: 점군 업로드(.npz/.xyz/.txt, points-only .ply fallback)·
줄자 천장고 입력(blank/0 → auto)·snap 체크박스. 신규 인자는 키워드 전용 기본값 → 기존 7-positional
호출경로 byte-equal(하위호환). `PLACEMENT_SENSITIVITY_VERDICT.md` 3대 제품요구 착지. web 110p/1s ·
ruff·core mypy(--strict, 64) clean.

**임머시브 설계 탭** (additive, web-track only, core byte-equal). immersive-layout
Phase 4 / ADR 0060. 새 `roomestim_web/immersive_design.py` — 이미 배치된 레이아웃
(`room_state`/`layout_state` 재사용, 재배치 없음)을 P3 4축 trade-off 리포트로 평가·내보내기.
스피커 모델(`BUILTIN_SPEAKER_CATALOG`)·대당 가격(선택, 비우면 unpriced)·구동 전력·목표 SPL·
측정 RT60(양수→measured, blank/0→predicted) 입력 → `roomestim.design.tradeoff.evaluate_layout`
위임(물리 재유도 0, D29 web→core 단방향) → `gr.JSON`(note-first) + 면책 Markdown(report.note +
self-describing `spl_provenance`/`rt60_source`) 렌더. `imm_state` 가 마지막 `tradeoff_to_dict`
결과를 보관해 "트레이드오프 JSON 내보내기" 가 표시된 그대로 직렬화(recompute drift 없음, `_TEMP_REAPER`
cap-8 lifetime). raw exception 미노출(ADR 0038/OQ-45) — 서버 로그 + generic 한국어 메시지.
시각(육안) 확인은 사람 몫(headless Gradio 렌더 불가). web +7p · ruff·core mypy(--strict) clean.

## [0.59.0] — 2026-07-01

**`evaluate-layout` CLI 배선** (MINOR, additive, core byte-equal). ADR 0060 §Status-update.
인터랙티브 임머시브 레이아웃 설계 도구 Phase 3 의 4축 trade-off 리포트
(`roomestim.design.tradeoff.evaluate_layout`)를 CLI 에 노출 — `measure-rt60` 선례를
그대로 미러(parser `_add_evaluate_layout_parser` + handler `_cmd_evaluate_layout` +
main() dispatch). 신규 `roomestim evaluate-layout --in-room ROOM.yaml --in-placement
LAYOUT.yaml [--spec PATH | --spec-model KEY] [--price F] [--drive-w W]
[--target-spl-db DB] [--measured-rt60 S] [--json]`:
- room.yaml + layout.yaml 을 기존 reader 로 로드 → spec 해소(`--spec` datasheet 우선,
  없으면 `--spec-model` 빌트인 estimate; 둘 다 없으면 기본 `generic_surround_compact`;
  `--spec`/`--spec-model` 은 argparse mutually-exclusive group) → 선택 `--price` 는
  `dataclasses.replace` 로 주입 → measured RT60(>0→measured, 부재/<=0→predicted).
- 성공: 사람 모드 = `format_tradeoff_lines` → stdout, 고지 NOTE(`TRADEOFF_REPORT_NOTE`)
  → stderr; `--json` = `tradeoff_to_dict`(note-first) → stdout.
- 전부 core / torch-free(numpy-free) — 놓칠 optional extra 없음 → in-handler `ImportError`
  catch 없음. 누락파일(`FileNotFoundError`)·퇴화 room/placement·<2 스피커·미지의
  `--spec-model` 키·비양수 `drive_w`(`ValueError`)는 main() 의 기존 공유 except 튜플 →
  `error: …` + exit 1. 비양수/NaN `--measured-rt60` 은 (에러가 아니라) model-predicted
  로 silent fallback(help 명시; P4 웹 `_is_finite_positive` 와 동일 시맨틱).
- 신규 `tests/test_evaluate_layout_cli.py`(6 테스트, core 게이트): JSON happy-path(note-
  first + 4축)·`--spec-model … --price 125`(cost 8×125=1000 산술)·measured/predicted 분기·
  사람 모드(stdout trade-off / stderr NOTE)·미지 spec-model·누락 room 파일 plumbing 만 lock
  (정확도 단언 없음 — 합성 물리는 `test_tradeoff.py` 가 이미 검증). **물리 재유도 0** —
  evaluate_layout 위임만. default 776→782p · ruff·mypy(--strict, 69) clean.

## [0.58.0] — 2026-07-01

**임머시브 레이아웃 4축 trade-off 리포트** (MINOR, additive, core byte-equal). ADR 0060.
인터랙티브 임머시브 레이아웃 설계 도구 Phase 3. 신규 `roomestim/design/` 패키지(`tradeoff.py`):
`evaluate_layout`이 이미 ship 된 4축 부품을 단일 `TradeoffReport` frozen dataclass 로 **합성만**
한다 — (1) 직접음장 SPL field(level + `target_spl_db` headroom = `min_spl − target` exact, Phase 1)·
(2) 각도 균일도(panning, Phase 2)·(3) interference proxy(separation, Phase 2)·(4) per-speaker
`price` 산술 합(cost, 견적 아님) + RT60 컨텍스트(`predict_rt60_default` 모델 OR 엔지니어 주입
`MeasuredRT60`/float, `rt60_source` 라벨). **물리 재유도 0** — 기존 frozen score 를 forward,
각 메트릭 caveat 상속. `TradeoffCost`: 전부 priced→`complete=True`, 일부→부분합·`complete=False`,
전무→`total_price=None`. 단일진실원천 `TRADEOFF_REPORT_NOTE`(`reconstruct/_disclosure.py`):
4축 어느 것도 보장된 in-room 측정 아님 → 후보 레이아웃 상대 비교 guidance. Phase 1/2 스타일 재사용
(note-first `tradeoff_to_dict` 중첩 `spl`/`angular`/`interference`/`cost`/`rt60` + `format_tradeoff_lines`
헤더 NO acoustic guarantee). RT60 surface-area 집계는 `roomestim_web/report.py` 패턴 로컬 복제(additive).
독립 code-review(opus) **APPROVE-WITH-FIXES**(0 CRIT/HIGH) 2건 반영: (MEDIUM) `spl_provenance`
(datasheet/estimate/mixed) 를 리포트·dict·format line 에 노출 → 절대 SPL/headroom 주장이
note 없이도 self-describing; (LOW) `_resolve_measured_rt60` 가 float·`MeasuredRT60` 양 분기 모두
finite/>0 검증(`MeasuredRT60` 는 검증 `__post_init__` 없음). numpy-free·`import roomestim`
torch-free 경계 유지. default 754→775p(+21)·web 95p/4s 불변·mypy(--strict, 69) clean·ruff clean.

## [0.57.0] — 2026-06-29

**임머시브 레이아웃 각도 품질 메트릭** (MINOR, additive, core byte-equal). ADR 0059.
인터랙티브 임머시브 레이아웃 설계 도구 Phase 2. 신규 `roomestim/place/immersive_quality.py`:
`angular_uniformity`(청취자 원점 기준 스피커 방향들의 **구면 측지각** 최근접-이웃 gap →
`uniformity = min_nn/max_nn ∈ [0,1]`, dome elevation 완전 반영) + `interference_proxy`
(기하 최소분리 임계 below 쌍 플래그, `n_close_pairs` 정확 카운트 보존 + `close_pairs` 캡 20 +
`close_pairs_truncated` 플래그로 무성 드롭 금지). 단일진실원천 `IMMERSIVE_QUALITY_NOTE`
(`reconstruct/_disclosure.py`): GEOMETRIC only — VBAP/DBAP 패닝 매끄러움 근사일 뿐
radius/level/지향성/room 무시, interference는 comb-filter/심리음향 예측 아닌 RISK proxy, 10°
임계·uniformity-ratio는 미보정 rule-of-thumb. `coverage_overlap.py` 스타일 재사용(note-first
to_dict + format_lines). 독립 code-review(opus) **APPROVE**(0 CRIT/HIGH, 2 MEDIUM+4 LOW 전부
반영: truncation/flag 테스트·worst_pair uniform reword+sorted 정규화·non-finite/antipodal 테스트·
O(n²) doc). REPL 측지각 검증 EXACT(8-ring 45°/uniformity 1.0, 90°/0°/180°). numpy-free·
`import roomestim` torch-free 경계 유지. default 751p/7s(+15)·web 95p/4s·mypy(--strict, 67) clean·ruff clean.

## [0.56.0] — 2026-06-29

**SpeakerSpec 데이터 모델 + 직접음장(direct-field) SPL 엔진** (MINOR, additive, core byte-equal).
ADR 0058. 인터랙티브 임머시브 레이아웃 설계 도구 Phase 1. 신규 `roomestim/spec/` 패키지:
`SpeakerSpec`(datasheet 감도/maxSPL/dispersion/provenance) + `direct_field_spl_db`
(`sensitivity + 10·log10(W) − 20·log10(d) + directivity`; AVIXA −6 dB-at-half-angle 단순화
지향성, 비간섭 에너지 합) + `spl_field_over_area`(listener-area ear-plane SPL 필드,
`coverage_overlap` 샘플링 재사용) + `BUILTIN_SPEAKER_CATALOG`(전부 `estimate` 라벨) +
yaml/json 로더(실 datasheet 주입, default `datasheet`). 단일진실원천
`SPL_DIRECT_FIELD_NOTE`(`reconstruct/_disclosure.py`)가 **양방향 정직 고지**: 반사음장/
room-gain 미모델(과소추정) + `max_spl_db` 미캡·근거리 미모델(과대추정) = upper/lower bound
아닌 free-field direct 추정. 독립 code-review(opus) APPROVE-WITH-FIXES 3 MEDIUM 반영(NaN-aim
무성 on-axis화 차단, 과대추정 방향 고지+`exceeds_max_spl` 가시화, 테스트 23→35). REPL 물리
검증 EXACT(거리2배 −6.02 dB·10×W +10 dB·half-angle −6 dB). numpy-free·`import roomestim`
torch-free 경계 유지. default 736p/7s(+35)·web 95p/4s·mypy(--strict, 66) clean·ruff clean.

## [0.55.0] — 2026-06-29

MoGe-2 (**v2**) 단일-이미지 백엔드 **additive opt-in** (MINOR, additive, EXPERIMENTAL).
ADR 0057 §Status-update. `MoGeAdapter` 에 `model_version: Literal["v1","v2"] = "v1"`
파라미터 추가 — default `"v1"` 경로는 **byte-equal**(`weights` 시그니처가 `str` → `str|None`
로 바뀌었으나 `None`+v1 → 기존 `"Ruicheng/moge-vitl"` 로 해소, keyword-only `__init__` 라
positional 호출 없음, 구 default 를 직접 읽는 provenance/로깅 경로 없음). `model_version="v2"`
선택 시 `_load_model` 이 `moge.model.v2.MoGeModel` 를 import 하고 weights `Ruicheng/moge-2-vitl`
사용. `_infer_points` 무변경 — v2 `infer()` 가 동일 `fov_x` kwarg + `force_projection`/`apply_mask`
기본값을 갖고 `points`/`mask` 키를 반환(설치 소스 확인). `fov_x` 는 keyword 로 전달(v1≠v2
positional 순서 차이에 대한 가드 주석 추가). **GPU smoke 통과**(RTX 2080 Ti): `moge-2-vitl`
from_pretrained 로드 + `infer(fov_x=60)` → `points (H,W,3)` finite·`mask` 정상. **정직 한계**:
MoGe metric 백엔드의 절대 정확도는 여전 **UNVALIDATED**(MOGE_METRIC_NOTE NEGATIVE 입장 v2 에도
유지) — v2 는 experimental opt-in 일 뿐 정확도 주장 없음. default 701p/7s · web 95p/4s ·
mypy strict · ruff clean.

## [0.54.0] — 2026-06-28

Multiview metric scale-anchor **CLI 배선** (MINOR, additive). ADR 0056 §Status-update.
v0.53.0 의 `MultiviewAdapter.scale_anchor`(library-only)를 `ingest`/`run` 에 노출: 신규
`--known-floor-len-m M` 플래그(footprint diameter = **코너-대-코너 대각**, 최장 벽 아님)가
재구성 클라우드를 metric 으로 리스케일한다(`--ceiling-height-m` 와 페어). 공유 헬퍼
`_add_known_floor_len_arg` + `_scale_anchor_for` 를 backend 별 분기(image→`--cam-height`,
multiview→`--known-floor-len-m`, 그 외 None)로 재구성 — image/기존 backend 경로 무변경. 잘못된
length 는 adapter ValueError → CLI rc 1(room.yaml 미기록). +5 CLI 테스트(metric 착지 ~12㎡·CLI
scale-invariance rel 1e-6·no-anchor 회귀·run 출력·bad-length rc≠0). default·web 게이트 GREEN,
mypy strict·ruff clean.

## [0.53.0] — 2026-06-28

MultiviewAdapter metric **scale_anchor** (MINOR, additive). ADR 0056 §Status-update.
VGGT-class 재구성 클라우드는 metric-native 가 아니라 per-room scale 이 ~1–5x 드리프트한다 →
`parse(scale_anchor=ScaleAnchor(type, length_m))` 가 supplied 되면 방을 한 번 추출해 footprint
diameter(`floor_polygon` 코너 최대 pairwise 거리)를 재고, 클라우드를 `length_m/diameter` 로 등방
리스케일 후 재추출한다. `length_m` = footprint diameter = **코너-대-코너 대각**(최장 벽이 아님; 비정방형
방에서 벽을 재면 ~20% mis-scale). **scale-invariance**: 입력 클라우드를 임의 `k` 로 mis-scale 해도
anchored footprint 동일(결과는 입력 scale 에 무의존; *exact* 는 convex default, 양자화 reconstruction
하에선 근사). 가드:
`type ∈ {known_distance, user_provided}`·`length_m` finite>0·degenerate footprint 거부. no-anchor
경로 byte-equal(기존 동작 불변). **scope=library-only**(CLI `_scale_anchor_for` 는 `--backend image`
에만 anchor 제공, multiview CLI 노출은 follow-up). **검증 한계**: anchored 절대치 정확도는 footprint
추출 품질에 종속(under-captured convex-hull 이 diameter bias 가능), real-scan end-to-end 미검증.
default 791p/8s · web 95p/4s · mypy strict · ruff clean.

## [0.52.0] — 2026-06-27

MoGe metric 단일-이미지 백엔드 (MINOR, additive, EXPERIMENTAL). ADR 0057.
`[moge]` extra(MIT 코드·Apache-2.0 가중치, git-only), `--backend moge --experimental`.
**정직 negative**: cuboid-pano eval(n=100)서 HorizonNet 미달(per-DIM median 151.7 vs 58.0 cm,
천장 71.7 vs 13.1 cm); scale-invariant shape-only 비교에서도 미달. cam_h 불필요 + 상업 가중치가
장점이나 HorizonNet `image` 가 계속 documented rough-tier. 기존 backend·default gate byte-equal.

---

## [0.51.1] — 2026-06-27

py.typed PEP 561 마커 + CHANGELOG.md (패키징 위생, ADR 0007, PATCH additive).

---

## [0.51.0] — 2026-06-26

A3 측정(blind) RT60 — 컨트롤드-SIM 벤치(증분 2a) + CLI 배선 (MINOR, additive).
`roomestim measure-rt60 --audio PATH [--json]` CLI 배선 + `tests/eval/blind_rt60_benchmark.py`
controlled-sim accuracy bench (MAPE ~9%, SIM bound only). ADR 0055 §Status-update.

## [0.50.1] — 2026-06-26

v0.50.0 독립 code-review follow-up (PATCH, additive). ADR 0056 §Status-update.

## [0.50.0] — 2026-06-26 — `3edaa02`

A-consumer placement 레버 + multiview 점군 ingest (MINOR, additive). ADR 0056.

## [0.49.0] — 2026-06-24

A3 측정(blind) RT60 — `[audio]` extra (MINOR, additive, library-only 증분 1). ADR 0055.

## [0.48.0] — 2026-06-24

B4 coverage 완전성 densify-to-target (MINOR, additive, opt-in). ADR 0054.

## [0.47.0] — 2026-06-24

B2 coverage-circle overlap 검증 (MINOR, additive, opt-in). ADR 0053.

## [0.46.0] — 2026-06-24

A1 shoebox RT60 엔진 검증 vs dEchorate 측정 GT (MINOR, additive, out-of-gate). ADR 0028 §Status-update.

## [0.45.0] — 2026-06-24

B1 room-aware AVIXA ceiling coverage-grid 배치 (MINOR, additive, opt-in). ADR 0052.

## [0.43.0] — 2026-06-17

RoomPlan CapturedStructure splitter Phase S2+S3 (MINOR, additive). ADR 0050.

## [0.42.0] — 2026-06-17

multi-room RoomCollection 결합 USD export (MINOR, additive). ADR 0049.

## [0.41.0] — 2026-06-17

multi-room RoomCollection Phase 2+3 — per-room offset + 결합 glTF export (MINOR, additive). ADR 0049.

## [0.40.0] — 2026-06-17

multi-room RoomCollection 합성 레이어 Phase 1 (MINOR, additive). ADR 0049.

## [0.39.0] — 2026-06-17

ambisonics 배치 알고리즘 (MINOR, additive, EXPERIMENTAL). ADR 0041.

## [0.38.0] — 2026-06-16

`place`/`run` `--algorithm` 기본값 추가 (MINOR, backward-compatible).

## [0.37.1] — 2026-06-16

proto-bundling packaging fix (PATCH). ADR 0007.

## [0.37.0] — 2026-06-12

floater-robust auto-select footprint (MINOR, additive, opt-in). ADR 0048.

## [0.35.0] — 2026-06-09 — `4554e9a`

polygon-ISM 기하 path-length/TOA 헬퍼 (MINOR, additive, geometry-only). ADR 0040.

## [0.34.0] — 2026-06-09 — `67f98b5`

occupancy footprint 모드 (MINOR, additive, opt-in). ADR 0042.

## [0.33.0] — 2026-06-08 — `15e4b8a`

OQ-38 layout round-trip 라벨 보존 (MINOR). `x_target_algorithm` 키 보존.

## [0.32.0] — 2026-06-08 — `9a7d6c4`

concave footprint CLI 노출 (MINOR). `--floor-reconstruction` 플래그. ADR 0042.

## [0.31.1] — 2026-06-08 — `1b7fbca`

RT60 disclosure 정직성 보정 (PATCH). 수치·디폴트 무변경.

## [0.31.0] — 2026-06-08 — `c6eb9fd`

polygon-ISM geometry-only 이미지소스 enumerator (MINOR, additive). ADR 0040.

## [0.30.2] — 2026-06-08 — `ed9fae2`

candidate B 독립 code-review 후속 (PATCH). ADR 0047.

## [0.30.1] — 2026-06-08 — `3a02d7e`

RoomPlan 다중-floor 무손실 가드 (PATCH, robustness/honesty). ADR 0047.

## [0.30.0] — 2026-06-08 — `d3457c5`

spatial_engine 절대경로 디커플 + PyPI-ready 패키징 (MINOR, additive). ADR 0007.

## [0.29.0] — 2026-06-08 — `5c93da2`

image cam_h scale-honesty surfacing (MINOR, additive). ADR 0045.

## [0.28.0] — 2026-06-07 — `d8c5ea1`

천장 높이 confidence flag — measured-path under-report 가드 (MINOR, additive).

## [0.27.0] — 2026-06-07 — `90d050a`

가구 음향 배선 (MINOR, additive). Phase 2(상용화). ADR 0034.

## [0.26.1] — 2026-06-07 — `29b9edf`

measured 경로 P0 정확성 수정 — robust 천장 평면 추출 (PATCH). ADR 0027 §Status-update.

## [0.26.0] — 2026-06-07 — `16759a3`

.usdz mesh ingest + RT60 정직 고지 (MINOR, additive). ADR 0027.

## [0.25.3] — 2026-06-07 — `5064a8b`

MeshAdapter up-axis(gravity) 자동 정규화 (PATCH). ADR 0027.

## [0.25.2] — 2026-06-05 — `17c1264`

near-horizon 타당성 가드 + per-room 정직성 보정 (PATCH). ADR 0045.

## [0.25.1] — 2026-06-05 — `376bfef`

provenance 를 layout.yaml 아티팩트 경계로 전파 + 실모델 golden 회귀 (PATCH).

## [0.25.0] — 2026-06-04 — `6c9780f`

image→geometry 캡처 백엔드 출하 (MINOR, experimental rough-tier). ADR 0045 / ADR 0046.

## [0.24.0] — 2026-06-02 — `5d18c9c`

비-shoebox floor 재구성 — opt-in concave-hull footprint (MINOR, additive). ADR 0042.

## [0.23.1] — 2026-06-01 — `4cb87e0`

바이노럴 렌더러 HRTF 좌/우 채널 스왑 수정 (PATCH, web-tier correctness).

## [0.23.0] — 2026-05-31 — `fa7c48d`

RIR auralization Phase A (MINOR, additive, web-tier). ADR 0044.

## [0.22.2] — 2026-05-31 — `2eae5eb`

감사 발견 확정결함 PATCH — ISM 적응적 max_order 등 5건.

## [0.22.1] — 2026-05-29 — `66d0f4b`

doc-only PATCH — ADR 0030 §Status-update companion 파일 분리. ADR 0039.

## [0.22.0] — 2026-05-29 — `66d0f4b`

web 공개배포 하드닝 — security audit closure. ADR 0038.

## [0.21.0] — 2026-05-28 — `dfca44d`

edit/predict correctness — `wall_index` frame 단일화 + 음향 입력 검증. ADR 0037.

## [0.20.0] — 2026-05-27 — `8cb693b`

robustness 하드닝 + 전체-엔진 다관점 감사.

## [0.15.0–0.19.0] — 2026-05-17~26

predictor-default 전환(Sabine→ISM); 재질 override; 2D blueprint export; 엔진검증 토글;
object schema; 메시 export; layout round-trip nudge.
ADR 0030 / 0031 / 0032 / 0033 / 0034 / 0035 / 0036.

## [0.14.0] — 2026-05-16 — `d23c118`

D27 HARD WALL CLOSURE — Vorländer α₅₀₀ verbatim citation honesty-leak fallback + ISM 라이브러리 NEW. ADR 0028.

## [0.12-web.2] — 2026-05-16 — `48c1b63`

(web 트랙) `polycam.py` mypy --strict 회귀 + tests/web ruff carryover 정리.

## [0.12-web.1] — 2026-05-16 — `0bef198`

(web 트랙) MeshAdapter 일반화 — `.obj` / `.gltf` / `.glb` / `.ply` 지원. ADR 0027.

## [0.12-web.0] — 2026-05-15 — `cfea9cb`

(web 트랙) Gradio + HF Spaces 웹 데모 출시 + 바이노럴 ISM + HUTUBS HRTF 데모.
ADR 0024 / 0025 / 0026.

## [0.13.0] — 2026-05-13 — `2046681`

Vorländer α₅₀₀ SECOND 재유예; mypy --strict baseline 32개 파일 강제.

## [0.12.0] — 2026-05-12 — `d3c6cc2`

conference Sabine-shoebox residual 특성화. ADR 0021.

## [0.11.0] — 2026-05-11 — `eee3014`

MELAMINE_FOAM enum 추가; lab A11 PASS-gate 복원; CI tense-lint. ADR 0019 / 0020.

## [0.10.x] — 2026-05-09~10

정직성 정정 — `living_room` 제거; Stage-2 schema marker 회귀; ADR 0018 disagreement record.

## [0.7.0–0.9.0] — 2026-05-06~08

WFS CLI + Building_Lobby 분리 + Lecture_2 bracketing + SoundCam substitute.

## [0.5.0–0.6.0] — 2026-05-04~05

ACE 기하 검증 + MISC_SOFT enum + TASLP-MISC 표면 예산.

## [0.1.0–0.4.0] — 2026-05-03~04

초기 부트스트랩 — RoomModel + VBAP/DBAP/WFS + RoomPlan + Octave + Eyring.
