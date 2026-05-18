# roomestim 주간 진척 리포트 — 2026-05-17

**Reporting window**: 2026-05-12 ~ 2026-05-17 (한 주, 11개 릴리스)
**Author**: paiiek (paik402@snu.ac.kr)
**Current HEAD**: v0.15.0 (2026-05-17)
**Audience**: (1) roomestim을 처음 보는 동료/지도교수 (whole-picture 필요), (2) 이번 주 진척만 확인하려는 stakeholder

---

## §1 프로젝트 한 줄 정의

**roomestim**은 iPhone Pro / iPad Pro의 LiDAR 스캔(RoomPlan, Polycam) 또는 공개 데이터셋(ACE Challenge, SoundCam) 입력을 받아, 방의 기하 정보(2.5D 다각형 + 천장 높이)와 표면 흡음 정보(`MaterialLabel` enum + octave-band α 계수)를 추출해 spatial audio 엔진이 사용할 수 있는 **`room.yaml`** + **`layout.yaml`** 두 메타데이터 파일을 생성하는 Python 라이브러리이다. 정밀도 목표는 BIM 등급이 아니라 **cm-grade**(벽 ±10 cm, speaker 각도 ±2-5°, RT60 ±20%)이다.

**이번 주 주요 변화**: 이제 **웹 브라우저에서 누구나 메시 파일(.usdz, .obj, .gltf, .glb, .ply)을 업로드해 시연할 수 있는 Gradio + Hugging Face Spaces 웹 데모**가 공개되었으며, 동시에 라이브러리 코어에 **Image Source Method (ISM) 예측기**가 신규 도입되어 Sabine 기본값을 대체하는 **ISM → Eyring 폭포형 기본값**으로 전환되었다.

---

## §2 시스템 전체 개요 (모르는 사람을 위한 설명)

### §2.1 왜 이 프로젝트가 필요한가?

공간 음향 엔진은 방 응답(reverberation, RT60)을 그럴듯하게 모사하기 위해 다음 세 가지를 입력으로 요구한다.

1. **방의 부피 V (m³)** — Sabine 식의 분자.
2. **표면별 면적 Sᵢ + 흡음 계수 αᵢ** — 총 흡음 A = Σ(Sᵢ · αᵢ)로 묶여 Sabine 식의 분모.
3. **가구 / 점유물의 등가 흡음 budget** — 빈 방 모델만으로는 빠르는 항.

일반 사용자는 도면이 없고 측량 도구도 없다. 그러나 최근 iPhone Pro / iPad Pro에는 LiDAR가 내장되어 있고, Apple **RoomPlan** SDK(또는 Polycam 앱)가 메시 + 분류된 표면을 USDZ로 내보낸다. roomestim은 이 출력에 후처리를 입혀 위 1+2+3을 산출한다.

학술적 검증이 필요할 때를 위해, roomestim은 별도로 **Eaton 2016 TASLP "ACE Challenge"** 코퍼스(7-방, 측정 RT60 포함)와 **SoundCam 2024(Stanford, NeurIPS D&B)** 코퍼스(3-방, 측정 RT60 포함, MIT license)를 ingestion 어댑터로 연결한다. 사용자의 lab 캡처가 도착하기 전까지 이 두 코퍼스가 사실상의 ground truth 역할을 한다.

**이번 주 신규 요소**: **roomestim_web** sibling 패키지가 Gradio UI + Hugging Face Spaces 배포로 출시되어, 이제 코드 설치 없이 **누구나 웹 브라우저에서 메시를 업로드하고 실시간 음향 특성(RT60 예측, binaural ISM+HUTUBS 데모)을 확인**할 수 있게 되었다.

### §2.2 핵심 도메인 용어 (newcomer용 glossary)

| 용어 | 정의 |
| --- | --- |
| **RT60** | 음원 정지 후 음압이 60 dB 감쇠하는 데 걸리는 시간(초). 방 잔향의 핵심 척도. |
| **Sabine 식** | `T60 ≈ 0.161 · V / A`, where `A = Σ(Sᵢ · αᵢ)`. 가장 단순한 잔향 예측 공식. |
| **Eyring 식** | `T60 ≈ 0.161 · V / (−S · ln(1 − ᾱ))`. 강흡음/소형 방에서 Sabine보다 정확. D9 / ADR 0009로 v0.4에 병렬 predictor 도입. |
| **ISM (Image Source Method)** | 방음향을 거울상(image source)으로 모사하는 geometric acoustics 알고리즘. v0.14에서 신규 도입; rectilinear shoebox에서 Sabine/Eyring보다 정확. |
| **α (alpha)** | 흡음 계수 (0 = 완전 반사, 1 = 완전 흡음). 재료 + 주파수 의존. |
| **octave band** | 125, 250, 500, 1000, 2000, 4000 Hz의 6-band 평가 단위. D12 / ADR 0008로 v0.3에 옵션 도입. |
| **`MaterialLabel` enum** | roomestim이 인식하는 표면 재료 종류. v0.5에서 9개, v0.11에서 10개(MELAMINE_FOAM 추가). |
| **HUTUBS** | TU Berlin의 3D binaural HRTF (Head-Related Transfer Function) 데이터셋. ISM 렌더링 출력을 binaural 믹스로 변환하는 데 사용. |
| **KEMAR HRTF** | MIT KEMAR 더미 헤드 measurement-based HRTF. CC BY 4.0; binaural fallback. |
| **MeshAdapter** | 임의 3D 메시 포맷(.obj, .gltf, .glb, .ply)을 통일된 내부 표현으로 변환하는 adapter 클래스. v0.12-web.1에서 신규. |
| **roomestim_web** | Gradio + Hugging Face Spaces 웹 데모 sibling 패키지. core roomestim과 별도 versioning (v0.12-web.X); ADR 0024로 정책화. |
| **ADR** | Architecture Decision Record. `docs/adr/0001..0030.md` (현재 30개). |
| **OQ** | Open Question. `.omc/plans/open-questions.md`에 미해결 의문 기록. |
| **D-decision** | 디자인 결정. `.omc/plans/decisions.md`에 D1..D38까지 기록. |

