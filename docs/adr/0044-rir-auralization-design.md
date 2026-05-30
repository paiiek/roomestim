# ADR 0044 — Hybrid 물리-기반 RIR Auralization (Phase A: ISM early + filtered-noise late + BRIR) (draft)

- **Date**: 2026-05-30
- **Status**: Proposed (draft — 미구현; 본 문서는 설계 제안이며 코드/테스트는 아직 존재하지 않는다. 시제는 모두 제안/예정이다.) **REVISED 2026-05-30** — critic 리뷰(ACCEPT-WITH-RESERVATIONS; 0 CRITICAL + 0 MAJOR; citation 정확도 ~25 검증) 반영: (1) §A splice **per-band energy-continuity** 규약 명시 + late-tail 길이정책(max RT60_band 기반, 2 s 상수 미상속) + 밴드 recombination(power-complementary octave filterbank) + `t_mix` 정확 형식; (2) §A/§E **per-band vs broadband** 긴장 해소 — `compute_rir()` 는 broadband 단일 RIR 반환이므로 per-band 필요 시 image-source 직접 조립 경로, OQ-48 에 band-separability 추가; (3) §D diffuse-tail **IC target curve** 를 설계 파라미터로 명시; (4) citation 정정(`predictor.py:550`, `room_volume` 경로 `geom/polygon.py:66`) + blocking gate 에 splice-continuity 추가.
- **Deciders**: architect (설계 제안), critic (리뷰 예정), planner (확정 예정)
- **Refs**: ADR 0040 (pyroomacoustics polygon-ISM; `compute_rir`·`measure_rt60` 는 design-only), ADR 0041 (Ambisonics/HRTF 렌더 선례), ADR 0013 (equivalent-absorption-area 선례), ADR 0030/0031 (predictor default switch · per-band T60), ADR 0020 (tense-lint honesty scope), ADR 0038 (web 입력 자원 한계); D26 (forbidden-indefinite-deferral / YAGNI); 리서치 리포트 `.omc/research/rir-estimation-2026-05-30.md`; 로드맵 `.omc/plans/rir-estimation-roadmap.md` §스파이크 결과.

> **핵심요약 (권장안)**: room geometry + 재질 + ISM 만으로 **convolvable binaural RIR(BRIR)** 을 합성하는 RAZR 식 hybrid 경로를 web-tier 에서 **신규 패키지 0** 으로 제안한다. 소형 모듈 2개 — `roomestim_web/rir.py`(기존 pyroomacoustics ISM image-source 데이터로 early mono-RIR 조립 + analytic mixing-time + splice)와 `roomestim_web/late_reverb.py`(per-band T60 구동 late tail) — 를 추가한다. **v1 late 모델은 filtered-noise**(per-band 지수감쇠 shaped Gaussian)를 권장하고 FDN 은 follow-on 으로 deferred 한다. 6 octave 밴드를 **전부 유지**(현 데모의 500 Hz 스칼라 축소를 명시적으로 배제)하고, `predict_rt60_default_per_band` 를 T60 **단일 진실원천**으로 재사용하여 리포트 RT60 과 auralization tail 의 감쇠를 일치시킨다. 본 ADR 은 **Phase A**(학습데이터 0, 측정 0)만을 scope 로 하며, neural late-reverb 보정(Phase B)과 differentiable fitting(Phase C)은 out-of-scope 로 명시 deferred 한다.

---

## Context

### 현 상태 (코드 확인 사실 — 2026-05-30 스파이크)

음향 시뮬레이션·HRTF·pyroomacoustics 머신러리는 전부 `roomestim_web/` 아래 `[web]` extra 뒤에 있고(`pyproject.toml:28~43`), core `roomestim/` 는 audio 의존이 0 이다. 따라서 본 설계는 web-tier 한정이며 core 게이트를 오염시키지 않는다.

**(1) early reflections — 이미 live 로 존재한다.** `roomestim_web/binaural.py:292` 는 `room_pra.image_source_model()` 을 호출하고, 이어 `pra_source.images`(3×N image-source 위치, `binaural.py:308`)와 `pra_source.damping`(per-band × N 감쇠, `binaural.py:309`)를 순회한다. image 당 도달시간은 기하 거리(`binaural.py:334`)→delay sample(`binaural.py:347`), gain 은 `damping/distance`(`binaural.py:350`)로 산출된다. 이는 RAZR 의 "early ISM" 데이터(반사별 시간 + per-band 감쇠)와 정확히 동치이며, **재유도(re-derivation) 불필요**하다.

