---
title: roomestim — spatial audio configurator
emoji: 🏠
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: "6.14.0"
app_file: app.py
pinned: false
---

# roomestim · 공간 음향 구성기

> 스마트폰 방 스캔(Apple RoomPlan / Polycam / 일반 메시) 또는 공개 코퍼스를 입력으로 받아
> 단순화된 `RoomModel` + 알고리즘 인지 스피커 배치 + 엔진 호환 YAML을 생성하는
> **capture-to-config** 도구입니다.

`spatial_engine`에서 그대로 소비할 수 있는 `layout.yaml`을 출력하며,
부속으로 10-entry `MaterialLabel` enum + 옥타브 밴드 흡음 계수를 담은 `room.yaml`도 함께 내보냅니다.

---

## 빠른 시작

### 로컬 실행 — 웹 데모 (Gradio)

```bash
pip install -e ".[dev,web]"   # gradio + plotly + pyroomacoustics + HRTF SOFA 포함
python -m roomestim_web.app   # 또는: python roomestim_web/app.py
# → http://127.0.0.1:7860 접속
```

### Hugging Face Spaces

이 레포 자체가 HF Spaces SDK 호환 레이아웃입니다. 최상위 `app.py` + `requirements.txt` +
README 상단 YAML frontmatter가 Spaces 자동 빌드 트리거 역할을 합니다.
Space에 그대로 push하면 별도 설정 없이 빌드됩니다.

자세한 내용은 [`docs/adr/0024-web-demo-separate-package.md`](docs/adr/0024-web-demo-separate-package.md) 참조.

### CLI 사용 (코어만)

```bash
pip install -e ".[dev]"

# 5개 서브커맨드: ingest / place / export / run / edit
python -m roomestim run \
    --backend roomplan \
    --input tests/fixtures/lab_room.usdz \
    --algorithm vbap --n-speakers 8 --layout-radius 2.0 \
    --out-dir /tmp/roomestim_out

# room.yaml + layout.yaml 재방출 (idempotent); 메시 포맷 export 도 지원
python -m roomestim export \
    --in-room /tmp/roomestim_out/room.yaml \
    --in-placement /tmp/roomestim_out/layout.yaml \
    --format gltf --with-acoustics-sidecar \
    --out-dir /tmp/roomestim_out

# 기본 레인 테스트 (lab / web / e2e 픽스처 제외)
pytest -m "not lab and not web and not e2e" -v

# CI 정직성 lint (honesty-leak 감사)
python scripts/lint_tense.py
```

서브커맨드: `ingest` (capture → RoomModel) · `place` (배치 → layout.yaml) ·
`export` (room.yaml + layout.yaml 재방출, `--format {yaml,usdz,gltf,glb}` +
`--with-acoustics-sidecar` 지원) · `run` (ingest+place+export 합성) ·
`edit` (스피커 nudge + round-trip). `--backend` 는 `{roomplan,polycam,image}` 이며,
`polycam` 은 `MeshAdapter` alias 로 `.obj`/`.gltf`/`.glb`/`.ply` 를 처리합니다.
`image` 는 **실험적 rough-estimate tier**(v0.25.0, [ADR 0045](docs/adr/0045-image-to-geometry-capture-backend.md))
— 단일 equirectangular 파노라마 1장에서 geometry 를 *추정*합니다. **install-grade 아님**
(≤15 cm 정밀은 LiDAR/RoomPlan 한정). `[vision]` extra(`pip install -e ".[vision]"`)·
`--experimental` 게이트·`--cam-height`(스케일 앵커) 필요. 출력은 `provenance=reconstructed`,
재질 `unknown`, 치수는 근사 — CLI 가 `ESTIMATED` 고지를 출력합니다. v0.25.1 부터 이
reconstructed 마커는 (room.yaml / stderr 고지뿐 아니라) 방출된 `layout.yaml` 에도
`x_geometry_provenance` 로 영속하여, 다운스트림 소비자가 산출물 경계에서 rough-tier 출처를 봅니다.

> **정확도(현실 수치)**: 사용자가 준 cam-height(부정확할 수 있음)로는 spike 측정 기준 **per-dimension
> median 벽 오차 35–57 cm, ≤15 cm 도달 11–17%**(주거 PanoContext 35 cm/17%, 사무 S2D3D 57 cm/11%).
> 단, 이 35–57 cm/11–17% 는 **차원별(per-dimension)** 수치입니다 — cold eval(244 real panos, 출하 어댑터)
> 기준 **방 단위(per-room, 양변 모두 정확)** 현실은 약 2.5배 가혹합니다: **per-room median 벽 오차 ≈ 83–95 cm,
> 양변 모두 ≤15 cm 도달은 주거 8% · 사무 3%**뿐입니다. 흔히 인용되는 43–45% ≤15 cm 는 *perfect scale
> anchor* 오라클 천장이며 추론 시점엔 얻을 수 없습니다.
> `--cam-height` 가 모든 치수 스케일을 결정 — **±10 cm 오차 ≈ median 32 cm 벽 오차**이므로 가능한 한
> 실측하세요. v0.25.2 부터 비현실적 재구성(코너 >20 m, 방 ≈40 m 이상 또는 수평선-근처 코너 오검출)은
> 이제 조용히 거대한 방을 내보내지 않고 **명확한 에러로 거부**됩니다(주거 표본 약 2.9%). 매우 큰 방(>~40 m)은
> rough tier 에서 미지원입니다. 비직사각 방은 조용히 사각화되고, 재질 미상이라 음향(RT60) 추정은 시연 등급입니다.
> 신뢰 가능한 설치 측정용이 아니라 **rough pre-scan/sanity** 용도이며 — cold eval 데이터는 (무거운
> catastrophic tail 때문에) 오히려 더 가혹합니다.

```bash
python -m roomestim run --backend image --experimental \
    --cam-height 1.6 --input room_pano.jpg \
    --algorithm vbap --n-speakers 6 --out-dir /tmp/out
```

`--format usdz` 는 `[usd]` extra (usd-core) 가 필요하며, 없으면 친절한 에러로
안내합니다. export/edit 의 엔진 검증은 `--validate-engine PATH` /
`--no-engine-validation` 으로 토글합니다 (ADR 0033).

### 출력 편집 — 스피커 nudge + layout round-trip (v0.18+)

자동 배치된 `layout.yaml` 의 스피커 좌표를 다시 읽어 미세 조정한 뒤 되쓰는
경로 (ADR 0036). 구면 Δ (az/el/dist) 또는 직교 Δ (x/y/z) 중 하나만 입력한다
(동시 입력 시 ValueError).

```bash
# 채널-0 스피커를 방위 5° / 고도 3° 만큼 미세 조정
python -m roomestim edit \
    --in-placement /tmp/roomestim_out/layout.yaml \
    --speaker 0 --daz 5 --del-deg 3 \
    --out-dir /tmp/roomestim_edit
```

`roomestim edit` 는 read → nudge → 엔진 재검증 (collector) → write + unified
diff 를 수행한다. 고도각 delta 플래그는 항상 `--del-deg` 다 (`--del` 은 Python
예약어와 충돌). 엔진 검증은 `--validate-engine PATH` / `--no-engine-validation`
토글로 제어한다 (export 와 동일, ADR 0033). 웹 UI 에서는 "스피커 조정" 탭에서
채널을 고른 뒤 Δ 를 입력하고 **적용** 을 누르면 3D 뷰어가 재렌더된다.

