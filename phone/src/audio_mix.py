"""Several audio sources mixed into one, 20 ms at a time: 48 kHz mono 16-bit PCM.

Each source pushes what it receives; a clock takes one frame of each every 20 ms and sums them.
A source that is behind adds silence for the missing part, and one that runs ahead keeps at most
MAX_BUFFERED_FRAMES, dropping its oldest audio, so its delay stays bounded.
"""

from collections.abc import Hashable

import numpy as np

RATE = 48000
FRAME_SAMPLES = RATE // 50
FRAME_BYTES = FRAME_SAMPLES * 2
MAX_BUFFERED_FRAMES = 10


class AudioMix:
    def __init__(self) -> None:
        self._buffers: dict[Hashable, bytearray] = {}

    def add(self, source: Hashable) -> None:
        self._buffers[source] = bytearray()

    def remove(self, source: Hashable) -> None:
        self._buffers.pop(source, None)

    def push(self, source: Hashable, pcm: bytes) -> None:
        buffer = self._buffers.get(source)
        if buffer is None:
            return
        buffer += pcm
        # whole samples only, so the buffer stays aligned
        excess = (len(buffer) - MAX_BUFFERED_FRAMES * FRAME_BYTES) // 2 * 2
        if excess > 0:
            del buffer[:excess]

    def next_frame(self) -> bytes:
        mixed = np.zeros(FRAME_SAMPLES, dtype=np.int32)
        for buffer in self._buffers.values():
            # whole samples only: an odd byte left by a short push waits for the next one
            size = min(len(buffer), FRAME_BYTES) // 2 * 2
            take = bytes(buffer[:size])
            del buffer[:size]
            mixed[: size // 2] += np.frombuffer(take, dtype=np.int16)
        return np.clip(mixed, -32768, 32767).astype(np.int16).tobytes()
