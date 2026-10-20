"""Shared data contracts; defer validators to keep imports free of environment reads."""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Protocol, Self

from pydantic import BaseModel, Field, JsonValue, model_validator

from research_mcp.core.envelope import SourceStatus
from research_mcp.core.ids import Identifier as Identifier

__all__ = [
    "Author",
    "AuthUse",
    "CallRecord",
    "CitationPage",
    "Clock",
    "Conflict",
    "DownloadedFile",
    "FederatedResult",
    "FulltextCandidate",
    "Identifier",
    "JsonValue",
    "OaLocation",
    "ProbeResult",
    "Provenance",
    "SearchFilters",
    "SearchPage",
    "SearchRequest",
    "Sleeper",
    "TextResponse",
    "Work",
    "WorkRecord",
]


class Clock(Protocol):
    def now(self) -> datetime:
        """Return an aware UTC timestamp."""
        ...


class Sleeper(Protocol):
    async def sleep(self, seconds: float) -> None: ...


class AuthUse(StrEnum):
    SPEC = "spec"
    NONE = "none"


class Author(BaseModel, defer_build=True):
    name: str
    family: str | None = None
    orcid: str | None = None


class OaLocation(BaseModel, defer_build=True):
    url: str
    source: str
    kind: Literal["pdf", "html", "landing"]
    license: str | None = None
    version: str | None = None


class Provenance(BaseModel, defer_build=True):
    source: str
    upstream_id: str
    adapter_version: str
    retrieved_at: datetime


class WorkRecord(BaseModel, defer_build=True):
    ids: list[Identifier]
    title: str
    authors: list[Author] = Field(default_factory=list)
    year: int | None = None
    published_at: date | None = None
    venue: str | None = None
    work_type: str = "article"
    abstract: str | None = None
    oa_locations: list[OaLocation] = Field(default_factory=list)
    is_retracted: bool | None = None
    extra: dict[str, JsonValue] = Field(default_factory=dict)
    provenance: Provenance


class SearchFilters(BaseModel, defer_build=True):
    year_from: int | None = Field(default=None, ge=1800, le=2100)
    year_to: int | None = Field(default=None, ge=1800, le=2100)
    work_type: str | None = None
    oa_only: bool = False
    provider: str | None = None
    repository: str | None = None

    @model_validator(mode="after")
    def ordered_years(self) -> Self:
        if (
            self.year_from is not None
            and self.year_to is not None
            and self.year_from > self.year_to
        ):
            raise ValueError("year_from must not exceed year_to")
        return self


class SearchRequest(BaseModel, defer_build=True):
    query: str = Field(min_length=1, max_length=500)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=10, ge=1, le=25)
    cursor: str | None = None


class SearchPage(BaseModel, defer_build=True):
    records: list[WorkRecord]
    total: int | None = Field(default=None, ge=0)
    next_cursor: str | None = None


class FulltextCandidate(BaseModel, defer_build=True):
    location: OaLocation
    priority: int


class CitationPage(BaseModel, defer_build=True):
    ids: list[Identifier]
    records: list[WorkRecord] = Field(default_factory=list)
    next_cursor: str | None = None


class ProbeResult(BaseModel, defer_build=True):
    ok: bool
    latency_ms: int = Field(ge=0)
    shape_ok: bool
    detail_code: str | None = None
    quota_remaining: str | None = None
    credential_expires_at: datetime | None = None


class Conflict(BaseModel, defer_build=True):
    field: str
    values: dict[str, JsonValue]


class Work(BaseModel, defer_build=True):
    work_id: str | None = None
    ids: list[Identifier]
    title: str
    authors: list[Author]
    year: int | None
    venue: str | None
    work_type: str
    abstract: str | None
    oa_locations: list[OaLocation]
    found_in: list[str]
    fuzzy: bool = False
    conflicts: list[Conflict] = Field(default_factory=list)
    integrity_status: str = "unknown"
    cache_state: str = "none"


class FederatedResult(BaseModel, defer_build=True):
    works: list[Work]
    statuses: list[SourceStatus]
    next_cursor: str | None


class TextResponse(BaseModel, defer_build=True):
    url: str
    status: int = Field(ge=100, le=599)
    content_type: str
    text: str


class DownloadedFile(BaseModel, defer_build=True):
    sha256: str
    size: int = Field(ge=0)
    media_type: str
    storage_path: str
    final_url: str
    http_status: int = Field(ge=100, le=599)
    etag: str | None
    last_modified: str | None


class CallRecord(BaseModel, defer_build=True):
    ts: datetime
    source: str
    op: str
    status: int | None = Field(ge=100, le=599)
    error_code: str | None
    latency_ms: int = Field(ge=0)
    bytes: int = Field(ge=0)
    rl_remaining: str | None
    rl_reset: str | None
    cred_expires_at: str | None
    correlation_id: str | None
    attempt: int = Field(ge=1)
