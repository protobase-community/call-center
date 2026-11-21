import numpy as np

from audio_mix import FRAME_SAMPLES, RATE, AudioMix
from mix_track import MixTrack


async def test_frames_carry_the_mix_with_running_timestamps():
    mix = AudioMix()
    mix.add("caller")
    mix.push("caller", np.full(FRAME_SAMPLES * 2, 7, dtype=np.int16).tobytes())
    track = MixTrack(mix)
    first = await track.recv()
    second = await track.recv()
    assert (first.pts, second.pts) == (0, FRAME_SAMPLES)
    assert first.sample_rate == RATE
    assert np.all(second.to_ndarray() == 7)
