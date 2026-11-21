import numpy as np

from audio_mix import FRAME_BYTES, FRAME_SAMPLES, MAX_BUFFERED_FRAMES, AudioMix


def _pcm(*samples: int) -> bytes:
    return np.array(samples, dtype=np.int16).tobytes()


def _samples(frame: bytes) -> list[int]:
    return np.frombuffer(frame, dtype=np.int16).tolist()


def test_no_source_is_silence():
    assert AudioMix().next_frame() == bytes(FRAME_BYTES)


def test_sources_are_summed_and_clipped():
    mix = AudioMix()
    mix.add("caller")
    mix.add("music")
    mix.push("caller", _pcm(1000, 30000, -30000))
    mix.push("music", _pcm(24, 30000, -30000))
    assert _samples(mix.next_frame())[:4] == [1024, 32767, -32768, 0]


def test_a_source_behind_adds_silence_and_its_audio_comes_next_frame():
    mix = AudioMix()
    mix.add("caller")
    mix.push("caller", _pcm(*range(1, FRAME_SAMPLES + 3)))
    assert _samples(mix.next_frame())[-1] == FRAME_SAMPLES
    assert _samples(mix.next_frame())[:3] == [FRAME_SAMPLES + 1, FRAME_SAMPLES + 2, 0]


def test_a_source_ahead_keeps_only_its_newest_audio():
    mix = AudioMix()
    mix.add("caller")
    for n in range(MAX_BUFFERED_FRAMES + 5):
        mix.push("caller", _pcm(*[n] * FRAME_SAMPLES))
    assert _samples(mix.next_frame())[0] == 5


def test_a_removed_or_unknown_source_is_not_heard():
    mix = AudioMix()
    mix.add("caller")
    mix.remove("caller")
    mix.push("caller", _pcm(5))
    mix.push("stranger", _pcm(5))
    assert mix.next_frame() == bytes(FRAME_BYTES)
