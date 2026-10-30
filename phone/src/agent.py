"""Agent server entry point: `start` answers the phone calls LiveKit SIP puts in rooms."""

import os

from dotenv import load_dotenv
from livekit.agents import (
    AgentServer,
    AgentSession,
    BackgroundAudioPlayer,
    JobContext,
    cli,
    inference,
)
from livekit.agents.voice.turn import TurnHandlingOptions
from livekit.plugins import openai

from agent_name import AGENT_NAME
from assistant import Assistant
from call_center import CallCenter
from call_center_settings import call_center_settings
from call_ending import CallEnding
from caller_info import CallerInfo
from hold_queue import HoldQueue
from keypad import listen_to_keypad
from pin_entry import PinEntry, route_keys
from queue_settings import queue_settings
from room_options import room_options
from tools import session_tools

load_dotenv()

MODEL = "gpt-realtime-2.1"
# the built-in realtime voice the agent speaks with
VOICE = "marin"

# A phone line has no echo cancellation or noise suppression, unlike a browser. Replayed through
# gpt-realtime-2.1, a phone call's line noise started "speech" that cut the agent off under every
# eagerness and noise reduction of the model's own detection. LiveKit's VAD heard the same noise as
# 0.06 to 0.4 s of speech, and every real barge-in as at least 0.5 s; far_field dropped one more
# noise turn than near_field. LiveKit's audio turn detector judged a third of phone turns, finished
# ones too, as likely to go on, and each of those waited its 2.5 s maximum before the reply; a 1 s
# maximum caps that wait.
NOISE_REDUCTION = "far_field"
MIN_SPEECH = 0.3
MAX_DELAY = 1.0

# read at startup, so a missing key stops the server before any call
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError(f"OPENAI_API_KEY is not set; {MODEL} needs it")
call_center = CallCenter(call_center_settings(os.environ))
hold_settings = queue_settings(os.environ)

# its health and /worker pages stay on loopback, also where the host's network is shared
server = AgentServer(host="127.0.0.1")


def phone_turns() -> TurnHandlingOptions:
    return {
        # pinned: unpinned it picks LiveKit's cloud model in dev mode, which a self-hosted
        # server's keys cannot reach
        "turn_detection": inference.TurnDetector(version="v1-mini"),
        "endpointing": {"max_delay": MAX_DELAY},  # type: ignore[typeddict-item]
        # client-side turns would turn on LiveKit's adaptive interruption, which runs in LiveKit's
        # cloud only; plain voice activity interrupts instead
        "interruption": {"mode": "vad"},
    }


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    caller = CallerInfo()
    participant = await ctx.wait_for_participant()
    # the number LiveKit SIP gives the caller; None when it has none, such as a withheld number
    caller_number = participant.attributes.get("sip.phoneNumber") or None
    call_id = await call_center.register_call(ctx.room.name, caller_number)
    caller.call_id = call_id
    call_ending = CallEnding(lambda: call_center.end_call(call_id))
    ctx.add_shutdown_callback(call_ending.wait)

    session = AgentSession(
        # the model's turn_detection stays unset, which lets the session switch it off for
        # LiveKit's turn detector
        llm=openai.realtime.RealtimeModel(
            model=MODEL,
            voice=VOICE,
            api_key=api_key,
            input_audio_noise_reduction=NOISE_REDUCTION,
        ),
        userdata=caller,
        turn_handling=phone_turns(),
        # the session's default VAD, but a sound shorter than MIN_SPEECH does not start a turn
        vad=inference.VAD(model="silero", min_speech_duration=MIN_SPEECH),
    )

    def to_model(message: str) -> None:
        session.generate_reply(user_input=message)

    pin_entry = PinEntry(call_center, caller, to_model)
    # its own track in the caller's room, where the hold music plays
    player = BackgroundAudioPlayer()
    hold_queue = HoldQueue(
        player,
        hold_settings.music_file,
        hold_settings.max_wait_minutes,
        session.input.set_audio_enabled,
        to_model,
    )
    # no remote session host: it would let any room participant read the instructions and drive
    # the session over lk.agent.session
    await session.start(
        agent=Assistant(tools=session_tools(call_center, pin_entry, hold_queue)),
        room=ctx.room,
        room_options=room_options(),
        session_host=False,
        # nothing is recorded, as a self-hosted server asks by default
        record=False,
    )

    await player.start(room=ctx.room)
    ctx.add_shutdown_callback(player.aclose)

    caller.phone_identity = participant.identity
    keys = route_keys(pin_entry, lambda: hold_queue.waiting, to_model)
    stop_keypad = listen_to_keypad(ctx.room, participant.identity, keys)

    def on_close(_: object) -> None:
        stop_keypad()
        pin_entry.close()
        hold_queue.end_wait()
        call_ending.start()

    session.on("close", on_close)


if __name__ == "__main__":
    cli.run_app(server)
