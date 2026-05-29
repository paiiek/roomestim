# roomestim — 기능 종합 · 구현 내용 · 시장 비교 · 향후 TODO (2026-05-29)

> 본 문서는 v0.22.1 시점의 roomestim 전체 상태를 한 곳에 정리한 종합 보고서다.
> 기능·구현은 **실제 엔드투엔드 스모크 테스트로 검증**된 사실만 적고, 미구현 설계는
> `(설계 PROPOSED)` 로 명시한다. 시장 비교는 2026-05-05 [`competitive_analysis_2026-05-05.md`]
> 를 현재 상태에 맞게 갱신한 것이다.
>
> **버전**: 0.22.1 · **스키마**: `0.2-draft` · **게이트 baseline**: default 287 passed/5 skipped,
> web 67 passed/4 skipped, ruff clean, tense-lint clean.

---

## 1. 한 줄 정의

> 스마트폰 방 스캔(Apple RoomPlan / Polycam / 범용 메시) 또는 공개 코퍼스를 입력으로 받아,
> 단순화된 `RoomModel` → 알고리즘 인지 스피커 배치 → 엔진 호환 YAML 을 생성하는
> **capture-to-config** 도구. 부속으로 옥타브 밴드 흡음·RT60 예측·바이노럴 데모·3D 뷰어·설치 PDF 를 낸다.

roomestim 은 **렌더러가 아니다** — 형제 레포 `spatial_engine`(C++) 이 실제 공간음향을
렌더링하고, roomestim 은 그 엔진이 소비할 `layout.yaml` 을 만든다. 이 "스캔 → 배치 알고리즘 →
엔진 검증 YAML" 결합은 2024–2026 FOSS/상용 제품에 직접 등가물이 없는 niche 다(§4 참조).

---

## 2. 현재 기능 (v0.22.1 — 스모크 검증됨)

### 2.1 CLI — 5개 서브커맨드

| 커맨드 | 역할 | 핵심 옵션 |
|---|---|---|
| `ingest` | 캡처 → `RoomModel` → `room.yaml` | `--backend {roomplan,polycam}`, `--octave-band` |
| `place` | `room.yaml` → 배치 → `layout.yaml` | `--algorithm {vbap,dbap,wfs}`, `--n-speakers`, `--layout-radius`, `--el-deg`, `--wfs-f-max-hz`, `--wfs-spacing-m` |
| `export` | room+layout 재출력 (idempotent) | `--format {yaml,usdz,gltf,glb}`, `--with-acoustics-sidecar`, `--validate-engine`/`--no-engine-validation` |
| `run` | ingest+place+export 복합 | 위 전부 |
| `edit` | 스피커 nudge → 재검증 → diff | `--speaker`, 구면 Δ(`--daz`/`--del-deg`/`--ddist`) 또는 직교 Δ(`--dx`/`--dy`/`--dz`) |

- `backend=polycam` 은 `MeshAdapter` alias 로 `.obj`/`.gltf`/`.glb`/`.ply` 를 처리한다.
- `--format usdz` 는 `[usd]` extra(`usd-core`)가 필요하며, 미설치 시 친절한 설치 안내 에러로 종료한다(graceful).
- `edit` 의 고도각 delta 는 항상 `--del-deg` (Python `del` 예약어 충돌 회피).

### 2.2 입력 — 5개 포맷

| 포맷 | 백엔드 | 비고 |
|---|---|---|
| `.usdz` | RoomPlan / Reality Composer | LiDAR 메트릭 스케일; JSON sidecar 권장 |
| `.obj` | 범용 wavefront | 호환성 최고 |
| `.gltf` / `.glb` | Khronos glTF 2.0 | web/Three.js/Unity |
| `.ply` | Stanford PLY | surface mesh 필수 — point-only 는 자동 메싱 안 함(0-faces reject, OQ-21 CLOSED) |

공개 코퍼스: ACE Challenge(Eaton 2016 TASLP), SoundCam(Stanford).

### 2.3 배치 알고리즘 — 3종 (+ 1종 stub)

| 알고리즘 | 출처 | 동작 |
|---|---|---|
| `vbap` | Pulkki 1997 | equal-angle ring / stacked dome. el_deg·radius 파라미터화 |
| `dbap` | Lossius 2009 | 비대칭/불규칙 배치 허용 |
| `wfs` | Berkhout 1988 | 균등 간격 어레이; **spatial-aliasing bound `c/(2·f_max)` 를 수식과 함께 강제** — 위반 시 안전 `f_max`/`n_speakers` 를 계산해 안내 |
| `ambisonics` | — | enum stub만 존재; 정식화는 **설계 완료(ADR 0041, PROPOSED)** |

