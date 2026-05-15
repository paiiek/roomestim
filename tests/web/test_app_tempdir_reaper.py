"""tests/web/test_app_tempdir_reaper.py — deque eviction + stale-dir walker."""
from __future__ import annotations

import os
import tempfile
import time
import uuid
from pathlib import Path

import pytest

pytest.importorskip("gradio")

import roomestim_web.app as app_module
from roomestim_web.app import _TEMP_REAPER, _reap_stale_tempdirs


@pytest.mark.web
def test_deque_eviction_removes_oldest_tempdir() -> None:
    """Pushing 9 TemporaryDirectory entries onto _TEMP_REAPER (maxlen=8) must evict the oldest."""
    # Drain pre-existing entries from other tests in the same pytest run.
    while _TEMP_REAPER:
        try:
            _TEMP_REAPER.popleft().cleanup()
        except Exception:
            pass

    # Drain any pre-existing entries so the deque is clean for this test.
    # We can't clear() a module-level deque without side-effects, so we push
    # enough entries to flush whatever is already there, then track the 9th.
    initial_len = len(_TEMP_REAPER)

    # We need to push (maxlen - initial_len + 1) extra entries to guarantee eviction.
    # Simpler: fill the deque completely, then push one more and check the first is gone.

    # Record initial oldest entries (to restore nothing — we just note their dirs)
    # Push 8 fresh TDs to fill the deque (this evicts any prior entries)
    fill_tds = [tempfile.TemporaryDirectory(prefix="roomestim_test_fill_") for _ in range(8)]
    for td in fill_tds:
        _TEMP_REAPER.append(td)

    # Deque is now full (maxlen=8); all fill_tds[0..7] should be in it.
    # Record the directory that is currently oldest (index 0).
    oldest_td = _TEMP_REAPER[0]
    oldest_dir = Path(oldest_td.name)
    assert oldest_dir.exists(), "Oldest tempdir should exist before eviction"

    # Push one more — this evicts fill_tds[0]
    new_td = tempfile.TemporaryDirectory(prefix="roomestim_test_new_")
    _TEMP_REAPER.append(new_td)

    assert not oldest_dir.exists(), (
        f"Expected evicted tempdir {oldest_dir} to be removed from disk, but it still exists."
    )

    # Cleanup: explicitly close remaining entries to avoid leaking dirs.
    new_td.cleanup()
    for td in fill_tds[1:]:
        td.cleanup()


@pytest.mark.web
def test_reap_stale_tempdirs_removes_old_dirs(tmp_path: Path) -> None:
    """_reap_stale_tempdirs must delete roomestim_* dirs older than max_age_seconds."""
    tmproot = Path(tempfile.gettempdir())
    stale_name = f"roomestim_stale_{uuid.uuid4().hex[:8]}"
    stale_dir = tmproot / stale_name
    stale_dir.mkdir()

    # Backdate mtime to 5 hours ago (beyond the 4-hour threshold)
    old_time = time.time() - 5 * 3600
    os.utime(stale_dir, (old_time, old_time))

    assert stale_dir.exists(), "Stale dir must exist before calling reaper"

    _reap_stale_tempdirs(max_age_seconds=4 * 3600)

    assert not stale_dir.exists(), (
        f"Expected stale dir {stale_dir} to be removed by _reap_stale_tempdirs, but it still exists."
    )
