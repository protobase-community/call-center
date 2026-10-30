from livekit.agents import AgentSession, llm
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

from assistant import Assistant
from caller_info import CallerInfo
from conftest import StandIn
from instructions import GREETING, INSTRUCTIONS
from pin_entry import PinEntry
from tools import session_tools


class EchoLLM(llm.LLM):
    """A text LLM that records each request and replies with the last message it got."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[llm.ChatContext] = []
        self.tool_names: list[list[str]] = []

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        **_: object,
    ) -> llm.LLMStream:
        self.requests.append(chat_ctx.copy())
        self.tool_names.append([tool.id for tool in tools or []])
        return _EchoStream(self, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options)


class _EchoStream(llm.LLMStream):
    async def _run(self) -> None:
        last = self.chat_ctx.items[-1]
        text = last.text_content if last.type == "message" else None
        self._event_ch.send_nowait(
            llm.ChatChunk(id="echo", delta=llm.ChoiceDelta(role="assistant", content=text))
        )


def _tools(stand_in: StandIn) -> list[llm.Tool | llm.Toolset]:
    call_center = stand_in.call_center()
    return session_tools(call_center, PinEntry(call_center, CallerInfo(), lambda _: None))


def _system_texts(chat_ctx: llm.ChatContext) -> list[str]:
    return [
        item.text_content or ""
        for item in chat_ctx.items
        if item.type == "message" and item.role in ("system", "developer")
    ]


async def test_greets_on_enter_with_the_standing_instructions(stand_in: StandIn):
    echo = EchoLLM()
    async with AgentSession(llm=echo) as session:
        await session.start(Assistant(tools=_tools(stand_in)))

    greeting_request = echo.requests[0]
    assert _system_texts(greeting_request)[0] == INSTRUCTIONS
    assert GREETING in _system_texts(greeting_request)


async def test_answers_the_user_with_the_same_instructions(stand_in: StandIn):
    echo = EchoLLM()
    async with AgentSession(llm=echo) as session:
        await session.start(Assistant(tools=_tools(stand_in)))
        result = await session.run(user_input="Hola, ¿qué tal?")

    assert _system_texts(echo.requests[-1])[0] == INSTRUCTIONS
    reply = result.expect.next_event().is_message(role="assistant").event()
    assert reply.item.text_content == "Hola, ¿qué tal?"
    result.expect.no_more_events()


async def test_offers_the_session_tools_but_not_while_greeting(stand_in: StandIn):
    echo = EchoLLM()
    async with AgentSession(llm=echo) as session:
        await session.start(Assistant(tools=_tools(stand_in)))
        greeting_tools = echo.tool_names[0]
        await session.run(user_input="Hola")

    call_center_tools = ["ask_for_pin", "create_ticket", "customer_summary"]
    assert sorted(greeting_tools) == sorted(["current_date_and_time", *call_center_tools])
    assert sorted(echo.tool_names[-1]) == sorted(
        ["current_date_and_time", "end_call", *call_center_tools]
    )
