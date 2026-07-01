"""roomestim_server — optional FastAPI server over the frozen trade-off engine.

This package is gated behind the ``[server]`` extra (fastapi / uvicorn). Importing
the PACKAGE itself is cheap and dependency-free — fastapi is pulled in ONLY when
:func:`create_app` is actually called, via a lazy import of
:mod:`roomestim_server.app`. So ``import roomestim`` (core) and
``import roomestim_server`` both stay fastapi-free; only constructing the app
requires the extra. If fastapi is absent, :func:`create_app` raises a clear
``ImportError`` telling the user to install ``roomestim[server]``.

See ADR 0061 and ``.omc/plans/immersive-layout-p5-fastapi-threejs.md`` (P5.1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from roomestim_server.errors import MISSING_SERVER_EXTRA_MESSAGE

if TYPE_CHECKING:  # import only for type-checkers; never at runtime import time.
    from fastapi import FastAPI

__all__ = ["create_app"]


def create_app() -> "FastAPI":
    """Build the FastAPI app, importing fastapi lazily.

    Raises a friendly ``ImportError`` (``install roomestim[server]``) if the
    ``[server]`` extra is not installed.
    """
    try:
        from roomestim_server.app import create_app as _factory
    except ImportError as exc:
        try:
            import fastapi  # noqa: F401  # probe: is the [server] extra truly missing?
        except ImportError:
            raise ImportError(MISSING_SERVER_EXTRA_MESSAGE) from exc
        raise  # fastapi present → unrelated import error; surface it, don't mask
    return _factory()
