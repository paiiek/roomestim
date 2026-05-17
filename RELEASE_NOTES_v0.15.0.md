# roomestim v0.15.0 — Release Notes (CORE)

**Date**: 2026-05-17 evening
**Core package**: `roomestim.__version__ == "0.15.0"` (`pyproject.toml` 0.14.0 → 0.15.0)
**Web package**: `roomestim_web.__version__ == "0.12-web.6"` (unchanged; lane separation)
**Predecessor**: v0.12-web.6 (`9800fa5`)
**Trigger**: ADR 0028 §Reverse-criterion item 2 (D26 forbidden-indefinite-deferral)

---

## What v0.15.0 ships — predictor-default switch (Sabine → ISM > Eyring)

### 1. ADR 0030 NEW — predictor-default cascade

- **Cascade order**:
  1. ISM (`image_source_rt60`) for rectilinear shoebox rooms.
  2. Eyring (`eyring_rt60`) for non-shoebox rooms (or `prefer_ism=False`).
  3. Sabine is no longer the default; remains for backward-compat / comparison.
- **Trigger**: ADR 0028 §Reverse-criterion item 2 — Office_1 ISM/Sabine =
  2.0059 + conference ISM/Sabine = 5.0537 both > 1.15 across ≥ 2 glass-heavy rooms.
- **D26 honored**: forbidden-indefinite-deferral clause satisfied; v0.15.0 within
  the v0.15+ MUST-land trigger window. Failing to land would have made D26 a
  dead letter.

### 2. Core 신규 — `roomestim/reconstruct/predictor.py`

- `predict_rt60_default(room, area_dict, *, prefer_ism=True, max_order=50) -> RT60Prediction`
- `predict_rt60_default_per_band(room, area_dict, ...) -> RT60Prediction`
- `is_rectilinear_shoebox(room) -> bool` — 4-pt axis-aligned 검출.
- `RT60Prediction` frozen dataclass: `rt60_s`, `rt60_per_band_s`,
  `predictor_name: Literal["image_source", "eyring"]`, `rationale: str`.
- Geometry helpers `_polygon_area_3d`, `_room_volume`, `_shoelace_2d` core에
  duplicate (web 의존성 차단; D29 layering 준수).
- `roomestim/reconstruct/__init__.py` — public re-exports 5 symbols.

### 3. Web report 통합 — `roomestim_web/report.py`

- `AcousticReport` 에 4 신규 필드:
  - `default_rt60_500hz_s: float`
  - `default_rt60_per_band_s: dict[int, float] | None`
  - `default_predictor_name: str`
  - `default_predictor_rationale: str`
- `to_json_dict()`: 4 필드 직렬화 (string-keyed per-band dict 일관).
- `compute_acoustic_report()`: `predict_rt60_default*` 호출. ISM 실패 시 Eyring
  fallback degradation + rationale에 실패 사유 기록 (Acoustic Report tab 보호).
- `build_rt60_bar_chart()`: headline horizontal line을 default cascade로 전환:
  - "ISM (default) 500 Hz = X.XX s" (shoebox 분기)
  - "Eyring (default fallback) 500 Hz = X.XX s" (non-shoebox 분기)
  - ISM 분기 시 green "ISM (default)" per-band bar 추가.
- Sabine + Eyring 바 + 필드 모두 backward-compat 유지.

### 4. 테스트 — `tests/test_predict_rt60_default.py` NEW 9 케이스

- `is_rectilinear_shoebox`: lab_room True / 3-point False / off-axis False.
- `predict_rt60_default`: shoebox → ISM, rationale 'shoebox' + 'ISM'.
- `predict_rt60_default_per_band`: 6 밴드 + 500 Hz 일치.
- `prefer_ism=False`: Eyring 분기 escape hatch.
- ISM/Eyring 런타임 invariant: `ism_rt60 >= eyring_rt60 - 1e-6` (ADR 0009).
- `RT60Prediction` frozen 확인.
- `PredictorName` Literal 집합 = `{"image_source", "eyring"}`.

### 5. ADR / D / OQ

- **ADR 0030 NEW** — predictor-default switch decision.
- **ADR 0028 §Status-update-v0.15.0 NEW** — Item D landed 기록.
- **D38 NEW** — 정책 (cascade order).
- **OQ-30 NEW** — per-wall α decomposition for mixed-material walls (v0.15.x+).

---

## 버전

