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


def test_lint_tense_scope_includes_expanded_files() -> None:
    """v0.12 scope expansion (ADR 0020 §Status-update-2026-05-12): the lint
    scope MUST include perf docs + architecture + top-level README in addition
    to the v0.11 baseline scope (fixture README + ADR + past RELEASE_NOTES).

    Asserts that the live `_scoped_files()` returns at least one file from
    each of the 3 newly-added families (preemptive guard against silent
    scope contraction).

    NOTE (v0.13): v0.13 scope expansion-2 (ADR 0020 §Status-update-2026-05-MM-2)
    is a strict superset of v0.12 scope; this v0.12-baseline guard remains
    valid because the v0.13 expansion is strictly additive. The v0.13
    sibling test `test_lint_tense_scope_includes_v0_13_expansion` covers
    the new families.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("lint_tense", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = module._scoped_files()
    rel_names = {p.relative_to(REPO_ROOT).as_posix() for p in files}
    perf_hits = [n for n in rel_names if n.startswith("docs/perf_verification_") and n.endswith(".md")]
    assert perf_hits, f"v0.12 scope must include ≥1 docs/perf_verification_*.md; got {sorted(rel_names)}"
    assert "docs/architecture.md" in rel_names, (
        f"v0.12 scope must include docs/architecture.md; got {sorted(rel_names)}"
    )
    assert "README.md" in rel_names, (
        f"v0.12 scope must include top-level README.md; got {sorted(rel_names)}"
    )


def test_lint_tense_scope_includes_v0_13_expansion() -> None:
    """v0.13 scope expansion-2 (ADR 0020 §Status-update-2026-05-MM-2;
    governed by D28-P1 supersedure clause for factual-scope-list-growth):
    lint scope MUST include the remaining `docs/*.md` families
    (non-adr / non-perf / non-architecture) AND `.omc/research/*.md`.

    Asserts at least one file from each of the newly-added v0.13 families
    is present in `_scoped_files()` output. Preemptive guard against
    silent scope contraction in future refactors.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("lint_tense", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = module._scoped_files()
    rel_names = {p.relative_to(REPO_ROOT).as_posix() for p in files}

    weekly_hits = [
        n for n in rel_names
        if n.startswith("docs/weekly_progress_report_") and n.endswith(".md")
    ]
    assert weekly_hits, (
        "v0.13 scope must include ≥1 docs/weekly_progress_report_*.md; "
        f"got {sorted(rel_names)}"
    )
    competitive_hits = [
        n for n in rel_names
        if n.startswith("docs/competitive_analysis_") and n.endswith(".md")
    ]
    assert competitive_hits, (
        "v0.13 scope must include ≥1 docs/competitive_analysis_*.md; "
        f"got {sorted(rel_names)}"
    )
    research_hits = [
        n for n in rel_names if n.startswith(".omc/research/") and n.endswith(".md")
    ]
    assert research_hits, (
        "v0.13 scope must include ≥1 .omc/research/*.md; "
        f"got {sorted(rel_names)}"
    )


def test_lint_tense_v0_13_release_notes_exclusion_rotated() -> None:
    """v0.13 ship time: the current-version release-notes exclusion constant
    MUST rotate to `RELEASE_NOTES_v0.13.0.md` per ADR 0020 §Reverse-criterion
    item 4 (asymmetry-rotation requirement) and v0.11 §Reverse-criterion
    item 4.

    Guards against the v0.12 → v0.13 rotation being forgotten at release
    time (the asymmetry stays correct only if executor remembers to rotate).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("lint_tense", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.CURRENT_VERSION_RELEASE_NOTES == "RELEASE_NOTES_v0.13.0.md", (
        "v0.13 ship: CURRENT_VERSION_RELEASE_NOTES must rotate to "
        "RELEASE_NOTES_v0.13.0.md per ADR 0020 §Reverse-criterion item 4; "
        f"got {module.CURRENT_VERSION_RELEASE_NOTES}"
    )