스모크 확인: WFS 가 8000 Hz·16스피커·2 m 에서 aliasing bound 위반을 정확히 검출하고
"안전 f_max=643 Hz 또는 n_speakers≥188" 를 제시 → `--wfs-f-max-hz 600` 으로 통과.

### 2.4 음향 모델 — RT60 예측 3종 + 6밴드

| 예측기 | 공식 | 사용 시점 |
|---|---|---|
| **ISM** (Image-Source) | Allen & Berkley 1979 + Lehmann-Johansson | **shoebox 방의 default** (max_order=50) |
| **Eyring** | `0.161·V / (−S·ln(1−ᾱ))` | non-shoebox fallback |
| **Sabine** | `0.161·V / Σ(αᵢ·Sᵢ)` | 비교용 bar/JSON 필드 |

- 6 옥타브 밴드(125/250/500/1k/2k/4k Hz) per-band 예측 지원.
- `predict_rt60_default` 의 cascade: shoebox → ISM, non-shoebox → Eyring (ADR 0030). Sabine 은 더 이상 default 아님.
- lab_room.obj 실측(V=40 m³): ISM=1.594 s, Sabine=1.238 s, Eyring=1.193 s @500 Hz.
- 재질: 10-entry `MaterialLabel` enum + per-band 흡음 계수.

### 2.5 편집 (immutable evolve API)

- 스피커 nudge (CLI `edit` + 웹 "스피커 조정" 탭): 구면 또는 직교 Δ, 동시 입력 금지.
- 재질 교체 / 오브젝트 add·remove / surface 편집: `evolve_room_material` / `evolve_room_add_object` / `evolve_room_remove_object` / `evolve_surface` 등 (Python API; 원본 불변).
- 오브젝트→음향 경로 작동: glass window 추가 시 RT60 1.594→1.599 s (스모크 확인).
- `ObjectKind = {column, door, window}` (건축 요소만; 흡음 가구는 **설계 PROPOSED**, ADR 0043).
- round-trip 충실도 Level-1(구조 동치): position/channel/regularity/WFS 메타/aim 보존. `notes`/per-speaker `id`/DBAP·AMBISONICS `target_algorithm` 라벨은 비보존(OQ-37/38).

### 2.6 웹 데모 (Gradio + HF Spaces)

업로드 → 파이프라인 → 산출물. 모든 산출물 스모크로 실제 생성 확인:

- **3D 뷰어** (Plotly): 방+스피커 인터랙티브 (9 traces).
- **음향 리포트**: Sabine/Eyring/ISM per-band + 흡음 분포 차트.
- **바이노럴 데모 WAV**: pyroomacoustics ISM + 번들 HRTF(HUTUBS CC BY 4.0 / KEMAR public domain) — 5초 렌더 987 KB 확인.
- **설치 PDF** (reportlab): per-speaker 좌표+각도, 10 KB 확인.
- **ZIP 아카이브**: 산출물 일괄 다운로드.
- v0.22.0 에서 공개배포 하드닝(업로드 cap, leak 감사) 완료.

### 2.7 export 포맷

`room.yaml` / `layout.yaml`(YAML, 엔진 검증) + `room.usdz`(`[usd]` extra) + `room.gltf`/`.glb`
(+ `--with-acoustics-sidecar` 로 `.acoustics.json`). 스모크: gltf/glb/yaml 생성 확인, usdz 는 extra 안내.

---

## 3. 구현 내용 (아키텍처 / 모듈)