CLI `edit` 서브커맨드는 스피커 nudge 만 노출한다. 그 밖의 편집 —
표면 재질 교체 (`evolve_room_material` / `evolve_room_materials_bulk`),
오브젝트 add·remove (`evolve_room_add_object` / `evolve_room_remove_object`),
임의 surface/room/placement 필드 갱신 (`evolve_surface` / `evolve_room` /
`evolve_placement`) — 은 `roomestim/edit.py` 의 `evolve_*` Python API 로
제공된다 (모두 immutable copy 반환). 재질을 바꾸면 음향 recompute 가
트리거된다 (ADR 0031).

round-trip 충실도는 Level 1 (구조 동치): position / channel / regularity /
WFS 메타 / aim 방향 ({VBAP, WFS}) 이 보존된다. `notes` 와 per-speaker `id`,
그리고 DBAP/AMBISONICS 의 `target_algorithm` 라벨은 보존되지 않는다 (OQ-37 /
OQ-38). byte-equal (comment/key-order/float-format 완전 보존) 은 비-목표 (D51).

---

## 현재 상태 (2026-06-07)

| 버전 | 날짜 | 커밋 | 주요 변경 |
|---|---|---|---|
| **v0.27.0** | 2026-06-07 | (uncommitted) | 가구 음향 배선 (MINOR, additive) — **Phase 2(상용화)**: `ObjectKind` 에 음향관련 가구 `sofa`/`bed`/`table`/`storage` 추가. 가구는 column 과 동일한 **free-standing box**(`_objects_to_surfaces` 5-face 분해)로 RT60 흡음 예산에 반영되고, RoomPlan sidecar `_extract_objects` 가 해당 `CapturedRoomObject` 카테고리(sofa/couch·bed·table/desk·storage/cabinet/shelf/wardrobe/refrigerator)를 매핑(chair·toilet 등은 의도 제외). 단일 진실원천 `FREESTANDING_OBJECT_KINDS`/`WALL_ATTACHED_OBJECT_KINDS`(model.py) 를 predictor·gltf·usd·room.yaml reader·schema 가 공유. 재질=**대표 추정**(soft→`MISC_SOFT` 0.40, hard wood→`WOOD_FLOOR` 0.10), bbox-solid 가정의 정직한 ESTIMATE(`ace_challenge` furniture-budget 와 동일 철학). **기존 픽스처 RT60 byte-equal**(현재 어떤 adapter 도 가구 object 미방출 → 순수 additive). `proto/room_schema.v0_2.draft.json` 가구 enum+oneOf 브랜치 확장(schema-validated write↔read 라운드트립 핀). default 396p/3s·web 86p/3s·ruff/mypy EXIT0. (D95 / Phase 2). |
| **v0.26.1** | 2026-06-07 | (uncommitted) | measured 경로 P0 정확성 수정 — robust 천장 평면 추출 (PATCH, 정확성 수정·정확도 개선 아님) — 종전 full-extent(`y_max−y_min`) 천장 추출이 실 ARKit 스캔에서 floor-아래/ceiling-위 outlier(가구·노이즈)를 잡아 천장을 **+0.27~1.34 m 과대평가**(5-scene 0/5 ±10 cm 이내)하던 P0 를, Y-축 밀도 히스토그램의 floor/ceiling **평면** 추출(`_robust_floor_ceiling_y`)로 수정 — 독립 **Faro 레이저 GT** 대비 scene 42444946 **3.02 m vs 3.03 m (~1 cm)** 실증. README ±10 cm "독립 GT 검증 현황" 정직 고지 추가(천장만 실증; 벽/footprint 는 미검증), lab 회귀 assertion 강화(≥0.10 m outlier-rejection margin). (D94 / [ADR 0027](docs/adr/0027-mesh-format-generalisation.md) §Status-update-2026-06-07 (v0.26.1)). |
| **v0.26.0** | 2026-06-07 | (uncommitted) | .usdz mesh ingest + RT60 정직 고지 (MINOR, additive) — **Phase 1**: `.usdz`(USDZ) 지오메트리 ingest 를 `MeshAdapter` 에 추가(`[usd]` extra=usd-core; `pxr` 경유) — **default-prim 스코프** instance-proxy 순회(concrete `def`-prototype 이중계수 방지·round-3 HIGH), `metersPerUnit`→m 스케일(cm-unit USDZ 정합·round-2 HIGH), `upAxis` 힌트 교차검증, 천장 타당성 절대상한(`ROOMESTIM_MAX_CEILING_M`, 기본 20 m); v0.25.3 up-축(gravity) 정규화 재사용. **Phase 0c**: RT60 honesty labeling — 단일 진실원천 `_disclosure.RT60_DISCLOSURE`/`RT60_MODEL_NAME`, `RT60Prediction.disclosure` property, 음향 사이드카(usd/gltf)에 additive `disclaimer`/`acoustics_model`/`materials_status` 필드(**수치 불변**), README RT60 "정직 고지(모델 추정, 측정 아님 / guidance)" 블록. (D92 [0c] / D93 [Phase 1] / [ADR 0027](docs/adr/0027-mesh-format-generalisation.md) §Status-update-2026-06-07 (v0.26.0)). |
| **v0.24.0** | 2026-06-02 | (uncommitted) | 비-shoebox floor 재구성 — opt-in concave-hull footprint (MINOR, additive core feature) — 죽은 `floor_polygon_from_mesh` stub 을 `shapely.concave_hull`(신규 의존 0; `ratio=0.4`/`simplify=0.05`)로 구현; `MeshAdapter(floor_reconstruction="convex"\|"concave")` 생성자 인자 + `ROOMESTIM_MESH_FLOOR_RECON` env(precedence arg>env>convex). default convex 는 이전 동작과 **byte-equal**(회귀 핀), concave 는 degeneracy 시 convex+UserWarning fallback. **정직성(ICL-NUIM n=1 검증)**: concave/occupancy 모드는 shipped default(ratio=0.4 / min\_count=3)에서 **re-entrant 코너(notch)를 회복하지 못함** — convex +10.1%, concave +8.8%, occupancy +8.6% (GT +5.5% concavity 대비 모두 과대); notch 회복은 비-default·비-자동보정 knife-edge 임계값(min\_count=5)에서만 관측됨(+0.5%). concave/occupancy 는 convex 대비 **볼록 과대읽기를 소폭 감소**시키는 효과가 있으나 re-entrant 코너 보존을 보장하지 않음; CLI/web user-facing default 불변. (D82 / [ADR 0042](docs/adr/0042-live-mesh-corner-extraction.md) §Status-update-v0.24.0; OQ-13e 부분진척, 실측-메시 ≤10 cm 검증은 SoundCam access 대기로 OPEN 유지). |
| **v0.23.1** | 2026-06-01 | (uncommitted) | 바이노럴 렌더러 HRTF 좌/우 채널 스왑 수정 PATCH (web-tier correctness) — 렌더러가 pipeline 관례 azimuth(RIGHT=+az)를 SOFA 관례(LEFT=+az)로 변환 없이 `nearest_hrir` 에 넘겨 모든 측방 성분이 L↔R 거울반전되던 결함. 단일권위 `roomestim/coords.py:pipeline_to_ambix`(az→−az) 경유로 수정, 두 렌더 경로(`render_binaural_demo` / `synthesize_brir`) 동일 적용; diffuse late tail 무영향 (D80). dataset-grounded ILD 회귀테스트 2종 추가. core 무변경(회귀 0). |
| **v0.23.0** | 2026-05-31 | (uncommitted) | RIR auralization Phase A (MINOR, additive, web-tier 한정·신규 패키지 0) — image-source 직접 조립 early per-band mono-RIR + filtered-noise late tail + 2-채널 convolvable BRIR (D79 / [ADR 0044](docs/adr/0044-rir-auralization-design.md) §Status-update-v0.23.0; OQ-48 CLOSED; OQ-47/49/51 status-update). `roomestim_web/rir.py` + `roomestim_web/late_reverb.py` + `binaural.synthesize_brir`; RT60 단일 진실원천 `predict_rt60_default_per_band` 6-band 유지; per-band energy-continuity splice. core 무변경(회귀 0). |
| **v0.22.2** | 2026-05-31 | (uncommitted) | 감사 발견 확정결함 PATCH — ISM 기본 predictor 저흡음 적응적 max_order(Eyring 하한 불변식, D74 / [ADR 0030](docs/adr/0030-predictor-default-switch-status-updates.md) §Status-update-v0.22.2); 비-shoebox binaural DOA 축 스왑 + extrusion 렌더러 경로 활성화(D75); CLI ValidationError/YAMLError 포착(reader 가 ValueError 로 wrap, D76); `run` engine-validation 토글(D77); 자기교차 floor 거부(D78). MINOR-2(OQ-30)는 비수정. |
| **v0.22.1** | 2026-05-29 | `66d0f4b`* | doc-only PATCH — ADR 0030 §Status-update 블록을 companion 파일([`0030-...-status-updates.md`](docs/adr/0030-predictor-default-switch-status-updates.md))로 분리 (OQ-39 CLOSED; D73 / [ADR 0039](docs/adr/0039-adr-status-update-split-mechanism.md) NEW); README `__schema_version__` 마커 `0.1-draft`→`0.2-draft` 정직성 정정. (\*릴리즈 노트는 v0.22.0 커밋 위에 작성됨) |
| v0.22.0 | 2026-05-29 | `66d0f4b` | web 공개배포 하드닝 — security audit closure (D71/D72 NEW; OQ-45 CLOSED; OQ-46 NEW; [ADR 0038](docs/adr/0038-input-resource-bounds.md) NEW) |
| v0.21.0 | 2026-05-28 | `dfca44d` | edit/predict correctness — `wall_index` frame 단일화 + 음향 입력 검증 (D68/D69/D70 NEW; OQ-43/44 CLOSED; [ADR 0037](docs/adr/0037-wall-index-reference-frame.md)) |
| v0.20.0 | 2026-05-27 | `8cb693b` | robustness 하드닝 + 전체-엔진 다관점 감사 (D65/D66/D67 NEW; OQ-42/21 CLOSED) |
| v0.15.0–v0.19.0 | 2026-05-17~26 | — | predictor-default 전환(Sabine→ISM, [ADR 0030](docs/adr/0030-predictor-default-switch.md)); 재질 override([ADR 0031](docs/adr/0031-material-override-policy.md)); 2D blueprint export([ADR 0032](docs/adr/0032-blueprint-2d-export.md)); 엔진검증 토글([ADR 0033](docs/adr/0033-engine-validation-toggle.md)); object schema([ADR 0034](docs/adr/0034-object-schema.md)); 메시 export([ADR 0035](docs/adr/0035-mesh-export-policy.md)); layout round-trip nudge([ADR 0036](docs/adr/0036-layout-round-trip-nudge.md)) |
| **v0.14.0** | 2026-05-16 | `d23c118` | D27 HARD WALL CLOSURE — Vorländer α₅₀₀ verbatim citation honesty-leak fallback (path γ, [ADR 0028](docs/adr/0028-hardwall-closure-and-ism-adoption.md)); ISM 라이브러리 NEW (shoebox 전용, `roomestim/reconstruct/image_source.py` 603 LoC); conference ISM/Sabine = 5.05 → 시그너처 reframe; ACE Office_1 ratio = 2.01 → v0.15+ predictor-default 전환 강제 |
| v0.12-web.2 | 2026-05-16 | `48c1b63` | (web 트랙) `polycam.py` mypy --strict 회귀 + tests/web 9개 ruff carryover 정리 |
| v0.12-web.1 | 2026-05-16 | `0bef198` | (web 트랙) `MeshAdapter` 일반화 — `.obj` / `.gltf` / `.glb` / `.ply` 지원 ([ADR 0027](docs/adr/0027-mesh-format-generalisation.md)); `PolycamAdapter`는 deprecated alias로 보존 |
| v0.12-web.0 | 2026-05-15 | `cfea9cb` | (web 트랙) Gradio + HF Spaces 웹 데모 출시 ([ADR 0024](docs/adr/0024-web-demo-separate-package.md)); 바이노럴 ISM + HUTUBS HRTF 데모 ([ADR 0025](docs/adr/0025-binaural-demo-stack.md) / [ADR 0026](docs/adr/0026-hrtf-dataset-selection.md)) |
| v0.13.0 | 2026-05-13 | `2046681` | Vorländer α₅₀₀ SECOND 재유예 (D27 cadence); mypy --strict baseline 32개 파일 강제 |
| v0.12.0 | 2026-05-12 | `d3c6cc2` | conference Sabine-shoebox residual 특성화 ([ADR 0021](docs/adr/0021-sabine-shoebox-residual-study.md); ratio 1.128 ambiguous) |
| v0.11.0 | 2026-05-11 | `eee3014` | MELAMINE_FOAM enum 추가 ([ADR 0019](docs/adr/0019-melamine-foam-enum-addition.md)); lab A11 PASS-gate 복원 (+2.4% rel_err); CI tense-lint ([ADR 0020](docs/adr/0020-ci-lint-tense-policy.md)) |
| v0.10.x | 2026-05-09~10 | — | 정직성 정정 — `living_room` 제거; Stage-2 schema marker 회귀; ADR 0018 disagreement record |
| v0.7.0–v0.9.0 | 2026-05-06~08 | — | WFS CLI + Building_Lobby 분리 + Lecture_2 bracketing + SoundCam substitute |
| v0.5.0–v0.6.0 | 2026-05-04~05 | — | ACE 기하 검증 + MISC_SOFT enum + TASLP-MISC 표면 예산 |
| v0.1–v0.4.0 | 2026-05-03~04 | — | 초기 부트스트랩 — RoomModel + VBAP/DBAP/WFS + RoomPlan + Octave + Eyring |

