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

# 7개 서브커맨드: ingest / place / export / run / edit / collection / structure
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
`edit` (스피커 nudge + round-trip). `--backend` 는 `{roomplan,polycam,image,multiview,moge}` 이며,
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

### `moge` 백엔드 — MoGe metric 단일-이미지 (v0.52.0, [ADR 0057](docs/adr/0057-moge-metric-image-backend.md), EXPERIMENTAL)

`--backend moge` 는 **MoGe**(Microsoft Research, 코드 MIT + 가중치 Apache-2.0) metric depth 모델을 사용해 단일 equirectangular 파노라마에서 `cam_h` 없이 geometry 를 추정합니다. 파노라마를 known-rotation 퍼스펙티브 crop 으로 분할 → 각 crop MoGe 추론 → 3D 융합 → `MeshAdapter` 기하 추출 재사용(`--floor-reconstruction` 적용 가능). `provenance=reconstructed`, 재질 `UNKNOWN`. `[moge]` extra(`pip install 'roomestim[moge]'`, git-only) + `--experimental` 게이트 필요.

> **상업 가중치 장점**: HorizonNet 기본 가중치(`st3d`, 상용 적합성 미확인) / `zind`(NC ToU) 대비 MoGe Apache-2.0 가중치는 상업적으로 더 명확하다.

> **⚠ 정직 평가 고지 (load-bearing, 단일진실원천 `MOGE_METRIC_NOTE`)**: cuboid-pano 벤치(n=100, Stanford2D3D 사무 50 + PanoContext 주거 50)에서 MoGe 는 **HorizonNet 을 넘지 못한다** — per-DIM median 오차 **151.7 cm(MoGe convex) / 176.3 cm(MoGe robust) vs 58.0 cm(HorizonNet)**; 천장 median 오차 **71.7 cm vs 13.1 cm**. GT metric scale 편향(cam_h-derived) 제거 후 scale-invariant shape-only 비교에서도 MoGe convex **52.9 cm** 로 방 단위 ≤15 cm 율이 HorizonNet 미달(1.0% vs 3.1%). per-crop metric-scale 분산 CV median **14.7%**, p90 **25.8%**. ★벤치 GT 가 100% cuboid 이고 GT 스케일 자체가 cam_h-derived 이며 MoGe 가 개구부/창문을 투과 depth 로 보는 modality 차이가 있어 절대 비교가 MoGe 에 불리하게 편향되나, 이 편향을 제거한 shape-only 비교에서도 MoGe 가 우세하지 않다. 공정한 검증을 위해 non-cuboid measured-metric GT 가 필요하다. **이 백엔드는 cam_h 없이 쓸 수 있는 실험적 대안으로만 제공 — HorizonNet `image` 백엔드가 계속 documented rough-tier 이다.**

```bash
pip install 'roomestim[moge]'  # git-only extra; PyPI [moge] 미배포
python -m roomestim run --backend moge --experimental \
    --input room_pano.jpg \
    --algorithm vbap --n-speakers 6 --out-dir /tmp/out
```

### `multiview` 백엔드 + A-consumer 레버 (v0.50.0, [ADR 0056](docs/adr/0056-aconsumer-placement-levers-multiview-ingest.md))

`--backend multiview` 는 multi-view/video 재구성(예: VGGT)이 만든 **재구성된 포인트
클라우드**(`.ply` points-only / `.npz` / `.xyz`/`.txt`)를 입력으로 받습니다. `MeshAdapter`
가 거부하는 faces-없는 cloud 를 메우며, 동일한 footprint/ceiling/wall 추출을 재사용해
`--floor-reconstruction` 이 그대로 적용됩니다(`provenance=reconstructed`). frames→cloud
재구성 자체(VGGT, 무거운 GPU 의존)는 **out of scope** — 이 백엔드는 cloud 만 ingest 합니다.

거친 phone/video cloud 는 천장에 거의 닿지 않아 자동 추출 천장이 신뢰 불가하므로 두 개의
**A-consumer 레버**를 함께 제공합니다(둘 다 모든 백엔드에서 동작, additive):

- `--ceiling-height-m M` — 사용자가 줄자로 잰 단일 스칼라로 천장고를 **덮어씁니다**
  (벽/천장을 floor 평면에 일관되게 재구축, `ceiling_confidence=high`). cloud 가 천장을
  못 잡는 multiview 에 권장.
- `--known-floor-len-m M` (v0.54.0) — VGGT-class cloud 는 metric-native 가 아니라
  방마다 scale 이 ~1–5x 드리프트합니다. 알려진 **footprint diameter**(= 코너-대-코너 대각,
  임의 두 바닥 코너 사이 최대 거리 — **최장 벽이 아님**)를 주면 cloud 를 등방 리스케일해
  metric 으로 맞춥니다. `--ceiling-height-m` 와 페어 권장. 결과는 입력 cloud 의 scale 에
  무의존(절대치 정확도는 footprint 추출 품질에 종속, real-scan GT 미검증).
- `place --snap-to-surfaces` — 배치된 스피커를 가장 가까운 벽/천장 mount 표면에 **스냅**
  (floor 제외). 거친 geometry 위 계획이 실 표면에서 ~35 cm 벗어나는 것을 install-time 에
  완화하는 보정. PLACEMENT_SENSITIVITY_VERDICT.md 측정 기반.

#### upstream video→room (실험적 rough+ tier — cloud 를 어디서 얻는가)

`multiview` 백엔드는 **이미 재구성된 cloud** 를 입력으로 받습니다. 그 cloud 를 폰
**영상(frames)** 에서 만드는 한 가지 경로가 **VGGT**(feed-forward multi-view, `facebook/VGGT-1B`)
입니다. 이 frames→cloud 프런트엔드는 **roomestim 에 패키징되지 않습니다** — 별도 리서치
워크스페이스(`spike-vggt-multiview/scripts/video_to_room.py`)에 있으며 VGGT 코드 + 체크포인트는
PyPI 에 없습니다(git/HF 수동 설치, ~7 GB venv). roomestim 코어가 import 하는 VGGT/torch
의존은 **없습니다**. 따라서 `[vggt]` 류 extra 도 두지 않았습니다 (`pip install` 로 frames→room
이 바로 동작하지 않으며, 코어가 쓰지 않는 무거운 의존을 끌어오는 것은 overclaim — 이 백엔드는
어디까지나 cloud ingest 입니다). 이 외부 프런트엔드가 만든 cloud 를 위 `--backend multiview`
+ `--known-floor-len-m`(v0.54.0) + `--ceiling-height-m` 로 흘려보내는 것이 downstream 입니다.

> **⚠ 정직 평가 고지 (load-bearing, video→room 정확도 천장 — 이 블록이 수치의 단일 출처)**:
> video→room 경로는 **실험적이며 install-grade(≤15 cm) 가 아닙니다.** 진짜 multi-view 메트릭 GT
> (ARKitScenes raw, 10개 실방, 48 view)에서 VGGT-1B 의 floor-geometry 는 **corner median ≈22.4 cm
> (2/10 방만 ≤15 cm, 8/10 ≤30 cm)** 로 RoomPlan LiDAR ~8.5 cm 대비 ~2.6× 느슨합니다
> (`spike-vggt-multiview/VERDICT.md`). multi-view 의 결정적 이득은 **scale 축**입니다 — 단일-파노가
> cam_h 한 변수로 전체 scale 이 흔들리던 것과 달리, parallax 가 **메트릭 scale 을 안정화**합니다
> (best-fit 대비 median scale 오차 **1.6 %**, 6/10 방 ≤5 %). 단 anchor 없는 per-room scale 은 여전히
> ~1.04–5.0× 드리프트(median 1.95×, `PLACEMENT_SENSITIVITY_VERDICT.md`)하므로 metric 출력에는 **`--known-floor-len-m`(known floor 대각) + `--ceiling-height-m`
> 사용자 입력이 필수**입니다(v0.53.0 `MultiviewAdapter.scale_anchor` → v0.54.0 CLI). shape 정확도는
> **convex footprint 만** 권장 — `convex_band` 가 best ~13 cm(6/10)이나 이는 **convex-prior 아티팩트**
> 라 non-convex 방엔 일반화되지 않고, 일반 concave footprint 는 ~18–25 cm·면적 ~40 % under-coverage
> 로 install-grade 미달입니다(`A3_VERDICT.md`/`A4_VERDICT.md`). 지배 오차는 **VGGT periphery
> under-reconstruction**(coverage 한계)이며 cross-chunk 정합·coverage-aware selection·TSDF 모두
> 닫지 못한 채 negative 입니다. **요구 환경**: 2080Ti급 GPU(~7 GB VRAM, float16)·VGGT forward 는
> "seconds per scene"(VERDICT.md; 구체 초수는 미측정)·**데스크톱 전용(모바일 미지원)**. 이 경로는 단일-파노 `image`/`moge` 백엔드보다 scale-정직하게 우월한
> **rough pre-scan 추정**으로만 제공되며, ≤15 cm 설치 측정은 LiDAR/RoomPlan 의 몫입니다.

### `structure` 서브커맨드 — Apple CapturedStructure → N개 방 (정직 고지)

`structure` 는 **진짜 Apple RoomPlan `CapturedStructure` export 1개**(다중 방 device
스캔 JSON)를 받아 `section` 당 1개씩 N개의 단일방 `RoomModel` 로 분해한 뒤, 기존
`collection` 합성 경로(방별 placement + `room.<name>.yaml`/`layout.<name>.yaml` +
`collection.yaml` manifest)로 그대로 흘려보냅니다([ADR 0050](docs/adr/0050-roomplan-capturedstructure-splitter.md)).

