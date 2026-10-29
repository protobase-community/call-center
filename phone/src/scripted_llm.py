"""A text LLM for tests that gives scripted replies in order: text, or a call of one tool."""

import json
from dataclasses import dataclass, field

from livekit.agents import llm
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, object] = field(default_factory=dict)


Reply = str | ToolCall


class ScriptedLLM(llm.LLM):
    def __init__(self, replies: list[Reply]) -> None:
        super().__init__()
        self._replies = list(replies)
        self.requests: list[llm.ChatContext] = []

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        **_: object,
    ) -> llm.LLMStream:
        self.requests.append(chat_ctx.copy())
        if not self._replies:
            raise AssertionError("the agent asked for more replies than the test scripted")
        delta = _delta(self._replies.pop(0), call_id=f"call_{len(self.requests)}")
        return _ScriptedStream(
            self, delta, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options
        )


def _delta(reply: Reply, *, call_id: str) -> llm.ChoiceDelta:
    if isinstance(reply, str):
        return llm.ChoiceDelta(role="assistant", content=reply)

    call = llm.FunctionToolCall(
        name=reply.name, arguments=json.dumps(reply.arguments), call_id=call_id
    )
    return llm.ChoiceDelta(role="assistant", tool_calls=[call])


class _ScriptedStream(llm.LLMStream):
    def __init__(self, owner: ScriptedLLM, delta: llm.ChoiceDelta, **kwargs) -> None:
        super().__init__(owner, **kwargs)
        self._delta = delta

    async def _run(self) -> None:
        self._event_ch.send_nowait(llm.ChatChunk(id="scripted", delta=self._delta))
