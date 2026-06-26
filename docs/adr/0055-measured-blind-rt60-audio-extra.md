# ADR 0055 — Measured (blind) RT60 from a recording: `[audio]` extra (A3, increment 1)

- **Date**: 2026-06-24
- **Status**: Accepted (v0.49.0 — MINOR additive / opt-in: new `[audio]` extra + new lazily-imported module; core / `import roomestim` boundary unchanged. LIBRARY-ONLY increment — no CLI wiring this pass.)
- **Deciders**: main(설계+구현, plan Track A3), code-reviewer(예정). user: 성능평가 후 "B4→A3 순차".
- **Refs**: 코드 `roomestim/reconstruct/measured_rt60.py` + 단일진실원천 `roomestim/reconstruct/_disclosure.py::MEASURED_RT60_NOTE`. 의존: `blind-rt60` (PyPI v0.1.1, **License MIT** — 1차출처 검증; Ratnam et al. ML decay model) + `soundfile`. A1(ADR 0028) = geometric RT60 엔진은 NO-GO 절대정확도 → 측정 경로가 보완.

> **핵심요약**: 기하 RT60 MODEL(Sabine/Eyring/ISM, 가정된 재질 의존)과 달리, 녹음 신호에서 RT60 을 **측정**하는 경로를 옵셔널 `[audio]` extra 로 추가한다(`blind-rt60` MIT 래핑). 단일 BROADBAND 값, blind 추정기 자체 오차는 in-repo 미검증(ACE 벤치 defer). lazy import 로 core dep-free 유지. 단일진실원천 `MEASURED_RT60_NOTE`.

---

## Context

A1(ADR 0028 §Status-update)에서 기하 RT60 엔진은 측정 GT 대비 **절대정확도 NO-GO**(alpha-input gap)로 확인됐다. 측정 기반 RT60 은 가정된 재질이 아닌 실제 방을 반영하므로 보완 가치가 크고, off-the-shelf blind-RT60 라이브러리 부재는 차별화 여지였다(plan Track A3). `blind-rt60`(MIT) 가 Ratnam et al. ML decay 모델을 제공한다(1차출처 PyPI 검증).

## Decision

### 1. `[audio]` extra (pyproject)
`blind-rt60>=0.1.1` + `soundfile>=0.12`. blind-rt60 deps=scipy/numpy/matplotlib(전부 기존 보유). mypy override(`blind_rt60.*`/`soundfile.*` ignore_missing_imports — 스텁 없음, pxr 선례).

### 2. 신규 모듈 `roomestim/reconstruct/measured_rt60.py` (lazy import)
- `measure_rt60_from_signal(signal, fs, ...) -> MeasuredRT60`: 멀티채널→mono 평균, 빈/비유한/비양수 fs 검증, `BlindRT60(fs).estimate(x, fs)` 호출.
- `measure_rt60_from_audio(path, ...) -> MeasuredRT60`: soundfile 로 파일 읽고 위 함수 위임; 파일부재 `FileNotFoundError`.
- `MeasuredRT60`(rt60_s/sample_rate_hz/n_samples/source/method/note).
- **lazy import**: `blind_rt60`/`soundfile` 를 함수 내부에서만 import → `import roomestim` 가 extra 를 끌지 않음(테스트로 subprocess 검증). extra 부재 시 친절한 `ImportError`(`pip install 'roomestim[audio]'`).

### 3. 정직성 (`MEASURED_RT60_NOTE`)
측정이나 (a) blind 추정기 **자체 오차 in-repo 미검증**(ACE 벤치 defer; 공개 blind-RT60 오차 ~수백 ms), (b) 단일 BROADBAND(per-band 아님), (c) 녹음 품질 의존(clean impulsive excitation 최적). geometric MODEL 과 명확히 구분.

## Consequences

- **(+) 측정 RT60 경로 확보**: 가정된 재질 대신 실제 방. A1 의 기하 절대정확도 한계 보완.
- **(+) core 무변경 byte-equal**: lazy import → `import roomestim` dep-light 유지(subprocess 테스트 lock). default 게이트 byte-equal(764p/7s, +9 `tests/test_measured_rt60.py` skip-guard via importorskip).
- **(−) 정확도 in-repo 미검증**: blind 추정 오차 미정량 → indicative 측정으로만 표기(증분 2 = ACE 벤치).
- **(−) CLI 미배선(의도)**: ★`cli.py` 가 다른 동시 세션과 경합 중이라 이 증분은 LIBRARY-only — CLI `measure-rt60` 서브커맨드는 경합 해소 후 후속.
- 게이트: my 모듈 ruff·mypy(--strict, 패키지 63 files) clean.