```bash
python -m roomestim structure \
    --in-structure scan.CapturedStructure.json \
    --algorithm vbap --n-speakers 8 --name venue \
    --combined-gltf /tmp/out/venue.glb \
    --out-dir /tmp/out
```

> **정직 고지 (load-bearing)**: Apple 의 export 는 **element→room 멤버십을 주지
> 않습니다** — `sections`(=방)는 `label`/`story`/`center` 만 갖고 walls/doors/windows/
> objects 는 방 외래키 없는 flat 배열입니다. 따라서 roomestim 은 각 벽/가구/문/창을
> **명시적·문서화된 HEURISTIC**(floor-plane nearest-section-center, story 일치)으로 방에
> 배정합니다. 결과 per-room 분할은 **RECONSTRUCTION 이지 Apple-authoritative 데이터가
> 아닙니다**(단일진실원천 `ROOMPLAN_STRUCTURE_SPLIT_NOTE` — CLI 가 stderr 로 출력).
> per-room footprint 은 **배정된 벽들의 floor-projected convex hull**(재진입 코너를 복원
> 못 하는 **과대추정**)일 뿐 측정 floor 폴리곤이 아닙니다(export 의 `floors[]` 는 빌딩 전체
> 1개). ceiling 높이는 배정된 벽 높이의 중앙값으로 **합성**됩니다. **집계 footprint/volume/
> 결합 RT60 은 의도적으로 없습니다.** 문/창은 `parentIdentifier`(→부모 벽의 방)로 따라가며
> `wall_index` 를 그 방의 walls-only 프레임으로 **재계산**합니다(ADR 0037). doors/windows
> 는 Object 로, sofa/table/bed/storage 가구는 free-standing box 로 유지하고 chair/sink/
> toilet 은 기존 정책대로 무시합니다. `--combined-gltf`/`--combined-usd` 는 독립 방들의
> **시각적 조립**일 뿐(방-간 pose 추론 없음 → 방들이 원점에서 겹칠 수 있음)이며 결합 음향이
> 아닙니다.
>
> **정확도는 UNVALIDATED 입니다** — multi-room GT 가 없어 분할 정확도를 측정할 수 없습니다.
> **알려진 실패 모드**(해결 안 함, 정직 문서화): (1) **nested room**(예: 침실 안 욕실)은
> nearest-center 가 큰 방으로 빨아들임; (2) **동일 라벨 인접 방**(두 bedroom 중 하나가 적은
> 벽을 받을 수 있음 → <3 벽이면 low-confidence `UserWarning`); (3) **두 방 경계의 등거리
> 벽**은 deterministic 하게 최소 section index 로 tie-break. rough multi-room pre-scan
> 용도이며 install-grade 측정이 아닙니다.

### `measure-rt60` 서브커맨드 — 녹음에서 RT60 측정 (v0.51.0, [ADR 0055](docs/adr/0055-measured-blind-rt60-audio-extra.md))

가정된 재질에 의존하는 기하 RT60 **MODEL**(Sabine/Eyring/ISM)과 달리, 실제 방에서 **녹음한
신호**로부터 broadband RT60 을 **측정**합니다(`blind-rt60` ML decay 모델 래핑). 선택적
`[audio]` extra(`blind-rt60` + `soundfile`)가 필요합니다.

```bash
pip install 'roomestim[audio]'

# 사람 가독 출력 (RT60 + method/source/sample_rate/n_samples; 고지 NOTE 는 stderr)
python -m roomestim measure-rt60 --audio clap.wav

# 기계 가독 JSON (rt60_s, sample_rate_hz, n_samples, source, method, note)
python -m roomestim measure-rt60 --audio clap.wav --json
```

가장 좋은 입력은 **조용한 방에서의 깨끗한 impulsive 여기**(박수·풍선 터뜨림)입니다 —
연속 정상 잡음은 decay tail 이 없어 추정이 발산합니다.

> **정직 고지 (load-bearing, 단일진실원천 `MEASURED_RT60_NOTE`)**: blind 추정기는 자체
> 오차를 가집니다. 컨트롤드-**SIM** 벤치(`tests/eval/blind_rt60_benchmark.py`, out-of-gate)는
> pyroomacoustics shoebox RIR 의 Schroeder RT60 을 GT 로 하여 impulsive 여기 하 decay-fit
> 정확도를 **MAPE ~9% / max ~18% (n=5)**로 **바운드**합니다. ★이는 추정기 decay-fit 의 **SIM
> 바운드이지 측정-방 end-to-end 오차가 아니며**, **ACE 측정 코퍼스(CC-BY-ND) + Acta 폐형
> 보정 벤치는 여전히 DEFER(증분 2b)**입니다. 단일 **BROADBAND** 값(per-octave-band 아님)이며
> 녹음 품질에 의존합니다. indicative 측정으로 취급하고 calibrated 기준값으로 쓰지 마세요.

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

## 현재 상태 (2026-06-09)

