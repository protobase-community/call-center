"""The entrypoint registers the call with the app, then starts its session with the room options
that take no typed turns, and with the phone's turn-taking."""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import dotenv
import pytest
from livekit import rtc
from livekit.agents import AgentSession
from livekit.plugins import openai

from conftest import StandIn


class _Started(Exception):
    """Stops the entrypoint once it has started its session."""


def _environment(monkeypatch: pytest.MonkeyPatch, stand_in: StandIn) -> None:
    # the module reads its settings at import: give it test ones, never the developer's .env
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *_, **__: False)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("CALL_CENTER_URL", stand_in.url)
    monkeypatch.setenv("CALL_CENTER_SECRET", stand_in.secret)
    monkeypatch.delenv("MAX_WAIT_MINUTES", raising=False)
    monkeypatch.delenv("HOLD_MUSIC_FILE", raising=False)
    monkeypatch.delitem(sys.modules, "agent", raising=False)


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch, stand_in: StandIn) -> ModuleType:
    _environment(monkeypatch, stand_in)
    return importlib.import_module("agent")


class _Job:
    """The parts of a JobContext the entrypoint uses before its session starts."""

    def __init__(self) -> None:
        self.room = SimpleNamespace(name="call-test")
        self.job = SimpleNamespace(metadata="")
        self.shutdown_callbacks: list[Any] = []

    async def wait_for_participant(self) -> SimpleNamespace:
        return SimpleNamespace(
            kind=rtc.ParticipantKind.PARTICIPANT_KIND_SIP,
            identity="caller",
            attributes={"sip.phoneNumber": "+31205550101"},
        )

    def add_shutdown_callback(self, callback: Any) -> None:
        self.shutdown_callbacks.append(callback)


async def _started(agent: ModuleType, monkeypatch: pytest.MonkeyPatch, job: _Job | None = None):
    """The session the entrypoint built and the options it started it with."""
    started: dict[str, Any] = {}

    async def start(session: AgentSession, **options: Any) -> None:
        started.update(options, session=session)
        raise _Started

    monkeypatch.setattr(AgentSession, "start", start)
    with pytest.raises(_Started):
        await agent.entrypoint(job or _Job())
    return started


def test_stops_without_the_model_key(monkeypatch: pytest.MonkeyPatch, stand_in: StandIn):
    _environment(monkeypatch, stand_in)
    monkeypatch.delenv("OPENAI_API_KEY")

    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        importlib.import_module("agent")


@pytest.mark.parametrize("variable", ["CALL_CENTER_URL", "CALL_CENTER_SECRET"])
def test_stops_without_a_call_center_setting(
    monkeypatch: pytest.MonkeyPatch, stand_in: StandIn, variable: str
):
    _environment(monkeypatch, stand_in)
    monkeypatch.delenv(variable)

    with pytest.raises(ValueError, match=f"{variable} is not set"):
        importlib.import_module("agent")


@pytest.mark.parametrize(
    ("variable", "value"),
    [("CALL_CENTER_URL", "calls.example.com"), ("CALL_CENTER_SECRET", "not-a-secret")],
)
def test_stops_on_a_malformed_call_center_setting(
    monkeypatch: pytest.MonkeyPatch, stand_in: StandIn, variable: str, value: str
):
    _environment(monkeypatch, stand_in)
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValueError, match=f"^{variable} "):
        importlib.import_module("agent")


@pytest.mark.parametrize(
    ("variable", "value"), [("MAX_WAIT_MINUTES", "0"), ("HOLD_MUSIC_FILE", "/missing.ogg")]
)
def test_stops_on_a_malformed_queue_setting(
    monkeypatch: pytest.MonkeyPatch, stand_in: StandIn, variable: str, value: str
):
    _environment(monkeypatch, stand_in)
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValueError, match=f"^{variable} "):
        importlib.import_module("agent")


async def test_registers_the_call_and_ends_it_on_shutdown(
    agent: ModuleType, monkeypatch: pytest.MonkeyPatch, stand_in: StandIn
):
    job = _Job()
    started = await _started(agent, monkeypatch, job)
    caller = started["session"].userdata
    for callback in job.shutdown_callbacks:
        await callback()

    requests = stand_in.requests()
    assert requests[0]["answer"]["room_name"] == "call-test"
    assert requests[0]["answer"]["caller_number"] == "+31205550101"
    assert caller.call_id == requests[0]["answer"]["id"]
    assert requests[1]["path"] == f"/calls/{caller.call_id}/status"
    assert requests[1]["answer"]["status"] == "ended"


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
