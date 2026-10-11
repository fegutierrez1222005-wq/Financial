"""FINAGENT LAB shared domain core.

Intentionally free of web framework, ORM and broker dependencies so the research engines can
be unit tested without infrastructure.
"""

from finagent_core.cutoff import AsOfContext, LookAheadViolation
from finagent_core.errors import (
    ErrorCode,
    FinagentError,
    ProviderUnavailableError,
    SandboxDeniedError,
    ValidationFailedError,
)
from finagent_core.logging import bind_context, configure_logging, get_logger, log_context

__all__ = [
    "AsOfContext",
    "ErrorCode",
    "FinagentError",
    "LookAheadViolation",
    "ProviderUnavailableError",
    "SandboxDeniedError",
    "ValidationFailedError",
    "bind_context",
    "configure_logging",
    "get_logger",
    "log_context",
]

__version__ = "0.1.0"
