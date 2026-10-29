"""The entrypoint starts its session with the room options that take no typed turns, and with the
phone's turn-taking."""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import dotenv
import pytest
from livekit import rtc
from livekit.agents import AgentSession
from livekit.plugins import openai


class _Started(Exception):
    """Stops the entrypoint once it has started its session."""


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    # the module reads its key at import: give it a test key, never the developer's .env
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *_, **__: False)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.delitem(sys.modules, "agent", raising=False)
    return importlib.import_module("agent")


def _job() -> SimpleNamespace:
    async def wait_for_participant() -> SimpleNamespace:
        return SimpleNamespace(
            kind=rtc.ParticipantKind.PARTICIPANT_KIND_SIP, identity="caller", attributes={}
        )

    return SimpleNamespace(
        room=object(), job=SimpleNamespace(metadata=""), wait_for_participant=wait_for_participant
    )


async def _started(agent: ModuleType, monkeypatch: pytest.MonkeyPatch):
    """The session the entrypoint built and the options it started it with."""
    started: dict[str, Any] = {}

    async def start(session: AgentSession, **options: Any) -> None:
        started.update(options, session=session)
        raise _Started

    monkeypatch.setattr(AgentSession, "start", start)
    with pytest.raises(_Started):
        await agent.entrypoint(_job())
    return started


def test_stops_without_the_model_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *_, **__: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delitem(sys.modules, "agent", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        importlib.import_module("agent")


async def test_starts_the_session_without_typed_turns(
    agent: ModuleType, monkeypatch: pytest.MonkeyPatch
):
    started = await _started(agent, monkeypatch)

    room_options = started["room_options"]
    assert room_options.get_text_input_options() is None
    assert started["session_host"] is False
    assert started["record"] is False


async def test_takes_the_phone_turn_taking(agent: ModuleType, monkeypatch: pytest.MonkeyPatch):
    session: AgentSession = (await _started(agent, monkeypatch))["session"]

    assert isinstance(session.llm, openai.realtime.RealtimeModel)
    assert session.llm.model == agent.MODEL
    assert agent.phone_turns()["endpointing"] == {"max_delay": agent.MAX_DELAY}
    assert agent.phone_turns()["interruption"] == {"mode": "vad"}
