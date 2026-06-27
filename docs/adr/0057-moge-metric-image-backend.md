# ADR 0057 — MoGe metric 단일-이미지 백엔드: `[moge]` extra (실험적, SHIP-EXPERIMENTAL)

- **Date**: 2026-06-27
- **Status**: Accepted (v0.52.0 — MINOR additive: 신규 `[moge]` extra + 신규 `adapters/moge.py` + `--backend moge` CLI(--experimental 게이트). 기존 백엔드·default import 경계·골든 무변경.)
- **Deciders**: main(설계+구현, plan `.omc/plans/moge-image-backend.md`), code-reviewer(예정). Eval 근거: `.omc/research/_data/moge_image_benchmark_results.md`.
- **Refs**: 코드 `roomestim/adapters/moge.py` + 단일진실원천 `roomestim/reconstruct/_disclosure.py::MOGE_METRIC_NOTE`. 의존: `MoGe`(MIT 코드; **Microsoft Research, Apache-2.0 가중치** — 1차출처 검증; metric point-map + FoV 추정). 재사용: `MeshAdapter._extract_room_model`(ADR 0027/0051 footprint+robust planes) — `MultiviewAdapter`(ADR 0056) 선례 동일 패턴.

> **핵심요약**: `ImageAdapter`(HorizonNet)의 cam_h 스케일-앰비규이티를 우회하기 위해 MoGe metric depth 모델을 **additive opt-in 실험 백엔드**로 추가한다(`--backend moge --experimental`). 파노라마를 다중 퍼스펙티브 crop 으로 분할 → 각 crop MoGe 추론 → known-rotation 융합 → 점군 → `MeshAdapter` 추출 재사용. **cam_h 입력 없음**이 핵심 차별점. 단, cuboid-전용 벤치(n=100)에서 **HorizonNet 미달**(per-DIM median 151.7 cm vs 58.0 cm)이므로 **정직 NEGATIVE** 결과로 출하되며 `MOGE_METRIC_NOTE` 단일진실원천에 수치·한계 모두 명시. HorizonNet `image` 백엔드가 계속 documented rough-tier 이다.

---

## Context

`ImageAdapter`(HorizonNet, ADR 0045)의 지배 오차 레버는 cam_h 입력이다 — ±10 cm cam_h 오차가 median ~32 cm 벽 오차를 유발하며, 사용자가 정확한 cam_h 를 모를 경우 스케일이 불확정 상태로 남는다(ADR 0045 `IMAGE_CAM_H_SCALE_NOTE`). MoGe(Microsoft Research, 2024)는 **단일 이미지에서 metric point-map 을 직접 추정**하며 cam_h 를 일절 요구하지 않는다. 라이선스는 코드 MIT + 가중치 Apache-2.0 — HorizonNet 기본 가중치(`st3d`, 상용 적합성 미확인) 대비 **상업적으로 보다 명확**하다.

그러나 MoGe 는 **equirectangular 파노라마가 아닌 perspective 이미지**를 입력으로 받는다. 이를 파노라마 워크플로에 적용하려면 파노라마를 known-rotation crop 으로 분할한 뒤 추론 결과를 3D 융합해야 한다(다중-crop 접근). 그리고 이 설계는 per-crop metric-scale 드리프트(crop 간 일관된 스케일 보장 없음)라는 새로운 리스크를 낳는다.

## Decision

### 1. 다중-crop 파노라마 분할 + 융합 (`adapters/moge.py`)
equirectangular 파노라마를 **known-rotation** 퍼스펙티브 crop 으로 분할(FoV·stride 설정 가능) → 각 crop 에 MoGe 추론 → 3D 역투영 → known rotation 적용 → 하나의 점군으로 융합. 융합 후 `MeshAdapter._extract_room_model(points, ...)` 재사용(ADR 0056 `MultiviewAdapter` 패턴 동일) → footprint/ceiling/wall/listener 추출.

