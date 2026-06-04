# OQ-59 — focused floor-extraction front-end spike (resume truth source)

## VERDICT (2026-06-04) — CYCLE COMPLETE
- **VERDICT = FALLBACK (hardened).** front-end 레버 질문 NO — 배포가능 front-end 그 어느 것도 ≤15cm 미달.
  **PRIMARY RANSAC wall-plane corner 기각**(median 19.30cm vs convex 17.13cm, 2/10 vs 4/10, high-variance:
  41069048 3.4cm win / 41159519 105cm blow-up). 최고 배포가능 `convex_band` 17.13cm/4-of-10 도 FAIL.
  oracle `sweep_best` 11.60cm/7-of-10 = headroom 증명이나 GT-tuned·배포 불가. root cause = periphery
  under-coverage(corner-fitting 아님). **rough-tier 고정**, convex_band 는 rough-tier 내 무비용 in-tier upgrade.
- **모든 수치 = `/home/seung/mmhoa/spike-vggt-multiview/OQ59_VERDICT.md`**(독립 critic APPROVE). 여기 재유도 금지·복사.
- **doc write-back 완료**: D84(`.omc/plans/decisions.md`) + ADR 0045 §Status-update-2026-06-04 + §C 노트 갱신
  (`docs/adr/0045-...`) + OQ-59 RESOLVED + top-level 요약(`.omc/plans/open-questions.md`) + v0.24.x 트래커 close
  (`.omc/plans/v0.24.x-non-shoebox-and-multiview.md`) + 본 RESUME POINTER. ADR header PROPOSED 유지. repo byte-equal `f494732`.
- **이 파일이 OQ-59 resume 진실원천이며, 사이클은 COMPLETE.** 다음 = OQ-52(in-domain ckpt) 또는 coverage 레버(OQ-59 b/c/d).

## RESUME POINTER
- **목표**: OQ-53(D83)이 남긴 갭 — multi-view VGGT는 scale PASS이나 ≤15cm floor-geometry는 FALLBACK(median 22.4cm, 43% area undershoot). OQ-59 = "더 똑똑한 front-end가 ≤15cm 게이트를 close 하는가". 4 lever: (a) RANSAC wall-plane corner, (b) coverage-aware capture, (c) TSDF fusion, (d) VGGT-Omega ckpt.
- **스파이크 위치**: `/home/seung/mmhoa/spike-vggt-multiview/` (repo 밖, repo는 f494732 byte-equal 유지 — 이 사이클 산출물은 roomestim docs-only).
- **결정**: 사용자 "1번부터 진행" = OQ-59. 자율 execute→verify→repeat. OMC 오케스트레이션, 자기승인 금지.

## 착수 시점 발견된 현실 (이전 세션 잔여)
이전 세션이 OQ-59 compute를 거의 다 돌렸으나 3개 갭으로 **정직하게 닫을 수 없는 상태**:
1. **RANSAC(=PRIMARY lever a) 10방 전부 OOM 크래시** — wall band ~1M pts에서 N×N(예: 1.1M×1.1M float64 = TiB) 할당 시도. concave-hull fallback / RANSAC 경로. → 핵심 가설 **미검증**.
2. **`oq59_verdict.json:gate_pass=true`는 오해 소지** — `eval_frontends.py:170`에서 `all_pass`(=Step-1 reproduction gate, 캐시가 baseline 22.4cm 재현하는가)일 뿐, ≤15cm 정확도 게이트 아님.
3. **roomestim repo 미반영** — D84 없음, ADR 0045 §Status-update 없음, OQ-59 resolution 없음, `OQ59_VERDICT.md` 미생성.

## 현재까지의 데이터 (oq59_verdict.json, nv48 동일 cloud, best_fit_2d 동일)
- baseline_concave (control): median 22.41cm, 2/10 ≤15cm
- convex_band (배포가능 fixed-param): median 17.13cm, 4/10 ≤15cm — 개선이나 게이트 FAIL
- ransac_walls (PRIMARY): **CRASHED/미검증** (OOM)
- sweep_best (ORACLE, 배포 불가 — GT 대조 per-room param 선택): median 11.6cm, 7/10 ≤15cm → headroom 존재 증명, 단일 고정 param으로는 재현 불가(oracle)
- degeneracy 방: 41159503(scale 63% off), 41125756(scale 14% off)

## Phases (체크포인트)
- [x] P0: resume 상태 진단 — 위 3갭 식별, 캐시(10×120MB full cloud) 재사용 가능(오프라인, GPU 불필요) 확인.
- [x] P1: RANSAC OOM 수정 — wall band subsample(≤100k pts, seeded) + SVD full_matrices=False. 10방 전부 실제 polygon 산출(~1-2s/방). roomestim repo 무변경.
- [x] P2: `eval_frontends.py` 오프라인 재실행(cache). Step-1 reproduction gate PASS(10방 delta 0.00cm). 실제 ransac_walls 수치 확보(median 19.30cm).
- [x] P3: 정직한 `OQ59_VERDICT.md` 작성 — gate 의미 교정(reproduction≠accuracy), RANSAC 결과, oracle vs deployable 구분, 최종 verdict=FALLBACK hardened.
- [x] P4: 독립 code-review + verifier (자기승인 금지) — critic APPROVE.
- [x] P5: roomestim docs 반영 — D84, ADR 0045 §Status-update-2026-06-04, OQ-59 RESOLVED(open-questions), v0.24.x 트래커 close, 이 RESUME POINTER 갱신. doc-only(미커밋, 리뷰 대기).

## 게이트
- ≤15cm median corner error (vs RoomPlan LiDAR ~8.5cm) = install-grade 1급 경로 승급 기준. 미달 시 rough-estimate tier(정직 metric scale + per-corner uncertainty) 고정.
- 모든 변형은 동일 nv48 cloud + 동일 best_fit_2d metric. 배포가능(fixed-param) vs oracle 명확 구분 필수.

## 제약
- roomestim repo는 f494732 byte-equal 유지(스파이크는 out-of-repo). 유일 repo 변경 = docs.
- canonical 게이트(roomestim 쪽 doc 변경 후): default+web pytest + ruff/mypy/tense — 단, doc-only면 코드 게이트 무영향(확인만).
