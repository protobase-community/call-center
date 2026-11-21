"""The name the bridge registers under, and the job the agent dispatches it with.

The agent dispatches it explicitly to a call's SIP room once the app registered the call, with
the call's id in the dispatch's metadata, so the bridge never joins a room on its own.
"""

import json

BRIDGE_NAME = "call-center-bridge"


def bridge_metadata(call_id: int) -> str:
    return json.dumps({"call_id": call_id})


def bridged_call(metadata: str) -> int:
    call_id = json.loads(metadata).get("call_id")
    if not isinstance(call_id, int):
        raise ValueError("The bridge's dispatch names no call id")
    return call_id
