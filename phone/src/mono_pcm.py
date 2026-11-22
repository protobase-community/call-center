"""Decoded WebRTC audio (48 kHz Opus, stereo) as 16-bit mono PCM at the rate a consumer needs."""

from av import AudioFrame, AudioResampler


class MonoPcm:
    def __init__(self, rate: int) -> None:
        self._resampler = AudioResampler(format="s16", layout="mono", rate=rate)

    def convert(self, frame: AudioFrame) -> bytes:
        # a gap in the received timestamps (a lost packet) must not stall the resampler
        frame.pts = None
        return b"".join(out.to_ndarray().tobytes() for out in self._resampler.resample(frame))
