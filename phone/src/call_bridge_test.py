import asyncio
from types import SimpleNamespace

import pytest

from call_bridge import CallBridge
from staff_attribute import STAFF_ATTRIBUTE


class _Participant:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.written: list[str] = []

    async def set_attributes(self, attributes: dict[str, str]) -> None:
        if self.failures:
            self.failures -= 1
            raise ConnectionError("the room did not take the attributes")
        self.written.append(attributes[STAFF_ATTRIBUTE])


def _bridge(participant: _Participant) -> CallBridge:
    room = SimpleNamespace(local_participant=participant, remote_participants={})
    return CallBridge(room, "caller")  # type: ignore[arg-type]


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


async def test_staff_presence_is_written_once_per_change():
    participant = _Participant()
    bridge = _bridge(participant)
    bridge._on_members(["caller", "user-7"])
    bridge._on_members(["caller", "user-7"])
    await _settle()
    bridge._on_members(["caller", "user-7", "user-8"])
    bridge._on_members(["caller"])
    await _settle()
    assert participant.written == ["true", "false"]


async def test_a_failed_write_is_tried_again_on_the_next_roster():
    participant = _Participant(failures=1)
    bridge = _bridge(participant)
    bridge._on_members(["caller", "user-7"])
    await _settle()
    assert participant.written == []
    bridge._on_members(["caller", "user-7"])
    await _settle()
    assert participant.written == ["true"]
    with pytest.raises(ConnectionError):
        await bridge._background.close()
