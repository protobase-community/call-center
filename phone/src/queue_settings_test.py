from pathlib import Path

import pytest

from queue_settings import DEFAULT_MAX_WAIT_MINUTES, DEFAULT_MUSIC, queue_settings


def test_takes_the_bundled_music_and_the_default_wait_when_unset():
    settings = queue_settings({"MAX_WAIT_MINUTES": ""})

    assert settings.music_file == str(DEFAULT_MUSIC)
    assert DEFAULT_MUSIC.is_file()
    assert settings.max_wait_minutes == DEFAULT_MAX_WAIT_MINUTES


def test_reads_the_music_file_and_the_longest_wait(tmp_path: Path):
    music = tmp_path / "music.ogg"
    music.write_bytes(b"")

    settings = queue_settings({"HOLD_MUSIC_FILE": str(music), "MAX_WAIT_MINUTES": "12"})

    assert settings.music_file == str(music)
    assert settings.max_wait_minutes == 12


@pytest.mark.parametrize("value", ["0", "-3", "2.5", "five", " 5", "５"])
def test_stops_on_a_wait_that_is_no_positive_whole_number(value: str):
    with pytest.raises(ValueError, match="^MAX_WAIT_MINUTES must be a positive whole number"):
        queue_settings({"MAX_WAIT_MINUTES": value})


def test_stops_on_a_music_file_that_does_not_exist(tmp_path: Path):
    with pytest.raises(ValueError, match="^HOLD_MUSIC_FILE names no file"):
        queue_settings({"HOLD_MUSIC_FILE": str(tmp_path / "missing.ogg")})
