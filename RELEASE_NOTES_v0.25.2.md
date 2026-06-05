# roomestim v0.25.2 — near-horizon plausibility guard + per-room honesty disclosure

PATCH bump `0.25.1` → `0.25.2`. See ADR 0045
(`docs/adr/0045-image-to-geometry-capture-backend.md`,
§Status-update-2026-06-05c, D89/OQ-60), ADR 0046
(`docs/adr/0046-room-provenance-schema.md`, §Status-update-2026-06-05), and the
follow-up plan `.omc/plans/image-backend-honesty-followups.md` (§ROUND 2 F1/F2).

이 릴리스는 v0.25.0/0.25.1 image→geometry rough tier 의 **robustness / honesty
hardening** 입니다 — **정확도 개선이 아닙니다**. 단일-파노 image→geometry 는 여전히
**rough-estimate tier**, **install-grade 아님**(≤15 cm 는 LiDAR/RoomPlan 한정).

> **정직 우선.** 추정의 정확도는 달라지지 않았습니다. 이 릴리스는 (1) 비현실적
> 재구성을 조용히 내보내는 대신 요란하게 거부하고, (2) README 의 정확도 수치를
> 차원별 → 방 단위 현실로 정직하게 보정합니다. 데이터는 (무거운 catastrophic
> tail 때문에) 오히려 더 가혹합니다.

## ① near-horizon plausibility guard (F1) — `adapters/image.py`

단일-파노 cold eval(244 real panos)에서 가장 심각한 실패는 **near-horizon radius
blowup** 이었습니다: `r = cam_h / tan(-v_floor)` 는 floor 코너가 수평선에 가까울수록
발산하여, 주거 표본의 약 2%가 NO-FLAG 로 비현실적 거대 방(24.9 m, 41 m 등)을
방출했습니다. 기존 `_MIN_FLOOR_TAN=1e-6` 가드는 AT-horizon 만 잡고 NEAR-horizon 은
통과시켜 너무 느슨했습니다.

- `_corners_to_room` 에 per-corner 절대 반경 상한 `_MAX_PLAUSIBLE_RADIUS_M = 20.0` m
  추가. **데이터 기반**: legit-room max corner-radius p95 = 14.5 m, p99 = 27.9 m.
- 반경이 상한을 넘는 코너는 **조용히 건너뛰지 않고**(silent skip 은 force-cuboid
  quad 의 `<3 corners` 경로를 깨뜨림) depression-angle 진단을 담은 `ValueError` 로
  **요란하게 거부(raise)**합니다 — 비현실적 차원을 방출하느니 명확히 실패.
- 240 panos 에서 **false-reject 0**, 실제 reject rate ≈ **2.9%**(비현실적
  near-horizon tail + 단일-파노 st3d 가 어차피 신뢰 재구성 불가한 p95–p99 매우 큰
  방의 얇은 정상 슬라이스). 기존 `_MIN_FLOOR_TAN` AT-horizon skip 경로는 그대로
  보존됩니다(새 raise 가 가리지 않음).
- 매우 큰 방(>~40 m)은 rough tier 에서 **미지원**.

behavior change(이전엔 거대 방을 조용히 방출 → 이제 거부)이므로 **PATCH** 범프.

## ② README per-room accuracy disclosure (F2) — `README.md`

기존 image-backend 정확도 블록의 35–57 cm / 11–17% 는 **차원별(per-dimension)**
수치였습니다. cold eval 기준 **방 단위(per-room, 양변 모두 정확)** 현실은 약 2.5배
가혹합니다:

- per-room median 벽 오차 ≈ **83–95 cm**.
- **양변 모두 ≤15 cm 도달은 주거 8% · 사무 3%**뿐.
- dominant lever 는 여전히 사용자 공급 `--cam-height`(±10 cm → ≈ median 32 cm 벽
  오차, 선형).

"rough pre-scan/sanity, 설치 측정 아님" 결론은 유지되며 — 데이터는 오히려 더
가혹합니다.

## What stays the same

| Item | Value |
|---|---|
| Estimate accuracy | **개선 없음** — 여전히 rough tier, NOT install-grade |
| `__schema_version__` | `0.2-draft` (unchanged) |
| 정상 방 출력 | 변화 없음 — 모든 코너가 20 m 이내인 합법적 방은 그대로 |
| Core dependencies | unchanged — 모든 model dep 은 `[vision]` 뒤(core torch-free) |
| `roomestim_web` | untouched (web image upload 여전히 deferred — OQ-57) |
| ≤15 cm install-grade claim | LiDAR/RoomPlan 한정 |

## OQ-60 (NEW, deferred, low priority)

절대 반경 상한(`_MAX_PLAUSIBLE_RADIUS_M=20.0`)은 "큰 방"과 "코너 오검출"을
혼동합니다(legit p95–p99 매우 큰 방도 거부). 진짜 mis-detection 신호는 *한 코너의
반경이 나머지 median 의 k배 이상 ≫* 인 상대 이상치입니다. 절대 상한을 **상대
outlier 테스트로 교체/보강**하고 임계값 k 를 tunable 파라미터로 노출하는 것이
후속 과제입니다(deferred · low priority). ADR 0045 §Status-update-2026-06-05c 참조.

## Test / gate evidence

Canonical miniforge env (`/home/seung/miniforge3/bin/python -m pytest`):
- default (`-m "not web and not lab and not e2e"`): **356 passed / 6 skipped**
  (F1 가드용 신규 테스트 2개 추가).
- web (`-m web`): **86 passed / 4 skipped** (web source untouched).
- ruff `roomestim`: clean. mypy strict baseline + lint_tense: green (default gate).
- executor → independent code-review APPROVE-WITH-FIXES(적용 완료) → independent
  verifier. No self-approval.

## Versioning

- `roomestim`: `0.25.1` → `0.25.2` (PATCH — behavior change: 비현실적 재구성 거부 +
  honesty doc 보정). `pyproject.toml` + `roomestim/__init__.py`.
- `roomestim_web`: unchanged. `__schema_version__`: `0.2-draft` (unchanged).

## Tag note

Local-only PATCH tag (no PyPI release). Vendored HorizonNet under MIT; model
weights not redistributed.
