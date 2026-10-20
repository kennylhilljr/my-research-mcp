"""Stable, public error types. Messages must be safe for client output."""

from enum import StrEnum

from research_mcp.core.context import correlation_id as current_correlation_id


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "invalid_argument"
    NOT_FOUND = "not_found"
    UNCONFIGURED = "unconfigured"
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
    UPSTREAM_ERROR = "upstream_error"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TOO_LARGE = "too_large"
    BLOCKED_BY_POLICY = "blocked_by_policy"
    DISABLED = "disabled"
    EXTRACT_FAILED = "extract_failed"
    INTERNAL = "internal"


class ToolError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        retryable: bool = False,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = ErrorCode(code)
        self.message = message
        self.retryable = retryable
        self.correlation_id = (
            current_correlation_id.get() if correlation_id is None else correlation_id
        )


class HttpError(ToolError):
    """Classified HTTP failure without raw upstream bodies or URLs."""

    def __init__(
        self,
        code: ErrorCode,
        status: int | None = None,
        retry_after_ms: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(
            code,
            "Upstream request failed",
            retryable=code
            in {
                ErrorCode.RATE_LIMITED,
                ErrorCode.UPSTREAM_ERROR,
                ErrorCode.UPSTREAM_TIMEOUT,
            },
        )
        self.status = status
        self.retry_after_ms = retry_after_ms
        self.detail = detail
