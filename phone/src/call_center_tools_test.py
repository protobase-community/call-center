"""The call center's tools in a session: they refuse before verification, and PIN entry keeps the
caller's digits from the model, the transcript and every log line."""

import json
import logging

import pytest
from livekit import rtc
from livekit.agents import Agent, AgentSession
from livekit.rtc._proto import participant_pb2

from caller_info import CallerInfo
from conftest import StandIn
from fake_player import FakePlayer
from hold_queue import HoldQueue
from keypad import listen_to_keypad
from phone_line_stand_in import CUSTOMER_NUMBER, PIN
from pin_entry import PinEntry, route_keys
from scripted_llm import Reply, ScriptedLLM, ToolCall
from tools import session_tools

WRONG_PIN = "111111"
TICKET: dict[str, object] = {
    "subject": "Router keeps blinking red",
    "description": "The internet drops every hour.",
}


class _Call:
    """A session with the call center's tools, over a call registered with the stand-in."""

    def __init__(self, stand_in: StandIn, replies: list[Reply]) -> None:
        self.call_center = stand_in.call_center()
        self.model = ScriptedLLM(replies)
        self.caller = CallerInfo()
        self.session = AgentSession(llm=self.model, userdata=self.caller)
        self.replies = []
        self.pin_entry = PinEntry(self.call_center, self.caller, self.to_model)
        self.player = FakePlayer()
        self.queue = HoldQueue(
            self.player, "hold-music.ogg", 5, self.session.input.set_audio_enabled, self.to_model
        )

    def to_model(self, message: str) -> None:
        self.replies.append(self.session.generate_reply(user_input=message))

    async def start(self) -> None:
        self.caller.call_id = await self.call_center.register_call("call-1", None)
        tools = session_tools(self.call_center, self.pin_entry, self.queue)
        await self.session.start(Agent(instructions="Help the caller.", tools=tools))


def _output(result) -> dict:
    return json.loads(result.expect.next_event().is_function_call_output().event().item.output)


@pytest.mark.parametrize(
    "tool", [ToolCall("customer_summary"), ToolCall("create_ticket", TICKET)], ids=lambda t: t.name
)
async def test_the_customer_tools_refuse_before_verification(stand_in: StandIn, tool: ToolCall):
    call = _Call(stand_in, [tool, "Let me verify you first."])
    await call.start()
    async with call.session:
        result = await call.session.run(user_input="What are my tickets?")

    result.expect.next_event().is_function_call(name=tool.name)
    output = result.expect.next_event().is_function_call_output().event().item
    assert output.is_error
    assert "not verified" in output.output
    assert [r["path"] for r in stand_in.requests()] == ["/calls"]


async def test_pin_entry_keeps_the_digits_from_the_model_transcript_and_logs(
    stand_in: StandIn, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.DEBUG)
    call = _Call(
        stand_in,
        [
            ToolCall("ask_for_pin"),
            "Please type your customer number and press pound, then your PIN and press pound.",
            "That did not match. Let's try again.",
            ToolCall("ask_for_pin"),
            "Please type them again.",
            "Thank you, you are verified.",
            ToolCall("create_ticket", TICKET),
            "I opened a ticket for you.",
        ],
    )
    room = rtc.Room()
    caller_participant = rtc.RemoteParticipant(
        participant_pb2.OwnedParticipant(info=participant_pb2.ParticipantInfo(identity="caller"))
    )

    def press(keys: str) -> None:
        for key in keys:
            event = rtc.SipDTMF(code=0, digit=key, participant=caller_participant)
            room.emit("sip_dtmf_received", event)

    await call.start()
    async with call.session:
        stop = listen_to_keypad(
            room, "caller", route_keys(call.pin_entry, lambda: call.queue.waiting, call.to_model)
        )
        asked = await call.session.run(user_input="I need help with my router.")
        press(f"{CUSTOMER_NUMBER}#{WRONG_PIN}#")
        await call.pin_entry.wait()
        await call.replies[-1]
        await call.session.run(user_input="Can we try again?")
        press(f"{CUSTOMER_NUMBER}#{PIN}#")
        await call.pin_entry.wait()
        await call.replies[-1]
        ticket = await call.session.run(user_input="Please open a ticket about my router.")
        stop()

    asked.expect.next_event().is_function_call(name="ask_for_pin")
    assert _output(asked) == {"changed": {"keypad": "pin_entry"}}
    ticket.expect.next_event().is_function_call(name="create_ticket")
    assert _output(ticket)["changed"]["ticket"]["subject"] == TICKET["subject"]
    paths = [(r["path"].split("/")[-1], r["status"]) for r in stand_in.requests()]
    assert paths == [("calls", 201), ("verify", 200), ("verify", 200), ("tickets", 201)]

    seen_by_model = [json.dumps(request.to_dict()) for request in call.model.requests]
    transcript = json.dumps(call.session.history.to_dict())
    assert '{\\"verified\\": false}' in transcript
    assert '{\\"verified\\": true}' in transcript
    # the session logs at debug level meanwhile, so the check below reads real log lines
    assert len(caplog.records) > 0
    for text in [*seen_by_model, transcript, caplog.text]:
        for digits in (CUSTOMER_NUMBER, WRONG_PIN, PIN):
            assert digits not in text


async def test_asks_for_no_pin_once_verified(stand_in: StandIn):
    call = _Call(stand_in, [ToolCall("ask_for_pin"), "You are verified already."])
    await call.start()
    call.caller.verified = True
    async with call.session:
        result = await call.session.run(user_input="Check my PIN.")

    result.expect.next_event().is_function_call(name="ask_for_pin")
    assert result.expect.next_event().is_function_call_output().event().item.is_error
    assert not call.pin_entry.active


async def test_asking_for_a_person_sets_the_call_waiting_and_plays_the_music(stand_in: StandIn):
    call = _Call(stand_in, [ToolCall("ask_for_person")])
    await call.start()
    async with call.session:
        result = await call.session.run(user_input="Can I talk to a person?")
        waiting = call.queue.waiting
        listening = call.session.input.audio_enabled
        call.queue.end_wait()

    result.expect.next_event().is_function_call(name="ask_for_person")
    assert _output(result) == {"changed": {"call": "waiting"}}
    # no reply follows: the assistant stops replying while the caller waits
    result.expect.no_more_events()
    assert waiting
    assert not listening
    assert [(p.audio, p.loop) for p in call.player.played] == [("hold-music.ogg", True)]
    status = [r for r in stand_in.requests() if r["path"].endswith("/status")]
    assert [(r["status"], r["answer"]["status"]) for r in status] == [(200, "waiting")]


async def test_asks_for_no_person_twice_while_waiting(stand_in: StandIn):
    call = _Call(stand_in, [ToolCall("ask_for_person"), "You are in the queue already."])
    await call.start()
    call.queue.start()
    async with call.session:
        result = await call.session.run(user_input="Is anyone there?")
        call.queue.end_wait()

    result.expect.next_event().is_function_call(name="ask_for_person")
    assert result.expect.next_event().is_function_call_output().event().item.is_error
    assert len(call.player.played) == 1
