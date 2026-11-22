"""Checks run.sh's calls through the bridge, from what each side recorded.

usage: check_bridge_call.py <out dir> <clips dir>

The caller's side is the SIPp call's pcap: what the caller sent and what LiveKit SIP sent back,
the room's whole mix. The staff member's side is Chromium's recording of the caller's member in
the Protobase call, with the times of what the staff member did. Both use this machine's clock.

- hold: the caller waits on hold with music, then a staff member joins and says a line. The music
  was on before the join and is gone after it; the caller hears the staff line and not their own;
  the staff member hears the caller's line and not their own; the assistant says nothing.
- staff-first: the staff member joins while the assistant has the caller, so the music never
  starts; the same lines, then the staff member leaves and the assistant speaks again.

A line is heard when most of its window is loud and the loudness follows the clip's own (the
correlation of their 20 ms envelopes); a side is silent when nearly all of a window is quiet.
Prints one JSON object and exits 1 when a check fails.
"""

import json
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sip_call"))
from check_call import rtp_samples, split_call, udp_packets  # noqa: E402

FRAME = 0.02
# 16-bit RMS of a 20 ms frame that counts as sound, as tests/sip_call's checks take it
LOUD_RMS = 300.0
# where the caller's timeline puts its lines (run.sh passes the same seconds to bridge_call.sh)
CALLER_LINES = {"hold": {"caller-line": 50.0}, "staff-first": {"person": 16.0, "caller-line": 30.0}}
# how late a line may arrive on the other side: the network, jitter buffers and the bridge's mix
MAX_DELAY = 1.5
HEARD_SHARE = 0.5
HEARD_CORRELATION = 0.5
SILENT_SHARE = 0.05
# the music and the assistant need a moment to stop once staff join
SETTLE = 2.0
# the assistant speaks again within this many seconds after the staff member leaves
BACK_WITHIN = 15.0


@dataclass
class Envelope:
    """20 ms RMS levels of a recording, from `start` (seconds since the epoch)."""

    start: float
    levels: np.ndarray

    def window(self, start: float, end: float) -> np.ndarray:
        first = max(0, int(round((start - self.start) / FRAME)))
        last = max(first, int(round((end - self.start) / FRAME)))
        return self.levels[first:last]

    def loud_share(self, start: float, end: float) -> float:
        window = self.window(start, end)
        return float(np.mean(window > LOUD_RMS)) if len(window) else 0.0


def envelope(samples: np.ndarray, rate: int, start: float = 0.0) -> Envelope:
    size = int(rate * FRAME)
    count = len(samples) // size
    frames = samples[: count * size].astype(float).reshape(count, size)
    return Envelope(start, np.sqrt(np.mean(frames**2, axis=1)))


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path)) as read:
        if read.getsampwidth() != 2 or read.getnchannels() != 1:
            raise ValueError(f"{path} is not 16-bit mono")
        return np.frombuffer(read.readframes(read.getnframes()), np.int16), read.getframerate()


def heard(side: Envelope, clip: Envelope, start: float) -> dict:
    """Whether `clip`, said at `start`, is in `side`, at the delay that matches it best."""
    best = {"share": 0.0, "correlation": 0.0, "delay": None}
    for lag in range(int(MAX_DELAY / FRAME) + 1):
        at = start + lag * FRAME
        if at < side.start:
            # the recording starts later: a later delay may still find the whole line
            continue
        window = side.window(at, at + len(clip.levels) * FRAME)
        if len(window) < len(clip.levels):
            break
        correlation = float(np.corrcoef(np.log1p(window), np.log1p(clip.levels))[0, 1])
        if correlation > best["correlation"]:
            share = float(np.mean(window > LOUD_RMS))
            best = {"share": share, "correlation": correlation, "delay": round(lag * FRAME, 2)}
    best["passed"] = best["share"] >= HEARD_SHARE and best["correlation"] >= HEARD_CORRELATION
    return {k: round(v, 2) if isinstance(v, float) else v for k, v in best.items()}


def silent(side: Envelope, start: float, end: float) -> dict:
    share = side.loud_share(start, end)
    return {"loud_share": round(share, 3), "passed": share <= SILENT_SHARE}


