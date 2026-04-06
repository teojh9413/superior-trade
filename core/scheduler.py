from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

LOGGER = logging.getLogger(__name__)


class DailyScheduler:
    def __init__(self, timezone_name: str, hour: int, minute: int) -> None:
        self.timezone_name = timezone_name
        self.hour = hour
        self.minute = minute
        self._task: asyncio.Task[None] | None = None
        self._callback: Callable[[], Awaitable[None]] | None = None

    def start(self, callback: Callable[[], Awaitable[None]]) -> None:
        self._callback = callback
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop(), name="daily-brief-scheduler")

    def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

    def describe(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d} {self.timezone_name}"

    def seconds_until_next_run(self, now: datetime | None = None) -> float:
        tz = resolve_timezone(self.timezone_name)
        current = now.astimezone(tz) if now else datetime.now(tz)
        target = current.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if target <= current:
            target = target + timedelta(days=1)
        return (target - current).total_seconds()

    async def _run_loop(self) -> None:
        LOGGER.info("Daily scheduler loop started for %s.", self.describe())
        try:
            while True:
                await asyncio.sleep(self.seconds_until_next_run())
                if self._callback is None:
                    continue
                try:
                    await self._callback()
                except Exception:
                    LOGGER.exception("Scheduled job failed.")
        except asyncio.CancelledError:
            LOGGER.info("Daily scheduler loop stopped.")
            raise


def resolve_timezone(timezone_name: str) -> datetime.tzinfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name == "Asia/Singapore":
            LOGGER.warning("ZoneInfo data for Asia/Singapore is unavailable; falling back to fixed GMT+8.")
            return timezone(timedelta(hours=8), name="GMT+8")
        raise