```
Phone scan (.usdz/.obj/.gltf/.glb/.ply) | 공개 코퍼스(ACE/SoundCam)
        │  CaptureAdapter: adapters/{roomplan,mesh(=polycam alias),ace_challenge}.py
        ▼
   RoomModel  (model.py) ← 안정 추상화 경계
     floor_polygon · ceiling_height · listener_area · surfaces[] · objects[]
        │
        ├─► Reconstruct: reconstruct/{floor_polygon,walls,listener_area,materials,image_source,predictor}.py
        │     - floor_polygon.py / walls.py: 현재 stub (실제 추출은 mesh.py 인라인 convex hull) — B6 설계 대상
        │     - predictor.py: Sabine/Eyring/ISM cascade + per-band + Object 흡음 fold
        │     - image_source.py: shoebox 전용 ISM (622 LoC) — polygon 확장은 B4 설계 대상
        │
        ├─► Place: place/{vbap,dbap,wfs,dispatch,algorithm}.py
        │     - dispatch.run_placement(): vbap/dbap/wfs 분기 (ambisonics 미분기 — B5 설계 대상)
        │
        ├─► Export: export/{room_yaml,layout_yaml,usd,gltf}.py
        │     - layout_yaml: spatial_engine geometry_schema.json 으로 검증 (vendor 복사 금지)
        │
        └─► Edit / IO: edit.py, io/{room_yaml_reader,placement_yaml_reader}.py, coords.py, geom/polygon.py

roomestim_web/ (parallel track, v0.12-web.0+):
   app.py · pipeline.py · viewer.py · report.py · binaural.py · hrtf_io.py
   · setup_pdf.py · archive.py · object_add.py · material_override.py · speaker_nudge.py · provenance.py
```

- **좌표계**: origin=청취자, x=right/y=up/z=front (m), +az=right, +el=up.
- **엔진 계약**: `layout.yaml` 은 sibling `spatial_engine/proto/geometry_schema.json`(권위 schema, vendor 복사 금지)으로 검증. `regularity_hint` enum = `{LINEAR,CIRCULAR,PLANAR_GRID,IRREGULAR}`. `additionalProperties:true` 라 `x_*` extension key(예 `x_wfs_f_alias_hz`) 허용. SH 디코딩은 engine 책임(`ipc_schema.md` `/sys/ambi_order`).
- **품질 게이트**: pytest(default/web/lab/e2e 마커), ruff, mypy --strict, `scripts/lint_tense.py`(honesty-leak 감사, ADR 0020).
- **의사결정 추적**: ADR 41개(`docs/adr/0001~0043`), 결정 로그 D1~D74, Open Questions OQ-1~OQ-46.

---

## 4. 기존 시중 엔진과의 기능 비교

> 2026-05-05 분석 표를 v0.22.1 현실로 갱신. roomestim 행의 ★ 는 2026-05-05 이후 **새로 구현된** 항목.

### 4.1 포지셔닝 — roomestim 의 niche

대부분 도구는 세 범주 중 하나다: (A) **상용 venue 설계**(BIM-grade, 자사 하드웨어 종속), (B)
**FOSS 렌더러/시뮬레이터**(스캔 입력 없음), (C) **측정 도구**(마이크 sweep). roomestim 은
**"폰 스캔 → 배치 알고리즘 → 엔진 검증 YAML"** 결합으로 어디에도 정확히 속하지 않는다.

| 도구 | 범주 | 스캔 입력 | 배치 알고리즘 생성 | RT60 | 출력 | 라이선스 |
|---|---|---|---|---|---|---|
| **roomestim** | capture→config | ★ RoomPlan/Polycam/메시 5포맷 | ★ VBAP/DBAP/WFS (Ambisonics 설계중) | ★ Sabine/Eyring/ISM 6밴드 | layout/room YAML + usdz/gltf + ★바이노럴/PDF/3D뷰어 | MIT-target |
| Dolby Atmos DARDT | 상용 설계 | 없음(수동 dims) | 고정 Atmos bed | room-avg | 좌표 printout | 무료(Dolby) |
| L-Acoustics Soundvision | 상용 설계 | 없음(CAD) | 자사 제품만 | BIM ray-trace | 자사 config | HW 종속 |
| d&b ArrayCalc / Meyer MAPP 3D | 상용 설계 | 없음(수동/CAD) | 자사 제품만 | BIM | 자사 processor | HW 종속 |
| Trinnov / Genelec GLM | 측정 보정 | 없음(마이크) | 배치 안 함(보정만) | 측정 | DSP/EQ filter | HW 종속 |
| **SonarRoom** (iOS, $14.99) | 측정 진단 | LiDAR+sweep | **없음** | 측정(RT60/C50 heatmap) | CSV/JSON/PDF/EQ | 상용 |
| SoundScape Renderer (SSR) | FOSS 렌더러 | 없음(ASDF XML) | 없음(수동) | N/A | 오디오 출력 | GPL |
| SPARTA / IEM suite | FOSS 렌더러 | 없음(JSON layout) | AllRAD/VBAP 디코더 | shoebox 반사 | Ambisonic 디코드 | GPL |
| pyroomacoustics | FOSS 시뮬 | 없음(shoebox dict) | **없음**(배치 아님) | ISM | RIR numpy | MIT |
| Steam Audio / Resonance | game-grade | 게임 지오메트리 | 없음 | ray/ISM | 컨볼루션 reverb | Apache 2.0 |
| ODEON / EASE / CATT | 상용 분석 | CAD(OBJ/STL) | 없음(분석만) | BIM ray-trace | RT60/SPL/IR | $2k–10k+ |
| REW | freeware 측정 | 없음(마이크) | 배치 advisory | 측정 | EQ correction | 무료 |

