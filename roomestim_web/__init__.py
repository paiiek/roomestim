"""roomestim web demo — parallel-track v0.12-web.0 (sibling package)."""
from __future__ import annotations

__version__ = "0.12-web.0"

try:
    from roomestim import __schema_version__
except (ImportError, AttributeError):
    __schema_version__ = "unknown"

__all__ = ["__version__", "__schema_version__"]
