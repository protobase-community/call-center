"""How the bridge tells the agent that staff are in the call: an attribute of its participant in
the caller's room, `call_center.staff`, "true" while anyone but the caller is in the call."""

from collections.abc import Mapping

STAFF_ATTRIBUTE = "call_center.staff"
# the member the phone line's account joins as (the app's config/phone_calls/call-address.ts)
CALLER_MEMBER = "caller"


def staff_in(members: list[str]) -> bool:
    return any(member != CALLER_MEMBER for member in members)


def staff_attributes(present: bool) -> dict[str, str]:
    return {STAFF_ATTRIBUTE: "true" if present else "false"}


def staff_present(attributes: Mapping[str, str]) -> bool | None:
    """Whether the bridge says staff are in; None when the attributes are not a bridge's."""
    value = attributes.get(STAFF_ATTRIBUTE)
    if value is None:
        return None
    return value == "true"
