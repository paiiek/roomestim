# roomestim v0.12-web.4 — Release Notes

**Date**: 2026-05-17
**Web package**: `roomestim_web.__version__ == "0.12-web.4"`
**Core package**: `roomestim.__version__ == "0.14.0"` (byte-equal, no changes)
**Predecessor**: v0.12-web.3 (`997b63d`)

---

## What v0.12-web.4 ships

### Phase 1 — WFS UX (결함 1 닫기)

- **`roomestim_web/app.py`**: `wfs_f_max_hz` 슬라이더 추가 (500–8000 Hz, 기본 1500 Hz).
  `algorithm == "wfs"` 선택 시 자동으로 표시됨 (`algorithm.change` 콜백).
- **`_on_submit`**: `wfs_f_max_hz` 인자 추가; `ValueError`를 별도 except로 잡아
  `report_json = {"error": "...", "algorithm": "wfs"}` 형태로 음향 리포트 탭에 표시.
  이전엔 WFS aliasing 에러가 `(None,)*6`으로 조용히 삼켜졌음.
- **`roomestim_web/pipeline.py`**: `run_pipeline()` 시그니처에 `wfs_f_max_hz: float = 8000.0` 추가;
  `run_placement(wfs_f_max_hz=...)` 로 전달.

### Phase 2 — 데이터 fetch 스크립트 재작성 (결함 2 일부)

- **`scripts/fetch_web_data.py`** 전면 개편:
  - `_download_file()`: urllib + atomic rename (tmp + os.replace) + SHA-256 검증.
  - `fetch_kemar()`: KEMAR SOFA 2.5 MB 자동 다운로드. 이미 존재하면 skip (idempotent).
  - `fetch_librivox()`: LibriVox MP3 다운로드 + ffmpeg 30s mono 48kHz 트림.
  - `extract_hutubs()`: 로컬 다운로드 zip에서 pp1 SOFA 추출 (수동 전용).
  - `auto_fetch()`: KEMAR + LibriVox 무인 fetch (`ROOMESTIM_WEB_AUTO_FETCH=0` opt-out).
  - CLI: `--auto`/`--download`, `--data-dir`, `--extract-hutubs`, `--force` 플래그.
  - HUTUBS (1.36 GB zip)는 자동 다운로드 없음 — 수동 안내 텍스트만.

### Phase 3 — app.py 통합 (결함 2 완성)

- **`_ensure_web_data()`**: 모듈 레벨 함수. `build_demo()` 호출 시 1회 실행.
  데이터 미존재 + `ROOMESTIM_WEB_AUTO_FETCH != "0"` 이면 daemon background thread 시작.
  thread 에러는 WARNING 로그로만 남음 (UI crash 없음). ADR 0029 §B.
- **바이노럴 폴백**: source.wav 또는 HRTF SOFA 없을 때 `binaural_str = None` +
  `report_json["binaural_status"]` 한국어 안내 메시지 (`--auto` 실행 유도). ADR 0029 §C.
- **바이노럴 경로 수정**: `source_wav` 경로를 CWD 상대 경로에서 `_BINAURAL_DATA_ROOT` 절대
  경로로 교체 (HF Spaces CWD 불확정 문제 해결).

### Code-review 2026-05-17 흡수 (MAJOR 2건 + MINOR-6)

- **MAJOR-1 (race + .tmp cleanup)** — `_ensure_web_data()` 의 파일 존재 체크를
  `_BINAURAL_FETCH_LOCK` 내부로 이동 (TOCTOU 닫힘). 신규 `_cleanup_stale_download_tmps()` 가
  `_BINAURAL_DATA_ROOT/{hrtf,audio}/*.tmp` 파일을 시작 시 정리 (이전 daemon thread 의
  인터럽트된 다운로드 잔존물). `app.py:69-118`.
- **MAJOR-2 (SHA-256 pin 부재)** — ADR 0029 §A 에 §Status-update-2026-05-17 honesty patch
  추가: "infrastructure 는 v0.12-web.4 에 landed, KEMAR/LibriVox 실 digest pin 은
  v0.12-web.5 / OQ-27 로 deferred". 코드 동작 변경 없음 — 정직성 문서 패치 (ADR 0018 + D35).
  OQ-27 NEW.
