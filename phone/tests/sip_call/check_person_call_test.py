from check_call import Audio
from check_person_call import heard_music, music, waited

LOUD = [10_000] * 160
QUIET = [0] * 160


def _packets(start: float, end: float, samples: list[int], every: int = 1) -> list[Audio]:
    """20 ms packets from start to end; every nth one has the samples, the others are quiet."""
    count = round((end - start) * 50)
    return [Audio(start + i * 0.02, samples if i % every == 0 else QUIET) for i in range(count)]


REQUEST = _packets(8.0, 11.0, LOUD)


def test_hears_music_that_goes_on_after_the_request():
    agent = [*_packets(0.0, 3.0, LOUD), *_packets(12.0, 45.0, LOUD)]

    found = music(REQUEST, agent)

    assert found["request_end"] == 11.0
    assert heard_music(found)


def test_hears_no_music_in_speech_with_pauses_or_in_silence():
    speech = _packets(12.0, 45.0, LOUD, every=3)

    assert not heard_music(music(REQUEST, speech))
    assert not heard_music(music(REQUEST, _packets(12.0, 45.0, QUIET)))


def test_hears_no_music_once_the_line_goes_dead():
    assert not heard_music(music(REQUEST, _packets(12.0, 30.0, LOUD)))


def test_finds_no_request_from_a_silent_caller():
    assert music([], _packets(0.0, 45.0, LOUD))["request_end"] is None


def _status(call_id: int, status: str) -> dict:
    path = f"/calls/{call_id}/status"
    return {"method": "POST", "path": path, "status": 200, "answer": {"status": status}}


def _call(call_id: int) -> dict:
    return {"method": "POST", "path": "/calls", "status": 201, "answer": {"id": call_id}}


def test_sees_the_last_call_waiting():
    assert waited([_call(1), _call(2), _status(2, "waiting"), _status(2, "ended")])
    assert not waited([_call(1), _status(1, "waiting"), _call(2), _status(2, "ended")])