| 버전 | 날짜 | 커밋 | 주요 변경 |
|---|---|---|---|
| **v0.54.0** | 2026-06-28 | (commit) | multiview metric scale-anchor **CLI 배선** (MINOR, additive, [ADR 0056 §Status-update](docs/adr/0056-aconsumer-placement-levers-multiview-ingest.md)) — v0.53.0 의 library-only `MultiviewAdapter.scale_anchor` 를 `ingest`/`run` 에 노출. 신규 **`--known-floor-len-m M`**(footprint diameter = 코너-대-코너 대각, **최장 벽 아님**)가 재구성 cloud 를 metric 으로 리스케일(`--ceiling-height-m` 와 페어). 공유 헬퍼 `_add_known_floor_len_arg` + `_scale_anchor_for` 를 backend 별 분기(image→`--cam-height`, multiview→`--known-floor-len-m`, 그 외 None)로 재구성 — **image·기존 backend 경로 무변경**. 잘못된 length 는 adapter ValueError → CLI rc 1(room.yaml 미기록). 독립 code-review 반영. +5 CLI 테스트(`tests/test_cli_multiview_scale_anchor.py`: metric 착지 ~12㎡·CLI scale-invariance rel 1e-6·no-anchor 회귀·`run` 출력·bad-length rc≠0) · ruff·mypy(--strict) clean. |
| **v0.53.0** | 2026-06-28 | `9316426` | MultiviewAdapter metric **scale_anchor** (MINOR, additive, [ADR 0056 §Status-update](docs/adr/0056-aconsumer-placement-levers-multiview-ingest.md)) — VGGT-class 재구성 cloud 는 metric-native 가 아니라 per-room scale 이 ~1–5x 드리프트. `parse(scale_anchor=ScaleAnchor(type, length_m))` supplied 시 방 1회 추출→footprint diameter(코너 대각, scipy pdist) 측정→cloud 를 `length_m/diameter` 등방 리스케일→재추출. 결과는 입력 cloud scale 에 **무의존**(*exact* convex default, 양자화 reconstruction 선 근사). 가드: type∈{known_distance,user_provided}·length finite>0·degenerate footprint 거부. no-anchor byte-equal. **library-only**(이 시점 CLI 미배선 → v0.54.0). **정직**: `length_m`=대각(최장 벽 아님; 벽 재면 ~20% mis-scale), anchored 절대치 정확도는 footprint 추출 품질 종속·real-scan GT 미검증. 독립 code-review APPROVE-WITH-FIXES(0C/0H, 3M+2L) 계약명확화 반영. default 791p/8s · web 95p/4s · mypy strict·ruff clean. |
| **v0.52.0** | 2026-06-27 | (commit) | MoGe **metric 단일-이미지 백엔드** (MINOR additive, [ADR 0057](docs/adr/0057-moge-metric-image-backend.md)) — `[moge]` extra(MIT 코드·Apache-2.0 가중치, git-only), `--backend moge --experimental`. **정직 negative**: cuboid-pano eval(n=100)서 HorizonNet 미달(per-DIM median 151.7 vs 58.0 cm, 천장 71.7 vs 13.1 cm); scale-invariant shape-only 비교에서도 미달; cam_h 불필요 + 상업 가중치가 장점. HorizonNet `image` 가 계속 documented rough-tier. 기존 backend·default gate 770p/7s byte-equal. |
| **v0.51.1** | 2026-06-27 | (commit) | py.typed PEP 561 마커 + CHANGELOG.md (패키징 위생, ADR 0007, PATCH additive). |
| **v0.51.0** | 2026-06-26 | (commit) | A3 **측정(blind) RT60 — 컨트롤드-SIM 벤치(증분 2a) + CLI 배선** (MINOR, additive) — v0.49.0 의 library-only 측정 RT60 경로를 (1) **정확도 바운드** + (2) **CLI 노출**로 완성. **(1) 컨트롤드-SIM 벤치** `tests/eval/blind_rt60_benchmark.py`(out-of-gate, `test_` 없음·`__main__` 전용): pyroomacoustics shoebox RIR 의 Schroeder RT60 을 GT 로, **impulsive-clap** 여기 하에 blind-rt60 추정기의 decay-fit 정확도를 측정 → **MAPE ~9% (8.7%), bias -8.5%, MAE 135 ms, max \|err\| 17.8% (n=5)**. ★이는 **SIM 바운드(추정기 decay-fit)이지 측정-방 end-to-end 오차가 아님**; **steady-noise 음성 대조군은 decay tail 부재로 39.5 s 로 발산**(정직 caveat). **ACE 측정 코퍼스(CC-BY-ND) + Acta 폐형 보정은 여전히 DEFER(증분 2b)**. **(2) CLI** `roomestim measure-rt60 --audio PATH [--json]`: 녹음→broadband RT60 측정, 사람가독/JSON 출력 + `MEASURED_RT60_NOTE` stderr; `[audio]` extra 부재는 in-handler `ImportError`→친절 hint·exit 1, 누락파일/빈신호는 main 의 기존 except→exit 1. **단일진실원천 `MEASURED_RT60_NOTE` 갱신**(SIM 바운드 명시, ACE end-to-end DEFER 유지). default 767→+3 테스트 `tests/test_measure_rt60_cli.py`(importorskip skip-guard, **정확도 단언 없음** — plumbing only) · ruff·mypy(--strict, 63) clean. ([ADR 0055 §Status-update](docs/adr/0055-measured-blind-rt60-audio-extra.md)). |
| **v0.50.1** | 2026-06-26 | (commit) | v0.50.0 **독립 code-review follow-up** (PATCH, additive) — v0.50.0 가 리뷰 전 출하되어 별도 세션 독립 `code-reviewer`(APPROVE-WITH-FIXES: 0 CRITICAL/HIGH, 1 MEDIUM, 4 LOW) 결과를 반영. **(MEDIUM)** `evolve_room_ceiling_height` 의 floor_y 재앵커링이 floor 평면≠0 케이스 미검증(전 테스트 floor=y0) → docstring 의도 명시 + 회귀 테스트(클라우드 +5 m 리프트). **(LOW)** `MultiviewAdapter.__init__` 가 `≤20 m` plausibility bound 를 생성자에서 fail-fast(parse 까지 미지연). **(LOW)** `_points_from_npz` named-key 분기가 `(N,6)` xyzrgb 를 `[:, :3]` 슬라이스(`.xyz`/`.txt` 로더 parity). + v0.50.0 누락 **README 문서화**(backend 열거 + multiview/A-consumer 레버 섹션). 코어 byte-equal·기존 backend 무영향. default 767p/7s(764→+3 테스트) · ruff·mypy(--strict, 63) clean. ([ADR 0056 §Status-update](docs/adr/0056-aconsumer-placement-levers-multiview-ingest.md)). |
| **v0.50.0** | 2026-06-26 | `3edaa02` | **A-consumer placement 레버 + multiview 점군 ingest** (MINOR, additive) — `PLACEMENT_SENSITIVITY_VERDICT.md`(spike-vggt-multiview)가 도출한 rough consumer-tier 워크플로를 코드로 착지. (1) 신규 `MultiviewAdapter`(`--backend multiview`): `MeshAdapter` 가 거부하던 **faces-없는 재구성 점군**(.ply points-only/.npz/.xyz·.txt)을 ingest, 동일 footprint/ceiling/wall 추출 재사용(`--floor-reconstruction` 적용), `provenance=reconstructed`, DoS byte-cap(ADR 0038). (2) `edit.evolve_room_ceiling_height` + CLI `--ceiling-height-m M`(ingest/run): 사용자 줄자 천장고로 **모든 backend** 천장 override(벽/천장을 floor 평면에 일관 재구축, `ceiling_confidence=high`, `>0`·`≤20 m` 바운드). (3) `edit.snap_layout_to_surfaces` + CLI `place --snap-to-surfaces`: 배치 스피커를 최근접 벽/천장 mount 면에 스냅(floor 제외, `aim_direction` 유지) — rough-plan 의 ~35 cm 면오차 install-time 완화. 신규 primitive `geom/surface_distance.closest_point_on_surface`. **NO FAKE NUMBERS**: 새 음향/기하 magnitude 무발명·천장 override 는 USER 측정 라벨. **VGGT frames→cloud 재구성은 out of scope**(GPU). 기존 backend·골든 byte-equal. ([ADR 0056](docs/adr/0056-aconsumer-placement-levers-multiview-ingest.md)). |
| **v0.49.0** | 2026-06-24 | (commit) | A3 **측정(blind) RT60 — `[audio]` extra** (MINOR, additive, opt-in, library-only 증분 1) — 기하 RT60 MODEL(Sabine/Eyring/ISM, 가정 재질)과 달리 **녹음 신호에서 RT60 측정**. 신규 `[audio]` extra(`blind-rt60>=0.1.1` MIT[1차출처 검증, Ratnam et al. ML] + `soundfile`) + 신규 `reconstruct/measured_rt60.py`: `measure_rt60_from_audio(path)`/`measure_rt60_from_signal(x,fs)` → `MeasuredRT60`. **lazy import**(blind_rt60/soundfile 함수 내부 only) → `import roomestim` 가 extra 안 끔(subprocess 테스트 lock), core dep-light. **정직 고지(load-bearing `MEASURED_RT60_NOTE`): 측정이나 blind 추정기 자체 오차 in-repo 미검증(ACE 벤치 defer)·단일 BROADBAND(per-band 아님)·녹음품질 의존.** A1(기하 절대정확도 NO-GO) 보완. ~~★CLI 미배선(의도): cli.py 가 다른 동시 세션 경합 중→library-only.~~ **→ v0.51.0 에서 `roomestim measure-rt60` 로 CLI 배선 완료.** default 764p/7s + 신규 `tests/test_measured_rt60.py`(importorskip skip-guard) · ruff·mypy(--strict, 63) clean. ([ADR 0055](docs/adr/0055-measured-blind-rt60-audio-extra.md)). |
| **v0.48.0** | 2026-06-24 | (commit) | B4 **coverage 완전성 densify-to-target** (MINOR, additive, opt-in) — ★성능평가(현실 방 5종×grid 2×overlap 2)에서 B1 nominal grid 가 바닥 **평균 69~75%·최저 53%만 커버**(1-D AVIXA spacing 의 2-D 대각 갭) 발견 → 정직 해결. (1) `place_coverage_grid` 에 additive `spacing_scale`(default 1.0=byte-equal, `(0,1]` densify-only). (2) 신규 `place/coverage_complete.py` `place_coverage_grid_to_target`: **측정 커버리지(B2 overlap 오라클)를 목표까지** spacing 조밀화(×0.9 step, 수렴/cap honest), closed-form 상수 추정 대신 실측 수렴(NO FAKE NUMBERS). (3) CLI `--coverage-target FRAC`: 지정 시 조밀화+`overlap.target`(requested/achieved/converged) 사이드카; **미지정 시 실 커버리지<85%면 stderr 경고**(silent under-cover 제거). 결과: meeting 6×5 방 54%(4spk)→**97%(12spk) MET**. `COVERAGE_COMPLETE_NOTE`(SPL 무주장, 기하 −6dB 원). spacing_scale=1.0 기본→coverage_to_dict·5 알고리즘 golden byte-equal. default 755p/7s + 신규 `tests/test_coverage_complete.py` · ruff·mypy(--strict) clean. ([ADR 0054](docs/adr/0054-coverage-completeness.md)). |
| **v0.47.0** | 2026-06-24 | (commit) | B2 **coverage-circle overlap 검증** (MINOR, additive, opt-in) — B1 이 명시 보류한 "±3 dB 균일도 검증"을 **절대 SPL 발명 없이** B1 의 coverage-원 기하 그 자체를 검증하는 방향으로 닫음. 신규 `place/coverage_overlap.py` `score_coverage_overlap`: 청취평면 footprint 를 격자 샘플링하여 각 점이 몇 개의 coverage 원(반경=B1 `coverage_radius_m`)에 드는지 세고 `fraction_covered`(≥1, 갭 탐지)·`fraction_overlap_2plus`(≥2)·`worst_point_xz`(최악 갭) 보고. `--algorithm coverage` 가 `layout.coverage.json` 의 **신규 `overlap` 키**(말미 append)에 기록 + `--coverage-grid-res-m`(기본 0.5). **정직 고지(load-bearing `COVERAGE_OVERLAP_NOTE`): 기하 오버랩 검증 — SPL/음향 무주장(절대 SPL=감도/구동레벨 부재, direct-sound=근접장 지배로 비견고; ±3 dB boolean 미제공=잔향장 대상이라 오해 방지).** ★실측 발견: B1 의 1-D AVIXA spacing 은 2-D 에 대각 갭을 남김(square/background 기본은 8×6 m 방 ~51% 만 커버, 반경 1.20<셀반대각 1.44 m) — hex/speech 가 부분 개선. `coverage_to_dict`·5 알고리즘 golden/round-trip byte-equal. default 715→727p/7s + 신규 `tests/test_coverage_overlap.py` · web 86p/3s · ruff·mypy(--strict, 59) clean. ([ADR 0053](docs/adr/0053-coverage-overlap.md)). |
| **v0.46.0** | 2026-06-24 | (commit) | A1 **shoebox RT60 엔진 검증** vs dEchorate 측정 GT (MINOR, additive, out-of-gate) — shipped RT60 엔진 BYTE-EQUAL, out-of-gate 하니스 `tests/eval/rt60_validation.py` + transcribed-cited GT `tests/eval/data/dechorate_gt.yaml` 만 추가. dEchorate(DOI 10.1186/s13636-021-00229-0; Zenodo 5562386, CC-BY-4.0) 6×6×2.4 m, 10 흡음구성, Table 5 측정 RT60(500/1000/2000/4000 Hz). ROUTE-RAW(literature alpha → `image_source_rt60_per_band` 직접구동). **결과(n=40)**: diffuse-field Sabine/Eyring 가 측정 RT60 **ordering 강하게 추적(Spearman ρ≈0.90)** 0.14–0.81 s, 절대정확도 미확립(ISM 반사방 과대 MAPE~103%, Sabine 과소 ~28%), 사전확정 go/no-go = **NO-GO 절대 / GO trend**, 근본원인=alpha-input gap(재질명만, alpha無). `RT60_DISCLOSURE` 에 측정기반 dEchorate 문장블록 추가. default 715p/7s 무회귀, 독립 code-review APPROVE. ([ADR 0028 §Status-update](docs/adr/0028-hardwall-closure-and-ism-adoption.md)). |
| **v0.45.0** | 2026-06-24 | (commit) | B1 room-aware AVIXA **ceiling coverage-grid** 배치 (MINOR, additive, opt-in) — 신규 `place/coverage_grid.py`: 방 floor polygon + 천장고 + 귀높이 + 공칭 분산각으로부터 천장면에 **사각/육각 격자** 스피커 위치를 결정론적으로 계산하고 footprint 폴리곤에 클립(shapely). `--algorithm coverage`(place/run) + 4 플래그(`--ceiling-dispersion-deg`/`--ear-height-m`/`--overlap-mode {background,speech}`/`--grid {square,hex}`), `layout.coverage.json` 사이드카. AVIXA Audio Coverage Uniformity(구 InfoComm 1M:2012) 기하 공식: `coverage_radius=(천장고−귀높이)·tan(0.75·분산각/2)`, `spacing=2R(1−overlap)`, 첫/마지막 스피커 반-spacing 벽 inset. dbap 에 이은 2번째 **방-기하 인지** 경로. 신규 의존 0(numpy/shapely·기존 core). **정직 고지(load-bearing `COVERAGE_GRID_NOTE`): 기하 전용 — SPL 무계산·AVIXA ±3 dB 균일도 미검증(B2 보류)·이상화 원뿔·실 스피커 polar 무주장·공칭 분산각은 user datasheet(방에서 추론 안 함). centroid-in-polygon clip 이라 concave notch 에서 coverage 원이 벽을 넘칠 수 있음.** VBAP/DBAP/WFS/ambisonics golden·round-trip byte-equal(기본 `vbap` 불변, `x_target_algorithm=COVERAGE_GRID` 만 추가·reader 닫힌집합 additive 확장). default 695p/7s + 신규 `tests/test_coverage_grid.py` · ruff·mypy(--strict) clean. (D109 / [ADR 0052](docs/adr/0052-coverage-grid.md)). |
| **v0.43.0** | 2026-06-17 | (commit) | RoomPlan `CapturedStructure` splitter **Phase S2+S3** (MINOR, additive) — `structure` 서브커맨드가 진짜 Apple multi-room export 를 N개 단일방 `RoomModel` 로 분해하는 입력 경로 완성([ADR 0050](docs/adr/0050-roomplan-capturedstructure-splitter.md)). **S2**: `objects[]` 가구를 nearest-section-center 로 방에 배정(기존 RoomPlan 정책 재사용 — sofa/table/bed/storage 유지, chair/sink/toilet 무시; 실 fixture 13개 중 10개 kept), doors/windows 는 `parentIdentifier`→부모 벽의 방으로 따라가며 `wall_index` 를 그 방의 walls-only 프레임으로 **재계산**(ADR 0037 가드 통과; 실 fixture 4 doors + 4 windows 전부 in-range), `--combined-gltf`/`--combined-usd` 는 출시된 ADR 0049 결합 writer 재사용(시각적 조립일 뿐, 결합 음향 없음). **S3**: `openings[]` 를 벽과 동일 경로로 ingest, degenerate section(<3 벽)은 crash 대신 단일진실원천 `ROOMPLAN_STRUCTURE_SPLIT_NOTE` `UserWarning`+low-confidence footprint, 등거리 벽 tie-break=최소 section index(deterministic), `unidentified` section 은 방으로 보존. **정직 고지**: per-room 분할은 disclosed HEURISTIC RECONSTRUCTION(Apple 은 element→room 멤버십 미제공), per-room footprint 은 wall-hull 과대추정, **집계 footprint/volume/RT60 없음**, 정확도 UNVALIDATED(multi-room GT 없음); 알려진 실패 모드(nested/동일라벨 인접/등거리) README 문서화. **단일방 코드·`roomplan.py`·`collection.py`·기존 exporter/placement 무접촉 → 모든 golden byte-equal**(load-bearing 테스트: per-room layout == standalone `place` 바이트 동일). default 686p/7s · web 86p/3s · ruff·mypy clean. (D108 / [ADR 0050](docs/adr/0050-roomplan-capturedstructure-splitter.md)). |
| **v0.42.0** | 2026-06-17 | (commit) | multi-room `RoomCollection` **결합 USD export**(glTF parity, MINOR additive) — `collection --combined-usd PATH`: 신규 `export/collection_usd.py` 가 `export/usd._room_to_usd_stage` 빌더를 재사용해 방별 Xform+translate(=user offset, Y-up·metersPerUnit 1.0 frame)로 단일 USD 스테이지 조립, manifest 에 ref 기록. **glTF 와 동일 정직범위: 독립 방들의 시각적 조립일 뿐 — geometry/footprint merge·결합 RT60·aggregate 음향 없음.** offset 은 user-supplied only(추론 안함). 스키마 v0_1 유지(optional key); flag 부재⇒이전 출력 byte-equal; 단일방 코드·`write_usdz`/`_room_to_usd_stage` 무접촉⇒golden byte-equal. pxr 부재 시 skip. code-review APPROVE. default 666p/7s · web 86p/3s · ruff·mypy(56) clean. (D107 / [ADR 0049](docs/adr/0049-multi-room-roomcollection-composition.md)). |
| **v0.41.0** | 2026-06-17 | (commit) | multi-room `RoomCollection` **Phase 2+3** — per-room offset + 결합 glTF export (MINOR, additive) — `collection` 서브커맨드에 `--offsets X,Y,Z ...`(방 수와 일치, **user-supplied only — roomestim 은 방-간 pose 를 추론하지 않는다**, NaN/inf 거부, 부재⇒identity) + `--combined-gltf PATH`(신규 `export/collection_gltf.py` 가 `_room_to_trimesh_scene` 재사용·방별 offset 을 순수 translation 으로 적용·단일 .glb/.gltf 방출, manifest 에 `combined_ref` 기록). **결합 export 는 독립 방들의 *시각적 조립*일 뿐 — footprint union·결합 volume/RT60·aggregate 음향 주장 없음**(offset 없으면 방들이 원점에 겹침을 정직 고지). 스키마는 optional `offset`/`combined_ref` 추가로 **v0_1 유지**(기존 Phase-1 manifest 유효). **offset 부재⇒Phase-1 byte-equal**(테스트 증명); 단일방 코드·`write_gltf` 무접촉⇒golden byte-equal. USD 결합 export 는 DEFER([usd] extra-gate). OMC planner-spec→executor(opus)→code-review(opus, APPROVE-WITH-FIXES: offset finite 체크 1건 적용)→verifier. default 660p/7s · web 86p/3s · ruff·mypy clean. (D106 / [ADR 0049](docs/adr/0049-multi-room-roomcollection-composition.md)). |
| **v0.40.0** | 2026-06-17 | (commit) | multi-room `RoomCollection` **합성(composition) 레이어 Phase 1** (MINOR, additive) — 신규 `roomestim/collection.py` `RoomCollection`(`name`, `rooms`, `placements`) + `collection` CLI 서브커맨드: `--in-rooms A.yaml B.yaml ...`(N≥2 단일방 room.yaml)를 받아 **각 방을 독립적으로** 배치하고 `layout.<room>.yaml` per-room + `collection.yaml` manifest 를 쓴다. **정직 범위 고지: roomestim 은 multi-room 을 *추론하지 않는다* — 컬렉션은 N개의 명시적 단일방 입력의 순서있는 번들이다.** footprint union·결합 volume/RT60·방-간 pose 추론 **없음**(ADR0047 가짜숫자 트랩 회피); aggregate 음향 주장 없음. Phase 1=manifest only(결합 glTF/USD 와 명시적 offset 은 Phase 2/3 DEFER). 신규 의존 0(jsonschema 재사용). **단일방 코드 경로 무접촉 → 모든 단일방 golden/round-trip byte-equal by construction**(load-bearing 테스트: collection per-room layout == standalone `place` 바이트 동일). (D105 / [ADR 0049](docs/adr/0049-multi-room-roomcollection-composition.md)). |
| **v0.39.0** | 2026-06-17 | (commit) | ambisonics 배치 알고리즘 (MINOR, additive, EXPERIMENTAL) — 신규 `place/ambisonics.py` `place_ambisonics(order)`: platonic closed-form 리그(1=octahedron6/2=icosahedron12/3=dodecahedron20, n≥(N+1)²), numpy-only, **신규 의존 0**. `--algorithm ambisonics --order {1,2,3}` (place/run). **정직 고지(load-bearing `AMBISONICS_RIG_DISCLOSURE`): roomestim 은 리그 좌표만 방출 — SH 인코딩/디코딩·decoder 선택은 engine 책임이며 end-to-end 라우팅 계약(ADR 0041 §D-3a point 1)은 미확정/UNCONFIRMED.** VBAP/DBAP/WFS golden byte-equal. PR4 t-design DEFER. (D104 / [ADR 0041](docs/adr/0041-ambisonics-placement-design.md)). |
| **v0.38.0** | 2026-06-16 | (commit) | `place`/`run` `--algorithm` 기본값 추가 (MINOR, backward-compatible new capability) — `--algorithm` 을 생략하면 이제 오류 대신 `vbap` 으로 기본 동작한다(사용자 승인 2026-06-16). `vbap` 은 벽·천장 표면 없이 항상 동작하기 때문에 기본값으로 선택; `dbap` 은 `place/dispatch.py` 가 surface(벽·천장) 1개 이상을 요구하므로 기하 없는 입력에서 crash 하여 기본값으로 부적합. **정직 고지: 이 기본값은 geometry-blind 다 — 기하-인지 배치가 목적이면 명시적으로 `--algorithm dbap` 을 지정해야 한다.** 명시적 `--algorithm vbap\|dbap\|wfs` 호출은 동작 불변. (D103). |
| **v0.37.1** | 2026-06-16 | (commit) | proto-bundling packaging fix (PATCH, no checkout behavior change) — relocated the room.yaml JSON schemas from repo-root `proto/` into in-package `roomestim/proto/` (`git mv`, byte-identical contents) and pointed `_proto_dir()` at `parents[1]/"proto"` so an installed wheel now ships (via the existing `[tool.setuptools.package-data]` glob) AND resolves the schemas, fixing self-validation/emit of room.yaml in an installed copy. Checkout golden round-trips unchanged. Regression guard: `tests/test_proto_packaging.py`. (ADR 0007 Honest-limitation → FIXED). |
| **v0.37.0** | 2026-06-12 | (commit) | floater-robust auto-select footprint (MINOR, additive, opt-in) — new `--floor-reconstruction auto`: coarse-grid (0.25 m) convex-hull area-inflation signal (φ≥1.10) switches to the occupancy extractor ONLY when a DISCONNECTED floater is detected, else stays convex (clean input byte-equal by construction). NOT default · NOT a bleed/re-entrant fix · threshold synthetic-fixture-validated (Redwood +22%→+5% cited). Single source `AUTO_FLOOR_RECON_NOTE`. (C1 / [ADR 0048](docs/adr/0048-auto-floater-footprint-select.md)). |
| **v0.35.0** | 2026-06-09 | `4554e9a` | polygon-ISM 기하 path-length/TOA 헬퍼 (MINOR, additive, geometry-only) — polygon image-source 의 기하 path-length / TOA 계산 헬퍼 추가; RT60·음향 수치는 미방출(geometry-only)이라 shoebox RT60 **byte-equal**. (Phase C ④ / [ADR 0040](docs/adr/0040-polygon-ism-design.md)). |
| **v0.34.0** | 2026-06-09 | `67f98b5` | occupancy footprint 모드 (MINOR, additive, opt-in) — density+connectivity 기반 floater-rejection footprint 추출 모드 추가. **NOT default**·n=1 검증·notch-recovery 아님. (Phase B ⑥ / [ADR 0042](docs/adr/0042-live-mesh-corner-extraction.md)). |
| **v0.33.0** | 2026-06-08 | `15e4b8a` | OQ-38 layout round-trip 라벨 보존 (MINOR) — `target_algorithm` 라벨을 `x_target_algorithm` 으로 보존, AMBISONICS/DBAP silent-collapse 수정. 라벨만 보존하고 producer 는 DEFER. (Phase 4 ⑦ PR1; OQ-38 부분해소). |
| **v0.32.0** | 2026-06-08 | `9a7d6c4` | concave footprint CLI 노출 (MINOR) — `--floor-reconstruction` 플래그로 concave 모드를 CLI 로 노출 + scan-jitter 강건성 테스트. reachability+robustness 이며 **정확도 주장 아님**. (Phase 2 ⑥ / [ADR 0042](docs/adr/0042-live-mesh-corner-extraction.md)). |
| **v0.31.1** | 2026-06-08 | `1b7fbca` | RT60 disclosure 정직성 보정 (PATCH) — disclosure 를 **BIDIRECTIONAL** 로 보정 + 극단방 ~2.3 s 명시. 수치·디폴트 **무변경**. (Phase 1 Option E). |
| **v0.31.0** | 2026-06-08 | `c6eb9fd` | polygon-ISM geometry-only 이미지소스 enumerator (MINOR, additive) — 신규 core `polygon_image_source.py`(numpy/shapely-only, **pyroomacoustics import 0**) `first_order_image_sources`: 벽 supporting-plane 미러링 + shapely on-segment 가시성 플래그, **POSITION 만 방출**. predictor 무변경(shoebox RT60 **byte-equal**). 단일 진실원천 `POLYGON_ISM_GEOMETRY_NOTE`. RT60 cascade 는 non-shoebox 측정 GT 부재로 DEFER. default 433p/3s. (D100 / candidate C / [ADR 0040](docs/adr/0040-polygon-ism-design.md)). |
| **v0.30.2** | 2026-06-08 | `ed9fae2` | candidate B 독립 code-review 후속 (PATCH, 2 LOW 반영) — 다중-floor 가드(`3a02d7e`)의 독립 리뷰 반영: `roomplan.py` UserWarning `stacklevel` 2→3(사용자 호출지점 귀속), public `parse()` 경로 parity 테스트 추가. 순수 additive·기하 수치 무변경. (D99 후속). |
| **v0.30.1** | 2026-06-08 | `3a02d7e` | RoomPlan 다중-floor 무손실 가드 (PATCH, robustness/honesty) — `floor_entries[1:]` 를 조용히 버리던 silent data-loss 를 단일 진실원천 `ROOMPLAN_MULTI_FLOOR_NOTE` UserWarning 으로 표면화(primary floor 만 표현; 나머지는 merge/export 안 함). `len==1` 경로 **byte-equal**. 진짜 multi-room RoomCollection 은 [ADR 0047](docs/adr/0047-multi-room-deferred.md) DEFER. default 418p/3s. (D99 / candidate B). |
| **v0.30.0** | 2026-06-08 | `d3457c5` | spatial_engine 절대경로 디커플 + PyPI-ready 패키징 (MINOR, additive) — 머신-특정 하드코딩 기본경로(`layout_yaml.py`) 제거 → `SPATIAL_ENGINE_REPO_DIR` env 만 해석, 미설정 시 descriptive `FileNotFoundError` fail-loud. env/CLI 가 실 schema 를 가리킬 때 layout.yaml **byte-equal**. 격리 venv wheel build/install/torch-free import 검증(PyPI-*ready*; publish 는 [ADR 0007](docs/adr/0007-distribution-model.md) deferred). default 416p/3s. (D98 / candidate A). |
| **v0.29.0** | 2026-06-08 | `5c93da2` | image cam_h scale-honesty surfacing (MINOR, additive, Phase 3) — 단일 파노가 원리적으로 scale-ambiguous(`r=cam_h/tan(−v_floor)`)임을 표면화: torch-free `_cam_h_sensitivity` 헬퍼 + anchor 미공급 시 ASSUMED UserWarning(단일 진실원천 `IMAGE_CAM_H_SCALE_NOTE`). user/anchor silent override 0. floor-plane cross-estimate 는 scale-INVARIANT 증명 후 DEFER. **정확도 개선 아님**(rough tier 불변)·검증갭(244 GT 100% cuboid). default 414p/3s. (D97 / candidate 6 / [ADR 0045](docs/adr/0045-image-to-geometry-capture-backend.md)). |
| **v0.28.0** | 2026-06-07 | `d8c5ea1` | 천장 높이 confidence flag — measured-path under-report 가드 (MINOR, additive, Phase 2) — 천장 plane 이 floor footprint 를 덮는 비율(`ceiling_coverage`, 25 cm 그리드 ±10 cm 밴드) 정직 기하측정 + 0.50 보수 임계 휴리스틱(`ceiling_confidence` high/low/unknown, **NOT calibrated**)으로 tabletop/mezzanine/under-sampled 천장 오선택을 경고. `ceiling_height_m`·RT60 **무변경**, 합성 픽스처만 검증. 단일 진실원천 `CEILING_CONFIDENCE_HEURISTIC_NOTE`. default 408p/3s. (D96 / Phase 2). |
| **v0.27.0** | 2026-06-07 | `90d050a` | 가구 음향 배선 (MINOR, additive) — **Phase 2(상용화)**: `ObjectKind` 에 음향관련 가구 `sofa`/`bed`/`table`/`storage` 추가. 가구는 column 과 동일한 **free-standing box**(`_objects_to_surfaces` 5-face 분해)로 RT60 흡음 예산에 반영되고, RoomPlan sidecar `_extract_objects` 가 해당 `CapturedRoomObject` 카테고리(sofa/couch·bed·table/desk·storage/cabinet/shelf/wardrobe/refrigerator)를 매핑(chair·toilet 등은 의도 제외). 단일 진실원천 `FREESTANDING_OBJECT_KINDS`/`WALL_ATTACHED_OBJECT_KINDS`(model.py) 를 predictor·gltf·usd·room.yaml reader·schema 가 공유. 재질=**대표 추정**(soft→`MISC_SOFT` 0.40, hard wood→`WOOD_FLOOR` 0.10), bbox-solid 가정의 정직한 ESTIMATE(`ace_challenge` furniture-budget 와 동일 철학). **기존 픽스처 RT60 byte-equal**(현재 어떤 adapter 도 가구 object 미방출 → 순수 additive). `proto/room_schema.v0_2.draft.json` 가구 enum+oneOf 브랜치 확장(schema-validated write↔read 라운드트립 핀). default 396p/3s·web 86p/3s·ruff/mypy EXIT0. (D95 / Phase 2). |
| **v0.26.1** | 2026-06-07 | `29b9edf` | measured 경로 P0 정확성 수정 — robust 천장 평면 추출 (PATCH, 정확성 수정·정확도 개선 아님) — 종전 full-extent(`y_max−y_min`) 천장 추출이 실 ARKit 스캔에서 floor-아래/ceiling-위 outlier(가구·노이즈)를 잡아 천장을 **+0.27~1.34 m 과대평가**(5-scene 0/5 ±10 cm 이내)하던 P0 를, Y-축 밀도 히스토그램의 floor/ceiling **평면** 추출(`_robust_floor_ceiling_y`)로 수정 — 독립 **Faro 레이저 GT** 대비 scene 42444946 **3.02 m vs 3.03 m (~1 cm)** 실증. README ±10 cm "독립 GT 검증 현황" 정직 고지 추가(천장만 실증; 벽/footprint 는 미검증), lab 회귀 assertion 강화(≥0.10 m outlier-rejection margin). (D94 / [ADR 0027](docs/adr/0027-mesh-format-generalisation.md) §Status-update-2026-06-07 (v0.26.1)). |
| **v0.26.0** | 2026-06-07 | `16759a3` | .usdz mesh ingest + RT60 정직 고지 (MINOR, additive) — **Phase 1**: `.usdz`(USDZ) 지오메트리 ingest 를 `MeshAdapter` 에 추가(`[usd]` extra=usd-core; `pxr` 경유) — **default-prim 스코프** instance-proxy 순회(concrete `def`-prototype 이중계수 방지·round-3 HIGH), `metersPerUnit`→m 스케일(cm-unit USDZ 정합·round-2 HIGH), `upAxis` 힌트 교차검증, 천장 타당성 절대상한(`ROOMESTIM_MAX_CEILING_M`, 기본 20 m); v0.25.3 up-축(gravity) 정규화 재사용. **Phase 0c**: RT60 honesty labeling — 단일 진실원천 `_disclosure.RT60_DISCLOSURE`/`RT60_MODEL_NAME`, `RT60Prediction.disclosure` property, 음향 사이드카(usd/gltf)에 additive `disclaimer`/`acoustics_model`/`materials_status` 필드(**수치 불변**), README RT60 "정직 고지(모델 추정, 측정 아님 / guidance)" 블록. (D92 [0c] / D93 [Phase 1] / [ADR 0027](docs/adr/0027-mesh-format-generalisation.md) §Status-update-2026-06-07 (v0.26.0)). |
| **v0.25.3** | 2026-06-07 | `5064a8b` | MeshAdapter up-axis(gravity) 자동 정규화 — measured 경로 P0 정확성 수정 (PATCH) — 실 ARKit(Z-up) 스캔 천장 6.5–9.6 m→2.49–3.69 m, 모호 시 fail-loud. **정확성 수정(정확도 개선 아님)**. (D91 / Phase 0a / [ADR 0027](docs/adr/0027-mesh-format-generalisation.md)). |
| **v0.25.2** | 2026-06-05 | `17c1264` | near-horizon 타당성 가드 + per-room 정직성 보정 (PATCH, image-backend cold-eval 후속) — 비현실 재구성(near-horizon blowup)을 조용히 내보내지 않고 명확히 거부 + README per-dim→per-room 현실 보정. **강건성·정직성 하드닝(정확도 개선 아님)**. (D89 / OQ-60). |
| **v0.25.1** | 2026-06-05 | `376bfef` | provenance 를 layout.yaml 아티팩트 경계로 전파 + 실모델 golden 회귀 (PATCH) — rough-tier 마커가 휘발성 stderr→영속 layout 키로 전파, 실 HorizonNet 경로 golden 회귀 차단. **정직성·강건성 하드닝(정확도 개선 아님)**. (D87·D88). |
| **v0.25.0** | 2026-06-04 | `6c9780f` | image→geometry 캡처 백엔드 출하 (MINOR, experimental rough-tier) — 단일-파노 사진→RoomModel rough-tier 백엔드. vendored HorizonNet(MIT) + `[vision]` extra(core torch-free) + provenance=reconstructed·material UNKNOWN. **install-grade 아님·정직 라벨**. (D86 / [ADR 0045](docs/adr/0045-image-to-geometry-capture-backend.md) / [ADR 0046](docs/adr/0046-room-provenance-schema.md)). |
| **v0.24.0** | 2026-06-02 | `5d18c9c` | 비-shoebox floor 재구성 — opt-in concave-hull footprint (MINOR, additive core feature) — 죽은 `floor_polygon_from_mesh` stub 을 `shapely.concave_hull`(신규 의존 0; `ratio=0.4`/`simplify=0.05`)로 구현; `MeshAdapter(floor_reconstruction="convex"\|"concave")` 생성자 인자 + `ROOMESTIM_MESH_FLOOR_RECON` env(precedence arg>env>convex). default convex 는 이전 동작과 **byte-equal**(회귀 핀), concave 는 degeneracy 시 convex+UserWarning fallback. **정직성(ICL-NUIM n=1 검증)**: concave/occupancy 모드는 shipped default(ratio=0.4 / min\_count=3)에서 **re-entrant 코너(notch)를 회복하지 못함** — convex +10.1%, concave +8.8%, occupancy +8.6% (GT +5.5% concavity 대비 모두 과대); notch 회복은 비-default·비-자동보정 knife-edge 임계값(min\_count=5)에서만 관측됨(+0.5%). concave/occupancy 는 convex 대비 **볼록 과대읽기를 소폭 감소**시키는 효과가 있으나 re-entrant 코너 보존을 보장하지 않음; CLI/web user-facing default 불변. **(2026-06-16 보강, 3DSES Gold 실측 TLS n=6)**: 위 "notch 회복 실패"는 **ICL-NUIM 합성 sparse(n=1)** 기준이다. 밀도 높은 실측 TLS(label-derived GT)에서는 동일 ratio=0.4 occupancy 가 **visibly non-convex 출력**을 내며 convex 과대읽기를 **부분적으로** 줄이는 *방향성*이 관측된다(여전히 실 floor 대비 과대읽기 — 완전회복 아님). 다만 이 occupancy 측정은 label-derived GT 기준이고(2026-06-17 사이클에서 CAD 가 Gold 에 sub-cm 로 정합됨을 확인했으나 이 occupancy 측정엔 미적용), 경계의 25–47% 가 wall-backed 가 아니어서(occlusion·doorway) **회복 비율을 정량 보정할 수 없으므로 수치는 주장하지 않는다**; `auto` 모드의 disconnected-floater 한정 범위는 불변. (D82 / [ADR 0042](docs/adr/0042-live-mesh-corner-extraction.md) §Status-update-v0.24.0; OQ-13e 부분진척, 실측-메시 ≤10 cm 검증은 SoundCam access 대기로 OPEN 유지). |
| **v0.23.1** | 2026-06-01 | `4cb87e0` | 바이노럴 렌더러 HRTF 좌/우 채널 스왑 수정 PATCH (web-tier correctness) — 렌더러가 pipeline 관례 azimuth(RIGHT=+az)를 SOFA 관례(LEFT=+az)로 변환 없이 `nearest_hrir` 에 넘겨 모든 측방 성분이 L↔R 거울반전되던 결함. 단일권위 `roomestim/coords.py:pipeline_to_ambix`(az→−az) 경유로 수정, 두 렌더 경로(`render_binaural_demo` / `synthesize_brir`) 동일 적용; diffuse late tail 무영향 (D80). dataset-grounded ILD 회귀테스트 2종 추가. core 무변경(회귀 0). |
| **v0.23.0** | 2026-05-31 | `fa7c48d` | RIR auralization Phase A (MINOR, additive, web-tier 한정·신규 패키지 0) — image-source 직접 조립 early per-band mono-RIR + filtered-noise late tail + 2-채널 convolvable BRIR (D79 / [ADR 0044](docs/adr/0044-rir-auralization-design.md) §Status-update-v0.23.0; OQ-48 CLOSED; OQ-47/49/51 status-update). `roomestim_web/rir.py` + `roomestim_web/late_reverb.py` + `binaural.synthesize_brir`; RT60 단일 진실원천 `predict_rt60_default_per_band` 6-band 유지; per-band energy-continuity splice. core 무변경(회귀 0). |
| **v0.22.2** | 2026-05-31 | `2eae5eb` | 감사 발견 확정결함 PATCH — ISM 기본 predictor 저흡음 적응적 max_order(Eyring 하한 불변식, D74 / [ADR 0030](docs/adr/0030-predictor-default-switch-status-updates.md) §Status-update-v0.22.2); 비-shoebox binaural DOA 축 스왑 + extrusion 렌더러 경로 활성화(D75); CLI ValidationError/YAMLError 포착(reader 가 ValueError 로 wrap, D76); `run` engine-validation 토글(D77); 자기교차 floor 거부(D78). MINOR-2(OQ-30)는 비수정. |
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