| 항목 | 이전 | 이후 |
|---|---|---|
| `roomestim.__version__` | `0.14.0` | **`0.15.0`** |
| `pyproject.toml version` | `0.14.0` | **`0.15.0`** |
| `roomestim_web.__version__` | `0.12-web.6` | `0.12-web.6` (불변; lane 분리) |
| `__schema_version__` | `0.1-draft` | `0.1-draft` (불변) |

---

## 검증 결과

| Check | 결과 |
|---|---|
| `pytest tests/test_predict_rt60_default.py` | **9 passed** |
| `pytest -m "not lab and not web"` | **159 passed, 4 skipped** (+9 from 150) |
| `pytest tests/web/` | **48 passed, 1 skipped** (report.py backward-compat) |
| `ruff check roomestim/ roomestim_web/ tests/` | All checks passed |
| `mypy --strict roomestim/` | 0 errors (**33 source files**, +1 predictor.py) |
| `roomestim.__version__` | `0.15.0` |
| `pyproject.toml version` | `0.15.0` |
| `predict_rt60_default(lab_room)` smoke | `image_source`, rt60 ≈ 1.92 s, rationale "shoebox L=5.00 W=4.00 H=2.85: ISM" |
| `_binaural_data_present()` (web smoke) | True (KEMAR + source.wav 로컬 존재) |

---

## What stays the same (byte-equal)

- `roomestim/reconstruct/materials.py` (Sabine + Eyring 공개 API 그대로).
- `roomestim/reconstruct/image_source.py` (ISM 공개 API 그대로).
- `roomestim/model.py`, `roomestim/adapters/`, `roomestim/place/`,
  `roomestim/export/` 모두 byte-equal.
- `AcousticReport.sabine_*` / `eyring_*` 필드 4개 backward-compat.
- ADR 0001-0029 unchanged. ADR 0028에 §Status-update-v0.15.0 append만.
- `roomestim_web/` 전체 byte-equal except `report.py` (default 필드 추가).

---

## Closed items

- **ADR 0028 §Reverse-criterion item 2**: Item D landed.
- **D26**: forbidden-indefinite-deferral clause honored (predictor-default
  switch within v0.15+ trigger window).

---

## Known gaps / 다음 버전 후보

- **OQ-30** (v0.15.0 NEW): per-wall α decomposition for mixed-material walls —
  현재 area-weighted average. v0.15.x 또는 v0.16.0.
- **OQ-23** (still deferred from v0.14.0): polygon ISM for non-shoebox rooms.
  현재 non-shoebox → Eyring fallback.
- **ADR 0030 §Reverse-criterion item 2**: UI toggle for `prefer_ism` —
  사용자 피드백 누적 시 추가 후보.
- **`prefer_ism` 강제 OFF 옵션 UI 표시 안 함**: web app.py에 default 변경
  표시 없음 — v0.12-web.7 후보.
- **HF Spaces 실 배포 검증**: web/core 양쪽 모두 unit test로만 검증.
- **v0.15.0 MEDIUM-1** (code-review 2026-05-17): `_band_alpha` per-band silent
  fallback. surface가 `absorption_bands` 없으면 `0.10` 또는 `absorption_500hz`
  scalar로 fallback — rationale string에 누적 기록 안 됨. v0.15.x patch에서
  rationale 누적 또는 surface-level pre-validation 추가 권고. 현재 docstring
  §"Per-band data fallbacks"에 명시.
- **v0.15.0 LOW-1** (code-review 2026-05-17): `_polygon_area_3d` /
  `_room_volume` / `_shoelace_2d`가 `predictor.py`와 `roomestim_web/report.py`
  양쪽에 duplicate. D29 lane separation 이유로 의도적이나 drift 위험. v0.15.x+
  `roomestim/geom/polygon.py` shared util로 추출하면 두 카피 drift 방지 가능
  (v0.12-web.x에서 web → core import로 정정).

---

## OMC orchestration

- **planner**: `.omc/plans/v0.15-design.md` NEW 4 Phase + 8 acceptance gates.
- **executor**: 본 패치 (predictor.py + report.py + tests + docs + version).
- **code-reviewer**: 본 commit 직후 (별도 패스).
- **verifier**: 본 commit 직전 검증 게이트 GREEN.

---

## 다음 큰 작업 — v0.15.x / v0.16.0 후보

1. **OQ-30** per-wall α decomposition (정확도 향상).
2. **OQ-23** polygon ISM (non-shoebox 처리).
3. **v0.12-web.7** UI 표시: default predictor name을 사이드바에 표시.
4. **HF Spaces 실 배포 dry-run** + cold-boot 측정.
