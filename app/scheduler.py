from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class PollingScheduler:
    def __init__(self) -> None:
        self._jobs: dict[int, asyncio.Task] = {}

    def sync_jobs(
        self,
        tasks: list,
        callback: Callable[[int], Awaitable[None]],
    ) -> None:
        active_ids = {task.id for task in tasks if task.enabled and task.id is not None}

        for task_id in list(self._jobs.keys()):
            if task_id not in active_ids:
                self._jobs[task_id].cancel()
                del self._jobs[task_id]

        for task in tasks:
            if not task.enabled or task.id is None:
                continue
            if task.id in self._jobs:
                continue
            self._jobs[task.id] = asyncio.create_task(self._runner(task.id, task.check_interval_sec, callback))

    async def _runner(
        self,
        task_id: int,
        interval_sec: int,
        callback: Callable[[int], Awaitable[None]],
    ) -> None:
        while True:
            try:
                await callback(task_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Scheduled task %s failed: %s", task_id, exc)
            await asyncio.sleep(interval_sec)

    async def shutdown(self) -> None:
        for job in self._jobs.values():
            job.cancel()
        await asyncio.gather(*self._jobs.values(), return_exceptions=True)
        self._jobs.clear()
