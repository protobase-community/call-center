"""The call center app's phone line, functions/phone-line: one signed request per route.

Each method is a thin call of one route and returns its answer as the app gives it. A refusal is
a CallCenterError naming the route, the status and the problem's slug, never the request's body,
which may hold the caller's customer number and PIN.
"""

import json
import time
import uuid
from collections.abc import Callable
from typing import Any, Literal

import aiohttp

from call_center_settings import CallCenterSettings
from webhook_signature import signed_headers

Verification = Literal["verified", "not_verified", "locked"]

PROBLEM_TYPE_PREFIX = "urn:protobase:problem:"
# seconds a request may take; the caller waits on the line meanwhile
TIMEOUT = 10.0


class CallCenterError(Exception):
    def __init__(self, method: str, path: str, status: int, problem: str | None) -> None:
        super().__init__(f"{method} {path} answered {status} {problem or ''}".rstrip())
        self.status = status
        # the problem's slug, such as call-has-ticket; None when the answer is no problem
        self.problem = problem


def _new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex}"


class CallCenter:
    def __init__(
        self,
        settings: CallCenterSettings,
        clock: Callable[[], float] = time.time,
        new_message_id: Callable[[], str] = _new_message_id,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._new_message_id = new_message_id

    async def register_call(self, room_name: str, caller_number: str | None) -> int:
        """The call's record, created incoming, or the one the room already has."""
        call = await self._request(
            "POST", "/calls", {"room_name": room_name, "caller_number": caller_number}
        )
        return call["id"]

    async def wait_in_queue(self, call_id: int) -> None:
        """The call waits for a person; again while it waits keeps the time it started waiting."""
        await self._request("POST", f"/calls/{call_id}/status", {"status": "waiting"})

    async def end_call(self, call_id: int) -> None:
        await self._request("POST", f"/calls/{call_id}/status", {"status": "ended"})

    async def verify(self, call_id: int, customer_number: str, pin: str) -> Verification:
        answer = await self._request(
            "POST", f"/calls/{call_id}/verify", {"customer_number": customer_number, "pin": pin}
        )
        return answer["result"]

    async def customer(self, call_id: int) -> dict[str, Any]:
        """The verified customer's name and their tickets not solved yet."""
        return await self._request("GET", f"/calls/{call_id}/customer")

    async def create_ticket(
        self, call_id: int, subject: str, description: str | None
    ) -> dict[str, Any]:
        return await self._request(
            "POST", f"/calls/{call_id}/tickets", {"subject": subject, "description": description}
        )

    async def _request(
        self, method: str, path: str, body: dict[str, object] | None = None
    ) -> dict[str, Any]:
        text = "" if body is None else json.dumps(body)
        headers = signed_headers(
            self._settings.key,
            text,
            message_id=self._new_message_id(),
            seconds=int(self._clock()),
        )
        if body is not None:
            headers["content-type"] = "application/json"

        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        async with (
            aiohttp.ClientSession(timeout=timeout) as http,
            http.request(
                method, self._settings.url + path, data=text or None, headers=headers
            ) as response,
        ):
            if response.ok:
                return await response.json()
            raise CallCenterError(method, path, response.status, await _problem(response))


async def _problem(response: aiohttp.ClientResponse) -> str | None:
    if response.content_type != "application/problem+json":
        return
    problem = await response.json(content_type=None)
    problem_type = problem.get("type", "") if isinstance(problem, dict) else ""
    return problem_type.removeprefix(PROBLEM_TYPE_PREFIX) or None
