"""What the session knows about the caller, read by tools at call time."""

from dataclasses import dataclass


@dataclass
class CallerInfo:
    # an IANA zone, such as Europe/Madrid; a phone caller's is unknown
    time_zone: str | None = None
    # the identity of the caller's SIP participant
    phone_identity: str | None = None