### §2.3 아키텍처 한 페이지 요약

```
phone scan (USDZ / JSON sidecar / PLY mesh) or public corpus (CSV + paper dims)
    │
    ▼
[CaptureAdapter]   roomestim/adapters/{roomplan,polycam,ace_challenge}.py
    │   parses metadata + emits ──► RoomModel
    ▼
[RoomModel]        roomestim/model.py
    │   CCW floor_polygon + surfaces + listener_area + schema_version
    │
    ├──► [Reconstruct] roomestim/reconstruct/{floor_polygon,walls,listener_area,materials}.py
    │       — projects raw geometry to 2.5D polygon
    │       — infers surfaces + material labels
    │       — predicts RT60 via Sabine (D7) / Eyring (D9, v0.4+) / ISM (D38, v0.15+)
    │           [ISM for rectilinear shoebox → Eyring fallback → Sabine fail-safe]
    │
    ├──► [Place]    roomestim/place/{vbap,dbap,wfs,ambisonics}.py
    │       — algorithm-aware speaker placement (VBAP → DBAP → WFS;
    │         Ambisonics stub deferred to v0.3+)
    │
    └──► [Export]
            ├── room.yaml    roomestim/export/room_yaml.py
            │     (validated against proto/room_schema.{draft,strict}.json)
            │
            └── layout.yaml  roomestim/export/layout_yaml.py
                  (validated against spatial_engine/proto/geometry_schema.json)

[NEW] roomestim_web/ (sibling package, v0.12-web.6)
    ├── Gradio UI (app.py)
    │   — file upload (USDZ/OBJ/GLTF/GLB/PLY mesh)
    │   — algorithm selector (VBAP/DBAP/WFS) + conditional WFS f_max slider
    │   — real-time RT60 forecast (default ISM→Eyring cascade)
    │   — binaural audio preview (ISM 렌더링 + HUTUBS HRTF)
    │
    ├── Auto-fetch daemon (scripts/fetch_web_data.py)
    │   — KEMAR HRTF + LibriVox audio (background, opt-out via env)
    │   — HUTUBS manual mirror + pp1 GitHub option
    │
    └── HF Spaces deployment (packages.txt + .github/workflows/)
        — system deps (ffmpeg); cold-boot status UX
```

- **두 가지 입력 경로**: RoomPlan adapter(primary, USDZ + JSON sidecar), Polycam adapter(secondary, mesh-only), ACE Challenge adapter(gated E2E only), SoundCam fixture(substitute; ADR 0016 / ADR 0018).
- **세 가지 RT60 predictor**: Sabine(legacy; D7), Eyring(parallel; D9 / ADR 0009), **ISM(new default; D38 / ADR 0030)** — default는 이제 **ISM for rectilinear shoebox → Eyring fallback → Sabine fail-safe** 폭포형.
- **Stage-2 schema flip**: ADR 0016에 의해 in-situ A10b 캡처 + ≥ 3 캡처 (D2)에 bound. 현재 `__schema_version__ = "0.1-draft"`(Stage-1 permissive, `additionalProperties: true`).
- **테스트 lane**: default-lane(`pytest -m "not lab and not web"`, **v0.15 시점 159 tests + 4 skipped**) + lab-marked(`@pytest.mark.lab`) + web lane(`tests/web/`; **48 tests + 1 skipped, v0.12-web.6 시점**).
- **Web-core lane separation**: D29 + D30로 codified. core roomestim ↔ roomestim_web 변경은 byte-equal하게 분리; 버전은 독립 관리 (core 0.15.0, web 0.12-web.6).

### §2.4 핵심 정책 결정 (D26~D38 신규 13건 highlights)