### 2. `[moge]` extra (pyproject)
MoGe 는 git-only 의존성(PyPI 미등록) — `pip install 'roomestim[moge]'` 는 `git+https://...` direct ref 를 요구하며, 이는 PyPI wheel 로 `[moge]` extra 를 publish 하는 것을 차단한다. core 는 publishable 그대로 유지. lazy import 로 `import roomestim` 는 MoGe/torch 를 끌지 않는다(subprocess 테스트 lock).

### 3. `--backend moge` + `--experimental` 게이트
`ingest`/`run` 의 `_get_adapter` 에 `moge` 분기. `--experimental` 없이 호출하면 `_ExperimentalGate` 가 차단. cam-height 인자를 무시하고 `MOGE_METRIC_NOTE` 를 NOTE 로 출력. `provenance="reconstructed"`, 재질 `UNKNOWN`, 객체 없음.

### 4. 단일진실원천 `MOGE_METRIC_NOTE` (`reconstruct/_disclosure.py`)
수치·caveat 의 단일 출처. "per-DIM median 151.7 cm(convex)/176.3 cm(robust) vs HorizonNet 58.0 cm; scale-invariant shape-only 52.9 cm 도 HorizonNet 미달; cuboid-only GT + cam_h-derived GT 스케일 한계; 공정 비교를 위해 non-cuboid measured-metric GT 필요" 를 명시. 모든 CLI/adapter 출력이 이 NOTE 를 참조.

## Consequences

- **(+) cam_h 불필요**: 사용자가 카메라 높이를 모르는 시나리오에 옵션 제공.
- **(+) 상업적으로 더 명확한 가중치**: Apache-2.0(MoGe) vs HorizonNet st3d(상용 적합성 미확인) / zind(NC ToU). B2B 워크플로에서 라이선스 부담 경감.
- **(+) core 무변경 byte-equal**: lazy import, `--experimental` 게이트, default 게이트 770p/7s 불변.
- **(−) cuboid 벤치에서 HorizonNet 미달**: per-DIM median 151.7 cm(MoGe convex) vs 58.0 cm(HorizonNet), 천장 median 오차 71.7 cm vs 13.1 cm. **정직 NEGATIVE 결과**.
- **(−) scale-invariant shape-only 에서도 미달**: GT metric scale 편향 제거 후에도 MoGe convex 52.9 cm vs(HorizonNet 기준 58.0 cm과 직접 비교 불가이나) 방 단위 ≤15 cm 0~1% vs HorizonNet 3.1%.
- **(−) per-crop metric-scale 드리프트**: 실측 CV median 14.7%, p90 25.8%, max 34.8% — crop 간 스케일 일관성 부재가 융합 점군에 노이즈를 더한다.
- **(−) GPU / 환경 의존**: MoGe 는 torch(GPU) 필요. 기본 게이트는 moge 마커 skip-guard 로 무영향.
- **(−) cuboid-only GT 한계**: 현재 벤치(n=100, 100% cuboid, cam_h-derived 스케일)는 MoGe 의 개구부/창문 투과 depth 를 GT 가 닫힌 벽으로 잘라 과대 오차를 만든다(modality bias). 그러나 이 편향이 있더라도 scale-invariant 비교에서도 MoGe 가 우세하지 않아 결론은 동일하다.
- **(−) `[moge]` extra PyPI 미배포 가능**: git-only direct ref → PyPI wheel install 시 `[moge]` 설치 불가. core publishability 무영향.

## Alternatives considered

### (a) HorizonNet 단독 유지
MoGe 미추가 — **REJECTED**: cam_h 스케일-앰비규이티 레버를 전혀 건드리지 못하며, 상업 가중치 옵션도 없다. 실험적이더라도 추가 가치가 있다고 판단해 채택.

### (b) MoGe 가중치를 저장소에 vendor
~1–2 GB 모델을 repo 에 포함 — **REJECTED**: 저장소 팽창, 라이선스 복잡화. 첫 사용 시 다운로드 패턴(HorizonNet 선례) 유지.

