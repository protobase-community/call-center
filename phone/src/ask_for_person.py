"""Putting the caller in the queue for a person, with hold music in their room.

The model says it is finding someone in the same reply that calls the tool, and the tool asks for
no reply: the music starts once that sentence has played, and the assistant stays silent until the
wait ends.
"""

from livekit.agents import RunContext, ToolError, ToolResult, function_tool, llm

from call_center import CallCenter, CallCenterError
from caller_info import CallerInfo
from hold_queue import HoldQueue
from tool_result import tool_result

_DESCRIPTION = """Put the caller in the queue for a person when they ask for one. Tell them in one
short sentence that you are finding someone, in the same reply, then call this tool. They hear
hold music until a person joins; you hear nothing meanwhile."""


def ask_for_person_tool(call_center: CallCenter, queue: HoldQueue) -> llm.FunctionTool:
    async def ask_for_person(context: RunContext[CallerInfo]) -> ToolResult:
        call_id = context.userdata.call_id
        if call_id is None:
            raise RuntimeError("The queue needs the call's record in the app")
        if queue.waiting:
            raise ToolError("The caller is waiting already")
        try:
            await call_center.wait_in_queue(call_id)
        except CallCenterError as error:
            if error.problem == "call-answered":
                raise ToolError("A person has answered this call already") from error
            raise
        await context.wait_for_playout()
        queue.start()
        return ToolResult(tool_result(changed={"call": "waiting"}), reply_required=False)

    return function_tool(ask_for_person, description=_DESCRIPTION)
