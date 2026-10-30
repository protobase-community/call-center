"""What the session knows about the caller, read by tools at call time."""

from dataclasses import dataclass


@dataclass
class CallerInfo:
    # an IANA zone, such as Europe/Madrid; a phone caller's is unknown
    time_zone: str | None = None
    # the identity of the caller's SIP participant
    phone_identity: str | None = None
    # the call's record in the call center app, once registered
    call_id: int | None = None
    # whether the caller gave a customer number and PIN the app verified
    verified: bool = False