> v0.14 가 **D27 cadence의 세 번째 사이클이자 HARD WALL CLOSURE**였습니다.
> Vorländer 2020 §11 / Appendix A "melamine foam panel" verbatim citation은
> path γ (honesty-leak fallback, 다중 출처 envelope 채택)로 닫혔습니다.
> v0.15.0 에서 shoebox default RT60 예측기가 Sabine → ISM 으로 전환되었고
> ([ADR 0030](docs/adr/0030-predictor-default-switch.md), D26 forbidden-indefinite-deferral
> 트리거 충족), 이후 v0.16~v0.22 사이클에서 export/edit 기능 확장과 robustness·security
> 하드닝이 이어졌습니다. 위 표는 최신 행만 상세히, 이전 행은 요약으로 보존합니다.
> 결정 맥락은 [`docs/adr/0028-hardwall-closure-and-ism-adoption.md`](docs/adr/0028-hardwall-closure-and-ism-adoption.md),
> [`docs/adr/0030-predictor-default-switch.md`](docs/adr/0030-predictor-default-switch.md),
> 그리고 [`RELEASE_NOTES_v0.22.1.md`](RELEASE_NOTES_v0.22.1.md) 를 참조하세요.

---

## 입출력

### 입력 — 방 스캔 파일

| 포맷 | 백엔드 | 비고 |
|---|---|---|
| `.usdz` | Apple RoomPlan / Reality Composer | LiDAR 메트릭 스케일; JSON sidecar 포함 권장 ([ADR 0001](docs/adr/0001-capture-backend-priority.md)) |
| `.obj` | 범용 wavefront | 가장 호환성이 높음 ([ADR 0027](docs/adr/0027-mesh-format-generalisation.md)) |
| `.gltf` / `.glb` | Khronos glTF | web / Three.js / Unity 워크플로우 |
| `.ply` | Stanford PLY | 메시 OK; 점군은 자동 메싱되지 않음 |

