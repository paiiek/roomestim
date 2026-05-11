# roomestim 주간 진척 리포트 — 2026-05-11

**Reporting window**: 2026-05-04 ~ 2026-05-11 (한 주, 8개 릴리스)
**Author**: paiiek (paik402@snu.ac.kr)
**Current HEAD**: `957c531` (v0.10.1) → v0.11.0 today
**Audience**: (1) roomestim을 처음 보는 동료/지도교수 (whole-picture 필요), (2) 이번 주 진척만 확인하려는 stakeholder

---

## §1 프로젝트 한 줄 정의

**roomestim**은 iPhone Pro / iPad Pro의 LiDAR 스캔(RoomPlan, Polycam) 또는 공개 데이터셋(ACE Challenge, SoundCam) 입력을 받아, 방의 기하 정보(2.5D 다각형 + 천장 높이)와 표면 흡음 정보(`MaterialLabel` enum + octave-band α 계수)를 추출해 spatial audio 엔진이 사용할 수 있는 **`room.yaml`** + **`layout.yaml`** 두 메타데이터 파일을 생성하는 Python 라이브러리이다. 정밀도 목표는 BIM 등급이 아니라 **cm-grade**(벽 ±10 cm, speaker 각도 ±2-5°, Sabine RT60 ±20%)이다.

**상위 컨텍스트**: 본 저장소(`/home/seung/mmhoa/roomestim/`)는 시리즈 작업의 한 축이다. 옆 저장소 `vid2spatial_v2`(`/home/seung/mmhoa/vid2spatial_v2/`)는 비디오에서 공간 정보를 추출하는 별도 라이브러리이고, `spatial_engine`(read-only sibling)은 두 라이브러리가 공급한 `room.yaml`/`layout.yaml`을 받아 실제 spatial audio(WFS, VBAP, DBAP, HOA)를 렌더링하는 엔진이다. roomestim은 spatial_engine을 위한 **room 메타데이터 공급자**이다.

---

## §2 시스템 전체 개요 (모르는 사람을 위한 설명)

### §2.1 왜 이 프로젝트가 필요한가?

공간 음향 엔진은 방 응답(reverberation, RT60)을 그럴듯하게 모사하기 위해 다음 세 가지를 입력으로 요구한다.

1. **방의 부피 V (m³)** — Sabine 식의 분자.
2. **표면별 면적 Sᵢ + 흡음 계수 αᵢ** — 총 흡음 A = Σ(Sᵢ · αᵢ)로 묶여 Sabine 식의 분모.
3. **가구 / 점유물의 등가 흡음 budget** — 빈 방 모델만으로는 빠르는 항.

일반 사용자는 도면이 없고 측량 도구도 없다. 그러나 최근 iPhone Pro / iPad Pro에는 LiDAR가 내장되어 있고, Apple **RoomPlan** SDK(또는 Polycam 앱)가 메시 + 분류된 표면을 USDZ로 내보낸다. roomestim은 이 출력에 후처리를 입혀 위 1+2+3을 산출한다.

학술적 검증이 필요할 때를 위해, roomestim은 별도로 **Eaton 2016 TASLP "ACE Challenge"** 코퍼스(7-방, 측정 RT60 포함)와 **SoundCam 2024(Stanford, NeurIPS D&B)** 코퍼스(3-방, 측정 RT60 포함, MIT license)를 ingestion 어댑터로 연결한다. 사용자의 lab 캡처가 도착하기 전까지 이 두 코퍼스가 사실상의 ground truth 역할을 한다.

### §2.2 핵심 도메인 용어 (newcomer용 glossary)

| 용어 | 정의 |
| --- | --- |
| **RT60** | 음원 정지 후 음압이 60 dB 감쇠하는 데 걸리는 시간(초). 방 잔향의 핵심 척도. |
| **Sabine 식** | `T60 ≈ 0.161 · V / A`, where `A = Σ(Sᵢ · αᵢ)`. 가장 단순한 잔향 예측 공식. |
| **Eyring 식** | `T60 ≈ 0.161 · V / (−S · ln(1 − ᾱ))`. 강흡음/소형 방에서 Sabine보다 정확. D9 / ADR 0009로 v0.4에 병렬 predictor 도입. |
| **α (alpha)** | 흡음 계수 (0 = 완전 반사, 1 = 완전 흡음). 재료 + 주파수 의존. |
| **octave band** | 125, 250, 500, 1000, 2000, 4000 Hz의 6-band 평가 단위. D12 / ADR 0008로 v0.3에 옵션 도입. |
| **`MaterialLabel` enum** | roomestim이 인식하는 표면 재료 종류. v0.5에서 9개(MISC_SOFT 추가), v0.11에서 10개(MELAMINE_FOAM 추가). |
| **ACE Challenge** | Eaton 2016 TASLP의 7-방 corpus (Office_1/2, Meeting_1/2, Lecture_1/2, Building_Lobby). |
| **SoundCam** | Stanford 2024 NeurIPS D&B 합성/측정 코퍼스 (lab, living_room, conference 3-방; MIT). v0.9에서 substitute로 도입, v0.10에서 living_room은 제거. |
| **A10 / A10a / A10b / A10-layout / A11** | 프로젝트 내부 acceptance ID. A10 = lab 캡처 + 코너 GT + 스피커 배치; A10a = synthesised SoundCam corner extraction smoke; A10b = in-situ 사용자 실측 (deferred, user-volunteer-only); A10-layout = VBAP-N speaker GT (non-substitutable per ADR 0017); A11 = ACE/SoundCam RT60 estimator gated E2E. |
| **ADR** | Architecture Decision Record. `docs/adr/0001..0020.md` (현재 19개 파일; ADR 0006은 결번). |
| **OQ** | Open Question. `.omc/plans/open-questions.md`에 미해결 의문 기록. 현재 OQ-1 ~ OQ-14, 그중 다수는 resolved 표시. |
| **D-decision** | 디자인 결정. `.omc/plans/decisions.md`에 D1..D25까지 기록. |
| **§Status-update / §Honesty-correction** | ADR 본문에 사후 갱신을 덧붙일 때 쓰는 in-line + append-block 패턴. D22(2026-05-10b)로 코드화. |
| **disagreement-record** | substitute prediction vs measured 사이의 차이를 `signature` 문자열과 함께 기록해 silent-pass를 막는 패턴. ADR 0018에서 정립. |

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
    │       — predicts RT60 via Sabine (D7) and Eyring (D9, v0.4+)
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
                  (validated against spatial_engine/proto/geometry_schema.json,
                   resolved at write-time via SPATIAL_ENGINE_REPO_DIR env var;
                   geometry_schema is NEVER vendored.)
