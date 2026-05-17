# roomestim v0.12-web.6 — Release Notes

**Date**: 2026-05-17 evening
**Web package**: `roomestim_web.__version__ == "0.12-web.6"`
**Core package**: `roomestim.__version__ == "0.14.0"` (byte-equal, no changes)
**Predecessor**: v0.12-web.5 (`a054add`)

---

## What v0.12-web.6 ships — 약한점·위험 모두 정돈 패치

### 1. HF Spaces 위험 차단

- **`packages.txt` NEW** (repo root): `ffmpeg` — HF Spaces가 system-level 의존성을
  auto-detect. v0.12-web.4 이후로 LibriVox MP3 → 30s WAV ffmpeg 트림이 HF Spaces
  default Python image에 ffmpeg 미설치로 영구 실패하던 위험을 닫음 (D37 NEW).
- **부팅 직후 안내**: `_ensure_web_data() -> bool` 변경 — daemon thread 시작 시 True,
  아니면 False. `build_demo()`가 반환값에 따라 `binaural_status_md` Markdown 초기값을
  설정 → 첫 클릭 전에도 사용자에게 "데이터 다운로드 중" / "데이터 미준비" 안내가 보임.
  이전 v0.12-web.4/5에서는 첫 클릭 전까지 바이노럴 탭이 완전 비어있는 UX 갭이 있었음.

### 2. v0.12-web.5 code-review follow-up (MEDIUM-1 + MINOR-1/2 모두 absorbed)

- **MEDIUM-1**: `tests/web/_md_helpers.py` NEW — `get_md_payload(maybe_update)` 헬퍼가
  dict / object 양쪽에서 `(value, visible)` 페이로드 추출. Gradio 내부 `gr.update`
  표현이 바뀌어도 테스트가 silent pass 되지 않도록 격리. `test_binaural_fallback.py`
  refactor.
- **MINOR-1**: `test_fetch_kemar_integration_sha_mismatch_raises_and_unlinks` NEW —
  `fetch_kemar`를 실 byte 미스매치 환경에서 호출 → `RuntimeError` + `kemar.sofa`
  미존재 + `.tmp` 잔존 없음 보장 (OQ-27 production path end-to-end 검증).
- **MINOR-2**: `binaural_status_md` Markdown 정의 위 4-line 코멘트 — value가 매 성공 시
  `_binaural_status_update(None)`로 clear되며, 헬퍼의 None 분기를 건너뛰는 최적화를
  도입하지 말 것 (stale 메시지 잔존 방지).

### 3. v0.12-web.4 code-review follow-up (MINOR-2/3/4/5 absorbed)

- **MINOR-2** (`print()` → quiet flag): `_progress_quiet()` 헬퍼 +
  `ROOMESTIM_WEB_QUIET_FETCH=1` env. `_download_file`의 진행률 print가 daemon 모드에서
  억제됨. `_ensure_web_data()`가 background thread 시작 시 env를 자동 setdefault.
- **MINOR-3** (`_BINAURAL_DATA_ROOT` 함수화): `_binaural_data_present()` 함수 추출 —
  데이터 존재 여부 체크를 한 곳으로 통합. `_BINAURAL_DATA_ROOT`는 mod-global 유지
  (테스트 patch 호환). 완전 lazy refresh는 over-engineering으로 판단, 보류.
- **MINOR-4** (env-gate DRY): `scripts.fetch_web_data.auto_fetch_enabled()` 헬퍼 NEW.
  3개 callsite (`auto_fetch`, `main()`, `app.py:_ensure_web_data`) 가 동일 해석 공유.
- **MINOR-5** (zip-slip docstring): `extract_hutubs` docstring에 4-line 노트 — 출력
  경로가 zip 내부 이름과 무관함을 명시 (실제 vulnerability 아닌 docstring 보강).

### 4. v0.12-web.5 MINOR-3 drift root-cause 식별

`tests/test_mypy_strict_baseline.py:30 pytest.mark.skipif(not _MYPY_AVAILABLE)` —
mypy 패키지 미설치 환경에서 1 skip 증가. v0.12-web.5 reviewer 환경에 mypy 없어 149p/5s,
writer 환경에 mypy 있어 150p/4s. 본 release notes에 root-cause 명시.

### 5. OQ NEW

