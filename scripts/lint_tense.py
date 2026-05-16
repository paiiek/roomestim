#!/usr/bin/env python
"""README/ADR/RELEASE_NOTES present-tense version-specific framing lint (ADR 0020).

Scope (v0.13+ — second expansion per ADR 0020 §Status-update-2026-05-MM-2;
governed by D28-P1 supersedure clause for factual-scope-list-growth):
  - tests/fixtures/**/README.md
  - docs/adr/*.md
  - RELEASE_NOTES_v*.md (excluding current-version RELEASE_NOTES_v0.14.0.md — asymmetry per ADR 0020)
  - docs/perf_verification_*.md (added v0.12 per ADR 0020 §Status-update-2026-05-12)
  - docs/architecture.md (added v0.12 per ADR 0020 §Status-update-2026-05-12)
  - README.md (added v0.12 per ADR 0020 §Status-update-2026-05-12)
  - docs/*.md remaining (non-adr, non-perf_verification_*, non-architecture):
    ace_geometry_audit_*.md, competitive_analysis_*.md,
    protocol_a10b_*.md, room_yaml_spec.md, weekly_progress_report_*.md
    (added v0.13 per ADR 0020 §Status-update-2026-05-MM-2; effectively
    "all docs/*.md" — adr/perf/architecture/protocol_a10b absorb into the
    same docs/*.md glob now).
  - .omc/research/*.md (added v0.13 per ADR 0020 §Status-update-2026-05-MM-2)
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
# Rotated v0.13.0 → v0.14.0 per ADR 0020 §Reverse-criterion item 4 (rotation requirement).
CURRENT_VERSION_RELEASE_NOTES = "RELEASE_NOTES_v0.14.0.md"

# Lint pattern + block-exclusion anchors (referenced from ADR 0020 §Decision).
LINT_PATTERN = re.compile(r"\bwe ship\b|\bship in v0\.[0-9]+\b", re.IGNORECASE)
EXCLUSION_BLOCK_HEADERS = ("## §Status-update-", "## §Honesty-correction-")
NOQA_MARKER = re.compile(r"#\s*noqa:\s*lint-tense", re.IGNORECASE)


def _scoped_files() -> list[Path]:
    """Collect the v0.13 lint scope (factual-scope-list-growth-2 per ADR 0020
    §Status-update-2026-05-MM-2; D28-P1 supersedure clause applies).

    v0.11 scope: fixture README + ADR + past RELEASE_NOTES.
    v0.12 added: docs/perf_verification_*.md, docs/architecture.md, README.md
    per ADR 0020 §Status-update-2026-05-12.
    v0.13 adds: the remaining docs/*.md (non-adr / non-perf / non-architecture:
    ace_geometry_audit_*.md, competitive_analysis_*.md,
    protocol_a10b_insitu_capture.md, room_yaml_spec.md,
    weekly_progress_report_*.md) + .omc/research/*.md per ADR 0020
    §Status-update-2026-05-MM-2. Pattern + block-exclusion + per-line-escape
    + current-version-exclusion mechanism BYTE-EQUAL — only the
    factual-list-of-covered-files grows (D28-P1 governs; D24 reverse-trigger
    item 3's "successor ADR" wording is SUPERSEDED for the
    factual-scope-list-growth case).
    """
    files: list[Path] = []
    files.extend(sorted((REPO_ROOT / "tests" / "fixtures").rglob("README.md")))
    files.extend(sorted((REPO_ROOT / "docs" / "adr").glob("*.md")))
    for path in sorted(REPO_ROOT.glob("RELEASE_NOTES_v*.md")):
        if path.name == CURRENT_VERSION_RELEASE_NOTES:
            continue
        files.append(path)
    readme = REPO_ROOT / "README.md"
    if readme.exists():
        files.append(readme)
    # v0.13 scope expansion-2: take the union of all top-level docs/*.md
    # files (non-recursive — docs/adr/ subdir is handled separately above).
    # This absorbs the v0.12 perf_verification_*.md + architecture.md families
    # and adds the v0.13 remainder (ace_geometry_audit_*.md,
    # competitive_analysis_*.md, protocol_a10b_*.md, room_yaml_spec.md,
    # weekly_progress_report_*.md). Deduplicated by Path identity.
    docs_top = sorted((REPO_ROOT / "docs").glob("*.md"))
    seen = {p.resolve() for p in files}
    for p in docs_top:
        if p.resolve() not in seen:
            files.append(p)
            seen.add(p.resolve())
    # v0.13: .omc/research/*.md — narrative research notes carry the same
    # honesty-leak risk as docs/*. Revert this clause if first-run flags
    # > 3 files in .omc/research/ (per v0.13-design §0.0 Item D row).
    research_dir = REPO_ROOT / ".omc" / "research"
    if research_dir.exists():
        for p in sorted(research_dir.glob("*.md")):
            if p.resolve() not in seen:
                files.append(p)
                seen.add(p.resolve())
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