- **MINOR-6 (ffmpeg .tmp leak)** — `fetch_librivox()` 의 ffmpeg subprocess 호출부에
  중첩 `try/finally` 추가, KeyboardInterrupt / 실패 시 `source.wav.tmp` 정리.
  `scripts/fetch_web_data.py:174-191`.

### Phase 4 — 테스트 + 문서

- **`tests/web/test_wfs_ux.py`** NEW: 2 tests
  - `test_wfs_error_surfaces_in_report_json`: WFS aliasing → report_json["error"] 노출 확인.
  - `test_wfs_error_message_contains_aliasing_info`: dispatch ValueError 메시지 내용 확인.
- **`tests/web/test_fetch_web_data.py`** NEW: 3 tests
  - atomic download + SHA-256, fetch_kemar idempotent, extract_hutubs pp1 추출.
- **`tests/web/test_binaural_fallback.py`** NEW: 1 test
  - source.wav 없을 때 binaural=None + report_json["binaural_status"] 존재 확인.
- **`docs/adr/0029-web-data-autofetch.md`** NEW: auto-fetch 정책 ADR.
- **`.omc/plans/decisions.md`**: D36 NEW.
- **`.omc/plans/open-questions.md`**: OQ-26 NEW.
- **`tests/conftest.py`**: `ROOMESTIM_WEB_AUTO_FETCH=0` 기본값 설정 (CI 네트워크 격리).
- **`tests/web/test_app_exception_handling.py`**: `_on_submit` 인자 7개로 업데이트.

---

## 버전

| 항목 | 이전 | 이후 |
|---|---|---|
| `roomestim_web.__version__` | `0.12-web.3` | **`0.12-web.4`** |
| `roomestim.__version__` | `0.14.0` | `0.14.0` (byte-equal) |
| `pyproject.toml` | `0.14.0` | `0.14.0` (불변) |

---

## 검증 결과

| Check | 결과 |
|---|---|
| `pytest tests/web/test_wfs_ux.py` | 2 passed |
| `pytest tests/web/test_fetch_web_data.py` | 4 passed |
| `pytest tests/web/test_binaural_fallback.py` | 1 passed |
| `pytest tests/web/ -q` | **46 passed, 1 skipped** |
| `pytest -m "not lab and not web" -q` | **150 passed, 4 skipped** |
| `ruff check roomestim_web/ scripts/ tests/web/` | exit 0 (All checks passed) |
| `mypy --strict roomestim/` | 0 errors (32 source files) |
| `roomestim_web.__version__` | `0.12-web.4` |
| `pyproject.toml` | `0.14.0` 불변 |

---

## What stays the same (byte-equal)

- `roomestim/` 전체 (코어 byte-equal).
- `roomestim_web/binaural.py`, `hrtf_io.py`, `report.py`, `setup_pdf.py`, `archive.py`,
  `provenance.py`, `viewer.py` 모두 unchanged.
- ADR 0001–0028 unchanged.
- `pyproject.toml` 버전 `0.14.0` 불변 (D30).

---

## Known gaps / 다음 버전 후보

- **OQ-26**: HUTUBS URL 장기 안정성 미확인. pp1 SOFA GitHub mirror 확보 시 v0.12-web.5에서
  HUTUBS 자동 다운로드 가능.
- **OQ-27 (NEW, code-review MAJOR-2)**: `fetch_kemar` / `fetch_librivox` 가 SHA-256 pin
  없이 다운로드 (현재 WARNING 로그만). v0.12-web.5에서 실 digest pin 예정.
  ADR 0029 §A §Status-update-2026-05-17 참조.
- **HF Spaces cold-boot**: KEMAR 2.5 MB 다운로드가 60s 제한 내에 완료되지 않을 경우
  첫 부팅에서 바이노럴 탭이 비어있을 수 있음 (B3 폴백 메시지 표시). ADR 0029 §Reverse-criterion.
- **binaural_status_md Gradio 컴포넌트 (MINOR-1)**: 현재 `report_json["binaural_status"]`
  키로만 노출; 바이노럴 탭의 `gr.Markdown(elem_id="binaural-status")` 컴포넌트 wire-up은
  v0.12-web.5 UX 개선 후보.
