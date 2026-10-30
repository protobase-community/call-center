"""Reporting the end of a call to the app once, on whichever comes first: the session closing,
as when the caller hangs up, or the job shutting down."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any


class CallEnding:
    def __init__(self, end: Callable[[], Coroutine[Any, Any, None]]) -> None:
        self._end = end
        self._ending: asyncio.Task[None] | None = None

    def start(self) -> asyncio.Task[None]:
        if self._ending is None:
            self._ending = asyncio.create_task(self._end())
        return self._ending

    async def wait(self) -> None:
        await self.start()
