"""An audio mix as an aiortc track, so the bridge publishes it into the Protobase call.

It sends one 20 ms frame of the mix every 20 ms, silence when no source has audio.
"""

import asyncio
import fractions
import time

from aiortc import MediaStreamTrack
from av import AudioFrame

from audio_mix import FRAME_SAMPLES, RATE, AudioMix


class MixTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, mix: AudioMix) -> None:
        super().__init__()
        self._mix = mix
        self._start: float | None = None
        self._pts = 0

    async def recv(self) -> AudioFrame:
        if self._start is None:
            self._start = time.monotonic()
        else:
            self._pts += FRAME_SAMPLES
            await asyncio.sleep(self._start + self._pts / RATE - time.monotonic())
        frame = AudioFrame(format="s16", layout="mono", samples=FRAME_SAMPLES)
        frame.planes[0].update(self._mix.next_frame())
        frame.pts = self._pts
        frame.sample_rate = RATE
        frame.time_base = fractions.Fraction(1, RATE)
        return frame
