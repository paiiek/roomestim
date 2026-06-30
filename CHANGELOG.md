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
