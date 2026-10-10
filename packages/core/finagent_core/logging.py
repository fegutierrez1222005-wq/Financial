"""Structured JSON logging with correlation-id context.

Correlation ids (`request_id`, `run_id`, `evaluation_id`, tenancy ids) live in a
`contextvars` map, so any record emitted downstream — including from the pure engines — is
attributable to a request or a run without threading loggers through every API.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import time
from collections.abc import Iterator
from contextvars import ContextVar
from typing import Any

_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("finagent_log_context", default={})

_RESERVED = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName", "levelname",
    "levelno", "lineno", "module", "msecs", "message", "msg", "name", "pathname", "process",
    "processName", "relativeCreated", "stack_info", "taskName", "thread", "threadName",
}

#: Keys whose values are never written to logs, even if a caller passes them.
SENSITIVE_KEYS = {
    "password", "password_hash", "api_key", "apikey", "secret", "token", "refresh_token",
    "access_token", "authorization", "mfa_secret", "private_key", "plaintext_key",
}


def redact(payload: Any) -> Any:
    """Recursively replace sensitive values with ``"[REDACTED]"``."""
    if isinstance(payload, dict):
        return {
            key: ("[REDACTED]" if key.lower() in SENSITIVE_KEYS else redact(value))
            for key, value in payload.items()
        }
    if isinstance(payload, (list, tuple)):
        return [redact(item) for item in payload]
    return payload


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: A003 - stdlib signature
        base: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        base.update(redact(_LOG_CONTEXT.get()))
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED and not key.startswith("_")
        }
        if extras:
            base.update(redact(extras))
        if record.exc_info:
            base["exception"] = self.formatException(record.exc_info)
        return json.dumps(base, default=str)


class _SafeExtraLogger(logging.Logger):
    """Logger that cannot be crashed by a structured field name.

    ``Logger.makeRecord`` raises ``KeyError`` when ``extra`` contains a key that collides
    with a ``LogRecord`` attribute — ``filename`` and ``module`` are the easy ones to hit
    when logging about documents. A logging call must never be able to fail the operation
    it is describing, so colliding keys are prefixed rather than rejected.
    """

    def makeRecord(  # noqa: PLR0913 - stdlib signature
        self,
        name,  # noqa: ANN001
        level,  # noqa: ANN001
        fn,  # noqa: ANN001
        lno,  # noqa: ANN001
        msg,  # noqa: ANN001
        args,  # noqa: ANN001
        exc_info,  # noqa: ANN001
        func=None,  # noqa: ANN001
        extra=None,  # noqa: ANN001
        sinfo=None,  # noqa: ANN001
    ) -> logging.LogRecord:
        if extra:
            extra = {
                (f"extra_{key}" if key in _RESERVED else key): value
                for key, value in extra.items()
            }
        return super().makeRecord(name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)


logging.setLoggerClass(_SafeExtraLogger)


def configure_logging(level: str | None = None, *, json_output: bool | None = None) -> None:
    """Install the formatter on the root logger. Idempotent."""
    resolved_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    use_json = json_output if json_output is not None else os.getenv("LOG_FORMAT", "json") == "json"

    root = logging.getLogger()
    root.setLevel(resolved_level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if use_json
        else logging.Formatter("%(asctime)s %(levelname)-8s %(name)s %(message)s")
    )
    root.addHandler(handler)
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio", "multipart"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def bind_context(**values: Any) -> None:
    """Merge values into the ambient log context."""
    current = dict(_LOG_CONTEXT.get())
    current.update({key: value for key, value in values.items() if value is not None})
    _LOG_CONTEXT.set(current)


def current_context() -> dict[str, Any]:
    return dict(_LOG_CONTEXT.get())


@contextlib.contextmanager
def log_context(**values: Any) -> Iterator[None]:
    """Scoped binding; restores the previous context on exit."""
    token = _LOG_CONTEXT.set(
        {**_LOG_CONTEXT.get(), **{key: value for key, value in values.items() if value is not None}}
    )
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)
