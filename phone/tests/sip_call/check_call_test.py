import json
import struct
import wave

import pytest

from check_call import (
    PCMA,
    PCMU,
    Audio,
    decode_alaw,
    decode_ulaw,
    main,
    rtp_samples,
    split_call,
    stretches,
    verdict,
)

CALLER_PORT = 6000
AGENT_PORT = 10004
LOUD_ALAW = 0xAA  # +32256
QUIET_ALAW = 0xD5  # +8


def test_decodes_g711_at_known_points():
    assert decode_alaw(0xD5) == 8
    assert decode_alaw(0x55) == -8
    assert decode_alaw(0xAA) == 32256
    assert decode_alaw(0x2A) == -32256
    assert decode_ulaw(0xFF) == 0
    assert decode_ulaw(0x80) == 32124
    assert decode_ulaw(0x00) == -32124


def rtp(payload_type, byte, count=160):
    return bytes([0x80, payload_type]) + struct.pack(">HII", 1, 0, 1) + bytes([byte] * count)


def test_rtp_samples_skips_what_is_not_g711():
    assert rtp_samples(rtp(PCMA, LOUD_ALAW, 4)) == [32256] * 4
    assert rtp_samples(rtp(PCMU, 0xFF, 2)) == [0, 0]
    assert rtp_samples(rtp(101, 0x00, 4)) is None
    assert rtp_samples(b"\x00" * 20) is None


def audio(at, loud):
    return Audio(at, [2000 if loud else 10] * 160)


def test_stretches_merge_short_pauses_only():
    packets = [audio(0.0, True), audio(0.02, True), audio(0.3, False), audio(0.4, True)]
    packets += [audio(2.0, True)]

    assert stretches(packets) == [pytest.approx((0.0, 0.42)), pytest.approx((2.0, 2.02))]


def test_verdict_passes_greeting_question_reply():
    caller = [audio(5.0, True), audio(6.0, True)]
    agent = [audio(1.0, True), audio(1.5, True), audio(8.0, True)]

    result = verdict(caller, agent)

    assert result["passed"]
    assert result["greeting_at"] == 1.0
    assert result["question"] == [5.0, 6.02]
    assert result["reply_at"] == 8.0


def test_verdict_fails_without_greeting():
    result = verdict([audio(5.0, True)], [audio(8.0, True)])

    assert not result["passed"]
    assert result["missing"] == ["a greeting before the question"]


def test_verdict_fails_without_reply():
    result = verdict([audio(5.0, True)], [audio(1.0, True), audio(8.0, False)])

    assert not result["passed"]
    assert result["missing"] == ["a reply after the question"]


def test_verdict_does_not_count_a_greeting_that_runs_through_the_question():
    agent = [audio(t / 10, True) for t in range(10, 80)]

    result = verdict([audio(5.0, True)], agent)

    assert result["missing"] == ["a reply after the question"]


def test_verdict_fails_when_only_the_caller_is_loud():
    caller = [audio(t, True) for t in (1.0, 5.0, 9.0)]
    agent = [audio(t, False) for t in (1.0, 5.0, 9.0)]

    result = verdict(caller, agent)

    assert result["missing"] == ["a greeting before the question", "a reply after the question"]


# link type: its number and the link header in front of each IPv4 packet
ETHERNET = (1, bytes(12) + b"\x08\x00")
LINUX_COOKED_V2 = (276, b"\x08\x00" + bytes(18))


def pcap(packets, link=ETHERNET):
    """Builds a little-endian pcap of (time, source port, destination port, payload)."""
    link_type, link_header = link
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, link_type)
    for at, source, destination, payload in packets:
        udp = struct.pack(">HHHH", source, destination, 8 + len(payload), 0) + payload
        ip = bytes([0x45, 0]) + struct.pack(">H", 20 + len(udp)) + bytes(5) + b"\x11" + bytes(10)
        frame = link_header + ip + udp
        seconds = int(at)
        micros = round((at - seconds) * 1e6)
        out += struct.pack("<IIII", seconds, micros, len(frame), len(frame)) + frame
    return out


CALL = [
    (100.0, AGENT_PORT, CALLER_PORT, rtp(PCMA, LOUD_ALAW)),
    (100.02, CALLER_PORT, AGENT_PORT, rtp(PCMA, QUIET_ALAW)),
    (103.0, CALLER_PORT, AGENT_PORT, rtp(PCMA, LOUD_ALAW)),
    (103.02, CALLER_PORT, AGENT_PORT, rtp(101, 0)),
    (106.0, AGENT_PORT, CALLER_PORT, rtp(PCMA, LOUD_ALAW)),
    (106.5, 5060, 5060, b"SIP/2.0 200 OK"),
]


@pytest.mark.parametrize("link", [ETHERNET, LINUX_COOKED_V2])
def test_split_call_by_caller_port(link):
    caller, agent = split_call(pcap(CALL, link), CALLER_PORT)

    assert [a.at for a in caller] == pytest.approx([0.02, 3.0])
    assert [a.at for a in agent] == pytest.approx([0.0, 6.0])


def test_main_checks_a_recorded_call_and_writes_the_agent_side(tmp_path, capsys):
    (tmp_path / "call.pcap").write_bytes(pcap(CALL))

    status = main(str(tmp_path / "call.pcap"), CALLER_PORT, str(tmp_path))

    assert status == 0
    assert json.loads(capsys.readouterr().out)["reply_at"] == 6.0
    with wave.open(str(tmp_path / "agent.wav")) as file:
        assert file.getframerate() == 8000
        assert file.getnframes() == 6 * 8000 + 160


def test_main_fails_a_call_where_only_the_caller_spoke(tmp_path):
    quiet_agent = [p for p in CALL if p[1] != AGENT_PORT]
    (tmp_path / "call.pcap").write_bytes(pcap(quiet_agent))

    assert main(str(tmp_path / "call.pcap"), CALLER_PORT, str(tmp_path)) == 1