아래 **[core]** 는 CLI 코어(`roomestim`)가 생성하고, **[web]** 는 `[web]` extra(`roomestim_web`)에서만 생성됩니다.

- **[core]** `room.yaml` — 10-entry `MaterialLabel` enum + per-band 흡음 계수
- **[core]** `layout.yaml` — `spatial_engine/proto/geometry_schema.json` 검증을 통과한 스피커 좌표
- **[core]** `.usdz` / `.gltf` mesh export — geometry 메시 + 음향 사이드카
- **[web]** `setup_card.pdf` — 사용자가 인쇄해서 설치할 수 있는 안내 PDF (per-speaker 좌표 + 각도)
- **[web]** `binaural_demo.wav` — HUTUBS HRTF + pyroomacoustics ISM으로 합성한 30초 바이노럴 데모
- **[web]** **convolvable BRIR (auralization Phase A, v0.23.0)** — `roomestim_web.binaural.synthesize_brir` 가 geometry + 6-band 재질 + ISM 만으로 2-채널 임펄스 응답을 합성한다 (image-source 직접 조립 early + filtered-noise late tail + 2-HRIR decorrelation; RT60 단일 진실원천 = `predict_rt60_default_per_band`). diffuse tail 은 *plausible* 수준으로 기술하며 지각충실은 미검증(OQ-47). [ADR 0044](docs/adr/0044-rir-auralization-design.md)
- **[web]** `acoustic_report.json` — Sabine / Eyring / ISM RT60 + 옥타브 밴드별 결과
- **[web]** **3D 뷰어 (Plotly)** — 방 + 스피커 배치 인터랙티브 시각화
- **[web]** ZIP 아카이브 — 위 산출물 일괄 다운로드

