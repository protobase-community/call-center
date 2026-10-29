"""Ending the session, on LiveKit's own end-call tool, which waits for the goodbye to play.

The model says goodbye in the same reply that calls the tool, and the tool asks for no reply, so
hanging up takes one model response instead of a call and then a second response for the goodbye.
"""

from livekit.agents import ToolResult, llm
from livekit.agents.beta import EndCallTool

from tool_result import tool_result

_GOODBYE_FIRST = """Say goodbye to the user in one short sentence first, in the same reply, then
call this tool; the call ends once the goodbye has played."""


async def _no_reply(event: llm.Toolset.ToolCompletedEvent) -> None:
    event.output = ToolResult(tool_result(changed={"session": "ending"}), reply_required=False)


def end_session_tool() -> EndCallTool:
    return EndCallTool(
        extra_description=_GOODBYE_FIRST,
        on_tool_completed=_no_reply,
        # the greeting must not end the session before the user has said anything
        ignore_on_enter=True,
    )
