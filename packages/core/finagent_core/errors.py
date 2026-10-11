"""Platform error taxonomy.

Every failure surfaced to a user is one of these codes. The HTTP layer maps codes to safe,
actionable messages; raw exception text is logged, never returned.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    # Client / validation
    VALIDATION_FAILED = "VALIDATION_FAILED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

    # Providers
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"

    # Data / documents
    DOCUMENT_PARSE_FAILED = "DOCUMENT_PARSE_FAILED"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    DATASET_INVALID = "DATASET_INVALID"

    # Agent execution
    AGENT_TIMEOUT = "AGENT_TIMEOUT"
    AGENT_STEP_LIMIT = "AGENT_STEP_LIMIT"
    AGENT_FAILED = "AGENT_FAILED"
    TOOL_NOT_PERMITTED = "TOOL_NOT_PERMITTED"
    TOOL_FAILED = "TOOL_FAILED"
    SANDBOX_DENIED = "SANDBOX_DENIED"
    SANDBOX_TIMEOUT = "SANDBOX_TIMEOUT"

    # Research integrity
    LOOK_AHEAD_VIOLATION = "LOOK_AHEAD_VIOLATION"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    BACKTEST_INVALID = "BACKTEST_INVALID"

    # Infrastructure
    INTERNAL_ERROR = "INTERNAL_ERROR"


#: Human-readable, non-leaking messages for every code.
USER_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.VALIDATION_FAILED: "The request contained invalid values.",
    ErrorCode.NOT_FOUND: "The requested resource was not found.",
    ErrorCode.CONFLICT: "The resource already exists or is in a conflicting state.",
    ErrorCode.UNAUTHENTICATED: "Authentication is required.",
    ErrorCode.FORBIDDEN: "You do not have permission to perform this action.",
    ErrorCode.RATE_LIMITED: "Rate limit exceeded. Please retry shortly.",
    ErrorCode.QUOTA_EXCEEDED: "Your plan quota for this resource has been reached.",
    ErrorCode.PROVIDER_UNAVAILABLE: (
        "Data provider unavailable. Configure credentials or select another provider."
    ),
    ErrorCode.PROVIDER_ERROR: "The upstream provider returned an error.",
    ErrorCode.MODEL_UNAVAILABLE: "Model provider unavailable. Add an API key in Settings → Security.",
    ErrorCode.DOCUMENT_PARSE_FAILED: "Document could not be parsed.",
    ErrorCode.UNSUPPORTED_FILE_TYPE: "Unsupported file type.",
    ErrorCode.FILE_TOO_LARGE: "The file exceeds the maximum allowed size.",
    ErrorCode.DATASET_INVALID: "The dataset failed validation.",
    ErrorCode.AGENT_TIMEOUT: "Agent exceeded execution time.",
    ErrorCode.AGENT_STEP_LIMIT: "Agent exceeded its configured step limit.",
    ErrorCode.AGENT_FAILED: "The agent run failed.",
    ErrorCode.TOOL_NOT_PERMITTED: "The agent attempted to use a tool it is not permitted to use.",
    ErrorCode.TOOL_FAILED: "A tool call failed.",
    ErrorCode.SANDBOX_DENIED: "The sandbox rejected this code.",
    ErrorCode.SANDBOX_TIMEOUT: "Code execution exceeded the sandbox time limit.",
    ErrorCode.LOOK_AHEAD_VIOLATION: (
        "Look-ahead violation: information published after the information cutoff was requested."
    ),
    ErrorCode.EVALUATION_FAILED: "Evaluation could not be completed.",
    ErrorCode.BACKTEST_INVALID: "The backtest configuration is invalid and cannot be trusted.",
    ErrorCode.INTERNAL_ERROR: "An unexpected error occurred. The incident has been logged.",
}


class FinagentError(Exception):
    """Base class for all platform errors."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    retryable: bool = False

    def __init__(
        self,
        message: str | None = None,
        *,
        code: ErrorCode | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
    ) -> None:
        self.code = code or self.code
        self.details = details or {}
        if retryable is not None:
            self.retryable = retryable
        self.internal_message = message or self.code.value
        super().__init__(self.internal_message)

    @property
    def user_message(self) -> str:
        return USER_MESSAGES.get(self.code, USER_MESSAGES[ErrorCode.INTERNAL_ERROR])

    def to_payload(self) -> dict[str, Any]:
        """Safe representation for API responses (never the internal message)."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.user_message,
                "retryable": self.retryable,
                "details": self.details,
            }
        }


class ValidationFailedError(FinagentError):
    code = ErrorCode.VALIDATION_FAILED


class NotFoundError(FinagentError):
    code = ErrorCode.NOT_FOUND


class ConflictError(FinagentError):
    code = ErrorCode.CONFLICT


class UnauthenticatedError(FinagentError):
    code = ErrorCode.UNAUTHENTICATED


class ForbiddenError(FinagentError):
    code = ErrorCode.FORBIDDEN


class RateLimitedError(FinagentError):
    code = ErrorCode.RATE_LIMITED
    retryable = True


class QuotaExceededError(FinagentError):
    code = ErrorCode.QUOTA_EXCEEDED


class ProviderUnavailableError(FinagentError):
    code = ErrorCode.PROVIDER_UNAVAILABLE


class ProviderError(FinagentError):
    code = ErrorCode.PROVIDER_ERROR
    retryable = True


class ModelUnavailableError(FinagentError):
    code = ErrorCode.MODEL_UNAVAILABLE


class DocumentParseError(FinagentError):
    code = ErrorCode.DOCUMENT_PARSE_FAILED


class UnsupportedFileTypeError(FinagentError):
    code = ErrorCode.UNSUPPORTED_FILE_TYPE


class FileTooLargeError(FinagentError):
    code = ErrorCode.FILE_TOO_LARGE


class DatasetInvalidError(FinagentError):
    code = ErrorCode.DATASET_INVALID


class AgentTimeoutError(FinagentError):
    code = ErrorCode.AGENT_TIMEOUT
    retryable = True


class AgentStepLimitError(FinagentError):
    code = ErrorCode.AGENT_STEP_LIMIT


class AgentFailedError(FinagentError):
    code = ErrorCode.AGENT_FAILED
    retryable = True


class ToolNotPermittedError(FinagentError):
    code = ErrorCode.TOOL_NOT_PERMITTED


class ToolFailedError(FinagentError):
    code = ErrorCode.TOOL_FAILED


class SandboxDeniedError(FinagentError):
    code = ErrorCode.SANDBOX_DENIED


class SandboxTimeoutError(FinagentError):
    code = ErrorCode.SANDBOX_TIMEOUT


class EvaluationFailedError(FinagentError):
    code = ErrorCode.EVALUATION_FAILED
    retryable = True


class BacktestInvalidError(FinagentError):
    code = ErrorCode.BACKTEST_INVALID
