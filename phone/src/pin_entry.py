"""Taking the caller's customer number and support PIN on the keypad, past the model.

Once started, the caller's next two key sequences, each ended by the pound key or a pause, are the
customer number and the PIN. They go straight to the app's check and never to the model, a log or
the transcript: the model learns only the outcome, as a message such as {"verified": false}.
Outside PIN entry the keys reach the model as before.
"""

import asyncio
from collections.abc import Callable
from typing import Protocol

from call_center import CallCenterError, Verification
from caller_info import CallerInfo
from keypad import END_KEY, keypad_message
from tool_result import tool_result

# what the model is told of each outcome of the app's check
OUTCOMES: dict[Verification, bool | str] = {
    "verified": True,
    "not_verified": False,
    "locked": "locked",
}


class PinCheck(Protocol):
    async def verify(self, call_id: int, customer_number: str, pin: str) -> Verification: ...


class PinEntry:
    def __init__(
        self, check: PinCheck, caller: CallerInfo, report: Callable[[str], object]
    ) -> None:
        self._check = check
        self._caller = caller
        self._report = report
        self._entries: list[str] | None = None
        self._checks: set[asyncio.Task[None]] = set()

    @property
    def active(self) -> bool:
        return self._entries is not None

    def start(self) -> None:
        """The next two sequences are the customer number and the PIN; a restart drops any taken."""
        if self._caller.call_id is None:
            raise RuntimeError("PIN entry needs the call's record in the app")
        self._entries = []

    def take(self, keys: str) -> None:
        if self._entries is None:
            raise RuntimeError("PIN entry is not on")
        # a pound key on its own is an empty entry
        self._entries.append("" if keys == END_KEY else keys)
        if len(self._entries) < 2:
            return

        customer_number, pin = self._entries
        self._entries = None
        check = asyncio.create_task(self._verify(customer_number, pin))
        self._checks.add(check)
        check.add_done_callback(self._checks.discard)

    async def wait(self) -> None:
        """Waits for the checks under way, such as before the session ends."""
        await asyncio.gather(*self._checks)

    def close(self) -> None:
        self._entries = None
        for check in self._checks:
            check.cancel()

    async def _verify(self, customer_number: str, pin: str) -> None:
        call_id = self._caller.call_id
        if call_id is None:
            raise RuntimeError("PIN entry needs the call's record in the app")
        try:
            outcome = await self._check.verify(call_id, customer_number, pin)
        except CallCenterError:
            # the caller hears that the check failed rather than wait on it; the error goes on
            self._report(tool_result(pin_check="failed"))
            raise
        if outcome == "verified":
            self._caller.verified = True
        self._report(tool_result(verified=OUTCOMES[outcome]))


def route_keys(pin_entry: PinEntry, to_model: Callable[[str], object]) -> Callable[[str], None]:
    """Where each key sequence goes: to PIN entry while it is on, otherwise to the model."""

    def deliver(keys: str) -> None:
        if pin_entry.active:
            pin_entry.take(keys)
            return
        to_model(keypad_message(keys))

    return deliver
