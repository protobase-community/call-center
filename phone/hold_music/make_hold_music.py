"""Writes the hold music, a looped arpeggio over eight bars, as a 16-bit mono WAV.

usage: make_hold_music.py <out.wav>

Every note is synthesized here, from sine partials that decay, so the recording is self-made. Notes
that ring past the last bar wrap around to the first, so the file loops without a click.
Standard library only.
"""

import math
import struct
import sys
import wave

SAMPLE_RATE = 24000
BEAT = 60 / 92
# a bar is eight eighth notes
EIGHTH = BEAT / 2
# MIDI note numbers of each bar's chord, lowest first
CHORDS = [
    [60, 64, 67, 71],  # Cmaj7
    [57, 60, 64, 67],  # Am7
    [62, 65, 69, 72],  # Dm7
    [55, 59, 62, 65],  # G7
    [60, 64, 67, 71],  # Cmaj7
    [57, 60, 64, 67],  # Am7
    [53, 57, 60, 64],  # Fmaj7
    [55, 59, 62, 65],  # G7
]
# which chord tone each eighth note plays, up and back down an octave
PATTERN = [0, 1, 2, 3, 4, 3, 2, 1]
PEAK = 0.5


def frequency(note: int) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def add_note(samples: list[float], start: float, note: int, length: float, level: float) -> None:
    """A soft keyboard tone: three partials under a short attack and an exponential decay."""
    base = frequency(note)
    first = round(start * SAMPLE_RATE)
    for i in range(round(length * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        envelope = min(1.0, t / 0.01) * math.exp(-t / (length / 4))
        tone = (
            math.sin(2 * math.pi * base * t)
            + 0.4 * math.sin(2 * math.pi * 2 * base * t)
            + 0.15 * math.sin(2 * math.pi * 3 * base * t)
        )
        samples[(first + i) % len(samples)] += level * envelope * tone


def hold_music() -> list[float]:
    bar = 8 * EIGHTH
    samples = [0.0] * round(len(CHORDS) * bar * SAMPLE_RATE)
    for index, chord in enumerate(CHORDS):
        start = index * bar
        # the bass an octave below the chord's root, held over the bar
        add_note(samples, start, chord[0] - 12, bar * 1.5, 0.6)
        for step, tone in enumerate(PATTERN):
            note = chord[tone % 4] + 12 * (tone // 4)
            add_note(samples, start + step * EIGHTH, note, EIGHTH * 6, 0.35)
    loudest = max(abs(s) for s in samples)
    return [s * PEAK / loudest for s in samples]


def write(path: str, samples: list[float]) -> None:
    with wave.open(path, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(struct.pack(f"<{len(samples)}h", *(round(s * 32767) for s in samples)))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: make_hold_music.py <out.wav>")
    write(sys.argv[1], hold_music())