좌표는 **미터 (m)** 스케일을 권장합니다. 단위가 다른 경우 `--scale-anchor` 옵션으로 보정해야 합니다.
공개 코퍼스 경로로 ACE Challenge (Eaton 2016 TASLP) + SoundCam (Stanford NeurIPS D&B)도 지원합니다 —
자세한 픽스처 구성은 [`tests/fixtures/`](tests/fixtures/) 참조.

### 출력

- `room.yaml` — 10-entry `MaterialLabel` enum + per-band 흡음 계수
- `layout.yaml` — `spatial_engine/proto/geometry_schema.json` 검증을 통과한 스피커 좌표
- `setup_card.pdf` — 사용자가 인쇄해서 설치할 수 있는 안내 PDF (per-speaker 좌표 + 각도)
- `binaural_demo.wav` — HUTUBS HRTF + pyroomacoustics ISM으로 합성한 30초 바이노럴 데모
- **convolvable BRIR (auralization Phase A, v0.23.0)** — `roomestim_web.binaural.synthesize_brir` 가 geometry + 6-band 재질 + ISM 만으로 2-채널 임펄스 응답을 합성한다 (image-source 직접 조립 early + filtered-noise late tail + 2-HRIR decorrelation; RT60 단일 진실원천 = `predict_rt60_default_per_band`). diffuse tail 은 *plausible* 수준으로 기술하며 지각충실은 미검증(OQ-47). [ADR 0044](docs/adr/0044-rir-auralization-design.md)
- `acoustic_report.json` — Sabine / Eyring / ISM RT60 + 옥타브 밴드별 결과
- **3D 뷰어 (Plotly)** — 방 + 스피커 배치 인터랙티브 시각화
- ZIP 아카이브 — 위 산출물 일괄 다운로드

---

## 파라미터 레퍼런스 (웹 UI / CLI 공통)

### `algorithm` — 알고리즘

| 값 | 정식 명칭 | 출처 | 권장 스피커 수 | 특징 |
|---|---|---|---|---|
| `vbap` | Vector-Based Amplitude Panning | Pulkki 1997 | 4–16 | 가장 표준; 3-스피커 트라이앵글로 가상 음원을 패닝; sweet-spot 의존도 높음 |
| `dbap` | Distance-Based Amplitude Panning | Lossius 2009 | 4–24 | 비대칭 / 불규칙 스피커 배치 허용; sweet-spot 자유롭지만 sharp localization 약함 |
| `wfs` | Wave Field Synthesis | Berkhout 1988 | 8–16+ | 균등 간격 직선·곡선 어레이; wave front 재구성; 가장 정확하지만 하드웨어 요구가 큼 |

알고리즘 우선순위와 채택 배경은 [ADR 0003](docs/adr/0003-placement-algorithm-priority.md) 참조.
Ambisonics는 stub 상태로 v0.3+ 일정에서 보류 중입니다.

### `n_speakers` — 스피커 개수

- 권장값: **4 / 6 / 8 / 12 / 16**
- VBAP / DBAP는 4–16 모두 잘 동작합니다.
- WFS는 spatial-aliasing 주파수(`x_wfs_f_alias_hz`)를 합리적인 대역으로 유지하려면 8개 이상이 권장됩니다.

### `layout_radius_m` — 레이아웃 반경 (m)

- 청취자 중심에서 각 스피커까지의 거리(미터).
- 일반 거실 — **1.5–2.5 m**
- 스튜디오 / 모니터링 룸 — **0.5–1.5 m**
- 큰 강당 — **2.5–3.0 m+**
- 웹 UI 슬라이더 범위는 0.5–3.0 m입니다. 그 이상이 필요하면 CLI로 직접 지정해주세요.

### `elevation` — 고도각 (도, °)

- 스피커 고도각 — `0°`: 귀 높이 평면, `+30°`: 천장 방향, `−20°`: 바닥 방향.
- 가장 흔한 값은 `0°` 또는 `±15°` (height-channel용).
- 음악 감상 — `0°` 가 표준.
- 영화 / 게임 — height-channel 효과를 위해 `+30°` 까지 사용 (Atmos 스타일).

### `octave_band` — 옥타브 밴드 흡음 토글

- **켜짐 (권장)**: 6-밴드 (125 / 250 / 500 / 1 k / 2 k / 4 k Hz) 흡음 계수로 Sabine / Eyring / ISM 모두 계산합니다.
  정확도가 가장 높고, 계산 비용은 약간 증가합니다.
- **꺼짐**: 단일-밴드 500 Hz Sabine만 사용합니다. 빠르지만 broadband 정확도가 떨어집니다.
- 옥타브 밴드 도입 결정은 [ADR 0008](docs/adr/0008-octave-band-absorption.md) 참조.

### 지원 메시 포맷 정리

| 확장자 | 표준 | 권장 사용처 |
|---|---|---|
| `.usdz` | Pixar USD (Apple 확장) | iPhone Pro RoomPlan, AR Quick Look |
| `.obj` | Wavefront OBJ | 가장 폭넓은 도구 호환 |
| `.gltf` / `.glb` | Khronos glTF 2.0 | 웹 / Three.js / Unity |
| `.ply` | Stanford PLY | 학술 / 포인트 클라우드 (메시화는 외부 도구 선행) |

메시 포맷 일반화 결정은 [ADR 0027](docs/adr/0027-mesh-format-generalisation.md) 참조.

---

## 음향 모델

### RT60 예측기

| 예측기 | 공식 / 출처 | 사용 시점 | 상태 |
|---|---|---|---|
| **ISM** | Image-Source Method, Allen & Berkley 1979 + Lehmann-Johansson 2008 | **shoebox default** — 가장 물리적, 가장 비쌈 | v0.14+ 도입 ([ADR 0028](docs/adr/0028-hardwall-closure-and-ism-adoption.md)); v0.15+ default ([ADR 0030](docs/adr/0030-predictor-default-switch.md)) |
| **Eyring** | `T₆₀ = 0.161 · V / (−S · ln(1 − ᾱ))` | **non-shoebox default fallback** | v0.4+ ([ADR 0009](docs/adr/0009-eyring-parallel-predictor.md)) |
| **Sabine** | `T₆₀ = 0.161 · V / Σ(αᵢ · Sᵢ)` | 저-흡음 발산 한계; side-by-side 비교용 | v0.1+ |
| **Sabine (octave)** | 동일 공식, 6-밴드 αᵢ | 옥타브 분해가 필요할 때 ([D8](.omc/plans/decisions.md)) | v0.3+ |

