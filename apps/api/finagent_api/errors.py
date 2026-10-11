"""HTTP error handling.

Raw exceptions never reach a client. Every response carries the platform error code, a safe
message, whether a retry may help, and the request id so support can find the log line.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from finagent_core.errors import ErrorCode, FinagentError
from finagent_core.logging import get_logger

logger = get_logger(__name__)

STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.QUOTA_EXCEEDED: 402,
    ErrorCode.PROVIDER_UNAVAILABLE: 503,
    ErrorCode.PROVIDER_ERROR: 502,
    ErrorCode.MODEL_UNAVAILABLE: 503,
    ErrorCode.DOCUMENT_PARSE_FAILED: 422,
    ErrorCode.UNSUPPORTED_FILE_TYPE: 415,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.DATASET_INVALID: 422,
    ErrorCode.AGENT_TIMEOUT: 504,
    ErrorCode.AGENT_STEP_LIMIT: 422,
    ErrorCode.AGENT_FAILED: 500,
    ErrorCode.TOOL_NOT_PERMITTED: 403,
    ErrorCode.TOOL_FAILED: 500,
    ErrorCode.SANDBOX_DENIED: 400,
    ErrorCode.SANDBOX_TIMEOUT: 504,
    ErrorCode.LOOK_AHEAD_VIOLATION: 409,
    ErrorCode.EVALUATION_FAILED: 500,
    ErrorCode.BACKTEST_INVALID: 422,
    ErrorCode.INTERNAL_ERROR: 500,
}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(FinagentError)
    async def _finagent_error(request: Request, exc: FinagentError) -> JSONResponse:
        status = STATUS_BY_CODE.get(exc.code, 500)
        log = logger.warning if status < 500 else logger.error
        log(
            "request_failed",
            extra={
                "error_code": exc.code.value,
                "status": status,
                "path": request.url.path,
                "internal_message": exc.internal_message,
            },
        )
        body = exc.to_payload()
        body["error"]["request_id"] = _request_id(request)
        return JSONResponse(status_code=status, content=body)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {
                "field": ".".join(str(part) for part in error.get("loc", [])[1:]) or "body",
                "message": error.get("msg", "invalid value"),
            }
            for error in exc.errors()[:20]
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.VALIDATION_FAILED.value,
                    "message": "The request contained invalid values.",
                    "retryable": False,
                    "details": {"fields": fields},
                    "request_id": _request_id(request),
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: ErrorCode.UNAUTHENTICATED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            405: ErrorCode.VALIDATION_FAILED,
            409: ErrorCode.CONFLICT,
            413: ErrorCode.FILE_TOO_LARGE,
            415: ErrorCode.UNSUPPORTED_FILE_TYPE,
            429: ErrorCode.RATE_LIMITED,
        }.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code.value,
                    "message": exc.detail if isinstance(exc.detail, str) else "Request failed.",
                    "retryable": exc.status_code in (429, 502, 503, 504),
                    "details": {},
                    "request_id": _request_id(request),
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # A FastAPI handler runs outside the `except` block, so `sys.exc_info()` may be
        # empty here. Passing the exception explicitly is what keeps the traceback in the
        # log — without it the response would promise an incident record that has no
        # stack trace in it.
        logger.error(
            "unhandled_exception",
            exc_info=exc,
            extra={"path": request.url.path, "exception_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": "An unexpected error occurred. The incident has been logged.",
                    "retryable": True,
                    "details": {},
                    "request_id": _request_id(request),
                }
            },
        )