---

## 파라미터 레퍼런스 (웹 UI / CLI 공통)

### `algorithm` — 알고리즘

| 값 | 정식 명칭 | 출처 | 권장 스피커 수 | 방 기하 인지 | 특징 |
|---|---|---|---|---|---|
| `vbap` | Vector-Based Amplitude Panning | Pulkki 1997 | 4–16 | **무관 (by construction)** — 고정 반경 링; 청취자 원점 기준 좌표만 생성 | 가장 표준; 3-스피커 트라이앵글로 가상 음원을 패닝; sweet-spot 의존도 높음 |
| `dbap` | Distance-Based Amplitude Panning | Lossius 2009 | 4–24 | **인지 (유일)** — mount surface(벽·천장) + listener_area 를 실제로 사용 | 비대칭 / 불규칙 스피커 배치 허용; sweet-spot 자유롭지만 sharp localization 약함 |
| `wfs` | Wave Field Synthesis | Berkhout 1988 | 8–16+ | **무관** — 합성 baseline(반경에서 유도)을 사용, 방 벽 형상 미반영 | 균등 간격 직선·곡선 어레이; wave front 재구성; 가장 정확하지만 하드웨어 요구가 큼 |
| `ambisonics` | Ambisonics 디코더 리그 | Gerzon 1973 | 6 / 12 / 20 | **무관 (by construction)** — order 가 결정하는 platonic 리그; 청취자 원점 기준 좌표만 | **EXPERIMENTAL (v0.39.0)** — platonic 리그 좌표만 방출(`--order {1,2,3}`); SH 인코딩/디코딩·decoder 선택은 engine 책임이고 end-to-end 라우팅 계약(ADR 0041 §D-3a point 1)은 **미확정(UNCONFIRMED)** |
| `coverage` | AVIXA 분산-천장 coverage grid | AVIXA Audio Coverage Uniformity (구 InfoComm 1M:2012) | 격자가 결정(방 크기·천장고·overlap) | **인지 (dbap 에 이은 2번째)** — floor polygon + 천장고 + 귀높이 사용 | **v0.45.0** — 천장면 사각/육각 격자, footprint 클립; **기하 전용 — SPL/±3 dB 무계산**; 하향 발사 천장 캔(listener-aimed 아님); **v0.47.0 B2** = `overlap` 사이드카로 실제 coverage-원 오버랩 검증(SPL 무주장, 1-D spacing 의 2-D 대각 갭 표면화) |