### 4.2 roomestim 의 방어 가능한 차별점

1. **스키마-락 cross-repo 계약** — `layout.yaml` 이 `spatial_engine/geometry_schema.json` 으로 검증. 어떤 경쟁 도구도 특정 렌더 엔진과 이런 결합이 없다.
2. **결정론적 byte-equal idempotent 출력** — 같은 입력·버전이면 플랫폼 무관 동일 YAML. 재현 가능 연구·CI 회귀에 적합.
3. **지오메트리에서 알고리즘 인지 배치 생성** — 스캔 floor polygon 에서 VBAP ring/dome, DBAP, WFS `c/(2·f_max)` 간격을 직접 계산. 자사 하드웨어 불요.
4. **캡처 장비 종속 없음** — RoomPlan/Polycam/메시 모두 OK. 동글·캘리브레이션 마이크 불요.
5. **닫힌 재질 enum(10종)** — ODEON 의 100+ DB 와 반대 철학; Sabine 출력을 재현·감사 가능.
6. **CLI + Python 라이브러리 + 웹** 3중 인터페이스 — SonarRoom(iOS only)/상용(GUI only) 대비.
7. **★ honesty-leak CI lint** — present-tense 출시 과장 차단(ADR 0020). 도구 신뢰성 차별점.

### 4.3 여전히 없는 것 (경쟁 대비 gap — TODO 로 연결)

| 없는 기능 | 가진 경쟁자 | 심각도 | roomestim 대응 |
|---|---|---|---|
| 음향 **측정**(마이크 sweep RT60/C50) | SonarRoom, REW, Trinnov | 높음 | 비-목표(추정 도구). "측정 아닌 planning estimate" 명시로 완화 |
| 배치 후 **SPL/coverage 시뮬** | Soundvision, ODEON | 중 | 후보(pyroomacoustics ISM coverage) |
| 비-shoebox/불규칙 방 **정확 RT60** | ODEON, Soundvision | 중 | **B4 polygon ISM 설계 완료(PROPOSED)** |
| 흡음 **가구 모델링** | (대부분 BIM) | 중 | **B7 설계 완료(PROPOSED)** |
| 고차 Ambisonics 디코더 행렬 설계 | SPARTA/IEM AllRAD | 낮음 | 비-목표(engine 위임); 단 **B5 로 리그 배치는 설계** |
| GUI 비기술 사용자 | 전 상용, SonarRoom | 중 | ★ Gradio 웹 데모로 부분 해소 |
| iOS+Android 캡처 | Polycam(둘다) | 중 | 메시 포맷 일반화로 부분 해소; COLMAP 경로 experimental |

> **2026-05-05 → v0.22.1 진척**: 그때 "없음"으로 적힌 octave-band RT60·웹 뷰어·바이노럴·편집·메시 포맷
> 일반화는 **모두 구현됨**. 남은 gap 중 polygon ISM·가구는 **설계 완료(미구현)**, 측정·SPL coverage 는 미착수.

---

## 5. 향후 TODO

### 5.1 설계 완료, 구현 대기 (Feature-expansion 사이클 B4~B7 — 각 ADR critic 리뷰 반영 REVISED)

