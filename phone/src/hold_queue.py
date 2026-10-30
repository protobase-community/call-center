"""A caller waiting for a person: hold music in their room while the assistant stops listening.

The music plays on the caller's own room, through LiveKit Agents' BackgroundAudioPlayer, so the
queue is the set of rooms whose call the app shows as waiting. The wait ends when a person joins,
who calls `end_wait`, when the caller hangs up, or after the longest wait: then the music stops,
the assistant listens again and hears so as a message such as {"queue": {"waited_minutes": 5}}.
"""

import asyncio
from collections.abc import Callable
from typing import Protocol

from tool_result import tool_result


class Playing(Protocol):
    def stop(self) -> None: ...


class Player(Protocol):
    def play(self, audio: str, *, loop: bool = False) -> Playing: ...


class HoldQueue:
    def __init__(
        self,
        player: Player,
        music_file: str,
        max_wait_minutes: float,
        listen: Callable[[bool], None],
        report: Callable[[str], object],
    ) -> None:
        self._player = player
        self._music_file = music_file
        self._max_wait_minutes = max_wait_minutes
        # turns the assistant's hearing of the caller on or off
        self._listen = listen
        self._report = report
        self._music: Playing | None = None
        self._timer: asyncio.TimerHandle | None = None

    @property
    def waiting(self) -> bool:
        return self._music is not None

    def start(self) -> None:
        """Stops the assistant listening and plays the music until the wait ends."""
        if self.waiting:
            raise RuntimeError("The caller is waiting already")
        self._listen(False)
        self._music = self._player.play(self._music_file, loop=True)
        self._timer = asyncio.get_running_loop().call_later(
            self._max_wait_minutes * 60, self._waited_longest
        )

    def end_wait(self) -> None:
        """Stops the music and the longest wait's timer; the assistant stays silent."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._music is not None:
            self._music.stop()
            self._music = None

    def _waited_longest(self) -> None:
        self._timer = None
        self.end_wait()
        self._listen(True)
        self._report(tool_result(queue={"waited_minutes": self._max_wait_minutes}))