```

- **두 가지 입력 경로**: RoomPlan adapter(primary, USDZ + JSON sidecar), Polycam adapter(secondary, mesh-only), ACE Challenge adapter(gated E2E only), SoundCam fixture(substitute; ADR 0016 / ADR 0018).
- **두 가지 RT60 predictor**: Sabine(default; D7), Eyring(parallel; D9 / ADR 0009). 두 predictor 모두 single 500 Hz(v0.1) + octave-band(v0.3+; D12 / ADR 0008) 모드 지원.
- **Stage-2 schema flip**: ADR 0016에 의해 in-situ A10b 캡처 + ≥ 3 캡처 (D2)에 bound. 현재 `__schema_version__ = "0.1-draft"`(Stage-1 permissive, `additionalProperties: true`); v0.9에서 한 번 `"0.1"`로 flip되었다가 v0.10에서 honesty correction으로 revert.
- **테스트 lane**: default-lane(`pytest -m "not lab and not e2e"`; CI-buildable on Linux; **v0.11 시점 124 tests**) + lab-marked(`@pytest.mark.lab`; skipped unless `tests/fixtures/lab_real.usdz` exists) + e2e gated(`@pytest.mark.e2e`; ACE corpus, `ROOMESTIM_E2E_DATASET_DIR` env var).

### §2.4 핵심 정책 결정 (D1..D25 highlights)

| ID | 요약 |
| --- | --- |
| **D2** | `room.yaml` schema acceptance는 v0.1 ship blocker가 아니다. Stage-2 lock(`additionalProperties: false`)은 A10 lab 캡처 + ≥ 3 real `room.yaml` 검증 이후. |
| **D7 / D12** | v0.1은 single 500 Hz α만. v0.3에서 6-band octave (125-4000 Hz) opt-in 추가. `--octave-band` CLI flag. |
| **D9** | Eyring을 Sabine 대체가 아닌 **parallel** predictor로 ship (v0.4). 런타임 invariant: `eyring ≤ sabine + 1e-9`. |
| **D11** | 모든 git tag는 **local-only**. commit만 origin/main push. tag push는 별도 ratification 게이트(미정의). |
| **D14** | `MISC_SOFT` enum row는 representative-not-verbatim policy. honesty marker로 명시. (v0.5 / ADR 0011) |
| **D16** | ACE 코퍼스 geometry는 arXiv:1606.03365 Table 1에서 검증 (open access); **materials는 Eaton 2016 TASLP 본문에 없음** — 추측해서는 안 됨. (v0.5.1 / ADR 0012) |
| **D17** | TASLP §II-C의 explicit furniture counts에서 per-room MISC_SOFT surface budget을 합성 (Vorländer 2020 §11 / Appx A primary). Building_Lobby는 coupled-space로 exclude. (v0.6 / ADR 0013 + ADR 0014) |
| **D21** | v0.10 honesty correction — v0.9의 substitute over-claims walk-back. Stage-2 marker `"0.1"` → `"0.1-draft"` revert. |
| **D22** | same-week-old ADR correction을 위한 **hybrid audit-trail discipline**: 사실 오류는 in-line redaction + 끝에 `§Status-update-YYYY-MM-DD` 블록 추가; 구조 오류는 ADR supersedure (새 ADR + `§Status: superseded`). (v0.10.1) |
| **D23** | v0.11.0 hybrid scope lock — 4-item closure set (MELAMINE_FOAM + band tightening + CI lint + protocol DOC). |
| **D24** | CI tense-lint policy 코드화 (v0.11 / ADR 0020). |
| **D25** | doc-ahead-of-implementation 패턴: capture commitment 없이 protocol DOC만 먼저 ship해도 됨 (v0.11; A10b in-situ protocol). |

---

## §3 이번 주 핵심 진척 요약

### §3.1 한 문장 헤드라인

이번 주(2026-05-04 ~ 2026-05-11) 동안 roomestim은 **v0.5.0부터 v0.11.0까지 8개의 minor/patch 릴리스를 출시**했으며, 가장 큰 4가지 성과는 (1) ACE Challenge 7-방 코퍼스에 대해 E2E RT60 특성 측정이 가능해진 점, (2) v0.9의 Stage-2 schema flip이 substitute-tautology로 판명되어 v0.10에서 **honesty correction**으로 revert되고 v0.10.1에서 fabricated quote redaction까지 한 사이클 완수한 점, (3) SoundCam 데이터셋 substitute 도입과 **disagreement-record 패턴** 확립 (ADR 0018), (4) 오늘(2026-05-11) ship된 **v0.11.0에서 MELAMINE_FOAM enum 도입으로 lab A11 PASS-gate 회복** (rel_err +2.40%)과 CI tense-lint(ADR 0020) 도입이다.

### §3.2 버전별 진행 (timeline)

#### v0.5.0 (2026-05-07) — partial-A + B
ACE 코퍼스 geometry를 arXiv:1606.03365 Table 1과 byte-검증. Office_2 dimension patch (`W` 3.50 → 3.22 m, `H` 3.00 → 2.94 m; `V_m³` 53.55 → 48.28). 동시에 `MaterialLabel.MISC_SOFT` enum slot 추가 (`α₅₀₀ = 0.40`, 6-band `(0.20, 0.30, 0.40, 0.50, 0.60, 0.65)`). materials는 paywall로 Eaton 2016 TASLP 직접 확인 불가 — deferred. **ADR 0010, ADR 0011 NEW; D15 NEW**. Default-lane 80 → 84 tests.

#### v0.5.1 (2026-05-07) — audit framing 정정
SNU IEEE Xplore로 Eaton 2016 TASLP final paper 입수. cover-to-cover 검토 결과 **per-surface material assignment table이 paper에 존재하지 않는다**는 사실 확인. v0.5.0의 "TASLP paywall 때문에 materials 확인 불가" framing은 잘못된 가정에 기반한 것이었으므로 "TASLP final reviewed; per-surface materials NOT in paper; canonical-source exhausted"로 정정. **ADR 0012 NEW; D16 NEW**. 라이브러리 코드 로직 변경 0, 테스트 수 변경 0 (84 유지).

#### v0.6.0 (2026-05-09) — TASLP-MISC surface budget
TASLP §II-C의 explicit furniture counts (Office_2 "6 chairs + bookcase"; Lecture_2 "~100 chairs + ~35 tables" 등)를 활용해 per-room MISC_SOFT surface budget을 합성. per-piece α는 **Vorländer 2020 §11 / Appx A primary** + Beranek 2004 Ch.3 Table 3.1 cross-check (`office_chair α₅₀₀ = 0.50`, `lecture_seat = 0.45`, `table = 0.10`, `bookcase = 0.30`). Building_Lobby는 coupled-space caveat로 의도적 exclude. **ADR 0013 NEW; D17 NEW**. Default-lane 84 → 100 tests. Lecture_1 Sabine 500 Hz 잔차가 +1.201 s → +0.125 s로 붕괴 (-1.076 s 개선).

#### v0.7.0 (2026-05-09) — WFS CLI ergonomics + Building_Lobby ADR
zero-risk additive 릴리스. (A) `roomestim run --algorithm wfs --n-speakers 8 --layout-radius 2.0`가 toss하던 raw `ValueError(kErrWfsSpacingTooLarge: ...)`를 두 가지 구체적 remediation path (`--wfs-f-max-hz`, `--n-speakers`)를 안내하는 메시지로 wrap. (B) Building_Lobby coupled-space exclusion을 explicit ADR로 ratify. **ADR 0014 NEW; D18 NEW**. Default-lane 100 → 104 tests. 라이브러리 numerical baseline 100% byte-equal.

#### v0.8.0 (2026-05-09) — Lecture_2 ceiling/seat bracketing + per-band MAE snapshot
v0.7 critic이 borderline ADR-theatre를 지적한 데 대한 응답으로 substantive numerical experiment 도입. 4개 variant (V0 baseline / V1 ceiling=`ceiling_drywall` / V2 unoccupied `lecture_seat` α / V3 V1+V2) + 1개 bounding case (V4, env-gated). Verdict는 **NULL**: V3가 Lecture_2 |err|를 −0.908 s → −0.879 s로만 줄였고 ±0.5 s 수용 envelope 미달 + Meeting_1/2를 +0.108 s/+0.142 s 회귀시킴. 이 null result 자체가 publishable finding. 동시에 per-band ex-BL MAE snapshot golden 도입으로 향후 PR 회귀 가드. **ADR 0015 NEW; D19 NEW; OQ-11 NEW**. Default-lane 104 → 111 tests.

#### v0.9.0 (2026-05-10) — A10a SoundCam substitute + Stage-2 schema flip (later reverted)
v0.8 strategic-position 분석이 "8 릴리스 동안 A10 lab 캡처 0% 진척" 데드락을 지적. 사용자가 v0.9 scope를 "공개 데이터셋 substitute"로 lock — SoundCam 2024 (Stanford NeurIPS D&B, MIT, arXiv:2311.03517)의 lab + living_room + conference 3-방을 substitute로 도입. **A10a corner err 0.00 cm by construction** (synthesised shoebox; 페이퍼 published dimensions에서 GT corner 합성), **A11 RT60 boost** lab 0.28% / living_room 5.57% / conference 15.92% PASS 보고. **`__schema_version__` `"0.1-draft"` → `"0.1"` flip**, cross-repo PR proposal text 작성. **ADR 0016 NEW; ADR 0017 NEW; D20 NEW; OQ-12a/b/c NEW**. Default-lane 111 → 118 tests. (이 v0.9 출시의 핵심 클레임 다수는 v0.10에서 walk-back된다 — §3.3 #2 참조.)

#### v0.10.0 (2026-05-10) — honesty correction
v0.9.0 critic verdict(2026-05-10, 4.4/10)가 구조적 honesty leak를 지적: 모든 SoundCam fixture file이 `citation_pending: true`였고, placeholder 값들이 default-enum Sabine prediction이 silent하게 ±20%를 통과하도록 골라져 있었다. 페이퍼 retrieval agent 확인 결과 lab 측정 RT60 = 0.158 s (not 0.350 s), conference = 0.581 s (not 0.550 s), living_room은 페이퍼 §A.2가 "방이 집의 나머지 부분과 명확한 벽으로 구분되지 않는다"고 명시 — authoritative dims 자체가 없음. **ADR 0016 §Reverse-criterion 발동**: Stage-2 marker `"0.1"` → `"0.1-draft"` revert; living_room fixture **제거**; A10a corner test는 smoke로 reframe (revealed-tautology 명시); A11 substitute는 PASS claim 대신 **disagreement-record 패턴**으로 재구성. **ADR 0018 NEW (substitute-disagreement record); ADR 0016 §Status-update-2026-05-10 in-place append; D21 NEW**. Default-lane 118 → 116 tests (-2 from living_room removal). Disagreement-record 표:

| Room | Predicted (s) | Measured (s) | Rel-err | Signature |
| --- | ---: | ---: | ---: | --- |
| lab | 0.254 | 0.158 | +60% | `default_enum_underrepresents_treated_room_absorption` |
| conference | 0.449 | 0.581 | -22.7% | `sabine_shoebox_underestimates_glass_wall_specular` |

#### v0.10.1 (2026-05-10b) — factual-integrity patch
v0.10 critic verdict(7.6/10 composite)이 ADR 0018 §Drivers item 2의 **fabricated quote** (`living_room measured 1.121 s vs placeholder 0.45 s = 2.5× error` — `1.121 s`가 어느 곳에서도 인용되지 않음)를 MED honesty-leak로 지적. 동시에 SoundCam fixture `README.md` body가 v0.10 §Honesty-correction prepend block 뒤에서 여전히 v0.9 placeholder regime을 현재 시제로 서술하던 문제도 지적. ADR 0018 line 46 in-line redaction + `§Status-update-2026-05-10b` 첨부; README 본문 past-tense 재서술 + `[v0.9-historical, superseded by §Honesty-correction-2026-05-10]` marker prepend; `.omc/plans/v0.10-design.md` line 702 동일 redaction. **D22 NEW (hybrid audit-trail discipline 코드화); OQ-13f, OQ-13g, OQ-13h, OQ-13i NEW**. 라이브러리 코드 변경 0, 테스트 수 변경 0 (116 유지).

#### v0.11.0 (2026-05-11, **오늘 출시**) — hybrid scope 4-item closure
v0.10.1이 명시적으로 v0.11으로 deferred 한 4개 항목을 종결.

1. **MELAMINE_FOAM enum 추가** (OQ-13a 종결; ADR 0019 NEW). `MaterialLabel.MELAMINE_FOAM = "melamine_foam"` (enum 9 → 10 entries). `MaterialAbsorption[MELAMINE_FOAM] = 0.85` (α₅₀₀; **Vorländer 2020 §11 / Appx A**로 planner-locked envelope; 정확한 verbatim citation은 follow-up pending로 honestly flagged in ADR 0019 §References). 6-band `(0.35, 0.65, 0.85, 0.92, 0.93, 0.92)`. Lab fixture에서 wall material을 `misc_soft` → `melamine_foam`으로 flip.
2. **Lab A11 PASS-gate 회복 + 결함 band tightening** (OQ-13f 종결). §2.4 executor decision-point에서 한 번 측정 실행 후 결과에 따라 sub-branch A(PASS-gate) vs B(disagreement-band)를 선택하는 절차 적용. 실측 결과: **predicted = 0.161795 s, measured = 0.158 s, rel_err = +2.40%** — sub-branch A 채택, **PASS-gate 회복**. `_LAB_EXPECTED` band를 PASS-gate 값으로 교체 (`rel_err_min = -0.20`, `max = +0.20`, `signature = "RECOVERED_under_melamine_foam_enum"`). Lab umbrella `test_a11_soundcam_lab_disagreement_record` → `test_a11_soundcam_lab_band_record` 개명 + 새 companion `test_a11_soundcam_lab_pass_gate_recovered` 추가. Conference disagreement-band byte-equal + 구조 sign assert `assert rel_err < -0.10` 추가 (belt-and-braces).
3. **CI tense-lint policy** (OQ-13h 종결; ADR 0020 NEW; D24 NEW). standalone `scripts/lint_tense.py` (~110 lines) + `.github/workflows/ci.yml`의 `Lint (tense)` step. Scope: `tests/fixtures/**/README.md`, `docs/adr/*.md`, `RELEASE_NOTES_v*.md` (current-version `RELEASE_NOTES_v0.11.0.md`는 제외). Pattern: word-bounded `\bwe ship\b | \bship in v0\.[0-9]+\b`. Block exclusion: `## §Status-update-` / `## §Honesty-correction-` (D22 audit-trail 패턴 존중). Per-line `# noqa: lint-tense` escape. **live-repo first run: 0 files flagged**.
4. **In-situ A10b protocol DOC** (OQ-12a status-update; D25 NEW). `docs/protocol_a10b_insitu_capture.md` (90 lines, minimal stub). §1 Scope, §2 Corner GT acceptance criteria, §3 Scan device list, §4 Minimum scan completeness, §5 ABORT criteria, §6 Cross-references. **protocol-only; capture commitment 없음 — A10b actual capture는 여전히 user-volunteer-only**.

**ADR 0019, ADR 0020 NEW; D23, D24, D25 NEW; OQ-14 NEW (FIBERGLASS_CEILING + TILE_FLOOR v0.12+ defer)**. Default-lane 116 → **124 tests** (+5 net additions vs v0.10.1; pre-flight 119 baseline). `__schema_version__`은 `"0.1-draft"` 유지 (Stage-2 re-flip은 A10b in-situ + ≥ 3 캡처에 bound, v0.11은 substitute room 2개뿐).

### §3.3 가장 중요한 4가지 진척 (highlight)

#### 1) ACE Challenge 7-방 코퍼스 E2E 적용 가능 (v0.4 → v0.6)

이번 주 시작 시점에 가장 큰 미해결 항목은 "라이브러리는 동작하는데 검증 대상이 없다"였다. ACE Challenge 코퍼스(Eaton 2016 TASLP의 7 방: Office_1, Office_2, Meeting_1, Meeting_2, Lecture_1, Lecture_2, Building_Lobby)는 측정 T60 octave-band 데이터를 제공하므로 검증 대상으로 이상적이지만, 라이브러리가 코퍼스를 ingest하려면 (a) 7-방 dimensions, (b) 7-방 per-surface material 매핑, (c) 7-방 가구 적재량 정보가 필요하다.

v0.4-v0.6 사이에 이 세 가지가 정리되었다. (a)는 v0.5.0 + v0.5.1에서 arXiv:1606.03365 Table 1 (TASLP supporting material; open access)로 검증 + Office_2의 dimension 오류 patch. (b)는 v0.5.1 audit에서 "**materials는 paper에 없음**"이 확인되어 D16 / ADR 0012로 indeterminate-not-blocked 처리 — 추측해서 채우는 대신 honesty caveat로 명시. (c)는 v0.6에서 TASLP §II-C의 explicit furniture counts (Office_2 "6 chairs + bookcase"; Lecture_2 "~100 chairs + ~35 tables" 등)를 per-piece α (Vorländer 2020 §11 / Appx A primary)와 곱해 per-room MISC_SOFT surface budget으로 합성 (ADR 0013 / D17).

이 결과 Lecture_1의 Sabine 500 Hz 잔차가 v0.5 +1.201 s에서 v0.6 +0.125 s로 -1.076 s 만큼 붕괴했다. 동시에 per-band MAE snapshot golden(v0.8 / ADR 0015 / D19)이 도입되어 향후 PR이 residual을 silent하게 키울 경우 회귀 가드가 작동한다.

#### 2) Honesty correction 사이클 (v0.9 → v0.10 → v0.10.1)

이번 주 가장 중요한 메타-진척이다.

v0.9.0(2026-05-10)은 "8 릴리스 deadlock 해소"를 명분으로 SoundCam 데이터셋을 substitute로 도입하고 `__schema_version__`을 `"0.1-draft"`에서 `"0.1"`로 flip했다. ship 시점 release notes는 "A10a PASS — corner err 0.00 cm by construction", "A11 SoundCam RT60 boost — all 3 rooms within ±20%", "Stage-2 schema flip"을 헤드라인으로 제시했다.

**v0.9 critic verdict (2026-05-10, 4.4/10)이 다음을 지적했다**:
- 모든 SoundCam fixture file이 `citation_pending: true`였다 — placeholder 값.
- placeholder는 default-enum Sabine prediction이 silent하게 ±20%를 통과하도록 골라져 있었다.
- 페이퍼 retrieval로 확인된 실측치는 lab **0.158 s** (not placeholder 0.350 s), conference **0.581 s** (not placeholder 0.550 s); living_room은 페이퍼가 "방이 집의 나머지 부분과 명확한 벽으로 구분되지 않는다"고 명시 — authoritative dims 자체가 없음.
- "corner err 0.00 cm by construction"은 구조적 tautology — GT corner와 predicted corner를 같은 published dimensions에서 동시 합성하면 0.00 cm는 코드와 무관하게 항상 출력된다.

**v0.10.0 (같은 날 후속) 대응**:
- **ADR 0016 §Reverse-criterion 발동** — 이 조항은 본래 substitute-vs-in-situ disagreement를 위해 설계되었으나, 페이퍼-retrieved 실측치 자체가 partial in-situ 역할을 한다고 해석.
- Stage-2 marker `"0.1"` → `"0.1-draft"` revert.
- living_room fixture **제거** (3-방 → 2-방). v0.9 release notes body 보존, prepend `§Honesty-correction-2026-05-10` 블록 추가.
- A10a corner test → smoke로 reframe (revealed-tautology 명시).
- A11 substitute → **disagreement-record 패턴**으로 재구성: PASS/FAIL claim 대신 `(predicted, measured, rel_err, signature)` 튜플을 기록하고 sign assertion으로만 가드.
- ADR 0018 NEW (substitute-disagreement record + remediation plan). ADR 0016 §Status-update-2026-05-10 in-place append.

**v0.10.1 (2026-05-10b) factual-integrity patch**:
v0.10 critic verdict(7.6/10 composite)이 ADR 0018 자체에서 새 honesty-leak를 발견 — §Drivers item 2의 line 46이 `living_room measured 1.121 s` 같은 출처 없는 수치 인용을 포함. 동시에 SoundCam fixture `README.md` body가 v0.10 prepend block 뒤에서 v0.9 placeholder regime을 여전히 현재 시제로 서술. ADR 0018 in-line redaction + `§Status-update-2026-05-10b` 첨부; README past-tense 재서술 + `[v0.9-historical, superseded]` marker. **D22 NEW** — same-week-old ADR correction을 위한 hybrid audit-trail discipline 코드화 (사실 오류 = in-line + status-update; 구조 오류 = ADR supersedure).

**교훈**: silent fabrication을 잡는 cross-agent verification(critic 7.6/10 verdict)이 효과를 입증. 매주 ship 직후 critic pass를 통과하지 않으면 leak가 누적된다.

#### 3) v0.11 MELAMINE_FOAM 도입 + lab A11 PASS-gate 회복

오늘 출시된 v0.11.0의 가장 가시적 성과. v0.10.1이 deferred한 4-item hybrid scope (D23) 중 첫 번째 항목이자, 사실상 v0.9-v0.10 사이클이 폭로한 **"default 9-entry enum이 treated 방을 represent하지 못한다"** 문제를 라이브러리 수준에서 해결한 것이다.

| 단계 | 내용 |
| --- | --- |
| Planner | 1123-line design plan(`.omc/plans/v0.11-design.md`)에서 §2.4 executor empirical decision-point procedure 명시: 한 번 테스트 실행 후 결과에 따라 sub-branch A(PASS-gate 회복) vs B(여전히 disagreement)를 선택. |
| Executor | 16 file-ops (라이브러리 + 테스트 + ADR + 문서 + bookkeeping). `MaterialLabel.MELAMINE_FOAM = "melamine_foam"` 추가, `α₅₀₀ = 0.85` 등록, 6-band `(0.35, 0.65, 0.85, 0.92, 0.93, 0.92)`. Lab fixture에서 wall material `misc_soft` → `melamine_foam` flip. |
| 실측 | `predicted = 0.161795 s`, `measured = 0.158 s`, `rel_err = +2.40%`. sub-branch A 채택. |
| Code-reviewer | APPROVE 9.0/10 (모든 BLOCKING 통과). |
| Verifier | 16/16 evidence-based gates PASS. |

수치 인용 status: α₅₀₀ = 0.85는 Vorländer 2020 §11 / Appx A "melamine foam panel" / "acoustic foam absorber" envelope으로 **planner-locked**이지만, 정확한 page/row/panel-thickness column verbatim citation은 follow-up Vorländer lookup으로 **honestly pending** (ADR 0019 §References에 명시). 이는 D14 / OQ-2의 representative-not-verbatim policy + v0.10 fabricated quote 사건의 교훈을 함께 반영한 처리.

#### 4) CI tense-lint policy 도입 (v0.11; ADR 0020)

v0.10.1이 발견한 README-tense-mismatch 패턴 — `RELEASE_NOTES`나 ADR 본문에 `"we ship"`, `"ship in v0.9"` 같은 version-specific 현재 시제 framing이 들어가면 후속 버전에서도 여전히 현재 시제로 읽혀 "이 버전이 지금 ship 중이다"는 잘못된 인상을 준다 — 을 막기 위한 lightweight CI 가드.

- **Scope**: `tests/fixtures/**/README.md`, `docs/adr/*.md`, `RELEASE_NOTES_v*.md`. current-version `RELEASE_NOTES_v0.11.0.md`는 의도적 asymmetry로 제외 (release notes는 출시 시점에 현재 시제가 자연스럽다).
- **Pattern**: word-bounded `\bwe ship\b | \bship in v0\.[0-9]+\b`.
- **Block exclusion**: `## §Status-update-` / `## §Honesty-correction-` 블록 내부 (D22 audit-trail 패턴 존중 — 과거 버전의 framing을 보존해야 하므로 lint 면제).
- **Per-line escape**: `# noqa: lint-tense`.
- **Live-repo first run flagged 0 files** (v0.11 design §0.4 STOP rule #7 threshold > 3 well below).
- standalone `scripts/lint_tense.py`(~110 lines) + `.github/workflows/ci.yml`의 `Lint (tense)` step (`Type-check (mypy)` ↔ `Test (pytest, skip lab fixtures)` 사이).

이는 향후 ship 사이클에서 v0.10의 README-tense 사건이 재발하는 것을 자동으로 막는다.

---

## §4 현재 시스템 상태 (2026-05-11 기준)

### §4.1 코드 메트릭

| 항목 | 수치 | 비고 |
| --- | ---: | --- |
| Library code (`roomestim/*.py`) | **4072 lines** | `wc -l` total. |
| Test code (`tests/*.py`) | **4960 lines** | `wc -l` total. |
| ADR files | **19** (0001-0020, 0006 결번) | `docs/adr/`. |
| D-decisions | **25** (D1..D25) | `.omc/plans/decisions.md`. |
| Open Questions | **OQ-1 ~ OQ-14** (다수 resolved) | `.omc/plans/open-questions.md`. |
| Release notes files | **11** (v0.1.1, v0.2.0_v0.3.0 합본, v0.4.0, v0.5.0, v0.5.1, v0.6.0, v0.7.0, v0.8.0, v0.9.0, v0.10.0, v0.10.1, v0.11.0) | repo root. |
| Default-lane test count | **124** (`pytest -m "not lab and not e2e"`) | v0.11.0 시점. |
| Schema marker | `__schema_version__ = "0.1-draft"` | Stage-1 permissive. v0.9에서 `"0.1"` flip 후 v0.10에 revert; v0.11 unchanged. |
| MaterialLabel enum | **10 entries** | v0.5에서 9 (MISC_SOFT 추가), v0.11에서 10 (MELAMINE_FOAM 추가). |

**Default-lane test count growth timeline**:

| Release | Count | Δ |
| --- | ---: | ---: |
| v0.1.1 | 28 | baseline |
| v0.2 + v0.3 | 75 | +47 (octave-band + ACE adapter unit) |
| v0.4.0 | 80 | +5 (Eyring) |
| v0.5.0 | 84 | +4 (MISC_SOFT) |
| v0.5.1 | 84 | 0 (audit-only) |
| v0.6.0 | 100 | +16 (TASLP MISC_SOFT budget) |
| v0.7.0 | 104 | +4 (WFS ergonomics) |
| v0.8.0 | 111 | +7 (bracketing +5, snapshot +2) |
| v0.9.0 | 118 | +7 (A10a +3, A11 +3, schema +1) |
| v0.10.0 | 116 | -2 (living_room 제거) |
| v0.10.1 | 116 | 0 (audit-trail patch) |
| **v0.11.0** | **124** | **+8** (band-record umbrella +1, MELAMINE_FOAM band +2, MISC_SOFT range +1, tense-lint +1, lab PASS +1, etc.) |

### §4.2 핵심 invariant (회귀 가드)

- **ACE 코퍼스 RT60 회귀 가드** — `tests/fixtures/golden/per_band_mae_ex_bl_2026-05-09.json` per-band ex-BL MAE snapshot (v0.8 / D19). 향후 PR이 predictor / adapter / per-band table을 건드려 MAE를 ±0.001 s 이상 shift시키면 fail.
- **MISC_SOFT row byte-equal across versions** — `MaterialAbsorption[MISC_SOFT] = 0.40`, 6-band `(0.20, 0.30, 0.40, 0.50, 0.60, 0.65)` v0.5.0부터 v0.11.0까지 byte-equal. `band-2 == legacy scalar` invariant runtime assert.
- **Eyring monotonicity** — `eyring_500hz ≤ sabine_500hz + 1e-9` per-room per-band runtime assert (v0.4부터; Vorländer 2020 §4.2).
- **ADR 0001..0017 byte-equal post-v0.10.1** — ADR 0018만 v0.10.1에서 `§Drivers item 2` redaction + `§Status-update` append. v0.11은 ADR 0018 재편집 0; closure는 ADR 0019 §References에서 cross-reference.
- **`__schema_version__ == "0.1-draft"`** — v0.9에서 한 번 `"0.1"`로 flip 후 v0.10에서 revert; v0.10.1, v0.11.0 unchanged. Stage-2 re-flip은 (a) A10b in-situ 캡처 + (b) ≥ 3 real `room.yaml` per D2 + (c) ADR 0016 §Reverse-criterion 충족 모두 필요.

### §4.3 Stage-2 schema flip 게이트 현황

| 요구 조건 | 현 상태 |
| --- | --- |
| A10b in-situ user-lab capture | OPEN (OQ-12a; user-volunteer-only; v0.11 protocol DOC만 ship) |
| ≥ 3 real `room.yaml` files (D2) | 미달 (v0.11 substitute room: lab + conference 2개) |
| ADR 0016 §Reverse-criterion 충족 | 미달 (v0.10에서 발동되어 마커 revert 상태) |
| Cross-repo PR proposal | WITHDRAWN (D11 + ADR 0018 §References) |

---

## §5 미해결 이슈 / 다음 단계 (next steps)

### §5.1 OQ 14개 중 현재 OPEN 상태

| OQ | 내용 | 후보 release |
| --- | --- | --- |
| **OQ-11** | Lecture_2 ratification 3-조건 게이트 (acceptance envelope ±0.5 s + non-regression ≤ +0.1 s + independent evidence) | v0.12+ |
| **OQ-12a** | A10b in-situ user-lab capture (사용자 lab 방문 + iPad LiDAR + 측정 마이크 + 1일 일정) | user-volunteer-only (v0.11에서 protocol DOC만 ship) |
| **OQ-12b** | AnyRIR (ICASSP 2026 / arXiv 2025-10) watchlist promotion | passive watchlist; 페이퍼/데이터셋 follow-up 시 재평가 |
| **OQ-12c** | ARKitScenes (Apple 2021) scoping | v0.10+ deferred (license + hundreds-of-GB scope) |
| **OQ-13b** | Glass-heavy 방에서 Sabine-shoebox residual study (mirror-image or ray-tracing 비교) | v0.12+ |
| **OQ-13c** | Cross-repo PR (`spatial_engine/proto/room_schema.json`) 재제출 criteria | v0.12+ |
| **OQ-13e** | Live-mesh corner extraction (SoundCam PLY 메시에서 alpha-shape / RANSAC / Hough) | v0.12+ |
| **OQ-13g** | Same-week ADR correction discipline (D22로 codified, structural error 시 supersedure 적용) | active policy |
| **OQ-13i** | mypy strict project commitment (`roomestim/adapters/ace_challenge.py:554-556`의 3 pre-existing strict errors) | v0.12+ |
| **OQ-14** | FIBERGLASS_CEILING + TILE_FLOOR enum 추가 (v0.11 시점 NEW) | v0.12+ (lab이 MELAMINE_FOAM만으로 PASS-gate 회복; immediate need 없음) |

### §5.2 단기 우선순위 (v0.12 후보)

1. **A10b 실측 캡처** — OQ-12a 종결을 위한 사용자 lab 방문. 1일 calendar slot + iPad Pro LiDAR + 측정 마이크 필요. v0.11의 protocol DOC가 corner GT acceptance criteria(±10 cm), scan device list, minimum scan completeness, ABORT criteria를 이미 정의해두었으므로 sample capture-day workflow는 ready. 이것이 Stage-2 schema re-flip의 단일 critical-path 항목.
2. **Vorländer 2020 §11 / Appx A verbatim 인용 종결** — MELAMINE_FOAM α₅₀₀ = 0.85의 page/row/panel-thickness column 정확 인용. ADR 0019 §References pending status 해소.
3. **OQ-14 FIBERGLASS_CEILING + TILE_FLOOR 추가** — 다른 SoundCam 방(또는 A10b in-situ 방)에서 paper-faithful material map을 위해 새 enum이 필요해질 때.
4. **Cross-repo PR re-submission** — `spatial_engine/proto/room_schema.json` proposal 재시작. Stage-2 re-flip 직후 (또는 spatial_engine 팀의 명시적 요청 시).

### §5.3 중장기 로드맵 (v0.13+)

- **라이브 메시 추출 (OQ-13e)** — SoundCam PLY mesh에서 직접 corner extraction. `floor_polygon_from_mesh`에 non-convex polygon 지원 추가 + alpha-shape / RANSAC / Hough. SoundCam mesh download access + 1개 방에서 ≤ 10 cm corner err 확보 시 ship.
- **ARKitScenes 통합 (OQ-12c)** — Apple 비상업 데이터셋 (수백 GB). license non-blocker 처리 + 50-room curated subset.
- **Mypy strict compliance (OQ-13i)** — downstream consumer가 type-strict roomestim에 의존하게 되는 시점.
- **Coupled-space predictor (Cremer/Müller)** — Building_Lobby처럼 per-sub-volume geometry가 있는 방을 위한 ADR 0014 §Alternatives considered (b). ACE adapter가 per-sub-volume geometry를 emit하도록 확장된 이후.

---

## §6 작업 방식 (메타)

### §6.1 OMC 파이프라인

v0.11.0은 **OMC orchestration**(planner → executor → code-reviewer → verifier) 4-단계 파이프라인을 가장 엄격하게 거친 첫 릴리스이다.

| 단계 | 산출물 | 결과 |
| --- | --- | --- |
| **Planner** | `.omc/plans/v0.11-design.md` (1123 lines; 2026-05-11 scope-locked) | hybrid scope 4-item 명시; §2.4 executor empirical decision-point procedure(한 번 측정 후 sub-branch 분기) lock |
| **Executor** | 16 file-ops (라이브러리 + 테스트 + ADR + 문서 + bookkeeping) | 단일 empirical decision point에서 lab PASS-gate 회복 분기 채택 |
| **Code-reviewer** | APPROVE 9.0/10 | 모든 BLOCKING 통과 |
| **Verifier** | 16/16 evidence-based gates PASS | default-lane 124 tests PASS; `ruff check` clean |

이전 릴리스들(v0.5-v0.10)은 planner + executor 위주였고, code-reviewer는 v0.7 critic verdict 사건 이후로 strict해졌으며, verifier는 v0.11이 첫 명시적 통과.

### §6.2 Honesty-first 원칙

v0.9 → v0.10 → v0.10.1 사이클에서 확립되어 v0.11에 carry-over된 핵심 원칙들이다.

1. **인용 불가능한 수치는 명시적 PENDING + envelope-flagged** — v0.11의 MELAMINE_FOAM α₅₀₀ = 0.85는 Vorländer 2020 §11 / Appx A envelope으로 planner-locked, 정확한 page/row 인용은 ADR 0019 §References에서 "verbatim citation pending follow-up Vorländer lookup"으로 honestly flagged.
2. **§Status-update / §Honesty-correction 블록은 audit-trail 보존용** — D22 hybrid pattern. v0.10이 v0.9 release notes body를 verbatim 유지하면서 prepend `§Honesty-correction-2026-05-10` 블록을 추가한 것이 first precedent. v0.10.1이 ADR 0018에서 in-line redaction + `§Status-update-2026-05-10b` append로 같은 패턴을 ADR에 적용.
3. **Critic이 발견한 honesty leak는 즉시 자기 비판 + redaction** — v0.10 critic 7.6/10이 ADR 0018 fabricated quote를 지적 → 같은 날(2026-05-10b) v0.10.1 ship으로 redaction. silent하게 leak를 둔 채 다음 릴리스로 미루는 path는 거부.
4. **PASS framing이 tautology이면 PASS라 부르지 않는다** — v0.9의 "corner err 0.00 cm by construction"이 GT corner + predicted corner를 같은 published dims에서 합성한 결과이므로 항상 0.00 cm — extraction algorithm validation이 없음. v0.10이 smoke-test로 reframe.
5. **Cross-agent verification (critic gate) 직후 ship** — main-actor 자기 평가만으로는 honesty leak가 누적된다는 사실이 v0.9 → v0.10 사이클에서 입증됨.

### §6.3 Tag policy (D11)

| 항목 | 정책 |
| --- | --- |
| Tag scope | `v0.1.1` ~ `v0.11.0` 모두 **local-only** |
| Push | commit만 `origin/main`으로 push; tag는 push 안 함 |
| Rationale | tag push는 별도 ratification 게이트 (현재 미정의). 외부 consumer가 tag로 pin하면 라이브러리 채택 시그널이 되므로, Stage-2 schema lock + cross-repo PR proposal 적용 시점까지는 release notes + commit만으로 운영. |
| Reverse | 외부 consumer 1+이 `pip install roomestim` 요청하거나, spatial_engine이 명시적 vendoring 요청 시 (D11 reverse-criterion) tag push 정책 재평가. |

### §6.4 Audit-trail discipline (D22)

v0.10.1에서 codified. same-week-old ADR correction을 마주칠 때 결정 트리:

| 오류 type | 대응 |
| --- | --- |
| **사실 오류** (fabricated quote, miscited number) | in-line redaction + 끝에 `§Status-update-YYYY-MM-DDb` 블록 추가 (WHY 기록) |
| **구조 오류** (wrong decision frame, wrong scope) | ADR supersedure — 새 ADR + 원본 ADR에 `§Status: superseded by ADR XXXX` |
| **순수 append-only** (`<del>`/`<ins>` HTML markup) | **거부됨** (unreadable; 다음 reviewer가 따라가지 못함) |

이 패턴은 v0.10.1의 ADR 0018 §Drivers item 2 line 46 redaction에서 첫 적용; v0.11에서는 ADR 0018 추가 편집 없이 ADR 0019 §References의 cross-link으로만 closure (구조 변경 없음 → status-update 불필요).

---

## §7 결론 + 한 줄 메시지

> 이번 주는 **ACE 코퍼스 적용**에서 시작해(v0.5-v0.6) **honesty correction 사이클**(v0.9 → v0.10 → v0.10.1)을 거쳐 **v0.11.0의 MELAMINE_FOAM 도입으로 lab A11 PASS-gate 회복** + **CI tense-lint policy 도입**으로 마감했다. 시스템 상태는 ratchet-safe — 모든 byte-equal invariant, MAE snapshot, Eyring monotonicity, disagreement-record signature가 정상 가드 중이고, OMC 4-단계 파이프라인이 v0.11에서 첫 strict 통과. 다음 사이클의 critical-path는 **A10b 실측 캡처** (OQ-12a; user-volunteer-only)이며, 캡처가 도착하면 Stage-2 schema re-flip + cross-repo PR re-submission이 동시에 가능해진다.

**핵심 메트릭 한 줄**: 8 releases / 19 ADRs / 25 D-decisions / 14 OQs / 124 default-lane tests / 10-entry MaterialLabel enum / `__schema_version__ = "0.1-draft"` (Stage-1 permissive).

**한 줄 메시지**: "공급자 honesty가 라이브러리 invariant를 만든다 — 이번 주 가장 큰 자산은 회복된 lab PASS-gate가 아니라, 회복 과정을 만든 ratchet-safe walk-back 사이클(v0.9 → v0.10 → v0.10.1)과 D22 audit-trail discipline이다."
