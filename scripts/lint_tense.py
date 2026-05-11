#!/usr/bin/env python
"""README/ADR/RELEASE_NOTES present-tense version-specific framing lint (ADR 0020).

Scope: tests/fixtures/**/README.md, docs/adr/*.md, RELEASE_NOTES_v*.md
(excluding current-version RELEASE_NOTES_v0.11.0.md — asymmetry per ADR 0020).
Pattern (word-bounded): \\bwe ship\\b | \\bship in v0\\.[0-9]+\\b.
Block exclusion (D22): lines inside `## §Status-update-` /
`## §Honesty-correction-` blocks. Per-line escape: `# noqa: lint-tense`.
Exit 0 = clean; 1 = matches printed; 2 = IO error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Excluded from scope: the current-version release notes (inherently present tense).
CURRENT_VERSION_RELEASE_NOTES = "RELEASE_NOTES_v0.11.0.md"

# Lint pattern + block-exclusion anchors (referenced from ADR 0020 §Decision).
LINT_PATTERN = re.compile(r"\bwe ship\b|\bship in v0\.[0-9]+\b", re.IGNORECASE)
EXCLUSION_BLOCK_HEADERS = ("## §Status-update-", "## §Honesty-correction-")
NOQA_MARKER = re.compile(r"#\s*noqa:\s*lint-tense", re.IGNORECASE)


def _scoped_files() -> list[Path]:
    """Collect the v0.11 lint scope (fixture README + ADR + past RELEASE_NOTES)."""
    files: list[Path] = []
    files.extend(sorted((REPO_ROOT / "tests" / "fixtures").rglob("README.md")))
    files.extend(sorted((REPO_ROOT / "docs" / "adr").glob("*.md")))
    for path in sorted(REPO_ROOT.glob("RELEASE_NOTES_v*.md")):
        if path.name == CURRENT_VERSION_RELEASE_NOTES:
            continue
        files.append(path)
    return files


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return [(line_no, line_text), ...] for matches outside excluded blocks."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"lint_tense: cannot read {path}: {exc}", file=sys.stderr)
        return []
    inside_exclusion = False
    matches: list[tuple[int, str]] = []
    for idx, raw in enumerate(lines, start=1):
        # Block-exclusion state machine: enter on `## §Status-update-` or
        # `## §Honesty-correction-`; exit on the next `## ` or `# ` header.
        stripped = raw.lstrip()
        if stripped.startswith(EXCLUSION_BLOCK_HEADERS):
            inside_exclusion = True
            continue
        if inside_exclusion and (stripped.startswith("## ") or stripped.startswith("# ")):
            inside_exclusion = False
        if inside_exclusion:
            continue
        if NOQA_MARKER.search(raw):
            continue
        if LINT_PATTERN.search(raw):
            matches.append((idx, raw.rstrip()))
    return matches


def main() -> int:
    """Walk scope; print matches; return 0 (clean) or 1 (failures)."""
    if not REPO_ROOT.exists():
        print(f"lint_tense: repo root {REPO_ROOT} not found", file=sys.stderr)
        return 2
    failed = 0
    for path in _scoped_files():
        for line_no, text in _scan_file(path):
            rel = path.relative_to(REPO_ROOT)
            print(f"{rel}:{line_no}: {text}")
            failed += 1
    if failed:
        print(f"lint_tense: {failed} present-tense version-specific match(es) flagged.")
        print("Rewrite in past tense, or append `# noqa: lint-tense` with rationale.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
