import json
from datetime import UTC, datetime

from livekit.agents import Agent, AgentSession

from caller_info import CallerInfo
from current_time import current_time_tool
from scripted_llm import ScriptedLLM, ToolCall

NOW = datetime(2026, 10, 20, 18, 30, tzinfo=UTC)


async def _ask_time(caller: CallerInfo, arguments: dict[str, object]) -> str:
    model = ScriptedLLM([ToolCall("current_date_and_time", arguments), "It is half past eight."])
    agent = Agent(instructions="Be brief.", tools=[current_time_tool(clock=lambda: NOW)])
    async with AgentSession(llm=model, userdata=caller) as session:
        await session.start(agent)
        result = await session.run(user_input="What time is it?")

    result.expect.next_event().is_function_call(name="current_date_and_time")
    output = result.expect.next_event().is_function_call_output().event().item
    assert not output.is_error, output.output
    return output.output


async def test_reports_the_time_in_the_callers_zone():
    output = await _ask_time(CallerInfo(time_zone="Europe/Madrid"), {})

    assert json.loads(output) == {
        "now": "2026-10-20T20:30+02:00",
        "weekday": "Tuesday",
        "time_zone": "Europe/Madrid",
    }


async def test_a_named_zone_wins_over_the_callers():
    output = await _ask_time(CallerInfo(time_zone="Europe/Madrid"), {"time_zone": "America/Bogota"})

    assert json.loads(output)["now"] == "2026-10-20T13:30-05:00"


async def test_an_unknown_caller_zone_reports_utc_and_says_so():
    output = await _ask_time(CallerInfo(), {})

    assert json.loads(output) == {"now": "2026-10-20T18:30+00:00", "time_zone": None}


async def test_a_zone_that_does_not_exist_is_a_tool_error():
    model = ScriptedLLM([ToolCall("current_date_and_time", {"time_zone": "Mars/Base"}), "Sorry."])
    agent = Agent(instructions="Be brief.", tools=[current_time_tool(clock=lambda: NOW)])
    async with AgentSession(llm=model, userdata=CallerInfo()) as session:
        await session.start(agent)
        result = await session.run(user_input="What time is it on Mars?")

    result.expect.next_event().is_function_call(name="current_date_and_time")
    result.expect.next_event().is_function_call_output(
        output="'Mars/Base' is not an IANA time zone", is_error=True
    )
