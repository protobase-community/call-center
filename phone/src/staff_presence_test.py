import json

from staff_presence import StaffPresence


class _Agent:
    def __init__(self) -> None:
        self.events: list[object] = []

    def presence(self) -> StaffPresence:
        return StaffPresence(
            lambda present: self.events.append(("queue staff", present)),
            lambda on: self.events.append(("listening", on)),
            lambda: self.events.append("interrupted"),
            lambda message: self.events.append(json.loads(message)),
        )


def test_staff_joining_stops_the_music_and_silences_the_assistant():
    agent = _Agent()
    presence = agent.presence()
    presence.update(True)
    assert presence.present
    assert agent.events == [("queue staff", True), ("listening", False), "interrupted"]


def test_the_last_staff_member_leaving_hands_the_caller_back():
    agent = _Agent()
    presence = agent.presence()
    presence.update(True)
    agent.events.clear()
    presence.update(False)
    assert not presence.present
    assert agent.events == [("queue staff", False), ("listening", True), {"staff": "left"}]


def test_an_unchanged_presence_does_nothing():
    agent = _Agent()
    presence = agent.presence()
    presence.update(False)
    presence.update(True)
    presence.update(True)
    assert agent.events.count("interrupted") == 1
    assert {"staff": "left"} not in agent.events


class _Room:
    def __init__(self, participants: list[object]) -> None:
        self.remote_participants = {str(i): p for i, p in enumerate(participants)}
        self.handlers: dict[str, object] = {}

    def on(self, event: str, handler: object) -> None:
        self.handlers[event] = handler

    def off(self, event: str, handler: object) -> None:
        self.handlers.pop(event, None)


def test_staff_already_in_when_the_watch_begins_count():
    from types import SimpleNamespace

    from livekit import rtc

    from staff_attribute import staff_attributes
    from staff_presence import watch_staff

    bridge = SimpleNamespace(
        kind=rtc.ParticipantKind.PARTICIPANT_KIND_AGENT, attributes=staff_attributes(True)
    )
    caller = SimpleNamespace(kind=rtc.ParticipantKind.PARTICIPANT_KIND_SIP, attributes={})
    agent = _Agent()
    presence = agent.presence()
    stop = watch_staff(_Room([caller, bridge]), presence)  # type: ignore[arg-type]
    assert presence.present
    stop()


def test_a_tool_that_finishes_while_staff_are_in_gets_no_reply():
    from types import SimpleNamespace

    from staff_presence import quiet_tool_replies

    presence = _Agent().presence()
    on_executed = quiet_tool_replies(presence)
    cancelled: list[bool] = []
    event = SimpleNamespace(cancel_tool_reply=lambda: cancelled.append(True))
    on_executed(event)  # type: ignore[arg-type]
    assert cancelled == []
    presence.update(True)
    on_executed(event)  # type: ignore[arg-type]
    assert cancelled == [True]
