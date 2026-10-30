import asyncio
import json

import pytest

from fake_player import FakePlayer
from hold_queue import HoldQueue

MUSIC = "hold-music.ogg"
# a few milliseconds, so the longest wait passes within the test
SHORT_WAIT_MINUTES = 0.0005


class _Queue:
    def __init__(self, max_wait_minutes: float = 5) -> None:
        self.player = FakePlayer()
        self.listening: list[bool] = []
        self.reports: list[str] = []
        self.queue = HoldQueue(
            self.player, MUSIC, max_wait_minutes, self.listening.append, self.reports.append
        )


async def test_plays_the_music_in_a_loop_and_stops_listening():
    q = _Queue()

    q.queue.start()

    assert q.queue.waiting
    assert [(p.audio, p.loop, p.stopped) for p in q.player.played] == [(MUSIC, True, False)]
    assert q.listening == [False]
    q.queue.end_wait()


async def test_the_longest_wait_brings_the_assistant_back():
    q = _Queue(SHORT_WAIT_MINUTES)

    q.queue.start()
    await asyncio.sleep(SHORT_WAIT_MINUTES * 60 + 0.05)

    assert not q.queue.waiting
    assert q.player.played[0].stopped
    assert q.listening == [False, True]
    assert [json.loads(r) for r in q.reports] == [{"queue": {"waited_minutes": SHORT_WAIT_MINUTES}}]


async def test_ending_the_wait_stops_the_music_and_the_timer_and_keeps_the_assistant_silent():
    q = _Queue(SHORT_WAIT_MINUTES)

    q.queue.start()
    q.queue.end_wait()
    await asyncio.sleep(SHORT_WAIT_MINUTES * 60 + 0.05)

    assert not q.queue.waiting
    assert q.player.played[0].stopped
    assert q.listening == [False]
    assert q.reports == []


async def test_waits_again_after_the_longest_wait():
    q = _Queue(SHORT_WAIT_MINUTES)

    q.queue.start()
    await asyncio.sleep(SHORT_WAIT_MINUTES * 60 + 0.05)
    q.queue.start()

    assert q.queue.waiting
    assert len(q.player.played) == 2
    q.queue.end_wait()


async def test_refuses_a_second_start_while_waiting():
    q = _Queue()
    q.queue.start()

    with pytest.raises(RuntimeError, match="waiting already"):
        q.queue.start()
    q.queue.end_wait()
