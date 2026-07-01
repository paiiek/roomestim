"""roomestim_server.errors — generic-message + stable error-code mapping.

ADR 0038 / OQ-45 (mirrored at the HTTP boundary): the server logs the REAL
exception text server-side; the client only ever receives a GENERIC message and a
STABLE error code — never a stack trace, internal path, or raw ``ValueError``
text. This module owns the generic strings + the :class:`EvaluateError` that the
service raises for the client-attributable 400 path.

Pure-Python (no fastapi / pydantic import) so it stays on the right side of the
``[server]`` extra boundary and is unit-testable without the web stack.
"""

from __future__ import annotations

__all__ = [
    "EvaluateError",
    "GENERIC_INVALID_REQUEST_MESSAGE",
    "GENERIC_INTERNAL_MESSAGE",
    "GENERIC_ROOM_NOT_FOUND_MESSAGE",
    "GENERIC_VALIDATION_MESSAGE",
    "MISSING_SERVER_EXTRA_MESSAGE",
]

#: Friendly message raised when the ``[server]`` extra (fastapi/uvicorn) is absent.
MISSING_SERVER_EXTRA_MESSAGE = (
    "install roomestim[server]: pip install 'roomestim[server]'"
)

#: Generic 400 message — client-attributable evaluation failure. KR + EN, NO
#: internals (mirrors roomestim_web/immersive_design.py's Korean generic string).
GENERIC_INVALID_REQUEST_MESSAGE = (
    "요청을 평가할 수 없습니다. 입력 값을 확인하세요. "
    "(The layout could not be evaluated; check the inputs.)"
)

#: Generic 500 message — unexpected server error. NEVER includes stack/path.
GENERIC_INTERNAL_MESSAGE = (
    "내부 오류가 발생했습니다. 서버 로그를 확인하세요. "
    "(An internal error occurred; see the server logs.)"
)

#: Generic 404 message — unknown room id on ``GET /api/rooms/{id}``.
GENERIC_ROOM_NOT_FOUND_MESSAGE = "룸을 찾을 수 없습니다. (Room not found.)"

#: Generic 422 message — malformed request body (field-level ``fields`` list is
#: safe to return, but the message stays generic). KR + EN, NO internals.
GENERIC_VALIDATION_MESSAGE = (
    "요청 형식이 올바르지 않습니다. (The request body is malformed.)"
)


class EvaluateError(Exception):
    """A client-attributable evaluation failure mapped to a 400 envelope.

    Carries a STABLE ``code`` + a GENERIC ``message`` (no internals). The service
    raises this after logging the real cause server-side; the app's exception
    handler renders ``{"ok": false, "error": {"code": ..., "message": ...}}``.
    """

    def __init__(
        self,
        message: str = GENERIC_INVALID_REQUEST_MESSAGE,
        *,
        code: str = "INVALID_REQUEST",
    ) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
