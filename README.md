---
title: roomestim — spatial audio configurator
emoji: 🏠
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: "4.0.0"
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

python -m roomestim run \
    --backend roomplan \
    --input tests/fixtures/lab_room.usdz \
    --algorithm vbap --n-speakers 8 --layout-radius 2.0 \
    --out-dir /tmp/roomestim_out

# 기본 레인 테스트 (lab / web / e2e 픽스처 제외)
pytest -m "not lab and not web and not e2e" -v

# CI 정직성 lint (honesty-leak 감사)
python scripts/lint_tense.py
```

---

## 현재 상태 (2026-05-16)

| 버전 | 날짜 | 커밋 | 주요 변경 |
|---|---|---|---|
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

> v0.14 가 **D27 cadence의 세 번째 사이클이자 HARD WALL CLOSURE**입니다.
> Vorländer 2020 §11 / Appendix A "melamine foam panel" verbatim citation은
> path γ (honesty-leak fallback, 다중 출처 envelope 채택)로 닫혔습니다.
> 자세한 결정 맥락은 [`docs/adr/0028-hardwall-closure-and-ism-adoption.md`](docs/adr/0028-hardwall-closure-and-ism-adoption.md) 와
> [`docs/adr/0019-melamine-foam-enum-addition.md`](docs/adr/0019-melamine-foam-enum-addition.md) §Status-update-2026-05-16 를 참조하세요.

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
| **Sabine** | `T₆₀ = 0.161 · V / Σ(αᵢ · Sᵢ)` | 저-흡음 발산 한계 (디폴트) | v0.1+ |
| **Sabine (octave)** | 동일 공식, 6-밴드 αᵢ | 옥타브 분해가 필요할 때 ([D8](.omc/plans/decisions.md)) | v0.3+ |
| **Eyring** | `T₆₀ = 0.161 · V / (−S · ln(1 − ᾱ))` | 중·고-흡음 영역 | v0.4+ ([ADR 0009](docs/adr/0009-eyring-parallel-predictor.md)) |
| **ISM** | Image-Source Method, Allen & Berkley 1979 + Lehmann-Johansson 2008 | shoebox 전용, 가장 물리적, 가장 비쌈 | v0.14+ ([ADR 0028](docs/adr/0028-hardwall-closure-and-ism-adoption.md)) |

v0.14 시점 default predictor는 Sabine입니다. polygon ISM은 v0.15+로 예정되어 있습니다.
conference room ISM / Sabine 비율이 5.05로 발산하는 현상은 ADR 0028 §Decision 에서
"glass-heavy room에 대한 Sabine-shoebox 근사"로 시그너처가 reframe되었습니다.
ACE Office_1 ratio = 2.01 결과는 D26 forbidden-indefinite-deferral 절을 발화시켜
v0.15+ 에서 default-predictor 전환을 강제합니다.

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
| Sabine RT60 | ±20% |

캡처 노이즈가 dominant 한 오차 원인이며, sub-cm 정밀도는 명시적인 reverse goal입니다.
이 정밀도 목표를 위반하면 lab A11 / ACE A11 게이트가 실패합니다.

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

- **ADR (Architecture Decision Record)** — [`docs/adr/0001` ~ `0028`](docs/adr/) 까지 28개의 ADR이 있습니다.
  최근 핵심:
  - [ADR 0024](docs/adr/0024-web-demo-separate-package.md) — 웹 데모를 sibling package로 분리
  - [ADR 0025](docs/adr/0025-binaural-demo-stack.md) — 바이노럴 데모 스택 (ISM + HUTUBS HRTF)
  - [ADR 0026](docs/adr/0026-hrtf-dataset-selection.md) — HRTF 데이터셋 선택 (HUTUBS CC BY 4.0)
  - [ADR 0027](docs/adr/0027-mesh-format-generalisation.md) — 메시 포맷 일반화 (.obj/.gltf/.glb/.ply)
  - [ADR 0028](docs/adr/0028-hardwall-closure-and-ism-adoption.md) — D27 HARD WALL CLOSURE + ISM 채택
- **결정 로그 (D1 ~ D35)** — [`.omc/plans/decisions.md`](.omc/plans/decisions.md). 단일 이슈에 대해
  Yes/No로 종결된 의사 결정과 reverse-criterion을 기록합니다. 최근 추가:
  - **D26** — Predictor-adoption deferral policy (characterise first, decide second)
  - **D27** — Verbatim-pending closure cadence
  - **D28** — Audit-trail process meta-rules (P1 hybrid pattern + P2 re-deferral cadence)
  - **D29 / D30** — 웹 트랙 parallel 출시 (filename routing + versioning)
  - **D31** — HRTF licensing & bundling policy
  - **D32** — Tempdir lifecycle (bounded deque + atexit reaper)
  - **D33** — MeshAdapter 단일 canonical class; PolycamAdapter는 deprecated subclass
  - **D34** — v0.14 ADR + OQ 재번호 audit-trail (0022/0023 → 0028/0029)
  - **D35** — v0.14.0 hard-wall closure under path γ
- **Open Questions** — [`.omc/plans/open-questions.md`](.omc/plans/open-questions.md)

---

## 테스트 + 검증

| 레인 | 명령 | 비고 |
|---|---|---|
| Default | `pytest -m "not lab and not web"` | 152개 default-lane 테스트 — Linux CI에서 항상 실행 |
| Web | `pytest -m web` | 37개 + 1 skip — `[web]` extras 필요 |
| Lab | `pytest -m lab` | A10/A11 — `tests/fixtures/lab_real.usdz` + ground-truth 필요 (human-gated) |
| E2E | `pytest -m e2e` | ACE Challenge / SoundCam 외부 코퍼스 (env-var gated) |

추가 도구:

- `python scripts/lint_tense.py` — present-tense 정직성 leak 감사 ([ADR 0020](docs/adr/0020-ci-lint-tense-policy.md))
- `mypy --strict roomestim/` — 32개 파일 baseline clean (v0.13+ 강제)
- `ruff check` — clean

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
| `[usd]` | pyusd (USDZ parser) |
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
tests/web/                  # 웹 데모 테스트 (37 + 1 skip)
scripts/lint_tense.py       # honesty-leak lint (ADR 0020)
docs/                       # architecture, room_yaml_spec, ADR 0001-0028, 주간 보고서
docs/adr/                   # 28개 architecture decision records
docs/perf_verification_*.md # 버전별 perf 스냅샷
docs/protocol_a10b_*.md     # in-situ 캡처 프로토콜 DOC
.omc/plans/                 # 설계 계획 (v0-design ~ v0.14-design) + decisions.md (D1-D35) + open-questions.md
RELEASE_NOTES_v*.md         # 버전별 릴리즈 노트
```

