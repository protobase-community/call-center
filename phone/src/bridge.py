"""Bridge server entry point: `start` joins each phone call's SIP room to the Protobase call on
its record, so the caller and staff hear each other. See call_bridge.py.

The agent dispatches it to a call once the app registered the call. Every call's bridge runs on a
thread of this one process, so they share the phone line's session cookie.
"""

import logging
import os

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import AgentServer, AutoSubscribe, JobContext, JobExecutorType, cli
from websockets.exceptions import InvalidStatus

from bridge_join import JoinRefused, join_signed_in
from bridge_name import BRIDGE_NAME, bridged_call
from bridge_settings import bridge_settings
from call.call_client import CallClient, CallLeft, PeerModeUnsupported
from call_bridge import CallBridge
from phone_line_login import PhoneLineLogin, SignInFailed, SignInRefused

# the app's config/phone_calls/call-address.ts
SOCKET_PATH = "/api/functions/phone-call?phone_call="
# beside the agent's 8081, on loopback like it
PORT = 8082

load_dotenv()

logger = logging.getLogger("call-center-bridge")
# read at startup, so a missing account stops the bridge before any call
settings = bridge_settings(os.environ)
login = PhoneLineLogin(settings.origin, settings.email, settings.password)
socket_origin = settings.origin.replace("http", "ws", 1)

server = AgentServer(host="127.0.0.1", port=PORT, job_executor_type=JobExecutorType.THREAD)


@server.rtc_session(agent_name=BRIDGE_NAME)
async def entrypoint(ctx: JobContext) -> None:
    call_id = bridged_call(ctx.job.metadata)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    caller = await ctx.wait_for_participant(kind=rtc.ParticipantKind.PARTICIPANT_KIND_SIP)
    bridge = CallBridge(ctx.room, caller.identity)
    bridge.hear_room()
    open_call = bridge.open_call(f"{socket_origin}{SOCKET_PATH}{call_id}")
    client: CallClient | None = None

    async def join(cookie: str) -> CallClient:
        joining = open_call(cookie)
        await joining.join()
        return joining

    try:
        client = await join_signed_in(login, join)
        logger.info("joined the app's phone call %s", call_id)
        await bridge.bridge(client)
    except CallLeft as left:
        logger.info("left the app's phone call %s: %s", call_id, left.reason)
    except (SignInRefused, SignInFailed, JoinRefused, PeerModeUnsupported) as error:
        # the caller stays with the assistant; only the reason is reported, never a credential
        logger.error("no bridge for phone call %s: %s", call_id, error)
    except InvalidStatus as error:
        logger.error(
            "no bridge for phone call %s: its join answered %s",
            call_id,
            error.response.status_code,
        )
    finally:
        await bridge.close(client)
        ctx.shutdown("the bridge ended")


if __name__ == "__main__":
    cli.run_app(server)
