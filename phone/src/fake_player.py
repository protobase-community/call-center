"""A background audio player for tests: it records what it was asked to play and to stop."""

from dataclasses import dataclass


@dataclass
class FakePlaying:
    audio: str
    loop: bool
    stopped: bool = False

    def stop(self) -> None:
        self.stopped = True


class FakePlayer:
    def __init__(self) -> None:
        self.played: list[FakePlaying] = []

    def play(self, audio: str, *, loop: bool = False) -> FakePlaying:
        playing = FakePlaying(audio, loop)
        self.played.append(playing)
        return playing
