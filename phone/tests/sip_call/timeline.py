"""Writes a caller's whole side of a call as one clip: each line at its second, silence between.

usage: timeline.py <out.wav> <seconds> [<second>:<clip.wav> ...]

The clips are 16-bit mono at one rate, as the clips here are. SIPp then plays the timeline in one
stream, so the lines start when the scenario's clock says, whatever their lengths. Standard
library only, so it runs on the SIPp image.
"""

import sys
import wave


def timeline(out: str, seconds: float, lines: list[tuple[float, str]]) -> None:
    rate: int | None = None
    track = bytearray()
    for at, clip in sorted(lines):
        with wave.open(clip) as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2:
                raise ValueError(f"{clip} is not 16-bit mono")
            if rate not in (None, source.getframerate()):
                raise ValueError(f"{clip} has another rate than the clips before it")
            rate = source.getframerate()
            start = int(at * rate) * 2
            if start < len(track):
                raise ValueError(f"{clip} starts before the line before it ends")
            track += bytes(start - len(track)) + source.readframes(source.getnframes())
    rate = rate or 24000
    end = int(seconds * rate) * 2
    if end < len(track):
        raise ValueError("The lines go on past the end of the call")
    track += bytes(end - len(track))
    with wave.open(out, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(bytes(track))


def parse_line(text: str) -> tuple[float, str]:
    at, _, clip = text.partition(":")
    return float(at), clip


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: timeline.py <out.wav> <seconds> [<second>:<clip.wav> ...]")
    timeline(sys.argv[1], float(sys.argv[2]), [parse_line(a) for a in sys.argv[3:]])
