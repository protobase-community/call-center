import asyncio
import json
from collections.abc import Awaitable, Callable

import pytest
from livekit.agents import Agent, AgentSession, llm
from livekit.agents.beta.tools import end_call

from end_session import end_session_tool
from scripted_llm import ScriptedLLM, ToolCall


class _Job:
    """The parts of a JobContext the end-call tool uses once the session closes."""

    def __init__(self) -> None:
        self.shutdown_callbacks: list[Callable[[], Awaitable[None]]] = []
        self.shutdown_reason: str | None = None

    def add_shutdown_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        self.shutdown_callbacks.append(callback)

    def shutdown(self, reason: str = "") -> None:
        self.shutdown_reason = reason


async def test_reports_the_session_ending_and_ends_the_job_without_a_second_reply(
    monkeypatch: pytest.MonkeyPatch,
):
    job = _Job()
    monkeypatch.setattr(end_call, "get_job_context", lambda: job)
    model = ScriptedLLM([ToolCall("end_call")])
    agent = Agent(instructions="Be brief.", tools=[end_session_tool()])
    async with AgentSession(llm=model) as session:
        closed = asyncio.Event()
        session.on("close", lambda _: closed.set())
        await session.start(agent)
        result = await session.run(user_input="That's all, bye.")
        await asyncio.wait_for(closed.wait(), timeout=5)

    result.expect.next_event().is_function_call(name="end_call")
    output = result.expect.next_event().is_function_call_output().event().item
    assert json.loads(output.output) == {"changed": {"session": "ending"}}
    # the goodbye comes in the reply that calls the tool, so the model is asked only once
    result.expect.no_more_events()
    assert len(model.requests) == 1
    # the room is deleted with the session, which hangs up a phone caller too
    assert job.shutdown_reason is not None
    assert len(job.shutdown_callbacks) == 1


def test_asks_for_the_goodbye_before_the_call():
    (tool,) = end_session_tool().tools

    assert isinstance(tool, llm.FunctionTool)
    assert "goodbye to the user in one short sentence first" in (tool.info.description or "")