알고리즘 우선순위와 채택 배경은 [ADR 0003](docs/adr/0003-placement-algorithm-priority.md) 참조.

**방 기하 인지에 대한 정직 고지:** 현재 배치 알고리즘 중 방의 실제 벽·천장 형상과 청취 영역을
입력으로 사용하는 것은 `dbap` 하나뿐입니다. `vbap` 과 `wfs` 는 구조상(by construction) 청취자 원점을
중심으로 한 고정 반경 링/합성 baseline 만 생성하며 방 기하와 무관합니다 — 따라서 동일한 스피커 수·반경
입력이면(WFS 는 동일 WFS 파라미터 가정) 방이 달라져도 동일한 좌표를 냅니다. **기하-인지 배치가 목적이면 `--algorithm dbap` 을 사용하세요.**
(참고: v0.38.0(사용자 승인 2026-06-16)부터 `--algorithm` 의 기본값은 `vbap` 입니다 — `vbap` 은 벽·천장
표면 없이 항상 동작하기 때문입니다(고정 반경 링). **이 기본값은 위에서 밝힌 대로 방 기하와 무관(geometry-blind)
합니다 — 기본값을 그대로 쓰면 기하-인지 배치가 되지 않으며, 기하-인지 배치가 목적이면 명시적으로
`--algorithm dbap` 을 지정해야 합니다.**) Ambisonics 는 v0.39.0 부터 **EXPERIMENTAL** 로
사용 가능합니다(`--algorithm ambisonics --order {1,2,3}`): platonic closed-form 리그 좌표
(1=octahedron6/2=icosahedron12/3=dodecahedron20)만 방출하며, **SH 인코딩/디코딩·decoder 선택은
engine 책임이고 end-to-end 라우팅 계약(ADR 0041 §D-3a point 1)은 미확정(UNCONFIRMED)** 입니다 —
실행 시 stderr 로 load-bearing 고지(`AMBISONICS_RIG_DISCLOSURE`)가 항상 출력됩니다. PR4 t-design 은 보류(DEFER).

