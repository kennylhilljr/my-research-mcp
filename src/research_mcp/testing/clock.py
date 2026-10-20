"""Deterministic time without waiting or reading the system clock."""

import asyncio
from datetime import UTC, datetime, timedelta

from research_mcp.core.timeutil import validate_seconds


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        start = start if start is not None else datetime(2000, 1, 1, tzinfo=UTC)
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("FakeClock requires an aware datetime")
        self._now = start.astimezone(UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        validate_seconds(seconds)
        self._now += timedelta(seconds=seconds)


class FakeSleeper:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.calls: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.clock.advance(seconds)
        self.calls.append(seconds)
        await asyncio.sleep(0)
