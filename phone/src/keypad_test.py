import asyncio
import json

from livekit import rtc
from livekit.rtc._proto import participant_pb2

from keypad import KeypadSequence, keypad_message, listen_to_keypad

PAUSE = 0.2


def _participant(identity: str) -> rtc.RemoteParticipant:
    info = participant_pb2.ParticipantInfo(identity=identity)
    return rtc.RemoteParticipant(participant_pb2.OwnedParticipant(info=info))


def _press(room: rtc.Room, keys: str, participant: rtc.RemoteParticipant | None) -> None:
    for key in keys:
        room.emit("sip_dtmf_received", rtc.SipDTMF(code=0, digit=key, participant=participant))


def test_the_message_is_json_naming_the_keys():
    assert json.loads(keypad_message("1234")) == {"keypad": "1234"}


async def test_a_pause_ends_a_sequence():
    delivered: list[str] = []
    sequence = KeypadSequence(delivered.append, pause=PAUSE)

    for key in "12":
        sequence.press(key)
    await asyncio.sleep(PAUSE / 4)
    sequence.press("3")
    assert delivered == []
    await asyncio.sleep(PAUSE * 2)

    assert delivered == ["123"]


async def test_the_pound_key_ends_a_sequence_at_once():
    delivered: list[str] = []
    sequence = KeypadSequence(delivered.append, pause=PAUSE)

    for key in "4*2#":
        sequence.press(key)
    assert delivered == ["4*2"]
    await asyncio.sleep(PAUSE * 2)

    assert delivered == ["4*2"]


async def test_a_pound_key_on_its_own_is_delivered():
    delivered: list[str] = []
    sequence = KeypadSequence(delivered.append, pause=PAUSE)

    sequence.press("#")

    assert delivered == ["#"]


async def test_closing_drops_an_unfinished_sequence():
    delivered: list[str] = []
    sequence = KeypadSequence(delivered.append, pause=PAUSE)

    sequence.press("9")
    sequence.close()
    await asyncio.sleep(PAUSE * 2)

    assert delivered == []


async def test_only_the_callers_keys_are_delivered_until_it_stops():
    room = rtc.Room()
    delivered: list[str] = []
    stop = listen_to_keypad(room, "sip_caller", delivered.append)

    _press(room, "1#", _participant("sip_caller"))
    _press(room, "2#", _participant("sip_someone_else"))
    _press(room, "3#", None)
    stop()
    _press(room, "4#", _participant("sip_caller"))

    assert delivered == ["1"]
