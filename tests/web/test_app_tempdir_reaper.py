"""tests/web/test_app_tempdir_reaper.py — deque eviction + stale-dir walker."""
from __future__ import annotations

import os
import tempfile
import time
import uuid
from pathlib import Path

import pytest

pytest.importorskip("gradio")

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
    # Fill the deque completely, then push one more and check the first is gone.

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
    """_reap_stale_tempdirs must delete THIS PID's roomestim_<pid>_* dirs older than max_age.

    OQ-45 / ADR 0038: the reaper glob is now per-PID, so the stale dir must carry
    this process's PID to be matched.
    """
    tmproot = Path(tempfile.gettempdir())
    stale_name = f"roomestim_{os.getpid()}_stale_{uuid.uuid4().hex[:8]}"
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


@pytest.mark.web
def test_reap_stale_tempdirs_spares_other_pid(tmp_path: Path) -> None:
    """OQ-45 / ADR 0038: the per-PID reaper must NOT delete another process's tempdirs.

    A stale dir owned by an alien PID must survive; this process's own stale dir
    is still reaped in the same call.
    """
    tmproot = Path(tempfile.gettempdir())
    suffix = uuid.uuid4().hex[:8]
    alien_pid = os.getpid() + 1  # any PID that is not ours
    alien_dir = tmproot / f"roomestim_{alien_pid}_alien_{suffix}"
    ours_dir = tmproot / f"roomestim_{os.getpid()}_ours_{suffix}"
    alien_dir.mkdir()
    ours_dir.mkdir()
    old_time = time.time() - 5 * 3600
    os.utime(alien_dir, (old_time, old_time))
    os.utime(ours_dir, (old_time, old_time))

    try:
        _reap_stale_tempdirs(max_age_seconds=4 * 3600)

        assert alien_dir.exists(), (
            f"Alien-PID tempdir {alien_dir} must survive the per-PID reaper, but it was deleted."
        )
        assert not ours_dir.exists(), (
            f"This process's stale dir {ours_dir} should still be reaped, but it survives."
        )
    finally:
        if alien_dir.exists():
            alien_dir.rmdir()
        if ours_dir.exists():
            ours_dir.rmdir()