v0.15.0 부터 `predict_rt60_default` 는 **shoebox 방이면 per-band ISM (max_order=50)**
을, non-shoebox 방이면 Eyring 을 default 로 사용합니다 (ADR 0030 §A cascade).
Sabine 은 더 이상 default 가 아니며 비교용 bar/JSON 필드로만 남습니다. 전환 근거는
conference room ISM/Sabine = 5.05, ACE Office_1 = 2.01 의 systematic Sabine 과소추정이
D26 forbidden-indefinite-deferral 절을 발화시킨 데 있습니다 (ADR 0030 §Context).

실측 예 (`tests/fixtures/lab_room.obj`, V≈40 m³): default(ISM) RT60@500 Hz = 1.594 s,
Sabine = 1.238 s, Eyring = 1.193 s. 이 단일-밴드 경로(`predict_rt60_default`)의 rationale
문자열은 `"shoebox L=4.00 W=4.00 H=2.50: ISM (max_order=50)"` 형태이며, per-octave 변형
(`predict_rt60_default_per_band`)은 `"... per-band ISM (max_order=50)"` 로 기록됩니다.

**polygon ISM 은 여전히 미래 과제** (OQ-23) 로, non-shoebox 방은 ISM 대신 Eyring 으로
silently route 됩니다 (ADR 0030 §Consequences). polygon ISM 이 landing 하면
cascade 의 Eyring fallback 항목을 polygon ISM 으로 승격하는 것이 reverse-criterion 입니다.

> **정직 고지 (RT60 = 모델 추정, 측정 아님).** RT60 은 geometric-acoustics MODEL
> (Sabine / Eyring / ISM) 추정값으로 *guidance* 이며, 보증된 허용오차로 검증된 음향
> *측정값이 아닙니다*. 관측된 모델 오차는 measured ACE RT60 대비 평균 +0.16 s, 최대
> ~±1.4 s (Building_Lobby +1.4 s 는 coupled-space 로 제외, Lecture_2 −0.9 s; 근거
> [`docs/perf_verification_e2e_2026-05-08.md`](docs/perf_verification_e2e_2026-05-08.md)).
> roomestim 은 재질을 추론하지 않습니다 — 전부 UNKNOWN/추정/하드코딩이므로 음향은
> indicative 수준입니다. 단일 진실원천 disclosure 문자열은
> `roomestim/reconstruct/_disclosure.py` 의 `RT60_DISCLOSURE` 이며 export
> `.acoustics.json` sidecar 의 `disclaimer` 필드로도 동봉됩니다.
>
> **위 ~±1.4 s 는 ACE mixed-material 의 *중앙값* 규모이지 worst case 가 아닙니다.**
> 독립 GT(**U-Rochester RIR** dataset, figshare **48711175**, **CC-BY 4.0**, 14개 방
> 측정 RT60; raw WAV 은 repo 에 미포함, 아래는 파생 측정값) 대비, 음향적으로 **처리된
> (treated/absorptive)** 방에 **DEFAULT/unknown 재질**을 가정하면 예측기는 **체계적으로
> 과대예측(systematic over-prediction)** 합니다 — 직사각형 n=7 기준 **median +1.35 s
> (+326%), 최악 +4.6 s**(combined shoebox-feed 는 큰 hall 에서 최대 **+8.9 s**), 오차는
> **한쪽(양수)으로 치우칩니다**. 즉 unknown 재질 하에서는 오차가 **RT60 규모 그 자체**
> (median ≈ +1.3–2.9 s, 최대 ~+9 s)이며, ±1.4 s / ±20% 수치는 **재질 regime 이 대략
> 알려졌을 때(ACE-유사 mixed 방)에만** 적용됩니다. (U-Rochester 는 treated-room 편향이
> 강한 high-mismatch tail 표본이므로, 이는 "roomestim 이 항상 +326% 틀린다" 가 아니라
> "흡음 처리된 방에 default/reverberant 재질을 가정했을 때" 의 오차 상한 성격입니다.)

### `MaterialLabel` enum — 10개 항목

| Label | α₅₀₀ | 출처 |
|---|---|---|
| `WALL_PAINTED` | 0.05 | Vorländer 2020 §11 / Appx A |
| `WALL_CONCRETE` | 0.02 | " |
| `WOOD_FLOOR` | 0.10 | " |
| `CARPET` | 0.30 | " |
| `GLASS` | 0.04 | " |
| `CEILING_ACOUSTIC_TILE` | 0.55 | " |
| `CEILING_DRYWALL` | 0.10 | " |
| `UNKNOWN` | 0.10 | broadband 0.10 fallback ([D3](.omc/plans/decisions.md)) |
| `MISC_SOFT` | 0.40 | TASLP MISC 표면 예산 ([ADR 0011](docs/adr/0011-misc-soft-enum.md) / [ADR 0013](docs/adr/0013-taslp-misc-soft-surface-budget.md)) |
| `MELAMINE_FOAM` | 0.85 | path γ honesty-leak fallback — multi-source envelope ([ADR 0019](docs/adr/0019-melamine-foam-enum-addition.md) + [ADR 0028](docs/adr/0028-hardwall-closure-and-ism-adoption.md)) |

옥타브 밴드별 계수는 `roomestim/model.py` 의 `MaterialAbsorptionBands` 에서 확인할 수 있습니다.
모든 행은 "representative typical room-acoustics" 표기이며 verbatim Appendix A 행은 아닙니다 (citation policy OD-4).

### 좌표계

- **Origin**: 청취자 위치 (또는 listener-area centroid).
- **x** = right, **y** = up, **z** = front. 단위는 미터.
- **az_deg**: 방위각, **RIGHT = +az_deg**. 범위 (−180, +180].
- **el_deg**: 고도각, **UP = +el_deg**. 범위 [−90, +90].
- 자세한 컨벤션은 sibling 레포의 `spatial_engine/docs/coordinate_convention.md` 참조.

---

## 정밀도 목표 (NOT BIM precision)

| 항목 | 허용 오차 |
|---|---|
| 벽 위치 | ±10 cm |
| 스피커 각도 | ±2–5° |
| RT60 (default 예측기) | ±20% *(재질 regime 이 대략 알려졌을 때만; 아래 각주)* |

\* **RT60 ±20% 단서:** 이 ±20% 는 재질 regime 이 대략 알려진 ACE-유사 mixed 방에서만
성립합니다. **unknown/default 재질**에서는 오차가 한 자릿수 더 커서 — 흡음 처리된 방에
default 재질을 가정하면 **+160…+826%**(U-Rochester, figshare 48711175 / CC-BY 4.0,
median +329%) — 오차가 **RT60 규모 그 자체**(median +1.3–2.9 s, 최대 ~+9 s)이며
**과대예측으로 편향**됩니다. 자세한 내용은 위 RT60 정직 고지 블록 참조.

