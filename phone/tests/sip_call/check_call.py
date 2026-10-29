"""Checks a recorded SIPp call: the agent greeted, then answered the caller's spoken question.

usage: check_call.py <pcap> <caller media port> <out dir>

Prints one JSON line, writes the agent's side to <out dir>/agent.wav and exits 1 when the
greeting or the reply is missing. Standard library only, so it runs on the SIPp image.
"""

import json
import math
import struct
import sys
import wave
from collections.abc import Iterator
from dataclasses import dataclass

SAMPLE_RATE = 8000
LOUD_RMS = 300
# silences shorter than this stay inside one stretch of speech
STRETCH_GAP = 0.5
LINK_ETHERNET = 1
LINK_LINUX_COOKED = 113
# what newer tcpdump writes for -i any
LINK_LINUX_COOKED_V2 = 276
PCMU = 0
PCMA = 8


def decode_alaw(byte: int) -> int:
    byte ^= 0x55
    value = (byte & 0x0F) << 4
    segment = (byte & 0x70) >> 4
    if segment == 0:
        value += 8
    elif segment == 1:
        value += 0x108
    else:
        value = (value + 0x108) << (segment - 1)
    return value if byte & 0x80 else -value


def decode_ulaw(byte: int) -> int:
    byte = ~byte & 0xFF
    value = (((byte & 0x0F) << 3) + 0x84) << ((byte & 0x70) >> 4)
    return 0x84 - value if byte & 0x80 else value - 0x84


DECODE = {PCMA: [decode_alaw(b) for b in range(256)], PCMU: [decode_ulaw(b) for b in range(256)]}


@dataclass
class Audio:
    at: float
    samples: list[int]

    @property
    def loud(self) -> bool:
        rms = math.sqrt(sum(s * s for s in self.samples) / len(self.samples))
        return rms > LOUD_RMS


def udp_packets(pcap: bytes) -> Iterator[tuple[float, int, int, bytes]]:
    """Yields (time, source port, destination port, payload) for each IPv4 UDP packet."""
    magic = struct.unpack("<I", pcap[:4])[0]
    endian = "<" if magic == 0xA1B2C3D4 else ">"
    link = struct.unpack(endian + "I", pcap[20:24])[0]
    header = {LINK_ETHERNET: 14, LINK_LINUX_COOKED: 16, LINK_LINUX_COOKED_V2: 20}.get(link)
    if header is None:
        raise ValueError(f"unsupported pcap link type {link}")

    offset = 24
    while offset + 16 <= len(pcap):
        seconds, micros, length, _ = struct.unpack(endian + "IIII", pcap[offset : offset + 16])
        frame = pcap[offset + 16 + header : offset + 16 + length]
        offset += 16 + length
        if len(frame) < 28 or frame[0] >> 4 != 4 or frame[9] != 17:
            continue
        ip_length = (frame[0] & 0x0F) * 4
        source, destination = struct.unpack(">HH", frame[ip_length : ip_length + 4])
        yield seconds + micros / 1e6, source, destination, frame[ip_length + 8 :]


def rtp_samples(packet: bytes) -> list[int] | None:
    """Decodes a G.711 RTP packet; None for anything else, such as telephone-event."""
    if len(packet) < 12 or packet[0] >> 6 != 2:
        return None
    table = DECODE.get(packet[1] & 0x7F)
    payload = packet[12 + 4 * (packet[0] & 0x0F) :]
    if table is None or not payload:
        return None
    return [table[b] for b in payload]


def split_call(pcap: bytes, caller_port: int) -> tuple[list[Audio], list[Audio]]:
    """Returns (caller, agent) audio, timed from the first audio packet of the call."""
    caller: list[Audio] = []
    agent: list[Audio] = []
    for at, source, destination, payload in udp_packets(pcap):
        samples = rtp_samples(payload)
        if samples is None:
            continue
        if source == caller_port:
            caller.append(Audio(at, samples))
        elif destination == caller_port:
            agent.append(Audio(at, samples))
    start = min((a.at for a in caller + agent), default=0.0)
    for audio in caller + agent:
        audio.at -= start
    return caller, agent


def stretches(audio: list[Audio]) -> list[tuple[float, float]]:
    """Merges loud packets into (start, end) stretches of speech."""
    merged: list[tuple[float, float]] = []
    for packet in audio:
        if not packet.loud:
            continue
        end = packet.at + len(packet.samples) / SAMPLE_RATE
        if merged and packet.at - merged[-1][1] <= STRETCH_GAP:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((packet.at, end))
    return merged


def verdict(caller: list[Audio], agent: list[Audio]) -> dict:
    spoken = stretches(caller)
    answered = stretches(agent)
    question = (spoken[0][0], spoken[-1][1]) if spoken else None
    greeting = [s for s in answered if question and s[0] < question[0]]
    reply = [s for s in answered if question and s[0] > question[1]]

    missing = []
    if question is None:
        missing.append("the caller's question")
    if not greeting:
        missing.append("a greeting before the question")
    if not reply:
        missing.append("a reply after the question")
    return {
        "passed": not missing,
        "missing": missing,
        "greeting_at": round(greeting[0][0], 2) if greeting else None,
        "question": [round(t, 2) for t in question] if question else None,
        "reply_at": round(reply[0][0], 2) if reply else None,
        "packets": {"caller": len(caller), "agent": len(agent)},
        "loud_packets": {
            "caller": sum(a.loud for a in caller),
            "agent": sum(a.loud for a in agent),
        },
    }


def write_wav(path: str, audio: list[Audio]) -> None:
    """Writes the audio at its arrival times, so pauses stay where they were."""
    end = max((round(a.at * SAMPLE_RATE) + len(a.samples) for a in audio), default=0)
    samples = [0] * end
    for packet in audio:
        start = round(packet.at * SAMPLE_RATE)
        samples[start : start + len(packet.samples)] = packet.samples
    with wave.open(path, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def main(pcap_path: str, caller_port: int, out_dir: str) -> int:
    with open(pcap_path, "rb") as file:
        caller, agent = split_call(file.read(), caller_port)
    write_wav(f"{out_dir}/agent.wav", agent)
    result = verdict(caller, agent)
    print(json.dumps(result))
    if result["missing"]:
        print("missing: " + ", ".join(result["missing"]), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: check_call.py <pcap> <caller media port> <out dir>")
    sys.exit(main(sys.argv[1], int(sys.argv[2]), sys.argv[3]))
