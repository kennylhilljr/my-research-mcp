"""Immutable source policies, with no transport or credential access."""

from collections.abc import Callable
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field
from pydantic.dataclasses import dataclass

from research_mcp.core.errors import ErrorCode


@dataclass(frozen=True)
class AuthSpec:
    secrets: tuple[str, ...]
    required: bool
    placement: Literal["header", "query", "bearer"]
    param: str
    origins: tuple[str, ...]
    signup_url: str
    validation: Literal["probe", "github_rate_limit", "header_expiry", "none"] = "probe"

    def __post_init__(self) -> None:
        if not self.origins:
            raise ValueError("At least one credential origin is required")
        for origin in self.origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or any(char.isspace() for char in origin)
                or "*" in origin
                or origin != f"{parsed.scheme}://{parsed.netloc}"
            ):
                raise ValueError("Credential origins must be scheme://host[:port]")
            # Accessing port also rejects malformed and out-of-range ports.
            if parsed.port == 0 or parsed.netloc.endswith(":"):
                raise ValueError("Credential origin port must be positive")


@dataclass(frozen=True)
class RateSpec:
    rps: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    burst: Annotated[int, Field(ge=1)] = 1
    concurrency: Annotated[int, Field(ge=1)] = 2
    daily_quota: Annotated[int, Field(ge=1)] | None = None


@dataclass(frozen=True)
class ProbeSpec:
    cadence_s: Annotated[int, Field(gt=0)]
    cost: Literal["free", "metered"]
    description: str


ErrorClassifier = Callable[[int, bytes], tuple[ErrorCode, str | None] | None]


@dataclass(frozen=True)
class SourcePolicy:
    source: Annotated[str, Field(min_length=1)]
    hosts: frozenset[str]
    auth: AuthSpec | None
    rate: RateSpec
    timeout_s: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    max_bytes: Annotated[int, Field(gt=0)]
    error_classifier: ErrorClassifier | None = None

    def __post_init__(self) -> None:
        if not self.hosts or any(
            not host
            or any(c in host for c in "/:@*?#")
            or any(c.isspace() for c in host)
            for host in self.hosts
        ):
            raise ValueError("Policy hosts must be nonempty host names")
        if self.auth and any(
            urlsplit(origin).hostname not in {host.lower() for host in self.hosts}
            for origin in self.auth.origins
        ):
            raise ValueError("Credential origins must belong to policy hosts")
