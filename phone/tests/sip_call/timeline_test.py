import wave
from pathlib import Path

import pytest

from timeline import parse_line, timeline


def _clip(path: Path, samples: list[int], rate: int = 8000) -> str:
    with wave.open(str(path), "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(rate)
        clip.writeframes(b"".join(s.to_bytes(2, "little", signed=True) for s in samples))
    return str(path)


def _samples(path: Path) -> list[int]:
    with wave.open(str(path)) as read:
        data = read.readframes(read.getnframes())
    return [int.from_bytes(data[i : i + 2], "little", signed=True) for i in range(0, len(data), 2)]


def test_lines_start_at_their_second_with_silence_between(tmp_path: Path):
    line = _clip(tmp_path / "line.wav", [5] * 4000)
    timeline(str(tmp_path / "out.wav"), 2.0, [(1.0, line)])
    samples = _samples(tmp_path / "out.wav")
    assert len(samples) == 16000
    assert samples[7999] == 0
    assert samples[8000:12000] == [5] * 4000
    assert samples[12000:] == [0] * 4000


def test_overlapping_lines_are_refused(tmp_path: Path):
    line = _clip(tmp_path / "line.wav", [5] * 8000)
    with pytest.raises(ValueError, match="starts before"):
        timeline(str(tmp_path / "out.wav"), 3.0, [(0.0, line), (0.5, line)])


def test_a_line_is_a_second_and_a_clip():
    assert parse_line("8.5:person.wav") == (8.5, "person.wav")
