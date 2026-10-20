import asyncio
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from research_mcp.core.specs import AuthSpec, ProbeSpec, RateSpec, SourcePolicy
from research_mcp.core.timeutil import AsyncSleeper, SystemClock
from research_mcp.testing.clock import FakeClock, FakeSleeper


def auth(origin="https://api.example.test"):
    return AuthSpec(
        ("TEST_KEY",), True, "header", "X-Key", (origin,), "https://example.test"
    )


def test_policy_validation_and_immutability():
    """AT-PLAT-06: Policies validate rates, bounds, credential origins and enums."""
    policy = SourcePolicy(
        "test", frozenset({"api.example.test"}), auth(), RateSpec(1), 10, 1024
    )
    assert policy.rate.concurrency == 2
    with pytest.raises(FrozenInstanceError):
        policy.source = "other"
    for origin in [
        "https://api.example.test/path",
        "https://user@api.example.test",
        "ftp://api.example.test",
        "https://*.example.test",
        "https://api.example.test?key=x",
        "https://api.example.test:99999",
        "https://api.example.test#",
        "",
    ]:
        with pytest.raises(ValueError):
            auth(origin)
    for rate in [0, -1, float("nan"), float("inf")]:
        with pytest.raises(ValidationError):
            RateSpec(rate)
    with pytest.raises(ValidationError):
        RateSpec(1, concurrency=0)
    with pytest.raises(ValidationError):
        ProbeSpec(0, "free", "test")
    with pytest.raises(ValueError):
        SourcePolicy("test", frozenset({"other.test"}), auth(), RateSpec(1), 10, 1024)
    with pytest.raises(ValidationError):
        SourcePolicy(
            "test", frozenset({"api.example.test"}), None, RateSpec(1), 0, 1024
        )


def test_search_bounds():
    """AT-PLAT-06: Search filters reject out-of-bounds and reversed years."""
    from research_mcp.core.models import SearchFilters, SearchRequest

    assert SearchFilters(year_from=1800, year_to=2100).year_from == 1800
    for values in [
        {"year_from": 1799},
        {"year_to": 2101},
        {"year_from": 2025, "year_to": 2020},
    ]:
        with pytest.raises(ValidationError):
            SearchFilters(**values)
    for values in [
        {"query": ""},
        {"query": "x" * 501},
        {"query": "x", "limit": 0},
        {"query": "x", "limit": 26},
    ]:
        with pytest.raises(ValidationError):
            SearchRequest(**values)
    assert SearchRequest(query="research").limit == 10


def test_work_and_call_record():
    """AT-PLAT-06: Shared models validate nested records and telemetry bounds."""
    from research_mcp.core.ids import Identifier

    from research_mcp.core.models import CallRecord, Work, WorkRecord

    work = Work(
        ids=[],
        title="A study",
        authors=[],
        year=None,
        venue=None,
        work_type="article",
        abstract=None,
        oa_locations=[],
        found_in=["test"],
    )
    assert Work.model_validate_json(work.model_dump_json()) == work
    assert work.cache_state == "none"
    now = datetime(2025, 1, 1, tzinfo=UTC)
    record = WorkRecord(
        ids=[],
        title="A study",
        provenance={
            "source": "test",
            "upstream_id": "1",
            "adapter_version": "1",
            "retrieved_at": now,
        },
        extra={"nested": [1, True, None, {"x": "y"}]},
    )
    assert record.authors == []
    from research_mcp.core.models import Identifier as ReexportedIdentifier

    assert ReexportedIdentifier is Identifier
    call = CallRecord(
        ts=now,
        source="test",
        op="search",
        status=200,
        error_code=None,
        latency_ms=0,
        bytes=20,
        rl_remaining=None,
        rl_reset=None,
        cred_expires_at=None,
        correlation_id="request",
        attempt=1,
    )
    assert CallRecord.model_validate_json(call.model_dump_json()) == call
    for field, value in [
        ("attempt", 0),
        ("bytes", -1),
        ("latency_ms", -1),
        ("status", 600),
    ]:
        with pytest.raises(ValidationError):
            CallRecord.model_validate({**call.model_dump(), field: value})


def test_fake_clock_and_sleepers():
    """AT-PLAT-06: Time advances deterministically and sleepers yield asynchronously."""
    clock = FakeClock()
    start = clock.now()
    clock.advance(1.25)
    assert clock.now() == start + timedelta(seconds=1.25)
    sleeper = FakeSleeper(clock)
    asyncio.run(sleeper.sleep(2))
    assert clock.now() == start + timedelta(seconds=3.25)
    assert sleeper.calls == [2]
    for seconds in [-1, float("nan"), float("inf")]:
        with pytest.raises(ValueError):
            clock.advance(seconds)
    with pytest.raises(ValueError):
        FakeClock(datetime(2025, 1, 1))
    assert SystemClock().now().tzinfo == UTC
    asyncio.run(AsyncSleeper().sleep(0))