### `--check-angles` — 기하 레이아웃 각도 점검 (Atmos 스타일)

`place` 서브커맨드에 `--check-angles` 를 붙이면, 완성된 배치의 각 스피커에 대해 청취자
지점(기본값: `listener_area` centroid)에서 본 방위(azimuth)·고도(elevation)를 계산하고,
고도를 **공개 Dolby 지침**(Dolby Atmos Home Theater Installation Guidelines — height 스피커
30–55°, 이상값 45°)과 비교합니다. 출력은 사람이 읽는 per-speaker 라인 + `layout.angles.json`
사이드카이며, **`layout.yaml` 등 기존 출력은 바꾸지 않습니다**(플래그가 없으면 동작 불변).

이것은 **순수 기하 각도 준수 점검일 뿐, 음향 성능 주장이 아닙니다.** "pass" 는 마운트 각도가
공개된 창(window) 안에 든다는 뜻이며, 음색·이미징 품질이나 방-인지를 뜻하지 않습니다 —
고정-기하 VBAP/WFS 링도 이 점검을 통과할 수 있고, 그래도 방 기하와 무관합니다(위
'방 기하 인지에 대한 정직 고지' 참조). CTA/CEDIA RP22 표준은 **NOT EVALUATED** 입니다
(전문이 유료라 어떤 기준도 그에 대해 검증하지 않습니다). 밴드 구분(listener-level < 20°,
height 20–60°, overhead > 60°)은 roomestim 의 기하 관례이며 Dolby 분류가 아닙니다.
단일 진실원천은 `roomestim/place/standards.py` 의 `LAYOUT_ANGLE_CHECK_NOTE` 입니다.

### `--algorithm coverage` — 방-인지 AVIXA 천장 coverage 격자 (v0.45.0)

`place`/`run` 에 `--algorithm coverage` 를 주면, 청취자-중심 링이 아니라 **방 전체를 덮는
분산 천장 스피커의 정칙 격자**를 냅니다. 방의 floor polygon + 천장고 + 귀높이 + 공칭 스피커
분산각으로부터 AVIXA Audio Coverage Uniformity(구 InfoComm 1M:2012) 기하 공식으로 격자를
결정론적으로 계산하고 footprint 폴리곤에 클립(shapely)합니다:

```
effective_dispersion = nominal_dispersion × 0.75            # 유효≈공칭의 70–80%
coverage_radius      = (천장고 − 귀높이) × tan(effective/2)
center-to-center S   = 2 × coverage_radius × (1 − overlap)  # background 15% / speech 23%
첫/마지막 스피커        = 벽으로부터 반-spacing(S/2)            # 양변 inset
```

플래그: `--ceiling-dispersion-deg DEG`(공칭 datasheet 분산각, 기본 90), `--ear-height-m M`
(기본: `room.listener_area.height_m`), `--overlap-mode {background,speech}`(기본 background),
`--grid {square,hex}`(기본 square). 출력은 `layout.yaml`(스피커 위치, `x_target_algorithm=COVERAGE_GRID`)
+ `layout.coverage.json` 사이드카(radius/diameter/spacing/n_speakers/grid/overlap + 정직 NOTE)
이며, 실행 시 coverage 라인 + NOTE 를 출력합니다. 천장 스피커는 정-하향으로 aim 됩니다.

이것은 **결정론적 기하 레이아웃일 뿐, 음향 성능 주장이 아닙니다.** SPL(음압)을 계산하지 않고,
AVIXA **±3 dB 균일도 기준을 검증하지 않으며**(SPL/coverage 시뮬레이션이 필요 — **B2 로 보류**),
이상화된 원뿔을 가정하고 실 스피커의 polar 응답에 대해 아무 주장도 하지 않습니다. coverage
radius/spacing 은 공칭 기하이지 측정이 아니며, 공칭 분산각은 user 가 주는 datasheet 값입니다
(방에서 추론하지 않음). clip 규칙은 centroid-in-polygon 이라 concave notch 근처에서는 coverage
원이 벽을 넘칠 수 있습니다(NOTE 가 명시). 단일 진실원천은
`roomestim/place/coverage_grid.py` 의 `COVERAGE_GRID_NOTE` 입니다([ADR 0052](docs/adr/0052-coverage-grid.md)).

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
median +326% (직사각형 n=7); combined shoebox-feed n=10 은 +329%) — 오차가 **RT60 규모
그 자체**(median +1.3–2.9 s, 최대 ~+9 s)이며
**과대예측으로 편향**됩니다. 자세한 내용은 위 RT60 정직 고지 블록 참조.

캡처 노이즈가 dominant 한 오차 원인이며, sub-cm 정밀도는 명시적인 reverse goal입니다.
이 정밀도 목표를 위반하면 lab A11 / ACE A11 게이트가 실패합니다.

