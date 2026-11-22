"""A Protobase member's audio into a mix: their WebRTC track, decoded, as 48 kHz mono PCM."""

from collections.abc import Hashable

from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame

from audio_mix import RATE, AudioMix
from mono_pcm import MonoPcm


async def feed_member(track: MediaStreamTrack, mix: AudioMix, source: Hashable) -> None:
    """Until the member's track ends, or the task is cancelled when the bridge stops hearing it."""
    pcm = MonoPcm(RATE)
    mix.add(source)
    try:
        while True:
            try:
                frame = await track.recv()
            except MediaStreamError:
                return
            if not isinstance(frame, AudioFrame):
                raise TypeError("A member's audio track gave a frame that is not audio")
            mix.push(source, pcm.convert(frame))
    finally:
        mix.remove(source)