- **OQ-28 NEW**: 3 upstream URL (KEMAR/LibriVox/HUTUBS) availability monitoring —
  SHA pin은 byte 변조만 잡고 URL rotation은 못 잡음. GitHub Action cron stub 계획.
- **OQ-29 NEW**: HUTUBS pp1 SOFA GitHub mirror (OQ-26의 일부 — 10 MB만 mirror하면
  KEMAR과 같은 auto-fetch 경로 추가 가능).

---

## 버전

| 항목 | 이전 | 이후 |
|---|---|---|
| `roomestim_web.__version__` | `0.12-web.5` | **`0.12-web.6`** |
| `roomestim.__version__` | `0.14.0` | `0.14.0` (byte-equal) |
| `pyproject.toml` | `0.14.0` | `0.14.0` (불변) |

---

## 검증 결과

| Check | 결과 |
|---|---|
| `pytest tests/web/` | **48 passed, 1 skipped** (+1 SHA mismatch integration) |
| `pytest -m "not lab and not web"` | **150 passed, 4 skipped** (writer env) / 149+5 (mypy 없는 env) |
| `ruff check roomestim_web/ scripts/ tests/web/` | All checks passed |
| `mypy --strict roomestim/` | 0 errors (32 source files) |
| `git diff roomestim/` | empty (core byte-equal) |
| `build_demo()` smoke | 29 components, Markdown 초기값 조건부 |
| `_binaural_data_present()` smoke | True (KEMAR + source.wav 로컬 존재) |
| `_binaural_status_update("test")` smoke | `{'value': 'test', '__type__': 'update', 'visible': True}` |
| `roomestim_web.__version__` | `0.12-web.6` |
| `pyproject.toml` | `0.14.0` 불변 |

---

## What stays the same (byte-equal)

- `roomestim/` 전체 (코어 byte-equal).
- `roomestim_web/binaural.py`, `hrtf_io.py`, `report.py`, `setup_pdf.py`, `archive.py`,
  `provenance.py`, `viewer.py`, `pipeline.py` 모두 unchanged.
- ADR 0001–0028 unchanged. ADR 0029 §A에 §Status-update-v0.12-web.6 append.
- `pyproject.toml` 버전 `0.14.0` 불변 (D30).

---

## Closed items

- **MEDIUM-1** (v0.12-web.5 code-review): `gr.update` test contract → `_md_helpers.get_md_payload`.
- **MINOR-1** (v0.12-web.5 code-review): `fetch_kemar` integration mismatch test.
- **MINOR-2** (v0.12-web.5 code-review): binaural-status 코멘트.
- **MINOR-3** (v0.12-web.5 code-review): drift root-cause 식별.
- **MINOR-2** (v0.12-web.4 code-review): print → quiet flag.
- **MINOR-3** (v0.12-web.4 code-review): `_binaural_data_present()` 함수화 (부분).
- **MINOR-4** (v0.12-web.4 code-review): env-gate DRY.
- **MINOR-5** (v0.12-web.4 code-review): zip-slip docstring.
- **위험 #1**: HF Spaces ffmpeg → `packages.txt` NEW.
- **위험 #3**: 첫 클릭 전 빈 탭 → `_ensure_web_data() -> bool` + boot Markdown.

---

## Known gaps / 다음 버전 후보

- **OQ-26 + OQ-29**: HUTUBS pp1 SOFA GitHub mirror — 외부 의존성 (라이선스 + 호스팅).
- **OQ-28**: URL availability cron 모니터링 — GitHub Actions infrastructure 필요.
- **위험 #2**: KEMAR/LibriVox URL rotation 모니터링 — OQ-28으로 추적.
- **HF Spaces 실 배포 검증 0**: cold-boot 60s 측정, ffmpeg PATH 검증, daemon thread
  timing은 unit test로만 보장 — 실 배포 dry-run 권장.

---

## 다음 큰 작업 — Core v0.15 predictor-default switch

v0.14.0 ADR 0028 §Reverse-criterion item 2가 "predictor-default switch MUST land at
v0.15+ per D26 forbidden-indefinite-deferral clause"를 명시. Office_1 + conference
두 글래스 헤비 룸 모두 ISM/Sabine > 1.15 → signature 확정. v0.12-web.6 commit 후
**core v0.15.0** 진입 — `roomestim_web/report.py`의 default predictor annotation을
Sabine → ISM (shoebox일 때) / Eyring (non-shoebox fallback)로 전환 + ADR 0030 NEW.