### (c) 다른 metric depth 모델 (Depth Anything / Metric3D / UniDepth)
- **Depth Anything v2**: Apache-2.0 가중치이나 monocular metric 정확도가 MoGe 대비 room-scale 에서 낮고 FoV 추정이 미약.
- **Metric3D v2**: 가중치 라이선스 조건 불명확(비상업 제한 가능성), API 안정성 낮음.
- **UniDepth**: Apache-2.0 이나 point-map 직접 출력 API 가 MoGe 보다 추가 작업 필요.

→ MoGe 가 single-image metric point-map + FoV 직접 출력 + Apache-2.0 가중치 조합에서 가장 clean 하다고 판단. **채택**.

### (d) 단일 퍼스펙티브 이미지만 (crop 융합 없음)
방 전체를 하나의 crop 으로 커버 불가 — **REJECTED**: 파노라마로 닫힌 방 geometry 를 얻으려면 다중-crop 융합이 필요.

## Follow-ups

1. **Non-cuboid measured-metric GT 검증**: 현재 유일한 공정 비교 경로. 3DSES(CAD GT, CCv-BY-SA, §ADR 0051) 같은 metric 치수가 있는 데이터셋으로 non-cuboid 시나리오를 포함한 재벤치가 선결 과제.
2. **VGGT+GTSAM global BA**: 고정밀 multi-view 경로로 연구 합성에서 더 높은 ROI 가 예상되나(`.omc/research/usable-tech-SYNTHESIS-2026-06-23.md`), user-gated(GPU 환경·대규모 작업).
3. **`[moge]` extra PyPI 배포 가능성**: MoGe 가 PyPI 에 게시되거나 hf_hub 단일 파일 로드로 전환되면 direct ref 제거 → `[moge]` extra publish-grade 달성 가능.
4. **per-crop scale 정규화**: 융합 전 crop 간 스케일 alignment(예: overlapping 영역 median) → CV 드리프트 완화. 현재 미구현.

## Eval 수치 요약 (load-bearing, `.omc/research/_data/moge_image_benchmark_results.md`)

n=100 파노(50 사무 `camera_*` Stanford2D3D + 50 주거 `pano_*` PanoContext). GT = LayoutNet `label_cor` cuboid 코너 + nominal cam_h(1.6 m/1.4 m) metric 투영.

| 방법 | per-DIM median (cm) | per-room ≤15 cm (%) |
|---|---|---|
| HorizonNet (baseline) | **58.0** | **3.1** |
| MoGe convex | 151.7 | 1.0 |
| MoGe robust | 176.3 | 0.0 |

Scale-invariant shape-only(MoGe convex): **52.9 cm** — GT metric scale 편향 제거 후에도 방 단위 ≤15 cm 에서 HorizonNet 미달.

천장 median 오차: HorizonNet **13.1 cm** vs MoGe **71.7 cm**.

Per-crop metric-scale 분산(CV): median **14.7%**, p90 **25.8%**, max **34.8%**.

**Verdict: SHIP-EXPERIMENTAL** — MoGe 는 cuboid-pano 벤치에서 HorizonNet 을 넘지 못한다. HorizonNet `image` 백엔드가 계속 documented rough-tier 이며, `--backend moge` 는 cam_h 없이 쓸 수 있는 실험적 대안으로만 제공된다.

## Reverse-criterion

현재 cuboid-only GT 편향이 있는 상태에서 verdict 는 SHIP-EXPERIMENTAL 이다. non-cuboid measured-metric GT(예: 3DSES + RIR 방 메트릭, 또는 직접 laser 치수)로 재벤치했을 때 MoGe 가 HorizonNet 을 통계적으로 유의하게 넘으면 `--experimental` 해제 + `MOGE_METRIC_NOTE` 갱신을 검토.
