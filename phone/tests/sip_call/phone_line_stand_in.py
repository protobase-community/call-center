"""A stand-in of the call center app's phone line, functions/phone-line, for the SIPp call.

It answers the routes the app serves, with the app's answers and refusals (functions/phone-line/
calls.ts, verify.ts, customer.ts and tickets.ts), over one customer of its own instead of a
database: customer number CUSTOMER_NUMBER with the PIN PIN. Standard library only, so it runs on
the SIPp image.
"""

import json
import re
from datetime import UTC, datetime
from typing import Any

CUSTOMER_NUMBER = "100001"
PIN = "482915"
CUSTOMER = {"name": "Ama Mensah"}
# wrong PINs a call may give before its verification ends
CALL_TRIES = 3

Answer = tuple[int, dict[str, Any]]
_ANSWERED = (
    "id",
    "room_name",
    "caller_number",
    "status",
    "started_at",
    "waiting_since",
    "ended_at",
)
_TICKET = ("id", "subject", "status", "priority", "created_at")


class Problem(Exception):
    def __init__(self, status: int, slug: str, title: str, detail: str) -> None:
        super().__init__(detail)
        self.answer: Answer = (
            status,
            {
                "type": f"urn:protobase:problem:{slug}",
                "title": title,
                "status": status,
                "detail": detail,
            },
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _text(body: dict[str, Any], field: str, low: int, high: int, optional: bool = False) -> Any:
    value = body.get(field)
    if optional and value is None:
        return
    if not isinstance(value, str) or not low <= len(value) <= high:
        raise Problem(
            400, "invalid-body", "Bad Request", f"Give a text of {low} to {high} characters"
        )
    return value


class PhoneLine:
    def __init__(self) -> None:
        self.calls: dict[int, dict[str, Any]] = {}
        self.tickets: list[dict[str, Any]] = [
            {
                "id": 1,
                "subject": "Invoice question",
                "status": "open",
                "priority": None,
                "created_at": _now(),
            }
        ]

    def answer(self, method: str, path: str, text: str) -> Answer:
        try:
            return self._route(method, path, text)
        except Problem as problem:
            return problem.answer

    def _route(self, method: str, path: str, text: str) -> Answer:
        if (method, path) == ("POST", "/calls"):
            return self._create_call(_body(text))
        match = re.fullmatch(r"/calls/([^/]+)/(status|verify|customer|tickets)", path)
        routes = {"status": "POST", "verify": "POST", "customer": "GET", "tickets": "POST"}
        if not match or routes[match[2]] != method:
            raise Problem(
                404, "not-found", "Not Found", f"There is no {method} {path} on the phone line"
            )
        call = self._call(match[1])
        if match[2] == "status":
            return self._set_status(call, _body(text))
        if call["status"] == "ended":
            raise Problem(409, "call-ended", "Conflict", f"Phone call {call['id']} has ended")
        if match[2] == "verify":
            return self._verify(call, _body(text))
        if call["customer"] is None:
            raise Problem(
                404, "not-found", "Not Found", f"Phone call {call['id']} has no verified customer"
            )
        if match[2] == "customer":
            return 200, {
                **CUSTOMER,
                "tickets": [t for t in reversed(self.tickets) if t["status"] != "solved"],
            }
        return self._create_ticket(call, _body(text))

    def _call(self, text: str) -> dict[str, Any]:
        call = self.calls.get(int(text)) if text.isdigit() else None
        if call is None:
            raise Problem(404, "not-found", "Not Found", f"There is no phone call {text}")
        return call

    def _create_call(self, body: dict[str, Any]) -> Answer:
        room_name = _text(body, "room_name", 1, 200)
        caller_number = _text(body, "caller_number", 0, 40, optional=True)
        for call in self.calls.values():
            if call["room_name"] == room_name:
                return 200, _shown(call, _ANSWERED)
        call = {
            "id": len(self.calls) + 1,
            "room_name": room_name,
            "caller_number": caller_number,
            "status": "incoming",
            "started_at": _now(),
            "waiting_since": None,
            "ended_at": None,
            "customer": None,
            "ticket": None,
            "pin_failures": 0,
        }
        self.calls[call["id"]] = call
        return 201, _shown(call, _ANSWERED)

    def _set_status(self, call: dict[str, Any], body: dict[str, Any]) -> Answer:
        status = body.get("status")
        if status not in ("waiting", "ended"):
            raise Problem(400, "invalid-body", "Bad Request", "Give waiting or ended")
        if call["status"] == "ended" and status == "waiting":
            raise Problem(409, "call-ended", "Conflict", f"Phone call {call['id']} has ended")
        if status == "waiting" and call["status"] not in ("incoming", "waiting"):
            raise Problem(
                409, "call-answered", "Conflict", f"Phone call {call['id']} is {call['status']}"
            )
        time_field = "waiting_since" if status == "waiting" else "ended_at"
        call.update(status=status, **{time_field: call[time_field] or _now()})
        return 200, _shown(call, _ANSWERED)

    def _verify(self, call: dict[str, Any], body: dict[str, Any]) -> Answer:
        customer_number, pin = body.get("customer_number"), body.get("pin")
        if not isinstance(customer_number, str) or not isinstance(pin, str):
            raise Problem(400, "invalid-body", "Bad Request", "Give a text")
        if call["customer"] is not None:
            raise Problem(
                409, "call-verified", "Conflict", f"Phone call {call['id']} is verified already"
            )
        if call["pin_failures"] >= CALL_TRIES:
            return 200, {"result": "locked"}
        if (customer_number, pin) == (CUSTOMER_NUMBER, PIN):
            call["customer"] = CUSTOMER_NUMBER
            return 200, {"result": "verified"}
        call["pin_failures"] += 1
        tries_left = CALL_TRIES - call["pin_failures"]
        if tries_left == 0:
            return 200, {"result": "locked"}
        return 200, {"result": "not_verified", "tries_left": tries_left}

    def _create_ticket(self, call: dict[str, Any], body: dict[str, Any]) -> Answer:
        subject = _text(body, "subject", 1, 200)
        _text(body, "description", 0, 10_000, optional=True)
        if call["ticket"] is not None:
            raise Problem(
                409,
                "call-has-ticket",
                "Conflict",
                f"Phone call {call['id']} is about ticket {call['ticket']}",
            )
        ticket = {
            "id": len(self.tickets) + 1,
            "subject": subject,
            "status": "open",
            "priority": None,
            "created_at": _now(),
        }
        self.tickets.append(ticket)
        call["ticket"] = ticket["id"]
        return 201, _shown(ticket, _TICKET)


def _body(text: str) -> dict[str, Any]:
    try:
        body = json.loads(text)
    except json.JSONDecodeError as error:
        raise Problem(
            400, "malformed-json", "Bad Request", "The request body is not valid JSON"
        ) from error
    if not isinstance(body, dict):
        raise Problem(400, "invalid-body", "Bad Request", "Send a JSON object")
    return body


def _shown(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: record[field] for field in fields}
