"""Checks the bridge's sign-in in run.sh's calls, and that no credential reached a log.

usage: check_sign_in.py <out dir>   (PHONE_LINE_PASSWORD, STAFF_PASSWORD and ADMIN_PASSWORD in the
environment)

- The phone line had one session after the first call, none once an admin revoked it, and one
  again after the second call, which the bridge joined (check_bridge_call.py hears it), so it
  signed in again.
- With a wrong password the bridge gave up on the call after one refused sign-in, never joined,
  and the assistant still answered the caller.
- No log holds a password or a session cookie.
Prints one JSON object and exits 1 when a check fails.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sip_call"))
from check_call import split_call  # noqa: E402

SESSIONS = [1, 0, 1]
REFUSED = "The app refused the phone line's sign-in (401)"
JOINED = "joined the app's phone call"
# what Better Auth names its session cookie, with or without a prefix
COOKIE_NAME = "session_token"
GREETING_LOUD = 0.2


def sessions(out: Path) -> dict:
    found = [int(line) for line in (out / "sessions.txt").read_text().split()]
    return {"sessions": found, "passed": found == SESSIONS}


def wrong_password(out: Path, caller_port: int) -> dict:
    log = (out / "wrong-password-bridge.log").read_text()
    refusals = log.count(REFUSED)
    joins = log.count(JOINED)
    _, received = split_call((out / "wrong-password.pcap").read_bytes(), caller_port)
    loud = sum(a.loud for a in received) / len(received) if received else 0.0
    return {
        "refusals": refusals,
        "joins": joins,
        "assistant_loud_share": round(loud, 2),
        "passed": refusals == 1 and joins == 0 and loud >= GREETING_LOUD,
    }


def no_credentials(out: Path, secrets: list[str]) -> dict:
    found = []
    for log in sorted(out.glob("*.log")):
        text = log.read_text(errors="replace")
        if COOKIE_NAME in text or any(secret in text for secret in secrets):
            found.append(log.name)
    return {"logs_with_credentials": found, "passed": not found}


def main(out: Path, caller_port: int = 6000) -> int:
    variables = ("PHONE_LINE_PASSWORD", "STAFF_PASSWORD", "ADMIN_PASSWORD")
    secrets = [os.environ[v] for v in variables]
    results = {
        "revoked session signs in again": sessions(out),
        "wrong password stops the bridge for the call": wrong_password(out, caller_port),
        "no credential in a log": no_credentials(out, secrets),
    }
    passed = all(r["passed"] for r in results.values())
    print(json.dumps({"passed": passed, **results}, indent=1))
    return 0 if passed else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: check_sign_in.py <out dir>")
    sys.exit(main(Path(sys.argv[1])))
