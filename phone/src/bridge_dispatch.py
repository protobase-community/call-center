"""Sends the bridge to a registered call's SIP room, through LiveKit's explicit agent dispatch."""

from livekit import api

from bridge_name import BRIDGE_NAME, bridge_metadata


async def dispatch_bridge(lkapi: api.LiveKitAPI, room_name: str, call_id: int) -> None:
    request = api.CreateAgentDispatchRequest(
        agent_name=BRIDGE_NAME, room=room_name, metadata=bridge_metadata(call_id)
    )
    await lkapi.agent_dispatch.create_dispatch(request)
