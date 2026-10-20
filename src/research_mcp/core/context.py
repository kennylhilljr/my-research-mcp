"""Request context shared by the transport and platform layers."""

from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
