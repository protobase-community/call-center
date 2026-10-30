"""Checks the PIN call by what the phone line stand-in answered: the call was registered, a wrong
PIN got `not_verified`, the right one `verified`, a ticket was created, and the call ended, in
that order. Other requests may come between, such as a look at the customer's tickets.

usage: check_pin_call.py <stand-in log>

The call's end arrives once the agent sees the hang-up, so it waits up to WAIT seconds for it.
Prints one JSON line and exits 1 when a step is missing. Standard library only, so it runs on the
SIPp image.
"""

import json
import sys
import time

WAIT = 20.0
STEPS = [
    ("the call registered", lambda r: r["path"] == "/calls" and r["status"] == 201),
    ("a wrong PIN refused", lambda r: _verify(r, "not_verified")),
    ("the right PIN verified", lambda r: _verify(r, "verified")),
    ("a ticket created", lambda r: r["path"].endswith("/tickets") and r["status"] == 201),
    ("the call ended", lambda r: r["path"].endswith("/status") and _ended(r)),
]


def _verify(record: dict, result: str) -> bool:
    return record["path"].endswith("/verify") and record["answer"].get("result") == result


def _ended(record: dict) -> bool:
    return record["status"] == 200 and record["answer"].get("status") == "ended"


def last_call(records: list[dict]) -> list[dict]:
    """The requests about the last call registered, its registration first."""
    registered = [i for i, r in enumerate(records) if r["path"] == "/calls" and r["status"] == 201]
    if not registered:
        return []
    first = registered[-1]
    prefix = f"/calls/{records[first]['answer']['id']}/"
    return [records[first], *(r for r in records[first + 1 :] if r["path"].startswith(prefix))]


def missing_steps(records: list[dict]) -> list[str]:
    """The steps not seen in order, from the first one missing."""
    remaining = iter(last_call(records))
    for index, (_name, seen) in enumerate(STEPS):
        if not any(seen(record) for record in remaining):
            return [step for step, _ in STEPS[index:]]
    return []


def read(path: str) -> list[dict]:
    with open(path) as file:
        return [json.loads(line) for line in file if line.strip()]


def main(path: str, wait: float = WAIT) -> int:
    deadline = time.monotonic() + wait
    missing = missing_steps(read(path))
    while missing and time.monotonic() < deadline:
        time.sleep(1)
        missing = missing_steps(read(path))

    seen = [
        [r["method"], r["path"], r["status"], r["answer"].get("result")]
        for r in last_call(read(path))
    ]
    print(json.dumps({"passed": not missing, "missing": missing, "requests": seen}))
    return 1 if missing else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: check_pin_call.py <stand-in log>")
    sys.exit(main(sys.argv[1]))