캡처 노이즈가 dominant 한 오차 원인이며, sub-cm 정밀도는 명시적인 reverse goal입니다.
이 정밀도 목표를 위반하면 lab A11 / ACE A11 게이트가 실패합니다.

**독립 GT 검증 현황 (Phase 0b, 2026-06-07).** 위 ±10 cm 는 설계 **목표**입니다. 독립 GT(ARKitScenes **Faro 레이저 스캔**, roomestim 로직과 무관한 별도 센서) 대비 실측 검증은 현재 **천장 높이**만 커버합니다: 기존 full-extent(`y_max−y_min`) 추출이 실 ARKit 스캔에서 천장을 **+0.27~1.34 m 과대평가**(5-scene 0/5 가 ±10 cm 이내)하던 P0 를 robust floor/ceiling 평면 추출로 수정했고(**Phase 0b 국소 sub-scan** 기준 scene 42444946 = **3.02 m vs Faro GT 3.03 m, ~1 cm** — 이 scene 은 전체-건물 레이저 GT 가 모호해 5-scene 헤드라인에서는 제외되고 국소 crop 으로만 매칭), 이로써 **천장 높이는 가장 깨끗한 단일-방 scene 들에서 few-cm 수준으로 검증**되었습니다. 다만 이는 **±10 cm 의 포괄적 실증이 아닙니다**: 신뢰할 만한 단일-방 레이저 GT 를 갖는 scene 은 **n=2–3 개로 작고**(2/3 가 ±10 cm 이내; 5-scene 헤드라인의 가장 깨끗한 2개 scene 42444966·42445021 가 각 ~1.0 cm·~3.6 cm), 표본에 남겨둔 한 scene(42445429)은 **~6 m multi-floor venue 에서 ~31.8 cm 오차**를 보입니다(레이저 GT 자체의 mezzanine/two-floor 혼입 불확실성 가능). **벽 위치/footprint ±10 cm 는 (아래 3DSES clean-laser extraction 결과를 제외하면) 실 캡처 파이프라인에 대해 독립 GT 로 미검증 상태로 남습니다 — Faro 로는 검증을 *시도*했고 그 결과 현 ARKit↔레이저 데이터로는 ill-posed 임을 확인했습니다.** Faro 레이저 GT 는 단일 방이 아니라 **건물 한 층 전체(≈72×102 m, ~7000 m², 벽 길이 ~856 m, 수직 ~24.6 m 의 multi-floor)**의 스캔이고 ARKitScenes 는 ARKit↔레이저 정합 변환을 제공하지 않으므로(`_pose.txt` 는 레이저 스캔들 사이 정합만 — `raw/README.md`), 단일 방(둘레 ~31 m, 벽 길이의 ~3.6%)의 footprint 를 비교하려면 방을 레이저 venue 좌표계로 **registration** 해야 합니다. **천장 높이는 방을 venue 내에서 위치시키지 않아도 검증됩니다** — 그것은 floor↔ceiling 분리라는 *수평위치-불변 scalar* 라 floor+ceiling 평면을 담은 임의의 국소 sub-scan 으로 복원되기 때문입니다(검증에 쓴 3.03 m GT 는 전체 multi-floor venue 가 아니라 방과 같은 층의 국소 영역에서 나온 값). 반면 **footprint 는 방을 수평으로 *localization* 해야 하며 이는 초기추정 없이는 ill-posed** 입니다: open3d **FPFH+RANSAC** 전역정합(2회)과 중력제약 **2D yaw-sweep FFT** 정합 3가지 방법 모두 신뢰 임계 미달(2D 피크 margin ≈1.00×, RANSAC fitness ~0.2)로 방을 확신 있게 배치하지 못했습니다 — 비슷한 직사각형 방이 다수인 대형 multi-room 공간에서 예상되는 결과입니다. 따라서 잘못된 정합으로 *허위* ±cm 수치를 만드는 대신 footprint 를 **미검증**으로 정직하게 둡니다. 종결 경로: (a) 방 단위로 크롭된 레이저 또는 알려진 ARKit↔레이저 대응/seed 확보, (b) 작은 단독 공간을 ARKit 으로 캡처한 레이저 scene, (c) 근사 위치 seed → ICP refine(단, seed 가 독립적으로 정당화돼야 cherry-pick 아님). 도구: `test/full_eval` 외부 spike 디렉터리의 `footprint_validate.py`·`footprint_register.py`·`footprint_register2d.py`. 또한 roomestim 의 **기본(convex-hull) footprint 경로**는 비-convex 방에서 구조적으로 과대추정되며(이 경우 정합 잔차에 센서오차와 혼재; opt-in `floor_reconstruction="concave"` 는 별도 존재), 종전 "lab A11 게이트" 의 GT 는 roomestim 로직 파생이라 tautological 이었음을 유의하십시오.

**벽/footprint 의 첫 독립 GT 수치 (3DSES, registration-SOLVED clean-laser extraction — 파이프라인 정확도 아님).** ARKit↔레이저 정합이 ill-posed 였던 위 한계는 **3DSES**(Mérizette et al. 2024, Zenodo **13323342**, **CC-BY-SA 4.0**; raw 데이터는 repo 에 미포함, 아래 수치는 파생 측정값) 로 부분적으로 풀립니다 — 이 데이터셋은 CAD 모델로 **정합이 해결된**(scan↔GT 잔차 **1.3–1.9 cm**) GT 를 제공하므로, roomestim 의 추출 공식을 **깨끗한 TLS 포인트클라우드에 직접**(`MeshAdapter` 우회) 돌려 벽 위치를 측정할 수 있었습니다. axis-rectangular 방 **n=3**, 완벽 분할(tight crop) 기준: **벽 위치 median ~3.4 cm / max 5.0 cm (convex 기본; 일관되게 wall 바깥쪽으로 few-cm over-read), ~2.5 cm (occupancy)**, footprint 면적 **+1.6…+3.8% (convex), −2.2…+1.8% (occupancy)**. **결정적 프레이밍:** 이것은 **"깨끗한 레이저에 대한 추출(extraction-on-clean-laser) 정확도이지, 파이프라인 벽 정확도가 아닙니다."** 같은 추출 공식이라도 실제 RGB-D end-to-end 최악 사례에서는 **면적 +22% / 벽 +0.7…1.8 m**(Redwood) 로 **1–2 자릿수 더 느슨**합니다 — depth 노이즈·드리프트·불완전 캡처가 지배하기 때문입니다. 또한 **load-bearing 주의:** occupancy 모드는 **disconnected sparse floater** 는 제거하지만, doorway 등 **연결된 through-opening bleed 는 제거하지 못합니다**(3DSES 의 A 방 +34%→+23%, C 방 +202%→+172% loose-crop 에서 확인; largest-connected-component 가 문간으로 연결된 bleed 를 유지). 따라서 **실 캡처에서의 per-room footprint ≤15 cm 는 여전히 미검증**이며, clean-laser ≠ 현장(field) 정확도입니다.

---

## 아키텍처

roomestim는 두 개의 형제 패키지로 구성됩니다 — `roomestim` (core capture-to-config 파이프라인)과
`roomestim_web` (Gradio 기반 웹 데모, v0.12-web.0 이후 parallel track).