**(2) per-band T60 — 1급 반환값으로 존재한다.** `roomestim/reconstruct/predictor.py:525` 의 `predict_rt60_default_per_band` 는 `RT60Prediction.rt60_per_band_s`(`predictor.py:87`, `dict[int,float]` = `{band_hz: rt60_s}`)를 6 octave 밴드로 반환한다(밴드별 `image_source_rt60` 호출, `predictor.py:550`; 비-shoebox 는 Eyring fallback).

**(3) HRTF 렌더 — 방향 인덱스 룩업이다.** `roomestim_web/hrtf_io.py` 는 SOFA → `HrtfTable`(`hrtf_io.py:33~50`, `hrirs_left/right` M×N + `directions` M×2 az/el, 48 kHz 리샘플 `hrtf_io.py:58~73`)을 적재하고, `nearest_hrir()`(`hrtf_io.py:217`)이 great-circle 최근접 방향을 룩업한다.

**(4) 현존 "RIR-유사" 머신러리.** `binaural.py:353~363` 은 image source 별로 `fftconvolve(source_audio, hrir_l/r)` 한 뒤 gain·delay 를 적용해 stereo 버퍼에 합산한다. 즉 **mono RIR 배열을 만들지 않고** 방 응답과 dry source 를 한 패스로 융합한다. 2 s tail(`binaural.py:375`)은 유지되나 ISM late image(희소·specular)일 뿐이다.

**(5) 밴드 구조 — 균일 6-band octave.** `roomestim/model.py:75` `OCTAVE_BANDS_HZ = (125, 250, 500, 1000, 2000, 4000)`; `MaterialAbsorptionBands`(`model.py:86`)는 각 라벨을 6-tuple 로 매핑하고, `absorption_bands`(`model.py:154`)도 6-tuple 이다. pyroomacoustics 에는 이 6 밴드가 그대로 전달된다(`binaural.py:48`, `center_freqs=[125,250,500,1000,2000,4000]`). **정정**: 사전 가정이던 "10-band 재질 ↔ 6-band ISM mismatch" 는 **거짓**이다. 손실투영(10→6)은 없다. 코드 내 유일한 밴드 collapse 는 *반대 방향*으로, 데모 렌더가 `_resolve_damping_scalar`(`binaural.py:80~94`)에서 pra multi-band damping 을 500 Hz 스칼라로 축소하는 것이다 — Phase A 는 이 축소를 **중단**하고 6 밴드를 유지한다.

**(6) pyroomacoustics(설치 v0.10.1).** `pra.Room.compute_rir()` 와 `pra.measure_rt60` 은 존재하나 **코드에서 호출되지 않는다**(binaural.py 는 `image_source_model()` 만 사용). 두 심볼의 유일 참조는 design-only 이다(`docs/adr/0040-polygon-ism-design.md:65`). `compute_rir()` 는 동일 image source 로 진짜 mono RIR 을 합성하나, pra 자체 air-absorption·fractional-delay 모델을 적용한다.

**(7) 부재 확인.** repo·설치 pra 어디에도 FDN / feedback-delay / late-reverb / mixing-time / echo-density / mono-RIR 배열 생성 코드가 **없다**(grep 결과 로드맵 설계 텍스트만 매칭). pra 0.10.1 도 FDN 미제공(`fractional_delay_filter_bank` 만 존재).

### 문제

roomestim 은 hybrid RIR 파이프라인의 **physics 절반**(기하 + 6-band 재질 + ISM image source + HRTF)을 이미 보유한다. 그러나 현재 산출물은 RT60 스칼라/per-band dict(`image_source.py:432,541` 는 image list·RIR 을 내지 않음, 반환은 scalar/per-band only)와 데모용 stereo 융합 버퍼뿐이며, **재사용 가능한 convolvable RIR(임의 신호에 컨볼루션 가능한 임펄스 응답)은 어디에도 생성되지 않는다**. auralization(청취) 용도에는 (i) mono RIR 합성, (ii) diffuse late tail(ISM 의 specular-only 한계 보완), (iii) mono-RIR→BRIR 바이노럴화가 필요하다.

### 연구 근거 (요약; 전문 `.omc/research/rir-estimation-2026-05-30.md`)

