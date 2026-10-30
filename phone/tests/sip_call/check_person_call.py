"""Checks the call that asks for a person: hold music after the request, and the call waiting.

usage: check_person_call.py <pcap> <caller media port> <stand-in log> <out dir>

The music is the agent's side going on without a pause: from MUSIC_FROM to MUSIC_TO seconds after
the request ends, after the agent's sentence that it is finding someone, nearly every packet the
caller gets is loud, where speech leaves gaps. The stand-in of the app's phone line must have set
the last call `waiting`. Prints one JSON line, writes the agent's side to <out dir>/person-agent.wav
and exits 1 when either is missing. Standard library only, so it runs on the SIPp image.
"""

import json
import sys

from check_call import Audio, split_call, stretches, write_wav
from check_pin_call import last_call, read

MUSIC_FROM = 12.0
MUSIC_TO = 27.0
# the share of the window's 20 ms packets that must be loud, and that must have arrived
LOUD_SHARE = 0.9
PACKETS_PER_SECOND = 50


def music(caller: list[Audio], agent: list[Audio]) -> dict:
    spoken = stretches(caller)
    if not spoken:
        return {"request_end": None, "packets": 0, "loud": 0}
    request_end = spoken[-1][1]
    window = [a for a in agent if request_end + MUSIC_FROM <= a.at < request_end + MUSIC_TO]
    return {
        "request_end": round(request_end, 2),
        "packets": len(window),
        "loud": sum(a.loud for a in window),
    }


def heard_music(found: dict) -> bool:
    expected = (MUSIC_TO - MUSIC_FROM) * PACKETS_PER_SECOND
    return found["packets"] >= LOUD_SHARE * expected and found["loud"] >= LOUD_SHARE * expected


def waited(records: list[dict]) -> bool:
    return any(
        r["path"].endswith("/status") and r["status"] == 200 and r["answer"]["status"] == "waiting"
        for r in last_call(records)
    )


def main(pcap_path: str, caller_port: int, log_path: str, out_dir: str) -> int:
    with open(pcap_path, "rb") as file:
        caller, agent = split_call(file.read(), caller_port)
    write_wav(f"{out_dir}/person-agent.wav", agent)
    found = music(caller, agent)
    missing = []
    if found["request_end"] is None:
        missing.append("the caller's request")
    elif not heard_music(found):
        missing.append("hold music after the request")
    if not waited(read(log_path)):
        missing.append("the call waiting")
    print(json.dumps({"passed": not missing, "missing": missing, "music": found}))
    return 1 if missing else 0


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit("usage: check_person_call.py <pcap> <caller media port> <stand-in log> <out dir>")
    sys.exit(main(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]))