**독립 GT 검증 현황 (Phase 0b, 2026-06-07).** 위 ±10 cm 는 설계 **목표**입니다. 독립 GT(ARKitScenes **Faro 레이저 스캔**, roomestim 로직과 무관한 별도 센서) 대비 실측 검증은 현재 **천장 높이**만 커버합니다: 기존 full-extent(`y_max−y_min`) 추출이 실 ARKit 스캔에서 천장을 **+0.27~1.34 m 과대평가**(5-scene 0/5 가 ±10 cm 이내)하던 P0 를 robust floor/ceiling 평면 추출로 수정했고(**Phase 0b 국소 sub-scan** 기준 scene 42444946 = **3.02 m vs Faro GT 3.03 m, ~1 cm** — 이 scene 은 전체-건물 레이저 GT 가 모호해 5-scene 헤드라인에서는 제외되고 국소 crop 으로만 매칭), 이로써 **천장 높이는 가장 깨끗한 단일-방 scene 들에서 few-cm 수준으로 검증**되었습니다. 다만 이는 **±10 cm 의 포괄적 실증이 아닙니다**: 신뢰할 만한 단일-방 레이저 GT 를 갖는 scene 은 **n=2–3 개로 작고**(2/3 가 ±10 cm 이내; 5-scene 헤드라인의 가장 깨끗한 2개 scene 42444966·42445021 가 각 ~1.0 cm·~3.6 cm), 표본에 남겨둔 한 scene(42445429)은 **~6 m multi-floor venue 에서 ~31.8 cm 오차**를 보입니다(레이저 GT 자체의 mezzanine/two-floor 혼입 불확실성 가능). **벽 위치/footprint ±10 cm 는 (아래 3DSES clean-laser extraction 결과를 제외하면) 실 캡처 파이프라인에 대해 독립 GT 로 미검증 상태로 남습니다 — Faro 로는 검증을 *시도*했고 그 결과 현 ARKit↔레이저 데이터로는 ill-posed 임을 확인했습니다.** Faro 레이저 GT 는 단일 방이 아니라 **건물 한 층 전체(≈72×102 m, ~7000 m², 벽 길이 ~856 m, 수직 ~24.6 m 의 multi-floor)**의 스캔이고 ARKitScenes 는 ARKit↔레이저 정합 변환을 제공하지 않으므로(`_pose.txt` 는 레이저 스캔들 사이 정합만 — `raw/README.md`), 단일 방(둘레 ~31 m, 벽 길이의 ~3.6%)의 footprint 를 비교하려면 방을 레이저 venue 좌표계로 **registration** 해야 합니다. **천장 높이는 방을 venue 내에서 위치시키지 않아도 검증됩니다** — 그것은 floor↔ceiling 분리라는 *수평위치-불변 scalar* 라 floor+ceiling 평면을 담은 임의의 국소 sub-scan 으로 복원되기 때문입니다(검증에 쓴 3.03 m GT 는 전체 multi-floor venue 가 아니라 방과 같은 층의 국소 영역에서 나온 값). 반면 **footprint 는 방을 수평으로 *localization* 해야 하며 이는 초기추정 없이는 ill-posed** 입니다: open3d **FPFH+RANSAC** 전역정합(2회)과 중력제약 **2D yaw-sweep FFT** 정합 3가지 방법 모두 신뢰 임계 미달(2D 피크 margin ≈1.00×, RANSAC fitness ~0.2)로 방을 확신 있게 배치하지 못했습니다 — 비슷한 직사각형 방이 다수인 대형 multi-room 공간에서 예상되는 결과입니다. 따라서 잘못된 정합으로 *허위* ±cm 수치를 만드는 대신 footprint 를 **미검증**으로 정직하게 둡니다. 종결 경로: (a) 방 단위로 크롭된 레이저 또는 알려진 ARKit↔레이저 대응/seed 확보, (b) 작은 단독 공간을 ARKit 으로 캡처한 레이저 scene, (c) 근사 위치 seed → ICP refine(단, seed 가 독립적으로 정당화돼야 cherry-pick 아님). 도구: `test/full_eval` 외부 spike 디렉터리의 `footprint_validate.py`·`footprint_register.py`·`footprint_register2d.py`. 또한 roomestim 의 **기본(convex-hull) footprint 경로**는 비-convex 방에서 구조적으로 과대추정되며(이 경우 정합 잔차에 센서오차와 혼재; opt-in `floor_reconstruction="concave"` 는 별도 존재), 종전 "lab A11 게이트" 의 GT 는 roomestim 로직 파생이라 tautological 이었음을 유의하십시오.

**벽/footprint 의 첫 독립 GT 수치 (3DSES, registration-SOLVED clean-laser extraction — 파이프라인 정확도 아님).** ARKit↔레이저 정합이 ill-posed 였던 위 한계는 **3DSES**(Mérizette et al. 2024, Zenodo **13323342**, **CC-BY-SA 4.0**; raw 데이터는 repo 에 미포함, 아래 수치는 파생 측정값) 로 부분적으로 풀립니다 — 이 데이터셋은 CAD 모델로 **정합이 해결된**(scan↔GT 잔차 **1.3–1.9 cm**) GT 를 제공하므로, roomestim 의 추출 공식을 **깨끗한 TLS 포인트클라우드에 직접**(`MeshAdapter` 우회) 돌려 벽 위치를 측정할 수 있었습니다. axis-rectangular 방 **n=3**, 완벽 분할(tight crop) 기준: **벽 위치 median ~3.4 cm / max 5.0 cm (convex 기본; 일관되게 wall 바깥쪽으로 few-cm over-read), ~2.5 cm (occupancy)**, footprint 면적 **+1.6…+3.8% (convex), −2.2…+1.8% (occupancy)**. **결정적 프레이밍:** 이것은 **"깨끗한 레이저에 대한 추출(extraction-on-clean-laser) 정확도이지, 파이프라인 벽 정확도가 아닙니다."** 같은 추출 공식이라도 실제 RGB-D end-to-end 최악 사례에서는 **면적 +22% / 벽 +0.7…1.8 m**(Redwood) 로 **1–2 자릿수 더 느슨**합니다 — depth 노이즈·드리프트·불완전 캡처가 지배하기 때문입니다. 또한 **load-bearing 주의:** occupancy 모드는 **disconnected sparse floater** 는 제거하지만, doorway 등 **연결된 through-opening bleed 는 제거하지 못합니다**(3DSES 의 A 방 +34%→+23%, C 방 +202%→+172% loose-crop 에서 확인; largest-connected-component 가 문간으로 연결된 bleed 를 유지). 따라서 **실 캡처에서의 per-room footprint ≤15 cm 는 여전히 미검증**이며, clean-laser ≠ 현장(field) 정확도입니다. v0.37.0 의 opt-in `--floor-reconstruction auto`(ADR 0048)는 정확히 이 **disconnected-floater** 케이스만 자동 처리합니다 — coarse-grid convex-hull 면적-팽창 신호가 분리된 floater 를 감지할 때만 occupancy 추출기로 전환하고, 그렇지 않으면 convex 와 **byte-equal** 로 남습니다. 위 connected-bleed 한계를 **그대로 상속**하며(연결된 geometry 는 신호를 발화시키지 못함) bleed/notch 회복 주장이 아닙니다; 설계 근거 수치는 위 Redwood +22%→+5% 결과에 묶이며 벽 정확도가 아닙니다.

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
| Default | `pytest -q` | 562 passed / 7 skipped (v0.35.0; canonical default lane, miniforge) — Linux CI에서 항상 실행 |
| Web | `pytest -q -m web` | 86 passed / 3 skipped (v0.35.0) — `[web]` extras 필요 |
| Lab | `pytest -m lab` | A10/A11 — `tests/fixtures/lab_real.usdz` + ground-truth 필요 (human-gated) |
| E2E | `pytest -m e2e` | ACE Challenge / SoundCam 외부 코퍼스 (env-var gated) |

추가 도구:

- `python scripts/lint_tense.py` — present-tense 정직성 leak 감사 ([ADR 0020](docs/adr/0020-ci-lint-tense-policy.md))
- `mypy --strict roomestim/` — baseline clean (v0.13+ 강제; v0.35.0 시점 49개 파일)
- `ruff check` — clean

### 전체 게이트 한 번에 (권장 GREEN 확인)

```bash
PY=/home/seung/miniforge3/bin/python   # canonical env
$PY -m pytest -q                                         # default: 562 passed / 7 skipped (v0.35.0)
$PY -m pytest -q -m web                                  # web:     86 passed / 3 skipped (v0.35.0)
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
| `[moge]` | MoGe metric depth (experimental image backend; git-only, PyPI 미배포) |

---

## 레포 구조

```
roomestim/                  # core 패키지 — model, adapters, place, reconstruct, export, viz
roomestim_web/              # 웹 데모 패키지 (v0.12-web.0+; sibling)
app.py                      # HF Spaces 진입점 (roomestim_web.app:build_demo 임포트)
roomestim/proto/            # room.yaml JSON Schema (Stage 1 draft + Stage 2 locked; in-package, ships in wheel)
tests/                      # pytest, fixtures, hypothesis property tests
tests/fixtures/             # lab_room.usdz, ace_*/, soundcam_synthesized/, web/
tests/web/                  # 웹 데모 테스트 (86 passed / 3 skip @ v0.35.0)
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

- **메인 코드** — MIT (Anthropic Claude Code 협업 표기 포함; 루트 [`LICENSE`](LICENSE))
- **vendored HorizonNet 코드** (`roomestim/vision/horizonnet/`) — **MIT, (c) 2019 Cheng Sun** (verbatim·재라이선스 아님; 해당 디렉터리 `LICENSE`/`NOTICE`)
- **`[moge]` 가중치** — **Apache-2.0** (Microsoft Research MoGe, 첫 사용 시 내려받음; 상업 적합성은 사용자가 직접 검증). 코드는 MIT.
- **`[vision]` 사전학습 가중치** — **MIT 아님** (`roomestim/vision/horizonnet/NOTICE`): 기본 가중치는 `st3d`(Structured3D **research dataset** 파생 — 상용 적합성 미확인), 옵트인 가중치는 `zind`(ZInD, academic / **NON-COMMERCIAL** ToU — `ROOMESTIM_ACCEPT_ZIND_TOU=1` 명시 수락 필요). 가중치는 이 저장소에 포함되지 않고 첫 사용 시 내려받으며, 상용 배포 전 어느 가중치든 해당 약관 적합성을 사용자가 직접 검증해야 한다.
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
