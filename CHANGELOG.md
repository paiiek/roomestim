# Changelog

All notable changes to roomestim are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Web (앱-티어, roomestim 버전 무관)

rough+ 컨슈머 티어를 웹(Gradio) 경로에 노출 (`roomestim_web`, additive). 코어 패키지가 이미
구현한 rough-tier 워크플로(`MultiviewAdapter` 점군 ingest + 천장 override + snap-to-surfaces)를
consumer-facing `run_pipeline`/UI 에 배선: 점군 업로드(.npz/.xyz/.txt, points-only .ply fallback)·
줄자 천장고 입력(blank/0 → auto)·snap 체크박스. 신규 인자는 키워드 전용 기본값 → 기존 7-positional
호출경로 byte-equal(하위호환). `PLACEMENT_SENSITIVITY_VERDICT.md` 3대 제품요구 착지. web 110p/1s ·
ruff·core mypy(--strict, 64) clean.

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
