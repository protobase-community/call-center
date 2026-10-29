"""Agent server entry point: `start` answers the phone calls LiveKit SIP puts in rooms."""

import os

from dotenv import load_dotenv
from livekit.agents import AgentServer, AgentSession, JobContext, cli, inference
from livekit.agents.voice.turn import TurnHandlingOptions
from livekit.plugins import openai

from agent_name import AGENT_NAME
from assistant import Assistant
from caller_info import CallerInfo
from keypad import keypad_message, listen_to_keypad
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
    # no remote session host: it would let any room participant read the instructions and drive
    # the session over lk.agent.session
    await session.start(
        agent=Assistant(tools=session_tools()),
        room=ctx.room,
        room_options=room_options(),
        session_host=False,
        # nothing is recorded, as a self-hosted server asks by default
        record=False,
    )

    caller.phone_identity = participant.identity
    stop_keypad = listen_to_keypad(
        ctx.room,
        participant.identity,
        lambda keys: session.generate_reply(user_input=keypad_message(keys)),
    )
    session.on("close", lambda _: stop_keypad())


if __name__ == "__main__":
    cli.run_app(server)