```
Phone scan
    │
    ▼
[CaptureAdapter]         roomestim/adapters/{roomplan,polycam,mesh}.py
    │
    ▼
[RoomModel]              roomestim/model.py  ← 안정 추상화 경계
    │
    ├──► [Reconstruct]   roomestim/reconstruct/{floor_polygon,walls,listener_area,materials,image_source}.py
    │
    ├──► [Place]         roomestim/place/{vbap,dbap,wfs,dispatch}.py
    │
    └──► [Export]        roomestim/export/{room_yaml,layout_yaml}.py
                           ↓
                         room.yaml + layout.yaml (+ web 데모 산출물)
```

- 상세 다이어그램: [`docs/architecture.md`](docs/architecture.md)
- 웹 데모 패키지 구조: [`docs/adr/0024-web-demo-separate-package.md`](docs/adr/0024-web-demo-separate-package.md)
- `room.yaml` 스키마 명세: [`docs/room_yaml_spec.md`](docs/room_yaml_spec.md)

### 형제 레포 (read-only)

| 경로 | 역할 |
|---|---|
| `/home/seung/mmhoa/spatial_engine/` | 실제 spatial audio 렌더링 엔진 — roomestim의 `layout.yaml`을 소비합니다. `proto/geometry_schema.json`을 권위 있는 schema로 사용합니다 (vendor 복사 금지). |
| `/home/seung/mmhoa/vid2spatial_v2/` | 비디오 → spatial audio 파이프라인 — roomestim 산출물을 입력으로 활용할 수 있습니다. |

---

## ADR + 의사 결정 로그

설계 결정은 두 계층으로 추적됩니다.

- **ADR (Architecture Decision Record)** — [`docs/adr/`](docs/adr/) 에 37개 파일이 있습니다
  (0001~0039 번호대 + ADR 0030 의 §Status-update companion 파일 1개; 0034·0035 는 한 차례
  재번호된 적이 있어 번호 최댓값은 0039 입니다). 최근 핵심:
  - [ADR 0028](docs/adr/0028-hardwall-closure-and-ism-adoption.md) — D27 HARD WALL CLOSURE + ISM 채택
  - [ADR 0030](docs/adr/0030-predictor-default-switch.md) — shoebox default RT60 예측기 Sabine → ISM 전환
  - [ADR 0031](docs/adr/0031-material-override-policy.md) — 재질 override + 음향 recompute 트리거
  - [ADR 0032](docs/adr/0032-blueprint-2d-export.md) — 2D blueprint export
  - [ADR 0033](docs/adr/0033-engine-validation-toggle.md) — 엔진 검증 토글 (`--validate-engine`/`--no-engine-validation`)
  - [ADR 0034](docs/adr/0034-object-schema.md) — Object schema (Column/Door/Window)
  - [ADR 0035](docs/adr/0035-mesh-export-policy.md) — 메시 export (USDZ via usd-core; glTF via trimesh)
  - [ADR 0036](docs/adr/0036-layout-round-trip-nudge.md) — layout round-trip + 스피커 nudge
  - [ADR 0037](docs/adr/0037-wall-index-reference-frame.md) — `Object.wall_index` walls-only 참조 프레임
  - [ADR 0038](docs/adr/0038-input-resource-bounds.md) — adapter 단계 untrusted-input 리소스 바운드
  - [ADR 0039](docs/adr/0039-adr-status-update-split-mechanism.md) — ADR §Status-update 분리 메커니즘
- **결정 로그 (D1 ~ D82)** — [`.omc/plans/decisions.md`](.omc/plans/decisions.md). 단일 이슈에 대해
  Yes/No로 종결된 의사 결정과 reverse-criterion을 기록합니다. 최근 추가:
  - **D38** — predictor-default cascade policy (ADR 0030)
  - **D62** — test-only deprecated alias 마이그레이션
  - **D68/D69/D70** — `wall_index` frame 단일화 + 음향 입력 검증 (v0.21.0)
  - **D71/D72** — web 공개배포 security/honesty 하드닝 (v0.22.0)
  - **D73** — ADR §Status-update split-by-section 메커니즘 (ADR 0039, v0.22.1)
  - **D74~D78** — 감사 확정결함 PATCH (ISM 적응적 max_order / binaural DOA 축 / CLI 입력검증 / `run` 토글 / 자기교차 floor, v0.22.2)
  - **D79** — RIR auralization Phase A (rir.py + late_reverb.py + synthesize_brir, v0.23.0)
  - **D80** — 바이노럴 HRTF 좌/우 채널 스왑 수정 (coords.pipeline_to_ambix 단일권위 경유, v0.23.1)
  - **D82** — 비-shoebox floor 재구성 — opt-in concave-hull (`shapely.concave_hull`, 신규 의존 0; byte-equal default; ADR 0042 PR1, v0.24.0)
- **Open Questions (OQ-1 ~ OQ-58)** — [`.omc/plans/open-questions.md`](.omc/plans/open-questions.md).
  최근: OQ-45 CLOSED, OQ-46 NEW, OQ-52~58 NEW (image→geometry 설계); OQ-13e 부분진척 (concave 추출 landed, 실측-메시 ≤10 cm 검증 OPEN 유지).

---

## 테스트 + 검증

canonical 테스트 환경은 miniforge 입니다: `/home/seung/miniforge3/bin/python -m pytest`
(PATH 의 `.local/bin/pytest` 는 web extras 가 없어 misreport 합니다).

| 레인 | 명령 | 비고 |
|---|---|---|
| Default | `pytest -m "not lab and not web and not e2e"` | 312 passed / 5 skipped (v0.24.0; +12 concave floor 재구성 회귀 D82) — Linux CI에서 항상 실행 |
| Web | `pytest -m web` | 86 passed / 4 skipped (v0.24.0; core 변경이라 불변) — `[web]` extras 필요 |
| Lab | `pytest -m lab` | A10/A11 — `tests/fixtures/lab_real.usdz` + ground-truth 필요 (human-gated) |
| E2E | `pytest -m e2e` | ACE Challenge / SoundCam 외부 코퍼스 (env-var gated) |

추가 도구:

- `python scripts/lint_tense.py` — present-tense 정직성 leak 감사 ([ADR 0020](docs/adr/0020-ci-lint-tense-policy.md))
- `mypy --strict roomestim/` — baseline clean (v0.13+ 강제; v0.24.0 시점 38개 파일)
- `ruff check` — clean

### 전체 게이트 한 번에 (권장 GREEN 확인)

```bash
PY=/home/seung/miniforge3/bin/python   # canonical env
$PY -m pytest -m "not lab and not web and not e2e" -q   # default: 312 passed / 5 skipped
$PY -m pytest -m web -q                                  # web:     86 passed / 4 skipped
ruff check                                               # clean
$PY scripts/lint_tense.py                                # honesty-leak: clean (exit 0)
```

### 기능 스모크 테스트 가이드 (엔드투엔드 수동 검증)

각 기능을 픽스처로 직접 끝까지 돌려보는 절차다. canonical env(`PY`)를 쓰고, 산출물은 `/tmp` 에 떨군다.