## Alternatives considered

- **(a) 직접 Schroeder 적분 RT60 자작** — REJECTED: blind-rt60(MIT) 이 검증된 ML 모델 제공, 바퀴 재발명 불필요.
- **(b) per-octave-band 측정** — DEFER: blind-rt60 은 broadband 단일값. 대역분해는 사전 필터뱅크 필요(증분 2+).
- **(c) CLI 우선 배선** — DEFER: cli.py 동시-세션 경합(다른 autopilot 의 A-consumer multiview 미커밋 변경) → 충돌 위험. 라이브러리 먼저.

## Reverse-criterion

- ~~**증분 2**: ACE corpus(CC-BY-ND, Zenodo 6257551)로 blind-RT60 정확도 벤치(out-of-gate) → `MEASURED_RT60_NOTE` 에 측정 오차밴드 기입(A1 패턴). + Acta Acustica 2025 closed-form 보정(geo prior→측정 RT60 제약 투영). + CLI `measure-rt60` 배선(cli.py 경합 해소 후).~~
- **증분 2a (DONE, v0.51.0 — 아래 §Status-update)**: 컨트롤드-SIM 벤치(외부 다운로드 없음) + CLI `measure-rt60` 배선.
- **증분 2b (남은 일, DEFER)**: ACE 측정 코퍼스(CC-BY-ND, Zenodo 6257551)로 blind-RT60 **end-to-end** 정확도 벤치(out-of-gate, 외부 다운로드) → `MEASURED_RT60_NOTE` 에 **측정-방** 오차밴드 기입. + Acta Acustica 2025 closed-form 보정(geo prior→측정 RT60 제약 투영).

## Status-update (2026-06-26, v0.51.0 — 증분 2a + CLI 배선)

- **컨트롤드-SIM 벤치 (out-of-gate)**: `tests/eval/blind_rt60_benchmark.py` 추가 — pyroomacoustics shoebox RIR 의 Schroeder RT60 을 GT 로, **impulsive-clap** 여기 하 blind-rt60 decay-fit 정확도를 측정. 결과(n=5): **MAPE 8.7%, bias -8.5%, MAE 135 ms, max \|err\| 17.8%**. 음성 대조군(steady noise, decay tail 없음)은 **39.5 s 로 발산** → 사용 caveat(impulsive 여기 필수) 실증. `test_` 함수 없음·`__main__` 전용 → default 게이트 미수집(out-of-gate). 결과는 `.omc/research/_data/`(gitignored)에 기록.
  - ★**SIM 바운드의 한계(정직)**: GT 가 idealised specular shoebox RIR 이므로 이 수치는 **추정기 decay-fit 정확도의 바운드이지 측정-방 end-to-end 오차가 아님**. ACE 측정 코퍼스 + Acta 폐형 보정은 **증분 2b 로 여전히 DEFER**.
- **`MEASURED_RT60_NOTE` 갱신**: "in-repo 미검증" 절을 → 컨트롤드-SIM 벤치가 decay-fit 정확도를 **바운드**(~9% MAPE / max ~18%)하되 **end-to-end 측정-코퍼스(ACE)는 deferred** 로 명시. equality 테스트(`res.note == MEASURED_RT60_NOTE`) + honesty-invariant substring 테스트 GREEN 유지.
- **CLI 배선 (경합 해소)**: v0.49.0 §Consequences 의 "CLI 미배선(의도)" 사유(cli.py 동시-세션 경합)가 v0.50.x multiview 커밋으로 해소됨. 신규 `roomestim measure-rt60 --audio PATH [--json]`:
  - parser `_add_measure_rt60_parser` + handler `_cmd_measure_rt60` + main() dispatch (`structure` 패턴 미러).
  - 성공: 사람 모드 = RT60/method/source/sample_rate_hz/n_samples → stdout, 고지 NOTE → stderr; `--json` = 데이터클래스 필드 JSON → stdout.
  - `[audio]` extra 부재 = **in-handler `ImportError`**(친절 install hint, exit 1) → main 의 공유 except 튜플 무확장. 누락파일(`FileNotFoundError`)/빈·비유한 신호(`ValueError`)는 main 의 기존 except → exit 1.
  - 신규 `tests/test_measure_rt60_cli.py`(importorskip skip-guard): 사람/JSON/누락파일 plumbing 만 lock, **정확도 단언 없음**(honesty). default 767→+3.
- **게이트**: default 767p→+3 / 7s, web GREEN, ruff(roomestim/ + 신규 테스트)·mypy(--strict, roomestim) clean.
