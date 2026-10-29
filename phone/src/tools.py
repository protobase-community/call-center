"""The tools every call has. A domain tool is one more entry here."""

from livekit.agents import llm

from current_time import current_time_tool
from end_session import end_session_tool


def session_tools() -> list[llm.Tool | llm.Toolset]:
    return [end_session_tool(), current_time_tool()]