```bash
PY=/home/seung/miniforge3/bin/python
OUT=/tmp/roomestim_smoke; rm -rf $OUT; mkdir -p $OUT

# 1) run 복합 (ingest+place+export) — VBAP 8스피커
$PY -m roomestim run --backend polycam --input tests/fixtures/lab_room.obj \
    --algorithm vbap --n-speakers 8 --layout-radius 2.0 --out-dir $OUT/run_vbap

# 2) ingest (octave-band 6밴드 흡음) + place dbap/wfs
$PY -m roomestim ingest --backend polycam --input tests/fixtures/lab_room.obj --octave-band --out-dir $OUT/ingest
$PY -m roomestim place --in-room $OUT/ingest/room.yaml --algorithm dbap --n-speakers 12 --layout-radius 2.5 --out-dir $OUT/dbap
$PY -m roomestim place --in-room $OUT/ingest/room.yaml --algorithm wfs --n-speakers 16 --layout-radius 2.0 --wfs-f-max-hz 600 --out-dir $OUT/wfs
#   ↑ WFS 는 spatial-aliasing bound 를 강제한다. f-max 가 너무 높으면(기본 8000) 안전 f_max/n_speakers 안내와 함께 종료(정상 동작).

# 3) export 포맷 — gltf / glb (+ acoustics sidecar). usdz 는 [usd] extra 필요(없으면 친절한 에러).
$PY -m roomestim export --in-room $OUT/ingest/room.yaml --in-placement $OUT/run_vbap/layout.yaml --format gltf --with-acoustics-sidecar --out-dir $OUT/gltf

# 4) edit — 채널0 스피커 방위 +5° / 고도 +3° nudge (unified diff 출력)
$PY -m roomestim edit --in-placement $OUT/run_vbap/layout.yaml --speaker 0 --daz 5 --del-deg 3 --out-dir $OUT/edit

# 5) 음향 예측기 3종 + 웹 산출물(리포트/바이노럴/PDF/3D뷰어) — Python API
$PY - <<'EOF'
from roomestim.io.room_yaml_reader import read_room_yaml
from roomestim.reconstruct.predictor import predict_rt60_default, room_volume, is_rectilinear_shoebox
room = read_room_yaml("/tmp/roomestim_smoke/ingest/room.yaml")
print("V=", round(room_volume(room),2), "shoebox=", is_rectilinear_shoebox(room))
from roomestim_web.report import build_acoustic_report
r = build_acoustic_report(room)
print("default(ISM) RT60@500=", round(r.default_rt60_500hz_s,3), "predictor=", r.default_predictor_name)
EOF
```

기대 결과: 1–4 는 `wrote <path>` 출력(WFS 는 기본 f-max 에서 의도적 bound-violation 에러), 5 는
`V=40.0 shoebox=True / default(ISM) RT60@500=1.594 predictor=image_source`. 웹 데모 자체는
`$PY -m roomestim_web.app` → http://127.0.0.1:7860 에서 업로드→3D뷰어→리포트→바이노럴→ZIP 흐름으로 확인한다.

전체 기능·구현·시장 비교·향후 TODO 종합은 [`docs/project_status_and_roadmap_2026-05-29.md`](docs/project_status_and_roadmap_2026-05-29.md) 참조.
자세한 weekly progress 내러티브는 [`docs/weekly_progress_report_2026-05-11.md`](docs/weekly_progress_report_2026-05-11.md) 참조.

---

## 개발 환경 설정

```bash
# Debian/Ubuntu (PEP-668 system Python): --user --break-system-packages 또는 venv
pip install --user --break-system-packages -e ".[dev,web]"
# 또는
python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev,web]"
```

선택 의존성:

| Extra | 용도 |
|---|---|
| `[dev]` | pytest + ruff + mypy + hypothesis |
| `[web]` | gradio + plotly + pyroomacoustics + pysofaconventions + reportlab + soundfile |
| `[viz]` | matplotlib (정적 시각화) |
| `[usd]` | usd-core (USDZ parse + export) |
| `[mesh-export]` | usd-core (메시 export 경로; ADR 0035) |
| `[colmap]` | pycolmap (experimental capture backend) |

---

## 레포 구조

```
roomestim/                  # core 패키지 — model, adapters, place, reconstruct, export, viz
roomestim_web/              # 웹 데모 패키지 (v0.12-web.0+; sibling)
app.py                      # HF Spaces 진입점 (roomestim_web.app:build_demo 임포트)
proto/                      # room.yaml JSON Schema (Stage 1 draft + Stage 2 locked)
tests/                      # pytest, fixtures, hypothesis property tests
tests/fixtures/             # lab_room.usdz, ace_*/, soundcam_synthesized/, web/
tests/web/                  # 웹 데모 테스트 (86 passed / 4 skip @ v0.24.0)
scripts/lint_tense.py       # honesty-leak lint (ADR 0020)
docs/                       # architecture, room_yaml_spec, ADR 0001-0039, 주간 보고서
docs/adr/                   # 37개 ADR 파일 (0001~0039 번호대 + 0030 status-update companion)
docs/perf_verification_*.md # 버전별 perf 스냅샷
docs/protocol_a10b_*.md     # in-situ 캡처 프로토콜 DOC
.omc/plans/                 # 설계 계획 + decisions.md (D1-D82) + open-questions.md (OQ-1~OQ-58)
RELEASE_NOTES_v*.md         # 버전별 릴리즈 노트
```

---

## OMC 파이프라인 (v0.11+)

trivial 하지 않은 변경은 모두 `planner → executor → code-reviewer → verifier` 네 단계를 거칩니다.
자세한 운영 메모는 `/home/seung/.claude/projects/-home-seung-mmhoa-roomestim/memory/MEMORY.md` 에 있습니다.
v0.11.0이 네 단계를 명시적으로 거친 첫 릴리즈이며, 이후 v0.12 ~ v0.22 모두 동일한 파이프라인으로
release되었습니다.

---

## 라이선스 + 출처

- **메인 코드** — MIT (Anthropic Claude Code 협업 표기 포함)
- **HRTF 데이터** — HUTUBS (TU Berlin, **CC BY 4.0**) 우선; MIT KEMAR (public domain)는 대체 출처
- **테스트 오디오** — LibriVox (public domain)
- **HRTF 데이터셋 선택 근거** — [ADR 0026](docs/adr/0026-hrtf-dataset-selection.md)
- **HRTF licensing & bundling 정책** — D31 ([`.omc/plans/decisions.md`](.omc/plans/decisions.md))

---

## Tag 정책 (D11)

모든 git tag (`v0.1.1` ~ `v0.22.2` + `v0.12-web.*` 웹 트랙 태그)는 **로컬 전용**입니다.
커밋만 `origin/main` 으로 push되고, tag push는 별도 ratification gate (현재 미정의)를 통해야 합니다.

---

## Schema marker

- `__schema_version__ = "0.2-draft"` (Stage-1 permissive; bumped v0.17.0 per ADR 0034 §B)
- Stage-2 strict flip은 A10b in-situ 캡처에 묶여 있으며 ([ADR 0016](docs/adr/0016-stage2-schema-flip-via-substitute.md) §Reverse-criterion + [ADR 0018](docs/adr/0018-soundcam-substitute-disagreement-record.md)),
  v0.12+ 스코프에서 user-volunteer 캡처 후에 재개됩니다.

---

> 문제 제보 / 질문은 GitHub Issues 또는 sibling 레포의 PR 채널을 활용해주세요.
> 본 README는 lint scope에 포함되어 있으며, ADR 0020에서 정의한 honesty-leak 패턴이 발견되면
> CI가 차단합니다 — 본 한국어 본문은 해당 패턴(영문 present-tense 출시 framing)에서 자유롭게 작성되었습니다.