def caller_side(pcap: Path, caller_port: int) -> tuple[Envelope, float]:
    """What the caller heard, and when their timeline started (their first packet)."""
    data = pcap.read_bytes()
    sent, received = split_call(data, caller_port)
    if not sent or not received:
        raise ValueError(f"{pcap} holds no audio both ways")
    # split_call times the packets from the first; the staff side has this machine's clock
    epoch = next(
        at
        for at, source, destination, payload in udp_packets(data)
        if caller_port in (source, destination) and rtp_samples(payload) is not None
    )
    for audio in sent + received:
        audio.at += epoch
    start = received[0].at
    # each packet is 20 ms, placed at the time it came, so a lost one leaves a quiet frame
    levels = np.zeros(int(round((received[-1].at - start) / FRAME)) + 1)
    for audio in received:
        samples = np.array(audio.samples, float)
        levels[int(round((audio.at - start) / FRAME))] = np.sqrt(np.mean(samples**2))
    return Envelope(start, levels), sent[0].at


def staff_side(webm: Path, recording_started: float) -> Envelope:
    wav = webm.with_suffix(".wav")
    decode = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(webm), "-ac", "1", "-ar", "16000"]
    subprocess.run([*decode, str(wav)], check=True)
    samples, rate = read_wav(wav)
    return envelope(samples, rate, recording_started)


def _events(staff: dict, kind: str, detail: str | None = None) -> list[float]:
    return [
        e["at"] / 1000
        for e in staff["events"]
        if e["kind"] == kind and (detail is None or e.get("detail") == detail)
    ]


def check_call(out: Path, clips: dict[str, Envelope], name: str, caller_port: int) -> dict:
    staff = json.loads((out / f"{name}-staff.json").read_text())
    heard_by_caller, timeline_start = caller_side(out / f"{name}.pcap", caller_port)
    heard_by_staff = staff_side(out / f"{name}-staff.webm", _events(staff, "recording")[-1])
    joined = _events(staff, "joined")[0]
    said, said_end = _events(staff, "said_started")[0], _events(staff, "said_stopped")[0]
    lines = {n: timeline_start + at for n, at in CALLER_LINES[name].items()}
    caller_line = lines["caller-line"]
    caller_line_end = caller_line + len(clips["caller-line"].levels) * FRAME
    checks = {
        "caller hears the staff line": heard(heard_by_caller, clips["staff-line"], said),
        "staff hear the caller's line": heard(heard_by_staff, clips["caller-line"], caller_line),
        "staff do not hear their own line": silent(heard_by_staff, said, said_end + MAX_DELAY),
        "caller hears nothing between join and staff line": silent(
            heard_by_caller, joined + SETTLE, said
        ),
    }
    for line, at in lines.items():
        end = at + len(clips[line].levels) * FRAME + MAX_DELAY
        checks[f"caller does not hear their own {line}"] = silent(heard_by_caller, at, end)
    if name == "hold":
        call_end = heard_by_caller.start + len(heard_by_caller.levels) * FRAME
        checks["caller hears nothing after the staff line until hanging up"] = silent(
            heard_by_caller, said_end + MAX_DELAY, call_end
        )
        checks["caller hears hold music before the join"] = {
            "loud_share": round(heard_by_caller.loud_share(joined - 5, joined), 3),
            "passed": heard_by_caller.loud_share(joined - 5, joined) >= 0.8,
        }
        recording_end = heard_by_staff.start + len(heard_by_staff.levels) * FRAME
        checks["staff hear no assistant after the caller's line"] = silent(
            heard_by_staff, caller_line_end + MAX_DELAY, recording_end
        )
    else:
        left = next(s["at"] / 1000 for s in staff["steps"] if s["step"] == "left")
        checks["caller hears nothing after the staff line until staff leave"] = silent(
            heard_by_caller, said_end + MAX_DELAY, left
        )
        back = heard_by_caller.loud_share(left, left + BACK_WITHIN)
        checks["assistant speaks again after staff leave"] = {
            "loud_share": round(back, 3),
            "passed": back >= 0.1,
        }
    return checks


def main(out: Path, clips_dir: Path, caller_port: int = 6000) -> int:
    clips = {
        name: envelope(*read_wav(clips_dir / f"{name}.wav"))
        for name in ("caller-line", "staff-line", "person")
    }
    results = {name: check_call(out, clips, name, caller_port) for name in CALLER_LINES}
    passed = all(c["passed"] for checks in results.values() for c in checks.values())
    print(json.dumps({"passed": passed, **results}, indent=1))
    return 0 if passed else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: check_bridge_call.py <out dir> <clips dir>")
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
