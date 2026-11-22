"""The SIP room's audio and the bridge's way into it, through LiveKit's rtc.

Each audio track of the room, the caller's, the assistant's and the hold music, feeds one mix,
which the bridge sends into the Protobase call. What comes back from the call plays in the room
as one track of the bridge's own, which LiveKit SIP mixes into what the caller hears.
"""

import asyncio
import time
from collections.abc import Hashable

from livekit import rtc

from audio_mix import FRAME_SAMPLES, RATE, AudioMix

# the room's buffer before LiveKit sends the bridge's audio; small, so staff are heard promptly
QUEUE_MS = 100


async def feed_room_track(track: rtc.Track, mix: AudioMix, source: Hashable) -> None:
    """Until the track ends, or the task is cancelled when the bridge unsubscribes from it."""
    stream = rtc.AudioStream(track, sample_rate=RATE, num_channels=1)
    mix.add(source)
    try:
        async for event in stream:
            mix.push(source, event.frame.data.tobytes())
    finally:
        mix.remove(source)
        await stream.aclose()


def room_source() -> rtc.AudioSource:
    return rtc.AudioSource(RATE, 1, queue_size_ms=QUEUE_MS)


async def play_mix(mix: AudioMix, source: rtc.AudioSource) -> None:
    """Sends one 20 ms frame of the mix every 20 ms into the room, until cancelled."""
    start = time.monotonic()
    sent = 0
    while True:
        frame = rtc.AudioFrame(mix.next_frame(), RATE, 1, FRAME_SAMPLES)
        await source.capture_frame(frame)
        sent += FRAME_SAMPLES
        await asyncio.sleep(start + sent / RATE - time.monotonic())