- **RAZR**(Wendt et al., JAES 2014): geometry + octave 흡음(또는 T60) + HRIR 만으로, **측정 RIR 0** 으로 binaural RIR 합성. ISM early(저차) + FDN late, FDN 을 방 치수·per-band 흡음으로 파라미터화(Jot-Chaigne 흡음필터). = **pure-physics baseline**.
- **DAFx 2025**(York+Yamaha): 저차 RT early → Abel-Huang mixing time 에서 truncate → DecayFitNet 구동 VFM-FDN late append(crossfade 없음). VFM(K=4, δ=1)이 scattering-like echo density 주입 — ISM specular-only tail 의 핵심 sim-to-real gap 을 타겟. → **Phase B** 후보.
- **DiffRIR**("Hearing Anything Anywhere", CVPR 2024): physics 렌더러를 backprop 으로 **방당 ~12 측정 RIR** + planar 복원에 피팅. → **Phase C** 후보(측정 RIR 확보 전제).
- **honesty 경고**: EDC-neural 재구성 RIR 의 "reference 와 perceptual 등가" 주장은 적대적 검증에서 **반박**(MUSHRA 0-3 ×2; 2AFC 1-2). 따라서 어떤 방법에 대해서도 "perceptually faithful" 은 *방법 역량*으로만 기술하고 *검증된 지각 등가*로 단정하지 않는다.

---

## Decision

### §A — early/late 분해 아키텍처 + mixing-time splice

mono RIR 을 **early(physics ISM) + late(통계 tail)** 로 분해 합성할 것을 제안한다.

- **early**: `binaural.py:307~350` 의 image-source 순회(시간 + per-band 감쇠 `pra_source.damping[band,i]`)를 재사용해 **per-band early mono-RIR**(6 밴드 분리 유지)을 조립한다. `room_pra.compute_rir()`(§E)는 broadband 단일 RIR 을 반환하므로 §C 의 per-band handoff 를 깨끗이 적용하려면 image-source 직접 조립 경로가 1차이며, `compute_rir()` 채택은 §E spike(band-separability 포함)가 GREEN 일 때로 한정한다.
- **mixing time** `t_mix`: echo-density estimator 가 부재하므로 1차로 analytic Lindau 근사 `t_mix[ms] ≈ √(V[m³])` (Lindau 2012; 단일 형식으로 고정, 대체식 미사용)를 `roomestim/geom/polygon.py:66` `room_volume()`(기존 core geom helper; `report.py:141` 이 이미 소비 — 신규 core 의존 없음)에서 산출한다. 비-shoebox/coupled-space 적정성은 OQ-51.
- **splice**: early RIR 을 `t_mix` 에서 truncate 하고 late tail 을 paste 한다(DAFx 2025 no-crossfade 정책; crossfade 미도입). **energy-continuity 규약**: late 의 밴드별 noise envelope 초기값을 early RIR 의 `t_mix` 직전 윈도우 **per-band energy**(amplitude², `binaural.py:350` gain 은 amplitude-like 이므로 제곱 기준)와 연속이 되도록 정규화한다 — broadband 가 아니라 **per-band energy 연속**(§C 가 per-band envelope 를 commit 하므로 동일 기준). splice 지점 불연속(>3 dB)을 회귀 테스트로 금지 제안.

### §B — late 모델 선택 (핵심 결정): filtered-noise v1, FDN deferred

late tail 합성으로 **filtered-noise(per-band 지수감쇠 shaped Gaussian)** 를 v1 로 권장하고, **FDN 은 follow-on 으로 deferred** 한다. 근거:

- 의존성: 어떤 설치 dep 도 FDN 을 제공하지 않으므로(§Context (7)) FDN 은 신규 작성 + delay-line·feedback-matrix 튜닝이 필요한 **L** 규모이며 coloration 리스크가 있다. filtered-noise 는 scipy(이미 core dep)+numpy 로 충분한 **M** 규모이고, per-band T60→envelope slope 매핑이 직접적이다.
- 결정성(determinism): filtered-noise 는 seed 고정으로 byte-equal 재현이 자명하여 기존 테스트 규율(메모리: byte-equal RT60 회귀)과 정합한다. FDN 도 가능하나 부담이 크다.
- 충실도: filtered-noise 는 diffuse tail 의 지각적 1차 근사로 충분하다는 가설이며(RAZR 의 FDN 보다 단순), scattering-정밀 보정은 Phase B(VFM-FDN/neural)로 분리한다.

> FDN 채택 trigger: filtered-noise tail 이 §OQ 의 perceptual/JND 검증을 통과하지 못할 때.

### §C — per-band T60 → decay handoff (6 밴드)

