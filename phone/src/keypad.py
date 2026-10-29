"""Keys a phone caller presses (DTMF), handed to the model as one message per sequence.

A sequence ends at the pound key or after a pause, so a menu choice and a longer number both
arrive whole. LiveKit's own GetDtmfTask collects digits by switching the agent's instructions,
which would change the prompt in the middle of the call, so the keys reach the model as an
injected user message instead.
"""

import asyncio
from collections.abc import Callable

from livekit import rtc

from tool_result import tool_result

END_KEY = "#"
# seconds without a key press that end a sequence
PAUSE = 3.0


def keypad_message(keys: str) -> str:
    return tool_result(keypad=keys)


class KeypadSequence:
    """Collects key presses and hands each finished sequence to `deliver`."""

    def __init__(self, deliver: Callable[[str], object], pause: float = PAUSE) -> None:
        self._deliver = deliver
        self._pause = pause
        self._keys: list[str] = []
        self._timer: asyncio.TimerHandle | None = None

    def press(self, key: str) -> None:
        self._cancel_timer()
        if key == END_KEY:
            # a pound key on its own is a choice of its own, such as "press pound to repeat"
            self._finish(fallback=END_KEY)
            return
        self._keys.append(key)
        self._timer = asyncio.get_running_loop().call_later(self._pause, self._finish)

    def close(self) -> None:
        self._cancel_timer()
        self._keys.clear()

    def _finish(self, fallback: str | None = None) -> None:
        self._timer = None
        keys = "".join(self._keys) or fallback
        self._keys.clear()
        if keys:
            self._deliver(keys)

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None


def listen_to_keypad(
    room: rtc.Room, identity: str, deliver: Callable[[str], object]
) -> Callable[[], None]:
    """Delivers the key sequences of the participant `identity`; returns a function that stops."""
    sequence = KeypadSequence(deliver)

    def on_dtmf(event: rtc.SipDTMF) -> None:
        if event.participant is None or event.participant.identity != identity:
            return
        sequence.press(event.digit)

    room.on("sip_dtmf_received", on_dtmf)

    def stop() -> None:
        room.off("sip_dtmf_received", on_dtmf)
        sequence.close()

    return stop
