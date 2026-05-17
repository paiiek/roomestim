# roomestim v0.12-web.5 — Release Notes

**Date**: 2026-05-17
**Web package**: `roomestim_web.__version__ == "0.12-web.5"`
**Core package**: `roomestim.__version__ == "0.14.0"` (byte-equal, no changes)
**Predecessor**: v0.12-web.4 (`910733b`)

---

## What v0.12-web.5 ships — v0.12-web.4 code-review follow-up patch

### 1. OQ-27 closure — SHA-256 실 digest pin

`scripts/fetch_web_data.py`에 실 SHA-256 digest 두 개를 pin (2026-05-17 upstream에서
직접 다운로드 후 계산):

```python
KEMAR_SOFA_SHA256 = "2c531e26b225435aabec05024c125ed96d55ced0a63d16b89f34e249d0dc4fd9"
LIBRIVOX_MP3_SHA256 = "b3053bbc683f76b676e1c2233479e7254c701af95a42e4a614d68756f4fffa72"
```

- `fetch_kemar` → `_download_file(..., expected_sha256=KEMAR_SOFA_SHA256)` 전달.
- `fetch_librivox` → `_download_file(..., expected_sha256=LIBRIVOX_MP3_SHA256)` 전달.
- 디지스트 불일치 시 `RuntimeError` + 부분 파일 unlink (기존 `_download_file` 게이트 활용).
- ADR 0029 §A §Status-update-v0.12-web.5에 closure 기록 (ADR 0018 honesty + D35).
- OQ-27 closure 표시.

### 2. MINOR-1 wire-up — binaural-status Markdown 컴포넌트

이전: `report_json["binaural_status"]` 키로만 노출되어 사용자가 음향 리포트 탭의 JSON에서
필드를 찾아야 했음. 바이노럴 탭은 여전히 비어있음.

이후: `gr.Markdown(elem_id="binaural-status")` 컴포넌트에 `binaural_status_md` 핸들
부여 + `_on_submit` 반환을 6-tuple → 7-tuple로 확장 + `submit_btn.click(outputs=[...])`
7요소 wire-up.

- 새 헬퍼: `_binaural_status_update(msg)` → `gr.update(value=msg, visible=msg is not None)`.
- Gradio 미설치 unit-test 환경에서는 `dict` 폴백 (`{"value": ..., "visible": ...}`).
- `report_json["binaural_status"]` 키는 backward 호환으로 유지 (legacy).

### 3. MINOR-7 — WFS 슬라이더 기본값 코멘트

`app.py:wfs_f_max_hz` 슬라이더 정의 위에 1-line 코멘트: 슬라이더 default 1500 Hz가
`dispatch.run_placement` default (8000 Hz)와 다른 이유 명시. VBAP/DBAP 분기에서는
무시됨.

### 4. 테스트 마이그레이션

- `tests/web/test_wfs_ux.py`: 7-tuple 분해 + `binaural_status_md` 검증.
- `tests/web/test_binaural_fallback.py`: 7-tuple + `binaural_status_md.visible/value` 검증.
- `tests/web/test_app_exception_handling.py`: `(None,)*6` → 길이 7 + 위치별 검증.
- `tests/web/test_fetch_web_data.py`: `test_fetch_kemar_passes_sha256_pin` NEW (SHA pin
  forward 검증).

---

## 버전

| 항목 | 이전 | 이후 |
|---|---|---|
| `roomestim_web.__version__` | `0.12-web.4` | **`0.12-web.5`** |
| `roomestim.__version__` | `0.14.0` | `0.14.0` (byte-equal) |
| `pyproject.toml` | `0.14.0` | `0.14.0` (불변) |

---

## 검증 결과

| Check | 결과 |
|---|---|
| `pytest tests/web/test_wfs_ux.py` | 2 passed |
| `pytest tests/web/test_fetch_web_data.py` | 5 passed (+1 SHA pin) |
| `pytest tests/web/test_binaural_fallback.py` | 1 passed |
| `pytest tests/web/test_app_exception_handling.py` | 1 passed (7-tuple) |
| `pytest tests/web/` | **47 passed, 1 skipped** |
| `pytest -m "not lab and not web"` | **150 passed, 4 skipped** (writer env) / **149 passed, 5 skipped** (reviewer env, +1 optional-dep skip drift; D35 honesty per code-review MINOR-3) |
| `ruff check roomestim_web/ scripts/ tests/web/` | All checks passed |
| `mypy --strict roomestim/` | 0 errors (32 source files) |
| `git diff roomestim/` | empty (core byte-equal) |
| `_binaural_status_update("test")` smoke | `{'value': 'test', '__type__': 'update', 'visible': True}` |
| `build_demo()` smoke | 29 components (Markdown handle wired) |
| `roomestim_web.__version__` | `0.12-web.5` |
| `pyproject.toml` | `0.14.0` 불변 |

---

## What stays the same (byte-equal)

- `roomestim/` 전체 (코어 byte-equal).
- `roomestim_web/binaural.py`, `hrtf_io.py`, `report.py`, `setup_pdf.py`, `archive.py`,
  `provenance.py`, `viewer.py`, `pipeline.py` 모두 unchanged.
- ADR 0001–0028 unchanged. ADR 0029 §A에 §Status-update-v0.12-web.5 append.
- `pyproject.toml` 버전 `0.14.0` 불변 (D30).

---

## Closed items

- **OQ-27**: SHA-256 pin (closed).
- **MINOR-1** (code-review 2026-05-17): binaural-status wire-up.
- **MINOR-7** (code-review 2026-05-17): WFS 슬라이더 코멘트.

## Known gaps / 다음 버전 후보

- **OQ-26**: HUTUBS URL 장기 안정성 미확인. pp1 SOFA GitHub mirror 확보 시 자동 다운로드 가능.
- **v0.12-web.4 MINOR-2/3/4/5** (code-review 2026-05-17): print → log debug,
  `_BINAURAL_DATA_ROOT` 함수화, env-gate DRY, zip-slip 코멘트 — v0.12-web.6 정돈 후보.
- **v0.12-web.5 MEDIUM-1** (code-review 2026-05-17 PM): 테스트가 Gradio `gr.update`
  내부 dict 형식 (`{"value", "__type__", "visible"}`)에 직접 의존 → 헬퍼 `_get_md_payload`
  추출 + Gradio 버전 pin 권장 (v0.12-web.6 후보).
- **v0.12-web.5 MINOR-1** (code-review 2026-05-17 PM): `fetch_kemar` 통합 테스트
  (실 byte 미스매치 → RuntimeError + 미존재 보장) 추가 권장. 현재는 forward 테스트 +
  하위 `_download_file` gate 테스트 조합으로 커버 (v0.12-web.6 후보).
- **v0.12-web.5 MINOR-2** (code-review 2026-05-17 PM): `binaural-status` Markdown
  초기값 처리 코멘트 보강 권장 (v0.12-web.6 후보).
- **HF Spaces cold-boot**: KEMAR 2.5 MB 다운로드가 60s 제한 내 미완료 시 첫 부팅 폴백 메시지.
