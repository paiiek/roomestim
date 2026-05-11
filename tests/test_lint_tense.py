"""v0.11 ADR 0020 — tense lint smoke (live repo + 4 seeded-fixture branches).

The seeded branches mitigate pre-mortem §5.3 (lint becoming the new honesty
leak via mis-implemented block-exclusion regex). All branches live inside
ONE test function to keep the v0.11 +5-default-lane count intact.
"""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "lint_tense.py"


def _run_module_against_seeded_text(text: str, tmp_path: Path) -> tuple[int, str]:
    """Import lint_tense as a module against a tmp tree containing one
    seeded README.md; return (exit_code, captured_stdout)."""
    spec = importlib.util.spec_from_file_location("lint_tense", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seeded_dir = tmp_path / "tests" / "fixtures" / "seeded"
    seeded_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "adr").mkdir(parents=True, exist_ok=True)
    (seeded_dir / "README.md").write_text(text, encoding="utf-8")
    module.REPO_ROOT = tmp_path
    buf = io.StringIO()
    saved = sys.stdout
    try:
        sys.stdout = buf
        code = module.main()
    finally:
        sys.stdout = saved
    return code, buf.getvalue()


def test_no_present_tense_version_specific_framing(tmp_path: Path) -> None:
    """Live-repo lint exits 0; seeded-fixture branches (block + noqa) per ADR 0020."""
    # Branch 1: live repo
    live = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert live.returncode == 0, (
        f"live lint_tense flagged unexpected leaks (exit {live.returncode}):\n{live.stdout}"
    )

    # Branch 2: seeded bad outside exclusion
    bad_outside = (
        "# Title\n\nSome description.\n"
        "We ship MELAMINE_FOAM in v0.99.0 — deliberate bad case.\n"
    )
    code, out = _run_module_against_seeded_text(bad_outside, tmp_path / "b2")
    assert code == 1, f"branch 2: seeded-bad outside exclusion must trip lint; got {code}, {out!r}"

    # Branch 3: seeded bad inside §Status-update-
    bad_in_status = (
        "# Title\n\n"
        "## §Status-update-2026-05-11 (audit-trail block)\n"
        "We ship MELAMINE_FOAM in v0.11.0 — present tense ok inside the block.\n"
    )
    code, out = _run_module_against_seeded_text(bad_in_status, tmp_path / "b3")
    assert code == 0, f"branch 3: §Status-update-block must exclude; got {code}, {out!r}"

    # Branch 4: seeded bad inside §Honesty-correction-
    bad_in_honesty = (
        "# Title\n\n"
        "## §Honesty-correction-2026-05-10 (audit-trail block)\n"
        "We ship correction notes in v0.10.1 — present tense ok inside the block.\n"
    )
    code, out = _run_module_against_seeded_text(bad_in_honesty, tmp_path / "b4")
    assert code == 0, f"branch 4: §Honesty-correction-block must exclude; got {code}, {out!r}"

    # Branch 5: per-line noqa
    bad_with_noqa = (
        "# Title\n\n"
        "We ship MELAMINE_FOAM in v0.11.0  # noqa: lint-tense — intentional doc example\n"
    )
    code, out = _run_module_against_seeded_text(bad_with_noqa, tmp_path / "b5")
    assert code == 0, f"branch 5: noqa marker must exclude; got {code}, {out!r}"
