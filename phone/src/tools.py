"""The tools every call has. A domain tool is one more entry here."""

from livekit.agents import llm

from ask_for_person import ask_for_person_tool
from call_center import CallCenter
from call_center_tools import ask_for_pin_tool, create_ticket_tool, customer_summary_tool
from current_time import current_time_tool
from end_session import end_session_tool
from hold_queue import HoldQueue
from pin_entry import PinEntry


def session_tools(
    call_center: CallCenter, pin_entry: PinEntry, queue: HoldQueue
) -> list[llm.Tool | llm.Toolset]:
    return [
        end_session_tool(),
        current_time_tool(),
        ask_for_pin_tool(pin_entry),
        customer_summary_tool(call_center),
        create_ticket_tool(call_center),
        ask_for_person_tool(call_center, queue),
    ]
