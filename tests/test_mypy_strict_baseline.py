"""v0.13 — mypy --strict default-lane baseline guard (OQ-13i resolved).

Per `.omc/plans/v0.13-design.md` §1.2 row 3 (REQUIRED per Critic Round-2
Delta 5) and §2.C: this test invokes `mypy --strict roomestim/` as a
subprocess and asserts exit code 0. The `pyproject.toml [tool.mypy]` block
already declares `strict = true` + `files = ["roomestim"]`; v0.13 enforces
the previously-tolerated 3 pre-existing errors at
`roomestim/adapters/ace_challenge.py:554-556` (closed at v0.13 ship via
the `_geom_float` narrowing helper) and rejects any regression.

If this test ever fails:
- 1-3 new errors: investigate the touchpoint; the strict baseline is a
  HARD GATE post-v0.13 (no "≤ 5 escape hatch" per v0.13 §5.2).
- > 50 new errors: a deeper structural typing issue likely; per v0.13
  §0.4 STOP rule #1 the response is per-module narrowing under a
  successor D-decision (NOT this test's relaxation).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_mypy_strict_clean() -> None:
    """`mypy --strict roomestim/` exits 0 (no errors).

    Encodes the v0.13 closure of OQ-13i: the 3 known
    `float(object)` errors at `roomestim/adapters/ace_challenge.py:554-556`
    are fixed via the `_geom_float` narrowing helper; no cascade reveals
    landed during the v0.13 cleanup pass (3 known + 0 cascade = 3 total
    pre-fix; 0 post-fix). The `pyproject.toml [tool.mypy]` block already
    contains `strict = true`; this test guards against silent regression.
    """
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "roomestim/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"mypy --strict roomestim/ failed with exit code {result.returncode}.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
        "Per v0.13 §5.2: 0 errors REQUIRED; no relaxation hatch. "
        "If > 50 errors landed in one go, invoke v0.13 §0.4 STOP rule #1 "
        "(per-module narrowing under successor D-decision); for 1-N small "
        "regressions, fix the touchpoint."
    )