---

## OMC 파이프라인 (v0.11+)

trivial 하지 않은 변경은 모두 `planner → executor → code-reviewer → verifier` 네 단계를 거칩니다.
자세한 운영 메모는 `/home/seung/.claude/projects/-home-seung-mmhoa-roomestim/memory/MEMORY.md` 에 있습니다.
v0.11.0이 네 단계를 명시적으로 거친 첫 릴리즈이며, 이후 v0.12 ~ v0.14 모두 동일한 파이프라인으로
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

모든 git tag (`v0.1.1` ~ `v0.14.0` + `v0.12-web.0` ~ `v0.12-web.2`)는 **로컬 전용**입니다.
커밋만 `origin/main` 으로 push되고, tag push는 별도 ratification gate (현재 미정의)를 통해야 합니다.

---

## Schema marker

- `__schema_version__ = "0.1-draft"` (Stage-1 permissive)
- Stage-2 strict flip은 A10b in-situ 캡처에 묶여 있으며 ([ADR 0016](docs/adr/0016-stage2-schema-flip-via-substitute.md) §Reverse-criterion + [ADR 0018](docs/adr/0018-soundcam-substitute-disagreement-record.md)),
  v0.12+ 스코프에서 user-volunteer 캡처 후에 재개됩니다.

---

> 문제 제보 / 질문은 GitHub Issues 또는 sibling 레포의 PR 채널을 활용해주세요.
> 본 README는 lint scope에 포함되어 있으며, ADR 0020에서 정의한 honesty-leak 패턴이 발견되면
> CI가 차단합니다 — 본 한국어 본문은 해당 패턴(영문 present-tense 출시 framing)에서 자유롭게 작성되었습니다.
