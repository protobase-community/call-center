"""The tools that act on the caller's account in the call center app.

Each is a thin call of one phone line route that reports what it read or changed as JSON. Those
that reach the customer refuse until the caller is verified, so the model cannot act on an account
by guessing; the app refuses them too.
"""

from livekit.agents import RunContext, ToolError, function_tool, llm

from call_center import CallCenter, CallCenterError
from caller_info import CallerInfo
from pin_entry import PinEntry
from tool_result import tool_result

_ASK_FOR_PIN = """Start the caller's verification: call it before anything about their account,
tickets or customer record. Then ask the caller to type their customer number and press the pound
key, then their support PIN and press the pound key. Their keys go to the check, not to you; the
outcome arrives as a message such as {"verified": true}: true once verified, false when the number
or PIN did not match, which you may offer to try again by calling this tool again, or "locked" once
this call has no tries left. Never say whether a customer number exists."""

_CUSTOMER_SUMMARY = """Get the verified caller's name and their tickets not solved yet."""

_CREATE_TICKET = """Open a ticket for the verified caller about what they need help with; a call is
about one ticket.
subject: a short line that names the problem, in the caller's language.
description: what the caller told you about it, in a few sentences."""

_NOT_VERIFIED = "The caller is not verified: call ask_for_pin first"


def _verified_call(caller: CallerInfo) -> int:
    if not caller.verified or caller.call_id is None:
        raise ToolError(_NOT_VERIFIED)
    return caller.call_id


def ask_for_pin_tool(pin_entry: PinEntry) -> llm.FunctionTool:
    async def ask_for_pin(context: RunContext[CallerInfo]) -> str:
        if context.userdata.verified:
            raise ToolError("The caller is verified already")
        pin_entry.start()
        return tool_result(changed={"keypad": "pin_entry"})

    return function_tool(ask_for_pin, description=_ASK_FOR_PIN)


def customer_summary_tool(call_center: CallCenter) -> llm.FunctionTool:
    async def customer_summary(context: RunContext[CallerInfo]) -> str:
        customer = await call_center.customer(_verified_call(context.userdata))
        return tool_result(name=customer["name"], open_tickets=customer["tickets"])

    return function_tool(customer_summary, description=_CUSTOMER_SUMMARY)


def create_ticket_tool(call_center: CallCenter) -> llm.FunctionTool:
    async def create_ticket(context: RunContext[CallerInfo], subject: str, description: str) -> str:
        call_id = _verified_call(context.userdata)
        try:
            ticket = await call_center.create_ticket(call_id, subject, description)
        except CallCenterError as error:
            if error.problem == "call-has-ticket":
                raise ToolError("This call has a ticket already; a call is about one") from error
            raise
        return tool_result(changed={"ticket": ticket})

    return function_tool(create_ticket, description=_CREATE_TICKET)