| ID | 항목 | ADR | 권장안 | 구현 전 blocking gate |
|---|---|---|---|---|
| **B7-A** | 흡음 가구 ObjectKind 확장 | [0043](adr/0043-absorptive-furniture-objectkind.md) | ACE equivalent-absorption; **ISM 은 sabin 직접 누적(B-2)** | D26-YAGNI: 가구 RT60 영향 ±20% 잠식 **검증 선행** 후 enum 개방 |
| **B5** | Ambisonics 배치 정식화 | [0041](adr/0041-ambisonics-placement-design.md) | 디코더용 규칙 리그 배치(t-design); SH 디코딩은 engine | engine 이 IRREGULAR ambisonics 리그를 디코더로 라우팅하는 합의 |
| **B6** | Live-mesh corner 추출 | [0042](adr/0042-live-mesh-corner-extraction.md) | alpha-shape concave hull; convex default 보존(회귀 0) | 비-tautological L-shape 메시 생성기 선결 |
| **B4** | Polygon/non-rectilinear ISM | [0040](adr/0040-polygon-ism-design.md) | pyroomacoustics 재사용 + core lazy-import; 3-티어 cascade | D29 web↔core 레인 결정(planner) |

> **권장 구현 순서**: B7-A(검증선행, 저렴) → B5 PR1 `x_target_algorithm`(OQ-38 종결) → B6 alpha-shape(의존0) → B4 polygon ISM(최대 작업).
> 4개 모두 Status=PROPOSED. 각 ADR §Reverse-criterion + PR 분할 참조. 추적 진실원천: `.omc/plans/feature-expansion-roadmap.md`.

### 5.2 열린 Open Questions (선택 항목)

- **OQ-46**: 웹 extras용 CI `pip-audit` + 의존성 lockfile (공개배포 보안 후속).
- **OQ-40**: gradio `col_count` deprecation (Gradio 6 런타임 마이그레이션).
- **OQ-35**: USDZ/glTF 음향 메타데이터 표준 (현재 `.acoustics.json` sidecar 우회; Apple/Khronos 표준 대기).
- **OQ-37/38**: edit round-trip 충실도(`notes`/`id`/`target_algorithm` 라벨) — 보고 0건 재유예 중. B5 가 `x_target_algorithm` 으로 OQ-38 종결 제안.
- **OQ-33**: mesh BoundingBox 가구 자동 클러스터링 — 미안정+GT 부재로 deferred.
- **OQ-13e**: live-mesh corner — B6 가 부분 resolution; SoundCam mesh access 는 확인 불가.
- **신규 제안(B4~B7 파생)**: coupled-space marker, non-shoebox 측정 GT 코퍼스, pra RT60 fit 신뢰성, t-design 좌표 출처, sofa/curtain α provenance, D74(alpha-shape + D6 mislabel cleanup).

### 5.3 경쟁 대응 후보 (미설계, 시장 gap 기반)

- **SPARTA/IEM JSON + SSR ASDF export 어댑터** — roomestim 출력의 두 번째 소비자 확보(채택 확대).
- **REW/miniDSP EQ profile stub** — SonarRoom 위협 직접 대응(그들의 최강 export).
- **pyroomacoustics ISM coverage 체크** — 배치 후 SPL 분포 빠른 확인.
- **Android/COLMAP-mobile 경로** — iPhone 외 디바이스 확장.

### 5.4 문서/정직성 부채

- **D6 mislabel cleanup**(D74): convex-hull deferral 을 D6(capture-device)으로 오귀속한 흔적(ADR 0027:5, mesh.py:7 docstring, decisions.md:1257/1848) 정정.
- mesh.py:7 docstring "XY-projected" → 코드는 XZ(`v[0],v[2]`) — stale 주석 정정.
- README 의 일부 stale 카운트는 v0.22.1 갱신으로 대부분 정정됨(이번 사이클).

---

## 6. 검증 상태 (2026-05-29)

- **게이트 GREEN**: default 287 passed/5 skipped, web 67 passed/4 skipped, ruff clean, tense-lint clean.
- **canonical env**: `/home/seung/miniforge3/bin/python -m pytest` (PATH pytest 는 web extras 누락으로 오보고).
- **엔드투엔드 스모크**: CLI 5종 + 웹 전 산출물(3D/리포트/바이노럴/PDF/ZIP) + RT60 예측기 3종 모두 실제 실행 확인. 실질 버그 0건.
- **설계 사이클**: B4~B7 4개 ADR 모두 architect 설계 → critic 리뷰(사실 오류·물리 결함 적발) → 반영 REVISED. 코드 무변경(설계만)이라 게이트 baseline 불변.

> 테스트 실행 방법은 `README.md` §"테스트 + 검증" 및 §"기능 스모크 테스트 가이드" 참조.
