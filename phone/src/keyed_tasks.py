"""Background tasks by key, such as one per audio track, that end together.

Closing cancels them all and raises the first that failed, so a broken feed is never lost.
"""

import asyncio
from collections.abc import Coroutine, Hashable
from typing import Any


class KeyedTasks:
    def __init__(self) -> None:
        self._tasks: dict[Hashable, asyncio.Task[None]] = {}
        self._ended: list[asyncio.Task[None]] = []

    def __contains__(self, key: Hashable) -> bool:
        return key in self._tasks

    def start(self, key: Hashable, work: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
        if key in self._tasks:
            work.close()
            raise RuntimeError(f"A task for {key} runs already")
        task = self._tasks[key] = asyncio.create_task(work)
        return task

    def stop(self, key: Hashable) -> None:
        task = self._tasks.pop(key, None)
        if task is not None:
            task.cancel()
            self._ended.append(task)

    async def close(self) -> None:
        for key in list(self._tasks):
            self.stop(key)
        ended, self._ended = self._ended, []
        results = await asyncio.gather(*ended, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                raise result
