import numpy as np

from check_bridge_call import FRAME, Envelope, envelope, heard, silent

RATE = 8000


def _speech(seconds: float, seed: int) -> np.ndarray:
    """Bursts of noise and pauses, like a spoken line."""
    rng = np.random.default_rng(seed)
    frames = int(seconds / FRAME)
    loud = rng.random(frames) > 0.4
    samples = rng.normal(0, 3000, frames * int(RATE * FRAME))
    return (samples * np.repeat(loud, int(RATE * FRAME))).astype(np.int16)


def _side(lines: list[tuple[float, np.ndarray]], seconds: float, start: float) -> Envelope:
    side = np.zeros(int(seconds * RATE), np.int16)
    for at, line in lines:
        side[int(at * RATE) : int(at * RATE) + len(line)] += line
    return envelope(side, RATE, start)


def test_a_line_is_heard_late_but_whole():
    line = _speech(3.0, 1)
    side = _side([(2.3, line)], 10.0, start=1000.0)
    found = heard(side, envelope(line, RATE), 1002.0)
    assert found["passed"]
    assert found["delay"] == 0.3


def test_another_line_in_its_place_is_not_the_line():
    line, other = _speech(3.0, 1), _speech(3.0, 2)
    side = _side([(2.0, other)], 10.0, start=0.0)
    assert not heard(side, envelope(line, RATE), 2.0)["passed"]


def test_silence_allows_a_stray_frame():
    side = _side([(5.0, _speech(0.02, 3) + 20000)], 10.0, start=0.0)
    assert silent(side, 0.0, 10.0)["passed"]
    assert not silent(_side([(2.0, _speech(3.0, 4))], 10.0, 0.0), 0.0, 10.0)["passed"]
