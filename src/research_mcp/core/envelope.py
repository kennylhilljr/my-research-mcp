"""Typed tool output and labels for externally fetched content."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

from research_mcp.core.errors import ErrorCode

T = TypeVar("T")


class SourceStatus(BaseModel):
    source: str
    state: Literal[
        "ok",
        "empty",
        "timeout",
        "rate_limited",
        "error",
        "unconfigured",
        "disabled",
        "skipped_unhealthy",
        "skipped_budget",
    ]
    count: int = Field(default=0, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    retry_after_ms: int | None = Field(default=None, ge=0)
    error_code: ErrorCode | None = None


class Untrusted(BaseModel):
    untrusted: Literal[True] = True
    source: str
    content: str


class ToolResult(BaseModel, Generic[T]):
    data: T
    source_status: list[SourceStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_cursor: str | None = None
    truncated: bool = False
