"""pytest configuration shared across roomestim test modules."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Disable background auto-fetch in all tests to prevent network requests.
os.environ.setdefault("ROOMESTIM_WEB_AUTO_FETCH", "0")

# Engine-schema resolution for tests that exercise the default (validate=True)
# writer path. roomestim NO LONGER hardcodes a machine-specific default engine
# schema path (Candidate A / ADR 0007 §Status-update): _engine_schema_path()
# resolves SPATIAL_ENGINE_REPO_DIR only. Discover the sibling spatial_engine
# repo RELATIVE to this repo (not a machine-specific literal) so the canonical
# gate stays GREEN wherever the two repos are checked out side-by-side, and
# fails loud cleanly otherwise. `setdefault` respects an explicit env override.
_SIBLING_ENGINE_DIR = REPO_ROOT.parent / "spatial_engine"
if (_SIBLING_ENGINE_DIR / "proto" / "geometry_schema.json").is_file():
    os.environ.setdefault("SPATIAL_ENGINE_REPO_DIR", str(_SIBLING_ENGINE_DIR))
