"""Production implementations of the clock and sleeper protocols."""

import asyncio
import math
from datetime import UTC, datetime


def validate_seconds(seconds: float) -> None:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("seconds must be finite and nonnegative")


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class AsyncSleeper:
    async def sleep(self, seconds: float) -> None:
        validate_seconds(seconds)
        await asyncio.sleep(seconds)
