from livekit.agents import Agent, llm

from instructions import GREETING, INSTRUCTIONS


class Assistant(Agent):
    def __init__(self, tools: list[llm.Tool | llm.Toolset]) -> None:
        super().__init__(instructions=INSTRUCTIONS, tools=tools)

    async def on_enter(self) -> None:
        self.session.generate_reply(instructions=GREETING)
