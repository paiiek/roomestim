# DiffRIR non-shoebox 측정 GT — polygon-ISM 검증 사이클

**Created**: 2026-06-19
**Status truth source**: 이 파일 (RESUME POINTER 최신 유지)
**Cross-ref**: ADR 0040 (polygon-ISM design + RT60 cascade DEFER), [[project_polygon_ism_gt_hunt]], [[project_data_unblock_cycle_complete]] (C2 material-confound 교훈)

## ★ 정체/라이선스 정정 (2026-06-19, PRIMARY-SOURCE CONFIRMED) — DiffRIR 아니라 MP-RIR (CC-BY 4.0)
`data/rir_dataset/` = **MP-RIR** ("Multi-Purpose Room Impulse Response Dataset Measured on a 3D Spatial
Grid", Fraunhofer IIS — Friede·Tuna·Knauff·Prinn·Ersinadim·Walther; **Zenodo 11148712, license cc-by-4.0
= 상업 OK**, pub 2024-06-12). **Zenodo API 로 직접 확인** + 파일 byte-match(md5 identical, S*_Mrir
3,440,099,456 B). coord_polygon 도 CC-BY 4.0 동반 공개 → "geometry license 미해결" 블로커 **해소**,
라이선스 이메일(P5) **불필요(MOOT)**.
**★agent 충돌 해소**: `diffrir-specs` 가 "Zhao UTS / CC-BY-NC-4.0(비상업)" 으로 오식별(환각) → 1차
Zenodo 레코드로 **반박**. `backup-gt-precheck` 의 MP-RIR/CC-BY 가 정확. (세션 초기 "DiffRIR Complex"
프레이밍도 오류.) 교훈: agent 식별 주장은 1차 출처로 검증해야 — 특히 commercial-OK 게이트 좌우 라이선스.
durable note = `.omc/research/mp-rir-nonshoebox-toa-validation.md`.

## 무엇이 바뀌었나 (the unblock)
`data/rir_dataset/` 에 **비-shoebox 측정 RIR 코퍼스**가 처음으로 손에 들어옴 (MP-RIR):
- footprint = 사다리꼴 4정점, 내각 [90.0, 89.8, 102.2, 77.9]° → **진짜 non-rect** (area 41.75 m²)
- 8 source × 8592 mic (1074 xy × 8 height 0.70–1.75m), fs=48kHz, 100096-sample RIR (~2.085s)
- 측정 broadband RT60 (Schroeder T30) ≈ 0.80–0.89 s
ADR 0040 RT60 cascade DEFER 의 단일 게이트 criterion(iv) = "non-shoebox measured RT60 GT 부재" 가 깨짐.

## 정직성 경계 (CRITICAL — NO FAKE NUMBERS)
- **천장고·재질 GT 가 Setup.npz 에 없음.** → RT60 magnitude 직접 예측은 06-12 status-update 의 U-Rochester **material-confound** 위험을 그대로 가짐.
- 따라서 검증을 두 층위로 분리:
  - **T1 (geometry/TOA)**: 벽 반사 path-length 는 재질·천장고 불필요(벽 mirror=xz only, y 보존). 측정 early-echo TOA vs `first_order_path_lengths`. dEchorate **cuboid** 검증을 **진짜 non-rect 방**으로 확장 — fake-number-free, 즉시 가능.
  - **T2 (RT60 magnitude)**: 천장고(DiffRIR 논문) + 재질 필요. 독립 재질 GT 없으면 "cross-method 체크(재질=DiffRIR 추정)" 로만 정직하게 라벨. 절대정확도 주장 금지.

## Phases / RESUME POINTER
- [x] P0 데이터 inspect + footprint non-rect 확정 + 측정 RT60 샘플 (DONE)
- [x] P0.1 data/ gitignore 차단 (27GB) (DONE)
- [x] P1 (DONE, critic-REVISED) **T1 geometry/TOA 검증**: note `.omc/research/mp-rir-nonshoebox-toa-validation.md` + 재현 스크립트 `mp_rir_toa_validate.py`. **honesty-critic가 초기 과대주장 적발→하향**. 검증된 것: ①geometric SCALE/path-length(aggregate c=344–345, anchor-c robust) ②visibility-pruning(edge2 좌소스 prune/우소스 valid) ③axis-aligned wall3 1개(c=341.7·7cm·bias~0). **미검증(정직)**: 경사 edge2(유일 12° 경사) 직접테스트=INCONCLUSIVE(per-source c 308–368 산포·26cm) → 경사선 mirror 산술 미확증; wall0/1/floor 12–26cm은 method가 attribute 못하는 upper-bound. 코드/버전 무변경.
- [x] P2 (DONE, `diffrir-specs` 자기수정·1차출처) 천장고=**NOT FOUND**(무료출처 부재; 방 "complex-shaped, diversified wall structures" → 단일 평평천장 아닐 수도), 재질=**NONE published**(zero material GT), 음속=NOT FOUND(내 fit 340–346 만 존재), 라이선스=**CC-BY-4.0 전체(audio+geo), commercial OK**, T_system/T_guard=Zenodo README verbatim 확인(내 offset=6247 1차출처 corroborate). 인용: Friede·Tuna·Knauff·Prinn·Ersinadim·Walther, AES 156th Madrid 2024 paper#10702, DOI 10.5281/zenodo.11148712. 연락(천장고/재질 문의시): lukas.friede@iis.fraunhofer.de(INFERRED). → **T2(RT60 magnitude)는 재질·천장고 GT 부재로 확정 DEFER** (material-confound, [[project_data_unblock_cycle_complete]] C2 교훈).
- [x] P3 (DONE, `backup-gt-precheck`) MP-RIR=우리데이터 확정(CC-BY) + FLAIR=2차 non-rect GT(CC-BY, laser geo, H=3.35m, c=344.74) `data/backup_gt_probe/`
- [ ] P4 (조건부, P2 결과 의존) T2 RT60: 천장고 확보 시 polygon-ISM RT60 vs Eyring vs 측정 — material-confound 정직 라벨. cascade 구현은 executor+code-reviewer 경유 (코드 변경)
- [~] P5 라이선스 이메일 — **MP-RIR CC-BY 4.0 (geometry 포함) → 사실상 MOOT**. P2 가 별도 derivative 제약 발견 시에만 재고.
- [x] P6 (DONE) ADR 0040 §Status-update (2026-06-19) append — honesty-critic 2R(REVISE→APPROVE, 독립 스크립트 재실행 검증) 반영: non-rect scale/TOA+visibility+axis-aligned wall3 검증 / 경사 mirror UNCONFIRMED / RT60 DEFERRED. + memory 갱신. 코드 무변경(686p/7s 불변).

## 결과 누적 (채워가며)
- P0: footprint area 41.75 m², 내각 [90.0,89.8,102.2,77.9]°, RT60 T30 0.80–0.89s (S1, 5 mic)
- P1: (진행중)

## Gate baseline
v0.43.0 = default 686p/7s ([[reference_canonical_test_env]]). 이 사이클 P1~P3 는 doc-only/research → 회귀 0 기대. P4 코드 변경 시 full gate 재실행 필수.