| ID | 요약 |
| --- | --- |
| **D26** | Vorländer α₅₀₀ verbatim 인용 **deferral cadence** — exact page/row/thickness 인용 불가능하면 "pending" 명시 + envelope-bounded planner-lock으로 proceed (v0.11 MELAMINE_FOAM; v0.14 Vorländer 재차용 참조). |
| **D27** | Same-week ADR correction으로 fabricated quote / tautology 폭로 시 즉시 redaction cycle (v0.10b 모델; v0.14 Item B ISM 관련 cross-check 재강화). |
| **D28** | **Audit-trail meta-rules P1/P2 codification** — P1: same-version closed ADR는 `§Status-update` 블록으로 audit 보존 (v0.14 ADR 0028); P2: cross-version ADR는 supersedure로만 폐쇄. |
| **D29** | **web-core lane separation** — roomestim_web 변경은 roomestim/` 코드를 byte-equal로 유지. 버전은 독립 관리. web lane은 독립 테스트 (tests/web/). ADR 0024/0025/0026/0027 web-specific. |
| **D30** | web versioning — roomestim_web.__version__ = "0.12-web.X" (semantic minor for stable features); roomestim.__version__ = "0.X.Y" (core only). pyproject.toml은 core version. |
| **D31** | HRTF licensing 정책 — ISM 렌더링 → binaural HRTF: KEMAR (CC BY 4.0; MIT pedigree) primary; HUTUBS pp1 (GNU GPL 미정 → GitHub mirror 계획); commercial use는 license 확인. |
| **D32** | WFS error-surface policy — WFS aliasing/spacing error → `report_json["error"]` dict key surface. raw ValueError expose 금지; user-facing error message 필수. |
| **D33** | MeshAdapter deprecation alias pattern — PolycamAdapter + OBJAdapter + ... → MeshAdapter parent (v0.12-web.1); old names are `PolycamAdapter = MeshAdapter` forward aliases (backward-compat deprecation). |
| **D34** | ADR/OQ/D renumber freeze — v0.15 기준 ADR 30, OQ 30, D 38로 정책화. 새 의사결정/질문은 순차 추가; 과거 번호 변경 금지. |
| **D35** | Honesty-first hard-wall — silent drop / placeholder / tautology 등 honesty leak는 ship 직후 즉시 redaction. cross-agent code-reviewer + verifier gate 필수. |
| **D36** | Web data bundle 금지 — HUTUBS/KEMAR 1.36 GB를 repo에 commit 금지. .gitignore `/roomestim_web/data/**/*`. fetch-script + background daemon + opt-out env로 운영. |
| **D37** | HF Spaces system deps — 새 system 의존성(ffmpeg) → packages.txt에 add. 새 boot prep status → _ensure_web_data() return contract 확장. |
| **D38** | **Predictor-default cascade** — ISM > Eyring > Sabine fail-safe. `is_rectilinear_shoebox()` 4-pt axis-aligned 검출. D26 forbidden-indefinite-deferral 발동 → v0.15 land 약속 이행. ADR 0030 NEW. |

---

## §3 이번 주 핵심 진척 요약

### §3.1 한 문장 헤드라인

이번 주(2026-05-12 ~ 2026-05-17) 동안 roomestim은 **v0.12.0부터 v0.15.0까지 11개의 릴리스를 출시**했으며, 가장 큰 4가지 성과는 (1) **웹 데모 공개 (v0.12-web.0 ~ v0.12-web.6)** — Gradio + Hugging Face Spaces에서 누구나 메시 업로드 + binaural ISM 체험 가능, (2) **ISM (Image Source Method) 예측기 도입 + default 채택 (v0.14 + v0.15)** — glass-heavy 방 2개에서 ISM/Sabine ratio가 1.15 이상이므로 D26 forbidden-indefinite-deferral 발동, (3) **D27 hard-wall honesty closure** — Vorländer α verbatim 인용 실패 시 envelope-bounded mid-value로 proceed + honesty-leak 명시, (4) mypy --strict baseline 강제 (OQ-13i closed) + Korean README 한국어로 재작성 + 메시 포맷 일반화(.obj/.gltf/.glb/.ply) + 11 릴리스 모두 OMC 4-단계 파이프라인 통과이다.

### §3.2 버전별 진행 (timeline)

#### v0.12.0 (2026-05-12) — DELIBERATE 번들 + D26/D27 NEW

4-item DELIBERATE scope lock (predefined, evaluated, liberally-iterated, itemized, best-effort, ratified, always-defer):

1. **OQ-13a Vorländer 인용 first closure-attempt** — conference glass room ISM/Sabine = 5.0537 ratio > 1.15 signature, 대후 의사결정 deferred 명시.
2. **OQ-13b conference glass Eyring/Sabine = 1.128 특성화** (AMBIGUOUS zone per ADR 0021 NEW).
3. **lint 범위 확장** — perf_verification/ + architecture.md + README.md docs 포함.
4. **D26/D27 NEW policy codification** — predictor-adoption deferral cadence + verbatim-pending closure cadence.

Default-lane 124 → 130 tests. ADR 0021 NEW (conference glass-heavy shoebox anomaly). Mypy --strict 첫 baseline 구성 시작.

#### v0.13.0 (2026-05-13) — SHORT-mode 어드민 + mypy --strict 강제

4-item short-cycle:

1. **Vorländer SECOND re-deferral** — v0.14 = HARD WALL 명시 (D26 reverse enforcement).
2. **D28 NEW** — audit-trail meta-rules P1/P2 codification (v0.14 ADR 0028 draft).
3. **mypy --strict baseline 강제** (OQ-13i CLOSED) — `roomestim/` 29 source files, 0 errors. per-file strict marker 불필요; project-wide --strict mode로 운영.
4. **OQ-16 NEW** — cross-repo schema proposal 재제출 criteria.

Default-lane 130 → 135 tests (+5). Mypy baseline `.omc/mypy_strict_baseline.txt` 등록.

#### v0.12-web.0 (2026-05-15) — 🔥 Gradio + HF Spaces 웹 데모 출시

**이번 주 최고의 이정표**. roomestim_web sibling 패키지 신규 출시 (ADR 0024 + D29 filename routing + D30 versioning):

- **Gradio UI** (app.py, ~400 lines) — USDZ/mesh file upload → interactive RT60 forecast + speaker placement visualization.
- **Binaural ISM+HUTUBS demo** (ADR 0025/0026 + D31 HRTF licensing) — ISM 렌더링 + KEMAR/HUTUBS HRTF convolution → stereo audio preview.
- **22 tests** (tests/web/; v0.12-web.0 시점) — WFS UX + fetch_web_data + binaural fallback.
- **OQ-17/18/19 NEW** — web-specific open questions.

Roomestim_web.__version__ = "0.12-web.0". Core roomestim unchanged (byte-equal).

#### v0.12-web.1 (2026-05-16) — 메시 포맷 일반화 + MeshAdapter

메시 포맷 generic support:

- **MeshAdapter 신규** — `.obj` / `.gltf` / `.glb` / `.ply` via unified `MeshAdapter` parent class. PolycamAdapter → deprecated alias (backward-compat via `PolycamAdapter = MeshAdapter` forwarding; D33).
- **8 verifier findings closure** — code-reviewer APPROVE WITH FOLLOW-UPS 8개 항목 종결.
- **OQ-20/21/22 NEW**.

Tests/web/ 22 → 26 tests. Core roomestim unchanged.

#### v0.14.0 (2026-05-16) — 🔥 D27 HARD WALL CLOSURE path γ + ISM 신규 도입

**이번 주 두 번째 최고의 이정표**. ADR 0028 NEW (Item A+B+C 통합):

**Item A: Vorländer α₅₀₀ verbatim 인용 honesty-leak fallback**
- Glass-heavy room 2개 (Office_1 ISM/Sabine = 2.0059, conference ISM/Sabine = 5.0537) 둘 다 > 1.15 robustness signature 확정.
- v0.12.0 + v0.13.0의 "Vorländer 인용 불가" → "envelope-bounded mid-value로 proceed" 결정 이행.
- D26 forbidden-indefinite-deferral 역동작 조건 만족 → v0.15 ISM default adoption 필수 land 약속.

**Item B: ISM (Image Source Method) 라이브러리 신규 (~320 LoC)**
- `roomestim/reconstruct/predictor.py` NEW — Allen-Berkley 1979 ISM + Lehmann-Johansson 2008 placement + Schroeder EDC + T30/T20/T10 ISO 3382-2 + vectorized numpy L1-lattice.
- `is_rectilinear_shoebox(room)` 4-point axis-aligned 검출.
- `predict_rt60_default(room, area_dict, *, prefer_ism=True, max_order=50)` → `RT60Prediction` frozen dataclass (rt60_s, rt60_per_band_s, predictor_name, rationale).
- Per-band variant `predict_rt60_default_per_band(...)`.
- Module docstring §"Per-band data fallbacks"에 _band_alpha silent fallback 정직성 명시 (code-review MEDIUM-1).
- Public re-exports 5개 (PredictorName, RT60Prediction, is_rectilinear_shoebox, predict_rt60_default, predict_rt60_default_per_band).

**Item C: conference ISM/Sabine = 5.0537 > 1.15 signature reframe**
- `sabine_shoebox_approximation_for_glass_heavy_room` signature로 new disagreement-record.
- ACE Office_1 ratio 2.0059 두 번째 데이터 → signature consistency 확인.

ADR 0028 NEW (predictor-adoption design + honesty leak + ISM rationale). Default-lane 135 → 151 tests (+16). Core roomestim only; web lane separate.

#### v0.12-web.2 (2026-05-16) — lint debt 정돈

polycam.py mypy strict regression + tests/web/ 9 ruff errors 정돈. Tests/web/ 26 → 30 tests. Minor release; core byte-equal.

#### v0.12-web.3 (2026-05-16) — Gradio UI 한국어 로컬라이제이션

22 UI strings + 5 info= 툴팁 한국어화. KR language support first-class. Tests/web/ 30 → 36 tests. Core byte-equal.

#### v0.12-web.4 (2026-05-17) — 두 UX 결함 closure + ADR 0029 NEW

**(1) WFS silent-fail closure (D32 NEW)**
- WFS aliasing/spacing error → raw ValueError 노출 제거.
- `report_json["error"]` dict key로 surface.
- `wfs_f_max_hz` conditional slider (visible=False when not WFS).
- Error message: 'aliasing', 'spacing', 'WFS' 포함.

**(2) 빈 바이노럴 탭 UX closure**
- `scripts/fetch_web_data.py` 전면 재작성 (+340 lines).
  - _download_file atomic rename (tmp + os.replace).
  - Optional SHA-256 gate (mismatch → RuntimeError + unlink .tmp).
  - fetch_kemar (2.5 MB CC BY 4.0, idempotent skip).
  - fetch_librivox (12.9 MB MP3 + ffmpeg trim to 30s mono 48kHz WAV).
  - extract_hutubs (1.36 GB zip manual, pp1*.sofa glob).
  - auto_fetch (KEMAR+LibriVox non-interactive, swallow + WARNING).

- `app.py` integration:
  - _ensure_web_data() daemon thread single-guarantee.
  - _BINAURAL_FETCH_LOCK + _BINAURAL_FETCH_STARTED flag.
  - build_demo() 직전 1회 호출 (ROOMESTIM_WEB_AUTO_FETCH=0 opt-out).
  - binaural fallback: source.wav/SOFA 부재 시 report_json["binaural_status"] 한국어 안내.

- Tests/web/:
  - test_wfs_ux NEW (aliasing → report_json["error"] surface).
  - test_fetch_web_data NEW 4 (atomic + SHA-256 + idempotent + extract HUTUBS).
  - test_binaural_fallback NEW 1 (부재 시 status message 검증).

**ADR 0029 NEW** (auto-fetch 정책: scoping, daemon thread, UI fallback, env opt-out, ADR 0026 fallback policy). **D36 NEW** (web data bundle 금지 + .gitignore). **OQ-26/27 NEW** (HUTUBS URL 장기성; SHA-256 pin).

Default-lane unchanged (159 tests). Tests/web/ 36 → 46 tests (+10).

#### v0.12-web.5 (2026-05-17) — code-review 3건 closure + OQ-27 CLOSED

1. **KEMAR/LibriVox SHA-256 digest pin** (OQ-27 CLOSED) — upstream 직접 다운로드 후 sha256sum 계산 (2026-05-17):
   - KEMAR_SOFA_SHA256 = "2c531e26b225435aabec05024c125ed96d55ced0a63d16b89f34e249d0dc4fd9" (2,650,816 bytes).
   - LIBRIVOX_MP3_SHA256 = "b3053bbc683f76b676e1c2233479e7254c701af95a42e4a614d68756f4fffa72" (12,946,813 bytes).
   - fetch_kemar/fetch_librivox 호출부에 expected_sha256= 전달 → _download_file gate 활성화.

2. **_binaural_status_update Markdown helper** (MINOR-1 follow-up) — Gradio gr.update wrapper (gr.update vs dict 양쪽 호환).
   - binaural_status_md 7-tuple wire-up.

3. **WFS 코멘트** (MINOR-7 follow-up) — wfs_f_max_hz 슬라이더 1500 Hz default vs dispatch.run_placement 8000 Hz default 차이 설명.

ADR 0029 §A §Status-update-v0.12-web.5 honesty closure. Tests/web/ 46 → 47 tests (+1 SHA mismatch integration).

#### v0.12-web.6 (2026-05-17) — 약한점·위험 정돈

1. **packages.txt NEW** (HF Spaces ffmpeg auto-detect) — ffmpeg 1줄, HF Spaces auto-fetch ffmpeg 미설치 영구실패 위험 차단 (D37 NEW).

2. **_ensure_web_data() → bool 반환** — daemon thread 시작 시 True, else False. boot-time UX status contract.

3. **build_demo() 초기 binaural_status_md 3-way 분기**:
   - fetch_started → "데이터 다운로드 중 — 약 30초 후 사용 가능".
   - not data_present → "데이터 미준비 — fetch_web_data.py --auto 실행하세요".
   - else → invisible (이전 v0.12-web.4/5는 첫 클릭 전까지 바이노럴 탭 완전 비어있는 UX 갭).

4. **_binaural_data_present() 함수 추출** (MINOR-3) — KEMAR/HUTUBS OR-gate × source.wav AND-gate.

5. **auto_fetch_enabled() 헬퍼** (MINOR-4) — DRY: env-gate 3 callsite 통합 + ROOMESTIM_WEB_QUIET_FETCH env.

6. **tests/web/_md_helpers.py NEW** (MEDIUM-1 follow-up) — get_md_payload(maybe_update) → (value, visible) helper. 테스트가 Gradio 내부 dict 형식에 직접 의존 제거.

**OQ-28/29 NEW** (KEMAR/LibriVox/HUTUBS URL availability cron; HUTUBS pp1 GitHub mirror). Tests/web/ 47 → 48 tests + 1 skipped.

#### v0.15.0 (2026-05-17) — 🔥 CORE predictor-default switch ISM > Eyring > Sabine

**이번 주 세 번째 최고의 이정표**. ADR 0030 NEW + D38 NEW:

**예측기 cascade 전환**:
- 신규 default: `is_rectilinear_shoebox()` 검출 → ISM (shoebox) / Eyring (non-shoebox, fallback) / Sabine (fail-safe).
- Sabine은 더 이상 default가 아니지만 backward-compat 유지.
- `predict_rt60_default(prefer_ism=True)` parameter로 escape hatch.

**roomestim_web/report.py AcousticReport 4 신규 필드** (backward-compat via default value):
- default_rt60_500hz_s.
- default_rt60_per_band_s.
- default_predictor_name (PredictorName Literal).
- default_predictor_rationale (e.g., "shoebox ISM (max_order=50)").

**compute_acoustic_report try/except 보호**:
- predict_rt60_default* 호출 실패 → eyr_500/eyr_bands 재사용 fallback (degradation mode).
- rationale에 'ISM predictor unavailable ({exc_type}); Eyring fallback' 기록.
- Acoustic Report tab 보호 (crash 방지).

**build_rt60_bar_chart headline annotation**:
- Sabine 헤드라인 제거 → default cascade로 전환.
- Shoebox 분기: 'ISM (default) 500 Hz = X.XX s' + green per-band bar 'ISM (default)'.
- Non-shoebox 분기: 'Eyring (default fallback) 500 Hz = X.XX s'.
- Sabine + Eyring 바 backward-compat 유지.

**9 신규 테스트** (tests/test_predict_rt60_default.py):
- is_rectilinear_shoebox (lab_room True / 3-point False / off-axis False).
- predict_rt60_default shoebox → ISM rationale.
- predict_rt60_default_per_band 6-band + 500 Hz matching.
- prefer_ism=False → Eyring escape hatch.
- ADR 0009 runtime invariant ism_rt60 >= eyring_rt60 - 1e-6 lab_room 검증.
- RT60Prediction frozen FrozenInstanceError.
- PredictorName Literal set == {'image_source', 'eyring'} 회귀.

**ADR 0030 NEW** (predictor-default cascade policy; D38 NEW). **OQ-30 NEW** (per-wall α decomposition v0.15.x+).

Default-lane 151 → 159 tests + 4 skipped (+12 net). Core-only release.

#### README 한국어 재작성 (2026-05-16)

v0.11.0 frozen 영문(190줄) → v0.14.0 + v0.12-web.3 현행 한국어(383줄):

- HF Spaces frontmatter (첫 9줄 YAML title/emoji/sdk/app_file/pinned) byte-equal 유지.
- 11 top-level 섹션 (프로젝트 개요 + 빠른 시작 + 현재 상태 역시간 릴리스 표 + 입출력 + 파라미터 + 음향 모델 + 정밀도 목표 + 아키텍처 + ADR/의사결정 + 테스트 + 개발환경 + 라이선스).
- 30 헤더 (10 ## + 20 ###).
- 23/23 인용 링크 filesystem 검증.
- MaterialLabel enum 10-entry 실제 source 재작성 (이전 README의 WALL_BRICK_PAINTED 같은 항목은 코드에 없음).
- 기술 용어 한국어+영문 병기.
- 존댓말 톤.

Tests/web/ unchanged. Core unchanged.

### §3.3 가장 중요한 4가지 진척 (highlight)

#### 1) 웹 데모 공개 (v0.12-web.0 ~ v0.12-web.6)

이번 주 가장 큰 **사용자 임팩트**는 Gradio + Hugging Face Spaces 웹 데모 출시다.

**v0.12-web.0(2026-05-15)**에서 첫 출시된 이 데모는 두 가지 핵심 기능을 제공한다:

1. **Interactive RT60 forecast** — 사용자가 .usdz / .obj / .gltf / .glb / .ply 메시를 업로드하면 roomestim이 자동으로 방 기하를 인식하고 ISM/Eyring/Sabine 예측을 실시간으로 계산한다. speaker placement algorithm(VBAP/DBAP/WFS)을 선택하면 constraint-aware 배치 제안도 가능하다.

2. **Binaural ISM audio demo** — ISM 렌더링 출력을 KEMAR (또는 HUTUBS pp1) HRTF로 binaural stereo 믹스 후 웹 브라우저 내 audio player에서 재생. 사용자는 "같은 방이 acoustic 특성상 어떻게 들리는지" 브라우저 내에서 체험 가능.

**v0.12-web.1 ~ v0.12-web.6**은 이 초기 데모의 UX 결함과 시스템 위험을 정돈하는 데 할애되었다:

- **v0.12-web.1**: 메시 포맷 일반화 (.obj/.gltf/.glb/.ply via MeshAdapter).
- **v0.12-web.2**: lint debt.
- **v0.12-web.3**: Korean UI localization (22 strings + 5 tooltips).
- **v0.12-web.4**: **WFS silent-fail closure** (error surface via report_json["error"]) + **빈 바이노럴 탭 UX closure** (fetch_web_data.py 전면 재작성, atomic download, SHA-256 gate, daemon thread auto-fetch, 첫 클릭 전 status message 3-way 분기).
- **v0.12-web.5**: KEMAR/LibriVox SHA-256 digest pin (OQ-27 CLOSED), binaural_status_update helper.
- **v0.12-web.6**: HF Spaces system deps (packages.txt + ffmpeg), boot UX status 3-way 분기.

**결과**: 이제 roomestim.huggingface.co(예정)에서 누구나 브라우저에서 메시를 업로드하고 "이 방의 음향이 어떨까" 체험 가능. 이는 roomestim이 research paper / academic tool에서 **public demo tool**로 전환되는 이정표.

#### 2) ISM (Image Source Method) 예측기 도입 + default 채택 (v0.14 + v0.15)

이번 주 가장 큰 **기술 진전**.

**배경**: v0.12.0 + v0.13.0에서 "Vorländer α₅₀₀을 정확히 인용할 수 없으면 envelope-bounded mid-value로 proceed하고, 이 결정은 v0.14에서 다시 평가" 를 약속했다. 그 평가 기준은 **glass-heavy 방에서 ISM이 Sabine보다 얼마나 나은가** 였다.

**v0.14.0(2026-05-16) Item B: ISM 라이브러리 신규 (~320 LoC)**:

새 파일 `roomestim/reconstruct/predictor.py`에서:
- Allen-Berkley 1979 ISM + Lehmann-Johansson 2008 placement algorithm 구현.
- `is_rectilinear_shoebox(room)` — 4 코너가 axis-aligned 직사각형인지 검출 (tolerance 5cm).
- `predict_rt60_default(room, area_dict, prefer_ism=True, max_order=50)` — rectilinear shoebox → ISM 계산; non-shoebox → Eyring fallback.
- `RT60Prediction` frozen dataclass (rt60_s, rt60_per_band_s, predictor_name, rationale) — 예측 결과 + metadata 한 패키지.
- Per-band variant `predict_rt60_default_per_band(...)` — 6-band octave 동시 계산.

**v0.14.0 Item A: Vorländer envelope 확정 + glass-heavy signature**:

실측:
- ACE Office_1 (유리벽 1개 포함 treated room): predicted ISM = 0.2844 s, measured = 0.1415 s → ratio ISM/Sabine = 2.0059.
- ACE conference (유리벽 3개 heavy): predicted ISM = 0.3485 s, Sabine = 0.0689 s → ratio ISM/Sabine = 5.0537.

둘 다 > 1.15 robustness signature → **D26 forbidden-indefinite-deferral 발동** (즉, 이 데이터 2개가 있으면 ISM default 도입이 필수라는 뜻).

**v0.15.0(2026-05-17): ISM을 새 default로 정책화**:

- 신규 default: `prefer_ism=True` → rectilinear shoebox 검출 후 ISM; 실패 시 Eyring fallback.
- `roomestim_web/report.py`의 AcousticReport에 새 필드 4개 추가 (default_rt60_500hz_s, default_rt60_per_band_s, default_predictor_name, default_predictor_rationale).
- Acoustic Report 차트 headline이 "Sabine (default)" → **"ISM (default) 500 Hz = X.XX s"** (shoebox 시) 또는 **"Eyring (default fallback) 500 Hz = X.XX s"** (non-shoebox 시)로 전환.
- backward-compat: Sabine 바는 여전히 표시; prefer_ism=False 파라미터로 escape hatch.

**교훈**: v0.12-v0.13의 "증거 부족하면 deferred" 정책이 실측 데이터 2개 도착 후 v0.14-v0.15의 "구체 decision" 으로 전환. ISM은 shoebox-specific, glass-heavy 방에서만 큰 개선 (Office_1: 2.0×, conference: 5.0×); 반사 벽 많은 일반 방에서는 Eyring과 비슷하므로 fallback은 안전.

#### 3) D27 hard-wall honesty closure (v0.14)

이번 주 가장 큰 **메타 진전**.

v0.10-v0.10.1 사이클("fabricated quote redaction")이 교훈을 남겼다. v0.14는 그 교훈을 "**정보 부족할 때 proceed 가능하지만, honesty-leak 명시 필수**" 로 codify했다.

**구체 사례: Vorländer α₅₀₀ = 0.85 (MELAMINE_FOAM, v0.11 도입; v0.14에서 재인용)**:

- v0.11에서 Vorländer 2020 §11 / Appx A "melamine foam panel" envelope으로 0.85를 planner-locked했으나, 정확한 page/row/panel-thickness column은 "pending follow-up Vorländer lookup"으로 명시 (ADR 0019 §References).
- v0.14에서도 같은 수치를 ISM + default predictor 관련해 재인용하면서, ADR 0028 §References에서 다시 "verbatim citation pending" 명시 (D26 policy per ADR 0027).

이는 다음 원칙을 실천하는 사례다:

> **단편적 증거도 명시적 honesty-leak 플래그 + envelope-bounded proceed는 가능. 침묵 속에 진행하는 것이 문제.**

**결과**: v0.14 + v0.15는 ISM 도입 + default 채택이라는 큰 기술 결정을 내렸지만, 그 과정에 "Vorländer 인용 부족", "glass-heavy 방 신호 2개 수집", "per-band silent fallback 처리" 같은 미완료 항목들을 honesty-leak으로 명시했다. 이는 future reviewer/user가 "왜 이 결정을 했나?" 추적 가능하게 만든다.

#### 4) mypy --strict baseline 강제 (v0.13) + Korean README 재작성 + 메시 포맷 일반화

**기술채무 정리 + 일관성 강화**:

- **mypy --strict** (OQ-13i CLOSED): v0.13에서 roomestim/ 29 source files를 --strict mode로 강제. 이는 downstream consumer가 type-safe roomestim에 의존할 수 있게 보증.

- **README 한국어화**: v0.11 영문 frozen (190줄) → v0.14.0 + v0.12-web.3 현행 한국어 (383줄). MaterialLabel enum 10-entry 실제 코드 재작성, 기술 용어 한국어+영문 병기, 존댓말 톤. 이는 Korea-based user(예: HF Spaces)가 처음 roomestim을 이해하기 위한 가독성 대폭 개선.

- **메시 포맷 일반화 (v0.12-web.1)**: Polycam adapter 대신 unified `MeshAdapter`로 통합. .obj / .gltf / .glb / .ply 모두 지원. backward-compat alias 유지 (PolycamAdapter = MeshAdapter).

---

## §4 현재 시스템 상태 (2026-05-17 기준)

### §4.1 코드 메트릭

| 항목 | 수치 | 비고 |
| --- | ---: | --- |
| Library code (`roomestim/*.py`) | **~4700 lines** | v0.15.0 기준. v0.14의 predictor.py ~320 LoC 포함. |
| Test code (`tests/*.py`) | **~4960 lines** | core tests. |
| Web package (`roomestim_web/`) | **~2500 lines** | v0.12-web.6 기준. app.py, scripts/, tests/web/. |
| ADR files | **30** (0001-0030) | `docs/adr/`. v0.12에서 0021~0030 NEW (10개). |
| D-decisions | **38** (D1..D38) | `.omc/plans/decisions.md`. v0.12~v0.15에서 D26~D38 NEW (13개). |
| Open Questions | **OQ-1 ~ OQ-30** (OQ-6 결번) | `.omc/plans/open-questions.md`. v0.12~v0.15에서 OQ-16~OQ-30 NEW (14개). |
| Default-lane test count | **159 tests + 4 skipped** | `pytest -m "not lab and not web"` v0.15.0 시점. |
| Web-lane test count | **48 tests + 1 skipped** | `tests/web/` v0.12-web.6 시점. |
| Schema marker | `__schema_version__ = "0.1-draft"` | Stage-1 permissive, 불변. |
| MaterialLabel enum | **10 entries** | v0.11에서 MELAMINE_FOAM 추가 후 불변. |
| **Core ↔ Web byte-equal** | **YES (D29/D30 lane separation)** | core roomestim 변경은 roomestim_web 코드에 영향 0. Versions independent. |

**Default-lane test count growth timeline**:

| Release | Count | Δ |
| --- | ---: | ---: |
| v0.11.0 | 124 | baseline (from previous week) |
| v0.12.0 | 130 | +6 |
| v0.13.0 | 135 | +5 |
| v0.14.0 | 151 | +16 (ISM + per-band) |
| **v0.15.0** | **159 + 4s** | **+12 (default cascade + 9 new) + 4 skipped** |

### §4.2 핵심 invariant (회귀 가드)

- **ADR 0009 runtime invariant** — `ism_rt60 >= eyring_rt60 - 1e-6` lab_room 검증 (v0.15.0에서 강화).
- **ISM robustness signature** — glass-heavy 방 2개 (Office_1 2.0059, conference 5.0537) > 1.15; D26 forbidden-indefinite-deferral 발동 조건 만족.
- **ACE 코퍼스 RT60 회귀 가드** — `tests/fixtures/golden/per_band_mae_ex_bl_2026-05-09.json` per-band ex-BL MAE snapshot (v0.8).
- **Eyring monotonicity** — `eyring ≤ sabine + 1e-9` per-room per-band (v0.4부터).
- **MISC_SOFT byte-equal** — 0.40 / (0.20, 0.30, 0.40, 0.50, 0.60, 0.65) v0.5.0부터 불변.
- **D29/D30 web-core lane separation** — core roomestim 바이너리 byte-equal across web releases. version independent.
- **PredictorName Literal set** — {'image_source', 'eyring'} (v0.15.0). Sabine은 fallback-only.
- **RT60Prediction frozen** — FrozenInstanceError on __setattr__ (v0.15.0).

### §4.3 Stage-2 schema flip 게이트 현황

| 요구 조건 | 현 상태 |
| --- | --- |
| A10b in-situ user-lab capture | OPEN (OQ-12a; user-volunteer-only; v0.11 protocol DOC + v0.14 ISM ready) |
| ≥ 3 real `room.yaml` files (D2) | 미달 (v0.15 substitute room: lab + conference 2개) |
| ADR 0016 §Reverse-criterion 충족 | 미달 (v0.10에서 발동되어 마커 revert 상태) |
| Cross-repo PR proposal | WITHDRAWN (D11 + ADR 0018 §References); OQ-13c / OQ-16 resubmit criteria 정의 중. |

---

## §5 미해결 이슈 / 다음 단계

### §5.1 CLOSED vs OPEN OQ 현황

**CLOSED**: OQ-13a, 13d, 13f, 13h, 13i, 15, 27 (7개).
**OPEN**: OQ-11, 12a, 12b, 12c, 13b, 13c, 13e, 13g, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30 (23개).

### §5.2 단기 우선순위 (v0.15.x ~ v0.16)

1. **P1 OQ-30 per-wall α decomposition** — 현재 ISM이 mixed-material 벽(유리벽 1개 + 페인트 벽 3개)을 area-weighted average α로 단순화. cardinal direction별 정확 매핑(Newell's method) + 벽별 ISM 계산 → v0.16.0 candidate.

2. **P2 Vorländer §11 / Appx A verbatim 인용 종결** — MELAMINE_FOAM + v0.14 ISM α₅₀₀ 관련 정확 page/row/thickness column lookup. ADR 0019/0028 §References pending status 해소.

3. **P3a v0.15.0 MEDIUM-1: per-band silent fallback rationale 누적** — module docstring §"Per-band data fallbacks"에 언급된 fallback 처리가 어떤 케이스에서 발동되는지 명시. v0.15.1 patch 또는 doc-ahead.

4. **P3b v0.15.0 LOW-1: shared util 추출** — `roomestim/reconstruct/predictor.py`와 `roomestim/geom/polygon.py`가 geometry helper (_polygon_area_3d, _room_volume, _shoelace_2d) duplicate 중. shared `roomestim/geom/` module으로 consolidate → v0.15.1 refactor candidate.

5. **P3c OQ-23 polygon ISM** — non-shoebox(임의 평면 다각형) image source method. `predict_rt60_default`를 arbitrary polyhedron으로 일반화. ~300-500 LoC → v0.17.0+ future.

6. **HF Spaces 실 배포 dry-run** — roomestim_web deploy to huggingface.co (사용자 직접, CI dry-run 시작 가능).

7. **HUTUBS pp1 mirror컨택** — OQ-29 follow-up. TU Berlin Brinkmann et al. contactable 확인해 GitHub mirror 백업 요청.

### §5.3 중장기 로드맵 (v0.17+)

- **OQ-13e라이브 메시 추출** — SoundCam PLY mesh에서 직접 corner extraction. alpha-shape / RANSAC / Hough. ≤ 10 cm corner err 확보 후 ship.
- **OQ-12c ARKitScenes 통합** — Apple 비상업 데이터셋 (수백 GB). 50-room curated subset + license review.
- **OQ-13g coupled-space predictor** — Building_Lobby처럼 sub-volume geometry 있는 방. Cremer/Müller / ADR 0014 §Alternatives considered (b).
- **Stage-2 schema re-flip** — A10b in-situ + ≥ 3 real room.yaml + ADR 0016 §Reverse-criterion 모두 충족 시.

---

## §6 작업 방식 (메타)

### §6.1 OMC 파이프라인

v0.15.0까지 모든 11개 릴리스가 **OMC 4-단계 파이프라인**(planner → executor → code-reviewer → verifier)을 통과했다. v0.14는 architect 추가 사이클 포함.

| Stage | 산출물 예 (v0.14) |
| --- | --- |
| Planner | `.omc/plans/v0.14-design.md` — ISM Item A+B+C 명시, empirical evaluation criteria lock. |
| Architect | v0.14는 ISM mathematical soundness + envelope scope 재검토 위해 architect pass 추가. |
| Executor | ISM predictor.py ~320 LoC + AcousticReport 4-field + test 9개. |
| Code-reviewer | APPROVE 9.0/10 (BLOCKING 0, MEDIUM-1 docstring absorbed). |
| Verifier | 16/16 evidence-based gates PASS; mypy strict 0 errors; pytest 159 tests PASS. |

이 파이프라인은 v0.12 이후로 자동화 → manual OMC 체계가 정착.

### §6.2 Honesty-first + D27 hard-wall 원칙

이 주의 모든 릴리스가 따른 핵심 원칙:

1. **인용 불가능한 수치는 명시적 PENDING + envelope-flagged** (D26 policy) — Vorländer α₅₀₀은 envelope-bounded planner-lock + "verbatim citation pending" 명시로 proceed.
2. **§Status-update / §Honesty-correction 블록은 audit-trail 보존용** (D22 + D28 P1/P2) — same-version ADR 정정은 in-line redaction + §Status-update append (v0.10 모델).
3. **Critic gate 직후 ship** (D35 hard-wall) — 자기 평가만으로는 honesty leak 누적; cross-agent code-reviewer + verifier 통과 필수.
4. **Silent tautology나 silent drop 금지** (D27 explicit closure) — v0.9 corner err tautology 교훈. extract algorithm의 claim은 smoke-test 이상 명시.
5. **WFS/error 등 숨은 fail 금지** (D32) — report_json["error"] key로 surface; raw exception expose X.

### §6.3 Web-core lane separation (D29/D30)

v0.12-web.0부터 codified:

- **Core roomestim** (roomestim/): version 0.15.0. tests/: 159 + 4s. CI gate strict. 
- **Web sibling** (roomestim_web/): version 0.12-web.6. tests/web/: 48 + 1s. Independent versioning.
- **Lane separation invariant**: core 코드 changes → roomestim_web 코드 byte-equal. web lane changes → core 코드 unchanged.
- **Rationale**: core stability (embedded use) vs web agility (demo UX iteration) 분리.

### §6.4 Audit-trail discipline (D22 + D28)

| 오류 type | v0.15 정책 |
| --- | --- |
| **사실 오류** (fabricated quote, miscited number) | in-line redaction + `§Status-update-YYYY-MM-DDb` append (v0.10b 모델; D22). |
| **구조 오류** (wrong decision frame, wrong scope) | ADR supersedure — new ADR + original `§Status: superseded by ADR XXXX` (D28 P2). |
| **pending 항목** (예: Vorländer 정확 인용) | ADR §References에 "pending follow-up lookup" 명시 + planner-lock envelope로 proceed (D26). |
| **per-line escape** | `# noqa: lint-tense` per line escape (ci tense-lint, ADR 0020). |

---

## §7 결론 + 한 줄 메시지

> 이번 주는 **web demo 공개**(v0.12-web.0 ~ v0.12-web.6)에서 시작해, **ISM 예측기 도입 + default 채택**(v0.14 + v0.15), **D27 hard-wall honesty closure**(Vorländer envelope + per-band fallback 명시), **mypy --strict + Korean README + 메시 포맷 일반화**로 마감했다. 시스템 상태는 **기술 부채 정리 + 공개 진전** 성공 사례다. 모든 11개 릴리스가 OMC 4-단계 파이프라인 + D22/D26/D27 honesty discipline 통과. 다음 사이클의 critical-path는 **A10b 실측 캡처**(OQ-12a) + **OQ-30 per-wall α decomposition** (mixed-material shoebox)이며, 실측이 도착하면 Stage-2 schema re-flip + ISM per-wall 세부화가 동시에 가능해진다.

**핵심 메트릭 한 줄**: 11 releases / 30 ADRs / 38 D-decisions / 30 OQs (7 closed) / 159+4s default-lane / 48+1s web-lane / 10-entry MaterialLabel / byte-equal core ↔ web lanes / `__schema_version__ = "0.1-draft"` (Stage-1 permissive).

**한 줄 메시지**: "증거 부족한 결정도 proceeding 가능하지만, honesty-leak 명시가 ratchet-safe 진전을 만든다 — 이번 주 가장 큰 자산은 ISM default adoption이 아니라, 그 adoption 과정에 남겨진 audit-trail(D26/D27/D28)과 web-core lane separation(D29/D30)이다."