late tail 의 per-band 감쇠는 `predict_rt60_default_per_band`(`predictor.py:525`)의 `rt60_per_band_s`(6 밴드)를 **단일 진실원천**으로 사용한다. filtered-noise 의 밴드별 지수 envelope slope 는 `decay(t) = 10^(−3·t / RT60_band)` 로 둔다(60 dB 정의). 6 밴드뿐이므로 projection 손실이 없고, 리포트가 표시하는 RT60 과 tail 의 실제 감쇠가 **정의상 일치**한다(일관성 invariant; 테스트로 고정 제안).

**밴드 recombination**: 6 octave 밴드 noise stream 은 **power-complementary octave 필터뱅크**로 분해/재합성하여 밴드 경계 energy 과대·과소를 방지한다(단순 합산 금지). **tail 길이정책**: convolvable RIR 총길이는 `max(RT60_band)` 의 −60 dB 도달시간에서 도출하며, 데모의 2 s 상수(`binaural.py:375`)를 **상속하지 않는다**(RT60 > ~0.66 s 룸에서 2 s 가 −60 dB 전 truncate → 위 invariant 가 명목상만 성립하는 것을 방지).

### §D — mono-RIR → BRIR 바이노럴화

- **early(pre-`t_mix`)**: 각 image 에 DOA 가 존재하므로(`binaural.py:339~342`) `nearest_hrir`(`hrtf_io.py:217`) per-DOA 컨볼루션을 그대로 재사용한다.
- **late(post-`t_mix`)**: FDN/filtered-noise tail 은 **방향이 없다**. 현 `nearest_hrir`(방향 인덱스)에 맞지 않으므로, diffuse-field 처리가 신규로 필요하다. v1 로 **interaural-coherence-shaped 2-HRIR decorrelation**(좌/우에 약간 다른 HRIR 또는 IC-shaped noise)를 제안한다. **IC target curve** 는 설계 파라미터로 명시한다 — diffuse-field 의 주파수별 interaural coherence `IC(f) = sinc(2πf·d/c)`(d=두 귀 간격, c=음속; Lindemann 형식)를 목표로 둔다(현재 시점에 지정 가능한 결정변수). 이 *목표곡선*과 별개로 그 결과의 *지각충실*은 **검증 대상**(OQ-47)이며 단정하지 않는다.

### §E — `compute_rir()` vs `image_source_model()` (선결 spike)

mono early-RIR 조립에서 `room_pra.compute_rir()` 는 fractional-delay splatting 재구현을 피하는 편의가 있으나, pra 0.10.1 의 `compute_rir()` 는 **per source-mic pair 당 broadband 단일 RIR** 을 반환하여 air-absorption·재질필터를 한 임펄스에 baking 한다 — 6 밴드를 분리 형태로 돌려주지 않는다. §A 가 요구하는 per-band early RIR 과 충돌하므로, **per-band 보존이 필요한 한 image-source 직접 조립(`pra_source.damping` per-band, `binaural.py:309`)이 1차 경로**다. `compute_rir()` 채택은 **착수 전 spike** 가 (i) RT60 일관성(T20/T30 ±5% 내, vs `predict_rt60_default_per_band`)과 (ii) **band-separability**(per-band RIR 추출 가능 여부)를 둘 다 GREEN 으로 확인할 때로 한정한다(OQ-48). ADR 0040(`docs/adr/0040-polygon-ism-design.md:67`)이 sparse-ISM-RIR 의 `measure_rt60` 신뢰성을 **미검증**으로 플래그했으므로, 불일치 시 image-source 직접 조립으로 폴백한다.

---

## Consequences

**Positive**
- web-tier 격리: core `roomestim/` 무변경 → core 게이트 회귀 0 (`pyproject.toml:28~43` 경계).
- 신규 패키지 0: scipy+numpy 로 충분.
- early 반은 사실상 재사용(`binaural.py` image-source 데이터, `predictor.py` per-band T60), 신규는 소형 2 모듈.
- RT60 단일 진실원천(§C)으로 리포트-auralization 일관성 invariant 확보.
- 측정 RIR·학습데이터 0 → 즉시 가용(blind geometry+material 합성).

**Negative / risk**
- diffuse late-tail 바이노럴화(§D)가 기존 HRTF 추상화(방향 인덱스)에 맞지 않아 신규 코드 필요 — Phase A 최대 불확실성.
- mixing-time analytic 근사(√V)는 1차 — 비-shoebox/coupled-space 에서 부정확 가능(OQ).
- filtered-noise tail 의 지각충실 미검증 — perceptual/JND 검증 전까지 "plausible" 로만 기술.
- `compute_rir()` RT60 일관성 미확인 시 폴백 경로 필요(§E).

