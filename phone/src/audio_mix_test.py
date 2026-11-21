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


def test_an_odd_byte_waits_for_the_rest_of_its_sample():
    mix = AudioMix()
    mix.add("caller")
    sample = _pcm(0x0201)
    mix.push("caller", sample[:1])
    assert mix.next_frame() == bytes(FRAME_BYTES)
    mix.push("caller", sample[1:])
    assert _samples(mix.next_frame())[0] == 0x0201


def test_dropping_old_audio_keeps_samples_whole():
    mix = AudioMix()
    mix.add("caller")
    audio = _pcm(*[0x0701] * (MAX_BUFFERED_FRAMES * FRAME_SAMPLES + 3))
    # an odd split, so the oldest audio is dropped while a sample is half there
    mix.push("caller", audio[:-1])
    mix.push("caller", audio[-1:])
    assert set(_samples(mix.next_frame())) == {0x0701}
