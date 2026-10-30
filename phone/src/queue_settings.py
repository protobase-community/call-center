"""The hold music a waiting caller hears and how long they wait before the assistant comes back.

Both are read at startup, so a wrong one stops the agent before any call.
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

MUSIC_VARIABLE = "HOLD_MUSIC_FILE"
MAX_WAIT_VARIABLE = "MAX_WAIT_MINUTES"
# the self-made recording in phone/hold_music, see its README for its licence
DEFAULT_MUSIC = Path(__file__).resolve().parent.parent / "hold_music" / "hold-music.ogg"
DEFAULT_MAX_WAIT_MINUTES = 5


@dataclass(frozen=True)
class QueueSettings:
    # an audio file LiveKit Agents decodes, played in a loop
    music_file: str
    max_wait_minutes: int


def queue_settings(environ: Mapping[str, str]) -> QueueSettings:
    return QueueSettings(music_file=_music_file(environ), max_wait_minutes=_max_wait(environ))


def _music_file(environ: Mapping[str, str]) -> str:
    path = environ.get(MUSIC_VARIABLE) or str(DEFAULT_MUSIC)
    if not os.path.isfile(path):
        raise ValueError(f"{MUSIC_VARIABLE} names no file: give the path of an audio file")
    return path


def _max_wait(environ: Mapping[str, str]) -> int:
    text = environ.get(MAX_WAIT_VARIABLE, "")
    if not text:
        return DEFAULT_MAX_WAIT_MINUTES
    if not re.fullmatch(r"[0-9]+", text) or int(text) == 0:
        raise ValueError(f"{MAX_WAIT_VARIABLE} must be a positive whole number of minutes")
    return int(text)