**Neutral**
- demo 렌더의 `_resolve_damping_scalar`(`binaural.py:80~94`) 500 Hz 축소는 Phase A 신규 경로에서 미사용 — 기존 데모 경로는 불변 유지(별도 함수 추가, 기존 경로 무수정).

---

## Reverse-criterion (neural 절반을 하지 말 것)

다음 증거 중 하나라도 성립하면 Phase B/C(neural late / differentiable fitting)를 **하지 않고** pure-physics Phase A 에 머문다:

1. 대상 방의 캘리브레이션용 실측 RIR(DiffRIR 기준 방당 ~12)을 현실적으로 확보할 수 없다 → Phase C 불가, blind Phase A 만 의미.
2. 용도가 청취(auralization)가 아니라 음향 파라미터 추정으로 좁혀진다 → RIR 합성 자체가 RT60 예측 위 잉여, neural 불요.
3. filtered-noise(또는 RAZR-FDN) physics tail 이 §OQ 의 perceptual/JND 검증을 이미 통과한다 → neural 보정의 한계효용이 의존성·데이터 비용을 정당화하지 못함.
4. neural late 의 perceptual 등가가 입증되지 않는다(현 문헌 상태: EDC-neural 등가 주장 반박됨, §연구 근거) → 성급한 도입 금지.

> 근거: RAZR 가 학습데이터 0 으로 binaural RIR 합성을 입증했고, neural late 의 지각 우위는 현재 검증된 바 없다.

## Blocking gate (Phase A 구현 착수 전 충족)

1. §D diffuse-tail 바이노럴화 전략 합의(2-HRIR decorrelation + IC target curve 수용 여부 — planner/critic).
2. §E spike GREEN — RT60 일관성 **및** band-separability 둘 다(또는 image-source 직접 조립 폴백 확정).
3. §A splice **per-band energy-continuity** 검증 — `t_mix` 지점 밴드별 불연속 >3 dB 금지(회귀 테스트).
4. 기존 default + web 게이트 회귀 0 재확인(canonical `/home/seung/miniforge3/bin/python -m pytest`), tense-lint EXIT=0.

## Alternatives considered

- **FDN-first late**: 물리적으로 RAZR 정통이나 신규 L + 튜닝/coloration 리스크 + byte-equal 부담 → v1 기각, follow-on(§B).
- **`compute_rir()` 단독(early+late 통째 pra)**: pra RIR 의 late 도 specular-image 기반이라 diffuse tail 빈약(sim-to-real gap 미해결) → late 보강 필요, 단독 기각.
- **pure-neural(NAF/INRAS/DANF)**: data-hungry, 측정/학습 필요, roomestim 의 기하 자산 미활용 → Phase A 부적합(DANF 는 B5 Ambisonics directional-output 참고로만).
- **blind(FiNS)**: 기하 불요(roomestim 이 이미 보유하는 것을 버림) → leverage 경로 아님, 기각.

## Open Questions (신규)

- **OQ-47**: diffuse late-tail 바이노럴화(§D, 2-HRIR decorrelation / IC-shaped)의 지각충실 — perceptual 검증 필요. (Phase A 최대 불확실성)
- **OQ-48**: `compute_rir()` 선결 spike — (i) sparse-ISM-RIR 의 `measure_rt60` 가 `predict_rt60_default_per_band` 와 RT60 일관한가(ADR 0040:67 연계), (ii) broadband 반환에서 per-band RIR 추출(band-separability)이 가능한가. 둘 다 GREEN 아니면 image-source 직접 조립 경로.
- **OQ-49**: Phase A auralization 평가 metric 선정 — 어느 objective(EDT/C50/C80/DRR/EDC fit/log-spectral)가 지각품질과 best 상관 + 잔향 JND 임계. (리서치 Q2 미해결; 추가 문헌조사 필요)
- **OQ-50**: 대상 방당 ~12 측정 RIR 확보 현실성 — Phase C(DiffRIR) gate. (불가 시 Reverse-criterion #1)
- **OQ-51**: mixing-time analytic √V 근사가 비-shoebox/coupled-space(예: Building_Lobby)에서 충분한가, echo-density profile 필요한가.

---

*본 ADR 은 설계 제안이며 코드/테스트는 존재하지 않는다. 확정·구현은 critic 리뷰 및 planner 승인, blocking gate 충족 후 별도 진행한다.*
