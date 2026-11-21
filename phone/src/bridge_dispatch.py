"""Sends the bridge to a registered call's SIP room, through LiveKit's explicit agent dispatch.

A dispatch LiveKit refuses or cannot take leaves the call with the assistant: the failure is
logged, and the agent answers the caller as it would without staff.
"""

import logging

import aiohttp
from livekit import api

from bridge_name import BRIDGE_NAME, bridge_metadata


async def dispatch_bridge(lkapi: api.LiveKitAPI, room_name: str, call_id: int) -> None:
    request = api.CreateAgentDispatchRequest(
        agent_name=BRIDGE_NAME, room=room_name, metadata=bridge_metadata(call_id)
    )
    try:
        await lkapi.agent_dispatch.create_dispatch(request)
    except (api.TwirpError, aiohttp.ClientError) as error:
        logging.getLogger("call-center-agent").error(
            "no bridge for phone call %s: its dispatch failed: %s", call_id, error
        )
